---
name: hotel-search
description: >
  같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾는 스킬입니다.
  "신라호텔 서울 8월 1일부터 2박 최저가 비교해줘", "이 호텔 부킹이랑 아고다 중 어디가 싸? 예약 링크도 줘", "제주 그랜드하얏트 이번 주말 가격이랑 싼 날짜 알려줘"처럼 말하면 됩니다.
  Xotelo(트립어드바이저 메타서치) API 를 표준 라이브러리로 직접 호출합니다 — 브라우저·hyve 없이 동작.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, WebSearch, mcp__workspace__bash
argument-hint: "rates|heatmap|resolve --hotel-key g#-d# | --url <TripAdvisor URL> --checkin YYYY-MM-DD --checkout YYYY-MM-DD"
metadata:
  author: "Chinseok"
  version: "0.3.4"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-07-07"
  updated_at: "2026-09-25"
  tags: "hotel, price, comparison, travel, tripadvisor, xotelo, ota, booking, agoda, read-only, api"
---

> ⚠️ **실험(experimental) 스킬** · hyve#1013
>
> `flight-search`(항공권 최저가)의 호텔판입니다. **가격 소스는 Xotelo API**(트립어드바이저
> 메타서치 — Booking·Agoda·Trip.com·Klook·공식사이트 등 OTA 실시간 요금을 한 번에 반환).
> 구 버전(0.1.0)의 web_browse `mode=attach` 수동 워밍업 경로는 폐기했습니다.

## 어떤 불편을 푸나요?

> 같은 호텔인데 Booking·Agoda·Trip.com마다 값이 다르다. 탭 여러 개 띄워 날짜를 똑같이 넣고
> 일일이 비교하다 지쳐, 결국 대충 한 곳에서 예약하고 나중에 더 싼 걸 발견해 억울하다.

이 스킬은 호텔 하나 + 날짜로 **여러 OTA의 1박가·총액을 한 표**로 모아 그 비교 노동을 없앱니다.
덤으로 **"싼 날/비싼 날 달력"**(heatmap)도 봅니다. **조회 전용** — 예약·결제는 하지 않습니다.

## 동작 방식 (Xotelo API 직접 호출 — standalone)

