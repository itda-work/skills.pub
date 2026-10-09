---
name: eatery-trend
description: >
  여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다.
  "제주 요즘 뜨는 맛집", "성수에서 트렌디한 국밥", "지금 핫한 디저트 뭐야"처럼 말하면 됩니다.
  평점(레벨)이 아니라 관심의 급증(velocity)으로 유행을 판별하고 가게는 네이버 지역검색으로 찾습니다.
  요청은 itda-hyve 가 보내고 네이버 오픈API 키는 itda-hyve 시크릿에 둡니다(월검색량·협찬 거품 판정은 지금 빠집니다).
license: MIT
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch plan_file)이 한다. 키는 itda-hyve 시크릿 NAVER_CLIENT_ID·NAVER_CLIENT_SECRET."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Read, Bash, Write, mcp__workspace__bash"
argument-hint: "[지역/테마] 또는 [동네 주제]"
metadata:
  author: "Chinseok"
  version: "0.4.0"
  category: "data-fetching"
  status: "experimental"
  created_at: "2026-06-01"
  updated_at: "2026-10-06"
  tags: "restaurant, food-trend, hotplace, search-volume, surge, naver-datalab, eatery-trend"
---

# eatery-trend

여행지·동네의 **지금 뜨는 맛집·음식 트렌드**를 탐지합니다. 핵심 가설:
**유행 = 평점(레벨)이 아니라 관심의 미분(검색량 velocity)**. 네이버 데이터랩
검색트렌드의 surge를 측정해 *지금 떠오르는지*를 판별하고, 장소는 네이버 공식 지역검색 API로 해결합니다(스크래핑 0).
사용자용 가이드는 GUIDE.md 참조.

## 두 모드

- **모드 B — 핫키워드 탐지(주 파이프라인)**: `지역/테마 seed`(예: 제주) → 지역×음식 후보 10개의 surge 순위 Top-N + 근거 + 매핑 가게.
- **모드 A — 검색 보강**: `동네 + 주제`(예: 성수 국밥) → 가게목록 + 주제 surge 맥락.

## 쓰는 소스 (2026-10-06, itda-work/skills#46)

