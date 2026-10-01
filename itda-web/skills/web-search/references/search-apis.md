# 검색 엔진 API 계약 (web-search)

각 엔진의 인증·요청·응답 핵심 필드. 요청 인자는 `scripts/engines.py` `build_call` 이 만들고(`plan`),
정규화는 같은 모듈의 `parse_response` 가 한다(`collect`). 모든 엔진은 공통 스키마
(`title·url·snippet·source·engine·score·published_at`)로 매핑된다. 요청은 itda-hyve `http_request` 가 보낸다 —
스크립트는 네트워크를 하지 않는다([netbridge.md](netbridge.md)). SKILL.md 의 예시 JSON 은 `plan` 출력과 같다(테스트가 고정).

| 엔진 | 엔드포인트 | 인증(헤더, itda-hyve 시크릿) | 요청 본문·파라미터 | 응답 핵심 |
|------|-----------|------|------|----------|
| Tavily | `POST https://api.tavily.com/search` | `Authorization: Bearer {{secret:TAVILY_API_KEY}}` | `query`·`max_results`(0–20)·`search_depth: basic`·`include_answer: false` | `query`(되돌림) · `results[].{title,url,content,score}` |
| Serper | `POST https://google.serper.dev/search` | `X-API-KEY: {{secret:SERPER_API_KEY}}` | `q`·`num`(≤20)·`gl: kr`·`hl: ko` | `searchParameters.q`(되돌림) · `organic[].{title,link,snippet,date}` |
| Exa | `POST https://api.exa.ai/search` | `x-api-key: {{secret:EXA_API_KEY}}` | `query`·`numResults`(≤20)·`type: auto`·`contents.highlights.maxCharacters: 300`·`contents.text.maxCharacters: 500` | `results[].{title,url,publishedDate,highlights,text}` |
| Naver | `GET https://openapi.naver.com/v1/search/{type}.json` | `X-Naver-Client-Id: {{secret:NAVER_CLIENT_ID}}` · `X-Naver-Client-Secret: {{secret:NAVER_CLIENT_SECRET}}` | `query`·`display`(≤100)·`start: 1`, news·blog 만 `sort: sim` | `total` + `items[].{title,link,description,pubDate/postdate}` |

- POST 는 `Content-Type: application/json` 을 요청이 직접 싣는다(itda-hyve 는 넣지 않는다). 본문은 JSON 문자열이다.
- 키는 **헤더에만** 싣는다 — URL·쿼리·본문에 키가 없다. Tavily 는 옛 판(0.2.x)의 본문 `api_key` 대신 Bearer 헤더를 쓴다
  (공식 문서의 유일한 인증 방식이고, itda-hyve 프리셋 `TAVILY_API_KEY` 의 verify 요청과 같은 모양).
- 허용 호스트(itda-hyve 프리셋): `api.tavily.com` · `google.serper.dev` · `api.exa.ai` · `openapi.naver.com`.
- 결과 목록 키(`results`·`organic`·`items`)는 **배열이어야** 한다 — 아니면 "0건 성공" 이 아니라 `PARSE_ERROR`.
- 되돌림 질의(Tavily `query`·Serper `searchParameters.q`)가 보낸 질의와 다르면 **경고만** 한다(NFC·공백·대소문자 무시). Tavily 문서는 이 필드를 "The search query that was executed" 라고 적는다 — 보낸 그대로라는 보장이 아니다. 키 있는 실측에서 따옴표·연산자·한글 질의를 그대로 되돌리는지 확인한다.

### 공식 문서 대조 (2026-09-30)

- **Tavily** — `published_date` 는 `include_published_date: true`(또는 `topic: news`)일 때만 온다. 지금 요청은 싣지 않아 날짜가 없다.
  429 본문 `{"detail": {"error": "Your request has been blocked due to excessive requests. …"}}`, 432 는 플랜 한도(`exceeds your plan's set usage limit`).
  422 는 `{"detail": [{"loc", "msg", "type"}]}` — 배열이다. 요청 검증 오류(`API_ERROR`)로 읽는다.
- **Exa** — `highlights.numSentences`·`highlightsPerUrl` 은 폐기됐다("Use `maxCharacters` instead"·"Currently ignored") → `maxCharacters` 로 바꿨다.
  결과 항목에 `score` 는 없다(`highlightScores` 만). 402 는 키가 있는 요청이면 크레딧·예산 소진, 키 없는 요청이면 x402 결제 요구다.
- **Naver** 웹문서(`webkr`) — 파라미터는 `query`·`display`(최대 100)·`start`(최대 1000) 셋. `sort` 는 news·blog 에만 있어 webkr 에는 싣지 않는다.
- **Serper** — 공개 문서가 없다(플레이그라운드는 로그인). 옛 코드와 같은 본문이다. 결과 0건일 때 `organic` 이 빠지는지는 키 있는 실측 대기.

