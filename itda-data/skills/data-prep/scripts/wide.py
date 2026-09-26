"""가로 전개(wide) 진단 + melt (SPEC-DATA-VERTICAL-001 — tidy parity).

'지역,1월,2월,3월' 처럼 값이 컬럼으로 퍼진 표를 long 형태로. 감지는 [가설],
실제 melt 는 사용자가 id/value 분할을 확인한 뒤 적용한다.
"""
from __future__ import annotations
import re

_NUMISH = re.compile(r"^\d{1,4}$|^\d{1,2}\s*월$|^\d{4}\s*년?$|^Q[1-4]$|^\d{4}-\d{2}$", re.I)


def detect_wide(header: list[str]) -> dict:
    value_idx = [i for i, h in enumerate(header) if _NUMISH.match(str(h).strip())]
    if len(value_idx) >= 3:
        id_idx = [i for i in range(len(header)) if i not in set(value_idx)]
        return {"is_wide": True, "id_columns": id_idx, "value_columns": value_idx}
    return {"is_wide": False, "id_columns": list(range(len(header))), "value_columns": []}


def melt(header: list[str], rows: list[list[str]], id_idx: list[int], value_idx: list[int],
         var_name: str = "구분", value_name: str = "값") -> tuple[list[str], list[list[str]]]:
    new_header = [header[i] for i in id_idx] + [var_name, value_name]
    out: list[list[str]] = []
    for r in rows:
        ids = [(r[i] if i < len(r) else "") for i in id_idx]
        for v in value_idx:
            out.append(ids + [str(header[v]), (r[v] if v < len(r) else "")])
    return new_header, out
