---
name: blog-seo
description: >
  네이버 SearchAd API로 블로그 SEO용 블루키워드를 발굴하는 스킬입니다.
  "블루키워드 찾아줘", "경쟁 적은 키워드 분석해줘", "블로그 키워드 포화지수 확인해줘"처럼 말하면 됩니다.
  포화지수·KEI 계산과 S~D 등급 분류를 제공합니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+"
allowed-tools: Bash, Read, Write, mcp__workspace__bash
user-invocable: true
argument-hint: "[시드 키워드] [--min-volume 500] [--min-grade B] [--trend] [--format md|json|csv]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "seo"
  version: "0.11.0"
  created_at: "2026-03-26"
  updated_at: "2026-09-30"
  tags: "SEO, KEI, blue keyword, keyword analysis, naver, blog seo, saturation index"
---

# blog-seo

네이버 API 기반 블루키워드 발굴 도구. 검색량 대비 경쟁이 적은 키워드를 자동으로 찾아줍니다.

> Python 표준 라이브러리만 사용 — 추가 의존성 없음

## 환경 변수

| Variable | Service | Guide |
|---|---|---|
| `NAVER_SEARCHAD_ACCESS_KEY` | 네이버 검색광고 API ([searchad.naver.com](https://searchad.naver.com)) | 네이버 검색광고 회원가입 → API 관리 → 라이선스 키 발급 |
| `NAVER_SEARCHAD_SECRET_KEY` | 네이버 검색광고 API ([searchad.naver.com](https://searchad.naver.com)) | 네이버 검색광고 API 관리에서 ACCESS KEY와 함께 발급 |
| `NAVER_SEARCHAD_CUSTOMER_ID` | 네이버 검색광고 API ([searchad.naver.com](https://searchad.naver.com)) | 네이버 검색광고 API 관리 → 고객 ID 확인 |
| `NAVER_CLIENT_ID` | 네이버 Open API ([developers.naver.com](https://developers.naver.com)) | 네이버 개발자 센터 → 애플리케이션 등록 → Client ID 발급 |
| `NAVER_CLIENT_SECRET` | 네이버 Open API ([developers.naver.com](https://developers.naver.com)) | 네이버 개발자 센터 → 애플리케이션 등록 → Client Secret 발급 |

상세 발급 절차는 아래 [API 키 발급 방법](#api-키-발급-방법) 섹션을 참고하세요.

## Prerequisites

Python 3.10 이상만 있으면 됩니다. 추가 패키지 설치는 필요하지 않습니다.

**네이버 API 키 2종**이 필요합니다 (아래 [API 키 설정](#api-키-설정) 참고):

| 키 종류 | 발급처 | 필수 여부 |
|--------|-------|---------|
| 네이버 검색광고 API (3개 키) | searchad.naver.com | **필수** — 키워드 확장의 핵심 |
| 네이버 오픈 API (2개 키) | developers.naver.com | **필수** — 블로그 문서수 조회 |

> **주의**: 네이버 검색광고 API는 **광고주 계정**이 있어야 발급됩니다.
> 네이버 광고 계정이 없다면 아래 [API 키 발급 방법](#api-키-발급-방법) 을 먼저 확인하세요.

## 지표 설명

| 지표 | 계산식 | 의미 |
|------|--------|------|
| 포화지수 | (문서수 / 월간검색량) × 100 | 낮을수록 블루키워드 |
| 문서비율 | 문서수 / 월간검색량 | 경쟁 강도 |
| KEI | 월간검색량² / 문서수 | 높을수록 좋은 키워드 |

## 등급 기준

| 등급 | 포화지수 | 문서비율 | 레이블 |
|------|---------|---------|--------|
| S | < 10% | < 0.5 | 블루키워드 |
| A | 10~20% | 0.5~1.0 | 유망 키워드 |
| B | 20~40% | 1.0~1.5 | 기회 있음 |
| C | 40~60% | 1.5~3.0 | 경쟁 치열 |
| D | > 60% | > 3.0 | 레드키워드 |

> 포화지수와 문서비율 등급이 다를 경우 **더 낮은(보수적) 등급** 적용

## API 키 설정

### 환경변수 목록

| 환경변수 | 발급처 | 용도 | 필수 |
|---------|-------|------|------|
| `NAVER_SEARCHAD_ACCESS_KEY` | searchad.naver.com | 키워드 확장 (HMAC 인증) | ✅ |
| `NAVER_SEARCHAD_SECRET_KEY` | searchad.naver.com | HMAC-SHA256 서명 | ✅ |
| `NAVER_SEARCHAD_CUSTOMER_ID` | searchad.naver.com | 광고주 고객 ID | ✅ |
| `NAVER_CLIENT_ID` | developers.naver.com | 블로그 검색, 데이터랩 | ✅ |
| `NAVER_CLIENT_SECRET` | developers.naver.com | 블로그 검색, 데이터랩 인증 | ✅ |

### 키 등록

**키는 환경변수로만 넣는다 — 스킬은 `.env` 같은 파일을 읽지 않는다(itda-work/skills#45):**

| 환경 | 키를 넣는 곳 | 쓰이는 곳 |
|---|---|---|
| Claude Code | 셸 환경변수, 또는 키마다 `claude config set env.NAVER_CLIENT_ID "..."`(위 5개 모두, 등록 뒤 세션을 다시 시작) | 스크립트가 `os.environ` 에서 읽는다 |

> itda-hyve 시크릿 경로는 이 스킬에 아직 없다 — 스크립트가 API 를 직접 부르므로 itda-hyve 에 등록한 키는 쓰이지 않는다.

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find`·파일 열람으로 **사전 점검하지 않는다** — 스크립트를 **우선 실행**한다. 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `NAVER_SEARCHAD_ACCESS_KEY=<키> NAVER_CLIENT_ID=<키> ... python3 "$SKILL_DIR/scripts/keyword_analysis.py" ...`. 지침에도 없으면 위 경로와 GUIDE의 발급 안내를 제시한다. `.env` 파일을 만들라고 안내하지 않는다(스크립트가 읽지 않는다). 키 값을 대화로 받지 않는다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수의 NAVER_CLIENT_ID 를 사용했습니다"). 값은 어디에도 표시하지 않는다.

> 스크립트의 키 소스: `os.environ`(Claude 주입 포함). env 파일·`~/.claude/settings.json` 은 읽지 않는다.

### API 키 발급 방법

#### 1. 네이버 검색광고 API (NAVER_SEARCHAD_*)

> **광고주 계정 필요** — 네이버 광고 시스템에 등록된 광고주만 발급 가능합니다. 자세한 내용은 [references/naver-api.md](references/naver-api.md#1-네이버-검색광고-api-키-발급)를 참고하세요.

1. https://ads.naver.com 접속 후 광고주 가입
2. 가입 완료 후 https://manage.searchad.naver.com 로그인
3. 상단 메뉴 **도구** → **API 사용 관리** 이동
4. Access License (= `NAVER_SEARCHAD_ACCESS_KEY`), Secret Key (= `NAVER_SEARCHAD_SECRET_KEY`) 복사
5. 같은 페이지 URL의 숫자(`/customers/숫자/`)가 `NAVER_SEARCHAD_CUSTOMER_ID`

#### 2. 네이버 오픈 API (NAVER_CLIENT_*)

> 일반 네이버 계정으로 발급 가능합니다 (광고주 계정 불필요). 자세한 내용은 [references/naver-api.md](references/naver-api.md#2-네이버-오픈-api-키-발급)를 참고하세요.

> **⚠️ NAVER API HUB 이관 고지 (2026-07 약관 변경)**: 검색·데이터랩 API는 네이버클라우드(NCP) **NAVER API HUB**로 이관된다. 2026-07-30 이후 개발자센터 신규 이용 신청 불가 — 신규 사용자가 아래 절차에서 신청이 막히면 NAVER API HUB에서 발급하도록 안내한다. 기존 키는 **2027-06-30까지** 현행대로 동작한다. 검색광고 API는 별개 서비스로 무관.

1. https://developers.naver.com 접속 후 회원가입 또는 로그인
2. 상단 메뉴 **Application** → **애플리케이션 등록** 클릭
3. 사용 API에서 두 항목 체크: **검색** + **데이터랩(검색어트렌드)**
   - "데이터랩(쇼핑인사이트)"는 이 스킬에서 사용하지 않음
4. **WEB 설정** → Callback URL에 `https://example.com` 입력
5. 등록 완료 후 **Client ID** 와 **Client Secret** 복사

## 실행 전 — 스킬 디렉토리 확정

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
printf "%s\n" "$c"' _ blog-seo itda-doc "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'blog-seo'; $P = 'itda-doc'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

## API 사용량 안내 (실행 전 필독)

이 스킬을 실행하기 전에 반드시 아래 내용을 사용자에게 안내한다.

### API별 일일 한도

| API | 일일 한도 | 1회 실행 소모량 |
|-----|---------|--------------|
| 블로그 검색 (문서수 조회) | 25,000회/일 | `--top-n` 값만큼 (기본 20회) |
| 데이터랩 검색어트렌드 | **1,000회/일** | `--top-n` 값만큼 (기본 20회) |
| 검색광고 키워드 확장 | 제한 없음 | 1회 |

### --trend 플래그 사용 시 필수 안내

`--trend`를 사용하면 필터링된 키워드 **1개당 데이터랩 API 1회** 소모된다.

- `--top-n 20` (기본값) → 최대 **20회/실행**
- 일일 한도 1,000회 ÷ 20회 = 하루 **최대 50회** 실행 가능
- 한도 초과 시 당일 자정까지 트렌드 조회 불가 (블로그 검색은 계속 가능)

### 권장 사용 패턴

1. `--trend` 없이 먼저 실행해 유망 키워드를 추린다
2. 추려진 키워드만 `--keywords`에 넣고 `--trend`로 재실행한다
3. 대량 분석이 필요하면 `--top-n`을 낮춰 소모량을 줄인다

```
# 1단계: 트렌드 없이 전체 탐색 (데이터랩 0회 소모)
python3 "$SKILL_DIR/scripts/keyword_analysis.py" --keywords "파이썬" --min-grade B

# 2단계: 유망 키워드만 트렌드 포함 분석 (데이터랩 top-n회 소모)
python3 "$SKILL_DIR/scripts/keyword_analysis.py" --keywords "파이썬 독학,파이썬 기초" --min-grade B --trend --top-n 10
```

## 사용법

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/keyword_analysis.py" --keywords "파이썬 독학,파이썬 강의"

# Windows
py -3 "$env:SKILL_DIR\scripts\keyword_analysis.py" --keywords "파이썬 독학,파이썬 강의"
```

### 주요 옵션

```
--keywords      시드 키워드, 쉼표 구분 (최대 5개)
--min-volume    최소 월간 검색량 (기본값: 500)
--min-grade     최소 등급 S|A|B|C|D (기본값: B)
--top-n         블로그 문서수 조회 최대 수 (기본값: 20)
--trend         트렌드 분석 포함 (Naver Datalab 사용)
--format        출력 포맷 md|json|csv (기본값: md)
--output        저장 파일 경로 (기본값: stdout)
```

### 예시

```bash
# 블루키워드만 추출 (S, A등급)
python3 "$SKILL_DIR/scripts/keyword_analysis.py" \
  --keywords "파이썬 독학,파이썬 강의" \
  --min-grade A \
  --format md

# 트렌드 분석 포함, CSV 저장
python3 "$SKILL_DIR/scripts/keyword_analysis.py" \
  --keywords "파이썬" \
  --trend \
  --format csv \
  --output result.csv

# 고검색량 키워드 집중 분석
python3 "$SKILL_DIR/scripts/keyword_analysis.py" \
  --keywords "파이썬,자바,자바스크립트" \
  --min-volume 1000 \
  --top-n 100
```

## 상세 레퍼런스

API 인증 방식, 응답 형식, Rate Limit 처리에 대한 상세 내용은 [references/naver-api.md](references/naver-api.md)를 참고하세요.

## 캐시 정책

블로그 문서수 조회 결과는 `.itda-skills/blog-seo-cache.json`에 1시간 동안 캐시됩니다.
캐시 파일은 현재 작업 디렉토리(CWD) 기준 상대 경로에 저장됩니다.
