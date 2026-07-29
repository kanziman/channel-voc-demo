# issue-29 — evidence-panel: GraphRAG 서브그래프 드로잉

스택: **[FE]** `web/` (Vitest + RTL, react-cytoscapejs mock). 대상:
- `web/src/api/graph.ts` [NEW]
- `web/src/components/EvidencePanel.tsx` [NEW]
- 테스트: `graph.test.ts`, `EvidencePanel.test.tsx`

## 0. 백엔드 계약 (src/server/routers/graph.py)
- `GET /api/graph/subgraph` → `SubgraphResponse { nodes: GraphNode[], edges: GraphEdge[], center: string|null }`
  - `GraphNode { id, type, label, ...extra }`, id 스킴 `rc::rc_billing` / `comp::billing` / `conv::conv_00001` / `sym::...` / `act::...`.
  - `GraphEdge { source, target, type, ...extra }`.
  - `?expand=<id>&hops=1|2` — 없으면 build_snapshot(루트원인 스냅샷).
- chat `subgraph_ref = { top_component, root_cause_key?, conversation_ids? }` → `root_cause_key` 있으면 `expand=rc::<key>&hops=1`, 없으면 default 스냅샷.
- 범위: EvidencePanel + graph.ts만(AC 관련파일). ChatStream/App 통합은 AC 밖 → 별도. EvidencePanel은 props 주도(subgraphRef, evidence, onExplore).

## 1. 시그니처 (확정)

### web/src/api/graph.ts
```ts
export interface GraphNode { id: string; type: string; label: string; [k: string]: unknown }
export interface GraphEdge { source: string; target: string; type: string; [k: string]: unknown }
export interface SubgraphResponse { nodes: GraphNode[]; edges: GraphEdge[]; center: string | null }
export interface SubgraphQuery { expand?: string; hops?: 1 | 2 }
// GET {API_BASE}/api/graph/subgraph?expand=&hops=. !ok → {error} 봉투 throw.
export async function getSubgraph(q?: SubgraphQuery, signal?: AbortSignal): Promise<SubgraphResponse>;
```

### web/src/components/EvidencePanel.tsx
```ts
import type { ElementDefinition, Stylesheet } from "cytoscape";

export interface EvidenceItem { id: string; arms: string[]; score: number; label?: string }
export interface EvidenceSubgraphRef { top_component?: string; root_cause_key?: string; conversation_ids?: string[] }
export interface EvidencePanelProps {
  subgraphRef: EvidenceSubgraphRef | null;
  evidence?: EvidenceItem[];
  onExplore?: () => void;                                  // "⤢ 탐색" → 콘솔 진입
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>; // 기본 getSubgraph
}

// SubgraphResponse → cytoscape elements(노드 data:{id,label,type}, 엣지 data:{source,target,type}).
export function toElements(sub: SubgraphResponse): ElementDefinition[];
// 노드/엣지 base 스타일 + RootCause 노드만 glow(underlay). glow 색은 인자로 주입(토큰 해석 결과).
export function graphStylesheet(glow: string): Stylesheet[];

export function EvidencePanel(props: EvidencePanelProps): JSX.Element;
```
동작:
- subgraphRef 변경 시 `getSubgraphFn` 호출: `root_cause_key` 있으면 `{expand:"rc::"+key, hops:1}`, 없으면 인자 없이(default 스냅샷). null이면 조회 안 하고 placeholder.
- 서브그래프는 `<CytoscapeComponent elements={toElements(g)} stylesheet={graphStylesheet(glow)} />`. `--glow-rootcause`는 CSS drop-shadow 필터라 cytoscape underlay-color(색상)에 대입 불가 → glow 색은 `--node-rootcause`(RootCause 노드색)를 읽어 underlay로 적용(RootCause 전용 예외 유지). 노드색도 `--node-*` 토큰 런타임 해석(폴백 리터럴).
- 근거 리스트: 각 EvidenceItem = D/S/G arm 태그(관통 3색) + score(mono).
- "⤢ 탐색" 버튼 → onExplore().
- 그라데이션 금지, 유일 예외 RootCause `--glow-rootcause`. 수치·ID mono.

## 2. 테스트 시나리오

### graph.test.ts
- [x] [정상] getSubgraph — should GET /api/graph/subgraph with no query when called without params
- [x] [정상] getSubgraph — should include expand and hops in the query string when provided
- [x] [정상] getSubgraph — should return the parsed SubgraphResponse when res.ok
- [x] [예외] getSubgraph — should throw the {error} envelope message when res.ok is false

### EvidencePanel.test.tsx (react-cytoscapejs mock)
- [x] [정상] toElements — should map nodes and edges to cytoscape element definitions
- [x] [정상] toElements — should assign a per-type fill color to each node (ac-verifier)
- [x] [정상] graphStylesheet — should apply the glow only to RootCause nodes (others have no glow)
- [x] [정상] EvidencePanel — should fetch the subgraph with expand=rc::<key> when root_cause_key is present
- [x] [정상] EvidencePanel — should fetch the default snapshot (no expand) when root_cause_key is absent
- [x] [정상] EvidencePanel — should render each evidence item with its D/S/G arm tags and score (mono)
- [x] [정상] EvidencePanel — should call onExplore when the 탐색 action is clicked
- [x] [경계] EvidencePanel — should render a placeholder and not fetch when subgraphRef is null
- [x] [예외] EvidencePanel — should show an error state (not stay loading) when the subgraph fetch fails (ac-verifier)

## 3. AC 교차 대조 (issue #29)
| AC | 커버 시나리오 |
| :-- | :-- |
| EvidencePanel.tsx 생성 | EvidencePanel 시나리오 전체 |
| graph.ts — GET /api/graph/subgraph(subgraph_ref 사용) | getSubgraph 시나리오 + fetch with expand=rc::key |
| 노드/엣지 렌더(cytoscape), RootCause만 glow | toElements + graphStylesheet(glow only RootCause) |
| 근거 리스트 arm 태그 + 점수(mono) | render evidence item with arm tags and score |
| "⤢ 탐색" 콘솔 진입 트리거 | should call onExplore |
| vitest — 조회/렌더 + arm 태그 | 위 통합 시나리오 |
