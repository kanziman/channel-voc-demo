# 공용 규약 — 스택 감지 & 경로/브랜치 컨벤션 (TDD 스킬 공통)

> 이 레포는 **Python 백엔드(`src/`, pytest)** 와 **TS 프론트(`web/`, vitest)** 가 한 저장소에 공존한다.
> TDD 스킬(tdd-loop / test-scenarios / tdd-red / tdd-green / tdd-refactor / security-review / create-pr)은
> 스택별로 스킬을 중복 생성하지 않고, **대상 경로로 툴체인을 자동 판별**하여 하나의 스킬로 양쪽을 처리한다.
> 각 스킬은 실행 시작 시 이 파일을 읽어 아래 규약을 적용한다.

---

## 1. 스택 감지 (모든 실행 0단계)

대상 task/파일의 경로가 `web/` 하위면 **[FE]**, 그 외(`src/`, `tests/`, 루트 설정파일)면 **[BE]** 로 간주한다.
tdd-loop이 넘긴 대상 파일 또는 이슈 본문의 대상 경로를 기준으로 판정하며, 판정 결과를 이후 모든 단계에서 고정한다.

| 항목 | **[BE] Python** | **[FE] `web/` (TypeScript)** |
| :-- | :-- | :-- |
| 단일 테스트 | `pytest tests/test_<mod>.py -q` | `cd web && npx vitest run <파일>` |
| 전체 테스트 | `pytest -q` | `cd web && npm test` |
| 테스트 파일 위치·명명 | `tests/test_<모듈명>.py` | 대상과 동일 폴더 `<name>.test.ts(x)` |
| 프레임워크 | pytest (FastAPI는 `httpx.AsyncClient`/`TestClient`) | Vitest + React Testing Library |
| 타입 검사 | `mypy src` | `cd web && npx tsc --noEmit` |
| 의존성 취약점 | `pip-audit` | `cd web && npm audit` |
| E2E | 없음 → **skip(pass)** | `cd web && npm run test:e2e` (Playwright) |
| 커버리지 | `pytest --cov` | `cd web && npx vitest run --coverage` |
| 시크릿 노출 grep 대상 | `os.getenv(...)` / `os.environ[...]` 하드코딩 | `import.meta.env.*` / `process.env.*` 하드코딩 |

**BE 선행 조건**: `pytest`·`pytest-asyncio`·`httpx`·`mypy`·`pip-audit`이 미설치면(현재 미설치) 먼저 dev 의존성으로 추가한다.
`pyproject.toml`의 `[dependency-groups]` dev(또는 `[project.optional-dependencies].dev`)에 넣고 `uv sync`. 이 설치가 끝나기 전에는 BE TDD 단계를 진행하지 않는다.

---

## 2. 문서 경로 컨벤션

- 원본 스킬의 `docs/features/{tag}/issue-{N}.md`는 이 레포에 존재하지 않는다.
- 대신 **`docs/dev/issue-<N>.md`** (flat) 를 시그니처·시나리오 영속화 파일로 사용한다. 폴더가 없으면 생성한다.
- 작업 대상은 `checklist.json`(→ `src/docs/PHASE3_PLAN.md`)의 task로도 식별된다. 이슈 본문에 대상 경로가 없으면 checklist의 해당 task `path`/`relatedPaths`를 대상 파일로 사용한다.

## 3. 브랜치 컨벤션

- 원본의 `feature/<spec>` 부모 / `feat/` 자식 규칙은 쓰지 않는다.
- **부모 브랜치** = tdd-loop 실행 시작 시점의 현재 브랜치(예: `phase3/design-tokens`).
- **자식 브랜치** = `<부모>-issue-<N>` (예: `phase3/design-tokens-issue-6`). 부모가 자식의 접두 디렉토리가 아니므로 D/F ref 충돌 없음.
- **PR base** = 그 부모 브랜치.

## 4. CLAUDE.md

- 이 레포에는 프로젝트 루트 `CLAUDE.md`가 없다. 컨벤션 소스는 `src/docs/PHASE3_PLAN.md`·`src/docs/PHASE2_PLAN.md`·기존 `src/graph/*` 코드 스타일을 사용한다.
- CLAUDE.md를 참조하는 단계는 "있으면 읽고, 없으면 위 문서/코드 관습을 따른다"로 처리한다.

## 5. 입력 인자 (`$ARGUMENTS`)

- 원칙: **GitHub 이슈 번호**. 이 레포는 GitHub 원격(`kanziman/channel-voc-demo`)과 이슈를 사용한다.
- 단, 열린 이슈 중 일부는 데모가 자동 발행한 VOC 내용 이슈(#6/#8/#10)로 **개발 task가 아니다**. tdd-loop에 넘기는 번호는 반드시 **개발 작업용 이슈**여야 한다.
- 개발 task가 아직 이슈로 없으면, checklist의 task를 이슈로 등록한 뒤(제목·본문·AC 포함) 그 번호로 실행한다. AC가 없는 이슈는 시나리오 도출 근거가 없으므로 진행 전에 AC를 채운다.

## 6. TDD가 성립하지 않는 task (순수 설정/의존성)

- `deps-fastapi`(pyproject에 의존성 추가), 순수 스캐폴딩(`web-scaffold`), 설정 파일(`vercel.json`) 등 **도출할 시그니처·단위 테스트가 없는 task**는 Red/Green 사이클을 강제하지 않는다.
- 이런 task는 tdd-loop 대신 일반 편집으로 처리하고, **검증은 "가져오기/기동 스모크"로 대체**한다. 예: `deps-fastapi` → `uv sync` 후 `python -c "import fastapi, uvicorn"` 성공. 이후 실제 코드 task(`serve-fastapi-migration`, `checkpoint-neo4j-impl`, 각 라우터)부터 TDD를 적용한다.
- tdd-loop이 이런 task를 대상으로 호출되면, 1~5단계(시나리오~리팩토링)를 스킵하고 스모크 검증 + 커밋(7단계) + PR(8단계)만 수행함을 사용자에게 알린 뒤 진행한다.
