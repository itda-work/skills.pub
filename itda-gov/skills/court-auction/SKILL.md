---
name: court-auction
description: >
  대법원 법원경매정보(courtauction.go.kr)의 부동산 매각공고·사건·물건을 조회하는 스킬입니다.
  "오늘 서울중앙지법 경매 공고 보여줘", "2024타경100001 사건 진행상황 알려줘",
  "강남 아파트 5억 이하 유찰 1회 물건 찾아줘"처럼 말하면 됩니다. API 키 없이 동작하며 요청은 itda-hyve 가 보냅니다.
  읽기 전용·참고용이며, 입찰 전 반드시 법원 원문을 재확인하세요.
  [책임 경계] 본 스킬은 법원경매 매각공고·사건·물건 조회 전담 — itda-gov:realty-deals 는 아파트 실거래가, itda-gov:realty-price-stats 는 가격 지수.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 네트워크는 itda-hyve 0.10.4 이상(로컬 MCP 서버 — http_request)이 한다."
user-invocable: true
allowed-tools: "mcp__remote-devices__itda-hyve__http_request, Bash, Read, AskUserQuestion, mcp__workspace__bash"
argument-hint: "서울중앙지법 오늘 경매 / 2024타경100001 사건 / 강남 아파트 5억 이하 경매"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.2.0"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-10-01"
  tags: "court-auction, auction, realestate, courtauction, property, real-estate-auction, foreclosure, court, keyless"
---

# court-auction

대법원 **법원경매정보**(`courtauction.go.kr`)의 부동산 매각공고·사건·물건을 조회해 JSON 으로 돌려줍니다.
itda-gov 의 부동산 시장 데이터(실거래·전세·공급·가격)와 달리 **경매 매물**을 다룹니다. 사용자용 가이드는 GUIDE.md 참조.

## ⚠️ 시작 전 반드시 확인 (디스클레이머)

- 공식 OPEN API 가 없어 **사이트 화면이 부르는 내부 검색(WebSquare JSON POST)** 을 같은 모양으로 부릅니다.
  사이트가 바뀌면 **언제든 동작이 멈출 수 있습니다**.
- 사이트는 **IP 단위 자동화 차단이 공격적**입니다(≈16회/30초면 약 1시간 차단). 이 스킬은 회차당 호출 10회 상한,
  호출 사이 2초, 차단 즉시 중단으로 보수적으로 동작합니다. **차단되면 같은 IP 로 약 1시간 뒤에야 복구**됩니다.
- **읽기 전용·참고용**입니다. 공고 시점 기준이며 정정·취하·연기로 바뀔 수 있으니 **입찰 전 법원 원문 매각공고를 재확인**하세요.
- **입찰서 작성·제출·결제는 하지 않으며**(입찰은 법원에서 사람이 직접), 매크로(자동 반복 조회·폴링)도 하지 않습니다.

## 흐름 — 요청은 itda-hyve, 가공은 스크립트

