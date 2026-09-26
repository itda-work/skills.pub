"""수식·데이터 감사 체크 (#952 audit-xls 이식 — 수식·데이터 레벨).

[정확성 원칙] plausible ≠ correct. 각 체크는 **보수적**으로 — 확신이 낮으면 판정을 보류하거나
severity 를 낮춘다. false positive(멀쩡한 셀을 틀렸다 하기)가 감사 신뢰를 무너뜨린다.

재무모델 무결성(BS balance·cash tie-out·DCF/LBO 등)은 범위 외.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from openpyxl.utils import column_index_from_string, get_column_letter

import loader
from loader import a1

# ── 정규식: 문자열 리터럴 · 셀참조 · 범위 · 함수 ────────────────────────────
_STR_LIT = re.compile(r'"[^"]*"')
# 셀참조: (옵션 시트/외부접두)!? $?열$?행 — 뒤에 '(' 가 오면 함수명이므로 제외
_CELL_REF = re.compile(
    r"(?:'[^']+'|\[[^\]]+\][A-Za-z0-9_ ]*|[A-Za-z_][\w.]*)?!?"
    r"\$?[A-Za-z]{1,3}\$?\d+(?!\s*\()"
)
_RANGE = re.compile(r"\$?([A-Za-z]{1,3})\$?(\d+)\s*:\s*\$?([A-Za-z]{1,3})\$?(\d+)")
_RANGE_FN = re.compile(
    r"\b(SUM|AVERAGE|AVERAGEA|COUNT|COUNTA|MIN|MAX|MEDIAN|STDEV|STDEVP|VAR|PRODUCT)\s*\(",
    re.IGNORECASE,
)
# 산술 연산자에 붙은 숫자 리터럴(하드코드 후보) — 셀참조 마스킹 후 적용
_HARDCODE = re.compile(r"[*/^]\s*\$?\d+(?:\.\d+)?|\$?\d+(?:\.\d+)?\s*[*/^]|[+\-]\s*\$?\d*\.\d+")
_SHEET_REF = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w. ]*))!")
_NUM = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Finding:
    sheet: str
    cell: str
    severity: str       # 'Critical' | 'Warning' | 'Info'
    category: str
    issue: str
    fix: str


def _mask(formula: str) -> str:
    """문자열 리터럴·셀참조를 지운 구조만 남긴다(하드코드 탐지용)."""
    f = _STR_LIT.sub("", formula)
    f = _CELL_REF.sub("#", f)
    return f


def _sig(formula: str) -> str:
    """수식 구조 시그니처 — 참조는 R, 숫자는 N 으로 정규화(불일치 탐지용)."""
    f = _STR_LIT.sub('""', formula)
    f = _CELL_REF.sub("R", f)
    f = _NUM.sub("N", f)
    return re.sub(r"\s+", "", f)


# ── 1. 수식 오류 ──────────────────────────────────────────────────────────
def check_formula_errors(view: loader.SheetView) -> list[Finding]:
    out = []
    for rc, f in view.formulas.items():
        hit = next((c for c in loader.ERROR_CODES if c in f), None)
        if hit is None and loader.is_error_value(view.computed.get(rc)):
            hit = view.computed[rc]
        if hit:
            out.append(Finding(view.name, a1(*rc), "Critical", "수식 오류",
                                f"{hit} — {f}",
                                f"참조 대상과 함수 인자를 점검하세요({hit})."))
    for rc, v in view.literals.items():
        if loader.is_error_value(v):
            out.append(Finding(view.name, a1(*rc), "Critical", "수식 오류",
                                f"{v} 값이 셀에 고정됨",
                                "에러 상태가 값으로 붙여넣기 됨 — 원 수식을 복구하세요."))
    return out


# ── 2. 수식 내 하드코드 ───────────────────────────────────────────────────
def check_hardcodes(view: loader.SheetView) -> list[Finding]:
    out = []
    for rc, f in view.formulas.items():
        masked = _mask(f)
        m = _HARDCODE.search(masked)
        if not m:
            continue
        nums = _NUM.findall(m.group())
        # 0·1 같은 사소한 상수만이면 흔한 정당 패턴 → 제외(정확성)
        if nums and all(float(n) in (0.0, 1.0) for n in nums):
            continue
        out.append(Finding(view.name, a1(*rc), "Warning", "하드코드",
                            f"수식에 상수 {m.group().strip()} 박힘 — {f}",
                            "상수를 입력 셀로 빼고 셀 참조로 바꾸면 추적·수정이 쉬워집니다."))
    return out


# ── 3. 이웃과 다른 수식 ───────────────────────────────────────────────────
def check_inconsistent(view: loader.SheetView) -> list[Finding]:
    out = []
    cols: dict[int, list[tuple[int, str]]] = {}
    for (r, c), f in view.formulas.items():
        cols.setdefault(c, []).append((r, f))
    for c, cells in cols.items():
        if len(cells) < 3:
            continue
        groups: dict[str, list[tuple[int, str]]] = {}
        for r, f in cells:
            groups.setdefault(_sig(f), []).append((r, f))
        if len(groups) < 2:
            continue
        major = max(groups, key=lambda s: len(groups[s]))
        major_n = len(groups[major])
        if major_n < len(cells) * 0.6:
            continue  # 뚜렷한 다수 패턴 없음 → 판정 보류
        for sig, items in groups.items():
            if sig == major:
                continue
            for r, f in items:
                out.append(Finding(view.name, a1(r, c), "Warning", "수식 불일치",
                                   f"같은 열 다수({major_n}개)와 다른 구조 — {f}",
                                   "이웃 셀과 다른 계산식입니다 — 의도된 예외인지 확인하세요."))
    return out


# ── 4. off-by-one 범위 ────────────────────────────────────────────────────
def _filled_rows_by_col(view: loader.SheetView) -> dict[int, set[int]]:
    filled: dict[int, set[int]] = {}
    for (r, c), v in view.literals.items():
        filled.setdefault(c, set()).add(r)
    for (r, c), v in view.computed.items():
        if v is not None:
            filled.setdefault(c, set()).add(r)
    return filled


def check_off_by_one(view: loader.SheetView) -> list[Finding]:
    out = []
    filled = _filled_rows_by_col(view)
    for rc, f in view.formulas.items():
        if not _RANGE_FN.search(f):
            continue
        for m in _RANGE.finditer(f):
            c1, r1, c2, r2 = m.group(1).upper(), int(m.group(2)), m.group(3).upper(), int(m.group(4))
            if c1 != c2:
                continue  # 단일 열 범위만(다열은 판정 보류)
            col = column_index_from_string(c1)
            colrows = filled.get(col, set())
            miss = []
            below = r2 + 1
            if below in colrows and below != rc[0]:
                miss.append(f"{c1}{below}")
            above = r1 - 1
            if above >= 1 and above != rc[0]:
                av = view.literals.get((above, col))
                if av is None:
                    av = view.computed.get((above, col))
                if isinstance(av, (int, float)):  # 헤더 오탐 방지 — 숫자일 때만
                    miss.append(f"{c1}{above}")
            if miss:
                out.append(Finding(view.name, a1(*rc), "Warning", "off-by-one",
                                   f"{f} 범위 {c1}{r1}:{c2}{r2} 가 인접 데이터 {', '.join(miss)} 를 빠뜨림",
                                   "집계 범위가 데이터 첫/끝 행을 포함하는지 확인하세요."))
    return out


# ── 5. 복붙으로 값이 된 수식 ──────────────────────────────────────────────
def check_pasted_over(view: loader.SheetView) -> list[Finding]:
    out = []
    cols: dict[int, dict[str, set[int]]] = {}
    for (r, c) in view.formulas:
        cols.setdefault(c, {"f": set(), "l": set()})["f"].add(r)
    for (r, c) in view.literals:
        cols.setdefault(c, {"f": set(), "l": set()})["l"].add(r)
    for c, g in cols.items():
        nf, nl = len(g["f"]), len(g["l"])
        if nf < 3 or nl == 0:
            continue
        if nf / (nf + nl) < 0.7:  # 수식이 뚜렷한 다수인 열만
            continue
        fmin, fmax = min(g["f"]), max(g["f"])
        for r in sorted(g["l"]):
            if not (fmin < r < fmax):  # 수식 행 범위 안에 낀 상수만(헤더/합계 제외)
                continue
            v = view.literals.get((r, c))
            if isinstance(v, (int, float)):
                out.append(Finding(view.name, a1(r, c), "Warning", "복붙된 값",
                                   f"수식 열({get_column_letter(c)}) 중간에 상수 {v!r} — 수식이 값으로 덮인 듯",
                                   "이웃 수식을 복사해 되살리거나 의도된 상수인지 확인하세요."))
    return out


# ── 6. 순환참조 ───────────────────────────────────────────────────────────
def _same_sheet_refs(formula: str) -> list[tuple[int, int]]:
    tmp = _RANGE.sub(" ", formula)   # 범위는 사이클 판정에서 제외(개별 셀만)
    tmp = _STR_LIT.sub("", tmp)
    refs = []
    for m in re.finditer(r"(?<![\w!$'])\$?([A-Za-z]{1,3})\$?(\d+)(?!\s*\()", tmp):
        try:
            refs.append((int(m.group(2)), column_index_from_string(m.group(1).upper())))
        except ValueError:
            continue
    return refs


def check_circular(view: loader.SheetView) -> list[Finding]:
    graph = {rc: _same_sheet_refs(f) for rc, f in view.formulas.items()}
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict = {}
    cycles: list[list] = []

    def dfs(u, stack):
        color[u] = GRAY
        stack.append(u)
        for v in graph.get(u, []):
            if v not in graph:
                continue
            if color.get(v, WHITE) == GRAY and v in stack:
                cycles.append(stack[stack.index(v):])
            elif color.get(v, WHITE) == WHITE:
                dfs(v, stack)
        stack.pop()
        color[u] = BLACK

    for node in list(graph):
        if color.get(node, WHITE) == WHITE:
            dfs(node, [])

    out, seen = [], set()
    for cyc in cycles:
        key = frozenset(cyc)
        if key in seen:
            continue
        seen.add(key)
        chain = " → ".join(a1(*x) for x in cyc)
        out.append(Finding(view.name, a1(*cyc[0]), "Critical", "순환참조",
                           f"순환참조 사이클: {chain}",
                           "의도된 반복계산인지 확인하고, 아니면 참조 고리를 끊으세요."))
    return out


# ── 7. 깨진 시트 링크 ─────────────────────────────────────────────────────
def check_broken_links(view: loader.SheetView, all_names: list[str]) -> list[Finding]:
    out = []
    valid = set(all_names)
    for rc, f in view.formulas.items():
        f_clean = f
        for code in loader.ERROR_CODES:
            f_clean = f_clean.replace(code, "")  # #REF! 등은 수식 오류지 시트 링크가 아님(오탐 방지)
        for m in _SHEET_REF.finditer(f_clean):
            if "[" in m.group(0):  # 외부 워크북 참조 → 판정 보류
                continue
            name = m.group(1) or m.group(2)
            if name in valid:
                continue
            out.append(Finding(view.name, a1(*rc), "Critical", "깨진 시트 링크",
                               f"존재하지 않는 시트 참조 {name!r} — {f}",
                               f"시트 {name!r} 가 없습니다 — 이름 변경/삭제된 시트를 확인하세요."))
    return out


# ── 8. 단위/스케일 급변 (매우 보수적) ─────────────────────────────────────
def check_unit_mismatch(view: loader.SheetView) -> list[Finding]:
    out = []
    cols: dict[int, list[tuple[int, float]]] = {}
    for src in (view.literals, view.computed):
        for (r, c), v in src.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
                cols.setdefault(c, []).append((r, abs(v)))
    for c, vals in cols.items():
        if len(vals) < 5:  # 표본 작으면 판정 보류(정확성)
            continue
        med = statistics.median(v for _, v in vals)
        if med == 0:
            continue
        for r, v in vals:
            ratio = v / med if v > med else med / v
            if ratio >= 1000:
                out.append(Finding(view.name, a1(r, c), "Warning", "단위/스케일",
                                   f"같은 열 중앙값 대비 {ratio:.0f}배 차이(값 {v:g}, 중앙값 {med:g})",
                                   "천/백만 단위 혼용이나 0 개수 오타일 수 있습니다 — 확인하세요."))
    return out


# ── 9. 숨긴 행·시트 ───────────────────────────────────────────────────────
def check_hidden(view: loader.SheetView) -> list[Finding]:
    out = []
    if view.state in ("hidden", "veryHidden"):
        out.append(Finding(view.name, "-", "Info", "숨김",
                           f"숨겨진 시트({view.state})",
                           "숨긴 시트에 override/stale 계산이 있는지 확인하세요."))
    if view.hidden_rows:
        shown = ",".join(map(str, view.hidden_rows[:20]))
        more = "…" if len(view.hidden_rows) > 20 else ""
        out.append(Finding(view.name, f"행 {shown}{more}", "Info", "숨김",
                           f"숨겨진 행 {len(view.hidden_rows)}개",
                           "숨긴 행의 값/수식이 집계에 포함되는지 확인하세요."))
    if view.hidden_cols:
        out.append(Finding(view.name, f"열 {','.join(view.hidden_cols[:20])}", "Info", "숨김",
                           f"숨겨진 열 {len(view.hidden_cols)}개",
                           "숨긴 열에 override 가 있는지 확인하세요."))
    return out


_SEV_ORDER = {"Critical": 0, "Warning": 1, "Info": 2}


def run_all(views: list[loader.SheetView], all_names: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for v in views:
        findings += check_formula_errors(v)
        findings += check_hardcodes(v)
        findings += check_inconsistent(v)
        findings += check_off_by_one(v)
        findings += check_pasted_over(v)
        findings += check_circular(v)
        findings += check_broken_links(v, all_names)
        findings += check_unit_mismatch(v)
        findings += check_hidden(v)
    # dedup (sheet, cell, category)
    seen, out = set(), []
    for f in findings:
        k = (f.sheet, f.cell, f.category)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    out.sort(key=lambda f: (_SEV_ORDER.get(f.severity, 9), f.sheet, f.cell))
    return out
