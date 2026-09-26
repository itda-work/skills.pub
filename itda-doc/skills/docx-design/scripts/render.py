# -*- coding: utf-8 -*-
"""render — .docx 를 페이지 PNG 로 렌더(시각 검수·검증용).

엔진 분기:
  - Windows: Microsoft Word COM(설치 시) → PDF → PyMuPDF 래스터. LibreOffice/poppler 불요.
  - 그 외 / Word 부재: LibreOffice(soffice) → PDF → PyMuPDF.
둘 다 없으면 {engine: None, error: ...} 로 표면화(검증의 render 의존 검사만 생략).

PyMuPDF(fitz)는 PDF→PNG 에 필요. 없으면 PDF 까지만 산출.

사용:
  py -3 scripts/render.py <docx> [out_dir] [--dpi 140]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys


def winpath(p: str) -> str:
    """MSYS/git-bash 경로(/c/...)를 Windows 절대경로로 정규화."""
    if re.match(r"^/[a-zA-Z]/", p):
        p = p[1].upper() + ":" + p[2:]
    return os.path.abspath(p)


def _pdf_to_png(pdf_path, out_dir, stem, dpi):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return [], "PyMuPDF(fitz) 미설치 — PDF 까지만 산출"
    pages = []
    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            png = os.path.join(out_dir, f"{stem}-p{i + 1:02d}.png")
            pix.save(png)
            pages.append(png)
    finally:
        doc.close()
    return pages, None


def _render_word_com(docx_path, pdf_path):
    """Word COM 으로 docx→pdf. 필드(PAGE/NUMPAGES) 갱신 포함. 성공 시 None, 실패 시 사유."""
    try:
        import win32com.client as win32
    except ImportError:
        return "pywin32 미설치"
    import pythoncom
    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        doc = word.Documents.Open(docx_path, ReadOnly=True)
        try:
            doc.Fields.Update()
        except Exception:
            pass
        doc.SaveAs2(pdf_path, FileFormat=17)  # wdFormatPDF
        return None
    except Exception as e:  # pragma: no cover - 환경 의존
        return f"Word COM 실패: {e}"
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _render_soffice(docx_path, out_dir):
    """LibreOffice headless 로 docx→pdf. 성공 시 pdf 경로, 실패 시 None."""
    import shutil
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
            check=True, capture_output=True, timeout=120,
        )
    except Exception:
        return None
    stem = os.path.splitext(os.path.basename(docx_path))[0]
    pdf = os.path.join(out_dir, stem + ".pdf")
    return pdf if os.path.exists(pdf) else None


def render(docx_path, out_dir=None, dpi=140):
    """docx → 페이지 PNG. 반환 {engine, pdf, pages, error}."""
    docx_path = winpath(docx_path)
    if not os.path.isfile(docx_path):
        return {"engine": None, "pdf": None, "pages": [], "error": f"파일 없음: {docx_path}"}
    stem = os.path.splitext(os.path.basename(docx_path))[0]
    out_dir = winpath(out_dir) if out_dir else os.path.join(os.path.dirname(docx_path), "_render")
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, stem + ".pdf")

    engine = None
    error = None
    if sys.platform.startswith("win"):
        err = _render_word_com(docx_path, pdf_path)
        if err is None:
            engine = "word-com"
        else:
            error = err
    if engine is None:  # 비Windows 또는 Word 실패 → LibreOffice
        pdf = _render_soffice(docx_path, out_dir)
        if pdf:
            engine = "libreoffice"
            pdf_path = pdf
            error = None
        elif error is None:
            error = "렌더 엔진 없음(Word COM/LibreOffice 모두 불가)"

    if engine is None:
        return {"engine": None, "pdf": None, "pages": [], "error": error}

    pages, png_err = _pdf_to_png(pdf_path, out_dir, stem, dpi)
    return {"engine": engine, "pdf": pdf_path, "pages": pages, "error": png_err}


def main(argv):
    if not argv:
        print("usage: render.py <docx> [out_dir] [--dpi N]")
        return 2
    docx = argv[0]
    out_dir = None
    dpi = 140
    rest = argv[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--dpi" and i + 1 < len(rest):
            dpi = int(rest[i + 1])
            i += 2
        else:
            out_dir = rest[i]
            i += 1
    res = render(docx, out_dir, dpi)
    print(f"engine={res['engine']} pages={len(res['pages'])} error={res['error']}")
    for p in res["pages"]:
        print(" ", p)
    return 0 if res["engine"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
