---
name: synthetic-data
description: >
  실제 데이터 없이 업무 문서의 구조만 인터뷰로 받아 같은 구조의 가상 데이터 세트를 만듭니다.
  요양병원(입퇴원 대장·근무표·환자분류군 집계·상담 기록지)·노인장기요양(수급자 명단·급여제공기록지·근무표·프로그램 일지)
  프리셋에서 출발해 엑셀·HWPX 양식에 채우고, 규칙 검증 리포트와 개인정보 등급표를 냅니다.
  "우리 대장 구조로 가상 데이터 50건", "실습용 가짜 환자 명단", "이 양식에 테스트 데이터 채워줘"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 가상 데이터 생성 전담 — itda-data:biz-redact 는 실제 문서 영업기밀 마스킹·복원, itda-data:pii-redact 는 정형 PII 마스킹.
license: MIT
compatibility: "Python 3.10+ · xlsx 산출에 openpyxl"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, mcp__workspace__bash
argument-hint: "[도메인/문서 프리셋 또는 스펙.json] [--rows N] [--xlsx-template 양식.xlsx] [--hwpx-template 양식.hwpx]"
metadata:
  author: "Chinseok"
  version: "0.1.3"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-09-05"
  updated_at: "2026-09-28"
  tags: "synthetic-data, test-data, privacy, interview, preset, nursing-hospital, long-term-care, xlsx, hwpx, deterministic, korean"
---

# synthetic-data

> 병원마다 서식이 다르고 실제 데이터는 한 건도 받을 수 없습니다(개인정보 보호법 제23조 민감정보·제28조의8 국외 이전·의료법 제19조).
> 이 스킬은 **구조는 진짜, 값은 전부 가짜**인 데이터 세트를 만듭니다 — 수강생이 본인 서식으로 1교시 안에 직접 돌립니다(15분).

표·규칙·검증·서식 채우기는 전부 `scripts/synth.py` 가 로컬에서 결정론으로 합니다. 에이전트(LLM)는 **인터뷰를 진행하고 자유텍스트(상담 내용 등) 가상 문장만** 씁니다.

---

## [HARD] 철칙

1. **첫 질문은 고정이다:** "이 예시는 실제 환자·직원이 아닌 것을 확인합니다." — 사용자가 예시로 주는 2~3건도 **가짜**여야 한다. 실제 행을 넣어 늘리는 것은 이 스킬이 막으려는 행위 그 자체다. 확인 전에는 인터뷰를 진행하지 않고, 확인을 받은 뒤에만 `generate` 에 `--confirm-fake` 를 붙인다(플래그 없이는 스크립트가 거부, exit 2). 스크립트는 예시 행·자유텍스트에서 **검증식을 통과하는 주민번호·부여 가능 대역의 휴대전화**를 발견하면 실제 데이터 의심으로 거부한다 — 이 탐지는 형식 기반이라 실명·실제 문장은 잡지 못하므로 사람 확인이 여전히 1차 방어선이다.
2. **실제 문장은 예시로도 받지 않는다.** 상담 메모·특이사항 같은 자유텍스트는 사용자 예시를 받지 말고 AI 가 가상 문장을 쓴다(`fill-text`).
3. **원본 양식 파일을 덮어쓰지 않는다.** 산출은 항상 `--out` 새 디렉토리이고 양식은 읽기만 한다(스크립트가 같은 경로면 거부, exit 2).
4. **한계 고지 2종은 지우지 않는다.** 데이터 한계(상관관계 없음·경영 판단 금지) + 프리셋 한계(예측일 뿐 정확하지 않음)가 `report.md` 와 xlsx 「안내」 시트에 **항상** 실린다. hwpx 는 양식에 `(한계고지)` placeholder 가 있을 때만 안에 기입되며, 없으면 리포트가 ⚠️ 로 경고한다 — 그 hwpx 는 `report.md` 와 함께 전달한다. 프리셋을 고치지 않고 그대로 생성하면 "프리셋 그대로 생성 — 본인 서식과 다를 수 있음" 이 추가된다.
5. **검증 리포트의 규칙 위반이 0 이 아니면 산출물을 넘기지 않는다.** 스펙(규칙)이나 생성기를 고치고 다시 돌린다.

---

## 인터뷰 흐름 (프리셋에서 출발 — 백지 인터뷰 금지)

**0. 첫 화면** — 아래 두 문장을 그대로 보여 준 뒤 시작한다.

> 이 예시는 실제 환자·직원이 아닌 것을 확인합니다. (확인해 주세요)
>
> 이 프리셋의 항목·규칙은 해당 업무의 문서 구조를 **예측해 만든 것일 뿐 정확하지 않습니다.** 실제 업무의 데이터 구조(항목 이름·규칙·서식)를 알려주시면 그에 맞춰 생성할 수 있습니다.

**1. 업무명·문서 종류** — 프리셋 목록(`presets`)을 보여 주고 가장 가까운 것을 고르게 한다. 없으면 가장 비슷한 프리셋을 골라 고친다.

