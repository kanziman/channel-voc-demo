"""TDD (issue #13) — POST /api/search/hybrid router [WRAP].

retriever.hybrid_search hits Neo4j + fastembed, so it is monkeypatched; these
tests verify only the router/adapter contract and that it is mounted on the app.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.graph import serve

# a realistic hybrid_search return (one 3-arm result)
FAKE = {
    "query": "refund",
    "top_component": "billing",
    "counts": {"dense": 12, "sparse": 12, "graph": 6},
    "results": [
        {"id": "conv_01", "dense": 0.82, "sparse": 3.1, "in_graph": True,
         "text": "i need a refund", "component": "billing", "severity": 4,
         "rrf": 0.0491, "arms": ["dense", "sparse", "graph"]},
    ],
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


def _patch(monkeypatch, fn):
    # the router imports the symbol; patch it where it is looked up
    import src.server.routers.search as mod
    monkeypatch.setattr(mod, "hybrid_search", fn)


def test_should_return_200_with_full_shape_when_query_valid(client, monkeypatch):
    _patch(monkeypatch, lambda query, k: FAKE)
    r = client.post("/api/search/hybrid", json={"query": "refund", "k": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "refund"
    assert body["top_component"] == "billing"
    assert body["counts"] == {"dense": 12, "sparse": 12, "graph": 6}
    assert len(body["results"]) == 1


def test_should_preserve_arms_and_rrf_per_result(client, monkeypatch):
    _patch(monkeypatch, lambda query, k: FAKE)
    r = client.post("/api/search/hybrid", json={"query": "refund"})
    res0 = r.json()["results"][0]
    assert res0["arms"] == ["dense", "sparse", "graph"]
    assert res0["rrf"] == 0.0491


def test_should_call_hybrid_search_with_query_and_k(client, monkeypatch):
    seen = {}
    _patch(monkeypatch, lambda query, k: seen.update(query=query, k=k) or FAKE)
    client.post("/api/search/hybrid", json={"query": "orders", "k": 3})
    assert seen == {"query": "orders", "k": 3}


def test_should_default_k_to_6_when_k_omitted(client, monkeypatch):
    seen = {}
    _patch(monkeypatch, lambda query, k: seen.update(k=k) or FAKE)
    client.post("/api/search/hybrid", json={"query": "orders"})
    assert seen["k"] == 6


def test_should_return_error_envelope_when_query_missing(client):
    r = client.post("/api/search/hybrid", json={})
    assert r.status_code == 422
    assert "error" in r.json() and "detail" not in r.json()


def test_should_return_error_envelope_when_hybrid_search_raises(monkeypatch):
    def boom(query, k):
        raise RuntimeError("neo4j down")
    _patch(monkeypatch, boom)
    c = TestClient(serve.app, raise_server_exceptions=False)
    r = c.post("/api/search/hybrid", json={"query": "x"})
    assert r.status_code == 500
    assert r.json() == {"error": "neo4j down"}


def test_should_mount_hybrid_route_on_serve_app():
    assert "/api/search/hybrid" in serve.app.openapi()["paths"]
