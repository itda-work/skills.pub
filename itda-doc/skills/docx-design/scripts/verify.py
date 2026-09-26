# -*- coding: utf-8 -*-
"""verify — DOCX 디자인 검증 게이트 (SPEC-OFFICE-DOC-GEN-DEEPEN-001).

docx 는 흐름(flow) 문서라 pptx 의 절대좌표 경계이탈 검사가 없다. 대신 docx 의
HARD 불변량은 **한글 East Asian 바인딩**(이 SPEC 의 핵심 재설계)이다 — 한글 run 이
eastAsia 폰트로 바인딩되지 않으면 라틴 디스플레이 폰트가 글리프를 먹어 깨진다.

층:
  (A) 콘텐츠 존재: 문서에 텍스트가 하나도 없으면 빈 문서 [HARD]
  (B) 콘텐츠 대조: --tokens 의 필수 토큰이 본문(단락+표)에 존재 [HARD]
  (C) ★한글 eastAsia 바인딩: 한글 run 이 run/스타일/docDefaults 어디서도 eastAsia 미해소 [HARD]
       — 라틴 디스플레이 폰트로 eastAsia 가 바인딩된 의심 케이스는 [advisory]
  (D) 구조/스타일 휴리스틱: 본문은 있는데 헤딩 0개·빈 표 셀 [advisory]
  (E) 렌더 빈 페이지: 렌더 PNG 가 완전 백지 [advisory] (렌더 도구 부재 시 생략)

HARD GATE = (빈문서 + 토큰누락 + 한글_eastAsia_미바인딩) == 0 → PASS 시 exit 0.

사용:
  py -3 verify.py <docx> [--tokens tokens.txt] [--ko 삼성전자,하이닉스]
                         [--out DIR] [--dpi 130] [--no-render]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as render_mod  # noqa: E402
import dockit as dk  # noqa: E402 (has_hangul 재사용)


# ──────────────────────────────────────────────── 본문 순회 (단락+표, 중첩 포함)
def _iter_block_items(parent):
    """body 또는 _Cell 의 자식 블록(Paragraph/Table)을 문서 순서대로."""
    if hasattr(parent, "element"):
        el = parent.element.body if hasattr(parent.element, "body") else parent._tc
    else:  # _Cell
        el = parent._tc
    for child in el.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _all_paragraphs(parent):
    for block in _iter_block_items(parent):
        if isinstance(block, Paragraph):
            yield block
        else:  # Table
            for row in block.rows:
                for cell in row.cells:
                    yield from _all_paragraphs(cell)


def _doc_text(doc):
    return "\n".join(p.text for p in _all_paragraphs(doc))


# ──────────────────────────────────────────────── 스타일 eastAsia 해소
def _style_eastasia_map(doc):
    m = {}
    for st in doc.styles.element.findall(qn("w:style")):
        sid = st.get(qn("w:styleId"))
        rpr = st.find(qn("w:rPr"))
        ea = None
        if rpr is not None:
            rf = rpr.find(qn("w:rFonts"))
            if rf is not None:
                ea = rf.get(qn("w:eastAsia"))
        m[sid] = ea
    return m


def _docdefaults_eastasia(doc):
    dd = doc.styles.element.find(qn("w:docDefaults"))
    if dd is None:
        return None
    rprd = dd.find(qn("w:rPrDefault"))
    if rprd is None:
        return None
    rpr = rprd.find(qn("w:rPr"))
    if rpr is None:
        return None
    rf = rpr.find(qn("w:rFonts"))
    return rf.get(qn("w:eastAsia")) if rf is not None else None


def _run_eastasia(run):
    rpr = run._element.find(qn("w:rPr"))
    if rpr is None:
        return None
    rf = rpr.find(qn("w:rFonts"))
    return rf.get(qn("w:eastAsia")) if rf is not None else None


def _run_ascii(run):
    rpr = run._element.find(qn("w:rPr"))
    if rpr is None:
        return None
    rf = rpr.find(qn("w:rFonts"))
    return rf.get(qn("w:ascii")) if rf is not None else None


def resolve_eastasia(run, style_id, style_map, docdef_ea):
    """run → 효과적 eastAsia 폰트(run > 단락스타일 > Normal > docDefaults)."""
    return (_run_eastasia(run)
            or (style_map.get(style_id) if style_id else None)
            or style_map.get("Normal")
            or docdef_ea)


# 한글 run 에 eastAsia 로 박히면 의심스러운(라틴 디스플레이) 폰트 — 정확 판별이 아니라 트립와이어
def _looks_latin_only(font_name):
    if not font_name:
        return False
    n = font_name.strip().lower()
    latinish = ("helvetica", "arial", "calibri", "times", "georgia", "garamond",
                "palatino", "impact", "courier", "verdana", "tahoma", "cambria",
                "didot", "futura", "roboto", "inter", "open sans", "lato")
    if any(k in n for k in latinish):
        return True
    return False


# ──────────────────────────────────────────────── (F) 색 대비(가독성) 해소
def _wcag_lum(hex6):
    def _lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _safe_hex6(c):
    """color → 검증된 6자리 hex 또는 None(파싱 불가: 테마/인덱스/잘못된 값)."""
    h = dk._hex6(c)
    if len(h) != 6:
        return None
    try:
        int(h, 16)
    except ValueError:
        return None
    return h


def _wcag_contrast(c1, c2):
    h1, h2 = _safe_hex6(c1), _safe_hex6(c2)
    if h1 is None or h2 is None:
        return 21.0   # 파싱 불가 색(외부 docx 의 테마색 등)은 검사 생략 — 거짓양성 회피
    l1, l2 = _wcag_lum(h1), _wcag_lum(h2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _style_color_map(doc):
    """styleId → 효과적 w:color val(없으면 None)."""
    m = {}
    for st in doc.styles.element.findall(qn("w:style")):
        sid = st.get(qn("w:styleId"))
        rpr = st.find(qn("w:rPr"))
        val = None
        if rpr is not None:
            col = rpr.find(qn("w:color"))
            if col is not None:
                v = col.get(qn("w:val"))
                if v and v != "auto":
                    val = v
        m[sid] = val
    return m


def _docdefaults_color(doc):
    dd = doc.styles.element.find(qn("w:docDefaults"))
    if dd is None:
        return None
    rprd = dd.find(qn("w:rPrDefault"))
    rpr = rprd.find(qn("w:rPr")) if rprd is not None else None
    col = rpr.find(qn("w:color")) if rpr is not None else None
    if col is None:
        return None
    v = col.get(qn("w:val"))
    return None if (not v or v == "auto") else v


def _run_color(run):
    rpr = run._element.find(qn("w:rPr"))
    col = rpr.find(qn("w:color")) if rpr is not None else None
    if col is None:
        return None
    v = col.get(qn("w:val"))
    return None if (not v or v == "auto") else v


def _shd_fill(container):
    shd = container.find(qn("w:shd")) if container is not None else None
    if shd is None:
        return None
    v = shd.get(qn("w:fill"))
    return None if (not v or v == "auto") else v


def _effective_fill(run):
    """run 의 효과적 배경: run shd > 단락 shd > 셀 shd > 페이지(흰색)."""
    r = run._element
    f = _shd_fill(r.find(qn("w:rPr")))
    if f:
        return f
    p = r.getparent()
    while p is not None and p.tag != qn("w:p"):
        p = p.getparent()
    if p is not None:
        f = _shd_fill(p.find(qn("w:pPr")))
        if f:
            return f
    # 셀 음영: 가장 안쪽 셀부터 바깥 셀까지(중첩 표) — 첫 음영을 채택. 안쪽 셀이
    # 음영 없으면 바깥 셀 음영이 실제 시각 배경이다.
    node = r.getparent()
    while node is not None:
        if node.tag == qn("w:tc"):
            f = _shd_fill(node.find(qn("w:tcPr")))
            if f:
                return f
        node = node.getparent()
    return "FFFFFF"


def verify(docx_path, tokens=None, ko=None, out_dir=None, dpi=130, do_render=True):
    docx_path = render_mod.winpath(docx_path)
    doc = Document(docx_path)
    stem = os.path.splitext(os.path.basename(docx_path))[0]
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(docx_path)), "_verify")
    os.makedirs(out_dir, exist_ok=True)

    issues = {
        "empty_document": [], "missing_content": [], "kr_unbound": [],
        "low_contrast": [], "weak_contrast": [],
        "kr_eastasia_latinish": [], "no_headings": [], "empty_table_cells": [],
        "blank_page": [], "render_unavailable": [],
    }

    text = _doc_text(doc)
    if not text.strip():
        issues["empty_document"].append({"note": "문서에 텍스트가 없음"})

    # (B) 토큰 대조
    if tokens:
        compact = text.replace(" ", "")
        for tok in tokens:
            if tok.replace(" ", "") not in compact:
                issues["missing_content"].append(tok)

    # (C) 한글 eastAsia 바인딩
    style_map = _style_eastasia_map(doc)
    docdef_ea = _docdefaults_eastasia(doc)
    kr_total = 0
    for p in _all_paragraphs(doc):
        sid = None
        try:
            sid = p.style.style_id if p.style is not None else None
        except Exception:
            sid = None
        for run in p.runs:
            t = run.text or ""
            if not dk.has_hangul(t):
                continue
            kr_total += 1
            ea = resolve_eastasia(run, sid, style_map, docdef_ea)
            if not ea:
                issues["kr_unbound"].append({"text": t[:24].replace("\n", " "), "style": sid})
            elif _looks_latin_only(ea):
                issues["kr_eastasia_latinish"].append(
                    {"text": t[:24].replace("\n", " "), "font": ea})

    # (F) 색 대비(가독성): 라이트 본문 위 텍스트가 배경과 충분히 대비되는가.
    #   HARD = ratio < 3.0(사실상 안 보임 — 라이트 위 라이트 텍스트 등),
    #   ADVISORY = 3.0~4.5(대형 텍스트는 통과, 본문은 보강 권장). 다크 프리셋을
    #   라이트 본문에 그대로 쓰면(보정 전) 여기서 잡힌다(샌드위치 정책 강제선).
    color_map = _style_color_map(doc)
    docdef_col = _docdefaults_color(doc)
    for p in _all_paragraphs(doc):
        try:
            sid = p.style.style_id if p.style is not None else None
        except Exception:
            sid = None
        for run in p.runs:
            t = run.text or ""
            if not t.strip():
                continue
            col = (_run_color(run) or (color_map.get(sid) if sid else None)
                   or color_map.get("Normal") or docdef_col or "000000")
            bg = _effective_fill(run)
            ratio = _wcag_contrast(col, bg)
            rec = {"text": t[:24].replace("\n", " "), "fg": "#" + dk._hex6(col),
                   "bg": "#" + dk._hex6(bg), "ratio": round(ratio, 2)}
            if ratio < 3.0:
                issues["low_contrast"].append(rec)
            elif ratio < 4.5:
                issues["weak_contrast"].append(rec)

    # (D) 구조/스타일 휴리스틱
    headings = sum(1 for p in _all_paragraphs(doc)
                   if (getattr(p.style, "style_id", "") or "").startswith("Heading"))
    if text.strip() and headings == 0:
        issues["no_headings"].append({"note": "본문은 있으나 헤딩 0개 — 위계 부재 의심"})
    for block in _iter_block_items(doc):
        if isinstance(block, Table):
            for ri, row in enumerate(block.rows):
                for ci, cell in enumerate(row.cells):
                    if not cell.text.strip():
                        issues["empty_table_cells"].append({"row": ri, "col": ci})

    # (E) 렌더 + 빈 페이지
    pages = []
    if do_render:
        try:
            res = render_mod.render(docx_path, out_dir=os.path.join(out_dir, f"{stem}_render"), dpi=dpi)
            if res["engine"] is None:
                issues["render_unavailable"].append({"note": res.get("error")})
            pages = res.get("pages", [])
        except Exception as e:  # 렌더 인프라 문제는 덱 결함 아님
            issues["render_unavailable"].append({"note": f"렌더 실패: {e}"})
    else:
        issues["render_unavailable"].append({"note": "do_render=False"})

    for pi, png in enumerate(pages, start=1):
        try:
            from PIL import Image
            im = Image.open(png).convert("RGB").resize((80, 110))
            cols = im.getcolors(80 * 110) or []
            if cols and max(cols, key=lambda x: x[0])[0] / (80 * 110) > 0.997:
                issues["blank_page"].append({"page": pi})
        except Exception:
            pass

    counts = {k: len(v) for k, v in issues.items()}
    gate = (counts["empty_document"] + counts["missing_content"]
            + counts["kr_unbound"] + counts["low_contrast"])
    result = {
        "docx": docx_path, "hard_gate_pass": gate == 0, "counts": counts,
        "kr_runs_total": kr_total, "headings": headings,
        "render_pages": len(pages), "issues": issues,
    }
    json.dump(result, open(os.path.join(out_dir, f"{stem}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return result


def main():
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--tokens", help="필수 토큰 파일(1줄 1토큰)")
    ap.add_argument("--ko", help="(예약) 한글명 advisory")
    ap.add_argument("--out", help="검증 산출물 디렉토리")
    ap.add_argument("--dpi", type=int, default=130)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    tokens = None
    if a.tokens and os.path.exists(a.tokens):
        tokens = [ln.strip() for ln in open(a.tokens, encoding="utf-8") if ln.strip()]
    r = verify(a.docx, tokens=tokens, out_dir=a.out, dpi=a.dpi, do_render=not a.no_render)
    c = r["counts"]
    print(f"[HARD] empty_doc={c['empty_document']} missing_tokens={c['missing_content']} "
          f"kr_unbound={c['kr_unbound']} low_contrast={c['low_contrast']} (한글 run {r['kr_runs_total']}개)")
    print(f"[ADVISORY] weak_contrast={c['weak_contrast']} kr_eastasia_latinish={c['kr_eastasia_latinish']} "
          f"no_headings={c['no_headings']} empty_table_cells={c['empty_table_cells']} blank_page={c['blank_page']} "
          f"render_unavailable={c['render_unavailable']} (헤딩 {r['headings']}개, 렌더 {r['render_pages']}p)")
    for o in r["issues"]["missing_content"]:
        print(f"  [토큰누락] '{o}'")
    for o in r["issues"]["low_contrast"]:
        print(f"  [HARD/대비] {o['ratio']}:1 (fg {o['fg']} / bg {o['bg']}): '{o['text']}' — 사실상 안 보임")
    for o in r["issues"]["weak_contrast"][:8]:
        print(f"  [ADVISORY/대비] {o['ratio']}:1 (fg {o['fg']} / bg {o['bg']}): '{o['text']}'")
    for o in r["issues"]["kr_unbound"]:
        print(f"  [HARD/한글] eastAsia 미바인딩 (style={o['style']}): '{o['text']}' — 라틴 폰트 글리프 잠식 위험")
    for o in r["issues"]["kr_eastasia_latinish"]:
        print(f"  [ADVISORY/한글] eastAsia 가 라틴 폰트 '{o['font']}': '{o['text']}' — 한글 폰트로 교체 권장")
    for o in r["issues"]["render_unavailable"]:
        print(f"  [render] {o['note']}")
    print("HARD GATE:", "PASS" if r["hard_gate_pass"] else "FAIL")
    sys.exit(0 if r["hard_gate_pass"] else 1)


if __name__ == "__main__":
    main()
