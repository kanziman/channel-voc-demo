# issue-14 — router-chat (POST /api/chat) + retrieval-gating [NEW]

스택: **[BE] pytest**. `hybrid_search` 근거 조회 → 3분기 retrieval-gating(§5-6). answer 분기는 `rootcause.compute`로 실제 ₩값 보강.

## 1. 시그니처

```python
# src/server/routers/chat.py
router = APIRouter(prefix="/api", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None

class ChatResponse(BaseModel):
    answer: str
    arms: list[str]                      # 점등된 검색 갈래(D/S/G) union — retrieval trace
    subgraph_ref: dict | None = None     # 근거 패널이 /api/graph/subgraph 호출에 쓰는 참조
    confidence: float
    gate: str                            # "refuse" | "low_confidence" | "answer"
    related_questions: list[str]         # chips (항상 non-empty)
    interrupt_payload: dict | None = None  # #16에서 실제 승인 게이트 payload 주입 (여기선 None)

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest): ...
```

`serve.py`에 `include_router(chat.router)` → `POST /api/chat`.

### Retrieval-gating 정책 (§5-6 — 승격 임계값을 신뢰 경계로 사용)
§5-6은 **`ROOTCAUSE_MIN_CONVERSATIONS=8`(루트원인 승격 임계값)을 신뢰 경계**로 쓰라고 명시. 따라서 게이트는 arm 개수가 아니라 **top_component가 루트원인으로 승격됐는가**로 분기(ac-verifier #14가 arm-기반 divergence 지적 → 재설계).
`ev = hybrid_search(message, k=6)` → `results`. `rc = compute(write=False)`에서 top_component 매칭.
- **refuse** — `results == []`: 답 생성 차단, 정직한 거절 + 답가능 질문 chips. confidence 0.0.
- **low_confidence** — 근거는 있으나 `rc is None`(승격 임계값 `ROOTCAUSE_MIN_CONVERSATIONS` 미만): ⚠ 헤지("N건, 임계값 미만, 참고용") + 재질문 chips. confidence = min(n/threshold,1)·0.5 (≤0.5).
- **answer** — `rc` 승격됨(≥ threshold): 실제 ₩위험·회수·frequency·confidence(=`rc.confidence_avg`)로 답변 구성.

`arms` 필드 = 전체 결과의 arm union(트레이스 시각화). `subgraph_ref` = `{top_component, conversation_ids, root_cause_key?}`.
에러/500은 #13에서 단 전역 `{"error"}` 핸들러가 커버. LLM 미사용(답변은 실제 그래프 값으로 결정론적 구성 — §2.1).

### 테스트 전략
`hybrid_search`·`rootcause.compute`를 monkeypatch. `TestClient(serve.app)`로 3분기 각각 검증.

## 2. 테스트 시나리오

- [x] [예외] chat — should refuse with confidence 0 and chips when 0 hits
- [x] [경계] chat — should return low_confidence hedged answer when top result has a single arm
- [x] [정상] chat — should answer with real rootcause ₩ values when evidence is multi-arm
- [x] [정상] chat — should fall back to evidence answer when no promoted rootcause matches
- [x] [정상] chat — should expose arms union and subgraph_ref for the evidence panel
- [x] [경계] chat — should accept optional thread_id and default it to None
- [x] [정상] chat — should call hybrid_search with the message
- [x] [예외] chat — should return 422 {"error"} when message field missing
- [x] [정상] mount — should expose POST /api/chat on serve.app
- [x] [정상] chat — related_questions should always be non-empty (all branches)

## 3. AC 교차 대조

| AC | 시나리오 |
|---|---|
| chat.py 생성 | mount |
| POST /api/chat {message, thread_id?} | thread_id optional + call hybrid_search |
| 응답 {answer,arms,subgraph_ref,confidence,interrupt_payload?} | arms/subgraph_ref + 각 분기 |
| gating 3분기 | refuse / low_confidence / answer(+fallback) |
| pytest 3분기 검증 | 위 3 + fallback |
