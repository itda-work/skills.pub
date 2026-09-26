# Changelog — itda-gov/funding

## [1.0.0] — 2026-07-28 (이슈 #1320) — **BREAKING**

키워드 검색 스킬에서 **전수 수집 → 로컬 보존 → 변경 트래킹 → 원문 검증 → A/B/C 판정** 워크플로 스킬로 전면 전환.

### Removed (breaking)

- `collect_funding.py search` 서브커맨드 제거 — 키워드 검색 표면 폐기.
- `collect_funding.py overview` 서브커맨드 제거 — 연도별 통합공고 현황 조회 폐기(대체 기능 없음).
- `collect_funding.py`·`funding_api.py` 스크립트 삭제(후자는 `kstartup_api.py` 로 통합).
- SPEC-COLLECTOR-CLI-001(`collect_*.py` 동일 인자 규약) 적용 대상에서 제외 — 신규 표면은 조회기가
  아니라 수집·diff 파이프라인이다. 예외는 `itda-gov/README.md` 규약 절에 등재.

### Added

- `scripts/survey_crawl.py` — 5종 소스(K-Startup·기업마당·NIPA·KOCCA·SMTECH) 모집중 공고 전수 수집.
  `list`(목록) / `detail`(상세·첨부) 서브커맨드, jsonl + `run_manifest.json`(schema v1) 산출.
- `scripts/survey_diff.py` — 회차 비교. NEW·CHANGED·GONE·NEEDS_REHASH·UNCHANGED 분류,
  프로필 fingerprint 로 판정 승계 무효화, partial 회차의 GONE 오판 억제.
- **fail-closed exit 계약** — 0=전수 / 2=partial(네트워크·페이지 캡·파싱 실패·소스 일부 실패·
  api-window·첨부 불완전) / 3=차단(401/403·CAPTCHA, 우회 금지).
- **저장 경로 합의 게이트** — 사용자 확인 전에는 파일을 쓰지 않는다(SKILL.md 필수 절).
- **검증/보완 루프 옵트인** — 후보 상세 검증은 사용자 확인 후 실행.
- 첨부 robots 준수 다운로드 + **HWP/PDF → md 변환 스킬 조합**(`itda-work:hwpx-reader`·
  `itda-work:pdf-context-refinery`). 미설치 시 조용히 생략하지 않고 보고서 한계 고지에 명시.
- `requirements.txt`(`curl_cffi>=0.15`, 선택 — 미설치 시 urllib 경로 + stderr 1회 고지).
- `references/cli-contract.md`(스크립트 표면 정본)·`references/sources.md`(소스 레지스트리 + robots
  실측 표)·`references/third-party.md`(ir-search MIT 차용 고지)·`references/diff_record_schema.json`.

### Changed

- frontmatter: `argument-hint` 를 신규 표면으로 교체, `allowed-tools` 에 `Skill` 추가,
  description 을 전수조사·재조사 트리거로 재작성. `license: Apache-2.0` 유지(third-party MIT 병기).
- `KO_DATA_API_KEY` 는 **선택**이 되었다 — 없으면 K-Startup 이 공개 페이지 크롤 경로로 동작한다.
- `references/funding.md` 를 신규 파이프라인 기준으로 갱신(API 는 K-Startup 수집의 최적화 경로).

### 마이그레이션

| 0.9.x | 1.0.0 |
|---|---|
| "AI 지원사업 검색해줘" | "AI 쪽 지원사업 전수조사 해줘" — 전수 수집 후 A/B/C 분류 |
| `--active`(모집 중만) | 전수 수집이 기본적으로 모집중 공고만 대상 |
| "2026년 통합공고 현황" | 대체 없음 — K-Startup 사이트 직접 확인 안내 |

코드 차용: [ir-search](https://github.com/djfksjd/ir-search)(MIT) — 고지는 `references/third-party.md`.

## [0.9.11] — 2026-07-26 (이슈 #1284)

### Fixed

- 파일 구조 절 정정 — env_loader/itda_path 스킬 직속 광고를 shared 주입 사실로 교체, tests/ 실제 구조 반영.

## [0.9.10] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.9.9] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.9.8] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

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
