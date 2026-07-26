# PHASE 2 PLAN — Root-Cause Intelligence (LangChain · LangGraph · Neo4j)

> **성격**: 해커톤 제출 아님. **포트폴리오**용 고도화. PHASE1(룰베이스 파이프라인, 심사 AI 100 / 사람 90)을 기반으로, "실제 에이전트 시스템 + 지식그래프 + GraphRAG"로 승격한다.
> **확정 결정**: 모든 LLM API = **OpenRouter**(생성/추출) · 임베딩 = **로컬 fastembed(ONNX, torch 불필요)**(OpenRouter는 임베딩 미제공 → API 표면 OpenRouter 하나로 통일) · 스코프 = **집중(루트원인 GraphRAG 1-arm 딥다이브)** · 데이터 = **영어 Bitext 유지** · **모든 산출물은 시각적으로 임팩트 있게(§2.4 first-class)**.
> **상태**: 계획 확정, 구현 대기. 유일 선행 blocker = OpenRouter 키 주입(§7).

---

## 0. 한 줄 요약

**1,200건 실 대화 → 지식그래프 → `증상→컴포넌트→반복 루트원인` 그래프 순회 → GraphRAG로 근거(선례 대화 인용) 붙인 GitHub Issue 초안 → 사람 승인 interrupt → 실제 배포**, 이 전 과정을 **LangGraph 상태 그래프**가 오케스트레이션한다. 그리고 이 업그레이드가 룰베이스 대비 얼마나 나아졌는지 **held-out κ로 측정**한다.

포트폴리오 서사: *"정적 클러스터 라벨을, 지식그래프 위에서 도는 검증된 에이전트 루트원인 엔진으로 승격시켰다 — 그리고 그 향상을 숫자로 증명했다."*

---

## 1. PHASE1 → PHASE2 매핑 (도구가 때리는 실제 약점)

| PHASE1 현실 | 잔여 약점 | PHASE2 해결 |
| :-- | :-- | :-- |
| `analyze.py` = TF-IDF + LogisticRegression, LLM 없음, 영어 전용, 의미론 없음 | 테마 = 얕은 클러스터 라벨 | **LangChain**: 임베딩 의미 검색 + LLM 구조화 추출/라벨 |
| "AI 부서/에이전트" = 은유(선형 스크립트) | 진짜 에이전트가 아님 | **LangGraph**: 상태 그래프 + 조건부 엣지 + 재시도 + 사람 interrupt |
| 루트원인 = 대표 발화 3건 | why-chain이 아님 | **Neo4j**: 증상→컴포넌트→반복 루트원인 순회 |
| ₩ 감사추적 = JSON id 역참조(정적) | 신뢰되나 정적 | **Neo4j**: 모든 ₩가 그래프 **경로**(Cypher로 추적) |
| 액션 텍스트 = 템플릿 | "사실 기반인가" | **GraphRAG**: 선례 대화 검색→인용 붙인 생성 |

**보존(버리지 않음)**: held-out κ 검증, 투명한 ₩ 가정모델([assumptions.py](../pipeline/assumptions.py)), 실제 dispatch(gh/MCP, [dispatch.py](../pipeline/dispatch.py)). sklearn 분류기는 폐기가 아니라 **벤치마크 베이스라인**으로 재활용한다.

---

## 2. 목표 아키텍처

```
                 LangGraph StateGraph  (공유 VOCState, checkpointer)
                                │
  analyst_extract → graph_writer → researcher_cluster → triage_rootcause
        │(LLM 구조화 추출)  │(Neo4j MERGE)   │(임베딩 클러스터) │(Cypher 순회)
        │                                                        ▼
        │                              action_drafter (GraphRAG: 벡터+그래프 하이브리드 검색)
        │                                                        ▼
        │                          ┌── interrupt: human_approval ──┐  ← 승인 게이트
        │                          ▼                               │
        └───────────────── dispatcher (실제 GH Issue) → reporter ──┘
                                                        ▼
              이중 반환: manifest.json (에이전트층) + dashboard.html (사람층, +그래프 뷰)
```

### 2.1 Neo4j 그래프 스키마 (system of record)

