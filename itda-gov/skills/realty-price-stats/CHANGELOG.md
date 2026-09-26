# Changelog — itda-realty/realty-price-stats

## [0.9.8] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.9.7] — 2026-07-26 (이슈 #1282)

### Changed

- `.env` 안내를 "Cowork에 연결한 작업 폴더" → "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체.
- 셸 환경변수·`~/.claude/settings.json` 의 `env` 로도 설정 가능함을 같은 문단에 명시.

## [0.9.6] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.9.5] — 2026-07-26 (이슈 #1275)

### Fixed

- 배포본 ImportError 해소 (#1275) — 모듈 최상단 `from deals_collector import ...` 가 배포 레이아웃에서 실패해 `deals_collector` 를 안 쓰는 `rone` 서브커맨드까지 전부 죽던 결함(실측). shared 승격으로 주입 대상 편입, 배포 레이아웃 실측 exit 0 확인.

## [0.9.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.3] — 2026-05-21

### Changed

- 환경변수 누락 시 친절한 에러 메시지(발급 가이드+URL+설정 방법) 출력 (SPEC-ENV-ERROR-001). RONE_API_KEY·KO_DATA_API_KEY 양쪽에 `_SETUP_GUIDE_RONE`/`_SETUP_GUIDE_KODATA` 분리 적용.

## [0.9.2] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
