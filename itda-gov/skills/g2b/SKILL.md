---
name: g2b
description: >
  조달청 나라장터 G2B API로 정부 입찰 공고를 검색·조회하는 스킬입니다.
  "나라장터 입찰공고 검색해줘", "조달청 공고 확인해줘", "소프트웨어 개발 입찰 공고 찾아줘"처럼 말하면 됩니다.
  키워드·기간 필터링과 상세 공고 조회를 지원합니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch plan_file)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[키워드] [기간 YYYY-MM-DD~YYYY-MM-DD] [상세]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.12.1"
  created_at: "2026-03-29"
  updated_at: "2026-10-01"
  tags: "G2B, procurement, tender, bid announcement, narajangteo"
---

# g2b

조달청 나라장터(G2B) 공공데이터개방표준서비스로 정부 입찰공고를 검색·조회합니다.
입찰 제안서 작성, 경쟁사 분석, 사업 기회 탐색에 필요한 공고 정보를 제공합니다.

- **1개월 창**: API 는 한 요청에 1개월 이내만 받는다 — 기간을 달력 달 단위 창으로 나눠 부른다
- **전량 수집**: 창마다 `totalCount` 까지 쪽을 끝까지 받는다(하루 약 1,900건 — 첫 쪽만 보면 거짓 0건)
- **키워드 필터**: 전 쪽을 받은 뒤 공고명으로 거른다

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 여러 쪽은
**itda-hyve 의 `batch`**(`mcp__remote-devices__itda-hyve__batch`)로 한 번에 받을 수 있다.
스크립트는 네트워크를 하지 않는다 — 호출 계획을 만들고, itda-hyve 가 `save_as` 로 저장한 응답을 `--input` 으로 읽어
창별 전량 대조·중복 제거·필터만 한다. 공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan(창 나누기) → 창마다 1쪽 받기 → collect → (모자라면 next_calls 받기 → collect 다시) → 결과
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`KO_DATA_API_KEY`** 로 등록해 둔 것을 **이름으로만** 가리킨다.
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 공공데이터포털은 **Decoding 키**를 등록해야 한다
(`params` 가 한 번 인코딩하므로 Encoding 키는 이중 인코딩돼 `30` 이 난다).
발급: <https://www.data.go.kr/data/15058815/openapi.do> 활용신청(자동승인, 게이트웨이 동기화 5~30분).

## 1단계 — 호출 계획 (네트워크 불요)

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
printf "%s\n" "$c"' _ g2b itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'g2b'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

- 기간을 말하지 않으면 `--from`·`--to` 를 빼면 된다(최근 7일). 날짜는 `YYYY-MM-DD`.
- 출력 `calls` 는 **창마다 1쪽**을 받는 호출이다 — `args` 가 `http_request` 인자 그대로다. 날짜 계산을 손으로 하지 않는다.
- `--write` 는 같은 호출을 itda-hyve `batch` 의 `plan_file` 로 쓰고, 출력에는 `plan_files`(쓴 파일 목록)·`call_count`·
  앞 3개만 담은 `calls_preview` 를 싣는다. 호출이 **40개를 넘으면 40개씩 나눠** `plan-1a.json`·`plan-1b.json` … 으로 쓴다
  (batch 는 40개를 넘으면 하나도 실행하지 않는다). `--write` 없이 받은 `calls` 를 하나씩 `http_request` 로 불러도 된다.
- 계획 파일은 **그 회차 `save_dir` 안**에 쓴다 — `plan_file` 의 상대 경로가 `save_dir` 기준으로 풀린다.
  Cowork 는 `$HOME/mnt/<폴더 이름>/…`, Claude Code CLI 처럼 같은 머신이면 `save_dir` 의 절대 경로 그대로(예: `/Users/me/Projects/작업폴더/g2b/plan-1.json`).

## 2단계 — itda-hyve 로 창마다 받기

### 하나씩: `http_request`

`calls[i].args` 에 **`save_dir`(Cowork 연결 폴더의 호스트 경로)** 만 더해 그대로 보낸다.

```json
{"url": "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo",
 "params": {"serviceKey": "{{secret:KO_DATA_API_KEY}}", "type": "json", "pageNo": "1", "numOfRows": "999",
            "bidNtceBgnDt": "202609010000", "bidNtceEndDt": "202609292359"},
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "g2b/bids-20260901-20260929-p1.json"}
```

