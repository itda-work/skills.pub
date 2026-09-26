"""Native Python HWP/HWPX conversion for the hwpx skill."""
from __future__ import annotations

from .convert import convert_file, convert_to_markdown
from .hwp5.reader import read_hwp5_file
from .hwpx.reader import read_hwpx_file
from .writer_html import write_html
from .writer_md import write_markdown

__all__ = [
    "convert_file",
    "convert_to_markdown",
    "read_hwp5_file",
    "read_hwpx_file",
    "write_html",
    "write_markdown",
]

__version__ = "0.1.0"
