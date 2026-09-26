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
  version: "0.3.0"
  status: "experimental"
  created_at: "2026-06-05"
  updated_at: "2026-09-01"
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

**권장 (비개발자 포함 모든 사용자) — 작업 폴더 `.env`에 계정 등록:**

작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트) 루트에 `.env` 파일을 만들고 아래 두 줄을 넣어 두면 스킬이 자동으로 찾아 읽습니다. 파일명 별칭 `.env.txt`·`env.txt`·`환경변수.txt` 도 동일하게 탐색된다. `.env` 대신 셸 환경변수나 `~/.claude/settings.json` 의 `env` 로 설정해 두어도 로더가 자동으로 찾습니다. 비밀번호가 담긴 `.env` 파일은 작업 폴더 밖으로 공유하지 마세요.

```dotenv
KORAIL_USER_ID=코레일 회원번호 또는 휴대폰번호 또는 이메일
KORAIL_PASSWORD=코레일 로그인 비밀번호
```

등록을 마쳤으면 **"코레일 계정 확인해줘"** 라고 요청해 로그인 1회로 설정을
검증할 수 있습니다(`check` — 규칙 7 참조).

> **키 주입 (Claude 실행 규칙):** 자격증명 유무를 `ls`/`find` 등으로 **사전 점검하지 않는다** — 스크립트가 `.env`·`.env.txt`·`env.txt`·`환경변수.txt` 를 스스로 탐색하므로 **우선 실행**한다(셸 glob·검색 패턴은 별칭을 놓쳐 오탐한다: `.env*`→env.txt 누락, `*env*`→환경변수.txt 누락). 실행이 자격증명 누락으로 실패하면, 사용자 지침("Claude 지침"·`CLAUDE.md`)에 해당 변수가 선언돼 있는 경우 그 값을 환경변수로 전달해 재시도한다 — 예: `KORAIL_USER_ID=<ID> KORAIL_PASSWORD=<PW> python3 "$SKILL_DIR/scripts/main.py" ...`. 지침에도 없으면 fail-loud 안내를 제시한다. 주입한 값은 출력·요약·로그에 노출하지 않는다(SAFE-3). 수동 확인이 꼭 필요하면 파일명 4종(`.env`·`.env.txt`·`env.txt`·`환경변수.txt`)을 그대로 나열해 확인한다.

> **출처 표시 (Claude 실행 규칙):** 스크립트 stderr 에 `[자격증명] KEY ← 출처` 줄이 나오면, 그 내용을 사용자에게 짧게 알린다(예: "환경변수.txt 의 KORAIL_PASSWORD 를 사용했습니다") — 사용자가 어느 설정파일이 쓰였는지 인지하게 하는 계약이다. 값은 어디에도 표시하지 않는다.

**개발자 (선택) — 환경변수 / `.env`:** 셸 환경변수, `~/.claude/settings.json` 의 env, 작업 폴더/홈의 `.env`도 사용할 수 있습니다.
> 조회 우선순위: 셸 환경변수 > `~/.claude/settings.json` 의 env(Claude 주입 포함) > 작업 폴더/홈의 `.env`.
> 키가 없으면 fail-loud로 발급·설정 방법을 안내합니다(크래시 아님). 비밀번호는 출력·로그에 평문으로 남기지 않습니다(마스킹).

## 실행

먼저 스킬 디렉토리를 확정합니다(이후 모든 실행이 이 기준).

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/train-ktx}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/train-ktx' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\train-ktx"  # 미설정이면 SKILL.md 위치 절대경로 사용
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
