"""Load extractions → Neo4j knowledge graph (§2.1). Idempotent MERGE + embeddings.

Builds the graph of record:
  (Customer)-[:SENT]->(Conversation)-[:EXPRESSES]->(Intent)-[:ROLLS_UP_TO]->(Theme)
  (Conversation)-[:MENTIONS]->(Symptom)-[:IMPLICATES]->(Component)
Every Conversation carries a 384-d embedding (local fastembed) for GraphRAG.

Usage:
  python -m src.graph.load              # extract (cached) + load all 1,200
  python -m src.graph.load --limit 50   # subset
  python -m src.graph.load --keep       # don't wipe existing nodes first
"""
from __future__ import annotations

import argparse
import time

from . import config, db, llm
from .extract import extract_many, load_conversations
from .taxonomy import INTENT_TO_CATEGORY, INTENT_TO_COMPONENT

_LOAD_CYPHER = """
UNWIND $rows AS row
MERGE (conv:Conversation {id: row.conv_id})
  SET conv.text = row.text,
      conv.channel = row.channel,
      conv.created_at = row.created_at,
      conv.severity = row.severity,
      conv.confidence = row.confidence,
      conv.intent_true = row.intent_true
WITH conv, row
CALL db.create.setNodeVectorProperty(conv, 'embedding', row.embedding)
MERGE (cust:Customer {id: row.customer_id})
MERGE (cust)-[:SENT]->(conv)
MERGE (intent:Intent {name: row.intent})
MERGE (conv)-[:EXPRESSES]->(intent)
MERGE (theme:Theme {name: row.theme})
  SET theme.arm = row.theme
MERGE (intent)-[:ROLLS_UP_TO]->(theme)
MERGE (comp:Component {name: row.component})
WITH conv, comp, row
UNWIND row.symptoms AS sx
  MERGE (s:Symptom {text: sx})
  MERGE (conv)-[:MENTIONS]->(s)
  MERGE (s)-[:IMPLICATES]->(comp)
"""


def _prepare(extractions: list[dict]) -> list[dict]:
    """Attach embeddings, theme rollup, synthetic customer, symptom fallback."""
    texts = [e["text"] for e in extractions]
    print(f"  embedding {len(texts)} conversations (local fastembed)...")
    t = time.time()
    vecs = llm.embed(texts)
    print(f"  ✓ embedded ({time.time()-t:.1f}s)")

    rows = []
    for e, vec in zip(extractions, vecs):
        intent = e["intent"]
        symptoms = [s.strip().lower() for s in (e.get("symptoms") or []) if s and s.strip()]
        if not symptoms:  # keep every conv attached to its component
            symptoms = [f"{intent.replace('_', ' ')} issue"]
        rows.append(
            {
                "conv_id": e["conv_id"],
                "text": e["text"],
                "channel": e.get("channel", "web"),
                "created_at": e.get("created_at"),
                "severity": int(e.get("severity", 3)),
                "confidence": float(e.get("confidence", 0.5)),
                "intent": intent,
                "intent_true": e.get("intent_true"),
                "component": e.get("component") or INTENT_TO_COMPONENT.get(intent, "support"),
                "theme": INTENT_TO_CATEGORY.get(intent, "ACCOUNT"),
                "symptoms": symptoms[:3],
                "customer_id": f"cust_{e['conv_id'].split('_')[-1]}",
                "embedding": vec,
            }
        )
    return rows


def load(rows: list[dict], batch_size: int = 100) -> None:
    for i in range(0, len(rows), batch_size):
        db.run_write(_LOAD_CYPHER, rows=rows[i : i + batch_size])
        print(f"  loaded {min(i + batch_size, len(rows))}/{len(rows)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--keep", action="store_true", help="don't wipe existing nodes first")
    args = ap.parse_args()

    db.apply_schema()
    if not args.keep:
        print("Wiping existing graph...")
        db.wipe()

    convs = load_conversations(limit=args.limit)
    print(f"Extracting {len(convs)} (cached)...")
    extractions = extract_many(convs)
    rows = _prepare(extractions)

    print(f"Loading {len(rows)} conversations into Neo4j...")
    load(rows)

    print(f"\n✓ graph loaded. node counts: {db.counts()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
