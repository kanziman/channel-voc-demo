---
name: test-scenarios
description: 이 스킬은 GitHub 이슈 번호를 입력받아 구현 전 단계에서 함수 및 컴포넌트의 시그니처를 확정하고 테스트 시나리오를 도출하는 워크플로우를 진행합니다. 사용자가 "/test-scenarios [이슈번호]"를 호출하거나 이슈에 따른 테스트 시나리오 및 시그니처 정의를 요청할 때 반드시 활성화하십시오.
---

# 테스트 시나리오 도출 스킬 (test-scenarios)

이 스킬은 개발 작업(TDD)을 시작하기 전, 이슈 번호를 바탕으로 함수/컴포넌트의 시그니처를 설계하고 정밀한 테스트 시나리오(정상/경계/예외)를 도출하여 문서화하는 가이드라인을 강제합니다.

> **선행**: [`.claude/skills/_shared/stack-and-conventions.md`](../_shared/stack-and-conventions.md)를 먼저 읽는다. 대상 경로로 [BE]Python/[FE]web 스택을 판별하고, 문서는 `docs/dev/issue-<N>.md`에 영속화한다.

## 사용법

- `/test-scenarios [GitHub 이슈 번호]` (예: `/test-scenarios 1`)

## 입력 인자

- `$ARGUMENTS`: GitHub 이슈 번호 (예: `1`)

## 상세 실행 단계

이 스킬이 활성화되면 다음 7단계를 순서대로 엄격히 수행하며, 각 승인 단계에서는 개발자의 명시적인 컨펌을 받기 전까지 절대 다음 단계로 진행하지 않습니다.

### 1단계: 정보 분석 및 시그니처 확정

- **동작**: 입력받은 이슈 번호(`$ARGUMENTS`)에 해당하는 GitHub 이슈 본문을 `gh issue view $ARGUMENTS` 명령어를 실행하여 가져옵니다.
- **분석 대상**:
  - 가져온 이슈 본문 (+ 대응하는 `checklist.json` task의 `path`/`relatedPaths`/`description`)
  - 사양 문서: `src/docs/PHASE3_PLAN.md` (해당 task 관련 절)
  - 기존 코드베이스 패턴 — [BE]: `src/graph/*.py`(`retriever.py`, `agent.py`, `serve.py` 등)의 함수 시그니처·타입힌트 스타일 / [FE]: `web/src/**`의 컴포넌트 Props·API 클라이언트 패턴
- **설계 내용**:
  - **함수 시그니처**: 이름, 파라미터 타입, 반환 타입 정의
  - **에러 케이스**: 어떤 상황에서 예외(error)를 발생시키거나 실패 결과를 반환하는지 정의
  - **컴포넌트 Props 타입**: UI 컴포넌트 관련 작업인 경우 Props 인터페이스 정의
- **주의사항**:
  - **구현 코드는 절대 작성하지 않습니다.** 시그니처와 명세만 정의합니다.
  - 기존 코드베이스의 설계 관습과 스타일([BE] 함수형 모듈·타입힌트·dataclass / [FE] Context API·API 클라이언트 패턴 등)을 일관성 있게 준수합니다.

### 2단계: 시그니처 개발자 검토 및 승인

- 설계한 시그니처 명세(함수 정의, 에러 조건, Props)를 깔끔한 Markdown 형식으로 개발자에게 제시합니다.
- 개발자가 검토하고 승인(컨펌)할 때까지 **대기**합니다.

### 3단계: 시그니처 문서화

- 개발자 승인을 받으면, `docs/dev/` 디렉토리(없으면 생성) 아래에 `issue-{N}.md` 파일을 생성(또는 수정)합니다. (여기서 `{N}`은 `$ARGUMENTS`로 전달받은 이슈 번호입니다)
- 승인된 시그니처 상세 내용을 `docs/dev/issue-{N}.md` 파일의 **상단**에 기록합니다.

### 4단계: 테스트 시나리오 도출

- 확정된 시그니처와 이슈 내용을 바탕으로 테스트 케이스(시나리오) 목록을 구상합니다.
- **구조화 및 분류**: 시나리오를 **[정상]**, **[경계]**, **[예외]** 세 가지 카테고리로 엄격히 분류합니다.
- **작성 포맷**: 다음 규칙을 준수하여 작성해야 합니다.
  - `[정상/경계/예외] 함수명/컴포넌트명 — should [기대동작] when [조건]`
  - 예: `[정상] runImportPipeline — should transit state to completed when all steps succeed`
  - 예: `[예외] runImportPipeline — should throw error and mark status as failed when downloadStep throws exception`
- **주의사항**: 실제 테스트 코드는 작성하지 않고, 오직 시나리오 문장만 도출합니다.

### 5단계: 시나리오 문서화

- 도출된 정상/경계/예외 테스트 시나리오 목록을 `docs/dev/issue-{N}.md` 파일의 **하단**에 추가하여 영속화합니다.

### 6단계: GitHub Issue AC(Acceptance Criteria) 교차 대조

- `gh issue view $ARGUMENTS`를 통해 읽어온 이슈의 **Acceptance Criteria (AC)** 항목들을 도출된 테스트 시나리오 목록과 1:1로 비교 검증합니다.
- **비교 분석 규칙**:
  - 모든 AC 항목이 최소 1개 이상의 구체적인 테스트 시나리오에 의해 커버되고 있는지 대조합니다.
  - AC 항목 중 대응하는 테스트 시나리오가 없는 경우, 적절한 시나리오를 설계하여 목록에 추가합니다.
  - 추가된 시나리오 역시 `docs/dev/issue-{N}.md` 파일 하단에 업데이트합니다.

### 7단계: 최종 시나리오 승인 및 대기

- AC와 대조를 마친 최종 테스트 시나리오 목록을 개발자에게 보여줍니다.
- 개발자가 시나리오 목록 전체를 검토하고 **최종 승인(컨펌)**을 내릴 때까지 작업을 멈추고 대기합니다.
