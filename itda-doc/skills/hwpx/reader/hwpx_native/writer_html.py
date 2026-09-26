"""HTML writer compatible with hyve's Go htmlgen generator."""
from __future__ import annotations

import base64
from html import escape as _html_escape
from io import StringIO

from . import document as docir


def write_html(document: docir.Document) -> str:
    out = StringIO()
    for block in document.blocks:
        _write_block(block, out)
    return out.getvalue()


def _write_block(block: docir.Block, out: StringIO) -> None:
    if isinstance(block, docir.Heading):
        _write_heading(block, out)
    elif isinstance(block, docir.Paragraph):
        _write_paragraph(block, out)
    elif isinstance(block, docir.Table):
        _write_table(block, out)
    elif isinstance(block, docir.List):
        _write_list(block, out)
    elif isinstance(block, docir.Image):
        _write_image(block, out)
    elif isinstance(block, docir.HorizontalRule):
        out.write("<hr/>\n")
    elif isinstance(block, docir.CodeBlock):
        _write_code_block(block, out)


def _write_heading(heading: docir.Heading, out: StringIO) -> None:
    tag = f"h{heading.level}"
    out.write(f"<{tag}{_alignment_style(heading.alignment)}>")
    _write_inlines(heading.children, out)
    out.write(f"</{tag}>\n")


def _write_paragraph(paragraph: docir.Paragraph, out: StringIO) -> None:
    out.write(f"<p{_alignment_style(paragraph.alignment)}>")
    _write_inlines(paragraph.children, out)
    out.write("</p>\n")


def _alignment_style(alignment: str) -> str:
    if alignment == "":
        return ""
    return f' style="text-align: {alignment}"'


def _write_table(table: docir.Table, out: StringIO) -> None:
    out.write("<table>\n")
    use_header = len(table.rows) >= 2
    for row_index, row in enumerate(table.rows):
        is_header_row = use_header and row_index == 0
        if is_header_row:
            out.write("<thead>\n")
        elif use_header and row_index == 1:
            out.write("<tbody>\n")
        out.write("<tr>\n")
        for cell in row.cells:
            col_span = cell.col_span or 1
            row_span = cell.row_span or 1
            attrs = ""
            if col_span > 1:
                attrs += f' colspan="{col_span}"'
            if row_span > 1:
                attrs += f' rowspan="{row_span}"'
            tag = "th" if is_header_row else "td"
            out.write(f"<{tag}{attrs}>")
            for child in cell.children:
                _write_block(child, out)
            out.write(f"</{tag}>\n")
        out.write("</tr>\n")
        if is_header_row:
            out.write("</thead>\n")
    if use_header:
        out.write("</tbody>\n")
    out.write("</table>\n")


def _write_list(list_block: docir.List, out: StringIO) -> None:
    tag = "ol" if list_block.ordered else "ul"
    out.write(f"<{tag}>\n")
    for item in list_block.items:
        out.write("<li>")
        for child in item.children:
            _write_block(child, out)
        out.write("</li>\n")
    out.write(f"</{tag}>\n")


def _write_image(image: docir.Image, out: StringIO) -> None:
    alt = image.alt
    if image.data:
        mime = "image/" + image.format if image.format else "image/png"
        src = "data:" + mime + ";base64," + base64.b64encode(image.data).decode("ascii")
    else:
        src = image.path or "image." + image.format
    out.write(f'<img src="{src}" alt="{_escape_attr(alt)}"/>\n')


def _write_code_block(code_block: docir.CodeBlock, out: StringIO) -> None:
    class_attr = f' class="language-{code_block.language}"' if code_block.language else ""
    out.write(f"<pre><code{class_attr}>{_escape_html(code_block.code)}</code></pre>\n")


def _write_inlines(inlines: list[docir.Inline], out: StringIO) -> None:
    for inline in inlines:
        _write_inline(inline, out)


def _write_inline(inline: docir.Inline, out: StringIO) -> None:
    if isinstance(inline, docir.Text):
        _write_text(inline, out)
    elif isinstance(inline, docir.Bold):
        out.write("<strong>")
        _write_inlines(inline.children, out)
        out.write("</strong>")
    elif isinstance(inline, docir.Italic):
        out.write("<em>")
        _write_inlines(inline.children, out)
        out.write("</em>")
    elif isinstance(inline, docir.Underline):
        out.write("<u>")
        _write_inlines(inline.children, out)
        out.write("</u>")
    elif isinstance(inline, docir.Strikethrough):
        out.write("<del>")
        _write_inlines(inline.children, out)
        out.write("</del>")
    elif isinstance(inline, docir.Link):
        out.write(f'<a href="{_escape_attr(inline.url)}">')
        _write_inlines(inline.children, out)
        out.write("</a>")
    elif isinstance(inline, docir.Code):
        out.write(f"<code>{_escape_html(inline.value)}</code>")
    elif isinstance(inline, docir.LineBreak):
        out.write("<br/>")


def _write_text(text: docir.Text, out: StringIO) -> None:
    if text.style is None or not text.style.has_values():
        out.write(_escape_html(text.value))
        return
    props: list[str] = []
    if text.style.font_name:
        props.append(f"font-family: '{text.style.font_name}'")
    if text.style.font_size > 0:
        props.append(f"font-size: {text.style.font_size:.1f}pt")
    if text.style.color:
        props.append(f"color: {text.style.color}")
    out.write(f'<span style="{"; ".join(props)}">')
    out.write(_escape_html(text.value))
    out.write("</span>")


def _escape_html(value: str) -> str:
    return _html_escape(value, quote=False)


def _escape_attr(value: str) -> str:
    return _escape_html(value).replace('"', "&quot;")
