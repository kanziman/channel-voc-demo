# issue-44 — frontend-shell: App 배선 (챗봇 셸 + 3-탭 콘솔 통합)

스택: **[FE]** `web/` (Vitest + RTL, react-cytoscapejs mock). 대상:
- `web/src/App.tsx` [MODIFY] — 정적 스캐폴드 → 상태 있는 통합 셸
- `web/src/App.test.tsx` [NEW]
- `web/src/components/ChatStream.tsx` — `onResponse`·`threadId` prop 추가(부작용 없음)
- 재사용(무변경): `EvidencePanel`, `ApprovalCard`, `OntologyGraphTab`, `HybridSearchTab`, `RootCauseGateTab`

## 0. 배선 계약 (기존 컴포넌트 → App)

- **ChatStream** 은 대화 상태를 내부 소유한다. App이 최신 답변의 `subgraph_ref`/`interrupt_payload`를 얻으려면 응답이 안착할 때 호출되는 **콜백**이 필요 → `onResponse(resp)` 추가.
- **thread_id**: `ChatResponse` 에는 없다. App이 세션 thread_id를 소유해 (a) `ChatStream` → chat 요청 `thread_id`, (b) `ApprovalCard.threadId` 에 동일 값 전달.
- **ApprovalCard 배치**: 목업은 인라인이나 ChatStream은 완성·불변이므로 재렌더하지 않는다. App은 오른쪽 레일(`.rail`)에 `ApprovalCard`(payload null이면 자체적으로 `null` 렌더) + `EvidencePanel` 을 세로 배치. 현재 `chat.py`는 `interrupt_payload`를 항상 null로 반환 → 카드는 배선되나 백엔드가 채우기 전까지 휴면(정상).
- **EvidencePanel.onExplore** ("⤢ 탐색") → App이 `view`를 `console`로 전환.
- **콘솔 3-탭**: 각 탭은 자체 fetch fn(기본값) 소유 → App은 탭 전환 셸(tabnav)만 제공. 테스트 주입을 위해 App은 선택적 `deps`로 각 fn을 하위에 전달.

## 1. 시그니처 (확정)

### web/src/components/ChatStream.tsx (변경분)
```ts
export interface ChatStreamProps {
  postChatFn?: (req: ChatRequest) => Promise<ChatResponse>;
  armStepMs?: number;
  onResponse?: (resp: ChatResponse) => void; // [NEW] 답변 안착 시 1회 호출
  threadId?: string;                          // [NEW] 요청 thread_id 로 전달
}
// runQuestion: postChatFn({ message: q, thread_id: threadId }) → 성공 시 onResponse?.(resp)
```

### web/src/App.tsx
```ts
import type { ChatRequest, ChatResponse } from "./api/chat";
import type { SubgraphQuery, SubgraphResponse } from "./api/graph";
import type { DispatchRequest, DispatchResponse, RootCause, RunResponse } from "./api/agent";
import type { HybridSearchRequest, HybridSearchResponse } from "./api/search";
import type { EvidenceSubgraphRef } from "./components/EvidencePanel";
import type { InterruptPayload } from "./api/agent";

export type View = "copilot" | "console";
export type ConsoleTab = "ontology" | "search" | "gate";

export interface AppDeps {
  postChatFn?: (req: ChatRequest) => Promise<ChatResponse>;
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>;
  dispatchFn?: (req: DispatchRequest) => Promise<DispatchResponse>;
  rootcausesFn?: () => Promise<{ rootcauses: RootCause[] }>;
  runFn?: (live?: boolean) => Promise<RunResponse>;
  searchFn?: (req: HybridSearchRequest) => Promise<HybridSearchResponse>;
}

export interface AppProps {
  deps?: AppDeps;
  initialThreadId?: string; // 기본 newThreadId()
  initialView?: View;       // 기본 "copilot"
  initialTab?: ConsoleTab;  // 기본 "ontology"
}

export function newThreadId(): string; // `t_${8자리 base36}` — mono 표시
export function App(props?: AppProps): JSX.Element;
```

동작 요약:
- 상태: `view`, `tab`, `latest: ChatResponse | null`, `threadId`.
- 파생: `subgraphRef = latest?.subgraph_ref as EvidenceSubgraphRef | null`; `interruptPayload = latest?.interrupt_payload as InterruptPayload | null`.
- copilot 뷰: `ChatStream(onResponse=setLatest, threadId, postChatFn)` | `.rail`( `ApprovalCard(interruptPayload, threadId, dispatchFn)` + `EvidencePanel(subgraphRef, onExplore=()=>setView("console"), getSubgraphFn)` ).
- console 뷰: `.tabnav`( ← 코파일럿 back + 3 탭 버튼, `aria-selected`) + 활성 탭 컴포넌트.
- 헤더 badge 에 `threadId`(mono) 노출.

## 2. 신규 CSS (App.css, 토큰만·그라데이션 금지)
`.rail`(flex column), `.console-view`, `.tabnav`, `.tabnav button`/`[aria-selected="true"]`, `.tab-back`. 기존 `.chat/.evidence/.approval-card/.console-tab/.ct-*/.rc-*/.st-*` 재사용.

## 3. 테스트 시나리오

### ChatStream (회귀 + 신규)
- [x] [정상] ChatStream — should send thread_id in the chat request when threadId prop is set
- [x] [정상] ChatStream — should invoke onResponse with the landed response when an answer arrives
- [x] [경계] ChatStream — should not invoke onResponse when postChatFn rejects (error turn)
- [x] [경계] ChatStream — 기존 회귀(23 tests) message 전송 등 objectContaining 유지

### App
- [x] [정상] App — should render copilot view by default (ChatStream composer + EvidencePanel placeholder present)
- [x] [정상] App — should own a session thread_id and pass it into the chat request (postChatFn called with thread_id)
- [x] [정상] App — should feed the latest response subgraph_ref into EvidencePanel (getSubgraphFn called with expand=rc::<key> after a promoted answer)
- [x] [정상] App — should show ApprovalCard when the latest response carries interrupt_payload
- [x] [경계] App — should not render ApprovalCard when interrupt_payload is null (default backend)
- [x] [정상] App — should switch to console view when EvidencePanel "⤢ 탐색" is clicked
- [x] [정상] App — should render 3 console tabs and switch active tab on tab-button click
- [x] [정상] App — should return to copilot view via the "← 코파일럿" back control
- [x] [경계] App — should render thread_id in the header (mono)
- [x] [경계] App — should default console active tab to ontology
- [x] [예외] App — should not crash when a console tab's fetch fn rejects (error placeholder rendered)

## 4. AC ↔ 시나리오 대조
| AC | 커버 시나리오 |
| :-- | :-- |
| copilot↔console 전환 | App switch to console / back to copilot |
| copilot: ChatStream+EvidencePanel+ApprovalCard 마운트 | render copilot view / show ApprovalCard when payload |
| subgraph_ref→EvidencePanel | feed subgraph_ref into EvidencePanel |
| interrupt_payload→ApprovalCard(null 미표시) | show ApprovalCard / not render when null |
| App 소유 thread_id → 요청+ApprovalCard | pass thread_id into request / render thread_id header + ChatStream thread_id |
| ChatStream onResponse/threadId(부작용 없음) | ChatStream onResponse + thread_id + omitted-behavior 회귀 |
| console 3-탭 셸+전환 | render 3 tabs and switch |
| ⤢탐색→콘솔 | switch to console via 탐색 |
| 토큰만·App.test 데이터흐름 | 위 App 시나리오 전반 (CSS는 리뷰 대조) |
