"""정직 보고 (SPEC-DATA-VERTICAL-001 REQ-003·040).

소셀 경고는 queryplan 이 강제 주입한 `n` 컬럼에서 자동 발동한다(LLM SQL 의존 아님).
"""
from __future__ import annotations

_COUNT_KEYS = {"n", "count", "cnt", "건수", "개수", "표본수"}


def small_n_rows(result: dict, threshold: int = 5) -> list:
    lower = [str(c).lower() for c in result["columns"]]
    idx = next((i for i, name in enumerate(lower) if name in _COUNT_KEYS), None)
    if idx is None:
        return []
    flagged = []
    for row in result["rows"]:
        try:
            if row[idx] is not None and float(row[idx]) < threshold:
                flagged.append(row)
        except (TypeError, ValueError):
            continue
    return flagged


def render(result: dict, threshold: int = 5) -> str:
    lines = [f"실행한 SQL: {result['sql']}", "열: " + ", ".join(str(c) for c in result["columns"])]
    for row in result["rows"]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    if result.get("truncated"):
        lines.append(f"… (상위 {result['row_count']}행만 표시)")
    if result.get("fallback"):
        lines.append("⚠️ 이 결과는 QueryPlan 으로 표현 불가해 직접 SQL(fallback)로 실행됐습니다 — 수치 해석에 주의하세요.")
    flagged = small_n_rows(result, threshold)
    if flagged:
        lines.append(f"⚠️ 표본이 작은 그룹(N<{threshold})이 {len(flagged)}건 — 우연일 수 있으니 단정하지 마세요.")
    return "\n".join(lines)
