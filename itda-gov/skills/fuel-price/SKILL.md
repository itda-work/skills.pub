---
name: fuel-price
description: >
  오피넷(한국석유공사) 주유소 평균 유가 조회 스킬입니다. 전국·시도(16개) × 일간/주간/월간 평균가와 전기 대비 등락,
  과거 특정 시점(--end) 조회를 제공합니다. "오늘 기름값 얼마야", "서울 휘발유 가격", "이달 전국 경유 월평균",
  "지난 7월 인천 휘발유 평균", "최근 두 달 휘발유 추세"처럼 말하면 됩니다. API 키 없이 동작하며, 요청은 itda-hyve 가 보냅니다.
  [책임 경계] 본 스킬은 평균 유가 조회 전담 — 주유소 위치·최저가 검색, 유류비 정산 단가·공지문 생성은 하지 않고,
  환율은 itda-work:exchange-rate 가 맡습니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request)이 한다."
user-invocable: true
argument-hint: "[지역] [제품] [--term day|week|month] [--end YYYY-MM(-DD)] [--format json|table]"
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.5.0"
  created_at: "2026-09-02"
  updated_at: "2026-09-30"
  tags: "fuel-price, opinet, gasoline, diesel, oil-price, korea, keyless"
---

# Fuel Price (오피넷 평균 유가 조회)

오피넷 **평균 판매가격**(부가세 포함, 원/리터)을 조회합니다 — 전국·시도 × 일간/주간/월간, 전기 대비 등락, 과거 시점.
**조회 전용**입니다: 유류비 정산 단가 계산·공지문 생성은 범위 밖이며(간단한 산식이라 회사 규정대로 소비자가 적용),
주유소 단위 검색도 하지 않습니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 스크립트는 네트워크를
하지 않는다 — 다음에 부를 호출을 만들고(`plan`), itda-hyve 가 `save_as` 로 저장한 파일을 `--input` 으로 읽어 판독만 한다(`parse`).
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
웹 경로(기본, 키 불요 — 호출 2회, 같은 날 같은 종류 화면을 이미 받았으면 1회):
  plan → http_request GET(save_as) → plan --input view-….html → http_request POST(save_as) → parse --input avg-….html
API 경로(선택, --source api — 호출 1회):
  plan --source api → http_request GET(save_as) → parse --input api-….json
