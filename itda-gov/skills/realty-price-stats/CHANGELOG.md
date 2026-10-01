# Changelog — itda-realty/realty-price-stats

## [0.12.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.12.0] — 2026-09-30 (itda-work/skills#45·#46)

미공개 0.11.0(derive 이전·W1 리뷰 보강)을 이 판에 합쳤다 — 0.11.0 은 어느 `skills-v*` 태그에도 없다(마지막 공개 skills-v13.0.1 은 0.9.10).

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed

- **BREAKING — 두 명령의 네트워크를 모두 itda-hyve 로 옮겼다** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). 스크립트는 R-ONE 도
  공공데이터포털도 부르지 않는다. 두 명령이 같은 흐름이다 — 계획(`rone-plan`·`plan`, `--write` 로 batch `plan_file`) → itda-hyve `batch`·`http_request`
  가 `save_as` 로 저장 → 가공(`rone --input`·`derive --input`, 모자라면 `--next-plan`). 옛 `rone --index-type … --start-month … --end-month …`(직접 호출)은
  `rone-plan`(같은 인자) + `rone --input` 두 단계로 바뀌었다. 래칫 가드 `LEGACY` 에서 이 스킬을 뺐다.
- **BREAKING — `RONE_API_KEY`·`KO_DATA_API_KEY` 는 itda-hyve GUI 시크릿 탭으로만 가리킨다.** 셸 환경변수·`claude config set env.…`·키 주입 규칙·
  `env_loader` 를 지웠다. 키 없음은 스크립트의 `error: config` 가 아니라 itda-hyve 의 `secret_missing` 으로 온다(`config` 오류 코드 없어짐).
- **BREAKING — R-ONE 요청 계약을 공식 명세대로 고쳤다.** R-ONE Open API 목록 「통계 조회 조건 설정」(2026-09-30 판독)과 키 없는 sample 호출로 대조했다.
  옛 파라미터 `apiKey`·`statbl_id`·`strtYymm`·`endYymm`·`format` 과 통계표 `HPIWK`·`HPIMON`·`JRRATE` 는 실제 API 에 없어 늘 실패했을 것이다 →
  `KEY`·`Type`·`pIndex`·`pSize`·`STATBL_ID`·`DTACYCLE_CD`·`START_WRTTIME`·`END_WRTTIME`, 통계표 `T244183132827305`(주간, `WK`)·`A_2024_00045`(월간, `MM`)·
  `A_2024_00156`(전월세 전환율_아파트, `MM`). 주간 시점 ID(`YYYYWW`)는 ISO 주차가 **아니다** — 달력으로 확정하지 않고, 어림한 창을
  앞뒤로 한 주씩 넓혀 받은 뒤 행의 `WRTTIME_DESC`(그 주 월요일)가 시작월 1일~종료월 말일 안인 주만 남긴다(W2 리뷰 M1 — 아래 Fixed).
- **BREAKING — rone 출력 필드가 바뀌었다.**
  - `results[]` 행: `{index_type, period, value}` → `{index_type, period, period_desc, region, region_code, item, value, unit}`.
    R-ONE 은 한 질의에 전국·시도·시군구 행을 모두 주므로 지역(`region` = 분류 전체명, `region_code` = `CLS_ID`)이 없으면 행을 구분할 수 없다.
    `period` 는 R-ONE 시점 ID(주간 `YYYYWW`·월간 `YYYYMM`), `period_desc` 는 R-ONE 시점 설명. `value` 는 값이 없으면 `0.0` 대신 `null`.
  - 최상위에 `index_type`·`label`·`statbl_id`·`cycle`·`start_month`·`end_month`·`start_wrttime`·`end_wrttime`·`total_count`·`scanned_count`·`period_filter`·`need_pages`·
    `truncated`·`region`·`sources`·`warnings` 를 더했다. JSON 은 계속 `indent=2`.
  - 오류 출력: `error` 값이 `config`·`args` 대신 `api`(+`error_code`)·`incomplete`(+`need_pages`·`will_truncate`·`next_call_count`·`next_calls`·`plan_files`)·
    `input`·`truncated`·`http`·`hyve`·`argument`(exit 2) 이다.
