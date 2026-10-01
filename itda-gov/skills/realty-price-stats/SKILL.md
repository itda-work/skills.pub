---
name: realty-price-stats
description: >
  한국부동산원 R-ONE 가격지수·전월세전환율과 realty-deals raw 데이터 기반 파생 통계를 제공하는 스킬입니다.
  "강남구 아파트 주간 가격지수 6개월치 가져와줘", "분당구 최근 3개월 평균·중위 매매가 통계 보여줘", "전월세전환율 추이 조회해줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 R-ONE 가격지수와 파생 통계 전담 — 실거래 원본 행 수집은 itda-gov:realty-deals(derive 의 입력), 공급·청약 지표는 itda-gov:realty-supply.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch plan_file)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "지수 유형 + 기간 (예: 주간 가격지수 2026년 1~6월 / 강남구 아파트 매매 통계 2026년 1월)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.12.1"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-10-01"
  tags: "R-ONE, price index, statistics, realestate, reb"
---

# realty-price-stats

한국부동산원 **R-ONE** 가격지수·전월세전환율과 `realty-deals` raw 데이터 기반 **파생 통계**를 제공합니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 여러 쪽은
**itda-hyve 의 `batch`**(`mcp__remote-devices__itda-hyve__batch`)로 한 번에 받을 수 있다.
스크립트는 네트워크를 하지 않는다 — 호출 계획을 만들고, itda-hyve 가 `save_as` 로 저장한 응답을 `--input` 으로 읽어
오류 판정·전량 대조·정리만 한다. 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.
두 명령 모두 같은 모양이다 — **계획 → batch(`plan_file`) → 가공(모자라면 `--next-plan` 으로 다음 계획)**.

```
rone  : rone-plan --write → batch(plan_file) → rone   --next-plan → (모자라면 batch → rone 다시)
derive: plan      --write → batch(plan_file) → derive --next-plan → (모자라면 batch → derive 다시)
```

키는 사용자가 **itda-hyve GUI 시크릿 탭**에 등록해 둔 것을 **이름으로만** 가리킨다. 값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다.

| 명령 | 시크릿 이름 | 발급 |
|---|---|---|
| `rone-plan`·`rone`(R-ONE 가격지수) | `RONE_API_KEY` | <https://www.reb.or.kr/r-one/> 로그인 → Open API 에서 인증키 신청(「인증키 발급내역」에서 확인) |
| `plan`·`derive`(실거래 파생 통계) | `KO_DATA_API_KEY` | data.go.kr 실거래 서비스 활용신청 — **Decoding 키**(realty-deals 와 같은 키) |

## 주의사항

