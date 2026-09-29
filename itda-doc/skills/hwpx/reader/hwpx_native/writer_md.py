"""Markdown writer compatible with hyve's Go markdown writer."""
from __future__ import annotations

from html import escape as _html_escape
from io import StringIO
from pathlib import Path
import posixpath
import re

from . import document as docir


class MarkdownWriter:
    def __init__(self, images_dir: str | Path | None = None, extract_images: bool = True) -> None:
        self.images_dir = Path(images_dir) if images_dir else None
        self.extract_images = extract_images
        self.image_counter = 0

    def write(self, document: docir.Document) -> tuple[str, int]:
        out = StringIO()
        for block in document.blocks:
            self._write_block(block, out, 0)
        return out.getvalue(), self.image_counter

    def _write_block(self, block: docir.Block, out: StringIO, depth: int) -> None:
        if isinstance(block, docir.Heading):
            self._write_heading(block, out)
        elif isinstance(block, docir.Paragraph):
            self._write_paragraph(block, out, depth)
        elif isinstance(block, docir.Table):
            self._write_table(block, out)
        elif isinstance(block, docir.List):
            self._write_list(block, out, depth)
        elif isinstance(block, docir.Image):
            self._write_image(block, out)
        elif isinstance(block, docir.HorizontalRule):
            out.write("---\n\n")
        elif isinstance(block, docir.CodeBlock):
            out.write(f"```{block.language}\n{block.code}\n```\n\n")

    def _write_heading(self, heading: docir.Heading, out: StringIO) -> None:
        inline = render_inlines(heading.children)
        out.write("#" * heading.level + " " + inline + "\n\n")

    def _write_paragraph(self, paragraph: docir.Paragraph, out: StringIO, depth: int) -> None:
        inline = render_inlines(paragraph.children)
        if inline == "":
            return
        if depth > 0:
            out.write(inline)
            return
        out.write(inline + "\n\n")

    def _write_image(self, image: docir.Image, out: StringIO) -> None:
        src = image.path
        alt = image.alt or "image"
        if image.data and self.images_dir is not None and self.extract_images:
            src = self._extract_image_file(image)
        elif image.data and not self.extract_images:
            src = "#image-omitted"
        elif src == "":
            src = "image." + image.format

        if image.width > 0 or image.height > 0:
            out.write(f'<img src="{src}" alt="{alt}" width="{image.width}" height="{image.height}" />\n\n')
        else:
            out.write(f'<img src="{src}" alt="{alt}" />\n\n')

    def _extract_image_file(self, image: docir.Image) -> str:
        self.image_counter += 1
        data = image.data
        # 선언 format 보다 실제 바이트가 우선 — 선언이 틀린 파일이 실재한다
        ext = _sniff_ext(data) or _mime_to_ext(image.format)
        if ext == "bmp":
            converted = _convert_bmp_to_png(data)
            if converted is not None:
                data = converted
                ext = "png"
        filename = f"image_{self.image_counter:04d}.{ext}"
        assert self.images_dir is not None
        self.images_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.images_dir / filename
        clean_dir = self.images_dir.resolve()
        clean_path = file_path.resolve()
        if clean_dir != clean_path and clean_dir not in clean_path.parents:
            raise ValueError(f"이미지 경로가 허용 범위를 벗어납니다: {filename}")
        file_path.write_bytes(data)
        ref = posixpath.join(self.images_dir.name, filename)
        image.path = ref
        return ref

    def _write_list(self, list_block: docir.List, out: StringIO, depth: int) -> None:
        indent = "  " * depth
        for index, item in enumerate(list_block.items):
            prefix = f"{indent}{index + 1}. " if list_block.ordered else indent + "- "
            item_out = StringIO()
            for child in item.children:
                if isinstance(child, docir.Paragraph):
                    self._write_paragraph(child, item_out, depth + 1)
                elif isinstance(child, docir.List):
                    self._write_list(child, item_out, depth + 1)
                else:
                    self._write_block(child, item_out, depth + 1)
            content = item_out.getvalue()
            lines = _split_after(content, "\n")
            if lines and lines[-1] == "":
                lines = lines[:-1]
            for line_index, line in enumerate(lines):
                out.write((prefix if line_index == 0 else "  ") + line)
            if content and not content.endswith("\n"):
                out.write("\n")
        if depth == 0:
            out.write("\n")

    def _write_table(self, table: docir.Table, out: StringIO) -> None:
        if not table.rows:
            return
        if _table_needs_html(table):
            self._write_table_html(table, out)
        else:
            self._write_table_gfm(table, out)

    def _write_table_gfm(self, table: docir.Table, out: StringIO) -> None:
        all_rows: list[list[str]] = []
        for row in table.rows:
            rendered_row = []
            for cell in row.cells:
                rendered_row.append(_escape_pipe_cell(self._render_cell(cell.children)))
            all_rows.append(rendered_row)
        out.write(_row_to_gfm(all_rows[0]))
        out.write(_row_to_gfm(["---"] * len(all_rows[0])))
        for row in all_rows[1:]:
            out.write(_row_to_gfm(row))
        out.write("\n")

    def _write_table_html(self, table: docir.Table, out: StringIO) -> None:
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
                txt = self._render_cell_html(cell.children)
                attrs = ""
                if cell.col_span > 1:
                    attrs += f' colspan="{cell.col_span}"'
                if cell.row_span > 1:
                    attrs += f' rowspan="{cell.row_span}"'
                tag = "th" if is_header_row else "td"
                out.write(f"<{tag}{attrs}>{txt}</{tag}>\n")
            out.write("</tr>\n")
            if is_header_row:
                out.write("</thead>\n")
        if use_header:
            out.write("</tbody>\n")
        out.write("</table>\n\n")

    def _render_cell(self, blocks: list[docir.Block]) -> str:
        """표 셀 안의 블록을 **문단 경계를 살려** 한 줄 문자열로 만든다 (#1651 R1).

        구 구현은 셀 문단을 depth>0 경로로 써서 구분자 없이 이어 붙였다 —
        `브라더 공기관` + `기본 보고서 양식` 이 `브라더 공기관기본 보고서 양식` 이
        됐고, 목차 표는 `Ⅰ. 개요 1Ⅱ. 추진배경 2…` 로 뭉쳤다. 문단 사이는 개행으로
        두고, GFM 표는 `_escape_pipe_cell` 이 `<br>` 로, HTML 표는 호출부가 `<br>` 로 바꾼다.
        """
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, docir.Paragraph):
                inline = render_inlines(block.children).strip()
                if inline:
                    parts.append(inline)
            elif isinstance(block, docir.Heading):
                parts.append(render_inlines(block.children).strip())
            else:
                rendered = self._render_blocks([block], 1).strip()
                if rendered:
                    parts.append(rendered)
        return "\n".join(parts)

    def _render_cell_html(self, blocks: list[docir.Block]) -> str:
        """HTML 표 셀 내용 (#3).

        HTML 블록 안에서는 마크다운이 처리되지 않으므로 강조는 `<strong>`·`<em>` 로, 텍스트는
        이스케이프해서 쓴다. 셀 안 중첩 표는 한 줄 HTML 로 그대로 넣는다 — 줄바꿈을 `<br>` 로
        바꾸면 표 마크업이 글자처럼 보인다.
        """
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, (docir.Paragraph, docir.Heading)):
                rendered = render_inlines_html(block.children).strip()
                rendered = _strip_br_edges(rendered)
            elif isinstance(block, docir.Table):
                rendered = self._table_html_inline(block)
            else:
                rendered = self._render_blocks([block], 1).strip().replace("\n", "<br>")
            if rendered:
                parts.append(rendered)
        return "<br>".join(parts)

    def _table_html_inline(self, table: docir.Table) -> str:
        rows: list[str] = []
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                attrs = ""
                if cell.col_span > 1:
                    attrs += f' colspan="{cell.col_span}"'
                if cell.row_span > 1:
                    attrs += f' rowspan="{cell.row_span}"'
                cells.append(f"<td{attrs}>{self._render_cell_html(cell.children)}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return "<table>" + "".join(rows) + "</table>"

    def _render_blocks(self, blocks: list[docir.Block], depth: int) -> str:
        out = StringIO()
        for block in blocks:
            self._write_block(block, out, depth)
        return out.getvalue()


def write_markdown(
    document: docir.Document,
    images_dir: str | Path | None = None,
    extract_images: bool = True,
) -> tuple[str, int]:
    return MarkdownWriter(images_dir=images_dir, extract_images=extract_images).write(document)


def render_inlines(inlines: list[docir.Inline]) -> str:
    return "".join(render_inline(inline) for inline in _merge_adjacent_emphasis(inlines))


_EMPHASIS_TYPES = (docir.Bold, docir.Italic, docir.Strikethrough)


def _merge_adjacent_emphasis(inlines: list[docir.Inline]) -> list[docir.Inline]:
    """글자모양 경계로 쪼개진 같은 강조를 하나로 잇는다 — `**무료****대여**` 잔재 방지(#3, #7).

    밑줄은 마크다운·HTML 셀 어디서도 표시를 만들지 않으므로 먼저 포장을 푼다. 글자모양 순서상 밑줄이 가장
    바깥이라(`Underline(Bold(Text))`) 풀지 않으면 `굵게 · 밑줄(굵게) · 굵게` 가 이어지지 못해 `**출****자**`,
    `(****https://…` 가 남았다(#7). 빈 글자 조각(필드·하이퍼링크 컨트롤 자리)도 병합을 막으므로 건너뛴다.
    이은 자식은 렌더 때 다시 이 함수를 거치므로 안쪽 강조까지 이어진다.
    """
    flat: list[docir.Inline] = []
    for inline in inlines:
        if isinstance(inline, docir.Underline):
            flat.extend(inline.children)
        elif isinstance(inline, docir.Text) and inline.value == "":
            continue
        else:
            flat.append(inline)
    merged: list[docir.Inline] = []
    for inline in flat:
        last = merged[-1] if merged else None
        if last is not None and type(last) is type(inline) and isinstance(inline, _EMPHASIS_TYPES):
            merged[-1] = type(inline)(children=[*last.children, *inline.children])
        else:
            merged.append(inline)
    return merged


_MD_EDGE_RE = re.compile(r"^(\s*)(.*?)(\s*)$", re.DOTALL)


def _wrap_md(marker: str, inner: str) -> str:
    """강조 표시 안쪽 끝에 공백·줄바꿈이 오면 마크다운이 강조로 읽지 않는다 — 태그 밖으로 뺀다.
    내용이 비면 표시를 만들지 않는다(빈 `****` 잔재 방지, #3)."""
    lead, body, trail = _MD_EDGE_RE.match(inner).groups()
    if not body:
        return lead + trail
    return f"{lead}{marker}{body}{marker}{trail}"


def render_inline(inline: docir.Inline) -> str:
    if isinstance(inline, docir.Text):
        # 원문 별표(각주 `*`·가림 `****`)는 강조 구문과 섞이면 강조가 잘못 짝지어지거나 줄머리 `* ` 가 목록이 된다 —
        # 글자로 남도록 이스케이프한다(#8). HTML 셀 경로(_render_inline_html)는 마크다운이 아니라 불필요.
        return inline.value.replace("*", "\\*")
    if isinstance(inline, docir.Bold):
        return _wrap_md("**", render_inlines(inline.children))
    if isinstance(inline, docir.Italic):
        return _wrap_md("*", render_inlines(inline.children))
    if isinstance(inline, docir.Underline):
        return render_inlines(inline.children)
    if isinstance(inline, docir.Strikethrough):
        return _wrap_md("~~", render_inlines(inline.children))
    if isinstance(inline, docir.Link):
        return "[" + render_inlines(inline.children) + "](" + inline.url + ")"
    if isinstance(inline, docir.Code):
        return "`" + inline.value + "`"
    if isinstance(inline, docir.LineBreak):
        return "\n"
    return ""


def render_inlines_html(inlines: list[docir.Inline]) -> str:
    html = "".join(_render_inline_html(inline) for inline in _merge_adjacent_emphasis(inlines))
    # 글자모양 경계로 쪼개진 같은 강조를 잇는다: `<strong>무료</strong><strong>대여</strong>` → 하나
    return _ADJACENT_TAG_RE.sub("", html)


_ADJACENT_TAG_RE = re.compile(r"</(strong|em|del)><\1>")
_EDGE_RE = re.compile(r"^((?:\s|<br>)*)(.*?)((?:\s|<br>)*)$", re.DOTALL)


def _wrap_html(tag: str, inner: str) -> str:
    """앞뒤 공백·줄바꿈은 태그 밖으로 뺀다. 내용이 비면 태그를 만들지 않는다(빈 `****` 잔재 방지)."""
    lead, body, trail = _EDGE_RE.match(inner).groups()
    if not body:
        return lead + trail
    return f"{lead}<{tag}>{body}</{tag}>{trail}"


def _render_inline_html(inline: docir.Inline) -> str:
    if isinstance(inline, docir.Text):
        return _html_escape(inline.value, quote=False).replace("\r\n", "<br>").replace("\n", "<br>")
    if isinstance(inline, docir.Bold):
        return _wrap_html("strong", render_inlines_html(inline.children))
    if isinstance(inline, docir.Italic):
        return _wrap_html("em", render_inlines_html(inline.children))
    if isinstance(inline, docir.Underline):
        return render_inlines_html(inline.children)
    if isinstance(inline, docir.Strikethrough):
        return _wrap_html("del", render_inlines_html(inline.children))
    if isinstance(inline, docir.Link):
        return f'<a href="{_html_escape(inline.url)}">{render_inlines_html(inline.children)}</a>'
    if isinstance(inline, docir.Code):
        return "<code>" + _html_escape(inline.value, quote=False) + "</code>"
    if isinstance(inline, docir.LineBreak):
        return "<br>"
    return ""


def _strip_br_edges(value: str) -> str:
    lead, body, trail = _EDGE_RE.match(value).groups()
    return body


def _table_needs_html(table: docir.Table) -> bool:
    """병합 셀이나 셀 안 표가 있으면 HTML 표로 쓴다 — GFM 셀은 표를 담을 수 없다(#3)."""
    for row in table.rows:
        for cell in row.cells:
            if cell.col_span > 1 or cell.row_span > 1:
                return True
            if any(isinstance(child, docir.Table) for child in cell.children):
                return True
    return False


def _escape_pipe_cell(value: str) -> str:
    value = value.replace("\r\n", "<br>")
    value = value.replace("\n", "<br>")
    value = value.replace("|", r"\|")
    return value


def _row_to_gfm(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |\n"


def _split_after(value: str, sep: str) -> list[str]:
    if sep == "":
        return [value]
    parts: list[str] = []
    start = 0
    while True:
        index = value.find(sep, start)
        if index == -1:
            parts.append(value[start:])
            return parts
        end = index + len(sep)
        parts.append(value[start:end])
        start = end


def _sniff_ext(data: bytes) -> str | None:
    """실제 바이트로 이미지 형식을 판정한다(선언 format 보다 우선).

    HWPX 의 bindata 선언 확장자가 실제 페이로드와 다른 파일이 실재한다(실측:
    format="bmp" 인데 바이트는 PNG). 선언만 믿으면 Pillow 가 없을 때 **PNG 를
    .bmp 로 저장**한다 — Pillow 가 있으면 변환 과정에서 우연히 교정돼 있어
    의존성이 있는 환경에서는 드러나지 않는다.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    return None


def _mime_to_ext(format_name: str) -> str:
    lower = format_name.lower()
    if lower == "png":
        return "png"
    if lower in {"jpg", "jpeg"}:
        return "jpg"
    if lower == "bmp":
        return "bmp"
    if lower == "gif":
        return "gif"
    return "bin"


def _convert_bmp_to_png(data: bytes) -> bytes | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    from io import BytesIO

    try:
        with Image.open(BytesIO(data)) as image:
            out = BytesIO()
            image.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        return None
