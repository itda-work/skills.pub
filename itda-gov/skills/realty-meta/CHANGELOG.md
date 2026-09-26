# Changelog — itda-realty/realty-meta

## [0.9.4] — 2026-07-26 (이슈 #1284)

### Fixed

- 색인 정정 — court-auction 행 추가(5스킬 완결) + realty-price-stats 필요 키를 RONE_API_KEY 로 정정.

## [0.9.3] — 2026-07-26 (이슈 #1280·#1282)

### Changed

- compatibility 라벨 "Designed for Claude Cowork" → "Claude Code & Cowork. Python 3.10+".
- `.env` 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체하고 셸 환경변수·settings.json `env` 경로 병기.

## [0.9.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
