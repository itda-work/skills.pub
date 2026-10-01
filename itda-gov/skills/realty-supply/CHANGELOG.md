# Changelog — itda-realty/realty-supply

## [0.11.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.11.0] — 2026-09-30 (itda-work/skills#45)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).
> 청약홈(`api.odcloud.kr`) 허용 호스트는 itda-hyve 0.10.4 프리셋에 들어갔다 — 그 전에 `KO_DATA_API_KEY` 를 등록했다면 GUI 에서 추가한다(프리셋 변경은 새 등록에만 적용).

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 계획·가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). 스크립트가 KOSIS·청약홈을 직접 부르지 않는다. `kosis-plan`·`subscription-plan` 이 itda-hyve `http_request` 인자(자리표시자 `{{secret:KOSIS_API_KEY}}`·`{{secret:KO_DATA_API_KEY}}`)를 만들고, `kosis --input FILE`·`subscription --input FILE…` 이 `save_as` 로 저장된 응답을 가공한다. 옛 `kosis --indicator … --start-month … --end-month …`·`subscription --start-month … --end-month …` 호출 형태는 없어졌다.
- **BREAKING — 키 경로** — 셸 환경변수·`claude config set env.*`·`env_loader`·키 주입 규칙(`KEY=<값> python3 …`)·출처 표시 규칙을 지웠다. 키는 itda-hyve GUI 시크릿 탭에 등록한 이름으로만 가리킨다. 출력 `error: "config"` 는 없어졌다.
- **BREAKING — KOSIS URL 오타 교정** — `…/Param/statisticsParamData.do`(itda-hyve 실측 HTTP 404) → `…/Param/statisticsParameterData.do`(kosis 스킬과 같은 URL). 0.10.0 까지 kosis 명령은 성공한 적이 없다.
- **BREAKING — KOSIS 표 ID 교체** — 옛 `DT_MLTM_5209`·`5140`·`5141`·`5142` 는 KOSIS 에 없는 표였다(통계표 화면 「통계청::error」, 대조군 정상 — aside 판독). 미분양 `DT_MLTM_2082`(시·군·구별 미분양현황) · 인허가 `DT_MLTM_1946`(부문별, **월별 누계** — 월계 표가 없다) · 착공 `DT_MLTM_5386` · 준공 `DT_MLTM_5372`. `itmId` 는 `T10+` 대신 `ALL`, 분류는 표마다 `objL1..objL<n>=ALL`. API 로는 키가 없어 확인하지 못했다(Cowork 실측 대기).
- **BREAKING — kosis 출력 행** — `{indicator, period, value}` → `{indicator, period, region, region_code, category, category_code, item, value, unit}`. 옛 행은 `objL1=ALL` 로 섞여 온 지역 구분을 버려 같은 달 값이 지역 수만큼 반복됐다. 비수치 값(`-` 등)은 0 이 아니라 `null`. 출력에 `table`·`start_month`·`end_month`·`completeness: "no_baseline"`·`warnings`·`source` 를 싣고, 청약용 `meta`·`note` 는 kosis 출력에서 뺐다. `--region` 부분일치 필터를 더했다.
  지역은 표마다 선언한 축에서만 뽑는다(`table.region_axis`) — 미분양 `C1`·`C2`(시도·시군구), 인허가 `C3`(시도), **착공·준공은 항목 `ITM`(시도)**.
  나머지 분류(구분·부문명)는 `category`·`category_code`, 지역이 항목 축인 표의 `item` 은 빈 문자열이다. `--region` 은 지역 축만 보고, 거른 뒤
  0행이면 `warnings` 로 알린다. 선언한 지역 축이 빈 행도 `warnings` 로 센다(W2 리뷰 M3 — 지역 축은 화면 근거 추정, Cowork 실측 대기).
  응답의 `C<n>_OBJ_NM`(지역 축 밖 분류가 시도·시군구·지역을 말함)과 항목 축 표의 `ITM_NM`(시도 이름 부재)으로 선언을 대조해 어긋나면 경고하고,
  0행 경고 문구는 그 표의 지역 단위에 맞춘다(재리뷰 minor 4·5).
