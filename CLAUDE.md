# CLAUDE.md

## Design System
Phase 3 프론트엔드(챗봇 코파일럿 + 3-탭 근거 콘솔) 작업 전 반드시 `DESIGN.md`를 읽는다.
- 색·타이포·간격·모션·radius 토큰의 정본은 `DESIGN.md`, 기계 소비용은 `tokens.css`.
- 컴포넌트는 `var(--token)`만 참조. 하드코딩 hex 금지.
- **그라데이션 금지**(§5-7). 유일 예외: evidence 그래프 RootCause 노드 `--glow-rootcause`.
- D/S/G arm 3색은 관통 시각 언어 — 다른 의미로 재사용 금지.
- 모든 수치(₩·ID·점수)는 mono.
- DESIGN.md와 어긋나는 코드는 QA에서 플래그. 변경은 사용자 승인 후에만.
