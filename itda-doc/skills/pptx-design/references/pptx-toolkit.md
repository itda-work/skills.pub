# PPTX 디자인 생성 Toolkit (deckkit + matplotlib + Pillow)

`scripts/deckkit.py` 의 공개 헬퍼 API 로 16:9 와이드 덱을 생성하는 레시피·함정·CJK 폰트 규칙·렌더 명령을 정리한다.
**직접 python-pptx 보일러플레이트를 다시 쓰지 말고 deckkit 헬퍼를 import 해서 쓴다** — 도형 기본 테두리·그림자 제거, CJK latin/ea/cs 동시 지정, 그라디언트 PNG 베이크가 이미 내장돼 있다.

스택: **python-pptx + matplotlib(차트→PNG) + Pillow/numpy(그라디언트·모티프→PNG)**. 크로스플랫폼(macOS/Linux), Microsoft Office **불필요**. 캔버스 기본 **13.333" × 7.5"(16:9)**.

핵심 원칙(REPORT.md §6 + SPEC-002):
- **차트 갈래 두 개**: ① **네이티브 편집 차트(`dk.add_native_chart`, 기본 권장)** — PowerPoint 편집 가능 객체 + DESIGN.md 팔레트 + CJK 폰트 자동 주입. ② **matplotlib PNG(고디자인/특수)** — 면적채움·끝점 라벨·커스텀 슬라이더 등 네이티브로 못 내는 정보 밀도용(편집 불가 명시). 둘 다 기본 파랑/주황 금지.
- **한글은 항상 `dk.kr_font_name()`(Noto Sans KR·Pretendard 우선) + 자동 가드** — LibreOffice 명조/붓글씨 폴백 차단. 폰트가 자간보다 지배적 레버다.
- **그라디언트·glow·모티프 배경은 Pillow 로 PNG 베이크 후 임베드** — python-pptx 는 그라디언트 fill 을 직접 지원하지 않는다.
- **표는 도형(rect)+텍스트로 직접 그리는 것을 권장** — 네이티브 표는 디자인 통제가 어렵다.

---

## 0. import 와 슬러그 규약

per-invocation 생성 스크립트(`gen.py`)는 deckkit 을 import 한다. 스크립트 위치에서 `scripts/` 를 path 에 넣는다.

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))  # 경로는 실제 배치에 맞게
import deckkit as dk
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
```

산출 파일은 스킬이 지정한 출력 경로 안에서만 쓴다(차트/모티프 PNG → `assets/`, 최종 → `<slug>.pptx`). 공통 자산은 읽기 전용.

---

## 1. 16:9 스캐폴드 (deckkit)

```python
prs = dk.new_deck()              # 기본 13.333" × 7.5" (16:9). new_deck(w_in, h_in) 으로 변경 가능
KR = dk.kr_font_name()           # 이 환경에서 안전한 한글 폰트명 (set_run_font name 용)

slide = dk.blank_slide(prs)      # 완전 빈 레이아웃(idx 6)
dk.set_bg(slide, "faf9f5")       # 슬라이드 배경색 (hex, '#' 유무 무관)

dk.save_deck(prs, "out/deck.pptx")   # 디렉토리 자동 생성 후 저장
```

- `dk.hexrgb("cc785c")` → RGBColor. 색을 직접 만들 일이 있을 때만. 대부분 헬퍼가 hex 문자열을 그대로 받는다.
- 풀블리드 이미지 배경(그라디언트 등)은 **맨 먼저** 깔아 이후 요소가 위에 쌓이게 한다(아래 §3).

### 도형 (테두리·그림자 기본 제거됨)

```python
# 평면 색블록 — 기본값으로 이미 테두리 없음·그림자 없음
dk.rect(slide, x=0.6, y=1.2, w=4.0, h=2.4, fill="cc785c")

# 테두리만 있는 카드(헤어라인)
dk.rect(slide, 0.6, 4.0, 4.0, 2.0, fill=None, line="e6dfd8", line_w=1.0)

# 둥근 사각형 — radius 는 비율(0~0.5). pill 은 radius 크게
dk.rect(slide, 6.0, 1.2, 3.0, 0.5, fill="533afd",
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)

# 원/타원 (정원은 w==h)
dk.rect(slide, 10.0, 1.2, 1.2, 1.2, fill="141413", shape=MSO_SHAPE.OVAL)

