---
name: exchange-rate
description: >
  원화 기준 일별·월 평균 매매기준율(서울외국환중개)을 조회하는 스킬입니다.
  "오늘 달러 환율 알려줘", "이번 달 엔화 평균 환율 보여줘", "EUR 환율 조회해줘", "9월 한 달 달러 환율 일별로"처럼 말하면 됩니다.
  공휴일에는 직전 영업일 환율로 폴백합니다. API 키 없이 동작하며, 요청은 itda-hyve 가 보냅니다.
  [책임 경계] 본 스킬은 매매기준율 조회 전담 — itda-gov:fuel-price 는 국내 유가, itda-gov:ecos 는 한국은행 통계 시계열.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch)이 한다."
user-invocable: true
argument-hint: "[YYYY-MM-DD|YYYY-MM|기간] [통화] - 날짜·월·기간과 통화(기본 USD)"
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, mcp__workspace__bash"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.11.0"
  created_at: "2026-03-18"
  updated_at: "2026-10-01"
  tags: "exchange-rate, currency, forex, korea, keyless, itda-hyve"
---

# Exchange Rate (매매기준율 조회)

서울외국환중개(www.smbs.biz)가 고시하는 **원화 매매기준율**을 일별·월평균·기간 표로 보여 줍니다. 통화 58종(`data/currencies.json` —
사이트 통화 선택 목록과 2026-10-01 전수 대조). 매매기준율은 은행 영업일(월~금) 하루 한 번, 9시 이전에 고시된다(사이트 안내).

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 스크립트는 네트워크를
하지 않는다 — 부를 호출을 만들고(`plan`), itda-hyve 가 `save_as` 로 저장한 파일을 `--input` 으로 읽어 판독한다(`show`).
공용 규약(실패 코드·저장 폴더)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다. 키는 필요 없다.

```
plan → http_request GET(save_as) → show --input <저장한 파일>                  (보통 호출 1회)
plan --write-dir … → batch(plan_file) → show --input <파일1> --input <파일2> …  (1년 넘는 일별 표만 — 조각마다 1회)
```

**`plan` 이 준 `call` 을 그대로 `http_request` 인자로 보낸다.** URL·`params`·`save_as` 를 고쳐 쓰거나 새로 짓지 않는다 —
휴일 폴백 창(요청일부터 14일 전까지)·조각·저장 이름을 스크립트가 계산한다. **날짜를 직접 계산하지 않는다** — "오늘·어제·이번 달·
지난달·최근 N일" 은 `today`·`yesterday`·`this`·`last`·`--last-days N` 로 넘기면 스크립트가 한국 시간으로 푼다(샌드박스 시계는 UTC 일 수 있다).
`save_as` 이름은 `show` 가 인자와 대조하는 식별 계약이다(응답 본문에는 통화·기간이 실려 오지 않는다). `User-Agent` 등 헤더를 더하지 않는다.

## Step 1: 스킬 디렉토리

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
printf "%s\n" "$c"' _ exchange-rate itda-work "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'exchange-rate'; $P = 'itda-work'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

표준 라이브러리만 쓴다(Python 3.10+).

## Step 2: 요청 해석

`$ARGUMENTS` 와 발화에서 질의 하나를 고른다. **`plan` 과 `show` 에 같은 인자를 준다**(`plan` 출력의 `then` 이 날짜를 푼 `show` 인자다).

| 질의 | 인자 | 예 |
|---|---|---|
| 그날 환율(휴일이면 직전 영업일) | `--date YYYY-MM-DD`·`today`·`yesterday` | "오늘 달러 환율" → `--date today` |
| 월평균 | `--month YYYY-MM`·`this`·`last` | "이번 달 엔화 평균" → `--month this --currency 엔` |
| 월평균 표(최대 60개월, 호출 1회) | `--month-from YYYY-MM --month-to YYYY-MM` | "올해 월평균 추이" → `--month-from 2026-01 --month-to this` |
| 일별 표 | `--from YYYY-MM-DD --to YYYY-MM-DD`(끝은 `today` 도 됨) · `--last-days N` | "9월 한 달 달러 일별" → `--from 2025-09-01 --to 2025-09-30` |
| 통화 | `--currency` 코드 또는 한국어 별칭(`달러`·`엔`·`유로`·`위안`…), 기본 `USD` | |

- 한 달 일별은 날짜마다 따로 부르지 말고 표 한 번으로 받는다. 비교("이번 달과 지난달 엔화 평균")는 월평균 표 한 번(`--month-from last --month-to this`).
- 일별 표는 366일마다 한 조각(호출)이다 — `plan` 의 `calls` 가 2 이상이면 **호출 수를 먼저 알린다**. 최대 10조각, 그보다 길면 월평균 표를 쓴다.
- 2000년 전, 오늘 이후 날짜·달은 `plan` 이 `args` 로 거부한다.
- "위안" 은 CNH 다(사이트가 CNH 를 "위안" 으로 부른다). CNY 는 2016-01-01부터 고시되지 않는다.