```cypher
// 노드
(:Customer {id})
(:Conversation {id, text, channel, created_at, embedding})   // 벡터 인덱스
(:Intent {name})            // 27-class (Bitext)
(:Theme {name, arm})        // 11 coarse
(:Symptom {text})           // LLM 추출
(:Component {name})         // checkout, auth, shipping ...
(:RootCause {hypothesis})   // LLM 추론 + 그래프 집계
(:Action {type, url, status, revenue_at_risk_krw})

// 관계
(Customer)-[:SENT]->(Conversation)
(Conversation)-[:EXPRESSES]->(Intent)-[:ROLLS_UP_TO]->(Theme)
(Conversation)-[:MENTIONS]->(Symptom)-[:IMPLICATES]->(Component)
(Component)-[:CAUSED_BY]->(RootCause)
(RootCause)-[:DISPATCHED_AS]->(Action)
(Action)-[:EVIDENCES]->(Conversation)   // provenance: ₩·이슈가 어느 대화에서 왔나
```

- **제약/인덱스**: 각 노드 `id`/`name` UNIQUE 제약, `Conversation.embedding` 벡터 인덱스(코사인, **로컬 임베딩 384d — `BAAI/bge-small-en-v1.5`**, 무키·무API·재현적).
- **루트원인 = 그래프 집계**: 여러 Conversation이 같은 Component를 반복 지목 → RootCause 승격(빈도·₩ 임계값). 이게 "클러스터 라벨"과 결정적으로 다른 점.

### 2.2 LangGraph 상태

```python
class VOCState(TypedDict):
    conversations: list[dict]          # 입력
    extracted: list[dict]              # {conv_id, intent, symptoms[], component, severity}
    graph_written: bool
    root_causes: list[dict]            # Cypher 순회 결과 (component, freq, ₩, 대표 conv_ids)
    candidate_actions: list[dict]      # GraphRAG로 초안 작성된 이슈
    approved: list[dict]               # interrupt 이후
    dispatched: list[dict]             # 실제 URL
    briefing: str
```

- **checkpointer**: 재실행·재현성·interrupt 복귀용(SqliteSaver).
- **human_approval**: `interrupt()` — confidence/₩ 임계값 미만은 자동 보류(PHASE1 `DISPATCH_REQUIRE_APPROVAL` / `DISPATCH_CONFIDENCE_THRESHOLD`를 실제 그래프 게이트로 승격).

### 2.3 GraphRAG 하이브리드 검색 (action_drafter)

이슈 초안 1건 생성 시:
1. **벡터**: 대상 루트원인 대표 대화와 유사한 과거 대화 top-k (Neo4j 벡터 검색, **로컬 임베딩**).
2. **그래프**: 같은 Component/RootCause 이웃 순회로 구조적 근거(동일 증상 빈도, ₩ 경로).
3. 둘을 합쳐 컨텍스트 → **OpenRouter LLM**이 **인용 id를 명시**한 이슈 본문 생성. 모든 문장이 실 대화로 역추적 가능(= "사실 기반" 증명).

### 2.3.1 API 연결 규약 — 전부 OpenRouter

- **모든 채팅/추출/생성**: `ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY, model="openai/gpt-4o-mini")`. LangChain 그대로 사용(OpenAI 호환). 모델 문자열만 바꾸면 Claude/Gemini/Llama도 무교체 스왑 → **모델 벤치마크**도 포트폴리오 소재.
- **임베딩**: OpenRouter가 임베딩 미제공 → **로컬 `fastembed`(ONNX, bge-small-en-v1.5, 384d)**. torch 불필요(설치 181MB), 외부 API 표면은 OpenRouter 하나로 유지, 오프라인·무료·결정적. *(이 환경에서 실측 검증: 최초 다운로드 9.6s, 3문장 임베딩 0.02s)*
- 단일 클라이언트 팩토리 `src/graph/llm.py`(`chat()` / `embed()`)로 캡슐화 → 전 코드가 여기만 의존.

### 2.4 시각적 임팩트 레이어 (포트폴리오 핵심 — first-class)

> 사용자 지시: **"모든 것을 시각적으로 임팩트 있게."** 시각화는 2.4 단계 마감이 아니라 **전 단계가 향하는 목표**로 취급한다. 전부 PHASE1처럼 **자립형(self-contained) HTML** — 인라인 JS/CSS, 외부 요청 0, CSP-safe, 라이트/다크·모바일 대응. `artifact-design` 스킬 기준.

