---
name: web-search
description: >
  여러 검색엔진으로 웹을 한 번에 검색해 정규화된 결과 목록(제목·URL·발췌)을
  돌려주는 스킬입니다.
  "파이썬 입문 자료 검색해줘", "AI 규제 관련 최신 기사 찾아줘",
  "경쟁사 가격 정책 정보 모아줘"처럼 말하면 됩니다.
  1회성 정보 탐색과 출처 URL 수집이 목적이며, 시장조사 보고서·팩트체크·본문 추출은
  다루지 않습니다.
  [책임 경계] 본 스킬은 검색엔진 결과 목록(제목·URL·발췌) 수집 전담 — 찾은 URL 의 본문 추출은 itda-web:web-reader 이며, 시장조사 보고서·팩트체크는 다루지 않습니다.
license: Apache-2.0
compatibility: "Claude Cowork & Code. Python 3.10+. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "[질의어] [--engine auto|tavily|naver|serper|exa] [--count 5] [--naver-type web|news|blog]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "search"
  version: "0.3.0"
  created_at: "2026-06-09"
  updated_at: "2026-10-01"
  tags: "search, web search, query, multi engine, tavily, serper, naver, exa"
---

# web-search

질의어 하나로 여러 검색엔진을 한 번에 호출해, 출처가 다른 결과를 정규화된 목록으로
돌려주는 조회 전용 스킬. 기본 웹 검색이 한 곳만 긁어 오는 한계를 보완해 인덱스 출처를
다양화한다(Tavily · Serper(Google) · Naver 국내 · Exa 시맨틱).

> Python 표준 라이브러리만 사용 — 추가 의존성 없음. 스크립트는 네트워크를 하지 않는다.

