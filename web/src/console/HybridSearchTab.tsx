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
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    setFailed(false);
    setLoading(true);
    searchFn({ query: q, k: 6 })
      .then((r) => setResp(r))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }

  const cols = resp ? toColumns(resp.results) : null;

  return (
    <section className="console-tab search-tab" data-testid="search-tab">
      <form className="st-search" onSubmit={handleSubmit}>
        <input
          className="st-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="order status"
          disabled={loading}
        />
        <button type="submit" className="st-go" disabled={loading}>
          {loading && <span className="spinner" style={{ marginRight: 6 }} />}
          검색
        </button>
      </form>

      {failed ? (
        <div className="st-error mono" data-testid="search-error">검색에 실패했어요</div>
      ) : loading ? (
        <div className="st-placeholder mono" data-testid="search-loading">
          <span className="spinner" style={{ marginRight: 8 }} />
          3중 하이브리드 서치 검색 중…
        </div>
      ) : cols ? (
        <>
          <div className="st-cols">
            {COLUMNS.map((col) => (
              <div key={col.key} className={`st-col st-col--${col.key}`} data-testid={`col-${col.key}`}>
                <div className="st-col-h">{col.label}</div>
                <ul className="st-col-list">
                  {cols[col.key].map((r) => {
                    const itemKey = `${col.key}:${r.id}`;
                    const isExpanded = expandedId === itemKey;
                    return (
                      <li
                        key={itemKey}
                        className={`st-row-item${isExpanded ? " is-expanded" : ""}`}
                        onClick={() => setExpandedId(isExpanded ? null : itemKey)}
                      >
                        <div className="st-row">
                          <span className="st-id mono">
                            <span className="st-arrow">{isExpanded ? "▾" : "▸"}</span> {r.id}
                          </span>
                          <span className="st-score mono">{fmt(col.score(r))}</span>
                        </div>
                        {isExpanded && r.text && (
                          <div className="st-detail mono" data-testid={`detail-${col.key}-${r.id}`}>
                            {r.component && <div className="st-detail-comp">[{r.component}]</div>}
                            <div className="st-detail-text">"{r.text}"</div>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>

          <div className="st-info mono" data-testid="search-info">
            <div className="st-info-title">💡 하이브리드 서치 결과 참고 안내</div>
            <ul className="st-info-list">
              <li><b>DENSE</b>: 벡터 의미 유사도 점수 (0~1). 맥락/의미가 유사한 대화 탐색</li>
              <li><b>SPARSE (BM25)</b>: 키워드 완전 일치 점수. 쿼리 단어가 텍스트 원문에 직치할 때 탐색</li>
              <li><b>GRAPH</b>: Neo4j 지식그래프 구조 상에서 1-hop으로 직접 연결된 지식/대화 추적</li>
              <li><b>RRF 융합</b>: 3가지 갈래의 상위 랭크를 RRF(Reciprocal Rank Fusion) 상호 순위 융합 공식을 통해 최종 하이브리드 랭킹으로 통합</li>
            </ul>
          </div>
        </>
      ) : (
        <div className="st-placeholder mono">query를 입력해 3중 하이브리드 서치를 실행하세요</div>
      )}
    </section>
  );
}