| # | 비주얼 | 무엇을 "와"하게 만드나 | 기술 |
| :-- | :-- | :-- | :-- |
| 1 | **인터랙티브 지식그래프** (showstopper) | RootCause 노드 클릭 → ₩ 경로가 Component→Symptom→근거 대화까지 **하이라이트 애니메이션**. 노드 크기=₩, 색=타입 | `vis-network` 인라인, Neo4j→JSON export |
| 2 | **LangGraph 실행 플로우** | 에이전트 그래프를 그리고 **이번 실행 경로 + interrupt 지점**을 하이라이트. "진짜 에이전트"를 눈으로 증명 | Mermaid(네이티브) + 실행 로그 오버레이 |
| 3 | **GraphRAG Provenance 카드** | 생성된 이슈 옆에 검색된 선례 대화 카드(유사도 % + 그래프 hop 배지). 문장→근거 연결선 | HTML + 인라인 데이터 |
| 4 | **Agent Activity Feed** | 각 노드 발화(analyst→graph_writer→…) 실시간풍 로그 + 소요시간. 부서가 일하는 느낌 | 스트리밍풍 CSS 애니 |
| 5 | **Before/After 벤치마크** | sklearn vs LLM κ/F1을 델타 바로. "업그레이드를 측정했다" 증명 | 인라인 SVG 차트 (`dataviz` 스킬) |
| 6 | **₩ Root-cause Flow(Sankey)** | Component → RootCause → ₩ at risk 흐름. 어디서 돈이 새는지 한 장 | 인라인 Sankey |

- **일관 디자인 시스템**: PHASE1 대시보드의 컬러/타이포/severity 색을 계승해 "한 제품"으로 읽히게. `frontend-design`·`dataviz` 스킬 적용.
- **결정적 재생**: 캐시된 그래프 스냅샷으로 데모가 항상 같은 화면 → 녹화/스크린샷 안정.
- **단일 진입 뷰**: 1 커맨드 → 하나의 대시보드에서 위 6개를 스크롤로 관통(에이전트 실행 → 그래프 → 루트원인 → 근거 → 배포 → 벤치마크).

---

## 3. 단계 계획 (집중 스코프)

> 각 단계 끝에 **검증 게이트**. 5-arm 확장은 2.3 검증 후 별도(“단계적 확장” 여지만 남김).

### PHASE 2.0 — 기반 & 연결 (de-risk)
- `neo4j-graphrag/`를 메인으로 승격: `src/graph/`(로더·스키마·검색), 환경 통일(py3.12 단일 venv), `langgraph`·`langchain-openai`(OpenRouter 호환)·`fastembed`·`langchain-neo4j` 의존성 정리. `src/graph/llm.py` 클라이언트 팩토리(§2.3.1).
- `src/graph/schema.cypher`: 제약 + 벡터 인덱스 생성 스크립트.
- 연결 스모크(이미 검증됨: 노드 2개) + OpenAI 임베딩 1건 왕복 테스트.
- **게이트**: `python -m src.graph.smoke` → Neo4j write/read + 임베딩 성공.

### PHASE 2.1 — Ingest → 지식그래프
- `src/graph/extract.py`: LangChain 구조화 출력(function calling)로 대화당 `{intent, symptoms[], component, severity}` 추출. temperature=0 + 디스크 캐시(재현성·비용).
- `src/graph/load.py`: 멱등 `MERGE`로 노드/엣지 적재 + 대화 임베딩 upsert.
- **벤치마크**: sklearn 베이스라인(PHASE1) vs LLM 인텐트 추출을 **동일 held-out 600건**에서 κ/F1 비교표.
- **게이트**: 1,200건 그래프 적재 완료, κ 비교표 생성, LLM κ ≥ sklearn κ(또는 근접+질적 우위 서술).

### PHASE 2.2 — 루트원인 순회 + GraphRAG
- `src/graph/rootcause.py`: Cypher 순회 — (a) 반복 Component→RootCause 승격, (b) 증상 co-occurrence, (c) RootCause별 ₩ 경로 집계.
- `src/graph/retriever.py`: 벡터+그래프 하이브리드 리트리버.
- **게이트**: top 루트원인 3건이 각각 근거 대화 id·₩ 경로와 함께 재현.

