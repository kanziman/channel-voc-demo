# issue-30 — approval-gate-inchat: 채팅 내 승인 게이트 (interrupt-in-chat)

스택: **[FE]** `web/` (Vitest + RTL). 대상:
- `web/src/api/agent.ts` [NEW]
- `web/src/components/ApprovalCard.tsx` [NEW]
- 테스트: `agent.test.ts`, `ApprovalCard.test.tsx`

## 0. 백엔드 계약 (src/server/routers/agent.py, src/graph/dispatch.py)
- `POST /api/agent/dispatch` — req `{ thread_id, decision }` (decision: "approve"|"reject"|key[]) →
  `{ thread_id, status: "dispatched"|"rejected", dispatched: Action[] }`.
- interrupt payload(= chat/agent 응답의 `interrupt_payload`) = `{ message, candidates: Candidate[] }`.
  - Candidate `{ root_cause_key, component, title, revenue_at_risk_krw, confidence?, cited_conv_ids? }`.
- Action `{ key(act_*), root_cause_key, title, url|null, status, revenue_at_risk_krw, cited }`.
- 범위: ApprovalCard + agent.ts만. ChatStream/App 배선은 AC 밖(후속).

## 1. 시그니처 (확정)

### web/src/api/agent.ts
```ts
export interface InterruptCandidate {
  root_cause_key: string; component: string; title: string;
  revenue_at_risk_krw: number; confidence?: number; cited_conv_ids?: string[];
}
export interface InterruptPayload { message: string; candidates: InterruptCandidate[] }
export interface DispatchedAction {
  key: string; root_cause_key: string; title: string;
  url: string | null; status: string; revenue_at_risk_krw: number; cited: string[];
}
export interface DispatchResponse { thread_id: string; status: "dispatched" | "rejected"; dispatched: DispatchedAction[] }
export interface DispatchRequest { thread_id: string; decision: "approve" | "reject" | string | string[] }
// POST {API_BASE}/api/agent/dispatch. !ok → {error} 봉투 throw.
export async function postDispatch(req: DispatchRequest, signal?: AbortSignal): Promise<DispatchResponse>;
```

### web/src/components/ApprovalCard.tsx
```ts
export interface ApprovalCardProps {
  interruptPayload: InterruptPayload | null;
  threadId: string;
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>; // 기본 postDispatch
  onResolved?: (res: DispatchResponse) => void;
}
export function ApprovalCard(props: ApprovalCardProps): JSX.Element | null;
```
동작:
- `interruptPayload == null` → `null`(카드 미표시).
- 있으면 카드: message + 후보별(액션=title, 대상=component, 회수손실=revenue_at_risk_krw[mono ₩]) + thread_id(mono). 승인/반려 버튼.
- 승인 → `dispatchFn({thread_id, decision:"approve"})` → 결과 렌더(dispatched Action별 Issue url 링크 or status/act_ provenance). `onResolved(res)`.
- 반려 → `dispatchFn({thread_id, decision:"reject"})` → status "rejected" → "반려됨" 렌더. `onResolved(res)`.
- 디스패치 중 버튼 disabled. 실패 시 에러 메시지(카드 유지).
- thread_id·₩회수손실·act_ 키는 mono. 그라데이션 금지, 토큰만.

## 2. 테스트 시나리오

### agent.test.ts
- [x] [정상] postDispatch — should POST /api/agent/dispatch with {thread_id, decision}
- [x] [정상] postDispatch — should return the parsed DispatchResponse when res.ok
- [x] [예외] postDispatch — should throw the {error} envelope message when res.ok is false
- [x] [예외] postDispatch — should fall back to statusText when the error body is not JSON (ac-verifier)

### ApprovalCard.test.tsx
- [x] [경계] ApprovalCard — should render nothing when interruptPayload is null
- [x] [정상] ApprovalCard — should show action, target, thread_id(mono) and 회수손실(₩ mono) when payload present
- [x] [정상] ApprovalCard — should dispatch approve and render the opened issue link/provenance on 승인
- [x] [정상] ApprovalCard — should dispatch reject and render the rejected state on 반려
- [x] [정상] ApprovalCard — should call onResolved with the dispatch response after resolving
- [x] [경계] ApprovalCard — should disable the buttons while dispatching
- [x] [예외] ApprovalCard — should show an error and keep the card when dispatch fails

## 3. AC 교차 대조 (issue #30)
| AC | 커버 시나리오 |
| :-- | :-- |
| ApprovalCard.tsx 생성 | ApprovalCard 시나리오 전체 |
| agent.ts — POST /api/agent/dispatch({thread_id,decision}) | postDispatch 시나리오 |
| interrupt_payload 있을 때만 카드 렌더(액션·대상·thread_id·회수손실) | render nothing when null / show action,target,thread_id,회수손실 |
| 승인 → dispatch(approve) → 결과(Issue 링크/provenance) | dispatch approve renders issue link/provenance |
| 반려 → dispatch(reject) → resume | dispatch reject renders rejected state |
| thread_id/₩회수손실 mono | show ... thread_id(mono) and 회수손실(₩ mono) |
| vitest — interrupt 유무 분기 + approve/reject | 위 시나리오 |
