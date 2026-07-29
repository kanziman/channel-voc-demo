# issue-49 — chat-evidence-list: chat 응답에 per-hit evidence 노출 → EvidencePanel 배선

스택: **[BE]** `src/server/routers/chat.py` (pytest) + **[FE]** `web/src/api/chat.ts`·`web/src/App.tsx` (vitest). 방안 B(백엔드 확장 — 중복 retrieval 없음, 답변이 근거로 삼은 것과 동일 보장).

## 0. 배경 / 계약
- `EvidencePanel`(#29)은 `evidence?: EvidenceItem[]`(`{id, arms, score, label?}`)로 per-hit 근거 리스트(D/S/G arm 태그 + score mono)를 그린다.
- `ChatResponse`는 per-hit score를 안 담아 리스트가 항상 빔. 그러나 `chat.py`는 이미 `hybrid_search(message, k=6)`를 실행하고 `results`(각 hit에 `id`·`arms`·`rrf` 보유)를 가진다 → **재조회 없이** 그대로 노출.
- score는 앱 전역 관습대로 rrf 원값을 verbatim 렌더(HybridSearchTab과 동일, 반올림 없음).

## 1. 시그니처 (확정)

### src/server/routers/chat.py
```python
def _evidence(results: list[dict]) -> list[dict]:
    """Per-hit retrieval evidence for the panel (#49) — the same hybrid_search
    results the answer was gated on (no re-query). id + D/S/G arms + rrf score."""
    return [{"id": r["id"], "arms": r.get("arms", []), "score": r.get("rrf", 0)}
            for r in results]

class ChatResponse(BaseModel):
    ...
    evidence: list[dict] = []   # [NEW] per-hit {id, arms, score}
# refuse → evidence=[]; low_confidence·answer → evidence=_evidence(results)
```

### web/src/api/chat.ts
```ts
export interface ChatResponse {
  ...
  evidence: { id: string; arms: string[]; score: number }[];  // [NEW]
}
```

### web/src/App.tsx
```tsx
// 최신 응답의 evidence를 EvidencePanel에 전달 (구조적으로 EvidenceItem[]와 호환)
<EvidencePanel subgraphRef={subgraphRef} evidence={latest?.evidence ?? []} ... />
```

## 2. 테스트 시나리오

### [BE] tests/test_router_chat.py
- [정상] chat answer — should expose per-hit evidence (id/arms/score) mirroring the hybrid_search results
- [정상] chat low_confidence — should expose evidence for the hedged results
- [경계] chat answer — evidence ids should equal the results ids (single retrieval, no re-query drift)
- [경계] chat — evidence score should mirror each result's rrf
- [경계] chat refuse — should expose empty evidence when there are no hits

### [FE]
- [정상] chat.ts ChatResponse — parses the evidence array (covered via App wiring test + type)
- [정상] App — should feed the latest response evidence into EvidencePanel (renders evidence items)
- [경계] App — should render no evidence items when the response evidence is empty

## 3. AC ↔ 시나리오 대조
| AC | 커버 시나리오 |
| :-- | :-- |
| ChatResponse.evidence 필드(BE+FE) | expose per-hit evidence / App wiring + chat.ts 타입 |
| answer·low_confidence evidence=results(재조회 없음) | expose evidence (answer/low_conf) / evidence ids == results ids / score == rrf |
| refuse evidence=[] | empty evidence when no hits |
| 기존 계약 불변 | 기존 test_router_chat 전부 green |
| App → EvidencePanel.evidence 렌더 | App feeds evidence into EvidencePanel / empty case |
