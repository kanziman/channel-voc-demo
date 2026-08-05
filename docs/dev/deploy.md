# 배포 런북 — Vercel (방안 B)

VOC 코파일럿을 **하나의 Vercel 프로젝트**에 배포한다: Vite 프론트(`/`) + 정적 대시보드
(`/dashboard.html`) + FastAPI 서버리스 함수(`/api/*`). (GH#53, PHASE3_PLAN §5-1/§6)

## 왜 방안 B인가
로컬 `fastembed`(ONNX 런타임 + bge-small 모델 ~130MB)와 `scikit-learn`/`pandas`가
Vercel 서버리스 Python 번들 한계(~250MB)를 초과한다. 그래서:

- 쿼리 임베딩을 **호스티드 OpenAI 호환 엔드포인트**로 옮긴다 — **동일 모델 `bge-small-en-v1.5` @384d**.
  동일 dim이라 **Neo4j 벡터 인덱스를 재색인할 필요가 없다**.
- 서버리스 `requirements.txt`에서 `fastembed`/`scikit-learn`/`pandas`/`joblib`를 제외한다.
- 코드 스위치: `VOC_EMBED_BACKEND=api` → `llm._embed_api`(langchain-openai `OpenAIEmbeddings`).
  `local`(기본)은 fastembed 그대로라 개발·그래프 적재는 영향 없음.

## 파일
| 파일 | 역할 |
| :-- | :-- |
| `api/index.py` | 서버리스 진입점 — `src.graph.serve:app`(ASGI) 재노출 |
| `requirements.txt` | 서버리스 런타임 deps(무거운 로컬 deps 제외) |
| `vercel.json` | 프론트 빌드 + `out/*` 복사 + `/api/*`→함수 라우팅 + `src/**` 포함 + Cron Keep-Alive (`/api/health` 매일 0시) |
| `src/graph/llm.py` · `config.py` | `EMBED_BACKEND` 분기 + `CACHE_DIR` env-override |

## Vercel 프로젝트 환경변수 (필수)
```
NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD   # Aura
OPENROUTER_API_KEY                          # chat/hypothesis LLM
VOC_EMBED_BACKEND=api
VOC_EMBED_API_URL=<OpenAI 호환 /v1 base>     # 예: https://api.deepinfra.com/v1/openai
VOC_EMBED_API_KEY=<임베딩 키>
VOC_CACHE_DIR=/tmp/graph_cache              # 읽기전용 FS 회피(쓰기는 /tmp만 가능)
```
프론트는 same-origin `/api/*`를 호출하므로 `VITE_API_BASE`는 불필요(기본 "" = 동일 출처).

### 임베딩 엔드포인트 요건
`bge-small-en-v1.5`를 **384d**로 서빙하는 OpenAI 호환 `/v1/embeddings`. 예: Deepinfra
`BAAI/bge-small-en-v1.5`. dim이 384가 아니면 인덱스 불일치 → 재색인 필요(방안 B의 취지 상실).

## 로컬에서 검증된 것 / 배포 시 확인할 것
**검증됨(로컬):** `EMBED_BACKEND` 분기 단위 테스트(`tests/test_llm.py` 5 pass), `api` 경로가
fastembed를 import하지 않음, `api/index.py`가 `app`을 import(EMBED_BACKEND=api·VOC_CACHE_DIR=/tmp),
`vercel.json` 유효 JSON, 전체 pytest 회귀 없음(91 pass).

**배포 시 확인 필요(사용자 인프라):**
1. **함수 타임아웃** — Hobby 10s. `POST /api/agent/run`(LangGraph + Neo4j + LLM)은 콜드스타트에
   초과할 수 있음. 무거운 왕복은 Pro(더 긴 timeout) 또는 컨테이너 병행을 고려.
2. **`requirements.txt` 완전성** — 첫 배포 로그에서 `ModuleNotFoundError`가 나면 해당 런타임
   의존성 추가(경량인 것만). 무거운 것(fastembed/sklearn/pandas) 재유입 금지.
3. **`includeFiles: src/**`** 로 함수 번들에 `src/`가 포함되는지(임포트 경로).
4. **대시보드 URL** — 기존 정적 대시보드가 `/`였다면 이제 `/`=앱, 대시보드=`/dashboard.html`.
   별도 유지가 필요하면 대시보드를 분리 프로젝트로 두는 선택지도 있음(§5-1 "병행 서비스").

## 배포
```bash
# 프리뷰
vercel
# 프로덕션
vercel --prod
```
환경변수는 대시보드(또는 `vercel env add`)로 이미 설정됨. 첫 배포 후 `/api/health`와
`/api/chat`(가벼운 쿼리)로 스모크 → 임베딩/Neo4j 왕복 확인.
