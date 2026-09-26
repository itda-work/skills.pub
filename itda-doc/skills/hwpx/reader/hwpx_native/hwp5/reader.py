"""HWP5/OLE reader ported from hyve's deleted Go implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import struct
import zlib

from .. import document as docir

try:
    import olefile
except ImportError:  # pragma: no cover - exercised only without requirements installed
    olefile = None


HWPTAG_BEGIN = 0x10
HWPTAG_ID_MAPPINGS = HWPTAG_BEGIN + 1
HWPTAG_BIN_DATA = HWPTAG_BEGIN + 2
HWPTAG_FACE_NAME = HWPTAG_BEGIN + 3
HWPTAG_CHAR_SHAPE = HWPTAG_BEGIN + 5
HWPTAG_PARA_SHAPE = HWPTAG_BEGIN + 9
HWPTAG_STYLE = HWPTAG_BEGIN + 10

HWPTAG_PARA_HEADER = HWPTAG_BEGIN + 50
HWPTAG_PARA_TEXT = HWPTAG_BEGIN + 51
HWPTAG_PARA_CHAR_SHAPE = HWPTAG_BEGIN + 52
HWPTAG_CTRL_HEADER = HWPTAG_BEGIN + 55
HWPTAG_LIST_HEADER = HWPTAG_BEGIN + 56
HWPTAG_PAGE_DEF = HWPTAG_BEGIN + 57
HWPTAG_SHAPE_COMPONENT = HWPTAG_BEGIN + 60
HWPTAG_TABLE = HWPTAG_BEGIN + 61
HWPTAG_SHAPE_COMPONENT_PICTURE = HWPTAG_BEGIN + 69

CTRL_TYPE_GSO = 0x67736F20
HWPU_TO_MM = 25.4 / 7200.0

# HWP5 FileHeader 플래그 (한/글 문서 파일 형식 5.0)
HWP5_FLAG_COMPRESSED = 0x01
HWP5_FLAG_ENCRYPTED = 0x02
HWP5_FLAG_DISTRIBUTION = 0x04


def check_readable_flags(flags: int) -> None:
    """본문을 읽을 수 없는 문서를 **명시 에러**로 거른다 (#1536 ③).

    ⚠️ 배포용 보호(0x04)를 빠뜨리면 조용히 빈 문서가 나온다. 그런 문서는 본문이
    `BodyText` 가 아니라 **`ViewText` 에 암호화**되어 있어, `BodyText` 만 읽으면
    문단 0개 → 3바이트 산출 + 종료코드 0 이 된다. 호출자가 길이를 재지 않으면
    "변환 성공" 으로 집계되며, 이 클래스는 **호출자 쪽에서 구조적으로 못 잡는다**.

    Raises:
        ValueError: 암호화 또는 배포용 보호가 걸린 문서일 때
    """
    if flags & HWP5_FLAG_ENCRYPTED:
        raise ValueError("hwp: encrypted HWP5 file (flags & 0x02)")
    if flags & HWP5_FLAG_DISTRIBUTION:
        raise ValueError(
            "hwp: distribution-protected HWP5 file (flags & 0x04) — "
            "body text is stored encrypted in ViewText, not BodyText; "
            "extracting it would silently produce an empty document"
        )


@dataclass(slots=True)
class Record:
    tag_id: int
    level: int
    size: int
    data: bytes
    children: list["Record"] = field(default_factory=list)


@dataclass(slots=True)
class FileHeader:
    signature: bytes
    version: int
    flags: int


@dataclass(slots=True)
class FaceName:
    name: str


@dataclass(slots=True)
class CharShape:
    face_id: list[int] = field(default_factory=lambda: [0] * 7)
    font_size: int = 0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    text_color: int = 0


@dataclass(slots=True)
class ParaShape:
    alignment: int = 0
    line_spacing_type: int = 0
    left_margin: int = 0
    right_margin: int = 0
    indent: int = 0
    line_spacing: int = 0
    space_before: int = 0
    space_after: int = 0


@dataclass(slots=True)
class Style:
    name: str = ""
    english_name: str = ""
    para_shape_id: int = 0
    char_shape_id: int = 0
    style_type: int = 0
    next_style_id: int = 0


@dataclass(slots=True)
class BinDataRef:
    type: int = 0
    compressed: int = 0
    status: int = 0
    abs_path: str = ""
    rel_path: str = ""
    bin_data_id: int = 0
    extension: str = ""


@dataclass(slots=True)
class DocInfoTables:
    face_names: list[FaceName] = field(default_factory=list)
    char_shapes: list[CharShape] = field(default_factory=list)
    para_shapes: list[ParaShape] = field(default_factory=list)
    styles: list[Style] = field(default_factory=list)
    bin_data_refs: list[BinDataRef] = field(default_factory=list)


@dataclass(slots=True)
class ParaHeader:
    text_char_count: int = 0
    control_mask: int = 0
    para_shape_id: int = 0
    style_id: int = 0
    char_shape_count: int = 0


@dataclass(slots=True)
class CharShapeMapping:
    position: int
    char_shape_id: int


@dataclass(slots=True)
class TextSpan:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    font_name: str = ""
    font_size: int = 0
    text_color: int = 0
    char_shape_id: int = 0


@dataclass(slots=True)
class FormattedParagraph:
    header: ParaHeader = field(default_factory=ParaHeader)
    text: str = ""
    spans: list[TextSpan] = field(default_factory=list)
    style_id: int = 0
    heading_level: int = 0
    alignment: str = ""
    left_indent_mm: float = 0.0
    right_indent_mm: float = 0.0
    first_line_indent_mm: float = 0.0
    line_spacing_percent: float = 0.0
    space_before_mm: float = 0.0
    space_after_mm: float = 0.0


@dataclass(slots=True)
class CellDef:
    row: int = 0
    col: int = 0
    row_span: int = 1
    col_span: int = 1
    width: int = 0
    height: int = 0
    paragraphs: list[FormattedParagraph] = field(default_factory=list)


@dataclass(slots=True)
class ParsedTableRow:
    cells: list[CellDef] = field(default_factory=list)


@dataclass(slots=True)
class ParsedTable:
    row_count: int = 0
    col_count: int = 0
    rows: list[ParsedTableRow] = field(default_factory=list)
    cell_margin_mm: float = 0.0


@dataclass(slots=True)
class ShapeComponent:
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class ImageData:
    data: bytes = b""
    mime_type: str = ""
    width: int = 0
    height: int = 0
    cur_width: int = 0
    cur_height: int = 0
    bin_data_id: int = 0
    file_name: str = ""


class HWP5File:
    def __init__(self, data: bytes) -> None:
        if olefile is None:
            raise RuntimeError("olefile is required for HWP5 parsing")
        self.ole = olefile.OleFileIO(BytesIO(data))
        self.file_header = self._parse_file_header()
        if not self.file_header.signature.startswith(b"HWP Document File"):
            raise ValueError("not a valid HWP5 file")
        check_readable_flags(self.file_header.flags)
        self.doc_info_tables: DocInfoTables | None = None
        self.body_text_sections: list[bytes] = []
        self._parse_doc_info()
        self._parse_body_text()

    def _open_stream(self, path: str | list[str]) -> bytes:
        return self.ole.openstream(path).read()

    def _stream_exists(self, path: str | list[str]) -> bool:
        return bool(self.ole.exists(path))

    def _parse_file_header(self) -> FileHeader:
        data = self._open_stream("FileHeader")
        if len(data) < 256:
            raise ValueError("FileHeader too small")
        version, flags = struct.unpack_from("<II", data, 32)
        return FileHeader(signature=data[:32], version=version, flags=flags)

    def _parse_doc_info(self) -> None:
        if not self._stream_exists("DocInfo"):
            return
        data = self._open_stream("DocInfo")
        if self.is_compressed:
            data = self.decompress(data)
        try:
            self.doc_info_tables = parse_doc_info_stream(data)
        except Exception:
            self.doc_info_tables = None

    def _parse_body_text(self) -> None:
        paths = self.ole.listdir(streams=True, storages=False)
        section_names = [
            parts[-1]
            for parts in paths
            if len(parts) >= 2 and parts[-2] == "BodyText" and parts[-1].startswith("Section")
        ]
        section_names.sort(key=_section_number)
        for name in section_names:
            data = self._open_stream(["BodyText", name])
            if self.is_compressed:
                try:
                    data = self.decompress(data)
                except Exception:
                    continue
            self.body_text_sections.append(data)
        if not self.body_text_sections:
            raise ValueError("no BodyText sections found")

    @property
    def is_compressed(self) -> bool:
        return bool(self.file_header.flags & 0x01)

    def decompress(self, data: bytes) -> bytes:
        try:
            return zlib.decompress(data, -15)
        except zlib.error:
            return zlib.decompress(data)

    def resolve_bin_data(
        self,
        bin_data_id: int,
        cur_width: int,
        cur_height: int,
        shape: ShapeComponent | None,
        tables: DocInfoTables,
    ) -> ImageData | None:
        index = bin_data_id - 1
        if index < 0 or index >= len(tables.bin_data_refs):
            return None
        ref = tables.bin_data_refs[index]
        image = ImageData(bin_data_id=bin_data_id)
        if shape is not None:
            image.width = shape.width
            image.height = shape.height
        image.cur_width = cur_width
        image.cur_height = cur_height

        if ref.type == 0:
            image.file_name = ref.abs_path
            image.mime_type = "application/octet-stream"
            return image

        if ref.type not in {1, 2}:
            return image

        base_name = f"BIN{bin_data_id:04X}"
        stream_name = base_name + (f".{ref.extension}" if ref.extension else "")
        stream_data = b""
        for path in (["BinData", stream_name], ["BinData", base_name], stream_name, base_name):
            try:
                if self._stream_exists(path):
                    stream_data = self._open_stream(path)
                    if stream_data:
                        break
            except Exception:
                continue
        if not stream_data:
            return None

        extracted = stream_data
        should_decompress = ref.compressed == 1 or (ref.compressed == 0 and self.is_compressed)
        if should_decompress:
            try:
                extracted = self.decompress(stream_data)
            except Exception:
                extracted = stream_data

        image.data = extracted
        image.mime_type = detect_mime_type(extracted)
        image.file_name = stream_name
        return image


def read_hwp5_file(path: str | Path) -> docir.Document:
    return parse_hwp5_to_document(Path(path).read_bytes())


def parse_hwp5_to_document(data: bytes) -> docir.Document:
    if len(data) < 8 or data[:8] != b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        raise ValueError("invalid HWP file format")
    hwp5 = HWP5File(data)
    return convert_hwp5_to_formatted_ir(hwp5)


def convert_hwp5_to_formatted_ir(hwp5: HWP5File) -> docir.Document:
    document = docir.Document()
    for section_index, section in enumerate(hwp5.body_text_sections):
        records = parse_records(section)
        tree = build_record_tree(records)
        layout = find_page_def_layout(records)
        blocks = convert_sections_to_blocks(tree, hwp5)
        document.sections.append(
            docir.Section(
                index=section_index,
                blocks=blocks,
                layout=layout,
                source=docir.SectionSource(reader="hwp", id=f"Section{section_index}"),
            )
        )
        document.blocks.extend(blocks)
    apply_heuristic_headings_from_sections(document)
    return document


def parse_records(data: bytes) -> list[Record]:
    records: list[Record] = []
    offset = 0
    length = len(data)
    while offset < length:
        if offset + 4 > length:
            break
        header = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        tag_id = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > length:
                break
            size = struct.unpack_from("<I", data, offset)[0]
            offset += 4
        payload = data[offset : offset + size]
        if len(payload) < size:
            break
        offset += size
        records.append(Record(tag_id=tag_id, level=level, size=size, data=payload))
    return records


def build_record_tree(records: list[Record]) -> list[Record]:
    roots: list[Record] = []
    stack: list[Record] = []
    for record in records:
        level = record.level
        if level < len(stack):
            stack = stack[:level]
        if level == 0:
            roots.append(record)
        elif level <= len(stack):
            stack[level - 1].children.append(record)
        else:
            roots.append(record)
        if level < len(stack):
            stack[level] = record
        else:
            stack.append(record)
    return roots


def parse_doc_info_stream(data: bytes) -> DocInfoTables:
    tables = DocInfoTables()
    for record in parse_records(data):
        if record.tag_id == HWPTAG_FACE_NAME:
            tables.face_names.append(parse_face_name(record.data))
        elif record.tag_id == HWPTAG_CHAR_SHAPE:
            tables.char_shapes.append(parse_char_shape(record.data))
        elif record.tag_id == HWPTAG_PARA_SHAPE:
            tables.para_shapes.append(parse_para_shape(record.data))
        elif record.tag_id == HWPTAG_STYLE:
            tables.styles.append(parse_style(record.data))
        elif record.tag_id == HWPTAG_BIN_DATA:
            tables.bin_data_refs.append(parse_bin_data_ref(record.data))
    return tables


def parse_face_name(data: bytes) -> FaceName:
    if len(data) < 3:
        return FaceName("")
    name_len = struct.unpack_from("<H", data, 1)[0]
    return FaceName(read_utf16le(data, 3, name_len))


def parse_char_shape(data: bytes) -> CharShape:
    if len(data) < 50:
        return CharShape()
    face_id = list(struct.unpack_from("<7H", data, 0))
    font_size = struct.unpack_from("<I", data, 42)[0]
    props = struct.unpack_from("<I", data, 46)[0]
    text_color = struct.unpack_from("<I", data, 52)[0] if len(data) >= 56 else 0
    return CharShape(
        face_id=face_id,
        font_size=font_size,
        italic=bool(props & 0x01),
        bold=bool(props & 0x02),
        underline=bool((props >> 2) & 0x03),
        strikethrough=bool((props >> 18) & 0x07),
        text_color=text_color,
    )


def parse_para_shape(data: bytes) -> ParaShape:
    if len(data) < 28:
        return ParaShape()
    props = struct.unpack_from("<I", data, 0)[0]
    fields = struct.unpack_from("<6i", data, 4)
    return ParaShape(
        alignment=props & 0x03,
        line_spacing_type=(props >> 2) & 0x07,
        left_margin=fields[0],
        right_margin=fields[1],
        indent=fields[2],
        line_spacing=fields[3],
        space_before=fields[4],
        space_after=fields[5],
    )


def parse_style(data: bytes) -> Style:
    offset = 0
    if len(data) < 2:
        return Style()
    local_len = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    name = read_utf16le(data, offset, local_len)
    offset += local_len * 2
    if offset + 2 > len(data):
        return Style(name=name)
    english_len = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    english_name = read_utf16le(data, offset, english_len)
    offset += english_len * 2
    style = Style(name=name, english_name=english_name)
    if offset < len(data):
        style.style_type = data[offset]
        offset += 1
    if offset < len(data):
        style.next_style_id = data[offset]
        offset += 1
    offset += 2
    if offset + 4 <= len(data):
        style.para_shape_id, style.char_shape_id = struct.unpack_from("<HH", data, offset)
    return style


def parse_bin_data_ref(data: bytes) -> BinDataRef:
    if len(data) < 2:
        return BinDataRef()
    offset = 0
    attr_word = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    ref = BinDataRef(
        type=attr_word & 0x000F,
        compressed=(attr_word >> 4) & 0x03,
        status=(attr_word >> 8) & 0x03,
    )
    if ref.type == 0 and offset + 2 <= len(data):
        abs_len = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        ref.abs_path = read_utf16le(data, offset, abs_len)
        offset += abs_len * 2
        if offset + 2 <= len(data):
            rel_len = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            ref.rel_path = read_utf16le(data, offset, rel_len)
    elif ref.type == 1 and offset + 4 <= len(data):
        ref.bin_data_id = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        ext_len = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        ref.extension = read_utf16le(data, offset, ext_len)
    elif ref.type == 2 and offset + 2 <= len(data):
        ref.bin_data_id = struct.unpack_from("<H", data, offset)[0]
    return ref


def convert_sections_to_blocks(tree: list[Record], hwp5: HWP5File) -> list[docir.Block]:
    blocks: list[docir.Block] = []
    doc_info = hwp5.doc_info_tables
    for root in tree:
        if root.tag_id == HWPTAG_PARA_HEADER:
            paragraph = extract_formatted_paragraph_from_record(root, doc_info)
            blocks.append(convert_formatted_paragraph(paragraph))
            for child in root.children:
                if child.tag_id == HWPTAG_CTRL_HEADER:
                    blocks.extend(convert_ctrl_record(child, doc_info, hwp5))
        elif root.tag_id == HWPTAG_CTRL_HEADER:
            blocks.extend(convert_ctrl_record(root, doc_info, hwp5))
    return blocks


def convert_ctrl_record(
    record: Record,
    doc_info: DocInfoTables | None,
    hwp5: HWP5File,
) -> list[docir.Block]:
    type_name = parse_ctrl_type_name(record.data)
    if type_name == "tbl ":
        table = parse_table_from_record(record, doc_info)
        if table is None:
            return []
        blocks: list[docir.Block] = [convert_parsed_table(table)]
        blocks.extend(extract_nested_images(record, doc_info, hwp5))
        return blocks
    if type_name == "gso ":
        return [convert_image_data(image) for image in extract_images_from_tree([record], doc_info, hwp5)]
    return []


def extract_nested_images(
    record: Record,
    doc_info: DocInfoTables | None,
    hwp5: HWP5File,
) -> list[docir.Block]:
    blocks: list[docir.Block] = []
    for child in record.children:
        if child.tag_id == HWPTAG_CTRL_HEADER and parse_ctrl_type_name(child.data) == "gso ":
            blocks.extend(convert_image_data(image) for image in extract_images_from_tree([child], doc_info, hwp5))
        blocks.extend(extract_nested_images(child, doc_info, hwp5))
    return blocks


def extract_formatted_paragraph_from_record(
    root: Record,
    doc_info: DocInfoTables | None,
) -> FormattedParagraph:
    header = parse_para_header(root.data)
    para_raw_data = b""
    mappings: list[CharShapeMapping] = []
    for child in root.children:
        if child.tag_id == HWPTAG_PARA_TEXT:
            para_raw_data = child.data
        elif child.tag_id == HWPTAG_PARA_CHAR_SHAPE:
            mappings = parse_para_char_shape(child.data)
    para_text = parse_para_text(para_raw_data)
    spans = build_formatted_spans_from_raw(para_raw_data, mappings, doc_info)
    fp = FormattedParagraph(
        header=header,
        text=para_text,
        spans=spans,
        style_id=header.style_id,
    )
    if doc_info is not None and header.style_id < len(doc_info.styles):
        fp.heading_level = detect_heading_level(doc_info.styles[header.style_id].name)
    if doc_info is not None and header.para_shape_id < len(doc_info.para_shapes):
        para_shape = doc_info.para_shapes[header.para_shape_id]
        fp.alignment = alignment_to_string(para_shape.alignment)
        fp.left_indent_mm = para_shape.left_margin * HWPU_TO_MM
        fp.right_indent_mm = para_shape.right_margin * HWPU_TO_MM
        fp.first_line_indent_mm = para_shape.indent * HWPU_TO_MM
        fp.space_before_mm = para_shape.space_before * HWPU_TO_MM
        fp.space_after_mm = para_shape.space_after * HWPU_TO_MM
        if para_shape.line_spacing_type in {0, 2}:
            fp.line_spacing_percent = float(para_shape.line_spacing)
    return fp


def parse_para_header(data: bytes) -> ParaHeader:
    if len(data) < 11:
        return ParaHeader()
    text_char_count, control_mask, para_shape_id, style_id = struct.unpack_from("<IIHB", data, 0)
    char_shape_count = struct.unpack_from("<H", data, 12)[0] if len(data) >= 14 else 0
    return ParaHeader(
        text_char_count=text_char_count,
        control_mask=control_mask,
        para_shape_id=para_shape_id,
        style_id=style_id,
        char_shape_count=char_shape_count,
    )


def parse_para_text(data: bytes) -> str:
    text, _ = parse_para_text_with_positions(data)
    return text


def parse_para_text_with_positions(data: bytes) -> tuple[str, dict[int, int]]:
    chars: list[str] = []
    pos_map: dict[int, int] = {}
    offset = 0
    wchar_index = 0
    rune_index = 0
    while offset + 2 <= len(data):
        ch = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        if ch == 0x00:
            wchar_index += 1
        elif ch in {0x09, 0x0A, 0x0D}:
            pos_map[wchar_index] = rune_index
            chars.append("\t" if ch == 0x09 else "\n")
            wchar_index += 1
            rune_index += 1
        elif 0x01 <= ch <= 0x08 or ch in {0x0B, 0x0C, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x15, 0x16, 0x17}:
            offset += 14
            wchar_index += 8
        elif 0x13 <= ch <= 0x1F:
            wchar_index += 1
        else:
            pos_map[wchar_index] = rune_index
            chars.append(_rune_from_utf16_code_unit(ch))
            wchar_index += 1
            rune_index += 1
    return "".join(chars), pos_map


def parse_para_char_shape(data: bytes) -> list[CharShapeMapping]:
    mappings: list[CharShapeMapping] = []
    for offset in range(0, len(data) - 7, 8):
        position, char_shape_id = struct.unpack_from("<II", data, offset)
        mappings.append(CharShapeMapping(position=position, char_shape_id=char_shape_id))
    return mappings


def build_formatted_spans_from_raw(
    raw_data: bytes,
    mappings: list[CharShapeMapping],
    doc_info: DocInfoTables | None,
) -> list[TextSpan]:
    text, pos_map = parse_para_text_with_positions(raw_data)
    if not mappings:
        return [TextSpan(text=text)]
    translated: list[CharShapeMapping] = []
    for mapping in mappings:
        rune_pos = pos_map.get(mapping.position)
        if rune_pos is None:
            rune_pos = find_closest_rune_pos(pos_map, mapping.position)
        translated.append(CharShapeMapping(position=rune_pos, char_shape_id=mapping.char_shape_id))
    return build_formatted_spans(text, translated, doc_info)


def find_closest_rune_pos(pos_map: dict[int, int], wchar_index: int) -> int:
    best_wchar = -1
    best_rune = 0
    for wchar, rune in pos_map.items():
        if wchar <= wchar_index and wchar > best_wchar:
            best_wchar = wchar
            best_rune = rune
    return best_rune


def build_formatted_spans(
    text: str,
    mappings: list[CharShapeMapping],
    doc_info: DocInfoTables | None,
) -> list[TextSpan]:
    if not mappings:
        return [TextSpan(text=text)]
    spans: list[TextSpan] = []
    chars = list(text)
    for index, mapping in enumerate(mappings):
        end = mappings[index + 1].position if index + 1 < len(mappings) else len(chars)
        start = min(mapping.position, len(chars))
        end = min(end, len(chars))
        span = TextSpan(text="".join(chars[start:end]), char_shape_id=mapping.char_shape_id)
        if doc_info is not None and mapping.char_shape_id < len(doc_info.char_shapes):
            char_shape = doc_info.char_shapes[mapping.char_shape_id]
            span.bold = char_shape.bold
            span.italic = char_shape.italic
            span.underline = char_shape.underline
            span.strikethrough = char_shape.strikethrough
            span.font_size = char_shape.font_size
            span.text_color = char_shape.text_color
            face_id = char_shape.face_id[0]
            if face_id < len(doc_info.face_names):
                span.font_name = doc_info.face_names[face_id].name
        spans.append(span)
    return spans


def parse_table_from_record(record: Record, doc_info: DocInfoTables | None) -> ParsedTable | None:
    table_def = None
    for child in record.children:
        if child.tag_id == HWPTAG_TABLE:
            table_def = parse_table_def(child.data)
            break
    if table_def is None:
        return None

    cell_defs: list[CellDef] = []
    current_cell: CellDef | None = None
    for child in record.children:
        if child.tag_id == HWPTAG_LIST_HEADER:
            if current_cell is not None:
                cell_defs.append(current_cell)
            current_cell = parse_cell_def(child.data)
            if current_cell is not None:
                current_cell.paragraphs = extract_paragraphs_from_cell(child, doc_info)
        elif child.tag_id == HWPTAG_PARA_HEADER and current_cell is not None:
            current_cell.paragraphs.append(extract_formatted_paragraph_from_record(child, doc_info))
    if current_cell is not None:
        cell_defs.append(current_cell)

    margins = table_def["margins"]
    min_margin = min(margins) if margins else 0
    return ParsedTable(
        row_count=table_def["row_count"],
        col_count=table_def["col_count"],
        rows=organize_cells_into_rows(cell_defs, table_def["row_count"]),
        cell_margin_mm=min_margin * HWPU_TO_MM,
    )


def parse_table_def(data: bytes) -> dict[str, object] | None:
    if len(data) < 18:
        return None
    row_count, col_count, _cell_spacing, left, right, top, bottom = struct.unpack_from("<7H", data, 4)
    return {"row_count": row_count, "col_count": col_count, "margins": [left, right, top, bottom]}


def parse_cell_def(data: bytes) -> CellDef | None:
    if len(data) < 22:
        return None
    col, row, col_span, row_span, width, height = struct.unpack_from("<HHHHII", data, 6)
    return CellDef(row=row, col=col, col_span=col_span, row_span=row_span, width=width, height=height)


def extract_paragraphs_from_cell(record: Record, doc_info: DocInfoTables | None) -> list[FormattedParagraph]:
    paragraphs: list[FormattedParagraph] = []
    for child in record.children:
        if child.tag_id == HWPTAG_PARA_HEADER:
            paragraphs.append(extract_formatted_paragraph_from_record(child, doc_info))
    return paragraphs


def organize_cells_into_rows(cells: list[CellDef], row_count: int) -> list[ParsedTableRow]:
    if not cells:
        return [ParsedTableRow() for _ in range(row_count)]
    max_row = row_count
    for cell in cells:
        max_row = max(max_row, cell.row + 1)
    rows = [ParsedTableRow() for _ in range(max_row)]
    for cell in cells:
        rows[cell.row].cells.append(cell)
    return rows


def extract_images_from_tree(
    tree: list[Record],
    doc_info: DocInfoTables | None,
    hwp5: HWP5File,
) -> list[ImageData]:
    if doc_info is None:
        return []
    images: list[ImageData] = []
    for record in tree:
        if record.tag_id == HWPTAG_CTRL_HEADER and parse_ctrl_type_name(record.data) == "gso ":
            image = extract_image_from_gso_children(record.children, doc_info, hwp5)
            if image is not None:
                images.append(image)
            continue
        images.extend(extract_images_from_tree(record.children, doc_info, hwp5))
    return images


def extract_image_from_gso_children(
    children: list[Record],
    doc_info: DocInfoTables,
    hwp5: HWP5File,
) -> ImageData | None:
    shape_component: ShapeComponent | None = None
    for child in children:
        if child.tag_id != HWPTAG_SHAPE_COMPONENT:
            continue
        shape_component = parse_shape_component(child.data)
        for grandchild in child.children:
            if grandchild.tag_id != HWPTAG_SHAPE_COMPONENT_PICTURE:
                continue
            parsed = parse_picture_shape(grandchild.data)
            if parsed is None:
                continue
            bin_data_id, cur_width, cur_height = parsed
            image = hwp5.resolve_bin_data(bin_data_id, cur_width, cur_height, shape_component, doc_info)
            if image is not None:
                return image
    return None


def parse_shape_component(data: bytes) -> ShapeComponent | None:
    if len(data) < 24:
        return None
    return ShapeComponent(
        width=struct.unpack_from("<I", data, 16)[0],
        height=struct.unpack_from("<I", data, 20)[0],
    )


def parse_picture_shape(data: bytes) -> tuple[int, int, int] | None:
    if len(data) < 73:
        return None
    left, top, right, bottom = struct.unpack_from("<4i", data, 44)
    bin_data_id = struct.unpack_from("<H", data, 71)[0]
    cur_width = right - left if right - left > 0 else 0
    cur_height = bottom - top if bottom - top > 0 else 0
    return bin_data_id, cur_width, cur_height


def convert_parsed_table(table: ParsedTable) -> docir.Table:
    rows: list[docir.TableRow] = []
    for row in table.rows:
        cells: list[docir.TableCell] = []
        for cell in row.cells:
            children = [convert_formatted_paragraph(paragraph) for paragraph in cell.paragraphs]
            cells.append(
                docir.TableCell(
                    children=children,
                    col_span=cell.col_span or 1,
                    row_span=cell.row_span or 1,
                    width_mm=cell.width * HWPU_TO_MM,
                )
            )
        rows.append(docir.TableRow(cells=cells))
    return docir.Table(rows=rows, cell_padding_mm=table.cell_margin_mm)


def convert_image_data(image: ImageData) -> docir.Image:
    display_width = image.cur_width or image.width
    display_height = image.cur_height or image.height
    return docir.Image(
        data=image.data,
        format=mime_to_extension(image.mime_type),
        width=hwp_unit_to_pixel(image.width),
        height=hwp_unit_to_pixel(image.height),
        path=image.file_name,
        display_width_mm=display_width * HWPU_TO_MM,
        display_height_mm=display_height * HWPU_TO_MM,
    )


def convert_formatted_paragraph(paragraph: FormattedParagraph) -> docir.Block:
    inlines: list[docir.Inline] = []
    spans = paragraph.spans or [TextSpan(text=paragraph.text)]
    for span in spans:
        text_node = docir.Text(value=span.text)
        style = span_to_text_style(span)
        if style.has_values():
            text_node.style = style
        inline: docir.Inline = text_node
        if span.bold:
            inline = docir.Bold(children=[inline])
        if span.italic:
            inline = docir.Italic(children=[inline])
        if span.underline:
            inline = docir.Underline(children=[inline])
        if span.strikethrough:
            inline = docir.Strikethrough(children=[inline])
        inlines.append(inline)
    if paragraph.heading_level > 0:
        return docir.Heading(level=paragraph.heading_level, children=inlines, alignment=paragraph.alignment)
    return docir.Paragraph(
        children=inlines,
        alignment=paragraph.alignment,
        left_indent_mm=paragraph.left_indent_mm,
        right_indent_mm=paragraph.right_indent_mm,
        first_line_indent_mm=paragraph.first_line_indent_mm,
        line_spacing_percent=paragraph.line_spacing_percent,
        space_before_mm=paragraph.space_before_mm,
        space_after_mm=paragraph.space_after_mm,
    )


def span_to_text_style(span: TextSpan) -> docir.TextStyle:
    return docir.TextStyle(
        font_name=span.font_name,
        font_size=span.font_size / 100.0 if span.font_size > 0 else 0.0,
        color=color_to_hex(span.text_color) if span.text_color else "",
    )


def apply_heuristic_headings_from_sections(document: docir.Document) -> None:
    if not document.sections:
        return
    counts: dict[float, int] = {}
    for section in document.sections:
        for block in section.blocks:
            if isinstance(block, docir.Paragraph):
                for inline in block.children:
                    walk_inline_font_sizes(inline, counts)
    body_font_size = most_common_font_size(counts)
    if body_font_size < 8.0:
        return
    for section in document.sections:
        for index, block in enumerate(section.blocks):
            if isinstance(block, docir.Paragraph):
                level = detect_heuristic_heading_level(block, body_font_size)
                if level > 0:
                    section.blocks[index] = docir.Heading(
                        level=level,
                        children=block.children,
                        alignment=block.alignment,
                    )
    document.blocks = [block for section in document.sections for block in section.blocks]


def walk_inline_font_sizes(inline: docir.Inline, counts: dict[float, int]) -> None:
    if isinstance(inline, docir.Text):
        if inline.style is not None and inline.style.font_size > 0:
            counts[inline.style.font_size] = counts.get(inline.style.font_size, 0) + 1
    elif isinstance(inline, docir.Bold | docir.Italic | docir.Underline | docir.Strikethrough):
        for child in inline.children:
            walk_inline_font_sizes(child, counts)


def most_common_font_size(counts: dict[float, int]) -> float:
    best = 0.0
    best_count = 0
    for size, count in counts.items():
        if count > best_count or (count == best_count and size < best):
            best = size
            best_count = count
    return best


def detect_heuristic_heading_level(paragraph: docir.Paragraph, body_font_size: float) -> int:
    if not paragraph.children:
        return 0
    text_parts: list[str] = []
    max_font_size = 0.0
    for inline in paragraph.children:
        if not isinstance(inline, docir.Bold):
            return 0
        for child in inline.children:
            if isinstance(child, docir.Text):
                text_parts.append(child.value)
                if child.style is not None:
                    max_font_size = max(max_font_size, child.style.font_size)
    text = "".join(text_parts).strip()
    if not text or len(text) > 80 or max_font_size < body_font_size * 1.2:
        return 0
    if max_font_size >= body_font_size * 1.8:
        return 1
    if max_font_size >= body_font_size * 1.4:
        return 2
    return 3


def find_page_def_layout(records: list[Record]) -> docir.PageLayout:
    for record in records:
        if record.tag_id == HWPTAG_PAGE_DEF and len(record.data) >= 40:
            values = struct.unpack_from("<9I", record.data, 0)
            props = struct.unpack_from("<I", record.data, 36)[0]
            return docir.PageLayout(
                width_mm=values[0] * HWPU_TO_MM,
                height_mm=values[1] * HWPU_TO_MM,
                margin_left_mm=values[2] * HWPU_TO_MM,
                margin_right_mm=values[3] * HWPU_TO_MM,
                margin_top_mm=values[4] * HWPU_TO_MM,
                margin_bottom_mm=values[5] * HWPU_TO_MM,
                orientation="landscape" if props & 0x01 else "portrait",
                column_count=1,
            )
    return docir.PageLayout()


def parse_ctrl_type_name(data: bytes) -> str:
    if len(data) < 4:
        return ""
    return bytes([data[3], data[2], data[1], data[0]]).decode("latin1")


def detect_heading_level(name: str) -> int:
    lower = name.strip().lower()
    for prefix in ("제목 ", "heading ", "heading", "개요 "):
        if lower.startswith(prefix):
            rest = lower[len(prefix) :].strip()
            if len(rest) == 1 and "1" <= rest <= "7":
                return min(int(rest), 6)
    for keyword, level in (("큰제목", 1), ("중간제목", 2), ("작은제목", 3)):
        if keyword in lower:
            return level
    return 0


def alignment_to_string(code: int) -> str:
    if code == 1:
        return "left"
    if code == 2:
        return "right"
    if code == 3:
        return "center"
    if code in {0, 4, 5}:
        return "justify"
    return ""


def detect_mime_type(data: bytes) -> str:
    if len(data) >= 4 and data[:4] == b"\x89PNG":
        return "image/png"
    if len(data) >= 3 and data[:3] == b"\xFF\xD8\xFF":
        return "image/jpeg"
    if len(data) >= 4 and data[:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 2 and data[:2] == b"BM":
        return "image/bmp"
    if len(data) >= 4 and data[:4] == b"\xD7\xCD\xC6\x9A":
        return "image/wmf"
    if len(data) >= 4 and data[:4] == b"\x01\x00\x00\x00":
        return "image/emf"
    return "application/octet-stream"


def mime_to_extension(mime_type: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/wmf": "wmf",
        "image/emf": "emf",
    }.get(mime_type, "bin")


def hwp_unit_to_pixel(value: int) -> int:
    return int(value * 96 / 7200) if value else 0


def color_to_hex(color: int) -> str:
    red = color & 0xFF
    green = (color >> 8) & 0xFF
    blue = (color >> 16) & 0xFF
    if red == 0 and green == 0 and blue == 0:
        return ""
    return f"#{red:02X}{green:02X}{blue:02X}"


def read_utf16le(data: bytes, offset: int, count: int) -> str:
    chars: list[str] = []
    for _ in range(count):
        if offset + 2 > len(data):
            break
        chars.append(_rune_from_utf16_code_unit(struct.unpack_from("<H", data, offset)[0]))
        offset += 2
    return "".join(chars)


def _rune_from_utf16_code_unit(value: int) -> str:
    if 0xD800 <= value <= 0xDFFF:
        return "\uFFFD"
    return chr(value)


def _section_number(name: str) -> int:
    try:
        return int(name.removeprefix("Section"))
    except ValueError:
        return 0