# 디자인이 그림자를 의도하면 shadow=True 로 보존
dk.rect(slide, 0.6, 1.2, 4.0, 2.4, fill="ffffff", shadow=True)
```

> `rect()` 는 기본적으로 LibreOffice 가 preset effectRef 로 강제 상속하는 드롭섀도를 XML 로 중화한다(`_kill_shadow`). 직접 `sp.shadow.inherit=False` 를 호출할 필요가 없다.
> 선은 별도 connector 대신 **얇은 RECTANGLE**(예: h=0.01)로 그리는 게 단순·안정적이다.

---

## 2. 텍스트 + CJK 폰트 규칙 (가장 중요)

`set_run_font(name=...)` 는 **latin / ea / cs typeface 를 동시 지정**한다 — 이 동시 지정이 한글 tofu·세리프 폴백을 막는 핵심이다(REQ-004).

```python
# add_text: 단일 문단. runs = [(text, {font kwargs}), ...]
dk.add_text(slide, x=0.6, y=0.5, w=8.0, h=1.0,
            runs=[("삼성전자 vs SK하이닉스", {"name": KR, "size": 40, "bold": True, "color": "141413"})],
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)

# 혼합 run: 영문 디스플레이 라틴 + 한글 — run 단위로 폰트를 나눈다
dk.add_text(slide, 0.6, 2.0, 8.0, 0.8, runs=[
    ("HBM ", {"name": "Georgia", "size": 28, "color": "0d253d"}),     # 영문/숫자 전용 run
    ("슈퍼사이클", {"name": KR, "size": 28, "color": "0d253d"}),       # 한글 run 은 한글 폰트
])
```

### 멀티라인 본문 (불릿)

```python
tb = dk.add_text(slide, 0.6, 2.5, 6.0, 3.0,
                 runs=[("• AI 서버·가속기 수요 폭증", {"name": KR, "size": 16, "color": "3d3d3a"})],
                 line_spacing=1.3, space_after=8)
dk.add_paragraph(tb.text_frame,
                 runs=[("• 범용 DRAM/NAND 가격 반등 사이클 진입", {"name": KR, "size": 16, "color": "3d3d3a"})],
                 space_after=8, line_spacing=1.3)
```

- 글머리표는 유니코드 "•" 를 텍스트에 직접 넣는 게 가장 안정적이다(이 toolkit 허용).
- 세로 가운데 정렬: `anchor=MSO_ANCHOR.MIDDLE`. `add_text` 는 박스 margin 을 0 으로 잡아 정렬 어긋남을 방지한다.
- 자간: `set_run_font(spacing=...)` (pt 단위, 음수 가능). 단 LibreOffice 에서 약하게만 적용된다(§한계는 design-md-mapping.md).
- **★em-dash(U+2014) 함정**: 한글 인접 run 에서 em-dash 글리프가 **통째로 드롭**(유령 공백)될 수 있다 — 음수 자간 라틴 run(stripe 실험)만이 아니라 **일반 한글 본문에서도 실측**(2026-06-11 비교 덱, 54건). 구분 대시는 **en-dash(U+2013) 또는 middle-dot(·)** 을 쓴다.

### 한글 폰트명 선택 + ★자동 가드 (SPEC-PPTX-DESIGN-002 REQ-001/006)

- **항상 `dk.kr_font_name()`** 로 환경 안전 폰트명을 받아 한글 run 에 쓴다. 체인은 **LibreOffice 에서 또렷한 굵은 고딕(Noto Sans KR → Pretendard) 우선**으로 정렬됐다(실측: NanumGothic·Apple SD Gothic Neo 는 LibreOffice 에서 자간 벌어진 명조풍으로 치환 → 후순위).
- **`set_run_font` 한글 가드(자동, force=False 기본)**:
  - 한글 run 에 **비-한글 폰트**(Georgia·Impact·Helvetica Neue 등 라틴 세리프/디스플레이) 지정 → `kr_font_name()` 안전 고딕으로 **강제 교체**.
  - 한글 run 의 **음수 자간 → 0**, 과대 양수 → `KR_SPACING_CAP_PT(2.0pt)` 캡.
  - 라틴 전용 run 은 음수 자간·세리프 디스플레이 **그대로 허용**.
  - 의도적 우회는 `set_run_font(..., force=True)`.
- 디자인의 라틴 디스플레이 폰트(Georgia, Times New Roman, Impact, Arial Black, Helvetica Neue, Courier New 등)는 **영문/숫자 전용 run** 에만 쓴다.
- **안전책**: 한글+영문 혼합 텍스트는 run 을 나누되, 섞을 거면 한글 폰트로 통일한다(가드가 어차피 한글 포함 run 을 안전 고딕으로 강제). 순수 영문/숫자 헤드라인만 디자인 라틴 폰트로 분리.
- 한글 세리프는 시스템에 거의 없다 → 세리프가 정체성인 디자인도 한글은 고딕으로 폴백된다(design-md-mapping.md 한계 카탈로그 참조).

---

## 3. Pillow — 그라디언트·glow·모티프 PNG

python-pptx 에 그라디언트 fill 이 없으므로 **Pillow 로 고해상도 PNG 를 베이크**해 풀블리드로 깐다. 권장 해상도 **2667 × 1500 px**(= 13.333"×7.5" @ 200dpi).

```python
# 선형 그라디언트 — c_*: (r,g,b) 튜플
img = dk.linear_gradient(2667, 1500, c_top=(28, 30, 84), c_bottom=(13, 37, 61), vertical=True)
img.save("assets/bg_grad.png")

