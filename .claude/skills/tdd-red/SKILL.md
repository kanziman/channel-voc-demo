---
name: tdd-red
description: 이 스킬은 이슈 번호를 입력받아 승인된 테스트 시나리오를 바탕으로 실패하는(TDD Red) 테스트 코드를 작성하고 실행하는 과정을 진행합니다. 사용자가 "/tdd-red [이슈번호]"를 입력하거나, 실패하는 테스트 코드 작성, TDD Red 단계 실행, Vitest 테스트 추가 등을 요구할 때 반드시 활성화하십시오.
---

# TDD Red 테스트 코드 작성 스킬 (tdd-red)

이 스킬은 확정된 명세와 테스트 시나리오를 바탕으로, 실제 비즈니스 로직을 구현하기 전에 **실패하는 테스트 코드(Red)**를 안전하게 작성하고 실행하여 TDD(Test Driven Development) 개발의 시작 단계를 보장하는 가이드라인을 강제합니다.

## 사용법

- `/tdd-red [GitHub 이슈 번호]` (예: `/tdd-red 1`)

## 입력 인자

- `$ARGUMENTS`: GitHub 이슈 번호 (예: `1`)

## 상세 실행 단계

이 스킬이 활성화되면 다음 단계를 순서대로 엄격히 수행합니다.

> **선행**: [`.claude/skills/_shared/stack-and-conventions.md`](../_shared/stack-and-conventions.md)를 먼저 읽어 스택([BE]/[FE])과 테스트 러너·파일 명명을 확정한다.

### 1단계: 시나리오 및 시그니처 읽기

- **동작**: `docs/dev/issue-{번호}.md` 파일에서 해당 이슈(`$ARGUMENTS`)의 확정된 함수/컴포넌트 시그니처와 정상/경계/예외 테스트 시나리오 목록을 읽어옵니다. (여기서 `{번호}`는 `$ARGUMENTS` 값입니다)
- **분석**: 작성해야 하는 테스트 대상 파일의 정확한 위치와 대상 함수/컴포넌트를 명확히 식별하고, 그 경로로 스택을 판정합니다(`web/`=FE, 그 외=BE).

### 2단계: 실패하는 테스트 코드 작성 및 순차 실행

- **환경 (스택별)**:
  - **[BE] Python**: `pytest`(+ FastAPI는 `httpx.AsyncClient`/`TestClient`, 비동기는 `pytest-asyncio`).
  - **[FE] web/**: `Vitest` + `React Testing Library`.
- **테스트 파일 명명 및 위치 컨벤션**:
  - **[BE]**: `tests/test_{모듈명}.py`. (예: `src/server/routers/chat.py` → `tests/test_router_chat.py`, `src/graph/checkpoint_neo4j.py` → `tests/test_checkpoint_neo4j.py`)
  - **[FE]**: 테스트 대상과 **동일 디렉토리**, `{대상파일명}.test.ts(x)`. (예: `web/src/components/ChatStream.tsx` → `web/src/components/ChatStream.test.tsx`)
- **구조화**:
  - **[BE]**: 대상 함수/클래스 단위로 `class TestXxx:` 또는 함수 그룹으로 묶고, 테스트 함수명은 `test_should_<기대>_when_<조건>` 형식을 준수합니다.
  - **[FE]**: `describe` 블록으로 그룹화하고, `it`/`test` 이름은 **`should [기대 동작] when [조건]`** 형식을 준수합니다.
- **TDD Red 구현 순서**:
  - **제약 사항: 구현 코드([BE]`src/`, [FE]`web/src/`의 비즈니스 코드)는 절대 생성/수정하지 않습니다.** (구현이 비어있거나 시그니처 선언만 존재하는 상태여야 합니다)
  - 도출된 시나리오를 **한 번에 하나씩** 테스트 코드로 작성합니다.
  - 하나의 테스트를 작성할 때마다 즉시 실행([BE]`pytest tests/test_<mod>.py -q` / [FE]`cd web && npx vitest run <파일>`)하여 **실패(Red)하는 것을 명확히 확인**합니다.
  - 해당 테스트의 실패를 확인한 후에만 다음 시나리오의 테스트 코드를 작성하며 순차적으로 나아갑니다.

### 3단계: 전체 테스트 실행 및 검사

- 모든 시나리오에 대한 테스트 케이스 작성이 끝나면, 전체 테스트([BE]`pytest -q` / [FE]`cd web && npm test`)를 실행합니다.
- 작성된 모든 테스트가 예외 없이 **실패(Red)** 상태를 유지하고 있는지 최종적으로 확인합니다. (단, import 대상 모듈 부재로 인한 **collection error**는 Red로 간주하지 않고, 시그니처만 담은 스텁 생성이 필요한 신호로 tdd-green에 인계합니다.)
- 전체 테스트 실패 결과를 로그와 함께 개발자에게 요약하여 공유하고 단계를 마무리합니다.
