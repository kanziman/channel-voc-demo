# issue-27 — chat-cite-drilldown: 인라인 링크(cite) 드릴다운

스택: **[FE]** `web/` (Vitest + RTL). 대상 파일:
- `web/src/components/CiteLink.tsx` [NEW]
- `web/src/components/ChatStream.tsx` (통합: 답변 렌더 + 클릭 자동 제출)
- 테스트: `web/src/components/CiteLink.test.tsx`, 기존 `ChatStream.test.tsx`에 cite 통합 케이스 추가

## 0. spec ↔ 백엔드 갭 (기록)
현재 `POST /api/chat`의 answer prose(`src/server/routers/chat.py:97-100`)는
`'ORDER' 관련 근거 N건. 위험 ₩... 가설: ...` 형태로 **ID 토큰(rc_*/conv_*)을 직접 담지 않는다.**
실제 ID는 `subgraph_ref`(root_cause_key, conversation_ids)에만 존재.
→ #27은 AC대로 "답변 텍스트 내 ID 토큰" 링크화만 구현(범위 준수). 답변 prose에 rc 키를
노출시키는 것은 백엔드(#14) 후속으로 분리. CiteText는 백엔드가 ID를 노출하는 즉시 동작.

백엔드 ID 프리픽스(실측): `rc_<COMPONENT>`(rootcause.py:122, 대문자 가능), `conv_00000`(숫자),
`act_*`(dispatch.py:61), `cust_*`(load.py:76), `sym`(Symptom), `comp`(component).

## 1. 시그니처 (확정)

### web/src/components/CiteLink.tsx
```ts
// 그래프 백엔드가 방출하는 ID 프리픽스.
export const CITE_PREFIXES = ["rc", "sym", "conv", "comp", "act", "cust"] as const;

// 전역 매칭. <prefix>_<token>, token은 [A-Za-z0-9] 세그먼트를 _로 연결(대문자/숫자 허용).
export const CITE_RE: RegExp;

// 클릭된 ID에 대응하는 후속 질문 문자열. 예: "rc_ORDER" → "rc_ORDER 근거 대화 보여줘".
export function citeQuestion(id: string): string;

export interface CiteTextProps {
  text: string;
  onCite: (id: string) => void;
}
// text를 렌더하되 ID 토큰만 클릭 가능한 mono 링크(<button class="cite mono">)로 치환.
// 매칭되지 않는 텍스트는 그대로(verbatim) 출력.
export function CiteText(props: CiteTextProps): JSX.Element;
```

### ChatStream.tsx 통합
- 제출 파이프라인을 `runQuestion(q: string)`로 추출. `handleSubmit`(타이핑, 입력 clear 포함)과
  `handleCite(id) → runQuestion(citeQuestion(id))`(cite 클릭)가 공유. `tracing` 가드 유지.
- bot(비에러) 답변: `<div className="answer" data-testid="answer"><CiteText text={msg.text} onCite={handleCite} /></div>`.
- 회귀 보정: 기존 #26 "verbatim" 어서션은 `getByTestId("answer")` + `toHaveTextContent(answer)`로 변경
  (링크 분할과 무관하게 "내용 무손실" 의도를 검증). 다른 #26 테스트는 ID 없는 답변이라 영향 없음.

## 2. 테스트 시나리오

### CiteLink.test.tsx
- [x] [정상] citeQuestion — should build "<id> 근거 대화 보여줘" for a given id
- [x] [정상] CiteText — should render an rc_ id token as a clickable link
- [x] [정상] CiteText — should call onCite with the exact id when a cite link is clicked
- [x] [정상] CiteText — should render the cite link id in a mono element
- [x] [정상] CiteText — should linkify multiple distinct ids as separate links
- [x] [정상] CiteText — should linkify an uppercase/numeric id (rc_ORDER, conv_00012)
- [x] [경계] CiteText — should render plain text unchanged when no id token is present
- [x] [경계] CiteText — should not linkify a word with underscore but no known prefix (foo_bar, order_id)
- [x] [경계] CiteText — should disable cite links and not fire onCite when disabled is true (ac-verifier (b))
- [x] [회귀] CiteText — should produce no cite links for the current backend answer prose (ac-verifier (e), 갭 고정)

### ChatStream.test.tsx (cite 통합 추가)
- [x] [정상] ChatStream — should render an rc_ id in the answer as a clickable cite link
- [x] [정상] ChatStream — should auto-submit the follow-up question when a cite link is clicked
      (postChatFn 2회차가 "<id> 근거 대화 보여줘"로 호출되고, 그 텍스트의 user 메시지가 스트림에 추가)
- [x] [회귀] ChatStream — verbatim 어서션을 getByTestId("answer")+toHaveTextContent로 보정 (내용 무손실 유지)
- [x] [경계] ChatStream — should disable cite links and ignore clicks while a question is in flight (ac-verifier (b))

## 3. AC 교차 대조 (issue #27)
| AC | 커버 시나리오 |
| :-- | :-- |
| CiteLink.tsx 생성 | CiteText/citeQuestion 시나리오 전체 |
| 답변 텍스트 내 ID 토큰을 클릭 링크로 렌더 | render rc_ id as clickable link / multiple / uppercase-numeric |
| 클릭 시 후속 질문 자동 제출 | onCite exact id + ChatStream auto-submit follow-up |
| ID는 mono | should render the cite link id in a mono element |
| vitest — cite 클릭 → 후속 질문 디스패치 | ChatStream auto-submit follow-up |
