# Changelog — itda-realty/realty-jeonse-gap

## [0.11.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.11.0] — 2026-09-30 (itda-work/skills#45, #46 리뷰 반영)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed (W1 리뷰 반영 — 같은 판, 미공개)

- **BREAKING — 전세가는 전세 계약의 보증금 중위값이다** (리뷰 M5). 조인이 월세·반전세 계약의 보증금까지 후보로 넣고 최댓값을 골라, 실측(강남구 2026-08)
  조인 60건 중 11건이 월세 보증금이었다(전세가율 1.5%·2.5% 같은 값). 이제 `monthlyRent == 0` 인 계약만 쓰고, 같은 단지·면적에 여러 건이면 **중위값**을
  쓴다(신규·갱신 계약이 섞여 최댓값은 한 건에 끌린다). 결과 행에 `jeonse_count`·`deposit_min`·`deposit_max` 를 싣고, 행의 `monthly_rent` 는 뺐다.
  단지명·전용면적이 빈 행은 조인하지 않는다(`warnings` 에 건수).
- **BREAKING — 해제된 매매를 기본으로 뺀다** (리뷰 M6). `cdealType`(실측 `O`)이 있는 매매가 조인에 들어가고 있었다(실측 95건 중 4건). 결과 행에
  `cdeal_type`·`cdeal_day` 를 싣고, 뺀 수는 `excluded.cancelled_trade`, 넣으려면 `--include-cancelled`.
- **BREAKING — `--start-month`·`--end-month` 가 다시 필수다** (리뷰 m1). 선택으로 두자 달 누락이 조용히 통과했다. `YYYYMM` 형식·순서를 검사하고
  기간 밖 달의 파일은 거부한다.
- **BREAKING — 출력 `counts` 가 바뀌었다**: `trade`·`trade_used`·`rent`·`rent_jeonse`·`joined`. `excluded`·`include_cancelled`·`deposit_basis` 를 더했다.
  `start_month`·`end_month` 는 받은 파일이 아니라 인자 값이다.
- hyve 실패 자리(`{"error": …}` 파일)는 `error: api` + `code: HYVE_<code>` 가 아니라 **`error: hyve` + `code: <hyve 코드>`** 다 — ecos·g2b 와 같은 분류(리뷰 M3).
- `compatibility` 를 itda-hyve 0.10.4 이상으로 — 리뷰 m7 이 지적한 미공개 판 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐이다. 이 줄의 초판은 개발판들이 한 판으로 함께 공개됐다고 잘못 적었다).

### Added (W1 리뷰 반영)

- **`plan` 하위 명령과 `screen --next-plan`** (리뷰 M3). 스크립트가 itda-hyve batch `plan_file` 을 쓴다 — 모델이 `pageNo`·`DEAL_YMD`·`save_as` 를
  손으로 옮겨 적지 않는다. 40호출을 넘으면 `plan-1a.json`·`plan-1b.json` 처럼 나눠 쓰고 `plan_files` 로 알린다. 계획 파일은 회차 폴더
  (`jeonse-gap/<코드>-<시작월>-<종료월>[-<tag>]`) 안에만 쓴다. `--next-plan` 을 주면 stdout 에는 호출 수와 앞 3개만 싣는다.
- **전량 대조가 건수 합만 보지 않는다** (리뷰 M1). 같은 (달, 쪽) 이 두 파일에 있으면 인자 오류, 저장 이름을 본문과 대조(`-p<쪽>` ↔ `pageNo`·
  `<YYYYMM>` ↔ 거래월·`<코드>` ↔ `sggCd`·`<유형>` ↔ `--prop-type`), 매매·전월세 지역 섞임 거부. 같은 달 쪽마다 `totalCount`·`numOfRows` 가 다르거나
  쪽 경계에서 행이 겹치거나 건수가 넘치면 그 달을 `refetch` 로 두고, 사용자 확인 뒤 `--overwrite` 로 1쪽부터 덮어쓰는 계획을 쓴다(`max` 로 합치지 않는다).
  게이트는 `warnings` 와 `missing_pages` 를 함께 본다.
- 입력 인자의 글로브(`*`)를 스크립트가 펼친다 — PowerShell 은 와일드카드를 넘기지 않는다(리뷰 m6).
- 실측 발췌 픽스처 `live_apt_rent_11680_202608_joinable.xml`(강남구 2026-08 전월세 12쪽 중 매매와 단지·면적이 같은 183행 — 키 없음).

### Changed

- **BREAKING — 네트워크를 itda-hyve 로 옮겼다** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). 스크립트가 공공데이터포털을 직접 부르지 않는다 — 매매·전월세 요청은 itda-hyve `batch`·`http_request` 가 보내 `save_as` 로 저장하고, `screen` 은 그 파일을 `--trade-input <파일…> --rent-input <파일…>` 로 읽어 가공만 한다(realty-deals 의 파서 재사용). `--start-month`·`--end-month` 는 이제 선택 인자이고 "기간 중 파일이 없는 달" 검사에 쓴다.
- 키는 itda-hyve GUI 시크릿 탭의 `KO_DATA_API_KEY` 로만 가리킨다. 셸 환경변수·`claude config set env.*`·키 주입 규칙·출처 표시 규칙을 지웠다(`env_loader` 의존 제거). SKILL.md 에 엔드포인트별 요청 JSON, 1차(달마다 1쪽)·2차(`missing_pages`) batch 계획, 저장 이름 규칙, 호출 예산, 실패 코드 표를 적었다. `references/netbridge.md` 동봉.

### Added

- **전량 대조** — 달마다 `totalCount` ↔ 받은 건수를 대조해 미달·빠진 달이면 결과 없이 `status: "incomplete"`(exit 1)와 더 받을 쪽 목록 `missing_pages` 를 낸다. 부분 조인이 전세가율을 조용히 틀리게 만드는 것을 막는다.
- 저장된 파일이 오류 응답이면 `error: api` + `code` — 본문 `resultCode`, 게이트웨이 오류(`<OpenAPI_ServiceResponse>`), XML 이 아닌 본문(HTTP 오류 페이지), 닫히지 않은 XML(절단), itda-hyve 응답 JSON 의 HTTP 오류·`body_truncated`.
- 매매·전월세 파일 뒤바뀜과 `--prop-type` 불일치를 인자 오류로 거부한다. `regions` 하위 명령(법정동코드 목록)을 더했다.
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다.
- 실측 픽스처 2종(강남구 2026-08 아파트 매매 1쪽·전월세 12쪽, itda-hyve 로 받음 — 키 없음).

## [0.10.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. `KO_DATA_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.KO_DATA_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. SKILL.md·GUIDE.md 의 키 설정 안내·키 주입 규칙·오류표를 고쳤다.

## [0.9.10] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.9.9] — 2026-09-28 (itda-work/skills#26)

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

- 배포본 ImportError 해소 (#1275) — `deals_collector` 가 형제 스킬 scripts/ 에만 있어 publish 주입 pool 밖이었고 배포 레이아웃에서 `--help` 조차 `ModuleNotFoundError` 로 실패(실측). `itda-realty/shared/` 승격으로 주입 대상 편입, 배포 레이아웃 실측 exit 0 확인.

## [0.9.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.3] — 2026-05-21

### Changed

- 환경변수 누락 시 친절한 에러 메시지(발급 가이드+URL+설정 방법) 출력 (SPEC-ENV-ERROR-001). `resolve_api_key()`에 `guide_msg` 인자 추가.

## [0.9.2] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
