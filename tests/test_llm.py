"""TDD (issue #53) — pluggable embedding backend for serverless deploy (방안 B).

llm.embed dispatches on config.EMBED_BACKEND: "local" (fastembed, dev + graph
load) vs "api" (hosted OpenAI-compatible bge-small @384d, no ONNX in the bundle).
The api path must NOT import fastembed. Both paths are order-preserving.
"""
from __future__ import annotations

import sys
import types

import pytest

from src.graph import config, llm


@pytest.fixture(autouse=True)
def _reset_embedder_cache():
    # _embedder is lru_cached; clear so backend switches take effect per test.
    llm._embedder.cache_clear()
    yield
    llm._embedder.cache_clear()


def test_should_use_local_backend_by_default(monkeypatch):
    monkeypatch.setattr(config, "EMBED_BACKEND", "local")
    called = {"local": 0}

    def _fake_local(texts):
        called["local"] += 1
        return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr(llm, "_embed_local", _fake_local)
    out = llm.embed(["a", "b"])
    assert called["local"] == 1
    assert len(out) == 2 and out[0] == [0.1, 0.2, 0.3]


def test_should_use_api_backend_when_configured(monkeypatch):
    monkeypatch.setattr(config, "EMBED_BACKEND", "api")
    seen = {}

    def _fake_api(texts):
        seen["texts"] = list(texts)
        return [[0.9] * config.EMBED_DIM for _ in texts]

    monkeypatch.setattr(llm, "_embed_api", _fake_api)
    out = llm.embed(["q1", "q2"])
    assert seen["texts"] == ["q1", "q2"]
    assert len(out) == 2 and len(out[0]) == config.EMBED_DIM


def test_api_backend_calls_openai_embeddings_with_hosted_config(monkeypatch):
    """The api backend routes through an OpenAI-compatible embeddings endpoint
    (base_url/api_key/model from config) — no fastembed import."""
    monkeypatch.setattr(config, "EMBED_BACKEND", "api")
    monkeypatch.setattr(config, "EMBED_API_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.setattr(config, "EMBED_API_KEY", "sk-test")

    captured = {}

    class _FakeEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def embed_documents(self, texts):
            return [[0.5] * config.EMBED_DIM for _ in texts]

    fake_mod = types.ModuleType("langchain_openai")
    fake_mod.OpenAIEmbeddings = _FakeEmbeddings
    fake_mod.ChatOpenAI = getattr(sys.modules.get("langchain_openai"), "ChatOpenAI", object)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)

    out = llm.embed(["결제 실패"])
    assert out == [[0.5] * config.EMBED_DIM]
    assert captured.get("base_url") == "https://api.deepinfra.com/v1/openai"
    assert captured.get("model") == config.EMBED_MODEL  # same bge-small → 384d, no re-index


def test_api_backend_does_not_import_fastembed(monkeypatch):
    """Guard the serverless size win: the api path must not pull fastembed."""
    monkeypatch.setattr(config, "EMBED_BACKEND", "api")

    class _FakeEmbeddings:
        def __init__(self, **kwargs):
            pass

        def embed_documents(self, texts):
            return [[0.0] * config.EMBED_DIM for _ in texts]

    fake_mod = types.ModuleType("langchain_openai")
    fake_mod.OpenAIEmbeddings = _FakeEmbeddings
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)
    # Sabotage fastembed import → if the api path touched it, this would raise.
    monkeypatch.setitem(sys.modules, "fastembed", None)

    out = llm.embed(["x"])
    assert len(out) == 1


def test_embed_one_returns_first_vector(monkeypatch):
    monkeypatch.setattr(config, "EMBED_BACKEND", "local")
    monkeypatch.setattr(llm, "_embed_local", lambda texts: [[1.0], [2.0]][: len(list(texts))])
    assert llm.embed_one("solo") == [1.0]