### PHASE 2.3 — LangGraph 오케스트레이션 + 실제 배포
- `src/graph/agent.py`: StateGraph(노드 §2.2), checkpointer, **human_approval interrupt**.
- action_drafter → 승인 → 기존 [dispatch.py](../pipeline/dispatch.py) gh 경로 재사용해 실제 Issue 생성(인용 포함).
- **게이트**: 1 커맨드로 그래프 실행 → interrupt에서 멈춤 → 승인 시 실 Issue URL(200) + manifest.

### PHASE 2.4 — 시각적 임팩트 & 포트폴리오 마감
- **§2.4의 6개 비주얼을 단일 자립형 대시보드로 구현**(인터랙티브 지식그래프·LangGraph 플로우·Provenance·Activity Feed·벤치마크·₩ Sankey). `dataviz`·`frontend-design`·`artifact-design` 스킬 적용.
- 아키텍처 문서 + 다이어그램(LangGraph 렌더 + Neo4j 스키마), 벤치마크 표, 짧은 녹화 데모, (선택) LangSmith 트레이스.
- **게이트**: 1 커맨드 → 6개 비주얼 렌더(콘솔 에러 0, 그래프 클릭→₩경로 하이라이트 동작), README에 "before(PHASE1)/after(PHASE2)" 비교 + 재현 커맨드.

---

## 4. 성공 기준 (포트폴리오급)

- **측정된 업그레이드**: sklearn vs LLM κ/F1 표 존재(정직한 향상/트레이드오프 서술).
- **진짜 에이전트**: LangGraph 그래프 이미지 + interrupt 승인 흐름 시연.
- **진짜 그래프**: 모든 ₩·이슈가 Cypher 경로로 역추적. 루트원인이 다수 대화의 집계임을 쿼리로 증명.
- **사실 기반 생성**: 생성된 이슈의 모든 근거가 인용 conv_id로 열림.
- **기능 무결성**: PHASE1처럼 전 스테이지 exit 0, 실 아티팩트 재현.

---

## 5. 리스크 & 완화

| 리스크 | 완화 |
| :-- | :-- |
| LLM 비용/속도 | OpenRouter `gpt-4o-mini`, temperature=0 + **디스크 캐시**, N 캡 |
| **OpenRouter 임베딩 미제공** | 임베딩은 **로컬 fastembed(ONNX, torch 불필요)**로 분리(무API·결정적). API 표면은 OpenRouter만 |
| LLM 비결정성(데모 재현성) | 캐시된 추출/임베딩 스냅샷 커밋 → 데모는 결정적 재생 |
| 추출 품질 | held-out 라벨로 검증, 저신뢰는 보류 큐 |
| Neo4j 스키마 드리프트 | `schema.cypher` 단일 소스 + 멱등 MERGE |
| 환경 파편화(2 venv) | 2.0에서 단일 py3.12 venv로 통일 |

---

## 6. 레포 전략 (권장)

`neo4j-graphrag/`(현재 별도 uv 학습 스캐폴드)를 **메인 프로젝트로 흡수** → `src/graph/` 패키지. 이유: 하나의 파이프라인(ingest→graph→agent→dispatch→dashboard)으로 통합돼야 "1 커맨드 데모"와 재현성이 성립. 학습 노트북(`KG_P1_01_*.ipynb`)은 `notebooks/`로 보존.

---

## 7. 선행 blocker (구현 착수 전 유일 필요)

- **OpenRouter API 키**: `OPENROUTER_API_KEY` 주입 필요(추출+생성 전부 여기 의존). `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`. 주입되면 2.0부터 바로 착수.
- **임베딩**: 별도 키 불필요 — 최초 실행 시 `bge-small-en` 모델 로컬 다운로드(~130MB).
- **Neo4j**: 연결 검증됨(AuraDB, 노드 2). 추가 세팅 불필요.

---

## 8. 결정 로그

- 2026-07-25: PHASE1(해커톤) 현 상태 종료. PHASE2(포트폴리오) 착수 결정.
- 2026-07-25: 스코프=루트원인 GraphRAG 집중(1-arm 딥, 5-arm은 검증 후 확장), 데이터=영어 Bitext 유지. (사용자 명시 선택)
- 2026-07-25: 모든 API 연결부=**OpenRouter**(생성/추출), 임베딩=로컬 fastembed(ONNX, torch 불필요)(OpenRouter 임베딩 미제공 대응). (사용자 지시)
- 2026-07-25: **시각적 임팩트를 first-class 목표**로 승격(§2.4 6개 자립형 비주얼). (사용자 지시)
