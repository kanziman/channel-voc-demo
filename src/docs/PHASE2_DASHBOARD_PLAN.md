# PHASE 2 — Visualization-First Dashboard Plan (rewritten)

> **Focus**: make `out/dashboard.html` easy to *watch* and *understand* — a viewer
> should follow one support conversation as it flows through all 6 stages into a
> shipped, cited GitHub issue. Backend work is minimized to what the visuals need.
>
> This rewrites the "BGE-M3 Hybrid" draft after a review found its backend premise
> broken in this environment. See **§0 Review corrections**.

---

## 0. Review corrections (why this differs from the draft)

| Draft claim | Reality (verified) | Decision |
| :-- | :-- | :-- |
| "FastEmbed auto-loads `BAAI/bge-m3` (1024d)" | **False** — fastembed 0.8.0 lists neither bge-m3 dense nor sparse. Would fail at `smoke`. | **Drop BGE-M3.** Keep dense = `bge-small-en-v1.5` (384d, already cached, deterministic). |
| "Sparse = Full-Text / Token Weights" (treated as one) | Neo4j has **full-text (Lucene BM25)** but **no native learned-sparse vector index**. bge-m3 sparse weights couldn't be indexed. | Sparse arm = **Neo4j full-text**. Real, works today. |
| "Live real-time hybrid search" in static HTML | Impossible standalone — no embedding model in a static file. | **Local search endpoint** (`serve.py`) embeds the query with the *same* fastembed model; page falls back to precomputed samples when offline. |

Locked scope (from user review):
- **Embedding**: 384d bge-small + Neo4j full-text sparse + graph 1-hop, fused with RRF. All three arms render identically as a **3-arm score breakdown**, so the visual story is unchanged.
- **Live search**: Method B — `python -m src.graph.serve` (stdlib `http.server`, zero new deps). Query typed on screen → POST → fastembed embed → real Neo4j dense + full-text + graph → RRF → scores + original text.

Non-goals: no BGE-M3, no learned-sparse index, no browser-side ONNX, no re-embedding, no vector-index dimension change.

---

## 1. The live hybrid search — how real-time query embedding works

```
Browser playground                       serve.py  (127.0.0.1:8756, stdlib only)
────────────────────                     ─────────────────────────────────────
type "payment refund 502"  ──POST /search──▶  q = llm.embed_one(query)     # SAME bge-small as ingest
                                              dense  = db.index.vector.queryNodes('conversation_embedding', k, q)
                                              sparse = db.index.fulltext.queryNodes('conversation_fulltext', query)
                                              graph  = 1-hop component neighbours
                                              fused  = RRF(dense, sparse, graph)   # 1/(60+rank)
   render 3 bars + cards  ◀──JSON──────────  {per_arm_scores, fused, original_text}
```