# 방사형 글로우 — 어두운 base 위 glow 색
img = dk.radial_glow(2667, 1500, base=(11, 11, 11), glow=(30, 215, 96), cx=0.5, cy=0.35, radius=0.7)
img.save("assets/bg_glow.png")

# 풀블리드로 맨 먼저 깐다 (이후 요소가 위에 쌓임)
dk.add_picture(slide, "assets/bg_grad.png", 0, 0, w=13.333, h=7.5)
```

- 대각/노이즈/도트·그리드 모티프는 numpy 로 자유 합성 후 `Image.fromarray(...).save(...)`.
- 베이크는 래스터다(벡터 아님). 확대 시 픽셀화하고 **텍스트 위 그라디언트는 불가** — 처음부터 고해상도로 굽고, 글자는 솔리드 색으로.
- hex → (r,g,b) 변환이 필요하면: `c = dk.hexrgb("1c1e54"); rgb = (c[0], c[1], c[2])` 또는 직접 `int(h[i:i+2],16)`.

---

## 4. matplotlib — 디자인 팔레트 차트 → PNG

`mpl_korean()` 을 **차트 그리기 전 1회 호출**해 한글 폰트를 등록하고 마이너스 부호를 정상화한다(음수 영업이익 등). 반환값은 등록된 폰트명(없으면 DejaVu Sans).

```python
fam = dk.mpl_korean()   # 한글 폰트 등록 + axes.unicode_minus=False
import matplotlib.pyplot as plt

PAL = {"samsung": "cc785c", "hynix": "0d253d"}   # DESIGN.md 팔레트 hex 사용
fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=200)
ax.bar(years, samsung_op, color="#" + PAL["samsung"])
ax.bar(years, hynix_op,   color="#" + PAL["hynix"])
for s in ("top", "right"):
    ax.spines[s].set_visible(False)        # 군더더기 제거
ax.tick_params(colors="#6c6a64")
fig.savefig("assets/chart_op.png", transparent=True, bbox_inches="tight", pad_inches=0.05)
plt.close(fig)

dk.add_picture(slide, "assets/chart_op.png", x=6.5, y=1.5, w=6.0)   # w 만 주면 종횡비 유지
```

- 색은 **반드시 그 디자인의 팔레트 hex** 로(기본 matplotlib 파랑/주황 추방). 의미색(상승=초록·하락=빨강 등)도 디자인 톤에 맞춰.
- 어두운 슬라이드: `transparent=True` 로 두고 축/라벨/선을 밝은 톤으로, 또는 `fig.savefig(facecolor="#0b0b0b")` 로 슬라이드 배경과 동일하게.
- 음수 값(예: 하이닉스 2023 영업이익 -7.7조)은 0 기준선 아래로 정확히 표현 — `mpl_korean()` 가 마이너스 부호 깨짐을 막아준다.
- PNG 임베드 시 **width 만** 주면 비율이 자동 유지된다(`dk.add_picture(..., w=6.0)`).
- 차트/표 데이터는 입력 데이터(JSON 등)와 **정확히 일치**시킨다.

---

## 4.5 네이티브 편집 차트 — `dk.add_native_chart` (기본 권장)

PowerPoint 에서 **편집 가능한 진짜 차트 객체**가 필요하면(받는 사람이 수치를 직접 수정) matplotlib PNG 대신 네이티브 차트를 쓴다. DESIGN.md 팔레트와 CJK 안전 폰트가 자동 적용된다.

```python
# 클러스터 막대 — 매출 vs 영업이익(음수 영업이익도 0 기준선 아래로 정확)
dk.add_native_chart(
    slide, x=0.6, y=1.2, w=6.0, h=4.5, kind="column",
    categories=["2023", "2024", "2025E", "2026E"],
    series=[("매출", [26, 30, 38, 46]), ("영업이익", [-7.7, 12, 24, 33])],
    palette=["1c1e54", "533afd"],          # DESIGN.md 팔레트 hex(기본 파랑/주황 금지)
    data_labels=True, number_format="0.0", gap_width=80, legend_pos="bottom",
)

