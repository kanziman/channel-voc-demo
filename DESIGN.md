# Design System — VOC Copilot (Phase 3)

> Phase 3 프론트엔드(운영자 코파일럿 챗봇 + 3-탭 근거 콘솔)의 **소스 오브 트루스**.
> `src/docs/PHASE3_PLAN.md` §5-7 확정 사항의 실체. 컴포넌트 착수 전 이 문서와 `tokens.css`가 먼저다.
> 기계 소비용 토큰은 [`tokens.css`](tokens.css)에 있고, 이 문서는 **값 + 이유**를 담는다.

## Product Context
- **무엇:** VOC 지식그래프 위에 사는 내부 운영자용 GraphRAG 코파일럿. 채널톡 데스크 인라인 챗봇 + 확대 진입하는 3-탭 근거 콘솔.
- **누구:** CS/운영 담당자(비-개발자 포함). 하루 종일 보는 업무 툴.
- **공간:** 엔터프라이즈 내부 운영 콘솔. 대시보드보다 데이터 밀도가 높고, 채팅보다 근거가 많다.
- **타입:** data-dense internal tool (chat surface + console surface).

## 기억에 남길 한 가지
**"봇이 근거를 숨기지 않는다."** 답변 옆에 항상 검색 arm(Dense/Sparse/Graph)과 근거 서브그래프가 색으로 드러난다. 이 시스템의 시각 언어 전체가 **provenance를 색으로 추적 가능하게** 만드는 데 복무한다. 디자인이 예뻐 보이는 것보다, 어떤 근거로 이 답이 나왔는지 한눈에 보이는 것이 우선이다.

## Aesthetic Direction
- **방향:** Industrial / Utilitarian — 다크 운영 콘솔. 기능 우선, 데이터 밀도 높음, mono 강세.
- **장식 수준:** minimal. 타이포와 색이 일한다. **그라데이션·블롭·글로우 배경 전면 금지**(AI slop 회피, §5-7). 유일하게 허용되는 발광은 evidence 그래프의 RootCause 노드 `drop-shadow` 하나뿐(근거 강조 목적).
- **무드:** 진지한 업무 소프트웨어. 웜 뉴트럴(순수 회색이 아닌 살짝 따뜻한 검정)로 장시간 응시 피로를 낮추고, amber 액센트로 "행동/승인" 지점만 밝힌다.
- **계승:** 기존 정적 대시보드(`out/dashboard.html`)의 웜 팔레트(`--bg` 웜 블랙, severity 색)를 다크 콘솔 톤으로 확장.

---

## Color

원칙: **솔리드 토큰만.** 반투명(`rgba`)은 오버레이/포커스 링 등 상호작용 상태에만 쓰고, 표면 색으로는 쓰지 않는다.

### Elevation (표면 사다리 — 웜 블랙)
낮음→높음. 값이 밝아질수록 위로 떠 있는 표면.

| 토큰 | Hex | 용도 |
| :-- | :-- | :-- |
| `--bg` | `#0e0e0d` | 앱 베이스 |
| `--sunken` | `#121210` | 눌린 표면 (입력창 내부) |
| `--surface-1` | `#151513` | 헤더/데스크 바 |
| `--surface-2` | `#1a1a19` | 채팅 컬럼, 근거 패널, 카드 |
| `--surface-3` | `#201f1d` | 떠 있는 요소 (chips, 카드 내부 강조) |
| `--raised` | `#232320` | 봇 말풍선, 인용 블록 |

### Border
| 토큰 | Hex | 용도 |
| :-- | :-- | :-- |
| `--border` | `#2b2a27` | 기본 구분선 |
| `--border-2` | `#3d3b37` | 강조 테두리 (chips, 입력창, 액션 버튼 아웃라인) |

### Ink (텍스트)
| 토큰 | Hex | 용도 |
| :-- | :-- | :-- |
| `--ink` | `#f5f4ef` | 본문 (웜 오프화이트, 순백 아님) |
| `--muted` | `#8a897f` | 보조 텍스트 |
| `--dim` | `#5f5e57` | 라벨·placeholder·메타 |
| `--faint` | `#c9c8c0` | 그래프 노드 라벨(어두운 배경 위) |

