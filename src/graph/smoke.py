"""PHASE 2.0 verification gate (§2.0).

Proves the full stack end-to-end in one command:
  1. Neo4j write + read round-trip
  2. OpenRouter chat round-trip (via the llm.py factory)
  3. Local fastembed embedding (384-d)
  4. Schema applies (constraints + vector index present)

Usage:  python -m src.graph.smoke
Exit 0 = gate passed.
"""
from __future__ import annotations

import time

from . import db, llm


def _t(label: str, fn):
    t = time.time()
    out = fn()
    print(f"  ✓ {label} ({time.time() - t:.2f}s)")
    return out


def main() -> int:
    print("PHASE 2.0 smoke — full-stack de-risk\n")

    print("[1/4] Neo4j write/read round-trip")
    _t("apply schema (constraints + vector index)", db.apply_schema)
    _t(
        "write :SmokeTest node",
        lambda: db.run_write(
            "MERGE (s:SmokeTest {id:'smoke'}) SET s.at=timestamp() RETURN s.id"
        ),
    )
    got = _t(
        "read it back",
        lambda: db.run("MATCH (s:SmokeTest {id:'smoke'}) RETURN s.id AS id"),
    )
    assert got and got[0]["id"] == "smoke", "Neo4j round-trip failed"
    db.run_write("MATCH (s:SmokeTest) DELETE s")

    print("\n[2/4] OpenRouter chat round-trip")
    reply = _t("chat('OK')", lambda: llm.chat().invoke("Reply with one word: OK").content)
    assert "ok" in reply.lower(), f"unexpected chat reply: {reply!r}"
    print(f"       reply = {reply!r}")

    print("\n[3/4] Local fastembed embedding")
    vecs = _t("embed 2 texts", lambda: llm.embed(["checkout is broken", "payment failed"]))
    assert len(vecs[0]) == 384, f"expected 384-d, got {len(vecs[0])}"
    print(f"       dim = {len(vecs[0])}")

    print("\n[4/4] Graph state")
    print(f"       node counts = {db.counts()}")

    print("\n✅ GATE PASSED — Neo4j + OpenRouter + fastembed all green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
