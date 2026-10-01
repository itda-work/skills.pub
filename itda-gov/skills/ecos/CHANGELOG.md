# Changelog — itda-gov/ecos

## [0.12.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.12.0] — 2026-09-30 (itda-work/skills#45)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `--input` 가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `collect_econ.py` 의 모든 명령(`key`·`search`·`items`·`tables`·`word`)이 API 를 부르지 않고, itda-hyve `http_request` 가 `save_as` 로 저장한 응답 JSON 을 `--input <파일…>` 으로 읽는다. 키는 itda-hyve GUI 시크릿 탭의 `ECOS_API_KEY` 를 URL 경로의 `{{secret:ECOS_API_KEY}}` 로만 가리킨다. `--api-key` 인자·`os.environ` 키 경로·키 주입 규칙·네트워크 코드(`urllib.request`)를 지웠다. 옛 인자 `--stat`·`--start`·`--end`·`--period`·`--item1`·`--item2`·`--word`·`--count` 는 요청 URL 의 경로 세그먼트로 옮겨 SKILL.md 에 적었다.
- **전량 대조** — 응답의 `list_total_count` 와 받은 행 수를 대조해 모자라면 `error: "incomplete"` 로 실패하고 더 받을 행 범위를 알려 준다(같은 범위를 두 번 넣어 넘쳐도 실패). 옛 `search` 는 1~1000행 한 번만 받았고, `items` 는 500행에서 잘렸다(901Y009 세부항목은 1,743행 — 2026-09-30 실측).
- **입력 판정** — 본문 절단(`truncated`)·HTTP 오류(`http`)·itda-hyve 실패 자리(`hyve`)·다른 서비스의 응답(`input`)을 명시 에러로 낸다. `search` 에서 값이 숫자가 아니라 빠진 행 수를 `skipped_non_numeric` 로 남긴다. `tables` 표 출력이 `CYCLE: null` 행(상위 분류)에서 죽던 것을 고쳤다.
- SKILL.md 를 "요청은 itda-hyve, 가공은 스크립트" 한 흐름으로 다시 썼다 — 서비스별 URL·저장 이름 규칙·쪽 이어받기·실패 코드 표. GUIDE.md 는 시크릿 탭 등록만 안내한다. Windows 콘솔 UTF-8 출력 재설정을 넣었다.
- **BREAKING — 출력 필드 변화**: `word` 출력에서 `query` 가 빠졌다(응답 본문에 질의어가 없다). `items`·`search` 의 `stat_code` 는 인자값이 아니라 **첫 행의 `STAT_CODE`** 이고, 데이터가 없으면(`INFO-200`) 빈 문자열이다. `search` 의 `period` 는 인자값이 아니라 **TIME 형식으로 추정**한 값(`year`·`semi`·`quarter`·`month`·`day`)이다. 모든 명령에 `total_count`·`sources`(파일별 `path`·`start_row`·`total_count`·`rows`)가 붙고, 경고가 있으면 `warnings` 가 붙는다.
- **BREAKING — 저장 이름의 `-r<시작행>` 이 계약이다**(W4 리뷰 M2, itda-work/skills#46). 응답 본문에 행 범위가 없어 이름으로 범위를 세운다 — 이름 끝이 `-r<시작행>.json` 이 아니면 `error: "input"`. `search` 저장 이름에 항목코드를 넣는다(`…-<항목1>[-<항목2>]-r<시작행>.json`, 항목만 바꿔 받을 때 이름이 겹쳐 `invalid_input` 이 나던 것 — m5).
- **전량 대조를 행 수 합에서 범위 대조로**(W4 리뷰 M2). 파일마다 `list_total_count` 가 다르면 다른 질의가 섞인 것이라 `error: "input"`, 같은 시작행 두 번·범위 겹침·행 중복도 `input` 이다(첫 쪽을 두 폴더에서 두 번 넘기면 `ok` 로 통과하던 것). 빈 범위는 1행부터 정확히 계산한다(둘째 쪽만 넘기면 `1~1000`) — `incomplete` 출력에 `missing_ranges`·`need_calls`·`confirm_first` 를 싣는다. 같은 범위를 두 번 넣어 넘치는 경우는 `incomplete` 가 아니라 `input` 이다.
- **호출 폭증을 받기 전에 확인** — 남은 호출이 5회를 넘으면(5,000행 초과) `confirm_first: true` 이고 SKILL.md 가 받기 전에 사용자에게 묻게 한다(m4). 여러 범위는 itda-hyve `batch`(GET)로 받는 예시를 넣고 `allowed-tools` 에 `batch` 를 더했다.
- `list_total_count` 가 없는 응답은 받은 행 수로 세되 `warnings` 에 "전량 기준선이 없다" 를 싣는다(m1 — 조용히 `ok` 이던 것).
- 문서: `timeout` 대응을 "50초를 넘기지 않고 1회만, 같은 이름 거부면 늦게 생긴 파일을 쓴다" 로, 종료 코드 표의 `truncated`·`http` 를 "응답 JSON 전체를 옮겨 적은 파일일 때" 로 좁혔다(`save_as` 원본이 HTML 오류 페이지면 `input`). `collect_econ.py` docstring 의 한글 저장 이름 예시를 순번으로 고쳤다.

## [0.11.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. 키는 두 경로로만 받는다 — Claude Code: 셸 환경변수 또는 `claude config set env.ECOS_API_KEY "키"`(스크립트가 `os.environ` 에서 읽음) / Cowork: itda-hyve 시크릿 탭의 `ECOS_API_KEY`(itda-hyve `http_request` 로 직접 부를 때 URL 경로의 `{{secret:ECOS_API_KEY}}` — 전용 절차가 없어 스크립트 가공 없는 원 응답). SKILL.md·GUIDE.md·references 의 키 설정 안내·키 주입 규칙·오류표를 두 경로로 고쳤다.

## [0.10.13] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.10.12] — 2026-09-29 (itda-work/skills#44)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다. 동작은 그대로다.

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
