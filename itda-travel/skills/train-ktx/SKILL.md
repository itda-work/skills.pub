---
name: train-ktx
description: >
  KTX 고속열차를 검색하고 예약하는 스킬입니다. 2026-09-01 SRT가 KTX로 통합되어
  옛 SRT 구간(수서·동탄·평택지제 출발)도 이 스킬이 담당합니다.
  "다음 주 금요일 서울에서 부산 KTX 찾아줘", "수서에서 부산 가는 표 있어?",
  "오후 2시 이후 동대구 가는 표 있어?", "아까 그 열차로 예약해줘",
  "코레일 계정 확인해줘"처럼 말하면 됩니다.
  코레일 비공식 API를 사용하며, 예약은 반드시 확인을 거치고
  결제·취소는 사용자가 직접 합니다.
  [책임 경계] 본 스킬은 KTX·옛 SRT 전 고속열차 예매 전담 —
  itda-travel:train-srt 는 통합 안내 스텁이며 기능을 갖지 않습니다.
license: MIT
compatibility: "Python 3.10+. 코레일 비공식 API(korail2 계열) 의존."
user-invocable: true
allowed-tools: Bash, Read, AskUserQuestion, mcp__workspace__bash
argument-hint: "서울에서 부산 KTX / 수서에서 부산 / 금요일 저녁 동대구 가는 표"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.4.0"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-09-30"
  tags: "ktx, korail, srt, train, booking, reservation, travel"
---

# train-ktx

KTX 열차를 **검색**하고 **예약**합니다. 사용자용 가이드는 GUIDE.md 참조.

## 2026-09-01 SRT → KTX 통합

