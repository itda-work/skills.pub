"""section XML 스캐너 — 문단·run·<hp:t>·표 셀 위치 레지스트리 (문자열 splice 전용, DOM 재직렬화 금지).

설계 요지:
- 태그 토크나이저(정규식)로 전체 XML 을 한 번 훑고, 여는/닫는 태그 스택으로 깊이를 추적한다.
  표 셀 안의 문단은 `<hp:tbl>` → `<hp:tr>` → `<hp:tc>` → `<hp:subList>` → `<hp:p>` 로 중첩되므로
  문단 스택·셀 스택을 따로 둔다. 중첩 표의 셀은 부모 표에 속하지 않는다.
- 문단 텍스트 = 그 문단에 **직접** 속한 `<hp:t>` 조각 + 그 형제로 놓인 비텍스트 요소를 문서 순서로 이어붙인 것.
  `<hp:fwSpace/>` → 공백 1개, 그 밖은 전부 매칭 불가 sentinel(U+FFFC): `<hp:t>` 안 인라인 컨트롤(tab·lineBreak…)과
  **문단 직속 비텍스트 요소**(`<hp:ctrl>`(fieldBegin/fieldEnd)·`<hp:pic>`·`<hp:tbl>`·`<hp:secPr>` 등).
  즉 키가 컨트롤을 가로지르면 절대 매칭되지 않는다(fail-closed, Codex R1 F4 · R2 F1).
  `<hp:linesegarray>` 는 조판 메타라 조각을 만들지 않고, 접힌 요소 안(중첩 표 등)은 부모 문단에서 조각 하나로 센다
  — 그 안의 문단은 여전히 별개 문단이다.
- 모든 위치는 원본 XML 문자열 오프셋이다. 편집은 `edits.apply_edits` 로 한 번에 splice 한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SENTINEL = "￼"  # 매칭 불가 컨트롤 자리표시(OBJECT REPLACEMENT CHARACTER)
FWSPACE_TAG = "hp:fwSpace"
T_TAG = "hp:t"
CTRL_WRAPPER = "hp:ctrl"

# 문단 직속 비텍스트 요소의 두 부류 — **텍스트를 나누는가**가 기준이다(Claude R2 C-F1).
#  · 나누는 것: 개체(hp:pic·hp:tbl·hp:rect·hp:polygon·hp:container…)와 인라인 앵커(fieldBegin/fieldEnd·footNote·
#    bookmark 류) → sentinel. 키가 가로지르면 매칭 불가(fail-closed).
#  · 나누지 않는 것: **무텍스트 레이아웃 컨트롤**. 한컴은 표 셀 첫 문단 첫 run 에
#    `<hp:ctrl><hp:colPr/></hp:ctrl>` 을 넣는다(실 픽스처 section1 의 30셀) — 이것을 sentinel 로 접으면
#    셀 텍스트가 '￼검토완료' 가 되어 --label 정확 일치가 깨지고 --dump CTRL 이 14→63 으로 부푼다(실측).
# 판정은 이름 나열이 아니라 **구조**다: 아래 집합의 요소, 그리고 그 집합만 품은 `<hp:ctrl>` 이 레이아웃이고
# **그 밖은 전부 sentinel** 이다(모르는 컨트롤은 나눈다고 본다 — fail-closed).
# 실 픽스처(reader fixtures) `<hp:ctrl>` 직속 자식 실측: colPr 382 · fieldBegin 4 · newNum 4 · fieldEnd 4 ·
# footNote 3 · footer 2 · pageNum 2 — 이 중 fieldBegin/fieldEnd/footNote 만 텍스트를 나눈다.
LAYOUT_ELEMENTS = frozenset({
    "hp:secPr", "hp:colPr", "hp:newNum", "hp:pageNum", "hp:pageNumCtrl",
    "hp:pageHiding", "hp:pageOddEven", "hp:header", "hp:footer",
    "hp:footNotePr", "hp:endNotePr", "hp:autoNumFormat",
})

# 태그 토크나이저: PI·주석·CDATA 는 이름 없이 통째로 건너뛰고, 요소 태그는 이름·속성·self-closing 을 잡는다.
# 속성값은 따옴표 단위로 읽어 값 안의 '>' 에 오작동하지 않는다.
TAG_RE = re.compile(
    r"<(?:"
    r"\?.*?\?>"
    r"|!--.*?-->"
    r"|!\[CDATA\[.*?\]\]>"
    r"|!DOCTYPE[^>]*>"
    r"|(?P<close>/)?(?P<name>[A-Za-z_][\w:.\-]*)"
    r"(?P<attrs>(?:\s+[\w:.\-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*(?P<self>/)?>"
    r")",
    re.S,
)
ENTITY_RE = re.compile(r"&(#x[0-9A-Fa-f]+|#\d+|amp|lt|gt|quot|apos);")
_ENTS = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
ATTR_RE = re.compile(r"([\w:.\-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")


def xml_unescape(raw: str) -> str:
    def rep(m: re.Match) -> str:
        e = m.group(1)
        if e[:2].lower() == "#x":
            return chr(int(e[2:], 16))
        if e[0] == "#":
            return chr(int(e[1:]))
        return _ENTS[e]

    return ENTITY_RE.sub(rep, raw)


def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def raw_offset(raw: str, k: int) -> int:
    """디코딩된 텍스트 오프셋 k 를 raw XML 텍스트 오프셋으로 — 엔티티(&amp; 등)는 1글자로 센다."""
    pos = 0
    remaining = k
    while remaining > 0:
        m = ENTITY_RE.match(raw, pos)
        if m:
            pos = m.end()
        else:
            pos += 1
        remaining -= 1
    return pos


def parse_attrs(attrs: str) -> dict[str, str]:
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3)) for m in ATTR_RE.finditer(attrs)}


@dataclass
class Piece:
    """문단 텍스트를 이루는 조각. kind: text | fw(fwSpace→' ') | ctrl(sentinel) | layout(무텍스트 — text='')."""

    kind: str
    raw_start: int
    raw_end: int
    text: str
    name: str = ""
    pos: int = 0  # 문단 텍스트 안 시작 오프셋(scan 후 채움)
    tnode: "TNode | None" = None


@dataclass
class TNode:
    start: int
    open_end: int
    close_start: int = -1
    end: int = -1
    self_closing: bool = False
    attrs: str = ""
    run: "Run | None" = None
    pieces: list[Piece] = field(default_factory=list)


@dataclass
class Run:
    start: int
    open_end: int
    close_start: int = -1
    end: int = -1
    self_closing: bool = False
    attrs: str = ""
    para: "Para | None" = None
    tnodes: list[TNode] = field(default_factory=list)


@dataclass
class Cell:
    table: "Table"
    start: int
    open_end: int
    end: int = -1
    row_addr: int = -1
    col_addr: int = -1
    col_span: int = 1
    row_span: int = 1
    paras: list["Para"] = field(default_factory=list)
    nested_tables: int = 0

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paras)

    @property
    def is_empty(self) -> bool:
        """비교는 **보이는 텍스트**로 — sentinel(그림·표 등)은 채울 텍스트가 아니다(Claude R2 C-F1)."""
        return not any(visible(p.text) for p in self.paras)

    @property
    def coord(self) -> str:
        return f"표{self.table.index} r{self.row_addr} c{self.col_addr}"


@dataclass
class Table:
    index: int
    start: int
    end: int = -1
    parent: "Table | None" = None
    cells: list[Cell] = field(default_factory=list)
    nested: int = 0  # 이 표 안(어느 깊이든)에 든 중첩 표 수

    def cell_at(self, row: int, col: int) -> Cell | None:
        for c in self.cells:
            if c.row_addr == row and c.col_addr == col:
                return c
        return None

    @property
    def has_span(self) -> bool:
        return any(c.col_span != 1 or c.row_span != 1 for c in self.cells)


@dataclass
class Para:
    ordinal: int  # 문서 전체 문단 일련번호(모든 문단, 0부터)
    start: int
    open_end: int
    close_start: int = -1
    end: int = -1
    self_closing: bool = False
    cell: Cell | None = None
    runs: list[Run] = field(default_factory=list)
    tnodes: list[TNode] = field(default_factory=list)
    lineseg: tuple[int, int] | None = None
    pieces: list[Piece] = field(default_factory=list)
    items: list = field(default_factory=list)  # 문서 순서의 TNode | Piece(문단 직속 비텍스트 요소)
    text: str = ""
    ctrl_names: list[str] = field(default_factory=list)
    number: int = 0  # --dump/--check 가 쓰는 나열 번호(나열 문단만, 1부터) — cli.number_paras 가 채운다

    @property
    def has_ctrl(self) -> bool:
        """분절 컨트롤이 **보이는 텍스트와 함께** 있는가.

        "키를 컨트롤 앞뒤로 나누세요" 라는 안내는 나눌 텍스트가 있을 때만 뜻이 있다 — 표만 품은 셀 문단까지
        CTRL 로 표시하면 실 양식에서 플래그가 14→30 으로 부풀고 틀린 안내가 된다(Claude R2 C-F1)."""
        return bool(self.ctrl_names) and bool(visible(self.text))

    @property
    def location(self) -> str:
        return self.cell.coord if self.cell is not None else "본문"

    @property
    def is_listed(self) -> bool:
        """--dump/--check 에 나열되는 문단: 보이는 텍스트가 있거나 표 셀 문단(빈 셀 = 채움 대상).

        sentinel 만 든 문단(표를 품은 본문 문단·secPr 만 있는 첫 문단 등)은 채울 자리가 없으므로 나열하지 않는다
        — 그렇지 않으면 F1 로 표·필드를 조각으로 등록한 순간 나열 번호가 통째로 밀린다."""
        return bool(visible(self.text)) or self.cell is not None

    def display_text(self) -> str:
        return display(self.text)


def visible(text: str) -> str:
    """sentinel 을 뺀 '사람이 읽는' 텍스트 — 비어 있음·라벨 일치 판정의 기준이다."""
    return text.replace(SENTINEL, "").strip()


def display(text: str) -> str:
    """사람용 표시: sentinel 을 눈에 보이는 표식으로(⇥ 탭·⏎ 줄바꿈은 스캔 시 이름별로 치환됨)."""
    return text.replace("\r", " ").replace("\n", " ")


_DISPLAY_MARK = {"hp:tab": "⇥", "hp:lineBreak": "⏎"}


@dataclass
class Section:
    xml: str
    paras: list[Para]
    tables: list[Table]
    table_base: int = 0


def scan_section(xml: str, table_base: int = 0, para_base: int = 0) -> Section:
    """section XML 을 훑어 레지스트리를 만든다. table_base/para_base 는 문서 전체 일련번호의 시작."""
    paras: list[Para] = []
    tables: list[Table] = []
    stack: list[tuple[str, int, int]] = []  # (name, start, open_end)
    para_stack: list[Para] = []
    run_stack: list[Run] = []
    cell_stack: list[Cell] = []
    table_stack: list[Table] = []
    cur_t: TNode | None = None
    t_cursor = 0
    t_inner_depth = 0
    t_inner_start = 0
    t_inner_name = ""
    lineseg_open: tuple[Para, int] | None = None
    # 문단 직속 비텍스트 요소(필드·그림·표…)를 sentinel 한 조각으로 접기 위한 상태.
    # ctrl_open: (요소 깊이, 그 조각을 품은 문단, 조각) — 조각이 None 이면 '접되 조각은 만들지 않음'(linesegarray).
    # 항목: [요소 깊이, 그 조각을 품은 문단, 조각(없으면 None — linesegarray), 요소 이름, 직속 자식 이름 집합]
    ctrl_open: list[list] = []
    depth = 0

    def flush_text(upto: int) -> None:
        nonlocal t_cursor
        if cur_t is not None and upto > t_cursor:
            raw = xml[t_cursor:upto]
            cur_t.pieces.append(Piece("text", t_cursor, upto, xml_unescape(raw), tnode=cur_t))
        t_cursor = upto

    def reg_para() -> Para | None:
        """지금 조각을 등록할 문단 — 이미 sentinel 로 접힌 요소 안이면 None(그 요소 자체가 조각 하나다)."""
        if not para_stack:
            return None
        p = para_stack[-1]
        if ctrl_open and ctrl_open[-1][1] is p:
            return None
        return p

    for m in TAG_RE.finditer(xml):
        name = m.group("name")
        if name is None:
            # PI/주석/CDATA — <hp:t> 안이면 매칭 불가 컨트롤로 취급(fail-closed)
            if cur_t is not None and t_inner_depth == 0:
                flush_text(m.start())
                cur_t.pieces.append(Piece("ctrl", m.start(), m.end(), SENTINEL, name="!", tnode=cur_t))
                t_cursor = m.end()
            continue
        is_close = m.group("close") == "/"
        is_self = m.group("self") == "/"
        attrs = m.group("attrs") or ""

        if cur_t is not None:
            # <hp:t> 내부: 텍스트 조각과 인라인 컨트롤을 분리한다
            if is_close and name == T_TAG and t_inner_depth == 0:
                flush_text(m.start())
                cur_t.close_start = m.start()
                cur_t.end = m.end()
                cur_t = None
                depth -= 1
                continue
            if t_inner_depth == 0:
                flush_text(m.start())
                if is_self:
                    if name == FWSPACE_TAG:
                        cur_t.pieces.append(Piece("fw", m.start(), m.end(), " ", name=name, tnode=cur_t))
                    else:
                        cur_t.pieces.append(Piece("ctrl", m.start(), m.end(), SENTINEL, name=name, tnode=cur_t))
                    t_cursor = m.end()
                elif is_close:
                    # 짝 없는 닫는 태그 — 컨트롤로 취급
                    cur_t.pieces.append(Piece("ctrl", m.start(), m.end(), SENTINEL, name=name, tnode=cur_t))
                    t_cursor = m.end()
                else:
                    t_inner_depth = 1
                    t_inner_start = m.start()
                    t_inner_name = name
            else:
                if is_close:
                    t_inner_depth -= 1
                    if t_inner_depth == 0:
                        cur_t.pieces.append(
                            Piece("ctrl", t_inner_start, m.end(), SENTINEL, name=t_inner_name, tnode=cur_t)
                        )
                        t_cursor = m.end()
                elif not is_self:
                    t_inner_depth += 1
            continue

        if is_close:
            depth -= 1
            if ctrl_open and ctrl_open[-1][0] == depth:
                _, _, _pc, _name, _kids = ctrl_open.pop()
                if _pc is not None:
                    _pc.raw_end = m.end()
                    # `<hp:ctrl>` 은 자식이 정해질 때까지 종류를 알 수 없다 — 닫는 시점에 판정한다.
                    if _name == CTRL_WRAPPER and _kids <= LAYOUT_ELEMENTS:
                        _pc.kind, _pc.text = "layout", ""
            # 스택에서 같은 이름을 찾아 pop (불일치는 관대하게 처리)
            while stack and stack[-1][0] != name:
                stack.pop()
            if stack:
                stack.pop()
            if name == "hp:p":
                if para_stack:
                    p = para_stack.pop()
                    p.close_start = m.start()
                    p.end = m.end()
            elif name == "hp:run":
                if run_stack:
                    r = run_stack.pop()
                    r.close_start = m.start()
                    r.end = m.end()
            elif name == "hp:tc":
                if cell_stack:
                    c = cell_stack.pop()
                    c.end = m.end()
            elif name == "hp:tbl":
                if table_stack:
                    t = table_stack.pop()
                    t.end = m.end()
            elif name == "hp:linesegarray":
                if lineseg_open is not None:
                    p, s = lineseg_open
                    p.lineseg = (s, m.end())
                    lineseg_open = None
            continue

        # 여는 태그 또는 self-closing
        if ctrl_open and ctrl_open[-1][0] + 1 == depth:
            ctrl_open[-1][4].add(name)  # 접힌 요소의 직속 자식 — <hp:ctrl> 종류 판정에 쓴다
        # <hp:t> 형제로 놓인 비텍스트 요소(hp:ctrl/fieldBegin·hp:pic·hp:tbl·기타)를 문단 텍스트의 sentinel
        # 한 조각으로 등록한다 — 키가 그것을 가로지르면 절대 매칭되지 않는다(fail-closed, Codex R2 F1).
        # 접힌 요소 안은 그 문단에 대해 더 등록하지 않는다(중첩 표는 부모 문단에서 조각 하나, 안쪽 문단은 별개).
        host = reg_para()
        if host is not None and name not in (T_TAG, "hp:run", "hp:p"):
            if name == "hp:linesegarray":
                if not is_self:
                    ctrl_open.append([depth, host, None, name, set()])  # 조판 메타 — 조각도 만들지 않는다
            else:
                # 레이아웃 컨트롤은 text='' 인 layout 조각 — 매칭·표시·CTRL 플래그 어디에도 안 실린다.
                # 빈 `<hp:ctrl/>` 도 나눌 것이 없으므로 레이아웃이다.
                layout = name in LAYOUT_ELEMENTS or (name == CTRL_WRAPPER and is_self)
                _piece = Piece("layout" if layout else "ctrl", m.start(), m.end(), "" if layout else SENTINEL, name=name)
                host.items.append(_piece)
                if not is_self:
                    ctrl_open.append([depth, host, _piece, name, set()])
        if not is_self:
            depth += 1
        if name == "hp:p":
            p = Para(ordinal=para_base + len(paras), start=m.start(), open_end=m.end(), self_closing=is_self)
            p.cell = cell_stack[-1] if cell_stack else None
            if p.cell is not None:
                p.cell.paras.append(p)
            paras.append(p)
            if is_self:
                p.close_start = m.end()
                p.end = m.end()
            else:
                para_stack.append(p)
                stack.append((name, m.start(), m.end()))
            continue
        if name == "hp:run":
            r = Run(start=m.start(), open_end=m.end(), self_closing=is_self, attrs=attrs)
            r.para = para_stack[-1] if para_stack else None
            if r.para is not None:
                r.para.runs.append(r)
            if is_self:
                r.close_start = m.end()
                r.end = m.end()
            else:
                run_stack.append(r)
                stack.append((name, m.start(), m.end()))
            continue
        if name == T_TAG:
            if host is None:
                continue  # 접힌 요소 안의 <hp:t> — 그 요소가 이미 조각 하나다(이중 계상 금지)
            t = TNode(start=m.start(), open_end=m.end(), self_closing=is_self, attrs=attrs)
            t.run = run_stack[-1] if run_stack else None
            para = para_stack[-1] if para_stack else None
            if t.run is not None:
                t.run.tnodes.append(t)
            if para is not None:
                para.tnodes.append(t)
                para.items.append(t)
            if is_self:
                t.close_start = m.end()
                t.end = m.end()
            else:
                cur_t = t
                t_cursor = m.end()
                t_inner_depth = 0
            continue
        if name == "hp:tbl":
            t = Table(index=table_base + len(tables), start=m.start())
            t.parent = table_stack[-1] if table_stack else None
            for anc in table_stack:
                anc.nested += 1
            if cell_stack:
                cell_stack[-1].nested_tables += 1
            tables.append(t)
            if not is_self:
                table_stack.append(t)
                stack.append((name, m.start(), m.end()))
            continue
        if name == "hp:tc":
            if table_stack:
                c = Cell(table=table_stack[-1], start=m.start(), open_end=m.end())
                table_stack[-1].cells.append(c)
                if not is_self:
                    cell_stack.append(c)
                    stack.append((name, m.start(), m.end()))
            continue
        if name == "hp:cellAddr" and cell_stack:
            a = parse_attrs(attrs)
            cell_stack[-1].col_addr = int(a.get("colAddr", cell_stack[-1].col_addr))
            cell_stack[-1].row_addr = int(a.get("rowAddr", cell_stack[-1].row_addr))
            if not is_self:
                stack.append((name, m.start(), m.end()))
            continue
        if name == "hp:cellSpan" and cell_stack:
            a = parse_attrs(attrs)
            cell_stack[-1].col_span = int(a.get("colSpan", 1))
            cell_stack[-1].row_span = int(a.get("rowSpan", 1))
            if not is_self:
                stack.append((name, m.start(), m.end()))
            continue
        if name == "hp:linesegarray" and para_stack:
            if is_self:
                para_stack[-1].lineseg = (m.start(), m.end())
            else:
                lineseg_open = (para_stack[-1], m.start())
                stack.append((name, m.start(), m.end()))
            continue
        if not is_self:
            stack.append((name, m.start(), m.end()))

    # 셀 좌표 미기재(cellAddr 없음) 보정: 등장 순서로 채운다(행 정보 없음 → 열만)
    for tbl in tables:
        for i, c in enumerate(tbl.cells):
            if c.row_addr < 0 or c.col_addr < 0:
                c.row_addr = max(c.row_addr, 0)
                c.col_addr = c.col_addr if c.col_addr >= 0 else i

    # 문단 텍스트·조각 오프셋 확정
    for p in paras:
        pos = 0
        pieces: list[Piece] = []
        names: list[str] = []
        for item in p.items:
            for pc in item.pieces if isinstance(item, TNode) else (item,):
                pc.pos = pos
                pos += len(pc.text)
                pieces.append(pc)
                if pc.kind == "ctrl":
                    names.append(pc.name)
        p.pieces = pieces
        p.text = "".join(pc.text for pc in pieces)
        p.ctrl_names = names
    return Section(xml=xml, paras=paras, tables=tables, table_base=table_base)


def display_with_marks(p: Para) -> str:
    """sentinel 을 컨트롤 종류별 표식(⇥ 탭·⏎ 줄바꿈·▯ 기타)으로 바꾼 표시 문자열."""
    out: list[str] = []
    for pc in p.pieces:
        if pc.kind == "ctrl":
            out.append(_DISPLAY_MARK.get(pc.name, "▯"))
        else:
            out.append(pc.text)
    return display("".join(out))


def tag_signature(xml: str, exclude: frozenset[str] = frozenset({T_TAG, FWSPACE_TAG})) -> list[str]:
    """XML 안 요소 태그 이름의 순서 목록(여는/닫는/self-closing 구분 포함) — 치환 전후 불변 자기검사용."""
    sig: list[str] = []
    for m in TAG_RE.finditer(xml):
        name = m.group("name")
        if name is None or name in exclude:
            continue
        kind = "/" if m.group("close") else ("s" if m.group("self") else "o")
        sig.append(kind + name)
    return sig
