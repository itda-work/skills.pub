---
name: ecos
description: >
  한국은행 ECOS API로 거시경제 지표를 조회하는 스킬입니다.
  "GDP 추이 알려줘", "금리 환율 정리해줘", "100대 경제지표 확인해줘"처럼 말하면 됩니다.
  GDP·금리·환율·CPI·100대 핵심 지표 데이터셋을 다룹니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[key|search|word|items|tables] 지표·통계표코드·기간 (예: 소비자물가지수 2020~2024 연간)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.12.1"
  created_at: "2026-03-29"
  updated_at: "2026-10-01"
  tags: "GDP, ECOS, CPI, economics, interest rate, exchange rate, Bank of Korea"
---

# ecos

한국은행 ECOS(경제통계시스템) API로 거시경제 지표를 수집합니다.
GDP·금리·환율·물가·100대 경제지표 등 정책 보고서와 사업계획서에 필요한 경제 데이터를 제공합니다.

- **5개 서비스**: 100대 지표(key) · 통계 조회(search) · 세부항목(items) · 통계표 목록(tables) · 용어사전(word)
- **전량 수집**: 응답의 `list_total_count` 까지 1000행씩 이어 받는다 — 모자라면 스크립트가 실패로 끝낸다

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 여러 쪽은
**itda-hyve 의 `batch`**(`mcp__remote-devices__itda-hyve__batch`)로 한 번에 받을 수 있다.
스크립트는 네트워크를 하지 않는다 — itda-hyve 가 `save_as` 로 저장한 응답 JSON 을 `--input` 으로 읽어 오류 판정·전량 대조·정리만 한다.
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
(코드를 모르면 tables·items 로 확인) → 명령마다 http_request + save_as → collect_econ.py <명령> --input …
```

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`ECOS_API_KEY`** 로 등록해 둔 것을 URL **경로**의 `{{secret:ECOS_API_KEY}}` 자리표시자로만 가리킨다.
값을 묻지 않고, 대화에 붙여 넣어도 쓰지 않는다. 발급: <https://ecos.bok.or.kr/api/> 회원가입 → 인증키 신청(즉시 발급).

## 1단계 — itda-hyve 의 http_request 로 받기

URL 은 전부 경로 방식이다. 쿼리(`params`)는 쓰지 않는다.

```
https://ecos.bok.or.kr/api/<서비스>/{{secret:ECOS_API_KEY}}/json/kr/<시작행>/<끝행>/<선택 세그먼트…>/
```

| 명령 | `<서비스>` | 선택 세그먼트 | 저장 이름(`save_as`) |
|---|---|---|---|
| `key` | `KeyStatisticList` | — | `ecos/key-r<시작행>.json` |
| `search` | `StatisticSearch` | `<통계표코드>/<주기>/<시작>/<끝>` [`/<항목1>` [`/<항목2>`]] | `ecos/search-<통계표코드>-<주기>-<시작>-<끝>[-<항목1>[-<항목2>]]-r<시작행>.json` |
| `items` | `StatisticItemList` | `<통계표코드>` | `ecos/items-<통계표코드>-r<시작행>.json` |
| `tables` | `StatisticTableList` | — | `ecos/tables-r<시작행>.json` |
| `word` | `StatisticWord` | `<용어>`(한글 그대로) | `ecos/word-<순번>-r<시작행>.json` |

예 — 소비자물가지수(901Y009) 연간 2020~2024:

```json
{"url": "https://ecos.bok.or.kr/api/StatisticSearch/{{secret:ECOS_API_KEY}}/json/kr/1/1000/901Y009/A/2020/2024/",
 "timeout_sec": 30,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "ecos/search-901Y009-A-2020-2024-r1.json"}
