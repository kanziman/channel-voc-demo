"""Single self-contained portfolio dashboard (§2.4).

Reads the pipeline artifacts (graph_snapshot / root_causes / benchmark / manifest
/ drafts) and emits ONE self-contained out/dashboard.html — inline JS/CSS, zero
external requests, CSP-safe, light/dark, mobile — with all six visuals:

  1. Agent execution flow (LangGraph) with this-run path + interrupt highlight
  2. Agent activity feed (per-node timings)
  3. Interactive knowledge graph (click a root cause → ₩-path highlight)
  4. Root causes + GraphRAG provenance cards (cited conv_ids, similarity/hop)
  5. Before/after benchmark (sklearn vs LLM, honest trade-off)
  6. ₩ root-cause money-flow (Sankey: component → dispatched/held)

Usage:  python -m src.graph.dashboard
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

OUT = config.OUT_DIR / "dashboard.html"
TEMPLATE = Path(__file__).parent / "dashboard_template.html"


def _read(name: str, default):
    p = config.OUT_DIR / name
    return json.loads(p.read_text()) if p.exists() else default


def build_payload() -> dict:
    snap = _read("graph_snapshot.json", {"nodes": [], "edges": [], "root_causes": []})
    bench = _read("benchmark.json", {})
    manifest = _read("manifest.json", {})
    drafts = _read("drafts.json", [])
    root_causes = snap.get("root_causes", [])

    total_risk = sum(rc["revenue"] for rc in root_causes)
    total_recover = sum(rc["recoverable"] for rc in root_causes)
    # Source of truth = the graph: a root cause is "dispatched" iff its Action has a live url.
    n_dispatched = sum(1 for rc in root_causes if rc.get("action_url"))

    # Sankey: each component's ₩ flows to Dispatched (has live url) or Held.
    sankey = [
        {"component": rc["component"], "revenue": rc["revenue"],
         "disposition": "배포됨" if rc.get("action_url") else "검토 대기"}
        for rc in root_causes
    ]

    # Agent flow: static node graph + which nodes executed (from activity log).
    executed = [a["node"] for a in (manifest.get("activity") or [])]
    flow_nodes = [
        {"id": "analyst_extract", "label": "analyst_extract", "sub": "LLM 추출"},
        {"id": "graph_writer", "label": "graph_writer", "sub": "Neo4j MERGE"},
        {"id": "researcher_cluster", "label": "researcher_cluster", "sub": "벡터 클러스터"},
        {"id": "triage_rootcause", "label": "triage_rootcause", "sub": "Cypher 순회"},
        {"id": "action_drafter", "label": "action_drafter", "sub": "GraphRAG 초안"},
        {"id": "human_approval", "label": "human_approval", "sub": "⏸ 승인 대기", "interrupt": True},
        {"id": "dispatcher", "label": "dispatcher", "sub": "GitHub 이슈"},
        {"id": "reporter", "label": "reporter", "sub": "manifest"},
    ]
    flow_edges = [
        ("analyst_extract", "graph_writer"), ("graph_writer", "researcher_cluster"),
        ("researcher_cluster", "triage_rootcause"), ("triage_rootcause", "action_drafter"),
        ("action_drafter", "human_approval"), ("human_approval", "dispatcher"),
        ("dispatcher", "reporter"),
    ]

    dispatched_url = next((rc["action_url"] for rc in root_causes if rc.get("action_url")), None)

    return {
        "kpis": {
            "total_risk": total_risk,
            "total_recover": total_recover,
            "n_root_causes": len(root_causes),
            "n_dispatched": n_dispatched,
            "dispatched_url": dispatched_url,
            "n_conversations": snap.get("graph_counts", {}).get("Conversation", 0),
            "n_components": snap.get("graph_counts", {}).get("Component", 0),
            "n_symptoms": snap.get("graph_counts", {}).get("Symptom", 0),
        },
        "graph": {"nodes": snap["nodes"], "edges": snap["edges"]},
        "root_causes": root_causes,
        "drafts": drafts,
        "benchmark": bench,
        "activity": manifest.get("activity") or [],
        "briefing": manifest.get("briefing", ""),
        "flow": {"nodes": flow_nodes, "edges": flow_edges, "executed": executed},
        "sankey": sankey,
        "graph_counts": snap.get("graph_counts", {}),
        # PHASE2 dashboard: 6-stage stepper + live search playground.
        "stages": snap.get("stages", {}),
        "corpus": snap.get("corpus", {}),
        "search_samples": snap.get("search_samples", []),
        "embedding_meta": snap.get("embedding_meta", {}),
        "roi_example": snap.get("roi_example", {}),
    }


def main() -> int:
    payload = build_payload()
    html = TEMPLATE.read_text()
    html = html.replace("/*__PAYLOAD__*/null", json.dumps(payload, ensure_ascii=False))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    kb = len(html.encode()) / 1024
    print(f"✓ wrote {OUT} ({kb:.0f} KB, self-contained)")
    print(f"  KPIs: ₩{payload['kpis']['total_risk']:,} at risk · "
          f"{payload['kpis']['n_root_causes']} root causes · "
          f"{payload['kpis']['n_dispatched']} dispatched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