**자체 브라우저도, hyve 도, MCP 도 필요 없습니다.** 이 스킬의 Python(`hotel_search.py`)이
[Xotelo](https://xotelo.com/) 무료 API 를 표준 라이브러리(`urllib`)로 직접 호출합니다.

| 서브커맨드 | 하는 일 |
|---|---|
| `resolve <URL\|텍스트>` | TripAdvisor URL/문자열에서 `hotel_key`(`g<geo>-d<hotel>`) 추출 |
| `rates` | OTA별 1박가·총액 비교표 (원화 환산 병기) |
| `heatmap` | 싼 날/평균/비싼 날 가격 달력 |

### hotel_key 를 먼저 확보한다 (이름→키 해소)

Xotelo 무료 티어에는 이름 검색이 없습니다(`/search`=유료, `/list`=고장, 실측 #1013).
그래서 조회 전에 대상 호텔의 `hotel_key` 를 **두 경로 중 하나로** 확보합니다:

1. **에이전트 web_search** — 사용자가 호텔명만 줄 때. `"<호텔명> tripadvisor hotel"` 로 검색해
   `tripadvisor.com/Hotel_Review-g…-d….html` URL 을 찾고, `resolve` 로 키를 뽑습니다.
   ⚠️ 검색 결과가 맞는 호텔인지 이름·도시로 확인합니다(data-accuracy — 동명 호텔 주의).
2. **사용자 URL/키 직접 제공** — 사용자가 TripAdvisor 링크나 `g294197-d5250436` 를 줄 때. 그대로 `--url`/`--hotel-key`.

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/hotel-search}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/hotel-search' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\hotel-search"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# macOS/Linux — URL 에서 hotel_key 추출
python3 "$SKILL_DIR/scripts/hotel_search.py" resolve "https://www.tripadvisor.com/Hotel_Review-g294197-d5250436-Reviews-Summit_Hotel_Seoul-Seoul.html"
# → g294197-d5250436
```

### 요금 비교 (rates)

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/hotel_search.py" rates --hotel-key g294197-d5250436 \
  --checkin 2026-08-15 --checkout 2026-08-17 --name "써미트 호텔 서울"

# Windows
py -3 "$env:SKILL_DIR\scripts\hotel_search.py" rates --url "<TripAdvisor URL>" \
  --checkin 2026-08-15 --checkout 2026-08-17
```

`rate` 는 각 OTA에서 **예약 가능한 최저 객실의 1박 평균가**입니다. 총액 = 1박가 × 박수.
결과는 1박가 오름차순(최저가에 🏆). Xotelo 는 KRW 미지원이라 **USD 등으로 수집 후 원화로 환산**해
`"418,656원 (USD 278)"` 형태로 병기합니다(환율 참고값 — 예약가 아님). `--no-krw` 로 환산을 끕니다.

**예약 링크** — `--name`(호텔명)을 주면 각 OTA 셀이 예약 링크가 됩니다. 라이브 검증(#1015) 결과
OTA마다 안정성이 달라 경로를 나눕니다:
- **Booking.com** = 네이티브 검색 딥링크(호텔명+날짜+인원 프리필 — 그 호텔·그 날짜로 바로 랜딩, 검증됨).
- **Agoda·Trip.com·Klook·공식사이트 등** = **Google 검색 링크**(`<호텔명> <OTA>`) — 이들은 내부 city/hotel
  ID 를 요구해 호텔명만으로 만든 직접 URL 이 깨진다(Agoda 홈 이동·Trip.com 0결과·KLOOK 404 실측). 대신
  Google 검색 최상단이 그 OTA 의 그 호텔 페이지라 클릭 한 번 더로 도달한다.

Xotelo 가 정확한 객실 URL 을 안 주므로 Booking 외에는 "그 호텔 페이지로 유도"까지다. `--name` 이 없으면
링크 없이 가격만 나옵니다.

### 지역 + 예산으로 찾기 (에이전트 오케스트레이션)

이 스킬은 **특정 호텔**의 가격만 조회합니다(무료 Xotelo 는 지역별 목록/이름검색 미지원 — `/list` 고장·
`/search` 유료). "장충동에서 8만~13만원 호텔 찾아줘" 같은 **지역+예산·모호** 질의는 에이전트(Claude)가
아래 흐름으로 처리합니다(계약 — 항상 이 순서):

1. **발견** — `WebSearch` 로 그 지역 호텔 후보와 TripAdvisor URL 을 찾는다("장충동 호텔 tripadvisor").
2. **후보 제시 → 선택 대기** — 찾은 **호텔 후보를 리스트로 사용자에게 제시**하고(이름·위치·대략 등급),
   **어느 호텔을 볼지 사용자의 선택을 기다린다.** 임의로 하나를 골라 진행하지 않는다.
   (단, 사용자가 "다 비교해줘"처럼 전체 조회를 명시하면 후보 전부를 조회한다.)
3. **가격** — 선택된 호텔(들)을 `rates` 로 조회한다(내일 1박 등).
4. **필터** — 예산 대역(원화)에 드는 것만 골라 표로 제시한다.

호텔명을 **대략만** 알아도(또는 지역만 알아도) 에이전트가 web_search 로 시작한다. 반대로 사용자가
특정 호텔을 콕 집으면 2번(후보 제시)을 건너뛰고 바로 조회한다.

### 가격 달력 (heatmap)

```bash
python3 "$SKILL_DIR/scripts/hotel_search.py" heatmap --hotel-key g294197-d5250436 --checkout 2026-08-16
```

체크아웃 기준 한 달치 날짜를 싼 날/평균/비싼 날로 분류해, 언제 예약하면 싼지 한눈에 봅니다.

---

## 명령 레퍼런스

**`rates`** · **`heatmap`** 공통: `--hotel-key g#-d#` **또는** `--url <TripAdvisor URL>` (택1, 필수) · `--name <표시명>`(선택) · `--format {markdown,json}`(기본 markdown) · `--output <경로>`

| 인자 | 대상 | 설명 |
|------|:---:|------|
| `--hotel-key` / `--url` | rates·heatmap | TripAdvisor `g<geo>-d<hotel>` 키 또는 호텔 페이지 URL (택1) |
| `--checkin` | rates | 체크인 `YYYY-MM-DD` |
| `--checkout` | rates·heatmap | 체크아웃 `YYYY-MM-DD` (rates 는 체크인보다 이후) |
| `--currency` | rates | Xotelo 수집 통화 (기본 USD — KRW 미지원, 원화는 환산 표시) |
| `--adults` / `--rooms` | rates | 성인 수(기본 2) / 객실 수(기본 1) |
| `--no-krw` | rates | 원화 환산 생략(수집 통화만) |

지원 수집 통화: USD·GBP·EUR·CAD·CHF·AUD·JPY·CNY·INR·THB·BRL·HKD·RUB·BZD (KRW 없음).
엔드포인트·응답 스키마 상세는 [`references/sources.md`](references/sources.md).

---

## Exit Code

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 일반 실패 (네트워크·API 오류) |
| 2 | 인자 오류 (필수 누락, 날짜 형식/역순, hotel_key 미해소, KRW 등 미지원 통화) |
| 3 | 결과 없음 (해당 날짜 OTA 요금 0건 — 매진·미커버 호텔) |

---

## 제한 사항

- **TripAdvisor 메타값** — 요금 출처가 메타서치라 **실제 예약가와 다를 수 있습니다**("동작함 ≠ 정확함", data-accuracy). 최종 예약 전 해당 OTA에서 재확인하세요.
- **OTA별 대표가 1개** — 객실 타입(디럭스/스위트) 구분이나 객실별 가격은 제공하지 않습니다. `tax`(세금)도 대부분 표기되지 않습니다.
- **OTA 노출 개수 편차** — 호텔·날짜에 따라 1~4개 OTA만 뜰 수 있습니다(재고·커버리지 차이).
- **이름 검색 없음** — 무료 티어는 `hotel_key`(TripAdvisor 등재 호텔)가 필요합니다. 미등재 호텔은 조회 불가.
- **원화는 환산 표시** — Xotelo 가 KRW 미지원이라 실시간 환율(`open.er-api.com`)로 환산한 참고값입니다.
- **조회 전용** — 예약·결제·로그인 계정 액션은 지원하지 않습니다.
- **비공식 표면** — 공식 파트너 API 가 아닙니다. 개인 참고 목적으로만 사용하세요.

## 의존성

표준 라이브러리만 사용합니다(별도 패키지·API 키 불필요). 네트워크로 `data.xotelo.com`(요금·달력)과
`open.er-api.com`(환율)에 접근합니다. 상세는 [`references/sources.md`](references/sources.md).