```

예 — 용어 "기준금리":

```json
{"url": "https://ecos.bok.or.kr/api/StatisticWord/{{secret:ECOS_API_KEY}}/json/kr/1/1000/기준금리/",
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "ecos/word-1-r1.json"}
```

- `<주기>`: `A`(연) · `S`(반기) · `Q`(분기) · `M`(월) · `D`(일). `<시작>`·`<끝>` 은 주기 형식을 따른다 — `2024` · `2024S1` · `2024Q1` · `202401` · `20240101`.
  형식이 어긋나면 `ERROR-101` 이다. 분기 GDP 예: `…/200Y106/Q/2020Q1/2024Q4/`.
- 항목코드는 필요할 때만 뒤에 붙인다(`…/731Y003/D/20240102/20240131/0000003/`). 코드를 모르면 `items` 를 먼저 받는다.
  항목코드를 붙였으면 **저장 이름에도 붙인다**(`ecos/search-731Y003-D-20240102-20240131-0000003-r1.json`) — 항목만 바꿔 받을 때 이름이 겹치지 않는다.
- **저장 이름 끝의 `-r<시작행>` 은 계약이다.** 응답 본문에는 행 범위가 없어 2단계 스크립트가 이 이름으로 범위를 세운다 — 이름을 바꾸지 않는다.
- 한글 용어는 경로에 **그대로** 쓴다 — itda-hyve 가 한 번 인코딩한다(미리 인코딩해도 같은 URL 로 나간다, 2026-09-30 실측). 저장 이름에는 한글을 넣지 않고 순번을 쓴다.
- **`save_dir` 에는 Cowork 연결 폴더의 호스트 경로**(절대 경로, 사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외)를 넣는다. 생략하면 itda-hyve 기본 저장 폴더.
- 같은 이름이 이미 있으면 덮어쓰지 않고 `invalid_input` 으로 거부된다. 다시 받을 때는 `save_dir` 를 새 하위 폴더로 바꾸거나, 사용자가 확인했을 때만 `overwrite: true`.

### 쪽 이어받기 — 1000행씩, `list_total_count` 까지

한 요청은 **1000행**(`1/1000`)씩 받는다. 응답의 `list_total_count` 가 전체 행 수다(2026-09-30 실측: 100대 지표 101 ·
통계표 목록 844 · 901Y009 세부항목 **1,743** — 세부항목은 2쪽이다).

1. 먼저 `1/1000` 을 받아 2단계를 돌린다.
2. 모자라면 스크립트가 `error: "incomplete"` 와 함께 **더 받을 행 범위** `missing_ranges`(`["1001~1743"]` 등)와 호출 수 `need_calls` 를 준다.
   범위마다 `<시작행>/<끝행>` 에 넣어 같은 URL 로 받고(`save_as` 는 `…-r1001.json`), **앞 파일과 함께** 다시 넘긴다.
3. `status: "ok"` 가 나올 때까지 되풀이한다. **incomplete 인 채로 결과를 말하지 않는다.**

넘기기 전에 스크립트가 보는 것 — 어긋나면 `error: "input"` 이다(행 수 합만 맞아도 통과시키지 않는다):

- 모든 파일의 `list_total_count` 가 같은가(다르면 다른 통계표·기간·항목의 응답이 섞였다)
- 같은 시작행이 두 번이거나 행 범위가 겹치지 않는가(다시 받은 사본은 **새 폴더의 것 하나만** 넘긴다)
- 같은 행이 두 번 나오지 않는가

빈 범위는 1행부터 끝까지 정확히 계산해 알려 준다 — 둘째 쪽만 넘기면 `1~1000` 을, 1쪽과 셋째 쪽만 넘기면 가운데를 안내한다.

### 응답 판정 — HTTP 200 은 성공이 아니다

- ECOS 는 오류도 HTTP 200 으로 준다. 본문이 `{"RESULT": {"CODE": …}}` 면 오류다(`INFO-200` 데이터 없음만 빈 결과로 성공).
  판정은 2단계 스크립트가 파일을 읽어 대신 한다(`error: "api"` + `error_code`).
- 응답 요약의 `final_url` 을 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

### 호출 예산

명령마다 보통 1회다(`list_total_count` 가 1000 을 넘으면 1000행마다 1회 더). 여러 지표·여러 통계표를 한 번에 요청받으면
**예상 호출 수를 먼저 알린다**. `ERROR-602`(과도한 호출)가 나면 멈춘다 — 연달아 다시 부르지 않는다.

- **첫 쪽 뒤 `confirm_first: true`**(남은 호출 `need_calls` 가 5회 초과 = 5,000행 초과)면 받기 전에 사용자에게 호출 수를 알리고
  확인받는다. 일간 표를 항목코드 없이 장기로 받으면(예: `731Y003/D/2000…/2024…`) 수십만 행이 될 수 있다 — 기간을 줄이거나
  항목코드를 붙이는 쪽을 먼저 권한다.
- 남은 범위가 여럿이면 `batch`(GET)로 한 번에 받는다. 한 번에 40호출까지, `save_as` 는 범위마다 다르게:

```json
{"save_dir": "/Users/me/Projects/작업폴더", "timeout_sec": 50,
 "calls": [{"id": "r1001", "tool": "http_request",
            "args": {"url": "https://ecos.bok.or.kr/api/StatisticItemList/{{secret:ECOS_API_KEY}}/json/kr/1001/2000/901Y009/",
                     "save_as": "ecos/items-901Y009-r1001.json"}},
           {"id": "r2001", "tool": "http_request",
            "args": {"url": "https://ecos.bok.or.kr/api/StatisticItemList/{{secret:ECOS_API_KEY}}/json/kr/2001/2500/901Y009/",
                     "save_as": "ecos/items-901Y009-r2001.json"}}]}
