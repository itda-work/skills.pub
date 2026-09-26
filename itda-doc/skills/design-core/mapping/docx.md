# 매체 매핑 — design-core v2 → DOCX (docx-design 어댑터)

design-core 의 매체 중립 토큰을 Word 문서(.docx) 산출물로 옮기는 어댑터 매핑이다. **렌더 구현·한글 East Asian 바인딩·재현 한계의 SSoT 는 `docx-design` 스킬**이며(`scripts/dockit.py` + `references/design-md-mapping.md`), 본 문서는 그 진입점과 v2 토큰 ↔ dockit 스타일 대응만 정리한다(중복 회피).

> **pptx 와의 핵심 차이**: pptx 는 16:9 캔버스에 **절대좌표**로 도형을 쌓고 LibreOffice 의 한글 세리프 폴백을 가드로 막는다. docx 는 **흐름(flow) 문서** — 단락·헤딩·표·헤더/푸터가 페이지를 따라 흐르고, Word 가 한글을 **네이티브로 정상 렌더**한다. 따라서 docx 어댑터의 한글 관심사는 "음수 자간 클램프"가 아니라 **run 의 `w:rFonts` 를 라틴(ascii/hAnsi) ↔ 한글(eastAsia)로 분리 바인딩**하는 정확성이다(SPEC-OFFICE-DOC-GEN-DEEPEN-001 결정: "docx 맥락 재설계").

## 진입점

```python
import sys; sys.path.insert(0, "../design-core/scripts")  # 형제 스킬
import design_core as dc

tokens = dc.load("consulting-mbb")     # 또는 경로/이름/DESIGN.md 텍스트
st = tokens.docx_styles()              # dockit 호환 평면 스타일
# st == {page_bg, ink, muted, primary, primary_text, accent, surface, surface_2, border,
#        up, down, is_dark, convention, latin_font, body_font, korean_fallbacks,
#        eastasia_guard, margin_in, gap_in, type_scale, page_size}
```

`docx_styles()` 는 색을 `#RRGGBB` 로 넘기고(dockit 이 `RGBColor.from_string` 으로 변환), 한글 폰트는 실제 이름을 고정하지 않고 **`korean_fallbacks` 후보 리스트**만 넘긴다 — 어댑터(`dockit.kr_font_name()`)가 환경에서 첫 존재 폰트를 선택한다(매체 중립 경계 유지).

**텍스트 토큰 vs fill 토큰 구분** — `ink·muted·primary_text·up·down` 은 **라이트 본문 위 텍스트색**이라 어댑터가 흰 배경(정확히는 가장 어두운 라이트 패널 `surface_2`) 대비로 가독성을 보정해 내보낸다(라이트 프리셋은 이미 충족 → 무변경). `primary·accent` 는 **fill(표지 밴드·헤더·액센트 바)** 용 브랜드 원본이고, 그 위 글자색은 `dockit.on_color()` 가 명도로 자동 선택한다. `is_dark` 는 다크 프리셋 여부(아래 샌드위치 정책 분기용).

## v2 토큰 → dockit / Word 스타일

| v2 토큰 → `st` 키 | dockit 적용 | Word 표현 |
|---|---|---|
| `color.bg` → `page_bg` | (식별용) 다크 프리셋 본문 잉크 원천 | 본문 페이지는 항상 흰색(아래 정책). `page_bg` 는 캔버스 식별값일 뿐 |
| `color.fg` → `ink`(보정) | `Normal` 스타일 글자색 | 본문 run 색(라이트 배경 대비 보정) |
| `color.primary` → `primary` | 표지/클로징 밴드·헤더 **fill** | `w:shd` 채움(글자색은 `on_color`) |
| (파생) → `primary_text` | 헤딩 스타일 색(`Heading 1/2`)·KPI 값·강조 텍스트 | 라이트 본문 위 가독 브랜드색(보정) |
| `color.accent` → `accent` | 표 헤더 fill·킥커 칩·강조 규칙선 | `w:tcPr/w:shd`(헤더), 액센트 바 |
| `color.surface`/`surface_2` → `surface`/`surface_2` | 표 zebra·콜아웃 박스 fill | 짝수행 `w:shd`, 단일 셀 표 음영(다크 프리셋은 라이트 틴트) |
| `color.muted` → `muted`(보정) | 캡션·푸터·출처 라인 | 작은 회색 run(라이트 배경 대비 보정) |
| `color.border` | 표 테두리·헤어라인 규칙선 | `w:tblBorders`/단락 하단 `w:pBdr` |
| `semantic.up`/`down` | 표·KPI 수치 강조 색 | run 색(convention 에 따라 의미 부여) |
| `font.display` (`latin_font`) | 헤딩·KPI 라틴 run | `w:rFonts w:ascii/w:hAnsi` |
| `font.body` (`kr-safe-gothic`) | 본문 라틴 + 한글 분리 | 본문 라틴=`latin_font`, 한글=`eastAsia` 안전 고딕 |
| `korean_fallbacks` | `kr_font_name()` 선택 입력 | `w:rFonts w:eastAsia`(Malgun Gothic 우선) |
| `space.margin` (`margin_in`) | 페이지 여백 | `w:sectPr/w:pgMar` |
| `space.gap` (`gap_in`) | 단락 간격 리듬 | `w:spacing w:before/after` |
| `type_scale` | 헤딩/본문 pt | run `w:sz` |
| `radius.base` | — | ▣ Word 단락/표에 모서리 반경 개념 없음(필터) |
| `motif` | 표지 규칙선·킥커 칩 등 평면 표현 | 도형 그라디언트는 비1급(Pillow PNG 임베드 시만) |

