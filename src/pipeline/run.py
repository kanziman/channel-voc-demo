#!/usr/bin/env python3
"""run.py — the single entry point the host agent invokes.

Runs the whole department for one day in order:
  ingest → analyze → validate → dispatch → dashboard
then assembles the **dual-return manifest** (handoff §4): the Human layer is the
HTML dashboard; the Agent layer is manifest.json — a structured, chainable summary
of what was found and what was dispatched.

Usage:
  python src/pipeline/run.py                 # full run, dispatch gated by env
  python src/pipeline/run.py --execute       # actually create GitHub artifacts
  python src/pipeline/run.py --no-dispatch   # analysis + dashboard only

The Jira (MCP) leg is performed by the host agent, not this script; if a prior
agent step wrote data/jira_dispatch.json, the manifest folds it in.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data"
OUT = ROOT / "out"

# Automatically use project's .venv python to avoid global numpy/pandas import conflicts
venv_python = ROOT / ".venv" / "bin" / "python3"
if venv_python.exists() and sys.executable != str(venv_python):
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)
PY = sys.executable


def _stage(name: str, args: list[str]) -> None:
    print(f"\n━━ {name} ━━", file=sys.stderr)
    r = subprocess.run([PY, str(HERE / f"{name}.py"), *args])
    if r.returncode != 0:
        raise SystemExit(f"[run] stage '{name}' failed ({r.returncode})")


def _load(name: str, default=None):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def build_manifest() -> dict:
    a = _load("analysis.json")
    v = _load("validation.json")
    disp = _load("dispatched.json", {"dispatched": []})
    jira = _load("jira_dispatch.json")

    dispatched = []
    for d in disp.get("dispatched", []):
        via = "code: run.py --execute (gh CLI)" if d["type"].startswith("github") else "code: file artifact"
        dispatched.append({"type": d["type"], "theme": d.get("theme"),
                           "title": d.get("title"), "url": d.get("url"),
                           "via": via,
                           "executed": bool(d.get("executed") and d.get("url"))})
    if jira:
        dispatched.append({"type": jira["type"], "theme": jira["theme"],
                           "title": jira["title"], "url": jira["url"],
                           "via": f"agent+mcp: {jira.get('integration','Atlassian MCP')} "
                                  f"(host-agent step; see dispatch_jira.py to reproduce)",
                           "executed": True})

    live = [d for d in dispatched if d["url"]]
    top = a["themes"][0]
    # ₩ carries the theming misassignment error: intent macro-F1 → ~(1-F1) band.
    intent = (v or {}).get("intent_level") or {}
    band_pct = round((1 - intent.get("macro_f1", v["macro_f1"] if v else 1.0)) * 100, 1)
    briefing = (
        f"Read {a['inbox_count']:,} real conversations from {a['day']}. "
        f"Total revenue at risk: ₩{a['total_revenue_at_risk_krw']:,} across {a['theme_count']} themes. "
        f"Top exposure: {top['theme']} (₩{top['revenue_at_risk_krw']:,}, {top['count']} convs). "
        f"Theming validated on held-out human labels at κ={v['cohen_kappa']} ({v['kappa_band']}), "
        f"macro-F1={v['macro_f1']}. Dispatched {len(live)} real actions."
    )

    return {
        "schema": "voc-intelligence.manifest/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "day": a["day"],
        "briefing": briefing,
        "dashboard_path": str((OUT / "dashboard.html").relative_to(ROOT)),
        "metrics": {
            "conversations_read": a["inbox_count"],
            "revenue_at_risk_krw": a["total_revenue_at_risk_krw"],
            "revenue_at_risk_band_pct": band_pct,
            "projected_recoverable_krw": a.get("projected_recoverable_krw"),
            "recovery_rate": a.get("recovery_rate"),
            "themes": a["theme_count"],
            "cohen_kappa": v["cohen_kappa"] if v else None,
            "macro_f1": v["macro_f1"] if v else None,
            "intent_cohen_kappa": intent.get("cohen_kappa"),
            "intent_macro_f1": intent.get("macro_f1"),
            "held_out_labels": v["heldout_count"] if v else None,
            "actions_dispatched": len(live),
        },
        "top_actions": a["top_actions"],
        "dispatched": dispatched,
        "validation": v and {"cohen_kappa": v["cohen_kappa"], "macro_f1": v["macro_f1"],
                             "accuracy": v["accuracy"], "kappa_band": v["kappa_band"],
                             "intent_level": {"cohen_kappa": intent.get("cohen_kappa"),
                                              "macro_f1": intent.get("macro_f1"),
                                              "n_classes": intent.get("n_classes")},
                             "caveat": v.get("caveat"),
                             "method": v["method"]},
        "source": a["source"],
        "assumptions_note": a["assumptions"]["globals"]["note"],
        # True when the dispatched set contains real, live artifact URLs (regardless
        # of whether this particular run re-dispatched or reused an executed run).
        "dispatch_executed_live": bool(live),
        "audit": "Every ₩ figure traces to conversation ids in analysis.json → themes[].representatives.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="create real GitHub artifacts")
    ap.add_argument("--no-dispatch", action="store_true", help="skip dispatch stage")
    ap.add_argument("--sample", type=int, default=1200)
    args = ap.parse_args()

    _stage("ingest", ["--sample", str(args.sample)])
    _stage("analyze", [])
    _stage("validate", [])
    if not args.no_dispatch:
        _stage("dispatch", ["--execute"] if args.execute else ["--dry-run"])
    _stage("dashboard", [])

    manifest = build_manifest()
    OUT.mkdir(exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                       encoding="utf-8")

    print("\n" + "═" * 64, file=sys.stderr)
    print("DUAL RETURN — Agent layer (manifest.json):", file=sys.stderr)
    print(json.dumps({"briefing": manifest["briefing"],
                      "metrics": manifest["metrics"],
                      "dispatched": manifest["dispatched"],
                      "dashboard_path": manifest["dashboard_path"]},
                     indent=2, ensure_ascii=False))
    print(f"\nHuman layer → {manifest['dashboard_path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
