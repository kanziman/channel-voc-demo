# issue-31 — retrieval-gate-ui: 신뢰도 게이트 UI (거절 / 확신 낮음)

스택: **[FE]** `web/` (Vitest + RTL). 대상:
- `web/src/components/ConfidenceGate.tsx` [NEW]
- `web/src/components/ChatStream.tsx` (통합)
- 테스트: `ConfidenceGate.test.tsx`, 기존 `ChatStream.test.tsx`에 gate 통합 케이스

## 0. 계약 (§5-6, web/src/api/chat.ts)
- `ChatResponse.gate ∈ {"refuse","low_confidence","answer"}`, `confidence: number`, `related_questions: string[]`.
- refuse: 0 hits → 정직한 거절 + 답 가능한 질문 chips. low_confidence: 경계 → ⚠ 배너 + confidence + 재질문 chips. answer: 배너 없음.
- chips는 #28 RelatedChips 재사용(빈 배열→시드 폴백). severity 색은 토큰(good/warning/serious/critical)만.

## 1. 시그니처 (확정)

### web/src/components/ConfidenceGate.tsx
```ts
import type { ChatResponse } from "../api/chat";
export interface ConfidenceGateProps {
  gate: ChatResponse["gate"];
  confidence: number;
  relatedQuestions: string[];
  onPick: (q: string) => void;
  disabled?: boolean;
}
// gate==="answer" → null. refuse/low_confidence → severity 배너 + (low_confidence 시 confidence mono) + RelatedChips.
export function ConfidenceGate(props: ConfidenceGateProps): JSX.Element | null;
```

### ChatStream.tsx 통합
- 최신 비에러 bot 메시지의 gate가 refuse/low_confidence면 그 아래 `<ConfidenceGate ... onPick={runQuestion} disabled={tracing}/>`를 렌더하고, **composer의 RelatedChips는 대체**(중복 방지). 그 외(answer/초기)면 기존 composer RelatedChips.
- StreamMessage는 이미 gate·confidence 보유(#26). refuse/low_confidence 답변은 severity 색 배너로 강조.

## 2. 테스트 시나리오

### ConfidenceGate.test.tsx
- [x] [정상] ConfidenceGate — should render nothing when gate is "answer"
- [x] [정상] ConfidenceGate — should render a refusal banner and answerable-question chips when gate is "refuse"
- [x] [정상] ConfidenceGate — should render a ⚠ low-confidence banner with confidence (mono) and chips when gate is "low_confidence"
- [x] [정상] ConfidenceGate — should call onPick with the question when a gate chip is clicked
- [x] [경계] ConfidenceGate — should still show seed chips (never empty) when relatedQuestions is empty
- [x] [경계] ConfidenceGate — should also seed-fall-back chips for the low_confidence branch when empty (ac-verifier)
- [x] [정상] ConfidenceGate — should expose data-gate for the gate branch (styling hook)

### ChatStream.test.tsx (gate 통합 추가)
- [x] [정상] ChatStream — should show the confidence gate banner (not plain composer chips) after a refuse answer
- [x] [정상] ChatStream — should show the ⚠ low-confidence banner with confidence after a low_confidence answer
- [x] [정상] ChatStream — should not show a gate banner after a normal (answer) response
- [x] [정상] ChatStream — should replace (not duplicate) the composer chips when a gate banner is shown (ac-verifier)
- [x] [정상] ChatStream — should clear the gate banner once a later answer turn arrives (ac-verifier)

## 3. AC 교차 대조 (issue #31)
| AC | 커버 시나리오 |
| :-- | :-- |
| ConfidenceGate.tsx 생성 | ConfidenceGate 시나리오 전체 |
| gate 3분기 렌더 (refuse/low-confidence/sufficient) | answer→null / refuse 배너 / low_confidence 배너 + ChatStream 3케이스 |
| refuse → 거절 메시지 + 답 가능한 질문 chips | refusal banner + chips |
| low-confidence → ⚠ 배너 + confidence(mono) + 재질문 chips | low-confidence banner with confidence(mono) + chips |
| severity 색 토큰만 | (App.css .gate-* → var(--critical/--warning) 확인; QA/security) |
| vitest — 3분기 UI | 위 통합 시나리오 |
