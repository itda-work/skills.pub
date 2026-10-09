"""HTML to Markdown conversion with custom converters.

Wraps markdownify with project-specific converters for tables, code blocks, figures.
"""
from __future__ import annotations

import re

from markdownify import MarkdownConverter


def _is_complex_table(el: object) -> bool:
    """Return True only when cells actually span multiple rows or columns."""
    for attr in ("colspan", "rowspan"):
        for cell in el.find_all(attrs={attr: True}):
            try:
                if int(cell[attr]) > 1:
                    return True
            except (ValueError, TypeError):
                pass
    return False


class DefuddleConverter(MarkdownConverter):
    """Custom Markdown converter with Defuddle-specific handling."""

    def convert_table(self, el: object, text: str, **kwargs: object) -> str:
        """Handle tables: complex (colspan/rowspan) -> HTML, simple -> MD."""
        # Complex tables with spanning cells: preserve as HTML
        if _is_complex_table(el):
            return str(el) + "\n\n"

        # Layout tables (no headers, single column): just extract text
        if not el.find("th"):
            rows = el.find_all("tr")
            if rows:
                first_row = rows[0]
                cells = first_row.find_all(["td", "th"])
                if len(cells) <= 1:
                    return text + "\n\n"

        # Simple table: fall through to default markdown conversion
        return super().convert_table(el, text, **kwargs)

    def convert_pre(self, el: object, text: str, **kwargs: object) -> str:
        """Preserve language fencing from code class."""
        code = el.find("code")
        if code:
            lang = ""
            classes = code.get("class") or []
            for cls in classes:
                if cls.startswith("language-"):
                    lang = cls[9:]
                    break
            code_text = code.get_text()
            return f"\n```{lang}\n{code_text}\n```\n\n"
        # Pre without code - use default behavior
        return super().convert_pre(el, text, **kwargs)

    def convert_figure(self, el: object, text: str, **kwargs: object) -> str:
        """Handle figure with optional figcaption."""
        figcaption = el.find("figcaption")
        img = el.find("img")
        if img:
            alt = img.get("alt", "")
            src = img.get("src", "")
            caption = figcaption.get_text().strip() if figcaption else ""
            if caption and caption != alt:
                return f"![{alt}]({src})\n_{caption}_\n\n"
            return f"![{alt}]({src})\n\n"
        return text


def html_to_markdown(html: str, title: str | None = None) -> str:
    """Convert standardized HTML to Markdown.

    Handles:
    - Simple tables (no colspan/rowspan) -> Markdown table syntax
    - Complex tables (cells spanning >1 row/col) -> Preserved as HTML
    - Layout tables (single column, no headers) -> Content extracted only
    - Code blocks with language fencing
    - Standard Markdown elements (headings, lists, links, images, etc.)
    """
    return DefuddleConverter().convert(html)


def post_process_markdown(md: str, title: str | None = None) -> str:
    """Apply post-processing to Markdown output.

    - Remove duplicate # Title if it matches metadata title
    - Remove empty links [](url) (preserve image links ![](url))
    - Collapse 3+ consecutive newlines to 2
    """
    # Remove duplicate title heading
    if title:
        title_heading = f"# {title}"
        lines = md.split("\n")
        filtered: list[str] = []
        found_title = False
        for line in lines:
            if not found_title and line.strip() == title_heading:
                found_title = True
                continue
            filtered.append(line)
        md = "\n".join(filtered)

    # Remove empty links but preserve image links
    # Pattern: [](url) but NOT ![](url)
    md = re.sub(r"(?<!!)\[\]\([^)]*\)", "", md)

    # Collapse 3+ consecutive newlines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)

    return md.strip()
