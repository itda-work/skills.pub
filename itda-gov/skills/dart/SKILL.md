---
name: dart
description: >
  금융감독원 DART 전자공시 API로 기업 정보를 수집하는 스킬입니다.
  "삼성전자 재무제표 조회해줘", "경쟁사 직원수 알려줘", "사업보고서 비교해줘",
  "네이버 배당 현황", "셀트리온 소송 이력"처럼 말하면 됩니다.
  기업 프로필·재무·인력·사업보고서·공시 목록에 더해 배당·증자·소송·전환사채 등 주요사항도 반환합니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request·batch plan_file)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, mcp__remote-devices__itda-hyve__batch, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "[search|info|finance|employees|profile|disclosure|business|compare|raw] [--name 회사명] [--corp-code 코드] [--year 연도] [--report annual|q1|q2|q3] [--prefer annual|latest] [--detail] [--unit auto|million|eok|jo] [--with-ratios] [--with-prior] [--endpoint 엔드포인트] [--param key=value] [--format json|table|csv]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  recommended: true
  version: "0.21.1"
  created_at: "2026-03-29"
  updated_at: "2026-10-01"
  tags: "DART, CSV, company, financial, disclosure, competitor, business report, compare"
---

# dart

금융감독원 DART 전자공시시스템 API로 기업 정보를 수집합니다.
경쟁사 분석, 입찰 제안서, 사업계획서에 필요한 기업 재무·직원 데이터를 제공합니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 여러 호출은
**itda-hyve 의 `batch`**(`mcp__remote-devices__itda-hyve__batch`)로 한 번에 받는다. 스크립트는 네트워크를 하지 않는다 —
명령에 필요한 호출을 알려 주고, itda-hyve 가 `save_as` 로 저장한 응답을 `--input` 으로 읽어 판정·전량 대조·가공만 한다.
공용 규약(자리표시자·실패 코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

모든 명령이 같은 순환을 돈다:

```
명령 실행 → error: "incomplete" + next_calls → itda-hyve 로 받기 → 같은 명령을 --input 을 붙여 다시 실행 → … → status: "ok"
```

- 회사명→코드, 연도 미지정→최신 보고서 찾기처럼 **앞 단 결과로 다음 요청이 정해지는 명령**(profile·finance·business·compare)은
  순환을 두세 번 돈다. 스크립트가 단계를 정한다 — 모델이 URL·날짜 창·쪽 번호를 계산하지 않는다.
- **incomplete 인 채로 결과를 말하지 않는다.** `status: "ok"` 가 나와야 끝이다.

API 키는 사용자가 itda-hyve GUI 시크릿 탭에 **`DART_API_KEY`** 로 등록해 둔 것을 이름으로만 가리킨다(값을 묻지 않고,
대화에 붙여 넣어도 쓰지 않는다). 발급: <https://opendart.fss.or.kr> 회원가입 → 오픈API → 인증키 신청/관리(40자리, 즉시 발급).

## 준비

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
printf "%s\n" "$c"' _ dart itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"

# 의존성 설치(defusedxml — XML 보안 파싱) — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"

# 연결 폴더 — itda-hyve save_dir(호스트 경로)와 같은 폴더가 샌드박스의 $HOME/mnt/<폴더 이름> 이다
WORK="$HOME/mnt/작업폴더"      # save_dir 가 /Users/me/Projects/작업폴더 일 때
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'dart'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
py -3 "$env:SKILL_DIR\scripts\collect_company.py" search --name "삼성전자" --input "C:\Users\me\Projects\작업폴더"
```

Claude Code CLI 처럼 같은 머신에서 도는 환경이면 `WORK` 는 `save_dir` 호스트 경로 그대로다.

## 1단계 — 명령을 실행한다

```bash
python3 "$SKILL_DIR/scripts/collect_company.py" profile --name "삼성전자" --year 2024 \
  --input "$WORK" --next-plan "$WORK/dart/plan-1.json"
```

- `--input` 에는 **연결 폴더**를 준다(파일을 하나씩 나열해도 된다). 스크립트는 그 폴더와 `dart/` 하위의 응답 파일을
  저장 이름으로 알아본다. 연결 폴더는 처음부터 있으니 첫 실행에도 그대로 준다(`dart/` 는 없어도 된다).
- `--next-plan` 은 더 받을 호출을 itda-hyve `batch` 의 `plan_file` 로 쓴다. **연결 폴더의 `dart/` 안**에 쓰고, 회차마다 이름을
  바꾼다(`plan-1.json`, `plan-2.json` …). 호출이 40개를 넘으면 `plan-1a.json`·`plan-1b.json` 처럼 나눠 쓰고 `plan_files` 로 알려 준다.
- 모자라면 stdout 이 이렇다(exit 1):

```json
{"status":"error","error":"incomplete","detail":"삼성전자(00126380) 기업개황·재무·직원현황을 받아야 합니다",
 "next_calls_count":3,"plan_files":[".../dart/plan-1.json"],"plan_file_args":["dart/plan-1.json"],
 "next_calls_preview":[{"id":"company-00126380-20260930","tool":"http_request","args":{…}}]}
```

  `--next-plan` 이 없으면 `next_calls` 에 호출 전부가 온다(`args` 가 `http_request` 인자 그대로).
  `plan_files` 는 스크립트가 본 경로(Cowork 면 샌드박스 경로)다 — batch 에는 `plan_file_args`(연결 폴더 기준 상대 경로)를 넘긴다.
  `--next-plan` 을 연결 폴더 밖에 주면 `plan_file_args` 가 없고 `warning` 이 온다 — 연결 폴더의 `dart/` 안으로 다시 준다.

## 2단계 — itda-hyve 로 받는다

### 한꺼번에: `batch` + `plan_file`

계획 파일을 옮겨 적지 않고 경로만 넘긴다. `plan_file` 에는 1단계 출력의 **`plan_file_args` 값을 그대로** 쓴다(`save_dir` 기준 상대 경로).

```json
{"save_dir": "/Users/me/Projects/작업폴더", "plan_file": "dart/plan-1.json"}
```

- `plan_file_args` 가 여럿이면(`dart/plan-1a.json`·`dart/plan-1b.json` …) 차례로 한 번씩 부른다(batch 는 40개를 넘으면 하나도 실행하지 않는다). 계획 파일의 `timeout_sec` 은 50 이다.
- 도구 목록에 `batch` 가 없거나 입력 스키마에 `plan_file` 이 없으면 옛 판이다 — `next_calls` 를 하나씩 `http_request` 로 부른다.

### 하나씩: `http_request`

`next_calls[i].args` 에 **`save_dir`(Cowork 연결 폴더의 호스트 경로)** 만 더해 그대로 보낸다. 예 — 재무제표:

```json
{"url": "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json",
 "params": {"crtfc_key": "{{secret:DART_API_KEY}}", "corp_code": "00126380", "bsns_year": "2024", "reprt_code": "11011"},
 "legacy_tls": true,
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/작업폴더",
 "save_as": "dart/fin-00126380-2024-11011.json"}
```

- `crtfc_key` 는 반드시 `params` 에 둔다. URL 쿼리에 자리표시자를 쓰면 `invalid_input` 으로 거부된다.
- `legacy_tls: true` 는 OpenDART 의 구형 핸드셰이크 때문에 필요하다(handshake failure 실측).
- **`save_as` 는 스크립트가 준 이름을 바꾸지 않는다.** 응답 본문에는 요청 인자가 없어 스크립트가 이름으로 어떤 질의의 응답인지 안다.
- `save_dir` 는 절대 경로(사용자 홈 아래 폴더 — 홈 자체·숨김 폴더·`AppData`·`~/Library` 제외, 클라우드 드라이브는 허용).
- ZIP(`corpcode-*.zip` 약 3.6MB, `doc-*.zip`)도 `save_as` 로 받는다 — 본문으로 받으면 1MB 에서 잘린다.
- 응답 요약의 `final_url`·헤더를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.

### 응답 판정 — HTTP 200 은 성공이 아니다

DART 는 오류를 HTTP 200 본문의 `status` 로 알린다(JSON `{"status":"013",…}`, ZIP 자리에는 `<result><status>010</status>…` XML,
키가 빠지면 오류 안내 HTML). 판정은 3단계 스크립트가 파일을 읽어 대신 한다.

## 3단계 — 같은 명령을 다시 실행한다

1단계 명령에 `--input "$WORK"` 를 붙여(이미 있으면 그대로) 다시 실행하고, `--next-plan` 이름은 다음 회차로 바꾼다.
`error: "incomplete"` 인 동안만 되풀이한다 — `status: "ok"` 가 나오면 끝이다.

- **다시 받으면 풀리는 오류는 스크립트가 알아서 다음 회차로 받게 한다** — 요청 한도(`020`)·시스템 점검(`800`)·정의되지 않은
  오류(`900`)·오류 안내 HTML·HTTP 5xx·본문 절단·깨진 ZIP·itda-hyve `timeout`·`network_error` 자리. 같은 질의를 `-r2`·`-r3`
  이름으로 받으라고 `incomplete` + `next_calls` 를 준다(오류 응답이 정본 이름에 남아도 막히지 않는다). 몇 초 기다렸다가 받는다.
  3회차도 같으면 `error: "api"`(또는 그 입력 오류)로 멈춘다 — `020` 이면 일 20,000건 한도일 수 있으니 내일 다시.
- **`incomplete` 가 아닌 오류에 `next_calls` 가 붙어 오면** 원인을 먼저 해결해야 한다는 뜻이다. 되풀이하지 말고 멈춘다.
  - `error: "api"` + `010`·`011`·`012`·`901`·`HTTP_403`(키·IP·권한) — 사용자에게 알리고, 사용자가 시크릿 탭 등을 고쳤다고 하면
    그 `next_calls` 로 받고 같은 명령을 다시 돌린다.
  - `error: "input"` + "저장 이름과 본문이 다릅니다"·"다른 질의의 쪽이 섞였습니다" — 다른 질의의 응답이 그 이름으로 저장됐다
    (호출 JSON 을 고쳐 쓰다 `corp_code`·기간을 놓친 경우). `save_as` 이름을 바꾸지 않았는지 확인하고, 그 `next_calls` 로 다시 받는다.
  - `next_calls` 가 없는 오류(`013` 데이터 없음·`100` 인자 오류 등)는 다시 받아도 같다.
- **쪽이 모자라거나 받는 사이 목록이 밀리면** — 빠진 쪽을 정확히 알려 주고, 건수가 맞지 않으면 전 쪽을 다음 회차 이름으로 다시 받게 한다.
  3회차에도 맞지 않으면 `error: "unstable"` 로 멈춘다 — **같은 명령을 되풀이하지 않는다.** `detail` 대로 기간을 좁히거나
  (받는 날을 포함하는 기간이면 끝 날짜를 어제로) 새 폴더에서 1쪽부터 받는다.
- 같은 폴더에 이미 받은 응답은 다시 받지 않는다. 날짜가 든 이름(`corpcode-<날짜>.zip`·`company-<코드>-<날짜>.json`)은
  **7일까지** 다시 쓰고, 그보다 오래되면 오늘 날짜 이름으로 새로 받게 한다. 그 파일이 오류 응답이면 오늘 날짜 이름으로 다시 받게 한다.

## 호출 수 — 받기 전에 알린다

| 명령 | 호출 | 수 |
|---|---|---|
| search | corpCode ZIP | 0~1 (7일 안에 받은 ZIP 이 있으면 0) |
| info | company.json | 1 |
| finance | (연도 없으면 공시 목록 1) → 주요계정 또는 `--detail` 전체 재무제표 | 1~2 |
| employees | empSttus.json | 1 |
| profile | corpCode ZIP → 기업개황·재무·직원현황 3개(batch 한 번) | 3~4 |
| disclosure | 공시 목록 쪽마다 1(쪽당 100건) | ⌈총건수 ÷ 100⌉, 상한 `--max-pages`(기본 10) |
| business | (접수번호 없으면 공시 목록 1) → document ZIP | 1~2 |
| compare | (이름이면 corpCode ZIP) → (연도 없으면 공시 목록 1) → 다중회사 주요계정 1(100개사까지) | 1~3 |
| raw | 그 엔드포인트 1 | 1 |

- 호출이 5개를 넘을 것 같으면(대개 disclosure) **첫 응답 뒤 남은 호출 수를 사용자에게 먼저 알린다.**
- disclosure 의 incomplete 에 `need_pages`(전체 쪽 수)·`will_truncate: true` 가 오면 상한 때문에 뒤쪽을 받지 않는다는 뜻이다.
  **받기 전에 사용자에게 묻는다** — 기간을 좁히거나 `--max-pages` 를 늘릴지. 결과의 `truncated: true` 도 그대로 알린다.

## itda-hyve 실패 코드

| 코드 | 대응 |
|---|---|
| `secret_missing` | GUI 시크릿 탭에 `DART_API_KEY` 등록을 안내하고 **멈춘다**. 값을 대화로 받지 않는다 |
| `secret_host_denied` | URL 호스트가 `opendart.fss.or.kr` 인지 먼저 확인. 같으면 사용자가 GUI 에서 허용 호스트를 추가해야 한다. 다른 주소로 우회하지 않는다 |
| `tls_error` | `legacy_tls: true` 가 빠졌는지 확인하고 넣어 다시 보낸다 |
| `invalid_input`(같은 이름 파일) | 앞 회차의 호출을 다시 보낸 것이다 — 3단계를 다시 돌려 새 `next_calls` 를 받는다(오류 응답이면 스크립트가 `-r<n>` 이름을 준다). `overwrite: true` 는 쓰지 않는다 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `save_as` 로 다시 받는다 |
| `timeout` | `timeout_sec` 을 늘려 1회만 다시 보낸다 |

batch 에서 `ok: false` 인 호출은 파일이 없으니 3단계가 같은 호출을 다시 달라고 한다. 원인이 위 코드면 먼저 해결한다.
실패 자리를 파일로 따로 적어 두지 않는다(그 이름에 적으면 다음 회차로 넘어가며 회차 하나를 쓴다).

## 명령

모든 명령은 `--input`(연결 폴더 또는 응답 파일들)·`--next-plan FILE`·`--format json|table|csv` 를 받는다(서브커맨드 앞·뒤 어디든).

```bash
C="$SKILL_DIR/scripts/collect_company.py"

python3 "$C" search --name "삼성전자" --input "$WORK"                         # 회사명 → 고유번호
python3 "$C" info --corp-code 00126380 --input "$WORK"                        # 기업개황
python3 "$C" finance --corp-code 00126380 --year 2024 --input "$WORK"         # 주요계정
python3 "$C" finance --corp-code 00126380 --year 2023 --detail --input "$WORK"   # 전체 재무제표
python3 "$C" finance --corp-code 00126380 --prefer latest --input "$WORK"     # 연도 없이 — 분기·반기 포함 최신
python3 "$C" employees --corp-code 00126380 --year 2024 --input "$WORK"       # 직원현황
python3 "$C" profile --name "카카오" --year 2023 --input "$WORK"               # 종합 프로필(권장)
python3 "$C" disclosure --corp-code 00126380 --bgn 20240101 --end 20241231 --type A --input "$WORK"
python3 "$C" business --corp-code 00126380 --section "사업의 내용" --input "$WORK"   # 최신 사업보고서 원문
python3 "$C" business --rcept-no 20250311001085 --max-chars 2000 --input "$WORK"
python3 "$C" --format table compare --names "삼성전자,LG전자,SK하이닉스" --year 2024 \
  --accounts "매출액,영업이익,자산총계" --with-ratios --input "$WORK"
python3 "$C" --format csv compare --corp-codes "00159023,00190321,00231363" --names "SKT,KT,LGU+" \
  --year 2024 --report q2 --unit eok --input "$WORK"                         # ok 가 된 뒤에만 > compare.csv
python3 "$C" raw --endpoint alotMatter --param corp_code=00126380 --param bsns_year=2023 \
  --param reprt_code=11011 --input "$WORK"                                    # 전용 명령이 없는 엔드포인트
```

(실제로는 각 줄에 `--next-plan "$WORK/dart/plan-<n>.json"` 을 붙여 1~3단계 순환으로 돌린다.)

**CSV 를 파일로 받을 때** — 받을 것이 남은 동안의 출력은 JSON(`incomplete`)이다. 순환을 JSON 으로 돌려 `status: "ok"` 를 본 뒤에
같은 명령에 `--format csv … > 파일.csv` 를 붙여 한 번 더 실행한다(처음부터 리다이렉트하면 `incomplete` JSON 이 CSV 파일에 들어간다).

- **finance·compare 자동 폴백** — `--year` 가 없으면 최근 1년 + 95일 정기공시에서 최신 보고서를 고르고 stderr 로 알린다
  (`--prefer annual`=사업보고서만, `latest`=분기·반기 포함). 고른 보고서의 연도와 보고서 코드(반기면 `11012`)를 함께 쓴다.
  `--report q1|q2|q3` 를 연도 없이 주면 **그 유형 가운데 최신**을 고른다(`--prefer` 보다 먼저).
- **compare** 는 다중회사 주요계정(`fnlttMultiAcnt`) 한 번으로 100개사까지 받는다(2026-09-30 실측: 한 회사의 행이 단일회사
  주요계정과 같다). 데이터가 없는 회사는 빈 칸 + `warnings`. 계정 매칭은 정확 일치 우선 + 부분 일치 fallback
  ("영업이익" → "영업이익(손실)"). JSON 에 기업별 `source.rcept_no` + 공시원문 URL 이 들어간다.
- **disclosure** 는 기간 전체를 쪽당 100건으로 받아 전량 대조한다(쪽 번호·총건수·중복·회사·접수일). `--single-page` 는 최근 100건만 훑는다.
  JSON·표 stdout 에는 최근 `--limit`(기본 20)건만 싣는다(`count` 는 받은 전량). 전량이 필요하면 `--out FILE` 로 파일에 쓴다.
  `--type`(pblntf_ty): A=정기공시, B=주요사항보고, C=발행공시, D=지분공시, E=기타공시, F=외부감사관련, G=펀드공시,
  H=자산유동화, I=거래소공시, J=공정위공시. `list.json` 은 회사명을 요청 인자로 받지 않는다 — 코드를 먼저 확보한다.
- **profile** 은 기업개황·재무·직원현황 가운데 일부가 오류면 그 부분에 오류를 담아 `ok` 로 끝내고 `warnings` 를 싣는다.
  키 오류처럼 고친 뒤 받을 수 있는 부분은 `retry_calls` 에 호출이 온다.
- **business** 는 document ZIP 에서 가장 큰 파일을 꺼내 UTF-8/EUC-KR 로 풀고 태그를 걷는다. `--section` 은 정규식.
- **raw** 는 `references/` 에 명세만 있는 80여 개 엔드포인트(배당·소송·전환사채·증자 등)용이다. JSON 원문만 준다 — 단위변환·CSV·
  출처링크는 없다(가공이 필요하면 finance/compare). `--endpoint` 는 영숫자만(경로·URL·쿼리 주입 차단), `crtfc_key` 는 자리표시자로
  자동으로 들어간다. status `013`·`014`(데이터 없음)는 빈 결과. 엔드포인트 이름·파라미터는 [references/dart.md](references/dart.md) 의 disambiguation 표.
  스크립트를 거치는 이유는 이름 규칙·status 판정·020 재요청을 다른 명령과 같게 하기 위해서다.
- **`--report`** `annual`(사업) / `q1` / `q2`(반기) / `q3` — finance·compare·employees·profile. 옛 `half` 는 친절한 오류로 거부한다.

## CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--input` | 연결 폴더(그 안과 `dart/` 하위를 본다) 또는 응답 파일들. 파일을 직접 주면 저장 이름 규칙을 지켜야 한다 | — |
| `--next-plan` | 더 받을 호출을 batch `plan_file` 로 쓴다(40개씩 나눔) | — |
| `--name` | 회사명 (search/profile) | — |
| `--corp-code` | DART 기업 코드 (8자리) | — |
| `--year` | 사업연도 (finance·compare 는 미지정 시 자동 폴백) | — |
| `--report` | `annual` / `q1` / `q2` / `q3` (연도 없이 주면 그 유형의 최신) | `annual` |
| `--prefer` | 폴백 범위: `annual`=사업보고서만, `latest`=분기·반기 포함 | `annual` |
| `--detail` | 전체 재무제표(fnlttSinglAcntAll). finance 전용 | OFF |
| `--fs-div` | `CFS`(연결)/`OFS`(개별). finance 전용 | `CFS` |
| `--bgn` / `--end` | 기간 YYYYMMDD (disclosure) | — |
| `--type` | 공시 유형 A~J (disclosure) | 전체 |
| `--max-pages` | 받을 쪽 상한, 쪽당 100건 (disclosure) | 10 |
| `--single-page` | 전량 대조 없이 1쪽만 (disclosure) | OFF |
| `--limit` | stdout(json·table)에 싣는 건수, 0=전부 (disclosure — CSV 는 늘 전량) | 20 |
| `--out` | 받은 전량을 JSON 파일로 (disclosure) | — |
| `--rcept-no` | 접수번호 14자리 (business) | — |
| `--section` | 섹션 정규식 (business) | 전체 |
| `--max-chars` | 최대 문자수, 0=무제한 (business) | 5000 |
| `--names` / `--corp-codes` | 회사명·코드 쉼표 구분 (compare, 병기 시 이름이 헤더) | — |
| `--accounts` | 계정명 쉼표 구분 (compare) | `매출액,영업이익,당기순이익,자산총계` |
| `--unit` | `auto`/`million`/`eok`/`jo` (compare) | `auto` |
| `--with-ratios` / `--with-prior` | 영업이익률·순이익률 / 전기 열(둘 다면 증감률) (compare) | OFF |
| `--endpoint` / `--param` | raw 전용 | — |
| `--format` | `json` / `table` / `csv` (raw 는 json 만) | `json` |

## 저장 이름 규칙 (스크립트가 짓는다)

| 이름 | 응답 |
|---|---|
| `dart/corpcode-<오늘>.zip` | 기업 고유번호 목록(corpCode.xml) |
| `dart/company-<코드>-<오늘>.json` | 기업개황 |
| `dart/list-<코드>-<시작>-<끝>-<유형|all>-p<쪽>.json` | 공시 목록 한 쪽 |
| `dart/fin-<코드>-<연도>-<보고서코드>.json` · `finall-…-<CFS|OFS>.json` | 주요계정 · 전체 재무제표 |
| `dart/emp-<코드>-<연도>-<보고서코드>.json` | 직원현황 |
| `dart/multi-<연도>-<보고서코드>-<해시>.json` | 다중회사 주요계정(해시 = 요청 회사 코드 목록) |
| `dart/doc-<접수번호>.zip` | 공시서류 원본 |
| `dart/raw-<엔드포인트>-<해시>.json` | raw(해시 = 파라미터) |

다시 받는 회차는 `-r2`·`-r3` 이 붙고, 스크립트는 회차가 가장 큰 파일을 쓴다. 날짜·쪽·해시는 한글이 없다.

## 출력 형식

- `--format json` (기본): 구조화된 JSON. 가공에 쓴 파일 이름이 `sources` 에 들어간다
- `--format table`: 사람이 읽기 쉬운 테이블
- `--format csv`: UTF-8 BOM CSV (엑셀 한글 호환, RFC 4180)

## 응답 규칙 (모델 표현)

- **요약 우선**: JSON 원문을 그대로 붙여넣지 말고 핵심만 요약한다.
  - `info`: 회사명·대표자·업종·주소·결산월 / `finance`·`compare`: 매출액·영업이익·당기순이익·자산총계·부채총계·자본총계 우선
  - `disclosure`: 최근 5~10건의 보고서명·접수일·제출인과 전체 건수(`count`) / `business`: 요청 섹션의 요지
- **원본 병기**: 금액을 억/조로 풀어 보여줄 때 원본 수치(원 단위)도 함께 남긴다.
- **비정상 status 안내**: `error: api` 면 `error_code` 의미를 사용자 언어로 안내한다(`013`=해당 기간/보고서에 데이터 없음,
  `020`=요청 한도 초과 → 잠시 후 다시).
- **출처 동봉**: `finance`·`compare` JSON 의 `source.url`(공시원문 링크)을 답변에 함께 제시한다.
- **면책 푸터**: 답변 말미에 한 줄 — `※ 금융감독원 DART 공시 데이터 기준이며 투자 조언이 아닙니다`.

### Done when (작업 완료 기준)

- 명령이 `status: "ok"` 로 끝났다(`incomplete` 로 멈춘 결과를 말하지 않았다).
- 회사명만 받았으면 `search`/`profile` 로 `corp_code` 를 먼저 확보했다.
- `truncated`·`warnings`·`retry_calls`(profile 일부가 키 오류 등으로 빠짐)가 있으면 사용자에게 알렸다.
- `source.url`(공시원문)을 동봉하고 면책 푸터를 남겼다.

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 더 받을 것이 있다(`incomplete`) · 가공 실패 — `error`: `api`(DART status) · `truncated`·`http`·`hyve`(입력이 잘림·HTTP 오류·itda-hyve 실패 자리 — 회차 상한까지 다시 받고도 같을 때) · `input`(파일 없음·이름 규칙 위반·형식 오류·이름과 본문 불일치) · `unstable`(공시 목록을 3회차까지 받아도 건수가 맞지 않음 — 되풀이하지 않는다) · `not_found`(profile 회사명). 원인을 고친 뒤 다시 받을 수 있으면 `next_calls` 가 붙는다 |
| 2 | 인자 오류 (`args`) |

### 정본 status 코드 (DART API)

| 코드 | 의미 | 권장 조치 |
|------|------|----------|
| 000 | 정상 | — |
| 010 | 등록되지 않은 키 | 시크릿 탭의 `DART_API_KEY` 값·활용신청 확인 → 고친 뒤 `next_calls` 로 다시 |
| 011 | 사용할 수 없는 키 (일시 중지) | 활용신청 URL 확인 |
| 012 | 접근할 수 없는 IP | DART 콘솔에서 IP 등록 |
| 013 | 조회된 데이터 없음 | 다른 연도·보고서로 |
| 014 | 파일이 존재하지 않습니다 | 접수번호 재확인 |
| 020 | 요청 제한 초과 (일 20,000건) | 스크립트가 다음 회차 이름으로 다시 받게 한다(최대 3회) |
| 021 | 조회 가능 회사 개수 초과 (최대 100건) | 스크립트가 100개사씩 나눈다 |
| 100 | 필드의 부적절한 값 | 인자 형식 확인 |
| 101 | 부적절한 접근 | 활용신청 URL 확인 |
| 800 | 시스템 점검으로 인한 서비스 중지 | 스크립트가 다음 회차로 다시 받게 한다(최대 3회) — 그래도 같으면 나중에 |
| 900 | 정의되지 않은 오류 | 스크립트가 다음 회차로 다시 받게 한다(최대 3회) — 그래도 같으면 문의 |
| 901 | 사용자 계정 개인정보 보유기간 만료 | 재가입 또는 갱신 |

권한 관련 오류(010/011/901)는 활용신청 URL(`https://opendart.fss.or.kr`)을 메시지에 붙인다. HTTP 403 게이트웨이 거부도 같다.

## 트리거 키워드

기업정보, 재무제표, 매출, 영업이익, 경쟁사 분석, DART, 전자공시,
직원수, 직원현황, 기업 비교, 상장사, 공시, 사업보고서, 회사 검색, 기업개황,
company info, financial statements, competitor analysis, DART

## 파일 구조

```
dart/
  SKILL.md
  CHANGELOG.md
  GUIDE.md
  requirements.txt
  scripts/
    dart_api.py         # 호출·저장 이름·응답 판독·전량 대조·가공 (네트워크 없음)
    collect_company.py  # 9개 명령 CLI (search/info/finance/disclosure/business/employees/profile/compare/raw)
  tests/
    test_dart_api.py · test_collect_company.py · test_collect_company_arg_position.py · test_response_compact_guard.py
    fixtures/           # 2026-09-30 itda-hyve 실측 응답(개인 제출인명 가림·일부 축소)
  references/
    netbridge.md        # itda-hyve 규약 (정본 shared/netbridge.md 사본)
    dart.md             # 요약 가이드
    공시정보/ 정기보고서-주요정보/ 정기보고서-재무정보/ 지분공시-종합정보/ 주요사항보고서-주요정보/ 증권신고서-주요정보/
```

itda-hyve 입력 판독(`hyve_input.py`)은 저장소 `shared/` 에 있고 배포 때 `scripts/` 로 들어간다.

## Troubleshooting

### 한글 경로가 인식되지 않을 때

Cowork sandbox 등 일부 환경의 bash 는 `LANG`/`LC_ALL` 미설정 시 한글 디렉토리명을 직접 인자로 받지 못한다
(증상: `/sessions/.../mnt/실습-클로드-1기/` 에서 `No such file or directory`). 변수로 캡처해 우회한다:

```bash
WORK=$(ls -d "$HOME"/mnt/*/ | grep -v 'lost+found' | head -1)
python3 "$SKILL_DIR/scripts/collect_company.py" search --name "삼성전자" --input "$WORK"
```

## 테스트 실행

```bash
python3 -m pytest itda-gov/skills/dart/tests -q     # Windows: py -3 -m pytest …
```

## 상세 API 가이드

`references/` 에 OpenDART 공식 가이드 6개 분류 · 83개 API 의 정본 명세를 보관한다.

| 분류 | API 수 | 위치 |
|------|--------|------|
| 공시정보 | 4 | [references/공시정보/](references/공시정보/) |
| 정기보고서 주요정보 | 28 | [references/정기보고서-주요정보/](references/정기보고서-주요정보/) |
| 정기보고서 재무정보 | 7 | [references/정기보고서-재무정보/](references/정기보고서-재무정보/) |
| 지분공시 종합정보 | 2 | [references/지분공시-종합정보/](references/지분공시-종합정보/) |
| 주요사항보고서 주요정보 | 36 | [references/주요사항보고서-주요정보/](references/주요사항보고서-주요정보/) |
| 증권신고서 주요정보 | 6 | [references/증권신고서-주요정보/](references/증권신고서-주요정보/) |

요약본: [references/dart.md](references/dart.md). 전용 명령이 없는 엔드포인트는 명세만 읽고 끝내지 말고 `raw` 로 받는다.
