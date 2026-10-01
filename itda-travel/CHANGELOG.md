# Changelog — itda-travel

이 플러그인의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/),
버전은 [SemVer](https://semver.org/lang/ko/)를 따릅니다.

## [3.0.0] - 2026-10-01

> 요구: **itda-hyve 0.10.4 이상**(hotel-search). itda-hyve 0.10.4 를 먼저 설치·업데이트한 뒤 이 판을 설치한다 — 0.10.3 이하는 응답 `final_url` 등에 시크릿이 되비치고 기본 User-Agent 에 제품명이 실린다.

### BREAKING

- **`hotel-search` 0.4.0 — 요청은 itda-hyve, 스크립트는 판독만** (itda-work/skills#46, 규칙 `cowork-network-via-hyve`). 키 없는 Xotelo·환율 조회를 itda-hyve 가 받고 스크립트는 응답을 대조(되비친 체크인·체크아웃·통화)해 가공한다. 저장 이름이 식별 계약이고, 결과 없음은 exit 3 이다.
- **env 파일을 읽지 않는다** (itda-work/skills#45). `eatery-trend` 0.2.0(네이버 키 5종)·`train-ktx` 0.4.0(`KORAIL_USER_ID`·`KORAIL_PASSWORD`)은 Claude Code 의 셸 환경변수 또는 `claude config set env.<KEY> "값"` 으로만 받는다. 두 스킬은 스크립트가 직접 호출해서 itda-hyve 시크릿 경로가 아직 없다(요청 서명·로그인 세션 기능을 itda-hyve 에 요청할 예정).

### Removed

- `place-finder` — 카카오맵 검색의 키 없는 두 경로가 robots 불허(`map.kakao.com`)와 요청 프로파일 위반(Referer 를 지어내야 성립)에 걸린다(사용자 결정 2026-10-01). 카카오맵·네이버지도 앱에서 직접 검색한다.
- `flight-search` — Google Flights 공개 화면을 조회하는 방식이 약관상 회색지대이고 스킬 문서 스스로 "배포하지 마세요" 였다(사용자 결정 2026-10-01). 항공권은 항공사·여행사 앱이나 사이트에서 직접 검색한다.

### Fixed

- **SKILL_DIR 확정 블록**(itda-work/skills#47) — 새 Cowork 배치(`/root/.claude/plugins/synced/…`, `CLAUDE_PLUGIN_ROOT` 없음)에서 빈 값을 내던 옛 블록을 바꿨다. 스킬을 불러올 때 받은 base directory 를 먼저 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾으며, 후보가 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다(PowerShell 블록도 같은 계약). `eatery-trend`·`hotel-search`·`train-ktx`·`train-srt` 0.3.1.

## [2.0.0] - 2026-09-28

### BREAKING

- **자격증명 파일 별칭에서 `env.txt` 를 뺐다** (itda-work/skills#26, 사용자 결정 2026-09-28). 스킬이 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 에 키를 두었다면 **`환경변수.txt` 또는 `.env` 로 이름을 바꾼다** — 그대로 두면 키를 못 찾는다. 스킬은 `env.txt` 라는 파일을 더 이상 알아보지 못하며 별도 안내도 하지 않는다. 대상 스킬: `eatery-trend` 0.1.5 · `train-ktx` 0.3.1(파일명 별칭 안내·키 주입 규칙을 3종으로).

## [1.0.3] - 2026-09-27

### Changed

- `train_cli.py`(train-ktx·train-srt 공용 코어) 머리 주석에서 공개 배포에 없는 팩의 모듈 비유를 뺐다. 동작 변화 없음.

## [1.0.2] - 2026-09-27

### Changed

- 외부로 나가는 User-Agent 에서 우리 신원(저장소 URL·조직·스킬 이름)을 뺐다(outbound-identity-leak) — `eatery-trend` 0.1.4(네이버 자동완성 UA `Mozilla/5.0 (compatible; eatery-trend-skill; +itda-skills)` → `Mozilla/5.0`) · `hotel-search` 0.3.5(환율 UA `Mozilla/5.0 hotel-search/1.0` → `Mozilla/5.0`, Xotelo UA 끝의 `hotel-search/1.0` 제거).

## [1.0.1] - 2026-09-25

### Changed

- 저장소 이관(itda-work/itda-hyve#6) — `plugin.json` 의 homepage·repository 를 공개 저장소 자리표시자 `itda-work/skills.pub` 로. `IDEAS.md` §8 에 hyve 전제 무효 안내 한 줄. `hotel-search` 0.3.4 — 없는 규칙 참조 정리.

## [1.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-travel-plan` → **`itda-travel`** (#1703).

## [0.7.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-travel` 개명(#1648 2단계). 스킬 구성 불변. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## [Unreleased]


### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.
### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: eatery-trend 0.1.1 · flight-search 0.3.2 · hotel-search 0.3.2 · place-finder 0.1.2 · train-ktx 0.2.1 · train-srt 0.2.1.

### Added

- **flight-search v0.3.1 — 활용 시나리오 문서화**: 인천→깐느(니스) 라이브 실측
  사례를 GUIDE(자연어 "넓게 훑고 좁게 파기" 시나리오)와 SKILL 라우팅 가이드
  (coarse→fine 재스캔 — weekly 월 스캔으로 좁힌 뒤 유망 구간 일 단위 재스캔)에
  반영. 주 단위 표본이 놓친 저가일을 일 단위가 찾은 실증(-20만원대) 근거.
- **flight-search v0.3.0 — 다중 목적지(관문) 최저가 비교 `compare-destinations` (#1025)**:
  같은 날짜(단일 `--date` 또는 `--month` weekly 강제)를 목적지 후보(쉼표 구분,
  최대 8개)별로 조회해 관문 최저가 순위를 출력. 총 조회 상한 40(목적지 × 날짜,
  날짜 축 절삭)·요청간격 하한 유지. 후보는 사용자/에이전트가 제시(Explore 자동
  발견·후보 자동 선정 비목표), 출력에 "관문 최저가 ≠ 여정 총비용" 주의 고정.
  모호 도시(도쿄 등)가 목록에 있으면 조회 시작 전에 되묻는다.
- **flight-search v0.2.0 — 왕복 날짜 유연 비교 `--stay` (#1024)**: `compare-month`·
  `compare-range`·`compare-years` 에 체류일 고정 슬라이딩 왕복 모드 추가. 출발일
  `d` 마다 귀국일 `d+N` 왕복 1회 조회라 조회 수는 편도 비교와 동일 — 일수
  cap(31)·요청간격 하한(1초) 매크로 금지 계약 불변. 출력·JSON 에 출발~귀국
  구간과 `trip`/`stay_days` 반영. 출발×귀국 2D 전수 그리드는 비목표(계약 위반).

## [0.6.4] — 2026-07-18 (이슈 #1217)

### Changed
- 자격증명 사전 점검 금지 규칙 (#1217) — SKILL "키 주입" 실행 규칙을 실패 주도로 재서술: `ls`/`find` 사전 점검 금지(셸 패턴이 별칭 파일명을 놓쳐 오탐 — 실사용 리포트 검증), 스크립트 우선 실행 후 자격증명 누락 실패 시에만 지침 값 주입 재시도.

## [0.6.3] — 2026-07-18 (이슈 #1210·#1212)

### Changed
- 환경변수 파일명 별칭 안내 (#1210) — eatery-trend·train-ktx·train-srt GUIDE/SKILL에 `환경변수.txt` 등 별칭 지원 안내 추가.
- 자격증명 출처 표시 규칙 (#1212) — eatery-trend·train-ktx·train-srt SKILL에 출처 표시 규칙 추가.

## [0.6.2] — 2026-07-18 (이슈 #1205)

### Changed
- 자격증명 안내 반전 (#1205) — eatery-trend·train-ktx·train-srt GUIDE/SKILL 6개 문서의 키 설정 1순위를 Claude 지침에서 **작업 폴더 루트 `.env`**(자동 탐색)로 반전. 지침 방식은 보조.

## [0.6.1] — 2026-06-10

### Added

- **eatery-trend GUIDE 발급 안내 신설 (SPEC-CREDENTIALS-GUIDE-001)**: 네이버 오픈API·검색광고
  발급 절차 요약과 "키가 없으면 빠지는 기능" 표 추가 — 검색광고 키 없이도 surge 분석은
  부분 동작함을 안내. 상세 절차는 발급 가이드 페이지(<https://itda.work/credentials/>) 링크로 연결.

### Fixed

- **place-finder v0.1.1**: `--limit` 0/음수 입력이 제한 없이 전체 결과를 출력하던 문제를
  차단하고, `geocode_anchor`/`search_places`의 `timeout` 인자가 실제 HTTP 요청에
  전달되도록 수정. 통합 저장소 기준 실행 경로(`skills/itda-travel/...`)로 문서 정정.
- **train-ktx v0.1.1**: 승객 수·날짜·시각·열차종·좌석유형·예약 index 입력을
  코레일 접속 전에 검증하도록 보강하고, 통합 저장소 기준 실행 경로
  (`PYTHONPATH=skills/shared`, `skills/itda-travel/...`)로 문서 정정.
- **train-srt v0.1.1**: 승객 수·날짜·시각·좌석유형·예약 index 입력을 SR 접속 전에
  검증하도록 보강하고, 통합 저장소 기준 실행 경로(`PYTHONPATH=skills/shared`,
  `skills/itda-travel/...`)로 문서 정정.

## [0.6.0] — 2026-06-05

### Changed

- **열차 스킬 이름 변경**: 디렉토리·스킬명을 `train-ktx`·`train-srt`로 통일 (마스터 결정 2026-06-05).
  열차 예약 스킬을 `train-*` 접두사로 묶어 스킬 목록에서의 그루핑 가시성을 높임.
  - 디렉토리·SKILL.md `name`·스킬 간 상호 참조·README(플러그인/루트)·GUIDE·`requirements.txt`·`v8.1.0` 릴리즈 노트·CI 테스트 경로(`release-skills.yml`)를 일괄 갱신 — 옛 이름 잔여·깨진 링크(404) 0.
  - SPEC 제목·식별자(`SPEC-KTX-BOOKING-001`/`SPEC-SRT-BOOKING-001`)는 추적성 유지를 위해 보존, 본문 스킬 참조는 갱신.

## [0.5.0] — 2026-06-05

### Added

- **place-finder** 스킬 신설 (PoC v0.1.0) — 카카오맵 목적별 근처 장소 찾기(SPEC-PLACE-FINDER-001).
  - 위치(역명/동네/랜드마크) + 엄선 카테고리 4묶음(먹거리·여행·편의·교통, 11종) → 거리순 Top-N.
  - 비공식 카카오맵 검색 엔드포인트(평점·리뷰수·편의시설 8종) — 실측으로 공식 로컬 API 대비
    목적별 큐레이션 우위 확인. 거리는 anchor 지오코딩 + haversine 직접 계산(카카오 distance
    필드는 서버 IP 추정 기준이라 부정확). 영업상태(openoff)는 실시간과 무관해 미노출(링크 위임).
  - `--amenity`(주차·와이파이·반려동물·흡연·예약·배달·포장·장애인편의) 필터, `--sort distance|rating`.
    urllib(stdlib only·의존성 0), 자격증명 불필요.
  - `--category`는 11종 프리셋 외 **자유 키워드**(칼국수·돈까스 등 구체 음식/업종)도 수용 — 프리셋 미매칭 시 그대로 검색어로 사용(preset=null).
  - 비공식 API·ToS 회색이라 PRIVATE 유지(읽기전용·1회성·매크로 금지). 단위 49 passed/0 skip·ruff clean.

## [0.4.0] — 2026-06-05

### Added

- **flight-search** 스킬 신설 (PoC v0.1.0) — Google Flights 공개 검색 항공권
  조회·비교(SPEC-FLIGHT-SEARCH-001, 기존 Skyscanner+web_browse 접근에서 전환).
  - 범위: **검색 + 비교 전용**(예약·결제·좌석지정은 영구 비목표). **자격증명 0**
    (공개 표면 무인증 — itda-travel 스킬 중 유일).
  - 서브커맨드 `search`(편도/왕복) / `compare-month` / `compare-range` /
    `compare-years`. 공통옵션은 서브커맨드 뒤 배치(--json 위치 함정 회피).
  - 데이터: `fast-flights`(Google Flights 공개 표면). **직접 조회(common) 우선,
    차단 시 외부 fetch 서버(fallback) 폴백** — 검색조건의 제3자 노출 최소화.
  - 매크로 금지: 비교는 **일수 cap(31)·요청간격 하한(1초)을 코드로 강제**. 상세
    누락(partial) 비결정성은 complete 우선 정렬 + 가격·band·링크 유효로 정직 안내.
  - 한국어 도시명→IATA 힌트(모호 도시는 확인), KRW, 예약 검색 링크(deep link 아님).
  - 어댑터(flights_adapter)에 fast-flights 지연 import·예외 변환 격리(fail-loud).
  - 단위 77 passed/0 skip(itda-refine 5에이전트 게이트 후 dedup·₩0 가드·compare
    fail-loud 대칭·차단메시지 우선순위 보강 포함). 라이브: ICN-NRT search + 2026-07
    weekly 최저가 비교 검증. CI release-skills.yml test allowlist 에 등록.
  - 공개 배포 디스클레이머: Google ToS 회색·CAPTCHA 우회 없음·가격 조회시점.

### Changed

- itda-travel: flight-search 추가로 **열차 검색·예약(ktx·srt) + 맛집 트렌드(eatery)
  + 항공권 검색·비교(flight)** 4스킬. plugin.json description·keywords 확장.

## [0.3.0] — 2026-06-05

### Added

- **train-srt** 스킬 신설 (PoC v0.1.0) — SRT(수서고속철) 검색·예약(SPEC-SRT-BOOKING-001).
  - train-ktx 자매 스킬. SRTrain(비공식 SR 클라이언트) 어댑터(지연 import·예외 변환·마스킹).
  - `search` / `reserve` / `reservations`. `reserve` 는 `--confirm` 코드 게이트(SAFE-1).
  - 자격증명 `SRT_USER_ID`/`SRT_PASSWORD`. SR 역명 정규화(KTX 전용역 SRT 미정차 안내).
  - 결제·취소 비목표(ktx와 동일). 단위 25 passed/0 skip. 공개 배포 디스클레이머.

## [0.2.0] — 2026-06-05

### Added

- **train-ktx** 스킬 신설 (PoC v0.1.0) — KTX 열차 검색·예약(SPEC-KTX-BOOKING-001).
  - 범위: **검색 + 예약까지**(결제·취소는 사용자가 직접). 취소·매크로는 영구 비목표.
  - 서브커맨드 `search` / `reserve` / `reservations`. `reserve` 는 `--confirm` 코드
    게이트로 강제(SAFE-1) — 플래그 없으면 미리보기만, 실제 예약 호출 0.
  - 코레일 비공식 API(korail2 계열) 어댑터 — 안티봇/로그인/매진/결과없음을 사람이
    읽을 우리 예외로 변환(fail-loud, SAFE-4). 자격증명 `KORAIL_ID`/`KORAIL_PW`
    (env_loader 재사용·마스킹, SAFE-3). 역명 정규화 + SRT 전용역 안내(REQ-009).
  - 공개 배포 디스클레이머: 비공식 API·코레일 ToS·자기책임·매크로 금지(REQ-012).

### Changed

- itda-travel thesis 재정의: "맛집 트렌드 탐지 스킬팩" → **"여행 스킬팩"**(열차
  예약 + 맛집 트렌드). plugin.json description·keywords 확장. eatery-trend는 변경
  없이 한 슬라이스로 존속.

## [0.1.0] — 2026-06-01

### Added

- **eatery-trend** 스킬 신설 (PoC v0.1.0) — 유행 맛집 탐지(SPEC-EATERY-TREND-001).
  - thesis: 유행 = 평점(레벨)이 아니라 **관심의 미분(검색량 surge)**.
  - 모드 B(핫키워드 탐지, 주 파이프라인): 지역 seed → 발굴(자동완성+geo×음식 그리드
    +SearchAd 연관) → relevance(geo 게이트+사전+LLM 판정 훅) → 데이터랩 velocity
    3레인 분류(신규출현·검증상승·미디어스파이크) → 협찬 거품 필터 → 지역검색 장소 매핑.
  - 모드 A(검색 보강): 동네×주제 → 가게목록 + 주제 surge 맥락(희박 신호 인정).
  - 3레인 분류기 + 카테고리 상대 YoY(macro 보정) + 모멘텀 가드 + 전레인 magnitude floor.
  - 데이터 소스: 네이버 자동완성·데이터랩·SearchAd(HMAC)·지역검색·블로그검색(stdlib urllib).
  - fail-loud(소스 도달 실패 표면화)·rate-limit·TTL 캐시(검색량 휘발성 대응).
  - 라이브 검증: "제주" 종단 통과(카테고리 macro YoY 0.74, 카페루시아 상대YoY 5.31,
    감성카페 거품 970, 성수 뉴뉴 패션 차단). §8 PoC 회귀 케이스 재현.
  - 인스타 직접 스크래핑은 영구 비목표(검색량 surge가 다운스트림 그림자).
- itda-travel 플러그인 신설(flight-search 자매 도메인).
