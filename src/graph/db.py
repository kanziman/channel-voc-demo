"""Neo4j driver helper — thin wrapper over the official driver.

Uses the raw neo4j Python driver (not langchain's Neo4jGraph) so we control
transactions, parameterised writes, and vector-index queries directly.
"""
from __future__ import annotations

import functools
from pathlib import Path

from neo4j import Driver, GraphDatabase

from . import config


@functools.lru_cache(maxsize=1)
def driver() -> Driver:
    config.require("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    return GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
        notifications_disabled_categories=["DEPRECATION", "GENERIC"],
    )


def run(cypher: str, **params):
    """Run a single Cypher statement, return list[dict]."""
    with driver().session(database=config.NEO4J_DATABASE) as s:
        return [r.data() for r in s.run(cypher, **params)]


def run_write(cypher: str, **params):
    with driver().session(database=config.NEO4J_DATABASE) as s:
        return s.execute_write(lambda tx: [r.data() for r in tx.run(cypher, **params)])


def apply_schema(path: Path | None = None) -> int:
    """Execute every statement in schema.cypher (idempotent). Returns count."""
    path = path or (Path(__file__).parent / "schema.cypher")
    # Split on ';', then strip //-comment lines from each chunk. A chunk that
    # begins with a comment block must NOT be discarded — its CREATE lives below
    # the comment (dropping it silently skipped the vector/full-text indexes).
    cleaned = []
    for chunk in path.read_text().split(";"):
        body = "\n".join(
            ln for ln in chunk.splitlines() if not ln.strip().startswith("//")
        ).strip()
        if body:
            cleaned.append(body)
    with driver().session(database=config.NEO4J_DATABASE) as sess:
        for stmt in cleaned:
            sess.run(stmt).consume()  # consume so DDL errors surface (not lazy)
    return len(cleaned)


def wipe() -> None:
    """Delete all nodes/relationships (fresh reload). Keeps constraints/indexes."""
    run_write("MATCH (n) DETACH DELETE n")


def counts() -> dict:
    rows = run(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC"
    )
    return {r["label"]: r["n"] for r in rows}
