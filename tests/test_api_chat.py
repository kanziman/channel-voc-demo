"""Integration (issue #17) — chat retrieval-gating, all three branches.

Beyond per-endpoint checks: verifies the *relationship* between branches
(confidence ordering refuse < borderline < sufficient) and that the gate is
tied to the root-cause promotion threshold (§5-6), not just that each returns 200.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.graph import serve


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


def _patch(monkeypatch, search_fn, rootcause_fn):
    import src.server.routers.chat as mod
    monkeypatch.setattr(mod, "hybrid_search", search_fn)
    monkeypatch.setattr(mod, "compute_rootcauses", rootcause_fn)


def _ev(results, top_component):
    return {"query": "q", "top_component": top_component, "counts": {}, "results": results}


def _result(arms):
    return {"id": "c1", "dense": 0.5, "sparse": 1.0, "in_graph": True,
            "text": "t", "component": "billing", "severity": 3, "rrf": 0.04, "arms": arms}


_PROMOTED = [{"key": "rc_billing", "component": "billing", "frequency": 240,
              "revenue_at_risk_krw": 5982900, "projected_recoverable_krw": 2094015,
              "confidence_avg": 0.89, "hypothesis": "billing misconfig",
              "sample_conv_ids": ["c1"]}]


def _ask(client, monkeypatch, results, top_component, rcs):
    _patch(monkeypatch, lambda message, k: _ev(results, top_component), lambda write=False: rcs)
    return client.post("/api/chat", json={"message": "billing 문제?"}).json()


# ── branch behaviours (not just 200) ──────────────────────────────────────────
def test_sufficient_branch_answers_with_real_won_and_rc_confidence(client, monkeypatch):
    b = _ask(client, monkeypatch, [_result(["dense", "sparse", "graph"])], "billing", _PROMOTED)
    assert b["gate"] == "answer"
    assert b["confidence"] == 0.89                       # == rc.confidence_avg
    assert "5,982,900" in b["answer"] and "240" in b["answer"]
    assert b["subgraph_ref"]["root_cause_key"] == "rc_billing"


def test_zero_hits_branch_refuses_without_fabricating(client, monkeypatch):
    b = _ask(client, monkeypatch, [], None, [])
    assert b["gate"] == "refuse"
    assert b["confidence"] == 0.0
    assert "근거" in b["answer"]           # honest "no evidence", not an answer
    assert "5,982,900" not in b["answer"]  # nothing invented
    assert b["related_questions"]          # answerable-question chips offered


def test_borderline_branch_hedges_below_threshold(client, monkeypatch):
    # evidence exists but the component is NOT promoted (no rootcause) → hedge
    b = _ask(client, monkeypatch, [_result(["dense", "sparse", "graph"])], "orders", [])
    assert b["gate"] == "low_confidence"
    assert "⚠" in b["answer"] and "임계값" in b["answer"]
    assert 0.0 < b["confidence"] < 0.5


def test_confidence_orders_refuse_lt_borderline_lt_sufficient(client, monkeypatch):
    refuse = _ask(client, monkeypatch, [], None, [])["confidence"]
    border = _ask(client, monkeypatch, [_result(["dense", "sparse"])], "orders", [])["confidence"]
    suff = _ask(client, monkeypatch, [_result(["dense", "sparse", "graph"])], "billing", _PROMOTED)["confidence"]
    assert refuse < border < suff