## 오류 본문 (2026-09-30 itda-hyve 실측 — 인증 헤더 없이 보낸 요청)

| 엔진 | HTTP | 본문 | 분류 |
|------|------|------|------|
| Tavily | 401 | `{"detail": {"error": "Unauthorized: missing or invalid API key."}}` | `AUTH_FAILED` |
| Naver | 401 | `{"errorMessage": "Not Exist Client ID : Authentication failed. …", "errorCode": "024"}` | `AUTH_FAILED` |
| Serper | 403 | `{"message": "Unauthorized. Sign up for a free account.", "statusCode": 403}` | `AUTH_FAILED` |
| Exa | 402 | `{"error": "Payment required to access this resource", "tag": "X402_PAYMENT_REQUIRED", …}` | `AUTH_FAILED` |

- 한도 초과는 실측하지 않았다: 429·432·433 · Exa 402(x402 가 아닌 것) · Naver `errorCode 010` · 메시지의 `excessive requests`·`rate limit`·`quota`·`exceed`·`credit`·`budget` 류를
  `RATE_LIMITED` 로 본다. Naver `010` 은 itda-hyve 프리셋 verify 가 "검색 API 사용 신청 확인" 으로 읽는다 — 공통 오류 문서에는 숫자 코드 표가 없어 둘 중 어느 쪽이 맞는지 키 있는 실측으로 확정한다.
- `save_as` 는 HTTP 오류여도 본문을 저장한다 — `collect` 가 본문을 읽어 가른다. 응답 JSON 전체를 옮겨 적은 파일이면 `status` 를 함께 본다.
  본문이 0바이트인 오류는 모델이 `{"error": {"code": "http_<status>", …}}` 실패 자리를 쓰고, `collect` 가 상태 코드로 가른다.
- 실패 자리의 `code` 가 itda-hyve 실패 코드(`secret_missing`·`secret_host_denied`·`timeout` …)가 아니면 hyve 실패가 아니라 엔진 오류로 읽는다
  (OpenAI 호환 꼴 `{"error": {"code": "insufficient_quota"}}` 가 실패 자리 모양과 겹친다). 코드는 대소문자를 가리지 않고, 감싸지 않은 itda-hyve 오류 `{"code", "message", "hint"}`(최상위 `code` 가 itda-hyve 실패 코드일 때만)도 실패 자리로 읽는다.

## 종료코드

| 상황 | `errors[].code` | exit(전 엔진이 같은 사유일 때) |
|------|------|------|
| itda-hyve `secret_missing` | `SECRET_MISSING` | 3 |
| 401/403 · Naver 024·028 · Exa x402 | `AUTH_FAILED` | 4 |
| 429·432·433 · Exa 402 · Naver 010 | `RATE_LIMITED` | 5 |
| 그 밖의 API·HTTP·파싱·잘림·itda-hyve 실패 | `API_ERROR`·`HTTP_ERROR`·`PARSE_ERROR`·`TRUNCATED`·`INPUT_ERROR`·`HYVE_FAILURE` | 6 |

엔진 1개라도 성공하면 0. 사유가 섞여 전부 실패하면 6. 입력 파일 묶음이 질의와 맞지 않으면(빠진 엔진·없는 경로·다른 질의·겹친 파일) 2.

## Naver 검색 종류 매핑

| `--naver-type` | 엔드포인트 | `sort` |
|----------------|-----------|--------|
| `web` | `/v1/search/webkr.json` | 싣지 않음 |
| `news` | `/v1/search/news.json` | `sim` |
| `blog` | `/v1/search/blog.json` | `sim` |

## 참고

- **Perplexity**: 0.3.0 에서 뺐다. Sonar Chat Completions 지원이 2026-09-27 에 끝났다("reformulated as Agent API requests, rolling out gradually by model" —
  docs.perplexity.ai, 2026-09-30 판독). 필요해지면 Agent API(`POST /v1/agent`)로 다시 넣는다.
- Google Custom Search JSON API: 신규 가입 차단, 2027-01-01 폐지 → 미채택(Serper로 대체).
- Bing Web Search API: 2025-08-11 완전 은퇴 → 미채택(Serper·Tavily로 대체).
- Tavily: 무료 월 1,000건. Naver: 일 한도는 앱 등급에 따라 다름(콘솔 확인). Serper: 가입 시 크레딧 한 번, 그 뒤 선불.
- Brave: v0.1 보류(무료 구독 활성화 이슈) — 구현은 git 이력 보존, 향후 재검토.
