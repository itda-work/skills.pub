---
name: flight-search
description: >
  Google Flights 공개 검색으로 항공권을 조회·비교하는 스킬입니다.
  "인천에서 도쿄 6월 26일 항공권 찾아줘", "ICN-NRT 다음 달 최저가 언제야?",
  "9월에 7일 일정 왕복으로 제일 싼 출발일은?", "로마·파리·암스테르담 중 어디로
  들어가는 게 싸?", "올해랑 내년 6월 1일 가격 비교"처럼 말하면 됩니다.
  예약·결제는 하지 않고 검색 결과·예약 검색 링크·날짜별 최저가만 제공합니다.
license: MIT
compatibility: "Python 3.10+. fast-flights(Google Flights 공개 표면) 의존."
user-invocable: true
allowed-tools: Bash, Read, AskUserQuestion, mcp__workspace__bash
argument-hint: "인천에서 나리타 6월 26일 / ICN-BKK 다음 달 최저가"
metadata:
  author: "Chinseok"
  category: "data-fetching"
  version: "0.3.4"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-07-26"
  tags: "flight, airfare, google-flights, fast-flights, travel, iata, fare-compare"
---

# flight-search

Google Flights 공개 검색으로 **항공권을 조회·비교**합니다(예약·결제 없음).
사용자용 가이드는 GUIDE.md 참조.

## ⚠️ 시작 전 반드시 확인 (디스클레이머)

- **Google Flights 공개 검색 표면**을 `fast-flights` 로 조회합니다. 로그인·API
  key·결제·CAPTCHA 우회를 하지 않으며 **공개 표면만** 사용합니다. Google ToS
  관점의 자동 조회는 회색지대이며, Google 변경 시 **언제든 동작이 멈추거나
  파싱이 깨질 수 있습니다**.
- 이 스킬은 **검색·비교까지만** 합니다. **예약·결제·좌석지정은 하지 않습니다** —
  `booking_search_url` 은 특정 판매자 결제 deep link 가 아니라 **Google Flights
  검색 링크**이며, 실제 구매는 사용자가 브라우저에서 직접 진행합니다.
- 표시 **가격은 조회 시점 기준**이며, 로그인가·카드할인·쿠폰·마일리지
  적용가와 다를 수 있습니다.
- **매크로(반복 폴링·최저가 자동 연타)는 제공하지 않습니다.** 비교 기능은
  날짜당 1회 조회이며, 일수 cap·요청간격 하한을 코드로 강제합니다.
- **차단 시 폴백 프라이버시**: 직접 조회(common)가 막히면 외부 fetch 서버를
  경유하며, 이때 출도착·날짜가 그 서버로 전달됩니다(검색조건 제3자 노출). 기본은
  직접 조회라 평상시엔 외부 서버를 거치지 않습니다.

## 자격증명

**필요 없습니다.** Google Flights 공개 표면은 무인증입니다(이 스킬은 키·로그인
불필요 — itda-travel 스킬 중 유일).

## 사전 준비 (의존성)

`fast-flights` 가 필요합니다. 처음 한 번 설치하세요.

```bash
# macOS/Linux — 정문(핀 fast-flights==2.2 를 그대로 건다)
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"   # fast-flights==2.2

# Windows — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

미설치 시 스킬이 fail-loud 로 설치 방법을 안내합니다(크래시 아님). 직접
조회(common)는 추가 브라우저 없이 동작합니다.

## 실행

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/flight-search}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/flight-search' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\flight-search"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

```bash
# 단일 검색(편도) — macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" search --from ICN --to NRT --date 2026-06-26 --limit 5

# 왕복
python3 "$SKILL_DIR/scripts/main.py" search --from ICN --to NRT --date 2026-06-26 --return-date 2026-07-01

# 한 달 최저가 비교(주 1회 샘플, 빠름)
python3 "$SKILL_DIR/scripts/main.py" compare-month --from ICN --to NRT --month 2026-07 --sample weekly

# 왕복 날짜 유연 비교 — 체류일 고정 슬라이딩(출발일마다 +7일 귀국 왕복가)
python3 "$SKILL_DIR/scripts/main.py" compare-month --from ICN --to NCE --month 2026-09 --stay 7

# 한 달 매일 비교(요청 누적 — 일수 cap·간격 하한 강제)
python3 "$SKILL_DIR/scripts/main.py" compare-month --from ICN --to BKK --month 2026-07 --sample daily --sleep 2

