"""검수 발견 렌더 — 사람용 마크다운 테이블 + 요약, 기계용 dict."""
from __future__ import annotations


def to_dicts(findings) -> list[dict]:
    return [
        {
            "category": f.category, "location": f.location,
            "expected": f.expected, "actual": f.actual, "diff": f.diff,
            "severity": f.severity, "message": f.message,
        }
        for f in findings
    ]


def counts(findings) -> dict:
    return {sev: sum(1 for f in findings if f.severity == sev)
            for sev in ("Critical", "Warning", "Info")}


def summary_line(findings) -> str:
    c = counts(findings)
    verdict = "이상 없음" if c["Critical"] == 0 and c["Warning"] == 0 else (
        "주요 불일치" if c["Critical"] else "경미 불일치")
    return f"검수 결과: {verdict} — Critical {c['Critical']} · Warning {c['Warning']} · Info {c['Info']}"


def _c(text) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def render(findings) -> str:
    if not findings:
        return "검수 결과: 이상 없음 — 발견된 불일치 없음"
    lines = [summary_line(findings), ""]
    lines.append("| # | 종류 | 위치 | 기대값 | 실제값 | 차이 | 심각도 | 내용 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, f in enumerate(findings, 1):
        lines.append(
            f"| {i} | {_c(f.category)} | {_c(f.location)} | {_c(f.expected)} | "
            f"{_c(f.actual)} | {_c(f.diff)} | {f.severity} | {_c(f.message)} |")
    return "\n".join(lines)
