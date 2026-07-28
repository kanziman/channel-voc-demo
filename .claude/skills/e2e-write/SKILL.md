---
name: e2e-write
description: 이 스킬은 docs/features/{기능명}/prd.md의 사용자 스토리를 바탕으로 사용자 중심의 E2E 테스트 시나리오를 도출하고, Playwright 기반 E2E 테스트 코드를 작성합니다. 사용자가 "E2E 테스트 작성", "/e2e-write [기능명]", 또는 Playwright E2E 코드 생성을 요청할 때 반드시 활성화하십시오.
---

# E2E 테스트 자동 작성 스킬 (e2e-write)

이 스킬은 피처별 PRD(Product Requirement Document) 내의 사용자 스토리를 분석하여, 실제 사용자의 동작 흐름을 시뮬레이션하는 Playwright 기반 E2E(End-to-End) 테스트 코드를 작성하고 검증하는 가이드라인을 강제합니다.

## 사용법

- `/e2e-write [기능명]` (예: `/e2e-write import-api`)

## 입력 인자

- `$ARGUMENTS`: 기능 이름 또는 피처 디렉토리명 (예: `import-api`)

## 상세 실행 단계

이 스킬이 활성화되면 다음 단계를 순서대로 엄격히 수행합니다.

### 1단계: PRD 사용자 스토리 및 환경 분석

- **동작**: `docs/features/{$ARGUMENTS}/prd.md` 파일을 읽어서 "사용자 스토리" 및 "Out of Scope", "입출력 명세"를 파악합니다.
- **분석**:
  - 사용자가 앱 화면 또는 API를 통해 얻고자 하는 가치 흐름과 핵심 시나리오를 추출합니다.
  - 프로젝트 루트의 `playwright.config.ts` 설정과 `CLAUDE.md` 컨벤션을 확인하여 E2E 실행 환경에 부합하도록 준비합니다.

### 2단계: E2E vs 단위 테스트 범위 분리

- **중복 검증 방지**:
  - 단위 테스트(`*.test.ts`, `*verify.ts`)가 이미 정밀하게 점검하고 있는 세부 비즈니스 로직(예: 계산 공식, 예외 포맷, 파일의 구체적인 JSON 필드 데이터 등)은 E2E에서 다시 세부 단언(Assertion)으로 검증하지 않습니다.
  - E2E 테스트는 **"사용자 관점의 시나리오 성공/실패 여부"**에만 집중합니다. (예: 정상 데이터를 제출하면 성공 알럿/컴포넌트가 노출되는가?, 유효하지 않은 포맷을 넣으면 폼에 에러 안내가 표기되는가?)

### 3단계: E2E 테스트 코드 작성 (Playwright)

- **테스트 파일 명명 및 위치**:
  - 파일은 반드시 **`e2e/`** 디렉토리 하위에 위치시킵니다.
  - 파일 이름 컨벤션은 `{기능명 또는 페이지명}.spec.ts` 로 구성합니다. (예: `e2e/import-flow.spec.ts`)
- **Playwright Best Practices 적용**:
  - **사용자 중심 Locators 사용**: CSS 셀렉터(`.btn-submit`)나 XPath 대신 복원력 높은 Playwright 내장 로케이터를 최우선적으로 사용합니다.
    - `page.getByRole('button', { name: 'Submit' })`
    - `page.getByLabel('YouTube URL')`
    - `page.getByTestId('import-status')`
  - **웹 퍼스트 단언(Web-First Assertions)**: 자동 대기(Auto-waiting)가 적용된 `expect`를 활용합니다.
    - `await expect(page.getByText('Import started')).toBeVisible();`
  - **인위적 대기 지양**: `page.waitForTimeout(3000)`과 같은 하드코딩된 타임아웃 대기는 테스트 플래키니스(Flakiness)를 유발하므로 절대 사용하지 않습니다. 대신 화면 상태 변화나 로딩 엘리먼트 소멸을 기다리는 로직을 적용합니다.
  - **상태 격리 (Isolate State)**: 각 테스트 케이스가 다른 테스트의 결과에 영향을 받지 않도록 독립적으로 실행될 수 있게 구성합니다.

### 4단계: 테스트 로컬 검증 및 수정

- **동작**: `npm run test:e2e` 또는 특정 E2E 파일 대상의 playwright 테스트를 실행하여 작성한 테스트가 통과하는지 검사합니다.
- **예외 처리**: E2E 테스트 구동에 필요한 Next.js 개발 서버가 실행 중인지 확인하고, 테스트 동작 중 에러가 발생하면 로케이터나 대기 로직을 수정합니다.

### 5단계: 결과 보고

- 도출한 E2E 시나리오 목록과 새로 생성/수정된 Playwright 테스트 파일 경로를 개발자에게 정리하여 보고합니다.

## 제약 사항

- PRD 및 사용자 스토리에 없는 임의의 가상 기능을 E2E 시나리오에 추가하지 마십시오.
- `src/` 내 비즈니스 코드는 수정하지 않고, E2E 테스트 파일만 작성하는 것을 원칙으로 합니다.