# 날짜 범위 비교
python3 "$SKILL_DIR/scripts/main.py" compare-range --from ICN --to BKK --start-date 2026-07-01 --end-date 2026-07-20 --step-days 3

# 다중 목적지(관문) 비교 — 같은 날짜의 목적지별 최저가 순위(쉼표 구분, 최대 8개)
python3 "$SKILL_DIR/scripts/main.py" compare-destinations --from ICN --to FCO,CDG,AMS --date 2026-09-10

# 관문 비교를 한 달 단위로(weekly 샘플 강제 — 목적지 × 날짜 총 조회 cap 40)
python3 "$SKILL_DIR/scripts/main.py" compare-destinations --from ICN --to FCO,CDG,AMS --month 2026-09

# 연도 비교(같은 월일)
python3 "$SKILL_DIR/scripts/main.py" compare-years --from ICN --to NRT --years 2026,2027 --month-day 06-01

# Windows: 위 python3 를 py -3, "$SKILL_DIR/scripts/main.py" 를 "$env:SKILL_DIR\scripts\main.py" 로 바꿉니다.
```

옵션(서브커맨드 **뒤**에 둡니다): `--adults N`(기본 1) ·
`--seat economy|premium-economy|business|first` · `--limit N` · `--json` ·
(비교) `--sleep 초` · `--stay N`(왕복 체류일 — 출발일마다 `+N`일 귀국 왕복가
비교, 미지정 시 편도. `compare-destinations` 에는 없음 — 관문×왕복 조합은
cap 재검토 전까지 범위 밖).

> 공항은 IATA 코드(ICN·NRT·BKK 등) 또는 흔한 한국어 도시명(서울·도쿄·방콕 등)으로
> 줍니다. 모호한 도시(도쿄=NRT/HND, 뉴욕, 런던 등)는 어느 공항인지 되묻습니다.

응답 주요 필드(`--json`): `meta.booking_search_url`,
`meta.price_band`(low/typical/high), `stats.min_price`·`avg_price`·`max_price`,
`flights[].name`·`departure`·`arrival`·`duration`·`stops`·`price_text`·
`quality`(complete|partial). 비교는 `stats.min_price`·`avg_of_daily_min`·
`max_of_daily_min` 과 `cheapest_dates[]`(왕복 `--stay` 시 각 항목에
`return_date`, `query.trip`/`query.stay_days` 병기). 관문 비교는
`destinations[]`(최저가 순 — `to`·`min_price`·`cheapest_date`·
`avg_of_daily_min`·`booking_search_url`·`rows[]`) 와
`meta.total_queries`.

## Claude 라우팅 가이드

Claude 가 이 스킬을 실행할 때 따르는 행동 규칙입니다.

**규칙 1 — 공항 해석 / 모호 도시 확인**
도시명이면 IATA 로 해석합니다. 도쿄(NRT/HND)·뉴욕·런던처럼 여러 공항이 있으면
임의로 고르지 말고 사용자에게 확인합니다(스킬이 후보를 안내). 서울은 기본
ICN(국제선), 김포는 GMP 입니다.

**규칙 2 — 비교는 보수적으로(매크로 금지)**
daily 월 비교는 ~30회 조회가 발생합니다. 사용자가 명시하지 않으면 weekly 샘플을
먼저 제안하고, daily 는 시간이 걸림을 안내합니다. 같은 검색을 반복 폴링하지
않습니다(1회 실행).

**규칙 3 — partial 결과 정직하게 전달**
출력에 "항공사·시간 상세가 빠졌습니다"(전체 partial)가 나오면 Google Flights 가
이 시점 상세를 제한한 것입니다. **가격·band·예약 검색 링크는 유효**하므로 그것으로
안내하고, 필요하면 잠시 후 재시도나 링크 직접 확인을 권합니다. 빈 결과를 "항공편
없음"으로 단정하기 전에 날짜·공항코드·차단 여부를 점검합니다.

**규칙 4 — 예약·결제는 안내만**
이 스킬은 예약·결제를 하지 않습니다. 사용자가 예약을 원하면 `booking_search_url`
을 열어 직접 진행하도록 안내합니다.

**규칙 5 — 가격은 조회 시점**
표시 가격이 실제 결제가(로그인가·할인·마일리지)와 다를 수 있음을 덧붙입니다.

**규칙 6 — 왕복 날짜 유연 요청은 `--stay` 2단 흐름**
"출발·귀국 날짜 유연하게 제일 싼 왕복" 요청은 ① 체류일을 확인(또는 사용자
언급에서 추론)해 `compare-month`/`compare-range` 에 `--stay N` 으로 1차 스캔 →
② 싼 출발일 TOP 에서 `search --date --return-date` 로 상세·예약 링크를
확인합니다. 출발×귀국 전 조합(2D 그리드) 전수 조회는 매크로 금지 계약 위반이라
하지 않습니다. 체류일이 여러 개면(예: 5일도 7일도 가능) 실행을 나눠 각각
스캔하고 조회량이 배가됨을 안내합니다.
날짜가 몇 달 열려 있으면 coarse→fine 으로: `compare-month`(weekly)로 싼 달을
좁힌 뒤, 유망 구간만 `compare-range --step-days 1 --stay N`(cap 31일 내)로
일 단위 재스캔합니다 — 주 단위 표본은 저가일을 놓칩니다(ICN-NCE 실증: 일 단위
재스캔이 주 단위 최저 대비 -20만원대 날짜를 발견).

**규칙 7 — 목적지 유연(관문) 요청은 후보를 확인받고 `compare-destinations`**
"유럽 아무 데나 싸게 들어가면 된다" 류 요청은 스킬이 목적지를 자동 발견하지
않습니다(Explore 미지원). Claude 가 흔한 관문 후보(예: 유럽 FCO·CDG·AMS·MXP·
BCN·IST)를 **제안하고 사용자 확인을 받아** 쉼표 목록으로 넘깁니다(최대 8개).
결과 전달 시 **관문 최저가 ≠ 여정 총비용**임을 반드시 덧붙입니다 — 관문에서
최종 목적지까지의 기차/저가항공 비용·시간을 더해 비교하도록 안내(출력의 ※
주의 문구 유지). 목적지가 확정된 요청(예: "깐느")을 임의로 관문 비교로 바꾸지
않습니다.

## 제약 (Exclusions)

- **예약·결제·좌석지정·취소** — 영구 비목표(검색·비교 전용).
- **로그인 회원가·카드할인·쿠폰·마일리지 적용가** — 범위 밖(공개 표면가만).
- **CAPTCHA·fingerprint·bot-block 우회** — 하지 않음.
- **Skyscanner 직접 조회** — `skyscanner.net` 은 기본 접속부터 CAPTCHA/403 이라
  provider 로 쓰지 않습니다(SPEC-FLIGHT-SEARCH-001 의 Google Flights 접근 전환 사유).
- **매크로/반복 폴링** — 비교는 일수 cap(최대 31)·요청간격 하한(1초)을 코드로 강제.
- **출발×귀국 2D 전수 그리드** — 왕복 날짜 비교는 체류일 고정 슬라이딩(`--stay`)
  만 지원. 전 조합 조회(~900회)는 매크로 금지 계약 위반이라 하지 않음(#1024).
- **Explore(목적지 자동 발견)·후보 자동 선정** — 관문 비교는 호출자가 제시한
  후보 열거만(#1025). fast-flights 는 Explore 표면 미지원이며, 스킬이 목적지를
  임의 선정하지 않음. 관문→최종 목적지 연결 비용(기차·LCC) 계산도 범위 밖.

## Failure modes

- Google Flights HTML/프론트 변경으로 항공사·시간 파싱이 비거나 깨질 수 있습니다.
  **같은 노선도 호출에 따라 상세 포함 여부가 달라집니다**(연속 호출 시 더 자주
  누락). 이때 가격·band·링크는 유효합니다.
- 일부 노선은 가격만 나오고 항공편 상세가 `partial` 로 떨어집니다.
- 잘못된 IATA·동일 출도착·존재하지 않는 노선·너무 먼 미래 날짜는 실패하거나 빈
  결과입니다.
- 비교는 날짜별 실시간 조회라 요청이 많습니다(daily ~30회). 차단·rate limit 시
  fallback(외부 fetch 서버)으로 폴백 후, 실패하면 사유를 표면화합니다.

## Done when

- 출발/도착/날짜/좌석/인원을 확인했다.
- 단일 검색이면 상위 후보(또는 가격·band)와 예약 검색 링크를 제공했다.
- 비교면 샘플 방식과 최저/평균/최고, 싼 날짜 TOP 을 제공했다.
- 가격은 조회 시점 기준이며 실제 결제가가 다를 수 있음을 표시했다.
- 예약·결제·CAPTCHA 우회는 하지 않았다.
