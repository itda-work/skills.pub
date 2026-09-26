---
name: web-reader
description: >
  WebFetch가 못 다루는 한국 웹페이지(EUC-KR/CP949·쿠키 인증·WAF 차단 정적 페이지)를 마크다운·JSON으로 가져오는 폴백 스킬입니다.
  "이 한국 사이트 읽어줘", "EUC-KR 페이지 가져와줘", "403 뜨는 페이지 가져와줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 정적 페이지 단건 페치·추출 전담 — 네이버 블로그는 itda-web:blog-reader, 키워드 검색은 itda-web:web-search, JS 렌더·로그인·봇 차단 페이지는 실제 브라우저 경로(itda-web:aside-browser-mcp — Aside, 없으면 Claude in Chrome 등).
license: Apache-2.0
compatibility: Claude Code & Cowork
allowed-tools: Bash, Read, Write, Agent, mcp__workspace__bash
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "7.2.0"
  created_at: "2026-03-18"
  updated_at: "2026-09-25"
  tags: "web, http, html, extraction, korean, fetch, scrape, markdown, json, defuddle, cli, coverage, ssrf, security, css-selector, encoding, euc-kr, cp949, cookie, waf, tls, static"
---

# web-reader

웹페이지를 깔끔한 Markdown 또는 JSON으로 변환한다. 한국 웹사이트(EUC-KR/CP949), 쿠키 인증 정적 페이지, WAF 차단 페이지(TLS impersonation 격자)에 최적화된 정적 페치 전용 스킬. JavaScript 동적 렌더링은 브라우저 경로(`itda-web:aside-browser-mcp`) 담당.

> **브라우저 경로**란 실제 브라우저로 페이지를 여는 것이다 — Aside(`itda-web:aside-browser-mcp`, macOS), 없으면 Claude in Chrome 등 연결된 브라우저 도구(Windows 는 Aside 미지원). 봇 차단을 “우회”해 준다는 보장은 없다 — 사람이 여는 브라우저처럼 열어 볼 뿐이다.

> **v7.0.0 안내**: Lightpanda 동적 fetch(`--dynamic-only`)가 제거되었습니다 (#1298). Cowork 실측에서
> 세션마다 151MB 바이너리 재설치가 발생하고, 핵심 대상인 진성 CSR SPA(wanted.co.kr 등)에서
> SIGILL 크래시로 동작하지 않아 v5.0.0 재흡수 근거가 무너졌습니다. 동적 렌더링은 v3 체제와
> 동일하게 브라우저 경로(`itda-web:aside-browser-mcp`) 로 위임합니다. `--dynamic-only` 호출은 exit 4 + 안내로 fail-fast.

> **v6.0.0 안내**: 정적 HTTP fetch 백엔드가 `curl_cffi` 단일 경로로 전환되었습니다. 기본 TLS
> impersonation은 `safari`이며, 첫 응답을 HTTP 200만으로 성공 처리하지 않고 challenge marker,
> known bad size, cookie sensor, optional success selector 검증을 통과한 뒤 반환합니다. WAF/챌린지로
> 보이면 `TLS impersonate × URL transform × Referer` 격자를 제한된 횟수로 자동 시도합니다.
> 인코딩 감지, SSRF 방지, cross-domain 쿠키 scoping, 50MB 제한은 기존과 동일하게 유지됩니다.

> **v4.0.0 안내**: YouTube 자막 추출 기능은 v4.0.0에서 제거되었습니다. `yt-dlp` + Claude 위임으로
> 동등 결과를 얻을 수 있어 이중 유지보수를 종료했습니다.
>
> **v3.0.0 안내**: SPA 어댑터(naver-land 등)는 제거됐습니다 — SPA 는 브라우저 경로(`itda-web:aside-browser-mcp`)를 씁니다.
> 봇 차단으로 막히면 실제 브라우저 경로(`itda-web:aside-browser-mcp` 등)로 열어 본다.

## Prerequisites

먼저 스킬 디렉토리를 확정한다.

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/web-reader}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/web-reader' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\web-reader"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# 의존성 설치 (Playwright/Chromium 불필요) — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# Windows: py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백(정문이 못 돌 때): python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 추천 워크플로우 (Fetch → Extract)

대부분의 경우 `fetch_html.py` + `extract_content.py` 2단계로 충분하다.

