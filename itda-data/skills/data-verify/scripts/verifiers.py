"""값 검수 4종 (#967) — 순수 판정 함수. 백엔드 독립(Grid 만 받는다).

[정확성 원칙] 부동소수점 비교는 허용오차(tolerance)로. 통화·천단위·% 표기는 숫자로 파싱.
plausible ≠ correct — 눈대중·정확 == 금지.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from openpyxl.utils import get_column_letter

_TOTAL = re.compile(r"(합계|소계|총계|총합|누계|^\s*계\s*$|\btotal\b|\bsum\b)", re.IGNORECASE)
_NUM_CLEAN = re.compile(r"[,$₩€£¥\s]")
_TOL = 0.01


@dataclass
class Finding:
    category: str
    location: str
    expected: str
    actual: str
    diff: str
    severity: str
    message: str


def to_number(v):
    """통화·천단위·% 표기를 숫자로. '$1,200'→1200, '45%'→45(기호만 제거), 실패 None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.rstrip("%")
    s = _NUM_CLEAN.sub("", s)
    try:
        return float(s)
    except ValueError:
        return None


def _a1(grid, row0: int, col0: int) -> str:
    return f"{grid.name}!{get_column_letter(col0 + 1)}{row0 + 1}"


def _row_label(row: list, idx: int) -> str:
    for c in row:
        if to_number(c) is None and str(c).strip():
            return str(c).strip()
    return f"{idx + 1}행"


def _is_total_row(row) -> bool:
    """합계/소계/총계 라벨이 있는 집계 행 — 규칙 검수(sum_to·중복 등) 대상에서 제외한다."""
    return any(_TOTAL.search(str(c)) for c in row)


# ── 1. 내부 정합 (소계/총계 ↔ 구성요소 합) ─────────────────────────────────
def verify_internal(grid, tolerance: float = _TOL) -> list[Finding]:
    out = []
    rows = grid.rows
    if len(rows) < 2:
        return out
    ncol = max((len(r) for r in rows), default=0)
    total_rows = [i for i, r in enumerate(rows) if any(_TOTAL.search(str(c)) for c in r)]
    for ti in total_rows:
        prev = max([p for p in total_rows if p < ti], default=0)
        block = range(prev + 1, ti)   # 헤더/이전 총계 제외
        for c in range(ncol):
            declared = to_number(rows[ti][c]) if c < len(rows[ti]) else None
            if declared is None:
                continue
            parts = [to_number(rows[i][c]) for i in block if c < len(rows[i])]
            parts = [p for p in parts if p is not None]
            if len(parts) < 2:
                continue
            s = sum(parts)
            if abs(s - declared) > tolerance:
                out.append(Finding(
                    "내부정합", _a1(grid, ti, c),
                    f"{s:g}(구성요소 합)", f"{declared:g}(표기)", f"{declared - s:+g}",
                    "Critical", f"'{_row_label(rows[ti], ti)}' 행 합계가 구성요소 합과 다름"))
    return out


