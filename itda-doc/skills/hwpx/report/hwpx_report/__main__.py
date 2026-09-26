from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import DocSpec
from .report import HWPXReportError, write_report_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hwpx_report")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="convert DocSpec JSON to HWPX")
    convert.add_argument("spec", help="DocSpec JSON path, or - for stdin")
    convert.add_argument("-o", "--output", required=True, help="output .hwpx path")
    which = convert.add_mutually_exclusive_group()
    which.add_argument("--template", default="gov-report", help="내장 템플릿 id 전용 (기본 gov-report) — 디렉토리는 --template-dir")
    which.add_argument(
        "--template-dir",
        default=None,
        help="커스텀 템플릿 디렉토리(derive_profile.py analyze 산출 프로파일). --template 과 함께 쓸 수 없다",
    )

    args = parser.parse_args(argv)
    if args.command != "convert":
        parser.error(f"unknown command: {args.command}")

    # --template 은 **내장 id 전용**이다 — 경로를 받으면 --template-dir 과 의미가 겹치고,
    # 디렉토리 이름이 내장 id 와 같으면 사용자 프로파일이 조용히 무시된다(Claude R2 C-F2·C-F9).
    if args.template_dir:
        template: str | Path = Path(args.template_dir)
    else:
        if "/" in args.template or "\\" in args.template or Path(args.template).is_dir():
            parser.error(f"--template 은 내장 템플릿 id 전용입니다: {args.template!r} — 디렉토리는 --template-dir 를 쓰세요")
        template = args.template
    try:
        if args.spec == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.spec).read_text(encoding="utf-8")
        spec = DocSpec.from_json(json.loads(raw))
        write_report_file(template, spec, args.output)
    except (OSError, json.JSONDecodeError, HWPXReportError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(f"보고서 HWPX 생성 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
