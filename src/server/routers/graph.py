"""Graph API (§2.5, §0-9) [WRAP+NEW].

  GET /api/graph/schema    — static ontology metadata (no DB).
  GET /api/graph/subgraph  — build_snapshot() by default; ?expand=<id>&hops=1|2
                             runs a new variable-length Cypher around one node.

Node ids follow the same scheme as export.build_snapshot ("comp::billing",
"rc::rc_billing", "conv::conv_00001", …) so a node clicked in the snapshot can
be expanded here and the panel stays in one coordinate system.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ...graph import db
from ...graph.export import build_snapshot

router = APIRouter(prefix="/api/graph", tags=["graph"])

# ── ontology (single source for the static schema endpoint) ───────────────────
# prefix ↔ (Neo4j label, key property). Whitelist → safe to inline in Cypher.
_ONTOLOGY: list[tuple[str, str, str]] = [
    ("cust", "Customer", "id"),
    ("conv", "Conversation", "id"),
    ("sym", "Symptom", "text"),
    ("comp", "Component", "name"),
    ("rc", "RootCause", "key"),
    ("act", "Action", "key"),
]
_BY_PREFIX = {p: (label, key) for p, label, key in _ONTOLOGY}
_BY_LABEL = {label: (p, key) for p, label, key in _ONTOLOGY}

ONTOLOGY_META = {
    "node_types": [{"type": label, "key": key} for _, label, key in _ONTOLOGY],
    "edge_types": ["MENTIONS", "IMPLICATES", "CAUSED_BY", "DISPATCHED_AS", "EVIDENCES"],
    "hierarchy": [label for _, label, _ in _ONTOLOGY],
}


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="allow")  # keep type-specific props
    id: str
    type: str
    label: str


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="allow")  # keep edge props (e.g. build_snapshot's rc)
    source: str
    target: str
    type: str


class SubgraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    center: str | None = None


def _node_id(labels: list[str], props: dict) -> tuple[str, str, str]:
    """(id, type, label) in build_snapshot's scheme for a raw Neo4j node."""
    label = next((l for l in labels if l in _BY_LABEL), labels[0] if labels else "Node")
    prefix, key = _BY_LABEL.get(label, (label.lower(), "id"))
    keyval = str(props.get(key, ""))
    # build_snapshot ids Actions by their root-cause key (act::rc_x), but the stored
    # Action.key is "act_<rc_key>" (dispatch.py) — strip so both paths share one id.
    if label == "Action":
        keyval = keyval.removeprefix("act_")
    return f"{prefix}::{keyval}", label, keyval


@router.get("/schema")
def schema() -> dict:
    return ONTOLOGY_META


@router.get("/subgraph", response_model=SubgraphResponse)
def subgraph(
    expand: str | None = None,
    hops: int = Query(1, ge=1, le=2),
) -> SubgraphResponse:
    # default: reuse the precomputed root-cause snapshot
    if expand is None:
        snap = build_snapshot()
        return SubgraphResponse(nodes=snap["nodes"], edges=snap["edges"])

    prefix, _, keyval = expand.partition("::")
    if prefix not in _BY_PREFIX or not keyval:
        raise HTTPException(status_code=400, detail="unknown node id")
    label, key = _BY_PREFIX[prefix]

    center = db.run(
        f"MATCH (n:{label} {{{key}:$v}}) RETURN labels(n) AS nl, properties(n) AS np",
        v=keyval,
    )
    if not center:
        raise HTTPException(status_code=404, detail="node not found")

    nodes: dict[str, dict] = {}

    def _add(labels: list[str], props: dict) -> str:
        nid, ntype, lbl = _node_id(labels, props)
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": lbl,
                          **{k: v for k, v in props.items()}}
        return nid

    _add(center[0]["nl"], center[0]["np"])  # always include the clicked node

    rows = db.run(
        f"MATCH (n:{label} {{{key}:$v}}) "
        f"MATCH (n)-[rel*1..{int(hops)}]-(m) "
        "UNWIND rel AS r WITH DISTINCT r "
        "RETURN labels(startNode(r)) AS sl, properties(startNode(r)) AS sp, "
        "labels(endNode(r)) AS el, properties(endNode(r)) AS ep, type(r) AS t",
        v=keyval,
    )
    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for r in rows:
        sid = _add(r["sl"], r["sp"])
        tid = _add(r["el"], r["ep"])
        key3 = (sid, tid, r["t"])
        if key3 not in seen:
            seen.add(key3)
            edges.append({"source": sid, "target": tid, "type": r["t"]})

    center_id = _node_id(center[0]["nl"], center[0]["np"])[0]
    return SubgraphResponse.model_validate(
        {"nodes": list(nodes.values()), "edges": edges, "center": center_id}
    )
