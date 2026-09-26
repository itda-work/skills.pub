"""xlsx 의 수식 셀·캐시·통합문서 설정·외부 링크를 stdlib 만으로 읽는다(openpyxl 불요).

재계산 전후 판정은 이 스캔 결과로 한다 — soffice 의 종료 코드만으로 "재계산됐다" 고 보지 않는다(#1690).

- XML 은 네임스페이스 URI 로 읽는다. 접두사 철자(`<x:c>`)가 섞여도 셀을 놓치지 않는다. Transitional 이 아닌 구조
  (Strict OOXML 등)는 **빈 통합문서로 오인하지 않고** 거부한다(UnsupportedWorkbook).
- 캐시 판정은 **타입별**이다. 숫자·논리·에러·공유 문자열 셀의 빈 `<v></v>` 는 캐시 없음이고, `t="str"` 의 빈 값은
  빈 문자열 결과라 정상이다. openpyxl 저장본은 모든 수식 셀에 빈 `<v></v>` 를 쓴다(실측 20,079셀).
- 공유 수식 자식 셀은 부모 수식을 옮겨 전개한 문자열을 `formula` 에 담는다(`formula_text.shift_formula`).
- 배열 수식은 결과가 범위 전체에 들어간다 — 부모 셀 밖의 결과 셀 캐시도 따로 모은다(`array_results`).
"""
from __future__ import annotations

import math
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

import formula_text

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_STRICT_MAIN = "http://purl.oclc.org/ooxml/spreadsheetml/main"
M = f"{{{NS_MAIN}}}"

_CELL_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([0-9]+)$")
ERROR_CODES = ("#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A", "#GETTING_DATA", "#SPILL!", "#CALC!")


class ScanError(Exception):
    """xlsx 구조를 읽지 못함(zip 아님·필수 파트 누락·XML 손상)."""


class UnsupportedWorkbook(ScanError):
    """읽을 수는 있지만 이 스킬이 검증할 수 없는 구조(Strict OOXML·데이터 테이블 등)."""


@dataclass
class FormulaCell:
    sheet: str
    cell: str
    formula: str  # 공유 수식 자식은 전개한 문자열
    f_type: str  # "", "shared", "array", "dataTable"
    t: str  # 셀 t 속성("" = 숫자)
    value: str | None  # <v> 텍스트(요소가 없으면 None)
    cache_problem: str | None  # None 이면 캐시값 유효
    ref: str = ""  # 배열 수식의 적용 범위

    @property
    def key(self) -> tuple[str, str]:
        return self.sheet, self.cell


@dataclass
class ExternalLink:
    index: int  # [n], 1-based
    part: str | None
    kind: str  # "book" · "dde" · "ole" · "missing" · "unknown"
    target: str = ""  # externalLinkPath 관계의 Target 원문
    sheet_names: list[str] = field(default_factory=list)
    cached: set[tuple[int, str]] = field(default_factory=set)  # (sheetId, "A1") — 타입에 맞는 값이 있는 셀
    defined_names: dict[str, str] = field(default_factory=dict)  # 이름(대문자) → refersTo

    @property
    def identity(self) -> tuple:
        return self.kind, self.target, tuple(s.upper() for s in self.sheet_names)


@dataclass
class ScanResult:
    sheets: list[str] = field(default_factory=list)
    formulas: list[FormulaCell] = field(default_factory=list)
    array_results: dict[tuple[str, str], str | None] = field(default_factory=dict)  # 배열 결과 셀 → 캐시 문제
    defined_names: dict[str, list[str]] = field(default_factory=dict)  # 이름(대문자) → 정의 목록(시트 범위 포함)
    external_links: list[ExternalLink] = field(default_factory=list)
    date1904: bool = False
    full_precision: bool = True

    @property
    def missing_cache(self) -> list[FormulaCell]:
        return [c for c in self.formulas if c.cache_problem is not None]

    @property
    def error_cells(self) -> list[FormulaCell]:
        return [c for c in self.formulas if c.t == "e" and c.cache_problem is None]


