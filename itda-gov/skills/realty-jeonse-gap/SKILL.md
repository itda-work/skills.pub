---
name: realty-jeonse-gap
description: >
  매매와 전월세 실거래를 단지·전용면적 기준으로 조인해 전세가율과 갭 투자 후보를 스크리닝하는 스킬입니다.
  "강남구 아파트 전세가율 80% 넘는 단지 찾아줘", "분당 연립다세대 갭 3천만 이하 목록 뽑아줘", "전세가율 임계값 스크리닝 해줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 매매×전월세 조인·전세가율·갭 스크리닝 전담 — 실거래 원본 행 수집은 itda-gov:realty-deals, 평균·중위 통계는 itda-gov:realty-price-stats.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — batch plan_file·http_request)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "지역명 + 기간 + 필터 (예: 강남구 2026년 1~6월 전세가율 80% 이상)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.11.1"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-10-01"
  tags: "jeonse, gap, screener, realestate"
---

# realty-jeonse-gap

매매와 전월세 실거래가를 **단지·전용면적 기준으로 조인**하여 전세가율과 갭을 산출합니다.
커뮤니티 최상위 페인포인트(전세가율 시계열, 갭투자 스크리닝)를 해소하는 스킬입니다.

## 흐름 — 요청은 itda-hyve, 계획과 가공은 스크립트

