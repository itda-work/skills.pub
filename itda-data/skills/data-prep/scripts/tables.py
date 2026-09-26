"""다중 표 경계 감지 (SPEC-DATA-VERTICAL-001 — tidy parity).

한 시트에 빈 행으로 구분된 여러 표가 있을 때 경계를 [가설]로 제시한다.
"""
from __future__ import annotations


def _empty_row(row: list[str]) -> bool:
    return all(str(c).strip() == "" for c in row)


def detect_table_boundaries(grid: list[list[str]]) -> list[tuple[int, int]]:
    """비어있지 않은 연속 구간 [start, end) 목록. 2개 이상이면 다중 표 후보."""
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for i, row in enumerate(grid):
        if _empty_row(row):
            if start is not None:
                segments.append((start, i))
                start = None
        elif start is None:
            start = i
    if start is not None:
        segments.append((start, len(grid)))
    return segments