## 흐름 — 요청은 itda-hyve, 계획과 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다.
스크립트는 네트워크를 하지 않는다 — `plan` 이 엔진마다 보낼 `http_request` 인자를 내고, itda-hyve 가 `save_as` 로
저장한 응답을 `collect --input` 이 읽어 오류 판정·정규화·병합만 한다. URL·본문·헤더·저장 이름은 스크립트가 정한다 —
**호출 JSON 을 손으로 짓지 않는다.** 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한
[references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan(엔진 고르기·호출 수 알림) → 엔진마다 http_request 1회(차례로, 실패면 실패 자리) → collect --input(전부) → 결과
```

API 키는 사용자가 itda-hyve GUI **시크릿 탭**에 등록해 둔 것을 **이름으로만** 가리킨다(`plan` 이 준 헤더에 `{{secret:…}}` 가 들어 있다).
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 키가 등록돼 있는지 미리 알 방법은 없다 — **호출해 보고 `secret_missing` 이면 그 엔진은 키가 없다.**

## 엔진 · 시크릿 이름 · 무료 한도 · 요금 (2026-06 기준, 변동 가능)

| 엔진 (유형) | itda-hyve 시크릿 이름 | `auto` | 무료 한도 | 유료(대략) | 발급처 |
|---|---|---|---|---|---|
| **Tavily** (범용 raw) | `TAVILY_API_KEY` | ✅ | 월 1,000 크레딧, 카드 불요 | PAYG $0.008/크레딧 | [app.tavily.com](https://app.tavily.com) |
| **Naver** (국내 web/news/blog) | `NAVER_CLIENT_ID` · `NAVER_CLIENT_SECRET` | ✅ | 일 25,000건, 무료 | — | [developers.naver.com](https://developers.naver.com) |
| **Serper** ⚠️회색지대 (Google SERP) | `SERPER_API_KEY` | ✅ | 가입 시 2,500 크레딧 **한 번**(카드 불요), 그 뒤는 선불 충전 — 충전하지 않으면 과금 없음 | 1,000쿼리당 약 $0.3~1 · 결과 11개 이상은 2크레딧(2차 출처) | [serper.dev](https://serper.dev) |
| **Exa** (시맨틱) 💰 | `EXA_API_KEY` | — | 월 1,000 요청 | 검색 $7/1k (결과 10개 초과 +$1/1k) | [dashboard.exa.ai](https://dashboard.exa.ai) |

- **`--engine auto`(기본)는 자동 과금이 없는 엔진 3종**(tavily·naver·serper)만 고른다. 💰 유료 엔진(exa)은 `--engines`/`--engine` 으로 지목했을 때만 부른다(비용 가드 — 키가 있으면 호출이 곧 과금이다).
- **유료 엔진 확인 규칙(하나로 정한다)**: 사용자가 **이름으로 지목**했으면("Exa 로 찾아줘") 과금된다는 것을 한 줄 알리고 그대로 보낸다 — 다시 묻지 않는다. **Claude 가 유료 엔진을 쓰자고 제안**할 때만 먼저 묻고 동의를 받는다.
- 키 등록 안내는 한 가지다: "itda-hyve GUI 시크릿 탭에 `<이름>` 으로 등록". **무료로 시작**: `TAVILY_API_KEY` + `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`.
  네이버 키 이름은 blog-seo·eatery-trend 와 같지만, 그 두 스킬이 itda-hyve 로 옮기기 전까지는 **저장소가 다르다** — 이 스킬은 시크릿 탭만 읽으므로 설정 파일 `env` 에만 넣어 둔 네이버 키는 여기서 보이지 않는다. 시크릿 탭에 따로 등록한다.
- **⚠️ Naver 이관 고지 (2026-07 약관 변경)**: 개발자센터 검색 API는 네이버클라우드(NCP) **NAVER API HUB**로 이관된다. 2026-07-30 이후 개발자센터 신규 이용 신청 불가 — 신규 사용자는 NAVER API HUB에서 발급하도록 안내한다. 기존 키는 **2027-06-30까지** 현행대로 동작한다.
- 요금·한도는 변동되므로 각 공식 페이지를 정본으로 본다(위 수치는 2026-06 기준).
- **⚠️ Serper(회색지대 — 보조용)**: Serper는 Google 공식 API가 아니라 공개 SERP를 스크래핑하는 제3자다. Google이 **동종 SerpApi를 DMCA 제소(2025-12-19)** 하고 **SearchGuard(2025-01)로 스크래퍼를 기술 차단** 중이라 카테고리 전반에 **중단·품질저하 가능성**이 있다. 견고성이 필요하면 자체 인덱스(Tavily·Exa)·공식 API(Naver)를 우선하고, Serper는 보조로 쓴다(키가 없으면 `secret_missing` 으로 빠진다).
- **미지원(의도적 제외)**: Perplexity — Sonar Chat Completions 지원이 2026-09-27 에 끝났다(0.3.0 에서 뺐다. 필요해지면 Agent API 로 다시 넣는다). Google Custom Search JSON API — 공식 문서가 "closed to new customers" + 2027-01-01 종료 명시. Bing Web Search API — 2025-08-11 완전 은퇴.

## 엔진 선택 가이드 (언제 어떤 엔진 — Claude 라우팅 지침)

질의 성격에 맞는 엔진을 고른다. 사용자가 엔진을 지정하면 그대로 따른다. (강점 근거: AN Score 에이전트 검색 벤치마크 2026 — Exa 8.7·Tavily 8.6·Serper 8.0, 그리고 키워드 vs 시맨틱 검색 특성.)

| 상황 / 질의 유형 | 권장 | 근거 |
|---|---|---|
| **한국어·국내** (뉴스·블로그·맛집·지역·카페·지식iN) | `naver` (필요시 `--naver-type news\|blog`) | 국내 색인, 글로벌 엔진이 못 메우는 영역 |
| **광범위·인기·최신** ("Google에 뭐가 뜨나") | `serper`(⚠️회색지대) 또는 `auto` | 실제 Google SERP·신선한 색인 |
| **의미로 탐색** ("이것과 비슷한 글", 개념·리서치, 키워드가 애매) | `exa` 💰 | 신경망 시맨틱 — 단어 안 겹쳐도 의미로 매칭 |
| **범용 웹 검색 / RAG / 에이전트 기본 raw** | `tavily` | 에이전트 특화·정제된 결과 |
| **정확한 명칭·고유명사·코드·식별자** (exact 매칭) | `serper`/`tavily`/`naver` (키워드형) | 시맨틱(`exa`)은 exact 매칭이 약함 |
| **출처 다양성·교차검증** (어디가 강할지 불확실) | `auto` (무료 3종 fan-out) | 겹치지 않는 인덱스 병합 |

"바로 답 + 요약" 이 필요하면 이 스킬의 결과(URL·발췌)를 읽고 Claude 가 요약한다 — 요약 답변을 주는 엔진은 없다(`answer` 는 늘 `null`).

**라우팅 규칙(Claude):**
1. 사용자가 엔진을 지정 → 그대로(유료면 위 확인 규칙대로 한 줄 알린다).
2. 한국어·국내 주제 → `naver` 우선(또는 `auto` 에 포함).
3. "비슷한 것/개념" → `exa` 가 맞지만 유료라, 사용자가 지목하지 않았으면 먼저 묻는다.
4. 일반·불확실 → `auto`. 견고성 우선이면 회색지대(serper) 제외: `--engines tavily,naver`.
5. **이 대화에서 한 번 `SECRET_MISSING` 이 난 엔진은 다음 검색부터 `--engines` 로 뺀다** — 키 없는 엔진을 검색마다 다시 부르고
   실패 자리를 쓰지 않는다. 사용자가 "등록했다" 고 하면 다시 넣는다.

## 1단계 — 호출 계획 (네트워크 불요)

**먼저** 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 `SKILL_DIR` 에 넣고 아래 블록을 실행한다 — 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다(후보가 여럿이면 멈춘다).

```bash
# SKILL_DIR 확정(skill-dir-resolution) — 스킬을 불러올 때 받은 base directory 를 먼저 SKILL_DIR="그 경로" 로 넣는다(항상)
# 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다 — SKILL.md 가 있는 후보가 하나일 때만 받고 아니면 멈춘다
SKILL_DIR=$(sh -c '
S=$1 P=$2 H=${5:-$HOME/.claude}
ok() { d=${1%/}; [ "${d##*/}" = "$S" ] && [ -f "$d/SKILL.md" ] && (cd "$d" && pwd -P); }
[ -n "$3" ] && { ok "$3" && exit; d=${3%/}; [ "${d##*/}" = "$S" ] && echo "SKILL_DIR 무시: $3 에 SKILL.md 가 없다" >&2; }
[ -n "$4" ] && { ok "$4/skills/$S" && exit; echo "CLAUDE_PLUGIN_ROOT 무시: $4/skills/$S 에 SKILL.md 가 없다" >&2; }
c=$(for d in "$H"/plugins/synced/*/"$P"/skills/"$S" "$H"/plugins/synced/*/"$P"~*/skills/"$S" "$H"/plugins/cache/*/"$P"/*/skills/"$S" \
    /root/.claude/plugins/synced/*/"$P"/skills/"$S" /root/.claude/plugins/synced/*/"$P"~*/skills/"$S" \
    /sessions/*/mnt/.remote-plugins/*/skills/"$S" /sessions/*/mnt/.claude/skills/"$S"; do ok "$d"; done | sort -u)
[ "$(printf "%s\n" "$c" | grep -c .)" -gt 1 ] && { printf "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다:\n%s\n" "$c" >&2; exit 1; }
printf "%s\n" "$c"' _ web-search itda-web "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"

python3 "$SKILL_DIR/scripts/web_search.py" plan "2026년 최저임금"                              # auto = tavily·naver·serper
python3 "$SKILL_DIR/scripts/web_search.py" plan "반도체 수출 동향" --engine naver --naver-type news
python3 "$SKILL_DIR/scripts/web_search.py" plan "python async 입문" --engines tavily,serper --count 8
```

Windows(PowerShell):

```powershell
# Windows
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'web-search'; $P = 'itda-web'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
py -3 "$env:SKILL_DIR\scripts\web_search.py" "검색어"
```

출력 `calls[i]` 는 엔진 하나다 — `engine`·`paid`·`secrets`(그 엔진의 시크릿 이름)·`args`(`http_request` 인자 그대로).
`call_count` 가 부를 호출 수다. **보내기 전에 "엔진 N개를 차례로 부른다" 를 알린다.** `paid_engines` 가 비어 있지 않으면
위 유료 엔진 확인 규칙을 따른다.

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--engine` | `auto`(무료 3종) · `tavily` · `naver` · `serper` · `exa` | `auto` |
| `--engines` | 쉼표로 구분한 엔진 목록(순서 = 결과 섞는 순서, 같은 엔진 두 번은 오류) | — |
| `--count` | 결과 수(엔진마다 이만큼 요청하고 — Tavily·Serper·Exa 20, Naver 100 이 상한 — 합친 뒤 이만큼 남긴다) | 5 |
| `--naver-type` | 네이버 검색 종류 `web`·`news`·`blog` | `web` |

## 2단계 — itda-hyve 의 http_request 로 받기 (엔진마다 1회, 차례로)

`calls[i].args` 에 **`save_dir`(Cowork 연결 폴더의 호스트 경로)** 만 더해 **그대로** 보낸다. POST 는 itda-hyve `batch` 로 묶을 수 없어
엔진마다 `http_request` 를 한 번씩 부른다(네이버 GET 도 한 질의 1회라 같은 방식으로 부른다).
예 — `plan "2026년 최저임금"` 의 세 호출:

```json
{"url": "https://api.tavily.com/search", "method": "POST",
 "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{secret:TAVILY_API_KEY}}"},
 "body": "{\"query\":\"2026년 최저임금\",\"max_results\":5,\"search_depth\":\"basic\",\"include_answer\":false}",
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "web-search/tavily-72b10d52.json"}
```

```json
{"url": "https://openapi.naver.com/v1/search/webkr.json",
 "params": {"query": "2026년 최저임금", "display": "5", "start": "1"},
 "headers": {"X-Naver-Client-Id": "{{secret:NAVER_CLIENT_ID}}", "X-Naver-Client-Secret": "{{secret:NAVER_CLIENT_SECRET}}"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "web-search/naver-93ad7cea.json"}
```

```json
{"url": "https://google.serper.dev/search", "method": "POST",
 "headers": {"Content-Type": "application/json", "X-API-KEY": "{{secret:SERPER_API_KEY}}"},
 "body": "{\"q\":\"2026년 최저임금\",\"num\":5,\"gl\":\"kr\",\"hl\":\"ko\"}",
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "web-search/serper-7c7c67e5.json"}
```

유료 엔진을 지목했을 때(`--engines …,exa`)의 호출:

```json
{"url": "https://api.exa.ai/search", "method": "POST",
 "headers": {"Content-Type": "application/json", "x-api-key": "{{secret:EXA_API_KEY}}"},
 "body": "{\"query\":\"2026년 최저임금\",\"numResults\":5,\"type\":\"auto\",\"contents\":{\"highlights\":{\"maxCharacters\":300},\"text\":{\"maxCharacters\":500}}}",
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "web-search/exa-9aaf8571.json"}
```

- 키는 **헤더에만** 있다. URL·`params`·`body` 에 키를 넣지 않는다(`plan` 이 준 그대로면 된다).
- `body` 는 **문자열**이다 — `plan` 출력의 `body` 를 바꾸지 말고 그대로 넣는다(질의어 이스케이프를 스크립트가 했다).
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다** — 이름 끝의 8자 지문이 질의어·`--count`·`--naver-type` 의 지문이라 3단계가 이름으로 짝을 맞춘다.
- `save_dir` 는 절대 경로(사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외). 생략하면 itda-hyve 기본 저장 폴더.
  같은 이름이 이미 있으면 덮어쓰지 않고 `invalid_input` 으로 거부된다 — 같은 검색을 다시 하면 `save_dir` 를 새 하위 폴더로 바꾼다
  (사용자가 확인했을 때만 `overwrite: true`).
- 응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.
- **응답 요약의 `status` 가 400 이상이면 같은 요청을 다시 보내지 않는다**(3단계가 저장된 오류 본문을 읽어 가른다). 저장된 파일이 비어 있으면
  그 자리에 `{"error": {"code": "http_<status>", "message": "본문 없음"}}` 을 쓴다(예: `"http_429"`).

### 호출이 실패하면 — 그 엔진만 빼고 끝까지 간다

**itda-hyve 안내와 [netbridge.md](references/netbridge.md) 의 "`secret_missing` 이면 안내하고 멈춘다" 는 그 엔진 하나에 대한 것이다.**
이 스킬에서는 실패한 엔진의 `save_as` 자리에 실패를 쓰고 **다음 엔진으로 가며, 마지막에 반드시 `collect` 를 부른다.**
키를 다른 길로 넣는 것이 아니므로 우회가 아니다 — 이미 받은 엔진의 결과를 버리지 않기 위해서다.

itda-hyve 가 오류를 돌려주면 파일이 생기지 않는다. 그 호출의 `save_as` 경로에 **`{"error": {"code": "<코드>", "message": "<메시지>"}}`**
한 줄을 써 두고(도구가 준 `{"code","message","hint"}` 를 그대로 써도 읽는다)(`Write`) 다음 엔진으로 넘어간다 — 3단계가 그 엔진을 "실패" 로 보고하고 나머지 엔진 결과는 살린다.

| 코드 | 뜻 | 대응 |
|---|---|---|
| `secret_missing` | 그 엔진 키가 시크릿 탭에 없다 | 실패 자리를 쓰고 계속. 결과를 전할 때 "itda-hyve GUI 시크릿 탭에 `<secrets>` 등록" 을 안내한다. **값을 대화로 받지 않는다** |
| `secret_host_denied` | 키를 이 호스트로 보낼 수 없다 | URL 이 `plan` 출력과 같은지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다. 실패 자리를 쓰고 계속 |
| `invalid_input` | 같은 이름 파일이 이미 있음·인자 오류 | 새 하위 폴더를 `save_dir` 로 다시 보낸다 |
| `body_truncated: true` | `save_as` 없이 받았다 | `save_as` 로 다시 받는다 |
| `timeout` | 응답 없음 | **먼저** 1회만 다시 보낸다(`timeout_sec` 은 50 을 넘기지 않는다 — Cowork 호출 상한 60초. 유료 엔진이면 과금 중복이 될 수 있어 다시 보내기 전에 묻는다). 다시 보낸 것이 "같은 이름" 으로 거부되면 늦게 생긴 파일이니 그대로 쓴다. 다시 보낸 것도 실패했을 때 **그 뒤에** 실패 자리를 쓴다(먼저 쓰면 재전송이 제 실패 자리 때문에 거부된다) |

POST 는 itda-hyve 가 자동 재시도하지 않는다(과금 중복 방지 — `retry_unsafe` 를 붙이지 않는다).

## 3단계 — 저장한 응답을 합치기

`plan` 과 **같은 질의·엔진 선택·옵션**으로 `collect` 를 부르고, 받은 파일(실패 자리 포함) **전부**를 `--input` 에 넘긴다.
Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 — `save_dir` 의 **폴더 이름** 뒤에 `saved_path` 를 붙인다
(파일을 찾아 헤매지 않는다). Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다.

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
D="$HOME/mnt/작업폴더/web-search"
python3 "$SKILL_DIR/scripts/web_search.py" collect "2026년 최저임금" \
  --input "$D/tavily-72b10d52.json" "$D/naver-93ad7cea.json" "$D/serper-7c7c67e5.json"
python3 "$SKILL_DIR/scripts/web_search.py" collect "반도체 수출 동향" --engine naver --naver-type news \
  --format json --input "$HOME/mnt/작업폴더/web-search/naver-….json"

# Windows
py -3 "$env:SKILL_DIR\scripts\web_search.py" collect "2026년 최저임금" --input "…\web-search\tavily-72b10d52.json" "…\web-search\naver-93ad7cea.json" "…\web-search\serper-7c7c67e5.json"
```

이번에 받은 `saved_path` 만 넘긴다(폴더를 `*.json` 으로 통째로 넘기면 앞선 검색의 파일이 섞여 `input` 오류가 난다).
`--format` 은 `markdown`(기본) · `json`. 스크립트가 보는 것 — 어긋나면 `error: "input"`(exit 2)이고 **무엇을 더 받을지** 이름으로 알려 준다:

- 고른 엔진마다 파일이 **정확히 하나**, 그 경로에 **실제로** 있는가(빠진 엔진 → 받아야 할 `save_as` 를 알려 준다. 실패했으면 실패 자리를 쓴다)
- 파일 이름의 지문이 이번 질의·옵션과 같은가(다른 검색의 파일이 섞이지 않았는가)
- 응답이 질의어를 되돌려 주는 엔진(Tavily `query`·Serper `searchParameters.q`)은 그 값이 이번 질의와 같은가(공백·대소문자 차이는 같다고 본다)
- 고르지 않은 엔진의 파일·plan 이 주지 않은 이름이 없는가

출력(json): `query` · `engine`(엔진이 하나면 그 이름, 여럿이면 `auto`) · `engines_used`(성공한 엔진) · `results[]`(`rank`·`title`·`url`·`snippet`·`source`·`engine`·`score`·`published_at`)
· `answer`(늘 `null` — 요약 답변을 주던 Perplexity 를 뺐다, 호환을 위해 필드는 둔다) · `engine_meta` · `errors[]`(`engine`·`code`·`message`, 키 미등록이면 `secrets`) · `notes`(있을 때 — 키 등록 안내·URL 없는 결과 수).
결과는 엔진 순서대로 번갈아 섞고(round-robin) 같은 URL 은 한 번만 남긴 뒤 `--count` 개로 자른다.
Tavily 결과에는 날짜(`published_at`)가 없다(요청에 `include_published_date` 를 싣지 않는다).

검색 응답 파일은 `save_dir` 아래 `web-search/` 에 남는다. 결과를 전한 뒤 필요 없으면 사용자가 지워도 된다(스크립트는 다시 읽지 않는다).

### 응답 판정 — HTTP 200 만으로 성공이 아니다

엔진마다 오류 본문 모양이 다르다(2026-09-30 itda-hyve 실측 — 인증 없이 보낸 요청): Tavily `{"detail":{"error":…}}` · Naver `{"errorCode":"024",…}` ·
Serper `{"message":…,"statusCode":403}` · Exa **402** `{"error":"Payment required…","tag":"X402_PAYMENT_REQUIRED"}`(키 없는 요청에만 오는 x402).
키가 있는 요청의 Exa 402 는 크레딧·예산 소진이다(문서). 3단계가 본문을 읽어 가른다 — 모델이 판정하지 않는다.

| `errors[].code` | 뜻 |
|---|---|
| `SECRET_MISSING` | itda-hyve `secret_missing` — 시크릿 탭에 `secrets` 의 이름으로 등록 |
| `AUTH_FAILED` | 키가 틀렸거나 권한 없음(Naver `024`·`028`, 401·403, Exa x402) — 시크릿 탭의 값 확인 |
| `RATE_LIMITED` | 한도·크레딧 소진(429·432·433, Exa 402, Naver `010`, "excessive requests" 류) — 한도가 풀리거나 충전한 뒤 다시 |
| `API_ERROR` · `HTTP_ERROR` | 그 밖의 API 오류(Tavily 422 요청 검증 오류 포함)·HTTP 오류(`http_<status>` 실패 자리 포함). Exa 의 `API_ERROR` 는 크레딧 소진일 수도 있다(태그 목록이 문서에 없다) — 대시보드 잔액을 확인하라고 안내한다 |
| `PARSE_ERROR` · `TRUNCATED` · `INPUT_ERROR` | JSON 이 아님(저장이 끊겼거나 HTML 오류 페이지)·결과 목록이 없거나 배열이 아님·본문 잘림·빈 파일 — 그 호출의 응답 요약 `status` 가 **200** 이었고 JSON 이 아님·잘림·빈 파일일 때만 `save_as` 로 한 번 다시 받는다. `status` 가 400 이상이었거나 결과 목록 문제면 다시 보내지 않는다(같은 결과가 오고, Exa 면 과금이 한 번 더 나간다) |
| `HYVE_FAILURE` | 그 밖의 itda-hyve 실패(`hyve_code` 참고) |

## 종료 코드 (`collect`)

| code | 의미 |
|------|------|
| 0 | 성공 — 1개 이상 엔진 성공(일부 엔진 실패는 `errors[]` 에) |
| 2 | 인자 오류(질의어 없음, 잘못된 엔진명, 같은 엔진 두 번, count<1) · 입력 파일 오류(`error: "input"`) |
| 3 | 모든 엔진 키 미등록(`secret_missing`) — `notes` 가 등록할 이름과 유료 엔진 지목 방법을 알려 준다 |
| 4 | 모든 엔진 인증 실패 |
| 5 | 모든 엔진 한도 초과 |
| 6 | 그 밖의 전체 실패(또는 실패 종류가 섞임) |

`auto` 가 exit 3 이면(무료 3종 모두 키 없음) 결과 없이 **등록 안내**를 전한다. 유료 엔진으로 넘어가는 것은 사용자가 원할 때만이다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 찾은 URL 의 본문을 마크다운으로 추출 | itda-web:web-reader |
| 네이버 블로그 글 목록·댓글(robots 불허) | 브라우저 경로 — itda-web:aside-browser-mcp |
| 시장조사 보고서·경쟁 분석 | itda-research:market-scan |
| 주장·수치의 출처 검증 | itda-research:ground-check |
| 로그인·JS 렌더가 필요한 사이트 | itda-web:aside-browser-mcp |

## 범위 밖 (다른 스킬로 위임)

| 상황 | 맞는 스킬 |
|------|-----------|
| 의사결정용 시장조사·경쟁분석 **보고서** ("정리·분석해줘") | market-scan |
| 1차 소스 강제 **팩트체크**·교차검증 | ground-check |
| 이미 아는 **URL의 본문** 추출 | web-reader |
| 네이버 블로그 목록·댓글 | aside-browser-mcp(브라우저 — 네이버 robots 가 자동 수집을 막는다) |
| 블로그 SEO 블루키워드 발굴 | blog-seo |
| 근본원인 규명("왜 느리지") | investigate |

"경쟁사 동향 **검색**해줘"(URL 목록)는 web-search, "경쟁사 동향 **정리·분석**해줘"(보고서)는
market-scan으로 구분한다.

## 인접 스킬 핸드오프

검색 결과를 다음 단계로 자연스럽게 넘긴다.

| 다음 단계 | 스킬 |
|-----------|------|
| 결과 URL의 **본문**이 필요할 때 | web-reader |
| 결과를 **1차 소스로 팩트체크** | ground-check |
| 수집을 **의사결정용 보고서로** | market-scan |

네이버 블로그 검색은 본 스킬(`--engine naver --naver-type blog`, 공식 OpenAPI)이 맡는다. 찾은 글을 읽어야 하면
사용자가 브라우저로 연다(aside-browser-mcp) — 키 없이 블로그를 훑던 blog-reader 는 2026-10-01 제거했다(네이버 robots 가
목록·댓글·전체 검색을 막는다).

## 주의

- `--engine auto` 는 무료 엔진 3종(tavily·naver·serper)을 1회씩 부른다. Exa 는 요청당 과금이라
  사용자가 지목했거나 제안에 동의했을 때만 `--engines` 로 넣는다.
- 본 스킬은 검색 결과 본문을 크롤링하거나 사실 여부를 판정하지 않는다 — 목록·출처만 제공한다.
- 정상 응답 shape는 각 엔진 공식 문서 기준이다(2026-09-30 대조 — 키 있는 실측은 Cowork 대기, 참고: [references/search-apis.md](references/search-apis.md)). 오류 본문 모양은 2026-09-30 실측이다.
