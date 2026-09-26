"""Document IR ported from hyve's Go HWPX engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TextStyle:
    font_name: str = ""
    font_size: float = 0.0
    color: str = ""

    def has_values(self) -> bool:
        return bool(self.font_name or self.font_size or self.color)


class Inline:
    pass


@dataclass(slots=True)
class Text(Inline):
    value: str
    style: TextStyle | None = None


@dataclass(slots=True)
class Bold(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass(slots=True)
class Italic(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass(slots=True)
class Underline(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass(slots=True)
class Strikethrough(Inline):
    children: list[Inline] = field(default_factory=list)


@dataclass(slots=True)
class Link(Inline):
    url: str = ""
    children: list[Inline] = field(default_factory=list)


@dataclass(slots=True)
class Code(Inline):
    value: str


@dataclass(slots=True)
class LineBreak(Inline):
    pass


class Block:
    pass


@dataclass(slots=True)
class Heading(Block):
    level: int
    children: list[Inline] = field(default_factory=list)
    alignment: str = ""
    explicit_bold: bool | None = None


@dataclass(slots=True)
class Paragraph(Block):
    children: list[Inline] = field(default_factory=list)
    alignment: str = ""
    left_indent_mm: float = 0.0
    right_indent_mm: float = 0.0
    first_line_indent_mm: float = 0.0
    line_spacing_percent: float = 0.0
    space_before_mm: float = 0.0
    space_after_mm: float = 0.0


@dataclass(slots=True)
class TableCell(Block):
    children: list[Block] = field(default_factory=list)
    col_span: int = 1
    row_span: int = 1
    width_mm: float = 0.0


@dataclass(slots=True)
class TableRow(Block):
    cells: list[TableCell] = field(default_factory=list)


@dataclass(slots=True)
class Table(Block):
    rows: list[TableRow] = field(default_factory=list)
    cell_padding_mm: float = 0.0


@dataclass(slots=True)
class ListItem(Block):
    children: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class List(Block):
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)


@dataclass(slots=True)
class Image(Block):
    data: bytes = b""
    format: str = ""
    width: int = 0
    height: int = 0
    alt: str = ""
    path: str = ""
    display_width_mm: float = 0.0
    display_height_mm: float = 0.0


@dataclass(slots=True)
class HorizontalRule(Block):
    pass


@dataclass(slots=True)
class CodeBlock(Block):
    language: str = ""
    code: str = ""


@dataclass(slots=True)
class PageBreak(Block):
    pass


@dataclass(slots=True)
class PageLayout:
    width_mm: float = 210.0
    height_mm: float = 297.0
    orientation: str = "portrait"
    margin_top_mm: float = 20.0
    margin_right_mm: float = 20.0
    margin_bottom_mm: float = 20.0
    margin_left_mm: float = 20.0
    column_count: int = 1
    column_gap_mm: float = 0.0
    has_column_separator: bool = False


@dataclass(slots=True)
class PageDecorations:
    has_header: bool = False
    has_footer: bool = False
    has_page_background: bool = False


@dataclass(slots=True)
class SectionSource:
    reader: str = ""
    id: str = ""


@dataclass(slots=True)
class Section:
    index: int
    name: str = ""
    blocks: list[Block] = field(default_factory=list)
    layout: PageLayout = field(default_factory=PageLayout)
    decorations: PageDecorations = field(default_factory=PageDecorations)
    source: SectionSource = field(default_factory=SectionSource)


@dataclass(slots=True)
class Document:
    blocks: list[Block] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    title: str = ""
    creator: str = ""
