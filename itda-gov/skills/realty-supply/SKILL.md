---
name: realty-supply
description: >
  KOSIS 주택 공급 지표(미분양·인허가·착공·준공)와 청약홈 분양 공고를 수집하는 스킬입니다.
  "올해 강남구 아파트 미분양 추이 보여줘", "2024년 전국 인허가·착공·준공 통계 가져와줘", "이번 분기 청약 분양 공고 목록 보여줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 KOSIS 공급 지표·청약 분양 공고 전담 — 개별 실거래 원본은 itda-gov:realty-deals, 가격지수·파생 통계는 itda-gov:realty-price-stats.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch plan_file)이 한다. subscription 은 KO_DATA_API_KEY 허용 호스트에 api.odcloud.kr 가 있어야 한다(0.10.4 전에 등록한 키는 GUI 에서 추가)."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
argument-hint: "지표 종류 + 기간 (예: 미분양 2024년 전국 / 청약 분양 공고 2026년 1~6월)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.11.1"
  category: "domain"
  status: "active"
  created_at: "2026-05-15"
  updated_at: "2026-10-01"
  tags: "KOSIS, supply, subscription, housing"
---

# realty-supply

KOSIS(국가통계포털) **주택 공급 지표**(미분양·인허가·착공·준공)와 청약홈 **분양 공고**를 수집합니다.

| 명령 | 데이터 | 시크릿 |
|---|---|---|
| `kosis` | 국토교통부 KOSIS 표 — 월별·지역별 | `KOSIS_API_KEY` |
| `subscription` | 한국부동산원 청약홈 분양정보(모집공고일 기준) | `KO_DATA_API_KEY` |

| 지표(`--indicator`) | KOSIS 표 | 값 |
|---|---|---|
| `unsold` | 시·군·구별 미분양현황(`DT_MLTM_2082`) | 그 달 미분양 호수 — 시도·시군구 |
| `permitted` | 부문별 주택건설 인허가실적(`DT_MLTM_1946`) | **그 해 1월부터 그 달까지 누계**(월계 표가 없다) — 시도 |
| `started` | 주택건설 착공실적(`DT_MLTM_5386`) | 그 달 착공 호수 — 시도 |
| `completed` | 주택건설 준공실적(`DT_MLTM_5372`) | 그 달 준공 호수 — 시도 |

- **청약 경쟁률은 제공하지 않는다** — 청약홈 분양정보 서비스에 경쟁률 필드가 없다(별도 서비스). 경쟁률을 물으면 그렇게 말한다.
- 청약 데이터는 **2020년 2월(202002)부터** 있다. 그 이전 구간은 보간하지 않는다(R18).
- 요청 계약의 근거(URL·문서·판독일)는 [references/api-contract.md](references/api-contract.md) 에 있다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 여러 쪽은
**itda-hyve 의 `batch`**(`mcp__remote-devices__itda-hyve__batch`)로 한 번에 받을 수 있다.
스크립트는 네트워크를 하지 않는다 — 호출 계획을 만들고, itda-hyve 가 `save_as` 로 저장한 응답을 `--input` 으로 읽어
오류 판정·전량 대조·정리만 한다. 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan → itda-hyve 로 받기(save_as) → 가공(--input) → (청약이 모자라면 next_calls 받기 → 가공 다시) → 결과
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 등록해 둔 것을 **이름으로만** 가리킨다 — **`KOSIS_API_KEY`**(kosis),
**`KO_DATA_API_KEY`**(subscription, 공공데이터포털 **Decoding 키**). 값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다.

- KOSIS 발급: <https://kosis.kr/openapi/> 회원가입 → 활용신청(자동 승인).
- 청약홈: 공공데이터포털 <https://www.data.go.kr/data/15098547/openapi.do> 에서 **이 데이터셋을 따로 활용신청**한다(realty-deals 와 같은 키지만 신청은 데이터셋마다).
- subscription 은 `api.odcloud.kr` 로 나간다. itda-hyve 0.10.4 전에 `KO_DATA_API_KEY` 를 등록했다면 GUI 시크릿 탭에서 허용 호스트에
  **`api.odcloud.kr` 를 추가**한다(프리셋 변경은 새 등록에만 적용된다 — 안 하면 `secret_host_denied`).

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
printf "%s\n" "$c"' _ realty-supply itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'realty-supply'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

## KOSIS 공급 지표 (kosis)

