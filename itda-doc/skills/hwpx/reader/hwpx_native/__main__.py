"""Command line entry point for the native hwpx skill converter."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .convert import UnsupportedFormatError, convert_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hwpx_native")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="convert HWP/HWPX to Markdown or HTML")
    convert.add_argument("input", help="input .hwp or .hwpx file")
    convert.add_argument("-o", "--output", required=True, help="output file path")
    convert.add_argument("--format", choices=("md", "markdown", "html"), default="md")
    convert.add_argument(
        "--no-extract-images",
        action="store_true",
        help="skip Markdown image extraction and emit #image-omitted placeholders",
    )
    convert.add_argument(
        "--unwrap-layout-tables",
        action="store_true",
        help="본문 전체를 감싼 레이아웃 표(1×1·무거운 셀만 있는 1열 표)를 풀어 본문으로 올린다 (옵트인)",
    )

    args = parser.parse_args(argv)
    if args.command == "convert":
        try:
            output, image_count = convert_file(
                Path(args.input),
                Path(args.output),
                format=args.format,
                extract_images=not args.no_extract_images,
                unwrap_layout=args.unwrap_layout_tables,
            )
        except UnsupportedFormatError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 2
        except FileNotFoundError:
            print(f"오류: 입력 파일이 없습니다: {args.input}", file=sys.stderr)
            return 2
        suffix = f" ({image_count} images)" if image_count else ""
        print(f"converted: {args.input} -> {output}{suffix}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