네트워크는 **itda-hyve 의 `http_request`**(`mcp__remote-devices__itda-hyve__http_request`)로만 나간다. 스크립트는 네트워크를
하지 않는다 — 부를 호출을 만들고(`plan`), itda-hyve 가 `save_as` 로 저장한 파일을 읽어 판정·정규화만 한다(`collect`).
공용 규약(저장 폴더·실패 코드)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan <종류> … → http_request(출력 calls[0] 그대로, 하나씩) → collect --input "$R/<save_as>"
```

- **`plan` 이 준 호출을 그대로 `http_request` 인자로 보낸다.** URL·헤더·본문·`save_as` 를 고쳐 쓰거나 새로 짓지 않는다 —
  본문과 화면이 넣는 헤더는 2026-10-01 aside 로 뜬 화면 요청과 바이트 동일하다(공고 목록·펼치기, 사건, 법원 목록, 물건검색의
  법원 분기와 소재지 분기 — 테스트 골든). `Origin`·`Referer` 는 브라우저가 붙이는 값이라 캡처가 아니라 그 요청을 뜬 **화면 주소로
  재현**한다. `User-Agent`·`Cookie` 를 더하지 않는다(쿠키·세션 없이 성립 — 2026-10-01 itda-hyve 실측).
- 사이트 요청은 전부 **POST** 라 batch 로 묶을 수 없다(batch 는 GET 만 받는다). 한 번에 하나씩 부른다.
- **응답 요약의 `final_url`·헤더(`Set-Cookie` 포함)를 대화에 옮겨 적지 않는다.** 필요한 것은 `status`·`saved_path` 뿐이다.

## Step 1: 스킬 디렉토리와 회차 폴더

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
printf "%s\n" "$c"' _ court-auction itda-gov "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'court-auction'; $P = 'itda-gov'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

Windows 는 아래 명령의 `python3` → `py -3`, 경로 `"$SKILL_DIR/…"` → `"$env:SKILL_DIR\…"`. 표준 라이브러리만 쓴다(추가 설치 없음).

**회차 폴더** — 한 대화의 조회는 폴더 하나에 모은다. 작업 폴더 아래 `court-auction-runs/<YYYYMMDD-HHMM>/` 를 새로 쓰고,
어디에 받는지 사용자에게 한 줄로 알린다. 같은 폴더를 두 경로로 부른다:

- `S` — itda-hyve 가 쓸 **호스트 절대 경로**(`--save-dir`, 호출의 `save_dir`). 사용자 홈 아래, 숨김 폴더·`AppData`·`~/Library` 제외.
- `R` — 스크립트가 보는 같은 폴더(`--run-dir`). Claude Code 는 `S` 와 같다. Cowork 는 연결 폴더가 `$HOME/mnt/<폴더 이름>` 이다.

```bash
# Claude Code — 같은 머신
S="/Users/me/Documents/court-auction-runs/20261001-1400"; R="$S"
# Cowork — 연결 폴더 호스트 경로가 /Users/me/Documents 일 때
S="/Users/me/Documents/court-auction-runs/20261001-1400"; R="$HOME/mnt/Documents/court-auction-runs/20261001-1400"
# 호스트가 Windows 면 S 는 그 PC 의 경로 그대로 — 예: S='C:\Users\me\Documents\court-auction-runs\20261001-1400'
```

Cowork 에 연결 폴더가 없으면 폴더 연결을 요청하고 멈춘다. 같은 대화의 다음 조회는 **같은 회차 폴더**를 계속 쓴다 —
호출 상한을 회차 폴더에 세고, 이미 받은 파일은 다시 부르지 않는다.

## Step 2: 호출 예산 — 먼저 알린다

- 조회 하나 = 호출 1회. **회차당 10회**가 상한이다(`--max-calls` 로 첫 `plan` 에서만 1~15 — 이후 `plan` 에 다른 값을 주면 `args` 로
  거부한다). `plan` 출력의 `calls_remaining` 을
  사용자에게 알려 추가 조회를 판단하게 한다. 상한에 닿으면 `plan` 이 `budget` 으로 거부한다.
- 여러 번 부를 조회(공고 목록 → 펼치기 → 사건 셋)는 **호출 수를 먼저 말하고** 시작한다.
- 호출 사이를 **2초 이상** 둔다(`sleep 2`). 연속 조회 루프·폴링을 만들지 않는다.
- 같은 호출을 다시 계획해도 한 번으로 센다 — 받지 못한 호출을 끝없이 다시 계획하지 않게 하는 장치다.

## Step 3: 종류별 호출

아래 예시 JSON 은 `S="/Users/me/Documents/court-auction-runs/20261001-1400"` 로 2026-10-01 에 낸 `plan` 출력의 `calls[0]` 이다.

### 법원 코드 — `plan courts`

`notices`(선택)·`case`(필수)·`search`(선택)는 법원사무소코드(예: 서울중앙지방법원 `B000210`)를 쓴다. 모르면 이것으로 찾는다.

```bash
python3 "$SKILL_DIR/scripts/main.py" plan courts --run-dir "$R" --save-dir "$S"
```

```json
{"url": "https://www.courtauction.go.kr/pgj/pgj002/selectCortOfcLst.on", "method": "POST",
 "headers": {"Accept": "application/json", "Content-Type": "application/json", "Origin": "https://www.courtauction.go.kr",
             "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"},
 "body": "{\"cortExecrOfcDvsCd\":\"00079B\"}",
 "follow_redirects": false, "timeout_sec": 50,
 "save_dir": "/Users/me/Documents/court-auction-runs/20261001-1400", "save_as": "court-auction/courts.json"}
```

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R" --input "$R/court-auction/courts.json"
```

