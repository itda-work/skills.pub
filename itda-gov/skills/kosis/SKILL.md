---
name: kosis
description: >
  통계청 KOSIS 국가통계포털 API로 공식 통계를 검색·탐색·조회하는 스킬입니다.
  "인구 통계 알려줘", "KOSIS 통계표 검색해줘", "이 통계표 분류·항목 코드 찾아줘",
  "국제통계 목록 탐색해줘", "산업 시장규모 조회해줘"처럼 말하면 됩니다.
  통계표 목록·구조(objL·itmId 코드)·데이터·통계설명·주요지표를 다룹니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[search|data|info|list|meta|indicator|region] 키워드·기관 ID·통계표 ID·기간"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.14.1"
  created_at: "2026-03-29"
  updated_at: "2026-10-01"
  tags: "KOSIS, statistics, population, market"
---

# kosis

통계청 KOSIS(국가통계포털) API로 국가 공식 통계를 수집합니다.
사업계획서, 시장 분석, 정책 보고서에 필요한 인구·산업·경제 통계를 제공합니다.

- **7개 명령**: 통합검색(search) · 통계자료(data) · 통계표 구조(info) · 통계목록 트리(list) · 통계설명(meta) · 주요지표(indicator) · 지역명→분류 코드(region)
- **분류축 자동 해석**: 첫 축이 `objL1` 이 아닌 통계표도 `--obj1` 로 부른다 — 스크립트가 다음에 받을 호출을 알려 준다

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`) 하나로만 나간다.
스크립트는 네트워크를 하지 않는다 — 부를 호출을 만들고(`plan`), itda-hyve 가 `save_as` 로 저장한 응답을 `--input` 으로 읽어
오류 판정·분류축 해석·정리만 한다. 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan <명령> → calls[0].args 로 http_request → <명령> --input <저장 파일> → (data 가 next_calls 를 주면 받고 다시)
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`KOSIS_API_KEY`** 로 등록해 둔 것을 **이름으로만** 가리킨다(`params.apiKey` 의
`{{secret:KOSIS_API_KEY}}`). 값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다.
발급: <https://kosis.kr/openapi/> 회원가입 → Open API → 활용신청(자동 승인) → 마이페이지에서 인증키 확인.
Base64 키라 끝 `=` 까지 전부 복사해 등록해야 한다.

## 준비 — 스킬 디렉토리

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
printf "%s\n" "$c"' _ kosis itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'kosis'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

## 1단계 — 호출 계획 (네트워크 불요)

명령마다 `plan <명령>` 이 부를 호출을 낸다. 출력 `calls[i].args` 가 `http_request` 인자 그대로다 — URL·파라미터·저장 이름을 손으로 짓지 않는다.

```bash
python3 "$SKILL_DIR/scripts/collect_stats.py" plan search --keyword "인구"
python3 "$SKILL_DIR/scripts/collect_stats.py" plan data --org-id 101 --tbl-id DT_1B04005N --recent 3
python3 "$SKILL_DIR/scripts/collect_stats.py" plan info --org-id 101 --tbl-id DT_1DA7104S          # --type PRD 등
python3 "$SKILL_DIR/scripts/collect_stats.py" plan list --vw-cd MT_RTITLE                          # --parent-id A_7
python3 "$SKILL_DIR/scripts/collect_stats.py" plan meta --org-id 101 --tbl-id DT_1DA7104S          # 또는 --stat-id
python3 "$SKILL_DIR/scripts/collect_stats.py" plan indicator --jipyo-id 5000
python3 "$SKILL_DIR/scripts/collect_stats.py" plan region --org-id 101 --tbl-id DT_1YL20631
# Windows: py -3 "$env:SKILL_DIR\scripts\collect_stats.py" plan search --keyword "인구"
```

| 명령 | URL (`https://kosis.kr/openapi/…`) | 저장 이름(`save_as`) |
|---|---|---|
| `search` | `statisticsSearch.do` (method=getList) | `kosis/search-<지문>.json` |
| `data` | `Param/statisticsParameterData.do` (method=getList) | `kosis/data-<기관>-<통계표>-<지문>-{json1\|json2\|sdmx}.{json\|xml}` |
| `info` · `region` | `statisticsData.do` (method=getMeta) | `kosis/info-<기관>-<통계표>-<유형>.json` |
| `list` | `statisticsList.do` | `kosis/list-<서비스뷰>-<시작목록 또는 root>.json` |
| `meta` | `statisticsExplData.do` | `kosis/meta-<통계조사 ID 또는 기관-통계표>-<항목>.json` |
| `indicator` | `pkNumberService.do` | `kosis/indicator-<지표>-p<쪽>-n<건수>.json` |

