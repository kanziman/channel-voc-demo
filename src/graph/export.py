"""Export a curated Neo4j subgraph → out/graph_snapshot.json for the dashboard.

Not the full 1,200-node graph (too dense to read) — a legible slice that still
proves the structure: Components, promoted RootCauses, their top Symptoms, a few
evidence Conversations, and dispatched Actions, plus the ₩ paths used for the
click-to-highlight animation and the Sankey flows.
"""
from __future__ import annotations

import json

from . import config, db

_SUBGRAPH = """
MATCH (comp:Component)-[:CAUSED_BY]->(r:RootCause)
OPTIONAL MATCH (r)-[:DISPATCHED_AS]->(a:Action)
WITH comp, r, a
CALL (comp, r) {
  WITH comp, r
  MATCH (conv:Conversation)-[:MENTIONS]->(s:Symptom)-[:IMPLICATES]->(comp)
  WITH s, count(DISTINCT conv) AS freq
  ORDER BY freq DESC LIMIT 5
  RETURN collect({text: s.text, freq: freq}) AS top_symptoms
}
RETURN comp.name AS component,
       r.key AS rc_key, r.hypothesis AS hypothesis, r.frequency AS frequency,
       r.revenue_at_risk_krw AS revenue, r.projected_recoverable_krw AS recoverable,
       r.severity_avg AS severity, r.confidence_avg AS confidence,
       r.sample_conv_ids AS sample_conv_ids,
       top_symptoms,
       a.url AS action_url, a.status AS action_status, a.title AS action_title
ORDER BY revenue DESC
"""

_CONV_TEXTS = """
UNWIND $ids AS id
MATCH (c:Conversation {id: id})
RETURN c.id AS id, left(c.text, 160) AS text, c.severity AS severity
"""

_COMPONENT_TOTALS = """
MATCH (conv:Conversation)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(c:Component)
RETURN c.name AS component, count(DISTINCT conv) AS n ORDER BY n DESC
"""


def build_snapshot() -> dict:
    rows = db.run(_SUBGRAPH)
    comp_totals = {r["component"]: r["n"] for r in db.run(_COMPONENT_TOTALS)}

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(nid, ntype, label, **props):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, **props}
        return nid

    conv_ids = set()
    root_causes = []
    for r in rows:
        comp_id = add(f"comp::{r['component']}", "Component", r["component"],
                      total_conversations=comp_totals.get(r["component"], 0))
        rc_id = add(f"rc::{r['rc_key']}", "RootCause", r["component"],
                    hypothesis=r["hypothesis"], frequency=r["frequency"],
                    revenue=r["revenue"], recoverable=r["recoverable"],
                    severity=r["severity"], confidence=r["confidence"])
        edges.append({"source": comp_id, "target": rc_id, "type": "CAUSED_BY", "rc": rc_id})

        for s in r["top_symptoms"]:
            sid = add(f"sym::{s['text']}", "Symptom", s["text"], freq=s["freq"])
            edges.append({"source": sid, "target": comp_id, "type": "IMPLICATES", "rc": rc_id})

        for cid in (r["sample_conv_ids"] or [])[:3]:
            conv_ids.add(cid)
            add(f"conv::{cid}", "Conversation", cid)
            edges.append({"source": f"conv::{cid}", "target": f"sym::{r['top_symptoms'][0]['text']}"
                          if r["top_symptoms"] else comp_id, "type": "MENTIONS", "rc": rc_id})

        if r["action_url"] or r["action_status"]:
            aid = add(f"act::{r['rc_key']}", "Action",
                      "Issue" + (" ✓" if r["action_url"] else ""),
                      url=r["action_url"], status=r["action_status"], title=r["action_title"])
            edges.append({"source": rc_id, "target": aid, "type": "DISPATCHED_AS", "rc": rc_id})
            for cid in (r["sample_conv_ids"] or [])[:3]:
                edges.append({"source": aid, "target": f"conv::{cid}", "type": "EVIDENCES", "rc": rc_id})

        root_causes.append({
            "rc": rc_id, "component": r["component"], "hypothesis": r["hypothesis"],
            "frequency": r["frequency"], "revenue": r["revenue"], "recoverable": r["recoverable"],
            "severity": r["severity"], "confidence": r["confidence"],
            "top_symptoms": r["top_symptoms"],
            "sample_conv_ids": (r["sample_conv_ids"] or [])[:3],
            "action_url": r["action_url"], "action_status": r["action_status"],
        })

    conv_texts = {c["id"]: c for c in db.run(_CONV_TEXTS, ids=list(conv_ids))} if conv_ids else {}
    for cid, meta in conv_texts.items():
        n = nodes.get(f"conv::{cid}")
        if n:
            n["text"] = meta["text"]
            n["severity"] = meta["severity"]

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "root_causes": root_causes,
        "conversations": conv_texts,
        "component_totals": comp_totals,
        "graph_counts": db.counts(),
    }