입찰구분·용도·지역 코드표는 호출 없이 `python3 "$SKILL_DIR/scripts/main.py" codes bid-types|usages|regions`.

### 매각공고 목록 — `plan notices`

사이트는 **월 단위**로만 준다. `--date YYYY-MM-DD` 면 그 달을 받아 그날만 남긴다. 사이트 안내상 기일입찰은 오늘부터
**14일 뒤 매각기일까지**만 조회된다.

```bash
python3 "$SKILL_DIR/scripts/main.py" plan notices --run-dir "$R" --save-dir "$S" --date 2026-10 --court-code B000210 --bid-type date
```

```json
{"url": "https://www.courtauction.go.kr/pgj/pgj143/selectRletDspslPbanc.on", "method": "POST",
 "headers": {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json",
             "submissionid": "mf_wfm_mainFrame_sbm_selectRletDspslPbanc", "SC-Userid": "SYSTEM",
             "Origin": "https://www.courtauction.go.kr",
             "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ141M00.xml&pgjId=143M01"},
 "body": "{\"dma_srchDspslPbanc\":{\"srchYmd\":\"202610\",\"cortOfcCd\":\"B000210\",\"bidDvsCd\":\"000331\",\"srchBtnYn\":\"Y\"}}",
 "follow_redirects": false, "timeout_sec": 50,
 "save_dir": "/Users/me/Documents/court-auction-runs/20261001-1400", "save_as": "court-auction/notices-202610-B000210-000331.json"}
```

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R" --input "$R/court-auction/notices-202610-B000210-000331.json"
```

사이트가 공고 총계를 주지 않아 전량 대조를 하지 않는다 — `warnings` 에 그 사실이 실린다(그대로 전한다).

### 공고 펼치기 — `plan notice-detail`

**같은 회차에서 받은 목록**의 `items[].noticeId` 를 넘긴다. 스크립트가 저장된 목록에서 그 행을 읽어 화면과 같은 본문을 만든다 —
행 값(담당계 코드·전화·법정·시각)을 옮겨 적지 않는다. 목록이 없으면 `input` 으로 거부한다.

```bash
python3 "$SKILL_DIR/scripts/main.py" plan notice-detail --run-dir "$R" --save-dir "$S" --notice-id B000210_1002_20261015
```

```json
{"url": "https://www.courtauction.go.kr/pgj/pgj143/selectRletDspslPbancDtl.on", "method": "POST",
 "headers": {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json",
             "submissionid": "mf_wfm_mainFrame_sbm_rletDspslPbancDtlInfo", "SC-Userid": "SYSTEM",
             "Origin": "https://www.courtauction.go.kr",
             "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ141M00.xml&pgjId=143M01"},
 "body": "{\"dma_srchGnrlPbanc\":{\"cortOfcCd\":\"B000210\",\"dspslDxdyYmd\":\"20261015\",\"bidBgngYmd\":\"\",\"bidEndYmd\":\"\",\"jdbnCd\":\"1002\",\"cortAuctnJdbnNm\":\"\",\"jdbnTelno\":\"530-1814(제4별관 민사집행과)\",\"dspslPlcNm\":\"경매법정(제4별관211호)\",\"fstDspslHm\":\"1000\",\"scndDspslHm\":\"\",\"thrdDspslHm\":\"\",\"fothDspslHm\":\"\",\"bidDvsCd\":\"000331\"}}",
 "follow_redirects": false, "timeout_sec": 50,
 "save_dir": "/Users/me/Documents/court-auction-runs/20261001-1400", "save_as": "court-auction/detail-B000210-20261015-1002-000331.json"}
```

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R" --input "$R/court-auction/detail-B000210-20261015-1002-000331.json"
```

응답의 사건 수(`caseCount`)와 받은 행의 서로 다른 사건 수(`receivedCaseCount`)를 대조한다 — 다르면 `incomplete`(결과를 내지 않는다).

### 사건 — `plan case`

`2024타경100001` 권장(`2024-100001` 도 정규화).

```bash
python3 "$SKILL_DIR/scripts/main.py" plan case --run-dir "$R" --save-dir "$S" --court-code B000210 --case-number 2026타경100664
```

