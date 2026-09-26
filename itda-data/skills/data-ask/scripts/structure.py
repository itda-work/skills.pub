"""경량 구조 진단 — prep preflight 트리거 (SPEC-DATA-VERTICAL-001 REQ-030·031).

ask 는 정밀 진단을 하지 않는다. "이건 정돈이 필요하다"는 **신호만** 잡아
data-prep 으로 보낸다(정밀 진단·정돈은 data-prep #11 의 책임).
"""
from __future__ import annotations


def _empty_ratio(row: dict) -> float:
    vals = list(row.values())
    if not vals:
        return 1.0
    return sum(1 for v in vals if v in (None, "")) / len(vals)


def assess_structure(rows: list[dict]) -> dict:
    """{needs_prep: bool, signals: [..]}. 보수적 — 명백한 비정돈 신호만."""
    if not rows:
        return {"needs_prep": True, "signals": ["빈 데이터"]}

    signals: list[str] = []
    cols = list(rows[0].keys())

    if any(c is None or str(c).strip() == "" for c in cols):
        signals.append("빈 컬럼명 — 헤더 행 추정 실패 가능(다중 헤더?)")
    if len(cols) != len(set(cols)):
        signals.append("중복 컬럼명")

    near_empty = sum(1 for r in rows if _empty_ratio(r) >= 0.7)
    if near_empty / len(rows) > 0.2:
        signals.append(f"거의 빈 행 {near_empty}건 — 소계/구분선 의심")

    for c in cols:
        if c is None or str(c).strip() == "":
            continue
        miss = sum(1 for r in rows if r.get(c) in (None, "")) / len(rows)
        if miss > 0.5:
            signals.append(f"'{c}' 결측 {miss:.0%}")

    return {"needs_prep": bool(signals), "signals": signals}
