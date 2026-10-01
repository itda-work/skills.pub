---
name: taxlaw
description: >
  국세법령정보시스템(taxlaw.nts.go.kr)에서 세법 법령·세법해석례(예규)·판례/결정례·상담사례를
  검색하고 전문(全文)을 조회하는 스킬입니다. "양도소득세 예규 찾아줘", "부가가치세 판례 검색해줘",
  "국세기본법 제18조 보여줘", "서면-2019-법령해석재산-1234 문서 찾아줘", "세법 해석사례 조사해줘",
  "국세청 상담사례 검색해줘"처럼 말하면 됩니다. API 키 없이 동작하며 요청은 itda-hyve 가 보냅니다.
  문서번호 검색·페이지네이션·정렬·전문 조회를 지원합니다.
  [책임 경계] 본 스킬은 국세법령정보시스템 세법 조회(법령·예규·판례) 전담 — 위하고·홈택스 등 세무 포털 자동화·장부 수집은 범위 밖(현재 지원 스킬 없음)이며, 세법 밖 일반 법령은 다루지 않습니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request)이 한다."
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, Write, mcp__workspace__bash"
user-invocable: true
argument-hint: "\"검색어\" [--domain law|interpretation|precedent|counsel|form|library|all] [--limit N] [--page N] [--sort accuracy|registered|produced] [--docno] [--format table|json|md]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  version: "0.2.0"
  created_at: "2026-09-01"
  updated_at: "2026-10-01"
  tags: "tax law, NTS, statute, tax ruling, precedent, tax tribunal, Korea tax"
---

# taxlaw

