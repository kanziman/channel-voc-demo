"""Apply the Neo4j schema (constraints + vector index). Idempotent.

Usage:  python -m src.graph.schema
"""
from __future__ import annotations

from . import db


def main() -> int:
    n = db.apply_schema()
    print(f"✓ applied {n} schema statements (constraints + vector index)")
    idx = db.run("SHOW INDEXES YIELD name, type WHERE name = 'conversation_embedding' RETURN name, type")
    print(f"✓ vector index: {idx or 'MISSING'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
