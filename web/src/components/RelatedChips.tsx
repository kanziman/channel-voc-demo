// Related-question chips (§2, §5-5). Always non-empty: seeds on cold start,
// then contextual follow-ups from each answer. Tokens only, no gradients.

// Cold-start seeds — mirrors src/server/routers/chat.py:_SEED_CHIPS.
export const SEED_CHIPS: string[] = [
  "손실 Top3 루트원인은?",
  "가장 심각한 컴포넌트는?",
  "billing 이슈 근거 대화 보여줘",
];

export interface RelatedChipsProps {
  questions: string[];
  onPick: (question: string) => void;
  disabled?: boolean;
}

export function RelatedChips({ questions, onPick, disabled = false }: RelatedChipsProps) {
  const chips = questions.length > 0 ? questions : SEED_CHIPS;
  return (
    <div className="chips">
      {chips.map((q) => (
        <button
          key={q}
          type="button"
          className="chip"
          disabled={disabled}
          onClick={() => onPick(q)}
        >
          <span className="chip-icon" aria-hidden="true" style={{ marginRight: 4, opacity: 0.8 }}>✦</span>
          {q}
        </button>
      ))}
    </div>
  );
}
