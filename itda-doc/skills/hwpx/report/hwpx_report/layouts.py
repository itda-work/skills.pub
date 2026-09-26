"""템플릿별 조판(layout) — 본문 XML 조립을 템플릿 manifest 의 `layout` 값으로 갈라 맡는다 (#1651).

- `report`(기본): 제목 박스 + □/❍ 개조식 — `report.build_report_body_xml` 이 그대로 담당한다.
- `official-letter`: 기안문. 상단 기관명 → 수신·(경유)·제목 → 항목기호 4단(1. 가. 1) 가))
  본문 → 붙임 → "끝." → 발신명의 → 하단 시행 정보. 항목기호·2타 들여쓰기·날짜 표기·붙임/끝
  규칙은 「행정업무의 운영 및 혁신에 관한 규정」 시행규칙의 서식 원칙을 우리 문장으로 옮긴 것.
- `briefing`: 내부 보고서. 표지(기관명·제목·작성일) → 목차 → 본문 제목 → 섹션마다 로마숫자
  섹션바(1×3 표) + □ ○ ― ※ 4단 개조식.

외부 공개 스킬(gonggong_hwpxskills)에서 얻은 것은 위 **양식 구조**뿐이고, XML·수치·팔레트·
조립 로직은 전부 여기서 새로 정했다. 템플릿 스타일 이름은 각 style-map.json 이 소유한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .models import DocSpec, ReportBlock, ReportItem, ReportSection, ReportTable
from .profile import ImageEntry, xml_escape
from .writecontext import WriteContext

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
HANGUL_ORDER = list("가나다라마바사아자차카타파하")

# 기안문 항목기호 4단 (시행규칙: 1. → 가. → 1) → 가) → (1) → (가) → ① → ㉮ 중 앞 4단만 지원)
OFFICIAL_MARKERS = ("digit-dot", "hangul-dot", "digit-paren", "hangul-paren")
# 내부 보고서 4단 기호
BRIEFING_MARKERS = ("□", "○", "―", "※")


def roman(n: int) -> str:
    return ROMAN[n - 1] if 1 <= n <= len(ROMAN) else str(n)


def hangul(n: int) -> str:
    return HANGUL_ORDER[n - 1] if 1 <= n <= len(HANGUL_ORDER) else str(n)


def official_marker(level: int, n: int) -> str:
    kind = OFFICIAL_MARKERS[level - 1]
    if kind == "digit-dot":
        return f"{n}."
    if kind == "hangul-dot":
        return f"{hangul(n)}."
    if kind == "digit-paren":
        return f"{n})"
    return f"{hangul(n)})"


def format_official_date(value: str) -> str:
    """공문서 날짜: 연·월·일 대신 온점, 월·일 앞 0 없음 — `2026. 9. 6.`"""
    from .report import parse_report_date

    parsed = parse_report_date(value.strip()) if value.strip() else None
    if parsed is None:
        if value.strip():
            return value.strip()
        parsed = date.today()
    return f"{parsed.year}. {parsed.month}. {parsed.day}."


@dataclass
class _Style:
    charPrIDRef: str
    paraPrIDRef: str
    borderFillIDRef: str = ""


def paragraph(ctx: WriteContext, style: _Style, text: str, *, page_break: bool = False) -> str:
    pb = "1" if page_break else "0"
    body = f"<hp:t>{xml_escape(text)}</hp:t>" if text else "<hp:t/>"
    return (
        f'<hp:p id="{ctx.paragraph_id()}" styleIDRef="0" paraPrIDRef="{xml_escape(style.paraPrIDRef)}" '
        f'pageBreak="{pb}" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{xml_escape(style.charPrIDRef)}">{body}</hp:run></hp:p>'
    )


def _flatten(section: ReportSection) -> list[ReportBlock]:
    """items/tables 분리형과 blocks 순서형을 한 시퀀스로 통일한다."""
    if section.blocks:
        return list(section.blocks)
    blocks = [ReportBlock(item=item) for item in section.items]
    blocks += [ReportBlock(table=table) for table in section.tables]
    return blocks


# ── 번호 붙이기: 같은 부모 아래 형제 수를 세어, 형제가 하나뿐이면 기호를 생략한다(시행규칙) ──


def number_items(items: list[ReportItem], max_level: int) -> list[tuple[ReportItem, int, int]]:
    """각 항목에 (항목, 형제 순번, 형제 총수) 를 붙인다.

    형제 = 직전 상위 항목(level 이 더 작은 가장 가까운 앞 항목) 아래의 같은 level 항목들.
    형제 총수가 1 이면 호출부가 항목기호를 생략한다(시행규칙: 항목이 하나만 있으면 기호 미부여).
    """
    parent_key: list[tuple[int, int]] = []
    stack: list[tuple[int, int]] = []  # (level, index)
    for index, item in enumerate(items):
        level = min(max(item.level, 1), max_level)
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else -1
        parent_key.append((parent, level))
        stack.append((level, index))
    totals: dict[tuple[int, int], int] = {}
    for key in parent_key:
        totals[key] = totals.get(key, 0) + 1
    running: dict[tuple[int, int], int] = {}
    result: list[tuple[ReportItem, int, int]] = []
    for item, key in zip(items, parent_key):
        running[key] = running.get(key, 0) + 1
        result.append((item, running[key], totals[key]))
    return result


# ── official-letter ────────────────────────────────────────────────────────────


def build_official_letter(tmpl, spec: DocSpec, render_table, render_image) -> tuple[str, list[ImageEntry]]:
    st = tmpl.style
    ctx = WriteContext()
    parts: list[str] = []
    images: list[ImageEntry] = []
    img_idx = 1
    fields = spec.fields
    max_level = int(tmpl.manifest.get("max_level", 4))

    org = fields.get("org", "").strip()
    if org:
        parts.append(paragraph(ctx, st("org"), org))
    receiver = fields.get("receiver", "").strip()
    parts.append(paragraph(ctx, st("line"), f"수신  {receiver}" if receiver else "수신  내부결재"))
    via = fields.get("via", "").strip()
    parts.append(paragraph(ctx, st("line"), f"(경유)  {via}" if via else "(경유)"))
    parts.append(paragraph(ctx, st("label"), f"제목  {spec.title.strip()}"))
    parts.append(paragraph(ctx, st("blank"), ""))

    # 섹션 제목이 있으면 1단계 항목으로 승격하고 그 아래 항목을 한 단계 내린다.
    flat_items: list[ReportItem] = []
    ordered_blocks: list[tuple[str, object]] = []
    for section in spec.sections:
        shift = 0
        if section.heading.strip():
            head = ReportItem(level=1, text=section.heading.strip())
            flat_items.append(head)
            ordered_blocks.append(("item", head))
            shift = 1
        for block in _flatten(section):
            if block.item is not None:
                item = ReportItem(level=min(block.item.level + shift, max_level), text=block.item.text)
                flat_items.append(item)
                ordered_blocks.append(("item", item))
            elif block.table is not None:
                ordered_blocks.append(("table", block.table))
            elif block.image is not None:
                ordered_blocks.append(("image", block.image))
    for table in spec.tables:
        ordered_blocks.append(("table", table))

    numbering = {id(item): (n, total) for item, n, total in number_items(flat_items, max_level)}
    body_parts: list[str] = []
    last_kind = ""
    for kind, obj in ordered_blocks:
        if kind == "item":
            item: ReportItem = obj  # type: ignore[assignment]
            n, total = numbering[id(item)]
            marker = official_marker(item.level, n) + " " if total > 1 else ""
            body_parts.append(paragraph(ctx, st(f"level{item.level}"), marker + item.text.strip()))
        elif kind == "table":
            body_parts.append(render_table(ctx, obj, tmpl))
        else:
            rendered, entry = render_image(ctx, obj, img_idx, st("level1").charPrIDRef)
            img_idx += 1
            images.append(entry)
            body_parts.append(rendered)
        last_kind = kind

    attachments = [a.strip() for a in spec.attachments if a.strip()]
    if attachments:
        parts.extend(body_parts)
        lines = []
        if len(attachments) == 1:
            lines.append(f"붙임  {attachments[0]}")
        else:
            # 둘째 줄부터는 문단 내어쓰기(left=intent)가 "붙임  " 폭만큼 맞춰 준다 — 선행 공백을 넣으면 이중 들여쓰기(한컴 실렌더 #1651)
            lines = [f"붙임  {i}. {a}" if i == 1 else f"{i}. {a}" for i, a in enumerate(attachments, 1)]
        lines[-1] = lines[-1] + "  끝."
        for i, line in enumerate(lines):
            parts.append(paragraph(ctx, st("attachment" if i == 0 else "attachment_more"), line))
    elif body_parts:
        if last_kind == "item":
            # 본문 마지막 글자에서 2타 띄우고 "끝." — 마지막 문단 텍스트에 이어 붙인다
            body_parts[-1] = body_parts[-1].replace("</hp:t></hp:run></hp:p>", "  끝.</hp:t></hp:run></hp:p>", 1)
            parts.extend(body_parts)
        else:
            # 표·이미지로 끝나면 그 아래 왼쪽 기본선에서 2타 띄우고 "끝."
            parts.extend(body_parts)
            parts.append(paragraph(ctx, st("line"), "  끝."))
    else:
        parts.append(paragraph(ctx, st("line"), "  끝."))

    sender = fields.get("sender", "").strip()
    if sender:
        parts.append(paragraph(ctx, st("blank"), ""))
        parts.append(paragraph(ctx, st("sender"), sender))

    # 별지 제1호서식 비고: 기안자·검토자·결재권자·협조자 **용어는 표시하지 않고** 그 내용(직위 성명)만 적는다.
    # 값은 "사무관 김서준" 처럼 직위+성명으로 받는 것이 정본이며, 성명만 와도 그대로 싣는다.
    signers = [fields.get(key, "").strip() for key in ("drafter", "reviewer", "approver")]
    signers = [s for s in signers if s]
    if signers:
        parts.append(paragraph(ctx, st("footer_info"), "   ".join(signers)))
    cooperator = fields.get("cooperator", "").strip()
    if cooperator:
        parts.append(paragraph(ctx, st("footer_info"), f"협조자  {cooperator}"))
    doc_no = fields.get("doc_no", "").strip()
    stamp = format_official_date(spec.report_date)
    # 서식: `시행  처리과명-일련번호(시행일)` — 괄호는 붙여 쓴다(참조 문서 §관련 근거와 같은 표기)
    parts.append(paragraph(ctx, st("footer_info"), f"시행  {doc_no}({stamp})" if doc_no else f"시행  ({stamp})"))
    contact = [fields.get("address", "").strip(), fields.get("phone", "").strip(), fields.get("email", "").strip()]
    contact_line = " / ".join(x for x in contact if x)
    disclosure = fields.get("disclosure", "").strip()
    if disclosure:
        contact_line = (contact_line + " / " if contact_line else "") + f"공개 구분  {disclosure}"
    if contact_line:
        parts.append(paragraph(ctx, st("footer_info"), contact_line))
    return "".join(parts), images


# ── briefing ───────────────────────────────────────────────────────────────────


def _bar_cell(ctx: WriteContext, style: _Style, text: str, col: int, width: int, height: int) -> str:
    body = f"<hp:t>{xml_escape(text)}</hp:t>" if text else "<hp:t/>"
    return (
        f'<hp:tc name="" header="0" hasMargin="1" protect="0" editable="0" dirty="0" borderFillIDRef="{xml_escape(style.borderFillIDRef)}">'
        '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="{ctx.paragraph_id()}" paraPrIDRef="{xml_escape(style.paraPrIDRef)}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{xml_escape(style.charPrIDRef)}">{body}</hp:run></hp:p></hp:subList>'
        f'<hp:cellAddr colAddr="{col}" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>'
    )


def section_bar(ctx: WriteContext, tmpl, numeral: str, title: str, *, width: int = 47849, height: int = 2600) -> str:
    """로마숫자(남색) + 간격 + 제목(연회색) 1×3 표. 본문 폭에 맞춘다."""
    st = tmpl.style
    num_w, gap_w = 3600, 700
    title_w = width - num_w - gap_w
    container = st("bar_container").borderFillIDRef or "1"
    cells = (
        _bar_cell(ctx, st("bar_num"), numeral, 0, num_w, height)
        + _bar_cell(ctx, st("bar_gap"), "", 1, gap_w, height)
        + _bar_cell(ctx, st("bar_title"), title, 2, title_w, height)
    )
    tbl = (
        f'<hp:tbl id="{ctx.paragraph_id()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
        f'lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" rowCnt="1" colCnt="3" cellSpacing="0" '
        f'borderFillIDRef="{xml_escape(container)}" noAdjust="1">'
        f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="141" right="141" top="283" bottom="283"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
        f"<hp:tr>{cells}</hp:tr></hp:tbl>"
    )
    return (
        f'<hp:p id="{ctx.paragraph_id()}" styleIDRef="0" paraPrIDRef="{xml_escape(st("blank").paraPrIDRef)}" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{xml_escape(st("blank").charPrIDRef)}">{tbl}<hp:t/></hp:run></hp:p>'
    )


def briefing_item_text(level: int, text: str) -> str:
    marker = BRIEFING_MARKERS[min(max(level, 1), 4) - 1]
    stripped = text.strip()
    if stripped.startswith(marker):
        return stripped
    return f"{marker} {stripped}"


def build_briefing(tmpl, spec: DocSpec, render_table, render_image) -> tuple[str, list[ImageEntry]]:
    st = tmpl.style
    ctx = WriteContext()
    parts: list[str] = []
    images: list[ImageEntry] = []
    img_idx = 1
    max_level = int(tmpl.manifest.get("max_level", 4))
    title = spec.title.strip() or "보고서 제목"
    org = spec.fields.get("org", "").strip()

    # 1쪽 표지 — 위·아래 여백은 빈 문단으로 잡는다(레이아웃 엔진이 없으므로 결정론 수치).
    # 빈 줄 수는 한컴 실렌더로 맞췄다(#1651): 6+8 이면 작성일이 2쪽으로 밀렸다.
    parts.append(paragraph(ctx, st("blank"), ""))
    for _ in range(4):
        parts.append(paragraph(ctx, st("cover_title"), ""))
    if org:
        parts.append(paragraph(ctx, st("cover_org"), org))
    parts.append(paragraph(ctx, st("cover_title"), title))
    for _ in range(5):
        parts.append(paragraph(ctx, st("cover_title"), ""))
    parts.append(paragraph(ctx, st("cover_date"), format_official_date(spec.report_date)))

    # 2쪽 목차 — 섹션 제목에서 생성. 쪽번호는 레이아웃 엔진이 없어 싣지 않는다(정직성).
    headings = [s.heading.strip() for s in spec.sections if s.heading.strip()]
    parts.append(paragraph(ctx, st("toc_title"), "목  차", page_break=True))
    parts.append(paragraph(ctx, st("blank"), ""))
    for i, heading in enumerate(headings, 1):
        parts.append(paragraph(ctx, st("toc_item"), f"{roman(i)}. {heading}"))
    attachments = [a.strip() for a in spec.attachments if a.strip()]
    if attachments:
        parts.append(paragraph(ctx, st("blank"), ""))
        parts.append(paragraph(ctx, st("toc_item"), "[붙 임]"))
        for i, a in enumerate(attachments, 1):
            parts.append(paragraph(ctx, st("toc_item"), f"  {i}. {a}"))

    # 3쪽~ 본문
    parts.append(paragraph(ctx, st("doc_title"), title, page_break=True))
    parts.append(paragraph(ctx, st("blank"), ""))
    numeral_idx = 0
    for section in spec.sections:
        heading = section.heading.strip()
        if heading:
            numeral_idx += 1
            parts.append(section_bar(ctx, tmpl, roman(numeral_idx), heading))
        for block in _flatten(section):
            if block.item is not None:
                level = min(max(block.item.level, 1), max_level)
                parts.append(paragraph(ctx, st(f"level{level}"), briefing_item_text(level, block.item.text)))
            elif block.table is not None:
                parts.append(render_table(ctx, block.table, tmpl))
            elif block.image is not None:
                rendered, entry = render_image(ctx, block.image, img_idx, st("level1").charPrIDRef)
                img_idx += 1
                images.append(entry)
                parts.append(rendered)
    for table in spec.tables:
        parts.append(render_table(ctx, table, tmpl))
    return "".join(parts), images


LAYOUTS = {
    "official-letter": build_official_letter,
    "briefing": build_briefing,
}


# ── ai-report (행정안전부 AI 친화적 보고서 원칙, 2026-08-24) ─────────────────────
# 원칙: ① 표·그림은 상단에 제목·번호, 셀 병합 최소, 표 안의 표 금지 ② 문장은 서술식,
# 항목 표시 표준화(Ⅰ. 1. 가. 1) 가)), 불필요한 시각적 꾸미기 지양. 제목 박스·섹션 바 같은
# 장식 표를 두지 않고 텍스트만으로 구조를 드러낸다.

AI_SYMBOL_MARKERS = ("○", "-", "·")


def ai_item_marker(level: int, n: int, style: str, numbering: str = "digit") -> str:
    """항목 표시. `outline` 은 행안부 표준 체계(Ⅰ. 1. 가. 1) 가))에 맞춰 절 번호 축에 따라 시작점이 다르다:
    절이 `Ⅰ.` 이면 항목은 `1.` 부터, 절이 `1.` 이면 항목은 `가.` 부터 (#1652 D6)."""
    if style == "outline":
        offset = 0 if numbering == "roman" else 1
        return official_marker(level + offset, n)
    return AI_SYMBOL_MARKERS[min(max(level, 1), 3) - 1]


_CAPTION_NUMBERED = re.compile(r"^(표|그림)\s*\d+\s*[.:]\s*")


def caption_text(kind: str, index: int, caption: str) -> str:
    """`< 표 1. 제목 >` — 번호는 등장 순서로 **항상 엔진이 매긴다**. 사용자가 `표 7.` 처럼 번호를 썼으면
    그 번호는 벗기고 자동 번호로 바꾼다(매퍼가 불일치를 경고). `표준`·`그림자` 처럼 낱말이 "표"로 시작하는
    제목은 번호 표기가 아니다(#1652 D1·D2 — 구 판정 `startswith(kind)` 의 오탐)."""
    text = caption.strip().strip("<>").strip()
    text = _CAPTION_NUMBERED.sub("", text).strip()
    return f"< {kind} {index}. {text} >" if text else f"< {kind} {index} >"


_HEADING_NUMBERED = re.compile(r"^(\d+\.|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+\.)\s+")


def build_ai_report(tmpl, spec: DocSpec, render_table, render_image) -> tuple[str, list[ImageEntry]]:
    st = tmpl.style
    ctx = WriteContext()
    parts: list[str] = []
    images: list[ImageEntry] = []
    max_level = int(tmpl.manifest.get("max_level", 3))
    marker_style = spec.fields.get("item_markers", "symbol").strip() or "symbol"
    numbering = spec.fields.get("section_numbering", "digit").strip() or "digit"

    parts.append(paragraph(ctx, st("doc_title"), spec.title.strip() or "보고서 제목"))
    meta = [spec.fields.get("report_type", "").strip(), format_official_date(spec.report_date)]
    who = " ".join(x for x in (spec.dept.strip(), spec.fields.get("drafter", "").strip()) if x)
    if who:
        meta.append(who)
    parts.append(paragraph(ctx, st("meta"), " / ".join(x for x in meta if x)))

    table_no = 0
    image_no = 0
    img_idx = 1
    section_no = 0
    headings = [s.heading.strip() for s in spec.sections if s.heading.strip()]
    numbered_flags = [bool(_HEADING_NUMBERED.match(h)) for h in headings]
    # 절 번호 체계는 하나여야 한다. 사용자가 **전부** 번호를 썼으면 그대로 두고, 일부만 썼으면(혼재)
    # 사용자 번호를 벗기고 전부 자동으로 매긴다 — 구 구현은 혼재 시 `Ⅰ. → 1. → Ⅲ.` 로 번호가 튀었다(#1652 D5).
    keep_user_numbers = bool(headings) and all(numbered_flags)
    for section in spec.sections:
        heading = section.heading.strip()
        if heading:
            section_no += 1
            if keep_user_numbers:
                shown = heading
            else:
                bare = _HEADING_NUMBERED.sub("", heading)
                shown = (f"{roman(section_no)}. " if numbering == "roman" else f"{section_no}. ") + bare
            parts.append(paragraph(ctx, st("heading"), shown))
        blocks = _flatten(section)
        items_only = [b.item for b in blocks if b.item is not None and b.item.kind == "item"]
        numbered = {id(item): n for item, n, _ in number_items(items_only, max_level)}
        for block in blocks:
            if block.item is not None:
                item = block.item
                if item.kind == "prose":
                    parts.append(paragraph(ctx, st("prose"), item.text.strip()))
                    continue
                level = min(max(item.level, 1), max_level)
                marker = ai_item_marker(level, numbered[id(item)], marker_style, numbering)
                parts.append(paragraph(ctx, st(f"level{level}"), f"{marker} {item.text.strip()}"))
            elif block.table is not None:
                table_no += 1
                parts.append(paragraph(ctx, st("caption"), caption_text("표", table_no, block.table.caption)))
                parts.append(render_table(ctx, block.table, tmpl))
            elif block.image is not None:
                image_no += 1
                parts.append(paragraph(ctx, st("caption"), caption_text("그림", image_no, block.image.caption or block.image.alt)))
                rendered, entry = render_image(ctx, block.image, img_idx, st("level1").charPrIDRef)
                img_idx += 1
                images.append(entry)
                parts.append(rendered)
    for table in spec.tables:
        table_no += 1
        parts.append(paragraph(ctx, st("caption"), caption_text("표", table_no, table.caption)))
        parts.append(render_table(ctx, table, tmpl))
    return "".join(parts), images


LAYOUTS["ai-report"] = build_ai_report
