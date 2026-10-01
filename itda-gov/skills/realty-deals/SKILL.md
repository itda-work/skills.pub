---
name: realty-deals
description: >
  국토교통부 부동산 실거래 12개 유형을 단일 인터페이스로 수집하는 스킬입니다.
  "최근 6개월 강남구 아파트 실거래 전부 받아줘", "분당 연립다세대 매매 2025년 데이터 CSV로 줘", "강서구 오피스텔 전월세 조회해줘"처럼 말하면 됩니다.
  전체 페이지네이션·다개월 범위·CSV/JSON 출력을 지원합니다.
  [책임 경계] 본 스킬은 국토교통부 실거래 raw 수집 전담 — 가격지수·평균/중위 파생 통계는 itda-gov:realty-price-stats, 미분양·인허가·청약은 itda-gov:realty-supply.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — batch plan_file·http_request)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "지역명 + 기간 + 유형 (예: 강남구 2026년 1~6월 아파트 매매)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.13.1"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-10-01"
  tags: "realestate, molit, trade, rent, csv, json"
---

# realty-deals

국토교통부 공공데이터포털의 실거래가 API 12개 유형을 단일 인터페이스로 수집합니다.

- **절단 버그 교정**: `page=1` 단일 요청이 아니라 `totalCount` 전량까지 페이지를 돈다
- **12유형**: 아파트·오피스텔·연립다세대·단독다가구·토지·상업업무용·공장창고·분양입주권 × 매매/전월세
- **다월 수집**: 달마다 따로 조회해 합친다

## 흐름 — 요청은 itda-hyve, 계획과 가공은 스크립트

네트워크는 **itda-hyve**(`mcp__remote-devices__itda-hyve__batch`·`mcp__remote-devices__itda-hyve__http_request`)로만 나간다.
스크립트는 네트워크를 하지 않는다 — **호출 계획을 파일로 쓰고**(`plan`·`--next-plan`), itda-hyve 가 `save_as` 로 저장한 응답 XML 을
`--input` 으로 읽어 전량 대조·정규화·요약만 한다. 쪽 번호·`DEAL_YMD`·저장 이름은 스크립트가 정한다 — **호출 JSON 을 손으로 옮겨 적지 않는다.**
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
regions(코드 확정) → plan --write(호출 수 알림) → batch(plan_file)
  → collect --next-plan → incomplete 면 batch(plan_files) → collect 다시 → 결과
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`KO_DATA_API_KEY`** 로 등록해 둔 것을 **이름으로만** 가리킨다(계획 파일에 `{{secret:KO_DATA_API_KEY}}` 가 들어 있다).
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 공공데이터포털은 **Decoding 키**를 등록해야 한다
(`params` 가 한 번 인코딩하므로 Encoding 키는 이중 인코딩돼 `resultCode 30` 이 난다).

## 1단계 — 지역코드 확정 (네트워크 불요)

사용자가 5자리 법정동코드를 주지 않았으면 스크립트로 찾는다. 목록에 없으면 사용자에게 묻는다 — **코드를 짐작하지 않는다.**

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
printf "%s\n" "$c"' _ realty-deals itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"

python3 "$SKILL_DIR/scripts/deals_cli.py" regions
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'realty-deals'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
py -3 "$env:SKILL_DIR\scripts\deals_cli.py" regions
```

출력의 `name` → `lawd_cd` 를 쓴다. 별도 패키지 설치는 필요 없다(표준 라이브러리만 사용).

> **저장소 체크아웃에서 직접 실행 시(개발자)**: 공용 모듈(`deals_collector`·`data_go_client`·`lawd_codes`·`hyve_input`)이
> `itda-gov/shared/`·`shared/` 에 있어 `PYTHONPATH=itda-gov/shared:shared` 를 붙여야 한다. 배포본은 publish 주입으로 불필요.

## 2단계 — 호출 계획 (스크립트가 쓴다)

회차 폴더는 `realty/<코드>-<시작월>-<종료월>` 이다(`save_dir` 기준). 계획 파일은 **그 폴더 안**에 쓴다 — batch 의 `plan_file` 은
`save_dir` 기준 상대 경로로 풀린다. Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 보인다.

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
D="$HOME/mnt/작업폴더/realty/11680-202601-202603"
python3 "$SKILL_DIR/scripts/deals_cli.py" plan \
  --region "강남구" --type apt_trade --start-month 202601 --end-month 202603 --write "$D/plan-1.json"
```

