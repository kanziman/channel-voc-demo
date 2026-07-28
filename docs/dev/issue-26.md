# issue-26 — chat-stream: 대화 스트림 + retrieval trace (D/S/G arm 점등)

스택: **[FE]** `web/` (Vitest + React Testing Library). 대상 파일:
- `web/src/api/chat.ts` [NEW]
- `web/src/components/ChatStream.tsx` [NEW]
- 테스트: 동일 폴더 `chat.test.ts`, `ChatStream.test.tsx`

## 1. 시그니처 (확정)

### web/src/api/chat.ts
```ts
export interface ChatRequest {
  message: string;
  thread_id?: string;
}
export interface ChatResponse {
  answer: string;
  arms: string[];
  subgraph_ref: Record<string, unknown> | null;
  confidence: number;
  gate: "refuse" | "low_confidence" | "answer";
  related_questions: string[];
  interrupt_payload: Record<string, unknown> | null;
}
// POST {API_BASE}/api/chat, body=JSON(req). !res.ok → 응답 {error} 봉투를 메시지로 throw.
export async function postChat(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>;
```
- `API_BASE = import.meta.env.VITE_API_BASE ?? ""` (동일 오리진 기본, serve.py 전역 {"error"} 봉투와 정합).

### web/src/components/ChatStream.tsx
```ts
export const ARM_ORDER = ["D", "S", "G"] as const; // Dense/Sparse/Graph — 관통 시각 언어, 재사용 금지
type Role = "user" | "bot";
interface StreamMessage {
  id: string;
  role: Role;
  text: string;
  arms?: string[];            // bot 메시지에만: 응답 arms union
  gate?: ChatResponse["gate"];
  confidence?: number;
}
interface ChatStreamProps {
  postChatFn?: (req: ChatRequest) => Promise<ChatResponse>; // 테스트 주입, 기본 = postChat
  armStepMs?: number;                                       // arm 점등 간격(ms), 기본 220
}
export function ChatStream(props: ChatStreamProps): JSX.Element;
```

### 동작 명세
1. composer에 질문 입력 후 제출 → 즉시 `role:"user"` 메시지 append, 입력창 clear.
2. 제출 직후 retrieval trace 활성: `D → S → G` 순서로 각 `armStepMs`마다 한 arm씩 점등.
   응답 `arms`에 포함된 arm = hit(강조), 미포함 = dim. 점등 상태는 `data-arm`/`data-state`(pending|lit)로 노출.
3. G까지 점등 완료 후 `role:"bot"` 메시지 append, `text = response.answer` **그대로**(클라이언트 재생성/포맷 금지).
4. `postChatFn` reject 시 스트림에 오류 메시지 append(크래시 없음), trace 종료.
5. 색·간격은 `var(--token)`만. 그라데이션 금지. arm 라벨·ID·confidence는 mono.

### 에러/경계 케이스
- `postChat`: `res.ok===false`면 body의 `{error}` 문자열(없으면 statusText)로 `throw new Error`.
- refuse 게이트: `arms:[]` → trace는 3-arm 애니메이션을 돌리되 전부 dim, answer(거절문) 렌더.
- 빈 입력/공백 제출 → 전송 무시(메시지 append 안 함).

## 2. 테스트 시나리오

### web/src/api/chat.ts — chat.test.ts
- [x] [정상] postChat — should POST to /api/chat with JSON body and return parsed ChatResponse when res.ok
- [x] [정상] postChat — should include thread_id in body when provided
- [x] [예외] postChat — should throw Error with {error} envelope message when res.ok is false
- [x] [예외] postChat — should throw with statusText when error body is absent/unparseable

### web/src/components/ChatStream.tsx — ChatStream.test.tsx
- [x] [정상] ChatStream — should append the user message to the stream when a question is submitted
- [x] [정상] ChatStream — should clear the composer input after submit
- [x] [정상] ChatStream — should light arms in D→S→G order (D lit before S before G) when awaiting the answer
- [x] [정상] ChatStream — should render the bot answer only after all three arms have lit
- [x] [정상] ChatStream — should render response.answer verbatim (exact ₩ text, no client-side regeneration)
- [x] [정상] ChatStream — should mark arms present in response.arms as lit-hit and absent ones as dim
- [x] [경계] ChatStream — should still complete the trace and render the refuse answer when arms is empty
- [x] [경계] ChatStream — should ignore submit when the input is empty or whitespace
- [x] [예외] ChatStream — should append an error message and not crash when postChatFn rejects

## 3. AC 교차 대조 (issue #26)
| AC | 커버 시나리오 |
| :-- | :-- |
| `web/src/components/ChatStream.tsx` 생성 | 컴포넌트 시나리오 전체 |
| `web/src/api/chat.ts` — POST /api/chat, 전 필드 파싱 | postChat 정상/thread_id 시나리오 |
| 질문 전송 → 스트림 append | should append the user message |
| 답변 전 D/S/G 순차 점등 | should light arms in D→S→G order |
| 답변은 `answer` 그대로(재생성 금지) | should render response.answer verbatim |
| `cd web && vitest` 순서 검증 | arm order + answer-after-arms 시나리오 |
| 디자인: token만/그라데이션 금지/수치 mono | (테스트 대상 아님 → tdd-refactor·security-review·QA에서 검증) |
