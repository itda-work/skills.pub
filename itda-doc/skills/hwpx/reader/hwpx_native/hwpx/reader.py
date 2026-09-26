"""HWPX ZIP/XML reader ported from hyve's Go implementation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from .. import document as docir


_HEADING_STYLE_NAMES = {
    "제목 1": 1,
    "heading 1": 1,
    "heading1": 1,
    "제목 2": 2,
    "heading 2": 2,
    "heading2": 2,
    "제목 3": 3,
    "heading 3": 3,
    "heading3": 3,
    "제목 4": 4,
    "heading 4": 4,
    "heading4": 4,
    "제목 5": 5,
    "heading 5": 5,
    "heading5": 5,
    "제목 6": 6,
    "heading 6": 6,
    "heading6": 6,
    "개요 1": 1,
    "개요 2": 2,
    "개요 3": 3,
    "개요 4": 4,
    "개요 5": 5,
    "개요 6": 6,
    "개요 7": 6,
}

_HEADING_CONTAINS = (("큰제목", 1), ("중간제목", 2), ("작은제목", 3))


@dataclass(slots=True)
class _BinItem:
    id: str = ""
    href: str = ""
    media_type: str = ""
    data: bytes = b""


@dataclass(slots=True)
class _CharPr:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    font_name: str = ""
    font_size: float = 0.0
    color: str = ""

    def has_flags(self) -> bool:
        return self.bold or self.italic or self.underline or self.strikethrough


@dataclass(slots=True)
class _ParaProperty:
    alignment: str = ""  # header paraPr <align horizontal> — 셀 정렬(좌/우)이 역변환에 남아야 왕복 검증이 된다(#1652 D-6)
    line_spacing_percent: float = 0.0
    space_before_hwp: int = 0
    space_after_hwp: int = 0
    left_indent_hwp: int = 0
    right_indent_hwp: int = 0
    first_line_indent_hwp: int = 0


@dataclass(slots=True)
class _ResolvedParagraphProps:
    alignment: str = ""
    left_indent_mm: float = 0.0
    right_indent_mm: float = 0.0
    first_line_indent_mm: float = 0.0
    line_spacing_percent: float = 0.0
    space_before_mm: float = 0.0
    space_after_mm: float = 0.0


def read_hwpx_file(path: str | Path) -> docir.Document:
    with zipfile.ZipFile(path) as zf:
        return _parse_zip(zf)


def _parse_zip(zf: zipfile.ZipFile) -> docir.Document:
    names = set(zf.namelist())
    style_map, char_pr_map, para_properties_map = _parse_header(zf, names)
    bin_index = _parse_bin_index(zf, names)
    section_files = sorted(
        (name for name in names if _is_section_file(name)),
        key=_section_index,
    )
    if not section_files:
        raise ValueError("hwpx: no section files found in archive")

    document = docir.Document()
    for index, name in enumerate(section_files):
        root = ET.fromstring(zf.read(name))
        blocks = _section_to_blocks(
            root,
            style_map,
            char_pr_map,
            para_properties_map,
            bin_index,
        )
        document.sections.append(
            docir.Section(
                index=index,
                blocks=blocks,
                layout=_extract_page_layout(root),
                source=docir.SectionSource(reader="hwpx", id=name),
            )
        )
        document.blocks.extend(blocks)
    return document


def _parse_header(
    zf: zipfile.ZipFile,
    names: set[str],
) -> tuple[dict[str, int], dict[str, _CharPr], dict[str, _ParaProperty]]:
    style_map: dict[str, int] = {}
    char_pr_map: dict[str, _CharPr] = {}
    para_properties_map: dict[str, _ParaProperty] = {}
    if "Contents/header.xml" not in names:
        return style_map, char_pr_map, para_properties_map

    root = ET.fromstring(zf.read("Contents/header.xml"))
    style_containers = _children(root, "styles")
    if not style_containers:
        style_containers = _children(root, "styleList")
    for container in style_containers:
        for style in _children(container, "style"):
            style_id = style.attrib.get("id", "")
            name = unicodedata.normalize("NFC", style.attrib.get("name", ""))
            normalized = name.strip().lower()
            if normalized in _HEADING_STYLE_NAMES:
                style_map[style_id] = _HEADING_STYLE_NAMES[normalized]
                continue
            for keyword, level in _HEADING_CONTAINS:
                if keyword in normalized:
                    style_map[style_id] = level
                    break

    ref_list = _first_child(root, "refList")
    if ref_list is None:
        return style_map, char_pr_map, para_properties_map

    char_properties = _first_child(ref_list, "charProperties")
    if char_properties is not None:
        for char_pr in _children(char_properties, "charPr"):
            char_id = char_pr.attrib.get("id", "")
            char_pr_map[char_id] = _char_pr_def_to_char_pr(char_pr)

    para_properties = _first_child(ref_list, "paraProperties")
    if para_properties is not None:
        for para_pr in _children(para_properties, "paraPr"):
            para_id = para_pr.attrib.get("id", "0")
            para_properties_map[str(_to_int(para_id))] = _parse_para_property(para_pr)

    return style_map, char_pr_map, para_properties_map


def _parse_bin_index(zf: zipfile.ZipFile, names: set[str]) -> dict[str, _BinItem]:
    result: dict[str, _BinItem] = {}
    if "Contents/content.hpf" not in names:
        return result
    root = ET.fromstring(zf.read("Contents/content.hpf"))
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        href = item.attrib.get("href", "")
        if not href.startswith("BinData/"):
            continue
        item_id = item.attrib.get("id", "")
        data = zf.read(href) if href in names else b""
        result[item_id] = _BinItem(
            id=item_id,
            href=href,
            media_type=item.attrib.get("media-type", ""),
            data=data,
        )
    return result


def _section_to_blocks(
    root: ET.Element,
    style_map: dict[str, int],
    char_pr_map: dict[str, _CharPr],
    para_properties_map: dict[str, _ParaProperty],
    bin_index: dict[str, _BinItem],
) -> list[docir.Block]:
    blocks: list[docir.Block] = []
    for paragraph in _children(root, "p"):
        blocks.extend(
            _paragraph_to_blocks(
                paragraph,
                style_map,
                char_pr_map,
                para_properties_map,
                bin_index,
            )
        )
    return blocks


def _paragraph_to_blocks(
    paragraph: ET.Element,
    style_map: dict[str, int],
    char_pr_map: dict[str, _CharPr],
    para_properties_map: dict[str, _ParaProperty],
    bin_index: dict[str, _BinItem],
) -> list[docir.Block]:
    blocks: list[docir.Block] = []
    inlines: list[docir.Inline] = []
    props = _resolve_paragraph_props(paragraph, para_properties_map)

    for table in _children(paragraph, "tbl"):
        blocks.append(_table_to_block(table, style_map, char_pr_map, para_properties_map, bin_index))

    for run in _children(paragraph, "run"):
        text = _run_text(run)
        if text != "":
            char_pr = _inline_char_pr(run)
            char_pr_id_ref = run.attrib.get("charPrIDRef", "")
            if char_pr_id_ref and not char_pr.has_flags():
                char_pr = char_pr_map.get(char_pr_id_ref, char_pr)
            inline: docir.Inline = docir.Text(
                value=unicodedata.normalize("NFC", text),
                style=docir.TextStyle(
                    font_name=char_pr.font_name,
                    font_size=char_pr.font_size,
                    color=char_pr.color,
                )
                if (char_pr.font_name or char_pr.font_size or char_pr.color)
                else None,
            )
            hlink = _first_child(run, "hlink")
            if hlink is not None and hlink.attrib.get("href", ""):
                inline = docir.Link(url=hlink.attrib["href"], children=[inline])
            if char_pr.bold:
                inline = docir.Bold(children=[inline])
            if char_pr.italic:
                inline = docir.Italic(children=[inline])
            if char_pr.underline:
                inline = docir.Underline(children=[inline])
            if char_pr.strikethrough:
                inline = docir.Strikethrough(children=[inline])
            inlines.append(inline)

        for table in _children(run, "tbl"):
            if inlines:
                blocks.append(_new_paragraph_block(inlines, props))
                inlines = []
            blocks.append(_table_to_block(table, style_map, char_pr_map, para_properties_map, bin_index))

        for picture in _children(run, "pic"):
            image = _resolve_picture(picture, bin_index)
            if image is not None:
                if inlines:
                    blocks.append(_new_paragraph_block(inlines, props))
                    inlines = []
                blocks.append(image)

        for shape in _drawing_shapes(run):
            shape_blocks = _drawing_text_blocks(
                shape, style_map, char_pr_map, para_properties_map, bin_index
            )
            if shape_blocks:
                if inlines:
                    blocks.append(_new_paragraph_block(inlines, props))
                    inlines = []
                blocks.extend(shape_blocks)

    if not inlines:
        return blocks
    blocks.append(_build_text_block(paragraph, inlines, style_map, props))
    return blocks


# 글상자·도형 안 텍스트를 담는 그리기 개체 (#1651 R2).
# 정부 서식의 제목 박스(titleShape)는 <hp:rect><hp:drawText><hp:subList><hp:p> 구조라,
# run 직계 <t>·<tbl>·<pic> 만 보던 구 구현은 **문서 제목을 통째로 잃었다** — 우리
# 생성 엔진의 산출을 우리 리더가 못 읽어 "생성 후 읽기 교차검증" 이 제목 축에서 공허했다.
_DRAWING_SHAPE_NAMES = frozenset(
    {"rect", "ellipse", "arc", "polygon", "curve", "connectLine", "container", "textart"}
)


def _drawing_shapes(element: ET.Element) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) in _DRAWING_SHAPE_NAMES]


def _drawing_text_blocks(
    shape: ET.Element,
    style_map: dict[str, int],
    char_pr_map: dict[str, _CharPr],
    para_properties_map: dict[str, _ParaProperty],
    bin_index: dict[str, _BinItem],
) -> list[docir.Block]:
    """도형의 drawText 문단을 블록으로 변환한다. container 는 자식 도형을 재귀한다."""
    blocks: list[docir.Block] = []
    draw_text = _first_child(shape, "drawText")
    if draw_text is not None:
        sub_list = _first_child(draw_text, "subList")
        paragraphs = _children(sub_list, "p") if sub_list is not None else _children(draw_text, "p")
        for para in paragraphs:
            blocks.extend(
                _paragraph_to_blocks(para, style_map, char_pr_map, para_properties_map, bin_index)
            )
    for child in _drawing_shapes(shape):
        blocks.extend(_drawing_text_blocks(child, style_map, char_pr_map, para_properties_map, bin_index))
    return blocks


def _table_to_block(
    table: ET.Element,
    style_map: dict[str, int],
    char_pr_map: dict[str, _CharPr],
    para_properties_map: dict[str, _ParaProperty],
    bin_index: dict[str, _BinItem],
) -> docir.Table:
    table_rows = _children(table, "tr")
    rows: list[docir.TableRow] = []
    cell_padding_mm = 0.0

    if table_rows:
        for cell in _children(table_rows[0], "tc"):
            margin = _first_child(cell, "cellMargin")
            if margin is None:
                continue
            values = [
                _to_int(margin.attrib.get("left", "0")),
                _to_int(margin.attrib.get("right", "0")),
                _to_int(margin.attrib.get("top", "0")),
                _to_int(margin.attrib.get("bottom", "0")),
            ]
            min_value = min(values)
            if min_value > 0:
                cell_padding_mm = _hwp_unit_to_mm(min_value)
                break

    for row in table_rows:
        cells: list[docir.TableCell] = []
        for source_cell in _children(row, "tc"):
            width_mm = 0.0
            cell_sz = _first_child(source_cell, "cellSz")
            if cell_sz is not None:
                width = _to_int(cell_sz.attrib.get("width", "0"))
                if width > 0:
                    width_mm = _hwp_unit_to_mm(width)

            children: list[docir.Block] = []
            for para in _cell_paragraphs(source_cell):
                children.extend(
                    _paragraph_to_blocks(
                        para,
                        style_map,
                        char_pr_map,
                        para_properties_map,
                        bin_index,
                    )
                )

            cells.append(
                docir.TableCell(
                    col_span=_effective_col_span(source_cell),
                    row_span=_effective_row_span(source_cell),
                    width_mm=width_mm,
                    children=children,
                )
            )
        rows.append(docir.TableRow(cells=cells))
    return docir.Table(rows=rows, cell_padding_mm=cell_padding_mm)


def _resolve_picture(picture: ET.Element, bin_index: dict[str, _BinItem]) -> docir.Image | None:
    img = _first_child(picture, "img")
    if img is None:
        return None
    ref = img.attrib.get("binaryItemIDRef", "")
    if not ref:
        return None
    item = bin_index.get(ref)
    if item is None or not item.data:
        return None
    # 배치 크기(hp:sz/curSz — 본문 폭에 맞춘 축소 반영)가 있으면 그것을, 없으면 원본 치수(imgDim)를 쓴다(#1652 D7).
    img_dim = None
    for name in ("sz", "curSz", "imgDim"):  # Element 진리값(`or`)은 deprecated — 명시 None 검사
        img_dim = _first_child(picture, name)
        if img_dim is not None:
            break
    # imgDim 은 HWPUNIT(1/7200 inch). md <img width> 는 픽셀이라 96dpi 로 환산한다 (#1652 D-2 —
    # 구 구현은 단위를 그대로 실어 480px 이미지가 36000px 로 선언됐다). hwp5 리더의 hwp_unit_to_pixel 과 같은 식.
    width = _hwp_unit_to_px(_to_int(img_dim.attrib.get("width") or img_dim.attrib.get("dimwidth", "0"))) if img_dim is not None else 0
    height = _hwp_unit_to_px(_to_int(img_dim.attrib.get("height") or img_dim.attrib.get("dimheight", "0"))) if img_dim is not None else 0
    return docir.Image(
        data=item.data,
        format=_image_format(item),
        width=width,
        height=height,
        alt=ref,
    )


def _image_format(item: _BinItem) -> str:
    media_type = item.media_type.lower()
    if "png" in media_type:
        return "png"
    if "jpg" in media_type or "jpeg" in media_type:
        return "jpeg"
    if "gif" in media_type:
        return "gif"
    if "bmp" in media_type:
        return "bmp"
    if "." in item.href:
        return item.href.rsplit(".", 1)[1]
    return ""


def _resolve_paragraph_props(
    paragraph: ET.Element,
    para_properties_map: dict[str, _ParaProperty],
) -> _ResolvedParagraphProps:
    props = _ResolvedParagraphProps()
    para_pr_id_ref = paragraph.attrib.get("paraPrIDRef", "")
    if para_pr_id_ref and para_pr_id_ref in para_properties_map:
        resolved = para_properties_map[para_pr_id_ref]
        props.alignment = resolved.alignment
        props.left_indent_mm = _hwp_unit_to_mm(resolved.left_indent_hwp)
        props.right_indent_mm = _hwp_unit_to_mm(resolved.right_indent_hwp)
        props.first_line_indent_mm = _hwp_unit_to_mm(resolved.first_line_indent_hwp)
        props.line_spacing_percent = resolved.line_spacing_percent
        props.space_before_mm = _hwp_unit_to_mm(resolved.space_before_hwp)
        props.space_after_mm = _hwp_unit_to_mm(resolved.space_after_hwp)

    para_pr = _first_child(paragraph, "paraPr")
    if para_pr is not None:
        if para_pr.attrib.get("align", ""):
            props.alignment = para_pr.attrib["align"]
        inline = _parse_inline_para_pr(para_pr)
        for field in (
            "left_indent_mm",
            "right_indent_mm",
            "first_line_indent_mm",
            "line_spacing_percent",
            "space_before_mm",
            "space_after_mm",
        ):
            value = getattr(inline, field)
            if value != 0:
                setattr(props, field, value)
    return props


def _parse_para_property(para_pr: ET.Element) -> _ParaProperty:
    prop = _ParaProperty()
    align = _first_child(para_pr, "align")
    if align is not None:
        horizontal = align.attrib.get("horizontal", "").lower()
        if horizontal in ("left", "right", "center"):
            prop.alignment = horizontal
    margin = _resolve_para_margin(_first_child(para_pr, "margin"), _first_child(para_pr, "switch"))
    if margin is not None:
        prop.space_before_hwp = _para_value_or_zero(_first_child(margin, "prev"))
        prop.space_after_hwp = _para_value_or_zero(_first_child(margin, "next"))
        prop.left_indent_hwp = _para_value_or_zero(_first_child(margin, "left"))
        prop.right_indent_hwp = _para_value_or_zero(_first_child(margin, "right"))
        prop.first_line_indent_hwp = _para_value_or_zero(_first_child(margin, "intent"))
    line_spacing = _resolve_line_spacing(_first_child(para_pr, "lineSpacing"), _first_child(para_pr, "switch"))
    if line_spacing is not None and line_spacing.attrib.get("type", "").lower() == "percent":
        prop.line_spacing_percent = _to_float(line_spacing.attrib.get("value", "0"))
    return prop


def _parse_inline_para_pr(para_pr: ET.Element) -> _ResolvedParagraphProps:
    props = _ResolvedParagraphProps()
    margin = _resolve_para_margin(_first_child(para_pr, "margin"), _first_child(para_pr, "switch"))
    if margin is not None:
        props.left_indent_mm = _hwp_unit_to_mm(_para_value_or_zero(_first_child(margin, "left")))
        props.right_indent_mm = _hwp_unit_to_mm(_para_value_or_zero(_first_child(margin, "right")))
        props.first_line_indent_mm = _hwp_unit_to_mm(_para_value_or_zero(_first_child(margin, "intent")))
        props.space_before_mm = _hwp_unit_to_mm(_para_value_or_zero(_first_child(margin, "prev")))
        props.space_after_mm = _hwp_unit_to_mm(_para_value_or_zero(_first_child(margin, "next")))
    line_spacing = _resolve_line_spacing(_first_child(para_pr, "lineSpacing"), _first_child(para_pr, "switch"))
    if line_spacing is not None and line_spacing.attrib.get("type", "").lower() == "percent":
        props.line_spacing_percent = _to_float(line_spacing.attrib.get("value", "0"))
    return props


def _resolve_para_margin(direct: ET.Element | None, switch: ET.Element | None) -> ET.Element | None:
    if direct is not None:
        return direct
    shape = _switch_shape(switch)
    if shape is None:
        return None
    return _first_child(shape, "margin")


def _resolve_line_spacing(direct: ET.Element | None, switch: ET.Element | None) -> ET.Element | None:
    if direct is not None:
        return direct
    shape = _switch_shape(switch)
    if shape is None:
        return None
    return _first_child(shape, "lineSpacing")


def _switch_shape(switch: ET.Element | None) -> ET.Element | None:
    if switch is None:
        return None
    default = _first_child(switch, "default")
    if default is not None:
        return default
    return _first_child(switch, "case")


def _new_paragraph_block(inlines: list[docir.Inline], props: _ResolvedParagraphProps) -> docir.Paragraph:
    return docir.Paragraph(
        children=inlines,
        alignment=props.alignment,
        left_indent_mm=props.left_indent_mm,
        right_indent_mm=props.right_indent_mm,
        first_line_indent_mm=props.first_line_indent_mm,
        line_spacing_percent=props.line_spacing_percent,
        space_before_mm=props.space_before_mm,
        space_after_mm=props.space_after_mm,
    )


def _build_text_block(
    paragraph: ET.Element,
    inlines: list[docir.Inline],
    style_map: dict[str, int],
    props: _ResolvedParagraphProps,
) -> docir.Block:
    style_id = paragraph.attrib.get("styleIDRef", "") or paragraph.attrib.get("styleId", "")
    if style_id in style_map:
        return docir.Heading(level=style_map[style_id], children=inlines, alignment=props.alignment)
    return _new_paragraph_block(inlines, props)


def _char_pr_def_to_char_pr(char_pr: ET.Element) -> _CharPr:
    font_ref = _first_child(char_pr, "fontRef")
    underline = _first_child(char_pr, "underline")
    strikeout = _first_child(char_pr, "strikeout")
    result = _CharPr(
        bold=_first_child(char_pr, "bold") is not None,
        italic=_first_child(char_pr, "italic") is not None,
        underline=underline is not None
        and underline.attrib.get("type", "") != ""
        and underline.attrib.get("type", "") != "NONE",
        strikethrough=_is_active_strikeout(strikeout.attrib.get("shape", "") if strikeout is not None else ""),
    )
    if font_ref is not None and font_ref.attrib.get("face", ""):
        result.font_name = font_ref.attrib["face"]
    height = _to_int(char_pr.attrib.get("height", "0"))
    if height > 0:
        result.font_size = height / 100.0
    if char_pr.attrib.get("textColor", ""):
        result.color = char_pr.attrib["textColor"]
    return result


def _inline_char_pr(run: ET.Element) -> _CharPr:
    char_pr = _first_child(run, "charPr")
    if char_pr is None:
        return _CharPr()
    return _CharPr(
        bold=_to_bool(char_pr.attrib.get("bold", "")),
        italic=_to_bool(char_pr.attrib.get("italic", "")),
        underline=_to_bool(char_pr.attrib.get("underline", "")),
        strikethrough=_to_bool(char_pr.attrib.get("strikethrough", "")),
    )


def _extract_page_layout(root: ET.Element) -> docir.PageLayout:
    layout = docir.PageLayout()
    sec_pr = _first_child(root, "secPr")
    if sec_pr is None:
        return layout
    page_pr = _first_child(sec_pr, "pagePr")
    if page_pr is None:
        return layout
    width = _to_int(page_pr.attrib.get("width", "0"))
    height = _to_int(page_pr.attrib.get("height", "0"))
    if width > 0:
        layout.width_mm = _hwp_unit_to_mm(width)
    if height > 0:
        layout.height_mm = _hwp_unit_to_mm(height)
    layout.orientation = "landscape" if layout.width_mm > layout.height_mm else "portrait"
    margin = _first_child(page_pr, "margin")
    if margin is not None:
        for attr, field in (
            ("left", "margin_left_mm"),
            ("right", "margin_right_mm"),
            ("top", "margin_top_mm"),
            ("bottom", "margin_bottom_mm"),
        ):
            value = _to_int(margin.attrib.get(attr, "0"))
            if value > 0:
                setattr(layout, field, _hwp_unit_to_mm(value))
    space_columns = _to_int(sec_pr.attrib.get("spaceColumns", "0"))
    if space_columns > 0:
        layout.column_gap_mm = _hwp_unit_to_mm(space_columns)
    return layout


def _cell_paragraphs(cell: ET.Element) -> list[ET.Element]:
    sub_list = _first_child(cell, "subList")
    if sub_list is not None:
        paragraphs = _children(sub_list, "p")
        if paragraphs:
            return paragraphs
    return _children(cell, "p")


def _effective_col_span(cell: ET.Element) -> int:
    span = _first_child(cell, "cellSpan")
    if span is not None and _to_int(span.attrib.get("colSpan", "0")) > 0:
        return _to_int(span.attrib.get("colSpan", "0"))
    value = _to_int(cell.attrib.get("colSpan", "0"))
    return value if value > 0 else 1


def _effective_row_span(cell: ET.Element) -> int:
    span = _first_child(cell, "cellSpan")
    if span is not None and _to_int(span.attrib.get("rowSpan", "0")) > 0:
        return _to_int(span.attrib.get("rowSpan", "0"))
    value = _to_int(cell.attrib.get("rowSpan", "0"))
    return value if value > 0 else 1


def _run_text(run: ET.Element) -> str:
    """run 의 직계 <t> 를 **전부 이어붙인다** (#1536 ①).

    구 구현은 `text = ...` 로 덮어써 **마지막 <t> 만** 남겼다. 삭제된 Go 구현의
    `encoding/xml` 이 반복 필드를 마지막 값으로 덮어쓰던 동작을 그대로 옮긴 것인데,
    그건 이식할 계약이 아니라 **버그였다**.

    하이퍼링크·필드·각주 같은 제어 요소는 run 안에서 <t> 를 여러 조각으로 쪼갠다.
    그래서 그런 요소가 든 문단은 **앞부분 텍스트를 통째로 잃었다.** 실측(#1535):

        원문 <t> 3개 : '※ 건설산업지식정보 시스템('  'www.kiscon.net)'  ' 건설업체 정보조회 결과'
        구 산출      :                                                  ' 건설업체 정보조회 결과'

    <lineBreak/> 같은 중첩 제어 요소는 itertext() 가 주변 CharData 만 남기고 건너뛴다.
    """
    return "".join("".join(child.itertext()) for child in _children(run, "t"))


def _is_section_file(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return base.startswith("section") and base.endswith(".xml")


def _section_index(path: str) -> int:
    base = path.rsplit("/", 1)[-1]
    match = re.search(r"section(\d+)\.xml$", base)
    return int(match.group(1)) if match else 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local_name(child.tag) == name:
            return child
    return None


def _para_value_or_zero(element: ET.Element | None) -> int:
    if element is None:
        return 0
    return _to_int(element.attrib.get("value", "0"))


def _to_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes"}


def _hwp_unit_to_px(value: int) -> int:
    return int(round(value * 96 / 7200)) if value > 0 else 0


def _hwp_unit_to_mm(value: int) -> float:
    return value * 25.4 / 7200.0


def _is_active_strikeout(shape: str) -> bool:
    return shape not in {"", "NONE", "3D"}
