"""채우기 코어 — 문단 단위 매칭·splice, 셀/라벨/체크박스 채움, 위생.

원칙:
- 편집은 원본 XML 오프셋 기준 (start, end, replacement) 목록을 모아 한 번에 적용한다(`apply_edits`).
- 텍스트 치환은 **원본 문단 텍스트**에서 키를 찾는다 — 값 안의 글자는 다시 치환되지 않으며, 먼저 처리된
  키가 차지한 구간과 겹치는 등장은 건너뛴다.
- 치환 구간이 걸친 `<hp:t>` 조각 중 **첫 조각에 값 전체**, 나머지 조각은 겹친 부분만 제거한다(서식은 첫 run).
  구간 안의 fwSpace 는 제거된다(공백 정규화 계약). tab·lineBreak 등은 sentinel 이라 애초에 매칭되지 않는다.
- 치환 전후 `<hp:t>`·fwSpace 를 제외한 태그 시퀀스가 동일함을 단언한다(`ControlInvariantError`).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from .scan import (
    Cell,
    Para,
    SENTINEL,
    Section,
    T_TAG,
    display,
    raw_offset,
    scan_section,
    tag_signature,
    visible,
    xml_escape,
)


def show(text: str) -> str:
    """사용자에게 보여 줄 셀·문단 텍스트 — sentinel 은 ▯, 개행은 공백(Claude R2 C-F6)."""
    return display(text.replace(SENTINEL, "▯")).strip()

Value = str | list[str]


class FillError(Exception):
    """사용자에게 보고할 채우기 오류(exit 2)."""


class ControlInvariantError(Exception):
    """치환 전후 컨트롤 요소 목록이 달라짐 — 내부 자기검사 실패(중단)."""


@dataclass(order=True)
class Edit:
    start: int
    end: int
    text: str = field(compare=False)


def apply_edits(xml: str, edits: list[Edit]) -> str:
    """겹치지 않는 편집을 한 번에 적용한다. 겹치면 내부 오류."""
    if not edits:
        return xml
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    out: list[str] = []
    cursor = 0
    for e in ordered:
        if e.start < cursor:
            raise ControlInvariantError(f"편집 구간이 겹쳤습니다: {e.start}<{cursor}")
        out.append(xml[cursor : e.start])
        out.append(e.text)
        cursor = e.end
    out.append(xml[cursor:])
    return "".join(out)


def value_to_xml(value: str) -> str:
    """값 → <hp:t> 안 XML. 줄바꿈은 <hp:lineBreak/> 로."""
    return "<hp:lineBreak/>".join(xml_escape(line) for line in value.replace("\r\n", "\n").split("\n"))


def splice_span(xml: str, para: Para, a: int, b: int, replacement_xml: str) -> list[Edit]:
    """문단 텍스트 [a,b) 구간을 replacement_xml 로 바꾸는 편집 목록."""
    edits: list[Edit] = []
    first = True
    for pc in para.pieces:
        ps, pe = pc.pos, pc.pos + len(pc.text)
        if pe <= a or ps >= b or ps == pe:
            continue
        if pc.kind == "ctrl":
            raise ControlInvariantError("치환 구간이 컨트롤을 포함했습니다(매칭 불가 sentinel)")
        lo, hi = max(a, ps), min(b, pe)
        if pc.kind == "fw":
            raw_lo, raw_hi = pc.raw_start, pc.raw_end
        else:
            raw = xml[pc.raw_start : pc.raw_end]
            raw_lo = pc.raw_start + raw_offset(raw, lo - ps)
            raw_hi = pc.raw_start + raw_offset(raw, hi - ps)
        if first:
            edits.append(Edit(raw_lo, raw_hi, replacement_xml))
            first = False
        else:
            edits.append(Edit(raw_lo, raw_hi, ""))
    return edits


def _overlaps(spans: list[tuple[int, int]], a: int, b: int) -> bool:
    return any(a < e and s < b for s, e in spans)


@dataclass
class FillReport:
    counts: dict[str, int] = field(default_factory=dict)  # 키별 치환 수
    occurrences: dict[str, int] = field(default_factory=dict)  # 키별 등장 수(다른 키에 선점된 것 제외)
    changed: set[int] = field(default_factory=set)  # 변경된 문단 ordinal


def fill_texts(sec: Section, mapping: dict[str, Value], cursors: dict[str, int], report: FillReport) -> list[Edit]:
    """문단 단위 매칭 → 편집 목록. cursors 는 순차 치환(리스트 값)의 섹션 간 소비 위치."""
    edits: list[Edit] = []
    for key in mapping:
        report.counts.setdefault(key, 0)
        report.occurrences.setdefault(key, 0)
    for p in sec.paras:
        if not p.text:
            continue
        claimed: list[tuple[int, int]] = []
        for key, value in mapping.items():
            if not key or SENTINEL in key:
                continue  # sentinel 을 품은 키는 컨트롤 자리를 겨냥한 것 — 절대 매칭하지 않는다
            idx = 0
            while True:
                pos = p.text.find(key, idx)
                if pos < 0:
                    break
                idx = pos + len(key)
                if _overlaps(claimed, pos, idx):
                    continue
                report.occurrences[key] += 1
                if isinstance(value, list):
                    cur = cursors.get(key, 0)
                    if cur >= len(value):
                        continue  # 값 소진 — 자리는 그대로(호출부가 leftover 경고)
                    cursors[key] = cur + 1
                    val = value[cur]
                else:
                    val = value
                claimed.append((pos, idx))
                edits.extend(splice_span(sec.xml, p, pos, idx, value_to_xml(val)))
                report.counts[key] += 1
                report.changed.add(p.ordinal)
    return edits


def assert_control_invariant(xml: str, edits: list[Edit]) -> None:
    """편집을 '삭제만' 으로 적용한 사본의 태그 시퀀스가 원본과 같은지 — 삽입 값을 제외한 구조 불변 단언."""
    masked = apply_edits(xml, [Edit(e.start, e.end, "") for e in edits])
    if tag_signature(masked) != tag_signature(xml):
        raise ControlInvariantError("치환 전후 컨트롤 요소 목록이 달라졌습니다 — 중단(내부 자기검사)")


TICK_BOXES = "□☐"


def tick_items(sec: Section, items: list[str], report: FillReport, counts: dict[str, int]) -> list[Edit]:
    """`□항목`/`☐항목`(공백 허용) → `☑항목`. 박스 글자 하나만 바꾼다."""
    edits: list[Edit] = []
    for p in sec.paras:
        if not p.text:
            continue
        claimed: list[tuple[int, int]] = []
        for item in items:
            counts.setdefault(item, 0)
            if not item or SENTINEL in item:
                continue
            rx = re.compile("[" + TICK_BOXES + r"][ 　]*" + re.escape(item))
            for m in rx.finditer(p.text):
                if _overlaps(claimed, m.start(), m.start() + 1):
                    continue
                claimed.append((m.start(), m.start() + 1))
                edits.extend(splice_span(sec.xml, p, m.start(), m.start() + 1, "☑"))
                counts[item] += 1
                report.changed.add(p.ordinal)
    return edits


@dataclass
class CellFillResult:
    coord: str
    previous: str
    mode: str  # t | t-self | run | run-new
    warning: str = ""


def fill_cell(sec: Section, cell: Cell, value: str, report: FillReport) -> tuple[list[Edit], CellFillResult]:
    """셀 텍스트를 값으로. 첫 <hp:t> 에 값·나머지 <hp:t> 비움 / self-closing 펼침 / run 안 t 생성 / run 생성."""
    if not cell.paras:
        raise FillError(f"{cell.coord}: 셀에 문단이 없어 채울 수 없습니다")
    vx = value_to_xml(value)
    edits: list[Edit] = []
    previous = cell.text
    tnodes = [t for p in cell.paras for t in p.tnodes]
    if tnodes:
        first = tnodes[0]
        if first.self_closing:
            edits.append(Edit(first.start, first.end, f"<hp:t{first.attrs}>{vx}</hp:t>"))
            mode = "t-self"
        else:
            edits.append(Edit(first.open_end, first.close_start, vx))
            mode = "t"
        for t in tnodes[1:]:
            if not t.self_closing and t.close_start > t.open_end:
                edits.append(Edit(t.open_end, t.close_start, ""))
        for p in cell.paras:
            if p.tnodes:
                report.changed.add(p.ordinal)
        return edits, CellFillResult(cell.coord, previous, mode)
    runs = [r for p in cell.paras for r in p.runs]
    if runs:
        r = runs[0]
        if r.self_closing:
            edits.append(Edit(r.start, r.end, f"<hp:run{r.attrs}><hp:t>{vx}</hp:t></hp:run>"))
        else:
            edits.append(Edit(r.close_start, r.close_start, f"<hp:t>{vx}</hp:t>"))
        report.changed.add(r.para.ordinal if r.para is not None else cell.paras[0].ordinal)
        return edits, CellFillResult(cell.coord, previous, "run")
    p = cell.paras[0]
    if p.self_closing:
        raise FillError(f"{cell.coord}: 문단이 self-closing(<hp:p/>) 이라 run 을 넣을 자리가 없습니다")
    edits.append(Edit(p.open_end, p.open_end, f'<hp:run charPrIDRef="0"><hp:t>{vx}</hp:t></hp:run>'))
    report.changed.add(p.ordinal)
    return edits, CellFillResult(
        cell.coord, previous, "run-new", warning=f"{cell.coord}: run 이 없어 charPrIDRef=\"0\" 으로 생성했습니다(글꼴 확인 필요)"
    )


CELL_SPEC_RE = re.compile(r"^\s*표\s*(\d+)\s+r\s*(\d+)\s+c\s*(\d+)\s*=(.*)$", re.S)


def parse_cell_spec(spec: str) -> tuple[int, int, int, str]:
    m = CELL_SPEC_RE.match(spec)
    if not m:
        raise FillError(f"--cell 형식은 '표<i> r<row> c<col>=값' 입니다: {spec!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def find_cell(tables: list, table_index: int, row: int, col: int) -> Cell:
    tbl = next((t for t in tables if t.index == table_index), None)
    if tbl is None:
        raise FillError(f"표{table_index} 이(가) 없습니다(표 {len(tables)}개: 0~{len(tables) - 1})")
    cell = tbl.cell_at(row, col)
    if cell is None:
        rows = max((c.row_addr for c in tbl.cells), default=-1)
        cols = max((c.col_addr for c in tbl.cells), default=-1)
        raise FillError(f"표{table_index} r{row} c{col} 셀이 없습니다(r0~{rows}, c0~{cols}; 병합 셀은 왼쪽 위 좌표)")
    return cell


LABEL_STRIP_RE = re.compile(r"[\s:：]+")


def norm_label(s: str) -> str:
    """라벨 비교용 정규화 — 공백·콜론과 **sentinel** 을 뺀다.

    한컴은 셀 첫 run 에 레이아웃 컨트롤을 넣고 그림·표를 품은 셀도 있다 — 라벨은 보이는 글자로 맞춘다."""
    return LABEL_STRIP_RE.sub("", s.replace(SENTINEL, ""))


@dataclass
class LabelTarget:
    label_cell: Cell
    target: Cell
    direction: str  # 오른쪽 | 아래


def resolve_label(tables: list, label: str) -> LabelTarget:
    """라벨 셀(텍스트가 라벨과 정확히 같은 셀) → 논리 그리드의 오른쪽/아래 빈 셀. 0·2+ 매칭·span·중첩은 거부."""
    want = norm_label(label)
    if not want:
        raise FillError("--label 의 라벨이 비었습니다")
    hits = [c for t in tables for c in t.cells if norm_label(c.text) == want]
    if not hits:
        raise FillError(f"라벨 {label!r} 셀을 찾지 못했습니다(--dump 로 표 셀 텍스트를 확인하세요)")
    if len(hits) > 1:
        coords = ", ".join(c.coord for c in hits)
        raise FillError(f"라벨 {label!r} 셀이 {len(hits)}개입니다({coords}) — --cell 좌표 모드를 쓰세요")
    lc = hits[0]
    tbl = lc.table
    if tbl.has_span:
        raise FillError(f"라벨 {label!r} 의 표{tbl.index} 에 병합 셀이 있어 라벨 모드를 거부합니다 — --cell \"표{tbl.index} r c=값\" 좌표 모드를 쓰세요")
    # 중첩 표는 **양쪽 다** 거부한다 — 중첩 표를 품은 바깥 표(tbl.nested)뿐 아니라 자신이 다른 표 안에 든
    # 내부 표(tbl.parent)도. 스펙 §4 C "중첩 표는 라벨 모드에서 명시 거부"(Codex R2 F2): 내부 표는 부모 셀의
    # 논리 그리드와 좌표계가 달라 "오른쪽/아래" 가 사람이 보는 것과 어긋날 수 있다.
    if tbl.nested or tbl.parent is not None:
        where = "중첩 표가 있어" if tbl.nested else "이 표가 다른 표 안의 중첩 표라"
        raise FillError(f"라벨 {label!r} 의 표{tbl.index} 에 {where} 라벨 모드를 거부합니다 — --cell 좌표 모드를 쓰세요")
    right = tbl.cell_at(lc.row_addr, lc.col_addr + lc.col_span)
    if right is not None and right.is_empty and right.paras:
        return LabelTarget(lc, right, "오른쪽")
    below = tbl.cell_at(lc.row_addr + lc.row_span, lc.col_addr)
    if below is not None and below.is_empty and below.paras:
        return LabelTarget(lc, below, "아래")
    what = []
    if right is not None:
        what.append(f"오른쪽 {right.coord}={show(right.text)!r}")
    if below is not None:
        what.append(f"아래 {below.coord}={show(below.text)!r}")
    raise FillError(f"라벨 {label!r}({lc.coord}) 의 오른쪽·아래 셀이 비어 있지 않습니다({'; '.join(what) or '셀 없음'}) — --cell 좌표 모드를 쓰세요")


def strip_lineseg_edits(sec: Section, ordinals: set[int]) -> list[Edit]:
    """변경된 문단의 <hp:linesegarray>…</hp:linesegarray>(self-closing 포함) 제거."""
    return [Edit(p.lineseg[0], p.lineseg[1], "") for p in sec.paras if p.ordinal in ordinals and p.lineseg]


def rescan(xml: str, table_base: int, para_base: int) -> Section:
    return scan_section(xml, table_base=table_base, para_base=para_base)


def warn(msg: str) -> None:
    print(f"경고: {msg}", file=sys.stderr)


__all__ = [
    "Edit",
    "FillError",
    "ControlInvariantError",
    "FillReport",
    "CellFillResult",
    "LabelTarget",
    "apply_edits",
    "assert_control_invariant",
    "fill_texts",
    "fill_cell",
    "find_cell",
    "parse_cell_spec",
    "resolve_label",
    "show",
    "splice_span",
    "strip_lineseg_edits",
    "tick_items",
    "value_to_xml",
    "T_TAG",
]
