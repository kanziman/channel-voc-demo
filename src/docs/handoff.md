# HANDOFF — Channel VOC Intelligence Dept. (AX 해커톤 제출 전략)

> **목적**: 다음 세션/에이전트가 곧바로 구현에 착수할 수 있도록, 확정된 방향·문제정의·솔루션·데모·검증·다음 산출물을 한 문서에 고정한다.
> **상태**: 전략 확정, 구현 대기(사용자 지시). 아래 "6. 다음 산출물"부터 시작.

---

## 0. 한 줄 요약

**채널톡 대화를 읽고 → 스스로 분석 코드를 짜서 '고객의 진실(Customer Truth)'을 ₩로 정량화하고 → 실제 액션(GitHub PR / FAQ diff / CSM 브리핑)을 자동 배포하는 상시 AI 인사이트 부서.**
해자 = "코드를 짜고 도구를 실행하는" Codex 네이티브 실행력. 경쟁 CS AI("LLM이 답변만 생성")가 못 넘는 선.

---

## 1. 결정적 통찰 — 이건 GUI가 아니라 "에이전트가 호출하는 부서"다

- 심사 시나리오: **사람이 에이전트에게 "이 플러그인 테스트해봐"라고 시킨다.** 승부는 화면 클릭감이 아니라 **호출 1번의 결과물(output)** 에서 갈린다.
- 그 결과가 **사람에겐 시각적으로, AI에겐 구조적으로** 동시에 "와"여야 심사(사람+AI) 만장일치가 나온다.
- 5000개 대부분: 호출하면 텍스트를 프린트. 우리: 호출 1번에 **부서 하나의 하루 산출물**이 쏟아진다.

---

## 2. 문제 정의 (sharp) — 3개 → 관통하는 1개

기존 Idea 1·2·3(이탈/버그/churn)은 분산돼 무뎠다. 하나로 관통한다:

> **"채널톡엔 매일 수백~수천 건 대화가 쌓이지만, 전량을 읽고 '무엇을·왜·얼마나 급히 고쳐야 하는지'를 ₩로 정량화해 실제 액션으로 만드는 주체가 없다. 사람은 샘플만 읽고, 기존 AI는 응대만 하고 끝난다."**

가려운 곳 = **인사이트와 실행 사이의 간극.** 대시보드는 넘치는데, 스스로 실행되는 건 없다.

---

## 3. 솔루션 (깎아낸 형태) — "Insight that ships"

- **오늘 당장 쓰는 wedge**: `Daily Customer Truth` — 매일 아침 어제 대화 전량 분석 → **정량화된 액션 브리핑 + 자동 배포**. (당장 필요, 당장 사용 가능)
- **유니크**: 읽기전용 분석이 아니라 **실행까지 닫는 루프**. Codex만 가능(코드 작성 + MCP 도구 실행).
- **공통 척추**: `Listen → Understand → Quantify(코드 작성·실행) → Dispatch(액션 배포) → Report`

### AI 부서 조직도 (모듈 = 직원 롤)

```
              [Chief of Staff Agent]  ← 주간 경영 내러티브 + 라이브 대시보드
                        │
   ┌──────────┬─────────┴─────────┬──────────────┐
[Analyst]  [Researcher]      [Triage/QA]     [CSM/Growth Ops]
스스로 코드   대화 클러스터링    버그→GitHub      churn→CSM 브리핑/CRM
짜서 ₩정량화  ·테마·감정        Issue+PR         cart이탈→회복 플레이북/FAQ
   └──────────┴──────── 공통 척추: Listen→Understand→Quantify→Dispatch ────┘
```

- 기존 3개 아이디어는 폐기하지 않고 각각 **액션 팔**로 흡수:
  - Idea 1(이탈 회복) → **Growth Ops** 팔 (회복 플레이북 / FAQ)
  - Idea 2(CX→Dev) → **Triage·QA** 팔 (GitHub Issue+PR)
  - Idea 3(B2B churn) → **CSM Ops** 팔 (브리핑 / CRM)

---

