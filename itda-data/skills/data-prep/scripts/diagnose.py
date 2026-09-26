"""구조 진단 (SPEC-DATA-VERTICAL-001 REQ-050). 모든 추론은 [가설].

흔한 비정돈 3종: 제목/빈 행 위의 헤더, 소계/빈 행, 빈 열. (가로전개·다중표는 후속)
"""
from __future__ import annotations
import re

_SUBTOTAL = re.compile(r"(합계|소계|총계|총합|누계|subtotal|grand\s*total|^\s*계\s*$)", re.I)


def _is_num(s) -> bool:
    try:
        float(str(s).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


def _ne_ratio(row: list) -> float:
    if not row:
        return 0.0
    return sum(1 for c in row if str(c).strip() != "") / len(row)


def detect_header_row(grid: list[list[str]], scan: int = 10) -> int:
    """레이블(비숫자) 비중이 높고 다음 행이 데이터로 보이는 첫 행을 헤더로 추정."""
    for i, row in enumerate(grid[:scan]):
        ne_count = sum(1 for c in row if str(c).strip() != "")
        if ne_count < 2 or _ne_ratio(row) < 0.6:
            continue
        nonnum = sum(1 for c in row if str(c).strip() != "" and not _is_num(c))
        if nonnum < max(2, ne_count * 0.6):
            continue
        if i + 1 < len(grid) and _ne_ratio(grid[i + 1]) >= 0.3:
            return i
    return 0


def detect_subtotal_rows(grid: list[list[str]], header_idx: int) -> list[int]:
    out = []
    for i in range(header_idx + 1, len(grid)):
        row = grid[i]
        if any(_SUBTOTAL.search(str(c)) for c in row):
            out.append(i)
        elif _ne_ratio(row) < 0.3:
            out.append(i)
    return out


def detect_empty_columns(grid: list[list[str]], header_idx: int) -> list[int]:
    if header_idx >= len(grid):
        return []
    width = len(grid[header_idx])
    data = grid[header_idx + 1:]
    return [c for c in range(width)
            if all(c >= len(r) or str(r[c]).strip() == "" for r in data)]


def _is_num_loose(s) -> bool:
    """통화기호·천단위 콤마가 붙은 숫자도 숫자로 인정(number_as_text 정제로 해소되므로)."""
    t = str(s)
    for sym in "$₩€£¥":
        t = t.replace(sym, "")
    try:
        float(t.replace(",", "").strip())
        return True
    except (TypeError, ValueError):
        return False


def detect_mixed_type_columns(grid: list[list[str]], data_anchor: int, num_ratio: float = 0.7) -> list[dict]:
    """대부분 숫자인데 '정제로도 안 풀리는' 텍스트가 소수 섞인 열 [가설] 감지. 경고만 한다.

    통화·천단위 표기($1,200)는 number_as_text 정제로 숫자가 되므로 숫자로 본다 — 이걸 텍스트로
    오판하면 정제하면 사라질 것을 경고하게 된다. 어느 타입으로 통일할지는 사람만 판단(값 삭제 위험).
    """
    data = grid[data_anchor + 1:]
    if not data:
        return []
    width = max((len(r) for r in data), default=0)
    out = []
    for c in range(width):
        vals = [str(r[c]).strip() for r in data if c < len(r) and str(r[c]).strip() != ""]
        if len(vals) < 4:
            continue
        nums = sum(1 for v in vals if _is_num_loose(v))
        ratio = nums / len(vals)
        if num_ratio <= ratio < 1.0:
            samples = [v for v in vals if not _is_num_loose(v)][:3]
            out.append({"col": c, "num_ratio": round(ratio, 2), "text_samples": samples})
    return out


def detect_multirow_header(grid: list[list[str]], header_idx: int) -> int:
    """그룹 행 + 실제 컬럼 행으로 된 2행 헤더 감지(F6). 1 또는 2 반환."""
    if header_idx + 1 >= len(grid):
        return 1
    r0, r1 = grid[header_idx], grid[header_idx + 1]
    ne0 = [str(c).strip() for c in r0 if str(c).strip() != ""]
    ne1 = [str(c).strip() for c in r1 if str(c).strip() != ""]
    if len(ne1) < 2:
        return 1
    nonnum1 = sum(1 for c in ne1 if not _is_num(c))
    if nonnum1 < max(2, len(ne1) * 0.6):       # 둘째 행도 라벨 행이어야
        return 1
    if ne0 and len(set(ne0)) < len(ne0):        # 첫 행 중복 = 그룹 스패닝 신호
        return 2
    return 1


def flatten_header(grid: list[list[str]], header_idx: int) -> list[str]:
    """2행 헤더를 '그룹 / 컬럼' 으로 평탄화(구분자 ' / ', SPEC-DATA-TIDY 계승)."""
    r0, r1 = grid[header_idx], grid[header_idx + 1]
    width = max(len(r0), len(r1))
    out = []
    for i in range(width):
        g = str(r0[i]).strip() if i < len(r0) else ""
        s = str(r1[i]).strip() if i < len(r1) else ""
        out.append(f"{g} / {s}" if (g and s and g != s) else (s or g))
    return out


def diagnose(grid: list[list[str]]) -> dict:
    if not grid:
        return {"status": "blocked", "reason": "빈 파일"}
    h = detect_header_row(grid)
    header_rows = detect_multirow_header(grid, h)
    header_hypothesis = flatten_header(grid, h) if header_rows == 2 else (grid[h] if h < len(grid) else [])
    data_anchor = h + header_rows - 1   # 데이터 시작 직전 행(detect_* 는 +1 부터 스캔)
    return {
        "status": "diagnosed",
        "header_row": h,
        "header_rows": header_rows,
        "header_hypothesis": header_hypothesis,
        "subtotal_rows": detect_subtotal_rows(grid, data_anchor),
        "empty_columns": detect_empty_columns(grid, data_anchor),
        "mixed_type_columns": detect_mixed_type_columns(grid, data_anchor),
    }
