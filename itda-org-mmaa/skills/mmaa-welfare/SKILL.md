---
name: mmaa-welfare
description: >
  군인공제회 복지포털 스냅샷 Q&A — 복지부조(신규가입·출산 축하금, 재해위로금, 축하기념품)·
  회원콘도 이용안내·유익한 정보(취업·창업·시니어)를 출처 URL·수집일과 함께 답합니다.
  "출산축하금 얼마?", "군인공제회 콘도 이용 조건", "재해위로금 대상" 같은 군인공제회 복지
  질문이거나 사용자가 이 스킬을 지명하면 사용합니다. 제휴복지·특별할인·콘도 예약은 회원
  로그인 영역이라 URL 안내까지만 합니다.
license: Apache-2.0
compatibility: "Python 3.10+, Claude Code & Cowork. 검색은 표준 라이브러리만. 스냅샷 재수집만 beautifulsoup4 와 itda-hyve 0.10.4 이상(로컬 MCP 서버 — batch plan_file)이 필요하다."
allowed-tools: "Bash, Read, mcp__workspace__bash, mcp__remote-devices__itda-hyve__batch"
user-invocable: true
argument-hint: "[질문] [--refresh]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  status: "active"
  version: "0.4.0"
  created_at: "2026-07-27"
  updated_at: "2026-10-01"
  tags: "MMAA, welfare, benefits, condo, snapshot, QnA"
---

# mmaa-welfare

군인공제회 복지포털(`https://www.mmaa.or.kr/web/contents/welfaremain.do`)의 공개
콘텐츠를 수집·구조화한 스냅샷(`data/pages.jsonl`)을 근거로 복지 관련 질문에
답합니다. 사이트 재방문 없이 즉답하되, **출처 URL 과 스냅샷 수집일을 항상 함께**
제시합니다.

## Prerequisites

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
printf "%s\n" "$c"' _ mmaa-welfare itda-org-mmaa "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

Windows(PowerShell):

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'mmaa-welfare'; $P = 'itda-org-mmaa'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

검색만 할 때는 표준 라이브러리만 사용하므로 설치가 필요 없습니다.
재수집(`--refresh`) 시에만 의존성(beautifulsoup4 — HTML 판독)을 설치합니다:

```bash
# macOS/Linux (재수집 시에만) — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

```powershell
# Windows (재수집 시에만) — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 사용법 — 질문 답변 (기본)

1. 사용자 질문에서 핵심 키워드를 뽑아 스냅샷을 검색한다:

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/search.py" "출산축하금 금액" --top 5

# Windows
py -3 "$env:SKILL_DIR\scripts\search.py" "출산축하금 금액" --top 5
```

2. 상위 결과 중 관련 페이지를 `--full` 로 본문 전체를 받아 근거로 답한다:

```bash
python3 "$SKILL_DIR/scripts/search.py" "출산축하금" --top 2 --full
```

3. 답변 계약 (필수):
   - **모든 정보 항목에 출처 URL 을 명시**한다 — 여러 페이지를 근거로 하면
     항목별로 해당 URL 을 붙인다. 답변 끝에 **스냅샷 수집일**(`snapshot_date`)을
     명시한다. 예: `출처: https://www.mmaa.or.kr/... (2026-09-04 수집 기준)`
   - **스냅샷 한계를 설명**한다: 이 스킬에 패키징된 데이터는 수집 시점의 박제라
     스킬 스스로 갱신할 수 없으며, 금액·기간·할인율 등은 현재 변경됐을 수 있다.
     최신 확인이 필요하면 "최신화 요청"이 가능함을 알린다(아래 절).
   - 결과에 `auth_required: true` 페이지만 있으면(신청·조회·예약 등 로그인 영역)
     "회원 로그인이 필요한 영역"임을 알리고, 해당 URL 을 안내한다 — 본문을
     추측으로 채우지 않는다.
   - 검색 결과가 없으면 "스냅샷에 없는 내용"이라고 명시하고, 원하면 라이브
     확인이 가능함을 안내한다(무단 라이브 조회로 조용히 대체하지 않는다).

## 사용법 — 최신화 요청 (라이브 조회)

사용자가 "지금 기준으로", "최신 정보로", "요즘도 그래?" 등 **최신화를 요청**하면:

1. 스냅샷 검색으로 해당 정보의 **출처 URL** 을 찾는다.
2. 사용 가능한 실브라우저 도구로 그 URL 을 라이브 조회한다 — 우선순위:
   - Claude in Chrome(`claude-in-chrome` 도구)이 있으면 해당 페이지를 열어 판독
   - aside 브라우저(`itda-web:aside-browser-mcp`)가 연결돼 있으면 해당 페이지를 열어 판독
   - 둘 다 없으면 라이브 확인이 불가함을 알리고 URL 직접 방문을 안내
3. 라이브 결과를 스냅샷과 **비교해 차이를 명시**하며 전달한다.
   예: "스냅샷(2026-09-04)에는 30만원이었는데, 현재 사이트 기준으로 변경되었습니다."