```powershell
$D = "$HOME\mnt\작업폴더\realty\11680-202601-202603"
py -3 "$env:SKILL_DIR\scripts\deals_cli.py" plan --region "강남구" --type apt_trade --start-month 202601 --end-month 202603 --write "$D\plan-1.json"
```

출력: `run_dir` · `call_count` · `plan_files`(batch 에 넘길 경로 — 40개를 넘으면 `plan-1a.json`·`plan-1b.json` 처럼 여럿) · `calls_preview`.
`--write` 없이 부르면 `calls` 전체를 싣는다(도구 하나씩 부를 때).

- **1차는 달마다 1쪽**(달 수만큼)이다. `body/totalCount` 가 그 달의 전체 건수이고 쪽 수는 `ceil(totalCount / 100)` 이라 1쪽을 받아 봐야 안다.
  **1페이지만 받고 끝내지 않는다**(이 스킬이 교정한 절단 버그 그대로다) — 3단계 `collect` 가 모자란 쪽을 계획으로 알려 준다.
- **호출 전에 사용자에게 예상 호출 수를 알린다.** 강남구 아파트 매매 한 달이 1~2쪽, 전월세는 10쪽을 넘는다. 6개월 이상·여러 유형이면
  범위를 확인받는다. 연달아 부르다 `resultCode 22`(일일 트래픽 초과)가 나면 멈춘다(재시도는 itda-hyve 가 한다).
- 같은 지역·기간을 다시 받으면 같은 이름이 있어 `invalid_input` 이다 — `--tag 2` 로 새 회차 폴더(`…-202603-2`)를 쓴다.

`plan_files` 의 파일마다 `batch` 를 한 번씩 부른다(여럿이면 차례로). 계획 파일을 **옮겨 적지 않고** 경로만 넘긴다.

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "realty/11680-202601-202603/plan-1.json"}
```

- **`save_dir` 에는 Cowork 연결 폴더의 호스트 경로**(절대 경로, 사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외, 클라우드 드라이브는 허용)를 넣는다.
- 계획 파일에는 `calls`·`timeout_sec: 50`(Cowork 는 도구 호출 하나를 60초에 끊는다)이 들어 있다. batch 는 GET 만, 한 번에 최대 40호출이다.
- 결과의 `failed` 가 0 이 아니면 그 호출의 `error.code`·`message` 를 사용자에게 전하고 **멈춘다**(실패한 호출은 파일을 쓰지 않는다).
- **응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `ok`·`failed`·`saved_path` 뿐이다.**
  itda-hyve 0.10.4 전 판은 `save_as` 로 받은 응답의 `final_url` 에서 키를 가리지 않았다(itda-work/itda-hyve#31) — 판과 관계없이 옮겨 적지 않는다.
- 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면(옛 판) `plan` 을 `--write` 없이 불러 `calls` 를 받고,
  호출마다 그 `args` 에 `save_dir`·`"timeout_sec": 50` 을 더해 `http_request` 를 하나씩 부른다. 호출 한 칸은 이렇다:

```json
{"url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "LAWD_CD": "11680", "DEAL_YMD": "202601",
            "pageNo": "1", "numOfRows": "100"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "realty/11680-202601-202603/apt_trade-11680-202601-p1.xml"}
```

- `serviceKey` 는 반드시 `params` 에 둔다. URL 쿼리에 자리표시자를 쓰면 `invalid_input` 으로 거부된다. `params` 값은 전부 **문자열**이다.
- URL 은 유형별로 `https://apis.data.go.kr/1613000/<서비스>/get<서비스>` 다(계획이 채운다).

| 키 | `<서비스>` | 키 | `<서비스>` |
|---|---|---|---|
| `apt_trade` | `RTMSDataSvcAptTrade` | `apt_rent` | `RTMSDataSvcAptRent` |
| `offi_trade` | `RTMSDataSvcOffiTrade` | `offi_rent` | `RTMSDataSvcOffiRent` |
| `rh_trade` | `RTMSDataSvcRHTrade` | `rh_rent` | `RTMSDataSvcRHRent` |
| `sh_trade` | `RTMSDataSvcSHTrade` | `sh_rent` | `RTMSDataSvcSHRent` |
| `land_trade` | `RTMSDataSvcLandTrade` | `biz_trade` | `RTMSDataSvcNrgTrade` |
| `factory_trade` | `RTMSDataSvcFctTrade` | `presale_trade` | `RTMSDataSvcSilvTrade` |

**저장 이름이 식별 계약이다** — `<유형>-<코드>-<YYYYMM>-p<쪽>.xml`. 스크립트는 이름을 본문과 대조한다(`-p<쪽>` ↔ `pageNo`,
`<YYYYMM>` ↔ 거래월, `<코드>` ↔ `sggCd`, `<유형>` ↔ `--type`). 어긋나면 `error: args` 다. 이름을 바꾸지 않는다.

