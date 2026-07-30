"""GraphRAG hybrid retriever (§2.3) — vector + graph evidence.

For an issue draft we gather two complementary kinds of precedent:
  1. VECTOR  — conversations semantically similar to the root cause (Neo4j
               vector index over local fastembed embeddings).
  2. GRAPH   — structural neighbours: conversations that implicate the SAME
               component via symptoms (1-hop provenance).

Every returned conversation carries provenance (similarity % and/or graph hop)
so the generated issue can cite exact conv_ids — the "fact-grounded" proof.
"""
from __future__ import annotations

from . import db, llm

_VECTOR_QUERY = """
CALL db.index.vector.queryNodes('conversation_embedding', $k, $vec)
YIELD node, score
OPTIONAL MATCH (node)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(cc:Component)
WITH node, score, collect(DISTINCT cc.name)[0] AS component
RETURN node.id AS id, node.text AS text, score,
       node.severity AS severity, node.intent_true AS intent, component
ORDER BY score DESC
"""

_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes('conversation_fulltext', $q, {limit: $k})
YIELD node, score
OPTIONAL MATCH (node)-[:MENTIONS]->(:Symptom)-[:IMPLICATES]->(cc:Component)
WITH node, score, collect(DISTINCT cc.name)[0] AS component
RETURN node.id AS id, node.text AS text, score,
       node.severity AS severity, node.intent_true AS intent, component
ORDER BY score DESC
"""

_GRAPH_NEIGHBORS = """
MATCH (comp:Component {name: $component})<-[:IMPLICATES]-(s:Symptom)<-[:MENTIONS]-(conv:Conversation)
WITH conv, collect(DISTINCT s.text) AS symptoms, comp
OPTIONAL MATCH (conv)-[:EXPRESSES]->(i:Intent)
RETURN conv.id AS id, left(conv.text, 240) AS text, conv.severity AS severity,
       i.name AS intent, symptoms, 1 AS hop