# ── 2. 규칙 위반 ───────────────────────────────────────────────────────────
def verify_rules(grid, rules: dict) -> list[Finding]:
    out = []
    data = grid.data_rows()   # 합계/총계 행은 각 루프에서 _is_total_row 로 건너뛴다(이중 계산 방지)

    for col_name in rules.get("non_negative", []):
        ci = grid.col_index(col_name)
        if ci is None:
            continue
        for ri, row in enumerate(data):
            if _is_total_row(row):
                continue
            v = to_number(row[ci]) if ci < len(row) else None
            if v is not None and v < 0:
                out.append(Finding("규칙위반", _a1(grid, ri + 1, ci),
                                   "≥ 0", f"{v:g}", f"{v:g}", "Warning",
                                   f"'{col_name}' 음수 불가인데 음수"))

    for col_name, bounds in rules.get("range", {}).items():
        ci = grid.col_index(col_name)
        if ci is None:
            continue
        lo, hi = bounds
        for ri, row in enumerate(data):
            if _is_total_row(row):
                continue
            v = to_number(row[ci]) if ci < len(row) else None
            if v is not None and not (lo <= v <= hi):
                out.append(Finding("규칙위반", _a1(grid, ri + 1, ci),
                                   f"[{lo}, {hi}]", f"{v:g}", "", "Warning",
                                   f"'{col_name}' 범위를 벗어남"))

    for col_name in rules.get("unique", []):
        ci = grid.col_index(col_name)
        if ci is None:
            continue
        seen: dict = {}
        for ri, row in enumerate(data):
            if _is_total_row(row):
                continue
            key = str(row[ci]).strip() if ci < len(row) else ""
            if not key:
                continue
            if key in seen:
                out.append(Finding("규칙위반", _a1(grid, ri + 1, ci),
                                   "유일", f"중복 {key!r}", "", "Warning",
                                   f"'{col_name}' 키 중복: {key} (먼저 {seen[key] + 2}행)"))
            else:
                seen[key] = ri

    for col_name, target in rules.get("sum_to", {}).items():
        ci = grid.col_index(col_name)
        if ci is None:
            continue
        vals = [to_number(row[ci]) for row in data
                if not _is_total_row(row) and ci < len(row)]
        vals = [v for v in vals if v is not None]
        s = sum(vals)
        if abs(s - target) > _TOL:
            out.append(Finding("규칙위반", f"{grid.name}!{col_name}열",
                               f"{target:g}", f"{s:g}", f"{s - target:+g}", "Warning",
                               f"'{col_name}' 합이 {target:g} 이 아님"))
    return out


# ── 3. 외부 대조 (원장/원천 정답셋) ────────────────────────────────────────
def verify_external(grid, cfg: dict) -> list[Finding]:
    out = []
    key_col = grid.col_index(cfg.get("key"))
    val_col = grid.col_index(cfg.get("value"))
    ref = cfg.get("reference", {})
    if key_col is None or val_col is None:
        return out
    for ri, row in enumerate(grid.data_rows()):
        k = str(row[key_col]).strip() if key_col < len(row) else ""
        if k not in ref:
            continue
        actual = to_number(row[val_col]) if val_col < len(row) else None
        expected = to_number(ref[k])
        if actual is None or expected is None:
            continue
        if abs(actual - expected) > _TOL:
            out.append(Finding("외부대조", _a1(grid, ri + 1, val_col),
                               f"{expected:g}(원장)", f"{actual:g}", f"{actual - expected:+g}",
                               "Critical", f"'{k}' 값이 원장과 불일치"))
    return out


# ── 4. 교차 참조 (시트 간/파일 간 같아야 할 값) ────────────────────────────
def _resolve(sheets: dict, spec):
    sheet, ref = spec[0], spec[1]
    g = sheets.get(sheet)
    return g.cell_a1(ref) if g else None


def verify_cross(sheets: dict, links: list) -> list[Finding]:
    out = []
    for link in links:
        av, bv = _resolve(sheets, link["a"]), _resolve(sheets, link["b"])
        an, bn = to_number(av), to_number(bv)
        if an is None or bn is None:
            continue
        if abs(an - bn) > _TOL:
            out.append(Finding("교차참조", f"{link['a']} ↔ {link['b']}",
                               f"{an:g}", f"{bn:g}", f"{bn - an:+g}", "Critical",
                               "짝 위치의 값이 서로 다름"))
    return out


_SEV = {"Critical": 0, "Warning": 1, "Info": 2}


def run(sheets: dict, config: dict) -> list[Finding]:
    out = []
    target = config.get("sheet") or next(iter(sheets), None)
    grid = sheets.get(target)
    if grid is not None:
        if "internal" in config:
            out += verify_internal(grid, config["internal"].get("tolerance", _TOL))
        if "rules" in config:
            out += verify_rules(grid, config["rules"])
        if "external" in config:
            out += verify_external(grid, config["external"])
    if "cross" in config:
        out += verify_cross(sheets, config["cross"])
    out.sort(key=lambda f: _SEV.get(f.severity, 9))
    return out
