# Changelog — itda-gov/kosis

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