ORDER BY conv.severity DESC
LIMIT $k
"""


def vector_search(query_text: str, k: int = 5) -> list[dict]:
    vec = llm.embed_one(query_text)
    rows = db.run(_VECTOR_QUERY, k=k, vec=vec)
    for r in rows:
        r["similarity"] = round(r.pop("score"), 4)
        r["source"] = "vector"
    return rows


def fulltext_search(query_text: str, k: int = 5) -> list[dict]:
    """Lexical / "sparse" arm — Neo4j full-text (Lucene BM25)."""
    # Sanitise: Lucene special chars would raise; keep alnum + spaces, OR the terms.
    import re

    terms = re.findall(r"[A-Za-z0-9]+", query_text)
    if not terms:
        return []
    lucene = " OR ".join(terms)
    rows = db.run(_FULLTEXT_QUERY, q=lucene, k=k)
    for r in rows:
        r["lexical"] = round(r.pop("score"), 4)
        r["source"] = "fulltext"
    return rows


def graph_neighbors(component: str, k: int = 5) -> list[dict]:
    rows = db.run(_GRAPH_NEIGHBORS, component=component, k=k)
    for r in rows:
        r["source"] = "graph"
    return rows


def hybrid_for_rootcause(rc: dict, k_vector: int = 5, k_graph: int = 5) -> dict:
    """Assemble hybrid evidence for one root cause → context for action_drafter."""
    # Vector arm: query = hypothesis + top symptoms (the semantic gist).
    top_syms = [s for s, _ in rc.get("top_symptoms", [])][:5]
    query = rc["hypothesis"] + " | " + "; ".join(top_syms)
    vec_hits = vector_search(query, k=k_vector)
    graph_hits = graph_neighbors(rc["component"], k=k_graph)

    # Merge, dedup by id, keep richest provenance.
    merged: dict[str, dict] = {}
    for h in vec_hits + graph_hits:
        cur = merged.get(h["id"])
        if cur is None:
            merged[h["id"]] = h
        else:
            # conversation surfaced by BOTH arms → strongest evidence.
            cur["source"] = "vector+graph"
            if "similarity" in h:
                cur["similarity"] = h["similarity"]
            if "symptoms" in h:
                cur["symptoms"] = h["symptoms"]
    evidence = sorted(
        merged.values(),
        key=lambda e: (e.get("source") == "vector+graph", e.get("similarity", 0)),
        reverse=True,
    )
    return {
        "component": rc["component"],
        "hypothesis": rc["hypothesis"],
        "query": query,
        "evidence": evidence,
        "n_vector": len(vec_hits),
        "n_graph": len(graph_hits),
        "n_both": sum(1 for e in evidence if e["source"] == "vector+graph"),
    }


def _rrf(ranklists: dict[str, list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(doc) = Σ_arm 1/(k + rank_arm(doc))."""
    scores: dict[str, float] = {}
    for ids in ranklists.values():
        for rank, cid in enumerate(ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_search(query_text: str, k: int = 6, pool: int = 12) -> dict:
    """Free-query triple-arm hybrid: dense (bge-small) + sparse (full-text) + graph.

    Returns per-result arm scores + RRF rank + full original text — the data the
    dashboard playground renders as a 3-arm breakdown.
    """
    dense = vector_search(query_text, k=pool)
    sparse = fulltext_search(query_text, k=pool)

    # Graph arm: expand from the component the top hits point at (structural).
    comp_votes: dict[str, int] = {}
    for h in dense[:3] + sparse[:3]:
        c = h.get("component")
        if c:
            comp_votes[c] = comp_votes.get(c, 0) + 1
    top_component = max(comp_votes, key=comp_votes.get) if comp_votes else None
    graph = graph_neighbors(top_component, k=pool) if top_component else []

    # Fuse.
    ranklists = {
        "dense": [h["id"] for h in dense],
        "sparse": [h["id"] for h in sparse],
        "graph": [h["id"] for h in graph],
    }
    rrf = _rrf(ranklists)

    by_id: dict[str, dict] = {}

    def _slot(cid: str) -> dict:
        return by_id.setdefault(cid, {"id": cid, "dense": None, "sparse": None,
                                      "in_graph": False, "text": None, "component": None,
                                      "severity": None})

    for h in dense:
        s = _slot(h["id"]); s["dense"] = h["similarity"]; s["text"] = h["text"]
        s["component"] = h.get("component"); s["severity"] = h.get("severity")
    for h in sparse:
        s = _slot(h["id"]); s["sparse"] = h["lexical"]
        s["text"] = s["text"] or h["text"]; s["component"] = s["component"] or h.get("component")
        s["severity"] = s["severity"] if s["severity"] is not None else h.get("severity")
    for h in graph:
        s = _slot(h["id"]); s["in_graph"] = True
        s["text"] = s["text"] or h["text"]

    results = list(by_id.values())
    for r in results:
        r["rrf"] = round(rrf.get(r["id"], 0.0), 5)
        arms = [a for a, on in (("dense", r["dense"] is not None),
                                ("sparse", r["sparse"] is not None),
                                ("graph", r["in_graph"])) if on]
        r["arms"] = arms
    results.sort(key=lambda r: r["rrf"], reverse=True)
    return {
        "query": query_text,
        "top_component": top_component,
        "counts": {"dense": len(dense), "sparse": len(sparse), "graph": len(graph)},
        "results": results[: max(k * 2, 12)],
    }


def main() -> int:
    import json
    import sys

    from . import config

    if len(sys.argv) > 1:  # free-query hybrid demo
        q = " ".join(sys.argv[1:])
        out = hybrid_search(q)
        print(f"Hybrid search: {q!r}  (component≈{out['top_component']}, {out['counts']})\n")
        for r in out["results"]:
            d = f"{r['dense']*100:.0f}%" if r["dense"] is not None else "—"
            sp = f"{r['sparse']:.2f}" if r["sparse"] is not None else "—"
            g = "✓" if r["in_graph"] else "·"
            print(f"  {r['id']}  dense={d:>5} sparse={sp:>5} graph={g}  rrf={r['rrf']:.4f}  [{'+'.join(r['arms'])}]")
            print(f"     {(r['text'] or '')[:110].strip()}...")
        return 0

    rcs = json.loads((config.OUT_DIR / "root_causes.json").read_text())
    ctx = hybrid_for_rootcause(rcs[0])
    print(f"Hybrid evidence for root cause [{ctx['component']}]")
    print(f"  vector={ctx['n_vector']} graph={ctx['n_graph']} both={ctx['n_both']}\n")
    for e in ctx["evidence"][:6]:
        sim = f"{e['similarity']*100:.1f}%" if "similarity" in e else "—"
        print(f"  {e['id']}  [{e['source']}]  sim={sim}  sev={e.get('severity')}")
        print(f"     {e['text'][:120].strip()}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