### 응답 판정 — HTTP 200 은 성공이 아니다

- 루트가 `<response>` 이고 `header/resultCode` 가 `000`(또는 `00`·`0000`)일 때만 성공이다.
- 그 밖의 `resultCode` 는 실패다: `03` 데이터 없음(다른 달·지역) · `20` 활용 미승인(해당 유형의 활용신청, 승인 후 동기화 5~30분) ·
  `22` 일일 트래픽 초과 · `30` 등록되지 않은 키(**GUI 에 Decoding 키로 등록했는지** 먼저 확인) · `31` 키 기간 만료.
- 루트가 `<OpenAPI_ServiceResponse>` 이거나 `<header>` 가 없으면 **게이트웨이 오류**다. 0건으로 접지 않는다.
- `save_as` 로 저장했으면 본문 대신 `saved_path` 만 온다 — 판정은 3단계 스크립트가 파일을 읽어 대신 한다(오류 응답이면 `error: api` + `code`).

## 3단계 — 가공과 2차

회차 폴더의 파일을 **글로브로 전부** 넘긴다(순서 무관). 따옴표로 감싼 패턴은 스크립트가 펼친다 — PowerShell 도 같다.

```bash
python3 "$SKILL_DIR/scripts/deals_cli.py" collect \
  --region "강남구" --type apt_trade --start-month 202601 --end-month 202603 \
  --input "$D/apt_trade-*.xml" --next-plan "$D/plan-2.json" --summary
```

```powershell
py -3 "$env:SKILL_DIR\scripts\deals_cli.py" collect --region "강남구" --type apt_trade --start-month 202601 --end-month 202603 `
  --input "$D\apt_trade-*.xml" --next-plan "$D\plan-2.json" --summary
```

- **전량이 아니면** `status: "incomplete"`(exit 1)이고 결과를 내지 않는다. `missing_pages` 에 더 받을 쪽, `next_call_count` 에 호출 수,
  `plan_files` 에 다음 계획이 있다. 호출 수를 사용자에게 알리고(40을 넘으면 확인받는다) 2단계처럼 받은 뒤 **같은 명령**을 다시 돌린다
  (`--next-plan` 은 `plan-3.json` 처럼 새 이름). `incomplete` 가 없어질 때까지 반복한다. **쪽 수를 짐작하지 않는다.**
- **`refetch`·`need_overwrite: true`** — 그 달은 받는 사이 목록이 바뀌었다(쪽마다 `totalCount` 가 다름·쪽 경계에서 행이 겹침·건수 초과).
  그 달을 1쪽부터 같은 이름으로 덮어써 다시 받아야 하므로, 사용자에게 알리고 확인받은 뒤 `--overwrite` 를 붙여 다시 돌린다.
  1차와 2차는 **이어서** 부른다 — 실거래는 매일 늘어난다.
- 파일이 회차 폴더 밖에 있으면 `--next-plan` 은 `error: args` 다. 계획은 `plan` 이 만든 폴더의 파일로만 이어 받는다.

인자: `--input`(필수, 파일·글로브) · `--start-month`·`--end-month`(필수, `YYYYMM` — 기간 밖 달의 파일은 거부, 파일이 없는 달은 `incomplete`) ·
`--region` 또는 `--lawd-cd`(응답 `sggCd` 와 대조) · `--type`(기본 `apt_trade` — 저장 이름·단지명 필드와 대조) · `--name`(단지명 부분 일치) ·
`--summary`(해제 거래 제외) · `--include-cancelled` · `--next-plan FILE` · `--overwrite`(사용자 확인 뒤에만) · `--format json|table`(서브커맨드 앞).

## 지원 엔드포인트 유형

| 키 | 유형 | 거래 | 키 | 유형 | 거래 |
|---|---|---|---|---|---|
| `apt_trade` | 아파트 | 매매 | `apt_rent` | 아파트 | 전월세 |
| `offi_trade` | 오피스텔 | 매매 | `offi_rent` | 오피스텔 | 전월세 |
| `rh_trade` | 연립다세대 | 매매 | `rh_rent` | 연립다세대 | 전월세 |
| `sh_trade` | 단독다가구 | 매매 | `sh_rent` | 단독다가구 | 전월세 |
| `land_trade` | 토지 | 매매 | `biz_trade` | 상업업무용 | 매매 |
| `factory_trade` | 공장창고 | 매매 | `presale_trade` | 분양입주권 | 매매 |

## 출력 형식

```json
{
  "status": "ok",
  "region": "강남구",
  "lawd_cd": "11680",
  "type": "apt_trade",
  "start_month": "202601",
  "end_month": "202601",
  "count": 95,
  "results": [
    {"apt_nm": "래미안퍼스티지", "deal_amount": 155000, "deal_year": "2026", "deal_month": "01",
     "deal_day": "05", "exclu_use_ar": "84.98", "floor": "12", "build_year": "2009",
     "umd_nm": "도곡동", "jibun": "467-1", "cdeal_type": "", "cdeal_day": ""}
  ],
  "sources": [{"path": "…/apt_trade-11680-202601-p1.xml", "month": "202601", "total_count": 95, "page": 1,
               "num_of_rows": 100, "item_count": 95, "sgg_cd": "11680"}],
  "months": [{"month": "202601", "total_count": 95, "collected": 95}],
  "excluded": {"cancelled": 4},
  "warnings": [],
  "summary": {"avg": 120000, "median": 115000, "max": 200000, "min": 80000, "count": 91}
}
```

전월세 유형은 `deal_amount`·`cdeal_*` 대신 `deposit`·`monthly_rent` 가 들어간다.

- **해제 거래** — 매매 응답의 `cdealType` 이 있으면(실측 `O`) 계약이 해제된 거래다. `results` 에는 `cdeal_type`·`cdeal_day` 를 실은 채 **그대로 남기고**
  (원본 행 수집이다), `summary` 에서는 기본으로 빼고 뺀 수를 `excluded.cancelled` 에 싣는다. 사용자가 원하면 `--include-cancelled`.
- **`status` 판정** — 달마다 받은 건수가 `totalCount` 에 못 미치거나, 기간 중 파일이 없는 달이 있거나, 받는 사이 목록이 바뀐 달이 있으면
  `status: "incomplete"` + exit 1 이고 결과를 내지 않는다. **수집 성공으로 말하지 않는다.**

```json
{"status": "incomplete", "error": "incomplete", "missing_pages": {"202601": [2]}, "next_call_count": 1,
 "plan_files": ["realty/11680-202601-202603/plan-2.json"],
 "warnings": ["202601: totalCount=170 인데 수집=100 — 페이지를 더 받아야 합니다"]}
