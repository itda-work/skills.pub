# Changelog — itda-work/ground-check

본 스킬의 변경 이력. [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.

## [0.11.1] — 2026-09-01 (이슈 #1621)

### Changed

- §Task 2 디스패치 절에 ground-verifier 최종 텍스트 = AUDIT_SCHEMA JSON 계약 명시(검증표 파일 릴레이 불변). verifier 가 `Skill` 없이 도는 읽기 전용 감사자가 되어 web-reader 폴백은 본 세션 몫으로 이관.

## [0.11.0] — 2026-07-26 (이슈 #1285)

### Added

- "부록: Claude Code 확장 (선택)" 절 신설 — code-extension-appendix 규약 파일럿. 본문(Cowork 기준) 불변.

## [0.10.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.4] — 2026-07-26 (이슈 #1280)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork (Claude Code SDK 매핑은 부록 참조)` 로 교체 (#1280).

## [0.10.3] — 2026-05-28

### Improvements

- 프로젝트 지침 재구성에 맞춰 삭제된 SPEC 링크를 제거하고 현재 코드·문서 기준을 명시.

## [0.10.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.10.1] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.10.0] — 2026-05-13

### New Features

- **Task 2-C Early Termination 절차 추가** (SKILL.md §Task 2-B 직후).
  - 라운드 1 결과가 3개 조건(FAIL 비율 20% 이하 + 보강 출처 URL 동봉 + 사실 오류가 아닌 누락 유형)을 모두 충족하면 라운드 2 spawn 없이 본 세션이 직접 WebFetch 재확인 후 종결.
  - 종결 불가 조건도 명시: 사실 불일치 / 비 1차 소스 보강 / FAIL 비율 초과 / hedge 발견.
  - 근거: M4 dogfooding (2026-05-13) 에서 라운드 1만으로 완결된 실제 사례.

### Improvements

- M4 dogfooding 결과를 산출 효율성 개선에 반영. SPEC "최대 3회"는 상한이지 의무가 아님을 본문에 명시.

## [0.9.1] — 2026-05-13

### Improvements

- M4 dogfooding 완료: "Claude Chat / Claude Code / Cowork 비교표" 시나리오 실사용 검증 (SPEC-GROUND-CHECK-001).
  - 1차 소스 9개 (claude.com 본문, claude.com/pricing, claude.com/download, code.claude.com/docs, support.claude.com 4개 도움말) 12셀 커버
  - 검증 라운드 1회로 종결 — 6셀 일치 + 1셀 부분 FAIL(CELL-1: ChromeOS·Linux 표기 누락) 보강 후 통과
  - hedge 표현 검증 통과: 산출물·검증 결과 어디에도 블랙리스트 표현 0건
  - AC 충족: 7/8 핵심 + 1 △ (AC-4 fallback trigger 미발생 — 모든 WebFetch 성공)

### 측정 가능한 효과

- 산출물 총 12셀 + 3개 단락 ("Cowork만 할 수 있는 것")
- 출처 URL 9개 모두 1차 소스 (블로그·뉴스 0건)
- 검증 라운드 토큰 소비: 약 105K tokens (Agent 1회 spawn, 12회 tool 사용)

## [0.9.0] — 2026-05-12

### New Features

- 스킬 최초 작성 (SPEC-GROUND-CHECK-001).
- Task 1/2/3 절차 정의: Ground Check (1-A) + 초안 (1-B) → 독립 검증 발화 (2-A) + 라운드 관리 (2-B) → 4줄 실사용 예시 (Task 3).
- WebFetch → web-reader fallback 체인: 4가지 실패 판정 기준 명시.
- Hedge 표현 블랙리스트: 한국어 12개 + 영어 9개.
- 1차 소스 도메인 판정 휴리스틱: 1차(`*.go.kr`·기업 공식·docs·표준·법령) vs 2차(뉴스·블로그·SNS·위키).
- 셀별 3-tuple 양식: 사실 한 줄 / 출처 URL / 확인 시각 (ISO-8601).
- 검증 라운드 최대 3회 + "미확인" 강등 규칙.
- 데이터 출처 카테고리 분리: Category A(Public Web, 본 스킬 범위) / B(Mounted file) / C(Connector) — B·C는 별도 SPEC 안내.
- Cowork 1차 타겟 + Claude Code SDK 매핑 부록.
- 템플릿 3종: `ground-check-cell.md`, `verification-table.md`, `example-extension.md`.
- 사용자 가이드 `GUIDE.md` — 비개발자 시나리오 5종 + FAQ + 한계 명시.