### Accent — 코파일럿 / 시스템 (Amber)
답변 주체(봇), 근거 강조, **승인/행동 게이트**를 밝힌다. 계승색.
| 토큰 | Hex | 용도 |
| :-- | :-- | :-- |
| `--accent` | `#e8a13a` | 봇 아바타, 승인 카드 테두리, cite 강조, RootCause 노드 |
| `--accent-hi` | `#f0c674` | cite 링크 텍스트, 하이라이트 |
| `--accent-wash` | `#1c1710` | amber 톤 솔리드 배경 (그라데이션 워시 대체) |

### Brand — 운영자 / 발신 (Blue)
운영자 자신의 발화·전송 액션. amber(시스템)와 **역할로 분리**된다.
| 토큰 | Hex | 용도 |
| :-- | :-- | :-- |
| `--brand` | `#3b82f6` | 운영자 말풍선, send 버튼 |
| `--brand-ink` | `#eaf1ff` | 운영자 말풍선 텍스트 |

### Retrieval Arms — 핵심 시각 언어 (D / S / G)
검색 갈래를 색으로 고정. retrieval trace chip, 근거 태그, evidence 그래프 노드가 **모두 같은 색을 공유**해 한 색이 챗·패널·콘솔을 관통한다. 이 3색은 절대 다른 의미로 재사용하지 않는다.
| 토큰 | Hex | Arm | 별칭 노드 |
| :-- | :-- | :-- | :-- |
| `--arm-dense` | `#5b9bd5` | Dense (벡터 cos-sim) | Component 노드 |
| `--arm-sparse` | `#8e6fd8` | Sparse (BM25) | Conversation 노드 |
| `--arm-graph` | `#3fb56b` | Graph (1-hop) | (= `--good`) |

### Semantic (severity)
대시보드/README 계승. 다크 배경에 맞춰 `good`만 밝은 녹색으로 조정(라이트 대시보드는 `#0ca30c`).
| 토큰 | Hex | 의미 |
| :-- | :-- | :-- |
| `--good` | `#3fb56b` | 성공/회수 가능(₩) · `--arm-graph`와 동일 |
| `--warning` | `#fab219` | 경고 |
| `--serious` | `#ec835a` | 위험 손실(₩) · Symptom 노드 |
| `--critical` | `#d03b3b` | 치명 |

### Evidence 그래프 노드 색 (별칭 정리)
노드 색은 위 토큰을 **의도적으로 재사용**한다(새 색을 늘리지 않기 위해). 범례에 명시할 것:
- RootCause → `--accent` `#e8a13a`
- Component → `--arm-dense` `#5b9bd5`
- Symptom → `--serious` `#ec835a`
- Conversation → `--arm-sparse` `#8e6fd8`

---

## Typography