- `serviceKey` 는 반드시 `params` 에 둔다. URL 쿼리에 자리표시자를 쓰면 `invalid_input` 으로 거부된다.
- `params` 값은 전부 **문자열**이다. `bidNtceBgnDt` 는 창 첫날 `0000`, `bidNtceEndDt` 는 창 끝날 `2359`.
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다**(`g2b/bids-<시작>-<끝>-p<쪽>.json`). 3단계가 이 이름으로 창과 쪽을 가른다.
- `save_dir` 는 절대 경로(사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외, 클라우드 드라이브는 허용). 생략하면 itda-hyve 기본 저장 폴더.
- 같은 이름이 이미 있으면 덮어쓰지 않고 `invalid_input` 으로 거부된다. 같은 기간을 다시 받으면 `save_dir` 를 새 하위 폴더
  (예: `/Users/me/Projects/작업폴더/g2b-2회차`)로 바꾸거나, 덮어써도 된다고 사용자가 확인했을 때만 `overwrite: true`.
  새 하위 폴더로 바꾸면 `plan --write`·`--next-plan` 경로도 **그 폴더 안으로** 바꾼다(옛 폴더의 계획 파일은 새 `save_dir` 기준으로 못 찾아 `not_found`).
  3단계에는 새 폴더의 파일만 넘긴다 — 옛 폴더 사본과 같은 쪽을 함께 넘기면 "같은 쪽이 두 번" 으로 실패한다.
- 한 쪽 응답은 약 2MB 다 — 반드시 `save_as` 로 받는다(본문으로 받으면 1MB 에서 잘린다).

### 한꺼번에: `batch` + `plan_file`

1단계 `--write` 로 쓴 계획 파일을 **옮겨 적지 않고** 경로만 넘긴다. `plan_file` 은 `save_dir` 기준 상대 경로(또는 호스트 절대 경로)다.

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "g2b/plan-1.json"}
```

- **`plan_files` 가 여러 개면 파일마다 batch 를 한 번씩** 부른다(`g2b/plan-1a.json` → `g2b/plan-1b.json` …). 한 파일은 40호출 이하다.
- batch 는 GET 만, 한 번에 최대 40호출·동시 8개다. 계획 파일의 `timeout_sec` 은 50 이다(Cowork 호출 하나 60초 상한 안).
- 응답은 호출별 요약이다 — `ok: false` 인 호출이 있으면 그 `error.code` 를 아래 실패 코드 표대로 처리한다.
  실패한 호출 자리에 파일이 없으니, 3단계에서 "쪽이 모자라다" 로 다시 나온다.
- 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면 옛 판이다 — `calls` 를 하나씩 `http_request` 로 부른다.

### 응답 판정 — HTTP 200 은 성공이 아니다

- 성공은 `response.header.resultCode` 가 `00` 일 때뿐이다. 판정은 3단계 스크립트가 파일을 읽어 대신 한다.
- 오류 본문은 두 형태다(실측): `nkoneps.com.response.ResponseError`(`resultCode 07` 입력범위 초과 — 기간 1개월 초과 등),
  `OpenAPI_ServiceResponse`(게이트웨이 — `20` 활용 미승인·키 없음, `22` 트래픽 초과, `30` **Decoding 키**로 다시 등록, `31` 키 만료).
  게이트웨이 오류는 HTTP 401 로 오지만 `save_as` 는 본문을 저장한다 — 3단계가 `error: api` 로 알린다.
- 응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

## 3단계 — 저장한 응답을 가공

Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 — `save_dir` 의 **폴더 이름** 뒤에 `saved_path` 를 붙인다.

```bash
python3 "$SKILL_DIR/scripts/collect_g2b.py" collect \
  --input "$HOME/mnt/작업폴더/g2b/bids-20260901-20260929-p1.json" \
  --keyword "소프트웨어" \
  --next-plan "$HOME/mnt/작업폴더/g2b/plan-next-1.json"
