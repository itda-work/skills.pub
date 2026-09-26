"""Command line entry point for the native hwpx skill converter."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .convert import convert_file


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

    args = parser.parse_args(argv)
    if args.command == "convert":
        output, image_count = convert_file(
            Path(args.input),
            Path(args.output),
            format=args.format,
            extract_images=not args.no_extract_images,
        )
        suffix = f" ({image_count} images)" if image_count else ""
        print(f"converted: {args.input} -> {output}{suffix}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