```bash
# 1. 페이지 가져오기
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "https://example.com" --output page.html

# 2. 콘텐츠 추출 (Markdown) — 파일 입력 시 --url 불요
python3 "$SKILL_DIR/scripts/extract_content.py" page.html --format markdown

# 또는 파이프라인 (Unix)
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "URL" | \
  python3 "$SKILL_DIR/scripts/extract_content.py" --format markdown --url "URL"
```

Windows:
```powershell
py -3 "$env:SKILL_DIR\scripts\fetch_html.py" --url "URL" --output page.html
py -3 "$env:SKILL_DIR\scripts\extract_content.py" page.html --format markdown
```

### 추출 레코드 (Fetch → Records) — v7.1.0

목록 페이지·RSS 를 **요약하지 말고 먼저 행 단위 레코드**로 뽑는다(출처 URL + 원문 발췌). 선별·요약은
그 레코드 위에서만 한다 — 결과가 이상할 때 "못 읽음 / 잘못 요약 / 지어냄"을 가를 수 있고, 다음 회차
레코드와 URL·해시로 diff 가 된다(hyve #1600).

```bash
# 목록 페이지 → 레코드 (봉투 재료는 fetch_html 의 stderr 값을 넘긴다)
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218" --output list.html
python3 "$SKILL_DIR/scripts/extract_records.py" list.html --url "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218" \
  --status 200 --fetched-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --format json     # 또는 --format csv

# RSS/Atom 도 같은 명령 (자동 감지)
python3 "$SKILL_DIR/scripts/extract_records.py" feed.xml --url "https://www.insnews.co.kr/rss/allArticle.xml"
```

출력 `{"page": 봉투, "records": [...], "stats": {...}}`. 행 = `source_url · link_raw · title · published · excerpt ·
page_final_url · page_fetched_at`. 계약: ① `excerpt` 는 원문 그대로이며 **페이지 텍스트의 부분문자열임을
코드가 검증**(아니면 `rejected_excerpt` 로 계수·제외) ② 날짜·링크가 없으면 빈 값 — 지어내지 않는다
(`javascript:` 링크는 `source_url=null` + `link_raw`) ③ 날짜 달린 목록이 없으면 레코드 0건 + 봉투
(`stats.reason=no_dated_list`) — 내비게이션을 목록으로 오인하지 않기 위함. 이 스크립트는 HTTP 를 하지 않는다.

**페이지 봉투(provenance)** — `extract_content --format json` 의 `provenance` 객체와 markdown 프론트매터
(`fetched_at`·`status`·`content_hash`)에도 같은 봉투가 실린다: `requested_url · final_url · status ·
fetched_at · encoding · fetch_phase · waf_profile · content_hash(sha256 of HTML) · extractor_version`.
파일·stdin 입력이면 fetch 사실이 없으므로 `status/fetched_at/encoding` 은 null.

### 동적 페이지 (JavaScript 렌더링) — v7.0.0에서 제거됨

JS 렌더링이 필요한 페이지(진성 CSR SPA)는 본 스킬 범위 밖이다. 브라우저 경로(`itda-web:aside-browser-mcp`)를 사용한다.
`--dynamic-only` 호출은 exit 4 + 안내 메시지로
fail-fast 한다. 참고: Next.js SSR 사이트는 SPA처럼 보여도 본문이 정적으로 내려오므로 먼저 정적 fetch를 시도한다.

### 출력 포맷

| 포맷 | 플래그 | 설명 |
|------|--------|------|
| HTML | `--format html` | 정제된 HTML (기본값) |
| Markdown | `--format markdown` | YAML frontmatter 포함 |
| JSON | `--format json` | 메타데이터 + 콘텐츠 구조화 |

## 특정 영역만 추출하기 (--selector)

본문 selector를 알고 있을 때 `--selector`로 자동 탐지를 우회하고 해당 요소만 추출한다.
노이즈(광고, 스크립트)는 selector 지정 시에도 자동 제거된다.

```bash
# 뉴스 기사 본문만 (nav/footer 제외)
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "https://example.com/article" --output page.html
python3 "$SKILL_DIR/scripts/extract_content.py" page.html --selector "article.post" --format markdown

# 표 데이터만 JSON으로 추출
python3 "$SKILL_DIR/scripts/extract_content.py" page.html --selector "table.price" --format json

# 매칭 0건 — exit code 1 (fallback 없음, 명시적 에러)
# python3 "$SKILL_DIR/scripts/extract_content.py" page.html --selector "div.does-not-exist"
# → Error: CSS selector 'div.does-not-exist' matched 0 elements in the document.

# 문법 오류 — exit code 2
# python3 "$SKILL_DIR/scripts/extract_content.py" page.html --selector "div::["
# → Error: Invalid CSS selector syntax: ...
```

| exit code | 의미 |
|-----------|------|
| 0 | 정상 추출 |
| 1 | selector 매칭 0건 또는 I/O·네트워크 오류 |
| 2 | selector 문법 오류 또는 잘못된 인자 |
| 4 | 정적 curl WAF 격자 소진(must_escalate) 또는 동적/SPA 요청(--dynamic-only·--adapter 등) → 브라우저 경로(itda-web:aside-browser-mcp) escalation |

## 인증 및 쿠키

```bash
# 개별 쿠키
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "URL" --cookie "session_id=abc123" --output page.html
# Cookie 헤더 통째로
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "URL" --cookie "session_id=abc123; token=xyz" --output page.html
```

쿠키는 원본 도메인에만 전송된다 (cross-domain redirect 시 자동 제거).

## SSL 에러 (macOS)

```bash
python3 "$SKILL_DIR/scripts/fetch_html.py" --url "URL" --output page.html --no-verify
```

## Script Reference

### fetch_html.py
```
CLI: fetch_html.py --url URL [--output FILE] [--timeout N] [--encoding CHARSET]
                   [--user-agent UA] [--header "Key: Value"] [--cookie "name=value"]
                   [--impersonate TARGET] [--max-attempts N] [--trace]
                   [--no-verify] [--allow-private]

Exit codes: 0=success, 1=network/HTTP error(404·timeout 등 종결), 2=invalid args or SSRF,
            4=WAF/challenge 격자 소진 → 에스컬레이트(아래 실패 게이트 참조)
SSRF 방지: http/https만 허용, private IP 차단, redirect 대상 검증
응답 크기 제한: 50MB (Content-Length 및 chunked transfer 양쪽 적용)
HTTP 백엔드: curl_cffi 단일 경로. 기본 --impersonate safari.
차단 대응: challenge 검증 후에만 WAF 프로파일 기반 격자(TLS/URL/Referer)를 시도.
--trace: 각 시도의 transform/impersonate/referer/verdict를 stderr JSON으로 출력.

실패 게이트(R6식 — exit 4 를 보면 사이트를 '도달 불가'로 선언하지 말 것):
  curl 격자가 WAF/차단으로 소진되면 exit 4 + stderr ⛔ NOT EXHAUSTED 배너를 출력하고,
  결과 dict 에 must_escalate / stop_reason(challenge·forbidden) / untried_routes /
  grid_exhausted / executed_attempts / content_is_challenge 를 담는다. exit 4 는
  '차단됨, 다음 경로로 에스컬레이트' 의미:
  → 브라우저 경로(itda-web:aside-browser-mcp).
  반대로 429(rate_limited)·401(auth_required)·404(not_found)·네트워크 에러는 must_escalate=False
  이며 exit 1 로 종결(브라우저로 가도 무익) — 429 는 백오프 후 재시도. extract_content 가 이
  신호를 읽어 자동으로 exit 4 를 surface 한다(에이전트가 프로즈를 추측할 필요 없음).
```

### extract_records.py

목록 HTML·RSS/Atom → 항목 레코드(JSON/CSV). 옵션: `--url`(상대 링크 해석·봉투) `--final-url` `--status`
`--fetched-at` `--encoding` `--fetch-phase` `--format json|csv` `--max-excerpt 300` `--min-title 8` `--output`.
exit 0 정상(0건 포함) · 1 입력/피드 파싱 오류. 상세는 위 "추출 레코드" 절.

### provenance.py

페이지 봉투 조립 공용 모듈(`build_provenance`·`provenance_from_fetch_extra`·`EXTRACTOR_VERSION`).
extract_content·extract_records 가 공유 — 두 표면의 봉투 키가 갈리지 않게 한다.

### extract_content.py
```
CLI: extract_content.py [INPUT_FILE] [--output FILE]
                        [--format html|markdown|json] [--url URL] [--lang CODE]
                        [--selector CSS]
     (reads stdin if INPUT_FILE omitted)
     --url과 INPUT_FILE은 상호 배타적 (동시 지정 시 에러)
     YouTube URL이 --url에 주어지면 v4.0.0부터 exit 2 + yt-dlp 안내 메시지 출력

--selector CSS            CSS selector로 추출 범위를 한정한다.
                          지정 시 자동 본문 탐지(ENTRY_POINT_SELECTORS)를 건너뛴다.
                          노이즈 제거(EXACT_REMOVE_SELECTORS, PARTIAL_REMOVE_PATTERNS)는 여전히 적용.
                          매칭 0건 → exit 1, 문법 오류(SelectorSyntaxError) → exit 2.

Exit codes: 0=success, 1=I/O or parse error or selector 매칭 0건,
            2=invalid args or selector 문법 오류,
            4=정적 curl WAF 격자 소진(must_escalate) 또는 동적/SPA 플래그 — 브라우저 경로 escalation

폐기 플래그 (호출 시 exit 4 + 브라우저 경로 안내):
  --dynamic-only            → v7.0.0 제거 (#1298). 브라우저 경로(itda-web:aside-browser-mcp) 사용.
  --adapter NAME            → 브라우저 경로(itda-web:aside-browser-mcp) 사용(네이버 부동산 등 SPA)
  --adapter-page KEY        → 위와 동일
  --from-capture FILE       → 브라우저 경로(`itda-web:aside-browser-mcp`) 사용
```

### clean_html.py
```
CLI: clean_html.py [INPUT_FILE] [--output FILE] [--max-depth N]
     (reads stdin if INPUT_FILE omitted)

Exit codes: 0=success, 1=parse error, 2=invalid args
제거: script, style, noscript, svg, iframe, HTML comments
유지 속성: id, class (전체), href (a), src+alt (img)
```

### url_validator.py
```
SSRF 방지 공통 모듈. 직접 CLI 실행하지 않음.
- http/https 스킴만 허용
- Private IP 차단 (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, ::1, fd00::/8 등)
- IPv4-mapped IPv6 (::ffff:127.0.0.1) 차단
- DNS 해석 후 IP 검증 (DNS rebinding 방어)
- --allow-private 플래그로 명시적 우회 가능
```

## Troubleshooting

fetch가 실패하거나 빈 응답을 반환할 때 레이어별 진단:

```bash
python3 "$SKILL_DIR/scripts/diagnose_url.py" https://example.com
```

SSRF → DNS → TCP → SSL → HTTP HEAD → robots.txt 를 분리 측정하여 어느 레이어가 문제인지 즉시 식별. 출력 JSON의 `diagnosis.code` 만 보면 됩니다.

진단 코드 예시:
- `dns_failure` — 호스트 이름 오타 / DNS 문제
- `ssrf_blocked` — private IP / loopback (보안 차단)
- `tcp_blocked` — 포트 차단 / 서버 다운
- `ssl_cert_invalid` — 인증서 만료 / CN 불일치
- `http_403_forbidden` — anti-bot — 브라우저 경로(`itda-web:aside-browser-mcp`) 시도
- `http_404_not_found` — URL 자체 잘못
- `http_429_rate_limit` — rate limit, 잠시 후 재시도
- `non_html_content` — PDF/이미지/binary, 별도 도구 필요
- `robots_denied` — robots.txt 가 fetch 금지
- `all_ok` — HTTP 레벨 정상, 다른 원인 (JS 렌더링 등) 점검 — 브라우저 경로(`itda-web:aside-browser-mcp`) 고려

## 추출 파이프라인 내부 구조

| 모듈 | 역할 |
|------|------|
| `web_selectors.py` | CSS selector 기반 노이즈 제거 패턴 |
| `scorer.py` | 콘텐츠 스코어링 (CJK 단어 수, 링크/이미지 밀도) |
| `metadata.py` | Schema.org LD+JSON, Open Graph, meta tag 추출 |
| `standardize.py` | 헤딩 정규화, 코드 블록, 이미지 lazy-load 해석 |
| `md_convert.py` | markdownify 래퍼 (테이블/코드/figure 커스텀 핸들러) |
| `url_validator.py` | SSRF 방지 URL 검증 |

retry 전략 (단어 수 부족 시 자동 완화):
- Pass 1: 전체 추출 (모든 selector 활성)
- Pass 2 (< 200단어): partial class/ID selector 제거 건너뜀
- Pass 3 (< 50단어): hidden element 제거도 건너뜀
- Pass 4 (< 50단어): content scoring도 건너뜀

## 보안

- **SSRF 방지**: 모든 fetch 진입점에서 URL scheme, private IP, DNS rebinding 검증
- **Cookie scoping**: cross-domain redirect 시 쿠키 자동 제거
- **Import 보호**: importlib 기반 모듈 로딩 + sys.modules 캐시 경로 검증
- **응답 제한**: 50MB body 크기 제한 (Content-Length + chunked 양쪽)

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 네이버 블로그 글·댓글 | itda-web:blog-reader |
| 키워드로 URL 찾기 | itda-web:web-search |
| JavaScript 렌더·로그인 세션·봇 차단 페이지 | 실제 브라우저 경로 — itda-web:aside-browser-mcp(Aside), 없으면 Claude in Chrome 등 |
| 사이트를 정찰해 등급·플레이북 만들기 | itda-web:web-scout |

## 마이그레이션

### v6.x → v7.0.0 (Lightpanda 동적 fetch 재제거)

v5.0.0에서 재흡수했던 Lightpanda 동적 fetch가 제거되었습니다 (#1298). Cowork 실측에서 세션당
151MB 바이너리 재설치가 반복되고, 핵심 대상인 진성 CSR SPA(wanted.co.kr·map.naver.com 등)에서
SIGILL 크래시가 100% 재현되어 재흡수 근거("가벼운 설치 + 안정 동작")가 무너졌습니다.

| 이전 (v5~v6) | v7.0.0 대체 |
|-------------|-------------|
| `extract_content.py --url URL --dynamic-only` | 브라우저 경로(`itda-web:aside-browser-mcp`) (exit 4 + 안내로 fail-fast) |
| `--dynamic-only --lp-markdown` | 브라우저 경로(`itda-web:aside-browser-mcp`) |
| `fetch_dynamic.py` / `install_lightpanda.py` | 삭제됨 |
| Anti-bot 차단 사이트 | **브라우저 경로(`itda-web:aside-browser-mcp`)** (escalation 자동 안내) |
| 네이버 부동산 등 SPA | **브라우저 경로(`itda-web:aside-browser-mcp`)** |

### v3.x → v4.0.0 (YouTube 자막 제거)

YouTube 자막 기능이 제거되었습니다. `yt-dlp` 한 줄로 동일한 결과를 얻을 수 있습니다.

| v3.x 호출 | v4.0.0 대체 |
|-----------|-------------|
| `python3 scripts/fetch_youtube.py --url URL` | `yt-dlp --write-auto-sub --sub-lang ko --skip-download <URL>` |
| `python3 scripts/extract_content.py --url <youtube_url>` | 동일 (exit 2 + yt-dlp 안내) |
| `--lang en` 영어 자막 | `yt-dlp --sub-lang en --skip-download <URL>` |

자세한 안내는 [GUIDE.md](GUIDE.md)의 "마이그레이션 안내 (v3 → v4)" 섹션 참조.

### v2.x → v3.0.0 (동적 fetch 제거) — 역사 기록

> 아래는 v3.0.0 당시 표다. 동적 fetch는 v5.0.0에서 Lightpanda로 부활했다가 **v7.0.0에서 재제거**되었다 — 현행 계약은 v3 과 동일(브라우저 경로 위임).

| v2.x 호출 | v3.0.0 당시 대체 (현재는 일부 부활) |
|-----------|-------------|
| `fetch_dynamic.py --url URL` | 브라우저 경로(`itda-web:aside-browser-mcp`) (v5~v6 한시 부활 후 v7.0.0 재제거) |
| `--adapter naver_land` (단지/매물) | 브라우저 경로(`itda-web:aside-browser-mcp`) |
| `--from-capture <jsonl>` | 브라우저 경로(`itda-web:aside-browser-mcp`) |
| `extract_content.py --dynamic-only` | 브라우저 경로(`itda-web:aside-browser-mcp`) (v5~v6 한시 부활 후 v7.0.0 재제거) |

호출 시 exit code 4 + stderr 안내 메시지로 마이그레이션 경로가 표시됩니다.
