---
name: data-verify
description: >
  엑셀·CSV의 숫자가 실제로 맞는지 검수하는 스킬입니다. 부분합↔총계 불일치·원장 대조·음수/범위/중복 규칙 위반·시트 간 값 어긋남을 찾아 "이 숫자 틀렸어요"를 근거(기대값 vs 실제값 vs 차이)와 함께 짚습니다. "이 수치 맞는지 검수해줘", "합계 검산해줘", "원장이랑 대조해줘", "이 값들 검산해줘", "숫자 이상 없는지 봐줘"처럼 말하면 됩니다.
  보고 전용 — 확인 없이 값을 바꾸지 않습니다. 파일 검수는 openpyxl 크로스플랫폼(Office 불필요).
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, mcp__workspace__bash
argument-hint: "[xlsx/csv 경로 또는 검수 요청]"
metadata:
  author: "Chinseok"
  version: "0.3.0"
  category: "data-tidy"
  status: "experimental"
  recommended: false
  created_at: "2026-07-07"
  updated_at: "2026-09-25"
  tags: "verify, reconcile, numbers, spreadsheet, openpyxl, integrity, incubating"
---

# data-verify

엑셀에 숫자를 정리해놨는데 — 부분합이 총계랑 미묘하게 안 맞고, 집계값이 원장이랑 다르고,
음수가 나오면 안 되는 칸에 음수가 있고, 두 시트에서 같아야 할 값이 어긋나 있다. 보고서 내기
직전 "이 숫자들 진짜 맞나?"가 불안한데 대조할 시간이 없어 그냥 믿고 내는 — 그 불안을 없애는
"수치 양심" 스킬.

itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask` · 수식감사 `data-audit` ·
수치검수 `data-verify`)의 값 검수 담당. (#967)

`data-audit` 이 "수식이 옳게 짜였나"라면, `data-verify` 는 "값이 실제로 맞나"를 본다.

---

## Claude 오케스트레이션 지시서

> [HARD] 보고 전용 — 검수 결과를 먼저 보고하고, 값 수정은 사용자가 명시적으로 요청할 때만.
> [HARD] plausible ≠ correct — 허용오차를 명시하고 눈대중 금지(data-accuracy). 차이는 항상 수치로 제시한다.
> 아래 모듈을 임포트해 쓸 때는 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다(CLI 로 쓰면 `python3 "$SKILL_DIR/scripts/verify.py"`).

### 관문1 — 검수 설정 구성
자동 가능한 **내부정합** 외에는 대조 기준(원장·규칙·짝)이 필요하다. 사용자와 함께 config 를 구성한다:
```python
config = {
  "sheet": "Sheet1",                                  # 대상 시트(기본: 첫 시트)
  "internal": {"tolerance": 0.01},                    # 소계/총계 ↔ 구성요소 합 (자동 감지)
  "rules": {"non_negative": ["금액"], "unique": ["ID"],
            "range": {"비율": [0, 100]}, "sum_to": {"비중": 100}},
  "external": {"key": "코드", "value": "금액",
               "reference": {"A001": 1000, "A002": 2000}},   # 원장 정답셋
  "cross": [{"a": ["요약", "B2"], "b": ["상세", "합계"]}],     # 시트 간 같아야 할 값
}
```

### 관문2 — 검수 실행
```python
import verify
result = verify.verify_workbook(path, config)   # 원본 불변, 순수 판정
```

### 관문3 — 보고
```python
import report
print(report.render(result))     # 항목·위치·기대값·실제값·차이·심각도 테이블 + 요약
```

### 관문4 — 수정 (사용자 확인 후에만)
- [HARD] 확인 없이 값 변경 금지. 사용자가 특정 발견의 수정을 요청하면 그 셀만 고친다.

---

## 무엇을 잡나 (값 정확성 4종)
| 종류 | 무엇을 대조 | 기준 |
|---|---|---|
| **내부 정합** | 소계/총계 ↔ 구성요소 합 | 자동 감지(합계 라벨) + 허용오차 |
| **규칙 위반** | 음수 불가·범위·중복 키·합계 목표 | `rules` config |
| **외부 대조** | 집계값 ↔ 원장/원천 정답셋 | `external.reference` |
| **교차 참조** | 시트 간/파일 간 같아야 할 값 | `cross` 짝 |

심각도: **Critical**(정합 깨짐·원장 불일치) · **Warning**(규칙 위반·범위) · **Info**(참고).

## 독립 검수 — 권장 체인 (data-auditor)

이 스킬이 낸 검수 결과를 **같은 세션이 다시 믿지 않게** 하려면 읽기 전용 감사자에게 넘긴다:

```
data-verify(검수 보고) → itda-data:data-auditor(원장·원 셀 독립 재계산, AUDIT_SCHEMA JSON)
```

`Agent` 도구로 `itda-data:data-auditor` 를 명시 디스패치한다(자동 위임은 발동하지 않는다). 프롬프트에
**검수 대상 산출물 경로 + 원장 경로**(없으면 원장 대조 축이 `unverifiable` 로 남는다)를 넘기고, 반환된
JSON 의 `verdict` 를 필드로 읽는다 — critical 1건이면 `FAIL` 이고 `unverifiable` 이 비어 있지 않으면
`PASS` 가 아니다. 감사자는 파일을 고치지 않으며 `outputs/data-audit-report.md` 1개만 쓴다
(계약: `cowork-agent-orchestration.md` §감사자). 에이전트 타입이 없는 환경이면 general-purpose
서브에이전트에 `agents/data-auditor.md` 지시서를 먼저 읽고 따르라고 명시한다.

## 범위 외
- 수식 구조·오류 감사(#REF!·하드코드 등) → `data-audit`
- 재무모델 무결성(BS balance·DCF/LBO) → 범위 밖
- 수식 감사 → `data-audit`. 캐시값이 빈 파일의 수식 재계산 → `itda-data:xlsx-recalc`.
- 열어둔 엑셀에 실시간 하이라이트/코멘트 — 본 스킬은 파일 기반 openpyxl.

## 정확성 원칙 (data-accuracy)
- 부동소수점 비교는 **허용오차**(`tolerance`, 기본 0.01)로 — 눈대중·정확한 `==` 금지.
- 통화/천단위/`%` 표기는 숫자로 파싱해 비교(`$1,200`→1200, `45%`→45 — 기호만 제거해 `45+55=100` 검산이 자연스럽게).
- "동작함"이 아니라 "값이 실제와 일치함"으로 판정. 표본·눈대중 금지.

## Prerequisites
**파일 경로(크로스플랫폼)**: Python 3.10+ · openpyxl (`scripts/requirements.txt`).
```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/data-verify}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/data-verify' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\data-verify"  # 미설정이면 SKILL.md 위치 절대경로 사용
```
```bash
# macOS/Linux — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/scripts/requirements.txt"
python3 "$SKILL_DIR/scripts/verify.py" <파일.xlsx> --config config.json
# Windows — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
py -3 "$env:SKILL_DIR\scripts\verify.py" <파일.xlsx> --config config.json
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | openpyxl 값 grid 로드(시트별). **백엔드 독립** 인터페이스 |
| `verifiers.py` | 내부정합·규칙위반·외부대조·교차참조 순수 판정 함수 |
| `report.py` | 발견 테이블 + 요약 렌더 |
| `verify.py` | 검수 오케스트레이션 엔트리(보고 전용) |
