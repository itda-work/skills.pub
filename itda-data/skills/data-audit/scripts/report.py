"""발견 렌더 — 사람용 마크다운 테이블 + 요약 한 줄, 기계용 dict 리스트."""
from __future__ import annotations


def to_dicts(findings) -> list[dict]:
    return [
        {
            "sheet": f.sheet,
            "cell": f.cell,
            "severity": f.severity,
            "category": f.category,
            "issue": f.issue,
            "fix": f.fix,
        }
        for f in findings
    ]


def counts(findings) -> dict:
    return {
        "Critical": sum(1 for f in findings if f.severity == "Critical"),
        "Warning": sum(1 for f in findings if f.severity == "Warning"),
        "Info": sum(1 for f in findings if f.severity == "Info"),
    }


def summary_line(findings) -> str:
    c = counts(findings)
    verdict = "Clean" if c["Critical"] == 0 and c["Warning"] == 0 else (
        "Major Issues" if c["Critical"] else "Minor Issues"
    )
    return f"감사 결과: {verdict} — Critical {c['Critical']} · Warning {c['Warning']} · Info {c['Info']}"


def _cell(text) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def render(findings) -> str:
    if not findings:
        return "감사 결과: Clean — 발견된 문제 없음 (수식·데이터 레벨)"
    lines = [summary_line(findings), ""]
    lines.append("| # | Sheet | Cell | Severity | Category | Issue | Fix |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, f in enumerate(findings, 1):
        lines.append(
            f"| {i} | {_cell(f.sheet)} | {_cell(f.cell)} | {f.severity} | "
            f"{_cell(f.category)} | {_cell(f.issue)} | {_cell(f.fix)} |"
        )
    return "\n".join(lines)
