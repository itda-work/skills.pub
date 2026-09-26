"""build_kma_points.py — 정본 xlsx → scripts/kma_points.py 정적 박제 (개발/재생성 도구).

런타임 아님(references/, .skill 패키징 제외 대상). stdlib only(zipfile/xml) —
openpyxl 불요. SPEC-WEATHER-HERE-001 REQ-003 정확성 자산 생성.

출처: references/동네예보지점좌표(위경도)_202601.xlsx (기상청 202601, 권위)
범위: 1단계(시·도) + 2단계(시군구) 대표행만 (3단계 읍면동 제외).

사용: python3 references/build_kma_points.py   (CWD = 스킬 루트)
"""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_SKILL = Path(__file__).resolve().parent.parent
_XLSX = _SKILL / "references" / "동네예보지점좌표(위경도)_202601.xlsx"
_OUT = _SKILL / "scripts" / "kma_points.py"

# 한국 bbox (검증용)
_LAT_MIN, _LAT_MAX = 33.0, 39.0
_LON_MIN, _LON_MAX = 124.0, 132.0
# KMA 동네예보 격자 범위 (대략)
_NX_MIN, _NX_MAX = 1, 149
_NY_MIN, _NY_MAX = 1, 253


def _read_rows() -> list[list[str]]:
    z = zipfile.ZipFile(_XLSX)
    sst: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        r = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in r.findall("m:si", _NS):
            sst.append("".join(t.text or "" for t in si.iter(
                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    out: list[list[str]] = []
    for row in root.find("m:sheetData", _NS).findall("m:row", _NS):
        vals: list[str] = []
        for c in row.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if v is None:
                vals.append("")
            elif c.get("t") == "s":
                vals.append(sst[int(v.text)])
            else:
                vals.append(v.text or "")
        out.append(vals)
    return out


def _dms(d: str, m: str, s: str) -> float:
    return int(d) + int(m) / 60.0 + float(s) / 3600.0


def build() -> tuple[list[dict], list[str]]:
    rows = _read_rows()
    header = rows[0]
    assert header[:7] == ["구분", "행정구역코드", "1단계", "2단계", "3단계",
                          "격자 X", "격자 Y"], f"스키마 불일치: {header[:7]}"
    points: list[dict] = []
    warnings: list[str] = []
    for i, r in enumerate(rows[1:], start=2):
        if len(r) < 14 or r[0] != "kor":
            continue
        l1, l2, l3 = r[2], r[3], r[4]
        if l3:  # 읍면동(3단계) 제외 — 시·도+시군구 대표만
            continue
        try:
            nx, ny = int(r[5]), int(r[6])
            lon = _dms(r[7], r[8], r[9])
            lat = _dms(r[10], r[11], r[12])
            lon_ref = float(r[13])  # 정본 경도 십진(내부 교차검증용)
        except (ValueError, IndexError) as e:
            warnings.append(f"row{i} 파싱불가 {l1}/{l2}: {e}")
            continue
        # 내부 정합: DMS→십진 경도 vs 정본 십진 (오차 > 0.01° = 데이터 무결성 경고)
        if abs(lon - lon_ref) > 0.01:
            warnings.append(
                f"row{i} {l1} {l2}: 경도 DMS({lon:.5f}) vs 정본({lon_ref:.5f}) 불일치")
        # bbox / 격자 범위 실패 = 무효점 → 제외(경고 아님). (0,0) 이어도 등.
        # 무의미 좌표를 표에 넣지 않는 게 정확성 우선 원칙.
        if not (_LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX):
            warnings.append(
                f"제외 row{i} {l1} {l2}: bbox 밖 ({lat:.4f},{lon:.4f}) — 행정구역 아님/무효")
            continue
        if not (_NX_MIN <= nx <= _NX_MAX and _NY_MIN <= ny <= _NY_MAX):
            warnings.append(
                f"제외 row{i} {l1} {l2}: 격자 범위 밖 ({nx},{ny})")
            continue
        points.append({"l1": l1, "l2": l2, "nx": nx, "ny": ny,
                       "lat": round(lat, 4), "lon": round(lon, 4)})
    return points, warnings


def emit(points: list[dict]) -> None:
    lines = [
        '"""kma_points.py — 행정구역(시·도+시군구) → KMA 격자/위경도 정적표.',
        "",
        "AUTO-GENERATED — references/build_kma_points.py 로 재생성. 손수정 금지.",
        "출처: references/동네예보지점좌표(위경도)_202601.xlsx (기상청 202601, 권위).",
        "SPEC-WEATHER-HERE-001 REQ-003. stdlib only, 런타임 import 전용.",
        '"""',
        "from __future__ import annotations",
        "",
        f"# 총 {len(points)}개 (시·도 + 시군구 대표, 읍면동 제외)",
        "POINTS: list[dict] = [",
    ]
    for p in points:
        lines.append(
            f'    {{"l1": {p["l1"]!r}, "l2": {p["l2"]!r}, '
            f'"nx": {p["nx"]}, "ny": {p["ny"]}, '
            f'"lat": {p["lat"]}, "lon": {p["lon"]}}},')
    lines.append("]")
    lines.append("")
    _OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    pts, warns = build()
    n_sido = sum(1 for p in pts if not p["l2"])
    n_sigungu = sum(1 for p in pts if p["l2"])
    print(f"추출: 총 {len(pts)} (시·도 {n_sido} / 시군구 {n_sigungu})")
    print(f"경고/불일치: {len(warns)}건")
    for w in warns[:20]:
        print("  ⚠", w)
    emit(pts)
    print(f"생성: {_OUT.relative_to(_SKILL)}")