4. **한계 고지**: 스킬에 패키징된 스냅샷 파일은 변경할 수 없으므로, 라이브로
   확인한 최신 정보는 이번 대화의 답변에만 반영되고 이후 질문에는 다시 스냅샷
   기준으로 답하게 됨을 설명한다. 영구 반영은 스냅샷 재수집 후 스킬 새 버전
   릴리즈로만 가능하다.

제휴복지(카테고리·무신사·메가스터디·특별할인소식)·콘도 예약·희망플러스·법률상담처럼
**회원 로그인 영역**(아래 한계 참조)은 라이브로도 본문을 볼 수 없다 — 로그인 필요
안내와 URL 제공까지만 하고, 라이브 조회를 시도하지 않는다.

## 사용법 — 스냅샷 재수집 (개발·로컬용)

패키징된 `data/` 는 읽기 전용이다. 새 스냅샷은 **요청은 itda-hyve, 판독은 스크립트**로 만든다 — `collect.py` 는 네트워크를
하지 않고, 바퀴마다 다음에 받을 페이지를 계획 파일로 쓰며 itda-hyve 가 저장한 HTML 을 읽는다. 공용 규약(저장 폴더·실패
코드·보안 계약)은 동봉한 [references/netbridge.md](references/netbridge.md) 가 정본이다.

```
plan → batch(plan_file) → collect → batch(plan_file …) → collect → … → collect(status ok → 스냅샷)
```

- **호출 수를 먼저 알린다** — 진입 1 + 메뉴 약 38 + 목록 9 = **약 48호출**(2026-10-01 기준). `plan` 출력의 `estimate` 를 그대로 전하고
  확인받은 뒤 시작한다.
- 회차 폴더: 작업 폴더 아래 `mmaa-runs/<YYYYMMDD-HHMM>/`. `--run-dir` 은 스크립트가 보는 경로(Cowork `$HOME/mnt/<연결 폴더>/mmaa-runs/<시각>`),
  `--save-dir` 은 같은 폴더의 **호스트 절대 경로**(Windows 호스트면 `C:\…`). 같은 머신이면 두 값이 같다. 이 폴더는 이 스크립트 전용이다.

```bash
# macOS/Linux
R="$HOME/mnt/작업/mmaa-runs/20261001-0930"; S="/Users/me/작업/mmaa-runs/20261001-0930"
python3 "$SKILL_DIR/scripts/collect.py" plan --run-dir "$R" --save-dir "$S"
# → 출력의 batch_args 를 **차례로** batch 에 보낸다(앞 batch 가 끝난 뒤 다음 — 한 번에 8개, 저속 수집)
python3 "$SKILL_DIR/scripts/collect.py" collect --run-dir "$R"
# → status 가 incomplete 면 새 batch_args 로 다시 batch → collect. ok 가 되면 스냅샷이 $R/snapshot/ 에 있다
python3 "$SKILL_DIR/scripts/search.py" "질문" --data-dir "$R/snapshot"

# Windows
py -3 "$env:SKILL_DIR\scripts\collect.py" plan --run-dir "$env:R" --save-dir "$env:S"
py -3 "$env:SKILL_DIR\scripts\collect.py" collect --run-dir "$env:R"
```

첫 계획 파일의 호출은 이런 모양이다(참고용 — 옮겨 적지 않고 `batch_args` 만 보낸다):

```json
{"calls": [{"id": "p-welfaremain-829fc997", "tool": "http_request",
            "args": {"url": "https://www.mmaa.or.kr/web/contents/welfaremain.do", "timeout_sec": 45,
                     "save_as": "mmaa/p-welfaremain-829fc997.html"}}],
 "overwrite": true, "timeout_sec": 50}
```

- 요청에 `User-Agent`·쿠키 헤더를 더하지 않는다(쿠키 없이 성립 — 2026-10-01 실측). `batch` 에 `plan_file` 이 없는 옛 판이면 업데이트를 안내한다
  (호출이 수십 개라 하나씩 부르지 않는다).
- **응답 요약의 `final_url`·헤더(`Set-Cookie`)를 대화에 옮겨 적지 않는다** — 한 메뉴는 세션 id 를 주소에 붙인 곳으로 넘어간다.
- batch 결과에 실패한 호출(`ok: false`)이 있으면 그 `save_as` 자리에 `{"error": {"code": "<code>", "message": "<message>"}}` 를 써 둔다 —
  경로는 이 스크립트가 보는 회차 폴더 기준 `$R/<save_as>` 다(`$S` 는 itda-hyve 호스트 경로라 샌드박스에서 쓰지 않는다).
  `collect` 가 그 페이지를 다시 계획한다(계획 파일에 `overwrite: true` 가 있어 같은 이름으로 다시 받는다).
