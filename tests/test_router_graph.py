"""TDD (issue #15) — /api/graph/schema + /api/graph/subgraph.

build_snapshot + db.run hit Neo4j, so both are monkeypatched; tests verify the
static schema, the build_snapshot passthrough, the 1/2-hop expand mapping, and
the error envelope, via the mounted routes.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.graph import serve


@pytest.fixture()
def client() -> TestClient:
    return TestClient(serve.app)


def _patch_snapshot(monkeypatch, value):
    import src.server.routers.graph as mod
    monkeypatch.setattr(mod, "build_snapshot", lambda: value)


def _patch_db_run(monkeypatch, fn):
    import src.server.routers.graph as mod
    monkeypatch.setattr(mod.db, "run", fn)


# ── schema (static, no DB) ────────────────────────────────────────────────────
def test_should_return_ontology_schema_without_db(client, monkeypatch):
    # if it touched the DB this would blow up:
    _patch_db_run(monkeypatch, lambda *a, **k: (_ for _ in ()).throw(AssertionError("DB hit")))
    b = client.get("/api/graph/schema").json()
    types = {t["type"] for t in b["node_types"]}
    assert {"Component", "RootCause", "Conversation"} <= types
    assert "CAUSED_BY" in b["edge_types"]
    assert b["hierarchy"][0] == "Customer"


# ── subgraph default → build_snapshot passthrough ─────────────────────────────
def test_should_return_snapshot_nodes_edges_when_no_expand(client, monkeypatch):
    snap = {"nodes": [{"id": "comp::billing", "type": "Component", "label": "billing",
                       "total_conversations": 240}],
            "edges": [{"source": "comp::billing", "target": "rc::rc_billing", "type": "CAUSED_BY"}],
            "root_causes": [], "conversations": {}, "component_totals": {}, "graph_counts": {}}
    _patch_snapshot(monkeypatch, snap)
    snap["edges"][0]["rc"] = "rc::rc_billing"  # build_snapshot tags edges with rc
    b = client.get("/api/graph/subgraph").json()
    assert b["nodes"][0]["id"] == "comp::billing"
    assert b["nodes"][0]["total_conversations"] == 240   # node extra props preserved
    assert b["edges"][0]["type"] == "CAUSED_BY"
    assert b["edges"][0]["rc"] == "rc::rc_billing"        # edge extra props preserved too


def test_should_id_action_by_rootcause_key_matching_snapshot(client, monkeypatch):
    # Action.key is stored as "act_<rc_key>" but build_snapshot uses "act::<rc_key>";
    # expanding a RootCause into its Action must land on the same snapshot id.
    rels = [
        {"sl": ["RootCause"], "sp": {"key": "rc_billing"},
         "el": ["Action"], "ep": {"key": "act_rc_billing"}, "t": "DISPATCHED_AS"},
    ]
    _patch_db_run(monkeypatch, _fake_expand_db(["RootCause"], {"key": "rc_billing"}, rels))
    b = client.get("/api/graph/subgraph", params={"expand": "rc::rc_billing"}).json()
    ids = {n["id"] for n in b["nodes"]}
    assert "act::rc_billing" in ids           # NOT act::act_rc_billing
    assert b["edges"][0]["target"] == "act::rc_billing"


def test_should_label_action_with_its_title_not_the_rootcause_key(client, monkeypatch):
    # Stripping "act_" off Action.key ("act_rc_billing") leaves "rc_billing" — the
    # *RootCause's own* key. Using that as the Action's display label renders it
    # as a visual duplicate of the RootCause node it's attached to (reported: the
    # evidence graph showed two "rc_billing"-labelled nodes). The Action's own
    # `title` property must win instead.
    rels = [
        {"sl": ["RootCause"], "sp": {"key": "rc_billing"},
         "el": ["Action"], "ep": {"key": "act_rc_billing", "title": "[VOC] Fix billing invoice mismatch"},
         "t": "DISPATCHED_AS"},
    ]
    _patch_db_run(monkeypatch, _fake_expand_db(["RootCause"], {"key": "rc_billing"}, rels))
    b = client.get("/api/graph/subgraph", params={"expand": "rc::rc_billing"}).json()
    action_node = next(n for n in b["nodes"] if n["id"] == "act::rc_billing")
    assert action_node["label"] == "[VOC] Fix billing invoice mismatch"


# ── expand 1-hop ──────────────────────────────────────────────────────────────
def _fake_expand_db(center_labels, center_props, rels):
    def run(cypher, **params):
        if "RETURN labels(n) AS nl" in cypher:
            return [{"nl": center_labels, "np": center_props}]
        return rels
    return run


def test_should_expand_one_hop_with_snapshot_ids_and_direction(client, monkeypatch):
    rels = [
        {"sl": ["Component"], "sp": {"name": "billing"},
         "el": ["RootCause"], "ep": {"key": "rc_billing"}, "t": "CAUSED_BY"},
    ]
    _patch_db_run(monkeypatch, _fake_expand_db(["Component"], {"name": "billing"}, rels))
    b = client.get("/api/graph/subgraph", params={"expand": "comp::billing", "hops": 1}).json()
    ids = {n["id"] for n in b["nodes"]}
    assert {"comp::billing", "rc::rc_billing"} <= ids
    assert b["center"] == "comp::billing"
    e = b["edges"][0]
    assert (e["source"], e["target"], e["type"]) == ("comp::billing", "rc::rc_billing", "CAUSED_BY")


def test_should_expand_two_hops_when_hops_2(client, monkeypatch):
    captured = {}
    def run(cypher, **params):
        if "RETURN labels(n) AS nl" in cypher:
            return [{"nl": ["Component"], "np": {"name": "billing"}}]
        captured["cypher"] = cypher
        return []
    _patch_db_run(monkeypatch, run)
    r = client.get("/api/graph/subgraph", params={"expand": "comp::billing", "hops": 2})
    assert r.status_code == 200
    assert "*1..2" in captured["cypher"]   # variable-length inlined with validated int


# ── error envelope ────────────────────────────────────────────────────────────
def test_should_400_when_expand_prefix_unknown(client):
    r = client.get("/api/graph/subgraph", params={"expand": "bogus::x"})
    assert r.status_code == 400
    assert "error" in r.json() and "detail" not in r.json()


def test_should_404_when_node_not_found(client, monkeypatch):
    _patch_db_run(monkeypatch, lambda cypher, **p: [])  # center query returns nothing
    r = client.get("/api/graph/subgraph", params={"expand": "comp::nope"})
    assert r.status_code == 404
    assert r.json() == {"error": "not found"}


def test_should_422_when_hops_out_of_range(client):
    r = client.get("/api/graph/subgraph", params={"expand": "comp::billing", "hops": 3})
    assert r.status_code == 422
    assert "error" in r.json() and "detail" not in r.json()


def test_should_mount_graph_routes(client):
    paths = serve.app.openapi()["paths"]
    assert "/api/graph/schema" in paths and "/api/graph/subgraph" in paths