```

**`plan` 이 준 `call` 을 그대로 `http_request` 인자로 보낸다.** URL·헤더·폼 본문·`save_as` 를 고쳐 쓰거나 새로 짓지 않는다 —
폼 본문은 오피넷 화면이 브라우저에서 보내는 FormData 와 키 집합·순서가 같고(조회에 쓰이지 않는 분기·일 셀렉트만 유효한
옵션 값으로 채운다 — 서버가 그 필드를 쓰지 않음을 실측으로 확인), `save_as` 이름은 `parse` 가 응답과 대조하는 식별 계약이다.
`User-Agent`·`Cookie` 헤더를 더하지 않는다(쿠키 없이 성립 — 2026-09-30 실측).

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
printf "%s\n" "$c"' _ fuel-price itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'fuel-price'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

표준 라이브러리만 쓰므로 추가 설치가 없다(Python 3.10+).

## Step 2: 요청 해석

`$ARGUMENTS` 와 사용자 발화에서 아래를 뽑는다. 없으면 기본값. **세 단계(plan·plan --input·parse) 모두에 같은 인자를 준다.**

| 축 | 인자 | 기본값 | 예 |
|---|---|---|---|
| 지역 | `--region` | `전국` | 아래 **지원 지역 16개**(시도 단위). 시군구·개별 주유소는 비지원 |
| 제품 | `--product` | `휘발유` | 휘발유·고급휘발유·경유(디젤)·등유 (LPG 비지원 — 평균판매가격 화면 4제품) |
| 기간 단위 | `--term` | `month` | `day`(일간) · `week`(주간) · `month`(월간) |
| 기간 수 | `--periods` | `3` | 전기 대비 계산용 — 추세를 보려면 6~12 |
| 종료 시점 | `--end` | 최신 | 특정 시점 조회 — 일간 `YYYY-MM-DD`, 주간·월간 `YYYY-MM` (예: "7월 평균" → `--term month --end 2026-07`). 오피넷 최신 시점 이후는 거부 |
| 출력 | `--format` | `json` | `parse` 만 — `json`(기본, compact — 필드+`summary`·`detail_table` 문자열 동봉) / `table`(사람용 텍스트) |

- "오늘·어제·현재 기름값"이면 `--term day`(오피넷은 전일까지 확정 통계 — "오늘" 값은 새벽에 갱신된 **전일자**가 최신이다. 출력의 기간 라벨이 기준일이니 그대로 보여준다).
- "월평균·이달 평균"이면 `--term month`, "추세"면 `--term week --periods 8`.
- 지난 특정 날/달을 물으면 `--end`. 두 시점 비교("6월 대비 8월")는 `--end 2026-08 --periods 3`.
- **유류비 단가·공지문을 요구받으면**: 조회 결과(기준가)를 주고, 단가는 회사 규정 산식(예: 기준가 ÷ 연비 × 보정계수)으로
  에이전트가 대화에서 계산해 준다 — 스킬 스크립트의 몫이 아니다. 연비 등 규정값은 사용자에게 묻고 지어내지 않는다.
- 제품·지역을 여러 개 물으면(“휘발유랑 경유 둘 다”) 조합마다 아래 흐름을 한 번씩 돈다. 화면(①)은 전국·시도 두 종이고
  같은 날에는 다시 받지 않으므로 호출 수는 **조합 수 + 화면 종류 수(1~2)** 다 — 먼저 알린다(예: 서울·인천 비교 = 3회).

**지원 지역(`--region`, 시도 16개 — 오피넷 지역별 화면 코드 순)**: 서울 · 부산 · 대구 · 인천 · 전남광주 · 대전 · 울산 · 경기 · 강원 · 충북 · 충남 · 전북 · 경북 · 경남 · 제주 · 세종.
"광주"·"전남"·"광주광역시"·"전라남도"는 모두 **전남광주**(2026-07-01 통합 — 오피넷이 통합특별시 통계로 제공)로 해석된다. "경기도"·"인천광역시" 같은 정식 명칭·약칭 모두 허용. 목록 밖(시군구·"수도권" 등)은 오류로 거부하며 지원 목록을 함께 안내한다.

## Step 3: 웹 경로 (기본, 키 불요) — 호출 2회

`--save-dir` 에는 **Cowork 연결 폴더의 호스트 경로**(절대 경로, 사용자 홈 아래 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외)를 넣는다.
그러면 `plan` 이 낸 `call` 에 `save_dir` 가 들어 있어 그대로 보내면 된다. 생략하면 itda-hyve 기본 저장 폴더다.

**① 화면 받기** — `plan` 이 GET 호출을 낸다. 화면은 전국(`view-nat-<받은 날>.html`)·시도(`view-area-<받은 날>.html`) 두 종이고
질의(지역·제품·기간)와 무관하다. **오늘 같은 종류 화면을 이미 받았으면 이 GET 을 건너뛰고 그 파일로 ②** 를 한다(출력의 `reuse`).

```bash
python3 "$SKILL_DIR/scripts/fuel_price.py" plan --save-dir "/Users/me/Projects/작업폴더"
```

출력의 `call` 을 그대로 `http_request` 로 보낸다(위 명령 = 전국·휘발유·월간 3개월 기본값, 2026-09-30 에 낸 출력):

```json
{"url": "https://www.opinet.co.kr/user/dopospdrg/dopOsPdrgSelect.do",
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "fuel/view-nat-20260930.html"}
```

**② 조회하기** — 저장한 화면을 넘기면 `plan` 이 POST 호출을 낸다(화면의 숨김 필드 = 최신 가용 시점으로 기간을 정한다).
화면 이름의 받은 날이 오늘이 아니면 `stale` 로 멈춘다 — `plan` 부터 다시 돈다.

```bash
# Cowork: 연결 폴더는 샌드박스의 $HOME/mnt/<폴더 이름> — save_dir 의 폴더 이름 뒤에 saved_path 를 붙인다
python3 "$SKILL_DIR/scripts/fuel_price.py" plan --save-dir "/Users/me/Projects/작업폴더" \
    --input "$HOME/mnt/작업폴더/fuel/view-nat-20260930.html"
