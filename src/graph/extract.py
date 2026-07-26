"""LLM structured extraction (§2.1) — the semantic upgrade over TF-IDF.

Per conversation → {intent, component, symptoms[], severity, confidence}.
- OpenRouter chat via llm.chat(), with_structured_output (function calling),
  temperature=0 → deterministic.
- Own JSON disk cache keyed by (model, prompt-version, conv-id): re-runs are
  instant and reproducible, independent of any network.

Usage:
  python -m src.graph.extract            # extract all conversations (cached)
  python -m src.graph.extract --limit 20 # smoke a subset
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import config, llm
from .taxonomy import COMPONENTS, INTENT_TO_COMPONENT, INTENTS

PROMPT_VERSION = "v1"
_EXTRACT_DIR = config.CACHE_DIR / "extractions" / config.CHAT_MODEL.replace("/", "_") / PROMPT_VERSION


class Extraction(BaseModel):
    """Structured VOC signal extracted from one customer conversation."""

    intent: Literal[tuple(INTENTS)] = Field(  # type: ignore[valid-type]
        description="The single best-matching customer intent from the fixed list."
    )
    component: Literal[tuple(COMPONENTS)] = Field(  # type: ignore[valid-type]
        description="The product surface this conversation implicates."
    )
    symptoms: list[str] = Field(
        description="1-3 short lowercase noun phrases naming the concrete problem "
        "the customer reports (e.g. 'password reset email not arriving'). Empty if none.",
        default_factory=list,
    )
    severity: int = Field(
        ge=1, le=5, description="1=trivial question, 5=blocking/angry/at-risk-of-churn."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Your confidence in the intent label (0-1)."
    )


_SYSTEM = (
    "You are a VOC analyst for a customer-support platform. Extract structured signal "
    "from a single customer conversation. Choose exactly one intent and one component "
    "from the provided enums. Symptoms must be concrete, deduplicated, lowercase noun "
    "phrases grounded in the customer's words — never invent details. Be strict."
)


def _customer_text(conv: dict) -> str:
    return " ".join(m["text"] for m in conv["messages"] if m["role"] == "customer").strip()


def _cache_path(conv_id: str) -> Path:
    return _EXTRACT_DIR / f"{conv_id}.json"


def _structured():
    return llm.chat().with_structured_output(Extraction)


def extract_one(conv: dict, use_cache: bool = True) -> dict:
    """Extract one conversation → dict (cached to disk)."""
    cid = conv["id"]
    cp = _cache_path(cid)
    if use_cache and cp.exists():
        return json.loads(cp.read_text())

    text = _customer_text(conv)
    msg = f"Conversation id: {cid}\nCustomer said:\n\"\"\"\n{text}\n\"\"\""
    result: Extraction = _structured().invoke([("system", _SYSTEM), ("human", msg)])
    out = result.model_dump()
    # Ground component with deterministic fallback if the model drifts.
    if out["component"] not in COMPONENTS:
        out["component"] = INTENT_TO_COMPONENT.get(out["intent"], "support")
    out["conv_id"] = cid
    out["text"] = text
    out["channel"] = conv.get("channel", "web")
    out["created_at"] = conv.get("created_at")
    out["intent_true"] = conv.get("intent_true")
    out["category_true"] = conv.get("category_true")

    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def extract_many(
    convs: list[dict],
    use_cache: bool = True,
    progress: bool = True,
    max_workers: int = 8,
) -> list[dict]:
    """Extract many; uses disk cache, calls the LLM only for misses (concurrently)."""
    from concurrent.futures import ThreadPoolExecutor

    n = len(convs)
    t0 = time.time()
    misses = [c for c in convs if not (use_cache and _cache_path(c["id"]).exists())]
    if misses:
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = [ex.submit(extract_one, c, use_cache) for c in misses]
            for f in futs:
                f.result()
                done += 1
                if progress and (done % 25 == 0 or done == len(misses)):
                    rate = done / max(time.time() - t0, 1e-6)
                    print(f"  llm-extracted {done}/{len(misses)} ({rate:.1f}/s)", file=sys.stderr)
    # Assemble in original order (all cached now).
    out = [extract_one(c, use_cache=True) for c in convs]
    if progress:
        print(f"  ✓ {n} extractions ({len(misses)} new llm calls, {time.time()-t0:.1f}s)", file=sys.stderr)
    return out


def load_conversations(path: Path | None = None, limit: int | None = None) -> list[dict]:
    path = path or config.CONVERSATIONS
    rows = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    return rows[:limit] if limit else rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    convs = load_conversations(limit=args.limit)
    print(f"Extracting {len(convs)} conversations (model={config.CHAT_MODEL}, cache={_EXTRACT_DIR})")
    rows = extract_many(convs, use_cache=not args.no_cache)
    # Quick sanity summary.
    import collections

    comp = collections.Counter(r["component"] for r in rows)
    print(f"✓ done. component distribution: {dict(comp)}")
    print(f"  sample: {json.dumps({k: rows[0][k] for k in ('conv_id','intent','component','symptoms','severity','confidence')}, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
