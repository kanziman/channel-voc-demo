"""TDD (issue #14) — POST /api/chat retrieval-gated generation.

hybrid_search + rootcause.compute are monkeypatched; tests drive the 3-branch
gating (refuse / low_confidence / answer) and the response envelope via the
mounted route.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.graph import serve


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


def _patch_search(monkeypatch, fn):
    import src.server.routers.chat as mod
    monkeypatch.setattr(mod, "hybrid_search", fn)


def _patch_rootcause(monkeypatch, fn):
    import src.server.routers.chat as mod
    monkeypatch.setattr(mod, "compute_rootcauses", fn)


def _ev(results, top_component=None):
    return {"query": "q", "top_component": top_component,
            "counts": {"dense": 0, "sparse": 0, "graph": 0}, "results": results}


def _result(rid, arms):
    return {"id": rid, "dense": 0.5 if "dense" in arms else None,
            "sparse": 1.0 if "sparse" in arms else None,
            "in_graph": "graph" in arms, "text": "t", "component": "billing",
            "severity": 3, "rrf": 0.04, "arms": arms}


# ── branch 1: refuse (0 hits) ─────────────────────────────────────────────────
def test_should_refuse_with_zero_confidence_and_chips_when_no_hits(client, monkeypatch):
    _patch_search(monkeypatch, lambda message, k: _ev([]))
    r = client.post("/api/chat", json={"message": "완전 무관한 질문"})
    assert r.status_code == 200
    b = r.json()
    assert b["gate"] == "refuse"
    assert b["confidence"] == 0.0
    assert b["arms"] == []
    assert b["related_questions"]  # non-empty
    assert b["interrupt_payload"] is None


# ── branch 2: low_confidence (evidence exists but component NOT promoted) ──────
def test_should_return_low_confidence_when_component_not_promoted(client, monkeypatch):
    _patch_search(monkeypatch,
                  lambda message, k: _ev([_result("c1", ["dense", "sparse", "graph"])], "orders"))
    _patch_rootcause(monkeypatch, lambda write=False: [])  # below promotion threshold
    b = client.post("/api/chat", json={"message": "약한 근거"}).json()
    assert b["gate"] == "low_confidence"
    assert 0.0 < b["confidence"] < 0.5
    assert "⚠" in b["answer"] and "임계값" in b["answer"]  # hedge marker + threshold
    assert b["subgraph_ref"]["top_component"] == "orders"
    assert "root_cause_key" not in b["subgraph_ref"]
    assert b["interrupt_payload"] is None
    assert b["related_questions"]


def test_should_not_leak_literal_none_when_top_component_missing(client, monkeypatch):
    _patch_search(monkeypatch, lambda message, k: _ev([_result("c1", ["dense"])], None))
    _patch_rootcause(monkeypatch, lambda write=False: [])
    b = client.post("/api/chat", json={"message": "x"}).json()
    assert b["gate"] == "low_confidence"
    assert "None" not in b["answer"]


# ── branch 3: answer (component promoted to a root cause) ──────────────────────
def test_should_answer_with_rootcause_krw_when_promoted(client, monkeypatch):
    _patch_search(monkeypatch,
                  lambda message, k: _ev([_result("c1", ["dense", "sparse", "graph"])], "billing"))
    _patch_rootcause(monkeypatch, lambda write=False: [
        {"key": "rc_billing", "component": "billing", "frequency": 240,
         "revenue_at_risk_krw": 5982900, "projected_recoverable_krw": 2094015,
         "confidence_avg": 0.89, "hypothesis": "billing misconfig",
         "sample_conv_ids": ["c1", "c2"]},
    ])
    b = client.post("/api/chat", json={"message": "billing 문제 근거"}).json()
    assert b["gate"] == "answer"
    assert b["confidence"] == 0.89
    assert "5,982,900" in b["answer"]        # real ₩ value surfaced
    assert "240" in b["answer"]
    assert b["subgraph_ref"]["root_cause_key"] == "rc_billing"
    assert b["interrupt_payload"] is None


# ── envelope + trace ──────────────────────────────────────────────────────────
def test_should_expose_arms_union_and_subgraph_ref(client, monkeypatch):
    _patch_search(monkeypatch, lambda message, k: _ev(
        [_result("c1", ["dense", "graph"]), _result("c2", ["sparse"])], "billing"))
    _patch_rootcause(monkeypatch, lambda write=False: [])
    b = client.post("/api/chat", json={"message": "x"}).json()
    assert set(b["arms"]) == {"dense", "sparse", "graph"}
    assert b["subgraph_ref"]["conversation_ids"]


def test_should_accept_optional_thread_id(client, monkeypatch):
    _patch_search(monkeypatch, lambda message, k: _ev([]))
    assert client.post("/api/chat", json={"message": "hi", "thread_id": "t-1"}).status_code == 200
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 200


def test_should_call_hybrid_search_with_message(client, monkeypatch):
    seen = {}
    _patch_search(monkeypatch, lambda message, k: seen.update(message=message) or _ev([]))
    client.post("/api/chat", json={"message": "specific text"})
    assert seen["message"] == "specific text"


def test_should_return_error_envelope_when_message_missing(client):
    r = client.post("/api/chat", json={})
    assert r.status_code == 422
    assert "error" in r.json() and "detail" not in r.json()


def test_should_mount_chat_route_on_serve_app():
    assert "/api/chat" in serve.app.openapi()["paths"]


@pytest.mark.parametrize("results,top", [([], None),
                                         ([_result("c", ["dense"])], "billing"),
                                         ([_result("c", ["dense", "sparse"])], "billing")])
def test_related_questions_always_non_empty(client, monkeypatch, results, top):
    _patch_search(monkeypatch, lambda message, k: _ev(results, top))
    _patch_rootcause(monkeypatch, lambda write=False: [])
    b = client.post("/api/chat", json={"message": "x"}).json()
    assert b["related_questions"]
