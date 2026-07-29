# issue-32 — console-ontology-tab: 탭1 온톨로지 & 그래프 탐색

스택: **[FE]** `web/` (Vitest + RTL, react-cytoscapejs mock). 대상:
- `web/src/console/OntologyGraphTab.tsx` [NEW]
- 테스트: `web/src/console/OntologyGraphTab.test.tsx`
- 재사용: `getSubgraph`(graph.ts), `toElements`/`graphStylesheet`(EvidencePanel #29) — RootCause glow 예외 동일.

## 0. 계약
- `GET /api/graph/subgraph`(expand 없음) → build_snapshot(온톨로지 체인 스냅샷).
- 노드 클릭 → `getSubgraph({ expand: "<prefix::key>", hops: 1|2 })` → 반환 서브그래프를 현재 그래프에 **병합**(노드 id·엣지 dedupe).
- Customer→Conversation→Symptom→Component→RootCause→Action 체인. RootCause만 glow(EvidencePanel graphStylesheet 재사용).

## 1. 시그니처 (확정)

### web/src/console/OntologyGraphTab.tsx
```ts
import type { SubgraphQuery, SubgraphResponse } from "../api/graph";

// 두 서브그래프 병합: 노드는 id로, 엣지는 source→target:type로 dedupe. center는 b 우선.
export function mergeSubgraph(a: SubgraphResponse, b: SubgraphResponse): SubgraphResponse;

export interface OntologyGraphTabProps {
  getSubgraphFn?: (q?: SubgraphQuery) => Promise<SubgraphResponse>; // 기본 getSubgraph
  initialHops?: 1 | 2;
}
export function OntologyGraphTab(props: OntologyGraphTabProps): JSX.Element;
```
동작:
- 마운트 시 `getSubgraphFn()`(default 스냅샷) 로드 → cytoscape 렌더(`toElements`+`graphStylesheet`).
- hops 토글(1/2). 노드 클릭 확장: **cytoscape 캔버스 노드 tap**(`cy.on('tap','node')`)과 접근성 노드 목록 버튼이 동일 `expand` 핸들러를 호출 → `getSubgraphFn({expand: id, hops})` → `mergeSubgraph`로 병합 렌더.
- 로딩/실패 상태. 토큰만·그라데이션 금지(RootCause glow 예외).

## 2. 테스트 시나리오

### OntologyGraphTab.test.tsx (react-cytoscapejs mock)
- [x] [정상] mergeSubgraph — should union nodes by id and edges by source→target:type (dedupe)
- [x] [정상] mergeSubgraph — should keep both distinct nodes/edges and prefer b.center
- [x] [정상] OntologyGraphTab — should load the default snapshot on mount (getSubgraphFn with no args)
- [x] [정상] OntologyGraphTab — should expand a node with {expand:id, hops:1} and merge the result on node click
- [x] [정상] OntologyGraphTab — should use hops:2 when the 2-hop toggle is selected
- [x] [정상] OntologyGraphTab — should expand from a cytoscape canvas node tap, not only the node list (ac-verifier)
- [x] [경계] OntologyGraphTab — should show an error state when the initial load fails

## 3. AC 교차 대조 (issue #32)
| AC | 커버 시나리오 |
| :-- | :-- |
| OntologyGraphTab.tsx 생성 | 시나리오 전체 |
| 온톨로지 체인 노드 렌더(cytoscape) | load default snapshot on mount (cytoscape elements) |
| 노드 클릭 → expand hops 1/2 병합 | expand node {expand,hops:1} merge / hops:2 toggle |
| RootCause만 glow | graphStylesheet(#29) 재사용 — glow-only-RootCause는 #29에서 검증 |
| vitest — 1/2-hop 확장·병합 | expand/hops/merge 시나리오 |
