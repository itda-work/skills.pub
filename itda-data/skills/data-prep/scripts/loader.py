"""원시 그리드 로드 (stdlib only) — SPEC-DATA-VERTICAL-001 REQ-010·050.

정돈 전 파일은 헤더가 어디인지 모르므로 DictReader 가 아니라 raw 그리드(list[list])로 읽는다.
인코딩: BOM 기반 utf-16/utf-8-sig 확정, 없으면 utf-8→cp949(⊇euc-kr) 시도.
구분자: , ; \\t 자동 감지(G1).
엑셀 원본(.xlsx zip · .xls OLE)은 읽지 않는다 — 첫 바이트로 알아보고 "CSV 로 저장해 달라"는
명시 에러를 낸다. 예전엔 cp949 로 풀려다 "인코딩 판별 실패"로 원인을 가렸다(itda-work/skills#30).
"""
from __future__ import annotations
import csv

_TRIAL_ENCODINGS: tuple[str, ...] = ("utf-8", "cp949")


_EXCEL_MAGIC = (
    (b"PK\x03\x04", "xlsx(엑셀 통합 문서)"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "xls(엑셀 97-2003)"),
)


class ExcelInputError(ValueError):
    """엑셀 원본이 들어왔다 — CSV 로 저장해 다시 넣어야 한다."""


def _reject_excel(path: str) -> None:
    with open(path, "rb") as f:
        head = f.read(8)
    for magic, kind in _EXCEL_MAGIC:
        if head.startswith(magic):
            raise ExcelInputError(
                f"{path} 는 {kind} 파일입니다 — data-prep 은 CSV·TSV 만 읽습니다. "
                "엑셀에서 '다른 이름으로 저장 → CSV UTF-8(쉼표로 분리)'로 저장한 파일을 넣어 주세요"
                "(시트가 여러 개면 정리할 시트를 골라 저장).")


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
    _reject_excel(path)
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
