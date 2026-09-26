"""render — soffice headless 로 PPTX→PDF→JPG 썸네일 (SPEC-PPTX-DESIGN-001 REQ-007).

병렬 안전: 슬러그별 격리 프로파일(-env:UserInstallation). 생성엔 불필요, 검증/미리보기용.

사용: python3 render.py <pptx_path> [out_dir] [--dpi 110]
"""
import os
import sys
import glob
import subprocess


def render(pptx_path, out_dir=None, dpi=110):
    pptx_path = os.path.abspath(pptx_path)
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(pptx_path)
    stem = os.path.splitext(os.path.basename(pptx_path))[0]
    out_dir = os.path.abspath(out_dir or os.path.join(os.path.dirname(pptx_path), f"{stem}_render"))
    os.makedirs(out_dir, exist_ok=True)
    profile = f"/tmp/lo_pd_{stem}"
    subprocess.run(
        ["soffice", f"-env:UserInstallation=file://{profile}", "--headless",
         "--convert-to", "pdf", "--outdir", out_dir, pptx_path],
        capture_output=True, timeout=240,
    )
    pdf = os.path.join(out_dir, f"{stem}.pdf")
    if not os.path.exists(pdf):
        raise RuntimeError(f"PDF 변환 실패: {pdf} (soffice 설치/경로 확인)")
    subprocess.run(
        ["pdftoppm", "-jpeg", "-r", str(dpi), pdf, os.path.join(out_dir, "slide")],
        capture_output=True, timeout=240,
    )
    return sorted(glob.glob(os.path.join(out_dir, "slide*.jpg")))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        # --help 는 아래 필터(`not a.startswith("--")`)에서 걸러져 args 가 비고
        # IndexError 로 죽었다(#1630 실측)
        print("usage: python3 render.py <pptx_path> [out_dir] [--dpi N]")
        sys.exit(0 if len(sys.argv) > 1 else 2)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dpi = 110
    for a in sys.argv[1:]:
        if a.startswith("--dpi"):
            dpi = int(a.split("=", 1)[1]) if "=" in a else 110
    jpgs = render(args[0], args[1] if len(args) > 1 else None, dpi)
    print(f"렌더 {len(jpgs)}장:")
    for j in jpgs:
        print(" ", j)
