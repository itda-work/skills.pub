# Changelog — itda-web-collect

## [3.0.0] - 2026-10-01

> 요구: **itda-hyve 0.10.4 이상**(web-search). itda-hyve 0.10.4 를 먼저 설치·업데이트한 뒤 이 판을 설치한다 — 0.10.3 이하는 응답 `final_url` 등에 시크릿이 되비치고 기본 User-Agent 에 제품명이 실린다.

### BREAKING

- **`web-search` 0.3.0 — 요청은 itda-hyve** (itda-work/skills#45·#46). `plan` → 엔진마다 itda-hyve `http_request` → `collect --input` 흐름이다. 키는 itda-hyve 시크릿 탭의 `TAVILY_API_KEY`·`SERPER_API_KEY`·`EXA_API_KEY`·`NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET` 이고, 네이버 이름은 `NAVER_CLIENT_*` 하나로 통일했다(옛 `NAVER_SEARCH_CLIENT_*` 는 쓰지 않는다). `--check-env` 를 지웠고 `--engine auto` 는 자동 과금이 없는 tavily·naver·serper 만 고른다. env 파일은 읽지 않는다(#45).
- **Perplexity 엔진 제거** — Sonar Chat Completions 지원이 2026-09-27 에 끝났다(사용자 결정).

### Removed

- `web-scout` — 여러 사이트의 robots·sitemap 을 훑는 정찰 방식이 사이트별 robots 판정·호출 최소화 원칙과 맞지 않는다(사용자 결정 2026-10-01). 웹 정보는 `itda-web:web-search`(검색)와 `itda-web:aside-browser-mcp`(Aside 브라우저로 직접 열기)로 찾는다.
- `blog-reader` — 네이버 블로그 robots.txt 가 글 목록·댓글·전체 검색의 자동 접근을 막고 AI 학습·RAG 목적 봇 접근 금지를 밝히고 있다(사용자 결정 2026-10-01). 네이버 블로그 글은 `itda-web:aside-browser-mcp` 로 직접 열고, 블로그 검색은 `web-search` 의 네이버 공식 검색(`--engine naver`)으로 한다.
- **`web-reader` 배포 보류** — 저장소에는 itda-hyve 경유판 8.0.0(robots 먼저 확인·리다이렉트 한 홉씩 목적지 검사)이 있지만, itda-hyve 의 사설·내부망 목적지 기본 거부가 들어온 뒤 v14.1 에 싣는다(사용자 결정 2026-10-01). 이 판 배포본에는 web-reader 가 없다. 그동안 정적 페이지는 내장 WebFetch, 로그인·JS 페이지는 `aside-browser-mcp` 로 읽는다. 팩 description 에서 정적 페이지 추출 구절을 뺐다.

### Fixed

- **SKILL_DIR 확정 블록**(itda-work/skills#47) — 새 Cowork 배치(`/root/.claude/plugins/synced/…`, `CLAUDE_PLUGIN_ROOT` 없음)에서 빈 값을 내던 옛 블록을 바꿨다. 스킬을 불러올 때 받은 base directory 를 먼저 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾으며, 후보가 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다(PowerShell 블록도 같은 계약). `web-search`.

## [2.0.0] - 2026-09-28

### BREAKING

- **자격증명 파일 별칭에서 `env.txt` 를 뺐다** (itda-work/skills#26, 사용자 결정 2026-09-28). 스킬이 읽는 파일명은 `.env`·`.env.txt`·`환경변수.txt` 세 가지다. `env.txt` 에 키를 두었다면 **`환경변수.txt` 또는 `.env` 로 이름을 바꾼다** — 그대로 두면 키를 못 찾는다. 스킬은 `env.txt` 라는 파일을 더 이상 알아보지 못하며 별도 안내도 하지 않는다. 대상 스킬: `web-search` 0.1.10(파일명 별칭 안내·키 주입 규칙을 3종으로).

## [1.2.1] - 2026-09-27

### Changed

- 외부로 나가는 User-Agent 에서 우리 신원(저장소 URL·조직·스킬 이름)을 뺐다(outbound-identity-leak) — `web-search` 0.1.9 — `itda-web-search/0.1 (+https://github.com/itda-skills)` → `Mozilla/5.0`.

## [1.2.0] - 2026-09-25

### Changed

- **hyve 안내 정리 (itda-work/itda-hyve#6)** — hyve 앱 폐기로 빠진 스킬(구 itda-hyve 팩의 web-automation)과 hyve `web_browse` 를 가리키던 안내를 Aside 브라우저 경로(`itda-web:aside-browser-mcp`)로 바꾸거나 지웠다.
  - **web-reader 7.2.0** — `[책임 경계]`·문서·CLI 안내문·WAF 폴백 토큰(`hyve_mcp` → `browser`). 브라우저 경로는 Aside 하나가 아니라 “실제 브라우저 — Aside, 없으면 Claude in Chrome 등”, 차단 통과는 보장하지 않음.
  - aside-browser-mcp 0.2.1(`references/repl.md` 폼·로그인 절에 “넣은 자격증명을 되돌려 보지 않음·보안 입력 실행당 1회·코드로만 넘길 때는 그 사실과 잔존 실측 결과를 적음” 추가) · blog-reader 0.12.3 · web-search 0.1.8 · web-scout 0.2.1(L4 브라우저 후보에서 hyve 삭제).
- README 의 #1704 안내 문단을 현행으로.

## [1.1.0] - 2026-09-21

### Removed

- **`web-automation` 이관 → `itda-hyve`(비공개, #1704)** — hyve `web_browse` MCP 가 스킬의 전부인데
  hyve 앱이 미배포라, 설치해도 쓸 수 없는 스킬이 공개 배포되고 있었다. 로그인·JS 렌더가 필요한
  페이지의 hyve 없는 경로는 `aside-browser-mcp`(Aside 브라우저)다.
- `[책임 경계]`·핸드오프 표의 지목을 `itda-web:web-automation` → `itda-hyve:web-automation` 으로 정합
  (web-reader·blog-reader·web-search·aside-browser-mcp).

## [1.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-web-collect` → **`itda-web`** (#1703).

## [0.2.0] - 2026-09-20

- **aside-browser-mcp 신설 (#1701)** — Aside(사용자의 로그인 세션·쿠키·메모리를 쥔 AI 브라우저)를 Cowork 에서 MCP 도구(`exec`·`repl`·`memory_search`)로 다루는 규율 정본. `web-automation`(hyve web_browse REPL 정본)과 같은 축의 형제다.
- 실측 반영: `repl` 도구 description 이 **2,048자에서 잘려** 전달되므로(원문 4,638자 중 56% 유실), 유실 구간의 규칙(탭 붙이기 4줄·`console.log` 로만 반환·`aside` 전역)을 `references/repl.md` 가 싣는다. 도구가 2종만 보이면 커넥터 설정의 Repl 토글이 꺼진 것이다.
- `web-automation` 라우팅 표에 역방향 경계 행 추가.

## [0.1.0] - 2026-09-05

- **팩 신설 (#1648 2단계)** — 웹에서 정보를 찾고 가져온다. 검색 → 정적 fetch(EUC-KR·WAF 폴백) → 정보원 정찰 → 브라우저 자동화(hyve MCP) 순 사다리. 목적: 가장 싼 경로부터, 실측으로 기억한다.
- 포함 스킬: blog-reader, web-automation, web-reader, web-scout, web-search.