- **Vector consistency**: the query is embedded by the exact model + preprocessing that produced the stored document vectors, so cosine scores are meaningful (the browser-ONNX route can't guarantee this).
- **Graceful fallback**: if `fetch` fails (dashboard opened as a bare file), the playground uses precomputed sample-query results baked into the payload and shows `▶ run python -m src.graph.serve for live queries`.
- **Determinism**: sample queries are precomputed at build time → the recorded demo always shows the same screen; the live box is the "try it yourself" layer on top.

---

## 2. Proposed changes

### Backend (minimal — only what the visuals need)

#### [MODIFY] `src/graph/schema.cypher`
- Add a full-text index (keep the existing 384d vector index unchanged):
  ```cypher
  CREATE FULLTEXT INDEX conversation_fulltext IF NOT EXISTS
  FOR (c:Conversation) ON EACH [c.text];
  ```

#### [MODIFY] `src/graph/retriever.py`
- Add `fulltext_search(query, k)` → `db.index.fulltext.queryNodes('conversation_fulltext', $q)`.
- Add `rrf_fuse(arms, k=60)` → Reciprocal Rank Fusion over dense / sparse / graph.
- Add `hybrid_search(query, k)` → returns, per result: `{id, dense_score, sparse_score, in_graph, rrf, text}`.
  Reuse existing `vector_search` (dense) and `graph_neighbors` (structure).
- Keep `hybrid_for_rootcause()`; internally route it through the new fusion so drafts and the playground share one code path.

#### [NEW] `src/graph/serve.py`
- Stdlib `http.server.ThreadingHTTPServer`; one route `POST /search {query,k}`.
- Calls `retriever.hybrid_search`; returns JSON (scores + original text). CORS `*` for `file://`.
- `GET /health` for the page to detect live mode. Port from `config.SEARCH_PORT` (default 8756).
- `python -m src.graph.serve` prints the URL and stays up.

#### [MODIFY] `src/graph/config.py`
- Add `SEARCH_PORT = int(os.getenv("VOC_SEARCH_PORT", "8756"))`. No embedding changes.

### Dashboard (the focus)

#### [MODIFY] `src/graph/export.py`
Collect a **per-stage sample** so each stepper panel shows real data for the SAME tracer conversation:
- Stage 1 — one raw conversation (full text) + its extracted JSON (from cache).
- Stage 2 — the `MERGE` Cypher + resulting node counts + "384d embedding upserted".
- Stage 3 — the traversal Cypher + one promoted RootCause with its ₩ aggregation + evidence ids.
- Stage 4 — one precomputed sample query → 3-arm evidence + RRF (for offline fallback).
- Stage 5 — the LangGraph interrupt payload (candidates + gate thresholds + approved decision).
- Stage 6 — the Action: issue url + `EVIDENCES` conv ids.
- Add `corpus`: `{conv_id: full_text}` for every evidence/sample conversation (for 원문 보기 + offline keyword fallback). ~1,200 texts ≈ 1 MB inlined — acceptable; scope to referenced ids if size matters.
- Add `search_samples`: 3–5 precomputed queries with full hybrid results.
- Add `embedding_meta`: `{model: bge-small-en-v1.5, dim: 384, sparse: neo4j-fulltext, fusion: RRF}`.

#### [MODIFY] `src/graph/dashboard_template.html`
1. **6-Stage interactive stepper** (primary new UX). A sticky step bar:
   `1 LLM Extraction → 2 Graph+Embed Ingest → 3 Root-Cause Traversal → 4 Hybrid GraphRAG → 5 승인 게이트 → 6 Dispatch+Provenance`.
   - Clicking a step reveals that stage's panel (raw data / Cypher / graph state / evidence / gate / issue) for one tracer conversation, so the viewer literally watches it transform.
   - A "▶ play" control auto-advances 1→6 with the existing agent-flow highlight synced.
   - Keeps the current 6 sections; the stepper is the guided narrative layer over them (progressive disclosure, not a rewrite).
2. **Step 5 approval-gate component** — shows the real `interrupt()` state from the manifest:
   `⏸ Pending Approval` (candidates + ₩ + confidence vs `DISPATCH_CONFIDENCE_THRESHOLD`) → `✓ Approved & Dispatched` with the issue link. Makes the human-in-the-loop gate legible.
3. **Interactive Hybrid Search Playground**:
   - Sample-query buttons (`ERR_PAY_502`, `checkout button frozen`, `invoice billing fail`, `refund policy`) → full 3-arm breakdown from precomputed data.
   - Free-text box → on submit, `fetch` the local endpoint for **live** dense+sparse+graph; offline → keyword match over `corpus` + the "run serve" hint.
   - Each result: **Dense (의미) / Sparse (키워드) / Graph (구조)** bars + RRF rank, and a **`[📄 원문 보기]`** toggle → inline expander with the full customer text (from `corpus`).
4. **원문 보기 on Provenance cards** — same toggle on the existing GraphRAG evidence rows.

#### [MODIFY] `src/graph/dashboard.py`
- Bind `stages`, `corpus`, `search_samples`, `embedding_meta`, and the approval-gate state into the payload. No structural change to the generator.

---

## 3. Verification plan

**Automated**
- `python -m src.graph.schema` — full-text index created, vector index still 384d ONLINE.
- `python -m src.graph.smoke` — Neo4j + OpenRouter + fastembed(384d) green (unchanged).
- `python -m src.graph.run` — full pipeline → `out/dashboard.html`, console-error-free (re-QA via browse).
- New: `python -m src.graph.retriever "payment refund"` prints dense/sparse/graph/RRF for a query.

**Manual (browse skill, headless)**
- Stepper: click 1→6, assert each panel renders its stage data; play mode advances.
- Step 5: shows `⏸ Pending → ✓ Approved` with issue #10 link.
- Playground offline: sample buttons show 3-arm scores; free-text shows keyword fallback + hint.
- Playground live: start `serve.py`, type a query, assert real scores return and `[📄 원문 보기]` opens full text.
- Dark mode + mobile viewport pass; 0 console errors.

---

## 4. Risks & mitigations

| Risk | Mitigation |
| :-- | :-- |
| Full-text index needs (re)build on AuraDB | idempotent `IF NOT EXISTS`; verify ONLINE in `schema.py` (consume results — same lazy-DDL gotcha as the vector index) |
| Inlined `corpus` bloats HTML | scope to referenced conv ids; ~1 MB is fine, measure and cap |
| Live endpoint not running during demo | precomputed sample queries + explicit "run serve" hint = never a dead UI |
| Free-text keyword fallback ≠ dense quality | label it honestly ("keyword match — start serve for semantic"); sample buttons carry the full-hybrid story |
| Stepper adds complexity to a working dashboard | build as an additive layer over the current 6 sections; keep scroll working if JS disabled |

---

## 5. Out of scope (explicitly not doing)
BGE-M3 / 1024d, learned-sparse indexing, browser-side ONNX embedding, re-embedding the corpus, vector-index dimension change, any new heavy dependency.
