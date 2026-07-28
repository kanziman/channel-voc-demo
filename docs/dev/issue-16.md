# issue-16 — router-agent (rootcauses / run / dispatch) [WRAP+신규설계]

스택: **[BE] pytest (+ 실 Neo4j checkpointer 왕복)**. §2.3·§5-3. LangGraph `interrupt()`를 **상태없는 HTTP run→dispatch**에 매핑.

## 1. 설계 — 상태없는 승인 왕복

핵심: `POST /run`과 `POST /dispatch`가 **서로 다른 HTTP 요청**(각자 새 `Neo4jCheckpointSaver`+그래프 인스턴스)인데, `thread_id`로 Neo4j에 저장된 체크포인트에서 이어져 `interrupt()`→`Command(resume)`가 성립. #12 스파이크가 증명한 프로세스 경계 재개를 API로 노출.

**focused 승인 그래프**(라우터 내, agent.py CLI 그래프는 불변):
```
START → human_approval(interrupt payload=candidates) → dispatcher(승인분 dispatch_issue) → END
```
candidates는 `rootcause.compute(write=False)`에서 LLM 없이 구성(`{root_cause_key, component, title, revenue_at_risk_krw, confidence, cited_conv_ids}`) — dispatch_issue(non-live)가 요구하는 필드 충족.

## 2. 엔드포인트

```python
router = APIRouter(prefix="/api/agent", tags=["agent"])

@router.get("/rootcauses")  # → {"rootcauses": compute(write=False)}
@router.post("/run")        # {live?} → 그래프 시작; {thread_id, interrupt: payload} 반환(또는 dispatched)
@router.post("/dispatch")   # {thread_id, decision} → Command(resume=decision) → {thread_id, status, dispatched}
```
- **decision**: `"approve"`/`"all"`→전체 승인, `"reject"`/`"none"`/`[]`→반려(dispatch 0), `list[str]`→해당 key만. 승인/반려 양방향.
- `dispatch_issue(c, live=state.live)` — non-live면 provenance만 기록(GitHub 미호출).

## 3. 테스트 전략
`compute`·`dispatch_issue`를 monkeypatch(가짜 candidate/기록), **checkpointer는 실 Neo4j** 사용(왕복의 핵심 증명). Neo4j 미가용 시 skip. run→interrupt 수신→dispatch(thread_id)→resume까지 **단순 200 아닌 왕복 정합성** 검증.

## 4. 테스트 시나리오

- [x] [정상] rootcauses — should return compute(write=False) results as {rootcauses}
- [x] [정상] run — should start graph and return thread_id + interrupt payload with candidates
- [x] [정상] dispatch(approve) — should resume via thread_id and dispatch all approved (roundtrip)
- [x] [경계] dispatch(reject) — should resume and dispatch nothing when rejected
- [x] [경계] dispatch(subset) — should dispatch only the decision's keys
- [x] [정상] roundtrip — run→dispatch uses fresh saver instances, resumes from Neo4j (stateless)
- [x] [예외] dispatch — should 422 {"error"} when thread_id missing
- [x] [정상] mount — should expose /api/agent/rootcauses, /run, /dispatch

## 5. AC 교차 대조

| AC | 시나리오 |
|---|---|
| agent.py 생성 | mount |
| GET /rootcauses → compute(write=False) | rootcauses |
| POST /run → thread_id + interrupt | run |
| POST /dispatch → Command(resume) → dispatch_issue | dispatch(approve)/roundtrip |
| 승인/반려 양방향 | dispatch(approve)/(reject)/(subset) |
| pytest 통과 | 전체 |

> **ac-verifier #16 갭 보강**: (1) 미지/만료 thread_id로 dispatch 시 500 대신 404(get_tuple None 체크). (2) 빈 candidates → interrupt 없이 조기 반환(dead-branch 정리). (3) decision 경계(all/none/[]/단일키) 단위 테스트. (4) live=True 전파 테스트.
