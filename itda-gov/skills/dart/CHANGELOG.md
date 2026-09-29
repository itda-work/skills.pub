# Changelog — itda-dart

## [0.19.3] — 2026-09-29 (itda-work/skills#44)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다. 동작은 그대로다.

## [0.19.2] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.19.1] — 2026-09-27

### Changed

- `references/netbridge.md` 사본 동기화 — 설치 판정을 서버 이름 기준으로 — 도구 목록에 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치·업데이트 안내. 앞 문구는 Cowork 접두어만 조건으로 삼아 Claude Code 에 연결한 사용자에게도 재설치를 안내하게 했다(12.0.0 공개 전 리뷰 M1). 금지는 "다른 서버의 도구·내장 fetch" 로 한정.
- 옛 서버 이름 안내 제거 — compatibility 의 옛 이름 병기를 빼고 `references/netbridge.md` 사본을 정본과 동기화(옛 판 분기를 "itda-hyve 도구가 없으면 0.9.0 이상 설치·업데이트 안내" 한 갈래로).

## [0.19.0] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0). `allowed-tools`·본문 도구 지목·스크립트 안내문을 itda-hyve 로. `references/netbridge.md` 사본 동기화. compatibility 에 itda-hyve 0.9.0 이상, `save_dir` 거부 범위(홈 자체·`AppData`·`~/Library`)를 정본대로.
- `references/netbridge.md` 사본 동기화 — itda-hyve 받는 곳 한 줄.

## [0.18.0] — 2026-09-23 (이슈 #1707)

### Added

- **`info --input <company.json>`** — itda-butler 의 `http_request` 가 `save_as` 로 저장한 응답 파일을 네트워크 없이 가공한다(두꺼운 스킬의 `--input` 패턴 1호). `dart_api.parse_saved_json()` 이 `_request_json` 과 같은 status 판정(`000` 만 성공)을 쓰므로 오류 응답 파일은 `error: api` + `error_code` 로 표면화된다. `--corp-code` 는 `--input` 이 있으면 생략하고, 둘 다 없으면 `error: args`(exit 2).
- SKILL.md 에 그 명령의 butler 흐름(URL·`params` 의 `crtfc_key: {{secret:DART_API_KEY}}`·`legacy_tls: true`·`save_dir`(Cowork 연결 폴더 호스트 경로)·`save_as`·샌드박스에서 `$HOME/mnt/<폴더 이름>/<saved_path>` 로 읽기·`--input`)과 `allowed-tools` 전체 도구 이름. **나머지 명령의 butler 흐름은 후속 이슈**임을 명시.
- 회귀 테스트 5건(정상 JSON·table·status≠000·파일 부재·인자 부재) — `--input` 회차에 네트워크 함수가 불리면 실패한다.

## [0.17.4] — 2026-09-22 (이슈 #1707)

### Changed