- **BREAKING — 청약 엔드포인트 교체** — 옛 `apis.data.go.kr/B552555/APTInfoSearchService2/getAPTLttotPblancDetail` 는 `returnReasonCode 12`(서비스 없음·폐기, itda-hyve 실측). 정본 data.go.kr 15098547 `api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail`(JSON, `page`·`perPage`·`cond[RCRIT_PBLANC_DE::GTE/LTE]`). itda-hyve `KO_DATA_API_KEY` 허용 호스트에 `api.odcloud.kr` 가 필요하다.
- **BREAKING — 청약 경쟁률 제거** — 분양정보 서비스에 경쟁률 필드가 없다. 옛 `cmptt_rate` 는 없는 `cmpttRate` 를 읽어 늘 `"0"` 이었다. description·GUIDE 에서 경쟁률 약속을 뺐다.
- **BREAKING — subscription 출력** — 옛 `count: 0`·`results: []`·`subscription_count`·`subscription_results`(행 `house_nm`·`rcrit_pblanc_de`·`cmptt_rate`·`tot_suply_hshldco`) → `count`·`results`(행 `house_manage_no`·`pblanc_no`·`house_nm`·`house_type`·`area`·`address`·`total_supply`(정수)·`rcrit_pblanc_de`·`rcept_bgnde`·`rcept_endde`·`przwner_presnatn_de`·`pblanc_url`)·`total_count`·`need_pages`·`truncated`·`pages`·`sources`·`warnings`. `meta.subscription_data_start`·2020-02 이전 `note` 는 유지.

### Fixed

- **청약 1쪽 절단** — 0.10.0 은 `pageNo=1, numOfRows=100` 한 번만 받고 총건수를 보지 않았다. 이제 `matchCount` 까지 쪽을 이어 받는다.

### Added

- 청약 전량 대조 — 분모 `matchCount`(쪽마다 다르면 경고 + 최댓값), 본문 `page` ↔ 이름 `-p<n>` 대조, 같은 쪽 두 번·`perPage` 불일치·여러 기간 혼입·필요한 쪽을 넘는 쪽·분모를 넘는 합친 행(W2 리뷰 m1)은 `input` 오류, 끝월이 2020-02 이후인 기간에 0건이면 조회 조건 확인 경고(리뷰 m2 — 기준 `end_ym` 은 재리뷰 minor 3 으로 테스트 고정), 중간 쪽이 덜 차면 1쪽부터 다시, 행 중복 계수. 모자라면 `error: "incomplete"` + `next_calls`·`need_pages`·`will_truncate`(첫 쪽에서도)·`next_call_count`, `--next-plan` 이면 계획 파일(`plan_files`) + 앞 3개 미리보기. `--max-pages`(기본 20) 초과는 `truncated`.
- batch 계획 파일은 40호출 단위로 나눠 쓴다(`plan-1a.json`·`plan-1b.json`…). 호출 `timeout_sec` 50.
- 입력 판독은 공용 `shared/hyve_input.py` — 본문 그대로·응답 JSON 전체·itda-hyve 실패 자리. 오류 `truncated`·`http`·`hyve`·`api`(KOSIS `err`·odcloud `code`·게이트웨이)·`input`. Windows 콘솔 UTF-8 재설정.
- `references/netbridge.md`(itda-hyve 규약 사본)·`references/api-contract.md`(요청 계약 근거·판독일).

## [0.10.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. `KOSIS_API_KEY`·`KO_DATA_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.KOSIS_API_KEY "키"` / `claude config set env.KO_DATA_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. SKILL.md·GUIDE.md 의 키 설정 안내·키 주입 규칙·오류표를 고쳤다.

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

## [0.9.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.9.6] — 2026-07-26 (이슈 #1282)

### Changed

- `.env` 안내를 "Cowork에 연결한 작업 폴더" → "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 교체.
- 셸 환경변수·`~/.claude/settings.json` 의 `env` 로도 설정 가능함을 같은 문단에 명시.

## [0.9.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.9.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.9.3] — 2026-05-21

### Changed

- 환경변수 누락 시 친절한 에러 메시지(발급 가이드+URL+설정 방법) 출력 (SPEC-ENV-ERROR-001). KOSIS_API_KEY·KO_DATA_API_KEY 양쪽에 `_SETUP_GUIDE_KOSIS`/`_SETUP_GUIDE_KODATA` 분리 적용.

## [0.9.2] — 2026-05-21

### Changed

- `env_vars` frontmatter 블록 폐기 → SKILL.md body `## 환경 변수` 표로 이전. itda-setup·check_env_vars.py 의존성 제거.

## [0.9.1] — 2026-05-21

### Improvements

- description을 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소. 트리거 정확도 영향 없음.
