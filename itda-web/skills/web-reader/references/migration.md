# web-reader 마이그레이션 안내 (개발자·기존 사용자용)

> 이 문서는 v2.x ~ v8.x 마이그레이션이 필요한 기존 사용자·외부 호출자용 내부 문서입니다. 일반 사용자는 `../GUIDE.md`만 보면 됩니다. 스킬 호출 시 자동 로드되지 않습니다.

---

## v8.0 → v8.1 (상태·Location 은 저장 메타 파일로, itda-hyve 0.12.0 필요)

`plan.py` 가 내는 `call` 에 `save_meta: true` 가 붙고, `plan.py next` 는 `--state` 하나만 받는다. 상태 코드·Location·Content-Type 은
itda-hyve 가 본문 옆에 쓴 `<save_as>.meta.json` 에서 읽는다(itda-hyve 0.12.0 `save_meta`, itda-work/itda-hyve#36). 같은 판에서 itda-hyve 가
사설·로컬 목적지를 연결 직전 IP 로 기본 거부한다(#33).

| v8.0 | v8.1 |
|---|---|
| `plan.py next --state S --status N [--location L] [--content-type CT]` | `plan.py next --state S` (세 인자는 없어졌다 — 주면 인자 오류 exit 2) |
| 도구 실패 `--hyve-error <code>` | 그대로. 출력의 `on_error` 명령에 채운다. `private_destination` 은 exit 2 로 멈추고 재시도하지 않는다 |
| 메타 파일 없음 | `hyve_outdated`(exit 2) — itda-hyve 0.12.0 미만이거나 `save_meta` 를 뺀 호출 |
| 메타의 최종 URL 이 호출 URL 과 다름 | `call_modified`(exit 2) — `follow_redirects: false` 를 바꾼 호출(기대값은 호출 URL 을 itda-hyve(Go)가 보내는 표현 — 한글 경로의 %XX 는 같은 곳, `%3B` 와 `;` 는 다른 곳) |
| — | `path_reencoded`(exit 4) — 한글과 인코딩된 예약문자(`%2F`·`%3B` 등)가 한 경로에 있어 itda-hyve 가 그것을 풀어 보내게 됨(호출 전에 멈춤). 브라우저 경로 |

## v7 → v8 (요청은 itda-hyve, 스크립트는 저장 파일 가공만)

web-reader 8.0.0 부터 스크립트가 네트워크를 열지 않는다(itda-work/skills#46, 규칙 `cowork-network-via-hyve`). Cowork 가 클라우드 VM 으로
옮겨 스크립트의 HTTP 가 간헐적으로 막히기 때문이다. 요청은 사용자 PC 의 itda-hyve `http_request` 가 보내고, `plan.py` 가 호출을 한 걸음씩
계획한다. 사용자 결정(2026-10-01) D1~D5 는 설계 권고안 그대로다.

| v7 호출 | v8.0.0 대체 |
|---|---|
| `fetch_html.py --url U --output page.html` | `plan.py start --url U --save-dir …` → `call` 을 itda-hyve `http_request` 로 → `plan.py next --state …` 되풀이(8.0 은 `--status …`) → `done` 의 `extract` 명령 |
| `extract_content.py --url U` (가져오기+추출) | 위 흐름 뒤 `extract_content.py <저장 파일> --url U --final-url … --status … --content-type …` (`done` 이 채워 준다) |
| `clean_html.py page.html` | 그대로 되지만 입력은 itda-hyve 원 바이트다 — `--content-type`·`--status` 를 같이 넘긴다(EUC-KR 판정·2xx 아님 거부·비HTML exit 3) |
| `extract_content.py page.html`(파일만) | 그대로 — `--url` 은 이제 **파일과 함께** 쓰는 기준 URL 이다(v7 은 파일과 동시 지정 금지) |
| `fetch_html.py … \| extract_content.py --url U` (파이프) | 파이프는 stdin 바이트로 그대로 되지만 가져오는 쪽이 없다 — 위 흐름을 쓴다 |
| `--impersonate`·`--max-attempts`·`--trace`(curl_cffi 지문·WAF 격자, D2) | 삭제. 1회 요청, 본문이 챌린지면 exit 4 → 브라우저 경로 |
| `--cookie`(쿠키 인증, D3) | 삭제. 로그인 페이지는 브라우저 경로 |
| `--header`·`--user-agent` | 삭제. 요청 JSON 에 헤더를 싣지 않는다(itda-hyve 기본 UA `Mozilla/5.0`) |
| `--no-verify` | itda-hyve `insecure_tls: true`(사용자 확인 뒤). handshake 실패는 `plan.py` 가 `legacy_tls` 로 1회 다시 계획 |
| `--allow-private` | 삭제. 사설·로컬 목적지는 늘 거부(D4) |
| `--encoding CHARSET` | 삭제. `--content-type`(도구 응답 값)의 charset → BOM → meta → UTF-8 → CP949 |
| `--static-only`·`--no-fallback`·`--min-text-length`·`--min-meaningful-tags`·`--lang` | 삭제(인자 오류 exit 2) |
| `diagnose_url.py URL` | 삭제. itda-hyve 실패 코드·상태 코드 표(SKILL.md) |
| `integration/quality_check.py`(실사이트 40곳) | 삭제. 오프라인 픽스처 회귀 |
| `extract_records.py --encoding --fetch-phase --content-sha256` | 삭제. `--content-type` 추가, 봉투 `encoding`·`content_hash`(원 바이트) 는 스크립트가 계산 |
| 봉투 `fetch_phase: static·degraded_static` · `waf_profile` 값 | `fetch_phase: hyve`(도구 응답 값을 넘김)·`input`, `waf_profile` 은 늘 null, `content_type` 추가 |
| Python API `fetch_pipeline.fetch_with_fallback`·`fetch_html.fetch_url`·`url_validator.validate_url(allow_private=…)` | 삭제 · 삭제 · `url_validator.check_url(url)`(DNS 해석 없음) |

**새로 생긴 멈춤** — robots.txt(`User-agent: *`)가 막는 경로는 받지 않는다(exit 5, D1). 네이버 뉴스(`n.news.naver.com`)는 `*` 전면 불허라
v8 에서 받지 않는다 — 추출기의 네이버 뉴스 셀렉터·회귀 픽스처는 **사용자가 가져온 저장 파일**을 읽을 때를 위해 남긴다.

**형제 스킬** — blog-reader 는 v7 의 `fetch_html.py` 를 subprocess 로 불렀다. 네이버 블로그 robots 의 `User-agent: *` 가
목록·댓글·전체 검색을 막아 2026-10-01 스킬째 제거했다(사용자 결정 — 네이버 블로그는 브라우저 경로 `itda-web:aside-browser-mcp`). web-scout 도 `fetch_html`·`url_validator.validate_url` 을 불러 썼다(같은 날 W15 에서 저장소째 제거).

---

## v6 → v7 (Lightpanda 동적 fetch 재제거)

web-reader v7.0.0에서 Lightpanda 동적 fetch가 **다시 제거**되었습니다 (#1298). Cowork 실측 근거:

- 설치 경로가 세션 홈(휘발 영역)이라 **세션마다 151MB / 약 33초 재설치**가 반복됨
- 핵심 대상인 진성 CSR SPA(wanted.co.kr·map.naver.com·musinsa.com)에서 lightpanda 0.3.6(aarch64-linux)이 **SIGILL 크래시 100% 재현** — v5 재흡수 근거("가벼운 설치 + 안정 동작")가 성립하지 않음

| v5~v6 호출 | v7.0.0 대체 |
|---|---|
| `extract_content.py --url URL --dynamic-only` | 브라우저 경로(`itda-web:aside-browser-mcp`) (호출 시 exit 4 + 안내) |
| `--dynamic-only --lp-markdown` / `--no-auto-install` | 플래그 삭제 |
| `fetch_dynamic.py` / `install_lightpanda.py` | 스크립트 삭제 |
| `$ITDA_LIGHTPANDA_DIR` / `$ITDA_LIGHTPANDA_BIN` | 더 이상 읽지 않음 |

아래 v4→v5 절은 역사 기록으로만 보존합니다.

## v4 → v5 (Lightpanda로 동적 fetch 부활)

web-reader v5.0.0에서 **JavaScript 동적 fetch가 부활**했습니다. LIGHTEN(v3.0.0)에서 당시 hyve 앱 MCP 로 위임한 이유는 Playwright/Chromium 설치(~200MB) 부담과 잦은 실패였는데, **Lightpanda**(Zig+V8 단일 바이너리, 65–135MB, 24MB 메모리, 100ms 부팅)가 그 제약을 해소했기 때문입니다.

### 우선순위

Lightpanda는 stdio MCP 서버 모드를 내장합니다. Claude Desktop의 `claude_desktop_config.json`에 lightpanda를 등록해 두면 Cowork에서도 자동 활성화되어 Claude가 MCP 도구로 직접 호출 가능합니다.

따라서 동적 fetch 요청 처리 우선순위:

1. **`mcp__lightpanda__*` 도구가 Claude 세션에 노출된 환경**: MCP 도구 직접 호출 (web-reader 활성화 안 함)
2. **MCP 도구 미노출 환경 / 정제 파이프라인 필요**: 본 스킬의 `--dynamic-only` 사용

> **Lightpanda 설치 및 MCP 등록은 사용자 영역**입니다. 본 스킬은 등록 절차 안내·실행에 관여하지 않습니다 (정책). 미설치 시 `--dynamic-only` 호출은 exit 3 + 플랫폼별 설치 안내 메시지만 출력합니다.

### 설치 (v6.1.0+: 관리 스크립트)

web-reader v6.1.0부터 `install_lightpanda.py`로 설치합니다(플랫폼/아키텍처 자동 감지, 표준 라이브러리만 사용, 신규 의존성 0). **동적 fetch 요청 시 미설치면 자동 설치**되므로 보통 수동 실행은 불필요합니다.

```bash
# 최신 안정 버전 — 없으면 설치, 있으면 skip (멱등)
python3 scripts/install_lightpanda.py

# 세션 간 재사용을 위해 영속 경로 지정 (권장) — 검출·설치 위치 둘 다 이 경로
# 반드시 절대경로로 — 상대경로는 cwd가 바뀌면 검출과 어긋나 재사용이 깨진다.
export ITDA_LIGHTPANDA_DIR="$(pwd)/tools"
python3 scripts/install_lightpanda.py

# 특정 버전 / 다운그레이드
python3 scripts/install_lightpanda.py --version 0.3.0

# 업데이트 (최신 안정으로 덮어쓰기)
python3 scripts/install_lightpanda.py --version latest --force

# Windows: 네이티브 미지원 — WSL2 내부(Linux)에서 위 명령 실행, 또는 브라우저 경로(itda-web:aside-browser-mcp)
```

최신 안정 해석은 `/releases/latest`(rolling `nightly` 반환)를 쓰지 않고, semver 태그(`v?X.Y.Z`) 중 prerelease/draft를 제외한 최고 버전을 선택합니다(nightly는 prerelease=false여도 semver가 아니라 제외). 릴리즈가 checksum을 제공하지 않아 `lightpanda version` 실행으로 무결성을 검증하며, 검증 통과 시에만 기존 바이너리를 원자적으로 교체합니다(손상 다운로드가 멀쩡한 바이너리를 덮어쓰지 않음).

검출 우선순위 (v6.1.0): `--lightpanda-bin` → `$ITDA_LIGHTPANDA_BIN` → `$ITDA_LIGHTPANDA_DIR/lightpanda` → `$PATH` → `~/.itda-skills/bin/lightpanda`. (Cowork 세션에서 마운트와 어긋나 헛다리 + 세션 휘발하던 cwd 상대 추측 경로 `./mnt/...`·`./.itda-skills/...`는 제거되었습니다.)

### CLI 사용 (fallback / 자동화 스크립트용)

```bash
# 1) 정제 파이프라인 통과 (YAML frontmatter + 본문 추출)
python3 scripts/extract_content.py --url "https://news.naver.com/section/100" --dynamic-only --format markdown

# 2) Lightpanda 자체 markdown 출력 (정제 우회, 한국 미디어 권장)
python3 scripts/extract_content.py --url "https://news.naver.com/" --dynamic-only --lp-markdown

# 3) 세부 옵션이 필요할 때 fetch_dynamic.py 직접 사용
python3 scripts/fetch_dynamic.py --url "URL" \
  --wait-selector "article" --terminate-ms 20000 --strip-mode js,css
```

### 도구 선택 매트릭스

| 케이스 | 도구 |
|--------|------|
| 한국 미디어/뉴스/블로그 SPA | web-reader `--dynamic-only` (1초대) |
| 정부 SPA (gov.kr, nts.go.kr 등) | web-reader `--dynamic-only` |
| 영문 SPA (github, vercel 등) | web-reader `--dynamic-only` |
| Akamai/Cloudflare 봇 차단 (coupang 등) | 실제 브라우저 경로(`itda-web:aside-browser-mcp` 등 — 통과 보장 없음) |
| SNS 인증 후 데이터 (인스타·X) | 브라우저 경로(`itda-web:aside-browser-mcp`) (인증 흐름) |
| 네이버 부동산 단지/매물 | 브라우저 경로(`itda-web:aside-browser-mcp`) |
| Windows 네이티브 환경 | 브라우저 경로(`itda-web:aside-browser-mcp`) (Lightpanda 는 WSL2 필수) |

web-reader가 bot challenge를 감지하면 exit 4 + 브라우저 경로 escalation 안내 메시지를 stderr로 출력합니다.

### 검증 매트릭스 (2026-05-13)

22개 URL 직접 측정 결과:
- 일반 사이트 (한국 미디어·블로그·정부·영문 SPA): **20/20 (100%) 성공**, 평균 1.2초
- Anti-bot/SNS: 2/2 실패 (예상대로 — escalation 권장)

자세한 데이터는 SPEC-WEBREADER-DYNAMIC-LIGHTPANDA-001 §1.2 참조.

---

## v3 → v4 (YouTube 자막 추출 제거)

web-reader v4.0.0에서 **YouTube 자막 추출 기능이 제거**되었습니다. 직접 비교 실험에서 `yt-dlp` 한 줄로 동일한 결과를 얻을 수 있고 Claude가 후처리까지 즉시 수행함을 확인했기 때문입니다. 이중 유지보수 비용이 사용자 체감 가치를 초과해 제거를 결정했습니다.

### 대체 방법

```bash
# 한국어 자동자막 + 메타데이터 (대부분의 경우 충분)
yt-dlp --write-auto-sub --sub-lang ko --skip-download \
  -o "%(id)s.%(ext)s" "https://www.youtube.com/watch?v=VIDEO_ID"

# 영어 자막
yt-dlp --write-auto-sub --sub-lang en --skip-download "<URL>"

# 자막 + 메타데이터 JSON
yt-dlp --write-auto-sub --sub-lang ko --write-info-json --skip-download "<URL>"
```

다운로드된 `.vtt` 파일을 Claude에 그대로 첨부하거나 단순히 Claude에게 "이 유튜브 자막 받아서 정리해줘"라고 요청하면 yt-dlp 호출과 VTT 파싱을 알아서 수행합니다.

### `fetch_youtube.py`를 직접 호출하던 스크립트가 있다면

| v3.x 호출 | v4.0.0 대체 |
|-----------|-------------|
| `python3 scripts/fetch_youtube.py --url URL` | `yt-dlp --write-auto-sub --sub-lang ko --skip-download <URL>` |
| `python3 scripts/extract_content.py --url <youtube_url>` | exit 2 + 안내 메시지 — 호출 측에서 yt-dlp로 전환 필요 |
| Python: `from fetch_youtube import fetch_youtube` | `subprocess.run(["yt-dlp", ...])` 또는 `yt-dlp` 라이브러리 |

`youtube-transcript-api` 의존성도 함께 제거되었습니다.

### yt-dlp 설치

```bash
pipx install yt-dlp           # 권장
uv tool install yt-dlp
brew install yt-dlp           # macOS
```

---

## v2 → v3 (동적 fetch 인프라 제거)

web-reader v3.0.0에서는 동적 fetch 인프라(Playwright/Chromium, SPA 어댑터, capture 처리)가 일체 제거되었습니다. 해당 use case는 당시 hyve 앱 MCP 로 옮겼고, 지금은 브라우저 경로(`itda-web:aside-browser-mcp`)가 맡습니다. v5.0.0에서 Lightpanda 기반으로 일부 부활했으나(위 v4→v5 참조), v2.x의 어댑터·capture·stealth 같은 고급 기능은 브라우저 경로 영역입니다.

### 변경 사항 요약

| v2.x (web-reader 내부) | v3.0.0+ 대체 |
|------------------------|------------------------|
| `fetch_dynamic.py --url URL` | 브라우저 경로(`itda-web:aside-browser-mcp`) 또는 v5.0+ `--dynamic-only` |
| `fetch_dynamic.py --url URL --stealth` | 실제 브라우저 경로(`itda-web:aside-browser-mcp` 등 — stealth 기능 없음) |
| `fetch_dynamic.py --adapter naver_land --adapter-page complexes` | 브라우저 경로(`itda-web:aside-browser-mcp`) |
| `fetch_dynamic.py --adapter naver_land --adapter-page complex_detail` | 브라우저 경로(`itda-web:aside-browser-mcp`) (단지 + 매물 XHR API 캡처) |
| `extract_content.py --from-capture <jsonl> --adapter naver_land` | 브라우저 경로(`itda-web:aside-browser-mcp`) (리뷰/단지 XHR 캡처 후 파싱) |
| `profile_manager.py warmup <name>` | 브라우저가 로그인 세션을 쥐므로 개별 명령 불필요 (`itda-web:aside-browser-mcp`) |

### Before / After 예시 (v2 → v3)

**SPA 페이지 동적 렌더링**

Before (v2.x):
```bash
python3 scripts/fetch_dynamic.py --url "https://example.com/spa-page" --stealth --output page.html
python3 scripts/extract_content.py page.html --format markdown
```

After (v3.0.0+):
```
aside 브라우저로 https://example.com/spa-page 페이지 마크다운으로 가져와줘
```

**네이버 부동산 단지 + 매물 목록**

Before (v2.x):
```bash
python3 scripts/fetch_dynamic.py --adapter naver_land --adapter-page complex_detail \
  --url "https://new.land.naver.com/complexes/104917" \
  --capture-api "^https://new\.land\.naver\.com/api/(complexes|articles)" \
  --stealth
python3 scripts/extract_content.py --from-capture capture.jsonl --adapter naver_land --format json
```

After (v3.0.0+):
```
aside 브라우저로 104917 단지 페이지 열고 매물 목록을 JSON으로 정리해줘
```

### 호환성 (v3.0.0+)

- 정적 fetch / 쿠키 fetch / `--selector` 지정 추출은 그대로 동작
- v2.x `--dynamic-only`, `--adapter`, `--adapter-page`, `--from-capture` 호출은 **exit code 4** + stderr에 브라우저 경로 안내
- `fetch_with_fallback()` Python API는 `dynamic_only=True` 호출 시 `ValueError`

### 브라우저 경로가 없는 환경

브라우저 MCP(aside 등)가 연결되지 않은 환경에서는 v2.x의 고급 동적 fetch use case가 작동하지 않습니다. 정적 fetch / 쿠키 fetch는 web-reader 그대로 사용 가능합니다.

---

## 개발자용 CLI 레퍼런스

자동화 스크립트·파이프라인에서 직접 호출할 때:

### 기본 기사 추출

```bash
# macOS/Linux — 파이프라인 한 줄
python3 scripts/fetch_html.py --url "URL" | \
  python3 scripts/extract_content.py --format markdown --url "URL"

# Windows
py -3 scripts/fetch_html.py --url "URL" --output page.html
py -3 scripts/extract_content.py page.html --format markdown
```

### 쿠키 인증

```bash
python3 scripts/fetch_html.py --url "URL" --cookie "session_id=abc; token=xyz" --output page.html
python3 scripts/extract_content.py page.html --format markdown
```

### 사전 진단

```bash
python3 scripts/diagnose_url.py "URL"
# SSRF → DNS → TCP → SSL → HTTP HEAD → robots.txt 레이어 한 번에 점검
```

### 동적 fetch (v5.0+, Lightpanda 필요)

```bash
# 정제 파이프라인
python3 scripts/extract_content.py --url "URL" --dynamic-only --format markdown

# Lightpanda 원본 markdown
python3 scripts/extract_content.py --url "URL" --dynamic-only --lp-markdown
```

### Exit Code

| Code | 의미 |
|------|------|
| 0 | 성공 |
| 1 | selector 매칭 0건 또는 Lightpanda runtime 오류 |
| 2 | selector 문법 오류 또는 잘못된 인자 |
| 3 | Lightpanda 바이너리 미설치 (stderr에 설치 안내) |
| 4 | Bot challenge 감지(Access Denied/Cloudflare) 또는 SPA 어댑터 요청 → 브라우저 경로 escalation |

자세한 옵션과 검증된 사이트 카탈로그는 `../GUIDE.md` 본문 참조.
