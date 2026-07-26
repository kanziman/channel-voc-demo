"""action_drafter (§2.3) — GraphRAG generation with citations.

Turns a root cause + its hybrid evidence into a GitHub Issue draft whose every
claim is traceable to real conversation ids. This is the "fact-grounded" proof:
the model is handed exact conv_ids and instructed to cite them inline.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from . import llm
from .retriever import hybrid_for_rootcause


class IssueDraft(BaseModel):
    title: str = Field(description="Concise, specific GitHub issue title (no ticket prefix).")
    body: str = Field(
        description="Markdown issue body. MUST cite evidence conversation ids inline "
        "as [conv_xxxxx]. Sections: **Problem**, **Root-cause hypothesis**, "
        "**Evidence** (bulleted, each citing a conv id), **Proposed fix**, **Impact**."
    )
    labels: list[str] = Field(description="2-4 GitHub labels, lowercase-kebab.", default_factory=list)
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="Engineering severity implied by frequency + customer impact."
    )


_SYSTEM = (
    "You are a staff engineer writing a crisp, actionable GitHub issue from VOC "
    "evidence. Ground EVERY factual claim in the provided conversations and cite "
    "their ids inline as [conv_xxxxx]. Never invent conversation ids or facts not "
    "supported by the evidence. Be concrete and buildable; no marketing language."
)


def _krw(n: int) -> str:
    return f"₩{n:,}"


def draft_for_rootcause(rc: dict, k_vector: int = 5, k_graph: int = 5) -> dict:
    ctx = hybrid_for_rootcause(rc, k_vector=k_vector, k_graph=k_graph)
    evidence_block = "\n".join(
        f"- [{e['id']}] (severity {e.get('severity')}, "
        f"{'sim ' + format(e['similarity']*100, '.0f') + '%' if 'similarity' in e else 'graph-neighbor'}): "
        f"{(e['text'] or '').strip()[:200]}"
        for e in ctx["evidence"][:10]
    )
    human = (
        f"Component: {rc['component']}\n"
        f"Root-cause hypothesis: {rc['hypothesis']}\n"
        f"Distinct conversations implicating this component: {rc['frequency']}\n"
        f"Revenue at risk: {_krw(rc['revenue_at_risk_krw'])} "
        f"(projected recoverable {_krw(rc['projected_recoverable_krw'])})\n"
        f"Top recurring symptoms: {', '.join(s for s, _ in rc['top_symptoms'][:6])}\n\n"
        f"Evidence conversations (cite these ids):\n{evidence_block}"
    )
    draft: IssueDraft = llm.chat().with_structured_output(IssueDraft).invoke(
        [("system", _SYSTEM), ("human", human)]
    )
    cited = [e["id"] for e in ctx["evidence"] if f"[{e['id']}]" in draft.body]
    return {
        "root_cause_key": rc["key"],
        "component": rc["component"],
        "title": draft.title,
        "body": draft.body,
        "labels": draft.labels,
        "severity": draft.severity,
        "revenue_at_risk_krw": rc["revenue_at_risk_krw"],
        "projected_recoverable_krw": rc["projected_recoverable_krw"],
        "confidence": rc["confidence_avg"],
        "frequency": rc["frequency"],
        "cited_conv_ids": cited,
        "evidence": ctx["evidence"][:10],
        "n_both": ctx["n_both"],
    }


def main() -> int:
    import json

    from . import config

    rcs = json.loads((config.OUT_DIR / "root_causes.json").read_text())
    d = draft_for_rootcause(rcs[0])
    print(f"TITLE: {d['title']}")
    print(f"LABELS: {d['labels']}  SEVERITY: {d['severity']}  ₩{d['revenue_at_risk_krw']:,}")
    print(f"CITED conv ids ({len(d['cited_conv_ids'])}): {d['cited_conv_ids']}\n")
    print(d["body"][:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
