# Changelog — itda-realty/realty-deals

## [0.13.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.13.0] — 2026-09-30 (itda-work/skills#45, #46 리뷰 반영)

> 이 판은 미공개였던 0.12.3 을 다시 매긴 것이다 — W1 리뷰 반영으로 출력·종료 계약이 바뀌어(BREAKING) patch 로 둘 수 없었다.

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed (BREAKING)

- **호출 계획을 스크립트가 쓴다 — `plan` 하위 명령과 `collect --next-plan`** (리뷰 M3). 모델이 달·쪽마다 `http_request` JSON 을 손으로 짓던 흐름을
  itda-hyve batch `plan_file` 로 바꿨다. 40호출 단위로 나누고(`plan-1a.json`·`plan-1b.json`), 회차 폴더(`realty/<코드>-<시작월>-<종료월>[-<tag>]`)
  안에만 쓴다. 저장 이름 `<유형>-<코드>-<YYYYMM>-p<쪽>.xml` 이 식별 계약이다. `allowed-tools` 에 `batch` 를 더했고 `compatibility` 는 itda-hyve 0.10.4 이상.
- **전량이 아니면 결과 없이 exit 1** — 형제 스킬(realty-jeonse-gap·realty-price-stats)과 같은 계약(리뷰 m2). 전에는 `status: "incomplete"` 와 부분
  결과를 exit 0 으로 냈다. 미달 출력에 `missing_pages`·`next_call_count`·`plan_files`(또는 `next_calls`)·`refetch`·`need_overwrite` 를 싣는다.
- **`--start-month`·`--end-month` 필수** — 기간 중 파일이 없는 달·기간 밖 달의 파일을 잡는다. `YYYYMM` 형식·순서 검사.
- **오류 JSON 에 `code`** — `error: api` 는 `resultCode`·`returnReasonCode`·`NOT_XML`·`TRUNCATED` 등을, hyve 실패 자리 파일은 `error: hyve` +
  hyve 코드를 싣는다(리뷰 m2·M3).
- **`--summary` 는 해제 거래를 뺀다** (리뷰 M6). 결과 행에 `cdeal_type`·`cdeal_day` 를 싣고 행은 그대로 남긴다(원본 수집). 뺀 수는 `excluded.cancelled`,
  넣으려면 `--include-cancelled`. `sources` 에 `num_of_rows`·`sgg_cd` 를 더했다.

### Fixed

- **같은 쪽 중복·쪽 경계 밀림이 건수 대조를 통과하던 결함** (리뷰 M1). 같은 (달, 쪽) 이 두 파일에 있으면 인자 오류, 저장 이름을 본문과 대조
  (`-p<쪽>` ↔ `pageNo`·`<YYYYMM>` ↔ 거래월·`<코드>` ↔ `sggCd`·`<유형>` ↔ `--type`), 같은 달 쪽마다 `totalCount`·`numOfRows` 가 다르거나 쪽 경계에서
  행이 겹치거나 건수가 넘치면 그 달을 `refetch` 로 둔다(`max` 로 합치지 않는다). `--type` 과 받은 파일의 단지명 필드도 대조한다(리뷰 m4).
- 입력 인자의 글로브(`*`)를 스크립트가 펼친다 — PowerShell 은 와일드카드를 넘기지 않는다(리뷰 m6).
- 공용 파서: `totalCount`·`pageNo`·`numOfRows` 가 숫자가 아니면 `BAD_XML`(파일 이름 포함), 성공 코드인데 `<body>` 가 없으면 `NOT_RESPONSE`,
  닫히지 않은 `<OpenAPI_ServiceResponse` 는 `TRUNCATED`. 오류 메시지의 키 가림이 JSON 꼴·퍼센트 인코딩 꼴도 잡는다(리뷰 m3).
- **게이트웨이 오류가 0건 성공으로 통과하던 결함** — 루트가 `<OpenAPI_ServiceResponse>` 인 응답(키·활용신청 단계 오류, `returnReasonCode`)을 공용 파서가 "`<body>` 없음 = 0건"으로 읽고 있었다. SKILL.md 는 이미 이것을 오류로 적고 있었다. 이제 `error: api` 로 낸다. XML 이 아닌 본문(HTTP 오류 페이지)·닫히지 않은 XML(절단)·`<header>` 없는 응답·itda-hyve 응답 JSON 의 오류(`error`·HTTP 4xx/5xx·`body_truncated`)도 각각 명시 오류다.
- 매매 유형에 전월세 파일(또는 반대)을 넘기면 금액 0 으로 가공하지 않고 인자 오류로 거부한다. 거래 0건인 달은 저장 이름(`-<YYYYMM>-p<쪽>.xml`)에서 달을 읽어 `months` 에 싣는다.

### Changed

- 공용 모듈 `data_go_client`·`deals_collector` 에서 네트워크 코드(`fetch_xml`·`fetch_all_pages`·`collect_deals_for_month`·`collect_deals_range`, `urllib.request`)를 지웠다 — 배포본에 주입되는 모듈에 소켓 코드가 더는 없어 래칫 가드 `LEGACY` 에서 빠졌다. 파일 읽기·전량 대조(`read_sources`·`month_completeness`)를 공용으로 올려 형제 스킬(realty-jeonse-gap·realty-price-stats)과 같은 판정을 쓴다. 테스트의 네트워크 모킹을 저장 파일 입력으로 바꿨다.
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다.
## [0.12.3] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다.
  Windows 명령이 쓰던 `$env:SKILL_DIR` 을 정하는 PowerShell 블록이 없던 것도 정본 블록으로 채웠다.

