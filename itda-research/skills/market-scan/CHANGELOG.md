# Changelog — itda-work/market-scan

본 스킬의 변경 이력. [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.

## [0.4.0] — 2026-09-30 (itda-work/skills#45·#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에**,
> `itda-web:web-search` 0.3.0 과 함께 배포한다. 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다.

### Changed (2026-10-01 추가)

- 위임 표의 `itda-web:blog-reader` 지목을 지웠다 — 그 스킬이 제거됐다(사용자 결정, itda-work/skills#46 W14 — 네이버 블로그 robots 가 목록·댓글·전체
  검색을 막는다). 단일 URL 본문 폴백은 `itda-web:web-reader` 하나다.

### Changed

- 상권·로컬 라우팅에서 `itda-travel:place-finder` 를 지웠다 — 그 스킬이 공개 팩에서 빠졌다(카카오맵 검색 경로가 robots·요청 프로파일 규칙에 걸림, itda-work/skills#46). 상권 조사는 웹 검색으로 한다.
- GUIDE 의 공공데이터포털 키 줄에서 `funding` 을 뺐다 — funding 3.0.0 은 키가 필요 없다(itda-hyve 로 공개 페이지를 받는다). "funding 은 아직 itda-hyve 로 옮기지 않았다" 예외 문구를 지웠다.
- **BREAKING — Q4 데이터 소스 가용성 점검을 itda-hyve 모델로** (itda-work/skills#45, W3 리뷰 M4). 키는 itda-hyve 시크릿 탭에만 있고 목록을 조회할 방법이 없어, 옛 점검(web-search `--check-env`·환경변수에 키가 있는지)은 늘 "없음" 이 되어 소스를 모두 뺐다. 이제 ① 스킬 설치 + 도구 목록에 itda-hyve `http_request` 가 있으면 **후보**로 올리고("(키는 첫 호출에서 확인)" 표기) ② 첫 호출이 `secret_missing` 이면 그 소스를 빼고 등록할 시크릿 이름을 알린다. 다중엔진 웹 검색과 공공데이터 API(dart·ecos·kosis·g2b·실거래) 모두 같다. "거짓 메뉴 금지" 는 확인 전 "키 있음" 이라 적지 않는 것으로 지킨다 — 문장도 "실제로 쓸 수 있는 소스만" 에서 "설치·연결이 확인된 소스만" 으로 맞췄다(W5 리뷰 m10). 한 번 `secret_missing` 으로 빠진 소스는 그 대화의 다음 조사 보기에 다시 올리지 않는다.
- **키 없는 소스를 빼고 계속하는 것은 우회가 아니다** — netbridge·itda-hyve 의 "`secret_missing` 이면 멈춘다" 는 그 소스 하나에 대한 것이라는 한 줄을 2단계 머리에 넣었다(W5 리뷰 M3 — 재리뷰 n6 에서 web-search 선택 시 절 밖으로 옮겨, web-search 를 고르지 않은 공공데이터 조사에서도 읽히게 했다. 공식 사이트 폴백은 API 가 아니라 공개 페이지라 키 우회가 아니라는 것도 적었다). 정본 `shared/netbridge.md` 에도 "여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다(스킬이 정한다)" 를 더했다.
- **BREAKING — web-search 시크릿 이름** — `NAVER_SEARCH_CLIENT_ID`·`NAVER_SEARCH_CLIENT_SECRET` 대신 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`(web-search 0.3.0 과 같은 이름). 유료 엔진은 Exa 하나다 — web-search 0.3.0 이 Perplexity 를 뺐다(Sonar Chat Completions 지원 종료 2026-09-27).
- 비용 가드 — web-search `auto` 가 무료 엔진(tavily·naver·serper)만 고르게 된 것을 반영했다. 기본은 `--engines tavily,naver`, Exa 는 Claude 가 제안하는 경우라 과금을 알리고 동의를 받은 뒤 지목한다. 첫 검색이 전부 `secret_missing` 이면 web-search 를 빼고 내장 WebSearch 로 계속하며, 빠진 소스를 보고서 출처 절에 적는다. 첫 검색에서 빠진 엔진은 다음 질의부터 뺀다. 한 조사의 다중엔진 질의는 10개 이내, 넘으면 호출 수를 먼저 알린다(W5 리뷰 m8).
- `allowed-tools` 에 `mcp__remote-devices__itda-hyve__http_request` 를 더했고 `compatibility` 에 itda-hyve 0.10.4 이상을 적었다. GUIDE.md 의 키 등록을 itda-hyve 시크릿 탭으로 바꾸고(settings.json `env` 블록 제거 — funding 만 예외로 그 스킬 가이드를 따른다), 다중엔진 웹 검색 소스 줄을 더했다.
- 계약 테스트 `itda-web/skills/web-search/tests/test_handoff_market_scan.py` 를 새 모델로 다시 썼다 — 이 문서의 시크릿 이름 ⊇ web-search 가 쓰는 이름, 옛 경로(`--check-env`·환경변수 감지·옛 네이버 이름·Perplexity) 부재, `secret_missing` 확정 문구, "기본은 무료 엔진(`--engines …`)" 문장에 유료 엔진 없음, 유료가 든 `--engines` 예시는 같은 줄에 과금·동의 문구(옛 단언은 항진이었다 — W5 리뷰 M4 #7).

## [0.3.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). 호출하는 형제 스킬들이 `.env`·`.env.txt` 를 포함해 어떤 env 파일도 읽지 않으므로, 관문의 공공데이터 키 "감지" 는 환경변수만 본다(`.env` 파일을 열어 보지 않는다). GUIDE.md 의 키 등록 안내를 Claude Code 설정 `env`·셸 환경변수 기준으로 고치고, Cowork 에서 넣는 방법은 스킬마다 다르다고 적었다. 이 스킬 자체는 키를 읽지 않는다.

## [0.2.5] — 2026-09-30 (itda-work/skills#45)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다. GUIDE.md 의 키 등록 안내를 `.env.txt` 기준으로 고쳤다.

## [0.2.4] — 2026-09-27

### Changed

- 주제 연관 전문 스킬 라우팅(본문 원칙·데이터 소스 표·GUIDE)에서 공개 배포에 없는 주식 스킬 추천을 빼고, 공개 스킬로 바꿨다 — 상장사·업종 재무는 `itda-gov:dart`, 금리·환율 등 거시 지표는 `itda-gov:ecos`. 설치할 수 없는 스킬을 데이터 소스 보기에 올리지 않는다.

## [0.2.3] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 창업 상권·로컬 라우팅에서 빠진 `naver-place`(hyve 앱 전제) 를 지우고 `itda-travel:place-finder` 만 남겼다.

## [0.2.2] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.2.1] — 2026-07-26 (이슈 #1272)

### Changed

- 라우팅 표의 부동산 실거래 경로를 `itda-gov:realestate` → `itda-realty:realty-deals` 로 교체 (realestate 제거 동반 정합).

## [0.1.1] — 2026-06-10

### Added

- **`web-search` 스킬을 수집 엔진 포트폴리오에 편입**(양방향 핸드오프 비대칭 해소 — web-search는 이미
  market-scan을 위임 대상으로 가리켰으나 그 역방향이 없었다). 다중 검색엔진(Tavily·Naver·Serper·Exa·
  Perplexity) fan-out으로 내장 WebSearch의 단일 인덱스 한계를 보완해, 교차검증의 전제인 "서로 다른 유형의
  독립 출처"를 넓힌다. 특히 **국내(지역=국내) 조사의 Naver 색인**·Exa 시맨틱이 차별점.
  - 위계 보존: web-search는 인접 **위임 경계**가 아니라 §2단계 **하위 수집 엔진**(WebSearch·web-reader와
    같은 층)으로 자리매김. URL·발췌만 돌려주므로 핵심 수치는 기존대로 WebFetch 원문 확인 후 반영.
  - **거짓 메뉴 금지 준수**: Q4 데이터 소스 메뉴에 무조건 올리지 않고, `--check-env`(또는 환경·"Claude 지침"의
    엔진 키) 점검으로 **키 보유 시에만** 노출. 키 0개면 보기에서 빼고 내장 WebSearch만.
  - **비용 가드**: 기본 무료 엔진(`--engines tavily,naver`), 유료(Perplexity·Exa)는 핵심 수치 교차검증이
    꼭 필요할 때만. 인접 스킬 참고 링크에 web-search 추가(핸드오프 대칭 완성).

## [0.1.0] — 2026-06-09

### Added

- 인터뷰 기반 시장조사 스킬 초안. 짧은 인터뷰(AskUserQuestion)로 조사 목적·범위를 받아낸 뒤
  1차 출처 우선·교차검증·사실/추정 분리를 절차로 적용해 의사결정용 보고서 한 장을 생성.
- **데이터 소스 선택을 인터뷰 단계로**: 가용성 점검 후 실제 쓸 수 있는 소스만 multiSelect로 제시
  (웹 / 공공 API / 주제 연관 전문 스킬). "거짓 메뉴"(미연결 엔진 노출) 금지.
- 소스 엔진 포트폴리오: 심층 다출처 수집은 WebSearch/WebFetch(막히면 `web-reader` 폴백)로 스킬 내장 처리,
  정형은 `itda-gov:*` 라우팅 — market-scan은 인터뷰·프레이밍·보고서에 집중. 스킬팩 내 기능만 사용한다.
- **확장형 소스**: 주제 연관 도메인 스킬(부동산 `itda-realty:*`·주식 `itda-stocks:*`·외식 `eatery-trend`·
  상권 `naver-place` 등)도 주제·가용성에 따라 소스 선택지로 제안. 고정 목록 아님(라우팅 추가로 흡수).
- GUIDE.md 상단에 "쓰는 자료·사용 스킬·사전 준비(API 키)" 섹션 — 키는 스킬별 상이
  (kosis=`KOSIS_API_KEY`·ecos=`ECOS_API_KEY`·dart=`DART_API_KEY`, stock-quote·funding·g2b·realestate=`KO_DATA_API_KEY` 공유), 키 없으면 공식사이트 폴백.
- GUIDE.md에 "시장 조사란?" 정의 섹션 — 목적(진입검토·동향·규모산정·가격유통)별 *핵심 질문·찾는 자료·산출 포맷*
  매트릭스로 용어를 구체화("뜬구름" 방지). SKILL.md Q2에도 목적별 핵심 수집 항목 매핑을 박아 수집 목록·보고서 §2와 연동.
- **의도 분기(개요 vs 시장 조사)**: 0단계에서 "빠른 뉴스 개요"인지 "결정용 시장 조사"인지 먼저 가른다.
  개요 모드는 인터뷰 생략 + 링크·발행일만 + 수치 "검증 전 참고" 표기(클리핑이 정당한 선택일 수 있음 반영).
  GUIDE에 "뉴스 클리핑과 무엇이 다른가" 비교표 추가.
- 국내 정형 데이터(시장규모·통계·기업재무·거시지표 등)를 `itda-gov:*` 공공데이터 스킬로 라우팅하는 표.
- 수집 폴백 체인: `itda-gov:*` → 공식 사이트 WebFetch → `web-reader` → "미확인". 공공 포털 JS 렌더링 대응.
- 시장 규모 추정 절차(top-down / bottom-up) + 단일 출처 함정(같은 원 보고서 재인용) 경고.
- 신뢰도 등급(A/B/C, 출처 유형 기준) + 3축 분리(출처/데이터/활용 적합도). 보정 확신도 생성 금지.
- 인접 스킬 경계표(investigate · ground-check · data-analysis-advisor · web-reader) + 검증 강도
  위임 정책(고위험 시 `ground-check` 위임, 검증 절차 중복 정의 금지).
- 정형 데이터 단위·의미 검증 가드(표 이름 "매출액"이라도 값이 지수면 시장규모 아님) + 리포트밀
  C등급 경고(자동생성 시장규모 판매 사이트). 라이브 dogfood(가정간편식/HMR)에서 실측 발견.
- 보고서 템플릿 `templates/report.md` + 사용자 가이드 `GUIDE.md`(비개발자 시나리오 5종).
- description에 트리거 경계절("단순 검색·단일 팩트체크가 아니라…진입검토 의도면") 추가 — skill-creator
  외부검증의 undertrigger 대응(400자 cap 내 복원).
