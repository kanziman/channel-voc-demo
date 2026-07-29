# issue-28 — chat-related-chips: 연관 질문 chips (항상 표시)

스택: **[FE]** `web/` (Vitest + RTL). 대상:
- `web/src/components/RelatedChips.tsx` [NEW]
- `web/src/components/ChatStream.tsx` (통합)
- 테스트: `RelatedChips.test.tsx`, 기존 `ChatStream.test.tsx`에 chips 통합 케이스

## 1. 시그니처 (확정)

### web/src/components/RelatedChips.tsx
```ts
// Cold-start seeds — mirrors src/server/routers/chat.py:_SEED_CHIPS so the panel
// is never empty before the first answer.
export const SEED_CHIPS: string[]; // ["손실 Top3 루트원인은?", "가장 심각한 컴포넌트는?", "billing 이슈 근거 대화 보여줘"]

export interface RelatedChipsProps {
  questions: string[];
  onPick: (question: string) => void;
  disabled?: boolean;
}
// questions가 비면 SEED_CHIPS로 폴백(항상 non-empty). 각 질문 = 클릭 가능한 chip 버튼.
export function RelatedChips(props: RelatedChipsProps): JSX.Element;
```

### ChatStream.tsx 통합
- `relatedQuestions` 상태(초기 `[]` → RelatedChips가 시드 폴백). bot 응답마다 `setRelatedQuestions(resp.related_questions)`.
- composer 위에 `<RelatedChips questions={relatedQuestions} onPick={runQuestion} disabled={tracing} />`.
- chip 클릭 → `runQuestion(question)`(자동 제출). tracing 중 비활성.

## 2. 테스트 시나리오

### RelatedChips.test.tsx
- [x] [정상] RelatedChips — should render each question as a clickable chip
- [x] [정상] RelatedChips — should call onPick with the question text when a chip is clicked
- [x] [경계] RelatedChips — should render SEED_CHIPS when questions is empty (never empty)
- [x] [경계] RelatedChips — should disable chips and not fire onPick when disabled is true

### ChatStream.test.tsx (chips 통합 추가)
- [x] [정상] ChatStream — should show seed chips before any question (cold-start non-empty)
- [x] [정상] ChatStream — should replace chips with response.related_questions after an answer
- [x] [정상] ChatStream — should auto-submit the question when a related chip is clicked

## 3. AC 교차 대조 (issue #28)
| AC | 커버 시나리오 |
| :-- | :-- |
| RelatedChips.tsx 생성 | RelatedChips 시나리오 전체 |
| response.related_questions로 chips 갱신 | should replace chips with response.related_questions |
| 초기 시드 chips(빈 배열 방지) | SEED_CHIPS when empty / show seed chips before any question |
| chip 클릭 → 자동 제출 | call onPick + ChatStream auto-submit |
| vitest — 시드/갱신/클릭 | 위 3 통합 시나리오 |
