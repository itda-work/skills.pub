# Changelog — itda-gov/funding

## [3.0.0] — 2026-09-30 (itda-work/skills#45·#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 공공 사이트 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 계획과 판정만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `survey_crawl.py` 는 사이트를 직접 부르지 않는다. 하위 명령이 바뀌었다:
  - `list <source> -o … [--max-pages] [--min-expected] [--smoke]` → `plan list <source…> --run-dir R --save-dir S` · itda-hyve `batch`(`plan_file`) · `collect list --run-dir R --next-plan`(모자라면 다음 계획, 다 모이면 `survey.jsonl`·`run_manifest.json`).
  - `detail <source> <url…> -o … --download-dir … --merge-into …` → `plan detail <source>:<id>|<url>|<공고번호>… --run-dir R` · batch · `collect detail --run-dir R --next-plan`(상세를 읽어 첨부를 계획) · batch · `collect detail` 다시.
  - 산출은 회차 폴더에 고정: `survey.jsonl`·`run_manifest.json`·`details/<source>-<id>.txt`·`raw/`(itda-hyve 가 받은 원본 — 저장 이름이 식별 계약). 결과·오류는 stdout JSON(옛판은 stderr 로그).
- **BREAKING — 종료코드 1 추가** — `incomplete`(더 받을 것이 있다)와 인자·입력 오류는 exit 1. 0 전수·2 partial·3 차단은 그대로다.
- **BREAKING — K-Startup 공공데이터 API 경로 삭제**(사용자 결정 D1) — `KO_DATA_API_KEY` 를 쓰지 않는다. 필터 없는 API 는 모집중을 모으려고 40~60쪽을 훑었고, 크롤은 12쪽으로 전수를 증명한다. 스킬에 시크릿이 없다.
- **BREAKING — 전량 대조를 분모 기반으로** — `--max-pages` 기본 40(bizinfo 105쪽·smtech 251쪽이라 `list all` 이 늘 exit 2 였다)과 `--min-expected` 를 없앴다 — 그 하한("K-Startup 50건 미만이면 실패")은 **1쪽 0건이면 네 소스 모두 partial(exit 2, `stop_reason: empty`)** 과 **분모 대조**가 대신한다: 1쪽이 알려 준 마지막 쪽·행 번호로 남은 쪽을 계획하고, bizinfo·nipa 는 행 번호 1..총건수가 빠짐없이 한 번씩(번호를 못 읽은 행이 있으면 그 쪽은 대조 불가로 다시 받고 그래도면 partial), kstartup 은 고유 id = 15×(마지막−1)+끝 쪽 행 수, smtech 는 마지막 쪽이 아니면 정확히 15행으로 대조한다. 2회전에는 1쪽을 나머지 쪽과 같은 회전의 **맨 앞과 맨 끝**에 다시 받는다(kstartup·bizinfo·nipa — 1회전과 2회전 사이에 공고가 내려가면 중복도 모자란 쪽도 생기지 않아 한 건이 빠질 수 있었고, 한 회전 안에서 맨 위 추가와 경계 부근 제거가 겹치면 행 번호가 빈틈없이 맞아 한 건이 빠진다 — 앞뒤 1쪽이 다르면 잡는다). 이상한 쪽은 그 쪽만 다시 받고(나쁜 판 3개까지, kstartup 은 2회전 뒤면 전 쪽), 받는 사이 목록이 바뀐 흔적이 보이면 **받은 쪽 전부를 한 회전에** 다시 받는다(두 번까지 — 쪽을 골라 받으면 bizinfo 가 12~52회전을 돌았다). 그래도 어긋나면 partial. 소스마다 계획 회전 상한(필요한 회전 + 6)에 닿으면 그때까지 받은 것으로 partial(`round-cap`). 쪽 상한(150, smtech 30)을 넘으면 받기 전에 `will_truncate`. 같은 저장 이름을 세 번 **시도**했는데(그 계획이 마지막으로 담은 이름 중 파일이 온 것이 있는데) 파일이 없으면 "받지 못함"(`hyve:missing`)으로 확정한다 — 아무것도 남기지 않은 계획은 부르지 않은 것으로 본다. 2회전의 1쪽 다시 받기만 실패하면 1회전 1쪽으로 분모를 잡아 받은 쪽과 함께 partial. 쓰인 쪽들이 여러 회전에 걸치거나 괄호의 한쪽만 왔으면 그 사이의 1쪽 판들을 대조한다(끝 확인이 없으면 1쪽 한 호출을 더 받는다). 재동기화 회전은 호출 id 의 `resync-` 표식으로 센다. `collect … ` 를 `--next-plan` 없이 부르면 미리보기(`preview_only`)다. 1쪽을 못 받거나 못 읽으면 `coverage: none`. `stop_reason` 이 `last-page`·`closed-streak`·`page-cap`·`round-cap`·`empty`·`smoke`·`robots-disallowed`·`parse-failure`·`fetch-failure`·`blocked` 로 바뀌었다.
- **BREAKING — SMTECH 식별자 `ancmId-dtlAncmSn`** — `ancmId` 하나로는 세부 공고가 겹쳐 하나가 버려지고 있었다(2026-09-30 1쪽에 S02847·S02871 각 2행). `survey_diff` 는 2.x 회차의 SMTECH 레코드를 url 로 새 식별자에 맞춘다. `field` 는 시스템 구분(`SMTECH`) 대신 사업명이다.
- **BREAKING — SMTECH 는 모집중 0 인 쪽이 3개 이어지면 멈춘다**(사용자 결정 D3) — `stop_reason: closed-streak`·`coverage: window`, `survey_diff` 는 window 회차에서 GONE 을 단정하지 않는다. NIPA·SMTECH(이력 목록)의 마감 행은 싣지 않고 `counted.closed_rows` 로 센다. 받은 구간에서 SMTECH 마감일 내림차순(멈춤 규칙의 전제)이 깨지면 경고한다.
- **BREAKING — KOCCA 목록 수집 중단**(사용자 결정 D2) — robots.txt `Disallow:/kocca/*/list.do` 가 목록 경로와 맞는다(2.x 는 목록 크롤에 robots 를 검사하지 않았다). manifest 에 `inactive`·`robots-disallowed` 로 남고, 상세 URL 은 `plan detail` 로 받는다.
- **BREAKING — 리다이렉트를 따라가지 않는다** — 호출은 `follow_redirects:false`. 정상 흐름(목록·상세·첨부 36회 실측)에서 리다이렉트 0회였고, 3xx 본문은 "그 쪽·그 공고가 아님"으로 판정해 다시 받거나 실패로 남긴다. 홉별 검사 코드를 지웠다. **첨부 `download_status` 의 `blocked_redirect` 값은 더 나오지 않는다**(`diff_record_schema.json` 에는 2.x 회차의 GONE 레코드가 그 값을 실을 수 있어 남겼다). 새 값 `unverified_format` 이 생겼다.
- **BREAKING — 차단(exit 3)은 본문으로만 판정** — 저장 파일에는 상태 코드가 없다. 401/403 이 평범한 오류 페이지면 exit 2 로 떨어진다(이전에는 3).
- **BREAKING — 상세 결과 판정** — 상세 페이지는 소스별 본문 컨테이너가 있어야 한다(없는 공고번호의 셸·3xx 본문·오류 화면은 한 번 다시 받고 `fail`). 목록 레코드 없이 지목해 본문이 그 공고인지 대조하지 못한 대상(K-Startup·NIPA URL·공고번호)은 `ok` 가 아니라 `partial`(exit 2). 상세 대상은 호스트·robots 에 더해 소스별 상세 화면 경로(`/web/contents/bizpbanc-ongoing.do`·`/sii/siia/selectSIIA200Detail.do`·`/home/2-2/<번호>`·`/front/ifg/no/notice02_detail.do`·`/kocca/pims/view.do`)만 계획한다. K-Startup robots 상수는 원문 전사(33줄)다 — 옛 상수는 첨부 게이트용 부분집합이라 `/bizpbanc-ongoing.do`·`/web*.do` 등을 상세 대상으로 통과시켰다.
- **BREAKING — `dropped` 는 결손만** — 링크·구조를 못 읽은 행(`no_link`·`parse_skip`)이 있으면 그 소스는 partial 이다. 정상 계수(`closed_rows`·`iris_rows`)는 `counted` 로 옮겼다.
- 첨부는 **바이트로 검사**한다 — 빈 파일·50MiB(itda-hyve 상한)·HTML 시작·확장자↔매직 바이트·잘림(PDF `%%EOF`·ZIP 끝·OLE 는 머리의 섹터 크기·FAT 위치를 읽어 FAT 가 쓰는 마지막 섹터까지 파일에 있는지·JPEG/PNG/GIF 끝 표지). 검사 규칙이 없는 확장자는 `unverified_format`(v3 을 찍지 않는다). hash v2/v3·`attachments_complete` 계약은 그대로다. 첨부 이름은 상세 페이지에서 읽는다(bizinfo 는 링크 title — 옛판은 `fileDown.do` 로 적었다). `attachments[]` 에 `local_path`(`raw/att/…`)·`size` 가 붙는다.
- 쿼리 순서를 사이트 링크 그대로(bizinfo `schEndAt, rows, cpage`) — `request-profile-first`.
- `run_manifest.json` run 에 `coverage`·`last_page`·`counted`·`dropped`, `inactive` 는 exit 0.