```

여러 창·여러 쪽은 파일을 **전부 나열**한다(순서 무관). Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다.

### 쪽 이어받기 — 모자라면 실패한다

창마다 필요한 쪽 = ⌈`totalCount` ÷ `numOfRows`⌉ 이다. 받은 쪽이 모자라면 collect 는 `status: "error"`, `error: "incomplete"` 로 끝나고
더 받을 호출 수 `next_call_count` 와 창별 `windows[].need_pages`·`will_truncate` 를 준다.
`--next-plan` 을 줬으면 호출을 계획 파일(`plan_files`, 40개씩 나뉨)로 쓰고 stdout 에는 앞 3개(`next_calls_preview`)만 싣는다.
`--next-plan` 이 없으면 `next_calls`(2단계와 같은 형식) 전부를 싣는다.

1. **`will_truncate: true` 면 받기 전에 사용자에게 묻는다** — 상한(`--max-pages`)까지 받아도 그 창의 뒤쪽 공고는 결과에 없다.
   기간을 좁히거나 `--max-pages` 를 `need_pages` 이상으로 올려 다시 collect 할지 정한다(다 받은 뒤에 알리지 않는다).
2. `plan_files` 를 파일마다 batch 로 받는다(`{"save_dir": …, "plan_file": "g2b/plan-next-1a.json"}` → `…-1b.json` …).
3. **지금까지의 파일 전부 + 새 파일**을 `--input` 으로 다시 collect 한다. 회차마다 `--next-plan` 이름을 `plan-next-2.json` 처럼 바꾼다.
4. `status: "ok"` 가 나올 때까지 되풀이한다. **incomplete 인 채로 결과를 말하지 않는다**(거짓 0건이 된다).

쪽은 다 있는데 행이 모자라면(받는 사이 공고가 밀림) `next_calls` 가 비어 있고 "이 창을 1쪽부터 다시 받으라" 고 한다 —
그 창만 새 하위 폴더에 다시 받는다.

### 호출 예산

한 쪽이 999건이고 평일 하루 약 1,900건이 올라온다(2026-09-28·29 실측) — 1주 ≈ 10쪽, **한 달 창 ≈ 33~40쪽**이다
(2026-08 한 달 창 `totalCount` 32,895 = 33쪽, 2026-09-30 실측). 31일 창은 `07` 없이 받아진다(같은 실측).
공고가 없는 창은 `resultCode 00` + `totalCount 0` 으로 온다(`03` 이 아니다 — 2026-10-10~11 실측) — 그 창은 1쪽으로 끝난다.
창마다 상한은 20쪽(`--max-pages`, 약 2만 건 ≈ 평일 열흘)이고, 넘으면 상한까지만 요구하고 결과에 `truncated: true` 와
경고가 붙는다(미조회분 공고는 결과에 없다). 한 달을 빠짐없이 보려면 `--max-pages 50` 으로 collect 한다.

- 첫 쪽들을 받은 뒤 `next_call_count` 로 **남은 호출 수를 먼저 알리고** 범위를 확인한다(1주를 넘으면 특히). 세 달을 `--max-pages 50` 으로 받으면 약 120호출이다.
- `will_truncate`·`truncated` 면 사용자에게 알리고, 기간을 좁히거나 `--max-pages` 를 늘려 쪽을 더 받을지 묻는다.
- `22`(트래픽 초과)·HTTP 429 가 나면 멈춘다. 재시도는 itda-hyve 가 이미 했다.

### itda-hyve 실패 코드

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `KO_DATA_API_KEY`(Decoding 키) 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `apis.data.go.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `invalid_input`(같은 이름 파일) | `save_dir` 를 새 하위 폴더로 바꾸거나, 사용자 확인 뒤 `overwrite: true` |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | 1회만 다시 보낸다(`timeout_sec` 은 50 을 넘기지 않는다 — Cowork 호출 상한 60초). itda-hyve 는 끊긴 뒤에도 돌아 파일을 나중에 쓸 수 있다 — 다시 보낸 것이 "같은 이름" 으로 거부되면 그 파일이 생긴 것이니 그대로 쓴다 |

## collect 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--input` | 저장한 응답 파일(들). 이름 규칙 `bids-<시작>-<끝>-p<쪽>.json` | (필수) |
| `--keyword` | 공고명 키워드 필터 (부분 일치, 대소문자 무시). 전 쪽을 받은 뒤 필터 | — (전체) |
| `--max-pages` | 창마다 받을 쪽 상한. 넘으면 `truncated` | 20 |
| `--single-page` | 전량 대조 없이 넘긴 쪽만 훑어본다("최근 공고 몇 건만 보여줘") | — |
| `--next-plan` | 전량 미달이면 더 받을 호출을 batch `plan_file` 로 쓴다 | — |
| `--format` | `json` / `table` | `json` |
| `--detail` | 상세 정보 포함 (table) | — |

