"""xlsx 입력 방어 — openpyxl 이 열기 전에 병합 범위를 검사한다 (itda-work/skills#30).

openpyxl(3.1) 은 병합 범위의 칸마다 MergedCell 객체를 만든다. 그래서
  · 거꾸로 적힌 병합(`B1:A1`)은 워크북 전체를 못 연다(ValueError — 시트 하나 때문에 파일 전체가 막힘).
  · 거대한 병합(`D5:Z100000`, 230만 칸)은 여는 데만 21초·653MB 가 든다(실측). 열 전체 병합이면 사실상 멈춘다.
  · 병합에 가려진 칸(왼쪽 위가 아닌 칸)의 값은 **조용히 버린다** — 겹친 병합이면 머리글까지 사라진다.

이 모듈은 stdlib(zipfile·ElementTree)만으로 시트 XML 의 병합 목록을 읽어
  1) 거꾸로 된 병합 · 칸 수가 상한을 넘는 병합을 **뺀 임시 사본**을 만들고(원본 불변),
  2) 가려진 값·겹친 병합을 세어
무엇을 했는지 `Note` 로 돌려준다. 호출자는 Note 를 보고서의 발견으로 싣는다 — 조용히 넘기지 않는다.

data-audit·data-verify 에 같은 사본이 있다(테스트가 바이트 동일을 확인한다).
"""
from __future__ import annotations

import contextlib
import io
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

# 병합 하나가 이 칸 수를 넘으면 뺀다 — 제목 줄·그룹 칸 같은 정상 병합은 수십~수천 칸이다.
MAX_MERGE_CELLS = 10_000
# 시트 하나의 병합 칸 합계 상한 — openpyxl 실측 약 9.4µs·0.28KB/칸, 20만 칸이면 2초·60MB 안쪽.
MAX_SHEET_MERGE_CELLS = 200_000

_MERGE_RE = re.compile(rb'<(?:\w+:)?mergeCell\b[^>]*?\bref="([^"]+)"[^>]*?/>')
_REF_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d+)$")
_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass
class Note:
    sheet: str
    ref: str          # 병합 범위 문자열(원문 그대로)
    kind: str         # 'merge_reversed' | 'merge_too_large' | 'merge_overlap' | 'merge_hidden_values'
    message: str


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def _parse_cell(ref: str):
    m = _REF_RE.match(ref.strip())
    if not m:
        return None
    return int(m.group(2)), _col_index(m.group(1))


def parse_range(ref: str):
    """'A1:B2' → (r1, c1, r2, c2) 원문 순서 그대로. 한 칸 'A1' 은 (r,c,r,c). 해석 불가면 None."""
    parts = ref.split(":")
    if len(parts) == 1:
        parts = parts * 2
    if len(parts) != 2:
        return None
    a, b = _parse_cell(parts[0]), _parse_cell(parts[1])
    if a is None or b is None:
        return None
    return a[0], a[1], b[0], b[1]