### Added

- `plan_io.py`(batch 계획 파일 — 40개·같은 사이트 20개씩), `listing.py`(목록 판독·분모 대조), `detailing.py`(상세·첨부 계획·검사·병합).
- SMTECH IRIS 행을 링크 없는 레코드로 싣는다(`detail: "iris"`, `system: "IRIS"`, 사용자 결정 D3-㉠) — 옛판은 쪽당 5~13행을 무음으로 버렸다. `counted.iris_rows` 로 센다.
- 상세 본문 대조 — 목록 제목(정규화 앞 15자), 레코드가 없으면 pblancId·ancmId·KOCCA 사업번호.
- `references/netbridge.md` 동봉. Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 `survey_crawl.py`·`survey_diff.py` 가 stdout·stderr 를 UTF-8 로 재설정한다(`survey_diff` 는 2.x 부터 cp949 에서 죽고 있었다).
- `--save-dir` 가 Windows 호스트 경로(`C:\…`·`C:/…`·`\\서버\…`)를 받는다 — Cowork 는 리눅스에서 스크립트를 돌려 `os.path.isabs` 가 이것을 상대 경로로 봤다(W10 리뷰 M1). 끝의 구분자만 떼고 드라이브 뿌리(`C:\`)는 남긴다.
- `raw/detail/`·`raw/att/` 에도 이름 규칙 밖 파일이 있으면 `error: input`(`raw/list/` 와 같다).
- 실측 픽스처 — 2026-09-30 itda-hyve 로 받은 목록·상세 17종(`tests/fixtures/live/`, 스크립트·스타일·머리 메뉴 제거, 연락처·작성자 이름·jsessionid 가림). 실측 첨부는 공고 안 연락처를 가릴 수 없어 넣지 않고 형식 표지만 맞춘 합성 바이트로 검사한다.

### Removed

- `scripts/kstartup_api.py`·`scripts/install_skill_deps.py`·`requirements.txt`·`deps.json` — curl_cffi(TLS 지문) 의존이 없어졌다(itda-hyve Go TLS 로 네 사이트 모두 차단 없음, 2026-09-30).
- `references/funding.md`(K-Startup API 가이드)·`references/k-startup-service-design-v2.0.{docx,md}`·`references/k-startup-codes.xlsx` — API 경로가 없어졌다(저장소 이력에 남는다).
- 테스트 `test_kstartup_api.py`·`test_no_curl_cffi.py`·`test_redirect_boundary.py`·`test_detail_attachments.py`·`test_hardening_round6.py`·`test_exit_contract.py` — 지운 전송·API 코드의 테스트. 남는 계약은 `test_listing.py`·`test_detailing.py`·`test_attach_download.py` 가 입력 파일로 다시 고정한다. 플러그인 라이브 스모크(`itda-gov/tests/test_gov_api_live.py::test_funding_live_smoke`)도 지웠다.

## [2.0.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. 선택 키 `KO_DATA_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.KO_DATA_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. 키가 없으면 크롤 경로로 가는 동작은 그대로다. SKILL.md·GUIDE.md·references 의 키 설정 안내·키 주입 규칙을 고쳤다.

## [1.0.3] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [1.0.2] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [1.0.1] — 2026-09-27 (#5)

### Fixed

- PDF 첨부 변환 계약 — `itda-doc:pdf-context-refinery` 가 돌려주는 "미검증 쪽" 목록(스캔이라 못 읽은 쪽)을 공고별로 한계 고지에 옮긴다.
  첫 3쪽 샘플로 스캔 여부를 정하던 refinery 가 뒤쪽 스캔 표를 조용히 빠뜨릴 수 있었다(refinery 1.3.0 과 짝).
- 첨부 변환 스킬 소속 표기 정정 — pdf-context-refinery 는 `itda-research` 가 아니라 `itda-doc` 소속이다(SKILL·GUIDE·설치 안내 문구).
- HWP 첨부 변환 정확도는 `itda-doc:hwpx` 1.3.2 의 HWP5 표 파싱 수정(#2)에 기댄다 — 실제 공고 첨부 표본은 hwpx 테스트
  `tests/reader/fixtures/hwp5_real/` 가 지킨다(구 리더는 그 공고의 지원내용 표를 전치했다).

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
