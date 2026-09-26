# -*- coding: utf-8 -*-
"""design-core PoC — 토큰 한 벌로 PPTX 덱 생성 (매체 독립 실증, SPEC-DESIGN-CORE-001 AC-03).

같은 빌더 코드가 `design_core.load(preset).pptx_palette()` 만 바꿔 삼성SDS·KARI 두 덱을
생성한다 — 디자인 시스템(토큰)이 PPTX 어댑터(deckkit)와 분리됐음을 실증한다.

⚠️ 콘텐츠 수치는 전부 **디자인 PoC용 예시**이며 실제 기관 IR/성과가 아니다.

실행(저장소 루트 기준):
  python3 skills/itda-doc/skills/design-core/examples/poc_build.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DC_ROOT = os.path.dirname(HERE)                                  # .../design-core
PD_SCRIPTS = os.path.join(DC_ROOT, os.pardir, "pptx-design", "scripts")
sys.path.insert(0, os.path.join(DC_ROOT, "scripts"))
sys.path.insert(0, PD_SCRIPTS)

import design_core as dc  # noqa: E402
import deckkit as dk  # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402

W, H = dk.DEFAULT_W_IN, dk.DEFAULT_H_IN   # 13.333 x 7.5
MX = 0.85
FL = "Helvetica Neue"

# ── PoC 콘텐츠 (디자인 테스트용 예시 — 실제 수치 아님) ──────────────────────
CONTENT = {
    "samsung-sds": {
        "eyebrow": "CORPORATE IT · IR (DESIGN POC)",
        "title": "삼성SDS 디지털 전환 성과",
        "subtitle": "클라우드 · 생성형 AI · 물류 플랫폼이 이끄는 B2B 성장 (예시)",
        "stats": [("₩13.8조", "연간 매출(예시)", "+5% YoY"),
                  ("₩8,100억", "영업이익(예시)", "+9%"),
                  ("32%", "클라우드 비중", "+6%p"),
                  ("18%", "R&D 투자율", "견조")],
        "chart_cats": ["2022", "2023", "2024", "2025E"],
        "chart_vals": [105, 118, 132, 150],
        "chart_title": "클라우드 매출 지수 (예시)",
        "grid": [("클라우드 (SCP)", "하이브리드·소버린 클라우드 확장"),
                 ("생성형 AI", "FabriX·Brity 기업용 AI 코파일럿"),
                 ("물류 (Cello)", "AI 기반 글로벌 SCM 플랫폼"),
                 ("엔터프라이즈 보안", "제로트러스트·통합 관제")],
        "closing": "데이터와 AI로\n기업이 일하는 방식을 바꾼다",
        "footer": "자료: 디자인 PoC용 예시 · design-core 토큰(samsung-sds) 적용",
    },
    "kari": {
        "eyebrow": "AEROSPACE RESEARCH (DESIGN POC)",
        "title": "한국항공우주연구원 우주개발 성과",
        "subtitle": "누리호 · 다누리가 연 대한민국 우주 시대 (예시)",
        "stats": [("3기", "누리호 발사(예시)", "연속 성공"),
                  ("100%", "다누리 궤도 안착", "임무 정상"),
                  ("1,000+", "위성 데이터셋", "공개"),
                  ("40+", "국제 협력 기관", "확대")],
        "chart_cats": ["2021", "2022", "2023", "2024"],
        "chart_vals": [2, 5, 8, 12],
        "chart_title": "우주 임무 누적 건수 (예시)",
        "grid": [("발사체", "누리호·차세대 발사체 개발"),
                 ("인공위성", "다목적·정지궤도 위성"),
                 ("심우주 탐사", "달 궤도선·심우주 임무"),
                 ("항공", "UAM·고고도 무인기")],
        "closing": "우주로 넓히는\n대한민국의 지평",
        "footer": "자료: 디자인 PoC용 예시 · design-core 토큰(kari) 적용",
    },
}


def _hx(v):
    """design_core 팔레트('#RRGGBB') → deckkit 형식(# 제거, gen.py 와 동일)."""
    return v.lstrip("#") if isinstance(v, str) else v


def build(preset: str, out: str, c: dict):
    t = dc.load(preset)
    P = {k: _hx(v) for k, v in t.pptx_palette().items()}
    CANVAS, SURFACE, INK, MUTED = P["canvas"], P["surface"], P["ink"], P["muted"]
    PRIMARY, ACCENT, HAIR = P["primary"], P["accent"], P["hairline"]
    ONP = "FFFFFF"
    FKR = dk.kr_font_name()
    prs = dk.new_deck()

    def header(s, eyebrow, title):
        dk.add_text(s, MX, 0.55, W - 2 * MX, 0.3,
                    [(eyebrow, dict(name=FL, size=11, color=PRIMARY, spacing=1.8))])
        dk.add_text(s, MX, 0.92, W - 2 * MX, 0.7,
                    [(title, dict(name=FKR, size=30, bold=True, color=INK, spacing=-0.5))])
        dk.rect(s, MX, 1.74, W - 2 * MX, 0.014, fill=HAIR)

    # ── S1 표지 (primary 풀블리드) ───────────────────────────────────────
    s = dk.blank_slide(prs); dk.set_bg(s, PRIMARY)
    dk.add_text(s, MX, 0.7, W - 2 * MX, 0.3, [(c["eyebrow"], dict(name=FL, size=12, color=ONP, spacing=2.0))])
    dk.rect(s, MX, 2.05, 1.0, 0.05, fill=ACCENT)
    dk.add_text(s, MX, 2.35, W - 2 * MX, 1.5, [(c["title"], dict(name=FKR, size=42, bold=True, color=ONP, spacing=-0.5))],
                line_spacing=1.05)
    dk.add_text(s, MX, 3.95, W - 2 * MX, 0.7, [(c["subtitle"], dict(name=FKR, size=17, color=ONP))], line_spacing=1.3)
    cw = (W - 2 * MX) / 3
    for i, (k, v, d) in enumerate(c["stats"][:3]):
        x = MX + i * cw
        dk.add_text(s, x, 5.75, cw - 0.2, 0.3, [(k, dict(name=FL, size=24, bold=True, color=ONP, spacing=-0.6))])
        dk.add_text(s, x, 6.25, cw - 0.2, 0.3, [(v, dict(name=FKR, size=11, color=ONP, spacing=0.3))])
        dk.add_text(s, x, 6.55, cw - 0.2, 0.3, [(d, dict(name=FKR, size=11, color=ACCENT))])
    dk.add_text(s, MX, H - 0.5, W - 2 * MX, 0.3,
                [("※ 수치는 디자인 PoC용 예시입니다.", dict(name=FKR, size=9, color=ONP))])

    # ── S2 핵심 요약 (4 스탯 카드, surface) ──────────────────────────────
    s = dk.blank_slide(prs); dk.set_bg(s, CANVAS)
    header(s, "EXECUTIVE SUMMARY", "핵심 요약")
    gap = 0.25
    cw = (W - 2 * MX - 3 * gap) / 4
    cy, ch = 2.15, 3.1
    for i, (val, lab, sub) in enumerate(c["stats"]):
        x = MX + i * (cw + gap)
        dk.rect(s, x, cy, cw, ch, fill=SURFACE, line=HAIR, line_w=1.0,
                shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        dk.rect(s, x + 0.3, cy + 0.32, 0.18, 0.18, fill=PRIMARY, shape=MSO_SHAPE.OVAL)
        dk.add_text(s, x + 0.3, cy + 0.78, cw - 0.6, 0.9,
                    [(val, dict(name=FL, size=32, bold=True, color=PRIMARY, spacing=-1.2))])
        dk.add_text(s, x + 0.3, cy + 1.85, cw - 0.6, 0.6, [(lab, dict(name=FKR, size=13, color=INK, spacing=-0.2))], wrap=True)
        dk.add_text(s, x + 0.3, cy + 2.45, cw - 0.6, 0.4, [(sub, dict(name=FKR, size=10.5, color=MUTED))])

    # ── S3 차트 (네이티브 편집 차트, primary 시리즈) ─────────────────────
    s = dk.blank_slide(prs); dk.set_bg(s, CANVAS)
    header(s, "GROWTH", "성장 추이")
    dk.rect(s, MX, 2.1, W - 2 * MX, 4.6, fill=SURFACE, line=HAIR, line_w=1.0,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    dk.add_text(s, MX + 0.4, 2.35, W - 2 * MX - 0.8, 0.4,
                [(c["chart_title"], dict(name=FKR, size=15, color=INK, spacing=-0.3))])
    dk.add_native_chart(
        s, MX + 0.35, 3.0, W - 2 * MX - 0.7, 3.4, "column",
        categories=c["chart_cats"], series=[("값", c["chart_vals"])],
        palette=[PRIMARY], data_labels=True, legend=False,
        font_name=FKR, font_color=MUTED, font_size=11,
    )

    # ── S4 사업 그리드 (2×2, surface) ────────────────────────────────────
    s = dk.blank_slide(prs); dk.set_bg(s, CANVAS)
    header(s, "PORTFOLIO", "핵심 사업 영역")
    gx, gyp = 0.3, 0.25
    gw = (W - 2 * MX - gx) / 2
    gh = 2.05
    sy = 2.15
    for i, (tt, dd) in enumerate(c["grid"]):
        cc, rr = i % 2, i // 2
        x = MX + cc * (gw + gx); y = sy + rr * (gh + gyp)
        dk.rect(s, x, y, gw, gh, fill=SURFACE, line=HAIR, line_w=1.0,
                shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
        dk.rect(s, x + 0.32, y + 0.32, 0.5, 0.5, fill=PRIMARY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.28)
        dk.add_text(s, x + 0.32, y + 0.32, 0.5, 0.5, [(f"{i+1:02d}", dict(name=FL, size=14, color=ONP))],
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        dk.add_text(s, x + 1.0, y + 0.34, gw - 1.3, 0.5, [(tt, dict(name=FKR, size=16, bold=True, color=INK, spacing=-0.3))],
                    anchor=MSO_ANCHOR.MIDDLE)
        dk.add_text(s, x + 0.32, y + 1.05, gw - 0.6, 0.8, [(dd, dict(name=FKR, size=12, color=MUTED))], line_spacing=1.25)

    # ── S5 클로징 (primary 풀블리드, 3존 리듬: 상단 킥커 / 중앙 메시지 / 하단 출처) ─
    s = dk.blank_slide(prs); dk.set_bg(s, PRIMARY)
    dk.add_text(s, MX, 0.75, W - 2 * MX, 0.3, [(c["eyebrow"], dict(name=FL, size=11, color=ONP, spacing=1.8))])
    dk.add_text(s, MX, 2.85, W - 2 * MX, 1.8, [(c["closing"], dict(name=FKR, size=30, bold=True, color=ONP, spacing=-0.5))],
                line_spacing=1.2)
    dk.rect(s, MX, 4.85, 1.0, 0.05, fill=ACCENT)
    dk.add_text(s, MX, 5.15, W - 2 * MX, 0.4, [(c["footer"], dict(name=FKR, size=11, color=ONP))])
    dk.add_text(s, MX, H - 0.6, W - 2 * MX, 0.3,
                [("design-core × pptx-design · SPEC-DESIGN-CORE-001 PoC", dict(name=FKR, size=9, color=ONP))])

    dk.save_deck(prs, out)
    return out


def main():
    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    for preset in ("samsung-sds", "kari"):
        out = os.path.join(out_dir, f"{preset}-poc.pptx")
        build(preset, out, CONTENT[preset])
        print("saved", out)


if __name__ == "__main__":
    main()