## Step 3: 호출 계획 → itda-hyve → 판독

`--save-dir` 에는 **Cowork 연결 폴더의 호스트 경로**(macOS `/Users/…`, Windows `C:\Users\…` — 작은따옴표로 감싼다)를 넣는다.
Cowork 에서는 **필수**다 — 생략하면 itda-hyve 기본 저장 폴더에 떨어져 샌드박스가 읽지 못한다. 연결 폴더가 없으면 사용자에게 폴더를
연결해 달라고 요청하고 멈춘다. Claude Code 처럼 같은 머신이면 생략해도 된다.

```bash
python3 "$SKILL_DIR/scripts/exchange_rate.py" plan --date 2025-10-05 --currency USD --save-dir "/Users/me/Projects/작업폴더"
```

출력의 `call` 을 그대로 `http_request` 로 보낸다(위 명령을 2026-09-30 에 낸 출력):

```json
{"url": "http://www.smbs.biz/ExRate/StdExRate_xml.jsp",
 "params": {"arr_value": "USD_2025-09-21_2025-10-05"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "exrate/daily-USD-20250921-20251005-20260930.xml"}
```

- 월평균은 URL 이 `…/MonAvgStdExRateUSD_xml.jsp`(USD)·`…/MonAvgStdExRate_xml.jsp`(그 밖), `params` 는 `{"arr_value": "JPY_2025-01_2025-09"}` 꼴이다.
  어느 쪽이든 `plan` 이 정한다. 주소가 `http://` 인 것은 사이트의 https 인증서가 `www.smbs.biz` 에 맞지 않아서다(2026-09-30 실측).
- **끝이 오늘인 질의**(오늘 환율·이번 달 평균·오늘까지 표)는 저장 이름에 받은 시각(`…-YYYYMMDDHHMM.xml`)이 붙는다. 같은 날 다시 물으면
  새 이름으로 다시 받는다 — 아침에 고시 전 값을 받았어도 낮에는 당일 값을 받는다.
- **조각이 둘 이상**(`calls` ≥ 2)이면 `--write-dir <연결 폴더의 이 환경 경로>` 를 더해 다시 `plan` 한다. 스크립트가 연결 폴더에 batch 계획 파일을 쓰고
  `batch: {"save_dir": "<--save-dir>", "plan_file": "exrate/plan-….json"}` 을 낸다 — 그 객체를 **그대로** itda-hyve **`batch`** 인자로 준다
  (`calls` 를 옮겨 적지 않는다. `plan_file` 은 `save_dir` 기준 상대 경로라 `save_dir` 를 빼면 기본 저장 폴더에서 찾다가 `not_found` 다).
  `batch` 의 입력 스키마에 `plan_file` 이 없는 옛 itda-hyve 면 `--write-dir` **없이** 다시 `plan` 해 받은 `call_list` 의 호출을 하나씩 `http_request` 로 보낸다.

저장한 파일을 **같은 인자**로 넘긴다(조각마다 `--input` 한 번):

```bash
# Cowork: 연결 폴더는 샌드박스의 $HOME/mnt/<폴더 이름> — 그 뒤에 saved_path 를 붙인다
python3 "$SKILL_DIR/scripts/exchange_rate.py" show --date 2025-10-05 --currency USD \
    --input "$HOME/mnt/작업폴더/exrate/daily-USD-20250921-20251005-20260930.xml"

# Windows
py -3 "$env:SKILL_DIR\scripts\exchange_rate.py" show --date 2025-10-05 --currency USD --input "…\exrate\daily-USD-20250921-20251005-20260930.xml"
```

`--input` 에는 **이 환경에서 보이는 경로**를 준다 — Cowork 는 `$HOME/mnt/<폴더>/…`, 같은 머신이면 `save_dir`/`saved_path`. 호스트 경로(`C:\…`)를
Cowork 에 그대로 넘기면 "입력 파일이 없습니다" 다. 파일을 `find` 로 뒤지지 않는다. 계산에 쓸 값이 필요하면 `show … --format json`
(필드 `rates`·`result_date`·`fallback`·`refetch`·`warnings`).

`show` 가 보는 것 — 어긋나면 결과를 내지 않고 실패로 끝낸다:

- 저장 이름이 인자로 다시 만든 조각과 같은가(통화·종류·기간), 조각이 빠지거나 겹치지 않았는가. 받은 날이 조회 끝보다 앞이거나 오늘 이후면 고쳐 쓴 이름이다(`input`)
- 응답이 환율 차트 XML 이고 `</chart>` 로 끝나는가(`site`·`truncated`), 일별·월평균 종류가 맞는가, 모든 행이 그 조각의 기간 안인가(`mismatch`)
- `--date`: 창 안에 고시가 하나도 없으면 `empty` — **14일보다 더 거슬러 가지 않는다**(통화 코드 오류도 사이트는 빈 차트로 답한다)
- 일별 표: 이어진 두 고시일 사이 공백이 14일을 넘으면 `gap`(폴백 창과 같은 근거 — 실측 최장 공백은 2017 추석 연휴 11일, 2017-09-29 → 10-10).
  시작 쪽 공백·고시 없는 평일(공휴일일 수 있다)은 실패가 아니라 `warnings` 로 알린다