```json
{"url": "https://www.courtauction.go.kr/pgj/pgj15A/selectAuctnCsSrchRslt.on", "method": "POST",
 "headers": {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json",
             "submissionid": "mf_wfm_mainFrame_sbm_selectCsDtlInf", "SC-Pgmid": "PGJ15AF01", "SC-Userid": "NONUSER",
             "Origin": "https://www.courtauction.go.kr",
             "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"},
 "body": "{\"dma_srchCsDtlInf\":{\"cortOfcCd\":\"B000210\",\"csNo\":\"2026타경100664\"}}",
 "follow_redirects": false, "timeout_sec": 50,
 "save_dir": "/Users/me/Documents/court-auction-runs/20261001-1400", "save_as": "court-auction/case-B000210-2026-100664.json"}
```

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R" --input "$R/court-auction/case-B000210-2026-100664.json"
```

없는 사건번호는 사이트가 status 204 로 답하고 결과는 `found: false` 다. 없다고 단정하지 말고 사건번호·법원을 다시 확인한다.

### 물건 자유검색 — `plan search`

한 번에 **한 쪽**이다(`--page`, `--page-size` 10/20/50/100). 결과의 `page.totalCount`·`pageCount`·`hasMore` 를 보고, 더 보려면
다음 쪽을 새로 계획한다(쪽마다 호출 1회 — 예산 안에서, 먼저 묻는다).

화면처럼 **둘 중 하나로** 고른다 — 법원(`--court-code`, 담당계) 또는 소재지(`--sido` → `--sigungu` → `--dong`). 둘을 함께 주면 `args`.

- **용도**는 이름이나 코드로 준다(`--usage-small 아파트` = `20104`). 소분류만 줘도 대·중분류가 채워진다(화면 cascade 와 같다).
  코드표는 사이트 화면의 목록 그대로다 — `codes usages`(75개)·`codes regions`(시도 20개). 표에 없는 이름·코드는 `args`.
- **시군구·읍면동**은 행정표준코드(해운대구 `26350`, 좌동 `26350107`)나 사이트 3자리(`350`·`107`)로 준다. 이름은 받지 않는다.
- **매각기일 기간**은 화면에서 비울 수 없다 — 주지 않으면 화면 기본값 **오늘 ~ 14일 뒤**(사이트도 그 뒤는 검색하지 않는다).
  `--sale-from` 을 주면 `--sale-to` 도 준다(끝의 기본값은 오늘 기준이라 시작이 그보다 늦으면 `args`). 기본값을 쓰면 `collect` 가
  `warnings` 에 실제 기간을 싣는다.
- **입찰구분**을 주지 않으면 화면의 "전체"다.

```bash
python3 "$SKILL_DIR/scripts/main.py" plan search --run-dir "$R" --save-dir "$S" \
  --sido 부산광역시 --sigungu 26350 --usage-small 아파트 --price-max 500000000 --flbd-min 1 \
  --sale-from 20261001 --sale-to 20261015