```

## 에러 코드

| 상황 | status | error | 조치 |
|---|---|---|---|
| 입력 파일 없음·알 수 없는 지역명·`--type` 불일치·이름↔본문 불일치·같은 쪽 중복·지역 섞임·기간 밖 달·`YYYYMM` 형식 | error | args | `detail` 대로 인자·파일을 고친다(`regions` 로 지역명 조회) |
| 저장된 XML 이 오류 응답(resultCode 20/30 등·게이트웨이·절단) | error | api | `code` 로 유형별 활용신청 승인 상태, Decoding 키 등록 확인 |
| 모델이 batch 실패 자리를 파일로 적었다 | error | hyve | `code`(`secret_missing` 등)를 아래 행대로 안내하고 멈춘다 |
| 쪽·달 누락, 받는 사이 목록 변경 | incomplete | incomplete | `plan_files` 를 받는다. `need_overwrite` 면 확인 뒤 `--overwrite` |
| `secret_missing` (itda-hyve) | — | — | GUI 시크릿 탭에 `KO_DATA_API_KEY` 등록 안내 후 멈춤 |
| `secret_host_denied` (itda-hyve) | — | — | URL 호스트가 `apis.data.go.kr` 인지 먼저 확인 |

## 테스트 실행

```bash
python3 -m pytest itda-gov/skills/realty-deals/tests/ -v     # Windows: py -3 -m pytest …
```

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 가격지수·전월세전환율·평균/중위 통계 | itda-gov:realty-price-stats |
| 미분양·인허가·착공·청약 통계 | itda-gov:realty-supply |
| 전세가율·갭 스크리닝 | itda-gov:realty-jeonse-gap |
| 법원 경매 물건 | itda-gov:court-auction |

## 마이그레이션 안내

구 itda-gov 팩 `realestate` 에서 이전하는 사용자:

- 키 이름은 `KO_DATA_API_KEY` 그대로다 — 다만 이제 **itda-hyve GUI 시크릿 탭**에 등록한다(`.env`·환경변수 경로는 쓰지 않는다).
- 기존 4유형(apt_trade, apt_rent, offi_trade, offi_rent) 동일하게 동작
- 새 스킬명: `realty-deals` (in plugin `itda-gov`)
