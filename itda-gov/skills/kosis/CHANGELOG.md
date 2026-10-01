# Changelog — itda-gov/kosis

## [0.14.1] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.14.0] — 2026-09-30 (itda-work/skills#45)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`--input` 가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `collect_stats.py` 는 KOSIS 를 직접 부르지 않는다. `plan <명령>` 이 `http_request` 인자(URL·`params`·`save_as`)를 내고, itda-hyve 가 `save_as` 로 저장한 응답을 `<명령> --input <파일…>` 이 읽는다. 7개 명령(search·data·info·list·meta·indicator·region) 모두 같다.
- **BREAKING — 출력 `error: "config"` 는 없어졌다** — 키가 없으면 스크립트가 아니라 itda-hyve 가 `secret_missing` 으로 알린다(W2 리뷰 m6).
- **BREAKING — 키 경로는 itda-hyve 시크릿 탭 하나** — `KOSIS_API_KEY` 는 `{{secret:KOSIS_API_KEY}}` 자리표시자로만 가리킨다. `--api-key` 인자, `os.environ` 읽기(`env_loader`), 셸 환경변수·`claude config set env.KOSIS_API_KEY` 안내, 키 주입(`KEY=<값> python3 …`)·출처 표시 규칙을 지웠다. 인증키 오류 안내 문구도 시크릿 탭 등록으로 바꿨다.
- **BREAKING — data 의 적응형 3단 흐름을 `next_calls` 루프로** — 1차 JSON 이 오류 20/21 이면 `error: "incomplete"`·`stage: "meta"` 와 getMeta ITM·TBL 호출을, 메타를 받으면 첫 축에 따라 JSON 재호출(`json2`) 또는 SDMX(`sdmx`) 호출을 `next_calls` 로 준다. 받은 파일 전부를 같은 인자로 다시 넘기면 다음 단계로 간다. 따옴표 없는 JSON 키 복구·SDMX Generic 파서·`OBJ_ID_SN` 슬롯 해석은 그대로다.
- **BREAKING — 출력 필드** — `data` 에 `raw_count`·`skipped_non_numeric`(값이 숫자가 아니라 뺀 행 수 — `notes` 에도 한 줄)을 더했다. `info`·`region` 의 `org_id`·`tbl_id` 는 가공 인자로 줄 때만 채워진다(`region` 출력에서 `org_id`·`tbl_id` 를 뺐다). `indicator` 출력에서 `jipyo_id` 를 뺐다. `search` 의 `keyword` 는 `--keyword` 를 줄 때만 채워진다. `list` 의 `vw_cd`·`parent_id` 는 저장 이름(`list-<서비스뷰>-<시작 목록|root>.json`)에서 읽는다 — `--vw-cd`·`--parent-id` 를 주면 이름과 대조해 다르면 `input` 오류다(W2 리뷰 m6 — 구현 초판은 `parent_id` 를 빠뜨리고 `vw_cd` 기본값 MT_ZTITLE 을 에코해 다른 서비스뷰 파일에 틀린 라벨을 달았다).
- 오류 31(조회결과 초과) 안내에 "기간·항목·분류를 나눠 받는다" 를 넣었다. KOSIS 응답에는 총건수가 없어 전량 대조 기준선이 없다는 것을 SKILL.md 에 적었다.

### Added

- 저장 이름 규칙 — 질의 인자 전부의 8자 지문을 이름에 싣는다(`kosis/data-<기관>-<통계표>-<지문>-{json1|json2|sdmx}`, `kosis/search-<지문>.json` 등). 다른 질의·다른 통계표·다른 명령의 파일, 같은 단계 파일 두 개는 `error: "input"` 이다.
- hyve 층 판독은 공용 `shared/hyve_input.py`(본문 그대로·응답 JSON 전체·실패 자리). 절단은 `truncated`, HTTP 오류는 본문의 KOSIS err 를 먼저 보고 없으면 `http`(403 은 활용신청 안내), 오타 URL 의 HTTP 404 HTML 은 `input`("KOSIS JSON 응답이 아닙니다").
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다. `references/netbridge.md` 동봉.
- `data` 의 메타 단계는 탐색 때 받은 `info-…-ITM.json`·`-TBL.json` 을 그대로 쓴다 — SKILL.md 에 "다시 받지 말고 함께 넘긴다" 를 적었다(W2 리뷰 m9).
- 테스트: `skipped_non_numeric` 값 고정(W2 리뷰 m4).
- 실측 픽스처 — 2026-09-30 itda-hyve 로 키 없이 받은 err 10 응답(JSON·SDMX XML). `KOSIS_API_KEY` 가 등록되지 않아 키 있는 응답은 Cowork 실측 대기다.

## [0.13.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. `KOSIS_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.KOSIS_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. SKILL.md·GUIDE.md·references 의 키 설정 안내·키 주입 규칙·오류표를 고쳤다.

## [0.12.2] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.12.1] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.12.0] — 2026-09-11 (이슈 #1684)

### Fixed

