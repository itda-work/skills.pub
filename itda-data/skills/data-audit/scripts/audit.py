#!/usr/bin/env python3
"""data-audit 엔트리 — 스프레드시트 수식·데이터 감사 (#952).

[HARD] 보고 전용 — 이 스크립트는 원본을 절대 수정하지 않는다. 수정은 사용자 확인 후 별도로.

macOS/Linux:  python3 scripts/audit.py <파일.xlsx> [--sheet 이름] [--json]
Windows:      py -3 scripts/audit.py <파일.xlsx> [--sheet 이름] [--json]

exit code: Critical 발견 2 · Warning 만 1 · Clean 0 (사용법 오류는 argparse 2).
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

import loader
import checks


def audit_workbook(path: str, sheet: str | None = None) -> list[checks.Finding]:
    """워크북(또는 지정 시트)을 감사해 Finding 리스트를 반환한다. 원본 불변."""
    views, all_names = loader.load_views(path, sheet=sheet)
    return checks.run_all(views, all_names)


def main(argv=None) -> int:
    import argparse
    import json

    import report

    p = argparse.ArgumentParser(description="스프레드시트 수식·데이터 감사 (보고 전용)")
    p.add_argument("path", help="감사할 .xlsx 경로")
    p.add_argument("--sheet", default=None, help="특정 시트만(기본: 전체, 숨은 시트 포함)")
    p.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    args = p.parse_args(argv)

    findings = audit_workbook(args.path, args.sheet)
    if args.json:
        print(json.dumps(report.to_dicts(findings), ensure_ascii=False, indent=2))
    else:
        print(report.render(findings))

    if any(f.severity == "Critical" for f in findings):
        return 2
    if any(f.severity == "Warning" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
