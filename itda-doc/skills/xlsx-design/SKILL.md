---
name: xlsx-design
description: >
  수치 데이터로 디자인된 Excel 통합문서(.xlsx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는 스킬입니다.
  design-core 디자인 토큰(팔레트·표 스타일·조건부서식·차트 팔레트·숫자서식)을 해석해 헤더·zebra·KPI·차트에 반영하고, 한글 셀은 안전 폰트로 보장합니다.
  "NovaTech 실적 엑셀로 만들어줘", "이 프리셋으로 대시보드 시트 디자인해줘", "데이터로 디자인된 xlsx 생성"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 디자인된 xlsx 신규 생성 전담 — 이미 있는 xlsx 의 수식 캐시값 재계산은 itda-data:xlsx-recalc.
license: Apache-2.0
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, WebFetch, AskUserQuestion, mcp__workspace__bash, mcp__workspace__web_fetch
argument-hint: "<데이터.json> [콘텐츠.md] [프리셋 또는 DESIGN.md 경로] [출력.xlsx]"
metadata:
  author: "스킬.잇다"
  version: "0.4.0"
  category: "document"
  status: "beta"
  recommended: true
  created_at: "2026-06-29"
  updated_at: "2026-09-25"
  tags: "xlsx, excel, spreadsheet, design-md, report"
---

# XLSX 디자인 생성 (xlsx-design)

수치 데이터(JSON/표)와 콘텐츠 명세를 입력받아, 디자인된 Excel 통합문서(.xlsx)를 **신규 생성**합니다. `pptx-design`·`docx-design` 의 xlsx 형제로, **design-core** 매체중립 토큰을 공유합니다(SSoT). 생성은 순수 Python(`openpyxl`)으로 수행되어 **macOS/Linux/Windows 에서 Microsoft Office 없이** 동작하며, 검증·미리보기 렌더는 Windows=Excel COM / 그 외=LibreOffice 로 처리합니다.

> **왜 이 스킬인가(#655 근거)**: 데이터만 넣은 엑셀은 평이한 표 출력에 머뭅니다. 본 스킬은 `pptx-design` 패턴을 xlsx 에 복제해 — 동일 데이터를 프리셋만 바꿔 **시각적으로 구별되는 디자인 통합문서**(헤더 fill·zebra·조건부서식·차트 팔레트)로 산출합니다.

## 백엔드

- **openpyxl(`gen.py` + `scripts/sheetkit.py`)**: 크로스플랫폼·Office 불필요. **항상 이 경로로 생성한다.**
- **수식 실계산**: openpyxl 은 수식을 계산하지 않는다(`=SUM(...)` 의 캐시값이 비어 `data_only=True` 로 `None`). 계산값이 필요하면 생성 뒤 `itda-data:xlsx-recalc` 로 재계산한다.

**비목표**: 기존 회사 .xlsx 편집·시트 보호·데이터유효성 등 기존 문서 조작, 피벗테이블·고급 조건부서식(데이터바·아이콘셋)은 본 스킬(신규 생성기)의 범위가 아니다. 기본 조건부서식은 `sheetkit.semantic_rules` 로 처리된다.

---

## 사전 준비: 의존성

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/xlsx-design}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/xlsx-design' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

# macOS/Linux — 정문(기본: openpyxl·PyYAML · `--all` 로 PyMuPDF·Pillow 까지)
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\xlsx-design"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"   # pywin32 는 마커로 Windows 에서만 설치된다
# 수동 폴백: py -3 -m pip install --user -r "$env:SKILL_DIR\requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

- **생성**(관문3)은 `openpyxl` 만으로 충분(Office·LibreOffice 불필요).
- **검증 렌더**(관문4)는 Windows=Excel COM / 그 외=LibreOffice. 없어도 HARD GATE(빈문서·토큰·한글폰트)는 정상 판정, 렌더 의존 검사만 생략(`render_unavailable` advisory).

레퍼런스:
- **디자인 프리셋 8종**: `../design-core/library/` (선택 표 `README.md`)
- **표준 DESIGN.md 차용(getdesign 75종 + 한국 확장 `../design-core/catalog/`)**: 유명 브랜드 톤이 오면 design-core getdesign-first 워크플로우(`../design-core/SKILL.md`)로 원문 획득 → 관문2 "표준 DESIGN.md 제공 시" 경로(`../design-core/schema/design-md-standard.md`)
- **토큰 → Excel 스타일 매핑**: `../design-core/mapping/xlsx.md`
- **DESIGN.md → xlsx 매핑 + 재현 카탈로그**: `references/design-md-mapping.md`
- **공개 헬퍼 API**: `scripts/sheetkit.py` · **검증기**: `scripts/verify.py` · **렌더기**: `scripts/render.py`
- **동작 예제**: `examples/sample/` (NovaTech FY2025 — data.json · gen.py, 요약·분기·리스크 3시트)

---

## Claude 오케스트레이션 지시서 ([HARD] 관문)

### 관문1 — 입력 수집
1. **수치 데이터(필수)** — JSON 또는 표. 모든 수치는 여기서 인용(손입력 금지).
2. **콘텐츠 명세(선택)** — 시트 구성·표 헤더·KPI 정의.
3. **프리셋/DESIGN.md(선택)** — 미제공이고 톤 키워드도 없으면 관문2의 톤 선택 게이트로.

### 관문2 — 디자인 시스템 해석
- **톤 신호 있음 → 바로 진행**: `../design-core/library/README.md` 에서 주제 적합 프리셋 1종 적용(IR·전략 → consulting-mbb, 데이터 리포트 → warm-editorial 등).
- **무신호 + 대화형 → [HARD] 톤 선택 게이트**: 후보 2~3종 + "알아서" 를 `AskUserQuestion` 으로.
- **무신호 + 비대화형 → 자동 폴백**: 주제 적합 프리셋 자동 선택 + 근거 한 줄.
- **토큰 적용(프리셋/v2)**: `design_core.load(<프리셋/경로>).xlsx_styles()` → 헤더 fill·zebra·차트 팔레트·조건부서식 색에 실제 hex 반영.
- **★표준 DESIGN.md(Stitch/getdesign) 제공 시**: `load()` **비대상**(원문을 깎음 — `../design-core/schema/design-md-standard.md` [HARD]). 원문을 직해석해 핵심 hex 를 `gen.py` 에 직접 인용하고, 한글 셀 안전 폰트(sheetkit)는 그대로 방어. 반복 파이프라인이면 v2 프리셋/이관(사람 확인) 후 `load()` 경로.
- **★한글 정책(xlsx 재설계)**: Excel 은 셀 단일 폰트(run/cell ascii↔eastAsia 분리 없음)라 docx 와 다르다 — **한글이 담긴 셀의 폰트를 Korean-capable(Malgun Gothic 우선)로 보장**한다. sheetkit 의 `set_cell`/`data_table` 가 셀 텍스트 언어로 자동 분기(한글=안전 고딕, 라틴/숫자=디스플레이 폰트).
- **재현 천장**: Excel 셀에 모서리 반경·그라디언트 모티프는 약함(무시). 표 스타일·숫자서식·조건부서식·차트 팔레트·freeze·열폭은 높은 재현.

### 관문3 — 생성 (`gen.py` 작성)
per-invocation `gen.py` 를 작성·실행합니다. **반드시 `scripts/sheetkit.py` 공개 API 사용**(직접 openpyxl 보일러플레이트 금지):

```python
import sys, os
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))                       # sheetkit
sys.path.insert(0, os.path.join(DESIGN_CORE, "scripts"))                      # design_core
import sheetkit as sk
import design_core as dc
from openpyxl.chart import Reference

st = dc.load("consulting-mbb").xlsx_styles()
wb = sk.new_book(); th = sk.apply_design(wb, st)
ws = wb.active; ws.title = "요약"
sk.title_block(ws, "FY2025 실적 요약", th, row=1, span=5)
sk.kpi_block(ws, 3, [("$4.82B","연간 매출"), ...], th)
dim = sk.data_table(ws, 6, headers=["사업부","매출","YoY"], rows=[...], theme=th,
                    number_formats=[None,'#,##0.00"B"','+0.0"%";-0.0"%"'])
sk.semantic_rules(ws, f"C{dim[0]}:C{dim[1]}", th)            # YoY 양수/음수 의미색
sk.add_bar_chart(ws, "사업부 매출", Reference(...), Reference(...), th, "F6")
sk.freeze(ws, "A7"); sk.set_columns(ws, [16,12,10])
sk.save_book(wb, OUT)
```

준수 사항:
- **한글 폰트(자동 가드)**: sheetkit 빌더가 한글 셀을 Korean-capable 폰트로 자동 지정.
- **색·차트 팔레트는 토큰에서만**: `st["accent"]`(헤더 fill)·`st["surface"]`(zebra)·`st["up"]/["down"]`(조건부서식)·`st["chart_palette"]`(차트).
- **표는 sheetkit `data_table`**: 헤더 fill + zebra + 테두리 + 숫자서식 자동.
- **숫자서식 필수**: 통화·퍼센트·천단위 콤마를 number_formats 로(원시 숫자 노출 금지).
- **결정론**: 난수 미사용.

### 관문4 — ★검증 게이트 [HARD — 건너뛰기 금지]
```bash
# macOS/Linux ($SKILL_DIR 는 사전 준비 절에서 확정)
python3 "$SKILL_DIR/scripts/verify.py" <생성.xlsx> --tokens tokens.txt
```

```powershell
# Windows
py -3 "$env:SKILL_DIR\scripts\verify.py" <생성.xlsx> --tokens tokens.txt
```
- **HARD GATE = (빈통합문서 + 토큰누락 + 한글_비안전폰트_셀 + 저대비) == 0**. PASS 시 exit 0.
- **토큰은 셀 값 기준** — `tokens.txt` 에는 시트명·차트 제목이 아니라 **셀에 실제 들어간 텍스트**를 적는다(토큰 게이트는 셀 값만 대조하므로 시트명을 토큰으로 넣으면 헛 FAIL).
- **한글 비안전 폰트 셀은 HARD** — 한글이 라틴 디스플레이 폰트로 박히면 의도와 다른 폴백.
- **저대비(가독성)도 HARD**(#668) — 셀 글자색 ↔ 채움색 WCAG 대비 **3.0:1 미만 FAIL**. **다크 프리셋(equity-research-dark·tech-vivid-dark·kari)은 샌드위치**(브랜드 표지 밴드 + 라이트 데이터 시트)로 렌더 — 스프레드시트 가독·인쇄를 위해 전면 다크를 피합니다(`../design-core/mapping/xlsx.md`). design-core 가 토큰을 자동 보정하므로 `title_block(fill=primary)`(표지 밴드)·`kpi_block`·강조는 그대로 안전합니다.
- advisory: 약대비(`weak_contrast` 3.0~4.5)·스타일 헤더 0개·차트 0개·빈 페이지·렌더 불가.
- **FAIL 시**: `_verify/<stem>.json` 확인 → `gen.py` 수정 → 재생성·재검증.
- **시각 QA**: 렌더 PNG(`_verify/<stem>_render/*.png`)를 Read 로 직접 확인(열 잘림·숫자서식·차트 색).

### 관문5 — 산출
1. **XLSX** 경로 · 2. **렌더 미리보기** PNG · 3. **검증 요약**(HARD GATE·적용 프리셋·팔레트 hex·재현 한계).

---

## 검증 도구 빠른 참조

| 도구 | 역할 | 호출 |
|---|---|---|
| `$SKILL_DIR/scripts/sheetkit.py` | 공개 헬퍼 API | `import sheetkit as sk` |
| `scripts/verify.py` | 빈문서/토큰/한글폰트/구조/렌더 + HARD GATE | `python3 "$SKILL_DIR/scripts/verify.py" <xlsx> [--tokens t.txt] [--no-render]` (Win: `py -3 "$env:SKILL_DIR\scripts\verify.py" …`) |
| `scripts/render.py` | Excel COM(Win)/LibreOffice 렌더 → PDF → PNG | `python3 "$SKILL_DIR/scripts/render.py" <xlsx> [out_dir] [--dpi N]` (Win: `py -3 "$env:SKILL_DIR\scripts\render.py" …`) |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 이미 만든 xlsx 의 수식 계산값이 비어 다른 도구에서 빈칸으로 보인다 | `itda-data:xlsx-recalc` |
| 기존 엑셀의 수식 오류·하드코드를 감사 | `itda-data:data-audit` |

## 에러 처리

| 상황 | 대응 |
|---|---|
| `openpyxl` 미설치 | `requirements.txt` 로 설치 |
| 렌더 도구 부재 | 생성은 가능, 렌더만 생략(advisory). 검증 공백 분리 보고 |
| 한글 비안전 폰트(HARD FAIL) | sheetkit 빌더 사용 확인 또는 `set_cell(..., kr=sk.kr_font_name())` → 재검증 |
| 수식 실계산 요청 | 생성 뒤 `itda-data:xlsx-recalc` 로 재계산 |
| 피벗/고급 CF 요청 | 본 스킬 비목표 — 생성한 .xlsx 를 Excel 에서 열어 직접 추가하도록 안내 |
| 기존 회사 xlsx 편집/시트 보호/데이터유효성 | 본 스킬(신규 생성기) 비목표 |