### 1단계 — 호출 계획

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" kosis-plan --indicator unsold --start-month 202601 --end-month 202606
# Windows: py -3 "$env:SKILL_DIR\scripts\supply_cli.py" kosis-plan --indicator unsold --start-month 202601 --end-month 202606
```

출력 `calls[0].args` 가 `http_request` 인자 그대로다. 지표 여러 개면 지표마다 한 번씩 plan 한다(지표마다 호출 1개).

### 2단계 — itda-hyve 의 http_request 로 받기

`calls[0].args` 에 **`save_dir`(Cowork 연결 폴더의 호스트 경로)** 만 더해 그대로 보낸다.

```json
{"url": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
 "params": {"method": "getList", "apiKey": "{{secret:KOSIS_API_KEY}}", "orgId": "116", "tblId": "DT_MLTM_2082",
            "itmId": "ALL", "objL1": "ALL", "objL2": "ALL", "prdSe": "M",
            "startPrdDe": "202601", "endPrdDe": "202606", "format": "json", "jsonVD": "Y"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "supply/kosis-unsold-202601-202606.json"}
```

- `apiKey` 는 반드시 `params` 에 둔다. URL 쿼리에 자리표시자를 쓰면 `invalid_input` 으로 거부된다. `params` 값은 전부 문자열이다.
- 분류 수(`objL1`…)는 지표마다 다르다(인허가는 3개) — plan 이 준 `params` 를 고치지 않는다.
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다**(`supply/kosis-<지표>-<시작>-<끝>.json`). 3단계가 이 이름으로 지표와 기간을 안다.

### 3단계 — 가공

Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 — `save_dir` 의 **폴더 이름** 뒤에 `saved_path` 를 붙인다.

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" kosis --input "$HOME/mnt/작업폴더/supply/kosis-unsold-202601-202606.json"
# 지역만: 뒤에 --region "강남구"  (그 표의 지역 축 이름 부분일치 — 아래 표)
```

지역이 어느 축에 있는지는 표마다 다르다 — 스크립트가 표마다 선언한 축에서 `region` 을 뽑고, 나머지 분류는 `category` 에 싣는다.

| 지표 | 지역 축 | `region` 예 | `category` 예 |
|---|---|---|---|
| `unsold` | 분류 구분(시도)·시군구 | `서울 강남구` | (없음) |
| `permitted` | 분류 시도별 | `서울` | `총계 총계` |
| `started`·`completed` | **항목**(시도 단위 — 시군구 없음) | `서울` | `민간부문 민간분양` |

- 착공·준공·인허가에 시군구(`강남구`)를 주면 0행이고 `warnings` 가 그 표의 지역 단위를 말한다 — 시도 이름으로 다시 거르거나 사용자에게 그대로 전한다.
- 지역 축은 통계표 화면 배치로 정했다(키 있는 응답 미확인 — Cowork 실측 대기). 선언한 축이 응답에 없으면 `warnings` 에 "지역 축이 비어 있는 행" 이,
  응답의 분류 이름(`C<n>_OBJ_NM`)·항목 값이 선언과 어긋나면 "지역 축 선언이 응답과 다르다" 가 실린다 — 그때는 `region`·`--region` 결과를 믿지 말고 경고를 그대로 전한다.

출력 행: `indicator`·`period`(YYYYMM)·`region`·`region_code`·`category`·`category_code`·`item`(지역이 항목 축인 표는 빈 문자열)·`value`·`unit`.
출력 `table.region_axis` 가 그 표의 지역 축이다.
값이 `-`·`x` 같은 비수치면 `value: null` 이고 `warnings` 에 개수가 실린다(0 으로 바꾸지 않는다).

**전량 대조 기준선이 없다** — KOSIS 통계자료 응답에는 총건수가 없다(`completeness: "no_baseline"`). 결과가 너무 크면 KOSIS 가
오류 31(조회결과 초과)을 준다 — 그때는 기간을 나눠 받는다.

## 청약홈 분양 공고 (subscription)

### 1단계 — 호출 계획

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" subscription-plan --start-month 202601 --end-month 202606 \
  --write "$HOME/mnt/작업폴더/supply/plan-1.json"
# Windows: py -3 "$env:SKILL_DIR\scripts\supply_cli.py" subscription-plan --start-month 202601 --end-month 202606
```

- 출력 `calls` 는 **1쪽**을 받는 호출이다(모집공고일 `RCRIT_PBLANC_DE` 로 기간을 건다). 2쪽 이후는 3단계가 알려 준다.
- `--write` 는 같은 `calls` 를 itda-hyve `batch` 의 `plan_file` 로 쓴다. 계획 파일은 **그 회차 `save_dir` 안**에 쓴다
  (`plan_file` 은 `save_dir` 기준 상대 경로로 풀린다). 출력 `plan_files` 가 쓴 파일 목록이다.

### 2단계 — itda-hyve 로 받기

하나씩: `calls[i].args` 에 `save_dir` 만 더해 `http_request` 로 보낸다.

```json
{"url": "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "page": "1", "perPage": "500", "returnType": "JSON",
            "cond[RCRIT_PBLANC_DE::GTE]": "2026-01-01", "cond[RCRIT_PBLANC_DE::LTE]": "2026-06-30"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "supply/subscription-202601-202606-p1.json"}
```

한꺼번에: 계획 파일을 옮겨 적지 않고 경로만 넘긴다.

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "supply/plan-1.json"}
```

- batch 는 GET 만, 한 번에 최대 40호출이다. 계획이 40개를 넘으면 스크립트가 `plan-1a.json`·`plan-1b.json` 처럼 나눠 쓴다 — `plan_files` 를 차례로 부른다.
- 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면 옛 판이다 — `calls` 를 하나씩 `http_request` 로 부른다.
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다**(`supply/subscription-<시작>-<끝>-p<쪽>.json`). 3단계가 본문의 `page` 와 이름의 쪽을 대조한다.
- 같은 이름이 이미 있으면 `invalid_input` 이다. 다시 받을 때는 `save_dir` 를 새 하위 폴더로 바꾸거나, 사용자가 확인했을 때만 `overwrite: true`.

### 3단계 — 가공과 이어받기

```bash
python3 "$SKILL_DIR/scripts/supply_cli.py" subscription \
  --input "$HOME/mnt/작업폴더/supply/subscription-202601-202606-p1.json" \
  --next-plan "$HOME/mnt/작업폴더/supply/plan-next-1.json"
```

필요한 쪽 = ⌈`matchCount` ÷ `perPage`⌉ 이다. 모자라면 `status: "error"`, `error: "incomplete"` 와 함께
`need_pages`·`will_truncate`·`next_call_count` 를 준다. `--next-plan` 을 줬으면 더 받을 호출을 계획 파일(`plan_files`)로 쓰고
stdout 에는 앞 3개(`next_calls_preview`)만 싣는다. 안 줬으면 `next_calls` 전부를 싣는다.

1. **첫 쪽을 받은 뒤 남은 호출 수(`next_call_count`)를 먼저 알린다.** `will_truncate: true` 면(필요한 쪽이 `--max-pages` 상한
   20 을 넘는다) **받기 전에 사용자에게 묻는다** — 기간을 좁힐지, `--max-pages` 를 늘릴지.
2. `next_calls`(또는 `plan_files`)를 2단계처럼 받는다.
3. **지금까지의 파일 전부 + 새 파일**을 `--input` 으로 다시 가공한다. 회차마다 `--next-plan` 이름을 `plan-next-2.json` 처럼 바꾼다.
4. `status: "ok"` 가 나올 때까지 되풀이한다. **incomplete 인 채로 결과를 말하지 않는다.**

쪽은 다 있는데 행이 모자라거나 중간 쪽이 덜 찼으면(받는 사이 목록이 밀림) `next_calls` 없이 "1쪽부터 다시 받으라" 고 한다 —
그 기간을 새 하위 폴더에 다시 받는다. 쪽마다 `matchCount` 가 다르면(받는 사이 공고가 붙음) 경고하고 **큰 값**을 분모로 쓴다.
필요한 쪽을 넘는 파일(다른 회차의 쪽)이 섞이거나 합친 행이 분모를 넘으면 `error: input` 이다 — 이 회차 파일만 넘긴다.

- **쪽 매김의 한계** — 쪽은 오프셋이라, 받는 사이 앞쪽 공고 1건이 빠지고 뒤에 1건이 붙으면(`matchCount` 그대로) 쪽 경계의 1건이
  조용히 빠질 수 있다. 건수로는 가를 수 없다 — 공고가 막 바뀌는 시점이면 사용자에게 이 한계를 말한다.
- **0건 경고** — 2020-02 이후 기간인데 `matchCount` 가 0 이면 `warnings` 에 조회 조건 확인이 실린다. 공고는 한 달에도 보통 수십 건이다 —
  `RCRIT_PBLANC_DE` 값 형식(`YYYY-MM-DD`)이 명세에 없어 추정한 것이므로, 이 경고가 나오면 결과를 "공고 없음" 으로 말하지 말고 경고를 그대로 전한다.

출력 `results` 행: `house_manage_no`·`pblanc_no`·`house_nm`·`house_type`·`area`(공급지역)·`address`·`total_supply`(공급 세대수)·
`rcrit_pblanc_de`(모집공고일)·`rcept_bgnde`·`rcept_endde`·`przwner_presnatn_de`(당첨자 발표일)·`pblanc_url`.
그 밖에 `total_count`(matchCount)·`need_pages`·`truncated`·`pages`·`sources`·`meta.subscription_data_start`·`warnings`.

## 응답 판정 — HTTP 200 은 성공이 아니다

판정은 가공 명령이 파일을 읽어 대신 한다.

| 출처 | 오류 형태 | 결과 |
|---|---|---|
| KOSIS | `{"err":"10",…}`(키에 따옴표 없는 표기도) — HTTP 200 | `error: api` + `error_code` (`10` 키 없음·`11` 만료·`20`/`21` 요청변수·`30` 결과 없음·`31` 결과 초과 → 기간을 나눈다) |
| KOSIS | HTML 페이지(주소 오류 404 등) | `error: input`(또는 응답 요약이면 `http`) |
| 청약홈 | `{"code":-401,"msg":…}` — HTTP 401 | `error: api` + `error_code` (`-401` 키·활용신청 확인) |
| 공공데이터포털 게이트웨이 | `<returnReasonCode>12</returnReasonCode>` 등 | `error: api` + `error_code: gateway-<코드>` |

응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

### itda-hyve 실패 코드

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `KOSIS_API_KEY` 또는 `KO_DATA_API_KEY`(Decoding 키) 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `kosis.kr`(kosis) · `api.odcloud.kr`(subscription) 인지 먼저 확인. 맞으면 사용자가 GUI 에서 그 키의 허용 호스트에 추가해야 한다(subscription 은 `api.odcloud.kr` — itda-hyve 0.10.4 전에 등록한 키). 다른 주소로 우회하지 않는다 |
| `invalid_input`(같은 이름 파일) | `save_dir` 를 새 하위 폴더로 바꾸거나, 사용자 확인 뒤 `overwrite: true` |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | `timeout_sec` 을 늘려 1회만 다시 보낸다(50 이하 — Cowork 는 호출 하나를 60초에 끊는다) |

일시적 실패(429·5xx)는 itda-hyve 가 이미 재시도했다 — 직접 반복하지 않는다.

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 가공 실패 — `error`: `incomplete`(쪽 모자람) · `api`(본문 오류 코드) · `truncated`·`http`·`hyve`(입력이 잘림·HTTP 오류·itda-hyve 실패 자리) · `input`(파일 없음·이름 규칙 위반·쪽 중복·perPage 불일치·다른 표) |
| 2 | 인자 오류 (`argument` — 월 형식 YYYYMM, 시작 ≤ 끝) |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 실거래 개별 건 원본(매매·전월세) | itda-gov:realty-deals |
| 가격지수·전월세전환율·평균/중위 통계 | itda-gov:realty-price-stats |
| 전세가율·갭 스크리닝 | itda-gov:realty-jeonse-gap |
| 법원 경매 물건 | itda-gov:court-auction |

## 파일 구조

```
realty-supply/
  SKILL.md · GUIDE.md · CHANGELOG.md
  scripts/
    supply.py        # 호출 계획·응답 판독·청약 전량 대조
    supply_cli.py    # kosis-plan / kosis / subscription-plan / subscription
  tests/
    test_supply.py   # --input 가공·전량 대조·오류 (실측 오류 본문 + 명세 형태 합성)
    fixtures/
  references/
    netbridge.md     # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    api-contract.md  # 요청 계약 근거(URL·문서·판독일)
```

## 테스트 실행

```bash
# macOS/Linux
python3 -m pytest itda-gov/skills/realty-supply/tests/ -q

# Windows
py -3 -m pytest itda-gov/skills/realty-supply/tests/ -q
```
