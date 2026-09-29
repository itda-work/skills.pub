---
name: web-search
description: >
  여러 검색엔진으로 웹을 한 번에 검색해 정규화된 결과 목록(제목·URL·발췌)을
  돌려주는 스킬입니다.
  "파이썬 입문 자료 검색해줘", "AI 규제 관련 최신 기사 찾아줘",
  "경쟁사 가격 정책 정보 모아줘"처럼 말하면 됩니다.
  1회성 정보 탐색과 출처 URL 수집이 목적이며, 시장조사 보고서·팩트체크·본문 추출은
  다루지 않습니다.
  [책임 경계] 본 스킬은 검색엔진 결과 목록(제목·URL·발췌) 수집 전담 — 찾은 URL 의 본문 추출은 itda-web:web-reader, 네이버 블로그는 itda-web:blog-reader 이며, 시장조사 보고서·팩트체크는 다루지 않습니다.
license: Apache-2.0
compatibility: "Claude Cowork & Code. Python 3.10+"
allowed-tools: Bash, Read, Write, mcp__workspace__bash
argument-hint: "[질의어] [--engine auto|tavily|serper|perplexity|naver|exa] [--count 5] [--format markdown|json] [--naver-type web|news|blog]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "search"
  version: "0.1.10"
  created_at: "2026-06-09"
  updated_at: "2026-09-28"
  tags: "search, web search, query, multi engine, tavily, serper, perplexity, naver, exa"
---

# web-search

질의어 하나로 여러 검색엔진을 한 번에 호출해, 출처가 다른 결과를 정규화된 목록으로
돌려주는 조회 전용 스킬. 기본 웹 검색이 한 곳만 긁어 오는 한계를 보완해 인덱스 출처를
다양화한다(Perplexity 요약 · Tavily · Serper(Google) · Naver 국내 · Exa 시맨틱).

> Python 표준 라이브러리만 사용 — 추가 의존성 없음

## 엔진 · 키 · 무료 한도 · 요금 (2026-06 기준, 변동 가능)

엔진별로 키가 있는 것만 사용한다(`--engine auto`는 키 보유 엔진만 자동 선택). **최소 1개**
엔진 키만 있으면 동작하며, 키가 없으면 사용 가능한 엔진 0개로 종료(코드 3)한다.

