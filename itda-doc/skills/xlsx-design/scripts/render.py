# -*- coding: utf-8 -*-
"""render — .xlsx 를 페이지 PNG 로 렌더(시각 검수·검증용).

엔진 분기:
  - Windows: Microsoft Excel COM(설치 시) → PDF → PyMuPDF 래스터. fit-to-width 자동 설정.
  - 그 외 / Excel 부재: LibreOffice(soffice) → PDF → PyMuPDF.
둘 다 없으면 {engine: None, error: ...}.

사용:
  py -3 scripts/render.py <xlsx> [out_dir] [--dpi 130]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys


def winpath(p: str) -> str:
    if re.match(r"^/[a-zA-Z]/", p):
        p = p[1].upper() + ":" + p[2:]
    return os.path.abspath(p)


def _pdf_to_png(pdf_path, out_dir, stem, dpi):
    try:
        import fitz
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


def _render_excel_com(xlsx_path, pdf_path):
    try:
        import win32com.client as win32
    except ImportError:
        return "pywin32 미설치"
    import pythoncom
    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(xlsx_path, ReadOnly=True)
        for ws in wb.Worksheets:
            try:
                ws.PageSetup.Zoom = False
                ws.PageSetup.FitToPagesWide = 1
                ws.PageSetup.FitToPagesTall = False
                ws.PageSetup.Orientation = 2  # xlLandscape
            except Exception:
                pass
        wb.ExportAsFixedFormat(0, pdf_path)  # 0 = xlTypePDF
        return None
    except Exception as e:  # pragma: no cover - 환경 의존
        return f"Excel COM 실패: {e}"
    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:
            pass
        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _render_soffice(xlsx_path, out_dir):
    import shutil
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, xlsx_path],
            check=True, capture_output=True, timeout=120,
        )
    except Exception:
        return None
    stem = os.path.splitext(os.path.basename(xlsx_path))[0]
    pdf = os.path.join(out_dir, stem + ".pdf")
    return pdf if os.path.exists(pdf) else None


def render(xlsx_path, out_dir=None, dpi=130):
    xlsx_path = winpath(xlsx_path)
    if not os.path.isfile(xlsx_path):
        return {"engine": None, "pdf": None, "pages": [], "error": f"파일 없음: {xlsx_path}"}
    stem = os.path.splitext(os.path.basename(xlsx_path))[0]
    out_dir = winpath(out_dir) if out_dir else os.path.join(os.path.dirname(xlsx_path), "_render")
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, stem + ".pdf")

    engine = None
    error = None
    if sys.platform.startswith("win"):
        err = _render_excel_com(xlsx_path, pdf_path)
        if err is None:
            engine = "excel-com"
        else:
            error = err
    if engine is None:
        pdf = _render_soffice(xlsx_path, out_dir)
        if pdf:
            engine, pdf_path, error = "libreoffice", pdf, None
        elif error is None:
            error = "렌더 엔진 없음(Excel COM/LibreOffice 모두 불가)"

    if engine is None:
        return {"engine": None, "pdf": None, "pages": [], "error": error}
    pages, png_err = _pdf_to_png(pdf_path, out_dir, stem, dpi)
    return {"engine": engine, "pdf": pdf_path, "pages": pages, "error": png_err}


def main(argv):
    if not argv:
        print("usage: render.py <xlsx> [out_dir] [--dpi N]")
        return 2
    xlsx = argv[0]
    out_dir, dpi = None, 130
    rest = argv[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--dpi" and i + 1 < len(rest):
            dpi = int(rest[i + 1]); i += 2
        else:
            out_dir = rest[i]; i += 1
    res = render(xlsx, out_dir, dpi)
    print(f"engine={res['engine']} pages={len(res['pages'])} error={res['error']}")
    for p in res["pages"]:
        print(" ", p)
    return 0 if res["engine"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
