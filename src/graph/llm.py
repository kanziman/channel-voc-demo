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
        api_key=config.OPENROUTER_API_KEY,
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


def embed(texts: Iterable[str]) -> list[list[float]]:
    """Local ONNX embeddings → list of 384-d vectors (order-preserving)."""
    return [vec.tolist() for vec in _embedder().embed(list(texts))]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