네트워크는 **itda-hyve**(`mcp__remote-devices__itda-hyve__batch`·`mcp__remote-devices__itda-hyve__http_request`)로만 나간다.
스크립트는 네트워크를 하지 않는다 — **호출 계획을 파일로 쓰고**(`plan`·`--next-plan`), itda-hyve 가 `save_as` 로 저장한 응답 XML 을
`--trade-input`·`--rent-input` 으로 읽어 전량 대조·조인·전세가율 계산만 한다. 쪽 번호·`DEAL_YMD`·저장 이름은 스크립트가 정한다 —
**호출 JSON 을 손으로 옮겨 적지 않는다.** 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
regions(코드 확정) → plan --write(호출 수 알림) → batch(plan_file)
  → screen --next-plan → incomplete 면 batch(plan_files) → screen 다시 → 결과
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`KO_DATA_API_KEY`** 로 등록해 둔 것을 **이름으로만** 가리킨다(계획 파일에 `{{secret:KO_DATA_API_KEY}}` 가 들어 있다).
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 공공데이터포털은 **Decoding 키**를 등록해야 한다
(`params` 가 한 번 인코딩하므로 Encoding 키는 이중 인코딩돼 `resultCode 30` 이 난다).
매매·전월세는 **서비스마다 따로 활용신청**해야 한다(아파트 매매 https://www.data.go.kr/data/15126469/openapi.do ·
아파트 전월세 https://www.data.go.kr/data/15126474/openapi.do).

## 계산 방식

- **전세가율** = 전세보증금 / 매매가 × 100 (%) · **갭** = 매매가 − 전세보증금 (만원)
- **전세보증금은 전세 계약만** 쓴다 — 전월세 응답 중 `monthlyRent` 가 0 인 계약. 월세·반전세의 보증금은 전세가가 아니다
  (실측 강남구 2026-08: 전월세 1,121건 중 월세 560건. 월세 보증금을 섞으면 전세가율 1.5%·2.5% 같은 값이 나왔다).
- 같은 단지·전용면적에 전세가 여러 건이면 **보증금 중위값**을 쓴다. 한 기간에 신규 계약과 갱신 계약(5% 상한)이 섞여,
  최댓값은 한 건의 높은 계약에 끌려 전세가율을 부풀리고 최솟값은 갱신에 끌린다. 결과 행에 `jeonse_count`(전세 건수)·
  `deposit_min`·`deposit_max` 를 함께 싣는다 — 건수가 1이면 그 한 건이다.
- **해제된 매매는 뺀다** — 매매 응답의 `cdealType` 이 있으면(실측 `O`) 계약이 해제된 거래다. 기본으로 조인에서 빼고 뺀 수를
  `excluded.cancelled_trade` 에 싣는다(실측 강남구 2026-08 매매 95건 중 4건). 사용자가 원하면 `--include-cancelled`.
- 단지명이나 전용면적이 빈 행은 조인하지 않는다(`warnings` 에 건수). 단독다가구(`sh`) 응답은 단지명·전용면적이 없을 수 있다 — 실측 전이다.

## 1단계 — 스킬 디렉토리·지역코드 확정 (네트워크 불요)

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
printf "%s\n" "$c"' _ realty-jeonse-gap itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'realty-jeonse-gap'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

출력의 `name` → `lawd_cd` 를 쓴다. 목록에 없으면 사용자에게 묻는다 — **코드를 짐작하지 않는다.** 별도 패키지 설치는 필요 없다(표준 라이브러리만 사용).

> **저장소 체크아웃에서 직접 실행 시(개발자)**: 공용 모듈(`deals_collector`·`data_go_client`·`lawd_codes`·`hyve_input`)이
> `itda-gov/shared/`·`shared/` 에 있어 `PYTHONPATH=itda-gov/shared:shared` 를 붙여야 한다. 배포본은 publish 주입으로 불필요.

## 2단계 — 호출 계획 (스크립트가 쓴다)

부동산 유형(`--prop-type`)마다 엔드포인트가 둘이다(매매·전월세). 기본은 아파트다.

| `--prop-type` | 매매 `<서비스>` | 전월세 `<서비스>` |
|---|---|---|
| `apt` (기본) | `RTMSDataSvcAptTrade` | `RTMSDataSvcAptRent` |
| `offi` | `RTMSDataSvcOffiTrade` | `RTMSDataSvcOffiRent` |
| `rh` | `RTMSDataSvcRHTrade` | `RTMSDataSvcRHRent` |
| `sh` | `RTMSDataSvcSHTrade` | `RTMSDataSvcSHRent` |

회차 폴더는 `jeonse-gap/<코드>-<시작월>-<종료월>` 이다(`save_dir` 기준). 계획 파일은 **그 폴더 안**에 쓴다 — batch 의 `plan_file` 은
`save_dir` 기준 상대 경로로 풀린다. Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 보인다.

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
D="$HOME/mnt/작업폴더/jeonse-gap/11680-202607-202608"
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" plan \
  --region "강남구" --start-month 202607 --end-month 202608 --write "$D/plan-1.json"
```

```powershell
$D = "$HOME\mnt\작업폴더\jeonse-gap\11680-202607-202608"
py -3 "$env:SKILL_DIR\scripts\jeonse_gap_cli.py" plan --region "강남구" --start-month 202607 --end-month 202608 --write "$D\plan-1.json"
```

출력: `run_dir` · `call_count` · `plan_files`(batch 에 넘길 경로 — 40개를 넘으면 `plan-1a.json`·`plan-1b.json` 처럼 여럿) · `calls_preview`(앞 3개).
`--write` 없이 부르면 `calls` 전체를 싣는다(도구 하나씩 부를 때).

- **1차는 달마다 매매·전월세 1쪽**(달 수 × 2 호출)이다. 쪽 수는 `ceil(totalCount / 100)` 이라 1쪽을 받아 봐야 안다.
  실측(2026-08 강남구 아파트): 매매 95건 = 1쪽, **전월세 1,121건 = 12쪽** → 한 달에 13회. 6개월이면 약 80회다.
- **호출 전에 사용자에게 예상 호출 수를 알린다.** 강남·서초처럼 거래가 많은 구의 전월세는 한 달에 10쪽을 넘는다.
  3개월을 넘으면 범위를 확인받는다. 연달아 부르다 `resultCode 22`(일일 트래픽 초과)가 나오면 멈춘다.
- 같은 지역·기간을 다시 받으면 같은 이름이 있어 `invalid_input` 이다 — `--tag 2` 로 새 회차 폴더(`…-202608-2`)를 쓰거나,
  사용자가 덮어써도 된다고 확인했을 때만 옛 폴더를 지운다.

## 3단계 — itda-hyve batch 로 받기

`plan_files` 의 파일마다 `batch` 를 한 번씩 부른다(여럿이면 차례로). 계획 파일을 **옮겨 적지 않고** 경로만 넘긴다.

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "jeonse-gap/11680-202607-202608/plan-1.json"}
```

- **`save_dir` 에는 Cowork 연결 폴더의 호스트 경로**(사용자 홈 아래 절대 경로 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외)를 넣는다.
- 계획 파일에는 `calls`·`timeout_sec: 50`(Cowork 는 도구 호출 하나를 60초에 끊는다)이 들어 있다. batch 는 GET 만, 한 번에 최대 40호출이다.
- 결과의 `failed` 가 0 이 아니면 그 호출의 `error.code`·`message` 를 사용자에게 전하고 **멈춘다**(실패한 호출은 파일을 쓰지 않는다 — 빠진 파일로 계산하지 않는다).
- **응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `ok`·`failed`·`saved_path` 뿐이다.**
  itda-hyve 0.10.4 전 판은 `save_as` 로 받은 응답의 `final_url` 에서 키를 가리지 않았다(itda-work/itda-hyve#31) — 판과 관계없이 옮겨 적지 않는다.
- 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면(옛 판) `plan` 을 `--write` 없이 불러 `calls` 를 받고,
  호출마다 그 `args` 에 `save_dir`·`"timeout_sec": 50` 을 더해 `http_request` 를 하나씩 부른다.

```json
{"url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "LAWD_CD": "11680", "DEAL_YMD": "202608", "pageNo": "1", "numOfRows": "100"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "jeonse-gap/11680-202607-202608/apt_rent-11680-202608-p1.xml"}
```

**저장 이름이 식별 계약이다** — `<유형>-<코드>-<YYYYMM>-p<쪽>.xml`. 스크립트는 이름을 본문과 대조한다(`-p<쪽>` ↔ `pageNo`,
`<YYYYMM>` ↔ 거래월, `<코드>` ↔ `sggCd`, `<유형>` ↔ `--prop-type`). 어긋나면 `error: args` 다. 이름을 바꾸지 않는다.

**응답 판정은 스크립트가 한다** — HTTP 200 은 성공이 아니다. 루트 `<response>` + `resultCode` `000`(또는 `00`·`0000`)만 성공이고,
`03` 데이터 없음 · `20` 활용 미승인(그 서비스의 활용신청, 승인 후 동기화 5~30분) · `22` 일일 트래픽 초과(멈춘다) ·
`30` 등록되지 않은 키(GUI 에 Decoding 키로 등록했는지) · `31` 키 기간 만료, 게이트웨이 오류(`<OpenAPI_ServiceResponse>`),
XML 이 아닌 본문(HTTP 오류 페이지), 닫히지 않은 XML(절단)은 `error: api` + `code`(`returnReasonCode`·`NOT_XML`·`TRUNCATED` 등)다. 0건으로 접지 않는다.

## 4단계 — 가공과 2차

회차 폴더의 파일을 **글로브로 전부** 넘긴다(순서 무관). 따옴표로 감싼 패턴은 스크립트가 펼친다 — PowerShell 도 같다.

```bash
python3 "$SKILL_DIR/scripts/jeonse_gap_cli.py" screen \
  --region "강남구" --start-month 202607 --end-month 202608 \
  --trade-input "$D/apt_trade-*.xml" --rent-input "$D/apt_rent-*.xml" \
  --next-plan "$D/plan-2.json" \
  --min-jeonse-ratio 80 --max-gap 30000
```

```powershell
py -3 "$env:SKILL_DIR\scripts\jeonse_gap_cli.py" screen --region "강남구" --start-month 202607 --end-month 202608 `
  --trade-input "$D\apt_trade-*.xml" --rent-input "$D\apt_rent-*.xml" --next-plan "$D\plan-2.json"
```

- **전량이 아니면** `status: "incomplete"`(exit 1)이고 결과를 내지 않는다. `missing_pages` 에 더 받을 쪽, `next_call_count` 에 호출 수,
  `plan_files` 에 다음 계획이 있다. 호출 수를 사용자에게 알리고(40을 넘으면 확인받는다) 3단계처럼 받은 뒤, **같은 명령**을 다시 돌린다
  (`--next-plan` 은 `plan-3.json` 처럼 새 이름). `incomplete` 가 없어질 때까지 반복한다. **쪽 수를 짐작하지 않는다.**
- **`refetch`·`need_overwrite: true`** — 그 달은 받는 사이 목록이 바뀌었다(쪽마다 `totalCount` 가 다름·쪽 경계에서 행이 겹침·건수 초과).
  실거래는 매일 늘어난다(실측: 같은 달 강남구 전월세 `totalCount` 가 몇 시간 사이 1,121 → 1,127). 그 달을 1쪽부터 **같은 이름으로 덮어써** 다시 받아야 하므로,
  사용자에게 알리고 확인받은 뒤 `--overwrite` 를 붙여 다시 돌린다. 그때 쓰인 계획 파일에는 `overwrite: true` 가 들어 있다.
- 1차와 2차는 **이어서** 부른다 — 시간이 벌어질수록 `refetch` 가 생긴다.
- 파일이 회차 폴더 밖에 있으면 `--next-plan` 은 `error: args` 다. 계획은 `plan` 이 만든 폴더의 파일로만 이어 받는다.

인자: `--trade-input`·`--rent-input`(필수, 파일·글로브) · `--start-month`·`--end-month`(필수, `YYYYMM` — 기간 밖 달의 파일은 거부, 파일이 없는 달은
`incomplete`) · `--region` 또는 `--lawd-cd`(응답 `sggCd` 와 대조) · `--prop-type apt|offi|rh|sh`(받은 엔드포인트와 같아야 한다) ·
`--min-jeonse-ratio PCT` · `--max-gap 만원` · `--include-cancelled` · `--next-plan FILE` · `--overwrite`(사용자 확인 뒤에만) ·
`--format json|table`(서브커맨드 앞).

## 출력 형식 (JSON)

```json
{
  "status": "ok",
  "region": "강남구",
  "count": 12,
  "results": [
    {"apt_nm": "래미안퍼스티지", "exclu_use_ar": "84.00", "deal_amount": 155000, "deposit": 120000,
     "jeonse_count": 3, "deposit_min": 110000, "deposit_max": 125000,
     "jeonse_ratio": 77.42, "gap": 35000, "deal_year": "2026", "deal_month": "8", "cdeal_type": ""}
  ],
  "filters": {"min_jeonse_ratio": 75.0},
  "lawd_cd": "11680",
  "start_month": "202607",
  "end_month": "202608",
  "prop_type": "apt",
  "months": {"trade": [{"month": "202608", "total_count": 95, "collected": 95}],
             "rent": [{"month": "202608", "total_count": 1121, "collected": 1121}]},
  "counts": {"trade": 95, "trade_used": 91, "rent": 1121, "rent_jeonse": 561, "joined": 48},
  "excluded": {"cancelled_trade": 4},
  "include_cancelled": false,
  "deposit_basis": "전세(월세 0) 보증금 중위값",
  "warnings": []
}
```

사용자에게는 `deposit_basis`(전세 중위값)·`excluded`(해제 매매 제외 수)를 함께 말한다.

## 에러 코드

| 상황 | status | error | 조치 |
|------|--------|-------|------|
| 입력 파일 없음·알 수 없는 지역명·매매/전월세 뒤바뀜·`--prop-type` 불일치·이름↔본문 불일치·같은 쪽 중복·지역 섞임·기간 밖 달·`YYYYMM` 형식 | error | args | `detail` 대로 인자·파일을 고친다. 이름↔본문 불일치는 계획을 다시 뽑아 그대로 받는다 |
| 저장된 파일이 오류 응답(resultCode·게이트웨이·HTTP 오류·절단) | error | api | `code` 를 3단계 판정으로 풀어 안내 |
| 모델이 batch 실패 자리를 파일로 적었다 | error | hyve | `code`(`secret_missing` 등)를 아래 표대로 안내하고 멈춘다 |
| 쪽·달 누락, 받는 사이 목록 변경 | incomplete | incomplete | `plan_files` 를 받는다. `need_overwrite` 면 확인 뒤 `--overwrite` |
| `secret_missing` (itda-hyve) | — | — | GUI 시크릿 탭에 `KO_DATA_API_KEY` 등록을 안내하고 멈춘다. 값을 대화로 받지 않는다 |
| `secret_host_denied` (itda-hyve) | — | — | URL 호스트가 `apis.data.go.kr` 인지 먼저 확인 |
| 본문 절단(`body_truncated: true`) | — | — | `save_as` 로 다시 받는다(`save_as` 로 받으면 잘리지 않는다) |

## 테스트 실행

```bash
python3 -m pytest itda-gov/skills/realty-jeonse-gap/tests/ -v     # Windows: py -3 -m pytest …
```

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 실거래 원본 행(CSV/JSON)·12유형 수집 | itda-gov:realty-deals |
| 가격지수·평균/중위 파생 통계 | itda-gov:realty-price-stats |
| 미분양·인허가·청약 | itda-gov:realty-supply |
