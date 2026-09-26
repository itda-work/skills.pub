# design-core 토큰 → XLSX 매핑 가이드

design-core 매체중립 토큰을 Excel 통합문서로 옮기는 방법과 재현 한계. 진입점·토큰↔스타일 SSoT 는 `../../design-core/mapping/xlsx.md`, 코드 SSoT 는 `../scripts/sheetkit.py`.

> **천장 규칙**: 정체성이 **색·표 스타일·조건부서식·차트 팔레트·숫자서식**에 살면 높은 재현. **모서리 반경·그라디언트·모티프**는 셀 매체의 천장. 한글 리스크는 docx 의 eastAsia 미바인딩과 달리 **한글 셀이 라틴 폰트로 박히는 것**(셀 단일 폰트).

## 1. 토큰 → Excel 표현

| 토큰 | sheetkit | Excel |
|---|---|---|
| `color.fg` | `set_cell(color=)` | `Font(color=)` |
| `color.primary` | 제목·강조 | 제목 `Font` |
| `color.accent` | `styled_header`/`data_table` 헤더 fill | `PatternFill` |
| `color.surface` | zebra(짝수행) | `PatternFill` |
| `color.muted` | 캡션·단위 | 회색 `Font` |
| `color.border` | 표 테두리 | `Border(thin)` |
| `semantic.up/down` | `semantic_rules` 조건부서식 | `CellIsRule(font=)` |
| `font.display` | 라틴/숫자 셀 | `Font(name=)` |
| `font.body`+`korean_fallbacks` | 한글 셀 | `Font(name=Korean-capable)` |
| `chart_palette` | `add_bar_chart`/`add_line_chart` | series `solidFill` |
| `type_scale` | 폰트 pt | `Font(size=)` |
| number format | `data_table(number_formats=)` | 셀 `number_format` |
| `radius`/`motif`/gradient | — | ▣ 셀 표현 약함(필터) |

## 2. 한글 폰트 가드 (xlsx 재설계)

Excel 셀은 단일 폰트라 docx 의 `w:rFonts` ascii↔eastAsia 분리가 없다. sheetkit 은 셀 텍스트에 한글이 있으면 폰트를 `kr_font_name()`(Malgun Gothic 우선)로, 아니면 디스플레이 폰트로 분기한다. `verify.py` 의 (C) 가 한글 셀의 라틴 폰트(`Calibri`·`Helvetica Neue` 등)를 **HARD** 로 적발한다.

실증(2026-06-29, #662 P5): NovaTech 동일 데이터를 4 프리셋으로 생성 → 4종 모두 한글 셀 27개 Korean-capable·HARD GATE PASS, 헤더 fill·zebra·조건부서식(YoY 의미색)·차트 팔레트가 프리셋별로 시각 구별.

## 3. 재현 잘됨 vs 한계

**잘됨**: 표 스타일(헤더 fill·zebra·테두리)·숫자서식·조건부서식(의미색)·차트 팔레트·freeze panes·열폭.
**한계**: 모서리 반경·그라디언트·모티프(무시); eastAsia 분리 타이포(셀 단일 폰트라 Korean-capable 단일 폰트로 통일); 수식 계산(openpyxl 비계산 — 값만, 계산은 `itda-data:xlsx-recalc`).