`<지문>` 은 질의 인자 전부(키워드·항목·분류값·주기·기간)의 8자 지문이다 — 조건이 다르면 이름이 달라 겹치지 않는다. 저장 이름에 한글은 넣지 않는다.

## 2단계 — itda-hyve 의 http_request 로 받기

`calls[0].args` 에 **`save_dir`(Cowork 연결 폴더의 호스트 경로)** 만 더해 그대로 보낸다. 예 — `plan search --keyword "인구"` 의 출력:

```json
{"url": "https://kosis.kr/openapi/statisticsSearch.do",
 "params": {"apiKey": "{{secret:KOSIS_API_KEY}}", "method": "getList", "searchNm": "인구", "sort": "RANK",
            "startCount": "1", "resultCount": "10", "format": "json"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "kosis/search-f3b91bb6.json"}
```

예 — `plan data --org-id 101 --tbl-id DT_1B04005N --recent 3` 의 출력:

```json
{"url": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
 "params": {"apiKey": "{{secret:KOSIS_API_KEY}}", "method": "getList", "orgId": "101", "tblId": "DT_1B04005N",
            "itmId": "ALL", "prdSe": "Y", "format": "json", "jsonVD": "Y", "objL1": "ALL", "newEstPrdCnt": "3"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "kosis/data-101-DT_1B04005N-c9bb5677-json1.json"}
```

- `apiKey` 는 반드시 `params` 에 둔다. URL 쿼리(`?…`)에 자리표시자를 쓰면 `invalid_input` 으로 거부된다. `params` 값은 전부 문자열이다.
- 한글 키워드는 `params` 에 그대로 쓴다 — itda-hyve 가 한 번 인코딩한다.
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다** — 3단계가 이름으로 명령·단계·질의를 가른다.
- `save_dir` 는 절대 경로(사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외). 생략하면 itda-hyve 기본 저장 폴더.
- 같은 이름이 이미 있으면 덮어쓰지 않고 `invalid_input` 으로 거부된다. 같은 조회를 다시 받으면 `save_dir` 를 새 하위 폴더로 바꾸거나,
  사용자가 확인했을 때만 `overwrite: true`.

### 응답 판정 — HTTP 200 은 성공이 아니다

- KOSIS 는 오류도 HTTP 200 으로 준다. 본문이 `{"err":"NN","errMsg":…}`(옛 서버는 키에 따옴표 없는 `{err:"NN",…}`, SDMX 는 `<error><err>NN</err>…`)면 오류다.
  판정은 3단계 스크립트가 파일을 읽어 대신 한다(`error: "api"` + `error_code`).
- 호출 URL 이 틀리면 KOSIS 는 HTTP 404 **HTML 안내 페이지**를 준다 — `save_as` 가 그 본문을 저장하므로 3단계가 `error: "input"`("KOSIS JSON 응답이 아닙니다")으로 알린다.
- 응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

## 3단계 — 저장한 응답을 가공

Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 — `save_dir` 의 **폴더 이름** 뒤에 `saved_path` 를 붙인다.
Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다.

```bash
D="$HOME/mnt/작업폴더"
python3 "$SKILL_DIR/scripts/collect_stats.py" search --input "$D/kosis/search-f3b91bb6.json" --keyword "인구"
python3 "$SKILL_DIR/scripts/collect_stats.py" --format table info --input "$D/kosis/info-101-DT_1DA7104S-ITM.json"
python3 "$SKILL_DIR/scripts/collect_stats.py" list --input "$D/kosis/list-MT_RTITLE-root.json"
python3 "$SKILL_DIR/scripts/collect_stats.py" meta --input "$D/kosis/meta-101-DT_1DA7104S-ALL.json"
python3 "$SKILL_DIR/scripts/collect_stats.py" indicator --input "$D/kosis/indicator-5000-p1-n10.json"
python3 "$SKILL_DIR/scripts/collect_stats.py" region --input "$D/kosis/info-101-DT_1YL20631-ITM.json" --region "인천 서구"
# Windows: py -3 "$env:SKILL_DIR\scripts\collect_stats.py" search --input "…\kosis\search-f3b91bb6.json"
```

명령과 파일이 맞아야 한다 — 다른 명령의 응답을 넘기면 `error: "input"` 이다(`region` 은 `info-…-ITM.json` 만 받는다).

### data — 받은 파일 전부로 다시 부르는 루프

`data` 는 **plan 과 같은 인자**에 지금까지 받은 파일을 **전부** 붙여 부른다. 분류축이 표준과 다른 통계표면 스크립트가
`status: "error"`, `error: "incomplete"` 와 함께 **`next_calls`**(더 받을 호출, 2단계와 같은 형식)와 `stage` 를 준다.

