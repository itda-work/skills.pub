#!/usr/bin/env python3
"""itda-imagekit CLI 진입점.

이미지 오퍼레이션(info, resize, crop-edges, set-dpi, convert, rotate)을 위한
argparse 기반 CLI. JSON 형식으로 stdout에 출력.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

if sys.version_info[0] < 3:
    sys.exit("Python 3 required")

import transform

VERSION = "0.3.0"
PLUGIN = "imagekit"


def build_response(success: bool, data: dict | None = None,
                   error: dict | None = None, elapsed_ms: int = 0) -> dict:
    """표준 JSON 응답 생성."""
    return {
        "success": success,
        "data": data,
        "error": error,
        "metadata": {
            "plugin": PLUGIN,
            "version": VERSION,
            "execution_time_ms": elapsed_ms,
        },
    }


def build_error(code: str, message: str, details: dict | None = None) -> dict:
    """에러 객체 생성."""
    return {
        "code": code,
        "message": message,
        "details": details or {},
    }


def cmd_info(args: argparse.Namespace) -> dict:
    """info 커맨드 실행."""
    return transform.get_info(args.image_path)


def cmd_resize(args: argparse.Namespace) -> dict:
    """resize 커맨드 실행."""
    tw = transform.parse_dimension(args.target_width) if args.target_width else 0
    th = transform.parse_dimension(args.target_height) if args.target_height else 0
    multiplier = args.multiplier or 0.0

    return transform.resize_image(
        input_path=args.input_image_path,
        output_path=args.output_image_path,
        target_width=tw,
        target_height=th,
        multiplier=multiplier,
        resize_mode=args.resize_mode or "fit",
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
        dry_run=getattr(args, "dry_run", False),
    )


def cmd_crop_edges(args: argparse.Namespace) -> dict:
    """crop-edges 커맨드 실행."""
    return transform.crop_edges(
        input_path=args.input_image_path,
        output_path=args.output_image_path,
        crop_top=args.crop_top,
        crop_bottom=args.crop_bottom,
        crop_left=args.crop_left,
        crop_right=args.crop_right,
        auto_detect=args.auto_detect,
        threshold=args.threshold,
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
        dry_run=getattr(args, "dry_run", False),
    )


def cmd_set_dpi(args: argparse.Namespace) -> dict:
    """set-dpi 커맨드 실행."""
    return transform.set_dpi(
        input_path=args.input_image_path,
        output_path=args.output_image_path,
        target_dpi=args.target_dpi,
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
        dry_run=getattr(args, "dry_run", False),
    )


def cmd_convert(args: argparse.Namespace) -> dict:
    """convert 커맨드 실행."""
    return transform.convert_image(
        input_path=args.input_image_path,
        output_path=args.output_image_path,
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
        dry_run=getattr(args, "dry_run", False),
    )


def cmd_rotate(args: argparse.Namespace) -> dict:
    """rotate 커맨드 실행."""
    return transform.rotate_image(
        input_path=args.input_image_path,
        output_path=args.output_image_path,
        angle=args.angle,
        flip=args.flip,
        jpeg_quality=args.jpeg_quality,
        overwrite=args.overwrite,
        dry_run=getattr(args, "dry_run", False),
    )


def build_parser() -> argparse.ArgumentParser:
    """서브커맨드를 포함한 인자 파서 생성."""
    parser = argparse.ArgumentParser(
        prog="imagekit",
        description="Image processing tool: info, resize, crop, DPI, convert, rotate.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 파일을 저장하지 않고 결과만 미리 확인")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- info ---
    p_info = subparsers.add_parser("info", help="Get image metadata")
    p_info.add_argument("--image-path", required=True, help="Path to image file")
    p_info.set_defaults(func=cmd_info)

    # --- resize ---
    p_resize = subparsers.add_parser("resize", help="Resize image")
    p_resize.add_argument("--input-image-path", required=True, help="Input image path")
    p_resize.add_argument("--output-image-path", required=True, help="Output image path")
    p_resize.add_argument("--target-width", default=None, help="Target width (int or 'Npx')")
    p_resize.add_argument("--target-height", default=None, help="Target height (int or 'Npx')")
    p_resize.add_argument("--multiplier", type=float, default=None, help="Scale factor (0.1-5.0)")
    p_resize.add_argument("--resize-mode", default="fit", choices=["fit", "fill", "exact"],
                          help="Resize mode (default: fit)")
    p_resize.add_argument("--jpeg-quality", type=int, default=85, help="JPEG quality 1-100 (default: 85)")
    p_resize.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    p_resize.set_defaults(func=cmd_resize)

    # --- crop-edges ---
    p_crop = subparsers.add_parser("crop-edges", help="Crop image edges")
    p_crop.add_argument("--input-image-path", required=True, help="Input image path")
    p_crop.add_argument("--output-image-path", required=True, help="Output image path")
    p_crop.add_argument("--crop-top", default=None, help="Top crop (pixels or 'N%%')")
    p_crop.add_argument("--crop-bottom", default=None, help="Bottom crop (pixels or 'N%%')")
    p_crop.add_argument("--crop-left", default=None, help="Left crop (pixels or 'N%%')")
    p_crop.add_argument("--crop-right", default=None, help="Right crop (pixels or 'N%%')")
    p_crop.add_argument("--auto-detect", action="store_true", help="Auto-detect uniform edges")
    p_crop.add_argument("--threshold", type=int, default=10,
                        help="Auto-detect sensitivity 0-255 (default: 10)")
    p_crop.add_argument("--jpeg-quality", type=int, default=85, help="JPEG quality 1-100 (default: 85)")
    p_crop.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    p_crop.set_defaults(func=cmd_crop_edges)

    # --- set-dpi ---
    p_dpi = subparsers.add_parser("set-dpi", help="Set image DPI metadata")
    p_dpi.add_argument("--input-image-path", required=True, help="Input image path")
    p_dpi.add_argument("--output-image-path", required=True, help="Output image path")
    p_dpi.add_argument("--target-dpi", type=int, required=True, help="Target DPI (1-3000)")
    p_dpi.add_argument("--jpeg-quality", type=int, default=95, help="JPEG quality 1-100 (default: 95)")
    p_dpi.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    p_dpi.set_defaults(func=cmd_set_dpi)

    # --- convert ---
    p_conv = subparsers.add_parser("convert", help="Convert between JPEG and PNG formats")
    p_conv.add_argument("--input-image-path", required=True, help="Input image path")
    p_conv.add_argument("--output-image-path", required=True, help="Output image path")
    p_conv.add_argument("--jpeg-quality", type=int, default=95, help="JPEG quality 1-100 (default: 95)")
    p_conv.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    p_conv.set_defaults(func=cmd_convert)

    # --- rotate ---
    p_rot = subparsers.add_parser("rotate", help="Rotate or flip image")
    p_rot.add_argument("--input-image-path", required=True, help="Input image path")
    p_rot.add_argument("--output-image-path", required=True, help="Output image path")
    p_rot.add_argument("--angle", type=int, default=None, choices=[90, 180, 270],
                       help="Rotation angle (90, 180, 270 degrees clockwise)")
    p_rot.add_argument("--flip", default=None, choices=["horizontal", "vertical"],
                       help="Flip direction (horizontal or vertical)")
    p_rot.add_argument("--jpeg-quality", type=int, default=95, help="JPEG quality 1-100 (default: 95)")
    p_rot.add_argument("--overwrite", action="store_true", help="Overwrite output if exists")
    p_rot.set_defaults(func=cmd_rotate)

    return parser


def main(argv: list[str] | None = None) -> int:
    """메인 진입점. 종료 코드를 반환한다."""
    parser = build_parser()
    args = parser.parse_args(argv)

    start = time.monotonic()
    try:
        data = args.func(args)
        elapsed = int((time.monotonic() - start) * 1000)
        response = build_response(success=True, data=data, elapsed_ms=elapsed)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0
    except transform.ImageKitError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        response = build_response(
            success=False,
            error=build_error(e.code, e.message, e.details),
            elapsed_ms=elapsed,
        )
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 1
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        response = build_response(
            success=False,
            error=build_error("INTERNAL_ERROR", str(e)),
            elapsed_ms=elapsed,
        )
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