# Sample queries for the playground — grounded in the Bitext domain so all three
# arms return real hits (each targets a different component).
SEARCH_SAMPLES = [
    "payment failed at checkout",
    "where is my refund",
    "can't reset my password",
    "change my delivery address",
]

_FULL_TEXT = """
UNWIND $ids AS id
MATCH (c:Conversation {id: id})
RETURN c.id AS id, c.text AS text, c.severity AS severity
"""


def _extraction(conv_id: str) -> dict | None:
    from .extract import _cache_path

    p = _cache_path(conv_id)
    return json.loads(p.read_text()) if p.exists() else None


def build_stages(root_causes: list[dict], manifest: dict, drafts: list[dict]) -> dict:
    """6-stage tracer: follow the top root cause's first evidence conversation."""
    top = root_causes[0] if root_causes else {}
    tracer_id = (top.get("sample_conv_ids") or ["conv_00000"])[0]
    extraction = _extraction(tracer_id) or {}
    top_draft = next((d for d in drafts if d.get("root_cause_key") == top.get("rc", "").replace("rc::", "")), {})

    return {
        "tracer_conv_id": tracer_id,
        "stage1_extraction": {
            "conv_id": tracer_id,
            "raw_text": extraction.get("text", ""),
            "extracted": {k: extraction.get(k) for k in
                          ("intent", "component", "symptoms", "severity", "confidence")},
        },
        "stage2_ingest": {
            "cypher": ("MERGE (conv:Conversation {id})\n"
                       "  SET conv.embedding = <384d bge-small vector>\n"
                       "MERGE (conv)-[:EXPRESSES]->(:Intent)-[:ROLLS_UP_TO]->(:Theme)\n"
                       "MERGE (conv)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(:Component)"),
            "counts": db.counts(),
            "embedding": {"model": config.EMBED_MODEL, "dim": config.EMBED_DIM},
        },
        "stage3_traversal": {
            "cypher": ("MATCH (conv)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(comp:Component)\n"
                       "WITH comp, count(DISTINCT conv) AS freq\n"
                       "WHERE freq >= 8   // promote to RootCause (aggregation, not a label)"),
            "component": top.get("component"),
            "frequency": top.get("frequency"),
            "revenue": top.get("revenue"),
            "hypothesis": top.get("hypothesis"),
            "evidence_ids": top.get("sample_conv_ids", []),
        },
        "stage4_graphrag": {
            "query": top_draft.get("title") or top.get("hypothesis", ""),
            "evidence": (top_draft.get("evidence") or [])[:6],
            "n_both": top_draft.get("n_both", 0),
        },
        "stage5_gate": {
            "threshold": config.DISPATCH_CONFIDENCE_THRESHOLD,
            "require_approval": config.DISPATCH_REQUIRE_APPROVAL,
            "candidates": [
                {"key": d["root_cause_key"], "title": d["title"], "severity": d["severity"],
                 "revenue_at_risk_krw": d["revenue_at_risk_krw"], "confidence": d["confidence"],
                 "cited": len(d.get("cited_conv_ids", []))}
                for d in drafts
            ],
            # Graph truth: a candidate is dispatched iff its RootCause Action has a live url.
            "dispatched": [
                {"key": rc["rc"].replace("rc::", ""), "url": rc["action_url"]}
                for rc in root_causes if rc.get("action_url")
            ],
        },
        "stage6_dispatch": {
            "issues": [
                {"component": rc["component"], "url": rc.get("action_url"),
                 "revenue": rc["revenue"], "evidence_ids": rc.get("sample_conv_ids", [])}
                for rc in root_causes if rc.get("action_url")
            ],
        },
    }


_ROLE_LABEL = {"customer": "👤 고객", "agent": "🎧 상담원", "user": "👤 고객", "bot": "🎧 상담원"}


def _full_dialogue(messages: list[dict]) -> str:
    """Render the complete multi-turn conversation (customer + agent) for 원문 보기."""
    return "\n\n".join(
        f"{_ROLE_LABEL.get(m.get('role'), m.get('role', '?'))}: {m.get('text', '').strip()}"
        for m in messages
    )


