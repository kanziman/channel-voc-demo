"""TDD (issue #11) — serve.py FastAPI migration.

hybrid_search hits Neo4j + fastembed, so it is monkeypatched here; these
tests exercise only the FastAPI route/contract layer (health, search,
error keys, CORS, port), which is what the static dashboard playground
depends on for regression.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.graph import config, serve

ORIGIN = {"Origin": "http://localhost"}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


# ── [정상] app ────────────────────────────────────────────────────────────
def test_should_expose_fastapi_app_when_imported():
    assert isinstance(serve.app, FastAPI)


# ── [정상] health ─────────────────────────────────────────────────────────
def test_should_return_status_ok_with_model_dim_when_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model"] == config.EMBED_MODEL
    assert body["dim"] == config.EMBED_DIM


# ── [정상/경계] search passthrough + k ────────────────────────────────────
def test_should_return_hybrid_search_payload_when_query_valid(client, monkeypatch):
    payload = {"query": "refund", "top_component": "billing", "results": [{"id": "x"}]}
    monkeypatch.setattr(serve, "hybrid_search", lambda query, k: payload)
    r = client.post("/search", json={"query": "refund", "k": 6})
    assert r.status_code == 200
    assert r.json() == payload


def test_should_default_k_to_6_when_k_omitted(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(serve, "hybrid_search",
                        lambda query, k: seen.update(query=query, k=k) or {"results": []})
    client.post("/search", json={"query": "orders"})
    assert seen["k"] == 6


def test_should_forward_k_when_k_given(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(serve, "hybrid_search",
                        lambda query, k: seen.update(k=k) or {"results": []})
    client.post("/search", json={"query": "orders", "k": 3})
    assert seen["k"] == 3


# ── [예외] search error contract ({"error": ...}) ─────────────────────────
def test_should_return_400_error_when_query_empty(client):
    r = client.post("/search", json={"query": ""})
    assert r.status_code == 400
    assert r.json() == {"error": "empty query"}


def test_should_return_400_error_when_query_whitespace(client):
    r = client.post("/search", json={"query": "   "})
    assert r.status_code == 400
    assert r.json() == {"error": "empty query"}


def test_should_return_500_error_when_hybrid_search_raises(client, monkeypatch):
    def boom(query, k):
        raise RuntimeError("neo4j down")
    monkeypatch.setattr(serve, "hybrid_search", boom)
    r = client.post("/search", json={"query": "x"})
    assert r.status_code == 500
    assert r.json() == {"error": "neo4j down"}


# ── [예외] error-envelope 일관성 ({"error"} 유지, {"detail"} 아님) ────────
def test_should_return_error_key_when_query_field_missing(client):
    r = client.post("/search", json={})
    assert r.status_code == 422
    body = r.json()
    assert "error" in body and "detail" not in body


def test_should_return_error_key_when_body_malformed(client):
    r = client.post("/search", content=b"not-json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert "error" in r.json() and "detail" not in r.json()


def test_should_return_not_found_error_when_unknown_route(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "not found"}


# ── [정상] CORS (dashboard cross-origin regression) ───────────────────────
def test_should_include_cors_allow_origin_header(client, monkeypatch):
    monkeypatch.setattr(serve, "hybrid_search", lambda query, k: {"results": []})
    r = client.post("/search", json={"query": "x"}, headers=ORIGIN)
    assert r.headers.get("access-control-allow-origin") == "*"


# ── [정상] main → uvicorn.run with config port ────────────────────────────
def test_should_run_uvicorn_with_search_port_when_main(monkeypatch):
    calls = {}
    monkeypatch.setattr(serve.uvicorn, "run",
                        lambda app, **kw: calls.update(app=app, **kw))
    serve.main()
    assert calls["app"] is serve.app
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == config.SEARCH_PORT


# ── [경계] vercel.json stays a static build (entrypoint 변경 불필요) ───────
def test_should_keep_vercel_static_build_without_python_function():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "vercel.json").read_text())
    assert cfg.get("framework") is None
    assert cfg.get("outputDirectory") == "public"
    assert "functions" not in cfg and "builds" not in cfg