## 4. 핵심 개선점 — Agent + Human 이중 인터페이스 (만장일치의 열쇠)

호출 1번이 **두 층위**를 동시에 반환하도록 설계한다.

| 층위 | 산출물 | 노리는 심사자 |
| :--- | :--- | :--- |
| **Human 층** | 자립형 HTML 대시보드 (Customer Truth Map · ₩ 임팩트 · 근거 인용 · Exec One-Pager) | 사람 심사 = 스크린샷각 비주얼 |
| **Agent 층** | 구조화 매니페스트 `{ briefing, dashboard_url, dispatched:[{type,url}], top_actions, metrics:{revenue_at_risk} }` | AI 심사 = 체이닝 가능한 실행력 |

> 이 이중 반환이 핵심. 사람은 대시보드를 보고 감탄하고, AI는 구조화된 실행 결과를 이어서 쓸 수 있어야 한다.

---

## 5. 승리 데모 스크립트 (30초 wow)

> **"채널톡 플러그인으로 어제 고객 대화 분석해줘"**
> 1. (5s) 에이전트가 대화 로드 + Analyst가 분석 코드 작성·실행
> 2. (15s) "체크아웃 오류 관련 47건 = 월 ₩12M 위험" 등 Top 이슈 ₩ 정량화
> 3. (자동) GitHub Issue + FAQ PR + CSM 브리핑 **실제 3건 생성**
> 4. 링크 하나 열면 → 인터랙티브 대시보드
>
> **"에이전트한테 시켰더니, 부서 하나가 하루치 일을 2분에 끝냈다."**

### 데모 화면 4장 (비주얼)
1. **Customer Truth Map** — 대화 클러스터 버블(크기=₩임팩트, 색=감정/긴급도), 클릭 시 대표 발화 인용.
2. **Agent Activity Feed** — AI가 직원처럼 일하는 실시간 로그.
3. **Insight→Artifact 플립카드** — 앞=문제, 뒤=자동 생성된 실제 PR diff / 브리핑 / FAQ diff.
4. **Exec One-Pager** — 컨설팅 톤 주간 요약 + Before/After 헬스 스코어.

---

## 6. 다음 산출물 (구현 착수 지점 — 우선순위)

> 사용자 신호 후 착수. `handoff.md`의 나머지 섹션이 스펙 역할.

1. **비주얼 데모 대시보드 (HTML Artifact)** — 화면 4장, 목업 데이터, 클릭 가능. `artifact-design` 스킬 기준으로 제작. *가장 먼저 만들면 "visually appealing" 증명됨.*
2. **SKILL.md 스켈레톤** — 부서 조직도의 각 에이전트 롤(Chief of Staff/Analyst/Researcher/Triage·QA/CSM·Growth Ops)을 Codex 스킬로 정의. 진입점 1개 + 이중 반환 매니페스트 스펙.
3. **플래그십 상세 보고서** — 문제정의·아키텍처·검증·해커톤 5문답을 단일 문서로 재작성(기존 `IDEA_1/2/3`는 "액션 팔" 부록으로 정리).

---

## 7. 검증 (부서 급, 순환논리 제거)