```

출력의 `call` 을 그대로 보낸다(위 명령의 2026-09-30 출력):

```json
{"url": "https://www.opinet.co.kr/user/dopospdrg/dopOsPdrgSelect.do",
 "method": "POST",
 "headers": {"Content-Type": "application/x-www-form-urlencoded",
             "Referer": "https://www.opinet.co.kr/user/dopospdrg/dopOsPdrgSelect.do"},
 "body": "all_chk_cnt=5&INIF_FLAG=N&chk_cnt=1&h_maxYY=2025&h_maxQQ=20262&h_maxMM=202608&h_maxDD=20260929&h_maxWW=2026095&sta_dt=&end_dt=&TERM=M&STA_Y=2026&STA_M=06&STA_Q=2&STA_W=1&STA_D=01&END_Y=2026&END_M=08&END_Q=3&END_W=1&END_D=01&OIL_CD_B027=Y&equal=Y",
 "retry_unsafe": true,
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "fuel/avg-nat-B027-M-202606-202608-20260930.html"}
```

시도는 URL 이 `…/dopOsPdrgAreaSelect.do`, Referer 가 `…/dopOsPdrgAreaView.do` 이다 — 어느 쪽이든 `plan` 이 정한다.
`retry_unsafe` 는 이 POST 가 조회 전용이라 다시 보내도 안전하기 때문이다.

**③ 판독** — 저장한 조회 결과를 넘긴다.

```bash
python3 "$SKILL_DIR/scripts/fuel_price.py" parse --input "$HOME/mnt/작업폴더/fuel/avg-nat-B027-M-202606-202608-20260930.html"
python3 "$SKILL_DIR/scripts/fuel_price.py" parse --region 인천 --product 경유 --term week --periods 4 --format table \
    --input "$HOME/mnt/작업폴더/fuel/avg-sido15-D047-W-2026081-2026095-20260930.html"