def _sheet_paths(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """[(시트 이름, zip 안 경로)] — workbook.xml 의 시트 순서대로."""
    try:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return []
    targets = {r.get("Id"): r.get("Target", "") for r in rels.iter(f"{_NS_PKG_REL}Relationship")}
    out = []
    for s in wb.iter(f"{_NS_MAIN}sheet"):
        target = targets.get(s.get(f"{_NS_REL}id"), "")
        if not target:
            continue
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        out.append((s.get("name", ""), path))
    return out


def _value_cells(xml: bytes) -> list[tuple[int, int]] | None:
    """값(<v> 또는 인라인 문자열 <is>)이 있는 칸 좌표. 스트리밍으로 센다.

    XML 이 깨졌으면 None — 가려진 값은 세지 않고, 파일을 못 여는 판정은 openpyxl 에 맡긴다.
    """
    try:
        return _scan_values(xml)
    except ET.ParseError:
        return None


def _scan_values(xml: bytes) -> list[tuple[int, int]]:
    out = []
    for _, el in ET.iterparse(io.BytesIO(xml), events=("end",)):
        if el.tag == f"{_NS_MAIN}c":
            r = el.get("r")
            if r and (el.find(f"{_NS_MAIN}v") is not None or el.find(f"{_NS_MAIN}is") is not None):
                rc = _parse_cell(r)
                if rc:
                    out.append(rc)
            el.clear()
        elif el.tag == f"{_NS_MAIN}row":
            el.clear()
    return out


def inspect_sheet(name: str, xml: bytes) -> tuple[list[str], list[Note]]:
    """(뺄 병합 ref 목록, Note 목록). 병합이 없으면 ([], [])."""
    refs = [m.decode("utf-8", "replace") for m in _MERGE_RE.findall(xml)]
    if not refs:
        return [], []
    drop: list[str] = []
    notes: list[Note] = []
    kept: list[tuple[str, int, int, int, int, int]] = []   # (ref, r1, c1, r2, c2, area)
    for ref in refs:
        rng = parse_range(ref)
        if rng is None:
            continue   # 해석 못 하는 표기는 openpyxl 판단에 맡긴다
        r1, c1, r2, c2 = rng
        if r2 < r1 or c2 < c1:
            drop.append(ref)
            notes.append(Note(name, ref, "merge_reversed",
                              f"거꾸로 적힌 병합 {ref} 을(를) 무시했습니다(그대로 두면 파일 전체를 열 수 없음)"))
            continue
        area = (r2 - r1 + 1) * (c2 - c1 + 1)
        if area > MAX_MERGE_CELLS:
            drop.append(ref)
            notes.append(Note(name, ref, "merge_too_large",
                              f"병합 {ref} 이(가) {area:,}칸으로 상한 {MAX_MERGE_CELLS:,}칸을 넘어 무시했습니다"
                              f"(병합을 풀어 읽었으므로 그 안의 값도 각 칸 값으로 보입니다)"))
            continue
        kept.append((ref, r1, c1, r2, c2, area))

    total = sum(k[5] for k in kept)
    if total > MAX_SHEET_MERGE_CELLS:
        for k in sorted(kept, key=lambda k: -k[5]):
            if total <= MAX_SHEET_MERGE_CELLS:
                break
            kept.remove(k)
            total -= k[5]
            drop.append(k[0])
            notes.append(Note(name, k[0], "merge_too_large",
                              f"시트 병합 칸 합계가 상한 {MAX_SHEET_MERGE_CELLS:,}칸을 넘어 큰 병합 {k[0]}"
                              f"({k[5]:,}칸)을 무시했습니다"))

    # 남는 병합: 겹침·가려진 값. 칸 합계가 상한 안이라 좌표 집합으로 센다.
    owner: dict[tuple[int, int], str] = {}
    overlaps: set[str] = set()
    for ref, r1, c1, r2, c2, _ in kept:
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                prev = owner.get((r, c))
                if prev is not None and prev != ref:
                    overlaps.add(ref)
                    overlaps.add(prev)
                owner[(r, c)] = ref
    for ref in sorted(overlaps):
        notes.append(Note(name, ref, "merge_overlap",
                          f"병합 {ref} 이(가) 다른 병합과 겹칩니다(엑셀은 이 파일을 복구 대상으로 봅니다)"))
    tops = {(k[1], k[2]) for k in kept}
    hidden: dict[str, int] = {}
    for rc in _value_cells(xml) or []:
        ref = owner.get(rc)
        if ref is not None and rc not in tops:
            hidden[ref] = hidden.get(ref, 0) + 1
    for ref in sorted(hidden):
        notes.append(Note(name, ref, "merge_hidden_values",
                          f"병합 {ref} 에 가려진 값 {hidden[ref]}개는 읽히지 않습니다(왼쪽 위 칸 값만 남음)"))
    return drop, notes


def _strip_merges(xml: bytes, refs: list[str]) -> bytes:
    targets = set(refs)
    removed: set[str] = set()

    def repl(m):
        ref = m.group(1).decode("utf-8", "replace")
        if ref in targets:
            removed.add(ref)
            return b""
        return m.group(0)

    out = _MERGE_RE.sub(repl, xml)
    missing = targets - removed
    if missing:   # 조용히 넘기지 않는다 — 못 뺀 병합이 있으면 openpyxl 이 다시 막힌다
        raise ValueError(f"병합 범위를 사본에서 빼지 못했습니다: {sorted(missing)}")
    return out


def inspect(path: str) -> tuple[dict[str, list[str]], list[Note]]:
    """({zip 안 시트 경로: 뺄 ref 목록}, Note 목록). xlsx(zip) 가 아니면 ({}, [])."""
    if not zipfile.is_zipfile(path):
        return {}, []
    drops: dict[str, list[str]] = {}
    notes: list[Note] = []
    with zipfile.ZipFile(path) as zf:
        for name, member in _sheet_paths(zf):
            try:
                xml = zf.read(member)
            except KeyError:
                continue
            drop, sheet_notes = inspect_sheet(name, xml)
            notes += sheet_notes
            if drop:
                drops[member] = drop
    return drops, notes


@contextlib.contextmanager
def prepared(path: str):
    """`with prepared(path) as (load_path, notes):` — 문제 병합이 있으면 뺀 임시 사본 경로를 준다.

    원본은 건드리지 않는다. 사본은 with 블록이 끝나면 지운다.
    """
    drops, notes = inspect(path)
    if not drops:
        yield path, notes
        return
    tmpdir = tempfile.mkdtemp(prefix="xlsx-guard-")
    try:
        out = os.path.join(tmpdir, os.path.basename(path))
        with zipfile.ZipFile(path) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename in drops:
                    data = _strip_merges(data, drops[info.filename])
                zout.writestr(info, data)
        yield out, notes
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