```

  도구 목록에 `batch` 가 없으면(옛 판) 범위마다 `http_request` 로 하나씩 부른다.

### itda-hyve 실패 코드

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `ECOS_API_KEY` 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `ecos.bok.or.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `invalid_input` | URL 쿼리(`?…`)에 자리표시자를 넣었거나 같은 이름 파일이 있다 — 경로 방식 URL·새 하위 폴더로 고친다 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | 1회만 다시 보낸다(`timeout_sec` 은 50 을 넘기지 않는다 — Cowork 호출 상한 60초). itda-hyve 는 끊긴 뒤에도 돌아 파일을 나중에 쓸 수 있다 — 다시 보낸 것이 "같은 이름" 으로 거부되면 그 파일이 생긴 것이니 그대로 쓴다 |

## 2단계 — 저장한 응답을 스크립트로 가공

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
printf "%s\n" "$c"' _ ecos itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'ecos'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

Cowork 에서는 연결 폴더가 샌드박스의 `$HOME/mnt/<폴더 이름>` 에 마운트된다 — `save_dir` 의 **폴더 이름** 뒤에 `saved_path` 를 붙인다
(파일을 찾아 헤매지 않는다). Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다.

```bash
# save_dir 가 /Users/me/Projects/작업폴더 였다면
python3 "$SKILL_DIR/scripts/collect_econ.py" search --input "$HOME/mnt/작업폴더/ecos/search-901Y009-A-2020-2024-r1.json"
python3 "$SKILL_DIR/scripts/collect_econ.py" --format table key --input "$HOME/mnt/작업폴더/ecos/key-r1.json"

# 여러 쪽은 전부 나열한다(순서 무관)
python3 "$SKILL_DIR/scripts/collect_econ.py" items \
  --input "$HOME/mnt/작업폴더/ecos/items-901Y009-r1.json" "$HOME/mnt/작업폴더/ecos/items-901Y009-r1001.json"

# Windows
py -3 "$env:SKILL_DIR\scripts\collect_econ.py" key --input "…\ecos\key-r1.json"
```

명령(`key`·`search`·`items`·`tables`·`word`)은 받은 서비스와 맞아야 한다 — 다른 서비스의 응답을 넘기면 `error: "input"` 이다.

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--input` | itda-hyve 가 저장한 응답 JSON(들). 쪽(행 범위)마다 1개, 이름 끝은 `-r<시작행>.json` | (필수) |
| `--format` | `json` / `table` (명령 앞·뒤 어디든) | `json` |

출력(json): `status`·`count`·`total_count`(`list_total_count`)·`items`(search 는 `data`)·`sources`(파일별 `start_row`·행 수).
`search` 는 `stat_code`·`period`(TIME 형식으로 추정)와, 값이 숫자가 아니라 뺀 행 수 `skipped_non_numeric`(0 이 아니면 `warnings`)를 싣는다.
응답에 `list_total_count` 가 없으면 받은 행 수로 세되 `warnings` 에 "전량 기준선이 없다" 를 싣는다 — 전량이라고 말하지 않는다.
`incomplete` 오류 출력: `missing_ranges`·`need_calls`·`confirm_first`.

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 (`INFO-200` 데이터 없음은 `count: 0` 성공) |
| 1 | 가공 실패 — `error`: `incomplete`(행 범위가 비었음) · `api`(본문 RESULT.CODE) · `truncated`·`http`(응답 JSON 전체를 옮겨 적은 파일에서 본문 잘림·HTTP 오류 — `save_as` 원본이 잘렸거나 HTML 오류 페이지면 `input`) · `hyve`(itda-hyve 실패 자리) · `input`(파일 없음·JSON 아님·다른 서비스·이름 규칙 위반·질의 혼입·범위 중복·행 중복) |
| 2 | 인자 오류 |

## 트리거 키워드

GDP, 금리, 환율, 물가, CPI, ECOS, 한국은행, 거시경제, 100대 지표,
경제지표, 소비자물가, 생산자물가, 기준금리, 달러환율,
economics, interest rate, exchange rate, inflation, Bank of Korea

## 파일 구조

```
ecos/
  SKILL.md
  scripts/
    ecos_api.py                       # 응답 파서·전량 대조·오류 코드 분류
    collect_econ.py                   # 가공 CLI (key/search/items/tables/word)
  tests/
    test_ecos_api.py                  # --input 가공·전량 대조·오류 (실측 픽스처)
    test_collect_econ_arg_position.py # CLI 인자 회귀 테스트
    fixtures/                         # 2026-09-30 itda-hyve 실측 응답(공개 시험 키 sample)
  references/
    netbridge.md                      # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    ecos.md                           # 요청 URL·주기 형식·자주 쓰는 통계표코드
    ecos-매뉴얼/                       # 한국은행 정본 명세 (xls + 발췌 md 6종)
