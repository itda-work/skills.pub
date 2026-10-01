---
name: hotel-search
description: >
  같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾는 스킬입니다.
  "신라호텔 서울 8월 1일부터 2박 최저가 비교해줘", "이 호텔 부킹이랑 아고다 중 어디가 싸? 예약 링크도 줘", "제주 그랜드하얏트 이번 주말 가격이랑 싼 날짜 알려줘"처럼 말하면 됩니다.
  Xotelo(트립어드바이저 메타서치) 무료 API 를 쓰고, 요청은 itda-hyve 가 보냅니다(키·브라우저 불필요).
license: MIT
compatibility: "Python 3.10+ (표준 라이브러리만), Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — batch plan_file·http_request)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__batch, mcp__remote-devices__itda-hyve__http_request, Read, Bash, Write, WebSearch, mcp__workspace__bash"
argument-hint: "호텔명(또는 TripAdvisor URL) + 체크인·체크아웃 날짜 — 예: 신라호텔 서울 8월 1일부터 2박"
metadata:
  author: "Chinseok"
  version: "0.4.0"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-07-07"
  updated_at: "2026-10-01"
  tags: "hotel, price, comparison, travel, tripadvisor, xotelo, ota, booking, agoda, read-only, api"
---

> ⚠️ **실험(experimental) 스킬** · hyve#1013
>
> 같은 호텔의 예약 사이트별 요금을 한 번에 비교합니다. **가격 소스는 Xotelo API**(트립어드바이저
> 메타서치 — Booking·Agoda·Trip.com·Klook·공식사이트 등 OTA 실시간 요금을 한 번에 반환).
> 구 버전(0.1.0)의 web_browse `mode=attach` 수동 워밍업 경로는 폐기했습니다. 0.4.0 부터 요청은 itda-hyve 가 보냅니다.

## 어떤 불편을 푸나요?

> 같은 호텔인데 Booking·Agoda·Trip.com마다 값이 다르다. 탭 여러 개 띄워 날짜를 똑같이 넣고
> 일일이 비교하다 지쳐, 결국 대충 한 곳에서 예약하고 나중에 더 싼 걸 발견해 억울하다.