국세법령정보시스템(국세청, <https://taxlaw.nts.go.kr>)을 검색합니다.
세무 리서치에 필요한 4개 축 — **법령 조문 · 세법해석례(예규/질의회신) · 판례/결정례 · 국세상담센터 상담사례** — 를
한 번의 요청으로 훑고, 개별 문서의 **전문**(판결문·회신문·조문 본문)까지 가져옵니다. API 키가 필요 없습니다.

> ⚠️ 법제처 **국가법령정보센터(law.go.kr)와 다른 시스템**입니다. 이 스킬의 대상은
> 국세청 국세법령정보시스템(taxlaw.nts.go.kr)입니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 스크립트는 네트워크를
하지 않는다 — 부를 호출을 만들고(`plan`), itda-hyve 가 `save_as` 로 저장한 파일을 `--input` 으로 읽어 판독만 한다(`parse`).
공용 규약(실패 코드·저장 폴더·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
검색(호출 1회):         plan search "검색어" → http_request POST(save_as) → parse search "검색어" --input search-….json
해석례·판례·상담(1회):  plan detail --domain … --id … → http_request POST → parse detail … --input …
법령 전문(2회):         plan detail --domain law --id … → http_request POST ×2 → parse detail … --input law-… --input lawlist-…
```

**`plan` 이 준 `calls` 를 하나씩 그대로 `http_request` 인자로 보낸다.** URL·헤더·본문·`save_as` 를 고쳐 쓰거나 새로 짓지 않는다 —
본문은 사이트 JS 가 보내는 XHR 본문과 글자까지 같고(2026-10-01 브라우저 캡처로 고정), 헤더는 사이트 JS 가 싣는 셋
(`Content-Type`·`Accept`·`X-Requested-With`)에 그 XHR 을 보내는 화면 주소로 고른 Referer 를 더한 것이다. `save_as` 이름은 `parse` 가 인자와
대조하는 식별 계약이다. 본문을 **옮겨 적다 한 글자라도 바뀌면** 응답이 되비친 요청 값이 계획과 달라 `parse` 가 `mismatch` 로 멈춘다. `User-Agent`·`Cookie` 헤더를 더하지 않는다(쿠키·세션 없이 성립 — 실측). POST 라 `batch` 로는 못 보낸다.
**`plan` 과 `parse` 에는 같은 인자를 준다** — 다르면 `parse` 가 "다른 호출의 응답" 으로 멈춘다.

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
printf "%s\n" "$c"' _ taxlaw itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'taxlaw'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

표준 라이브러리만 쓰므로 추가 설치가 없다(Python 3.10+).

`--save-dir` 에는 **Cowork 연결 폴더의 호스트 경로**(절대 경로 — `/Users/…` 또는 Windows 호스트면 `C:\Users\…`, 사용자 홈 아래 —
홈 자체·숨김 폴더·`AppData`·`~/Library` 제외)를 넣는다. 그러면 `plan` 이 낸 호출에 `save_dir` 가 들어 있어 그대로 보내면 된다.
생략하면 itda-hyve 기본 저장 폴더다. 저장본은 연결 폴더 안 `taxlaw/` 에 쌓인다. 연결 폴더가 없으면 연결을 요청한다.

## Step 2: 검색 — 호출 1회

| 옵션 | 의미 |
|---|---|
| `--domain` | `law`(법령) `interpretation`(세법해석례) `precedent`(판례·결정례) `counsel`(상담사례) `form`(별표·서식) `library`(전자도서관) — 쉼표로 복수, `all`=전부, 기본 `core`=핵심 4개 |
| `--limit N` / `--page N` | 도메인당 건수(기본 10, 최대 100) / 페이지(1-base). **검색엔진은 5,000번째 결과까지만 준다** — `page × limit` 이 5,000 을 넘으면 `plan` 이 받기 전에 `args` 로 막는다 |
| `--sort` | `accuracy`(정확도, 기본) · `registered`(등록일) · `produced`(생산일) |
| `--docno` | **문서번호 검색** — `"부가가치세과-1196"`, `"서면-2014-부가-22035"`, `"서울고등법원-2025-누-7641"` 등 |
| `--include 단어` / `--exclude 단어` | 결과 내 포함어/제외어 (반복 지정 가능) |
| `--synonym` | 동의어 확장 |
| `--format` | `parse` 만 — `table`(기본) · `json`(compact) · `md` |

```bash
python3 "$SKILL_DIR/scripts/search_taxlaw.py" plan search "가상자산 양도소득" --save-dir "/Users/me/Projects/세무조사"
```

출력 `calls[0]` 을 그대로 보낸다(위 명령의 2026-10-01 출력):

```json
{"url": "https://taxlaw.nts.go.kr/action.do",
 "method": "POST",
 "headers": {"Content-Type": "application/x-www-form-urlencoded",
             "Accept": "application/json, text/javascript, */*; q=0.01",
             "X-Requested-With": "XMLHttpRequest",
             "Referer": "https://taxlaw.nts.go.kr/is/USEISA001M.do"},
 "body": "actionId=ASEISA001MR01&paramData=%7B%22schVcb%22%3A%22%EA%B0%80%EC%83%81%EC%9E%90%EC%82%B0+%EC%96%91%EB%8F%84%EC%86%8C%EB%93%9D%22%2C%22startCount%22%3A1%2C%22collection%22%3A%22statute%2Cquestion%2Cprecedent%2ChometaxCnslThan%22%2C%22wnKey%22%3A%22%22%2C%22searchType%22%3A%22%22%2C%22sortField%22%3A%22SCORE%2FDESC%22%2C%22ntstTlawClCdList%22%3A%5B%5D%2C%22icldVcbCtl%22%3A%5B%5D%2C%22exclVcbCtl%22%3A%5B%5D%2C%22rltnStttCtl%22%3A%5B%5D%2C%22schDtBase%22%3A%22DCM_RGT_DTM%22%2C%22viewCount%22%3A%2210%22%2C%22prtsSprcChiefJdgmYn%22%3A%22%22%2C%22prtsAttrYrCtl%22%3A%5B%5D%2C%22prtsPrgrStatCtl%22%3A%5B%5D%2C%22mainIdCtl%22%3A%5B%5D%2C%22useSynonymYn%22%3A%22N%22%7D",
 "retry_unsafe": true,
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/세무조사",
 "save_as": "taxlaw/search-3e0813d0f52a-20261001.json"}
```

`retry_unsafe` 는 이 POST 가 조회 전용이라 다시 보내도 안전하기 때문이다. 받은 뒤 **같은 인자로** 판독한다:

```bash
# Cowork: 연결 폴더는 샌드박스의 $HOME/mnt/<폴더 이름> — save_dir 의 폴더 이름 뒤에 saved_path 를 붙인다
python3 "$SKILL_DIR/scripts/search_taxlaw.py" parse search "가상자산 양도소득" \
    --input "$HOME/mnt/세무조사/taxlaw/search-3e0813d0f52a-20261001.json"

# Windows
py -3 "$env:SKILL_DIR\scripts\search_taxlaw.py" parse search "가상자산 양도소득" --input "…\taxlaw\search-3e0813d0f52a-20261001.json"
```

Claude Code CLI 처럼 같은 머신이면 `save_dir`/`saved_path` 를 이어 붙인 절대 경로를 쓴다. 파일을 `find` 로 뒤지지 않는다.
다음 쪽은 `--page 2` 로 `plan`→`parse` 를 다시 돈다(이름이 달라 앞 파일과 겹치지 않는다). 분모가 수천 건이면 쪽을 넘기지 말고
검색어를 좁히거나 포함어·제외어·문서번호 검색을 쓰자고 사용자에게 먼저 권한다 — 5,000번째 뒤는 어떤 쪽으로도 받을 수 없다
(2026-10-01 실측: "세법" 해석례 전체 42,410건, 4,001번째는 오고 5,001번째부터 0건).

`parse` 가 보는 것 — 어긋나면 실패로 끝낸다(부분 결과를 말하지 않는다):

- 저장 이름의 지문이 이 인자로 만든 요청 본문과 같은가
- **응답이 되비친 요청 값**(검색어 `schVcb`·컬렉션·시작 번호·건수·정렬·검색 종류·포함어·제외어)이 이 인자의 요청과 같은가 — 다르면
  보낸 본문이 `plan` 출력과 달랐던 것이다(`mismatch`). 되비침이 없으면 대조 없이 통과하지 않는다(`site`). 동의어 확장(`useSynonymYn`)은
  되비치지 않아 이름 지문만 본다
- **도메인마다 받은 건수가 분모와 맞는가** — 기대 건수 = `min(limit, 전체 건수 − 시작 번호 + 1)`. `resultCount`·받은 목록 길이가
  다르면 `incomplete`. 마지막 쪽 너머면 0건이 정상이고 `warnings` 가 알린다. 분모 안인데 0건이면 검색엔진이 그 깊이를 주지 않는 것이다
  (`incomplete` + "다시 받아도 같습니다" — 다시 받지 않는다)
- 요청하지 않은 컬렉션이 섞였으면 `mismatch`. 요청한 도메인이 응답에 없으면 0건이 아니라 `missing` 블록 + `warnings`
- 응답이 JSON 이고 `status=SUCCESS`·`data.ASEISA001MR01` 이 있는가

## Step 3: 전문 조회

검색 결과의 `id` 를 그대로 넘긴다. 해석례·판례·상담사례는 호출 1회, **법령은 2회**(조문 전문 + 법령 목록 — 법령명을 얻는다).

```bash
python3 "$SKILL_DIR/scripts/search_taxlaw.py" plan detail --domain precedent --id 200000000000009799 --save-dir "/Users/me/Projects/세무조사"
```

```json
{"url": "https://taxlaw.nts.go.kr/action.do",
 "method": "POST",
 "headers": {"Content-Type": "application/x-www-form-urlencoded",
             "Accept": "application/json, text/javascript, */*; q=0.01",
             "X-Requested-With": "XMLHttpRequest",
             "Referer": "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000009799&wnKey="},
 "body": "actionId=ASIQTB002PR01&paramData=%7B%22dcmDVO%22%3A%7B%22ntstDcmId%22%3A%22200000000000009799%22%2C%22wnKey%22%3A%22%22%7D%7D",
 "retry_unsafe": true,
 "timeout_sec": 50,
 "save_dir": "/Users/me/Projects/세무조사",
 "save_as": "taxlaw/precedent-b7dd89f5496e-20261001.json"}
```

```bash
python3 "$SKILL_DIR/scripts/search_taxlaw.py" parse detail --domain precedent --id 200000000000009799 \
    --input "$HOME/mnt/세무조사/taxlaw/precedent-b7dd89f5496e-20261001.json"
```

- 세법해석례: `--domain interpretation`(Referer 가 `/qt/USEQTA002P.do?…`), 상담사례: `--domain counsel --id 1387`
  (Referer `/is/USEISA004P.do?reqStdId=…`) — 어느 쪽이든 `plan` 이 정한다.
- **법령**: `plan detail --domain law --id "<id>"` 가 호출 **2개**(`law-…`·`lawlist-…`)를 낸다. 둘 다 보낸 뒤
  `parse detail --domain law --id "<id>" --input <law-….json> --input <lawlist-….json> [--article 제18조]`(이 순서).
  법령 목록은 그 체계(법률·시행령 …)의 목록 전체라 클 수 있다(세법구분 `ZZZ` — 국세법 밖 일반 법령 — 의 시행령 목록이 약 4MB 였다,
  세법 `01/101` 은 28KB. `save_as` 로만 받는다).
  법령 id 는 다섯 칸(`<기본ID>:<내역ID>:<공포번호>:<체계구분>:<세법구분>`)이다 — 0.1.x 의 세 칸 id 는 검색을 다시 하면 새 id 가 나온다.
- `parse` 는 응답이 **그 문서의 것인지**(문서 id·법령 내역 id·체계구분)를 대조한다. 다르면 `mismatch`.
- `--format json` 을 주면 구조화 JSON(제목·문서번호·요지·회신·전문·관련법령), 기본은 사람이 읽는 텍스트.

## 호출 수·응답 요약·재시도

- 호출 수를 먼저 알린다: 검색 1회(쪽마다 1회), 해석례·판례·상담 문서마다 1회, 법령 전문 2회.
  여러 문서를 전문으로 읽을 때는 몇 건을 읽을지 먼저 사용자와 정한다(대량 수집 용도가 아니다).
- **응답 요약의 `final_url`·헤더(`Set-Cookie` 포함)를 대화에 옮겨 적지 않는다. 필요한 것은 `status`·`saved_path` 뿐이다.**
- **응답 `status` 가 200 이 아니면 그 파일을 스크립트에 넘기지 않는다** — itda-hyve 는 오류 상태의 본문도 저장한다. 상태 코드를 사용자에게 알리고 멈춘다.
- 같은 이름이 이미 있어 `invalid_input` 이면 **오늘 같은 호출로 이미 받은 파일**이다(이름에 요청 지문과 받은 날이 있다) — 그 파일로 `parse` 한다.
  다만 스크립트가 거부한 파일(`truncated`·`site`·`mismatch`·`incomplete`)은 다시 쓰지 않는다 — `--save-dir` 를 새 하위 폴더로 바꿔 `plan` 부터.
  새 폴더에서도 같은 오류면 멈추고 알린다. 덮어써도 된다고 사용자가 확인했을 때만 `overwrite: true`.
- 호출이 itda-hyve 실패로 끝났으면 그 `save_as` 자리에 `{"error":{"code":"<코드>","message":"<메시지>"}}` 를 써서 `parse` 에 넘기면
  `hyve` 로 판정된다(파일이 이미 있어 거부된 호출에는 쓰지 않는다). Cowork 에서 쓰는 곳은 샌드박스 경로
  `$HOME/mnt/<연결 폴더 이름>/<save_as>` 다(`save_dir` 호스트 경로가 아니다).

| itda-hyve 실패 | 대응 |
|---|---|
| `timeout` | 1회만 다시 보낸다. itda-hyve 는 끊긴 뒤에도 돌아 파일을 나중에 쓸 수 있다 — 다시 보낸 것이 "같은 이름" 으로 거부되면 그 파일이 생긴 것이니 그대로 쓴다 |
| `network_error` | URL 이 `plan` 출력 그대로인지 확인. 반복되면 사이트 상태 확인을 요청하고 멈춘다 |
| `tls_error` | `handshake failure` 면 `legacy_tls: true` 로 1회. 그 밖은 사용자에게 알리고 멈춘다 |
| `invalid_input` | 같은 이름 파일이 있다(위) 또는 `save_dir` 가 규칙 밖 — 메시지·`hint` 대로 고친다 |
| `body_truncated: true` | `save_as` 없이 받은 것이다 — `plan` 출력 그대로(`save_as` 포함) 다시 받는다 |

## Step 4: 표시와 결과 활용 (Claude 실행 규칙)

- 조사 보고에는 **문서번호·생산일자·원문 URL 을 반드시 함께 인용**한다 — 세무 판단의 근거는 문서 식별자가 전부다.
- 도메인별 `총 N건` 분모를 사용자에게 전달한다. limit 만큼만 표시했음을 밝히고, 더 필요하면 `--page` 로 이어간다.
- **`warnings` 가 비지 않았으면 전부 그대로 사용자에게 전한다.**
- 법령 검색 결과는 **특정 시행일자 기준 조문**이다(`시행 YYYY.MM.DD` 표기 확인). 개정 연혁 비교가 필요하면 원문 URL 로 안내한다.
- 사이트 안내문 그대로: 검색 결과는 참고자료이며 개별 사안에는 전문가 확인이 필요함을 세무 판단 성격의 답변에 덧붙인다.

## 오류 처리

실패하면 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 를 쓰고 exit 1(인자 오류 `args` 는 exit 2). `detail` 을 그대로 전달한다.

| `error` | 뜻 | 대응 |
|---|---|---|
| `args` | 알 수 없는 도메인·정렬, limit 범위(1~100), 5,000번째 뒤의 쪽, 빈 검색어, 법령 id 형식, `--input` 개수, `--article` 을 law 밖에 줌, `--save-dir` 가 절대 경로 아님 | 인자를 고친다 |
| `input` | 파일 없음·저장 이름이 계약과 다름·**다른 인자의 호출 응답**(지문 불일치)·법령 `--input` 순서 바뀜 | `plan` 이 준 `save_as` 그대로 저장했는지, 두 단계에 같은 인자를 줬는지 확인 |
| `incomplete` | 도메인의 받은 건수가 분모로 계산한 기대 건수와 다름 | 결과를 말하지 않는다. `detail` 에 "다시 받아도 같습니다" 가 있으면 검색엔진의 깊이 한계다 — 다시 받지 말고 검색어를 좁히자고 권한다. 그 밖에는 새 하위 폴더로 `plan` 부터 한 번, 되풀이되면 알린다 |
| `mismatch` | 응답이 되비친 요청 값이 계획과 다름(보낸 본문이 `plan` 출력과 다름), 요청하지 않은 컬렉션, 다른 문서·다른 법령 버전·다른 체계의 응답 | 넘긴 파일이 맞는지 본다. 맞으면 `plan` 출력을 **고치지 않고 그대로** 보냈는지 확인하고 새 하위 폴더로 `plan` 부터 |
| `not_found` | 문서·상담사례·조문이 없음(사이트는 SUCCESS 인 채 빈 값을 준다), `--article` 조문 없음 | id·조문 표시를 확인한다. 세법해석례 `정비`(실효) 문서는 비어 있을 수 있다 |
| `site` | JSON 이 아님(오류·점검 화면), `status` 가 SUCCESS 아님, 응답 키·형식이 계약과 다름 | 사이트 내부 API 계약이 바뀐 신호일 수 있다. `references/taxlaw-api.md` 의 재실측 절차를 따른다(조용한 우회 금지) |
| `truncated` | 본문 JSON 이 끝까지 오지 않음(또는 응답 JSON 전체를 옮겨 적은 파일의 `body_truncated`) | 새 하위 폴더로 `plan` 부터 |
| `hyve`·`http` | itda-hyve 실패 자리 파일(`hyve_code` 동봉), 응답 JSON 전체를 옮겨 적은 파일의 HTTP 오류 | 위 실패 표대로 |

## 한계

- 별표·서식(`form`)·전자도서관(`library`)은 검색·메타데이터까지 지원(첨부 파일 다운로드 비지원).
- 법령 전문 조회는 종류가 **법령**(국세법령 조문)인 결과만 지원한다. 기본통칙·세법집행기준·훈령·고시·조세조약은
  검색 결과에 `id` 없이 원문 URL 만 붙는다 — 그 URL 로 안내한다.
- 비공개 내부 API 다 — 무예고로 바뀔 수 있다. 계약 근거·재실측 절차·robots 판단은 [references/taxlaw-api.md](references/taxlaw-api.md).
- 대량 수집 용도가 아니다 — 조사·리서치 목적의 조회에만 사용한다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 위하고·홈택스 로그인·장부·분개장 수집 | 세무 포털 자동화는 현재 지원 스킬 없음 |
| 세법 밖 일반 법령·판례 | 미지원(국세법령정보시스템 범위 밖) |
| 대량 수집·크롤링 | 미지원 — 조사 목적 조회만 |
| 답변 근거의 출처 검증 | itda-research:ground-check |

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 병렬 처리

서로 다른 검색어·도메인 조사는 독립이다. 여러 주제를 동시에 조사할 때는 한 메시지에 복수
Agent 호출로 팬아웃하고, 산출은 파일로 회수한다. 같은 주제의 검색→전문 조회는 순차 유지.