```

## 오류 처리

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| `secret_missing` (itda-hyve) | `ECOS_API_KEY` 미등록 | itda-hyve GUI 시크릿 탭에 등록 |
| `error: incomplete` | 1000행을 넘는 결과를 첫 쪽만 넘김 | `missing_ranges` 를 더 받아 함께 넘긴다 |
| `error: input` "list_total_count 가 다릅니다" | 다른 질의의 파일이 섞임 | 한 명령에는 같은 URL 의 쪽들만 넘긴다 |
| `error: input` "두 번" · "겹칩니다" | 같은 범위를 두 폴더에서 넘김 | 한 폴더의 파일만 넘긴다 |
| `INFO-100` | 인증키 무효 | 시크릿 탭의 키 확인(앞뒤 공백), 발급 직후면 수 분 뒤 |
| `ERROR-101` | 주기와 날짜 형식 불일치 | 위 주기 형식 확인 |
| `INFO-200` | 기간·항목에 데이터 없음 | `items` 로 항목·기간(`START_TIME`~`END_TIME`) 확인 |

### 정본 RESULT 코드 (ECOS API 6개 공통)

#### 정보 (INFO) 타입

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| INFO-100 | 인증키 무효 | 활용신청 URL 확인 |
| INFO-200 | 데이터 없음 | 정상 응답 (결과 0건) |

#### 에러 (ERROR) 타입

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| ERROR-100 | 필수 값 누락 | 인자 형식 확인 |
| ERROR-101 | 주기/날짜 형식 불일치 | A:2024 / Q:2024Q1 / M:202401 / D:20240101 |
| ERROR-200 | 파일타입 오류 | xml 또는 json 사용 |
| ERROR-300 | 조회건수 누락 | 시작/종료 건수 명시 |
| ERROR-301 | 조회건수 타입 오류 | 정수 입력 |
| ERROR-400 | 검색범위 초과 (60초 TIMEOUT) | 검색 범위를 좁혀 재요청 |
| ERROR-500 | 서버 오류 / 서비스명 오류 | 잠시 후 재시도 |
| ERROR-600 | DB Connection 오류 | 잠시 후 재시도 |
| ERROR-601 | SQL 오류 | 잠시 후 재시도 |
| ERROR-602 | 호출 제한 (과도한 호출) | 백오프 후 재시도 |

> 응답은 `{"RESULT": {"CODE", "MESSAGE"}}` 형식이고 HTTP 200 으로 온다. 인증키 무효(INFO-100)는 스크립트가 활용신청 URL(`https://ecos.bok.or.kr/api/`)과 시크릿 등록 안내를 붙인다.

## 상세 API 가이드

`references/ecos-매뉴얼/` 디렉토리에 한국은행 ECOS API 6개 서비스의 정본 명세 (xls + 발췌 md)를 보관합니다.

| API 서비스 | 정본 xls + 발췌 md |
|-----------|------------------|
| StatisticTableList (서비스 통계 목록) | [01-StatisticTableList.md](references/ecos-매뉴얼/01-StatisticTableList.md) |
| StatisticWord (통계용어사전) | [02-StatisticWord.md](references/ecos-매뉴얼/02-StatisticWord.md) |
| StatisticItemList (통계 세부항목 목록) | [03-StatisticItemList.md](references/ecos-매뉴얼/03-StatisticItemList.md) |
| StatisticSearch (통계 조회) | [04-StatisticSearch.md](references/ecos-매뉴얼/04-StatisticSearch.md) |
| KeyStatisticList (100대 통계지표) | [05-KeyStatisticList.md](references/ecos-매뉴얼/05-KeyStatisticList.md) |
| StatisticMeta (통계메타DB) | [06-StatisticMeta.md](references/ecos-매뉴얼/06-StatisticMeta.md) |
| 통합 인덱스 + 공통 에러 코드 | [README.md](references/ecos-매뉴얼/README.md) |

기존 요약본: [references/ecos.md](references/ecos.md)
정본 xls (한국은행 발간): `references/ecos-매뉴얼/API개발명세서_*.xls` (6종)
