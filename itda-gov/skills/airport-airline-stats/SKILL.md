---
name: airport-airline-stats
description: >
  인천공항 항공사별 월별 통계(운항·여객·화물)를 LLM-친화 JSON으로 조회하는 스킬입니다.
  "2025년 3월 인천공항 항공사별 통계 알려줘", "지난달 국제선 여객기 통계 뽑아줘",
  "T1 터미널 항공사별 운항 횟수 조회해줘"처럼 말하면 됩니다. 인천공항만 지원하며
  김포·김해·제주 등 한국공항공사 14개 지방공항은 별도 시스템입니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+"
allowed-tools: Bash, Read, Write, mcp__workspace__bash
user-invocable: true
argument-hint: "--year YYYY --month MM [--route I|D|all] [--airline-type Y|N|all] [--terminal P01|P03|all] [--schedule 0|1|all] [--airline {IATA-code}] [--format json|csv|table]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "1.0.4"
  created_at: "2026-05-27"
  updated_at: "2026-07-26"
  tags: "airport, incheon, aviation, statistics, airline, monthly-stats, scraping"
---

# airport-airline-stats

인천국제공항공사(airport.kr) 공개 웹페이지에서 항공사별 월별 운항·여객·화물 통계를 조회합니다.
국제선/국내선·여객기/화물기·T1/T2·정기/부정기 필터를 지원하며 237개 IATA 항공사 코드 화이트리스트를 갖춥니다.

> Python 표준 라이브러리만 사용 — 추가 의존성·API 키 없음. Windows User-Agent + Referer + 세션 쿠키(WMONID)로 정상 브라우저 모방.

## 데이터 소스

| 항목 | 값 |
|---|---|
| 원천 사이트 | <https://www.airport.kr> (인천국제공항공사) |
| 페이지 | navigation: `/co_ko/651/subview.do` |
| 데이터 엔드포인트 | `/fsmFsn/co_ko/statisticCategoryOfAirline.do` |
| 인증 | 불필요 (공개 웹페이지) |
| 갱신 주기 | 월별 (인천공항공사 공지 기준) |
| 적용 범위 | 인천공항 **단일 공항**. 김포·김해·제주 등 14개 지방공항(한국공항공사 airport.co.kr)은 미지원 |

## 작동 원리 — 2단계 HTTP

```
1. GET /co_ko/651/subview.do                        ─→ WMONID 세션 쿠키 시드
   Referer: https://www.google.com/

2. GET /fsmFsn/co_ko/statisticCategoryOfAirline.do  ─→ 데이터 조회 (HTML 응답)
   ?layout=636f5f6b6f40403635314040666e637431
   &stYear=YYYY&stMonth=MM&edYear=YYYY&edMonth=MM
   &routeSe={I|D}&arplnSe={Y|N}&terminalId={P01|P03}&nvgSe={0|1}&airline={IATA}
   Referer: https://www.airport.kr/co_ko/651/subview.do
   Cookie: WMONID=...
```

WMONID 쿠키 없이 2단계 호출 시 HTTP 302 무한 리다이렉트가 발생합니다(라이브 검증 확인). 이 스킬은 두 단계를 자동 처리합니다.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/airport-airline-stats}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/airport-airline-stats' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

Windows(PowerShell):

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\airport-airline-stats"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

## 사용 예시

### macOS / Linux

```bash
# 2025년 3월 국제선 항공사별 통계 (JSON)
python3 "$SKILL_DIR/scripts/collect_airline_stats.py" --year 2025 --month 3 --route I

# T1 터미널, 여객기, 정기편만
python3 "$SKILL_DIR/scripts/collect_airline_stats.py" --year 2025 --month 3 --terminal P01 --airline-type Y --schedule 0

# 대한항공(KE)만, CSV 출력
python3 "$SKILL_DIR/scripts/collect_airline_stats.py" --year 2025 --month 3 --airline KE --format csv

# 표 형식 출력
python3 "$SKILL_DIR/scripts/collect_airline_stats.py" --year 2025 --month 3 --route I --format table

# 지원 항공사 코드 목록
python3 "$SKILL_DIR/scripts/collect_airline_stats.py" --list-airlines
```

### Windows

```powershell
py -3 "$env:SKILL_DIR\scripts\collect_airline_stats.py" --year 2025 --month 3 --route I
py -3 "$env:SKILL_DIR\scripts\collect_airline_stats.py" --list-airlines
```

## 인자

