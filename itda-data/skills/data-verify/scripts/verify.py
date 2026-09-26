#!/usr/bin/env python3
"""data-verify 엔트리 — 데이터 수치 검수 (#967).

[HARD] 보고 전용 — 원본을 절대 수정하지 않는다. 수정은 사용자 확인 후 별도로.

macOS/Linux:  python3 scripts/verify.py <파일.xlsx> [--config config.json] [--json]
Windows:      py -3 scripts/verify.py <파일.xlsx> [--config config.json] [--json]

exit code: Critical 발견 2 · Warning 만 1 · 이상 없음 0.
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

import loader
import verifiers


def verify_workbook(path: str, config: dict | None = None) -> list[verifiers.Finding]:
    """워크북을 config 에 따라 검수해 Finding 리스트를 반환한다. 원본 불변."""
    sheets = loader.load_sheets(path)
    return verifiers.run(sheets, config or {})


def main(argv=None) -> int:
    import argparse
    import json

    import report

    p = argparse.ArgumentParser(description="데이터 수치 검수 (보고 전용)")
    p.add_argument("path", help="검수할 .xlsx/.csv 경로")
    p.add_argument("--config", default=None, help="검수 설정 JSON 경로")
    p.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    args = p.parse_args(argv)

    config = {}
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            config = json.load(f)

    findings = verify_workbook(args.path, config)
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
