# -*- coding: utf-8 -*-
"""design-core 프리뷰 생성기 — 토큰 → 실제 샘플(web 페이지 + pptx 표지).

저작 워크플로우(SKILL.md 관문 C)의 "의도 확인" 단계에서 쓴다. 아직 library 에 없는
임시 토큰(dict·DESIGN.md 텍스트·파일)도 받아, **모든 토큰 색이 제 역할로 쓰인** web 한 장과
pptx 표지 한 장을 만든다. 사용자가 보고 컨펌/수정한다.

원칙:
- 프리뷰는 팔레트 나열이 아니라 "각 색이 적절한 곳에 쓰였는지" 검토하는 화면이다.
  모든 색(bg·surface·fg·muted·border·primary·accent·success·danger)이 컴포넌트 + 차트에 등장한다.
- 단독 HTML — 외부 라이브러리/CDN 없이 순수 인라인 SVG 차트라 오프라인에서도 그대로 열린다.

usage:
  python3 preview.py <이름|경로|->  [출력디렉토리]   (-: stdin 으로 DESIGN.md 텍스트)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design_core as dc  # noqa: E402

_ROLE = {
    "bg": "배경", "surface": "카드 면", "fg": "본문·제목", "muted": "보조·캡션",
    "border": "테두리·구분", "primary": "주색·버튼", "accent": "강조·배지",
    "success": "상승·긍정", "danger": "하락·경고",
}


# ── 인라인 SVG 차트 (외부 의존 0, 색은 CSS var 로 토큰 상속) ──────────────
def _svg_bars():
    """막대 — primary vs accent 두 시리즈(색 구분 확인)."""
    data = [(70, 48), (85, 60), (58, 74), (92, 40)]
    bw, base, maxh, x0 = 20, 150, 120, 26
    bars = f'<line x1="18" y1="{base}" x2="304" y2="{base}" stroke="var(--border)"/>'
    for i, (p, a) in enumerate(data):
        gx = x0 + i * 68
        hp, ha = maxh * p / 100, maxh * a / 100
        bars += f'<rect x="{gx}" y="{base-hp:.0f}" width="{bw}" height="{hp:.0f}" rx="3" fill="var(--primary)"/>'
        bars += f'<rect x="{gx+bw+5}" y="{base-ha:.0f}" width="{bw}" height="{ha:.0f}" rx="3" fill="var(--accent)"/>'
    return f'<svg viewBox="0 0 320 165" width="100%" role="img">{bars}</svg>'


def _svg_line():
    """추세 — primary 라인 + accent 영역."""
    vals = [28, 52, 44, 78, 70, 96, 112]
    base, n = 138, 7
    coords = [(20 + i * (276 / (n - 1)), base - v * 1.05) for i, v in enumerate(vals)]
    poly = " ".join(f"{x:.0f},{y:.0f}" for x, y in coords)
    area = f"M20,{base} " + " ".join(f"L{x:.0f},{y:.0f}" for x, y in coords) + f" L{coords[-1][0]:.0f},{base} Z"
    dots = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="var(--primary)"/>' for x, y in coords)
    return (f'<svg viewBox="0 0 320 160" width="100%" role="img">'
            f'<path d="{area}" fill="var(--accent)" opacity="0.16"/>'
            f'<polyline points="{poly}" fill="none" stroke="var(--primary)" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round"/>{dots}</svg>')


def _svg_donut():
    """구성 — 팔레트 도넛(primary·accent·success·danger·muted 세그먼트)."""
    r, cx, cy = 46, 70, 70
    circ = 2 * math.pi * r
    segs = [("primary", 0.34), ("accent", 0.24), ("success", 0.18), ("danger", 0.12), ("muted", 0.12)]
    off = 0.0
    ring = f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="none" stroke="var(--border)" stroke-width="20" opacity="0.4"/>'
    for name, ratio in segs:
        seg = circ * ratio
        ring += (f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="none" stroke="var(--{name})" stroke-width="20" '
                 f'stroke-dasharray="{seg:.1f} {circ-seg:.1f}" stroke-dashoffset="{-off:.1f}" '
                 f'transform="rotate(-90 {cx} {cy})"/>')
        off += seg
    return f'<svg viewBox="0 0 200 140" width="100%" role="img">{ring}</svg>'


_PAGE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
/*ROOT*/
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:var(--font-body);line-height:1.6}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px}
.palette{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:32px;padding-bottom:26px;border-bottom:1px solid var(--border)}
.sw{display:flex;align-items:center;gap:8px}
.chip{width:40px;height:40px;border-radius:8px;border:1px solid var(--border);display:inline-block;flex:none}
.sw code{font-size:11px;color:var(--muted);font-family:ui-monospace,monospace;line-height:1.35}
.sw code b{color:var(--fg);font-size:11px}
.kicker{font-family:var(--font-display);font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-family:var(--font-display);font-size:40px;font-weight:700;letter-spacing:-.02em;max-width:18ch;margin-top:8px}
.badge{display:inline-block;vertical-align:middle;background:var(--accent);color:#fff;font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;margin-left:10px}
.sub{color:var(--muted);font-size:18px;margin-top:12px;max-width:58ch}
.actions{margin-top:22px;display:flex;gap:10px;align-items:center}
.btn{display:inline-block;background:var(--primary);color:#fff;padding:11px 22px;border-radius:var(--radius);font-weight:600;text-decoration:none}
.btn-2{display:inline-block;border:1px solid var(--accent);color:var(--accent);background:transparent;padding:10px 20px;border-radius:var(--radius);font-weight:600;text-decoration:none}
.note{margin-top:24px;background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--danger);border-radius:var(--radius);padding:12px 16px;font-size:14px}
.note b{color:var(--danger)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:30px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px}
.card .n{font-family:var(--font-display);font-size:30px;font-weight:700;color:var(--primary)}
.card .l{font-size:13px;margin-top:6px}
.card .cap{font-size:12px;color:var(--muted);margin-top:2px}
.up{color:var(--success);font-size:12px;margin-top:8px;font-weight:600}
.down{color:var(--danger);font-size:12px;margin-top:8px;font-weight:600}
.charts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
.chart{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px}
.ct{font-size:12px;color:var(--muted);margin-bottom:10px}
.lg{display:flex;gap:12px;margin-top:8px;font-size:11px;color:var(--muted);flex-wrap:wrap}
.lg i{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:middle}
.type{margin-top:38px;border-top:1px solid var(--border);padding-top:24px}
.type .d{font-family:var(--font-display);font-size:28px}
.type .b{font-family:var(--font-body);font-size:15px;color:var(--muted);margin-top:8px;max-width:60ch}
footer{margin-top:38px;border-top:1px solid var(--border);padding-top:16px;color:var(--muted);font-size:12px}
</style></head><body><div class="wrap">
<div class="palette"><!--SWATCH--></div>
<div class="kicker">DESIGN PREVIEW</div>
<h1>{{TITLE}}<span class="badge">NEW</span></h1>
<p class="sub">이 토큰으로 만든 화면입니다. 위 팔레트의 <b>모든 색</b>이 아래 컴포넌트와 차트에서 실제 역할로 쓰였으니, 각 색이 적절한 자리에 있는지 확인하세요.</p>
<div class="actions">
  <a class="btn" href="#">주요 동작 (primary)</a>
  <a class="btn-2" href="#">보조 동작 (accent)</a>
</div>
<div class="note"><b>경고/하락</b> — danger 색은 이런 알림 띠와 하락 수치에 쓰입니다.</div>
<div class="cards">
<div class="card"><div class="n">128%</div><div class="l">샘플 지표 A</div><div class="cap">caption · muted</div><div class="up">▲ +12% 상승 (success)</div></div>
<div class="card"><div class="n">24.6</div><div class="l">샘플 지표 B</div><div class="cap">caption · muted</div><div class="down">▼ -5% 하락 (danger)</div></div>
<div class="card"><div class="n">3,200</div><div class="l">샘플 지표 C</div><div class="cap">caption · muted</div><div class="up">▲ 견조 (success)</div></div>
</div>
<div class="charts">
  <div class="chart"><div class="ct">막대 · primary vs accent</div><!--BARS-->
    <div class="lg"><span><i style="background:var(--primary)"></i>primary</span><span><i style="background:var(--accent)"></i>accent</span></div></div>
  <div class="chart"><div class="ct">추세 · primary 라인 + accent 영역</div><!--LINE--></div>
  <div class="chart"><div class="ct">구성 · 팔레트 도넛</div><!--DONUT-->
    <div class="lg"><span><i style="background:var(--primary)"></i>primary</span><span><i style="background:var(--accent)"></i>accent</span><span><i style="background:var(--success)"></i>success</span><span><i style="background:var(--danger)"></i>danger</span><span><i style="background:var(--muted)"></i>muted</span></div></div>
</div>
<div class="type">
<div class="d">디스플레이 폰트 — 제목용 Display 1234</div>
<div class="b">본문 폰트 — 한글과 영문(ABC abc 0123)이 이렇게 보입니다. 가독성과 분위기가 의도와 맞는지 확인하세요.</div>
</div>
<footer>design-core 프리뷰 · 9색 전부 컴포넌트·차트에서 역할대로 사용됨 · 단독 HTML(외부 의존 0) · 의도가 맞으면 컨펌하세요</footer>
</div></body></html>
"""