`plan` 옵션: `--from`(기본 7일 전) · `--to`(기본 오늘) · `--rows`(쪽당 행, 기본·최대 999) · `--write`(batch 계획 파일).

### JSON 출력 필드 의미

| 필드 | 의미 |
|------|------|
| `total_count` | API가 보고한 **필터 전** 기간 전체 결과 수(창 합) |
| `scanned_count` | 받은 쪽에서 중복을 없앤 항목 수. `total_count`보다 작은 경우는 셋이다 — `truncated`, `--single-page`, 받는 사이 공고가 바뀜(`warnings` 에 "totalCount 가 다릅니다") |
| `count` | **키워드 필터 후** 결과 수 (`results` 길이와 일치) |
| `truncated` | `--max-pages` 상한 때문에 미조회분이 남으면 `true` |
| `windows` | 창별 `from`·`to`·`total_count`·받은 `pages`·`collected` |
| `warnings` | 미조회분·쪽 경계 중복·쪽마다 다른 totalCount (있을 때만) |
| `page` | `--single-page` 면 쪽 번호, 아니면 `"all"` |

`incomplete` 오류 출력: `next_call_count` · `will_truncate` · `windows`(창별 `need_pages`·`will_truncate`) · `next_calls`(`--next-plan` 없을 때) 또는 `plan_files`·`next_calls_preview`(있을 때).

**쪽 매김의 한계** — 이 API 는 오프셋 쪽 매김이다. 받는 사이 앞쪽에서 1건이 지워지고 뒤쪽에 1건이 더해지면 `totalCount` 가 같아
경고 없이 1건이 빠질 수 있다. 판정은 쪽마다 `totalCount` 의 **최댓값**을 분모로 둬 삭제로 밀린 경우는 잡지만, 삭제와 추가가 상쇄되면 못 본다.
정확한 건수가 중요하면 같은 기간을 한 번 더 받아 `total_count`·`scanned_count` 가 같은지 본다.

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 가공 실패 — `error`: `incomplete`(쪽 모자람) · `api`(본문 오류 코드) · `truncated`·`http`(응답 JSON 전체를 옮겨 적은 파일에서 본문 잘림·HTTP 오류) · `hyve`(itda-hyve 실패 자리) · `input`(파일 없음·JSON 아님·이름 규칙 위반·같은 쪽 두 번·이름의 쪽과 본문 `pageNo` 불일치) |
| 2 | 인자 오류 (`argument` — 날짜 형식) |

## 트리거 키워드

나라장터, 입찰공고, 조달청, G2B, 입찰, 공고, 나라장터 공고, 조달 공고, 입찰 검색,
정부 조달, 수의계약, 일반경쟁, 공고번호,
procurement, tender, bid announcement, G2B, narajangteo, government procurement

## 파일 구조

```
g2b/
  SKILL.md
  GUIDE.md
  CHANGELOG.md
  scripts/
    g2b_api.py          # 창 나누기·호출 인자·응답 파서·창별 전량 대조
    collect_g2b.py      # plan / collect CLI
  tests/
    test_g2b_api.py     # 창·파서·전량 대조 (실측 픽스처)
    test_collect_g2b.py # CLI
    fixtures/           # 2026-09-30 itda-hyve 실측 응답(담당자 정보 가림)
  references/
    netbridge.md                              # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    g2b.md                                    # 나라장터 API 사용 가이드
    g2b-pubdata-opnstd-service-v1.1.md        # 조달청 정본 (검색·발췌용)
    g2b-pubdata-opnstd-service-v1.1.docx      # 조달청 정본 원본
```

## 테스트 실행

```bash
python3 -m pytest itda-gov/skills/g2b/tests -q     # Windows: py -3 -m pytest …
```

## 상세 API 가이드

- [references/g2b.md](references/g2b.md) — 나라장터 API 사용 가이드(오류 형태·필드)
- 조달청 정본 문서 (v1.1)
  - [g2b-pubdata-opnstd-service-v1.1.docx](references/g2b-pubdata-opnstd-service-v1.1.docx) — 공공데이터개방표준서비스 OpenAPI 참고자료 원본
  - [g2b-pubdata-opnstd-service-v1.1.md](references/g2b-pubdata-opnstd-service-v1.1.md) — 동일 내용 Markdown 변환본 (검색·발췌용)