| 인자 | 필수 | 값 | 설명 |
|---|---|---|---|
| `--year YYYY` | ✅ | 4-digit | 조회 연도 |
| `--month MM` | ✅ | 1-12 | 조회 월 |
| `--route` | | `all` (기본) / `I` / `D` | 국제선(I) / 국내선(D) / 전체 |
| `--airline-type` | | `all` (기본) / `Y` / `N` | 여객기(Y) / 화물기(N) / 전체 |
| `--terminal` | | `all` (기본) / `P01` / `P03` | T1(P01) / T2(P03) / 전체 |
| `--schedule` | | `all` (기본) / `0` / `1` | 정기(0) / 부정기(1) / 전체 |
| `--airline` | | IATA code | 항공사 코드 (예: `KE`, `OZ`, `7C`). 미지정 시 전체. `--list-airlines`로 확인 |
| `--format` | | `json` (기본) / `csv` / `table` | 출력 포맷 |
| `--list-airlines` | | | 지원되는 항공사 코드·이름 목록 출력 후 종료 |

## Claude 라우팅 가이드

사용자가 다음과 같이 말하면 본 스킬을 호출:

- "2025년 3월 인천공항 항공사별 통계 알려줘" → `--year 2025 --month 3`
- "지난달 국제선 통계" → `--year {지난달 연도} --month {지난달} --route I`
- "T1 항공사별 운항 횟수" → `--terminal P01 --format table`
- "대한항공 여객 통계" → `--airline KE`
- "화물기만 보여줘" → `--airline-type N`

연/월이 명시되지 않은 경우 사용자에게 명시적으로 물어볼 것. 미래 월은 사전 차단되어 `error: future_month`를 반환합니다.

**김포·김해·제주 등 다른 공항을 묻는 경우**: 본 스킬은 인천공항 전용이며 한국공항공사(airport.co.kr) 운영 14개 지방공항은 미지원임을 명시하고 별도 데이터 소스가 필요함을 안내.

## 출력 스키마 (JSON)

```json
{
  "query": {"year": 2025, "month": 3, "route": "I", "airline_type": "all", "terminal": "all", "schedule": "all", "airline": "all"},
  "results": [
    {
      "airline_name": "가루다인도네시아",
      "flights":    {"arrival": 29, "departure": 29, "total": 58},
      "passengers": {"arrival": 6429, "departure": 6543, "total": 12972},
      "cargo":      {"arrival": 288, "departure": 302, "total": 590}
    }
  ],
  "summary": {
    "total":      {"flights": {...}, "passengers": {...}, "cargo": {...}},
    "yoy_change": {"flights": {"arrival": "+6.0%", ...}, ...}
  },
  "meta": {
    "source": "인천국제공항공사 (airport.kr)",
    "source_url": "https://www.airport.kr/fsmFsn/co_ko/statisticCategoryOfAirline.do?layout=...",
    "fetched_at": "2026-05-27T05:12:34+00:00",
    "period": "2025-03",
    "row_count": 106,
    "disclaimer": "본 데이터는 인천국제공항공사(airport.kr) 공개 웹페이지를 직접 스크래핑한 결과이며, 통계는 인천공항공사 공식 통계 자료실의 원본을 우선으로 참조하시기 바랍니다.",
    "parse_warnings": []
  }
}
```

## 오류 분류

모든 오류 응답은 `error` 필드와 `message` 필드를 갖습니다. 오류 발생 시 종료 코드 2.

| `error` 값 | 원인 | 대처 |
|---|---|---|
| `future_month` | 사용자가 미래 월을 입력 | 현재 월 이하로 재시도 |
| `invalid_month` | 잘못된 연/월 (예: 13월) | 1-12 범위로 재시도 |
| `unknown_airline_code` | 화이트리스트에 없는 항공사 코드 | `--list-airlines`로 코드 확인 |
| `session_seed_failed` | navigation 페이지 호출 실패 (네트워크·차단) | 잠시 후 재시도 |
| `fetch_failed` | 데이터 페이지 호출 실패 | 잠시 후 재시도 |
| `no_data` | 응답이 정상이나 데이터 행 0개 | 다른 월·필터 조합으로 재시도 |

## 디스클레이머 (모든 출력 포맷에 부착)

본 데이터는 인천국제공항공사(airport.kr) 공개 웹페이지를 직접 스크래핑한 결과이며, 통계는 인천공항공사 공식 통계 자료실의 원본을 우선으로 참조하시기 바랍니다.

## 테스트

```bash
# Unit tests (mock-only, no network)
just -f ../../justfile test-skill airport-airline-stats

# Live smoke test (실제 airport.kr 호출, 환경변수 필요)
ITDA_AIRPORT_SMOKE=1 just -f ../../justfile smoke
```

## 알려진 한계

- HTML 마크업 의존: airport.kr 사이트 구조 변경 시 일시 동작 불가. 후속 패치 SPEC 대응.
- 응답 캐싱 미적용 (v1.0). 같은 월 반복 조회 시 매번 라이브 호출.
- 월 범위(start ~ end) 조회 미지원. 1개월씩만 호출.
- 인천공항 단일 공항. 김포·김해·제주 등은 미지원.

## 구현 기준

현재 동작 기준은 이 `SKILL.md`, `scripts/`, `tests/`, `CHANGELOG.md`입니다. 라이브 검증 기록은 `CHANGELOG.md`의 해당 버전 항목에 요약합니다.