**2. 항목 고치기** — `show <도메인/문서>` 로 항목 표를 보여 주고 "빼는 칸 / 더하는 칸 / 이름이 다른 칸" 만 묻는다. 더하는 칸은 타입·생성 방식·**개인정보 등급**(식별자 / 민감정보 / 준식별자 / 비개인정보)을 함께 정한다.

**3. 규칙** — "입원일 ≤ 퇴원일", "재원일수 = 차이", "병실 앞자리 → 병동" 처럼 항목 간 규칙을 묻는다. 프리셋 규칙을 보여 주고 맞는지만 확인해도 된다.

**4. 가짜 예시 2~3건**(선택) — 사용자가 손으로 친 가짜 행. 값은 선택지 후보(`choice`)에 편입된다. 자유텍스트 칸은 예시를 받지 않는다(철칙 2).

**5. 건수·서식** — 생성 건수(기본 50), 채울 양식 파일(xlsx / hwpx) 경로.

**6. 스펙 저장 → 생성 → 리포트 확인** — 고친 결과를 `spec.json` 으로 저장하고 `generate --confirm-fake` 를 돌린다. 자유텍스트 항목이 있으면 리포트의 placeholder 수만큼 `fill-text` 로 가상 문장을 채우고 **`render` 로 xlsx·hwpx·리포트를 다시 만든다**(`render` 는 행을 재생성하지 않는다).

---

## 실행

### 실행 전 — 스킬 디렉토리 확정

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/synthetic-data}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/synthetic-data' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\synthetic-data"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

