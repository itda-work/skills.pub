---
name: meeting-reliability
description: >
  회의 녹취·기록에서 "확인 / 확인 필요 / 예외"를 근거와 함께 정확히 가르는 신뢰성 검수 스킬입니다.
  "이 녹취 결정사항 표로 정리해줘", "회의록 신뢰성 검수해줘", "누가 뭘 언제까지 하기로 했는지 근거까지 보여줘"처럼 말하면 됩니다.
  담당 단정·추정 날짜·잡담을 코드 게이트로 차단하고, 각 행을 원문 발화에 연결한 HTML(근거 tooltip)로 출력합니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, mcp__workspace__bash
argument-hint: "[회의 녹취 파일 경로 또는 텍스트]"
metadata:
  author: "Chinseok"
  version: "0.1.5"
  category: "audit"
  status: "alpha"
  recommended: false
  created_at: "2026-06-21"
  updated_at: "2026-09-30"
  tags: "audit, reliability, meeting, transcript, verification, hallucination-guard, stdlib"
---

# meeting-reliability

회의 raw 녹취를 **신뢰성 검수 표**로 바꾼다. "정리"가 아니라 **검수**가 본질 —
확정/미정/확인필요를 근거와 함께 가르고, 원문에 없는 담당·날짜는 단정하지 않는다.
감사 신뢰성 엔진의 **레퍼런스 구현**(코어 5규칙은 타깃 비종속, 회의는 첫 타깃).

외부 라이브러리 없음(stdlib only), 인증키 없음. 산출은 단일 자족 HTML(근거 tooltip).

## 언제 쓰나

- "이 녹취/회의록에서 결정사항·담당·기한을 표로" — 단, **신뢰성**(근거·추정 차단)이 필요할 때
- 자동 받아쓰기(raw)처럼 잡담·과정값·발언자≠담당 혼선이 섞인 입력일수록 가치가 크다
- 단순 서술 정리·보고서화는 `itda-doc:draft-post`(작성)가 담당 — 본 스킬은 검수

## 코어 5규칙 (검수 원칙)

1. **근거 강제** — 각 행은 실재하는 원문 발화(인덱스)를 가리킨다. 가리킬 게 없으면 그 행은 환각이다.
2. **`확인 필요`의 over-hedge 균형** — 원문에 없으면 `확인 필요`/미표기, 발화로 분명하면 단정. (둘 다 안티패턴: "주최자로 기본값" 추정 채움 ↔ 과잉 `확인 필요`)
3. **결정 vs 후속 실무 분리, 확정 vs 미정 구분** — 한 항목에 결정과 실행이 섞이면 2행으로 나눈다.
4. **잡담·과정값 제거** — 점심·회의실 예약 같은 잡담, 바뀌기 전 안(출시일 "2월 말"→"3월 2일")은 넣지 않는다. 최종/확정만.
5. **선택적 심층검토(deep)** — 고신뢰 산출엔 다관점 비판→재검증. **원문에 없는 값은 추정하지 않는다**(날짜 환산·의존성 추정 기각).

## 격리 워커 위임 (대량 녹취 오염 차단)

회의 녹취 전문은 본 대화를 오염시키는 대량 raw 다. 환경에 서브에이전트
**`itda-research:meeting-reliability-worker`** 가 있으면, Lead 는 녹취를 본 컨텍스트로
들이지 말고 **녹취 파일 경로를 세션 폴더에 준비해 워커에게 명시 디스패치**한다. 워커는
격리된 컨텍스트에서 아래 워크플로우(추출 → selfcheck 게이트 → HTML)를 그대로 수행하고,
지정 출력 디렉토리에 `result.json` 과 자족 HTML 을 남긴 뒤 **HTML 경로 · 게이트 PASS/FAIL ·
행 수 · 사람 검토 필요 여부**만 반환한다. Lead 는 그 포인터만 사용자에게 인계한다(표
전문·원문은 본 대화로 돌아오지 않는다). 워커의 입력·출력·에러 계약은
`agents/meeting-reliability-worker.md` 가 정본이다.

- **명시 디스패치 전용** — 일반 "회의록 정리" 발화에 자동 위임하지 않는다. meeting-reliability
  로 신뢰성 검수를 진행할 때 Lead 가 이름을 지목해 호출한다.
- **폴백** — 워커가 없는 환경(예: 서브에이전트 미지원)에서는 아래 워크플로우를 **본
  컨텍스트에서 직접** 수행한다. 게이트·재작성 상한·산출 계약은 위임/폴백 어느 쪽이든 동일하다.

