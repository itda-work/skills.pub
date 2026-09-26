# -*- coding: utf-8 -*-
"""examples/sample/gen.py — docx-design 동작 예제 생성기 (NovaTech FY2025 연차 보고서).

docx-design 의 per-invocation 생성 스크립트(gen.py)가 어떤 모습이어야 하는지 보여주는
정식 예제다. 3개 SSoT 입력:
  - content.md : 섹션 콘텐츠 명세(고정)
  - data.json  : 수치 데이터(표·KPI)
  - design.md  : 적용 디자인(여기서는 design-core 프리셋 참조)

설계 규칙:
  - 모든 단락/표/콜아웃/규칙선/푸터는 ``scripts/dockit.py`` 공개 API 로 만든다(직접 python-docx 금지).
  - 색·폰트·여백은 design-core ``docx_styles()`` 토큰에서만 가져온다(손지정 금지).
  - 한글은 dockit 이 eastAsia 안전 고딕으로 분리 바인딩(라틴 디스플레이는 ascii/hAnsi).
  - 결정론: 난수 미사용(동일 입력 → 동일 산출).

사용:
  py -3 gen.py [preset|DESIGN.md경로] [out.docx]
  (기본 preset=consulting-mbb, out=novatech-<preset>.docx)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(HERE))            # .../docx-design
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))       # dockit
sys.path.insert(0, os.path.join(os.path.dirname(SKILL_ROOT), "design-core", "scripts"))  # design_core

try:
    import dockit as dk           # noqa: E402
    import design_core as dc      # noqa: E402
except ModuleNotFoundError as _e:  # design-core 형제 스킬 미동봉 진단(loud)
    sys.exit(
        f"[docx-design] 의존 모듈 로드 실패: {_e}. "
        "design-core 형제 스킬이 같은 플러그인(itda-doc)에 함께 설치돼야 합니다 "
        f"(기대 경로: {os.path.join(os.path.dirname(SKILL_ROOT), 'design-core', 'scripts')})."
    )

# ── 입력 -------------------------------------------------------------------
PRESET = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DOCX_DESIGN_PRESET", "consulting-mbb")
DATA = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
preset_label = os.path.splitext(os.path.basename(PRESET))[0]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, f"novatech-{preset_label}.docx")

# ── 디자인 토큰 → Word 스타일 --------------------------------------------
st = dc.load(PRESET).docx_styles()
doc = dk.new_doc(margin_in=st.get("margin_in") or 0.9, page=st.get("page_size") or "A4")
th = dk.apply_design(doc, st)

INK, PRIMARY, MUTED = st["ink"], st["primary"], st["muted"]
ACCENT, SURFACE, BORDER = st["accent"], st["surface"], st["border"]
UP, DOWN = st["up"], st["down"]
# PRIMARY = 브랜드 fill(표지·헤더 밴드용 원본). 라이트 본문 위 강조 '텍스트'는
# PRIMARY_TEXT(저대비 브랜드색은 design-core 가 보정, 대비 충족 시 동일).
PRIMARY_TEXT = st.get("primary_text", PRIMARY)
ON_PRIMARY = dk.on_color(PRIMARY)


def money(bn):
    return f"${bn:.2f}B"


def pct(v, signed=False):
    return (f"+{v:.1f}%" if (signed and v >= 0) else f"{v:.1f}%")


def yoy_run(v):
    col = UP if v >= 0 else DOWN
    return [(pct(v, signed=True), dict(color=col, bold=True))]


# ── 표지 (색 밴드) --------------------------------------------------------
cover = dk.band(doc, fill=PRIMARY, accent=ACCENT)
dk.add_paragraph(cover, [("ANNUAL REPORT · FY2025",
                          dict(latin=th["_latin"], size=10, color=ON_PRIMARY, bold=True,
                               all_caps=True, spacing=1.6))], space_after=10)
dk.add_paragraph(cover, [("NovaTech ", dict(latin=th["_latin"], size=30, bold=True, color=ON_PRIMARY)),
                         ("FY2025 연차 실적 보고서", dict(size=30, bold=True, color=ON_PRIMARY))],
                 space_after=6, line_spacing=1.05)
dk.add_paragraph(cover, [("AI 클라우드가 그린 성장의 변곡점",
                          dict(size=14, color=ON_PRIMARY))], space_after=14)
dk.add_paragraph(cover, [(f"발행 {DATA['as_of']}  ·  단위 USD  ·  작성 IR (가상)",
                          dict(latin=th["_latin"], size=9.5, color=ON_PRIMARY))], space_after=0)

dk.add_paragraph(doc, "", space_after=4)

# ── 1. 핵심 요약 ----------------------------------------------------------
dk.kicker(doc, "EXECUTIVE SUMMARY")
dk.heading(doc, "핵심 요약", level=1)
dk.kpi_strip(doc, [(k["value"], f"{k['label']} · {k['sub']}") for k in DATA["headline_kpis"]])
dk.callout(doc, [("요약  ", dict(bold=True, color=PRIMARY_TEXT)), (DATA["summary"], {})])

# ── 2. 재무 성과 ----------------------------------------------------------
dk.heading(doc, "재무 성과 (분기 추이)", level=2)
q = DATA["quarterly"]
rows = []
for i, lab in enumerate(q["labels"]):
    rows.append([lab, money(q["revenue_bn"][i]), money(q["op_profit_bn"][i]), pct(q["op_margin_pct"][i])])
dk.add_table(
    doc,
    headers=["분기", "매출", "영업이익", "영업이익률"],
    rows=rows,
    col_align=["left", "right", "right", "right"],
)
dk.body(doc, [("분기가 갈수록 영업이익률이 ", {}),
              (f"{q['op_margin_pct'][0]:.1f}% → {q['op_margin_pct'][-1]:.1f}%", dict(bold=True, color=PRIMARY_TEXT)),
              ("로 개선되며 수익성 레버리지가 확인됐다.", {})], space_before=4)

# ── 3. 사업부별 실적 ------------------------------------------------------
dk.heading(doc, "사업부별 실적", level=2)
seg_rows = []
for s in DATA["segments"]:
    seg_rows.append([s["name"], money(s["revenue_bn"]), yoy_run(s["yoy_pct"]),
                     pct(s["margin_pct"]), s["note"]])
dk.add_table(
    doc,
    headers=["사업부", "매출", "YoY", "마진", "비고"],
    rows=seg_rows,
    col_align=["left", "right", "right", "right", "left"],
)
regions = "  ·  ".join(f"{r['name']} {r['share_pct']}%" for r in DATA["regions"])
dk.body(doc, [("지역 매출 비중  ", dict(color=MUTED, bold=True)), (regions, dict(color=INK))], space_before=4)

# ── 4. 전망과 리스크 ------------------------------------------------------
dk.heading(doc, "전망과 리스크", level=2)
o = DATA["outlook_fy2026"]
dk.body(doc, [("FY2026 가이던스  ", dict(bold=True, color=PRIMARY_TEXT)),
              (f"매출 {money(o['revenue_low_bn'])}–{money(o['revenue_high_bn'])}, "
               f"영업이익률 {pct(o['margin_target_pct'])} 목표.", {})])
dk.body(doc, [("주요 리스크", dict(bold=True, color=INK))], space_before=6, space_after=2)
dk.bullet_list(doc, [[(r["title"] + " — ", dict(bold=True, color=INK)), (r["desc"], dict(color=MUTED))]
                     for r in DATA["risks"]])
dk.callout(doc, [("R&D 투자  ", dict(bold=True, color=PRIMARY_TEXT)),
                 (f"{money(DATA['rnd_bn'])} (매출의 {DATA['rnd_pct_of_rev']}%) — 미래 성장 동력에 집중 투자.", {})],
           accent=ACCENT)

# ── 클로징 (색 밴드) ------------------------------------------------------
dk.add_paragraph(doc, "", space_after=6)
closing = dk.band(doc, fill=INK, accent=ACCENT)
dk.add_paragraph(closing, [("AI 클라우드 수요를 발판으로 FY2026 두 자릿수 성장과 마진 확대를 지속한다.",
                            dict(size=14, bold=True, color=dk.on_color(INK)))], space_after=6)
dk.add_paragraph(closing, [("※ NovaTech Inc. 와 본 자료의 모든 수치는 디자인 테스트용 가상 데이터입니다.",
                            dict(size=9, color=dk.on_color(INK)))], space_after=0)

# ── 푸터 ------------------------------------------------------------------
dk.set_footer(doc, left=f"NovaTech {DATA['fiscal_year']} 연차 보고서 · {preset_label}")

dk.save_doc(doc, OUT)
print("saved", OUT, "| preset =", preset_label, "| kr_font =", th["_kr"])
