# Changelog — web-search

이 스킬의 주요 변경 이력입니다. (Keep a Changelog 형식)

## [0.3.0] — 2026-09-30 (itda-work/skills#45·#46)

> ⚠️ **배포 차단** — 둘 다 충족한 뒤에 배포한다. ① itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정)
> 공개. 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다 — 공개된 적 없는
> 개발판(0.9.x) 표기를 걷어냈다(공개판은 0.8.1·0.9.0·0.10.1 이후뿐, `references/netbridge.md` 도 같은 기준으로 동기화).
> ② **키 있는 엔진 실측** — 이 판의 정상 응답 경로는 합성 픽스처로만 돌았다(키 미등록). Cowork 에서 Tavily·네이버·Serper(·Exa) 키를 등록해
> SKILL 예시 그대로 받아 `collect` 가 결과를 내는지, 그리고 Tavily·네이버만 등록한 상태에서 `auto` 가 Serper 를 빼고 끝까지 가는지 확인한다.

### Changed (2026-10-01 추가)

- 형제 지목 정리 — `itda-web:blog-reader` 제거(사용자 결정, itda-work/skills#46 W14 — 네이버 블로그 robots 의 `User-agent: *` 가 목록·댓글·전체 검색을
  막는다)에 맞춰 `[책임 경계]`·"쓰지 않을 때"·범위 밖·핸드오프 표의 blog-reader 행을 지우고, 네이버 블로그 목록·댓글은 브라우저 경로
  (`itda-web:aside-browser-mcp`)로 안내한다. 네이버 블로그 **검색**은 이 스킬의 공식 OpenAPI 경로 그대로다.

### Removed

