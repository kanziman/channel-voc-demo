# Channel VOC Intelligence Dept. — AI Root-Cause GraphRAG Engine & Codex Plugin

> **Insight that ships.** An always-on AI *department* for [ChannelTalk](https://channel.io) that ingests customer support conversations, quantifies revenue leakage in ₩, builds a **Neo4j Knowledge Graph**, traverses root causes, and dispatches fact-grounded GitHub Issues/PRs and Jira tickets after a human-in-the-loop approval gate — delivering an interactive dashboard for humans and a structured manifest for agents.

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg?style=flat&logo=python)](pyproject.toml)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-orange.svg)](src/graph/agent.py)
[![Neo4j](https://img.shields.io/badge/Neo4j-Knowledge_Graph-008CC1.svg?logo=neo4j)](src/graph/schema.cypher)
[![FastEmbed](https://img.shields.io/badge/FastEmbed-bge--small--en-00A86B.svg)](src/graph/llm.py)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-GPT--4o--mini-6366F1.svg)](src/graph/llm.py)
[![AX Hackathon](https://img.shields.io/badge/AX_Hackathon-Submission-FF6B6B.svg)](src/docs/handoff.md)

---

## 📌 Executive Overview: Dual Phase Evolution

This repository contains both the **AX Hackathon Submission (PHASE 1)** and the **Portfolio Upgrade (PHASE 2)**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: AX Hackathon Codex Plugin (Rule-Based + Scikit-Learn)                         │
│  - 5-Arm Pipeline: Listen → Analyst → Triage/QA → Growth Ops → CSM Ops                 │
│  - Held-out Human Label Validation (Cohen's κ = 0.971) & Sourced ₩ Assumption Model    │
│  - Real GitHub Issue (#6), PR (#7), Jira Ticket (KAN-2) Dispatch via MCP               │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │  (Portfolio Upgrade)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: Agentic Root-Cause Engine (LangChain · LangGraph · Neo4j · GraphRAG)          │
│  - LLM Structured Signal Extraction (Intent · Symptoms · Component · Severity)          │
│  - Neo4j Knowledge Graph Traversal & Cypher Financial Root Cause Promotion (8+ convs)  │
│  - Triple Hybrid GraphRAG (Dense 384d + Lucene Sparse + Graph 1-hop) with RRF          │
│  - LangGraph interrupt() Human Approval Gate & 6-Visual Interactive Dashboard           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Before (PHASE 1) vs. After (PHASE 2) Comparison

| Dimensions | PHASE 1 (AX Hackathon Submission) | PHASE 2 (Portfolio Upgrade) |
|---|---|---|
| **Architecture** | Linear Script Pipeline (5-Arm Orchestrator) | **LangGraph StateGraph** + Checkpointer + `interrupt()` Gate |
| **Extraction** | TF-IDF + Scikit-Learn (Intent Labeling) | **LLM Function Calling**: Intent, Symptoms, Component, Severity |
| **Knowledge Store** | Static JSON Artifacts (`analysis.json`) | **Neo4j Knowledge Graph** (Customer $\rightarrow$ Conv $\rightarrow$ Symptom $\rightarrow$ Component) |
| **Root Cause Detection**| Top 3 Representative Sample Sentences | **Cypher Traversal**: Aggregates $8+$ convs implicating a Component $\rightarrow$ `RootCause` |
| **Search & Retrieval**| Exact String Match / Static Lookups | **Triple Hybrid Search**: BGE-Small Dense + Lucene Sparse + Graph 1-hop (RRF) |
| **Safety Gate** | Threshold Filtering in script | **LangGraph `interrupt()`**: Pauses execution for explicit human approval |
| **Traceability** | JSON ID Backreferences | **Cypher Graph Provenance**: `(Action)-[:EVIDENCES]->(Conversation)` |
| **Human Interface** | Static HTML Dashboard | **Interactive 6-Visual Dashboard** (6-Stage Stepper, Live Search Playground) |

---

## ⚡ Quick Start (1-Command Execution)

### PHASE 2 (Portfolio Agent & Interactive Dashboard)

```bash
# 1. Install dependencies into unified Python 3.12 environment
uv sync

# 2. Run the complete pipeline (Deterministic execution ~13s with cache)
python -m src.graph.run

# 3. (Optional) Launch real-time live search backend for the dashboard playground
python -m src.graph.serve
```

> **Outputs**: Opens `out/dashboard.html` in your browser. All LLM calls and embeddings are cached to `data/graph_cache/` for instant, deterministic replay.

### PHASE 1 (AX Hackathon Pipeline)

```bash
# Run the original hackathon 5-arm script pipeline
python src/pipeline/run.py --execute
```

---

## 🌌 PHASE 2 — Root-Cause GraphRAG Architecture

PHASE 2 transforms simple classification into an **Agentic Knowledge-Graph Root-Cause Engine**.

```
[ 1,200 Customer Convs ]
         │
         ▼ (Step 1: LLM Extraction - extract.py)
[ Intent, Symptoms, Component, Severity, Confidence ]
         │
         ▼ (Step 2: Neo4j & Vector Ingestion - load.py)
[ Neo4j Knowledge Graph ] ── (FastEmbed bge-small-en-v1.5 384d Vector & Lucene Full-text)
         │
         ▼ (Step 3: Cypher Root Cause Traversal - rootcause.py)
[ Cypher Traversal: 8+ convs implicating Component → Promoted Root Cause & ₩ Risk ]
         │
         ▼ (Step 4: Triple Hybrid GraphRAG - retriever.py & drafter.py)
[ RRF Fusion: Dense 384d + Sparse Lucene + Graph 1-Hop → Fact-Grounded Issue Draft ]
         │
         ▼ (Step 5: LangGraph Approval Gate - agent.py)
[ interrupt() Node: Pauses execution until Human Approval ]
         │
         ▼ (Step 6: GitHub Dispatch & Provenance Linking - dispatch.py)
[ Real GitHub Issue Creation + Neo4j Action-[:EVIDENCES]->Conversation Provenance Edge ]
         │
         ▼
[ out/dashboard.html (6 Interactive Portfolio Visuals) ]
```

### Module Map (`src/graph/`)

| Module | Purpose & Role |
|---|---|
| [`config.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/config.py) | Central configuration (Paths, OpenRouter LLM, FastEmbed 384d, Neo4j credentials, safety thresholds) |
| [`llm.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/llm.py) | Single entry point for model access (`chat()` via OpenRouter, `embed()` via FastEmbed ONNX) |
| [`db.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/db.py) & [`schema.cypher`](file:///Users/zorba/projects/channeltalk-solve/src/graph/schema.cypher) | Neo4j driver, uniqueness constraints, 384d vector index, Lucene full-text index |
| [`taxonomy.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/taxonomy.py) | Controlled vocabularies (27 Intents, 11 Themes, 8 Product Components: `auth`, `checkout`, `orders`, `shipping`, `billing`, `subscription`, `support`, `feedback`) |
| [`extract.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/extract.py) | LLM structured signal extraction using function calling, disk-cached |
| [`load.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/load.py) | Idempotent Cypher `MERGE` graph loader & embedding upsert |
| [`benchmark.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/benchmark.py) | Scikit-Learn vs LLM evaluation on 600 held-out conversations ($\kappa$ & macro-$F_1$) |
| [`rootcause.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/rootcause.py) | Cypher graph traversal $\rightarrow$ Root cause promotion & ₩ revenue-at-risk aggregation |
| [`retriever.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/retriever.py) | Triple-Arm Hybrid Retrieval (BGE-Small Dense + Lucene Sparse + Graph 1-hop) with RRF |
| [`drafter.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/drafter.py) | GraphRAG issue generation citing exact `conv_ids` |
| [`agent.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/agent.py) | LangGraph `StateGraph` orchestrator with SQLite checkpointer & `interrupt()` gate |
| [`dispatch.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/dispatch.py) | GitHub REST API dispatch (`gh issue create`) & Neo4j provenance linking |
| [`serve.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/serve.py) | Zero-dependency local HTTP server (`http.server`) for real-time dashboard playground search |
| [`export.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/export.py) & [`dashboard.py`](file:///Users/zorba/projects/channeltalk-solve/src/graph/dashboard.py) | Emits the single self-contained `out/dashboard.html` |

---

## 📊 The Honest Benchmark: Scikit-Learn vs. LLM

We evaluated both models on 600 held-out customer conversations for the 27-class **Intent** classification task:

| Model | Cohen's $\kappa$ | Macro-$F_1$ | Throughput | API Cost | Primary Role |
|---|---|---|---|---|---|
| **Scikit-Learn (TF-IDF + LogReg)** | **0.971** | **0.972** | ~700 convs/sec | **₩0** | **Fast Intent Labeler** |
| **LLM (OpenRouter GPT-4o-mini)** | 0.864 | 0.868 | ~1.2 convs/sec | $0.0003/conv | **Graph Signal Extractor** |

### Portfolio Narrative
Instead of claiming "LLMs win everything", we present an **honest engineering trade-off**:
1. **Scikit-Learn** is kept as the ultra-fast, zero-cost 1st-stage intent classifier ($\kappa = 0.971$).
2. **LLM** is used where TF-IDF fundamentally fails: extracting **unstructured relational graph signals** (`Symptom` $\rightarrow$ `Component` $\rightarrow$ `Severity` $\rightarrow$ `Confidence`).

---

## 🎨 Interactive Visual Deliverable (`out/dashboard.html`)

`out/dashboard.html` is a single, self-contained, CSP-safe HTML dashboard with **6 visual decision surfaces**:

1. **6-Stage Interactive Engine Stepper**: Clickable Step 1 to Step 6 buttons (or Auto-Play) showing live raw text, extracted JSON, Cypher code, GraphRAG evidence, LangGraph approval gate state, and GitHub issue provenance.
2. **LangGraph State Flow & Activity Feed**: Real-time execution graph highlighting executed nodes, timings, and the orange `interrupt()` approval pause.
3. **Interactive Neo4j Knowledge Graph**: Click any `RootCause` node to highlight its complete ₩ money flow path (`Conversation` $\rightarrow$ `Symptom` $\rightarrow$ `Component` $\rightarrow$ `Action`).
4. **GraphRAG Provenance Cards**: Issue drafts citing exact `conv_ids` with expandable `[📄 원문 보기 / View Original Text]` buttons.
5. **Honest Benchmark Bar Charts**: Scikit-Learn vs LLM performance comparison on held-out human labels.
6. **₩ Impact Sankey Diagram & Live Search Playground**: Component-to-disposition revenue flow + real-time 3-Arm (Dense / Sparse / Graph) search playground with live score meters.

---

## 🏆 PHASE 1 — AX Hackathon Submission Details

### Problem Statement
Customer support channels like ChannelTalk receive hundreds of daily conversations. However, team members only read random samples, while conventional CS AI chatbots merely answer queries and stop. No system reads *every* conversation, quantifies revenue leakage in ₩, and automatically dispatches developer tickets.

### PHASE 1 Pipeline Architecture (`src/pipeline/`)
- **Listen (`ingest.py`)**: Ingests 1,200 real public support conversations (Bitext dataset) into ChannelTalk schema.
- **Analyst (`analyze.py`)**: Classifies intents, calculates sentiment, and quantifies ₩ revenue at risk.
- **Assumptions (`assumptions.py`)**: Transparent financial model (Average Order Value = ₩55,000, 35% Recovery Rate based on Baymard Institute & TARP retention studies).
- **Triage/QA (`validate.py`)**: Evaluates classifier against held-out human labels ($\kappa = 0.992$ on 11 themes, $\kappa = 0.971$ on 27 intents).
- **Ops (`dispatch.py`)**: Dispatches real GitHub Issues (#6), FAQ Pull Requests (#7), and Jira Tickets via Atlassian Rovo MCP.

### Dispatched Hackathon Artifacts
- 🐛 **GitHub Issue (Triage)**: [Issue #6](https://github.com/kanziman/channel-voc-demo/issues/6)
- 🔀 **GitHub PR (Growth Ops)**: [PR #7](https://github.com/kanziman/channel-voc-demo/pull/7)
- 🧭 **Jira Ticket (CSM Ops)**: [`KAN-2`](https://risers.atlassian.net/browse/KAN-2)
- 🚀 **PHASE 2 Live Provenance Issue**: [Issue #10](https://github.com/kanziman/channel-voc-demo/issues/10)

---

## 📝 Written Hackathon Evaluation Answers

### 1. 어떤 문제를 해결하나요? (Problem Solved)
채널톡에는 매일 수많은 대화가 쌓이지만, 이를 전량 읽고 "어떤 시스템 부품에서 얼마의 매출 손실이 나는지"를 ₩로 정량화해 개발 티켓으로 작성하는 주체가 없습니다. 기존 CS AI는 응대만 하고 멈추는 반면, 본 솔루션은 **대화 수집 $\rightarrow$ 지식그래프 순회 $\rightarrow$ ₩ 손실액 정량화 $\rightarrow$ 실전 GitHub/Jira 이슈 배포**까지 닫는 루프를 완성합니다.

### 2. 어떻게 작동하나요? (Mechanism)
단 1회 호출로 `run.py`가 파이프라인을 실행합니다: 대화 추출(LLM) $\rightarrow$ Neo4j 지식그래프 적재 $\rightarrow$ Cypher 루트원인 순회(8건 이상 중복 탐지 시 ₩ 손실액 집계) $\rightarrow$ GraphRAG 근거 추출 $\rightarrow$ LangGraph `interrupt()` 승인 게이트 $\rightarrow$ GitHub Issue 배포. 결과는 사람용 `dashboard.html`과 에이전트용 `manifest.json`으로 이중 반환됩니다.

### 3. 왜 Codex/AX 네이티브인가요? (Differentiation)
단순히 텍스트 답변을 생성하고 멈추는 CS 챗봇과 달리, **직접 분석 코드를 짜고 Neo4j 그래프를 조회하며 실제 GitHub Issue/PR 및 Jira 티켓을 생성**합니다. CS 담당자 1명이 데이터 분석가 + 개발 티켓 작성자 + CSM 브리핑 역할까지 해내는 10배 인재밀도를 제공합니다.

### 4. 신뢰할 수 있나요? (Verification & Honesty)
1. **정직한 벤치마크**: 600건 격리 데이터셋에서 Scikit-Learn ($\kappa=0.971$)과 LLM ($\kappa=0.864$)의 성과를 데이터로 검증하고 빠른 분류기와 그래프 추출기로 역할을 분담했습니다.
2. **투명한 ₩ 모델**: 대화 건수는 실제 측정치이며, 돈 환산은 공인 논문(Baymard, TARP)에 근거한 투명한 가정 모델(`assumptions.py`)로 계산됩니다.
3. **감사 추적성(Provenance)**: 생성된 모든 GitHub Issue에는 근거가 된 대화 ID (`conv_id`)가 박히며, Neo4j 상에서 `(Action)-[:EVIDENCES]->(Conversation)` 엣지로 역추적됩니다.

### 5. 성장성은 어떤가요? (Scalability)
채널톡 Open API v5 (`/open/v5/user-chats`) 호환 로더가 이미 구현되어 있어, API 키만 입력하면 실전 프로덕션 환경에 즉시 적용 가능합니다. 단순 CS 응대를 넘어 **채널톡 상단의 Customer Intelligence 레이어**로 확장 가능합니다.

---

## 📁 Repository Structure

```text
├── README.md                      # Primary project documentation
├── pyproject.toml / uv.lock       # Unified Python 3.12 dependencies
├── .env.example                   # Environment variable template (OpenRouter, Neo4j, GitHub)
├── out/
│   ├── dashboard.html             # Single self-contained 6-visual HTML deliverable
│   ├── manifest.json              # Agent-to-agent structured execution manifest
│   ├── graph_snapshot.json        # Subgraph data & searchable corpus
│   └── benchmark.json             # Scikit-Learn vs LLM evaluation results
├── src/
│   ├── graph/                     # PHASE 2: Agentic Root-Cause Engine
│   │   ├── run.py                 # One-command execution entry point
│   │   ├── serve.py               # Local live search HTTP server
│   │   ├── agent.py               # LangGraph StateGraph & interrupt() gate
│   │   ├── retriever.py           # Triple Hybrid Search (Dense + Sparse + Graph RRF)
│   │   ├── rootcause.py           # Cypher traversal & ₩ promotion
│   │   ├── extract.py             # LLM function calling signal extraction
│   │   ├── load.py / db.py        # Neo4j graph MERGE loader & schema driver
│   │   ├── benchmark.py           # Held-out kappa evaluation runner
│   │   ├── schema.cypher          # Neo4j constraints & vector/fulltext indexes
│   │   └── dashboard_template.html# Interactive HTML dashboard template
│   ├── pipeline/                  # PHASE 1: AX Hackathon Script Pipeline
│   │   ├── run.py                 # Hackathon 5-arm runner
│   │   ├── analyze.py / ingest.py # Scikit-Learn classifier & Bitext loader
│   │   ├── assumptions.py         # Transparent ₩ revenue model
│   │   └── dispatch.py            # GitHub/Jira dispatchers
│   └── docs/                      # Technical plans & handover architecture
└── data/                          # Cached extractions & 1,200 conversations
```

---

## 📜 License & Citation

* **Dataset**: Bitext Customer Support Dataset ([CDLA-Sharing-1.0](https://cdla.dev/sharing-1-0/))
* **License**: MIT License
