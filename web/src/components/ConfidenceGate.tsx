// Retrieval trust gate UI (§5-6). Turns the chat gate into an honest signal:
// refuse → a refusal banner + answerable-question chips; low_confidence → a ⚠
// hedge banner with the confidence value + re-ask chips; answer → nothing.
// Severity colors come from tokens only (--critical / --warning …), no gradients.
import { RelatedChips } from "./RelatedChips";
import type { ChatResponse } from "../api/chat";

export interface ConfidenceGateProps {
  gate: ChatResponse["gate"];
  confidence: number;
  relatedQuestions: string[];
  onPick: (q: string) => void;
  disabled?: boolean;
}

export function ConfidenceGate({
  gate,
  confidence,
  relatedQuestions,
  onPick,
  disabled = false,
}: ConfidenceGateProps) {
  if (gate === "answer") return null;

  const refuse = gate === "refuse";
  return (
    <div
      className={`gate ${refuse ? "gate-refuse" : "gate-low"}`}
      data-testid="confidence-gate"
      data-gate={gate}
    >
      <div className="gate-banner">
        {refuse ? (
          <span className="gate-label">근거 없음 · 답변 거절 — 아래 질문은 답할 수 있어요</span>
        ) : (
          <span className="gate-label">
            ⚠ 확신 낮음 · confidence <span className="gate-conf mono">{confidence}</span>
          </span>
        )}
      </div>
      <RelatedChips questions={relatedQuestions} onPick={onPick} disabled={disabled} />
    </div>
  );
}