- **BREAKING — Perplexity 엔진을 뺐다**(W5 리뷰 M2, 사용자 결정). 사유: **Sonar Chat Completions 지원이 2026-09-27 에 끝났다**
  (docs.perplexity.ai — 동기 요청은 Agent API 요청으로 모델별 점진 재구성 중이라 응답 모양을 장담할 수 없고, 유료라 모양이 바뀌면 과금 뒤 `PARSE_ERROR` 가 된다).
  **필요해지면 Agent API(`POST /v1/agent`)로 다시 넣는다.** `--engine perplexity`·`--engines …,perplexity`·`--model` 인자는 이제 오류(exit 2)다(perplexity 는 "0.3.0 에서 뺐습니다" 로 알린다). Tavily 응답에 `answer` 가 있어도 싣지 않는다.
  `PERPLEXITY_API_KEY` 는 이 스킬이 쓰지 않는다. 출력 `answer` 는 요약 답변을 주던 엔진이 없어 **늘 `null`** 이다(호환을 위해 필드는 둔다).

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`collect --input` 가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `web_search.py` 는 검색 API 를 부르지 않는다. `plan "<질의>"` 가 엔진마다 itda-hyve `http_request` 인자(URL·헤더·본문·`timeout_sec` 50·`save_as`)를 내고, 모델이 엔진마다 한 번씩 보낸 뒤(POST 는 `batch` 불가), `collect "<질의>" --input <파일…>` 이 저장된 응답을 병합·정규화한다. 옛 호출 `web_search.py "<질의>" [옵션]` 은 없어졌다.
- **BREAKING — 키 경로는 itda-hyve 시크릿 탭 하나.** 키는 헤더의 `{{secret:…}}` 자리표시자로만 가리킨다. `os.environ` 읽기(`env_loader`)·키 주입 규칙(`KEY=<값> python3 …`)·출처 표시 규칙·셸 환경변수/`claude config set env.*` 안내를 지웠다. Tavily 는 본문 `api_key` 대신 `Authorization: Bearer` 헤더다(공식 문서의 유일한 인증 방식, itda-hyve 프리셋 verify 와 같은 모양).
- **BREAKING — Naver 시크릿 이름을 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET` 하나로.** `NAVER_SEARCH_CLIENT_ID`·`NAVER_SEARCH_CLIENT_SECRET`(와 옛 env 폴백 `NAVER_CLIENT_*`)은 쓰지 않는다 — itda-hyve 프리셋 이름이다. blog-seo·eatery-trend 와 이름은 같지만 그 두 스킬이 itda-hyve 로 옮기기 전까지는 저장소가 달라(설정 파일 `env` 대 시크릿 탭) **시크릿 탭에 따로 등록해야 한다** — 옛 판에서 env 의 `NAVER_CLIENT_ID` 로 쓰던 사용자는 등록하기 전까지 `SECRET_MISSING` 이 된다(W5 리뷰 m1).
- **BREAKING — `--check-env` 를 지웠다.** itda-hyve 에는 시크릿 목록 도구가 없다. 키 유무는 호출해 보고 `secret_missing` 이면 그 엔진 없음으로 확정한다 — 모델이 실패 자리(`{"error":{"code","message"}}`)를 저장 이름에 쓰면 `collect` 가 `errors[].code: "SECRET_MISSING"`(`secrets` 에 등록할 이름)로 보고하고 나머지 엔진 결과는 살린다. 전부 없으면 exit 3. SKILL 실패 절 첫머리에 "netbridge·itda-hyve 의 '멈춘다' 는 그 엔진 하나에 대한 것 — 실패 자리를 쓰고 다음 엔진으로, 마지막에 반드시 `collect`" 를 단정했다(W5 리뷰 M3). 한 번 `SECRET_MISSING` 이 난 엔진은 그 대화의 다음 검색에서 뺀다(m8).
- **BREAKING — `--engine auto` 는 자동 과금이 없는 엔진 3종(tavily·naver·serper)만 고른다.** 옛 판은 "키가 있는 엔진 전부"였는데 이제 키 유무를 미리 알 수 없어, auto 가 유료 엔진(exa)을 부르면 키가 있는 순간 과금된다. 유료 엔진은 `--engines`/`--engine` 으로 지목했을 때만 부른다(비용 가드). 고른 엔진이 모두 키 없음이면 `notes` 가 **부르지 않은 무료 엔진을 먼저**, 그다음 유료 엔진 지목 방법을 알린다(자동으로 넘어가지 않는다, 재리뷰 n5). 유료 확인 규칙을 하나로 정했다 — 사용자가 이름으로 지목하면 한 줄 알리고 보내고, Claude 가 제안할 때만 먼저 묻는다(m9). 엔진 순서(결과를 섞는 순서)도 perplexity·tavily·serper·exa·naver 에서 tavily·naver·serper(·exa)로 바뀌었다.
- **BREAKING — `--engines` 에 같은 엔진을 두 번 주면 오류(exit 2)** 다. 옛 판은 받아들였다(m11).
- **요청 본문 문서 대조(2026-09-30)** — Exa `contents.highlights` 를 폐기된 `numSentences`·`highlightsPerUrl` 에서 `maxCharacters: 300` 으로(m3). Naver 웹문서(`webkr`) 요청에서 문서에 없는 `sort` 를 뺐다 — news·blog 만 `sort: sim`(m2). Tavily `max_results`·Serper `num`·Exa `numResults` 는 20, Naver `display` 는 100 이 상한이다.
- **입력 대조** — 저장 이름 `web-search/<엔진>-<지문>.json` 의 8자 지문이 질의어·`--count`·`--naver-type` 의 지문이다. 고른 엔진의 파일이 빠졌거나·그 경로에 파일이 없거나·다른 검색의 파일이 섞였거나·같은 엔진 파일이 두 개거나·고르지 않은 엔진 파일이 있으면 `error: "input"`(exit 2)이고 받아야 할 이름을 알려 준다. 응답이 질의어를 되돌려 주는 Tavily(`query`)·Serper(`searchParameters.q`)는 그 값을 대조하되 **다르면 경고만 한다**(`notes` + `engine_meta.<엔진>.echoed_query`, 결과는 싣는다) — NFC·공백·대소문자 차이는 같다고 본다. 되돌림 모양은 키 있는 실측 전이고 다른 검색의 파일은 이름 지문이 막으므로, 불일치로 정상 결과를 버리지 않는다(W5 재리뷰 n1 — 1차 반영 때는 검색 전체 exit 2 였다).
- **응답 판정** — 엔진별 오류 본문(2026-09-30 실측: Tavily `detail.error` · Naver `errorCode` · Serper `statusCode` · Exa 402 x402 결제 요구)을 읽어 `AUTH_FAILED`·`RATE_LIMITED`·`API_ERROR` 로 가른다. Exa 402 는 x402 태그만 `AUTH_FAILED`(키 없는 요청), 나머지 402 는 크레딧·예산 소진이라 `RATE_LIMITED`(m3). Tavily 문서의 429 문구("excessive requests")·432/433 을 `RATE_LIMITED` 로(m4). 결과 목록 키가 배열이 아니면 "0건 성공" 이 아니라 `PARSE_ERROR`(m5). 본문 없는 HTTP 오류는 모델이 `{"error":{"code":"http_<status>"}}` 를 써서 넘기면 상태 코드로 가르고, 실패 자리의 `code` 가 itda-hyve 실패 코드가 아니면(`insufficient_quota` 류) hyve 실패가 아니라 엔진 오류로 읽는다(m7). HTTP 오류 본문이 엔진 모양이 아니면 `HTTP_ERROR`, JSON 이 아니면 `PARSE_ERROR`, 본문 잘림은 `TRUNCATED`, itda-hyve 의 다른 실패는 `HYVE_FAILURE`(`hyve_code`). hyve 층 판독은 공용 `shared/hyve_input.py`. 실패 자리는 감싸지 않은 itda-hyve 오류(`{"code","message","hint"}`)·대문자 코드도 읽는다(재리뷰 n2). Tavily 422(`detail` 배열)는 `PARSE_ERROR` 가 아니라 요청 검증 `API_ERROR`(n3), Exa 의 x402 가 아닌 `payment required` 본문은 `RATE_LIMITED`(n4).
- **출력 필드** — 기존 필드(`query`·`engine`·`engines_used`·`results`·`answer`·`engine_meta`·`errors`)는 그대로다(`answer` 는 늘 `null`). 더해진 것: `errors[]` 의 `secrets`·`hyve_code`·`http_status`, 최상위 `notes`(있을 때 — 키 등록 안내·URL 없는 결과 수), `engine_meta.<엔진>.skipped_no_url`, `engine_meta.naver.total`. Exa 결과의 `score` 는 늘 `null`(문서상 응답에 없다), Tavily 결과의 `published_at` 도 `null`(`include_published_date` 를 싣지 않는다). 키 없음 코드는 `MISSING_API_KEY` 에서 `SECRET_MISSING`(itda-hyve 실패 코드와 같은 말)으로 바뀌었고, 옛 `NETWORK_ERROR`·`INTERNAL_ERROR` 류는 위 코드로 바뀌었다. 종료 코드 2 에 입력 파일 오류가 더해졌다.
- 재시도 — 옛 판은 스크립트가 2회 다시 보냈다. 이제 POST 는 itda-hyve 가 자동 재시도하지 않는다(과금 중복 방지 — `retry_unsafe` 를 붙이지 않는다). `status` 400 이상이면 다시 보내지 않고(`PARSE_ERROR` 도 응답 `status` 가 200 이었을 때만 다시 받는다 — 재리뷰 n3), `timeout` 이면 모델이 1회만(유료 엔진이면 묻고) 다시 보낸 **뒤에** 실패 자리를 쓴다(m9).
- 지운 파일: `scripts/{search_http,search_env,tavily_client,serper_client,exa_client,perplexity_client,naver_client}.py` 와 그 모킹 테스트. 새 파일: `scripts/engines.py`(호출 계획·응답 판정), `references/netbridge.md`(정본 사본). SKILL.md 를 "요청은 itda-hyve, 계획과 가공은 스크립트" 한 흐름으로, GUIDE.md 를 시크릿 탭 등록 하나로 고쳤다. Windows 콘솔 UTF-8 출력 재설정은 `main()` 첫 줄로 옮겼다. Serper 무료 한도를 "가입 시 한 번, 그 뒤 선불" 로 바로잡았다(m9).
- 테스트 — SKILL.md 의 예시 JSON 4개가 `plan` 출력과 같은지 골든으로 고정하고, 요청 본문·Naver 파라미터 집합·건수 상한·섞인 실패 exit 6·envelope 429 분류를 단언한다(W5 리뷰 M4 — 리뷰 뮤테이션 GREEN 10종). 픽스처 — 2026-09-30 itda-hyve 실측: `secret_missing`(이 Mac 에 검색 키 미등록), 인증 헤더 없이 보낸 오류 본문 4종. 정상 응답은 공식 문서 모양의 합성 픽스처, Tavily 429 는 문서 본문 그대로다.

## [0.2.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. 키(`TAVILY_API_KEY`·`SERPER_API_KEY`·`NAVER_SEARCH_CLIENT_ID`·`NAVER_SEARCH_CLIENT_SECRET`·`PERPLEXITY_API_KEY`·`EXA_API_KEY`)는 Claude Code 의 셸 환경변수 또는 `claude config set env.<KEY> "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 아직 없다. SKILL.md·GUIDE.md 의 키 설정 안내·키 주입 규칙·출처 표시 예시를 고쳤다.

