from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib import resources
import xml.etree.ElementTree as ET

from .models import ReportCell, ReportRun, ReportTable
from .profile import xml_escape

DEFAULT_REPORT_TABLE_TEMPLATE = "basic"
# 표 템플릿 이름은 단순 id — 슬래시·역슬래시·'.'/'..' 는 프로파일 루트 밖을 가리킨다(Codex R2 F7 · Claude R2 C-F7)
TABLE_TEMPLATE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class _TableStyle:
    border_fill_id_ref: str = ""
    char_pr_id_ref: str = ""
    para_pr_id_ref: str = ""


@dataclass
class _ReportTableTemplate:
    name: str
    width: int
    header_h: int
    body_h: int
    summary_h: int
    table_style: _TableStyle
    header: _TableStyle
    body: _TableStyle
    summary: _TableStyle


@dataclass
class _CellFormatCharRefs:
    plain: str
    bold: str
    italic: str
    bold_italic: str

    def ref(self, bold: bool, italic: bool) -> str:
        if bold and italic:
            return self.bold_italic
        if bold:
            return self.bold
        if italic:
            return self.italic
        return self.plain


def render_report_table(ctx: object, table: ReportTable, tmpl: object) -> str:
    table_tmpl = _load_report_table_template(tmpl, table.template)
    col_count = len(table.headers)
    row_count = len(table.rows) + 1
    widths = _resolve_report_table_widths(table_tmpl.width, col_count, table.col_widths)
    height = table_tmpl.header_h + len(table.rows) * table_tmpl.body_h

    body_aligns = _resolve_body_align_para_refs(table.aligns, col_count, tmpl, table_tmpl.body.para_pr_id_ref)
    fmt_refs = _resolve_cell_format_char_refs(tmpl, table_tmpl.body.char_pr_id_ref)
    parts = [
        f'<hp:p id="{ctx.paragraph_id()}" paraPrIDRef="2" styleIDRef="0" pageBreak="0" '
        f'columnBreak="0" merged="0"><hp:run charPrIDRef="{xml_escape(table_tmpl.body.char_pr_id_ref)}">'
        f'<hp:tbl id="{ctx.table_id()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" '
        f'borderFillIDRef="{xml_escape(table_tmpl.table_style.border_fill_id_ref)}" noAdjust="1">'
        f'<hp:sz width="{table_tmpl.width}" widthRelTo="ABSOLUTE" height="{height}" '
        'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" '
        'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="141" right="141" top="141" bottom="141"/>'
        '<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
    ]
    parts.append(_append_report_table_row(ctx, table.headers, None, 0, widths, table_tmpl.header_h, table_tmpl.header, [], fmt_refs))
    for index, row in enumerate(table.rows):
        rich_row = table.rich_rows[index] if index < len(table.rich_rows) else None
        parts.append(
            _append_report_table_row(ctx, row, rich_row, index + 1, widths, table_tmpl.body_h, table_tmpl.body, body_aligns, fmt_refs)
        )
    parts.append("</hp:tbl><hp:t/></hp:run></hp:p>")
    return "".join(parts)


def _load_report_table_template(tmpl: object, table_template: str) -> _ReportTableTemplate:
    name = table_template.strip() or DEFAULT_REPORT_TABLE_TEMPLATE
    try:
        return _read_report_table_template(tmpl, name)
    except FileNotFoundError:
        if name == DEFAULT_REPORT_TABLE_TEMPLATE:
            raise
        # 조용한 폴백 금지 — 요청한 표 템플릿이 없다는 사실을 말한다(Claude R2 C-F7)
        print(
            f"경고: 표 템플릿 {name!r} 이(가) 없어 {DEFAULT_REPORT_TABLE_TEMPLATE!r} 로 대체합니다"
            f" (템플릿 {getattr(tmpl, 'id', '')})",
            file=sys.stderr,
        )
        return _read_report_table_template(tmpl, DEFAULT_REPORT_TABLE_TEMPLATE)


