---
name: data-prep
description: >
  엉망인 CSV·엑셀을 진단하고 원본은 그대로 둔 채 깔끔한 정돈본을 새 파일로 만들어주는 스킬입니다. 공백·날짜·중복은 물론 대소문자 혼재(usa/USA)·깨진 인코딩(mojibake)·통화표기($1,200)까지 정제하고, 숫자에 텍스트가 섞인 열은 경고합니다. "이 엑셀 정리해줘", "제목 행이 위에 있는데 정리해줘", "소계 행 빼고 깔끔하게", "대소문자 통일해줘", "중복 제거해줘"처럼 말하면 됩니다.
  진단 → [가설] 제시 → 사용자 확인 → 정돈본 산출의 4단계로 안전하게 동작하며, cp949 한국 엑셀도 그대로 읽습니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[CSV 경로 또는 정돈 요청]"
metadata:
  author: "Chinseok"
  version: "0.2.2"
  category: "data-tidy"
  status: "experimental"
  recommended: false
  created_at: "2026-06-25"
  updated_at: "2026-07-26"
  tags: "csv, tidy, cleanup, header, subtotal, mojibake, casing, stdlib, incubating"
---

# data-prep

엉망인 CSV 를 진단해 **원본은 그대로 둔 채** 정돈본을 새 파일로 만드는 "구조 양심" 스킬.
itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask`)의 정리 담당.
(SPEC-DATA-VERTICAL-001, itda-data. 구 `data-tidy-advisor` 재구성)

`data-ask` 의 preflight 종착지 — 정돈본 경로·변환 로그·확인 ID 를 돌려준다.

---

## Claude 오케스트레이션 지시서

> [HARD] 진단→확인→산출 순서를 지킨다. "무조건"·"빠르게"로 사용자 확인을 건너뛰지 않는다.
> [HARD] 원본 파일은 절대 수정하지 않는다. 정돈본은 항상 새 파일.
> 아래 모듈 임포트 전에 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다.

### 관문1 — 진단
```python
import loader, diagnose
grid, enc = loader.read_grid(source_path)   # 원시 그리드(헤더 위치 미상이라 dict 아님)
diag = diagnose.diagnose(grid)              # header_row·subtotal_rows·empty_columns [가설]
```

### 관문2 — [가설] 카드 + 확인 요청
```python
import report
print(report.render_card(diag))        # 단정 금지, "~로 보입니다"
print(report.render_confirm(diag))
```

### 관문3 — 사용자 확인 (AskUserQuestion, 스크립트 외부)
- [HARD] 확인 없이 관문4 진행 금지. 정정이 있으면 diag 를 수정해 다시 제시.

### 관문4 — 정돈본 산출
```python
import emit
res = emit.emit_tidy(source_path, grid, diag)
# → {tidy_path, transform_log, confirmation_id, tidy_row_count, cleanse_stats}. 값 정제 자동 적용, 원본 불변·결정론.
```

### data-ask preflight 계약 (REQ-031)
`data-ask` 가 messy 를 감지하면 본 스킬을 blocking 호출하고 `tidy_path` 를 받아 재로드한다.

---

## 범위 (현재) / 범위 외
- 현재: 헤더 행 추정 · 소계/빈 행 제거 · 빈 열 제거 · 값 정제(공백·날짜·중복·mojibake 복구·대소문자 통일·통화/천단위 숫자화) · mixed-type 열 경고([가설]) · 가로 전개(wide→long melt) · 다중 표 경계 감지.
- 모든 변환은 [가설]로 제시 후 사용자 확인을 거쳐 적용한다(단정 금지).
- 범위 외: 통계 분석·질의 → `data-ask`. 원본 수정.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/data-prep}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/data-prep' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\data-prep"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

Python 3.10+ 표준 라이브러리만(설치 불요). 위 모듈들은 CLI 엔트리 없이 임포트하므로 **모듈 실행 전 `cd "$SKILL_DIR/scripts"`** 한다(Windows: `cd "$env:SKILL_DIR\scripts"`). macOS/Linux `python3`, Windows `py -3`.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | cp949·utf-8 원시 그리드 로드 |
| `diagnose.py` | 헤더·소계·빈 열 [가설] 진단 |
| `cleanse.py` | 값 정제(공백·날짜·중복·mojibake·casing·통화숫자화) |
| `wide.py` | 가로 전개 감지 + long melt |
| `tables.py` | 다중 표 경계 감지 |
| `report.py` | [가설] 카드 + 확인 요청 렌더 |
| `emit.py` | 정돈본 CSV + 변환 로그 산출(원본 불변·결정론) |