SRT는 2026-09-01부로 폐지되고 KTX로 통합됐습니다. **9월 1일 이후 운행 열차는
코레일+ 앱과 코레일 홈페이지에서만 예매**할 수 있고, SRT 앱 예매는 8월 31일
운행분까지였습니다. 따라서 옛 SRT 전용역(**수서·동탄·평택지제**)도 이 스킬이
담당합니다 — 자매 스킬 `train-srt` 는 통합 안내 스텁으로 강등됐습니다(#1624).

라이브 실측(2026-09-02 기준)으로 확인된 사실:

- 수서→부산/동대구/광주송정, 평택지제→부산, 동탄→부산, 부산→수서 각 10건 조회 정상
- 열차번호·종별코드·요금이 옛 SR API 응답과 **일치**(예: 수서→부산 06:00 SRT 303 =
  코레일 "KTX-산천" 303, 52,400원) — 같은 재고를 코레일이 판다
- 옛 SRT 열차는 코레일 표기로 **"KTX" / "KTX-산천"** 으로 나옵니다(정상)

**"SRT" 라는 열차명은 더 이상 존재하지 않습니다.** 차량도 코레일로 이관됐습니다 —
임대분 120000호대 22편성과 SR 발주분 130000호대 10편성이 한국철도공사로 돌아가
**전 편성이 KTX-산천으로 편입**됐습니다. 우리 실측의 종별코드 `07`·`0A`(KTX-산천)·
`00`(KTX)가 그 결과입니다. 검색 결과에 SRT가 하나도 안 나오는 것이 **정상**이며,
이를 결함으로 오판하지 마세요.

## ⚠️ 시작 전 반드시 확인 (디스클레이머)

- **코레일 비공식 API**를 사용합니다. 코레일 이용약관(ToS) 위반 소지가 있으며,
  코레일 측 변경(안티봇 등)으로 **언제든 동작이 멈출 수 있습니다**.
- 이 스킬은 **검색과 예약까지만** 합니다. **결제·취소는 하지 않습니다** —
  사용자가 코레일 앱/웹에서 직접 진행합니다. 예약 후 결제기한 내 미결제 시
  좌석은 **자동 취소**됩니다.
- **예약·결제·노쇼에 대한 책임은 사용자 본인**에게 있습니다.
- **매크로(취소표 자동 연타·반복 폴링)는 제공하지 않으며 금지**합니다. 1회성
  명령만 수행합니다.

## 의존 패키지 (첫 실행 전 1회)

이 스킬은 외부 라이브러리를 요구한다. **정본 선언은 `requirements.txt`** 이며 아래는
그것과 같은 것을 가리킨다(둘이 갈리면 `tests/test_install_guide.py` 가 RED 로 잡는다).

```bash
# macOS/Linux — 정문(korail2-ncard + pycryptodome>=3.20.0 하한을 함께 건다)
python3 "$SKILL_DIR/scripts/install_skill_deps.py"

# Windows
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"

# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만. 아래는 정문이 하는 판단을 손으로 할 때의 안내다.

> **위 명령이 `externally-managed-environment` 로 막히면** — homebrew·pyenv 등
> PEP 668 관리형 인터프리터입니다(흔한 기본값이며 `--user` 만 붙여도 막힙니다).
> 사용자 영역에만 설치하는 아래 조합을 쓰세요(#1626):
>
> ```bash
> # macOS/Linux
> python3 -m pip install --user --break-system-packages korail2-ncard pycryptodome
>
> # Windows
> py -3 -m pip install --user --break-system-packages korail2-ncard pycryptodome
> ```
>
> `--user` 를 **반드시 함께** 씁니다 — 빼면 인터프리터 본체 site-packages 가
> 오염됩니다. 더 깨끗한 대안은 전용 가상환경입니다:
> `python3 -m venv ~/.venvs/itda && ~/.venvs/itda/bin/pip install …` (이후 스킬을
> 그 venv 의 python 으로 실행).

`korail2-ncard` 는 안티봇(Dynapath) 대응이 된 korail2 계열 패키지로, 라이브 동작
검증으로 확정됐다(SPEC-KTX-BOOKING-001 OQ-1 종결, 2026-06-22).

> **Claude 실행 규칙:** 설치 여부를 미리 점검하지 말고 **우선 실행**한다. 미설치면
> 어댑터가 위 설치 명령을 그대로 담아 fail-loud 하므로(rc=1), 그 안내를 사용자에게
> 전달하거나 승인 후 설치하고 재시도한다. 검색 결과가 0건인 것과 라이브러리가 없는
> 것은 **다른 실패**다 — 메시지를 확인하지 않고 "열차 없음" 으로 보고하지 않는다.

## 자격증명 (계정)

| Variable | 설명 | 발급 |
|---|---|---|
| `KORAIL_USER_ID` | 코레일 회원 ID (회원번호 8자리 / 휴대폰 / 이메일) | [letskorail.com](https://www.letskorail.com) 회원가입 |
| `KORAIL_PASSWORD` | 코레일 로그인 비밀번호 | 위 계정의 비밀번호 |

**계정은 환경변수로만 넣는다 — 스킬은 `.env` 같은 파일을 읽지 않는다(itda-work/skills#45):**

| 환경 | 계정을 넣는 곳 | 쓰이는 곳 |
|---|---|---|
| Claude Code | 셸 환경변수, 또는 `claude config set env.KORAIL_USER_ID "..."`·`claude config set env.KORAIL_PASSWORD "..."`(등록 뒤 세션을 다시 시작) | 스크립트가 `os.environ` 에서 읽어 코레일에 직접 로그인한다 |

> itda-hyve 시크릿 경로는 이 스킬에 아직 없다 — 스크립트가 API 를 직접 부르므로 itda-hyve 에 등록한 키는 쓰이지 않는다.

등록을 마쳤으면 **"코레일 계정 확인해줘"** 라고 요청해 로그인 1회로 설정을
검증할 수 있습니다(`check` — 규칙 7 참조).

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find`·파일 열람으로 **사전 점검하지 않는다** — 스크립트를 **우선 실행**한다. 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `KORAIL_USER_ID=<ID> KORAIL_PASSWORD=<PW> python3 "$SKILL_DIR/scripts/main.py" ...`. 지침에도 없으면 fail-loud 안내와 위 경로를 제시한다. `.env` 파일을 만들라고 안내하지 않는다(스크립트가 읽지 않는다). 계정 값을 대화로 받지 않는다. 주입한 값은 출력·요약·로그에 노출하지 않는다(SAFE-3).

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수의 KORAIL_PASSWORD 를 사용했습니다"). 값은 어디에도 표시하지 않는다.

> 스크립트의 키 소스: `--id`/`--pw` > `os.environ`(Claude 주입 포함). env 파일·`~/.claude/settings.json` 은 읽지 않는다.
> 키가 없으면 fail-loud로 발급·설정 방법을 안내합니다(크래시 아님). 비밀번호는 출력·로그에 평문으로 남기지 않습니다(마스킹).

## 실행

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

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
printf "%s\n" "$c"' _ train-ktx itda-travel "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'train-ktx'; $P = 'itda-travel'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/main.py" search --dep 서울 --arr 부산 --date 20260612 --time 140000
python3 "$SKILL_DIR/scripts/main.py" reserve --dep 서울 --arr 부산 --date 20260612 --time 140000 --index 0            # 미리보기(예약 안 함)
python3 "$SKILL_DIR/scripts/main.py" reserve --dep 서울 --arr 부산 --date 20260612 --time 140000 --index 0 --confirm  # 실제 예약
python3 "$SKILL_DIR/scripts/main.py" reservations
python3 "$SKILL_DIR/scripts/main.py" check           # 계정 확인(로그인 1회, read-only)

# Windows
py -3 "$env:SKILL_DIR\scripts\main.py" search --dep 서울 --arr 부산
```

> **저장소 개발 부연**: 스크립트는 공용 `shared/` 모듈(`env_loader`)을 import 합니다.
> 배포본에서는 `shared/` 가 함께 주입되므로 별도 설정이 필요 없고, 저장소 체크아웃에서
> 직접 실행할 때만 저장소 루트에서 `PYTHONPATH=skills/shared` 를 앞에 붙입니다.

옵션: `--adults N`(기본 1) · `--children N` · `--seniors N` · `--train-type ktx|all` ·
`--seat general|special` · `--json`.

옵션 `--json` · `--id` · `--pw` 는 서브커맨드 **뒤**에 둡니다
(예: `... main.py search --dep 서울 --arr 부산 --json`).

## Claude 라우팅 가이드

Claude가 이 스킬을 실행할 때 반드시 따르는 행동 규칙입니다.

**규칙 1 — 역명 확인**
`search`/`reserve` 출력에 "역을 찾지 못했습니다" + 후보가 나오면, 임의로 고르지
말고 사용자에게 어느 역인지 확인합니다. 옛 SRT 전용역(수서·동탄·평택지제)은
2026-09-01 통합으로 **정상 지원**하므로 거부하지 않습니다(`지제`·`평택`은
`평택지제`로 정규화). 사용자가 "SRT" 라고 불러도 이 스킬로 그대로 처리하고,
결과에 "KTX-산천" 등으로 표기되는 것이 정상임을 필요 시 한 줄로 안내합니다.

**규칙 2 — 예약 2단계 확인 게이트 (SAFE-1, 필수)**
예약은 **절대 곧바로 `--confirm` 하지 않습니다.** 반드시 두 단계를 거칩니다:
1. 먼저 `--confirm` **없이** `reserve` 를 실행해 미리보기(열차·시각·구간·좌석·인원)를 받습니다. 이 단계에서는 실제 예약이 일어나지 않습니다.
2. 미리보기 내용을 `AskUserQuestion` 으로 사용자에게 제시하고 — 구간·시각·좌석유형·인원·예상 결제기한을 명시 — **명시적 승인**을 받습니다.
3. 승인된 경우에만 동일 명령에 `--confirm` 을 붙여 재실행합니다.
사용자 승인 없이 `--confirm` 을 붙이지 않습니다.

**규칙 3 — 결제·취소는 안내만 (SAFE-2)**
이 스킬은 결제·취소를 하지 않습니다. 예약 후에는 "결제는 코레일 앱/웹에서
직접, 결제기한 내" 임을 안내합니다. 취소 요청을 받으면 코레일 앱/웹·고객센터로
안내하고, 스킬로 자동 취소하지 않습니다(v1 비목표).

**규칙 4 — fail-loud (SAFE-4)**
"코레일 안티봇에 차단", "로그인 필요", "매진" 등 오류는 사유를 그대로 사용자에게
전달합니다. 빈 검색 결과를 "열차 없음"으로 단정하기 전에 날짜·시각·역명·차단
여부를 먼저 점검합니다.

**규칙 5 — 자격증명 보호 (SAFE-3)**
`KORAIL_USER_ID`/`KORAIL_PASSWORD` 값을 출력·요약·로그에 노출하지 않습니다.

**규칙 6 — 매크로 금지 (SAFE-6)**
매진 시 자동 반복 조회·취소표 낚기 루프를 만들지 않습니다. 사용자가 다시
요청할 때 1회 실행합니다.

**규칙 7 — 계정 확인 (check)**
"계정 확인해줘" 요청, 자격증명 최초 설정 직후, 로그인 오류 후 재설정 시에는
`check` 를 실행해 로그인 1회로 자격증명을 검증합니다. 출력은 **마스킹된 ID와
성공 여부만**입니다(SAFE-3 — 회원명 등 계정 정보 미출력). 검색·예약 흐름마다
강제 실행하지는 않습니다(불필요한 로그인 왕복 최소화).

## 제약 (Exclusions)

- **결제 자동완료 · 예약 취소 · 매크로/취소표 자동낚기** — 비목표(취소·매크로는 영구).
- ~~**SRT** — v1 비목표~~ → **2026-09-01 KTX 통합으로 지원 대상**(#1624).
  수서·동탄·평택지제 포함. 되돌려 읽지 마세요.
- 다구간 환승 · 운임 할인 자동 최적화 · 회원가입 — 비목표.
- 예약대기(매진 시 대기 등록)는 v1 범위 밖 — 검색에서 "대기가능"으로 표기만 합니다.
- 결제기한이 지나면 좌석은 **코레일이 자동 소멸**시킵니다(이 스킬이 취소하는 것 아님).
- 안티봇(Dynapath) 우회는 라이브러리에 위임하며, 코레일 변경 시 동작 불가할 수 있음.
