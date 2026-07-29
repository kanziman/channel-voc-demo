"""TDD (issue #16) — /api/agent rootcauses / run / dispatch.

The interrupt→resume roundtrip uses a REAL Neo4j checkpointer (that is the AC:
run and dispatch are separate requests sharing state only via Neo4j). compute
and dispatch_issue are monkeypatched so no LLM/GitHub/graph writes happen.
Skipped when Neo4j is unreachable.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.graph import db, serve


def _neo4j_available() -> bool:
    try:
        db.driver().verify_connectivity()
        return True
    except BaseException:
        return False


pytestmark = pytest.mark.skipif(not _neo4j_available(), reason="Neo4j not reachable")

_RCS = [
    {"key": "rc_billing", "component": "billing", "hypothesis": "billing misconfig",
     "revenue_at_risk_krw": 5982900, "confidence_avg": 0.89, "sample_conv_ids": ["c1", "c2"]},
    {"key": "rc_orders", "component": "orders", "hypothesis": "orders flakiness",
     "revenue_at_risk_krw": 4200000, "confidence_avg": 0.81, "sample_conv_ids": ["c3"]},
]


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    import src.server.routers.agent as mod
    monkeypatch.setattr(mod, "compute_rootcauses", lambda write=False: _RCS)
    # dispatch_issue records the call instead of writing to Neo4j/GitHub
    dispatched = []
    def fake_dispatch(draft, live=False):
        dispatched.append(draft["root_cause_key"])
        return {"key": f"act_{draft['root_cause_key']}", "status": "drafted",
                "root_cause_key": draft["root_cause_key"], "url": None}
    monkeypatch.setattr(mod, "dispatch_issue", fake_dispatch)
    c = TestClient(serve.app)
    c._dispatched = dispatched  # type: ignore[attr-defined]
    return c


def _cleanup(thread_id: str) -> None:
    db.run_write("MATCH (n:AgentCheckpoint {thread_id:$t}) DETACH DELETE n", t=thread_id)
    db.run_write("MATCH (w:AgentCheckpointWrite {thread_id:$t}) DETACH DELETE w", t=thread_id)


# ── rootcauses ────────────────────────────────────────────────────────────────
def test_should_return_rootcauses_from_compute(client):
    b = client.get("/api/agent/rootcauses").json()
    assert [r["key"] for r in b["rootcauses"]] == ["rc_billing", "rc_orders"]


# ── run → interrupt ───────────────────────────────────────────────────────────
def test_should_start_graph_and_return_thread_id_with_interrupt(client):
    b = client.post("/api/agent/run", json={}).json()
    try:
        assert b["thread_id"].startswith("agent-")
        assert b["dispatched"] is None
        cands = b["interrupt"]["candidates"]
        assert {c["root_cause_key"] for c in cands} == {"rc_billing", "rc_orders"}
    finally:
        _cleanup(b["thread_id"])


# ── roundtrip: run → dispatch(approve) resumes from Neo4j ──────────────────────
def test_should_resume_and_dispatch_all_when_approved(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        d = client.post("/api/agent/dispatch",
                        json={"thread_id": tid, "decision": "approve"}).json()
        assert d["status"] == "dispatched"
        assert {x["root_cause_key"] for x in d["dispatched"]} == {"rc_billing", "rc_orders"}
        assert set(client._dispatched) == {"rc_billing", "rc_orders"}
    finally:
        _cleanup(tid)


def test_should_dispatch_nothing_when_rejected(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        d = client.post("/api/agent/dispatch",
                        json={"thread_id": tid, "decision": "reject"}).json()
        assert d["status"] == "rejected"
        assert d["dispatched"] == []
        assert client._dispatched == []
    finally:
        _cleanup(tid)


def test_should_dispatch_only_selected_keys(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        d = client.post("/api/agent/dispatch",
                        json={"thread_id": tid, "decision": ["rc_orders"]}).json()
        assert [x["root_cause_key"] for x in d["dispatched"]] == ["rc_orders"]
        assert client._dispatched == ["rc_orders"]
    finally:
        _cleanup(tid)


def test_should_422_when_thread_id_missing(client):
    r = client.post("/api/agent/dispatch", json={"decision": "approve"})
    assert r.status_code == 422
    assert "error" in r.json() and "detail" not in r.json()


def test_should_404_when_thread_id_unknown(client):
    r = client.post("/api/agent/dispatch",
                    json={"thread_id": "agent-does-not-exist", "decision": "approve"})
    assert r.status_code == 404
    assert r.json() == {"error": "not found"}  # app standardises all 404 bodies


def test_should_return_empty_without_interrupt_when_no_candidates(client, monkeypatch):
    import src.server.routers.agent as mod
    monkeypatch.setattr(mod, "compute_rootcauses", lambda write=False: [])
    b = client.post("/api/agent/run", json={}).json()
    assert b["interrupt"] is None and b["dispatched"] == []


def test_should_propagate_live_flag_to_dispatch_issue(client, monkeypatch):
    import src.server.routers.agent as mod
    seen = {}
    monkeypatch.setattr(mod, "dispatch_issue",
                        lambda draft, live=False: seen.update(live=live) or {"root_cause_key": draft["root_cause_key"]})
    run = client.post("/api/agent/run", json={"live": True}).json()
    tid = run["thread_id"]
    try:
        client.post("/api/agent/dispatch", json={"thread_id": tid, "decision": ["rc_billing"]})
        assert seen["live"] is True
    finally:
        _cleanup(tid)


@pytest.mark.parametrize("decision,expected", [
    (None, ["rc_billing", "rc_orders"]),
    ("approve", ["rc_billing", "rc_orders"]),
    ("all", ["rc_billing", "rc_orders"]),
    ("reject", []),
    ("none", []),
    ([], []),
    (["rc_orders"], ["rc_orders"]),
    ("rc_billing", ["rc_billing"]),   # single key as bare string
])
def test_approved_from_decision(decision, expected):
    from src.server.routers.agent import _approved_from_decision
    cands = [{"root_cause_key": "rc_billing"}, {"root_cause_key": "rc_orders"}]
    assert _approved_from_decision(decision, cands) == expected


def test_should_mount_agent_routes(client):
    paths = serve.app.openapi()["paths"]
    assert {"/api/agent/rootcauses", "/api/agent/run", "/api/agent/dispatch"} <= set(paths)
