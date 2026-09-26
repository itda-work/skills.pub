"""Conversion entry points for the native HWPX package."""
from __future__ import annotations

from pathlib import Path

from .hwp5.reader import read_hwp5_file
from .hwpx.reader import read_hwpx_file
from .writer_html import write_html
from .writer_md import write_markdown


def convert_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    format: str = "md",
    extract_images: bool = True,
    images_dir: str | Path | None = None,
) -> tuple[Path, int]:
    input_path = Path(input_path)
    output = Path(output_path) if output_path is not None else input_path.with_suffix(f".{format}")
    if format not in {"md", "markdown", "html"}:
        raise ValueError(f"unsupported output format: {format}")
    document = _read_input_file(input_path)
    if format == "html":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(write_html(document), encoding="utf-8")
        return output, 0
    if images_dir is None and extract_images:
        images_dir = output.with_suffix("")
    markdown, image_count = write_markdown(document, images_dir=images_dir, extract_images=extract_images)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return output, image_count


def convert_to_markdown(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    extract_images: bool = True,
    images_dir: str | Path | None = None,
) -> str:
    input_path = Path(input_path)
    document = _read_input_file(input_path)
    resolved_images_dir = images_dir
    if resolved_images_dir is None and output_path is not None and extract_images:
        resolved_images_dir = Path(output_path).with_suffix("")
    markdown, _ = write_markdown(document, images_dir=resolved_images_dir, extract_images=extract_images)
    return markdown


def _read_input_file(input_path: Path):
    suffix = input_path.suffix.lower()
    if suffix == ".hwpx":
        return read_hwpx_file(input_path)
    if suffix == ".hwp":
        return read_hwp5_file(input_path)
    raise ValueError(f"unsupported input format: {input_path.suffix}")