- **① 정량화 재현성**: Analyst가 짠 코드 결과가 재현되는가.
- **② 근거 추적(Audit trail)**: ₩ 수치·클러스터가 **어느 대화에서 나왔는지 클릭으로 역추적** 가능(신뢰 핵심).
- **③ held-out 일치도**: 사람 라벨 vs 클러스터/분류 일치도(Cohen's κ), 혼동행렬·macro-F1.
- **④ 액션 품질 블라인드 평가**: 생성된 PR/브리핑을 현직자 3명이 "추가질문 없이 착수 가능?" Yes/No.
- **안전장치**: 자동배포 전 **사람 승인 게이트**, confidence 임계값 미만은 검토 큐로.

---

## 8. 성장성 & 포지셔닝

- **Wedge → 플랫폼**: Daily Customer Truth → VOC/QA/PM리서치/CSM옵스 통합 → 채널톡 위 **Customer Intelligence 레이어**.
- **데이터 플라이휠**: 대화량↑ → 정량화 정확도↑ → 액션 신뢰↑.
- **차별화(vs 기존 채널톡 AI)**: 기존 AI = 고객 "응대". 본 솔루션 = 대화 데이터의 "분석→실행" 후공정. 겹치지 않고 보완적.

---

## 9. ⚠️ 구현 전 확인 필요 (데이터·연동 정직성)

- 채널톡 **Open API / Webhook** 실제 엔드포인트·이벤트명은 발표 전 최신 공식 문서로 대조.
- 인용 통계(장바구니 69.99% 외)는 원문·연도 확인 또는 "가정"으로 재라벨링. (상세: 각 `IDEA_*` 문서의 "6. 보완" 섹션)
- 데모 데이터는 **익명화 샘플만** 사용.

### 9.1 데이터 소스 확정 — 옵션 B (공개 실데이터 재구성)

2026-07-24 사용자 확정. **합성 데이터 금지(순환검증 함정).**

- **입력(대화)**: 공개 실 CS 대화 — Customer Support on Twitter(Kaggle, 실 브랜드↔고객 ~280만), Bitext Customer Support(intent 라벨)를 채널톡 포맷으로 재구성.
- **검증**: 위 데이터 held-out 슬라이스에 **사람 라벨** → 분류/클러스터 정확도(κ, macro-F1). 자가생성 아님.
- **실행(액션)**: GitHub Issue/PR·FAQ diff는 **우리가 통제하는 실제 테스트 리포지토리에 진짜로 실행** → "액션 절반은 100% 진짜"가 데모 결정타.
- (선택) 채널톡 테스트 워크스페이스 시드 시 API end-to-end 실증.

## 10. 런타임 — OpenAI/Codex vs Claude CLI

- **직접 OpenAI API 호출 코드 없음.** 플러그인은 모델 비종속 마크다운 스킬. 구동 모델 = 호스트 에이전트(Codex/Claude).
- **이미 dual-wired**: `.codex/hooks.json` + `.claude/settings.json` 둘 다 존재 → Claude CLI로 개발·실행 가능(OpenAI 키 불필요).
- 제출 포맷이 "Codex 플러그인"이므로 Codex CLI 심사 시 구동 모델은 OpenAI(포맷 요건이지 코드 의존 아님). 서버/MCP가 LLM을 *직접* 호출하게 되면 Anthropic Messages API로 교체 가능(그때 `claude-api` 스킬 참조).
- **미해결 확인사항**: 해커톤이 "반드시 Codex 플러그인으로 심사"를 요구하는지 → (A) Codex 유지·Claude로 개발 vs (B) Claude 1급 타깃. 요건 확인 후 SKILL 재작성에 반영.

## 11. 리뷰 루프 (매 스테이지 자가채점)

- `src/skills/review-ai-rubric` + `review-human-rubric`(각 100점)를 **매 스테이지/마일스톤마다 실행 → 점수·개선 → 메모리 기록**.
- 점수 이력·개선 레버는 **메모리 `review-scores.md`** 에서 관리. 목표: 두 루브릭 모두 90+ (심사 만장일치).
- **Stage 0 베이스라인**: AI 56 / 사람 71. 최대 감점 = 구현·정합성·검증 미비(README 5문답 미작성, channeltalk-solver SKILL이 플래그십과 불일치, MCP 명세 부재).
- (선택) git init 후 PostCommit 훅으로 자동화 가능 — 현재 레포는 비-git 상태라 스테이지=마일스톤으로 운용.

---

## 10. 결정 로그

- 2026-07-24: 후보 A/B/하이브리드 중 **Flagship A(VOC Intelligence Dept.)** 확정(사용자 명시 선택). B(Revenue Defense)·하이브리드 미채택 — 상세 근거는 `00_SOLUTIONS_OVERVIEW.md` 의사결정 매트릭스.
- 2026-07-24: 문제를 3개→관통 1개로 sharpen, 솔루션을 "Insight that ships"로 깎음, Agent+Human 이중 인터페이스를 핵심 개선점으로 확정.
