"""Central config for the PHASE2 GraphRAG package.

Single source of truth for paths, model names, env loading, and the safety
gates promoted from PHASE1 (DISPATCH_REQUIRE_APPROVAL / *_CONFIDENCE_THRESHOLD).
All secrets live in the repo-root .env (gitignored); this module loads it once.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = REPO_ROOT / "out"
CACHE_DIR = REPO_ROOT / "data" / "graph_cache"     # deterministic extraction/embedding cache
CONVERSATIONS = DATA_DIR / "conversations.jsonl"    # 1,200 labelled convs (PHASE1 ingest)
HELDOUT = DATA_DIR / "heldout.jsonl"                # 600 held-out for benchmark

# Load repo-root .env exactly once (never overrides already-set process env).
load_dotenv(REPO_ROOT / ".env", override=False)

# ── Models (§2.3.1) ──────────────────────────────────────────────────────────
# All chat/extraction/generation → OpenRouter (OpenAI-compatible surface).
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CHAT_MODEL = os.getenv("VOC_CHAT_MODEL", "openai/gpt-4o-mini")
# Embeddings → local fastembed ONNX (no key, deterministic, offline after 1st pull).
EMBED_MODEL = os.getenv("VOC_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384

# ── Neo4j ────────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Safety gates (promoted from PHASE1 → real LangGraph interrupt gate) ───────
DISPATCH_REQUIRE_APPROVAL = os.getenv("DISPATCH_REQUIRE_APPROVAL", "true").lower() == "true"
DISPATCH_CONFIDENCE_THRESHOLD = float(os.getenv("DISPATCH_CONFIDENCE_THRESHOLD", "0.7"))

# Root-cause promotion thresholds (§2.1): a Component becomes a RootCause only
# when enough distinct conversations implicate it (aggregation, not a label).
ROOTCAUSE_MIN_CONVERSATIONS = int(os.getenv("VOC_ROOTCAUSE_MIN_CONVS", "8"))

# Local live-search endpoint (serve.py) — powers the dashboard's real-time
# hybrid search playground (query embedded by the SAME fastembed model).
SEARCH_PORT = int(os.getenv("VOC_SEARCH_PORT", "8756"))


def require(*names: str) -> None:
    """Raise a clear error if any required env var is empty."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise SystemExit(
            f"Missing required env var(s): {', '.join(missing)}. "
            f"Set them in {REPO_ROOT / '.env'} (see .env.example)."
        )