def build_corpus(ids: set[str]) -> dict:
    """Per conversation: `text` = customer-only (for search/snippet), `full` = the
    complete dialogue incl. agent replies (for the 원문 보기 viewer, so it shows
    more than the snippet)."""
    if not ids:
        return {}
    rows = db.run(_FULL_TEXT, ids=list(ids))
    corpus = {r["id"]: {"text": r["text"], "severity": r["severity"]} for r in rows}
    # Attach the full multi-turn transcript from the source data.
    for line in config.CONVERSATIONS.open(encoding="utf-8"):
        if not line.strip():
            continue
        c = json.loads(line)
        if c["id"] in corpus:
            corpus[c["id"]]["full"] = _full_dialogue(c.get("messages", []))
    return corpus


def build_search_samples() -> list[dict]:
    from .retriever import hybrid_search

    out = []
    for q in SEARCH_SAMPLES:
        res = hybrid_search(q, k=6)
        # drop bulky text from inline results; corpus carries full text by id.
        for r in res["results"]:
            r.pop("text", None)
        out.append(res)
    return out


_ROI_TRAVERSE = """
MATCH (conv:Conversation)-[:EXPRESSES]->(i:Intent)-[:ROLLS_UP_TO]->(t:Theme)
MATCH (conv)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(comp:Component {name:$component})
RETURN DISTINCT conv.id AS id, i.name AS intent, t.name AS theme
"""


def build_roi_example(root_causes: list[dict]) -> dict:
    """Transparent ₩ breakdown for the top root cause — reconciles exactly to the
    displayed number so a judge can check the math. Uses the PHASE1 assumptions
    model: per-conversation ₩ = category value_per_case × intent weight."""
    import collections

    from src.pipeline import assumptions as A

    if not root_causes:
        return {}
    top = root_causes[0]
    component = top["component"]
    rows = {r["id"]: r for r in db.run(_ROI_TRAVERSE, component=component)}
    by_cat = collections.Counter()
    total = 0.0
    for r in rows.values():
        risk = A.conversation_risk_krw(r["theme"], r["intent"])
        total += risk
        by_cat[r["theme"]] += risk
    total = int(round(total))
    by_category = [
        {"category": c, "krw": int(round(v)),
         "value_per_case": A.model_for(c)["value_per_case_krw"]}
        for c, v in by_cat.most_common()
    ]
    return {
        "component": component,
        "frequency": len(rows),
        "revenue": total,
        "recoverable": A.projected_recoverable_krw(total),
        "recovery_rate": A.RECOVERY_RATE,
        "aov": A.AOV_KRW,
        "by_category": by_category,
        "weights": {"info": A._INFO, "friction": A._FRICTION, "churn": A._CHURN},
    }


def main() -> int:
    snap = build_snapshot()

    manifest = json.loads((config.OUT_DIR / "manifest.json").read_text()) \
        if (config.OUT_DIR / "manifest.json").exists() else {}
    drafts = json.loads((config.OUT_DIR / "drafts.json").read_text()) \
        if (config.OUT_DIR / "drafts.json").exists() else []

    stages = build_stages(snap["root_causes"], manifest, drafts)
    search_samples = build_search_samples()

    # Corpus = every conversation referenced anywhere (for 원문 보기 + offline search).
    ids: set[str] = {stages["tracer_conv_id"]}
    for rc in snap["root_causes"]:
        ids.update(rc.get("sample_conv_ids", []))
    for d in drafts:
        ids.update(e["id"] for e in (d.get("evidence") or []))
    for s in search_samples:
        ids.update(r["id"] for r in s["results"])

    snap["stages"] = stages
    snap["corpus"] = build_corpus(ids)
    snap["search_samples"] = search_samples
    snap["roi_example"] = build_roi_example(snap["root_causes"])
    snap["embedding_meta"] = {
        "model": config.EMBED_MODEL, "dim": config.EMBED_DIM,
        "sparse": "neo4j-fulltext (Lucene BM25)", "fusion": "Reciprocal Rank Fusion (k=60)",
        "search_port": config.SEARCH_PORT,
    }

    out = config.OUT_DIR / "graph_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
    print(f"✓ wrote {out}: {len(snap['nodes'])} nodes, {len(snap['edges'])} edges, "
          f"{len(snap['root_causes'])} root causes, {len(snap['corpus'])} corpus texts, "
          f"{len(search_samples)} search samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
