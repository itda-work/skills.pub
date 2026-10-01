# Changelog — itda-gov

## [9.0.0] - 2026-10-01

> 요구: **itda-hyve 0.10.4 이상**(옮긴 스킬 전부). itda-hyve 0.10.4 를 먼저 설치·업데이트한 뒤 이 판을 설치한다 — 0.10.3 이하는 응답 `final_url` 등에 시크릿이 되비치고 기본 User-Agent 에 제품명이 실린다.

### BREAKING

- **요청은 itda-hyve, 스크립트는 계획·가공만** (itda-work/skills#45·#46, 규칙 `cowork-network-via-hyve`). 스크립트가 외부 사이트·API 를 직접 부르지 않는다. 스크립트가 낸 호출을 itda-hyve(`http_request`·`batch`)가 받아 저장하고, 스크립트는 그 파일을 `--input` 으로 읽어 판정·전량 대조·가공만 한다. Claude Code 와 Cowork 가 같은 경로다. 옮긴 스킬: `dart` 0.21.1 · `ecos` 0.12.1 · `g2b` 0.12.1 · `kosis` 0.14.1 · `realty-deals` 0.13.1 · `realty-jeonse-gap` 0.11.1 · `realty-price-stats` 0.12.1 · `realty-supply` 0.11.1 · `fuel-price` 0.5.0 · `funding` 3.0.0 · `customs-notice` 0.2.0 · `fss-docs` 0.2.0 · `taxlaw` 0.2.0 · `court-auction` 0.2.0(키 안내 `realty-meta` 0.11.0). 하위 명령·출력 필드·저장 이름이 바뀌었다 — 스킬별 CHANGELOG 를 본다.
- **API 키는 itda-hyve 시크릿 탭에만 둔다** — `DART_API_KEY` · `ECOS_API_KEY` · `KOSIS_API_KEY` · `KO_DATA_API_KEY` · `RONE_API_KEY` · `OPINET_API_KEY`(선택). 요청에는 `{{secret:이름}}` 자리표시만 실리고 스크립트·Claude 는 값을 보지 않는다. 환경변수·`--api-key`·`claude config set env.*` 경로와 키 주입 규칙을 지웠고, `.env`·`.env.txt` 같은 env 파일도 읽지 않는다(#45).
- **`funding` 은 키 없는 공개 페이지 수집 전용** — K-Startup 공공데이터 API 경로를 지웠고(`KO_DATA_API_KEY` 를 쓰지 않는다), KOCCA 목록 수집은 robots 불허라 멈췄다.

### Removed

- `bai-notice` — 감사원 목록 데이터가 robots `User-agent: *` 불허 경로(`/api/`)로만 나오고 RSS·오픈 API 대안이 없다(사용자 결정 2026-10-01). 감사원 누리집 통합공지(https://www.bai.go.kr/bai/notice/notification/tab01)를 직접 확인한다.
- `airport-airline-stats` — 인천공항 항공사별 통계 화면이 robots `User-agent: *` 불허 경로로만 나온다(사용자 결정 2026-10-01). 공공데이터포털 인천국제공항공사 API(15095072·15160910) 또는 공사 누리집 통계 화면을 직접 확인한다.

### Fixed

- **SKILL_DIR 확정 블록**(itda-work/skills#47) — 새 Cowork 배치(`/root/.claude/plugins/synced/…`, `CLAUDE_PLUGIN_ROOT` 없음)에서 빈 값을 내던 옛 블록을 바꿨다. 스킬을 불러올 때 받은 base directory 를 먼저 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾으며, 후보가 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다(PowerShell 블록도 같은 계약). 스크립트를 실행하는 스킬 전부.
- 옮기며 드러난 수집 결함 — 전량 대조·응답 되비침 대조를 넣으며 고쳤다. 예: `dart` 연도 없는 조회가 7~12월에 실패, `realty-supply` KOSIS URL 오타·없는 표 ID·폐기된 청약 엔드포인트, `realty-price-stats` R-ONE 주간 시점, `fss-docs` 첨부가 늘 0건, `court-auction` 용도 코드표가 사이트와 다름. 상세는 스킬별 CHANGELOG.

## [8.0.1] - 2026-09-29

### Changed

- itda-hyve 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44) — `realty-deals` 0.12.2(GUIDE 내려받기 링크) · `dart` 0.19.3 · `ecos` 0.10.12(`references/netbridge.md` 사본 동기화). 동작은 그대로다.

## [8.0.0] - 2026-09-28

### BREAKING

- **자격증명 파일 별칭에서 `env.txt` 를 뺐다** (itda-work/skills#26, 사용자 결정 2026-09-28). 스킬이 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 에 키를 두었다면 **`환경변수.txt` 또는 `.env` 로 이름을 바꾼다** — 그대로 두면 키를 못 찾는다. 스킬은 `env.txt` 라는 파일을 더 이상 알아보지 못하며 별도 안내도 하지 않는다. 로더를 쓰는 팩 내 모든 스킬(`fuel-price` 포함)에 적용된다. 문서를 고친 스킬: `dart` 0.19.2 · `ecos` 0.10.11 · `funding` 1.0.2 · `g2b` 0.10.4 · `kosis` 0.12.1 · `realty-jeonse-gap` 0.9.9 · `realty-meta` 0.9.5 · `realty-price-stats` 0.9.10 · `realty-supply` 0.9.9(파일명 별칭 안내·키 주입 규칙을 3종으로).

### Changed

- `dart`·`ecos`·`realty-deals` 의 `references/netbridge.md` 사본을 정본과 동기화 — itda-hyve 0.9.4 의 batch `plan_file`·`imap_search` 대량 발송 표지(`bulk`·`bulk_reason`) 절이 더해졌다(itda-work/skills#39). 세 스킬의 동작은 그대로다.
- 같은 사본에 itda-hyve 0.9.5 의 batch `account: "*"` 펼침·`imap_search` `include_snippet`·`location` 대기 시간 절이 더해졌다(itda-work/skills#40). 세 스킬의 동작은 그대로다.

## [7.0.2] - 2026-09-28

### Fixed

- `funding` 1.0.1 — PDF 첨부 변환에서 `itda-doc:pdf-context-refinery` 가 돌려주는 "미검증 쪽"(스캔이라 못 읽은 쪽)을 공고별 한계 고지에 옮긴다. pdf-context-refinery 소속 표기를 `itda-doc` 으로 바로잡았다(#5).

## [7.0.1] - 2026-09-27

### Changed

- **itda-hyve 설치 판정을 서버 이름 기준으로** — `dart`·`ecos`·`realty-deals` 의 `references/netbridge.md`: 이름에 `itda-hyve__` 가 든 도구(Cowork `mcp__remote-devices__itda-hyve__*`, Claude Code `mcp__itda-hyve__*`)가 없을 때만 설치 안내. Claude Code 에 연결한 사용자에게 재설치를 안내하던 문구를 바로잡았다(12.0.0 공개 전 리뷰 M1).
- **옛 서버 이름 안내 제거** — `dart`·`ecos`·`realty-deals`: compatibility 의 옛 이름 병기를 빼고 `references/netbridge.md` 사본을 정본과 동기화.

## [7.0.0] - 2026-09-25

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### BREAKING

- MCP 서버 이름 `itda-butler` → `itda-hyve` 로 도구 전체 이름이 바뀌었다(`mcp__remote-devices__itda-hyve__http_request`). dart·realty-deals·ecos 의 itda-hyve 경로는 0.9.0 이상에서만 동작한다.

### Changed

- **MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0, itda-work/itda-hyve#6)** — `dart` 0.19.0·`realty-deals` 0.12.0(도구 전체 이름 `mcp__remote-devices__itda-hyve__http_request`), `ecos` 0.10.9(`allowed-tools` 에 `http_request` 추가). `taxlaw` 0.1.3 — 세무 포털 자동화 라우팅을 “현재 지원 스킬 없음” 으로. `references/netbridge.md` 사본을 정본(`shared/netbridge.md`)과 동기화, `shared/data_go_client.py` 안내 문구.
- itda-hyve 받는 곳(공개 내려받기 주소)을 공용 규약 사본(dart·ecos·realty-deals)과 realty-deals GUIDE 에 적었다.

## [6.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-gov-collect` → **`itda-gov`** (#1703).
- `itda-realty-data` 흡수 — 부동산 실거래·가격지수·공급·전세가율·법원경매(6종). 소스가 전부 공공 API 라 같은 팩.

## [5.6.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-gov` 개명(#1648 2단계). 공공기관 게시판·통계 4종(구 itda-class-igm)과 taxlaw(구 itda-tax) 편입. ECOS/KOSIS 명세 references·API 키 가이드는 구 itda-work 에서 이곳으로. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## [5.5.0] - 2026-09-02 (이슈 #1632 후속)

### Changed

- **`fuel-price` v0.3.0 — 기본 출력 compact JSON**(팩 관례 정합): `--format json|table`, 표시용 `summary`·`detail_table`·`source_note` 동봉.

## [5.4.0] - 2026-09-02 (이슈 #1632 후속)

### Changed

- **`fuel-price` v0.2.0 — 조회 전용으로 축소**(마스터 결정): 유류비 단가(`--efficiency`·`--factor`)·공지문(`--notice`) 제거.
  단가 산식은 회사 규정대로 대화에서 적용하고, 스킬은 오피넷 평균 유가 조회(전국·시도 16 × 일/주/월·`--end`)에 집중.

## [5.3.0] - 2026-09-02 (이슈 #1632)

### Added

- **`fuel-price` v0.1.3 편입** — 출장 유류비 기준가 브리핑: 오피넷(한국석유공사) 주유소 평균 판매가격(전국·시도 16 × 일/주/월, `--end` 과거 시점)을 **키 없이** 조회(평균판매가격 화면 폼 POST 를 브라우저와 바이트 동일 재현 — aside 실측·payload 골든) → 전기 대비 요약 → km당 단가(`--efficiency`·`--factor`) → 직원 공지문(`--notice`). 선택 `--source api`(`OPINET_API_KEY`, 최근 7일 일별)는 키 오류 시 200+빈 배열 함정을 명시 에러로 표면화. itda-work 에서 저작 후 **공공데이터 소스(한국석유공사) 팩인 itda-gov 로 이동**(마스터 결정 2026-09-02, 미배포 상태라 별칭 없이 이동). 배경: IGM 9기 사전설문 "유류비 시가 정기 확인 후 내부 공지".

## [5.2.0] - 2026-07-26

아래 2026-07-26 일자 항목들을 포괄하는 버전 스탬프입니다 — 날짜형 헤더로 누적되어 plugin.json(5.0.3)과 어긋난 것을 정합(#1300). 세부 변경은 아래 일자별 항목 참조.

## 2026-07-26 (이슈 #1284)

### Fixed

- **문서-코드 drift 일괄 정합 (#1284)** — 95스킬 감사 부수 발견분. 세부는 각 스킬 CHANGELOG 참조.

## 2026-07-26 (이슈 #1280·#1281·#1282·#1283)

### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.

## 2026-07-26 (이슈 #1279)

### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: dart 0.17.1 · ecos 0.10.5 · funding 0.9.8 · g2b 0.10.1 · kosis 0.11.1.

## [5.1.0] — 2026-07-26 (이슈 #1272)

### Removed

- **realestate 스킬 제거** — v7.0.0(release-notes) 에서 deprecated + "후속 마이너에서 명시적 제거 예정" 예고분의 집행. 상위호환 대체는 `itda-realty:realty-deals`(동일 `KO_DATA_API_KEY`, 기존 4유형 동일 동작 + 12유형 확장). README 부동산 워크플로우도 realty-deals 안내로 교체.

## [5.0.3] — 2026-07-18 (이슈 #1217)

### Changed
- 자격증명 사전 점검 금지 규칙 (#1217) — SKILL "키 주입" 실행 규칙을 실패 주도로 재서술: `ls`/`find` 사전 점검 금지(셸 패턴이 별칭 파일명을 놓쳐 오탐 — 실사용 리포트 검증), 스크립트 우선 실행 후 자격증명 누락 실패 시에만 지침 값 주입 재시도.

## [5.0.2] — 2026-07-18 (이슈 #1210·#1212)

### Changed
- 환경변수 파일명 별칭 안내 (#1210) — GUIDE/SKILL에 `.env` 외 `환경변수.txt`(및 `.env.txt`·`env.txt`) 지원 안내 추가. 비개발자의 점(.) 파일 생성 장벽 대응(로더 별칭 4종은 shared 주입으로 도달).
- 자격증명 출처 표시 규칙 (#1212) — SKILL 6종에 "[자격증명] KEY ← 출처" stderr 줄을 사용자에게 표시하는 Claude 실행 규칙 추가(값 비노출).

## [5.0.1] — 2026-07-18 (이슈 #1205)

### Changed
- 자격증명 안내 반전 (#1205) — dart·ecos·funding·g2b·kosis·realestate GUIDE/SKILL 12개 문서의 키 설정 1순위를 Claude 지침에서 **작업 폴더 루트 `.env`**(자동 탐색)로 반전. 지침 방식은 보조로 강등(대화 컨텍스트 노출 사유 명시).

## [5.0.0] — 2026-06-20 (이슈 #515)

### Removed — 공공 주식 스킬 묶음 제거 (BREAKING)

- **stock-quote·stock-portfolio 제거**: 금융위 data.go.kr 중계 주식시세는 EOD·중계 한 단계·간헐 불안정으로 민간 KIS 실시간(`itda-stocks:kis-market`)과 중복·열위. 주식 데이터는 itda-stocks(KIS) 단일 트랙으로 일원화한다. 두 스킬은 닫힌 의존 사슬(`stock-portfolio` → `import stock_quote_api`)이라 묶음 제거.
- itda-gov 스킬 **8 → 6** (dart·ecos·funding·g2b·kosis·realestate). `references/getStockSecuritiesInfoService-v1.0.{docx,md}` 정본 동반 제거.
- `KO_DATA_API_KEY`는 **유지** — g2b·funding·realestate 3종이 계속 사용(닫힌 사슬 아님).
- 참조 정리: `ground_check.py` 매핑, `test_gov_api_live.py` 케이스, 크레덴셜 가이드, `plan-work` 카탈로그, `market-scan` 주가·시세 라우팅(제거), `release-skills.yml` 주석.

### Note

- KRX OpenAPI 직접 연동은 검토 후 **보류** — 주식 시세는 민간 중복, 거시 데이터(지수·외인/기관 순매수·VKOSPI·마스터)는 market-radar #12 별개 레이어에서 필요 시 처리.

## [4.3.0] — 2026-06-17 (이슈 #438)

### Changed — 전 itda-gov 스킬 응답 포맷 슬리밍 (무손실)

- **stdout JSON 응답을 compact 출력으로 전환**: 8개 스킬(dart·ecos·funding·g2b·kosis·realestate·stock-quote·stock-portfolio) scripts의 `json.dumps(...)` **41곳**에서 `indent=2` 제거 + `separators=(",", ":")` 적용. `ensure_ascii=False`는 유지(한글 보존). **무손실** — 필드·값·키 순서 불변, 파싱 결과 동일(전 스킬 테스트 681건 GREEN 유지).
- 대표 샘플 실측 절감(공백 제거만): dart 24.1% · ecos 25.9% · kosis 25.6% · g2b 21.1% · stock-quote 12.4% (평균 ~22.6%). 절감폭은 구조 의존(중첩·짧은 필드가 많을수록 큼), 대형 실응답은 절대 절감 비례 확대.

### Added

- **회귀 가드** `dart/tests/test_response_compact_guard.py`: itda-gov 어느 스킬 `scripts/`에든 `indent=` 재유입 시 실패(cross-skill, CI 상시 실행되는 dart/tests 호스팅, vacuous-pass 방지 포함).

### Note

- 내용/필드 축소(default-small·`detail_level`)는 **비목표** — 본 변경은 포맷 전용(무손실).

## [4.2.1] — 2026-06-10

### Changed

- **GUIDE 발급 안내 정비 (SPEC-CREDENTIALS-GUIDE-001)**: kosis·ecos·dart·realestate·g2b·stock-quote·stock-portfolio·funding GUIDE의 API 키 발급 안내를 발급 가이드 페이지(<https://itda.work/credentials/>) 링크로 연결. 발급 절차 변경 시 웹 페이지가 먼저 갱신됩니다.

## [4.2.0] — 2026-05-29 (SPEC-DART-FEEDBACK-001)

### 🔴 BREAKING CHANGES (dart only)

- **`itda-gov:dart --report half` 제거** — `--report q2`로 변경 (반기보고서 코드 11012 동일). 사용자 입력 `half` 시 친절한 deprecation 안내 메시지와 함께 SystemExit. 마이그레이션은 `--report half` → `--report q2` 한 곳 치환.
- `dart_api.REPRT_CODES`에서 `'half'` 키 → `'q2'`로 변경 (외부 코드가 직접 import하는 경우만 영향).

### Added — dart 사용자 피드백 7항목 일괄 반영

- **dart `--unit auto|million|eok|jo`** (compare): 금액 한국 단위 표기. `auto`(기본) = |값|≥1조 `4조 3,923억 원`, ≥1억 `156억 원`, 미만 `5 백만원`. 외화는 unit 무시(기존 `M USD` 포맷 유지).
- **dart `--with-ratios`** (compare): 영업이익률·순이익률 행 자동 추가. 매출액=0/누락이면 `N/A`. table/csv/json 출력 모두 통합.
- **dart `--names` + `--corp-codes` 병기 가능** (compare): 두 옵션의 `mutually_exclusive_group` 해제. 둘 다 지정 시 corp_codes 순서대로 처리하되 names를 헤더 표시명으로 사용 (`SKT (00159023)`). 추가 API 호출 0.
- **dart CSV `formatted_amount` 컬럼 신설**: 단위 변환된 표기 + ratio 행도 같은 컬럼에 percentage. 기존 `thstrm_amount` raw 보존.
- **dart `DEFAULT_ACCOUNTS` 상수**: `("매출액","영업이익","당기순이익","자산총계")` 순서 보존. `--accounts` 기본값으로 사용 + `--help` 텍스트에 명시.

### Improvements — 전 itda-gov 스킬 공통 (shared/env_loader)

- **`~/.claude/settings.json` env 키 자동 탐색**: `claude config set env.X "value"`로 등록된 환경변수가 Claude Cowork 등 격리 subprocess에 자동 inject되지 않는 경우를 보조. 조회 우선순위: `cli_arg > os.environ > ~/.claude/settings.json env > .env files`. 신설 `_load_claude_settings_env()` (graceful — 파일 부재·malformed JSON·env 키 부재 모두 `{}` 반환). DART·KOSIS·ECOS·realestate·funding·g2b·stock-quote·stock-portfolio 모두 자동 수혜.

### Documentation — dart SKILL.md

- **"실행 경로 안내 (Cowork 환경)" 섹션 신설**: SKILL.md 첫줄 `Base directory` ≠ 실제 실행 경로 시나리오에 대한 3단계 탐색 가이드(`$CLAUDE_PROJECT_DIR` → `find /sessions -type d -name dart` → SKILL.md 그대로).
- **파일 구조 false-confidence 해소**: 종전 SKILL.md `env_loader.py # API 키 관리` / `test_env_loader.py` 광고가 dart 직속 디렉토리에 실제로 존재하지 않던 문제를 정정. `shared/` 거주 명시.
- CLI 옵션 표 갱신: `--report q2`, `--unit`, `--with-ratios`, `--accounts` 기본값(`매출액,영업이익,당기순이익,자산총계`) 명시.
- `argument-hint` frontmatter에 `--unit`, `--with-ratios` 노출.

### Acceptance Criteria

- AC-1~AC-7: 사용자 피드백 7항목 모두 반영, 1줄 grep으로 검증 가능 (SPEC-DART-FEEDBACK-001 §3 참조).
- AC-8: 회귀 0 — itda-gov 전체 + shared 707 passed, 3 skipped(사용자 환경 KO_DATA_API_KEY conditional), 0 failed.
- AC-10: dart v0.15.0 CHANGELOG + SKILL.md metadata 정합.

### Tests

- 신규 30 케이스 (`TestFormatCompareAmount`·`TestComputeRatio`·`TestReportQ2Breaking`·`TestCompareNamesAndCodesTogether`·`TestCompareWithRatios`·`TestDefaultAccounts`·`TestCompareUnitOption`). itda-dart 248 passed (218→248), 회귀 0.
- shared/tests 11 신규 케이스 (`TestClaudeSettingsEnv`). shared 52 passed (41→52), 회귀 0.

## [4.1.0] — 2026-05-16 (SPEC-GOV-STOCK-001)

### New Features

- `stock-quote` 스킬: 금융위원회_주식시세정보 OpenAPI(15094808)를 사용하는 주식 현재가·과거시세·종목검색 스킬. OHLCV(시가/종가/고가/저가/거래량) + 등락률 + 시가총액 조회, `beginBasDt`/`endBasDt` 범위 조회로 과거가 지원. 비실시간 데이터(T+1성, 기준일 익영업일 13시 이후 갱신)이므로 출력에 `basDt`와 최신성 안내 필수. `KO_DATA_API_KEY` 재사용(동일 공공데이터포털 키) + **15094808 활용신청(자동승인) 선행조건**. 62건 테스트 통과(stock-quote 31건 mock + 라이브 스모크 포함).
- `stock-portfolio` 스킬: 보유 종목 리스트(티커, 수량, 평균단가)를 입력받아 15094808 최신 종가로 평가금액·평가손익(P&L)·수익률을 순수 산술 계산. 리밸런싱·추천·매도/매수 권유 불포함(P-1). 입력 일회성 계산만 사용, 프로파일 영속 금지(P-2). 97% 커버리지, 21건 테스트 통과.

### Improvements

- `itda-gov/README.md` — 주식시세 행 추가 + `KO_DATA_API_KEY` 주의사항 갱신(15094808 활용신청)
- 각 신규 스킬 SKILL.md에 `## 규제 주의 (정책)` 섹션 임베드 — P-1~P-6 정책 표 + 검증된 자본시장법 분석(자본시장과 금융투자업에 관한 법률 §6·§17·§101·§176·§178·§178의2·§445) + 고정 디스클레이머("정보 제공이며 투자자문이 아님, 투자판단·책임은 본인") 모든 출력 경로에 부착.

### Technical Details

- 데이터 소스: 공공데이터포털 금융위원회_주식시세정보 OpenAPI(data.go.kr/data/15094808, `GetStockSecuritiesInfoService/getStockPriceInfo`)
- 환경변수: 기존 공용 `KO_DATA_API_KEY` 재사용(DART/KOSIS/ECOS/realestate/funding/g2b 동일 키)
- 아키텍처: itda-gov `kosis`/`dart`/`g2b` 형제 스킬 동형 구조 — `scripts/collect_stock_quote.py` + `stock_quote_api.py` + `tests/`, `stock-portfolio` 동일 패턴
- 규제 정책: 과잉 설계(SPEC-INVESTMENT-001 전용 플러그인 + FROZEN 헌법) 폐기 — 경량 SKILL.md 정책 섹션 + 인수 기준으로 충족. itda-stocks(KIS 민간 API)·itda-mmaa(KACEM 입찰) 무수정.

### Acceptance Criteria

- AC-1~AC-6: P-1~P-6 정책 전수 검증 (출력 스키마 + 디스클레이머 부착)
- AC-7: 구조 정합 (itda-gov 형제 스킬 동형, 새 plugin/헌법 0건)
- AC-8: 품질 (stdlib-only, mock-only 테스트, 3 플랫폼 pytest 통과)
- AC-9: itda-stocks/itda-mmaa git diff 0 (무수정 확인)

## [4.0.0] — 2026-05-15 (SPEC-REALTY-001)

### Breaking Changes

- `itda-gov:realestate` 스킬 제거. 한국 실거래가·임대·전월세 수집 기능은 `itda-realty` 플러그인으로 이전.
  - 마이그레이션: `itda-gov:realestate` → `itda-realty:realty-deals`
  - `KO_DATA_API_KEY` 환경변수는 그대로 재사용 가능 (동일 공공데이터포털 키)
  - `collect_realestate.py --type apt_trade` → `realty-deals` 스킬의 동일 기능으로 대체
  - `itda-realty` 플러그인 설치 필요: 새 대화에서 `itda-realty` 플러그인 활성화

### Removed

- `itda-gov/skills/realestate/` 디렉토리 전체
  - `scripts/realestate_api.py`
  - `scripts/collect_realestate.py`
  - `tests/test_realestate_api.py`
  - `tests/test_collect_realestate.py`
  - `references/*.pdf` (MOLIT API 가이드 PDF 4종)
  - `SKILL.md`, `GUIDE.md`

### Improvements

- `plugin.json` 버전 3.0.0 → 4.0.0 (MAJOR bump: breaking removal)
- `plugin.json` description에서 "부동산" 제거 (전용 플러그인 itda-realty로 이전)
- `justfile` test 레시피에서 `skills/realestate/tests` 제거

---

## 흡수 이력 — itda-realty-data

> #1703 재편으로 이 팩이 흡수되었다. 아래는 흡수 시점까지의 itda-realty-data 변경 이력이다.

## Changelog — itda-realty

한국 부동산 공공데이터 API 스킬팩 — 실거래가, 전세 가격차, 공급, 가격 통계.

## [0.11.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-realty` 개명(#1648 2단계). 스킬 구성 불변. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## [Unreleased]

### Added

- `realty-deals` v0.9.9 · `realty-price-stats` v0.9.9 · `realty-supply` v0.9.8 — description `[책임 경계]` 슬롯 + `## 이 스킬을 쓰지 않을 때` 표 파일럿 (#1620): raw 수집(deals) ↔ 지수·파생 통계(price-stats) 경계를 상호 지목.



### Fixed

- **문서-코드 drift 일괄 정합 (#1284)** — 95스킬 감사 부수 발견분. 세부는 각 스킬 CHANGELOG 참조.
### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.
### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: court-auction 0.1.2 · realty-deals 0.9.5 · realty-jeonse-gap 0.9.6 · realty-price-stats 0.9.6 · realty-supply 0.9.5.

### Fixed

- **배포본 ImportError 해소 (#1275)** — realty-jeonse-gap v0.9.5 · realty-price-stats v0.9.5: `deals_collector` 가 형제 스킬(realty-deals) scripts/ 에만 있어 publish 주입 pool 밖 → 배포 레이아웃에서 두 스킬 CLI 가 `--help` 조차 `ModuleNotFoundError` 로 실패하던 결함(실측, Cowork·Code 공통). `deals_collector.py` 를 `itda-realty/shared/` 로 승격(realty-deals v0.9.4 — 동작 불변)해 주입 대상에 편입. publish dry-run 배포 레이아웃에서 3 스킬 CLI exit 0 실측, 관련 conftest 의 realty-deals/scripts 경로 우회 제거.

## [0.10.5] — 2026-07-18 (이슈 #1217)

### Changed
- 자격증명 사전 점검 금지 규칙 (#1217) — SKILL "키 주입" 실행 규칙을 실패 주도로 재서술: `ls`/`find` 사전 점검 금지(셸 패턴이 별칭 파일명을 놓쳐 오탐 — 실사용 리포트 검증), 스크립트 우선 실행 후 자격증명 누락 실패 시에만 지침 값 주입 재시도.

## [0.10.4] — 2026-07-18 (이슈 #1210·#1212)

### Changed
- 환경변수 파일명 별칭 안내 (#1210) — GUIDE/SKILL에 `환경변수.txt` 등 별칭 지원 안내 추가.
- 자격증명 출처 표시 규칙 (#1212) — SKILL 5종에 출처 표시 Claude 실행 규칙 추가.

## [0.10.3] — 2026-07-18 (이슈 #1205)

### Changed
- 자격증명 안내 반전 (#1205) — realty-deals·jeonse-gap·price-stats·supply GUIDE/SKILL + realty-meta SKILL 9개 문서의 키 설정 1순위를 Claude 지침에서 **작업 폴더 루트 `.env`**(자동 탐색)로 반전. 지침 방식은 보조.

## [0.10.2] — 2026-06-10

### Changed

- **GUIDE 발급 안내 정비 (SPEC-CREDENTIALS-GUIDE-001)**: realty-deals·realty-jeonse-gap·realty-supply·realty-price-stats GUIDE의 공공데이터포털·KOSIS 키 발급 안내를 발급 가이드 페이지(<https://itda.work/credentials/>) 링크로 연결.


## [0.10.1] — 2026-06-10

### Fixed

- **배포본 DOA 해소 (#196)** — skills.pub 산출물에 플러그인 전용 shared 모듈(`data_go_client.py`·`lawd_codes.py`)이 어떤 경로로도 실리지 않아 realty-deals·realty-jeonse-gap·realty-price-stats 3스킬이 배포 환경에서 `ModuleNotFoundError` 즉사하던 결함. `publish.py`에 플러그인 로컬 shared 주입 단계(3a-2) 신설로 해소 — dry-run E2E에서 산출물 `deals_cli.py regions` 직접 실행 exit 0(283개 지역) 실증. **다음 skills-v\* 릴리스에서 실배포 반영.**

### Removed

- `shared/env_loader.py`·`shared/itda_path.py` stale 사본 삭제(#196) — 루트 `skills/shared/`가 SSoT. 사본(8365B)은 Cowork `~/.claude/settings.json` env 폴백(SPEC-DART-FEEDBACK-001 REQ-002)이 없는 구버전으로, 테스트는 사본으로 GREEN인데 배포본은 루트 주입본으로 동작하는 거짓 GREEN 구조였다. 삭제 후 테스트·배포 모두 루트 단일 버전 사용(realty 전용 모듈 data_go_client·lawd_codes·code_mapper는 유지). 스킬별 테스트 90/41/28/32/31 + shared 58 GREEN 유지.

## [0.10.0] — 2026-06-05

### Added

- `court-auction` 스킬 입주 — 대법원 법원경매정보(courtauction.go.kr) 매각공고·사건·물건 **read-only 조회** (SPEC-COURT-AUCTION-001, itda-skills/hyve#101).
  - itda-realty 최초의 비공식 표면 스킬: 공식 OPEN API 부재로 WebSquare XHR을 직접 호출하며, **API 키 불필요**·`shared/data_go_client` 비의존(다른 4스킬과 달리 conftest 없는 독립 구조).
  - 5 서브커맨드(codes/notices/notice-detail/case/search), warmup 세션 쿠키·호출 간 2초 throttle·세션 10회 budget·`ipcheck=false` 즉시 중단(자동 재시도 없음).

## [0.9.0] — 2026-05-18

### Baseline

- 플러그인 등록 (commit `ec5e77b`).
- 5 스킬 입주: `realty-meta`, `realty-deals`, `realty-jeonse-gap`, `realty-price-stats`, `realty-supply`.
- 본 entry는 현행 상태 baseline 기록 (SPEC-CHANGELOG-LINT-001 Phase 1).

### Known drift (별도 SPEC 위임)

- 5 SemVer 트랙 부정합 (plugin 0.9.0 / `realty-meta` 0.9.2 / skills 0.9.3·0.9.4) — `SPEC-CHANGELOG-LINT-001 REQ-006` 봉합 결정 대상.
- MEMORY.md 광고 'REALTY v4.0.0 breaking' vs 실 plugin 0.9.0 격차 — `SPEC-REPO-SPEC-RESTORE-001` sub-SPEC 위임.