```

```json
{"url": "https://www.courtauction.go.kr/pgj/pgjsearch/searchControllerMain.on", "method": "POST",
 "headers": {"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json",
             "submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch", "SC-Userid": "SYSTEM",
             "Origin": "https://www.courtauction.go.kr",
             "Referer": "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"},
 "body": "{\"dma_pageInfo\":{\"pageNo\":1,\"pageSize\":10,\"bfPageNo\":\"\",\"startRowNo\":\"\",\"totalCnt\":\"\",\"totalYn\":\"Y\",\"groupTotalCount\":\"\"},\"dma_srchGdsDtlSrchInfo\":{\"rletDspslSpcCondCd\":\"\",\"bidDvsCd\":\"\",\"mvprpRletDvsCd\":\"00031R\",\"cortAuctnSrchCondCd\":\"0004601\",\"rprsAdongSdCd\":\"26\",\"rprsAdongSggCd\":\"350\",\"rprsAdongEmdCd\":\"\",\"rdnmSdCd\":\"\",\"rdnmSggCd\":\"\",\"rdnmNo\":\"\",\"mvprpDspslPlcAdongSdCd\":\"\",\"mvprpDspslPlcAdongSggCd\":\"\",\"mvprpDspslPlcAdongEmdCd\":\"\",\"rdDspslPlcAdongSdCd\":\"\",\"rdDspslPlcAdongSggCd\":\"\",\"rdDspslPlcAdongEmdCd\":\"\",\"cortOfcCd\":\"B000210\",\"jdbnCd\":\"\",\"execrOfcDvsCd\":\"\",\"lclDspslGdsLstUsgCd\":\"20000\",\"mclDspslGdsLstUsgCd\":\"20100\",\"sclDspslGdsLstUsgCd\":\"20104\",\"cortAuctnMbrsId\":\"\",\"aeeEvlAmtMin\":\"\",\"aeeEvlAmtMax\":\"\",\"lwsDspslPrcRateMin\":\"\",\"lwsDspslPrcRateMax\":\"\",\"flbdNcntMin\":\"1\",\"flbdNcntMax\":\"\",\"objctArDtsMin\":\"\",\"objctArDtsMax\":\"\",\"mvprpArtclKndCd\":\"\",\"mvprpArtclNm\":\"\",\"mvprpAtchmPlcTypCd\":\"\",\"notifyLoc\":\"on\",\"lafjOrderBy\":\"\",\"pgmId\":\"PGJ151F01\",\"csNo\":\"\",\"cortStDvs\":\"2\",\"statNum\":1,\"bidBgngYmd\":\"20261001\",\"bidEndYmd\":\"20261015\",\"dspslDxdyYmd\":\"\",\"fstDspslHm\":\"\",\"scndDspslHm\":\"\",\"thrdDspslHm\":\"\",\"fothDspslHm\":\"\",\"dspslPlcNm\":\"\",\"lwsDspslPrcMin\":\"\",\"lwsDspslPrcMax\":\"500000000\",\"grbxTypCd\":\"\",\"gdsVendNm\":\"\",\"fuelKndCd\":\"\",\"carMdyrMax\":\"\",\"carMdyrMin\":\"\",\"carMdlNm\":\"\",\"sideDvsCd\":\"\"}}",
 "follow_redirects": false, "timeout_sec": 50,
 "save_dir": "/Users/me/Documents/court-auction-runs/20261001-1400", "save_as": "court-auction/search-c8954ed882-p1-s10.json"}
