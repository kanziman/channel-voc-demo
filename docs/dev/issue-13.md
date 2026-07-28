# issue-13 — router-search (POST /api/search/hybrid) [WRAP]

스택: **[BE] pytest**. `retriever.hybrid_search()`의 얇은 HTTP 어댑터. 신규 로직 금지.

## 1. 시그니처

```python
# src/server/routers/search.py
router = APIRouter(prefix="/api/search", tags=["search"])

class HybridSearchRequest(BaseModel):
    query: str
    k: int = 6

class HybridResult(BaseModel):
    id: str
    dense: float | None = None
    sparse: float | None = None
    in_graph: bool = False
    text: str | None = None
    component: str | None = None
    severity: float | None = None
    rrf: float = 0.0
    arms: list[str] = []

class HybridSearchResponse(BaseModel):
    query: str
    top_component: str | None = None
    counts: dict[str, int]
    results: list[HybridResult]

@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid(req: HybridSearchRequest):
    return hybrid_search(req.query, k=req.k)   # 기존 함수 그대로, 신규 로직 없음
```

`src/graph/serve.py`에서 `app.include_router(search.router)`로 마운트 → 최종 경로 `POST /api/search/hybrid`.

### AC 해석 메모
- AC의 응답 "{results, arms, rrf}"에서 `arms`·`rrf`는 **per-result 필드**(각 result 안). 실제 `hybrid_search` 반환의 top-level은 `query/top_component/counts/results`이며 이를 무손실 모델링(대시보드/콘솔 호환).
- 기존 `/search`(대시보드용)는 그대로 두고 신규 `/api/search/hybrid`만 추가 → 회귀 없음.
- 에러 봉투는 #11에서 앱에 단 `{"error":...}` 핸들러가 이 라우터에도 동일 적용.

### 테스트 전략
`retriever.hybrid_search`(Neo4j+fastembed 실호출)를 monkeypatch. `TestClient(serve.app)`로 마운트된 실제 경로 검증.

## 2. 테스트 시나리오

- [x] [정상] hybrid — should return 200 with query/top_component/counts/results when query valid
- [x] [정상] hybrid — should preserve per-result arms and rrf fields (passthrough)
- [x] [정상] hybrid — should call hybrid_search with the given query and k
- [x] [경계] hybrid — should default k to 6 when k omitted
- [x] [예외] hybrid — should return 422 {"error"} when query field missing (app error envelope)
- [x] [정상] mount — should expose POST /api/search/hybrid on serve.app
- [x] [예외] hybrid — should return 500 {"error"} when hybrid_search raises (전역 핸들러)

> **ac-verifier #13 갭 보강**: 신규 라우터의 런타임 500이 plain-text였음 → serve.py에 전역 `Exception` 핸들러 추가로 `{"error": str(exc)}` 봉투 통일(모든 라우터 공통 적용, 향후 chat/graph/agent 포함).

## 3. AC 교차 대조

| AC | 시나리오 |
|---|---|
| search.py 생성 | (모듈 존재 — 임포트로 성립) |
| POST /api/search/hybrid 요청/응답 | hybrid 정상 + mount |
| hybrid_search 직접 호출(신규 로직 금지) | call hybrid_search with query/k |
| Pydantic 응답 모델(arms 구조) | passthrough arms/rrf |
| pytest 통과 | 전체 |
