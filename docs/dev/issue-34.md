# issue-34 — console-gate-tab: 탭3 루트원인 승인 센터

스택: **[FE]** `web/` (Vitest + RTL). 대상:
- `web/src/api/agent.ts` (확장: getRootcauses, postRun)
- `web/src/console/RootCauseGateTab.tsx` [NEW]
- 테스트: `web/src/console/RootCauseGateTab.test.tsx` (+ agent.test.ts에 getRootcauses/postRun)

## 0. 계약 (src/server/routers/agent.py)
- `GET /api/agent/rootcauses` → `{ rootcauses: RootCause[] }`.
  - RootCause `{ key, component, frequency, revenue_at_risk_krw, projected_recoverable_krw, severity_avg, confidence_avg, hypothesis, ... }`.
- `POST /api/agent/run {live}` → `{ thread_id, interrupt: InterruptPayload|null, dispatched: DispatchedAction[]|null }`.
- `POST /api/agent/dispatch {thread_id, decision}` → `{ thread_id, status, dispatched }` (기존 postDispatch #30).
- 승인/반려 = **run→dispatch 왕복**(상태없는 HTTP). decision: 승인 후보 key[] / "approve"(전체) / "reject"(전체).

## 1. 시그니처 (확정)

### web/src/api/agent.ts (추가)
```ts
export interface RootCause {
  key: string; component: string; frequency: number;
  revenue_at_risk_krw: number; projected_recoverable_krw: number;
  severity_avg: number; confidence_avg: number; hypothesis: string;
}
export interface RunResponse { thread_id: string; interrupt: InterruptPayload | null; dispatched: DispatchedAction[] | null }
export async function getRootcauses(signal?: AbortSignal): Promise<{ rootcauses: RootCause[] }>;   // GET /api/agent/rootcauses
export async function postRun(live?: boolean, signal?: AbortSignal): Promise<RunResponse>;          // POST /api/agent/run
```

### web/src/console/RootCauseGateTab.tsx
```ts
import type { DispatchRequest, DispatchResponse, RootCause, RunResponse } from "../api/agent";

export type Severity = "good" | "warning" | "serious" | "critical";
export function severityBucket(severityAvg: number): Severity; // 0.8+ critical / 0.6+ serious / 0.4+ warning / else good

export interface RootCauseGateTabProps {
  rootcausesFn?: () => Promise<{ rootcauses: RootCause[] }>;   // 기본 getRootcauses
  runFn?: (live?: boolean) => Promise<RunResponse>;           // 기본 postRun
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>; // 기본 postDispatch
}
export function RootCauseGateTab(props: RootCauseGateTabProps): JSX.Element;
```
동작:
- 마운트 시 `rootcausesFn()` → 카드 렌더(₩위험·₩회수·frequency·confidence 모두 mono, severity dot=토큰).
- 카드 승인 → `runFn()`→`dispatchFn({thread_id, decision:[key]})` → 카드 dispatched(Issue). 카드 반려 → run→dispatch("reject") → rejected.
- 일괄 승인 → dispatch("approve"), 일괄 반려 → dispatch("reject"). 액션 중 버튼 disabled. 실패 시 에러.
- severity 색은 good/warning/serious/critical 토큰만. 그라데이션 금지.

## 2. 테스트 시나리오

### agent.test.ts (추가)
- [x] [정상] getRootcauses — should GET /api/agent/rootcauses and return {rootcauses}
- [x] [정상] postRun — should POST /api/agent/run with {live} and return the run response

### RootCauseGateTab.test.tsx
- [x] [정상] severityBucket — should map severity_avg to good/warning/serious/critical thresholds
- [x] [경계] severityBucket — should place the exact threshold values in the higher bucket (>=) (ac-verifier)
- [x] [정상] RootCauseGateTab — should load rootcauses on mount and render ₩risk/₩recoverable/frequency/confidence (mono)
- [x] [정상] RootCauseGateTab — should approve a card via run→dispatch({decision:[key]}) and mark it dispatched
- [x] [정상] RootCauseGateTab — should bulk-approve via dispatch("approve")
- [x] [정상] RootCauseGateTab — should bulk-reject via dispatch("reject")
- [x] [정상] RootCauseGateTab — should reject only the clicked card and leave others pending (ac-verifier)
- [x] [정상] RootCauseGateTab — should approve only the clicked card (decision:[key]) and keep the other pending (ac-verifier)
- [x] [예외] RootCauseGateTab — should show an action error and keep the card pending when dispatch fails (ac-verifier)
- [x] [경계] RootCauseGateTab — should dispatch only once when 일괄 승인 is clicked twice (ac-verifier)
- [x] [경계] RootCauseGateTab — should show an error state when the rootcauses load fails

## 3. AC 교차 대조 (issue #34)
| AC | 커버 시나리오 |
| :-- | :-- |
| RootCauseGateTab.tsx 생성 | 시나리오 전체 |
| GET rootcauses 카드 목록(₩·frequency·confidence mono) | load rootcauses on mount + mono |
| 카드별 + 일괄 승인/반려 | approve a card / bulk-approve / bulk-reject |
| 승인/반려 → POST dispatch | run→dispatch({decision}) 시나리오 |
| severity 색 토큰만 | severityBucket + App.css .sev-* 토큰 (QA) |
| vitest — 카드 + 개별/일괄 dispatch | 위 시나리오 |