## 워크플로우

입력은 텍스트 녹취 파일(`transcript.md`). 음성은 먼저 텍스트로 받아써서 넣는다(이 저장소에 받아쓰기 스킬은 없다).

### 0) 스킬 디렉토리(SKILL_DIR) 확정

스킬 스크립트는 cwd 에 의존하지 않도록 **절대경로**로 실행한다. 아래 명령을 먼저 한 번 돌려 `SKILL_DIR` 을 확정하고, 이후 모든 스크립트를 `"$SKILL_DIR/scripts/..."` 로 실행한다:

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
printf "%s\n" "$c"' _ meeting-reliability itda-research "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

### 1) 발화 번호 확인 (근거 인덱스)

```bash
python3 "$SKILL_DIR/scripts/meeting_adapter.py" transcript.md
```

`idx⇥speaker⇥text`로 번호 매긴 발화가 나온다. 각 행의 `evidence`는 이 **idx**로 적는다.

### 2) 구조화 결과(JSON) 작성 — 5규칙 적용

`result.json`을 다음 스키마로 만든다(에이전트가 녹취를 읽고 5규칙에 따라 채운다):

```json
{
  "title": "회의 제목",
  "rows": [
    {
      "item": "신제품 A 출시일",
      "category": "결정",            // 결정 | 실무 | 리스크
      "status": "확정",              // 확정 | 미정 | 확인필요
      "owner": null,                  // 원문에 담당 발화 없으면 null 또는 "확인 필요" (단정 금지)
      "due": "3월 2일",               // 상대표현("다음 주까지")은 캘린더 환산 없이 그대로
      "evidence": [13, 47],           // 1)에서 본 발화 idx (필수, ≥1)
      "basis": "김팀장 '출시는 3월 2일로 확정'. 출시 주체 발화 없음 → 담당 미표기.",
      "risk_note": "품질점검 2/20 미달 시 재검토 가능"   // 없으면 null
    }
  ]
}
```

규칙 매핑: owner는 발화로 분명할 때만 단정(R2) · 결정/실무는 별 행(R3) · 잡담/과정값 행 금지(R4) · 모든 행에 evidence(R1).

### 3) 게이트 — selfcheck (필수)

```bash
python3 "$SKILL_DIR/scripts/selfcheck.py" result.json transcript.md
```

`PASS`(exit 0)면 통과. `FAIL`이면 위반(담당 단정·추정 날짜·잡담·근거 누락·결정/실무 병합)을 보고하니 **그 행을 고쳐 재작성**한다. 추정으로 칸을 채우지 말 것 — 모르면 `확인 필요`. 재작성은 **최대 3회**(`MAX_REWRITES`), 초과 시 사람 검토로 넘긴다(자동 보정 금지).

### 4) 출력 — HTML(근거 tooltip)

```bash
python3 "$SKILL_DIR/scripts/render_html.py" result.json transcript.md meeting_reliability.html
```

각 행의 `📎 근거`에 hover하면 **원문 발화 + 앞뒤 대화 맥락(±2) + 판정 근거**가 보인다(감사 drill-to-source). 단일 자족 HTML(외부 의존 0). 산출 후 사용자에게 제시한다.

## 모드

- **basic** — 5규칙으로 1회 작성 + selfcheck 통과(★). 입문·일상 회의록은 이걸로 충분.
- **deep** — basic 후 다관점 비판: over-hedge 교정(발화로 분명한 담당을 과잉 `확인 필요`로 빼지 않기), 숨은 리스크 의존 연결(예: 경쟁사 동시기 출시 ↔ 확정 출시일 충돌), 조건부 확정 정직 표기. **원문에 없는 값 추정은 deep에서도 기각**.

## 경계 / 비범위

- 음성→텍스트(STT): 범위 밖(받아쓰기 스킬 없음). 입력은 텍스트.
- 서술형 회의록 작성·보고서화: `itda-doc:draft-post`. 본 스킬은 검수(변환+verify).
- 전표·계약 검수, 통제 테스트, 감사 컨설팅: 후속(SPEC-AUDIT-RELIABILITY-002+). 코어 5규칙은 재사용, 어댑터만 교체.

## 골든 회귀

`tests/` — 부록 A 골든(raw 녹취 fixture + ③ 기대출력 + ★ assertion). `python3 -m pytest tests`로 검증. 자세한 계약은 `SPEC-AUDIT-RELIABILITY-001`.