이 스킬은 호텔 하나 + 날짜로 **여러 OTA의 1박가·총액을 한 표**로 모아 그 비교 노동을 없앱니다.
덤으로 **"싼 날/비싼 날 달력"**(heatmap)도 봅니다. **조회 전용** — 예약·결제는 하지 않습니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve**(`mcp__remote-devices__itda-hyve__batch`·`…__http_request`)로만 나간다. 스크립트(`hotel_search.py`)는
네트워크를 하지 않는다 — 부를 호출을 계획하고(`plan`), itda-hyve 가 `save_as` 로 저장한 파일을 읽어 표로 만든다(`rates`·`heatmap`).
공용 규약(저장 폴더·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
요금:  plan rates   → batch(plan_file) — 호출 2회: Xotelo /rates + 환율(오늘 이미 받았으면 1회) → rates
달력:  plan heatmap → batch(plan_file) — 호출 1회: Xotelo /heatmap → heatmap
```

| 서브커맨드 | 하는 일 |
|---|---|
| `resolve <URL\|텍스트>` | TripAdvisor URL/문자열에서 `hotel_key`(`g<geo>-d<hotel>`) 추출(네트워크 없음) |
| `plan rates` · `plan heatmap` | itda-hyve 호출 계획(계획 파일 + `batch_args`) |
| `rates` | OTA별 1박가·총액 비교표 (원화 환산 병기) |
| `heatmap` | 싼 날/평균/비싼 날 가격 달력 |

### hotel_key 를 먼저 확보한다 (이름→키 해소)

Xotelo 무료 티어에는 이름 검색이 없습니다(`/search`=유료, `/list`=고장, 실측 #1013).
그래서 조회 전에 대상 호텔의 `hotel_key` 를 **두 경로 중 하나로** 확보합니다:

1. **에이전트 web_search** — 사용자가 호텔명만 줄 때. `"<호텔명> tripadvisor hotel"` 로 검색해
   `tripadvisor.com/Hotel_Review-g…-d….html` URL 을 찾고, `resolve` 로 키를 뽑습니다.
   ⚠️ 검색 결과가 맞는 호텔인지 이름·도시로 확인합니다(data-accuracy — 동명 호텔 주의).
   TripAdvisor 페이지는 스킬이 열지 않습니다 — URL 문자열에서 키만 뽑습니다.
2. **사용자 URL/키 직접 제공** — 사용자가 TripAdvisor 링크나 `g294197-d5250436` 를 줄 때. 그대로 `--url`/`--hotel-key`.

### Step 1: 스킬 디렉토리

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
printf "%s\n" "$c"' _ hotel-search itda-travel "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'hotel-search'; $P = 'itda-travel'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

```bash
# macOS/Linux — URL 에서 hotel_key 추출
python3 "$SKILL_DIR/scripts/hotel_search.py" resolve "https://www.tripadvisor.com/Hotel_Review-g294197-d5250436-Reviews-Summit_Hotel_Seoul-Seoul.html"
# → g294197-d5250436
```

### Step 2: 회차 폴더

작업 폴더 아래 `hotel-search-runs/<YYYYMMDD-HHMM>/` 를 회차 폴더로 쓰고 사용자에게 한 줄로 알린다. 같은 대화의 후속 조회는 같은
회차 폴더를 쓴다(환율은 하루 한 번만 받는다). 경로는 둘이다 — **같은 폴더**를 가리킨다.

- `--run-dir` — 스크립트가 보는 경로. Cowork 는 `$HOME/mnt/<연결 폴더 이름>/hotel-search-runs/<시각>`
- `--save-dir`(`plan` 만) — itda-hyve 가 쓰는 **호스트 절대 경로**. Cowork 는 연결 폴더의 호스트 경로 + `/hotel-search-runs/<시각>`
  (Windows 호스트면 `C:\Users\me\작업\hotel-search-runs\<시각>`). Claude Code CLI 처럼 같은 머신이면 두 값이 같다.

연결 폴더가 없으면(Cowork) 폴더 연결을 요청하고 멈춘다.

### Step 3: 요금 비교 (rates)

```bash
# macOS/Linux — Cowork 예시(연결 폴더 호스트 경로 /Users/me/작업, 샌드박스 $HOME/mnt/작업)
R="$HOME/mnt/작업/hotel-search-runs/20261001-0930"; S="/Users/me/작업/hotel-search-runs/20261001-0930"
python3 "$SKILL_DIR/scripts/hotel_search.py" plan rates --hotel-key g294197-d14159727 \
  --checkin 2026-11-19 --checkout 2026-11-21 --run-dir "$R" --save-dir "$S"

# Windows
py -3 "$env:SKILL_DIR\scripts\hotel_search.py" plan rates --url "<TripAdvisor URL>" `
  --checkin 2026-11-19 --checkout 2026-11-21 --run-dir "$env:R" --save-dir "$env:S"
```

출력의 `batch_args` 를 **그대로** `batch` 에 보낸다(호출 목록을 옮겨 적지 않는다 — 스크립트가 계획 파일에 썼다):

```json
{"plan_file": "plan-rates-6560c394d6.json", "save_dir": "/Users/me/작업/hotel-search-runs/20261001-0930"}
```

계획 파일의 호출은 이런 모양이다(2026-10-01 위 명령의 출력 — 참고용, 옮겨 적지 않는다):

```json
{"url": "https://data.xotelo.com/api/rates",
 "params": {"hotel_key": "g294197-d14159727", "chk_in": "2026-11-19", "chk_out": "2026-11-21",
            "currency": "USD", "adults": "2", "rooms": "1"},
 "timeout_sec": 45, "save_as": "hotel/rates-g294197-d14159727-20261119-20261121-USD-a2-r1.json"}
{"url": "https://open.er-api.com/v6/latest/USD", "timeout_sec": 45, "save_as": "hotel/fx-USD-20261001.json"}
```

- `status: "ready"`(받을 것 없음 — 같은 조회를 이 회차 폴더에서 이미 받았다)면 batch 없이 바로 `rates` 로 간다. 요금표 머리에
  **조회 시각**이 찍히니 그대로 보여 준다. 최신 요금이 필요하면 새 회차 폴더로 `plan` 부터.
- `plan` 은 이미 있는 파일을 열어 본다. 실패 자리·빈 본문·잘린 본문·HTTP 오류(5xx·408·429)면 그 호출만 `overwrite: true` 로
  **다시 계획**하고 출력 `retry` 에 싣는다(한 이름에 **다시 받은** 것이 2번까지 — 넘으면 요금·달력은 `retry_exhausted`, 환율은
  `gave_up` 에 싣고 원화 환산만 뺀다). batch 를 보내기 전에 `plan` 을 다시 불러도 파일이 그대로면 세지 않고 같은 계획을 낸다.
  출력에 `warnings` 가 있으면(재시도 기록 파일이 깨짐 등) 사용자에게 한 줄로 전한다.
- `batch` 입력 스키마에 `plan_file` 이 없으면(옛 판) 출력의 `single_calls` 를 한 칸씩 `http_request` 로 보낸다(한 칸이 곧 인자).
- 요청에 `User-Agent` 등 헤더를 더하지 않는다(헤더 없이 성립 — 2026-10-01 실측).
- **응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다.** 필요한 것은 `ok`·`status`·`saved_path` 뿐이다.
- batch 결과에 실패한 호출(`ok: false`)이 있으면 그 `save_as` 자리에 `{"error": {"code": "<code>", "message": "<message>"}}` 를
  써 둔다 — 경로는 이 스크립트가 보는 회차 폴더 기준 `$R/<save_as>` 다(`$S` 는 itda-hyve 호스트 경로라 샌드박스에서 쓰지 않는다).
  판독이 실패 사유를 그대로 전하고, 다음 `plan` 이 그 호출을 다시 계획한다. 파일이 이미 있어 거부된 호출(`invalid_input`)에는 쓰지 않는다.

```bash
python3 "$SKILL_DIR/scripts/hotel_search.py" rates --hotel-key g294197-d14159727 \
  --checkin 2026-11-19 --checkout 2026-11-21 --name "노보텔 앰배서더 서울 동대문" --run-dir "$R"
```

`plan rates` 와 `rates` 에 **같은 호텔·날짜·`--currency`·`--adults`·`--rooms`·`--no-krw`** 를 준다(저장 이름이 그 값에서 나온다).

`rate` 는 각 OTA에서 **예약 가능한 최저 객실의 1박 평균가**입니다. 총액 = 1박가 × 박수.
결과는 1박가 오름차순(최저가에 🏆). Xotelo 는 KRW 미지원이라 **USD 등으로 수집 후 원화로 환산**해
`"519,814원 (USD 384)"` 형태로 병기합니다(환율 참고값 — 예약가 아님). `--no-krw` 로 환산을 끕니다.
환율 출처 표기("Rates By Exchange Rate API")는 이용 조건이라 출력에 늘 붙는다 — 빼지 않고 함께 보여 준다.
`warnings`(환산 생략 사유·묵은 환율·버린 행)는 전부 그대로 전한다.

**예약 링크** — `--name`(호텔명)을 주면 각 OTA 셀이 예약 링크가 됩니다. 라이브 검증(#1015) 결과
OTA마다 안정성이 달라 경로를 나눕니다:
- **Booking.com** = 네이티브 검색 딥링크(호텔명+날짜+인원 프리필 — 그 호텔·그 날짜로 바로 랜딩, 검증됨).
- **Agoda·Trip.com·Klook·공식사이트 등** = **Google 검색 링크**(`<호텔명> <OTA>`) — 이들은 내부 city/hotel
  ID 를 요구해 호텔명만으로 만든 직접 URL 이 깨진다(Agoda 홈 이동·Trip.com 0결과·KLOOK 404 실측). 대신
  Google 검색 최상단이 그 OTA 의 그 호텔 페이지라 클릭 한 번 더로 도달한다.

링크는 사용자가 누르는 주소일 뿐 스킬은 Booking·Google 에 요청하지 않는다. Xotelo 가 정확한 객실 URL 을 안 주므로
Booking 외에는 "그 호텔 페이지로 유도"까지다. `--name` 이 없으면 링크 없이 가격만 나옵니다.

### 지역 + 예산으로 찾기 (에이전트 오케스트레이션)

이 스킬은 **특정 호텔**의 가격만 조회합니다(무료 Xotelo 는 지역별 목록/이름검색 미지원 — `/list` 고장·
`/search` 유료). "장충동에서 8만~13만원 호텔 찾아줘" 같은 **지역+예산·모호** 질의는 에이전트(Claude)가
아래 흐름으로 처리합니다(계약 — 항상 이 순서):

1. **발견** — `WebSearch` 로 그 지역 호텔 후보와 TripAdvisor URL 을 찾는다("장충동 호텔 tripadvisor").
2. **후보 제시 → 선택 대기** — 찾은 **호텔 후보를 리스트로 사용자에게 제시**하고(이름·위치·대략 등급),
   **어느 호텔을 볼지 사용자의 선택을 기다린다.** 임의로 하나를 골라 진행하지 않는다.
   (단, 사용자가 "다 비교해줘"처럼 전체 조회를 명시하면 후보 전부를 조회한다.)
3. **가격** — 선택된 호텔(들)을 `plan rates` → batch → `rates` 로 조회한다(내일 1박 등). 호텔마다 호출 1회 + 환율 1회(하루 한 번)라
   **"N곳이면 호출 N+1회"를 먼저 알린다.** 같은 회차 폴더를 쓰면 환율은 한 번만 받는다.
4. **필터** — 예산 대역(원화)에 드는 것만 골라 표로 제시한다.

호텔명을 **대략만** 알아도(또는 지역만 알아도) 에이전트가 web_search 로 시작한다. 반대로 사용자가
특정 호텔을 콕 집으면 2번(후보 제시)을 건너뛰고 바로 조회한다.

### 가격 달력 (heatmap)

```bash
python3 "$SKILL_DIR/scripts/hotel_search.py" plan heatmap --hotel-key g294197-d14159727 --checkout 2026-11-21 \
  --run-dir "$R" --save-dir "$S"
# → batch_args 를 그대로 batch 에 → 
python3 "$SKILL_DIR/scripts/hotel_search.py" heatmap --hotel-key g294197-d14159727 --checkout 2026-11-21 --run-dir "$R"
```

체크아웃 기준 한 달치 날짜를 싼 날/평균/비싼 날로 분류해, 언제 예약하면 싼지 한눈에 봅니다.

### 실패 표

실패하면 stderr 에 `오류: …` 한 줄(`--format json`·`plan` 이면 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 도)과 종료 코드.

| `error` / itda-hyve 실패 | 뜻 | 대응 |
|---|---|---|
| `not_fetched` | 받은 파일이 없다 | batch 결과를 확인한다. `plan` 과 판독 명령의 인자가 같은지 본다 |
| `hyve`(`hyve_code`) · `network_error`·`timeout` | itda-hyve 가 요청을 못 끝냈다(재시도 뒤) | `plan` 을 같은 인자로 다시 실행한다 — 그 호출만 다시 계획한다(`retry`). 반복되면 사용자에게 알린다 |
| `mismatch` | 응답이 되비친 날짜·통화가 요청과 다르다 | 다른 조회의 파일이다 — 인자를 맞추거나 새 회차 폴더로 |
| `site` | JSON 이 아니거나 `rates`·`heatmap` 이 없다 | JSON 이 아니면(본문 잘림·점검 페이지) `plan` 을 다시 실행한다. 목록이 없으면 구조 변경 — 사용자에게 알린다 |
| `api` · `args`(Xotelo 400) | Xotelo 가 오류 객체를 줬다 | `detail` 을 그대로 전한다(400 은 인자 — 통화·날짜 확인) |
| `truncated`·`http` | 본문 잘림·HTTP 오류(상태를 `detail` 에 싣는다) | `plan` 을 다시 실행하고 그 출력의 `batch_args` 를 그대로 보낸다 |
| `retry_exhausted`(`plan`) | 같은 호출을 2번 다시 받아도 쓸 수 없다 | 더 받지 않는다. 사유를 사용자에게 알리고, 나중에 새 회차 폴더로 `plan` 부터 |
| `invalid_input`(itda-hyve) | 같은 이름 파일이 이미 있다 | 이미 받은 것이다 — 그대로 판독한다 |
| 환율 실패 | 원화 환산만 빠진다(실패 아님) | `warnings`·주석의 "원화 환산 생략 — 사유" 를 그대로 전한다 |

---

## 명령 레퍼런스

`plan rates`·`plan heatmap`·**`rates`**·**`heatmap`** 공통: `--hotel-key g#-d#` **또는** `--url <TripAdvisor URL>` (택1, 필수) · `--run-dir <회차 폴더>`(필수).
`plan …` 은 `--save-dir <같은 폴더의 호스트 절대 경로>`(필수). `rates`·`heatmap` 은 `--name <표시명>`(선택) · `--format {markdown,json}`(기본 markdown) · `--output <경로>`.

| 인자 | 대상 | 설명 |
|------|:---:|------|
| `--hotel-key` / `--url` | 전부 | TripAdvisor `g<geo>-d<hotel>` 키 또는 호텔 페이지 URL (택1) |
| `--checkin` | (plan) rates | 체크인 `YYYY-MM-DD` |
| `--checkout` | 전부 | 체크아웃 `YYYY-MM-DD` (rates 는 체크인보다 이후) |
| `--currency` | (plan) rates | Xotelo 수집 통화 (기본 USD — KRW 미지원, 원화는 환산 표시) |
| `--adults` / `--rooms` | (plan) rates | 성인 수(기본 2) / 객실 수(기본 1) |
| `--no-krw` | (plan) rates | 원화 환산 생략(수집 통화만) |

지원 수집 통화: USD·GBP·EUR·CAD·CHF·AUD·JPY·CNY·INR·THB·BRL·HKD·RUB·BZD (KRW 없음).
엔드포인트·응답 스키마 상세는 [`references/sources.md`](references/sources.md).

---

## Exit Code

| 코드 | 의미 |
|------|------|
| 0 | 성공·계획 |
| 1 | 입력 파일·itda-hyve·판독 실패 (`not_fetched`·`hyve`·`mismatch`·`site`·`api`·`output` …) |
| 2 | 인자 오류 (필수 누락, 날짜 형식/역순, hotel_key 미해소, KRW 등 미지원 통화) |
| 3 | 결과 없음 (해당 날짜 OTA 요금 0건 — 매진·미커버 호텔) |

---

## 제한 사항

- **TripAdvisor 메타값** — 요금 출처가 메타서치라 **실제 예약가와 다를 수 있습니다**("동작함 ≠ 정확함", data-accuracy). 최종 예약 전 해당 OTA에서 재확인하세요.
- **OTA별 대표가 1개** — 객실 타입(디럭스/스위트) 구분이나 객실별 가격은 제공하지 않습니다. `tax`(세금)도 대부분 표기되지 않습니다.
- **OTA 노출 개수 편차** — 호텔·날짜에 따라 1~4개 OTA만 뜰 수 있습니다(재고·커버리지 차이).
- **이름 검색 없음** — 무료 티어는 `hotel_key`(TripAdvisor 등재 호텔)가 필요합니다. 미등재 호텔은 조회 불가.
- **원화는 환산 표시** — Xotelo 가 KRW 미지원이라 환율(`open.er-api.com` — 하루 한 번 갱신, 출처 표기 필수)로 환산한 참고값입니다.
- **조회 전용** — 예약·결제·로그인 계정 액션은 지원하지 않습니다.
- **비공식 표면** — 공식 파트너 API 가 아닙니다. 개인 참고 목적으로만 사용하세요.

## 의존성

표준 라이브러리만 사용합니다(별도 패키지·API 키 불필요). 요청은 itda-hyve 가 `data.xotelo.com`(요금·달력)과
`open.er-api.com`(환율)으로 보냅니다 — 두 호스트 모두 robots.txt 가 없다(404, 2026-10-01). 상세는 [`references/sources.md`](references/sources.md).
