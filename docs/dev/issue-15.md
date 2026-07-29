# issue-15 — router-graph (schema + subgraph expand) [WRAP+NEW]

스택: **[BE] pytest**. 정적 스키마 + `build_snapshot()` 재사용 + 신규 1/2-hop Cypher(§0-9).

## 1. 시그니처

```python
# src/server/routers/graph.py
router = APIRouter(prefix="/api/graph", tags=["graph"])

class GraphNode(BaseModel):      # extra="allow" — type별 props(total_conversations/hypothesis 등) 보존
    id: str; type: str; label: str
class GraphEdge(BaseModel):
    source: str; target: str; type: str
class SubgraphResponse(BaseModel):
    nodes: list[GraphNode]; edges: list[GraphEdge]; center: str | None = None

@router.get("/schema") -> dict            # 정적 온톨로지 메타(node_types/edge_types/hierarchy). DB 미접근.
@router.get("/subgraph") def subgraph(expand: str | None = None, hops: int = 1):
    # expand 없음 → build_snapshot()의 nodes/edges 재사용
    # expand=<prefix::key>, hops∈{1,2} → 신규 Cypher
```

`serve.py`에 `include_router(graph.router)`.

### expand id ↔ Neo4j 노드 매핑 (build_snapshot id 규칙 계승)
`comp::name`→(Component{name}), `rc::key`→(RootCause{key}), `sym::text`→(Symptom{text}), `conv::id`→(Conversation{id}), `act::key`→(Action{key}). prefix는 화이트리스트 → label/keyprop 인라인 안전, keyval은 파라미터.

### 신규 Cypher (§0-9)
```cypher
// center 존재 확인 + 라벨/프로퍼티
MATCH (n:<Label> {<key>:$v}) RETURN labels(n) AS nl, properties(n) AS np
// 1/2-hop 확장 (hops는 검증된 정수 인라인, 무방향)
MATCH (n:<Label> {<key>:$v})
MATCH (n)-[rel*1..<H>]-(m)
UNWIND rel AS r
WITH DISTINCT r
RETURN labels(startNode(r)) AS sl, properties(startNode(r)) AS sp,
       labels(endNode(r))   AS el, properties(endNode(r))   AS ep, type(r) AS t
```
db.run은 노드를 properties-only dict로 반환(labels 소실) → 위처럼 labels/properties를 명시 반환. 응답은 build_snapshot과 동일한 `{nodes, edges}` 셰이프로 재구성(프론트 일관성).

### 에러
- 알 수 없는 prefix → 400 `{"error":"unknown node id"}` (전역/명시 봉투)
- hops ∉ {1,2} → 422 (Query 검증) `{"error"}`
- 노드 부재 → 404 `{"error":"node not found"}`
(모두 #13 전역 핸들러/HTTPException→{"error"} 봉투로 커버)

### 테스트 전략
`/schema`는 정적이라 DB 불필요. `/subgraph`는 `build_snapshot`·`db.run`(graph 모듈 내)을 monkeypatch, `TestClient(serve.app)`로 검증.

## 2. 테스트 시나리오

- [x] [정상] schema — should return ontology node_types/edge_types/hierarchy without hitting DB
- [x] [정상] subgraph — should return build_snapshot nodes/edges when no expand given
- [x] [정상] subgraph — should expand 1-hop into nodes/edges around the node when expand+hops=1
- [x] [경계] subgraph — should expand 2-hop when hops=2
- [x] [정상] subgraph — should derive snapshot-style ids (comp::/rc::/…) and preserve edge direction
- [x] [예외] subgraph — should 400 {"error"} when expand prefix unknown
- [x] [예외] subgraph — should 404 {"error"} when node not found
- [x] [예외] subgraph — should 422 {"error"} when hops not in {1,2}
- [x] [정상] mount — should expose /api/graph/schema and /api/graph/subgraph

## 3. AC 교차 대조

| AC | 시나리오 |
|---|---|
| graph.py 생성 | mount |
| GET /schema 정적 메타 | schema |
| GET /subgraph expand&hops 신규 Cypher | 1-hop/2-hop/ids·direction |
| 기본 응답 build_snapshot 재사용 | no-expand |
| Pydantic 노드/엣지 모델 | 전 응답(모델 직렬화) |
| pytest 통과 | 전체 |

> **ac-verifier #15 갭 보강**: (1) `GraphEdge`에 `extra=allow` 추가 → build_snapshot의 edge `rc` prop 무손실. (2) Action id 불일치 수정 — 저장된 `Action.key`(`act_<rc>`)를 build_snapshot 규칙 `act::<rc>`에 맞춰 prefix strip(양 경로 동일 좌표계).