def cache_problem(t: str, value: str | None, has_inline: bool = False, shared_count: int | None = None) -> str | None:
    """수식 셀 캐시가 유효하지 않은 이유. 유효하면 None. shared_count 는 공유 문자열 개수(파트가 없으면 0)."""
    if t == "inlineStr":
        return None if has_inline else "inline_string_missing"
    if value is None:
        return "no_value_element"
    if t in ("", "n"):
        text = value.strip()
        if not text:
            return "empty_numeric_cache"
        try:
            num = float(text)
        except ValueError:
            return "unparsable_numeric_cache"
        return None if math.isfinite(num) else "non_finite_numeric_cache"
    if t == "b":
        return None if value.strip() in ("0", "1") else "invalid_boolean_cache"
    if t == "e":
        return None if value.strip() in ERROR_CODES else "invalid_error_cache"
    if t == "s":
        text = value.strip()
        if not text.isdigit():
            return "invalid_shared_string_index"
        if shared_count is not None and int(text) >= shared_count:
            return "shared_string_index_out_of_range"
        return None
    if t == "str":
        return None  # 빈 문자열도 정상 결과다
    return f"unknown_cell_type:{t}"


def _parse(zf: zipfile.ZipFile, name: str) -> ET.Element:
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        raise ScanError(f"필수 파트가 없다: {name}") from None
    except ET.ParseError as e:
        raise ScanError(f"XML 을 읽지 못했다: {name} ({e})") from None


def _rels(zf: zipfile.ZipFile, rels_name: str, base_dir: str) -> dict[str, tuple[str, str, str]]:
    """관계 Id → (Type 끝 이름, 정규화한 파트 경로(External 이면 원문), TargetMode)."""
    if rels_name not in zf.namelist():
        return {}
    out = {}
    for rel in _parse(zf, rels_name).iter(f"{{{NS_PKG_REL}}}Relationship"):
        target = rel.get("Target", "")
        mode = rel.get("TargetMode", "")
        if mode != "External":
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base_dir, target))
        out[rel.get("Id", "")] = (rel.get("Type", "").rsplit("/", 1)[-1], target, mode)
    return out