## [0.1.11] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다 — 내용은 그대로 두면 된다. SKILL.md·GUIDE.md 의 파일명 별칭 안내·키 주입 규칙(파일명 2종·셸 glob 오탐 설명)·출처 표시 예시를 맞췄다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.1.10] — 2026-09-28 (itda-work/skills#26)

### Changed

- **자격증명 파일 별칭에서 `env.txt` 제거** (itda-work/skills#26) — 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 로 키를 두었다면 `환경변수.txt` 또는 `.env` 로 이름을 바꾼다. SKILL.md 의 파일명 별칭 안내·키 주입 규칙(파일명 3종·셸 glob 오탐 설명)을 맞췄다.

## [0.1.9] — 2026-09-27

### Changed

- User-Agent `itda-web-search/0.1 (+https://github.com/itda-skills)` → `Mozilla/5.0`. 검색 API 로그에 저장소 URL·스킬 이름을 남기지 않는다(outbound-identity-leak). 호출자가 준 UA 는 그대로 쓴다. 회귀: `tests/test_search_http.py`.

## [0.1.8] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 로그인·JS 렌더 사이트 안내에서 빠진 스킬(구 itda-hyve 팩의 web-automation)을 지우고 `itda-web:aside-browser-mcp` 만 남겼다.

## [0.1.6] — 2026-07-30 (이슈 #1334)

### Changed

- blog-reader `discover`와의 라우팅 경계·핸드오프 명문화 (#1332·#1334) — 네이버 블로그 한정 무자격 검색은 blog-reader `discover`(→`read` 이어읽기), 범용·다엔진 교차검증은 본 스킬 naver 엔진(공식 OpenAPI). 결과 중 blog.naver.com URL 본문·댓글은 blog-reader `read`로 위임.

## [0.1.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.4] — 2026-07-26 (이슈 #1282)

### Changed

- `.env` 위치 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 일반화하고 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 명시 (#1282).

## [0.1.3] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.2] — 2026-07-11

### Fixed

- **Windows cp949 stdio 크래시** (#1036) — 진입점에서 stdout/stderr 를 utf-8 로 reconfigure. locale(cp949) 콘솔·파이프에서 `--check-env` 의 `✓`/`✗`(U+2713/2717)·결과 렌더링의 em-dash(U+2014) 출력이 `UnicodeEncodeError` 로 죽고, cp949 로 나간 한국어 stderr 가 utf-8 부모 프로세스의 파이프 디코드를 깨뜨리던 문제 해소. deployed-style 테스트 4건이 Windows 에서 GREEN 복귀(저장소 관례 — etf-naver·docx-design 동형).

## [0.1.1] — 2026-06-10

### Added

- **market-scan 핸드오프 회귀 가드** (`tests/test_handoff_market_scan.py`) — market-scan Q4 '키 감지' 점검이 광고한 엔진 키 이름이 web-search `ENGINE_SPECS` required 키와 정합하는지 + `--check-env` 종착점이 격리 실행에서 살아있는지 검증(deployed-style, conftest 미의존). DATA-TIDY-001(광고된 파이프라인 실측 단절) 패턴 차단. 작성 즉시 market-scan 측 `NAVER_SEARCH_CLIENT_SECRET` 축약 표기로 인한 키 미감지 갭 1건 적발·교정.
- **naver 종류별 날짜 shape 회귀 케이스** (`tests/test_naver_client.py`) — live-prober 실측 기반: web(webkr 날짜 필드 부재 → `published_at` None)·news(`pubDate` RFC-822)·blog(`postdate` YYYYMMDD) 3종을 `pubDate or postdate` 폴백이 graceful 처리하는지 검증(기존 fixture는 blog 1종만 표현). 단위 66→68 GREEN.

### Changed

- **SKILL.md 사용법에 소스트리 개발자 PYTHONPATH 캐비엇 1줄 추가** — 배포본은 `publish.py`의 `_inject_shared_modules`가 `shared/`를 번들해 그대로 동작하나, 소스트리 직접 실행 시 `PYTHONPATH=skills/shared`가 필요함을 명시(미설정 시 `ModuleNotFoundError: env_loader`). 일반 사용자는 무관.

## [0.1.0] — 2026-06-09

### Added

- 다중 검색엔진(Perplexity · Tavily · Serper · Exa · Naver) 통합 조회 신설.
- `--engine auto`: 키 보유 엔진 fan-out → round-robin 병합 + URL 중복 제거 + count cap.
- 정규화 스키마(`rank·title·url·snippet·source·engine·score·published_at`) + `--format json|markdown`.
- Perplexity 요약 답변(`answer`) + 인용(citations) 매핑.
- 네이버 `--naver-type web|news|blog` 분기, 기존 `NAVER_CLIENT_ID/SECRET` 폴백.
- 키 주입(Claude 지침) 계약 + `--check-env` 진단 + 키 마스킹(stdout/stderr 미노출).
- 종료코드 매트릭스(0/2/3/4/5/6) + 부분 실패 `errors[]` envelope.
- 표준 라이브러리만 사용(추가 의존성 0).
- **엔진 선택 가이드**: SKILL.md에 상황별 라우팅 지침(AN Score 에이전트 검색 벤치마크 + 키워드 vs 시맨틱 근거), GUIDE.md에 평이언어 버전.
- **엔진별 무료 한도·요금·키 발급** 안내(2026-06 기준) — SKILL.md·GUIDE.md.
- **Serper 회색지대 경고**: 제3자 Google SERP 스크래퍼(Google v. SerpApi DMCA 제소 2025-12 · SearchGuard 차단) 명시, 보조용·키 설정 시에만 동작(미설정 시 auto 자동 제외).

### Notes

- Google Custom Search(2027 폐지)·Bing(2025 은퇴)은 채택하지 않음 — Serper·Tavily 등으로 대체.
- 각 엔진 응답 shape: tavily·naver·perplexity·serper·exa·auto **라이브 검증 완료**(P1).
- Brave는 무료 구독($5/월 크레딧 플랜) 활성화가 반복 실패해 **v0.1 활성 세트에서 제외**(향후 재검토, 구현 git 이력 보존). 라이브에서 발견한 "422-인증 신호" 재분류 가드(`search_http._looks_like_auth`)는 일반 방어로 유지.
