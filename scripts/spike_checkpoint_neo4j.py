"""PHASE3 §5-3 spike: prove Neo4jCheckpointSaver works before building the rest.

Two checks the plan demands:
  1. put -> get_tuple round-trips a checkpoint faithfully.
  2. interrupt() -> *new process's* saver+app -> Command(resume=...) resumes and
     finishes. We simulate the process boundary by throwing away the first saver
     and compiled graph, then building fresh ones (new objects, same Neo4j) to
     resume the same thread_id. This is exactly the stateless HTTP run/dispatch.

Run:  .venv/bin/python -m scripts.spike_checkpoint_neo4j
Exit code 0 = both checks passed. Test nodes are cleaned up afterwards.
"""
from __future__ import annotations

import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.graph import config, db
from src.graph.checkpoint_neo4j import Neo4jCheckpointSaver

THREAD = f"spike-{int(time.time())}"


class S(TypedDict, total=False):
    steps: Annotated[list, operator.add]


def step_a(_s: S) -> dict:
    return {"steps": ["a"]}


def gate(_s: S) -> dict:
    decision = interrupt({"ask": "approve?"})   # ← pauses the whole graph here
    return {"steps": [f"gate:{decision}"]}


def step_b(_s: S) -> dict:
    return {"steps": ["b"]}


def build_app(saver: Neo4jCheckpointSaver):
    g = StateGraph(S)
    g.add_node("a", step_a)
    g.add_node("gate", gate)
    g.add_node("b", step_b)
    g.add_edge(START, "a")
    g.add_edge("a", "gate")
    g.add_edge("gate", "b")
    g.add_edge("b", END)
    return g.compile(checkpointer=saver)


def cleanup() -> None:
    db.run_write(
        "MATCH (n:AgentCheckpoint {thread_id:$tid}) DETACH DELETE n", tid=THREAD)
    db.run_write(
        "MATCH (w:AgentCheckpointWrite {thread_id:$tid}) DETACH DELETE w", tid=THREAD)


def main() -> int:
    config.require("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    Neo4jCheckpointSaver.setup()
    cfg = {"configurable": {"thread_id": THREAD}}

    print(f"▶ spike thread_id = {THREAD}\n")

    # ── Check 1: run to the interrupt with saver #1 ───────────────────────────
    saver1 = Neo4jCheckpointSaver()
    app1 = build_app(saver1)
    res1 = app1.invoke({"steps": []}, cfg)
    assert "__interrupt__" in res1, f"expected interrupt, got {res1}"
    payload = res1["__interrupt__"][0].value
    print(f"⏸  interrupted at gate; payload = {payload}")

    # get_tuple round-trip: the paused checkpoint must be readable and carry the
    # progress so far (step 'a' already applied) + a pending __interrupt__ write.
    tup = saver1.get_tuple(cfg)
    assert tup is not None, "get_tuple returned None right after put"
    assert tup.checkpoint["channel_values"].get("steps") == ["a"], \
        f"round-trip lost state: {tup.checkpoint['channel_values']}"
    assert any(c == "__interrupt__" for _t, c, _v in tup.pending_writes), \
        f"interrupt write not persisted: {tup.pending_writes}"
    print("✅ check 1: put→get_tuple round-trip OK "
          f"(state={tup.checkpoint['channel_values']['steps']}, "
          f"pending_writes={[c for _t,c,_v in tup.pending_writes]})")

    # ── Check 2: SIMULATE PROCESS RESTART — brand-new saver + app, same Neo4j ──
    del saver1, app1, res1
    saver2 = Neo4jCheckpointSaver()          # fresh object, no in-memory state
    app2 = build_app(saver2)
    res2 = app2.invoke(Command(resume="yes"), cfg)   # resume the paused thread
    assert "__interrupt__" not in res2, f"did not resume: {res2}"
    assert res2["steps"] == ["a", "gate:yes", "b"], f"bad final state: {res2['steps']}"
    print(f"✅ check 2: resumed across a fresh saver/app → steps = {res2['steps']}")

    print("\n🎉 SPIKE PASSED — Neo4jCheckpointSaver survives a process boundary.")
    return 0


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    finally:
        try:
            cleanup()
            print("🧹 cleaned up spike checkpoint nodes.")
        except Exception as e:  # noqa: BLE001
            print(f"cleanup warning: {e}")
    raise SystemExit(rc)
