# 채널톡 VOC 인텔리전스 부서 — 루트원인 GraphRAG 엔진 & Codex 플러그인

> **인사이트에서 실전 액션 배포까지.** 하루 수천 건의 채널톡 고객 상담 대화를 자동으로 수집하고, **Neo4j 지식그래프**로 엮어 ₩ 매출 손실액과 루트원인을 탐지한 뒤, **LangGraph 인간 승인 게이트**를 거쳐 **실시간 GitHub Issue/PR 및 Jira 티켓**을 자동 발행하는 에이전틱 AI 부서 시스템.

[![Live Dashboard](https://img.shields.io/badge/📊_Live_Dashboard-channel--voc--demo.vercel.app-000000?style=for-the-badge&logo=vercel)](https://channel-voc-demo.vercel.app/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg?style=flat&logo=python)](pyproject.toml)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-orange.svg)](src/graph/agent.py)
[![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge_Graph-008CC1.svg?logo=neo4j)](src/graph/schema.cypher)
[![FastEmbed](https://img.shields.io/badge/FastEmbed-bge--small--en-00A86B.svg)](src/graph/llm.py)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-GPT--4o--mini-6366F1.svg)](src/graph/llm.py)
[![AX Hackathon](https://img.shields.io/badge/AX_Hackathon-Submission-FF6B6B.svg)](src/docs/handoff.md)

---

### 🔗 웹 대시보드 데모 (Vercel Live)

[![웹 대시보드 데모](docs/dashboard_preview.png)](https://channel-voc-demo.vercel.app/)

> [https://channel-voc-demo.vercel.app](https://channel-voc-demo.vercel.app)
> 
> *상단 이미지 또는 링크를 클릭하면 별도 환경 구축 없이 브라우저에서 6단계 엔진 프로세스와 하이브리드 검색을 직접 테스트해 보실 수 있습니다.*

---

## 📌 핵심 개요: 2단계 진화 과정 (Dual Phase Evolution)

본 프로젝트는 **AX 해커톤 제출작 (PHASE 1)**과 이를 바탕으로 고도화한 **포트폴리오 고도화 엔진 (PHASE 2)**을 모두 포함하고 있습니다.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: AX 해커톤 제출작 (Scikit-Learn 기반 룰베이스 파이프라인)                          │
│  - 5-Arm 파이프라인: Listen → Analyst → Triage/QA → Growth Ops → CSM Ops                 │
│  - 격리 데이터셋 검증 (Cohen's κ = 0.971) 및 근거 기반 ₩ 매출 손실 추정 모델                │
│  - 실제 GitHub Issue (#6), PR (#7), Jira 티켓 (KAN-2) MCP 실연동 배포                    │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │  (포트폴리오 고도화 승격)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: 루트원인 GraphRAG 엔진 (LangChain · LangGraph · Neo4j · GraphRAG)              │
│  - LLM 구조화 추출 (Intent · Symptoms · Component · Severity · Confidence)              │
│  - Neo4j 지식그래프 순회 및 8건 이상 중복 지목 시 `RootCause` 승격 & ₩ 손실액 자동 집계      │
│  - 3중 하이브리드 GraphRAG (BGE-Small Dense + Lucene Sparse + Graph 1-hop) & RRF 융합     │
│  - LangGraph interrupt() 인간 승인 게이트 & 6가지 인터랙티브 대시보드 (`out/dashboard.html`) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Before (PHASE 1) vs. After (PHASE 2) 비교표

| 축 | PHASE 1 (해커톤 제출작) | PHASE 2 (포트폴리오 고도화) |
|---|---|---|
| **시스템 아키텍처** | 선형 스크립트 파이프라인 (5-Arm Orchestrator) | **LangGraph StateGraph** + SQLite 체크포인터 + `interrupt()` 게이트 |
| **신호 추출 방식** | TF-IDF + Scikit-Learn (단순 의도 분류) | **LLM Function Calling**: Intent, Symptoms, Component, Severity |
| **지식 저장소** | 정적 JSON 파일 (`analysis.json`) | **Neo4j 지식그래프** (Customer $\rightarrow$ Conv $\rightarrow$ Symptom $\rightarrow$ Component) |
| **루트원인 탐지** | 대표 문장 3건 추론 | **Cypher 순회 집계**: 동일 Component를 지목하는 대화 8건+ $\rightarrow$ `RootCause` 승격 |
| **검색 및 근거** | 정적 키워드 / 문자열 매칭 | **3중 하이브리드 검색**: BGE-Small Dense + Lucene Sparse + Graph 1-hop (RRF) |
| **안전 승인 장치** | 스크립트 임계치 조건문 | **LangGraph `interrupt()`**: 사람의 최종 승인 전까지 실행 일시정지 |
| **감사 추적성** | JSON 대화 ID 정적 참 | **Cypher 그래프 감사추적**: `(Action)-[:EVIDENCES]->(Conversation)` 엣지 연결 |
| **사용자 인터페이스** | 정적 HTML 대시보드 | **6가지 인터랙티브 대시보드** (6단계 스테퍼, 원문 보기, 라이브 검색) |

---

## ⚡ 1-초간단 실행 방법 (Quick Start)

### PHASE 2 (포트폴리오 에이전트 & 인터랙티브 대시보드)

```bash
# 1. 단일 파이썬 3.12 환경 의존성 설치
uv sync

# 2. 전체 파이프라인 실행 (13초 내외, 캐시 기반 결정론적 100% 재현)
python -m src.graph.run

# 3. (선택) 대시보드 화면에서 직접 검색해볼 수 있는 라이브 검색 서버 실행
python -m src.graph.serve
```

> **결과물**: 브라우저에서 `out/dashboard.html`이 자동으로 열립니다. 모든 LLM 호출과 임베딩은 `data/graph_cache/`에 캐싱되어 재실행 시 100% 동일하게 초속으로 재현됩니다.

### PHASE 1 (AX 해커톤 파이프라인)

```bash
# 해커톤 초기 5-Arm 파이프라인 스크립트 실행
python src/pipeline/run.py --execute
```

---

## 🌌 PHASE 2 — 루트원인 GraphRAG 아키텍처

PHASE 2는 단순 텍스트 분류기를 넘어 **"에이전틱 지식그래프 루트원인 탐지 엔진"**으로 동작합니다.

```
[ 1,200건 고객 대화 ]
         │
         ▼ (1단계: LLM 구조화 추출 - extract.py)
[ Intent, Symptoms, Component, Severity, Confidence 추출 ]
         │
         ▼ (2단계: Neo4j 지식그래프 적재 & 임베딩 - load.py)
[ Neo4j Knowledge Graph ] ── (FastEmbed bge-small-en-v1.5 384d 벡터 & Lucene Full-text)
         │
         ▼ (3단계: Cypher 루트원인 순회 & ₩ 집계 - rootcause.py)
[ Cypher 순회: 8건 이상 동일 부품 지목 시 RootCause 승격 & 매출 위험액 집계 ]
         │
         ▼ (4단계: 3중 하이브리드 GraphRAG & 이슈 작성 - retriever.py & drafter.py)
[ RRF 융합: Dense 384d + Sparse Lucene + Graph 1-Hop → 팩트 근거 박힌 이슈 초안 ]
         │
         ▼ (5단계: LangGraph 인간 승인 게이트 - agent.py)
[ interrupt() 발동: 사람의 최종 승인 전까지 일시 정지 ]
         │
         ▼ (6단계: 실전 이슈 배포 & 출처 그래프 연결 - dispatch.py)
[ GitHub Issue 실시간 생성 + Neo4j Action-[:EVIDENCES]->Conversation 엣지 연동 ]
         │
         ▼
[ out/dashboard.html 생성 (6가지 인터랙티브 visual 시각화) ]
```

### 파이썬 모듈 역할 (`src/graph/`)

| 모듈명 | 주요 역할 및 기능 |
|---|---|
| [`config.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/config.py) | 중앙 설정 (경로, OpenRouter LLM, FastEmbed 384d, Neo4j 접속 정보, 안전 게이트 임계치) |
| [`llm.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/llm.py) | 단일 모델 접근 창구 (OpenRouter `chat()`, FastEmbed ONNX `embed()`) |
| [`db.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/db.py) & [`schema.cypher`](file:///Users/zorba/projects/channeltalk-solve/src/graph/schema.cypher) | Neo4j 드라이버, 제약조건, 384d 벡터 인덱스, Lucene Full-text 인덱스 생성 |
| [`taxonomy.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/taxonomy.py) | 통제 어휘집 (27개 Intent, 11개 Theme, 8개 제품 부품: `auth`, `checkout`, `orders`, `shipping`, `billing`, `subscription`, `support`, `feedback`) |
| [`extract.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/extract.py) | LLM Function Calling 기반 고객 대화 신호 추출 (디스크 캐싱) |
| [`load.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/load.py) | Neo4j 지식그래프 `MERGE` 적재 및 벡터 업서트 |
| [`benchmark.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/benchmark.py) | 600건 격리 데이터셋에 대한 Scikit-Learn vs LLM 성능 평가 ($\kappa$ 및 macro-$F_1$) |
| [`rootcause.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/rootcause.py) | Cypher 그래프 순회 $\rightarrow$ 8건 이상 중복 탐지 시 RootCause 승격 및 ₩ 손실 위험 집계 |
| [`retriever.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/retriever.py) | 3중 하이브리드 검색 (BGE-Small Dense + Lucene Sparse + Graph 1-hop) & RRF 융합 |
| [`drafter.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/drafter.py) | 대화 ID (`conv_id`) 근거가 명시된 GraphRAG GitHub 이슈 작성 |
| [`agent.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/agent.py) | LangGraph `StateGraph` 오케스트레이터 & SQLite 체크포인터 & `interrupt()` 게이트 |
| [`dispatch.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/dispatch.py) | GitHub REST API 이슈 생성 (`gh issue create`) 및 Neo4j 출처 엣지 연결 |
| [`serve.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/serve.py) | 표준 라이브러리 기반 0-의존성 로컬 HTTP 서버 (`http.server`) 대시보드 라이브 검색 지원 |
| [`export.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/export.py) & [`dashboard.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/dashboard.py) | 단일 자립형 대시보드 파일 `out/dashboard.html` 생성 |

---

## 📊 정직한 벤치마크: Scikit-Learn vs. LLM

600건의 격리된 고객 대화 데이터셋에 대해 27개 **Intent(의도)** 분류 과제를 평가했습니다:

| 평가 모델 | Cohen's $\kappa$ | Macro-$F_1$ | 처리 속도 | API 비용 | 주요 역할 |
|---|---|---|---|---|---|
| **Scikit-Learn (TF-IDF + LogReg)** | **0.971** | **0.972** | 초당 ~700건 | **₩0** | **빠른 1차 라벨러** |
| **LLM (OpenRouter GPT-4o-mini)** | 0.864 | 0.868 | 초당 ~1.2건 | 건당 $0.0003 | **그래프 신호 추출기** |

### 포트폴리오 서사 (Insight)
"무조건 LLM이 최고다"라고 주장하는 대신 **정직한 엔지니어링 트레이드오프**를 제시합니다:
1. **Scikit-Learn**: 속도가 초고속이고 비용이 0원인 단순 Intent 분류기($\kappa = 0.971$)로 그대로 유지합니다.
2. **LLM**: TF-IDF가 절대 만들 수 없는 **복합 구조 신호**(`Symptom` $\rightarrow$ `Component` $\rightarrow$ `Severity` $\rightarrow$ `Confidence`)를 지식그래프용으로 추출하는 데 집중시킵니다.

---

## 🎨 인터랙티브 대시보드 산출물 (`out/dashboard.html`)

`out/dashboard.html`은 단일 자립형 HTML 파일로, 외부 네트워크 요청 없이 동작하는 **6가지 비주얼 화면**을 포함합니다:

1. **6단계 인터랙티브 엔진 스테퍼**: Step 1~6 버튼(또는 자동 재생) 클릭 시 대화 원문 $\rightarrow$ JSON 추출 $\rightarrow$ Cypher 쿼리 $\rightarrow$ GraphRAG 근거 $\rightarrow$ 승인 게이트 $\rightarrow$ GitHub Issue 배포 과정을 시각적으로 확인.
2. **LangGraph 플로우 & 실시간 활동 피드**: 각 노드의 실행 상태, 처리 시간, 승인 대기(`interrupt()`) 지점을 시각화.
3. **인터랙티브 Neo4j 지식그래프**: 노드를 클릭하면 해당 장애가 어디서 시작되어 얼마의 ₩ 손실을 내는지 돈의 흐름 경로가 하이라이트됨.
4. **GraphRAG 근거 카드**: 인용된 실제 대화 ID와 함께 `[📄 원문 보기 / View Original Text]` 버튼을 클릭하여 고객 대화 전체 내용을 열람.
5. **정직한 벤치마크 차트**: Scikit-Learn vs LLM의 성능 비교 및 트레이드오프 서사 표시.
6. **₩ 손실 Sankey 다이어그램 & 라이브 검색 플레이그라운드**: 컴포넌트별 ₩ 손실 흐름 및 Dense+Sparse+Graph 3가지 파이프라인의 실시간 점수 검색창.

---

## 🏆 PHASE 1 — AX 해커톤 제출 정보

### 해결하고자 한 문제
채널톡에는 매일 수백~수천 건의 대화가 쌓이지만, 팀원들은 일부 샘플만 읽을 뿐이며 기존 CS AI 챗봇은 단순 답변만 하고 멈춥니다. **모든 대화를 읽고, ₩ 손실액을 정량화하고, 개발 티켓을 자동 발급하는 시스템이 없다는 문제**를 해결하고자 했습니다.

### PHASE 1 파이프라인 아키텍처 (`src/pipeline/`)
- **Listen (`ingest.py`)**: 1,200건의 실제 지원 대화(Bitext 데이터셋)를 채널톡 대화 스키마로 적재.
- **Analyst (`analyze.py`)**: 의도 분류, 감정 파악, ₩ 매출 위험액 정량화.
- **Assumptions (`assumptions.py`)**: 근거 있는 재무 가정 모델 (평균 주문 금액 ₩55,000, 서비스 회복률 35%, Baymard & TARP 연구 기반).
- **Triage/QA (`validate.py`)**: 격리 데이터셋 기반 라벨 검증 (11개 테마 $\kappa = 0.992$, 27개 인텐트 $\kappa = 0.971$).
- **Ops (`dispatch.py`)**: 실제 GitHub Issue(#6), FAQ PR(#7), Jira 티켓(Atlassian Rovo MCP) 자동 발급.

### 실제 생성된 아티팩트
- 🐛 **GitHub Issue (Triage/QA)**: [Issue #6](https://github.com/kanziman/channel-voc-demo/issues/6)
- 🔀 **GitHub PR (FAQ 개선)**: [PR #7](https://github.com/kanziman/channel-voc-demo/pull/7)
- 🧭 **Jira Ticket (CSM Ops)**: [`KAN-2`](https://risers.atlassian.net/browse/KAN-2)
- 🚀 **PHASE 2 실시간 디스패치 이슈**: [Issue #10](https://github.com/kanziman/channel-voc-demo/issues/10)

---

## 📝 서면 평가 질문 답변 (AX 해커톤)

### 1. 어떤 문제를 해결하나요?
채널톡에는 매일 수많은 대화가 쌓이지만, 이를 전량 읽고 "어떤 시스템 부품에서 얼마의 매출 손실이 나는지"를 ₩로 정량화해 개발 티켓으로 작성하는 주체가 없습니다. 기존 CS AI는 응대만 하고 멈추는 반면, 본 솔루션은 **대화 수집 $\rightarrow$ 지식그래프 순회 $\rightarrow$ ₩ 손실액 정량화 $\rightarrow$ 실전 GitHub/Jira 이슈 배포**까지 닫는 루프를 완성합니다.

### 2. 어떻게 작동하나요?
단 1회 호출로 `run.py`가 파이프라인을 실행합니다: 대화 추출(LLM) $\rightarrow$ Neo4j 지식그래프 적재 $\rightarrow$ Cypher 루트원인 순회(8건 이상 중복 탐지 시 ₩ 손실액 집계) $\rightarrow$ GraphRAG 근거 추출 $\rightarrow$ LangGraph `interrupt()` 승인 게이트 $\rightarrow$ GitHub Issue 배포. 결과는 사람용 `dashboard.html`과 에이전트용 `manifest.json`으로 이중 반환됩니다.

### 3. 왜 Codex/AX 네이티브인가요? (차별성)
단순히 텍스트 답변을 생성하고 멈추는 CS 챗봇과 달리, **직접 분석 코드를 짜고 Neo4j 그래프를 조회하며 실제 GitHub Issue/PR 및 Jira 티켓을 생성**합니다. CS 담당자 1명이 데이터 분석가 + 개발 티켓 작성자 + CSM 브리핑 역할까지 해내는 10배 인재밀도를 제공합니다.

### 4. 신뢰할 수 있나요? (검증 및 정직성)
1. **정직한 벤치마크**: 600건 격리 데이터셋에서 Scikit-Learn ($\kappa=0.971$)과 LLM ($\kappa=0.864$)의 성과를 데이터로 검증하고 빠른 분류기와 그래프 추출기로 역할을 분담했습니다.
2. **투명한 ₩ 모델**: 대화 건수는 실제 측정치이며, 돈 환산은 공인 논문(Baymard, TARP)에 근거한 투명한 가정 모델(`assumptions.py`)로 계산됩니다.
3. **감사 추적성(Provenance)**: 생성된 모든 GitHub Issue에는 근거가 된 대화 ID (`conv_id`)가 박히며, Neo4j 상에서 `(Action)-[:EVIDENCES]->(Conversation)` 엣지로 역추적됩니다.

### 5. 성장성은 어떤가요?
채널톡 Open API v5 (`/open/v5/user-chats`) 호환 로더가 이미 구현되어 있어, API 키만 입력하면 실전 프로덕션 환경에 즉시 적용 가능합니다. 단순 CS 응대를 넘어 **채널톡 상단의 Customer Intelligence 레이어**로 확장 가능합니다.

---

## 📁 프로젝트 디렉토리 구조

```text
├── README.md                      # 프로젝트 메인 한글 문서
├── pyproject.toml / uv.lock       # 통일된 파이썬 3.12 의존성 관리
├── .env.example                   # 환경 변수 템플릿 (OpenRouter, Neo4j, GitHub)
├── out/
│   ├── dashboard.html             # 6가지 시각화가 담긴 자립형 HTML 산출물
│   ├── manifest.json              # 에이전트 간 주고받는 구조화된 실행 리포트
│   ├── graph_snapshot.json        # 그래프 시각화 및 검색 코퍼스 데이터
│   └── benchmark.json             # Scikit-Learn vs LLM 평가 결과
├── src/
│   ├── graph/                     # PHASE 2: 루트원인 GraphRAG 엔진
│   │   ├── run.py                 # 단일 명령어 실행 진입점
│   │   ├── serve.py               # 라이브 검색 로컬 HTTP 서버
│   │   ├── agent.py               # LangGraph StateGraph & interrupt() 게이트
│   │   ├── retriever.py           # 3중 하이브리드 검색 (Dense + Sparse + Graph RRF)
│   │   ├── rootcause.py           # Cypher 순회 및 ₩ 손실 집계
│   │   ├── extract.py             # LLM Function Calling 신호 추출
│   │   ├── load.py / db.py        # Neo4j 지식그래프 적재 및 드라이버
│   │   ├── benchmark.py           # Held-out kappa 평가 러너
│   │   ├── schema.cypher          # Neo4j 제약조건 및 벡터/Full-text 인덱스
│   │   └── dashboard_template.html# 인터랙티브 대시보드 템플릿
│   ├── pipeline/                  # PHASE 1: 해커톤 초기 파이프라인
│   │   ├── run.py                 # 해커톤 5-Arm 실행 러너
│   │   ├── analyze.py / ingest.py # Scikit-Learn 분류기 및 대화 적재
│   │   ├── assumptions.py         # 투명한 ₩ 매출 위험 모델
│   │   └── dispatch.py            # GitHub/Jira 이슈 생성기
│   └── docs/                      # 설계 문서 및 핸드오프 리포트
└── data/                          # 1,200건 고객 대화 데이터 및 LLM 캐시
```

---

## 📜 라이선스 및 데이터 출처

* **데이터셋**: Bitext Customer Support Dataset ([CDLA-Sharing-1.0](https://cdla.dev/sharing-1-0/))
* **라이선스**: MIT License