- 네트워크가 막힌 환경의 itda-netbridge 경로 안내 1줄 + `references/netbridge.md` 동봉 (#1707). 전용 절차는 아직 없다(두꺼운 스킬 방침은 Cowork 파일 접근 확인 후 결정).

## [0.17.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.17.2] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- 의존성 설치 안내를 `uv pip install --system` 에서 `python3 -m pip install` 로 교체하고 uv 대안을 부연으로 분리 (#1281).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.17.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.17.0] — 2026-06-05

> k-dart(NomaDamas) 비교 검토(Agent Team: 다각분석 4 + 적대검토 2 + 종합 1)에서 적대검토 양측을 통과한 차용분만 반영. SPEC-DART-KDART-001.

### Added (k-dart 비교 차용 — SPEC-DART-KDART-001)

- **REQ-001/002 — `raw` 제네릭 서브커맨드 (escape-hatch)**: `collect_company.py raw --endpoint <이름> --param k=v ...`로 references에 명세만 있던 80여 개 doc-only 엔드포인트(배당 `alotMatter`·소송 `lwstLg`·전환사채 `cvbdIsDecsn`·증자 `irdsSttus` 등)를 직접 호출. `dart_api.request_raw`가 `_request_json`에 위임 → 재시도(1s,2s)·HTTP403 안내·status 분류 상속. **보안 경계**: endpoint는 `^[A-Za-z][A-Za-z0-9]*$`만 허용(경로/URL/쿼리 주입 차단), `crtfc_key` 자동 주입(사용자 params의 crtfc_key 무시). status `013`/`014`(데이터 없음)는 빈 결과로 반환. **JSON 출력 전용**(단위변환·CSV·source.url 미보장 — 가공은 전용 서브커맨드 finance/compare). `_request_json` 시그니처·동작 불변(엔진 blast radius 0, catch-in-wrapper 방식).
- **REQ-003 — SKILL.md "응답 규칙(모델 표현)" + Done when 섹션**: 모델이 받은 출력을 사용자에게 표현하는 규칙 — 요약 우선(서브커맨드별 우선 필드), 억/조 표기 시 원본 병기, 비정상 status 안내, `source.url` 동봉, **면책 푸터**(`※ 금융감독원 DART 공시 데이터 기준이며 투자 조언이 아닙니다`). "코드가 정본, 산문은 표현 레이어" — status/단위 변환은 코드가 처리하므로 산문 중복 금지. GUIDE.md엔 미반영(역할 분리).
- **REQ-004 — `list.json` corp_name gotcha**: `list.json`은 `corp_name`을 요청 파라미터로 받지 않음(응답에만 존재) → 회사명으로 좁히려면 `corp_code` 선확보. 우리 `references/공시정보/dart-공시검색-가이드.md` 요청표로 교차검증(환각 0).
- **REQ-005 — `references/dart.md` disambiguation 표 + `pblntf_ty` A~J**: 헷갈리는 12개 엔드포인트(유무상 `pifricDecsn`/유상 `piicDecsn`/무상 `fricDecsn`, 주요계정 `fnlttSinglAcnt`/전체 `fnlttSinglAcntAll` 등 — 전부 우리 references에 grep 실재 확인) + SKILL.md disclosure 섹션 `pblntf_ty` A~J 코드표. 전체 80행 인덱스는 작성 안 함(부피·drift 회피).

### Changed (SPEC-COWORK-ENV-GUIDE-001)
- **Cowork에서 `claude config set` 안내 제거** — 사용자 피드백: Cowork에선 `claude config set`이 적용되지 않아 헷갈림. 키 미설정 에러 메시지(`collect_company._SETUP_GUIDE`·`dart_api._DART_SETUP_GUIDE`)를 "작업 폴더 루트(outputs 등)에 `.env` 배치" 단일 안내로 통일(config set 문구 제거).
- **SKILL.md·GUIDE.md·references/dart.md "API 키 설정"** — `.env`를 모든 환경 공통 권장으로 1순위 배치. `claude config set`은 명시적 "로컬 CLI 전용" 펜스로만 잔존(Cowork 노출 0). 세션별 절대경로(`/sessions/<id>/...`) 고정 기입 금지 문구 추가.

### Documentation
- **`argument-hint`** — `raw`·`--endpoint`·`--param` 노출. **파일 구조** — 9개 커맨드로 갱신. **상세 API 가이드** — 미구현 엔드포인트를 `raw`로 호출하라는 안내 + disambiguation 포인터.
- **`description` 트리거 보강** (skill-creator 검수) — raw로 새로 가능해진 배당·소송·증자·전환사채 쿼리("네이버 배당 현황"·"셀트리온 소송 이력")를 description 예시·출력 목록에 추가해 언더트리거링 완화. (130→약 180자, 1024 한도 내.)

### Excluded (적대검토 REJECT/DEFER)
- corp_code 인라인 쉘 레시피 **REJECT**(find_corp_code의 defusedxml·ZIP폭탄 가드 우회 학습 위험). 인라인 curl로 스크립트 대체 **REJECT**(엔진 회귀). "corp_code 없으면 3개월 제한" **DEFER**(우리 reference 미검증). 에러코드표 3중복 dedup **DEFER**(차용 무관·컨텍스트 절감 아님 — references는 progressive-disclosure latent라 평상시 0토큰).

### Tests
- 신규: `TestRequestRaw`(위임·crtfc_key 주입·영숫자 검증·013 passthrough·단일레코드 passthrough·인증오류 재raise), `TestCmdRaw`(위임·`=` 보존·endpoint 거부·param 거부·비JSON 경고), arg-position 매트릭스 `raw` 추가. dart **297 passed** (270→297), 회귀 0, skip 0.
- 라이브 스모크: `raw --endpoint company`(삼성전자 status 000)·`alotMatter`(배당 15건 부활)·`lwstLg`(013 빈결과) 통과.

### Quality gate (itda-refine, 4-에이전트)
- **✅ PASS** (HIGH 0). spec-auditor(SPEC 정합·EXC 역검증 6건 honored)·live-prober(라이브 3콜, 013 passthrough·crtfc_key 주입 실인증)·deployed-runner(conftest-less PYTHONPATH=shared subprocess 11/11)·skip-skeptic(skip 0, 거짓 안전망 0). 게이트 MEDIUM 2건(arg-position raw 누락·SPEC status)은 본 릴리스에서 즉시 해소.

## [0.16.0] — 2026-05-29

### Added (사용자 2차 피드백 6항목 — SPEC-DART-FEEDBACK-002)

- **REQ-001 — `shared/itda_path._candidate_roots()` Cowork 절대 마운트 탐색 추가**: `$HOME` 비의존 후보 2종 추가. ① `CLAUDE_PROJECT_DIR`(설정 시) 및 그 상위 디렉토리, ② `/sessions/*/mnt/*` glob (`.`-prefix·outputs·uploads 제외). 기존 후보·우선순위·중복제거(resolve 기준) 동작 100% 보존.
- **REQ-003 — `filter_key_financials` CFS→OFS 자동 폴백 + 중복 제거**: CFS 결과가 비면 OFS로 폴백. 반환 시그니처 변경: `list` → `(list, fallback_bool)` 튜플. 폴백 시 `cmd_finance`/`cmd_compare`가 stderr로 `[참고] 연결재무제표 없음 — 개별재무제표(OFS) 기준` 안내. 동일 `(fs_div, account_nm)` 중복은 첫 건 유지(결정성 보장). `compare_financials`도 동일 폴백 적용.
- **REQ-004 — `get_financial_statements_all` 신설 + `finance --detail` 플래그**: `fnlttSinglAcntAll.json` 호출(176항목류, BS/IS/CIS/CF/SCE). `--detail` 미지정 시 기존 주요계정 동작 100% 보존(하위호환).
- **REQ-005 — rcept_no 출처 기본 노출**: `filter_key_financials`가 항목에 `rcept_no` 보존. `finance`·`compare` JSON 출력에 `source: {rcept_no, url}` 객체(`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=...`). table 출력에 출처 1줄. CSV는 기존 컬럼 보존(변경 없음).
- **REQ-006 — `compare --with-prior` opt-in**: `compare_financials`가 `frmtrm_amount`·`bfefrmtrm_amount` 보존. `--with-prior` 지정 시 출력에 전기 열/필드. `--with-prior --with-ratios` 병행 시 전기 대비 증감률(`매출액증감률`·`영업이익증감률`·`순이익증감률`) 추가. 미지정 시 기존 출력 100% 보존.

### Changed
- `compare_financials` 반환 구조 변경: `{corp_code: {acct: {...}}}` → `{corp_code: {"data": {...}, "fallback": bool, "rcept_no": str}}`. 이 변경에 맞춰 `cmd_compare`·관련 테스트 전면 업데이트.

### Documentation
- **SKILL.md "API 키 설정"** — Cowork에서 `claude config set env` 불가임을 명시. Cowork 권장 경로를 "워크스페이스 루트에 `.env` 배치"로 변경. 로컬 CLI는 config set/`.env` 둘 다 가능 유지.
- **SKILL.md compare 사용법** — 계정 매칭이 "검색어 라벨 + 부분 일치 fallback"임을 1줄 명시(`_match_account` 동작, 정규화 아님).
- **SKILL.md CLI 옵션 표** — `--detail`·`--with-prior` 신설 행 추가.
- **`argument-hint`** — `--detail`·`--with-prior` 노출.

### Tests
- 신규 28 케이스:
  - `TestCandidateRootsCowork` 6케이스 (shared/tests/test_itda_path.py)
  - `TestFilterKeyFinancials` 기존 3 → 8케이스 (폴백·dedup·rcept_no 보존 추가)
  - `TestCompareFinancials` 기존 5 → 10케이스 (fallback 전파·frmtrm 보존 추가)
  - `TestGetFinancialStatementsAll` 4케이스
  - `TestSourceMeta`·`TestFinanceJsonSourceOutput` 4케이스 (REQ-005)
  - `TestFsDivFallback` 2케이스 (REQ-003)
  - `TestWithPrior` 4케이스 (REQ-006)
  - `TestFinanceDetail` 3케이스 (REQ-004)
  - dart 278 passed (248→278), shared 57 passed (52→57), 합계 **378 passed**, 회귀 0, skip 0.

## [0.15.0] — 2026-05-29

### 🔴 BREAKING CHANGES
- `--report half` 제거 — `--report q2` 사용 (반기보고서). `half` 입력 시 친절한 deprecation 안내 메시지와 함께 즉시 argparse 에러로 종료. `dart_api.REPRT_CODES`에서 `'half'` 키 → `'q2'`로 변경 (코드 `11012` 동일).
- 사용자 마이그레이션: `--report half` → `--report q2` 한 곳 치환으로 끝.

### Added (사용자 피드백 7항목 일괄 반영 — SPEC-DART-FEEDBACK-001)
- **`--unit auto|million|eok|jo` 옵션 (compare)** — 금액 한글 단위 표기. `auto`(기본) = |값| ≥ 1조이면 `4조 3,923억 원`, ≥ 1억이면 `156억 원`, 미만이면 `5 백만원`. 외화는 unit 무시(기존 `M USD` 포맷 유지).
- **`--with-ratios` 옵션 (compare)** — 영업이익률·순이익률 행 자동 추가. 매출액 = 0/누락이면 `N/A`. table/csv/json 출력 모두 통합.
- **`--names`와 `--corp-codes` 병기 가능 (compare)** — 두 옵션의 `mutually_exclusive_group` 해제. 둘 다 지정 시 corp_codes 순서대로 처리하되 names를 헤더 표시명으로 사용 (예: `SKT (00159023)`). 추가 API 호출 0.
- **CSV `formatted_amount` 컬럼 신설 (compare)** — 단위 변환된 표기 + ratio 행(`영업이익률`·`순이익률`)도 같은 컬럼에 percentage 포함.
- **`~/.claude/settings.json` env 키 자동 탐색 (shared/env_loader.py)** — `claude config set env.X` 로 등록된 값이 Cowork 등 격리 subprocess에서 inject되지 않는 경우를 보조. 조회 우선순위: `cli_arg > os.environ > settings.json env > .env files`. 신설 `_load_claude_settings_env()` (graceful — 파일 부재/malformed JSON/env 키 부재 모두 `{}` 반환).
- **`DEFAULT_ACCOUNTS` 상수 (dart_api)** — `("매출액","영업이익","당기순이익","자산총계")` 순서 보존 tuple. `--accounts` 기본값으로 사용 + `--help` 텍스트에 명시.

### Documentation
- **SKILL.md "실행 경로 안내 (Cowork 환경)" 신설** — `Base directory` ≠ 실제 실행 경로 시나리오에 대한 3단계 탐색 가이드(`$CLAUDE_PROJECT_DIR` → `find /sessions -type d -name dart` → SKILL.md 그대로).
- **SKILL.md 파일 구조 false-confidence 해소** — 종전 `env_loader.py # API 키 관리` / `test_env_loader.py` 광고가 dart 직속 디렉토리에 실제로 존재하지 않던 문제를 정정. `shared/` 거주 명시.
- SKILL.md CLI 옵션 표 갱신 — `--report q2`, `--unit`, `--with-ratios`, `--accounts` 기본값(`매출액,영업이익,당기순이익,자산총계`) 명시.
- `argument-hint` frontmatter에 `--unit`, `--with-ratios` 노출.

### Tests
- 신규 30 케이스 (`TestFormatCompareAmount`·`TestComputeRatio`·`TestReportQ2Breaking`·`TestCompareNamesAndCodesTogether`·`TestCompareWithRatios`·`TestDefaultAccounts`·`TestCompareUnitOption`). itda-dart 248 passed (218→248), 회귀 0.
- `shared/tests/test_env_loader.py`에 11 신규 케이스 (`TestClaudeSettingsEnv`). shared 52 passed (41→52), 회귀 0.

## [0.14.0] — 2026-05-28

### Added
- `compare` 커맨드에 `--prefer annual|latest` 옵션 추가 (finance와 동형).
- `compare` 커맨드 `--year` 미지정 시 첫 corp_code 기준 `find_latest_report()`로 자동 폴백 + stderr `[자동 폴백]` 안내. finance와 동일한 UX로 옵션·동작 일관성 확보.

### Documentation
- SKILL.md CLI 옵션 표에 `--report annual|half|q1|q3` 행을 누락 보강. `finance`/`compare` 양쪽이 분기·반기 보고서를 모두 지원함을 명시.
- "분기 데이터가 필요할 때" 사용 예시 섹션 추가 (단일 기업 finance + 다기업 compare). 미공시 연도(예: 2026 사업보고서 미공시 시점)의 `--year` 생략 자동 폴백 패턴 안내.
- `argument-hint` 프론트매터에 `--report` 노출.

### Tests
- `TestCompareFallback` 5 케이스 추가 (218 passed, 회귀 0).

## [0.13.5] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.13.4] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.13.3] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.

## [0.13.2] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: `--format` 위치 안내에 노출된 `python3 scripts/collect_company.py --format table search ...` 등 CLI 예시 3건을 자연어 발화 예시("삼성전자 검색 결과 표로 보여줘", "삼성전자 2024년 재무 CSV로 정리해서 파일로 저장해줘")로 대체. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 준수.