- KB 데이터허브는 공식 API가 없으므로 스크래핑하지 않습니다 (R21).
  KB 데이터가 필요하면 공식 다운로드 페이지(https://data.kbland.kr)에서 직접 파일을 받아 활용하세요.
- R-ONE 인증키가 없으면 R-ONE 은 **sample(5행)만** 돌려준다 — 스크립트가 쪽 행 수 대조로 잡아 `error: input` 으로 멈춘다.

## 지원 R-ONE 지수 유형

| 키 | 지수 | 통계표 ID(`STATBL_ID`) | 주기(`DTACYCLE_CD`) · 시점 |
|----|------|------|------|
| `weekly` | 주간 아파트 매매가격지수(주간아파트동향) | `T244183132827305` | `WK` · `YYYYWW`(ISO 주차 아님 — 라벨은 그 주 월요일) |
| `monthly` | 월간 아파트 매매가격지수(월간동향) | `A_2024_00045` | `MM` · `YYYYMM` |
| `jeonse_rate` | 지역별 전월세 전환율_아파트(%) | `A_2024_00156` | `MM` · `YYYYMM` |

통계표 ID 는 R-ONE 「통계코드 검색」에서 확인했다(2026-09-30). 근거·요청 인자·메시지 코드: [references/rone-openapi.md](references/rone-openapi.md).

## 사전 요구사항

먼저 스킬 디렉토리를 확정합니다 (이후 모든 실행 명령이 `$SKILL_DIR` 기준).

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
printf "%s\n" "$c"' _ realty-price-stats itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'realty-price-stats'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

## 사용 예시

### R-ONE 가격지수 (rone) — 요청은 itda-hyve, 가공은 스크립트

```
rone-plan(1쪽 호출) → 1쪽 받기 → rone → (모자라면 next_calls 받기 → rone 다시) → 결과
```

한 질의는 **전국 모든 지역 행**을 준다(주간 지수 한 주 약 230행, 월간 한 달 230행 — 실측). 한 쪽은 1,000행이다.

**1단계 — 호출 계획 (네트워크 불요)**

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" rone-plan \
  --index-type weekly --start-month 202601 --end-month 202606 \
  --write "$HOME/mnt/작업폴더/rone/plan-1.json"
# Windows: py -3 "$env:SKILL_DIR\scripts\price_stats_cli.py" rone-plan --index-type weekly --start-month 202601 --end-month 202606
```

- 기간은 월(`YYYYMM`)로 준다. 주간은 스크립트가 시점 ID 를 어림해 **앞뒤로 한 주씩 넓힌** 창(`START_WRTTIME`·`END_WRTTIME`)을 만든다 —
  R-ONE 주차는 ISO 주차가 아니라 달력으로 확정할 수 없다. 날짜 계산을 손으로 하지 않는다. 기간을 가르는 것은 3단계다(아래 **주간 포함 규칙**).
- 출력 `calls` 의 `args` 가 `http_request` 인자 그대로다. `--write` 는 같은 내용을 batch `plan_file` 로 쓴다. 계획 파일은 **그 회차 `save_dir` 안**
  (Cowork `$HOME/mnt/<폴더 이름>/…`)에 쓴다 — `plan_file` 은 `save_dir` 기준 상대 경로로 풀린다.

**2단계 — itda-hyve 의 `http_request` 로 받기** (`calls[i].args` 에 `save_dir` 만 더한다)

```json
{"url": "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do",
 "params": {"KEY": "{{secret:RONE_API_KEY}}", "Type": "json", "pIndex": "1", "pSize": "1000",
            "STATBL_ID": "T244183132827305", "DTACYCLE_CD": "WK",
            "START_WRTTIME": "202552", "END_WRTTIME": "202628"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "rone/weekly-202601-202606-p1.json"}
```

- `KEY` 는 반드시 `params` 에 둔다(URL 쿼리에 자리표시자를 쓰면 `invalid_input`). `params` 값은 전부 문자열이다.
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다**(`rone/<지수 유형>-<시작월>-<종료월>-p<쪽>.json`). 응답 본문에 쪽 번호가 없어 3단계가 이 이름으로 질의와 쪽을 가른다.
- `save_dir` 는 절대 경로(사용자 홈 아래 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외). 같은 이름이 있으면 `invalid_input` —
  새 하위 폴더(예: `…/작업폴더/rone-2회차`)로 바꾸거나, 사용자가 확인했을 때만 `overwrite: true`.
- 여러 쪽은 **`batch` + `plan_file`**: `{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "rone/plan-next-1.json"}`.
  batch 는 GET 만, 한 번에 최대 40호출이다 — 스크립트가 40개씩 나눠 `plan-next-1a.json`·`plan-next-1b.json`… 으로 쓰고 `plan_files` 에 알려 준다(파일마다 한 번씩 부른다).
  도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면 옛 판이다 — `calls` 를 하나씩 `http_request` 로 부른다.
- 응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

**3단계 — 저장한 응답을 가공** (Cowork 는 `save_dir` 의 폴더 이름 뒤에 `saved_path` 를 붙인다)

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" rone \
  --input "$HOME/mnt/작업폴더/rone/weekly-202601-202606-p1.json" \
  --region 서울 --next-plan "$HOME/mnt/작업폴더/rone/plan-next-1.json"
```

- 여러 쪽은 파일을 **전부 나열**한다(순서 무관). 한 번에 **한 질의**(지수 유형·기간)만 넘긴다.
- `--region` 은 R-ONE 분류 전체명(예: `서울>강남지역>동남권>강남구`) 부분일치 필터다(`전국` 은 정확일치). 받는 행은 줄지 않는다 — 출력만 거른다.
- **주간 포함 규칙** — 행의 `WRTTIME_DESC`(그 주 월요일)가 **시작월 1일~종료월 말일 안**인 주만 남긴다. 넓혀 받은 창 밖 주는 거르고
  수를 `period_filter`(`kept`·`dropped_before`·`dropped_after`)에 싣는다. 요청 기간의 월요일 중 결과에 없는 주가 있거나(안쪽 결손),
  기간이 끝난 지 2주가 지났는데 기간 뒤 주가 한 행도 없으면(`dropped_after` 0 — 끝 결손) `warnings` 에 적힌다 — 그대로 사용자에게 전한다.
  월간은 받은 행의 시점이 요청 기간 밖이면 `error: input` 이다.
- **연초 첫 주** — 월요일 기준이라 R-ONE 의 "2021년 1주"(`202101`, 월요일 2020-12-28)는 2020년 12월 요청에 들고 2021년 1월 요청에서는 빠진다.
  "2021년 1월 주간지수" 의 첫 주가 R-ONE 사이트 표기와 한 주 다를 수 있다고 말한다.
- `--format table` 머리의 괄호는 요청 기간(`period_filter.from~to`)이다. `start_wrttime`·`end_wrttime` 은 넓힌 **요청 창**이라 기간으로 옮기지 않는다.

**쪽 이어받기 — 모자라면 실패한다.** 필요한 쪽 = ⌈`list_total_count` ÷ 1000⌉. 모자라면 `status: "error"`, `error: "incomplete"` 와
`need_pages`·`will_truncate`·`next_call_count`·`next_calls`(2단계와 같은 형식)를 준다. `--next-plan` 을 줬으면 계획 파일(`plan_files`)을 쓰고
stdout 에는 `next_calls` 앞 3개만 싣는다.

1. **1쪽을 받은 직후 `need_pages` 로 남은 호출 수를 사용자에게 먼저 알린다.** `will_truncate: true`(상한 `--max-pages` 20쪽 = 2만 행 초과)이거나
   남은 호출이 10개를 넘으면 **받기 전에 묻는다** — 기간을 좁힐지, `--max-pages` 를 늘릴지.
2. `next_calls` 를 받고 **지금까지의 파일 전부 + 새 파일**로 다시 `rone` 한다. 회차마다 `--next-plan` 이름을 `plan-next-2.json` 처럼 바꾼다.
3. `status: "ok"` 가 나올 때까지 되풀이한다. **incomplete 인 채로 결과를 말하지 않는다.** 결과에 `truncated: true` 면 미조회분이 있다고 알린다.

전량 대조는 건수만 보지 않는다 — 쪽마다 `list_total_count` 가 같아야 하고, 같은 쪽이 두 번 오거나 쪽 사이 행이 겹치거나, 마지막이 아닌 쪽이
1,000행이 아니면(sample 키·pSize 변조) `error: "input"` 이다. 그때는 그 질의를 1쪽부터 새 하위 폴더에 다시 받는다.

**응답 판정 — HTTP 200 은 성공이 아니다.** R-ONE 은 오류도 HTTP 200 + `{"RESULT": {"CODE": "ERROR-…"}}` 로 준다(실측). 판정은 3단계 스크립트가
대신 한다(`error: "api"` + `error_code`). `INFO-200`(데이터 없음)은 빈 결과 성공이다.

| 코드 | 뜻 | 대응 |
|---|---|---|
| `ERROR-290` | 인증키 무효 | 시크릿 탭의 `RONE_API_KEY` 확인(앞뒤 공백·재발급) |
| `ERROR-300` | 필수 값 누락 | plan 이 준 `params` 를 그대로 보냈는지 확인 |
| `ERROR-336` | 한 번에 1,000건 초과 | `pSize` 는 1000 이하 |
| `ERROR-337` | 일별 트래픽 초과 | **멈춘다** — 오늘은 더 부르지 않는다 |
| `ERROR-333`·`ERROR-310` | 요청위치 타입 오류·서비스 없음 | URL·`pIndex` 확인 |
| `ERROR-500`·`600`·`601` | R-ONE 서버·DB·SQL 오류 | 잠시 뒤 1회만 다시 |
| `INFO-300` | 관리자가 인증키 사용 제한 | R-ONE 고객지원 문의 |

**itda-hyve 실패 코드**

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `RONE_API_KEY` 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `www.reb.or.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `invalid_input`(같은 이름 파일) | `save_dir` 를 새 하위 폴더로 바꾸거나, 사용자 확인 뒤 `overwrite: true` |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | `timeout_sec` 을 늘려 1회만 다시 보낸다(Cowork 는 60초에서 끊으므로 50 이하) |

`rone` 옵션: `--input`(필수) · `--region` · `--max-pages`(기본 20) · `--next-plan` · `--format json|table`.
`rone-plan` 옵션: `--index-type`·`--start-month`·`--end-month`(필수) · `--write`.

### 실거래 파생 통계 (derive) — 요청은 itda-hyve, 계획과 가공은 스크립트

derive 의 네트워크는 **itda-hyve**(`mcp__remote-devices__itda-hyve__batch`·`mcp__remote-devices__itda-hyve__http_request`)로만 나간다.
스크립트는 **호출 계획을 파일로 쓰고**(`plan`·`--next-plan`), itda-hyve 가 `save_as` 로 저장한 **매매** 응답 XML 을 `--input` 으로 읽어
전량 대조·통계만 한다. 쪽 번호·`DEAL_YMD`·저장 이름은 스크립트가 정한다 — **호출 JSON 을 손으로 옮겨 적지 않는다.**
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
지역코드 확정 → plan --write(호출 수 알림) → batch(plan_file) → derive --next-plan → incomplete 면 batch(plan_files) → derive 다시
```

1. **지역코드** — 5자리 법정동코드(`LAWD_CD`)가 필요하다. 모르면 realty-deals 의 `regions` 로 찾거나 사용자에게 묻는다(짐작하지 않는다).
2. **계획** — 회차 폴더 `price-stats/<코드>-<시작월>-<종료월>` 안에 계획 파일을 쓴다(Cowork 연결 폴더는 `$HOME/mnt/<폴더 이름>`).

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
D="$HOME/mnt/작업폴더/price-stats/11680-202607-202608"
python3 "$SKILL_DIR/scripts/price_stats_cli.py" plan \
  --region "강남구" --type apt_trade --start-month 202607 --end-month 202608 --write "$D/plan-1.json"
```

```powershell
$D = "$HOME\mnt\작업폴더\price-stats\11680-202607-202608"
py -3 "$env:SKILL_DIR\scripts\price_stats_cli.py" plan --region "강남구" --type apt_trade --start-month 202607 --end-month 202608 --write "$D\plan-1.json"
```

   출력의 `call_count`(1차 = 달 수)를 먼저 사용자에게 알린다. 쪽 수는 `ceil(totalCount/100)` 이라 1쪽을 받아 봐야 안다
   (실측 2026-08 강남구 아파트 매매 95건 = 1쪽). 40개를 넘으면 `plan_files` 가 `plan-1a.json`·`plan-1b.json` 처럼 여럿이다.
   같은 지역·기간을 다시 받으면 이름이 겹친다 — `--tag 2` 로 새 회차 폴더를 쓴다.
3. **받기** — `plan_files` 의 파일마다 `batch` 를 한 번씩 부른다. 경로만 넘긴다:

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "price-stats/11680-202607-202608/plan-1.json"}
```

   - `save_dir` 는 Cowork 연결 폴더의 호스트 경로. 계획 파일에는 `calls`·`timeout_sec: 50` 이 들어 있다(GET 만, 한 번에 최대 40호출).
   - 결과의 `failed` 가 0 이 아니면 그 호출의 `error.code`·`message` 를 사용자에게 전하고 멈춘다.
   - **응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `ok`·`failed`·`saved_path` 뿐이다.**
     itda-hyve 0.10.4 전 판은 `save_as` 응답의 `final_url` 에서 키를 가리지 않았다(itda-work/itda-hyve#31) — 판과 관계없이 옮겨 적지 않는다.
   - 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면(옛 판) `plan` 을 `--write` 없이 불러 `calls` 를 받고,
     호출마다 그 `args` 에 `save_dir`·`"timeout_sec": 50` 을 더해 `http_request` 를 하나씩 부른다. 호출 한 칸은 이렇다:

```json
{"url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "LAWD_CD": "11680", "DEAL_YMD": "202608", "pageNo": "1", "numOfRows": "100"},
 "timeout_sec": 50, "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "price-stats/11680-202607-202608/apt_trade-11680-202608-p1.xml"}
```

4. **가공** — 회차 폴더의 파일을 글로브로 전부 넘긴다(따옴표로 감싼 패턴은 스크립트가 펼친다 — PowerShell 도 같다).

```bash
python3 "$SKILL_DIR/scripts/price_stats_cli.py" derive \
  --region "강남구" --type apt_trade --start-month 202607 --end-month 202608 \
  --input "$D/apt_trade-*.xml" --next-plan "$D/plan-2.json"
# 단지별: 위에 --group-by apt_nm
```

5. **2차** — `status: "incomplete"`(exit 1)면 통계를 내지 않고 `next_call_count`·`plan_files` 를 준다. 호출 수를 알리고 3처럼 받은 뒤
   같은 명령을 다시 돌린다(`--next-plan` 은 새 이름). **쪽 수를 짐작하지 않는다.** `refetch`·`need_overwrite: true` 면 그 달은 받는 사이
   목록이 바뀌었다(쪽마다 `totalCount` 가 다름 등) — 같은 이름으로 1쪽부터 덮어써 다시 받아야 하므로, 사용자 확인 뒤 `--overwrite` 를 붙인다.
   1차·2차는 이어서 부른다 — 실거래는 매일 는다.

**해제 거래는 뺀다** — 매매 응답의 `cdealType` 이 있으면(실측 `O`) 해제된 거래다. 평균·중위를 흔들므로 기본으로 빼고 뺀 수를
`excluded.cancelled` 에 싣는다(실측 강남구 2026-08: 95건 중 4건 — 평균 297,232 → 303,915, 중위 280,000 → 285,000 만원). 원하면 `--include-cancelled`.

인자(derive): `--input`(필수, 파일·글로브) · `--start-month`·`--end-month`(필수, `YYYYMM` — 기간 밖 달의 파일은 거부) ·
`--region` 또는 `--lawd-cd`(응답 `sggCd` 와 대조) · `--type`(매매 8종, 기본 `apt_trade` — 받은 파일의 저장 이름·단지명 필드와 대조) ·
`--group-by apt_nm` · `--include-cancelled` · `--next-plan FILE` · `--overwrite`(사용자 확인 뒤에만). `plan` 은 `--region`/`--lawd-cd`·`--type`·
`--start-month`·`--end-month`·`--tag`·`--write`.

| `--type` | `<서비스>` | `--type` | `<서비스>` |
|---|---|---|---|
| `apt_trade` | `RTMSDataSvcAptTrade` | `land_trade` | `RTMSDataSvcLandTrade` |
| `offi_trade` | `RTMSDataSvcOffiTrade` | `biz_trade` | `RTMSDataSvcNrgTrade` |
| `rh_trade` | `RTMSDataSvcRHTrade` | `factory_trade` | `RTMSDataSvcFctTrade` |
| `sh_trade` | `RTMSDataSvcSHTrade` | `presale_trade` | `RTMSDataSvcSilvTrade` |

**저장 이름이 식별 계약이다** — `<유형>-<코드>-<YYYYMM>-p<쪽>.xml`. 스크립트가 이름을 본문(`pageNo`·거래월·`sggCd`)과 대조하고,
같은 (달, 쪽) 이 두 파일에 있으면 거부한다. 이름을 바꾸지 않는다.

**응답 판정** — `save_as` 로 받으면 판정은 스크립트가 한다. 루트 `<response>` + `resultCode` `000` 만 성공이고,
그 밖의 코드(`03` 데이터 없음 · `20` 활용 미승인 · `22` 일일 트래픽 초과 — 멈춘다 · `30` 미등록 키 — Decoding 키 확인 · `31` 만료),
게이트웨이 오류(`<OpenAPI_ServiceResponse>`), XML 이 아닌 본문, 닫히지 않은 XML(절단)은 `error: api` + `code` 다.

## 출력 형식 (JSON)

### R-ONE 지수

```json
{
  "status": "ok",
  "count": 1,
  "results": [
    {"index_type": "weekly", "period": "202609", "period_desc": "2026-02-23", "region": "전국",
     "region_code": 50001, "item": "지수", "value": 98.8572393202812, "unit": "지수"}
  ],
  "index_type": "weekly", "label": "주간 아파트 매매가격지수(주간아파트동향)",
  "statbl_id": "T244183132827305", "cycle": "WK",
  "start_month": "202602", "end_month": "202602", "start_wrttime": "202605", "end_wrttime": "202610",
  "total_count": 1380, "scanned_count": 1380, "need_pages": 2, "truncated": false, "region": "전국",
  "period_filter": {"rule": "주간: WRTTIME_DESC(그 주 월요일)가 시작월 1일~종료월 말일 안인 주만 남긴다",
                    "from": "2026-02-01", "to": "2026-02-28", "kept": 920, "dropped_before": 230, "dropped_after": 230},
  "sources": [{"path": "…/rone/weekly-202602-202602-p1.json", "page": 1, "total_count": 1380, "row_count": 1000},
              {"path": "…/rone/weekly-202602-202602-p2.json", "page": 2, "total_count": 1380, "row_count": 380}],
  "warnings": []
}
```

`results` 는 시점·지역 순이다. `value` 는 숫자(값이 없으면 `null`), `period` 는 R-ONE 시점 ID(주간 `YYYYWW`·월간 `YYYYMM`), `period_desc` 는
R-ONE 시점 설명(주간은 기준일). `total_count` 는 R-ONE `list_total_count`, `scanned_count` 는 받은 행 수(필터 전), `count` 는 기간·지역 필터 뒤 행 수.
`period_filter` 는 기간 대조 규칙과 남긴 행·거른 행(요청 기간 앞·뒤) 수다.

### 파생 통계

```json
{
  "status": "ok",
  "count": 0,
  "results": [],
  "derived_summary": {
    "avg": 120000,
    "median": 115000,
    "max": 200000,
    "min": 80000,
    "count": 95
  },
  "region": "강남구",
  "lawd_cd": "11680",
  "type": "apt_trade",
  "start_month": "202608",
  "end_month": "202608",
  "months": [{"month": "202608", "total_count": 95, "collected": 95}],
  "excluded": {"cancelled": 4},
  "include_cancelled": false
}
```

달마다 받은 건수가 `totalCount` 에 못 미치거나, 기간 중 파일이 없는 달이 있거나, 받는 사이 목록이 바뀐 달(`refetch`)이 있으면
`status: "incomplete"` + exit 1 이고 **통계를 내지 않는다**(일부 쪽만으로 낸 평균·중위는 조용히 틀린다).

```json
{"status": "incomplete", "error": "incomplete", "missing_pages": {"202607": [2]}, "next_call_count": 1,
 "plan_files": ["price-stats/11680-202607-202608/plan-2.json"],
 "warnings": ["202607: totalCount=170 인데 수집=100 — 페이지를 더 받아야 합니다"]}
```

## 에러 코드

| 상황 | status | error | 조치 |
|------|--------|-------|------|
| 저장된 파일이 R-ONE 오류 응답 (rone) | error | api | `error_code` 를 위 R-ONE 코드 표로 풀어 안내 |
| 쪽 모자람 (rone) | error | incomplete | `next_calls` 대로 더 받는다(받기 전 `need_pages`·`will_truncate` 확인) |
| 파일 없음·이름 규칙 위반·질의 혼입·총건수 불일치·쪽 중복·행 겹침·쪽 행 수 이상 (rone) | error | input | 그 질의를 1쪽부터 새 하위 폴더에 다시 받는다 |
| 입력이 잘림·HTTP 오류·itda-hyve 실패 자리 (rone) | error | truncated·http·hyve | `save_as` 로 다시 받는다 / 실패 코드 표 |
| 인자 오류 (rone-plan 월 형식 등) | error | argument | exit 2 — 인자 확인 |
| 입력 파일 없음·매매 아닌 파일·`--type` 불일치·알 수 없는 지역명·이름↔본문 불일치·같은 쪽 중복·기간 밖 달 (plan·derive) | error | args | `detail` 대로 인자·파일을 고친다 |
| 저장된 파일이 오류 응답 (derive) | error | api | `code` 를 위 응답 판정으로 풀어 안내 |
| 모델이 batch 실패 자리를 파일로 적었다 (derive) | error | hyve | `code`(`secret_missing` 등)를 아래 행대로 안내하고 멈춘다 |
| 쪽·달 누락, 받는 사이 목록 변경 (derive) | incomplete | incomplete | `plan_files` 를 받는다. `need_overwrite` 면 확인 뒤 `--overwrite` |
| `secret_missing` (itda-hyve) | — | — | GUI 시크릿 탭에 `RONE_API_KEY`(rone)·`KO_DATA_API_KEY`(derive) 등록을 안내하고 멈춘다. 값을 대화로 받지 않는다 |
| `secret_host_denied` (itda-hyve, derive) | — | — | URL 호스트가 `apis.data.go.kr` 인지 먼저 확인 |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 실거래 개별 건 원본(CSV/JSON) | itda-gov:realty-deals |
| 미분양·인허가·청약 | itda-gov:realty-supply |
| 전세가율·갭 | itda-gov:realty-jeonse-gap |
| 스킬팩 전체 안내·키 발급 | itda-gov:realty-meta |

## 파일 구조

```
realty-price-stats/
  SKILL.md · GUIDE.md · CHANGELOG.md
  scripts/
    price_stats.py       # R-ONE 호출 계획·응답 파서·전량 대조, 파생 통계
    price_stats_cli.py   # rone-plan / rone / plan / derive CLI
  tests/
    test_rone.py         # rone (fixtures/rone — 2026-09-30 itda-hyve 실측, 키 없는 sample)
    test_price_stats.py  # derive
  references/
    netbridge.md         # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    rone-openapi.md      # R-ONE 요청 계약·통계표 ID·메시지 코드 (판독 근거)
```

## 테스트 실행

```bash
# macOS/Linux
python3 -m pytest itda-gov/skills/realty-price-stats/tests/ -v

# Windows
py -3 -m pytest itda-gov/skills/realty-price-stats/tests/ -v
```