## [0.12.2] — 2026-09-29 (itda-work/skills#44)

### Changed

- itda-hyve 설치·업데이트 안내의 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44). GUIDE.md 의 내려받기 링크.
- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다.

## [0.12.1] — 2026-09-27

### Changed

- `references/netbridge.md` 사본 동기화 — 설치 판정을 서버 이름 기준으로 — 도구 목록에 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치·업데이트 안내. 앞 문구는 Cowork 접두어만 조건으로 삼아 Claude Code 에 연결한 사용자에게도 재설치를 안내하게 했다(12.0.0 공개 전 리뷰 M1). 금지는 "다른 서버의 도구·내장 fetch" 로 한정.
- 옛 서버 이름 안내 제거 — compatibility 의 옛 이름 병기를 빼고 `references/netbridge.md` 사본을 정본과 동기화(옛 판 분기를 "itda-hyve 도구가 없으면 0.9.0 이상 설치·업데이트 안내" 한 갈래로).

## [0.12.0] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0). `allowed-tools`·본문 도구 지목·스크립트 안내문을 itda-hyve 로. `references/netbridge.md` 사본 동기화. compatibility 에 itda-hyve 0.9.0 이상, `save_dir` 거부 범위(홈 자체·`AppData`·`~/Library`)를 정본대로.
- GUIDE 「처음 설정하기」에 itda-hyve 받는 곳 링크. `references/netbridge.md` 사본 동기화 — itda-hyve 받는 곳 한 줄.

## [0.11.0] — 2026-09-23 (이슈 #1707)

### Changed (BREAKING — 사용 경로)

- **itda-butler 단일 네트워크 경로.** SKILL.md 가 `http_request` 를 직접 지시한다(정확한 URL·`params` 의 `serviceKey: {{secret:KO_DATA_API_KEY}}`·`LAWD_CD`·`DEAL_YMD`·`pageNo` 예시·`save_as`·`save_dir`). 저장은 **`save_dir` 에 Cowork 연결 폴더의 호스트 경로**를 넣고 샌드박스는 `$HOME/mnt/<폴더 이름>/<saved_path>` 로 읽는다(파일 `find` 절차 제거). 같은 이름 파일은 덮어쓰지 않으므로 페이지·월마다 이름을 달리 짓는다. `allowed-tools` 에 `mcp__remote-devices__itda-butler__http_request` 전체 이름을 적었다. `.env`·환경변수 키 해석 서술은 SKILL.md·GUIDE.md 에서 제거 — 키는 butler GUI 시크릿 탭에 **Decoding 키**로 등록한다.
- **`deals_cli.py` 는 파일 입력 전용이 됐다.** `collect --input <xml…>` 로 butler 가 `save_as` 한 응답을 읽어 정규화·요약한다. 네트워크 호출(`collect_deals_range`·`fetch_xml`)과 키 해석(`resolve_api_key`)을 제거했고, 정적 가드(`TestNoNetworkInScript`)가 재유입을 막는다. `--start-month`·`--end-month`·`--api-key` 인자는 사라졌다(월 범위는 butler 호출 쪽이 정한다).

### Added

- **전량 수집 대조를 산출에 싣는다** — `sources[]`(파일별 month·totalCount·page·item_count)·`months[]`(월별 totalCount ↔ collected)·`warnings[]`. 모자라면 `status: "incomplete"` 로 내린다(성공으로 말하지 않는다).
- `data_go_client.parse_response_xml()` — 저장된 응답 XML 을 읽는 공개 진입점(기존 `_parse_xml` 노출, 동작 동일).

## [0.10.0] — 2026-09-22 (이슈 #1707)

### Added

- **netbridge 경로 (#1707 파일럿)** — 네트워크가 막힌 환경(Cowork 샌드박스)에서 itda-netbridge `http_request` 로 직접 호출하는 절차를 SKILL.md 에 명시: `{{secret:KO_DATA_API_KEY}}` 자리표시자(`params` 전용), 12유형 서비스명 표, XML 성공 판정(`resultCode` 000 · 게이트웨이 `<OpenAPI_ServiceResponse>` 오류를 0건으로 접지 않음), 월×페이지 전량 순회와 `totalCount` 대조, 정규화 키 대응표, 호출 예산 안내.
- `references/netbridge.md` 동봉 — 정본 `skills/shared/netbridge.md` 사본(동기화 가드 `shared/tests/test_netbridge_doc_sync.py`).

## [0.9.8] — 2026-07-26 (이슈 #1284)

### Fixed

- 저장소 직접 실행용 PYTHONPATH 개발 부연 추가(배포본은 주입으로 불필요).

## [0.9.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.9.6] — 2026-07-26 (이슈 #1281·#1282)

### Changed

- 사전 요구사항의 `curl | sh`(astral.sh) uv 설치 블록 삭제 — 이 스킬은 표준 라이브러리만 쓰므로 설치 지시 자체가 불필요.
- `.env` 안내를 "Cowork에 연결한 작업 폴더" → "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체하고, 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 병기.

## [0.9.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.9.4] — 2026-07-26 (이슈 #1275)

### Changed

- `deals_collector.py` 를 스킬 scripts/ 에서 플러그인 `itda-realty/shared/` 로 승격 (#1275) — 형제 스킬(jeonse-gap·price-stats)이 publish 주입으로 도달 가능해짐. 동작·공개 API 불변.

## [0.9.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.2] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
