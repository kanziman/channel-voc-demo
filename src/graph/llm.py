"""Single LLM/embedding client factory (§2.3.1).

The whole PHASE2 codebase depends *only* on this module for model access:
  - chat()  → OpenRouter (OpenAI-compatible). Swap CHAT_MODEL to benchmark
              Claude / Gemini / Llama with zero code change.
  - embed() → local fastembed ONNX (bge-small-en-v1.5, 384d). No key, offline,
              deterministic — because OpenRouter serves no embedding endpoint.

A SQLite LLM cache makes chat calls deterministic + cheap on re-runs (demo
reproducibility). temperature is pinned to 0 everywhere.
"""
from __future__ import annotations

import functools
from typing import Iterable

from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from . import config

# Deterministic on-disk cache for all chat calls (keyed by prompt+model+params).
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
set_llm_cache(SQLiteCache(database_path=str(config.CACHE_DIR / "llm_cache.sqlite")))


@functools.lru_cache(maxsize=8)
def chat(model: str | None = None, temperature: float = 0.0) -> ChatOpenAI:
    """OpenRouter chat client. All extraction/generation flows through here."""
    config.require("OPENROUTER_API_KEY")
    return ChatOpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=SecretStr(config.OPENROUTER_API_KEY),
        model=model or config.CHAT_MODEL,
        temperature=temperature,
        timeout=60,
        max_retries=3,
        default_headers={
            # OpenRouter attribution headers (optional, harmless).
            "HTTP-Referer": "https://github.com/kanziman/channel-voc-demo",
            "X-Title": "Channel VOC Intelligence Dept",
        },
    )


@functools.lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=config.EMBED_MODEL)


def _embed_local(texts: list[str]) -> list[list[float]]:
    """Local fastembed ONNX (dev + graph loading)."""
    return [vec.tolist() for vec in _embedder().embed(texts)]


def _embed_api(texts: list[str]) -> list[list[float]]:
    """Hosted OpenAI-compatible embeddings — SAME bge-small model @384d, so the
    Neo4j vector index stays valid. Keeps the ONNX runtime out of the serverless
    bundle (§B deploy). Imports lazily so the api path never pulls fastembed."""
    from langchain_openai import OpenAIEmbeddings

    client = OpenAIEmbeddings(
        base_url=config.EMBED_API_URL,
        api_key=SecretStr(config.EMBED_API_KEY),
        model=config.EMBED_MODEL,
    )
    return client.embed_documents(texts)


def embed(texts: Iterable[str]) -> list[list[float]]:
    """384-d embeddings (order-preserving). Backend per config.EMBED_BACKEND:
    'local' fastembed | 'api' hosted OpenAI-compatible bge-small."""
    items = list(texts)
    if config.EMBED_BACKEND == "api":
        return _embed_api(items)
    return _embed_local(items)


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