def _ns(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _read_external_link(zf: zipfile.ZipFile, index: int, part: str | None) -> ExternalLink:
    if part is None or part not in zf.namelist():
        return ExternalLink(index=index, part=part, kind="missing")
    root = _parse(zf, part)
    book = root.find(f"{M}externalBook")
    if book is None:
        kind = "dde" if root.find(f"{M}ddeLink") is not None else "ole" if root.find(f"{M}oleLink") is not None else "unknown"
        return ExternalLink(index=index, part=part, kind=kind)
    rels = _rels(zf, posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels"),
                 posixpath.dirname(part))
    rel = rels.get(book.get(f"{{{NS_REL}}}id", ""))
    link = ExternalLink(index=index, part=part, kind="book", target=rel[1] if rel else "")
    names = book.find(f"{M}sheetNames")
    if names is not None:
        link.sheet_names = [s.get("val", "") for s in names.findall(f"{M}sheetName")]
    dn = book.find(f"{M}definedNames")
    if dn is not None:
        for d in dn.findall(f"{M}definedName"):
            link.defined_names[d.get("name", "").upper()] = d.get("refersTo", "")
    data = book.find(f"{M}sheetDataSet")
    if data is not None:
        for sd in data.findall(f"{M}sheetData"):
            sid = int(sd.get("sheetId", "-1"))
            for row in sd.findall(f"{M}row"):
                for cell in row.findall(f"{M}cell"):
                    ref = (cell.get("r") or "").replace("$", "").upper()
                    v = cell.find(f"{M}v")
                    # 값 요소가 있기만 한 것은 캐시가 아니다 — 타입에 맞는 값이어야 한다(Codex R2 #4).
                    if ref and cache_problem(cell.get("t", ""), None if v is None else (v.text or "")) is None:
                        link.cached.add((sid, ref))
    return link


def scan(path: str) -> ScanResult:
    """xlsx 의 수식 셀과 그 캐시값, 통합문서 설정, 외부 링크를 읽는다. 구조 오류는 ScanError."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ScanError(f"xlsx(zip) 로 열 수 없다: {e}") from None
    try:
        with zf:
            return _scan(zf)
    except (ValueError, zipfile.BadZipFile, OSError) as e:  # 손상된 숫자 속성(`<row r="oops">`)·zip 멤버 등
        raise ScanError(f"xlsx 구조를 읽지 못했다: {type(e).__name__}: {e}") from None


def _scan(zf: zipfile.ZipFile) -> ScanResult:
    res = ScanResult()
    root_rels = _rels(zf, "_rels/.rels", "")
    wb_part = next((t for kind, t, _ in root_rels.values() if kind == "officeDocument"), None)
    if wb_part is None:
        raise ScanError("통합문서 파트(officeDocument 관계)가 없다 — xlsx 가 아니다")
    wb_dir = posixpath.dirname(wb_part)
    wb = _parse(zf, wb_part)
    ns = _ns(wb.tag)
    if ns == NS_STRICT_MAIN:
        raise UnsupportedWorkbook("Strict Open XML 통합문서는 지원하지 않는다 — Excel 에서 'Excel 통합 문서(*.xlsx)' 로 다시 저장하라")
    if wb.tag != f"{M}workbook":
        raise UnsupportedWorkbook(f"알 수 없는 통합문서 형식이다(루트 {wb.tag})")
    wb_rels = _rels(zf, posixpath.join(wb_dir, "_rels", posixpath.basename(wb_part) + ".rels"), wb_dir)
    pr = wb.find(f"{M}workbookPr")
    if pr is not None and pr.get("date1904", "").lower() in ("1", "true"):
        res.date1904 = True
    calc = wb.find(f"{M}calcPr")
    if calc is not None and calc.get("fullPrecision", "").lower() in ("0", "false"):
        res.full_precision = False
    sheet_list = wb.find(f"{M}sheets")
    if sheet_list is None:
        raise ScanError("통합문서에 sheets 요소가 없다")
    dn = wb.find(f"{M}definedNames")
    if dn is not None:
        for d in dn.findall(f"{M}definedName"):
            res.defined_names.setdefault(d.get("name", "").upper(), []).append(d.text or "")
    refs = wb.find(f"{M}externalReferences")
    if refs is not None:
        for i, er in enumerate(refs.findall(f"{M}externalReference"), start=1):
            rel = wb_rels.get(er.get(f"{{{NS_REL}}}id", ""))
            res.external_links.append(_read_external_link(zf, i, rel[1] if rel else None))
    shared_count = 0
    sst_part = next((t for kind, t, _ in wb_rels.values() if kind == "sharedStrings"), None)
    if sst_part is not None:
        shared_count = len(_parse(zf, sst_part).findall(f"{M}si"))

    for sh in sheet_list.findall(f"{M}sheet"):
        name = sh.get("name", "")
        rel = wb_rels.get(sh.get(f"{{{NS_REL}}}id", ""))
        if rel is None:
            raise ScanError(f"시트 관계를 찾지 못했다: {name}")
        if rel[0] in ("chartsheet", "dialogsheet"):
            continue  # 셀 수식이 없는 시트
        if rel[0] != "worksheet":
            raise UnsupportedWorkbook(f"알 수 없는 시트 종류다: {name} ({rel[0]})")
        res.sheets.append(name)
        root = _parse(zf, rel[1])
        if root.tag != f"{M}worksheet":
            raise UnsupportedWorkbook(f"알 수 없는 시트 형식이다: {name} (루트 {root.tag})")
        sheet_data = root.find(f"{M}sheetData")
        if sheet_data is None:
            continue
        shared: dict[str, tuple[str, int, int]] = {}
        pending: list[tuple[FormulaCell, str, int, int]] = []
        arrays: list[tuple[int, int, int, int]] = []  # 배열 범위(c1, r1, c2, r2)
        cur_row = 0
        for row in sheet_data.findall(f"{M}row"):
            cur_row = int(row.get("r")) if row.get("r") else cur_row + 1
            cur_col = 0
            for c in row.findall(f"{M}c"):
                ref = c.get("r")
                if ref:
                    m = _CELL_RE.match(ref)
                    if not m:
                        raise ScanError(f"셀 주소를 읽지 못했다: {name}!{ref}")
                    cur_col = formula_text.col_to_num(m.group(1))
                    cur_row = int(m.group(2))
                    ref = f"{m.group(1).upper()}{m.group(2)}"
                else:
                    cur_col += 1
                    ref = f"{formula_text.num_to_col(cur_col)}{cur_row}"
                f = c.find(f"{M}f")
                v = c.find(f"{M}v")
                t = c.get("t", "")
                value = None if v is None else (v.text or "")
                problem = cache_problem(t, value, c.find(f"{M}is") is not None, shared_count)
                if f is None:
                    if any(c1 <= cur_col <= c2 and r1 <= cur_row <= r2 for c1, r1, c2, r2 in arrays):
                        res.array_results[(name, ref)] = problem
                    continue
                cell = FormulaCell(sheet=name, cell=ref, formula=f.text or "", f_type=f.get("t", ""), t=t,
                                   value=value, cache_problem=problem, ref=f.get("ref", ""))
                if cell.f_type == "dataTable":
                    # LibreOffice 는 데이터 테이블을 Excel 에 없는 TABLE() 수식으로 바꿔 저장한다(#1690 실측).
                    raise UnsupportedWorkbook(
                        f"데이터 테이블(가상 분석 표)은 지원하지 않는다: {name}!{ref} — LibreOffice 가 Excel 에 없는 "
                        "TABLE() 수식으로 바꿔 저장해 Excel 에서 깨진다")
                if cell.f_type == "array" and cell.ref:
                    span = _span(cell.ref)
                    if span is None:
                        raise ScanError(f"배열 수식 범위를 읽지 못했다: {name}!{ref} ref={cell.ref}")
                    arrays.append(span)
                if cell.f_type == "shared":
                    si = f.get("si", "")
                    if (f.text or "").strip():
                        shared[si] = (f.text or "", cur_row, cur_col)
                    else:
                        pending.append((cell, si, cur_row, cur_col))
                res.formulas.append(cell)
        for cell, si, r, col in pending:
            if si not in shared:
                raise ScanError(f"공유 수식 부모를 찾지 못했다: {name}!{cell.cell} (si={si})")
            text, pr_, pc = shared[si]
            cell.formula = formula_text.shift_formula(text, r - pr_, col - pc)
    return res


def _span(ref: str) -> tuple[int, int, int, int] | None:
    m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?(\d+)(?::\$?([A-Za-z]{1,3})\$?(\d+))?", ref.strip())
    if not m:
        return None
    c1, r1 = formula_text.col_to_num(m.group(1)), int(m.group(2))
    c2, r2 = (formula_text.col_to_num(m.group(3)), int(m.group(4))) if m.group(3) else (c1, r1)
    return min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2)


MAX_ARRAY_CELLS = 1_000_000


def array_cells(ref: str):
    """배열 범위의 셀 주소를 **지연** 생성한다. 범위를 읽지 못하거나 MAX_ARRAY_CELLS 를 넘으면 ScanError —
    `A1:XFD1048576` 같은 범위로 주소 목록을 통째로 만들어 메모리를 고갈시키지 않는다(Codex R3 신규 #3)."""
    span = _span(ref)
    if span is None:
        raise ScanError(f"배열 수식 범위를 읽지 못했다: {ref}")
    c1, r1, c2, r2 = span
    if (c2 - c1 + 1) * (r2 - r1 + 1) > MAX_ARRAY_CELLS:
        raise ScanError(f"배열 수식 범위가 너무 크다({ref}) — 결과 셀을 검증할 수 없다")
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            yield f"{formula_text.num_to_col(c)}{r}"


def _cells_in(target: str) -> list[str] | None:
    """외부 참조 대상의 셀 목록. 전체 열·행·이름처럼 셀 수 없는 모양은 None."""
    t = target.replace("$", "").upper()
    m = re.fullmatch(r"([A-Z]{1,3})(\d+)(?::([A-Z]{1,3})(\d+))?", t)
    if not m:
        return None
    c1, r1 = formula_text.col_to_num(m.group(1)), int(m.group(2))
    c2, r2 = (formula_text.col_to_num(m.group(3)), int(m.group(4))) if m.group(3) else (c1, r1)
    c1, c2 = sorted((c1, c2))
    r1, r2 = sorted((r1, r2))
    if (c2 - c1 + 1) * (r2 - r1 + 1) > 10000:
        return None
    return [f"{formula_text.num_to_col(c)}{r}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]


@dataclass
class ExternalProblem:
    sheet: str
    cell: str
    reference: str
    reason: str


def external_names(res: ScanResult) -> set[str]:
    """외부 참조에 (다른 이름을 거쳐서라도) 닿는 정의된 이름(대문자). 순환은 고정점 반복으로 끝난다 — 깊이 제한이 없다."""
    names = res.defined_names
    hit = {n for n, ds in names.items() if any(formula_text.has_external_marker(d) for d in ds)}
    changed = True
    while changed:
        changed = False
        for n, ds in names.items():
            if n not in hit and any(formula_text.name_used(d, o) for d in ds for o in hit):
                hit.add(n)
                changed = True
    return hit


def external_link_problems(res: ScanResult) -> tuple[int, list[ExternalProblem]]:
    """외부 링크를 참조하는 수식 중 링크 값 캐시가 없는 참조를 찾는다. (외부 참조 수, 문제 목록).

    LibreOffice 는 외부 통합문서를 다시 읽지 못하면 링크 파트의 값 캐시(`sheetDataSet`)로 계산한다. 그 캐시가 없으면
    0 을 성공으로 쓴다(#1690 A/B §3.7). 시트 캐시만 빈 경우(openpyxl 저장)는 문제가 아니다.
    셀을 셀 수 없는 모양(전체 열·3D·범위 연속·OFFSET/INDIRECT 와 함께 쓰인 외부 참조·해석 불가)은 보수적으로 문제로 센다.
    정의된 이름은 시트 범위·유니코드·이름 체인까지 따라간다(Codex R2 #2).
    """
    links = {l.index: l for l in res.external_links}
    ext = external_names(res)
    count = 0
    problems: list[ExternalProblem] = []

    def check_text(cell: FormulaCell, text: str, dynamic: bool) -> None:
        nonlocal count
        refs = formula_text.external_refs(text)
        by_filename = formula_text.has_filename_external_reference(text)
        if by_filename:
            count += 1
            problems.append(ExternalProblem(cell.sheet, cell.cell, text, "external_workbook_by_filename_without_link_part"))
        if formula_text.has_external_marker(text) and not refs and not by_filename:
            problems.append(ExternalProblem(cell.sheet, cell.cell, text, "unparsed_external_reference"))
        if refs and dynamic:
            problems.append(ExternalProblem(cell.sheet, cell.cell, text, "external_reference_with_dynamic_function"))
        for ref in refs:
            count += 1
            link = links.get(ref.link)
            where = ref.raw
            if link is None or link.kind == "missing":
                problems.append(ExternalProblem(cell.sheet, cell.cell, where, "external_link_part_missing"))
                continue
            if link.kind != "book":
                problems.append(ExternalProblem(cell.sheet, cell.cell, where, f"external_link_kind_{link.kind}"))
                continue
            if ref.sheet is None:  # [1]!Name — 외부 통합문서의 정의된 이름
                refers = link.defined_names.get(ref.target.upper())
                sub = None if refers is None else re.fullmatch(r"=?'?((?:[^'!]|'')+)'?!(.+)", refers)
                if sub is None:
                    problems.append(ExternalProblem(cell.sheet, cell.cell, where, "external_name_unresolved"))
                    continue
                sheet_name, target = sub.group(1).replace("''", "'"), sub.group(2)
            else:
                sheet_name, target = ref.sheet, ref.target
            idx = next((i for i, s in enumerate(link.sheet_names) if s.upper() == sheet_name.upper()), None)
            cells = _cells_in(target)
            if idx is None:
                problems.append(ExternalProblem(cell.sheet, cell.cell, where, "external_sheet_unresolved"))
            elif cells is None:
                problems.append(ExternalProblem(cell.sheet, cell.cell, where, "external_range_uncountable"))
            else:
                missing = [c for c in cells if (idx, c) not in link.cached]
                if missing:
                    problems.append(ExternalProblem(
                        cell.sheet, cell.cell, where,
                        f"external_link_value_cache_missing({', '.join(missing[:5])}{' …' if len(missing) > 5 else ''})"))

    for cell in res.formulas:
        texts = [cell.formula]
        seen: set[str] = set()
        queue = [n for n in ext if formula_text.name_used(cell.formula, n)]
        while queue:  # 수식이 쓰는 외부 이름과, 그 정의가 쓰는 외부 이름 전부
            n = queue.pop()
            if n in seen:
                continue
            seen.add(n)
            for d in res.defined_names.get(n, []):
                texts.append(d)
                queue.extend(o for o in ext if o not in seen and formula_text.name_used(d, o))
        # OFFSET·INDIRECT 가 수식에 있고 외부 참조는 이름 정의에 있어도 필요한 셀을 증명할 수 없다(Codex R3 #5) —
        # 셀이 거치는 문자열 전체를 한 단위로 본다.
        dynamic = any(formula_text.has_dynamic_reference(t) for t in texts)
        for text in texts:
            if formula_text.has_external_marker(text):
                check_text(cell, text, dynamic)
    return count, problems


def external_link_part_count(res: ScanResult) -> int:
    return sum(1 for l in res.external_links if l.kind != "missing")
