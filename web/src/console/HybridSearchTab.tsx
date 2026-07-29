// Console tab 2 — 3-column hybrid search (§2.5). Shows Dense / Sparse(BM25) /
// Graph arms side by side, then the RRF fusion ranking — the hybrid_search
// arms/rrf contract rendered verbatim. D/S/G keep the through-line arm colors.
import { useState } from "react";
import { postSearch } from "../api/search";
import type { HybridResult, HybridSearchRequest, HybridSearchResponse } from "../api/search";

export interface ArmColumns {
  dense: HybridResult[];
  sparse: HybridResult[];
  graph: HybridResult[];
  rrf: HybridResult[];
}

export function toColumns(results: HybridResult[]): ArmColumns {
  const byDesc = (get: (r: HybridResult) => number) => (a: HybridResult, b: HybridResult) =>
    get(b) - get(a);
  return {
    dense: results.filter((r) => r.dense != null).sort(byDesc((r) => r.dense ?? 0)),
    sparse: results.filter((r) => r.sparse != null).sort(byDesc((r) => r.sparse ?? 0)),
    graph: results.filter((r) => r.in_graph).sort(byDesc((r) => r.rrf)),
    rrf: [...results].sort(byDesc((r) => r.rrf)),
  };
}

export interface HybridSearchTabProps {
  searchFn?: (req: HybridSearchRequest) => Promise<HybridSearchResponse>;
  initialQuery?: string;
}

type ColumnKey = "dense" | "sparse" | "graph" | "rrf";
const COLUMNS: { key: ColumnKey; label: string; score: (r: HybridResult) => number | null }[] = [
  { key: "dense", label: "Dense", score: (r) => r.dense },
  { key: "sparse", label: "Sparse · BM25", score: (r) => r.sparse },
  { key: "graph", label: "Graph", score: (r) => r.rrf },
  { key: "rrf", label: "RRF 융합", score: (r) => r.rrf },
];

const fmt = (n: number | null) => (n == null ? "—" : String(n));

export function HybridSearchTab({ searchFn = postSearch, initialQuery = "" }: HybridSearchTabProps) {
  const [query, setQuery] = useState(initialQuery);
  const [resp, setResp] = useState<HybridSearchResponse | null>(null);
  const [failed, setFailed] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setFailed(false);
    searchFn({ query: q, k: 6 })
      .then((r) => setResp(r))
      .catch(() => setFailed(true));
  }

  const cols = resp ? toColumns(resp.results) : null;

  return (
    <section className="console-tab search-tab" data-testid="search-tab">
      <form className="st-search" onSubmit={handleSubmit}>
        <input
          className="st-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="하이브리드 검색 query…"
        />
        <button type="submit" className="st-go">검색</button>
      </form>

      {failed ? (
        <div className="st-error mono" data-testid="search-error">검색에 실패했어요</div>
      ) : cols ? (
        <div className="st-cols">
          {COLUMNS.map((col) => (
            <div key={col.key} className={`st-col st-col--${col.key}`} data-testid={`col-${col.key}`}>
              <div className="st-col-h">{col.label}</div>
              <ul className="st-col-list">
                {cols[col.key].map((r) => (
                  <li key={r.id} className="st-row">
                    <span className="st-id mono">{r.id}</span>
                    <span className="st-score mono">{fmt(col.score(r))}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="st-placeholder mono">query를 입력해 3중 하이브리드 서치를 실행하세요</div>
      )}
    </section>
  );
}
