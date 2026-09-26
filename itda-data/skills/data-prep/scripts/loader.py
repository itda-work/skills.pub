"""원시 그리드 로드 (stdlib only) — SPEC-DATA-VERTICAL-001 REQ-010·050.

정돈 전 파일은 헤더가 어디인지 모르므로 DictReader 가 아니라 raw 그리드(list[list])로 읽는다.
인코딩: BOM 기반 utf-16/utf-8-sig 확정, 없으면 utf-8→cp949(⊇euc-kr) 시도.
구분자: , ; \\t 자동 감지(G1).
"""
from __future__ import annotations
import csv

_TRIAL_ENCODINGS: tuple[str, ...] = ("utf-8", "cp949")


def _detect_encoding(path: str) -> str | None:
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return None


def _sniff_delimiter(line: str) -> str:
    counts = {d: line.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_grid(path: str, delimiter: str | None = None) -> tuple[list[list[str]], str]:
    detected = _detect_encoding(path)
    encs = (detected,) if detected else _TRIAL_ENCODINGS
    last: Exception | None = None
    for enc in encs:
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.readline()
                f.seek(0)
                delim = delimiter or _sniff_delimiter(sample)
                return [list(r) for r in csv.reader(f, delimiter=delim)], enc
        except UnicodeDecodeError as e:
            last = e
            continue
    raise ValueError(f"CSV 인코딩 판별 실패(utf-8/utf-16/cp949): {path}") from last