```bash
K="$D/kosis"
python3 "$SKILL_DIR/scripts/collect_stats.py" plan data --org-id 358 --tbl-id DT_358004_008 --item T001 --obj1 A02 --recent 3        # → save_as kosis/data-358-DT_358004_008-501fa5d9-json1.json
python3 "$SKILL_DIR/scripts/collect_stats.py" data --org-id 358 --tbl-id DT_358004_008 --item T001 --obj1 A02 --recent 3 --input "$K/data-358-DT_358004_008-501fa5d9-json1.json"
#   → incomplete, stage=meta: next_calls 2개(getMeta ITM·TBL)를 받아서
python3 "$SKILL_DIR/scripts/collect_stats.py" data --org-id 358 --tbl-id DT_358004_008 --item T001 --obj1 A02 --recent 3 --input "$K/data-358-DT_358004_008-501fa5d9-json1.json" \
  "$K/info-358-DT_358004_008-ITM.json" "$K/info-358-DT_358004_008-TBL.json"
#   → incomplete, stage=sdmx: next_calls 1개를 받아 "$K/data-358-DT_358004_008-501fa5d9-sdmx.xml" 을 더해 같은 명령 → status ok
```

파일 이름은 plan·`next_calls` 의 `save_as` 를 그대로 옮겨 쓴다(셸 글로브로 찾지 않는다 — 같은 폴더에 다른 질의 파일이 있으면 섞인다).

**이미 받은 메타는 다시 받지 않는다** — 탐색 단계에서 `plan info`(필터 없이)로 `info-<기관>-<통계표>-ITM.json`·`-TBL.json` 을 이미 받았다면
`stage=meta` 의 `next_calls` 가 **같은 이름**을 낸다. 그대로 부르면 itda-hyve 가 같은 이름이라며 `invalid_input` 을 준다 — 받지 말고
그 파일을 `--input` 에 함께 넘긴다(같은 요청이다). 처음부터 `data` 의 1차 파일과 함께 넘겨도 된다.

