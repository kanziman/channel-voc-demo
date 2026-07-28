# issue-11 — serve-fastapi-migration (stdlib http.server → FastAPI)

스택: **[BE] Python / pytest**. 대상 `src/graph/serve.py`. 사양 PHASE3_PLAN §3.1·§5-2.

## 1. 확정 시그니처

```python
# src/graph/serve.py
app = FastAPI(title="VOC live hybrid search")
# CORS: 대시보드(file:///정적)→127.0.0.1 교차출처 회귀 방지 (allow_origins=*)

class SearchRequest(BaseModel):
    query: str
    k: int = 6

@app.get("/health") -> dict
#   200 {"status": "ok", "model": config.EMBED_MODEL, "dim": config.EMBED_DIM}

@app.post("/search") -> dict | JSONResponse
#   200 hybrid_search(req.query, k=req.k)     # results/top_component/arms/rrf 등 원형 유지
#   400 {"error": "empty query"}              # query 빈/공백
#   500 {"error": str(e)}                     # hybrid_search 예외 (조용히 죽지 않음)

def main() -> int
#   uvicorn.run(app, host="127.0.0.1", port=config.SEARCH_PORT)  # 기본 8756 = 대시보드 계약
```

### AC vs 실제 코드 불일치 — 확정된 결정(추천안)
1. `/health` 본문: 기존 `{"ok":true,...}` → **`{"status":"ok","model","dim"}`** (AC의 `status:ok` 충족 + 정보 필드 보존). 대시보드는 `r.ok`(200)만 읽어 회귀 무해.
2. 로컬 포트: **`config.SEARCH_PORT`(8756) 유지** (대시보드 `search_port||8756` 계약). AC의 `--port 8000`은 임의 예시.
3. **CORS 미들웨어 필수** (AC 미명시지만 대시보드 회귀 방지 핵심).
4. 에러 응답 키: FastAPI 기본 `{"detail":...}` 대신 **`{"error":...}` 유지** (대시보드가 `d.error` 읽음) → `JSONResponse` 사용.
5. `vercel.json`은 순수 정적 빌드 → 파이썬 함수 미참조 → **entrypoint 변경 불필요**(AC 충족).

### 테스트 전략
`hybrid_search`는 Neo4j+fastembed 실호출 → `tests/test_serve.py`에서 `src.graph.serve.hybrid_search`를 **monkeypatch**, `fastapi.testclient.TestClient`로 라우트만 검증.

## 2. 테스트 시나리오

- [x] [정상] health — should return 200 with status ok and model/dim fields when called
- [x] [정상] search — should return 200 with hybrid_search payload passthrough when query is valid
- [x] [경계] search — should default k to 6 when k is omitted
- [x] [경계] search — should forward provided k to hybrid_search when k is given
- [x] [예외] search — should return 400 {"error":"empty query"} when query is empty
- [x] [예외] search — should return 400 {"error":"empty query"} when query is whitespace only
- [x] [예외] search — should return 500 {"error": msg} when hybrid_search raises
- [x] [정상] cors — should include Access-Control-Allow-Origin * header on response
- [x] [정상] app — should expose a FastAPI instance importable as src.graph.serve:app
- [x] [정상] main — should call uvicorn.run with host 127.0.0.1 and config.SEARCH_PORT when invoked
- [x] [경계] vercel — should keep vercel.json as a static build with no python function (entrypoint 변경 불필요)
- [x] [예외] search — should return {"error"} key (not {"detail"}) when query field missing (422)
- [x] [예외] search — should return {"error"} key when request body malformed (422)
- [x] [예외] route — should return 404 {"error":"not found"} when unknown route (구 stdlib 계약)

> **결정 #4 보강 (ac-verifier #11 갭)**: Pydantic 검증 실패·404도 FastAPI 기본 `{"detail":...}` 대신 `{"error":...}` 봉투로 통일 — `RequestValidationError`/`StarletteHTTPException` 핸들러 추가. 구 stdlib 서버의 전 구간 `{"error"}` 계약과 일치.

## 3. AC 교차 대조

| AC | 커버 시나리오 |
|---|---|
| serve.py가 FastAPI 인스턴스 기반 | app (FastAPI instance) |
| GET /health → 200 status ok | health |
| POST /search 스키마 유지(회귀) | search passthrough / k default / k forward |
| uvicorn ...:app 기동 | main (uvicorn.run + SEARCH_PORT) |
| vercel.json entrypoint 변경 불필요 | vercel (static, no py func) |
| pytest test_serve.py health/search 통과 | health + search 시나리오 전체 |
| 정적 대시보드 플레이그라운드 회귀 | cors 헤더 + search 응답 원형 유지 + 에러 키 {"error"} + 포트 8756(main) |