def _read_report_table_template(tmpl: object, name: str) -> _ReportTableTemplate:
    """표 템플릿은 템플릿 객체의 리소스 루트(내장 assets 또는 --template-dir 디렉토리)에서 읽는다."""
    template_id = str(getattr(tmpl, "id", ""))
    # 표 템플릿 이름은 단순 id 다 — 슬래시·역슬래시·'.'/'..' 는 프로파일 루트 밖을 가리킨다(Codex R2 F7).
    # 여기서 걸러야 아래 FileNotFoundError 폴백이 경로 이탈을 기본 템플릿으로 조용히 덮지 않는다.
    if not TABLE_TEMPLATE_NAME_RE.match(name):
        raise ValueError(f"hwpx report: invalid table template name {name!r} in template {template_id}")
    rel = f"tables/{name}.xml"
    reader = getattr(tmpl, "read_resource", None)
    try:
        if reader is not None:
            data = reader(rel)
        else:  # 리소스 루트가 없는 객체(테스트 더블) — 종전 내장 경로
            data = resources.files("hwpx_report").joinpath("assets", f"templates/{template_id}/{rel}").read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"hwpx report: load table template {template_id}/{name}: {exc}"
        ) from exc
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"hwpx report: parse table template {template_id}/{name}: {exc}") from exc
    meta = _child(root, "meta")
    if meta is None:
        raise ValueError(f"hwpx report: parse table template {template_id}/{name}: missing meta")

    row_height = _child(meta, "row-height")
    styles = _child(meta, "styles")
    table_tmpl = _ReportTableTemplate(
        name=_child_text(meta, "name") or name,
        width=_child_int(meta, "table-width"),
        header_h=_attr_int(row_height, "header") if row_height is not None else 0,
        body_h=_attr_int(row_height, "body") if row_height is not None else 0,
        summary_h=_attr_int(row_height, "summary") if row_height is not None else 0,
        table_style=_style_from_child(styles, "table-border"),
        header=_style_from_child(styles, "header-cell"),
        body=_style_from_child(styles, "body-cell"),
        summary=_style_from_child(styles, "summary-cell"),
    )
    if table_tmpl.width <= 0:
        table_tmpl.width = 47849
    if table_tmpl.header_h <= 0:
        table_tmpl.header_h = 2363
    if table_tmpl.body_h <= 0:
        table_tmpl.body_h = 1984
    if table_tmpl.summary_h <= 0:
        table_tmpl.summary_h = table_tmpl.body_h
    if not table_tmpl.table_style.border_fill_id_ref:
        table_tmpl.table_style.border_fill_id_ref = "4"
    if not table_tmpl.header.border_fill_id_ref:
        table_tmpl.header.border_fill_id_ref = "9"
    if not table_tmpl.header.char_pr_id_ref:
        table_tmpl.header.char_pr_id_ref = "26"
    if not table_tmpl.header.para_pr_id_ref:
        table_tmpl.header.para_pr_id_ref = "18"
    if not table_tmpl.body.border_fill_id_ref:
        table_tmpl.body.border_fill_id_ref = "10"
    if not table_tmpl.body.char_pr_id_ref:
        table_tmpl.body.char_pr_id_ref = "27"
    if not table_tmpl.body.para_pr_id_ref:
        table_tmpl.body.para_pr_id_ref = "18"
    return table_tmpl


def _append_report_table_row(
    ctx: object,
    cells: list[str],
    rich_cells: list[ReportCell] | None,
    row_addr: int,
    widths: list[int],
    row_height: int,
    style: _TableStyle,
    para_overrides: list[str],
    fmt_refs: _CellFormatCharRefs,
) -> str:
    parts = ["<hp:tr>"]
    for col_addr, text in enumerate(cells):
        para_pr_id_ref = style.para_pr_id_ref
        if col_addr < len(para_overrides) and para_overrides[col_addr]:
            para_pr_id_ref = para_overrides[col_addr]
        runs: list[ReportRun] = []
        if rich_cells is not None and col_addr < len(rich_cells) and rich_cells[col_addr].runs:
            runs = rich_cells[col_addr].runs
        parts.append(
            _append_report_table_cell(
                ctx,
                text,
                runs,
                fmt_refs,
                col_addr,
                row_addr,
                widths[col_addr],
                row_height,
                style,
                para_pr_id_ref,
            )
        )
    parts.append("</hp:tr>")
    return "".join(parts)


