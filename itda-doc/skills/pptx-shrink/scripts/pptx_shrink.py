#!/usr/bin/env python3
"""pptx 내부 이미지 재인코딩으로 파일 용량을 줄인다 (해상도 유지 · zip 직접 조작).

    python3 pptx_shrink.py report <덱.pptx> [--top N] [--json]
    python3 pptx_shrink.py shrink <덱.pptx> [-o 출력.pptx] [--quality 80] [--min-bytes 300000] [--json]
    python3 pptx_shrink.py shrink <덱.pptx> --in-place (--backup [경로] | --no-backup)
    python3 pptx_shrink.py shrink <덱.pptx> --quality 90 --downsample-ppi 220

report 는 추정이 아니라 실측이다 — 변환 대상 PNG 마다 품질 90/80/70 × 해상도 원본/220/150ppi 를 실제로
인코딩해 조합별 결과 크기를 표로 낸다(#1646). 해상도 축소는 슬라이드·레이아웃·마스터의 <p:pic> 표시 크기
(그룹 스케일 반영)보다 픽셀이 큰 이미지만 대상이며 슬라이드 XML 은 건드리지 않는다.

원본 보호 계약(#1645):
  - 기본은 **새 파일**(`<이름>-shrunk.pptx`) 저장. 원본은 읽기만 한다.
  - `--in-place` 는 `--backup [경로]` 또는 `--no-backup` 을 **명시**해야 동작한다. 둘 다 없으면
    거부(exit 2). 이 게이트는 SKILL.md 의 "사용자 확인" 을 스크립트가 강제하는 자리다.
  - 변환 뒤 verify(슬라이드·텍스트·노트·그림 수·rels 참조)를 자동으로 돌리고, 불일치면 산출을
    지우고(in-place 면 백업/원본을 되돌리고) exit 3. `--skip-verify` 는 개발용.

python-pptx 라운드트립을 쓰지 않는다 — zip 을 직접 열어 `ppt/media/*.png` 만 바꾸고 rels 의
Target 과 [Content_Types].xml 을 정합시킨다. 그래서 텍스트·애니메이션·노트·마스터는 바이트
그대로 남는다(hyve-training 12덱 212→57MB 실측 무손실, 2026-09-05).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image  # Pillow 없이는 아무 기능도 못 한다 — 시작 시점에 드러낸다(deps 측정 A0 계약)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify as _verify  # noqa: E402

DEFAULT_QUALITY = 80
DEFAULT_MIN_BYTES = 300_000
QUALITY_TIERS = (90, 80, 70)
PPI_TIERS = (220, 150)          # PowerPoint "그림 압축" 의 고화질 인쇄·웹 단계와 같은 눈금
EMU_PER_INCH = 914_400
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
PART_RE = re.compile(r"^ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$")
MEDIA_PNG_RE = re.compile(r"^ppt/media/.+\.png$", re.IGNORECASE)
MEDIA_RE = re.compile(r"^ppt/media/[^/]+$")  # 확장자가 URL 잔여물(`image8.xx&_nc_gid=…`)인 미디어도 실재한다(L 덱) — 이름 전체로 잡는다

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_VERIFY_FAILED = 3
EXIT_INPUT = 4


def _mb(n: int) -> float:
    return round(n / 1048576, 2)


def has_real_alpha(img) -> bool:
    """알파 채널이 실제로 쓰이는가(불투명하지 않은 픽셀이 있는가). 투명 PNG 는 JPEG 로 바꾸면 검게 깨진다."""
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
    elif img.mode == "P" and "transparency" in img.info:
        alpha = img.convert("RGBA").getchannel("A")
    elif img.mode == "PA":
        alpha = img.convert("RGBA").getchannel("A")
    else:
        return False
    lo, _hi = alpha.getextrema()
    return lo < 255


# ── 표시 크기 ─────────────────────────────────────────────────────────────────

def display_sizes(z: zipfile.ZipFile) -> dict[str, dict]:
    """미디어 → {"w_in","h_in","uses","unknown"}: 슬라이드·레이아웃·마스터의 <p:pic> 이 그 미디어를
    **가장 크게** 표시하는 인치 크기. 그룹(<p:grpSp>) 안이면 ext/chExt 스케일을 곱한다. srcRect(잘라내기)는
    무시한다 — 잘라낸 부분을 실제로 버리는 것은 이 스킬 범위 밖이고, 표시 크기는 보이는 영역의 크기다.
    <a:ext> 가 없는 pic 은 unknown 으로 표시해 축소 대상에서 뺀다(축소는 근거 없이는 하지 않는다)."""
    from xml.etree import ElementTree as ET

    names = set(z.namelist())
    out: dict[str, dict] = {}

    def rels_of(part: str) -> dict[str, str]:
        d, f = part.rsplit("/", 1)
        rn = f"{d}/_rels/{f}.rels"
        if rn not in names:
            return {}
        try:
            root = ET.fromstring(z.read(rn))
        except ET.ParseError:
            return {}
        return {r.get("Id"): "ppt/media/" + (r.get("Target") or "").split("/")[-1]
                for r in root.iter(f"{{{NS_REL}}}Relationship")
                if "/media/" in (r.get("Target") or "")}

    def walk(el, sx: float, sy: float, rels: dict[str, str]) -> None:
        for child in el:
            tag = child.tag
            if tag == f"{{{NS_P}}}grpSp":
                xfrm = child.find(f"{{{NS_P}}}grpSpPr/{{{NS_A}}}xfrm")
                nsx, nsy = sx, sy
                if xfrm is not None:
                    ext = xfrm.find(f"{{{NS_A}}}ext")
                    ch = xfrm.find(f"{{{NS_A}}}chExt")
                    if ext is not None and ch is not None:
                        try:
                            cw, chh = int(ch.get("cx")), int(ch.get("cy"))
                            if cw > 0 and chh > 0:
                                nsx *= int(ext.get("cx")) / cw
                                nsy *= int(ext.get("cy")) / chh
                        except (TypeError, ValueError):
                            pass
                walk(child, nsx, nsy, rels)
            elif tag == f"{{{NS_P}}}pic":
                blip = child.find(f".//{{{NS_A}}}blip")
                media = rels.get(blip.get(f"{{{NS_R}}}embed")) if blip is not None else None
                if not media:
                    continue
                slot = out.setdefault(media, {"w_in": 0.0, "h_in": 0.0, "uses": 0, "unknown": False})
                slot["uses"] += 1
                ext = child.find(f"{{{NS_P}}}spPr/{{{NS_A}}}xfrm/{{{NS_A}}}ext")
                try:
                    w = int(ext.get("cx")) * sx / EMU_PER_INCH
                    h = int(ext.get("cy")) * sy / EMU_PER_INCH
                except (AttributeError, TypeError, ValueError):
                    slot["unknown"] = True
                    continue
                slot["w_in"] = max(slot["w_in"], w)
                slot["h_in"] = max(slot["h_in"], h)
            else:
                walk(child, sx, sy, rels)

    for part in sorted(names):
        if not PART_RE.match(part):
            continue
        try:
            root = ET.fromstring(z.read(part))
        except ET.ParseError:
            continue
        walk(root, 1.0, 1.0, rels_of(part))
    return out


def target_px(img_w: int, img_h: int, disp: dict | None, ppi: int) -> tuple[int, int] | None:
    """표시 크기 기준 목표 픽셀. 축소가 성립할 때만(둘 다 원본보다 작을 때) 반환 — 확대·미상은 None."""
    if not ppi or not disp or disp.get("unknown") or disp["w_in"] <= 0 or disp["h_in"] <= 0:
        return None
    tw, th = int(round(disp["w_in"] * ppi)), int(round(disp["h_in"] * ppi))
    if tw < img_w and th < img_h and tw > 0 and th > 0:
        return tw, th
    return None


def encode_jpeg(img, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ── report ────────────────────────────────────────────────────────────────────

def analyze(infile: str, min_bytes: int, quality: int, top: int = 10) -> dict:
    """미디어 분해 + 조합별(품질 × 해상도) 실측. 파일을 쓰지 않는다.

    "예상" 이 아니다 — 변환 대상 PNG 마다 실제로 인코딩(필요하면 축소)해 바이트를 잰다."""
    total = os.path.getsize(infile)
    media_total = 0
    by_ext: dict[str, dict] = {}
    images: list[dict] = []
    convertible = 0
    kept_small = kept_alpha = 0
    conv_orig = 0                                   # 변환 대상의 원본 바이트 합
    tiers = {f"q{q}": {"orig": 0, **{str(p): 0 for p in PPI_TIERS}} for q in QUALITY_TIERS}
    down_candidates = {str(p): 0 for p in PPI_TIERS}
    with zipfile.ZipFile(infile, "r") as z:
        disp = display_sizes(z)
        for info in z.infolist():
            if not MEDIA_RE.match(info.filename):
                continue
            ext = os.path.splitext(info.filename)[1].lstrip(".").lower() or "(none)"
            size = info.file_size
            media_total += size
            slot = by_ext.setdefault(ext, {"count": 0, "bytes": 0})
            slot["count"] += 1
            slot["bytes"] += size
            d = disp.get(info.filename)
            row = {"name": os.path.basename(info.filename), "ext": ext, "bytes": size,
                   "width": None, "height": None, "alpha": None, "action": "keep",
                   "display_in": [round(d["w_in"], 2), round(d["h_in"], 2)] if d and not d["unknown"] else None,
                   "uses": d["uses"] if d else 0}
            if MEDIA_PNG_RE.match(info.filename):
                if size < min_bytes:
                    row["action"] = "keep_small"
                    kept_small += 1
                else:
                    try:
                        img = Image.open(io.BytesIO(z.read(info.filename)))
                        img.load()
                        row["width"], row["height"] = img.size
                        if has_real_alpha(img):
                            row["alpha"] = True
                            row["action"] = "keep_alpha"
                            kept_alpha += 1
                        else:
                            row["alpha"] = False
                            rgb = img.convert("RGB")
                            jpg = len(encode_jpeg(rgb, quality))
                            if jpg < size:
                                row["action"] = "convert"
                                row["est_bytes"] = jpg
                                convertible += 1
                                conv_orig += size
                                resized = {}
                                for ppi in PPI_TIERS:
                                    tp = target_px(rgb.width, rgb.height, d, ppi)
                                    if tp:
                                        resized[str(ppi)] = rgb.resize(tp, Image.LANCZOS)
                                        down_candidates[str(ppi)] += 1
                                row["target_px"] = {k: list(v.size) for k, v in resized.items()}
                                for q in QUALITY_TIERS:
                                    base = len(encode_jpeg(rgb, q))
                                    tiers[f"q{q}"]["orig"] += base
                                    for ppi in PPI_TIERS:
                                        im = resized.get(str(ppi))
                                        tiers[f"q{q}"][str(ppi)] += len(encode_jpeg(im, q)) if im is not None else base
                            else:
                                row["action"] = "keep_no_gain"
                    except Exception as exc:  # 깨진 PNG 는 건너뛴다 — 무음이 아니라 행으로 남긴다
                        row["action"] = f"keep_unreadable:{exc.__class__.__name__}"
            images.append(row)
    images.sort(key=lambda r: r["bytes"], reverse=True)
    # 조합별 결과 파일 크기(실측 바이트 합으로 환산 — 미디어 외 항목은 그대로)
    after = {qk: {rk: max(total - conv_orig + v, 0) for rk, v in qv.items()} for qk, qv in tiers.items()}
    key = f"q{quality}" if f"q{quality}" in after else "q80"
    base_after = after[key]["orig"]
    down_gain_pct = {p: (round((1 - after[key][p] / base_after) * 100, 1) if base_after else 0.0) for p in map(str, PPI_TIERS)}
    est_saved = conv_orig - tiers[key]["orig"] if key in tiers else 0
    return {
        "file": infile,
        "file_bytes": total,
        "file_mb": _mb(total),
        "media_bytes": media_total,
        "media_mb": _mb(media_total),
        "media_ratio": round(media_total / total, 3) if total else 0.0,
        "by_ext": by_ext,
        "convertible": convertible,
        "kept_small": kept_small,
        "kept_alpha": kept_alpha,
        "measured_saved_bytes": est_saved,
        "measured_saved_mb": _mb(est_saved),
        "measured_after_mb": _mb(base_after),
        "tiers_after_mb": {qk: {rk: _mb(v) for rk, v in qv.items()} for qk, qv in after.items()},
        "downsample_candidates": down_candidates,
        "downsample_gain_pct": down_gain_pct,
        "downsample_recommended": any(v >= 5.0 for v in down_gain_pct.values()),
        "top": images[:top],
        "params": {"min_bytes": min_bytes, "quality": quality, "quality_tiers": list(QUALITY_TIERS), "ppi_tiers": list(PPI_TIERS)},
    }


def print_report(rep: dict) -> None:
    print(f"파일: {rep['file']}  {rep['file_mb']} MB")
    print(f"미디어: {rep['media_mb']} MB ({rep['media_ratio'] * 100:.0f}% of file)")
    for ext, s in sorted(rep["by_ext"].items(), key=lambda kv: -kv[1]["bytes"]):
        print(f"  {ext:5s} {s['count']:3d}장 {_mb(s['bytes']):8.2f} MB")
    print(f"변환 대상: {rep['convertible']}장 · 작은 PNG 유지 {rep['kept_small']}장 · 투명 PNG 유지 {rep['kept_alpha']}장")
    q = rep["params"]["quality"]
    print(f"실측: {rep['file_mb']} MB → {rep['measured_after_mb']} MB (품질 {q}, 절감 {rep['measured_saved_mb']} MB)")
    if rep["convertible"]:
        ppis = rep["params"]["ppi_tiers"]
        print("조합별 결과 크기 (실측, MB):")
        print("           해상도 원본" + "".join(f"  {p:>4}ppi" for p in ppis))
        for qk, row in rep["tiers_after_mb"].items():
            print(f"  품질 {qk[1:]:>3}  {row['orig']:9.2f}" + "".join(f"  {row[str(p)]:7.2f}" for p in ppis))
        cand = rep["downsample_candidates"]
        gain = rep["downsample_gain_pct"]
        print("해상도 축소: " + " · ".join(f"{p}ppi 대상 {cand[str(p)]}장, 추가 절감 {gain[str(p)]}%" for p in ppis)
              + ("" if rep["downsample_recommended"] else "  → 이 덱에서는 권하지 않음(5% 미만)"))
    if rep["top"]:
        print("상위 이미지:")
        for r in rep["top"]:
            dim = f"{r['width']}×{r['height']}" if r["width"] else "-"
            est = f" → {_mb(r['est_bytes'])} MB" if r.get("est_bytes") else ""
            disp = f"  표시 {r['display_in'][0]}×{r['display_in'][1]}in" if r.get("display_in") else ""
            print(f"  {r['name']:18s} {_mb(r['bytes']):7.2f} MB {dim:>10s}  {r['action']}{est}{disp}")


# ── shrink ────────────────────────────────────────────────────────────────────

def shrink(infile: str, outfile: str, min_bytes: int, quality: int, downsample_ppi: int = 0) -> dict:
    """infile 을 읽어 outfile 로 쓴다. 변환 0장이면 outfile 을 만들지 않는다.
    downsample_ppi > 0 이면 표시 크기(display_sizes) 기준으로 그보다 큰 픽셀만 LANCZOS 축소한다."""
    with zipfile.ZipFile(infile, "r") as zin:
        infos = zin.infolist()
        raw = {i.filename: zin.read(i.filename) for i in infos}
        disp = display_sizes(zin) if downsample_ppi else {}

    renames: dict[str, str] = {}
    newdata: dict[str, bytes] = {}
    converted = kept = downsampled = 0
    saved = 0
    skipped: list[str] = []

    for name in list(raw):
        if not MEDIA_PNG_RE.match(name):
            continue
        data = raw[name]
        if len(data) < min_bytes:
            kept += 1
            continue
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as exc:
            skipped.append(f"{name}: 열기 실패 — {exc}")
            kept += 1
            continue
        if has_real_alpha(img):
            kept += 1
            continue
        rgb = img.convert("RGB")
        tp = target_px(rgb.width, rgb.height, disp.get(name), downsample_ppi)
        if tp:
            rgb = rgb.resize(tp, Image.LANCZOS)
        jpg = encode_jpeg(rgb, quality)
        if len(jpg) >= len(data):
            kept += 1
            continue
        if tp:
            downsampled += 1
        newname = re.sub(r"\.png$", ".jpeg", name, flags=re.IGNORECASE)
        base, n = newname, 1
        while newname in raw or newname in renames.values():
            newname = base[:-5] + f"_{n}.jpeg"
            n += 1
        renames[name] = newname
        newdata[newname] = jpg
        saved += len(data) - len(jpg)
        converted += 1

    result = {"converted": converted, "kept": kept, "downsampled": downsampled, "saved_bytes": saved, "skipped": skipped}
    if not converted:
        return result

    # rels 의 Target 치환 — 상대(../media/x)·절대(/ppt/media/x) 두 표기 모두
    short = {os.path.basename(k): os.path.basename(v) for k, v in renames.items()}
    for name in raw:
        if not name.lower().endswith(".rels"):
            continue
        text = raw[name].decode("utf-8")
        orig = text
        for old, new in short.items():
            text = text.replace(f"../media/{old}", f"../media/{new}")
            text = text.replace(f"/ppt/media/{old}", f"/ppt/media/{new}")
        if text != orig:
            newdata[name] = text.encode("utf-8")

    # [Content_Types].xml 에 jpeg Default 보장
    ct = "[Content_Types].xml"
    if ct in raw:
        text = raw[ct].decode("utf-8")
        if not re.search(r'Extension="jpeg"', text, re.IGNORECASE):
            ins = '<Default Extension="jpeg" ContentType="image/jpeg"/>'
            m = re.search(r"<Default\b", text)
            if m:
                text = text[: m.start()] + ins + text[m.start():]
            else:
                m2 = re.search(r"<Types[^>]*>", text)
                text = text[: m2.end()] + ins + text[m2.end():]
            newdata[ct] = text.encode("utf-8")

    with zipfile.ZipFile(outfile, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            name = info.filename
            outname = renames.get(name, name)
            data = newdata.get(outname, raw[name])
            zi = zipfile.ZipInfo(outname, date_time=info.date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zout.writestr(zi, data)
    return result


def default_output(infile: str) -> str:
    p = Path(infile)
    return str(p.with_name(f"{p.stem}-shrunk{p.suffix}"))


def default_backup(infile: str) -> str:
    p = Path(infile)
    return str(p.with_name(f"{p.stem}.bak{p.suffix}"))


def cmd_shrink(a: argparse.Namespace) -> int:
    infile = a.infile
    if not os.path.isfile(infile):
        return _fail(a, EXIT_INPUT, "FILE_NOT_FOUND", f"파일이 없습니다: {infile}")
    if not zipfile.is_zipfile(infile):
        return _fail(a, EXIT_INPUT, "NOT_PPTX", f"pptx(zip) 가 아닙니다: {infile}")

    # ── 원본 보호 게이트 ──
    if a.in_place:
        if a.output:
            return _fail(a, EXIT_USAGE, "USAGE", "--in-place 와 -o/--output 은 함께 쓸 수 없습니다")
        if a.backup is None and not a.no_backup:
            return _fail(a, EXIT_USAGE, "BACKUP_DECISION_REQUIRED",
                         "--in-place 는 원본을 덮어씁니다. 백업을 남길지 먼저 정하세요: "
                         "--backup [경로] (기본 <이름>.bak.pptx) 또는 --no-backup")
        if a.backup is not None and a.no_backup:
            return _fail(a, EXIT_USAGE, "USAGE", "--backup 과 --no-backup 은 함께 쓸 수 없습니다")
        backup_path = None
        if a.backup is not None:
            backup_path = a.backup or default_backup(infile)
            if os.path.exists(backup_path) and not a.force:
                return _fail(a, EXIT_USAGE, "BACKUP_EXISTS", f"백업 경로가 이미 있습니다: {backup_path} (--force 로 덮어쓰기)")
        outfile = None
    else:
        outfile = a.output or default_output(infile)
        if os.path.abspath(outfile) == os.path.abspath(infile):
            return _fail(a, EXIT_USAGE, "USAGE", "출력이 입력과 같습니다. 원본을 바꾸려면 --in-place 를 쓰세요")
        if os.path.exists(outfile) and not a.force:
            return _fail(a, EXIT_USAGE, "OUTPUT_EXISTS", f"출력 파일이 이미 있습니다: {outfile} (--force 로 덮어쓰기)")
        backup_path = None

    src_size = os.path.getsize(infile)
    if a.dry_run:
        rep = analyze(infile, a.min_bytes, a.quality, top=a.top)
        rep["dry_run"] = True
        rep["output"] = outfile or infile
        rep["backup"] = backup_path
        return _emit(a, rep, print_report)

    d = os.path.dirname(os.path.abspath(infile)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".pptx_shrink_", suffix=".pptx", dir=d)
    os.close(fd)
    try:
        res = shrink(infile, tmp, a.min_bytes, a.quality, a.downsample_ppi)
        if not res["converted"]:
            payload = {"status": "unchanged", "file": infile, "file_mb": _mb(src_size),
                       "converted": 0, "kept": res["kept"], "skipped": res["skipped"],
                       "message": "변환할 이미지가 없어 원본을 그대로 둡니다"}
            return _emit(a, payload, lambda p: print(p["message"] + f" ({p['file_mb']} MB, 유지 {p['kept']}장)"))

        # ── 검증 게이트 ──
        vres = None
        if not a.skip_verify:
            vres = _verify.compare(infile, tmp)
            if not vres["ok"]:
                os.unlink(tmp)
                tmp = None
                payload = {"status": "verify_failed", "file": infile, "verify": vres,
                           "message": "무손실 검증 실패 — 산출물을 폐기했습니다"}
                _emit(a, payload, lambda p: print(p["message"] + "\n" + _verify.format_report(p["verify"])))
                return EXIT_VERIFY_FAILED

        if outfile:
            shutil.move(tmp, outfile)
            tmp = None
            written = outfile
        else:
            if backup_path:
                shutil.copy2(infile, backup_path)
            os.chmod(tmp, os.stat(infile).st_mode & 0o7777)
            shutil.move(tmp, infile)
            tmp = None
            written = infile
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)

    out_size = os.path.getsize(written)
    payload = {
        "status": "ok", "file": infile, "output": written,
        "in_place": bool(a.in_place), "backup": backup_path,
        "before_mb": _mb(src_size), "after_mb": _mb(out_size),
        "reduction_pct": round((1 - out_size / src_size) * 100, 1) if src_size else 0.0,
        "converted": res["converted"], "kept": res["kept"], "downsampled": res["downsampled"],
        "image_saved_mb": _mb(res["saved_bytes"]), "skipped": res["skipped"],
        "verify": vres,
        "params": {"min_bytes": a.min_bytes, "quality": a.quality, "downsample_ppi": a.downsample_ppi},
    }

    def _p(p: dict) -> None:
        down = f", 해상도 축소 {p['downsampled']}장({p['params']['downsample_ppi']}ppi)" if p["params"]["downsample_ppi"] else ""
        print(f"변환: {p['converted']}장(품질 {p['params']['quality']}{down}), 유지: {p['kept']}장 (이미지 절감 {p['image_saved_mb']} MB)")
        print(f"파일 크기: {p['before_mb']} MB → {p['after_mb']} MB ({p['reduction_pct']}% 감소)")
        print(f"산출: {p['output']}" + (f"  백업: {p['backup']}" if p["backup"] else
                                      ("  (원본 교체, 백업 없음)" if p["in_place"] else "")))
        if p["verify"]:
            print("검증: " + ("PASS — 슬라이드·텍스트·노트·그림 수·참조 전건 일치" if p["verify"]["ok"] else "FAIL"))
        for s in p["skipped"]:
            print(f"  건너뜀: {s}")

    return _emit(a, payload, _p)


def cmd_report(a: argparse.Namespace) -> int:
    if not os.path.isfile(a.infile):
        return _fail(a, EXIT_INPUT, "FILE_NOT_FOUND", f"파일이 없습니다: {a.infile}")
    if not zipfile.is_zipfile(a.infile):
        return _fail(a, EXIT_INPUT, "NOT_PPTX", f"pptx(zip) 가 아닙니다: {a.infile}")
    rep = analyze(a.infile, a.min_bytes, a.quality, top=a.top)
    return _emit(a, rep, print_report)


def _emit(a: argparse.Namespace, payload: dict, human) -> int:
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        human(payload)
    return EXIT_OK


def _fail(a: argparse.Namespace, code: int, err: str, msg: str) -> int:
    if a.json:
        print(json.dumps({"status": "error", "error": err, "message": msg}, ensure_ascii=False))
    else:
        print(f"오류[{err}]: {msg}", file=sys.stderr)
    return code


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("infile")
        p.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES, help="이 크기 미만 PNG 는 건드리지 않는다")
        p.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help="JPEG 품질(1~95)")
        p.add_argument("--top", type=int, default=10, help="리포트 상위 이미지 수")
        p.add_argument("--json", action="store_true", help="기계 판독용 JSON 출력")

    pr = sub.add_parser("report", help="미디어 분해·예상 절감 (파일을 쓰지 않는다)")
    common(pr)
    pr.set_defaults(func=cmd_report)

    ps = sub.add_parser("shrink", help="이미지 재인코딩 (기본: 새 파일 저장)")
    common(ps)
    ps.add_argument("-o", "--output", help="출력 경로 (기본 <이름>-shrunk.pptx)")
    ps.add_argument("--downsample-ppi", type=int, default=0, metavar="PPI",
                    help="표시 크기 기준 해상도 축소(예: 220·150). 표시보다 작은 이미지는 건드리지 않는다. 기본 0=끔")
    ps.add_argument("--in-place", action="store_true", help="원본을 교체한다 — --backup 또는 --no-backup 필수")
    ps.add_argument("--backup", nargs="?", const="", default=None, metavar="경로",
                    help="원본 교체 전 백업 (경로 생략 시 <이름>.bak.pptx)")
    ps.add_argument("--no-backup", action="store_true", help="백업 없이 원본 교체 (사용자가 명시적으로 동의한 경우만)")
    ps.add_argument("--force", action="store_true", help="기존 출력/백업 파일 덮어쓰기 허용")
    ps.add_argument("--dry-run", action="store_true", help="쓰지 않고 예상 결과만")
    ps.add_argument("--skip-verify", action="store_true", help=argparse.SUPPRESS)
    ps.set_defaults(func=cmd_shrink)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if not (1 <= a.quality <= 95):
        return _fail(a, EXIT_USAGE, "USAGE", "--quality 는 1~95")
    if getattr(a, "downsample_ppi", 0) < 0:
        return _fail(a, EXIT_USAGE, "USAGE", "--downsample-ppi 는 0 이상")
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