- **`collect` 는 그 바퀴의 batch 가 전부 끝난 뒤에 부른다.** 일찍 불러도 아직 안 온 파일은 실패로 세지 않고 같은 계획을 다시 낸다
  (`waiting`). 새 파일 없이 5번 연달아 부르면 `not_fetched`(exit 1)로 멈추지만 회차 상태는 그대로라, batch 결과를 확인하고 파일이
  오면 `collect` 로 이어 간다.
- `collect` 의 판정: 누리집 페이지가 아닌 본문(WAF 차단 "Page Not Found (wf)"·잘린 본문)과 실패 자리는 다시 계획하고,
  **한 페이지가 세 번 나쁘게 오면 `partial`(exit 2) — 스냅샷을 쓰지 않는다**(부분본을 전량으로 저장하지 않는다). 바퀴는 30번까지 —
  앞 계획이 전부 판정된 `collect` 만 한 바퀴로 센다(batch 사이사이에 불러 일부만 온 호출은 세지 않는다).
  `partial` 은 그 회차의 끝이다 — 사유를 사용자에게 알리고, 다시 받으려면 **새 회차 폴더**로 `plan` 부터 한다.
  진입 페이지에서 복지포털 메뉴를 못 찾으면 `site`(구조 변경 — 추측으로 고치지 않고 알린다).
  스냅샷을 쓰기 직전에 받은 파일이 사라졌으면(회차 폴더를 옮기거나 지웠다) 그 페이지만 다시 계획한다(`lost`).
- 로그인 필요 페이지는 URL·제목만 기록하고 본문을 수집하지 않는다. 제휴복지 카테고리 8개·특별할인소식 목록은 1쪽부터 따라가지만
  2026-10-01 실측으로는 전부 로그인 셸이라 상세가 없다(`meta.json` 의 `listing_auth_count`). 목록이 열렸는데 1쪽에서 상세를
  하나도 못 읽으면 `warnings` 에 싣는다(구조 변경과 빈 게시판을 가를 수 없다 — 그대로 전한다). 읽은 상세 수는 `meta.listing_ids`.
- 스킬 `data/` 를 갱신하려면(저장소 체크아웃) `collect --output-dir <스킬>/data` 를 준다. `--limit N` 은 스모크용이다 —
  결과 `status` 가 `smoke` 이고 전량이 아니므로 `data/` 갱신에 쓰지 않는다.

## 데이터 구조

```
data/
├── meta.json      # generated_at(수집일)·페이지 수·로그인영역 수
└── pages.jsonl    # 페이지별 {url, breadcrumb, title, kind, auth_required, text, fetched_at}
```

`kind`: `page`(안내 페이지) · `partner`(제휴복지 상세) · `board`(특별할인소식 게시글).

## 범위와 한계

- **범위**: 복지포털 섹션 한정. 공개 본문이 실제로 있는 곳은 **복지부조 안내 5종**
  (퇴직급여 신규가입축하금·출산축하금·재해위로금·축하기념품·연금식 분할급여
  가입축하금), **회원콘도 이용안내**(대상·요금·예약안내), **제휴복지 제안**,
  **유익한 정보 6종**(취업·창업·여가/건강·금융/경제·지식정보·시니어)이다.
  저축·대여·주택 등 타 섹션은 범위 밖이다.
- **회원 로그인 영역**(2026-09-04 실측, 41페이지 중 25페이지): 신청·조회·예약뿐
  아니라 **콘도 예약 페이지(대명·한화), 제휴복지 전체(카테고리·더케이몰·건강검진·
  무신사·플러스앤·메가스터디·특별할인소식), 기타복지 전체(재무설계·희망플러스론·
  개인회생·법률상담·헤이웰)** 가 로그인 뒤에 있다. 정적 HTML 이 본문 대신
  `webLogin.do` 리다이렉트 스크립트만 싣고, 브라우저로 열어도 로그인 페이지로
  넘어간다. 사용자가 물으면 로그인 필요 안내와 URL 제공까지만 한다.
  - 오판 이력: 구 스냅샷(2026-07-27)은 이 22페이지의 GNB 메뉴 문자열(37자)을
    본문으로 세어 "본문 34페이지"라 했고, 특별할인소식·제휴업체 상세를 "WAF 경유
    JS 렌더라 미수집"으로 설명했다. 둘 다 틀렸다 — 실체는 로그인 영역이다(#1643).
    라이브 조회로 뚫리는 것이 아니므로 그 경로로 안내하지 않는다.
- 스냅샷은 수집 시점의 박제이며 **스킬 스스로 갱신할 수 없다** — 이벤트·할인은
  종료됐을 수 있다. 수집일 명시·한계 고지 계약을 지킨다.

## 데이터 경로 정책

- 스냅샷 정본: 스킬 동봉 `data/` (배포 시 포함)
- 재수집 산출: 기본은 회차 폴더의 `snapshot/`. 동봉 `data/` 갱신은 저장소 체크아웃에서 `--output-dir` 로만
- `.itda-skills/` 내부에는 최종 결과를 저장하지 않습니다
