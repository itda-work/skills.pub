# 매체 매핑 — design-core v2 → XLSX (xlsx-design 어댑터)

design-core 매체중립 토큰을 Excel 통합문서(.xlsx)로 옮기는 어댑터 매핑이다. **렌더 구현·한글 폰트 가드·재현 한계의 SSoT 는 `xlsx-design` 스킬**(`scripts/sheetkit.py` + `references/design-md-mapping.md`)이며, 본 문서는 진입점과 v2 토큰 ↔ sheetkit 스타일 대응만 정리한다.

> **docx 와의 차이**: docx 는 run 레벨에서 `w:rFonts` ascii/hAnsi ↔ eastAsia 를 분리 바인딩한다. Excel 은 **셀(또는 rich-text run) 폰트가 단일 이름**이라 그런 분리가 없다 — eastAsia 분리는 테마(major/minor)에서만 일어난다. 따라서 xlsx 의 한글 정책은 **한글이 담긴 셀의 폰트를 Korean-capable 폰트(Malgun Gothic 우선)로 보장**하는 것이다.

## 진입점

```python
import sys; sys.path.insert(0, "../design-core/scripts")
import design_core as dc

tokens = dc.load("consulting-mbb")
st = tokens.xlsx_styles()
# st == {page_bg, ink, muted, primary, primary_text, accent, surface, surface_2, border,
#        up, down, is_dark, convention, latin_font, body_font, korean_fallbacks,
#        kr_font_guard, chart_palette, type_scale}
```

색은 `#RRGGBB` 로 넘기고(sheetkit 이 openpyxl ARGB `FFRRGGBB` 로 변환), 한글 폰트는 후보 리스트(`korean_fallbacks`)만 넘긴다 — sheetkit 의 `kr_font_name()` 이 환경에서 첫 존재 폰트를 선택.

**텍스트 토큰 vs fill 토큰** — docx 와 동형: `ink·muted·primary_text·up·down` 은 라이트 시트 위 **텍스트색**이라 어댑터가 가독 대비로 보정해 내보내고(라이트 프리셋 무변경), `primary·accent` 는 **fill**(제목 밴드·헤더) 용 브랜드 원본으로 글자색은 `sheetkit.on_color()` 가 자동 선택한다. **`chart_palette` 는 보정 전 원본(비비드) 색** — 흰 배경 위 차트 시리즈가 또렷해야 하므로 텍스트 보정과 분리한다. `is_dark` 는 다크 프리셋 여부.

## v2 토큰 → sheetkit / Excel 표현

| v2 토큰 → `st` 키 | sheetkit 적용 | Excel 표현 |
|---|---|---|
| `color.bg` → `page_bg` | (식별용) 다크 프리셋 셀 잉크 원천 | 기본 시트는 라이트. `page_bg` 는 캔버스 식별값 |
| `color.fg` → `ink`(보정) | 본문 셀 글자색 | `Font(color=)`(라이트 시트 대비 보정) |
| `color.primary` → `primary` | 제목 밴드·헤더 **fill** | `PatternFill`(글자색은 `on_color`) |
| (파생) → `primary_text` | 제목 텍스트·KPI 값·시트 강조 | 라이트 시트 위 가독 브랜드색(보정) |
| `color.accent` → `accent` | 표 헤더 fill | 헤더행 `PatternFill` |
| `color.surface`/`surface_2` → `surface`/`surface_2` | zebra(짝수행)·KPI 카드 | 행 `PatternFill`(다크 프리셋은 라이트 틴트) |
| `color.muted` → `muted`(보정) | 캡션·주석·단위 라벨 | 작은 회색 `Font`(대비 보정) |
| `color.border` → `border` | 표 테두리·헤어라인 | `Border`(thin) |
| `semantic.up`/`down` → `up`/`down`(보정) | 수치 강조·조건부서식 | `Font(color=)`·`CellIsRule` |
| `font.display` (`latin_font`) | 제목·헤더 라틴 | `Font(name=)` (라틴 텍스트) |
| `font.body` + `korean_fallbacks` | 데이터 셀 폰트 | 한글 셀 = `kr_font_name()` Korean-capable |
| `chart_palette` | 차트 시리즈 색 | `Series` graphicalProperties solidFill |
| `type_scale` | 제목/헤더/본문 pt | `Font(size=)` |
| `convention` | up/down 의미 매핑 | 조건부서식 색 방향 |
| `radius` / `motif` / gradient | — | ▣ Excel 셀에 반경·그라디언트 모티프 개념 약함(필터) |

## 다크 프리셋 표현 정책 — **샌드위치** (#668)

다크 프리셋(equity-research-dark·tech-vivid-dark·kari)은 xlsx 에서 **제목 밴드·헤더만 브랜드 다크/액센트, 데이터 본문은 라이트 시트("샌드위치")** 로 렌더한다(docx 와 동일 정책). 스프레드시트는 데이터 작업 표면이라 전면 다크 시트는 가독·인쇄 모두 불리하므로 **샌드위치를 기본**으로 한다(전면 다크 셀 채움은 openpyxl 로 기술적으로 가능하나 채택하지 않음).

- **정체성 표현**: 표지 제목 **밴드**(`title_block(fill=primary)` → `on_color` 자동 글자색) + 브랜드색 표 헤더(`styled_header` accent fill) + **비비드 `chart_palette`**.
- **본문 가독**: 어댑터(`_sandwich_palette`, docx 와 공용)가 `ink=캔버스(bg)`(근-검정 + 브랜드 색조), `muted/primary_text/up/down` 을 라이트 대비로 보정, `surface`(zebra) 를 라이트 브랜드 틴트로 낮춘다. 프리셋 이름 분기 없이 `is_dark` 휘도 판정으로 자동.
- **강제선**: `xlsx-design/scripts/verify.py` 대비 게이트(F)가 셀 글자색 ↔ 채움색 WCAG 대비를 측정해 **3.0:1 미만 HARD FAIL**. 조건부서식(up/down)은 렌더 시 Excel 이 적용하므로 정적 셀은 `ink` 가독을 유지(거짓양성 없음).

## 한글 폰트 가드 계약 (`constraints.xlsx`)

`design_core` 가 프리셋에 주입하는 기본 프로필:

```yaml
kr_font_guard: true     # 한글 셀 → Korean-capable 폰트 보장
thousands: true         # 천단위 콤마 숫자서식 기본
fallback_fonts:
  korean: [Malgun Gothic, 맑은 고딕, Noto Sans KR, Pretendard]
```

sheetkit 의 `set_cell`/`styled_header`/`data_table` 가 한글 텍스트를 만나면 셀 `Font.name` 을 `kr_font_name()`(후보 중 첫 존재 폰트)로 지정한다. `verify.py` 는 한글 셀이 비-Korean-capable 폰트(라틴 디스플레이)로 박혔는지 적발한다.

## 재현 한계 (xlsx 매체)

- **표 스타일(헤더 fill·zebra·테두리)·숫자서식·조건부서식·차트 팔레트·freeze panes·열폭**: 높은 재현(스프레드시트의 본령).
- **모서리 반경·그라디언트·모티프**: Excel 셀 표현 약함(무시/필터).
- **eastAsia 분리 타이포**: 셀 단일 폰트라 docx 처럼 "라틴 세리프 + 한글 고딕" 동일 셀 혼합은 불가 — Korean-capable 단일 폰트로 통일.
- 상세는 `../../xlsx-design/references/design-md-mapping.md`.
