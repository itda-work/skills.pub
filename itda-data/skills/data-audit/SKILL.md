---
name: data-audit
description: >
  엑셀·스프레드시트의 수식 오류와 흔한 실수를 훑어 위험한 셀을 짚어주는 감사 스킬입니다. #REF!·하드코드(=A1*1.05)·범위 누락(off-by-one)·복붙으로 뭉개진 수식·순환참조·깨진 시트 링크를 찾습니다. "이 시트 감사해줘", "수식 검토해줘", "수식 오류 찾아줘", "QA해줘", "복붙하다 뭐 깨졌는지 봐줘", "모델에 뭔가 이상해"처럼 말하면 됩니다.
  보고 우선(확인 없이 셀 미변경). 파일은 openpyxl 크로스플랫폼(Office 불필요).
  [책임 경계] 본 스킬은 수식 오류·실수 감사 전담 — 캐시값이 빈 파일의 재계산은 itda-data:xlsx-recalc.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, mcp__workspace__bash
argument-hint: "[xlsx 경로 또는 감사 요청]"
metadata:
  author: "Chinseok"
  version: "0.3.0"
  category: "data-tidy"
  status: "experimental"
  recommended: false
  created_at: "2026-07-07"
  updated_at: "2026-09-25"
  tags: "xlsx, audit, formula, spreadsheet, openpyxl, qa, hardcode, incubating"
---

# data-audit

엑셀 모델을 며칠 손대다 보면 `=A1*1.05`처럼 숫자를 셀에 박아둔 곳, `SUM`이 마지막 행을 빠뜨린 곳,
복붙하다 수식이 값으로 뭉개진 곳을 눈으로는 못 찾는다. 보내기 직전 합계가 미묘하게 안 맞는데
어디서 틀어졌는지 몰라 처음부터 다시 훑는 — 그 반복을 없애는 "수식 양심" 스킬.

itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask` · 감사 `data-audit`)의 감사 담당.
(#952, Claude for Excel `audit-xls` 이식 — 수식·데이터 레벨. 재무모델 무결성은 범위 외.)

---

## Claude 오케스트레이션 지시서

> [HARD] 보고 우선 — 발견을 먼저 보고하고, 셀 수정은 사용자가 명시적으로 요청할 때만 그 셀만 고친다.
> [HARD] "동작함"이 아니라 "실제로 그 셀이 틀렸나"로 판정한다(데이터 정확성 원칙). 확신이 낮은 발견은 severity를 낮추고 근거를 함께 낸다.
> 아래 모듈을 임포트해 쓸 때는 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다(CLI 로 쓰면 `python3 "$SKILL_DIR/scripts/audit.py"`).

### 관문1 — 감사 실행
```python
import audit
result = audit.audit_workbook(path, sheet=None)   # sheet=None 이면 전체 워크북(숨은 시트 포함)
```

### 관문2 — 발견 보고
```python
import report
print(report.render(result))     # Sheet·Cell·Severity·Category·Issue·Fix 테이블 + 요약 한 줄
```

### 관문3 — 수정 (사용자 확인 후에만)
- [HARD] 확인 없이 셀 변경 금지. 사용자가 특정 발견의 수정을 요청하면 **그 셀만** 고치고, 원본 백업을 남긴다.

---

## 무엇을 잡나 (수식·데이터 레벨)
| Severity | 항목 |
|---|---|
| Critical | 수식 오류(`#REF!` `#VALUE!` `#N/A` `#DIV/0!` `#NAME?`) · 깨진 시트 링크 · 순환참조 |
| Warning | 수식 내 하드코드(`=A1*1.05`) · 이웃과 다른 수식 · off-by-one 범위 · 복붙으로 값이 된 수식 · 단위/스케일 급변 |
| Info | 숨긴 행·시트(override·stale 계산 은닉 가능) |

## 이 스킬을 쓰지 않을 때
| 상황 | 대신 쓸 스킬 |
|---|---|
| openpyxl 로 만든 파일이라 수식 캐시값이 비어 있다(값 기반 검사 전 재계산) | `itda-data:xlsx-recalc` |
| 수식 구조가 아니라 합계·원장 대조로 값이 맞는지 검산 | `itda-data:data-verify` |
| 데이터로 디자인된 엑셀을 새로 만들기 | `itda-doc:xlsx-design` |

## 범위 외
- 재무모델 무결성: BS balance·cash tie-out·재무제표 3표 정합, DCF/LBO/3-statement/Merger/Comps 모델별 버그 (#952 스코프 아웃)
- Excel 애드인(Office JS)·열어둔 엑셀에 실시간 하이라이트/코멘트 — 본 스킬은 파일 기반 openpyxl.

## 정확성 한계 (openpyxl 재계산)
openpyxl은 수식을 **재계산하지 않는다**. `#REF!`·`#DIV/0!` 같은 **동적 에러 값**은 파일에 마지막 저장된 캐시값 기준으로만 읽힌다.
한 번도 Excel/LibreOffice로 열어 계산·저장된 적 없는 파일은 이 캐시가 비어 놓칠 수 있다 —
필요하면 `itda-data:xlsx-recalc` 로 재계산한 새 파일을 감사한다(LibreOffice 단독, 격리 프로필·timeout).
수식 **문자열** 기반 검사(하드코드·off-by-one·순환참조·깨진 링크·복붙)는 이 한계와 무관하게 동작한다.

## Prerequisites
**파일 감사(크로스플랫폼)**: Python 3.10+ · openpyxl (`scripts/requirements.txt`).
```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/data-audit}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/data-audit' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\data-audit"  # 미설정이면 SKILL.md 위치 절대경로 사용
```
```bash
# macOS/Linux — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/scripts/requirements.txt"
python3 "$SKILL_DIR/scripts/audit.py" <파일.xlsx>            # 사람용 테이블
python3 "$SKILL_DIR/scripts/audit.py" <파일.xlsx> --json      # 기계용 JSON

# Windows — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
py -3 "$env:SKILL_DIR\scripts\audit.py" <파일.xlsx>
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | openpyxl 수식면·값면 양면 로드(`SheetView`) |
| `checks.py` | 수식·데이터 감사 체크(오류·하드코드·불일치·off-by-one·복붙·순환·링크·단위·숨김) |
| `report.py` | 발견 테이블 + 요약 렌더(사람용/기계용) |
| `audit.py` | 감사 오케스트레이션 엔트리(보고 우선) |