# Windows
py -3 "$env:SKILL_DIR\scripts\fuel_price.py" parse --input "…\fuel\avg-nat-B027-M-202606-202608-20260930.html"
```

Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다. 파일을 `find` 로 뒤지지 않는다.

`parse` 가 보는 것 — 어긋나면 실패로 끝낸다(부분 결과를 말하지 않는다):

- 저장 이름(`avg-<지역>-<제품>-<단위>-<시작>-<끝>-<받은 날>.html`)과 인자(`--region`·`--product`·`--term`)가 같은가
- **응답 화면이 되비친 조회 조건**(기간 단위·시작/종료 셀렉트·제품·지역 체크)이 저장 이름과 같은가 — 화면(view-…) 파일을
  넘겼거나 다른 질의의 응답이면 `mismatch`
- 이 인자(`--periods`·`--end`)와 **응답이 알려 준 오늘의 최신 시점**(서버가 매번 새로 싣는 `h_max*`)으로 다시 계산한 범위가 이름과
  같은가 — `--end` 없이 물었는데 묵은 화면으로 계획했으면 `stale`, 범위 끝은 같고 `--periods` 만 plan 때와 다르면 `input`
- 표의 기간 행이 **기대 목록의 이어진 한 구간**인가 — 월간·일간은 범위의 모든 기간, 주간은 "그 달 N번째 수요일이 든 주"
  규칙으로 만든 주(규칙과 표본은 [references/opinet-web-contract.md](references/opinet-web-contract.md)). 뒤쪽은 반드시 있어야 할
  기간까지 닿아야 하고(주간은 수요일이 최신 확정일 7일 전 이전인 주), 가운데가 비면 안 된다(`period`). 본문이 `</html>` 로
  닫혔는가(아니면 `truncated`)
- **앞쪽 결손은 실패가 아니다** — 오피넷은 자료 없는 기간의 행을 뺀다(전남광주는 2026-07-01 통합, 세종 주간은 2012년11월3주부터).
  요청한 구간 안에서 응답에 없는 기간의 수와 구간(`missing_range` — 하나면 그 기간, 둘 이상이면 `처음~끝`)을 `missing_count`·`missing_range` 에
  싣고 `summary` 끝에 "… 응답에 행 없음" 을, `warnings` 에 "요청한 N기간 중 M기간만" 을 코드가 붙인다. `--periods 1` 에서 빠진 앞 행은
  전기 대비용이라 결손으로 세지 않고 `warnings` 의 "전기 대비에 쓸 앞 기간 …" 으로만 알린다. 원인은 단정하지 않는다.
  사용자에게 그 문구와 `warnings` 를 빼지 말고 보여 준다
- **주간의 최신 한 주가 아직 없는 것도 실패가 아니다** — 수요일이 최신 확정일 7일 안인 주는 아직 안 올라왔을 수 있다.
  `warnings` 에 "최신 주(…)가 응답에 없습니다" 가 붙고, 그래서 요청한 주 수보다 한 주 적게 보일 수 있다(그 문구도 함께 보인다).
  목요일에는 이번 주 값이 아직 없는 것이 보통이다 — 사이트 안내가 "주간평균은 일~목 평균, 금요일에 발표" 다. 이 경고를 이상 징후처럼
  전하지 않는다. 최신 주 경고 없이 적게 보이면 "요청한 N주 중 M주만 보입니다" 한 줄이 따로 붙는다
- 최신 기간의 가격이 빈 칸이면 `empty` 다
- 최신 확정일이 받은 날 전전날 이전이면(새벽 갱신 전에 받았거나 사이트 갱신이 늦음) `plan`·`parse` 출력의 `warnings` 가 알린다 —
  사용자에게 전하고, 최신 값이 필요하면 새 하위 폴더로 `plan` 부터

## Step 3′: API 경로 (선택, `--source api`) — 호출 1회

최근 7일 일별만 된다(주간·월간·`--end`·`--periods` 8 이상은 거부). 키는 itda-hyve GUI 시크릿 탭에 **`OPINET_API_KEY`** 로 등록한 것을
`params` 의 `{{secret:OPINET_API_KEY}}` 자리표시자로만 가리킨다 — 값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다.
발급: https://www.opinet.co.kr/user/custapi/custApiInfo.do 하단 「일반 API 이용 신청」(회원가입 → 자동 승인, 무료 300회/일).

```bash
python3 "$SKILL_DIR/scripts/fuel_price.py" plan --source api --term day --region 서울 --save-dir "/Users/me/Projects/작업폴더"
```

```json
{"url": "https://www.opinet.co.kr/api/areaAvgRecentPrice.do",
 "params": {"out": "json", "code": "{{secret:OPINET_API_KEY}}", "area": "01", "prodcd": "B027"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "fuel/api-sido01-B027-20260930.json"}
```

```bash
python3 "$SKILL_DIR/scripts/fuel_price.py" parse --term day --region 서울 --input "$HOME/mnt/작업폴더/fuel/api-sido01-B027-20260930.json"
```

`parse` 는 행마다 명세 필드(`DATE`·`PRODCD`, 시도는 `AREA_CD`)가 있는지, 날짜가 하루씩 이어지는지, 최신 날짜가 받은 날 가까이인지 본다.

키는 URL 쿼리 문자열(`?code=…`)에 쓰지 않는다 — itda-hyve 가 `invalid_input` 으로 거부한다. 전국은 `plan` 이 `avgRecentPrice.do` 를 낸다.

## 응답 요약·재시도

- **응답 요약의 `final_url`·헤더(`Set-Cookie` 포함)를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.**
- **응답 `status` 가 200 이 아니면 그 파일을 스크립트에 넘기지 않는다** — itda-hyve 는 오류 상태의 본문(403·차단·점검 페이지)도
  저장하므로, 넘기면 "화면 구조가 바뀌었다"(`site`)로 잘못 읽힌다. 상태 코드를 사용자에게 알리고 멈춘다(403·차단은 사이트 상태 확인).
  itda-hyve 0.10.4 전 판은 `save_as` 로 받은 응답의 `final_url` 에서 키를 가리지 않았다(itda-work/itda-hyve#31).
- 같은 이름이 이미 있으면 덮어쓰지 않고 `invalid_input` 이다. 이름에 받은 날이 들어 있어 **같은 이름 = 오늘 같은 호출로 이미 받은 파일**이다:
  화면(①)이면 그 파일로 ② 를 하고, 조회 결과(②)면 그 파일로 `parse` 한다. 덮어써도 된다고 사용자가 확인했을 때만 `overwrite: true`.
- **나쁜 파일은 다시 쓰지 않는다** — 스크립트가 거부한 파일(`truncated`·`mismatch`·`period`·`site`·`stale`)과 응답 `status` 가 200 이
  아니었던 파일은 위 재사용 규칙에서 빠진다. 같은 이름으로 다시 받으면 그 파일로 되돌아오므로, **`--save-dir` 를 새 하위 폴더로
  바꿔 `plan` 부터** 다시 받는다. 새 폴더에서도 같은 오류면 멈추고 사용자에게 알린다.

| itda-hyve 실패 | 대응 |
|---|---|
| `secret_missing` (API 경로) | GUI 시크릿 탭에 `OPINET_API_KEY` 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다. 키 없이는 웹 경로(기본)를 쓴다 |
| `secret_host_denied` | URL 호스트가 `www.opinet.co.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `invalid_input` | 같은 이름 파일이 있다 — 오늘 이미 받은 것이니 그 파일을 쓴다(위). 또는 키를 URL 쿼리에 넣었다 — `plan` 출력 그대로 보낸다 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `plan` 출력 그대로(`save_as` 포함) 다시 받는다 |
| `timeout` | 1회만 다시 보낸다. itda-hyve 는 끊긴 뒤에도 돌아 파일을 나중에 쓸 수 있다 — **방금 보낸 호출이 시간 초과였을 때만**, 다시 보낸 것이 "같은 이름" 으로 거부되면 그 파일이 생긴 것이니 그대로 쓴다. 쓰기 전에 그 파일이 비지 않았는지 `parse` 가 판정한다 |

## Step 4: 표시

기본 출력은 **compact JSON**(itda-gov 팩 관례) — `status: "ok"` 와 필드(`series`·`latest_price`·`missing_count`·`missing_range`·`warnings`…), 표시용 완성 문자열
`summary`·`detail_table`·`source_note` 가 동봉된다. 사용자에게 보여줄 때는 **`summary`(+필요 시 `detail_table`)
문자열을 그대로** 쓰고 숫자를 다시 타이핑하지 않는다(전사 오류 방지). 후속 계산(단가·비교)은 JSON 필드로 한다.
`source_note`(출처)는 항상 함께 표시한다. 사람이 직접 읽을 원문이 필요하면 `--format table`(끝에 `warnings` 가 `※` 줄로 붙는다).
**`warnings` 가 비지 않았으면 전부 그대로 사용자에게 전한다** — 빼거나 줄이지 않는다.

## 오류 처리

실패하면 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 를 쓰고 exit 1(인자 오류는 2). `detail` 을 그대로 전달한다.

| `error` | 뜻 | 대응 |
|---|---|---|
| `args` | 알 수 없는 지역·제품, `--end` 가 오피넷 최신 시점 이후(`까지만 있습니다`), API 경로에 주간·월간·`--end` | 지원 지역 목록에서 고르거나 종료 시점을 앞당긴다. 주간·월간은 웹 경로 |
| `input` | 파일 없음·저장 이름이 계약과 다름·파일과 인자가 다름(`--periods`·`--end` 포함) | `plan` 이 준 `save_as` 그대로 저장했는지, 세 단계에 같은 인자를 줬는지 확인 |
| `stale` | 어제 받은 화면으로 계획했거나(② 에서), 응답의 최신 시점으로 다시 계산한 범위의 끝이 파일과 다름(`parse`), API 최신 날짜가 받은 날과 멀다 | 결과를 말하지 않는다. 새 하위 폴더로 `plan` 부터(나쁜 파일 규칙) |
| `mismatch` | 응답이 되비친 조회 조건이 요청과 다름(화면 파일을 넘김·다른 질의의 응답) | 넘긴 파일이 맞는지 먼저 본다. 맞으면 새 하위 폴더로 `plan` 부터(나쁜 파일 규칙) |
| `period` | 기간 행이 기대 목록의 이어진 구간이 아님 — 가운데·뒤쪽 결손, 범위 밖·중복 행(`missing`·`unexpected` 동봉). 앞쪽 결손은 여기가 아니라 `missing_count`·`missing_range`, 여유 안의 최신 주 부재는 `warnings` | 결과를 말하지 않는다. 새 하위 폴더로 `plan` 부터 한 번, 되풀이되면 알린다 |
| `empty` | 표는 있으나 기간 행이 없음, 또는 최신 기간 가격이 빈 칸 | 조회 기간에 통계 없음 — `--term`·`--periods` 조정 |
| `site` | 숨김 필드·조회 폼·가격 표(`tbl_type10`)를 못 찾음, 숨김 필드끼리 맞지 않음(`h_maxDD`·`h_maxWW`) — 화면 구조 변경 또는 점검·오류 페이지 | 응답 `status` 를 먼저 본다. 200 이었는데 되풀이되면 결함 신고 — 추측 수정 금지 |
| `api` | API 가 빈 배열(키 없음·오류 — 오피넷은 에러 대신 빈 배열을 준다)·다른 제품/지역 행 | 시크릿 탭의 `OPINET_API_KEY` 확인 또는 웹 경로 |
| `hyve` | itda-hyve 실패 자리 파일(`hyve_code` 동봉) | 위 실패 표대로 |
| `truncated`·`http` | 본문이 `</html>` 로 닫히지 않음, 또는 응답 JSON 전체를 옮겨 적은 파일에서 본문 잘림·HTTP 오류 | 새 하위 폴더로 `plan` 부터(나쁜 파일 규칙) |

## 데이터 경로와 지원 범위 (실측 2026-09-02 · itda-hyve 경유 2026-09-30)

**API 키가 없어도 아래 "웹 통계" 열 전부가 된다** — 현재(최신 일간) 시세, 시도 16곳, 과거 임의 시점(`--end`), 일/주/월 시계열.
키는 `--source api` 를 **명시**했을 때만 쓰이며, 제공 범위가 웹 경로보다 **좁다**(최근 7일 일별만).

| 축 | 웹 통계 (기본, 키 불요) | Open API (`--source api`, `OPINET_API_KEY`) |
|---|---|---|
| 현재(최신) 시세 | ✅ `--term day` 최신 확정일(전일) | ✅ 최근 7일 중 최신 |
| 지역 | ✅ 전국 + 시도 16 | ✅ 전국 + 시도(`areaAvgRecentPrice`) |
| 날짜별(일간) 시계열 | ✅ 최신에서 N일, 또는 `--end` 로 과거 임의 날짜 | ⚠️ 최근 7일만, 과거 지정 불가 |
| 주간 평균 | ✅ | ❌ (`avgLastWeek` 는 최근 1주만 — 미채택) |
| 월간 평균 | ✅ **정본** | ❌ 없음 |
| 과거 시점(`--end`) | ✅ 1997년~ (화면 지원 범위) | ❌ |
| 시군구·개별 주유소 | ❌ 비목표 | ❌ 비목표(API 는 있으나 스킬 범위 밖) |

| 경로 | 구현 | 비고 |
|---|---|---|
| **웹 통계** — `국내유가통계 > 주유소 > 평균판매가격` 화면의 폼 POST 를 브라우저 FormData 와 **키 집합·순서 동일**하게 재현 | `scripts/opinet_web.py` | NetFunnel 토큰·세션 쿠키 불요(GET 의 `Set-Cookie` 를 옮기지 않은 POST 가 표를 돌려줬다). 화면 숨김 필드(최신 가용 시점)를 GET 으로 읽어 되돌린다 |
| Open API — `avgRecentPrice` · `areaAvgRecentPrice` (`Opinet_API_Free.pdf` 계약) | `scripts/opinet_api.py` | 키 없음/오류 → 200 + 빈 배열(조용히 빔) → 명시 에러로 표면화 |

- 요청에 우리 식별자·부가 파라미터를 싣지 않는다(`outbound-identity-leak`·`request-profile-first`). payload 골든은
  `tests/test_payload_golden.py`.
- 저작권: 산출물에 항상 **출처 "오피넷(한국석유공사)"** 를 명시한다(오피넷 저작권 정책). 내부 이용은 무방,
  재배포·수익 목적은 공사와 사전 협의 대상.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 |
|---|---|
| 특정 주유소·최저가·반경 검색 | 오피넷 앱/사이트 직접 (본 스킬 비목표) |
| 유류비 정산 단가·공지문 생성 | 조회 결과 + 회사 규정 산식으로 대화에서 계산 (v0.1.x 의 단가·공지문 기능은 제거됨 — 마스터 결정 2026-09-02) |
| 환율·원자재 시황 | itda-work:exchange-rate · itda-gov:ecos |
| 국제유가(WTI·두바이) | 별도 — 본 스킬은 국내 주유소 판매가만 |

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 후속 요청 이어가기
"경유도 같이", "인천으로 다시" 같은 후속은 인자만 바꿔 다시 돈다 — 오늘 받은 같은 종류 화면은 그대로 쓰고(② 부터),
조회 결과 이름에는 지역·제품·기간이 들어가 앞 회차 파일과 겹치지 않는다.
