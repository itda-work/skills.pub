# Changelog — itda-work/pdf-context-refinery

## [1.2.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [1.2.2] — 2026-07-26 (이슈 #1280)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280) — Cowork 전용 오해 제거.

## [1.2.1] — 2026-07-26 (이슈 #1274)

### Fixed

- Step 6 검증 명령의 미정의 변수 `${CLAUDE_SKILL_DIR}` 제거 — Prerequisites 에 `SKILL_DIR` 확정 스니펫(Code=`$CLAUDE_PLUGIN_ROOT` / Cowork=세션 마운트 find) 신설. `python` 호출을 `python3` 로 교정(python-runtime 규칙).

## [1.2.0] — 2026-05-22 (SPEC-PDF-REFINERY-REFS-001)

### New Features

- `references/` 도메인 아키텍처 신설 (Progressive Disclosure 패턴).
  `references/README.md` 매핑표 + `domain-tax-accounting.md` / `domain-electronics.md` / `domain-legal.md` / `domain-engineering.md` 4개 도메인 파일 (§1~7 구조, 각 ≤130줄).
- `verify_quality.py --domain {tax-accounting|electronics|legal|engineering}` 옵션 추가.
  도메인별 페이지 헤더 정규식 + 검증 항목(수식 패턴, 조문 패턴, 단위 패턴 등) 활성화.
- Step 1 Analyze에 도메인 감지 단계 추가: `references/README.md` 매핑표 기준 키워드 grep, 임계값 3, 결정론적 동률 처리.
- `check_domain_items()` 신규 함수: 도메인별 검증 항목 반환 (`domain=None` → 빈 리스트, backward compat 보장).

### Improvements

- SKILL.md 도메인 어휘 외부화: 세무·회계 특화 키워드(`조특법`, `법인령`, OCR 아티팩트 예시 등) → `domain-tax-accounting.md §6`으로 이전.
- SKILL.md 283줄 → 180줄 (NFR-1 ≤180 달성). 항상-로드 토큰 절감 ~4K.
- `verify_quality.py` 페이지 헤더 정규식 한국어 세무 가정 → `--domain` 옵션으로 도메인별 분리. 미지정 시 기존 동작 100% 유지(backward compat).
- `references/README.md` 도메인 감지 키워드에 영문 보강 (electronics: `inverter·grid·voltage·current·frequency·AC·DC·capacitor·resistor`, legal: `plaintiff·defendant·court·statute·case·judgment`, engineering: `stress·strain·load·thermodynamics·fluid·material·Chapter`) + grep `-iE` 대소문자 무시. NREL 영문 PDF (152p inverter 매뉴얼) 라이브 재검증 통과 — electronics 1569 매칭으로 임계값 3 압도 1위.

### Tests

- `tests/test_verify_quality_domain.py` 신설: 22 tests (도메인별 4종 × 패턴 테스트 + backward compat 4 + 단위 테스트 5).
- 52 passed / 0 failed / 0 skipped (기존 30 + 신규 22).

## [1.1.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [1.1.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.
