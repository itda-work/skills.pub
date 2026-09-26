#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_html.py - HTML cleaner using stdlib html.parser only.

Removes noise (scripts, styles, ads) and preserves content structure.
Uses Python's built-in html.parser - no external dependencies.

Usage:
    python3 clean_html.py [INPUT_FILE] [--output FILE] [--max-depth N]
    py -3 clean_html.py [INPUT_FILE] [--output FILE] [--max-depth N]  # Windows

    Reads from stdin if INPUT_FILE is omitted.

Exit codes:
    0 - Success
    1 - Parse or I/O error
    2 - Invalid arguments
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or later is required.")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tags whose content should be completely removed (tag + all children)
REMOVE_TAGS = frozenset(["script", "style", "noscript", "svg", "iframe"])

# Tags that are safe to preserve in the output structure
KEEP_TAGS = frozenset([
    "html", "head", "body",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    "blockquote", "pre", "code",
    "a", "img",
    "div", "section", "article", "main", "nav", "header", "footer", "aside",
    "span", "strong", "em", "b", "i", "u", "s", "br", "hr",
    "dl", "dt", "dd",
    "figure", "figcaption",
    "form", "label",
    "details", "summary",
])

# Whitelisted attributes per tag (or global)
# Key is tag name, value is set of allowed attributes
# "*" means allowed on any tag
ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "*": frozenset(["id", "class"]),
    "a": frozenset(["href", "id", "class"]),
    "img": frozenset(["src", "alt", "id", "class"]),
}


# Pre-computed allowed attributes per tag (avoids recomputing frozenset union on every tag)
_ALLOWED_ATTRS_CACHE: dict[str, frozenset[str]] = {}


def _get_allowed_attrs(tag: str) -> frozenset[str]:
    """Return allowed attributes for a given tag (cached).

    Combines global allowed attributes with tag-specific ones.
    """
    if tag not in _ALLOWED_ATTRS_CACHE:
        global_attrs = ALLOWED_ATTRS.get("*", frozenset())
        tag_attrs = ALLOWED_ATTRS.get(tag, frozenset())
        _ALLOWED_ATTRS_CACHE[tag] = global_attrs | tag_attrs
    return _ALLOWED_ATTRS_CACHE[tag]


# ---------------------------------------------------------------------------
# HTML Cleaner (HTMLParser subclass)
# ---------------------------------------------------------------------------


class HtmlCleaner(HTMLParser):
    """Streaming HTML cleaner using html.parser.

    Removes unwanted elements, strips non-whitelisted attributes,
    removes HTML comments, and tracks depth for max_depth truncation.
    """

    def __init__(self, max_depth: int | None = None) -> None:
        super().__init__(convert_charrefs=False)
        self._output: list[str] = []
        self._skip_depth: int = 0   # depth counter for skipped elements
        self._current_depth: int = 0
        self._max_depth = max_depth

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        # If inside a remove-tag subtree, track depth only
        if self._skip_depth > 0:
            self._skip_depth += 1
            return

        # If this tag should be removed, start skipping
        if tag in REMOVE_TAGS:
            self._skip_depth = 1
            return

        self._current_depth += 1

        # max_depth truncation: skip children beyond max_depth
        if self._max_depth is not None and self._current_depth > self._max_depth:
            self._depth_exceeded = True
            self._skip_depth = 1
            self._current_depth -= 1
            return

        # Build cleaned tag with allowed attributes only
        if tag in KEEP_TAGS:
            allowed = _get_allowed_attrs(tag)
            clean_attrs = []
            for attr_name, attr_val in attrs:
                attr_name_lower = attr_name.lower()
                if attr_name_lower in allowed:
                    if attr_val is not None:
                        # Escape quotes in attribute values
                        escaped_val = attr_val.replace('"', "&quot;")
                        clean_attrs.append(f'{attr_name_lower}="{escaped_val}"')
                    else:
                        clean_attrs.append(attr_name_lower)

            if clean_attrs:
                self._output.append(f'<{tag} {" ".join(clean_attrs)}>')
            else:
                self._output.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._skip_depth > 0:
            self._skip_depth -= 1
            return

        if tag in KEEP_TAGS:
            self._output.append(f"</{tag}>")

        if tag not in {"br", "hr", "img"}:
            self._current_depth = max(0, self._current_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._output.append(data)

    def handle_comment(self, data: str) -> None:
        # Remove all HTML comments
        pass

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        self._output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        self._output.append(f"&#{name};")

    def get_output(self) -> str:
        """Return the cleaned HTML as a string."""
        return "".join(self._output)


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


# Compiled once at module level to avoid recompilation on every clean() call
_EMPTY_ELEMENT_RE = re.compile(
    r"<(div|span|p|section|article|aside|header|footer|nav|main|li|td|th)"
    r"(?:\s[^>]*)?>[ \t\r\n]*</\1>",
    re.IGNORECASE,
)


def _remove_empty_elements(html: str) -> str:
    """Remove empty block elements with no meaningful content.

    Empty is defined as: no text after whitespace strip AND
    no meaningful child elements (img, a with href).
    Uses a simple regex pass - not recursive.
    """
    # Apply multiple passes for nested empty elements
    prev = None
    result = html
    while result != prev:
        prev = result
        result = _EMPTY_ELEMENT_RE.sub("", result)
    return result


def _collapse_whitespace(html: str) -> str:
    """Collapse excessive whitespace in text content.

    - Multiple spaces -> single space
    - 3+ consecutive newlines -> 2 newlines
    """
    # Collapse multiple spaces (but preserve newlines)
    html = re.sub(r" {2,}", " ", html)
    # Collapse 3+ newlines to 2
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean(html: str, max_depth: int | None = None) -> str:
    """Clean HTML by removing noise and preserving content structure.

    Args:
        html: Raw HTML string.
        max_depth: If set, truncate DOM tree at this depth (1-indexed from body).

    Returns:
        Cleaned HTML string with reduced noise.
    """
    cleaner = HtmlCleaner(max_depth=max_depth)
    cleaner.feed(html)
    cleaned = cleaner.get_output()
    cleaned = _remove_empty_elements(cleaned)
    cleaned = _collapse_whitespace(cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Clean HTML by removing noise while preserving content structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        metavar="INPUT_FILE",
        help="Input HTML file (default: stdin)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        dest="max_depth",
        help="Truncate DOM tree at depth N",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 on success, 1 on I/O/parse error, 2 on invalid args.
    """
    args = _parse_args(argv)

    # Read input
    try:
        if args.input_file:
            with open(args.input_file, encoding="utf-8", errors="replace") as f:
                html = f.read()
        else:
            html = sys.stdin.read()
    except OSError as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 1

    original_size = len(html.encode("utf-8"))

    # Clean
    try:
        result = clean(html, max_depth=args.max_depth)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    cleaned_size = len(result.encode("utf-8"))
    if original_size > 0:
        reduction_pct = (original_size - cleaned_size) / original_size * 100
    else:
        reduction_pct = 0.0

    # Stats to stderr
    print(f"Original: {original_size} bytes", file=sys.stderr)
    print(f"Cleaned: {cleaned_size} bytes", file=sys.stderr)
    print(f"Reduction: {reduction_pct:.1f}%", file=sys.stderr)

    # Write output
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
        else:
            sys.stdout.write(result)
    except OSError as exc:
        print(f"Error writing output: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