# 도넛 — point 별 팔레트 색
dk.add_native_chart(
    slide, 6.9, 1.2, 6.0, 4.5, kind="doughnut",
    categories=["SK하이닉스", "삼성전자", "Micron"],
    series=[("HBM 점유율", [50, 35, 15])],
    palette=["533afd", "1c1e54", "ea2261"], data_labels=True,
    number_format='0"%"', legend_pos="right",
)
```

- `kind`: `column`·`bar`·`line`·`line_markers`·`pie`·`doughnut`·`stacked_column`·`stacked_bar`·`stacked_column_100`·`area`·`area_stacked`·`radar`.
- `series`: `[(name, [values...]), ...]`. pie/doughnut 은 단일 series 의 point 별 색.
- `palette`: series(원형은 point) 별 hex. 막대는 테두리 자동 제거, 라인은 line 색 적용.
- `font_name`: 범례·축·라벨 폰트(기본 `kr_font_name()`, latin/ea/cs 동시 주입 → 한글 라벨 안전).
- 옵션: `data_labels`·`number_format`·`legend`/`legend_pos`·`gridlines`·`value_axis`/`category_axis`·`gap_width`·`overlap`.
- 차트/표 데이터는 입력 데이터(JSON 등)와 **정확히 일치**시킨다(음수도 정확히).

> **언제 네이티브 vs matplotlib**: 편집성·표준 차트 → **네이티브**(`add_native_chart`). 면적채움 추세선·끝점 직접 라벨·커스텀 슬라이더 등 정보 밀도 높은 특수 시각 → **matplotlib PNG**(§4, 편집 불가 명시).

---

## 5. 표 — 도형으로 직접 그리기 권장

강한 커스텀 룩이 필요하면 네이티브 표 대신 **rect 셀 + add_text** 로 직접 그린다(REPORT.md §6 권장).

```python
# 도형 셀 + 텍스트 — 완전한 디자인 통제
COLS = ["지표", "삼성전자", "SK하이닉스"]
x0, y0, cw, rh = 0.6, 2.0, [2.4, 2.4, 2.4], 0.6
for ci, head in enumerate(COLS):
    cx = x0 + sum(cw[:ci])
    dk.rect(slide, cx, y0, cw[ci], rh, fill="141413")
    dk.add_text(slide, cx, y0, cw[ci], rh, runs=[(head, {"name": KR, "size": 14, "bold": True, "color": "ffffff"})],
                align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
```

네이티브 표가 더 적합하면 `add_table` 사용(기본 밴딩은 이미 꺼져 있다 — `first_row=False`, `horz_banding=False`):

```python
gt = dk.add_table(slide, 0.6, 2.0, 7.2, 2.4, nrows=4, ncols=3, col_w=[2.4, 2.4, 2.4])
cell = gt.cell(0, 0)
cell.text = "PER (배)"
cell.fill.solid(); cell.fill.fore_color.rgb = dk.hexrgb("efe9de")
run = cell.text_frame.paragraphs[0].runs[0]
dk.set_run_font(run, name=KR, size=14, color="141413")   # 셀도 set_run_font 로 CJK 안전 지정
```

---

## 6. 함정 체크리스트 (렌더 전후 자가점검)

- [ ] 도형 기본 파란 **테두리 제거** 됐는가 — `dk.rect()` 기본값이면 자동. 직접 add_shape 했다면 수동 제거.
- [ ] 도형 기본 **그림자 제거** 됐는가 — `dk.rect()` 가 `_kill_shadow` 로 자동 중화(디자인이 그림자 의도면 `shadow=True`).
- [ ] 한글이 네모(tofu)/깨짐 없이 의도한 폰트로 나오는가 — 한글 run 에 `dk.kr_font_name()` 적용, 혼합 run 분리.
- [ ] 텍스트가 박스 밖으로 **오버플로/잘림** 없는가 — 박스 넉넉히, 타이틀 36~48pt · 본문 14~18pt · 캡션 10~12pt.
- [ ] **대비**: 어두운 배경엔 밝은 글자, 밝은 배경엔 어두운 글자. 저대비 회색-위-회색 금지.
- [ ] 가장자리 마진 0.4" 이상, 요소 간 간격 일관(0.3~0.5" 이상).
- [ ] 차트 색이 디자인 팔레트와 일치하는가(기본 matplotlib 파랑/주황 금지).
- [ ] 차트/표 데이터가 입력 데이터와 정확히 일치하는가(음수도 정확히).
- [ ] 모든 슬라이드가 최소 1개 시각 요소를 가졌는가, 빈 슬라이드 없는가.
- [ ] 같은 레이아웃을 내내 반복하지 않았는가(표지/요약/차트/표/그리드/결론을 다르게).
- [ ] **AI 슬라이드 티**: 제목 밑줄 악센트 라인 금지. 여백·색면으로 위계 표현.

---

## 7. 렌더링·검증 명령

생성 자체엔 LibreOffice 가 불필요하지만, 검수·검증에는 필요하다.

### 렌더 (썸네일)

```bash
# macOS/Linux
python3 scripts/render.py <deck.pptx> [out_dir] [--dpi 110]
# Windows
py -3 scripts/render.py <deck.pptx> [out_dir] [--dpi 110]
```

슬러그별 격리 프로파일(`-env:UserInstallation`)로 PDF 변환 후 `pdftoppm` JPG 썸네일(`slide-XX.jpg`)을 만든다. **병렬 안전**. `--dpi 110` 이면 폭 ~1465px 로 검수에 충분하고 가볍다.

### 3층 검증 (HARD GATE)

```bash
# macOS/Linux
python3 scripts/verify.py <deck.pptx> [--tokens tokens.txt] [--ko "삼성전자,SK하이닉스"] [--out DIR] [--no-ocr]
# Windows
py -3 scripts/verify.py <deck.pptx> [--tokens tokens.txt] [--ko "삼성전자,SK하이닉스"]
```

| 층 | 방법 | 검출 | 등급 |
|---|---|---|---|
| **A 지오메트리** | python-pptx bbox | 경계이탈(off-slide)·0/음수 도형·텍스트박스 겹침 | 경계이탈·퇴화=**HARD** / 겹침=advisory |
| **B 콘텐츠 대조** | pptx 텍스트 vs `--tokens` | 필수 토큰 드롭(미렌더 텍스트) | **HARD** |
| **C OCR 렌더 대조** | LibreOffice 렌더 → tesseract(kor+eng) | 산출률·한글명 OCR 존재 | advisory(형식오탐 회피) |
| **D 한글 타이포** | rPr 정적 검사 | 한글 run 음수/과대 자간·비안전(세리프/라틴) 폰트 | advisory(가드 우회·구버전 회귀 트립와이어) |

- **HARD GATE = (경계이탈 + 퇴화도형 + 빈슬라이드 + 토큰누락) == 0 → PASS 시 exit 0.** 산출 조건이다(REQ-005). 타이포(D)는 advisory.
- `--tokens tokens.txt`(1줄 1토큰)로 필수 콘텐츠가 실제 pptx 텍스트에 들어갔는지 대조한다. 핵심 수치·종목명·섹션 제목을 넣는다.
- OCR 은 advisory 트립와이어(광범위 미렌더 회귀 감지)다 — tesseract/pytesseract 미설치 시 자동 스킵(`--no-ocr` 로 명시 비활성). 산출물: `_verify/<stem>.json` + `<stem>-annotated.png`(빨강=경계이탈·주황=겹침·보라=퇴화).
- 미세 충돌·경계 내 오정렬·약한 저대비는 게이트가 못 잡는다 → **렌더 시각 QA(슬라이드 JPG 직접 Read)** 로 보완한다.

---

## 8. 자가 수정 루프

생성 → `render.py` → `slide-*.jpg` 를 **직접 Read 해 눈으로 확인** → 문제 목록화 → 코드 수정 → 재렌더. 최소 1회 수정-재검 사이클을 돌고 `verify.py` HARD GATE PASS 를 확인하고 끝낸다. "문제 0개" 면 더 비판적으로 다시 본다.
