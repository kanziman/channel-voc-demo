---
name: mermaid-diagram
description: 프로젝트 구조를 분석하여 Mermaid 다이어그램 HTML을 생성하고 브라우저를 실행하여 시각화합니다. 사용자가 프로젝트 아키텍처 다이어그램 생성, 컴포넌트 간 의존성 시각화, 모듈 흐름도 작성, 혹은 브라우저로 구조를 확인하려 할 때 반드시 이 스킬을 활성화하세요.
---

# Mermaid Diagram Visualizer Skill

이 스킬은 프로젝트 내 소스 코드 간의 의존성 관계를 분석하고, Mermaid.js 다이어그램이 내장된 HTML 문서를 생성한 후 브라우저로 열어 사용자에게 시각적으로 아키텍처를 제공합니다.

## 사용 방법 (Workflow)

사용자가 아키텍처 시각화 또는 다이어그램 생성을 요청한 경우 아래 단계에 따라 작업을 수행하십시오:

1. **스크립트 실행**:
   이 스킬은 번들링된 Python 스크립트 `.claude/skills/mermaid-diagram/scripts/generate_and_open.py`를 활용해 자동으로 의존성을 탐색하고 Mermaid 코드가 포함된 HTML 문서를 작성한 뒤 브라우저를 띄웁니다.

   아래 터미널 명령을 프로젝트 루트 디렉토리에서 실행하십시오:

   ```bash
   python3 .claude/skills/mermaid-diagram/scripts/generate_and_open.py
   ```

2. **완료 보고**:
   스크립트가 정상적으로 종료되면, 다음 메시지를 정확히 출력하여 작업을 완료했음을 보고하십시오:
   `아키텍처 다이어그램이 브라우저에서 열렸습니다.`

## 주의 사항

- `src/`, `components/`, `app/`, `lib/` 디렉토리가 있는 경우, 스크립트가 해당 폴더 내의 `.ts`, `.tsx`, `.js`, `.jsx` 파일을 재귀적으로 스캔하여 컴포넌트 간의 import 관계를 기반으로 다이어그램을 빌드합니다.
- HTML 출력물은 `docs/architecture/index.html` 경로에 저장되며, 브라우저에서 로컬로 실행됩니다. 어두운 배경(#1a1a1a)에 산호색(#cc785c) 메인 포인트가 들어간 아름다운 UI 테마를 사용합니다.