- **BREAKING — derive 는 해제된 거래를 기본으로 뺀다** (#46 리뷰 M6). 실측(강남구 2026-08 매매 95건 중 해제 4건) 평균 297,232 → 303,915,
  중위 280,000 → 285,000 만원. 뺀 수는 `excluded.cancelled`, 넣으려면 `--include-cancelled`.
- **BREAKING — derive 의 `--start-month`·`--end-month` 는 필수다** (#46 리뷰 m1). `YYYYMM` 형식·순서를 검사하고 기간 밖 달의 파일은 거부한다.
  출력 `start_month`·`end_month` 는 인자 값이다. `--type` 은 매매 8종만 받고(전월세를 주면 금액 0 통계가 나오던 것을 인자에서 막는다),
  받은 파일의 저장 이름 유형·단지명 필드(`aptNm`·`offiNm`·`mhouseNm`)와 대조한다(리뷰 m4).
- hyve 실패 자리 파일은 두 명령 모두 `error: hyve` + `code: <hyve 코드>` 다 — ecos·g2b 와 같은 분류(리뷰 M3).
- `compatibility` 를 itda-hyve 0.10.4 이상으로(리뷰 m7 — 공개된 적 없는 판 표기를 걷어냈다). `batch`·`plan_file` 이 없는 옛 판이면 계획의 `calls` 를 `http_request` 로 하나씩 부른다.
- 안내 주소를 `https://www.reb.or.kr/r-one/` 로 통일했다(옛 스크립트 안내 `r-one.co.kr` 제거). GUIDE.md 의 `settings.json` `env` 블록·
  "Cowork 에서 키를 넣을 방법이 없습니다" 를 지우고 시크릿 탭 등록 하나로 고쳤다.

### Added

- `rone-plan`(`--write` 로 batch `plan_file`) · `rone --input`(`--region`·`--max-pages`·`--next-plan`·`--format json|table`).
- `plan`(derive 입력의 1차 호출, 달마다 1쪽 — `--region`/`--lawd-cd`·`--type`·기간·`--tag`·`--write`) · `derive --next-plan`·`--overwrite` (#46 리뷰 M3).
  계획 파일은 회차 폴더(`price-stats/<코드>-<시작월>-<종료월>[-<tag>]`) 안에만 쓴다.
- rone 전량 대조 — 쪽마다 `list_total_count` 일치, 같은 쪽 두 번·쪽 빈틈·필요 쪽 초과·행 겹침(`WRTTIME_IDTFR_ID`·`GRP_ID`·`CLS_ID`·`ITM_ID`)·
  쪽 행 수(마지막이 아닌 쪽 1,000행, 마지막 쪽은 나머지 — 인증키 없는 sample 5행을 잡는다)·본문 통계표와 저장 이름의 지수 유형 대조.
  모자라면 `next_calls`, 첫 쪽에서부터 `need_pages`·`will_truncate`(상한 20쪽 초과 예고). `list_total_count` 가 없으면 실패.
- derive 전량 대조 — 달마다 `totalCount` ↔ 받은 건수가 모자라거나 빠진 달이 있으면 통계 없이 `status: "incomplete"`(exit 1)와 `missing_pages`.
  같은 (달, 쪽) 중복·이름↔본문 불일치·지역 섞임은 인자 오류(`args`), 쪽마다 `totalCount`·`numOfRows` 불일치·쪽 경계 겹침·건수 초과는
  `refetch`(사용자 확인 뒤 `--overwrite`)(리뷰 M1). 입력 글로브를 스크립트가 펼친다(리뷰 m6).
- 저장된 매매 파일이 오류 응답이면 `error: api` + `code`(본문 `resultCode`·게이트웨이 오류·HTTP 오류 페이지·절단). 출력에 `lawd_cd`·`type`·`months` 를 싣는다.
- batch 계획 파일을 두 명령 모두 40호출 단위로 나눠 쓴다(`…-1a.json`·`…-1b.json` — 40개를 넘으면 batch 가 하나도 실행하지 않는다). 단건 `timeout_sec` 50.
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다.
- `references/rone-openapi.md`(요청 계약·통계표 ID·메시지 코드와 판독 근거)·`references/netbridge.md`. 실측 픽스처 `tests/fixtures/rone/`
  (키 없는 sample 3종 + 오류 2종, 2026-09-30)·강남구 2026-08 아파트 매매 1쪽(키 없음).

### Fixed (W2 리뷰 — #46)

- **주간 시점 ID 를 ISO 주차로 만들던 것** (M1). 초판은 한 표본(202609 → 2026-02-23)으로 ISO 를 확정했는데, R-ONE 은 주를 일~토로 끊고
  1월 1일이 든 주를 1주로 센다 — 1월 1일이 금·토인 2021·2022 년(앞으로 2027·2028)은 한 주씩 갈려, 예컨대 202201~202206 요청이
  2021-12-20 주를 넣고 2022-06-27 주를 뺀 채 `status: ok` 였다. 이제 요청 창을 앞뒤로 한 주씩 넓히고(연 경계는 전년 `52`·다음 해 `01`)
  `WRTTIME_DESC` 로 거른다. 출력 `period_filter`(`rule`·`from`·`to`·`kept`·`dropped_before`·`dropped_after`)에 거른 수를 싣고, 요청 기간의
  월요일 중 결과에 없는 주가 있으면 `warnings` 에 적는다. 월간은 행 시점이 요청 기간 밖이면 `input` 오류다. `start_wrttime`·`end_wrttime` 값이
  넓힌 창으로 바뀐다(예: 202602 주간 `202605`~`202610`). 재리뷰의 31표본(2015~2026) 실측을 골든 표(`RONE_WEEK_GOLDEN`)로 고정했다.
  재리뷰(minor 1·2·6): "결과에 없는 주" 경고는 안쪽 결손만 본다 — 끝 결손은 `dropped_after == 0` 으로 경고한다(기간 끝에서 14일이 지났을 때만,
  그 전은 미공표일 수 있다). `collect_rone(today=…)` 인자를 더했다. 월요일인 첫날·말일(2024-01-01·2026-08-31) 포함 경계를 테스트로 고정했다.
  `--format table` 머리는 요청 창 ID 대신 요청 기간(`period_filter.from~to`)을 찍는다.
- 뮤테이션에서 GREEN 이던 게이트 다섯을 테스트로 고정했다 (m4) — `INFO-300`(인증키 사용 제한)·`ERROR-5xx` 가 빈 성공으로 통과하는 경로,
  `head` 에 `RESULT` 가 없을 때의 실패, 같은 주기 다른 통계표(월간 매매 ↔ 전월세 전환율) 대조, 행 키의 `ITM_ID`, `--region 전국` 정확일치.

### Removed

- `price_stats.fetch_rone_index`·`_fetch_rone_json`(네트워크)과 KOSIS 형태로 잘못 만든 픽스처 `tests/fixtures/rone_index_response.json`.

## [0.10.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. `RONE_API_KEY`·`KO_DATA_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.RONE_API_KEY "키"` / `claude config set env.KO_DATA_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. SKILL.md·GUIDE.md 의 키 설정 안내·키 주입 규칙·오류표를 고쳤다.

## [0.9.11] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.9.10] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

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
