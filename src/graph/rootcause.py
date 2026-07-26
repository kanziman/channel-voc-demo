"""Root-cause traversal (§2.2) — the decisive difference from a cluster label.

A RootCause is NOT a label assigned to one conversation. It is an *aggregation*:
a Component that many distinct conversations independently implicate gets
promoted to a RootCause node, carrying:
  - frequency        (distinct conversations)
  - revenue_at_risk  (Σ per-conversation ₩, PHASE1 assumptions model)
  - top_symptoms     (what customers actually said)
  - cooccurring      (symptom co-occurrence, §2.2b)
  - sample_conv_ids  (provenance — every ₩ traces to real conversations)
  - hypothesis       (LLM inference over the aggregate, cached)

Writes RootCause nodes + (Component)-[:CAUSED_BY]->(RootCause) back into Neo4j
so the graph stays the system of record.

Usage:  python -m src.graph.rootcause
"""
from __future__ import annotations

import collections
import json
import time

from src.pipeline import assumptions

from . import config, db, llm

# One row per (conversation, component) with intent/theme/severity/symptoms.
_TRAVERSE = """
MATCH (conv:Conversation)-[:EXPRESSES]->(i:Intent)-[:ROLLS_UP_TO]->(t:Theme)
MATCH (conv)-[:MENTIONS]->(s:Symptom)-[:IMPLICATES]->(comp:Component)
WITH conv, i, t, comp, collect(DISTINCT s.text) AS symptoms
RETURN conv.id AS id, conv.severity AS severity, coalesce(conv.confidence,0.5) AS confidence,
       i.name AS intent, t.name AS theme, comp.name AS component, symptoms
"""

_WRITE_ROOTCAUSE = """
MERGE (r:RootCause {key: $key})
  SET r.hypothesis = $hypothesis,
      r.component = $component,
      r.frequency = $frequency,
      r.revenue_at_risk_krw = $revenue_at_risk_krw,
      r.projected_recoverable_krw = $projected_recoverable_krw,
      r.severity_avg = $severity_avg,
      r.confidence_avg = $confidence_avg,
      r.top_symptoms = $top_symptoms,
      r.sample_conv_ids = $sample_conv_ids
WITH r
MATCH (comp:Component {name: $component})
MERGE (comp)-[:CAUSED_BY]->(r)
"""

_HYP_SYSTEM = (
    "You are a senior SRE/product engineer triaging customer VOC. Given a product "
    "component and the recurring symptoms customers report about it, state the single "
    "most likely underlying root cause in ONE concise, engineering-actionable sentence. "
    "No preamble, no hedging, no restating the symptoms verbatim."
)


def _hypothesis(component: str, top_symptoms: list[str]) -> str:
    cache = config.CACHE_DIR / "hypotheses" / config.CHAT_MODEL.replace("/", "_")
    cache.mkdir(parents=True, exist_ok=True)
    fp = cache / f"{component}.json"
    if fp.exists():
        return json.loads(fp.read_text())["hypothesis"]
    msg = (
        f"Component: {component}\n"
        f"Recurring customer symptoms (most frequent first):\n"
        + "\n".join(f"- {s}" for s, _ in top_symptoms[:10])
    )
    hyp = llm.chat().invoke([("system", _HYP_SYSTEM), ("human", msg)]).content.strip()
    fp.write_text(json.dumps({"component": component, "hypothesis": hyp}, ensure_ascii=False))
    return hyp


def compute(min_convs: int | None = None, write: bool = True) -> list[dict]:
    min_convs = min_convs or config.ROOTCAUSE_MIN_CONVERSATIONS
    rows = db.run(_TRAVERSE)

    # Aggregate per component (deduplicate conversations).
    by_comp: dict[str, dict] = collections.defaultdict(
        lambda: {"convs": {}, "symptoms": collections.Counter(), "pairs": collections.Counter()}
    )
    for r in rows:
        comp = r["component"]
        agg = by_comp[comp]
        cid = r["id"]
        if cid not in agg["convs"]:
            risk = assumptions.conversation_risk_krw(r["theme"], r["intent"])
            agg["convs"][cid] = {
                "id": cid,
                "severity": r["severity"],
                "confidence": r["confidence"],
                "intent": r["intent"],
                "theme": r["theme"],
                "risk_krw": risk,
            }
        syms = sorted(set(r["symptoms"]))
        for s in syms:
            agg["symptoms"][s] += 1
        for a in range(len(syms)):  # symptom co-occurrence (§2.2b)
            for b in range(a + 1, len(syms)):
                agg["pairs"][(syms[a], syms[b])] += 1

    root_causes = []
    for comp, agg in by_comp.items():
        convs = list(agg["convs"].values())
        freq = len(convs)
        if freq < min_convs:
            continue
        revenue = int(round(sum(c["risk_krw"] for c in convs)))
        top_symptoms = agg["symptoms"].most_common(8)
        # representative conversations: highest severity, then highest ₩.
        sample = sorted(convs, key=lambda c: (c["severity"], c["risk_krw"]), reverse=True)[:6]
        cooccur = [
            {"a": a, "b": b, "count": n}
            for (a, b), n in agg["pairs"].most_common(5)
            if n >= 2
        ]
        rc = {
            "key": f"rc_{comp}",
            "component": comp,
            "frequency": freq,
            "revenue_at_risk_krw": revenue,
            "projected_recoverable_krw": assumptions.projected_recoverable_krw(revenue),
            "severity_avg": round(sum(c["severity"] for c in convs) / freq, 2),
            "confidence_avg": round(sum(c["confidence"] for c in convs) / freq, 2),
            "top_symptoms": top_symptoms,
            "cooccurring": cooccur,
            "sample_conv_ids": [c["id"] for c in sample],
            "hypothesis": _hypothesis(comp, top_symptoms),
        }
        root_causes.append(rc)

    root_causes.sort(key=lambda x: x["revenue_at_risk_krw"], reverse=True)

    if write:
        for rc in root_causes:
            db.run_write(
                _WRITE_ROOTCAUSE,
                key=rc["key"],
                hypothesis=rc["hypothesis"],
                component=rc["component"],
                frequency=rc["frequency"],
                revenue_at_risk_krw=rc["revenue_at_risk_krw"],
                projected_recoverable_krw=rc["projected_recoverable_krw"],
                severity_avg=rc["severity_avg"],
                confidence_avg=rc["confidence_avg"],
                top_symptoms=[s for s, _ in rc["top_symptoms"]],
                sample_conv_ids=rc["sample_conv_ids"],
            )
    return root_causes


def main() -> int:
    t = time.time()
    rcs = compute()
    print(f"Root-cause traversal → {len(rcs)} root causes (min_convs={config.ROOTCAUSE_MIN_CONVERSATIONS}, {time.time()-t:.1f}s)\n")
    for i, rc in enumerate(rcs[:5], 1):
        krw = rc["revenue_at_risk_krw"]
        print(f"{i}. [{rc['component']}]  freq={rc['frequency']}  ₩{krw:,} at risk  sev={rc['severity_avg']}")
        print(f"   hypothesis: {rc['hypothesis']}")
        print(f"   top symptoms: {', '.join(s for s, _ in rc['top_symptoms'][:4])}")
        print(f"   evidence convs: {', '.join(rc['sample_conv_ids'][:4])}\n")

    out = config.OUT_DIR / "root_causes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rcs, ensure_ascii=False, indent=2))
    print(f"✓ wrote {out}  |  graph now has RootCause nodes: {db.counts().get('RootCause', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
