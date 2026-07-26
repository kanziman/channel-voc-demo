"""One-command PHASE2 pipeline (§2.4 gate).

    python -m src.graph.run              # full run, dry dispatch, build + open dashboard
    python -m src.graph.run --live       # create real GitHub issues on approval
    python -m src.graph.run --reload      # re-extract + re-load the graph from scratch
    python -m src.graph.run --no-open     # don't auto-open the dashboard

Deterministic replay: extraction/embedding/LLM calls are all cached, so after the
first run everything is instant and identical — the demo shows the same screen.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

from . import config, db


def _step(n: int, total: int, label: str):
    print(f"\n\033[1m[{n}/{total}] {label}\033[0m")
    return time.time()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="create real GitHub issues on approval")
    ap.add_argument("--reload", action="store_true", help="wipe + re-load the knowledge graph")
    ap.add_argument("--no-open", action="store_true", help="don't auto-open the dashboard")
    args = ap.parse_args()

    total = 7
    t0 = time.time()
    print("═" * 60)
    print("  VOC Intelligence Dept — Root-Cause GraphRAG (PHASE2)")
    print("═" * 60)

    t = _step(1, total, "Schema — constraints + vector index (idempotent)")
    db.apply_schema()
    print(f"    ✓ ({time.time()-t:.1f}s)")

    t = _step(2, total, "Knowledge graph — ingest → Neo4j (cached extraction + embeddings)")
    counts = db.counts()
    if args.reload or counts.get("Conversation", 0) < 1000:
        from .load import main as load_main
        sys.argv = ["load"] + (["--keep"] if not args.reload else [])
        load_main()
    else:
        print(f"    ✓ already loaded: {counts.get('Conversation')} conversations (idempotent skip)")

    t = _step(3, total, "Benchmark — sklearn vs LLM on 600 held-out (κ / macro-F1)")
    from .benchmark import main as bench_main
    bench_main()

    t = _step(4, total, "Root causes — Cypher traversal + ₩ aggregation + hypotheses")
    from .rootcause import main as rc_main
    rc_main()

    t = _step(5, total, "Agent — LangGraph StateGraph (GraphRAG draft → interrupt → dispatch)")
    from .agent import run as agent_run
    agent_run(live=args.live)

    t = _step(6, total, "Export — curated graph snapshot for the dashboard")
    from .export import main as export_main
    export_main()

    t = _step(7, total, "Dashboard — single self-contained HTML (6 visuals)")
    from .dashboard import main as dash_main
    dash_main()

    out = config.OUT_DIR / "dashboard.html"
    print("\n" + "═" * 60)
    print(f"  ✅ DONE in {time.time()-t0:.0f}s  →  {out}")
    print("═" * 60)

    if not args.no_open and out.exists():
        try:
            subprocess.run(["open", str(out)], check=False)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
