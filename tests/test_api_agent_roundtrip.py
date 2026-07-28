"""Integration (issue #17) — the full stateless agent roundtrip.

Not a per-endpoint unit test: this exercises cross-endpoint consistency
(GET /rootcauses ↔ /run interrupt payload), the *physical* durability of the
paused checkpoint in Neo4j, and that a separate /dispatch request resumes that
same thread. Real Neo4j; compute/dispatch_issue monkeypatched.
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
     "revenue_at_risk_krw": 5982900, "confidence_avg": 0.89, "sample_conv_ids": ["c1"]},
    {"key": "rc_orders", "component": "orders", "hypothesis": "orders flakiness",
     "revenue_at_risk_krw": 4200000, "confidence_avg": 0.81, "sample_conv_ids": ["c3"]},
]


@pytest.fixture()
def client(monkeypatch):
    import src.server.routers.agent as mod
    monkeypatch.setattr(mod, "compute_rootcauses", lambda write=False: _RCS)
    dispatched: list[str] = []
    monkeypatch.setattr(mod, "dispatch_issue",
                        lambda draft, live=False: dispatched.append(draft["root_cause_key"])
                        or {"root_cause_key": draft["root_cause_key"], "status": "drafted"})
    c = TestClient(serve.app)
    c._dispatched = dispatched  # type: ignore[attr-defined]
    return c


def _checkpoint_count(thread_id: str) -> int:
    return db.run("MATCH (n:AgentCheckpoint {thread_id:$t}) RETURN count(n) AS n",
                  t=thread_id)[0]["n"]


def _cleanup(thread_id: str) -> None:
    db.run_write("MATCH (n:AgentCheckpoint {thread_id:$t}) DETACH DELETE n", t=thread_id)
    db.run_write("MATCH (w:AgentCheckpointWrite {thread_id:$t}) DETACH DELETE w", t=thread_id)


def test_rootcauses_keys_match_run_interrupt_candidates(client):
    rc_keys = {r["key"] for r in client.get("/api/agent/rootcauses").json()["rootcauses"]}
    run = client.post("/api/agent/run", json={}).json()
    try:
        cand_keys = {c["root_cause_key"] for c in run["interrupt"]["candidates"]}
        assert cand_keys == rc_keys  # the two endpoints agree on the work set
    finally:
        _cleanup(run["thread_id"])


def test_checkpoint_is_persisted_to_neo4j_after_run(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        assert _checkpoint_count(tid) >= 1  # the pause physically survives the request
    finally:
        _cleanup(tid)


def test_dispatch_resumes_thread_and_dispatches_run_candidates(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        run_keys = {c["root_cause_key"] for c in run["interrupt"]["candidates"]}
        d = client.post("/api/agent/dispatch",
                        json={"thread_id": tid, "decision": "approve"}).json()
        assert {x["root_cause_key"] for x in d["dispatched"]} == run_keys
        assert set(client._dispatched) == run_keys
    finally:
        _cleanup(tid)


def test_dispatch_reject_resumes_same_thread_and_dispatches_nothing(client):
    run = client.post("/api/agent/run", json={}).json()
    tid = run["thread_id"]
    try:
        d = client.post("/api/agent/dispatch",
                        json={"thread_id": tid, "decision": "reject"}).json()
        assert d["status"] == "rejected" and d["dispatched"] == []
        assert client._dispatched == []
    finally:
        _cleanup(tid)
