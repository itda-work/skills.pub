# Changelog — itda-g2b

## [0.10.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.2] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.10.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [Unreleased] — 키워드 검색 거짓 0건(silent under-collect) 수정

### Fixed
- **[치명] 키워드 검색 거짓 0건 수정.** 기존엔 `rows=10` 단일 페이지만 조회 후
  클라이언트 필터 → 키워드가 11번째 이후 공고에 있으면 `count:0`을 반환했다.
  나라장터는 하루 약 3,300건이 등록되므로 라이브에서 `구매`·`교육` 키워드가
  첫 10건엔 0건이나 전 범위엔 396·124건 존재함을 확인(거짓 0건 실증).
  `g2b_api.collect_all_bids()` 추가 — totalCount 소진 또는 `--max-pages`(기본 20,
  페이지당 999건) 상한까지 전 페이지를 순회·중복제거 후 누적, 그 위에서 키워드 필터.
- 페이지 경계 중복 제거: `(bidNtceNo, bidNtceOrd, refNtceNo, refNtceOrd)` 안정 키.
  같은 공고번호라도 차수가 다르면 별개 행으로 보존.

### Changed
- **출력 의미 구분.** `total_count`(API 필터 전 총계) vs `count`(필터 후) vs
  신규 `scanned_count`(실제 순회 건수) 분리. `truncated` 플래그 + `warnings` 추가 —
  `--max-pages` 상한 도달 시 "전체 N건 중 X건만 스캔, 미조회분 존재" 경고 출력.
- `--rows`/`--page` 명시 시 자동 순회를 끄고 단일 페이지만 조회(브라우즈 모드).
  미지정 시 키워드 검색은 전 페이지 자동 순회.
- 신규 옵션 `--max-pages`. SKILL.md 옵션표·argument-hint·`references/g2b.md` 동기화.
- SKILL.md "파일 구조" 환각 교정 — `env_loader.py`·`itda_path.py`는 g2b가 아니라
  `shared/`에서 주입, 존재하지 않던 `test_env_loader.py` 제거.

## [Unreleased] — SPEC-COWORK-ENV-GUIDE-001

### Changed
- Cowork에서 `claude config set` 안내 제거 — 에러 메시지 `.env` 단일 통일, 문서는 `.env` 1순위 + config set은 '로컬 CLI 전용' 펜스로만.

## [0.9.7] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.6] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.5] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.

## [0.9.4] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: 자동화 팁 섹션의 `py -3 scripts/collect_g2b.py ...` cron 예시를 "AI 키워드로 지난주 신규 입찰 공고 정리해줘"라는 자연어 반복 사용 예시로 대체. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 준수.
