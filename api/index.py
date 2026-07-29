"""Vercel Python serverless entrypoint (§B deploy).

Vercel's Python runtime auto-detects files under `api/` and serves a module-level
ASGI `app`. We re-export the existing FastAPI app (all /api/* routers) unchanged.

Required project env (set in the Vercel dashboard):
  NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD   — Aura connection
  OPENROUTER_API_KEY                            — chat/hypothesis LLM
  VOC_EMBED_BACKEND=api                         — use the hosted embedder (no fastembed)
  VOC_EMBED_API_URL / VOC_EMBED_API_KEY         — OpenAI-compatible bge-small @384d
  VOC_CACHE_DIR=/tmp/graph_cache                — writable cache dir (read-only FS otherwise)
"""
import pathlib
import sys

# The function bundle roots at the repo; make `src` importable.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.graph.serve import app  # noqa: E402  (re-exported ASGI app for Vercel)

__all__ = ["app"]