- **Sans:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Pretendard, Roboto, sans-serif`
  - Pretendard로 한글 커버(국문 VOC가 1급 콘텐츠). 시스템 폰트 스택으로 로딩 0 의존성.
- **Mono:** `"SF Mono", ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace`
  - **시그니처 규칙: 모든 수치는 mono.** 금액(₩), ID(conv#·rc_·thread_id), 점수(confidence·bm25·cos-sim·RRF k), arm 라벨(D/S/G). 데이터를 본문과 시각적으로 분리해 "이건 그래프에서 나온 실측값"이라는 신호를 준다.

### Scale (base 14px / line-height 1.55)
| 토큰 | px | 용도 |
| :-- | :-- | :-- |
| `--fs-label` | 10 | 대문자 mono 라벨(연관 질문·섹션 헤더), letter-spacing .06em |
| `--fs-meta` | 11 | 메타·태그·트레이스 |
| `--fs-sm` | 12.5 | chips, 근거 리스트, 보조 |
| `--fs-body` | 14 | 본문·말풍선·입력 |
| `--fs-lg` | 15 | 브랜드마크 |
| `--fs-title` | 17 | 콘솔 섹션 타이틀 |

- **Weight:** 500(보조) / 600(라벨·강조) / 650(버튼) / 700–800(수치·브랜드).
- **대문자 라벨:** `text-transform:uppercase; letter-spacing:.06em` — mono 라벨에만.

---

## Spacing
- **Base:** 4px. **밀도:** compact(운영 툴).
| 토큰 | px |
| :-- | :-- |
| `--sp-2xs` | 4 |
| `--sp-xs` | 8 |
| `--sp-sm` | 12 |
| `--sp-md` | 16 |
| `--sp-lg` | 22 |
| `--sp-xl` | 32 |
| `--sp-2xl` | 48 |

- 컬럼 패딩 22, 헤더 12×18, 말풍선 12×15, chips 7×13 등 기존 목업 값을 4의 배수로 정렬.
- **레이아웃 상수:** 앱 max-width `1240px`, 근거 패널 폭 `360px`, 반응형 breakpoint `860px`(이하 근거 패널 숨김).

## Layout
- **접근:** hybrid — 챗은 2단 그리드(`1fr 360px`), 콘솔은 3-컬럼 파이프라인.
- **그리드:** 챗 `chat | evidence`. 콘솔 탭2 `Dense | Sparse | Graph → RRF`.
- **최대 콘텐츠 폭:** 1240px, 좌우 border로 데스크 프레임.

## Radius
| 토큰 | px | 용도 |
| :-- | :-- | :-- |
| `--r-sm` | 6 | 태그·arm 칩·작은 배지 |
| `--r-md` | 9 | 입력창·버튼·근거 카드·아바타 |
| `--r-lg` | 12 | 승인 카드·컴포저 박스 |
| `--r-xl` | 14 | 말풍선·큰 카드 |
| `--r-pill` | 999 | chips·badge |
- **말풍선 꼬리:** 한쪽 모서리만 `4px`(운영자=우하단, 봇=좌하단).

## Motion
- **접근:** minimal-functional + 근거 등장 연출. 새 근거가 "쌓이는" 감각만 살리고 장식 애니메이션은 없다.
- **Easing:** enter `ease-out` · move `ease-in-out`.
| 토큰 | ms | 용도 |
| :-- | :-- | :-- |
| `--dur-micro` | 150 | hover·상태 전환 |
| `--dur-short` | 300 | arm 점등, 근거 카드 fade-in |
| `--dur-medium` | 400 | 서브그래프 노드 stagger |
| `--dur-long` | 500 | 엣지 stroke 드로잉 |
- **시퀀스:** retrieval trace(D→S→G 순차 점등, step ~240ms) → 엣지 드로잉(500) → 노드 fade-in(stagger 90ms) → 근거 리스트 stagger(130ms) → 답변 reveal. "검색→그래프→답변" 인과를 눈으로 보게 한다.
- `prefers-reduced-motion`: 모든 stagger/드로잉 제거, 즉시 표시.

---

## 그라데이션 → 솔리드 치환 매핑 (§5-7)
`out/phase3_mockup.html`의 7개 그라데이션을 컴포넌트 구현 시 아래로 대체. 챗봇 목업은 이미 0개.

| # | 위치 | 기존 | → 솔리드 |
| :-- | :-- | :-- | :-- |
| 1 | body 배경 amber glow | `radial-gradient(...amber)` | 제거 → `--bg` 단색 |
| 2 | body 배경 blue glow | `radial-gradient(...blue)` | 제거 → `--bg` 단색 |
| 3 | 헤더 페이드 | `linear-gradient(180deg,...)` | `--surface-1` + `border-bottom:1px solid --border` |
| 4 | `.card` | `linear-gradient(panel→panel2)` | `--surface-2` + `1px solid --border` |
| 5 | 그래프 영역 amber | `radial-gradient(...amber),#141412` | `--surface-2` 단색 |
| 6 | 파이프라인 컬럼 워시 | `linear-gradient(amber .08→transparent)` | `--accent-wash` 단색 + `border-left:2px solid --accent` |
| 7 | confidence 바 | `linear-gradient(90deg,accent→accent-hi)` | `--accent` 단색 fill |

---

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-28 | 초기 디자인 시스템 생성 | PHASE3_PLAN §5-7 확정. 두 목업 팔레트를 단일 정본으로 통합, 웜 다크 콘솔 계승 |
| 2026-07-28 | 그라데이션 전면 제거 | AI slop 회피. 7개 콘솔 그라데이션 솔리드 매핑표 확정 |
| 2026-07-28 | D/S/G arm 3색을 관통 시각 언어로 고정 | trace·근거 태그·그래프 노드가 색 공유 → provenance 추적성이 차별화 조건 |
| 2026-07-28 | 모든 수치 mono 규칙 | 그래프 실측값을 본문과 시각적 분리 |
| 2026-07-28 | accent(amber)=시스템/행동, brand(blue)=운영자 역할 분리 | 승인 게이트와 운영자 발화를 색으로 구분 |
