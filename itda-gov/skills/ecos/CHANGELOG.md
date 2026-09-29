# Changelog — itda-gov/ecos

## [0.10.11] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.10.10] — 2026-09-27

### Changed

- `references/netbridge.md` 사본 동기화 — 설치 판정을 서버 이름 기준으로 — 도구 목록에 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치·업데이트 안내. 앞 문구는 Cowork 접두어만 조건으로 삼아 Claude Code 에 연결한 사용자에게도 재설치를 안내하게 했다(12.0.0 공개 전 리뷰 M1). 금지는 "다른 서버의 도구·내장 fetch" 로 한정.
- 옛 서버 이름 안내 제거 — compatibility 의 옛 이름 병기를 빼고 `references/netbridge.md` 사본을 정본과 동기화(옛 판 분기를 "itda-hyve 도구가 없으면 0.9.0 이상 설치·업데이트 안내" 한 갈래로).

## [0.10.9] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- 네트워크 차단 환경 안내의 옛 이름 `itda-netbridge` → `itda-hyve`. `references/netbridge.md` 사본 동기화.
- `allowed-tools` 에 `mcp__remote-devices__itda-hyve__http_request` 를 넣고 본문에서 전체 이름으로 지목한다(규약 “두 곳에 적는다” — 기준 커밋 전부터 빠져 있던 것). compatibility 에 itda-hyve 0.9.0 이상.
- `references/netbridge.md` 사본 동기화 — itda-hyve 받는 곳 한 줄.

## [0.10.8] — 2026-09-22 (이슈 #1707)

### Changed

- 네트워크가 막힌 환경의 itda-netbridge 경로 안내 1줄 + `references/netbridge.md` 동봉 (#1707).

## [0.10.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.6] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.10.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [Unreleased] — 라이브 검증 기반 결함 수정 (2026-06-09)

### Fixed
- **dead 통계표코드 교체 (라이브 전수 검증).** 2020 기준년 개편으로 폐기된 구코드를
  현행 코드로 교체. 권위 출처(ECOS `StatisticTableList` API)와 라이브 응답 2출처 교차확인:
  - SKILL.md 분기 GDP 예시: `200Y001 --start 20201`(ERROR-101 + dead) → `200Y106 --start 2020Q1 --end 2024Q4`(1000건 반환, "경제활동별 GDP 및 GNI(원계열, 실질)").
  - SKILL.md items 예시: `021Y125`(0건, dead) → `901Y009`(소비자물가지수, 500건).
  - references/ecos.md 환율 예시: `731Y003 --period month --item1 0000001`(0건; 731Y003은 일간 주기, 0000001 미존재) → `731Y003 --period day --item1 0000003`(원/달러 종가, 라이브 반환).
  - references/ecos.md 통계표코드 표: dead `028Y001`(기준금리) → `722Y001`(한국은행 기준금리, 라이브 3.5% 반환), `0000001` USD 항목 → `0000003`(원/달러 종가).
- **한글 검색어 URL 미인코딩 크래시.** `word --word "GDP디플레이터"`·`"기준금리"`가
  `UnicodeEncodeError('ascii')`로 크래시하던 결함 수정 — `_build_url`이 각 PATH 세그먼트를
  percent-encoding 하도록 변경(라이브 재현·수정 후 각 1건 정상 반환).

### Removed
- **dead 상수 `KEY_STAT_CODES` 제거 (asset-deprecation).** 코드·테스트·문서 어디서도
  참조되지 않는 dead constant였고, 수록된 5개 코드 중 4개(021Y125·111Y017·028Y001·200Y001)는
  라이브 ECOS에서 INFO-200(데이터 없음)을 반환(StatisticTableList 교차확인). 회귀 가드 테스트 추가.

### Docs
- SKILL.md "파일 구조" 실제 트리 동기화: `env_loader.py`·`itda_path.py`는 `scripts/`가 아니라
  publish 시 `shared/`에서 주입됨을 명시. 테스트 파일명을 실제(`test_ecos_api.py`·
  `test_collect_econ_arg_position.py`)로 교정. `references/ecos-매뉴얼/` 추가.

## [Unreleased] — SPEC-COWORK-ENV-GUIDE-001

### Changed
- Cowork에서 `claude config set` 안내 제거 — 에러 메시지 `.env` 단일 통일, 문서는 `.env` 1순위 + config set은 '로컬 CLI 전용' 펜스로만.

## [0.10.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.10.3] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.10.2] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