## 다크 프리셋 표현 정책 — **샌드위치 (강제)** (#668)

equity-research-dark·tech-vivid-dark·kari 같은 다크 프리셋은 docx 에서 **표지/섹션 밴드만 다크, 본문은 라이트("샌드위치")** 로 렌더한다. 전면 다크 본문은 **불가**하다 — 선택이 아니라 매체 한계다:

- python-docx 는 페이지 배경(`w:background`) 을 노출하지 않는다. 그나마 raw XML `w:background` 도 Word 의 **화면 전용** 기능이라 인쇄/PDF 에 안 나온다. 즉 "전면 다크 본문"을 1급(python-docx) 경로로 만들 방법이 없다.
- 인쇄 지향 문서에서 전면 다크는 잉크 낭비·가독 저하다.

따라서 다크 프리셋의 정체성은 **다크 표지 밴드 + 클로징 밴드 + 브랜드색 헤더/헤딩/액센트**가 담고, 본문 텍스트·표는 라이트 배경 위 가독 색으로 렌더된다. 어댑터(`_sandwich_palette`)가 이를 자동 집행한다(프리셋 이름 분기 없음 — `is_dark = 캔버스 휘도 < 0.18` 으로 판정):

| 토큰 | 라이트 프리셋 | 다크 프리셋(샌드위치 보정) |
|---|---|---|
| `ink` | `fg` 그대로(어두움) | **캔버스(`bg`) 그대로** — 또렷한 근-검정 + 브랜드 색조(딥네이비 등) |
| `muted` | 원본 | 흰 배경 대비 ≥4.5 로 보정(밝은 muted → 중간 회색) |
| `primary_text` | `primary`(이미 가독) | `primary` 를 흰 배경 대비 ≥4.0 으로 보정(밝은 골드/그린 → 어두운 동계색) |
| `up`/`down` | 원본 | 라이트 패널 위 ≥3.5 로 보정 |
| `surface`/`surface_2`/`border` | 원본 | **브랜드 틴트의 라이트 면**(zebra·콜아웃을 라이트로) |
| `primary`/`accent` | 원본 | **원본 유지** — 표지/헤더 fill 용(브랜드 시그니처) |

> **kari 주의(알려진 한계)**: kari 프리셋은 `do: 본문도 다크 유지` / `dont: 라이트 배경 전환 금지` 를 명시하지만, docx 는 위 한계로 본문 다크가 불가하다. docx 에서 kari 의 다크 정체성은 **표지·클로징 밴드**로만 표현되고 본문은 샌드위치 라이트가 된다. "본문 다크" 의도는 pptx/슬라이드웨어에서 충족된다(매체 적합성 차이).

가독성은 문서 디스플린이 아니라 **코드로 강제**된다 — `docx-design/scripts/verify.py` 의 대비 게이트(F)가 라이트 본문 위 텍스트의 WCAG 대비를 측정해 **3.0:1 미만이면 HARD FAIL**(3.0~4.5 는 advisory)로 막는다. 보정 전 다크 토큰을 라이트 본문에 그대로 쓰면 여기서 잡힌다.

## East Asian 폰트 바인딩 계약 (`constraints.docx`)

`design_core` 는 프리셋에 `constraints.docx` 가 없으면 기본 프로필을 주입한다:

```yaml
eastasia_guard: true                       # 한글 run → eastAsia 분리 바인딩
page_size: A4
opentype: supported                        # Word 는 tnum/커닝 등 지원(pptx/LibreOffice 와 차이)
fallback_fonts:
  korean: [Malgun Gothic, 맑은 고딕, Noto Sans KR, Pretendard]
```

dockit 의 `set_run_font(run, latin=, kr=)` 가 이 계약을 집행한다:

1. run 텍스트에 한글이 있으면 `w:rFonts w:eastAsia` 를 `kr_font_name()`(후보 중 첫 존재 폰트, Windows 기본 Malgun Gothic)로 바인딩.
2. 라틴/숫자는 `w:ascii`/`w:hAnsi` 를 디스플레이 폰트로 — 라틴 디스플레이 폰트가 한글 글리프를 대신 먹어 깨지는 일을 차단.
3. Word 는 한글을 네이티브로 렌더하므로 pptx 의 음수 자간 클램프·세리프 강제 교체는 **불필요**. 단, LibreOffice 크로스플랫폼 프리뷰의 안전을 위해 eastAsia 후보에 Noto Sans KR·Pretendard 를 둔다(2차 방어).

## 재현 한계 (docx 매체)

- **색·헤딩 위계·표 스타일(헤더 fill·zebra·테두리)·헤더/푸터·페이지번호·간격 리듬**: 높은 재현(Word 흐름 문서의 본령).
- **모서리 반경(`radius`)**: Word 단락/표에 없음 — 무시(필터).
- **그라디언트·glow·모티프 배경**: Word 네이티브 도형 그라디언트는 비1급. 필요 시 Pillow PNG 를 인라인 이미지로 임베드(pptx 와 동일 우회), 단 흐름 문서라 풀블리드는 표지 한정.
- **OpenType 기능(tnum/ss01)**: pptx 와 달리 Word 는 지원하나 dockit 1급 경로는 미적용(후속).
- 상세·우회는 `../../docx-design/references/design-md-mapping.md` 를 따른다. 본 어댑터는 그 한계를 바꾸지 않는다.