def make_web_preview(tokens: dc.DesignTokens, outpath: str, title: str = "디자인 프리뷰") -> str:
    root_css = dc.to_css_vars(tokens)
    c, s = tokens.color, tokens.semantic
    order = [("bg", c.get("bg")), ("surface", c.get("surface")), ("fg", c.get("fg")),
             ("muted", c.get("muted")), ("border", c.get("border")),
             ("primary", c.get("primary")), ("accent", c.get("accent")),
             ("success", s.get("up")), ("danger", s.get("down"))]
    swatch = "".join(
        f'<div class="sw"><span class="chip" style="background:{hx}"></span>'
        f'<code><b>{k}</b><br>{_ROLE.get(k, "")}<br>{hx}</code></div>'
        for k, hx in order if hx
    )
    html = (_PAGE.replace("/*ROOT*/", root_css.strip())
                 .replace("<!--SWATCH-->", swatch)
                 .replace("<!--BARS-->", _svg_bars())
                 .replace("<!--LINE-->", _svg_line())
                 .replace("<!--DONUT-->", _svg_donut())
                 .replace("{{TITLE}}", title))
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)
    return outpath


def make_pptx_cover(tokens: dc.DesignTokens, outpath: str, title: str = "디자인 프리뷰") -> str:
    sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "pptx-design", "scripts"))
    import deckkit as dk  # noqa: E402
    P = {k: (v.lstrip("#") if isinstance(v, str) else v) for k, v in tokens.pptx_palette().items()}
    FKR = dk.kr_font_name()
    W, H, MX = dk.DEFAULT_W_IN, dk.DEFAULT_H_IN, 0.85
    prs = dk.new_deck()
    s = dk.blank_slide(prs); dk.set_bg(s, P["primary"])
    dk.add_text(s, MX, 0.8, W - 2 * MX, 0.4,
                [("DESIGN PREVIEW", dict(name="Helvetica Neue", size=12, color="FFFFFF", spacing=2.0))])
    dk.rect(s, MX, 2.2, 1.0, 0.05, fill=P["accent"])
    dk.add_text(s, MX, 2.5, W - 2 * MX, 1.5,
                [(title, dict(name=FKR, size=42, bold=True, color="FFFFFF", spacing=-0.5))], line_spacing=1.05)
    dk.add_text(s, MX, 4.15, W - 2 * MX, 0.6,
                [("이 토큰으로 만든 발표자료 표지 미리보기입니다.", dict(name=FKR, size=16, color="FFFFFF"))])
    cw = (W - 2 * MX) / 3
    strip = [("상승 (success)", "#" + P.get("up", "------")),
             ("하락 (danger)", "#" + P.get("down", "------")),
             ("강조 (accent)", "#" + P.get("accent", "------"))]
    for i, (k, v) in enumerate(strip):
        x = MX + i * cw
        dk.add_text(s, x, 5.85, cw - 0.2, 0.3, [(k, dict(name=FKR, size=11, color="FFFFFF"))])
        dk.add_text(s, x, 6.15, cw - 0.2, 0.4, [(v, dict(name=FKR, size=14, bold=True, color=P["accent"]))])
    dk.save_deck(prs, outpath)
    return outpath


def preview(source, outdir: str, name: str = "preview", title: str = "디자인 프리뷰", pptx: bool = True) -> dict:
    tokens = dc.load(source)
    os.makedirs(outdir, exist_ok=True)
    out = {"web": make_web_preview(tokens, os.path.join(outdir, f"{name}.html"), title)}
    if pptx:
        try:
            out["pptx"] = make_pptx_cover(tokens, os.path.join(outdir, f"{name}-cover.pptx"), title)
        except Exception as e:  # noqa: BLE001 — pptx 의존(python-pptx/deckkit) 없으면 web 만
            out["pptx_error"] = str(e)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        # --help 를 토큰 이름으로 받으면 FileNotFoundError 로 죽는다(#1630 실측)
        print("usage: python3 preview.py <이름|경로|-> [출력디렉토리]")
        return 0 if argv else 2
    src = argv[0]
    outdir = argv[1] if len(argv) > 1 else os.path.join(HERE, os.pardir, "examples", "preview")
    if src == "-":
        src = sys.stdin.read()
    res = preview(src, outdir)
    print("web :", res.get("web"))
    print("pptx:", res.get("pptx") or f"(건너뜀: {res.get('pptx_error')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