| 엔진 (유형) | 키 (환경변수) | 무료 한도 | 유료(대략) | 발급처 |
|---|---|---|---|---|
| **Tavily** (범용 raw) | `TAVILY_API_KEY` | 월 1,000 크레딧, 카드 불요 | PAYG $0.008/크레딧 | [app.tavily.com](https://app.tavily.com) |
| **Naver** (국내 web/news/blog) | `NAVER_SEARCH_CLIENT_ID`/`_SECRET` (기존 `NAVER_CLIENT_*` 폴백) | 일 25,000건, 무료 | — | [developers.naver.com](https://developers.naver.com) |
| **Serper** ⚠️회색지대 (Google SERP) | `SERPER_API_KEY` | 가입 시 2,500 쿼리, 카드 불요 | 1,000쿼리당 약 $0.3~1 | [serper.dev](https://serper.dev) |
| **Exa** (시맨틱) | `EXA_API_KEY` | 월 1,000 요청 | 검색 $7/1k (결과 10개 초과 +$1/1k) | [dashboard.exa.ai](https://dashboard.exa.ai) |
| **Perplexity** (요약+인용) | `PERPLEXITY_API_KEY` | 무료 크레딧 없음 | sonar $1/$1 + 요청료 $5~14/1k | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) |

- **무료로 시작**: `TAVILY_API_KEY` + `NAVER_SEARCH_CLIENT_ID`/`NAVER_SEARCH_CLIENT_SECRET`(둘 다 무료·카드 불요)이면 충분하다.
- **⚠️ Naver 이관 고지 (2026-07 약관 변경)**: 개발자센터 검색 API는 네이버클라우드(NCP) **NAVER API HUB**로 이관된다. 2026-07-30 이후 개발자센터 신규 이용 신청 불가 — 신규 사용자는 NAVER API HUB에서 발급하도록 안내한다. 기존 키는 **2027-06-30까지** 현행대로 동작한다.
- 요금·한도는 변동되므로 각 공식 페이지를 정본으로 본다(위 수치는 2026-06 기준).
- **⚠️ Serper(회색지대 — 보조용)**: Serper는 Google 공식 API가 아니라 공개 SERP를 스크래핑하는 제3자다. Google이 **동종 SerpApi를 DMCA 제소(2025-12-19)** 하고 **SearchGuard(2025-01)로 스크래퍼를 기술 차단** 중이라 카테고리 전반에 **중단·품질저하 가능성**이 있다(flight-search의 Google Flights 스크래핑과 동류의 ToS 회색지대). 견고성이 필요하면 자체 인덱스(Tavily·Exa)·공식 API(Naver·Perplexity)를 우선하고, Serper는 키를 설정할 때만 보조로 쓴다(미설정 시 auto에서 자동 제외).
- **미지원(낡은 방식, 의도적 제외)**: Google Custom Search JSON API — 공식 문서가 "closed to new customers" + 2027-01-01 종료 명시. Bing Web Search API — 2025-08-11 완전 은퇴. 활발히 유지보수되는 엔진만 지원한다.

## API 키 설정

### 키 등록 — 작업 폴더 `.env`에 등록 (권장, 비개발자 포함 모든 사용자)

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트, 연결한 폴더가 여러 개면 아무 폴더나) 루트에 `.env` 파일을 만들고 사용할 엔진의 키만 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`환경변수.txt` 도 동일하게 탐색된다. 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해 두어도 로더가 자동으로 찾아 쓴다.

```dotenv
TAVILY_API_KEY=발급받은_키
SERPER_API_KEY=발급받은_키
NAVER_SEARCH_CLIENT_ID=네이버앱_클라이언트ID
NAVER_SEARCH_CLIENT_SECRET=네이버앱_클라이언트시크릿
PERPLEXITY_API_KEY=발급받은_키
EXA_API_KEY=발급받은_키
```

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`·`*env*` 는 `환경변수.txt` 를, `*.env` 는 `.env.txt` 를 놓친다). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `TAVILY_API_KEY=<키> NAVER_SEARCH_CLIENT_ID=<키> NAVER_SEARCH_CLIENT_SECRET=<키> python3 "$SKILL_DIR/scripts/web_search.py" "검색어"`. 설정된 엔진 키만 주입하면 되고, 지침에도 없으면 GUIDE의 발급 안내를 제시한다. 수동 확인이 꼭 필요하면 파일명 3종(`.env`·`.env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 TAVILY_API_KEY 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 작업 폴더 루트 `.env`에 위 키, 또는 셸 환경변수도
사용할 수 있습니다.
> 키 소스 우선순위: `os.environ`(Claude 주입 포함) > `~/.claude/settings.json` > `.env`(자동 탐색).

## 엔진 선택 가이드 (언제 어떤 엔진 — Claude 라우팅 지침)

질의 성격에 맞는 엔진을 고른다. 사용자가 엔진을 지정하면 그대로 따른다. (강점 근거: AN Score 에이전트 검색 벤치마크 2026 — Exa 8.7·Tavily 8.6·Serper 8.0·Perplexity 6.8, 그리고 키워드 vs 시맨틱 검색 특성.)

| 상황 / 질의 유형 | 권장 | 근거 |
|---|---|---|
| 질문에 **바로 답 + 출처** ("~이 뭐야/얼마야/요약해") | `perplexity` | 합성 답변(answer)+인용. 단 raw 추출·검증엔 부적합 |
| **한국어·국내** (뉴스·블로그·맛집·지역·카페·지식iN) | `naver` (필요시 `--naver-type news\|blog`) | 국내 색인, 글로벌 엔진이 못 메우는 영역 |
| **광범위·인기·최신** ("Google에 뭐가 뜨나") | `serper`(⚠️회색지대) 또는 `auto` | 실제 Google SERP·신선한 색인 |
| **의미로 탐색** ("이것과 비슷한 글", 개념·리서치, 키워드가 애매) | `exa` | 신경망 시맨틱 — 단어 안 겹쳐도 의미로 매칭 |
| **범용 웹 검색 / RAG / 에이전트 기본 raw** | `tavily` | 에이전트 특화·정제된 결과 |
| **정확한 명칭·고유명사·코드·식별자** (exact 매칭) | `serper`/`tavily`/`naver` (키워드형) | 시맨틱(`exa`)은 exact 매칭이 약함 |
| **출처 다양성·교차검증** (어디가 강할지 불확실) | `auto` (키 보유 전부 fan-out) | 겹치지 않는 인덱스 병합 |

**라우팅 규칙(Claude):**
1. 사용자가 엔진을 지정 → 그대로.
2. 한국어·국내 주제 → `naver` 우선(또는 `auto`에 포함).
3. "바로 답/요약" 의도 → `perplexity`. "비슷한 것/개념" → `exa`.
4. 일반·불확실 → `auto`. 견고성 우선이면 회색지대(serper) 제외: `--engines tavily,naver,perplexity`.
5. 비용 민감 → 무료 위주: `--engines tavily,naver`.

**기본 전략:** 의도가 명확하면 단일 엔진(빠르고 저렴), 모호하거나 교차검증이 필요하면 `auto`. auto는 키 보유 엔진을 모두 1회씩 호출하므로 비용 누적에 유의(Perplexity·Exa는 유료). 키워드 검색(정확한 단어·명칭)과 시맨틱 검색(의미·유사도)은 상호보완이라, 둘 다 필요한 리서치는 `--engines tavily,exa`로 함께 돌린다.

## 사용법

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/web-search}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/web-search' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

# macOS/Linux
python3 "$SKILL_DIR/scripts/web_search.py" "검색어"
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\web-search"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\web_search.py" "검색어"
```

> **개발자 주의 — 이 저장소 소스트리에서 직접 실행 시:** 배포본은 `publish.py`가 `shared/` 모듈(`env_loader` 등)을 스킬 `scripts/`에 번들하므로 위 명령이 그대로 동작한다. 그러나 소스트리에서 직접 실행하면 `env_loader`를 찾도록 `PYTHONPATH`에 `skills/shared`를 추가해야 한다(없으면 `ModuleNotFoundError: env_loader`). 예: `PYTHONPATH=<repo>/skills/shared python3 scripts/web_search.py "검색어"`. 일반 사용자는 신경 쓸 필요 없다(배포본 자기치유).

### 주요 옵션

```
--engine        auto(기본) | tavily | serper | naver | perplexity | exa
--engines       쉼표로 구분한 서브셋 (예: tavily,serper,naver)
--count         반환 결과 수 (기본 5)
--format        markdown(기본) | json
--naver-type    네이버 검색 종류 web|news|blog (기본 web)
--model         Perplexity 모델 (기본 sonar)
--check-env     엔진별 키 보유 여부만 진단 (네트워크 호출 없음)
```

### 예시

```bash
# 키 보유 엔진 모두 fan-out (다양한 출처 병합)
python3 "$SKILL_DIR/scripts/web_search.py" "2026년 최저임금 인상률" --count 8

# 네이버 뉴스만
python3 "$SKILL_DIR/scripts/web_search.py" "반도체 수출 동향" --engine naver --naver-type news

# 특정 엔진 서브셋 + JSON
python3 "$SKILL_DIR/scripts/web_search.py" "python async 입문" --engines tavily,serper --format json

# 키 보유 현황 진단 (네트워크 0)
python3 "$SKILL_DIR/scripts/web_search.py" --check-env
```

## 종료 코드

| code | 의미 |
|------|------|
| 0 | 성공 (결과 0건 또는 일부 엔진 실패 포함 — 1개 이상 엔진 성공) |
| 2 | 인자 오류 (질의어 없음, 잘못된 엔진명, count<1) |
| 3 | 사용 가능한 엔진 없음 (auto인데 키 0개) / 강제 엔진 키 없음 |
| 4 | 인증 실패 (전 엔진 401/403) |
| 5 | 쿼터/레이트리밋 초과 (전 엔진 429) |
| 6 | 네트워크/타임아웃 (전 엔진 실패) |

일부 엔진만 실패하면 성공 엔진 결과를 반환하고 실패는 출력의 `errors[]`에 표기한다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 찾은 URL 의 본문을 마크다운으로 추출 | itda-web:web-reader |
| 네이버 블로그 글·댓글·블로그 내 검색 | itda-web:blog-reader |
| 시장조사 보고서·경쟁 분석 | itda-research:market-scan |
| 주장·수치의 출처 검증 | itda-research:ground-check |
| 로그인·JS 렌더가 필요한 사이트 | itda-web:aside-browser-mcp |

## 범위 밖 (다른 스킬로 위임)

| 상황 | 맞는 스킬 |
|------|-----------|
| 의사결정용 시장조사·경쟁분석 **보고서** ("정리·분석해줘") | market-scan |
| 1차 소스 강제 **팩트체크**·교차검증 | ground-check |
| 이미 아는 **URL의 본문** 추출 | web-reader |
| 네이버 블로그 본문·댓글 | blog-reader |
| **네이버 블로그 한정** 키워드 검색을 API 키 없이 (검색→정독 파이프라인) | blog-reader `discover` |
| 블로그 SEO 블루키워드 발굴 | blog-seo |
| 근본원인 규명("왜 느리지") | investigate |

"경쟁사 동향 **검색**해줘"(URL 목록)는 web-search, "경쟁사 동향 **정리·분석**해줘"(보고서)는
market-scan으로 구분한다.

## 인접 스킬 핸드오프

검색 결과를 다음 단계로 자연스럽게 넘긴다.

| 다음 단계 | 스킬 |
|-----------|------|
| 결과 URL의 **본문**이 필요할 때 | web-reader |
| 결과 중 **blog.naver.com URL의 본문·댓글** | blog-reader `read` |
| 결과를 **1차 소스로 팩트체크** | ground-check |
| 수집을 **의사결정용 보고서로** | market-scan |

네이버 블로그 검색은 두 경로가 있다: 다중 엔진 교차검증·뉴스/웹 포함 범용 탐색은
본 스킬(`--engine naver --naver-type blog`, 공식 OpenAPI), **네이버 블로그만** API 키
없이 찾아 바로 읽을 때는 blog-reader `discover`(→ `read` 이어읽기)가 경량 경로다 (#1334).

## 주의

- `--engine auto`는 키 보유 엔진을 **모두 1회씩** 호출한다. Perplexity·Exa는 요청당
  과금이므로, 비용을 줄이려면 `--engine` 또는 `--engines`로 범위를 좁힌다.
- 본 스킬은 검색 결과 본문을 크롤링하거나 사실 여부를 판정하지 않는다 — 목록·출처만 제공한다.
- 응답 shape는 각 엔진 공식 문서 기준이며, 라이브 검증으로 확정 권장(참고: [references/search-apis.md](references/search-apis.md)).
