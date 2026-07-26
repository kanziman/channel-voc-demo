# PHASE 2 — Root-Cause Intelligence (LangChain · LangGraph · Neo4j · GraphRAG)

> Portfolio upgrade of PHASE1's rule-based pipeline into a real agent system on a
> knowledge graph. Full plan: [`../docs/PHASE2_PLAN.md`](../docs/PHASE2_PLAN.md).

## One command

```bash
uv sync                              # unified py3.12 env (langchain/langgraph/neo4j/fastembed + sklearn)
python -m src.graph.run              # full pipeline → out/dashboard.html (opens it)
python -m src.graph.run --live       # also create real GitHub issues on approval
python -m src.graph.serve            # optional: live hybrid-search endpoint for the dashboard playground
```

The dashboard is a **6-stage interactive stepper** (raw text → extraction → graph →
traversal → GraphRAG → approval gate → dispatch) plus a **hybrid-search playground**.
Sample queries are precomputed (works offline, 0 console errors on load); typing a
free query and clicking *connect live* calls `serve.py`, which embeds the query with
the SAME bge-small model and runs real Neo4j dense + full-text + graph retrieval,
fused with RRF. Every result and provenance card has a `📄 원문 보기` full-text viewer.

Everything (LLM extraction, embeddings, hypotheses) is cached to `data/graph_cache/`,
so after the first run the demo replays deterministically in ~13s.

Requires `.env` with `OPENROUTER_API_KEY` and `NEO4J_*` (see [`../../.env.example`](../../.env.example)).
Embeddings are local (fastembed ONNX, `bge-small-en-v1.5`, 384d) — no key, offline.

## What it does (the loop)

```
1,200 real support conversations
  → LLM structured extraction   (intent · symptoms · component · severity · confidence)
  → Neo4j knowledge graph        (Customer→Conversation→Intent→Theme, Symptom→Component)
  → root-cause traversal         (a Component many convs implicate → RootCause, ₩-aggregated)
  → GraphRAG issue draft         (hybrid vector+graph retrieval → cited conv_ids)
  → LangGraph interrupt()        (human approval gate)
  → real GitHub issue            (+ provenance edges: Action→EVIDENCES→Conversation)
  → dual return: manifest.json (agents) + dashboard.html (humans, 6 visuals)
```

## Module map

| Module | Role |
|---|---|
| `config.py` | paths, model names, env, safety gates (single source of truth) |
| `llm.py` | the only model access — `chat()` (OpenRouter) / `embed()` (local fastembed) |
| `db.py` · `schema.cypher` | Neo4j driver + constraints + vector index |
| `taxonomy.py` | 27 intents · 11 themes · 8 components (controlled vocab) |
| `extract.py` | LLM structured extraction (function calling), disk-cached |
| `load.py` | idempotent `MERGE` of the graph + embedding upsert |
| `benchmark.py` | sklearn vs LLM on 600 held-out (κ / macro-F1) |
| `rootcause.py` | Cypher traversal → RootCause promotion + ₩ paths + hypotheses |
| `retriever.py` | GraphRAG hybrid (vector index + graph neighbors) |
| `drafter.py` | GraphRAG generation → GitHub issue with cited conv_ids |
| `agent.py` | LangGraph `StateGraph` + checkpointer + `interrupt()` |
| `dispatch.py` | real `gh issue create` + provenance edges (idempotent) |
| `export.py` · `dashboard.py` | curated snapshot → self-contained `out/dashboard.html` |
| `run.py` | the one-command orchestrator |

## Individual gates (each phase is runnable alone)

```bash
python -m src.graph.smoke        # 2.0 — Neo4j + OpenRouter + fastembed all green
python -m src.graph.load         # 2.1 — ingest 1,200 → graph
python -m src.graph.benchmark    # 2.1 — κ comparison table → out/benchmark.json
python -m src.graph.rootcause    # 2.2 — top root causes with ₩ paths + evidence
python -m src.graph.retriever    # 2.2 — hybrid retrieval demo
python -m src.graph.agent        # 2.3 — full agent to interrupt + resume
python -m src.graph.dashboard    # 2.4 — build the dashboard
```

## The honest benchmark

On the narrow, in-distribution 27-class **intent** task, the tuned TF-IDF classifier
wins (κ ≈ 0.97 vs 0.86) at ~700× throughput and zero API cost — so we **keep** it as
the fast labeler. The LLM earns its place by extracting **graph-structured signal**
(symptom → component → severity → confidence) that TF-IDF fundamentally cannot
produce, which is what powers the traversal. We measured both the win and the
trade-off. See `out/benchmark.json`.
