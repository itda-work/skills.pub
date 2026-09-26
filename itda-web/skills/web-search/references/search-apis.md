# 검색 엔진 API 계약 (web-search)

각 엔진의 인증·요청·응답 핵심 필드. 정규화는 `scripts/<engine>_client.py`가 담당하며,
모든 엔진은 공통 스키마(`title·url·snippet·source·engine·score·published_at`)로 매핑된다.
응답 shape는 **공식 문서 기준**이며, 라이브 falsification으로 확정 권장(SPEC-WEB-SEARCH-001 §10).

| 엔진 | 엔드포인트 | 인증 | 응답 핵심 |
|------|-----------|------|----------|
| Tavily | `POST https://api.tavily.com/search` | body `api_key` | `results[].{title,url,content,score,published_date}` + `answer` |
| Serper | `POST https://google.serper.dev/search` | header `X-API-KEY` | `organic[].{title,link,snippet,date}` |
| Exa | `POST https://api.exa.ai/search` | header `x-api-key` | `results[].{title,url,score,publishedDate,highlights,text}` |
| Perplexity | `POST https://api.perplexity.ai/chat/completions` | header `Authorization: Bearer` | `choices[].message.content` + `citations[]` (+`search_results[]`) |
| Naver | `GET https://openapi.naver.com/v1/search/{type}.json` | header `X-Naver-Client-Id`/`X-Naver-Client-Secret` | `items[].{title,link,description,pubDate/postdate}` |

## 키 비노출 (REQ-006)

- 키는 헤더 또는 바디로만 전달한다 — URL 쿼리에 싣지 않는다.
- HTTP 오류는 상태코드 기반 한국어 메시지로만 변환하고(원 예외 `from None`), 키 평문을
  메시지에 담지 않는다.

## 오류 → 종료코드 (REQ-007)

| 상황 | 예외 | exit |
|------|------|------|
| 401/403 | `AuthError` | 4 |
| 429 | `QuotaError` | 5 |
| 5xx/파싱 | `EngineHTTPError`/`ParseError` | 6 |
| 네트워크/타임아웃 | `NetworkError` | 6 |
| 키 없음 | `MissingKeyError` | 3 |

## Naver 검색 종류 매핑

| `--naver-type` | 엔드포인트 |
|----------------|-----------|
| `web` | `/v1/search/webkr.json` |
| `news` | `/v1/search/news.json` |
| `blog` | `/v1/search/blog.json` |

## 참고 (2026-06-09 지형)

- Google Custom Search JSON API: 신규 가입 차단, 2027-01-01 폐지 → 미채택(Serper로 대체).
- Bing Web Search API: 2025-08-11 완전 은퇴 → 미채택(Serper·Tavily로 대체).
- Tavily: 무료 월 1,000건. Naver: 일 한도는 앱 등급에 따라 다름(콘솔 확인).
- Brave: v0.1 보류(무료 구독 활성화 이슈) — 구현은 git 이력 보존, 향후 재검토.
- 일부 엔진은 인증 실패를 401/403 이 아닌 422(+본문)로 신호한다 → `search_http._looks_like_auth`가 AuthError(exit 4)로 재분류(일반 방어).