xlsx 산출에는 openpyxl 이 필요하다(없으면 xlsx 만 생략되고 csv·json·리포트는 나온다): `python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"`. Windows 는 `python3` 대신 `py -3` — 스크립트가 stdout/stderr 를 UTF-8 로 고정하므로 `-X utf8`·`PYTHONUTF8` 은 불요하고, 한글·공백이 든 경로(`C:\Users\…\바탕 화면\가상 데이터`)도 그대로 쓴다(Windows 11 + Python 3.13 실측, #1647).

### 명령

```bash
python3 "$SKILL_DIR/scripts/synth.py" presets                                  # 프리셋 8종 목록
python3 "$SKILL_DIR/scripts/synth.py" show nursing-hospital/admission-ledger    # 프리셋 JSON(첫 줄이 프리셋 한계 고지)
python3 "$SKILL_DIR/scripts/synth.py" validate spec.json                        # 스키마·규칙 참조·등급 검증 (RED = exit 1)
python3 "$SKILL_DIR/scripts/synth.py" generate spec.json --rows 50 --out ./가상데이터 --confirm-fake \
        [--seed 7] [--xlsx-template 우리양식.xlsx] [--hwpx-template 상담기록지.hwpx --hwpx-rows 3]
python3 "$SKILL_DIR/scripts/synth.py" fill-text ./가상데이터/data.json texts.json   # 자유텍스트 placeholder 치환
python3 "$SKILL_DIR/scripts/synth.py" render ./가상데이터/data.json [--xlsx-template …] [--hwpx-template …]   # 채운 뒤 재렌더
python3 "$SKILL_DIR/scripts/synth.py" verify spec.json ./가상데이터/data.json      # 규칙 재검증만
```

`generate` 의 첫 인자는 스펙 파일이거나 프리셋 이름(`도메인/문서`)이다. 프리셋 이름을 그대로 주면 "프리셋 그대로 생성" 고지가 붙는다. `--confirm-fake` 는 첫 질문 확인의 표시라 사용자 확인 없이 붙이지 않는다. 원본 양식이 `--out` 안의 산출 경로와 겹치면 아무것도 쓰지 않고 거부한다.

### 산출물 (`--out` 디렉토리)

| 파일 | 내용 |
|---|---|
| `data.csv` · `data.json` | 가상 데이터 N건 (json 에는 스펙·seed 동봉 — 재현·재검증용) |
| `<문서>.xlsx` | 양식을 줬으면 그 양식의 헤더 행 아래에 기입(다른 시트·제목·서식 보존, 헤더 아래에 이미 내용이 있으면 아래로 밀고 리포트에 적는다 — 수식 참조는 갱신되지 않으니 빈 양식 권장), 없으면 새 통합문서. 첫 시트 「안내」 에 한계 고지 |
| `<문서>-001.hwpx …` | hwpx 양식(1건 1장)의 `(항목명)`·`{{항목명}}` placeholder 치환. `(한계고지)` 가 있으면 고지도 기입, 없으면 리포트 ⚠️. 글자 서식이 갈린 곳에 걸쳐 치환 못 한 placeholder 도 리포트 ⚠️ |
| `report.md` | 한계 고지 2종 + 규칙별 위반 건수(0 확인) + 자유텍스트 placeholder 잔여 |
| `field-definitions.md` | 항목 정의표 — 항목별 개인정보 등급·재식별 준식별자 조합·근거 조문 (1교시 「판단 기준표」에 붙인다) |

### 자유텍스트 채우기 (LLM 의 유일한 몫)

`report.md` 의 placeholder 수를 보고, 항목별·행별 가상 문장을 JSON 으로 만들어 `fill-text` 에 넘긴다.

```json
{"상담내용": {"1": "보호자가 야간 낙상 우려를 말씀하셔서 침상 난간 사용을 안내함.", "2": "…"}}
```

문장은 **그럴듯하되 특정 실존 인물·기관을 떠올리게 하지 않는다**(실명·실재 병원명·실재 주소 금지). 자유텍스트가 아닌 항목에 넣거나, 검증식을 통과하는 주민번호·부여 가능 대역 휴대전화가 섞이면 스크립트가 거부한다(exit 2). 채운 뒤 `render` 로 xlsx·hwpx 를 다시 만든다.

---

## 프리셋 — 코드가 아니라 데이터

`presets/<도메인>/<문서>.json` 한 장이 도메인 지식 전부다. 스킬 본체(생성기·검증기·서식 채우기)는 도메인을 모른다. 스키마·생성기 종류·규칙 종류는 [`references/preset-schema.md`](./references/preset-schema.md).

| 도메인 | 문서 4종 | 근거 조문 |
|---|---|---|
| `nursing-hospital` 요양병원 | `admission-ledger` 입퇴원 대장 · `shift-roster` 3교대 근무표 · `patient-class-summary` 환자분류군 집계 · `counsel-record` 상담 기록지 | 의료법 제19조·제21조②·제23조③, 개인정보 보호법 제23조·제28조의8 (확인본) |
| `longterm-care` 노인장기요양 | `beneficiary-list` 수급자 명단 · `service-record` 급여제공기록지 · `caregiver-roster` 요양보호사 근무표 · `program-log` 프로그램 참여 일지 | 노인장기요양보험법 (**조문 확인 필요** — 미확인 표기), 개인정보 보호법 제23조·제24조 |

새 도메인은 JSON 한 장을 추가하고 `validate` 를 통과시키면 된다. 프리셋 8종 전건은 테스트가 매번 생성·검증한다.

## 공통 식별자 생성기 (프리셋 밖, 본체)

| 항목 | 생성 방식 | 실존 충돌 방지 |
|---|---|---|
| 이름 | 흔한 성 + 가상 이름 조합, **동명이인을 dup_ratio(기본 6%) 만큼 의도 삽입** | 동명이인이 biz-redact 실습·재식별 게임의 함정 재료가 된다 |
| 주민등록번호 | 생년월일·성별 자리는 맞추고 **검증자리를 일부러 틀리게** | 검증식을 통과하지 못하므로 실존 번호일 수 없다(테스트 500건 전건 확인) |
| 연락처 | `010-0000-XXXX` | 전기통신번호관리세칙상 이동전화는 `010-ABYY-YYYY`(A=2~9)라 부여될 수 없는 형식 밖 대역 |
| 주소 | `가상시 가상구 예시동 …` | 가상 지명 |
| 인정번호·코드 | 패턴(`LX########`) | `LX` 접두는 실제 인정번호 체계(L+숫자)와 겹치지 않는다 |

## 강의 교재로서

이 산출물은 요양병원 과정 **1교시 재식별 게임**(마스킹 후 `reid_keys` — 병실·등급·입원일 — 로 맞히기)과 **점검 도구 실습**(중복·누락·재원일수·장기재원)의 입력이다. 같은 강의의 `itda-data:biz-redact` 왕복 실습에도 이 데이터를 쓴다 — 동명이인·주민번호가 마스킹 함정을 만든다.

## 적용 제외 · 한계

- 항목별 분포만 닮고 항목 간 상관관계는 없다(예: 주진단과 재원일수 무관). 통계·경영 판단에 쓰지 않는다.
- docx 양식 채우기는 이번 판에 없다(`format: docx` 는 스펙에서 허용되나 산출은 xlsx/csv 로 낸다).
- hwpx 양식은 산출을 쓰기 전에 한 번 끝까지 풀어 본다 — ZIP 엔트리 500개·압축을 푼 크기 256MB 초과, 위조된 크기 정보, 경로 탐색 이름,
  XML 의 DOCTYPE 이면 exit 2 로 멈추고 아무 산출도 만들지 않는다. 정상 양식이 크기로 걸리면 `ITDA_MAX_UNZIP_MB`·`ITDA_MAX_ZIP_ENTRIES` 로 올린다.
- 프리셋의 개인정보 등급은 예측이다. 기관 내부 기준으로 `field-definitions.md` 를 고쳐 쓴다.

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 병렬 처리

여러 문서 종류(입퇴원 대장 + 근무표 + 상담 기록지)를 한 번에 만들 때는 스펙 저장 후 `generate` 를 문서별로 독립 실행할 수 있다 — 한 메시지에 복수 Bash 호출로 팬아웃하고 산출 디렉토리는 문서별로 나눈다. 자유텍스트 `fill-text` 는 문서마다 순차로.