| 단계 | 언제 | next_calls |
|---|---|---|
| `json1` | 1차 파일이 없을 때 | 1차 호출(plan 과 같음) |
| `meta` | 1차가 오류 20/21(분류축 슬롯 불일치)일 때 | getMeta `ITM`·`TBL` 2개 |
| `json2` | 실제 첫 축이 `objL1` 인 표 | 슬롯을 다시 맞춘 JSON 호출 |
| `sdmx` | 첫 축이 `objL1` 이 아닌 표(KOSIS JSON 이 빈 배열을 준다 — #1684) | SDMX(Generic) 호출(`.xml`) |

- 정상 표는 1차에서 끝난다(추가 호출 0). 최대 4번 받는다(1차 + 메타 2 + 재호출 1) — 여러 통계표를 한 번에 조회하면 **예상 호출 수를 먼저 알린다**.
- `incomplete` 인 채로 결과를 말하지 않는다. 다른 질의(인자를 바꾼)의 파일이 섞이면 `error: "input"` 이다 — 이름의 지문이 다르다.
- 결과의 `source`(`json`|`sdmx`)·`axis_slots`(실제 objL 번호)·`notes`(전환 사유)가 어느 경로로 받았는지 알려 준다.

### 전량 대조 — 기준선이 없는 API

KOSIS 통계자료·목록 응답에는 총건수가 없다(쪽 나눔도 없다) — 한 번에 4만 셀을 넘으면 잘라 주는 대신 **오류 31** 로 거부한다.
그래서 받은 행 수를 대조할 기준선이 없다. 오류 31 이면 기간·항목·분류를 나눠 여러 번 받는다. 값이 숫자가 아닌 행(`-`·`…`)을 뺀 수는
`skipped_non_numeric` 으로 싣는다.

### itda-hyve 실패 코드

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `KOSIS_API_KEY` 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `kosis.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `invalid_input` | URL 쿼리에 자리표시자를 넣었거나 같은 이름 파일이 있다 — `params`·새 하위 폴더로 고친다 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | `timeout_sec` 을 늘리지 말고(Cowork 는 60초에 끊는다) 기간·항목을 좁혀 1회만 다시 보낸다 |

## 분류축 슬롯(objL)은 통계표마다 다르다 — `--obj1` 은 "1번째 축"이라는 뜻

`--obj1`~`--obj4` 는 **그 통계표의 1~4번째 분류축**을 가리킨다. 실제 KOSIS 파라미터 번호(`objL1`·`objL2`…)는 `info --type ITM` 응답의
`OBJ_ID_SN` 이 정하며, **1 부터 시작하지 않는 통계표가 있다**. 예: 한국보건산업진흥원(`--org-id 358`)의 `DT_358004_008` 은 첫 축이
`objL2` 라 `objL1` 로 부르면 KOSIS 가 오류 21 로 거부한다. 위 data 루프가 이것을 처리한다.

## 워크플로우 (탐색이 필요할 때)

**코드를 이미 아는 반복 조회**는 `data` 로 바로 간다. **무엇을 조회할지부터 찾아야 하면** 아래 순서:

1. `search`(통합검색) 또는 `list`(트리 탐색) 로 통계표 후보 → `org-id`·`tbl-id` 확보
2. `info --type ITM` 으로 그 통계표의 **분류(objL)·항목(itmId) 코드 발견**
3. `data` 로 발견한 코드를 넣어 조회 (3~4중 분류는 `--obj3`/`--obj4`)
4. 필요 시 `meta`(작성목적·법적근거)·`indicator`(지표 개념) 로 맥락 보강

## CLI 옵션

모든 가공 명령: `--input`(저장한 응답 파일, 필수) · `--format json|table`(명령 앞·뒤 어디든, 기본 `json`).

| 명령 | 인자 (plan·가공 공통) |
|---|---|
| `search` | `--keyword`(plan 필수) · `--count`(기본 10) |
| `data` | `--org-id` `--tbl-id`(필수) · `--item`(기본 ALL) · `--obj1`~`--obj4` · `--period year\|half\|quarter\|month\|day`(기본 year) · `--start` `--end` 또는 `--recent N` |
| `info` | `--org-id` `--tbl-id`(plan 필수) · `--type ITM\|TBL\|ORG\|PRD\|CMMT\|UNIT\|SOURCE\|WGT\|NCD`(기본 ITM) · `--obj-id` `--item` |
| `list` | `--vw-cd`(plan 기본 MT_ZTITLE, 국제 MT_RTITLE, 지역 MT_ATITLE01 등) · `--parent-id`. 가공 때는 생략하면 저장 이름에서 읽고, 주면 이름과 대조한다 |
| `meta` | `--stat-id` 또는 `--org-id`+`--tbl-id` · `--meta-item`(기본 ALL) |
| `indicator` | `--jipyo-id`(plan 필수) · `--page` · `--count` |
| `region` | `--org-id` `--tbl-id`(plan 필수) · 가공은 `--region`(필수, 예: 인천 서구) |

`data` JSON 출력: `status`·`count`·`raw_count`·`skipped_non_numeric`·`source`·`axis_slots`·`notes`·`data`(`period`·`item_name`·`category`·`value`·`unit`·`table_name`…, 2중 분류면 `category2`).

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 가공 실패 — `error`: `incomplete`(data 다음 단계 필요 — `next_calls`) · `api`(본문 err 코드) · `truncated`·`http`·`hyve`(입력이 잘림·HTTP 오류·itda-hyve 실패 자리) · `input`(파일 없음·이름 규칙 위반·KOSIS 응답 아님·다른 질의 파일) |
| 2 | 인자 오류 |

## 오류 처리

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `secret_missing` (itda-hyve) | `KOSIS_API_KEY` 미등록 | itda-hyve GUI 시크릿 탭에 등록 |
| `KOSIS API 오류 (10/11/42)` | 인증키 누락·만료·이용 제한 | 시크릿 탭의 키 확인(끝 `=` 까지), 마이페이지에서 활용 상태·기간 확인. 발급 직후면 수 분 뒤 |
| `KOSIS API 오류 (21)` | 분류값 코드 불일치 | 메시지에 실제 분류축(`objL2=…`)이 함께 나온다 — `info --type ITM` 으로 코드 확인 후 `--obj1`~`--obj4` 재지정 |
| `KOSIS API 오류 (30)` | 조회결과 없음 | 기간·항목 조정 |
| `KOSIS API 오류 (31)` | 4만 셀 초과 | 기간·항목·분류를 나눠 받는다 |
| `KOSIS API 오류 (40/41/50)` | 호출 제한·서버 오류 | 멈추고 잠시 뒤 다시 받는다(연달아 부르지 않는다) |
| `error: input` "KOSIS JSON 응답이 아닙니다" | HTML 오류 페이지(틀린 URL 등) | plan 이 준 URL 을 그대로 썼는지 확인 |

정본 err 코드 표(10·11·20·21·30·31·40·41·42·50)는 [references/kosis-매뉴얼/01-인증키-에러메시지.md](references/kosis-매뉴얼/01-인증키-에러메시지.md).

## Troubleshooting — 한글 경로

Cowork sandbox 등 일부 환경의 bash 는 `LANG`/`LC_ALL` 미설정 시 한글 디렉토리명을 직접 인자로 받지 못한다
(`/sessions/.../mnt/실습-클로드-1기/` 에서 `No such file or directory`). 경로를 변수로 잡아 넘긴다:

```bash
WORKSPACE=$(/bin/ls /sessions/*/mnt/ | grep -v '^lost+found$' | head -1)
D=$(/bin/ls -d /sessions/*/mnt/"$WORKSPACE" 2>/dev/null | head -1)
python3 "$SKILL_DIR/scripts/collect_stats.py" search --input "$D/kosis/search-f3b91bb6.json"
```

## 트리거 키워드

통계, 인구, 시장규모, KOSIS, 국가통계, 산업통계, 경제통계,
통계청, 표본 조사, 통계표, 인구주택총조사,
statistics, population, market size, national statistics

## 파일 구조

```
kosis/
  SKILL.md
  GUIDE.md
  CHANGELOG.md
  scripts/
    kosis_api.py        # 호출 계획·응답 판독·분류축 해석·SDMX 파서 (네트워크 없음)
    collect_stats.py    # plan / search·data·info·list·meta·indicator·region 가공 CLI
  tests/
    test_kosis_input.py      # 호출 계획·hyve 층·오류 판독·단발 명령
    test_kosis_data_flow.py  # data 적응형 루프(json1→meta→json2|sdmx)
    fixtures/                # 2026-09-30 itda-hyve 실측 오류 응답(키 없음) + 기존 실측 형태
  references/
    netbridge.md        # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    kosis.md            # 요청 URL·파라미터 요약
    kosis-매뉴얼/        # 공식 매뉴얼 v1.0 정본 PDF + 11개 분류 발췌
```

## 상세 API 가이드

`references/kosis-매뉴얼/` 에 통계청 공식 KOSIS OpenAPI 매뉴얼 v1.0(158페이지) 정본 PDF와 11개 분류 발췌 md를 보관한다.
통계자료 URL `Param/statisticsParameterData.do` 는 매뉴얼 §2.2 통계표선택 방식의 진입점이다(매뉴얼 예시는 `statisticsData.do`).
2026-09-30 itda-hyve 실측으로 이 URL 이 KOSIS 오류 JSON 을 돌려주는 실재 엔드포인트임을 확인했다(오타 `statisticsParamData.do` 는 HTTP 404).

| 분류 | md 파일 |
|------|--------|
| 개요 + 제공 콘텐츠 7종 | [00-개요-제공콘텐츠.md](references/kosis-매뉴얼/00-개요-제공콘텐츠.md) |
| 인증키 + 에러메시지 | [01-인증키-에러메시지.md](references/kosis-매뉴얼/01-인증키-에러메시지.md) |
| 통계목록 (statisticsList.do) | [02-통계목록.md](references/kosis-매뉴얼/02-통계목록.md) |
| 통계자료 (statisticsData.do / Param/) | [03-통계자료.md](references/kosis-매뉴얼/03-통계자료.md) |
| 통계자료 SDMX(DSD) | [04-통계자료-SDMX-DSD.md](references/kosis-매뉴얼/04-통계자료-SDMX-DSD.md) |
| 통계자료 SDMX(Generic/StructureSpecific) | [05-통계자료-SDMX-Generic-StructureSpecific.md](references/kosis-매뉴얼/05-통계자료-SDMX-Generic-StructureSpecific.md) |
| 대용량 통계자료 (statisticsBigData.do) | [06-대용량통계자료.md](references/kosis-매뉴얼/06-대용량통계자료.md) |
| 통계설명 (statisticsExplData.do) | [07-통계설명.md](references/kosis-매뉴얼/07-통계설명.md) |
| 메타자료 (statisticsData.do?method=getMeta) | [08-메타자료.md](references/kosis-매뉴얼/08-메타자료.md) |
| 통합검색 (statisticsSearch.do) | [09-통합검색.md](references/kosis-매뉴얼/09-통합검색.md) |
| 통계주요지표 (지표 Open API) | [10-통계주요지표.md](references/kosis-매뉴얼/10-통계주요지표.md) |
| 참고: SDMX 표준 | [11-참고-SDMX.md](references/kosis-매뉴얼/11-참고-SDMX.md) |

요약본: [references/kosis.md](references/kosis.md) · 정본 PDF: [references/kosis-매뉴얼/openApi_manual_v1.0.pdf](references/kosis-매뉴얼/openApi_manual_v1.0.pdf)
