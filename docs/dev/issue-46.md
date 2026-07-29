# issue-46 — chat-answer-cites: chat 답변 prose에 rc_key·conv_id 노출

스택: **[BE]** `src/server/routers/chat.py` (pytest, TestClient) + **[FE]** 회귀 테스트 1건 갱신(`web/src/components/CiteLink.test.tsx`, vitest). 대상:
- `src/server/routers/chat.py` [MODIFY] — answer/low_confidence prose에 그래프 ID 삽입
- `tests/test_router_chat.py` — prose ID 노출 검증 추가
- `web/src/components/CiteLink.test.tsx` — "documents the live gap" 회귀 테스트를 "ID 발화" 검증으로 교체

## 0. 배경 / 계약
- 프론트 `CiteText`(#27)는 `CITE_RE = \b(rc|sym|conv|comp|act|cust)_[A-Za-z0-9]+(...)` 로 answer 문자열에서 ID를 링크화한다.
- 현재 chat.py answer prose는 `top_component`("billing")·hypothesis만 담아 매칭 토큰이 없다 → 실데이터 드릴다운 무발화. 프론트 회귀 테스트가 이 갭을 고정.
- `rootcause.compute()`는 `key`(=`rc_<component>`, 예 `rc_billing`)와 `sample_conv_ids`(예 `conv_00001`)를 제공한다. 둘 다 `CITE_RE` 매칭.
- 변경은 **prose 표면만** — 게이트 로직·₩값·`subgraph_ref`·`arms`·`confidence`·`related_questions`·`interrupt_payload` 계약 불변.

## 1. 시그니처 (확정 — 함수 시그니처 불변, prose 조립만 변경)

### src/server/routers/chat.py — answer 게이트
```python
# 승격 루트원인: rc['key'](rc_xxx) + 대표 근거 대화 ID(conv_xxxxx) 최대 3개를 prose에 삽입
sample_ids = (rc.get("sample_conv_ids") or conv_ids)[:3]
cite_tail = f" 근거 대화: {', '.join(sample_ids)}." if sample_ids else ""
answer = (
    f"루트원인 {rc['key']} — '{top_component}' 관련 근거 {rc['frequency']}건. "
    f"위험 ₩{rc['revenue_at_risk_krw']:,}, 회수가능 ₩{rc['projected_recoverable_krw']:,}, "
    f"confidence {rc['confidence_avg']}. 가설: {rc['hypothesis']}.{cite_tail}"
)
```

### src/server/routers/chat.py — low_confidence 게이트
```python
# 헤지 근거도 순회 가능하도록 근거 대화 ID 최대 3개 삽입 (⚠·임계값 마커·None-guard 유지)
cite_tail = f" 근거 대화: {', '.join(conv_ids[:3])}." if conv_ids else ""
answer = (f"⚠ 확신이 낮아요 — {comp_label}근거 {len(results)}건은 루트원인 승격 "
          f"임계값({threshold}건) 미만이라 참고용으로만 보세요.{cite_tail}")
```

### refuse 게이트 — 근거 없음 → prose ID 미삽입(불변)

## 2. 테스트 시나리오

### [BE] tests/test_router_chat.py
- [정상] chat answer — should embed rc['key'] (rc_xxx) in the answer prose when a component is promoted
- [정상] chat answer — should embed sample conversation ids (conv_xxxxx) in the answer prose when promoted
- [경계] chat answer — should embed at most 3 sample conv ids in the prose
- [정상] chat low_confidence — should embed evidence conversation ids in the hedged answer prose
- [경계] chat low_confidence — should keep ⚠/임계값 markers and not leak literal "None" while embedding ids
- [경계] chat answer — should preserve the existing ₩/frequency/confidence contract (regression)
- [경계] chat refuse — should not embed any id token in the refuse prose

### [FE] web/src/components/CiteLink.test.tsx (회귀 교체)
- [정상] CiteText — should linkify rc_key and conv ids now that the backend embeds them in answer prose

## 3. AC ↔ 시나리오 대조
| AC | 커버 시나리오 |
| :-- | :-- |
| answer prose에 rc['key'] 노출 | embed rc['key'] in answer prose |
| answer prose에 conv_xxxxx 최대 3개 | embed sample conv ids / at most 3 |
| low_confidence prose에 conv id 최대 3개 (⚠·임계값·None-guard 유지) | embed conv ids in low_confidence / keep markers no None |
| refuse ID 미노출 | refuse should not embed id |
| 기존 계약 불변 | preserve ₩/frequency/confidence contract + 기존 test_router_chat 전부 green |
| 프론트 회귀 갱신 | CiteText linkify rc_key and conv ids |