- **분류축 슬롯(objL 번호)을 `OBJ_ID_SN` 으로 실측 해석** — 첫 분류축이 `objL1` 이 아닌 통계표(한국보건산업진흥원 `--org-id 358` 계열)에서 `data` 가 KOSIS 오류 21(잘못된 요청 변수)로 전부 실패하던 결함 수정. `--obj1`~`--obj4` 의 의미는 "통계표의 1~4번째 분류축"으로 불변이며, 실제 `objL` 번호는 오류 20/21 발생 시에만 `getMeta type=ITM` 으로 해석해 1회 재시도한다(정상 통계표는 추가 호출 0 — 기존 동작·호출량 불변).
- **`objL1` 이 없는 통계표는 SDMX(Generic) 경로로 조회** — 그런 표는 슬롯을 맞춰 불러도 KOSIS **JSON** 이 빈 배열을 돌려주지만 같은 요청의 SDMX 에는 데이터가 전부 들어 있다(실측 #1684: `358/DT_358004_008` json 0건 / sdmx 54건, `358/DT_358004_007` json 0건 / sdmx 70건, 대조군 `358/DT_358004_001`·`101/DT_1K41014` 는 json 정상). SDMX 응답은 KOSIS JSON 행 스키마(`C1`/`C1_NM`/`ITM_NM`/`UNIT_NM`/`PRD_DE`/`DT`)로 환원하며, 이름·단위는 `getMeta` 원본에서만 채운다(추측 금지).

### Added

- `data` 응답에 진단 채널 `source`(`json`|`sdmx`)·`axis_slots`(실제 objL 번호)·`notes`(전환 사유) 추가. `--format table` 에서도 notes 를 함께 출력한다.
- 오류 21 메시지에 그 통계표의 **실제 분류축 목록**(`objL2=화장품부문유통채널별(A) 예: A01, A02 …`)과 `info` 재확인 명령을 부착.
- 2중 분류표의 두 번째 축을 `category2`·`category2_code` 로 보존(예: `358/DT_358004_007` 매출현황별).
- API: `get_table_axes()`(분류축 구조 해석)·`get_statistics_data_ex()`(행 + 진단) 공개. 기존 `get_statistics_data()` 시그니처·반환은 불변.

### Verified

라이브 실호출(2026-09-11): `358/DT_358004_008`(`--item T001 --obj1 A02 --recent 3` → 3건, 2022년 오프라인 판매 매출액 20,613,096 백만원)·`358/DT_358004_007`(210건)·대조군 `145/DT_145011_A009`(18건, source=json)·`101/DT_1K41014`(252건, source=json) 전건 성공.

## [0.11.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.11.2] — 2026-07-26 (이슈 #1280·#1281·#1282)

### Changed
- compatibility 라벨을 `Claude Code & Cowork. Python 3.10+` 로 교체 (#1280).
- `.env` 위치 안내를 Cowork 연결 폴더 / Claude Code 프로젝트 루트 양쪽 표기로 교체하고 셸 환경변수·settings.json `env` 경로를 명시 (#1282).

## [0.11.1] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.11.0] — 2026-07-15 (#1145)

### Added — MCP 벤치마크 기반 탐색·코드발견 파리티

kosismcp2026 MCP(10종) 대비 갭 분석에서, KOSIS OpenAPI 기반 기능을 스킬로 흡수(풀 파리티, `validate`·벡터검색 제외).

- **`info` 서브커맨드** (신규) — `statisticsData.do?method=getMeta`. 통계표의 분류(objL)·항목(itmId) 코드를 발견한다. `--type ITM`(기본)·TBL·ORG·PRD·CMMT·UNIT·SOURCE·WGT·NCD. **가장 큰 갭이자 최저 비용** — 스킬이 이미 쓰는 endpoint 에 method 만 바꾼 것. 이전엔 코드를 KOSIS 웹에서 직접 찾아야 했다.
- **`list` 서브커맨드** (신규) — `statisticsList.do` 트리 탐색. `--vw-cd`(MT_RTITLE=국제·OECD, MT_ATITLE01=지역 등)로 통합검색에 안 잡히는 통계 진입.
- **`meta` 서브커맨드** (신규) — `statisticsExplData.do`. 작성목적·법적근거·조사주기.
- **`indicator` 서브커맨드** (신규) — `pkNumberService.do`. 통계주요지표 개념·선정방법·출처.
- **`region` 서브커맨드** (신규) — 자연어 지역명 → objL 분류 코드 매핑(`info` ITM 파생).
- **`data --obj3`/`--obj4`** — objL1/2 만 지원하던 것을 objL4 까지 확장. 3~4중 분류 통계표 조회 가능.

### 유지 (의도적 비목표)

- `validate` 도구 미추가 — 스킬 모델에선 에이전트가 곧 적합성 판정자.
- 벡터 `item_search` 미구현 — stdlib 범위 밖(지자체 통계는 `list` 드릴다운+`info`로 대체).
- 대형 로컬 카탈로그 번들 안 함 — remote `search`는 항상 fresh(staleness 회피).
- MCP의 시범서비스 안내·출처 강제 보일러플레이트 미도입 — 순수 데이터 출력 유지.

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
