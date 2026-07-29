# issue-33 — console-search-tab: 탭2 3-컬럼 하이브리드 서치

스택: **[FE]** `web/` (Vitest + RTL). 대상:
- `web/src/api/search.ts` [NEW]
- `web/src/console/HybridSearchTab.tsx` [NEW]
- 테스트: `search.test.ts`, `HybridSearchTab.test.tsx`

## 0. 계약 (src/server/routers/search.py)
- `POST /api/search/hybrid` req `{ query, k=6 }` → `HybridSearchResponse { query, top_component|null, counts: Record<string,number>, results: HybridResult[] }`.
- `HybridResult { id, dense: number|null, sparse: number|null, in_graph: boolean, text?, component?, severity?, rrf: number, arms: string[] }`.
- 3컬럼 = Dense(dense≠null) / Sparse BM25(sparse≠null) / Graph(in_graph) → RRF 융합 컬럼(rrf desc). D/S/G 관통 3색 유지.

## 1. 시그니처 (확정)

### web/src/api/search.ts
```ts
export interface HybridSearchRequest { query: string; k?: number }
export interface HybridResult {
  id: string; dense: number | null; sparse: number | null; in_graph: boolean;
  text?: string | null; component?: string | null; severity?: number | null;
  rrf: number; arms: string[];
}
export interface HybridSearchResponse {
  query: string; top_component: string | null; counts: Record<string, number>; results: HybridResult[];
}
// POST {API_BASE}/api/search/hybrid. !ok → {error} 봉투 throw.
export async function postSearch(req: HybridSearchRequest, signal?: AbortSignal): Promise<HybridSearchResponse>;
```

### web/src/console/HybridSearchTab.tsx
```ts
import type { HybridResult, HybridSearchRequest, HybridSearchResponse } from "../api/search";

export interface ArmColumns { dense: HybridResult[]; sparse: HybridResult[]; graph: HybridResult[]; rrf: HybridResult[] }
// results → 4컬럼: dense(dense≠null, dense desc) / sparse(sparse≠null, sparse desc) / graph(in_graph, rrf desc) / rrf(전체, rrf desc).
export function toColumns(results: HybridResult[]): ArmColumns;

export interface HybridSearchTabProps {
  searchFn?: (req: HybridSearchRequest) => Promise<HybridSearchResponse>; // 기본 postSearch
  initialQuery?: string;
}
export function HybridSearchTab(props: HybridSearchTabProps): JSX.Element;
```
동작:
- 검색 입력 제출 → `searchFn({query, k})` → 응답 저장. 빈 쿼리 무시.
- 4컬럼 렌더: Dense(D색)/Sparse(S색)/Graph(G색)/RRF. 각 행 = id(mono) + 점수(mono, dense/sparse/rrf). Graph 컬럼은 rrf 기준.
- D/S/G 3색은 `--arm-dense/sparse/graph` 토큰. 그라데이션 금지. 실패 시 에러.

## 2. 테스트 시나리오

### search.test.ts
- [x] [정상] postSearch — should POST /api/search/hybrid with {query, k}
- [x] [정상] postSearch — should return the parsed HybridSearchResponse when res.ok
- [x] [예외] postSearch — should throw the {error} envelope message when res.ok is false

### HybridSearchTab.test.tsx
- [x] [정상] toColumns — should split results into dense/sparse/graph arms by their score/flag
- [x] [정상] toColumns — should sort each arm column and rrf fusion descending
- [x] [정상] HybridSearchTab — should call searchFn with the query and render the three arm columns + RRF on submit
- [x] [정상] HybridSearchTab — should render result ids and scores in mono
- [x] [경계] HybridSearchTab — should ignore an empty/whitespace query
- [x] [예외] HybridSearchTab — should show an error state when the search fails

## 3. AC 교차 대조 (issue #33)
| AC | 커버 시나리오 |
| :-- | :-- |
| HybridSearchTab.tsx 생성 | HybridSearchTab 시나리오 전체 |
| search.ts — POST /api/search/hybrid | postSearch 시나리오 |
| Dense/Sparse/Graph 3컬럼 + 점수(mono) | render three arm columns / ids and scores in mono |
| RRF 융합 순위 컬럼 | render ... + RRF / sort rrf descending |
| D/S/G 3색 관통 | (App.css .search-col--dense/sparse/graph → arm 토큰; QA) |
| vitest — 3컬럼 + rrf | toColumns + render 시나리오 |