def _append_report_table_cell(
    ctx: object,
    text: str,
    runs: list[ReportRun],
    fmt_refs: _CellFormatCharRefs,
    col_addr: int,
    row_addr: int,
    width: int,
    height: int,
    style: _TableStyle,
    para_pr_id_ref: str,
) -> str:
    parts = [
        f'<hp:tc name="" header="0" hasMargin="1" protect="0" editable="0" dirty="0" '
        f'borderFillIDRef="{xml_escape(style.border_fill_id_ref)}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
        'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{ctx.paragraph_id()}" paraPrIDRef="{xml_escape(para_pr_id_ref)}" '
        'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
    ]
    if runs:
        for run in runs:
            parts.append(f'<hp:run charPrIDRef="{xml_escape(fmt_refs.ref(run.bold, run.italic))}">')
            if run.text == "":
                parts.append("<hp:t/>")
            else:
                parts.append(f"<hp:t>{xml_escape(run.text)}</hp:t>")
            parts.append("</hp:run>")
    else:
        parts.append(f'<hp:run charPrIDRef="{xml_escape(style.char_pr_id_ref)}">')
        if text == "":
            parts.append("<hp:t/>")
        else:
            parts.append(f"<hp:t>{xml_escape(text)}</hp:t>")
        parts.append("</hp:run>")
    parts.append(
        f'</hp:p></hp:subList><hp:cellAddr colAddr="{col_addr}" rowAddr="{row_addr}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/><hp:cellSz width="{width}" height="{height}"/>'
        '<hp:cellMargin left="73" right="73" top="73" bottom="141"/></hp:tc>'
    )
    return "".join(parts)


def _resolve_report_table_widths(total: int, cols: int, weights: list[int]) -> list[int]:
    if len(weights) != cols:
        return _distribute_report_table_widths(total, cols)
    total_weight = 0
    for weight in weights:
        if weight <= 0:
            return _distribute_report_table_widths(total, cols)
        total_weight += weight
    if total_weight <= 0:
        return _distribute_report_table_widths(total, cols)
    widths: list[int] = []
    acc = 0
    for weight in weights:
        width = total * weight // total_weight
        widths.append(width)
        acc += width
    widths[-1] += total - acc
    return widths


def _distribute_report_table_widths(total: int, cols: int) -> list[int]:
    base = total // cols
    widths = [base] * cols
    widths[-1] += total - base * cols
    return widths


def _resolve_body_align_para_refs(aligns: list[str], col_count: int, tmpl: object, body_default: str) -> list[str]:
    if not aligns:
        return []
    left = _table_align_para_ref(tmpl, "table_body_left")
    right = _table_align_para_ref(tmpl, "table_body_right")
    center = _table_align_para_ref(tmpl, "table_body") or body_default
    refs: list[str] = []
    for index in range(col_count):
        token = aligns[index].strip().lower() if index < len(aligns) else ""
        ref = body_default
        if token == "left" and left:
            ref = left
        elif token == "right" and right:
            ref = right
        elif token == "center":
            ref = center
        refs.append(ref)
    return refs


def _table_align_para_ref(tmpl: object, name: str) -> str:
    style = getattr(tmpl, "styles", {}).get(name)
    return getattr(style, "paraPrIDRef", "") if style is not None else ""


def _table_style_char_ref(tmpl: object, name: str) -> str:
    style = getattr(tmpl, "styles", {}).get(name)
    return getattr(style, "charPrIDRef", "") if style is not None else ""


def _resolve_cell_format_char_refs(tmpl: object, body_default: str) -> _CellFormatCharRefs:
    refs = _CellFormatCharRefs(body_default, body_default, body_default, body_default)
    refs.bold = _table_style_char_ref(tmpl, "table_body_bold") or refs.bold
    refs.italic = _table_style_char_ref(tmpl, "table_body_italic") or refs.italic
    refs.bold_italic = _table_style_char_ref(tmpl, "table_body_bold_italic") or refs.bold_italic
    return refs


def _style_from_child(parent: ET.Element | None, name: str) -> _TableStyle:
    el = _child(parent, name) if parent is not None else None
    if el is None:
        return _TableStyle()
    return _TableStyle(
        border_fill_id_ref=el.attrib.get("borderFillIDRef", ""),
        char_pr_id_ref=el.attrib.get("charPrIDRef", ""),
        para_pr_id_ref=el.attrib.get("paraPrIDRef", ""),
    )


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in parent:
        if _local_name(child.tag) == name:
            return child
    return None


def _child_text(parent: ET.Element, name: str) -> str:
    child = _child(parent, name)
    return (child.text or "").strip() if child is not None else ""


def _child_int(parent: ET.Element, name: str) -> int:
    text = _child_text(parent, name)
    try:
        return int(text)
    except ValueError:
        return 0


def _attr_int(el: ET.Element, name: str) -> int:
    try:
        return int(el.attrib.get(name, ""))
    except ValueError:
        return 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
