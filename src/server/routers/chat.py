"""POST /api/chat — retrieval-gated copilot answers (§2.4, §5-6) [NEW].

Pipeline: hybrid_search retrieves evidence → a 3-branch gate decides whether to
refuse, hedge, or answer. Answers are composed from *real graph values*
(rootcause aggregates), not free LLM generation, so the bot can't hallucinate
past its evidence — the honesty property the demo needs to prove it is
graph-grounded.

Gate (deterministic — §5-6 uses the root-cause promotion threshold,
ROOTCAUSE_MIN_CONVERSATIONS, as the confidence boundary):
  results == []                         → refuse        (no evidence; honest refusal + chips)
  evidence but component NOT promoted   → low_confidence (< threshold convs; hedged + chips)
  component promoted to a root cause    → answer         (>= threshold; enrich with real ₩)
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ...graph import config
from ...graph.retriever import hybrid_search
from ...graph.rootcause import compute as compute_rootcauses

router = APIRouter(prefix="/api", tags=["chat"])

_SEED_CHIPS = [
    "손실 Top3 루트원인은?",
    "가장 심각한 컴포넌트는?",
    "billing 이슈 근거 대화 보여줘",
]


def _related_chips(component: str | None) -> list[str]:
    if not component:
        return list(_SEED_CHIPS)
    return [
        f"{component} 근거 대화 보여줘",
        f"{component} 위험액은 얼마야?",
        f"{component} 대표 증상 Top5는?",
    ]


def _cite_tail(conv_ids: list[str], limit: int = 3) -> str:
    """Trailing '근거 대화: <ids>.' clause so answer prose carries cite-drilldown
    ids (#46) — the frontend CITE_RE linkifies conv_xxxxx / rc_xxx tokens."""
    ids = conv_ids[:limit]
    return f" 근거 대화: {', '.join(ids)}." if ids else ""


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    arms: list[str]
    subgraph_ref: dict | None = None
    confidence: float
    gate: str
    related_questions: list[str]
    interrupt_payload: dict | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    ev = hybrid_search(req.message, k=6)
    results = ev.get("results", [])
    top_component = ev.get("top_component")
    arms_union = sorted({a for r in results for a in r.get("arms", [])})

    # ── refuse: no evidence at all ────────────────────────────────────────────
    if not results:
        return ChatResponse(
            answer="VOC 지식그래프에 근거가 없어 답할 수 없어요. 아래 질문은 답할 수 있어요.",
            arms=[], subgraph_ref=None, confidence=0.0, gate="refuse",
            related_questions=list(_SEED_CHIPS),
        )

    conv_ids = [r["id"] for r in results]
    comp_label = f"'{top_component}' " if top_component else ""

    # The root-cause promotion threshold (ROOTCAUSE_MIN_CONVERSATIONS) IS the
    # confidence boundary (§5-6): a promoted root cause == enough corroborated
    # evidence to answer; otherwise the evidence is below threshold → hedge.
    rc = next((r for r in compute_rootcauses(write=False)
               if r["component"] == top_component), None)

    # ── low_confidence: evidence exists but component not promoted (< threshold) ─
    if rc is None:
        threshold = config.ROOTCAUSE_MIN_CONVERSATIONS
        conf = round(min(len(results) / threshold, 1.0) * 0.5, 2)  # capped < 0.5
        # Surface the evidence conv ids so the hedged answer is still traversable.
        return ChatResponse(
            answer=(f"⚠ 확신이 낮아요 — {comp_label}근거 {len(results)}건은 루트원인 승격 "
                    f"임계값({threshold}건) 미만이라 참고용으로만 보세요.{_cite_tail(conv_ids)}"),
            arms=arms_union,
            subgraph_ref={"top_component": top_component, "conversation_ids": conv_ids},
            confidence=conf, gate="low_confidence",
            related_questions=_related_chips(top_component),
            interrupt_payload=None,
        )

    # ── answer: promoted root cause → compose from real ₩ / frequency values ──
    # Embed the rootcause key + representative conv ids so the operator can drill
    # into the graph via cite-drilldown (#46); both match the frontend CITE_RE.
    answer = (
        f"루트원인 {rc['key']} — '{top_component}' 관련 근거 {rc['frequency']}건. "
        f"위험 ₩{rc['revenue_at_risk_krw']:,}, 회수가능 ₩{rc['projected_recoverable_krw']:,}, "
        f"confidence {rc['confidence_avg']}. 가설: {rc['hypothesis']}."
        f"{_cite_tail(rc.get('sample_conv_ids') or conv_ids)}"
    )
    return ChatResponse(
        answer=answer, arms=arms_union,
        subgraph_ref={"top_component": top_component, "root_cause_key": rc["key"],
                      "conversation_ids": rc.get("sample_conv_ids", conv_ids)},
        confidence=rc["confidence_avg"], gate="answer",
        related_questions=_related_chips(top_component),
        interrupt_payload=None,
    )