- 월평균 표: 가운데·끝 달이 비면 `gap`, 앞쪽 달이 비면 `warnings`. 이번 달이 아직 집계 전이면 `empty`(단월)·`warnings`(표) — 이번 달은 일별 표로 본다
- 요청일이 받은 날 당일(평일)인데 고시가 없으면 직전 영업일로 폴백하고 `refetch: true` + "아직 고시 전일 수 있다" 경고. 폴백 거리가 11일을 넘으면 경고

## 응답 요약·재시도

- **응답 요약의 `final_url`·헤더(`Set-Cookie` 포함)를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.**
- **응답 `status` 가 200 이 아니면 그 파일을 스크립트에 넘기지 않는다** — 상태 코드를 사용자에게 알리고 멈춘다.
- itda-hyve 가 `invalid_input` 을 주면 **메시지를 본다**. "이미 있다(덮어쓰지 않는다)" 면 같은 이름 = 같은 질의로 이미 받은 파일이니 그 파일로 `show` 한다
  (끝이 오늘인 질의는 이름에 분 단위 시각이 있어 같은 분 안에서만 생긴다). 단, `show` 가 거부했던 파일이나 `status` 가 200 이 아니었던 파일이면
  `--save-dir` 를 새 하위 폴더로 바꿔 `plan` 부터 다시 한다. 그 밖의 `invalid_input`(상대 경로·숨김 폴더·홈 밖 `save_dir`)은 작업 폴더를 바로잡는다.
- `show` 결과의 `refetch: true`(고시 전·집계 전일 수 있음)는 사용자에게 그 경고를 전한다. 나중에 같은 질문을 받으면 `plan` 부터 다시 한다(새 이름).

| itda-hyve 실패 | 대응 |
|---|---|
| `network_error`(연결 실패) | itda-hyve 가 이미 재시도했다. 같은 호출을 되풀이하지 말고 사용자에게 알린다 |
| `timeout` | 1회만 다시 보낸다. 다시 보낸 것이 "이미 있다" 로 거부되면 늦게 저장된 파일이니 그대로 `show` 한다(비었으면 `show` 가 판정한다) |
| `invalid_input` | 위 메시지별 규칙 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `plan` 출력 그대로(`save_as` 포함) 다시 받는다 |

## Step 4: 표시

`show` 의 마크다운 출력을 **고치지 않고 그대로** 보여 준다(숫자를 다시 타이핑하지 않는다). `⚠️` 줄(폴백·고시 전·진행 중인 달·고시 없는 평일)과
출처 줄을 빼지 않는다.

## 오류 처리

실패하면 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 를 쓰고 exit 1(인자 오류 `args` 는 exit 2 — argparse 오류도 같은 JSON). `detail` 을 그대로 전한다.

| `error` | 뜻 | 대응 |
|---|---|---|
| `args` | 모르는 통화·날짜 형식·2000년 전·오늘 이후·조각·개월 상한 초과·`--save-dir` 상대 경로 | 인자를 고친다. 통화는 `data/currencies.json` 코드·별칭 |
| `input` | 파일 없음·저장 이름이 계약과 다름·인자와 다른 질의·빠진/겹친 조각(`missing`) | `plan` 의 `save_as` 그대로 저장했는지, 두 단계에 같은 인자를 줬는지, 조각을 전부 넘겼는지 |
| `empty` | 창·기간·달에 고시 없음(이번 달 월평균 집계 전·CNY 고시 중단 포함 — 사유가 `detail` 에) | `detail` 대로 안내한다. 창을 넓혀 다시 부르지 않는다 |
| `gap` | 일별 표 가운데·끝에 14일 넘는 공백, 월평균 표의 빈 달(`gaps`) | 결과를 말하지 않는다. 새 하위 폴더로 `plan` 부터 한 번, 되풀이되면 알린다 |
| `mismatch` | 다른 종류·다른 기간의 응답 | 넘긴 파일을 확인하고, 맞으면 새 하위 폴더로 `plan` 부터 |
| `site` | 차트 XML 이 아님(점검·오류 페이지)·라벨·값 형식 오류 | 응답 `status` 를 먼저 본다. 되풀이되면 결함 신고 — 추측 수정 금지 |
| `truncated`·`http` | 본문 잘림, 또는 응답 JSON 전체를 옮겨 적은 파일의 HTTP 오류 | 새 하위 폴더로 `plan` 부터 |
| `hyve` | itda-hyve 실패 자리 파일(`hyve_code` 동봉) | 위 실패 표대로 |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 |
|---|---|
| 한국은행 공식 통계 시계열(ECOS 환율 통계) | itda-gov:ecos |
| 국내 유가 | itda-gov:fuel-price |
| 은행별 현찰·송금 환율(살 때·팔 때) | 은행 고시 — 본 스킬은 매매기준율만 |