| 소스 | 지금 | 비고 |
|---|---|---|
| 데이터랩 검색어트렌드 (`POST https://openapi.naver.com/v1/datalab/search`) | **씀** | surge·카테고리 macro YoY. 하루 1,000회 한도 |
| 지역검색 (`GET https://openapi.naver.com/v1/search/local.json`) | **씀** | 라이저의 가게(쿼리당 5건) |
| 검색광고 키워드도구(월검색량·연관 키워드) | 빠짐 | 요청마다 서명 — itda-hyve 서명 기능(itda-work/itda-hyve#34) 대기 |
| 블로그 검색 total(협찬 거품) | 빠짐 | 거품 비율 = 블로그/**월검색량** — 분모가 검색광고라 함께 돌아온다 |
| 자동완성 `ac.search.naver.com` | **부르지 않음** | robots `User-agent: *` 전면 불허(2026-10-06 확인). 후보는 지역×음식 그리드뿐 |

월검색량이 없으므로 magnitude floor 는 **데이터랩 baseline 만** 보고(저볼륨 노이즈 격리는 그대로), 결과에 `level_known: false` 와
"월검색 미확인 · 거품 판정 보류" 가 실린다. **Claude 실행 규칙:** 그 두 가지가 빠졌다는 것을 결과와 함께 한 줄로 알린다 —
"레벨이 낮다" 나 "거품이 아니다" 로 바꿔 말하지 않는다.

## 흐름 — 요청은 itda-hyve, 계획과 가공은 스크립트

네트워크는 **itda-hyve**(`mcp__remote-devices__itda-hyve__http_request`·`mcp__remote-devices__itda-hyve__batch`)로만 나간다.
스크립트는 네트워크를 하지 않는다 — **호출 계획을 회차 폴더에 쓰고**, itda-hyve 가 `save_as` 로 저장한 파일을 읽어 판정만 한다.
저장 이름·데이터랩 조회 기간·받을 가게 검색은 스크립트가 정한다 — **호출 JSON 을 손으로 고치거나 새로 짓지 않는다.**
공용 규약(실패 코드·보안 계약)은 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan → http_request(single_calls: 데이터랩 POST, 하나씩) [+ batch(plan_file: 지역검색 GET)]
     → collect → (incomplete 면 새 single_calls·batch_args 를 받고 collect 다시) → ok: report
```

모드 B 는 보통 두 번 돈다(1회차 데이터랩 3건 → 2회차 라이저의 지역검색 최대 10건). 모드 A 는 한 번(데이터랩 2건 + 지역검색 1건).
**받기 전에 호출 수를 알린다** — 모드 B 약 13회(데이터랩 3 + 지역검색 ≤10), 모드 A 3회. 데이터랩은 계정당 하루 1,000회 한도다.

## 실행

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
printf "%s\n" "$c"' _ eatery-trend itda-travel "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'eatery-trend'; $P = 'itda-travel'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

회차 폴더를 정한다 — `R` 은 스크립트가 보는 경로, `S` 는 **같은 폴더**의 itda-hyve 호스트 절대 경로다(Claude Code 에서는 둘이 같다.
Cowork 에서는 연결 폴더 안의 하위 폴더 — `R` 은 VM 의 마운트 경로, `S` 는 사용자 PC 의 그 폴더 경로). 회차마다 새 폴더를 쓴다.

### ① 계획

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" plan --mode B --seed 제주 --run-dir "$R" --save-dir "$S"
python3 "$SKILL_DIR/scripts/main.py" plan --mode A --region 성수 --topic 국밥 --run-dir "$R" --save-dir "$S"

# Windows
py -3 "$env:SKILL_DIR\scripts\main.py" plan --mode B --seed 제주 --run-dir "$R" --save-dir "$S"
```

옵션: `--top-n N`(모드 B, 1~25, 기본 10) · `--json`(report 문자열 없이).

출력 `status: incomplete` 에 받을 호출이 두 갈래로 온다 — 둘 다 **전부** 부른 뒤 ③ 으로 간다:

- `single_calls` — 한 칸이 곧 `http_request` 인자다(`save_dir` 포함). **하나씩 그대로** 부른다(데이터랩 POST — batch 는 GET 만 받는다).
- `batch_args` — `batch` 에 **그대로** 넘긴다(`{"save_dir": …, "plan_file": "plan-<n>.json"}` — 지역검색 GET). 없으면 빈 목록이다.

### ② itda-hyve 로 받기

`single_calls` 한 칸(데이터랩, plan 이 준 그대로 — `body` 문자열을 바꾸지 않는다):

```json
{"url": "https://openapi.naver.com/v1/datalab/search", "method": "POST",
 "headers": {"X-Naver-Client-Id": "{{secret:NAVER_CLIENT_ID}}", "X-Naver-Client-Secret": "{{secret:NAVER_CLIENT_SECRET}}",
             "Content-Type": "application/json"},
 "body": "{\"startDate\":\"2025-04-07\",\"endDate\":\"2026-10-06\",\"timeUnit\":\"week\",\"keywordGroups\":[{\"groupName\":\"제주 맛집\",\"keywords\":[\"제주 맛집\"]}]}",
 "retry_unsafe": true, "follow_redirects": false, "timeout_sec": 50,
 "save_as": "raw/dl-3f9a1c2b7e.json", "save_dir": "/Users/me/Documents/eatery-runs/20261006-1400"}
```

계획 파일 안의 지역검색 한 칸(batch 가 부른다):

```json
{"id": "ls-8c41d0a9f2", "tool": "http_request",
 "args": {"url": "https://openapi.naver.com/v1/search/local.json", "params": {"query": "제주 국수", "display": "5"},
          "headers": {"X-Naver-Client-Id": "{{secret:NAVER_CLIENT_ID}}", "X-Naver-Client-Secret": "{{secret:NAVER_CLIENT_SECRET}}"},
          "follow_redirects": false, "timeout_sec": 50, "save_as": "raw/ls-8c41d0a9f2.json"}}
```

- 키는 **헤더의 자리표시**뿐이다. URL·`params`·`body` 에 키를 넣지 않는다. `User-Agent` 를 더하지 않는다(itda-hyve 0.10.4 기본 UA).
- **`save_as` 는 plan 이 준 이름을 바꾸지 않는다** — 이름이 요청 모양의 지문이라 ③ 이 이름으로 짝을 맞춘다. 같은 이름이 이미 있으면
  덮어쓰지 않는다(`overwrite` 금지 — 다시 받을 때는 스크립트가 `-r2`·`-r3` 이름을 준다).
- 호출이 itda-hyve 오류를 돌려주면(파일이 생기지 않는다) 그 호출의 **`R` 기준** `"$R/<save_as>"` 에
  `{"error": {"code": "<error.code>", "message": "<error.message>"}}` 한 줄을 **Write 로** 쓴다(스크립트가 "실패"와 "아직 안 받음"을 가르게).
  이미 파일이 있어 거부된 호출(`invalid_input`)에는 쓰지 않는다.
- 응답 `status` 가 200 이 아니어도 손대지 말고 ③ 으로 간다 — 저장된 오류 본문을 스크립트가 판정한다. **같은 요청을 다시 보내지 않는다.**
- **응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다.** 필요한 것은 `status`·`saved_path` 뿐이다.
- 도구 스키마에 `plan_file` 이 없으면(옛 itda-hyve) 계획 파일의 `calls[].args` 를 `http_request` 로 하나씩 부른다(`save_dir` 를 더해서).

### ③ 판정

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R"
```

| `status` | exit | 뜻 | 행동 |
|---|---|---|---|
| `ok` | 0 | 파이프라인이 원한 응답을 다 받았다 | `report` 문자열을 **그대로** 보여 주고 빠진 소스(월검색량·거품) 한 줄을 덧붙인다 |
| `incomplete` | 1 | 받을 호출이 남았다(다음 단계·빠진 파일·실패해 다시 받기) | 새 `single_calls`·`batch_args` 를 **전부** 부른 뒤 ③ 반복. `warning` 이 있으면 지난 계획을 아직 안 부른 것이다 |
| `partial` | 2 | 같은 요청을 세 번 받아도 실패(잘림·HTTP 오류·형식)했거나, 세 번 계획했는데 파일이 없었다 | **성공으로 취급하지 않는다.** `errors` 를 전하고, 받은 만큼의 `report` 를 "일부" 로 보여 준다 |
| `error` | 1 | `hyve`(`secret_missing`·`secret_host_denied`) · `naver`(키·앱 설정 오류 — errorCode 024·028·010) · `input`·`args` | `detail` 대로 안내하고 **멈춘다** — 다시 보내지 않는다. 사용자가 고쳤다고 하면 **같은 `--run-dir` 로 `collect`** 를 다시 부른다(멈춘 호출을 다시 받을 계획이 나온다) |

### 실패 코드 (itda-hyve)

| 코드 | 뜻 | 행동 |
|---|---|---|
| `secret_missing` | 시크릿 탭에 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET` 이 없다 | **값을 대화로 받지 않는다.** 시크릿 탭에 그 이름으로 등록하라고 안내하고 멈춘다 |
| `secret_host_denied` | 그 키를 이 호스트로 못 보낸다 | URL 이 `openapi.naver.com` 인지 확인. 같다면 시크릿의 허용 호스트에 `openapi.naver.com` 을 넣게 안내한다. 다른 주소로 우회하지 않는다 |
| 본문 절단·시간 초과·연결 실패 | 응답을 다 못 받았다 | 실패 자리를 쓰고 ③ — 스크립트가 다시 받을 이름을 준다 |

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 반드시 따르는 행동 규칙입니다. (전 사용자 공유
행동 규칙의 single source of truth는 본 섹션)

**규칙 1 — 모드 판별**
"요즘 뜨는 맛집", "제주 핫플", "지금 뭐가 떠?"처럼 *지역/테마*만 있으면 모드 B
(`plan --mode B --seed <지역>`). "성수 국밥", "이 동네 트렌디한 곳"처럼 *동네+주제*면
모드 A(`plan --mode A --region <동네> --topic <주제>`).

**규칙 3 — 레벨 vs 속도 구분 (REQ-006)**
출력의 "레벨(월검색량)"과 "속도(surge/상대YoY)"를 혼동해 설명하지 않습니다. 지금은 레벨이 "미확인" 이다 —
속도만으로 말하고, 레벨을 짐작해 채우지 않습니다.

**규칙 4 — 3레인 분리 표기 (REQ-017)**
🆕 신규출현 / 🔥 검증상승 / 📺 미디어스파이크를 구분해 전달합니다. 미디어스파이크
(성시경·흑백요리사 효과)는 **지속성이 약할 수 있음**을 함께 안내합니다(막주 모멘텀).

**규칙 5 — 강등 사유 전달 (REQ-007)**
노이즈(floor 미달)·안정/클래식 강등 사유를 전달합니다. 협찬 거품 판정은 지금 보류 상태다(월검색량 없음) — "거품 아님" 으로 말하지 않습니다.

**규칙 6 — fail-loud (REQ-008)**
출력의 `🚨 소스 상태` 에는 늘 빠진 소스(검색광고·자동완성)가 실린다 — 그 밖의 항목(데이터랩·지역검색 실패)이 있으면 그 사실을 알립니다.
빈 결과를 "뜨는 곳 없음"으로 단정하지 않습니다.

**규칙 7 — 출력 한국어 고정**, 모드 A는 모든 가게에 surge를 붙이지 않습니다(평범한
가게가 평탄한 건 정상 — REQ-020).

## 사전 준비 (자격증명)

네이버 오픈API 키 두 개를 **itda-hyve 앱의 시크릿 탭**에 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET` 이름으로 등록한다(web-search 와 같은 이름 —
이미 등록했다면 그대로 쓰인다). 허용 호스트는 `openapi.naver.com`. 애플리케이션 사용 API 에 **검색**과 **데이터랩(검색어트렌드)** 을 함께 넣는다.
키 값을 대화로 받지 않는다 — 붙여 넣어도 쓰지 않고 시크릿 탭 등록을 안내한다. 발급 절차: [네이버 오픈API](https://itda.work/credentials/naver-openapi/).

> **⚠️ NAVER API HUB 이관 고지 (2026-07 약관 변경)**: 네이버 OpenAPI(검색·데이터랩)는 네이버클라우드(NCP) **NAVER API HUB**로 이관된다. 2026-07-30 이후 개발자센터 신규 이용 신청 불가 — 신규 사용자는 NAVER API HUB에서 발급하도록 안내한다. 기존 키는 **2027-06-30까지** 현행대로 동작한다.

## 제약 (Exclusions)

- **인스타그램 직접 스크래핑 영구 비목표** — 검색량 surge가 인스타 유행의 다운스트림 그림자.
- 예약/결제(캐치테이블 영역) · 실시간 분 단위(데이터랩 일/주 lag 수용) 미지원.
- v1 wedge = 여행지/테마. 전국 cold 신상 발굴은 콘텐츠(유튜브) 발굴축 도입 후(로드맵).
- 지역검색 쿼리당 5건 cap · 0매칭(팝업/미등록)은 웹 폴백 권장 · 동음 다수는 리뷰수 tiebreak(OQ-3 잔여).
- surge 절대값은 작을 수 있음(1.2~2.2) · 카테고리 상대 YoY로 macro 보정하나 데이터랩 범위 제약.