```

```bash
python3 "$SKILL_DIR/scripts/main.py" collect --run-dir "$R" --input "$R/court-auction/search-c8954ed882-p1-s10.json"
```

소재지 분기 본문에는 화면이 숨긴 법원 셀렉트의 기본값(`cortOfcCd` `B000210`)이 실린다 — 화면이 그렇게 보내고 서버는 그 값을
쓰지 않는다(부산 조회 결과가 부산 법원 행). 고쳐 쓰지 않는다.

검색 조건 인자: `--sido`(이름·코드) `--sigungu` `--dong` `--usage-large|medium|small`(이름·코드)
`--price-min|max`(최저매각가) `--appraised-min|max`(감정가) `--area-min|max`(㎡) `--flbd-min|max`(유찰 횟수)
`--sale-from|to`(YYYYMMDD) `--court-code` `--bid-type date|period`.

`collect` 가 보는 것: 그 쪽에 와야 할 행 수(꽉 찬 쪽은 쪽 크기, 마지막 쪽은 나머지)와 받은 행 수가 다르면 `incomplete`.
행이 요청한 법원·입찰구분·지역·용도를 되비치지 않으면 `mismatch`. 같은 조건의 앞선 쪽과 총계가 다르면 "받는 사이 목록이
바뀌었다" 경고를 싣는다(쪽을 이어 붙이지 말고 새 회차 폴더에서 1쪽부터).

## Step 4: 결과·실패

`collect` 는 성공 `{"ok": true, "status": "ok", …}`(exit 0), 실패 `{"ok": false, "code": …, "error": …}`(exit 4)다.
기본 출력은 행마다 사이트 원본(`raw`)을 함께 싣는다 — **요약만 필요하면 `collect … --no-raw`** 로 대화에 들어오는 양을 줄인다
(검색 100행이면 원본만 수만 자다).
`plan` 은 `status: "planned"`(호출 1개) 또는 `"fetched"`(이 회차에 이미 받았다 — 호출 없이 `collect`)다.

| `code` | 뜻 | 할 일 |
|---|---|---|
| `blocked` | 사이트가 자동화 차단(`ipcheck=false`). 이 회차의 다음 `plan` 도 거부된다 | **자동으로 다시 시도하지 않는다.** 약 1시간 뒤·다른 네트워크를 안내한다 |
| `budget` | 회차 호출 상한을 다 썼다 | 사용자에게 알리고, 정말 필요하면 잠시 쉰 뒤 새 회차 폴더로 |
| `incomplete` | 사건 수·쪽 행 수 대조가 맞지 않는다(부분본 또는 초과본) | 결과를 내지 않는다. 사용자 확인 뒤 새 회차 폴더로 다시 |
| `mismatch` | 받은 응답이 계획한 질의(법원·입찰구분·지역·용도·쪽·사건번호)와 다르다 | 파일을 고치지 않는다. `plan` 이 준 호출을 그대로 불렀는지 확인 |
| `site` | JSON 이 아닌 화면(안내·차단 페이지)·사이트 오류 메시지·형태 변경 | `error` 를 그대로 전한다. 반복되면 스킬 업데이트 필요 |
| `truncated` | 본문이 끝까지 오지 않았다 | 그 파일을 쓰지 않는다. 새 회차 폴더로 다시 |
| `http` · `hyve` | HTTP 오류 · itda-hyve 실패 자리(`hyve_code`) | `error` 를 전한다 |
| `input` · `args` | 회차·파일·인자 문제(인자 오류도 JSON) | `error` 대로 고친다 |

**itda-hyve 호출이 실패하면**(연결 실패·시간 초과 등) `collect` 하지 말고 `code`·`message`·`hint` 를 사용자에게 전한다.
다시 받기는 사용자 확인 뒤 `plan` 부터(한 번 더 센다). POST 라 itda-hyve 가 자동 재시도하지 않는다(차단을 피하려 `retry_unsafe` 를 켜지 않는다).

| itda-hyve 실패 | 뜻 | 할 일 |
|---|---|---|
| `timeout` | 50초 안에 응답이 없다 | 사이트 지연 또는 차단 — 바로 다시 부르지 않는다 |
| `network_error` | 사이트에 닿지 못했다(DNS·연결 거부) | 사용자에게 알린다 — 반복되면 사이트 상태 확인 |
| `invalid_input`(같은 이름 파일) | 이 회차에 이미 받은 파일 | 다시 부르지 않는다 — `plan` 을 다시 부르면 `fetched` 로 `collect` 를 안내한다 |
| `body_truncated: true` | 응답이 잘렸다 | `collect` 가 `truncated` 로 거부한다 |

## Claude 라우팅 가이드

1. **법원코드 먼저** — 모르면 `plan courts` 로 찾거나 사용자에게 어느 법원인지 묻는다.
2. **공고 펼치기는 목록 다음** — 같은 회차에서 `notices` 를 받은 뒤 사용자가 고른 공고의 `noticeId` 로.
3. **차단·예산·부분본은 fail-loud** — `blocked`·`budget`·`incomplete` 는 그대로 알리고 자동으로 다시 시도하지 않는다.
4. **정직 고지(매번)** — ① 참고용이며 **입찰 전 법원 원문 재확인** ② 가격·기일은 **공고 시점 기준**(정정·취하·연기 가능).
   ③ 물건 검색은 **매각기일 기간**(요청값 또는 기본 오늘~14일)을 함께 말한다 — 그 밖의 물건은 결과에 없다.
   금액은 천단위 콤마 + 억/만 환산으로 요약한다. `warnings` 는 전부 그대로 전한다.
5. **read-only·매크로 금지** — 입찰서 작성·제출·결제는 하지 않는다. 반복 조회 루프를 만들지 않는다.

## 제약 (Exclusions)

- **입찰서 자동 작성·제출·결제**, **매크로/반복 폴링** — 영구 비목표.
- **동산(자동차·중기) 경매** 전용 검색 — 범위 밖(공고 펼치기에는 자동차 물건이 섞여 나올 수 있다).
- **매각물건명세서·현황조사서·감정평가서 PDF·물건 사진** — 후속 증분 후보.
- 사이트 변경 시 동작이 멈출 수 있으며, 결과의 정확성·최신성은 법원경매정보 데이터에 의존한다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 아파트·연립 실거래가(경매가 아닌 매매·전월세) | `itda-gov:realty-deals` |
| 지역 아파트 가격 지수·통계 추이 | `itda-gov:realty-price-stats` |
| 전세가율·갭 분석 | `itda-gov:realty-jeonse-gap` |
| 분양·입주 물량 | `itda-gov:realty-supply` |
