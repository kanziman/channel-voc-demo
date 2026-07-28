"""AC #12 spike, as pytest — Neo4jCheckpointSaver survives a process boundary.

Formalises scripts/spike_checkpoint_neo4j.py into the AC-required test:
  1. put → get_tuple round-trips the paused checkpoint (state + pending writes).
  2. interrupt() → *fresh* saver+graph (simulated process restart) →
     Command(resume=...) resumes and finishes on the same thread_id.

Requires a reachable Neo4j (NEO4J_* env); skipped otherwise so the suite stays
green on machines without the store.
"""
from __future__ import annotations

import operator
import time
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.graph import db
from src.graph.checkpoint_neo4j import Neo4jCheckpointSaver


def _neo4j_available() -> bool:
    try:
        db.driver().verify_connectivity()
        return True
    except BaseException:  # config.require raises SystemExit when env is unset
        return False


pytestmark = pytest.mark.skipif(
    not _neo4j_available(), reason="Neo4j not reachable (set NEO4J_* env)"
)


# ── minimal graph with a human-in-the-loop interrupt ──────────────────────────
class S(TypedDict, total=False):
    steps: Annotated[list, operator.add]


def _step_a(_s: S) -> dict:
    return {"steps": ["a"]}


def _gate(_s: S) -> dict:
    decision = interrupt({"ask": "approve?"})  # pauses the whole graph here
    return {"steps": [f"gate:{decision}"]}


def _step_b(_s: S) -> dict:
    return {"steps": ["b"]}


def _build_app(saver: Neo4jCheckpointSaver):
    g = StateGraph(S)
    g.add_node("a", _step_a)
    g.add_node("gate", _gate)
    g.add_node("b", _step_b)
    g.add_edge(START, "a")
    g.add_edge("a", "gate")
    g.add_edge("gate", "b")
    g.add_edge("b", END)
    return g.compile(checkpointer=saver)


@pytest.fixture()
def thread() -> str:
    tid = f"test-cp-{time.time_ns()}"
    yield tid
    db.run_write("MATCH (n:AgentCheckpoint {thread_id:$t}) DETACH DELETE n", t=tid)
    db.run_write("MATCH (w:AgentCheckpointWrite {thread_id:$t}) DETACH DELETE w", t=tid)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Neo4jCheckpointSaver.setup()


# ── AC 3.1: put → get_tuple round-trip ────────────────────────────────────────
def test_should_roundtrip_state_and_pending_writes_when_get_tuple_after_interrupt(thread):
    cfg = {"configurable": {"thread_id": thread}}
    saver = Neo4jCheckpointSaver()
    res = _build_app(saver).invoke({"steps": []}, cfg)
    assert "__interrupt__" in res

    tup = saver.get_tuple(cfg)
    assert tup is not None
    # progress before the gate must have been persisted...
    assert tup.checkpoint["channel_values"].get("steps") == ["a"]
    # ...and the pause must be recorded as a pending __interrupt__ write.
    assert any(ch == "__interrupt__" for _t, ch, _v in tup.pending_writes)


# ── AC 3.2: interrupt → process restart → resume ──────────────────────────────
def test_should_resume_and_finish_when_new_saver_resumes_same_thread(thread):
    cfg = {"configurable": {"thread_id": thread}}
    Neo4jCheckpointSaver()  # noqa — saver #1 lifecycle
    app1 = _build_app(Neo4jCheckpointSaver())
    assert "__interrupt__" in app1.invoke({"steps": []}, cfg)

    # simulate the process boundary: brand-new saver + graph, same Neo4j.
    app2 = _build_app(Neo4jCheckpointSaver())
    res2 = app2.invoke(Command(resume="yes"), cfg)
    assert "__interrupt__" not in res2
    assert res2["steps"] == ["a", "gate:yes", "b"]


# ── list + empty-thread edges ─────────────────────────────────────────────────
def test_should_list_checkpoints_newest_first_when_thread_has_history(thread):
    cfg = {"configurable": {"thread_id": thread}}
    saver = Neo4jCheckpointSaver()
    _build_app(saver).invoke({"steps": []}, cfg)  # writes several checkpoints
    tuples = list(saver.list(cfg))
    assert len(tuples) >= 2
    ids = [t.config["configurable"]["checkpoint_id"] for t in tuples]
    assert ids == sorted(ids, reverse=True)  # newest (lexicographically largest) first


def test_should_return_none_when_thread_unknown():
    saver = Neo4jCheckpointSaver()
    assert saver.get_tuple({"configurable": {"thread_id": "no-such-thread-xyz"}}) is None


def test_should_return_empty_when_list_thread_unknown():
    saver = Neo4jCheckpointSaver()
    assert list(saver.list({"configurable": {"thread_id": "no-such-thread-xyz"}})) == []


# ── async API (AC "+ async 변형") ─────────────────────────────────────────────
async def test_should_roundtrip_via_async_api_and_resume_with_ainvoke(thread):
    cfg = {"configurable": {"thread_id": thread}}
    saver = Neo4jCheckpointSaver()
    app1 = _build_app(saver)
    assert "__interrupt__" in await app1.ainvoke({"steps": []}, cfg)

    tup = await saver.aget_tuple(cfg)
    assert tup is not None and tup.checkpoint["channel_values"].get("steps") == ["a"]

    app2 = _build_app(Neo4jCheckpointSaver())  # fresh saver, async resume
    res2 = await app2.ainvoke(Command(resume="yes"), cfg)
    assert res2["steps"] == ["a", "gate:yes", "b"]


# ── list: limit / before / filter ─────────────────────────────────────────────
def test_should_apply_limit_and_before_when_listing(thread):
    cfg = {"configurable": {"thread_id": thread}}
    saver = Neo4jCheckpointSaver()
    _build_app(saver).invoke({"steps": []}, cfg)
    all_tuples = list(saver.list(cfg))
    assert len(all_tuples) >= 2

    assert len(list(saver.list(cfg, limit=1))) == 1

    newest = all_tuples[0].config
    older = list(saver.list(cfg, before=newest))
    newest_id = newest["configurable"]["checkpoint_id"]
    assert older and all(
        t.config["configurable"]["checkpoint_id"] < newest_id for t in older
    )


def test_should_filter_by_metadata_when_listing(thread):
    cfg = {"configurable": {"thread_id": thread}}
    saver = Neo4jCheckpointSaver()
    _build_app(saver).invoke({"steps": []}, cfg)
    tuples = list(saver.list(cfg))
    # pick a real (key, value) from an existing checkpoint's metadata
    key, val = next(iter(tuples[0].metadata.items()))
    matched = list(saver.list(cfg, filter={key: val}))
    assert matched and all(t.metadata.get(key) == val for t in matched)
    # an impossible filter yields nothing (proves filter is honoured, not ignored)
    assert list(saver.list(cfg, filter={"__nope__": "__never__"})) == []


# ── AC "blob은 Base64 직렬화" — verify raw stored string decodes as base64 ─────
def test_should_store_checkpoint_blob_as_valid_base64(thread):
    import base64

    cfg = {"configurable": {"thread_id": thread}}
    _build_app(Neo4jCheckpointSaver()).invoke({"steps": []}, cfg)
    rows = db.run(
        "MATCH (n:AgentCheckpoint {thread_id:$t}) RETURN n.checkpoint_blob AS b LIMIT 1",
        t=thread,
    )
    assert rows and base64.b64decode(rows[0]["b"], validate=True)
