# 매체 매핑 — design-core v2 → PPTX (pptx-design 어댑터)

design-core 의 매체 중립 토큰을 PPTX 산출물로 옮기는 어댑터 매핑이다. **렌더 구현·CJK 가드·재현 한계의 SSoT 는 `pptx-design` 스킬**이며(특히 `references/design-md-mapping.md` 의 "토큰 → pptx 3열 필터" + `references/pptx-toolkit.md`), 본 문서는 그 진입점과 v2 토큰 ↔ deckkit API 대응만 정리한다(중복 회피).

## 진입점

```python
import sys; sys.path.insert(0, "../design-core/scripts")  # 형제 스킬
import design_core as dc

tokens = dc.load("consulting-mbb")     # 또는 경로/이름/DESIGN.md 텍스트
pal = tokens.pptx_palette()            # deckkit 호환 평면 hex
# pal == {canvas, surface, ink, muted, primary, accent, hairline, up, down}
lay = tokens.pptx_layout()             # three_zone/grid/space → 좌표 헬퍼 입력 (P0, #701)
# lay == {margin_in, gap_in, three_zone{header,content,footer}, grid{columns,gutter}}
```

`pptx_palette()` 는 v2 `color.*`+`semantic.*` 을 **이주 전 프리셋의 `colors.*` 와 1:1 동치**로 역매핑한다(SPEC AC-02 회귀 보증). 기존 `gallery/*/build.py` 가 쓰던 hex 평면과 동일하므로, 생성 스크립트는 hex 를 그대로 `dk.set_bg`·`dk.rect(fill=)`·`dk.add_native_chart(palette=[...])` 에 넘긴다.

## v2 토큰 → deckkit API

| v2 토큰 | deckkit(`dk`) 적용 | 비고 |
|---|---|---|
| `color.bg` | `dk.set_bg(slide, hex)` | 슬라이드 배경 |
| `color.surface`/`border` | `dk.rect(fill=, line=)` | 카드·헤어라인 |
| `color.fg`/`muted`/`primary`/`accent` | `dk.set_run_font(color=)` | 텍스트·강조 |
| `semantic.up`/`down` | 수치 강조 색 | `convention` 에 따라 의미 부여 |
| `font.display` | `dk.set_run_font(name=)` (라틴 run) | 한글 run 은 가드가 `kr_font_name()` 강제 |
| `font.body` (`kr-safe-gothic`) | `dk.kr_font_name()` | 본문 한글 안전 고딕 |
| `radius.base` | `dk.rect(radius=비율)` | pill=0.5 근사 |
| `space.{margin,gap}` | `to_pptx_layout()→margin_in/gap_in` | 여백·요소 간격(인치) |
| `layout.three_zone` | `dk.zone_bounds(h_in, three_zone, margin_in)` | 헤더/본문/푸터 비율 분할 — **토큰 실소비**(P0, #701) |
| `layout.grid` | `dk.grid_cells(x,y,w,h,cols,rows,gutter)` | 본문 균일 그리드 셀 — **토큰 실소비**(P0, #701) |
| `motif` | 도형 + Pillow PNG | `linear_gradient`/`radial_glow` |
| `constraints.pptx.cjk_guard` | `dk.set_run_font` 한글 가드 활성 | 음수 자간→0, 세리프/thin 한글 필터 |
| `constraints.pptx.gradient: pillow-bake` | Pillow 고해상도 PNG 베이크 | 네이티브 그라디언트 미지원 |

## constraints.pptx 해석

`design_core` 는 프리셋에 `constraints.pptx` 가 없으면 기본 프로필(`cjk_guard:true`, `gradient:pillow-bake`, `motion:unsupported`, `opentype:unsupported`, `fallback_fonts.korean:[Noto Sans KR, Pretendard]`)을 주입한다. deckkit 의 한글 가드는 이 프로필과 **동일 동작**을 이미 구현하고 있으므로(REQ-007 비퇴행), 어댑터는 프로필을 "계약 명세"로 읽고 deckkit 가드가 집행한다.

## 재현 한계

색·레이아웃·평면 기하는 80~88% 재현, 폰트·사진·모션은 한계 — 상세 카탈로그와 우회책은 `pptx-design/references/design-md-mapping.md` §2 를 따른다. 본 어댑터는 그 한계를 바꾸지 않는다.
