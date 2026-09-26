# -*- coding: utf-8 -*-
"""examples/sample/gen.py — xlsx-design 동작 예제 생성기 (NovaTech FY2025 실적 통합문서).

xlsx-design 의 per-invocation 생성 스크립트(gen.py) 레퍼런스. 3 SSoT 입력:
  - content.md : 시트 콘텐츠 명세(고정)
  - data.json  : 수치 데이터
  - design.md  : 적용 디자인(design-core 프리셋 참조)

설계 규칙:
  - 모든 셀/표/차트/조건부서식은 ``scripts/sheetkit.py`` 공개 API 로(직접 openpyxl 보일러플레이트 금지).
  - 색·폰트·차트 팔레트는 design-core ``xlsx_styles()`` 토큰에서만.
  - 한글 셀은 sheetkit 이 Korean-capable 폰트로 가드. 결정론(난수 미사용).

사용:
  py -3 gen.py [preset|DESIGN.md경로] [out.xlsx]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(HERE))           # .../xlsx-design
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))      # sheetkit
sys.path.insert(0, os.path.join(os.path.dirname(SKILL_ROOT), "design-core", "scripts"))

try:
    import sheetkit as sk        # noqa: E402
    import design_core as dc     # noqa: E402
except ModuleNotFoundError as _e:  # design-core 형제 스킬 미동봉 진단(loud)
    sys.exit(
        f"[xlsx-design] 의존 모듈 로드 실패: {_e}. "
        "design-core 형제 스킬이 같은 플러그인(itda-doc)에 함께 설치돼야 합니다 "
        f"(기대 경로: {os.path.join(os.path.dirname(SKILL_ROOT), 'design-core', 'scripts')})."
    )
from openpyxl.chart import Reference  # noqa: E402

PRESET = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("XLSX_DESIGN_PRESET", "consulting-mbb")
DATA = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
preset_label = os.path.splitext(os.path.basename(PRESET))[0]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, f"novatech-{preset_label}.xlsx")

st = dc.load(PRESET).xlsx_styles()
wb = sk.new_book()
th = sk.apply_design(wb, st)

MONEY = '#,##0.00"B"'
PCT = '0.0"%"'
YOY = '+0.0"%";-0.0"%"'

# ── 시트 1: 요약 ----------------------------------------------------------
ws = wb.active
ws.title = "요약"
# 표지 제목 = 브랜드 밴드(샌드위치의 '표지 다크/브랜드' — docx 표지 밴드와 동형).
# title_block 이 fill 위 대비색을 자동 선택(on_color). 다크 프리셋도 안전.
sk.title_block(ws, f"NovaTech {DATA['fiscal_year']} 실적 요약", th, row=1, span=5, size=18,
               fill=st["primary"])
ws.row_dimensions[1].height = 30
sk.set_cell(ws, "A2", f"단위 USD · 발행 {DATA['as_of']} · 가상 데이터", theme=th,
            color=st["muted"], size=9)
sk.kpi_block(ws, 4, [(k["value"], k["label"]) for k in DATA["headline_kpis"]], th, start_col=1)

sk.set_cell(ws, "A7", "사업부별 실적", theme=th, bold=True, size=13,
            color=st.get("primary_text", st["primary"]))
seg = DATA["segments"]
dim = sk.data_table(
    ws, 8,
    headers=["사업부", "매출", "YoY", "마진"],
    rows=[[s["name"], s["revenue_bn"], s["yoy_pct"], s["margin_pct"]] for s in seg],
    theme=th, col_align=["left", "right", "right", "right"],
    number_formats=[None, MONEY, YOY, PCT],
)
fdr, lr, fc, lc = dim
sk.semantic_rules(ws, f"C{fdr}:C{lr}", th)   # YoY 양수=up/음수=down 색

# 차트: 사업부 매출
data = Reference(ws, min_col=2, min_row=8, max_row=lr)        # 헤더 포함(titles_from_data)
cats = Reference(ws, min_col=1, min_row=fdr, max_row=lr)
sk.add_bar_chart(ws, "사업부 매출 (USD Bn)", data, cats, th, "F4", y_title="USD Bn")

reg = "  ·  ".join(f"{r['name']} {r['share_pct']}%" for r in DATA["regions"])
sk.set_cell(ws, f"A{lr + 2}", "지역 매출 비중", theme=th, bold=True, color=st["muted"], size=10)
sk.set_cell(ws, f"A{lr + 3}", reg, theme=th, color=st["ink"], size=10)
sk.set_columns(ws, [16, 12, 10, 10, 10])
sk.freeze(ws, "A4")

# ── 시트 2: 분기 추이 -----------------------------------------------------
ws2 = wb.create_sheet("분기추이")
sk.title_block(ws2, "분기 실적 추이", th, row=1, span=4, size=16)
q = DATA["quarterly"]
rows = [[q["labels"][i], q["revenue_bn"][i], q["op_profit_bn"][i], q["op_margin_pct"][i]]
        for i in range(len(q["labels"]))]
dim2 = sk.data_table(
    ws2, 3,
    headers=["분기", "매출", "영업이익", "영업이익률"],
    rows=rows, theme=th, col_align=["left", "right", "right", "right"],
    number_formats=[None, MONEY, MONEY, PCT],
)
f2, l2, _, _ = dim2
# 라인 차트: 영업이익률 추이
data2 = Reference(ws2, min_col=4, min_row=3, max_row=l2)
cats2 = Reference(ws2, min_col=1, min_row=f2, max_row=l2)
sk.add_line_chart(ws2, "영업이익률 추이 (%)", data2, cats2, th, "F3", y_title="%")
sk.set_columns(ws2, [10, 12, 12, 12], start_col=1)
sk.freeze(ws2, "A3")

# ── 시트 3: 리스크 --------------------------------------------------------
ws3 = wb.create_sheet("리스크")
sk.title_block(ws3, "주요 리스크", th, row=1, span=2, size=16)
sk.data_table(
    ws3, 3,
    headers=["리스크", "설명"],
    rows=[[r["title"], r["desc"]] for r in DATA["risks"]],
    theme=th, col_align=["left", "left"],
)
sk.set_columns(ws3, [18, 70], start_col=1)
for r in range(4, 4 + len(DATA["risks"])):
    ws3.row_dimensions[r].height = 28
sk.freeze(ws3, "A3")

sk.save_book(wb, OUT)
print("saved", OUT, "| preset =", preset_label, "| kr_font =", th["_kr"])
