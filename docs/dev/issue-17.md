# issue-17 — backend-roundtrip 통합 테스트 (백엔드 MVP 캡스톤)

스택: **[BE] pytest (+ 실 Neo4j)**. 테스트 전용 이슈 — 라우터 구현(#11–#16)은 이미 머지됨. 단순 200 체크 금지, **크로스-엔드포인트 시나리오**로 검증.

## 1. tests/test_api_agent_roundtrip.py — Agent 왕복

per-router 단위 테스트(test_router_agent.py)와 차별: **엔드포인트 간 일관성 + 체크포인트 지속성**을 하나의 서사로 검증.
- `GET /rootcauses` → `POST /run`의 interrupt payload candidates가 rootcauses와 **동일 집합**인지(크로스-엔드포인트 정합).
- run 직후 Neo4j에 `(:AgentCheckpoint {thread_id})`가 **실제로 존재**(재개의 물리적 근거) — DB 직접 조회.
- `POST /dispatch(approve)`가 다른 요청(새 saver)인데 run의 candidates를 재개해 dispatch — resume 정합성.
- 반려 경로도 동일 서사로.

## 2. tests/test_api_chat.py — Chat 3분기

gate가 §5-6(ROOTCAUSE_MIN_CONVERSATIONS 승격 경계)와 연결됨을 시나리오로:
- **충분**: 승격 rc 존재 → answer + 실제 ₩값 + confidence=rc.confidence_avg.
- **0 hits**: refuse — 답 지어내지 않음(그래프 근거 문구) + chips + confidence 0.
- **경계**: 근거 有·승격 X → low_confidence + ⚠ + confidence < 충분 분기 confidence.
- 세 분기의 confidence가 refuse(0) < 경계 < 충분 **순서**임을 교차 검증(단순 값이 아닌 관계).

## 3. 시나리오
- [x] [정상] agent — rootcauses keys == run interrupt candidate keys (cross-endpoint)
- [x] [정상] agent — checkpoint persisted to Neo4j after run (durability)
- [x] [정상] agent — dispatch(approve) resumes thread and dispatches the run's candidates
- [x] [경계] agent — dispatch(reject) resumes same thread and dispatches nothing
- [x] [정상] chat — sufficient branch answers with real ₩ + rc confidence
- [x] [예외] chat — 0-hits branch refuses without a fabricated answer (+ chips)
- [x] [경계] chat — borderline branch hedges below threshold
- [x] [정상] chat — confidence ordering refuse(0) < borderline < sufficient

## 4. AC 교차 대조
| AC | 시나리오 |
|---|---|
| test_api_agent_roundtrip.py 생성·통과 | agent 4종 |
| run→interrupt→dispatch→resume + checkpointer 정합 | cross-endpoint + durability + resume |
| chat 3분기(충분/0hits/경계) | chat 3 + ordering |
| test_api_chat.py 생성·통과 | chat 파일 |
