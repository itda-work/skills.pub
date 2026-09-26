#!/usr/bin/env python3
"""참고 .hwpx 의 서식을 **프로파일(템플릿 디렉토리)** 로 추출한다 — 기존 조판이 그 서식으로 돈다 (#1652 P1 E).

    python3 derive_profile.py analyze ref.hwpx -o profile/ [--layout ai-report|report] [--id 이름] [--strict]
    python3 derive_profile.py compare profile/ out.hwpx [--ref ref.hwpx]

analyze — 참고 문서의 `header.xml` 을 그대로 가져오고(글꼴·charPr·paraPr·borderFill 정의), 본문 최상위 문단을
마커(□ ○ ― ※ · 1. 가. Ⅰ.)와 굵기·크기로 층위 분류해 층위별 **최빈 (paraPrIDRef, charPrIDRef)** 을 우리
style-map 이름에 대응시킨다. 첫 문단의 secPr(용지·여백·단)은 보존하고 거기 붙은 표·그림 개체는 뗀다.
데이터 표 하나에서 표 서식을 뽑아 `tables/basic.xml` 로 쓴다. 못 채운 이름은 **내장(gov-report/ai-report)
계량값을 참고 문서의 본문 글꼴로 합성**해 header 끝에 덧붙이고(id 유효성 유지) stderr 경고 + manifest `fallback`.

1차 범위는 **단일 섹션 본문 스타일 근사**다 — 다중 섹션·머리말/꼬리말·마스터페이지·표지·결재란은
사전검사에서 경고하고 본문 서식만 채택한다(개체 프로토타입은 `objects/` 에 떼어 두되 조판에 쓰지 않는다).

compare — 산출 hwpx 의 header/section 에서 **속성**(용지·여백·글꼴 이름·크기·굵기·정렬·들여쓰기·표 폭·셀 테두리)
을 읽어 참고 문서(`--ref`, 없으면 manifest 에 기록된 기대값)와 대조한다. 판정은 JSON + exit code(0 일치 · 2 불일치 ·
1 오류). 프로파일 style-map 을 다른 값으로 바꾸면 RED 여야 한다(no-op 이면 통과하는 게이트는 게이트가 아니다).

표준 라이브러리만 쓴다. 외부 저장소(jkf87/hwpx-skill, MIT) 의 `doc_spec analyze` 는 분해 관점(header 재사용 +
section 재조판, 첫 문단 secPr 보존, 배너 vs 콘텐츠 표 구분)만 참고했고 코드는 새로 썼다 — 외부 소스 미복제.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("python 3.10+ 가 필요합니다")

REPORT_DIR = Path(__file__).resolve().parent.parent
if str(REPORT_DIR) not in sys.path:
    sys.path.insert(0, str(REPORT_DIR))

from hwpx_report.models import DocSpec  # noqa: E402
from hwpx_report.profile import OWPML_NS  # noqa: E402
from hwpx_report.report import HWPXReportError, build_report, load_report_template_dir  # noqa: E402

SUPPORTED_LAYOUTS = ("ai-report", "report")

# ── 문단 마커 분류 ─────────────────────────────────────────────────────────────
ROMAN_CHARS = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
HANGUL_ORDER = "가나다라마바사아자차카타파하"
_KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("caption", re.compile(r"^[<＜〈\[［]\s*(표|그림)\s*\d")),
    ("caption", re.compile(r"^(표|그림)\s*\d+\s*[.:：]")),
    ("roman", re.compile(rf"^[{ROMAN_CHARS}]+\s*[.．]")),
    ("digit", re.compile(r"^\d{1,2}\s*[.．](?![\d.])")),
    ("hangul", re.compile(rf"^[{HANGUL_ORDER}]\s*[.．]")),
    ("digit_paren", re.compile(r"^\(?\d{1,2}\)")),
    ("hangul_paren", re.compile(rf"^\(?[{HANGUL_ORDER}]\)")),
    ("circled", re.compile(r"^[①-⑳㉮-㉻]")),
    ("square", re.compile(r"^[□■☐▣]")),
    ("circle", re.compile(r"^[○●◦ㅇ◎❍◯]")),
    ("dash", re.compile(r"^[―–—‒-]\s")),
    ("dot", re.compile(r"^[·•ㆍ‧∙]")),
    ("ref", re.compile(r"^※")),
    ("arrow", re.compile(r"^[⇒→▶▷►☞]")),
    ("diamond", re.compile(r"^[◇◆]")),
]
# 항목 사다리(들여쓰기 같으면 이 순서) — 제목축(roman/digit)은 사다리 끝
_LADDER_RANK = ["square", "circle", "hangul", "digit_paren", "hangul_paren", "circled", "dash", "dot", "diamond", "arrow", "ref", "digit", "roman"]
_BRACKET_CAPTION = re.compile(r"^[<＜〈].{1,60}[>＞〉]$")

# 조판별 style-map 이름 — layouts.py / report.py / table.py 가 실제로 조회하는 이름 전부
LAYOUT_STYLE_NAMES: dict[str, list[str]] = {
    "ai-report": ["heading", "heading_spacer", "body_box", "blank", "doc_title", "meta", "level1", "level2", "level3", "prose", "caption"],
    "report": ["heading", "heading_spacer", "body_box", "blank", "doc_title", "meta"],
}
TABLE_STYLE_NAMES = ["table_header", "table_body", "table_body_justify", "table_body_left", "table_body_right",
                     "table_body_bold", "table_body_italic", "table_body_bold_italic", "table_total", "table_container"]

# 폴백 계량값 — 내장 템플릿(ai-report: derive_template_headers.AI_* / gov-report: charPr 10·12·13·25 + paraPr 2·22·14)
# 의 크기·굵기·정렬·들여쓰기. 글꼴은 참고 문서의 본문 글꼴을 쓴다(header 안에서 id 유효성을 지키기 위해).
# (height, bold, align, left, intent, prev, next, line)
_FALLBACK: dict[str, dict[str, tuple[int, bool, str, int, int, int, int, int]]] = {
    "ai-report": {
        "doc_title": (1800, True, "CENTER", 0, 0, 600, 200, 160),
        "meta": (1100, False, "CENTER", 0, 0, 0, 800, 160),
        "heading": (1400, True, "JUSTIFY", 0, 0, 900, 200, 170),
        "level1": (1300, False, "JUSTIFY", 1300, -1300, 400, 0, 175),
        "level2": (1300, False, "JUSTIFY", 2300, -1000, 250, 0, 175),
        "level3": (1200, False, "JUSTIFY", 3300, -1000, 150, 0, 175),
        "prose": (1300, False, "JUSTIFY", 0, 1300, 400, 0, 175),
        "caption": (1100, True, "CENTER", 0, 0, 500, 100, 140),
        "blank": (1100, False, "JUSTIFY", 0, 0, 0, 0, 160),
        "heading_spacer": (400, False, "JUSTIFY", 0, 0, 0, 0, 160),
    },
    "report": {
        "doc_title": (2000, True, "CENTER", 0, 0, 600, 200, 160),
        "meta": (1400, False, "RIGHT", 0, 0, 0, 0, 110),
        "heading": (1600, False, "JUSTIFY", 0, 0, 0, 0, 160),
        "body_box": (1500, False, "JUSTIFY", 0, 0, 1000, 0, 160),
        "blank": (1100, False, "JUSTIFY", 0, 0, 0, 0, 160),
        "heading_spacer": (400, False, "JUSTIFY", 0, 0, 0, 0, 160),
    },
}
# gov-report tables/basic.xml 의 구조 계량값(행 높이·머리글 채움색·테두리)
_TABLE_FALLBACK = {"header_h": 2363, "body_h": 1984, "header_fill": "#D9D9D9", "border_width": "0.12 mm"}


class ProfileError(Exception):
    pass


# ── header.xml 모델 ────────────────────────────────────────────────────────────


FONT_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")


@dataclass
class CharPr:
    id: str
    height: int
    font: str  # hangul font id
    bold: bool
    italic: bool
    color: str
    border_fill: str
    xml: str
    fonts: dict = field(default_factory=dict)  # 언어별 fontRef id (hangul/latin/hanja/japanese/other/symbol/user)


@dataclass
class ParaPr:
    id: str
    align: str
    intent: int
    left: int
    right: int
    prev: int
    next: int
    line_type: str
    line_value: int
    border_fill: str
    tab_pr: str
    xml: str


@dataclass
class BorderFill:
    id: str
    sides: tuple[str, str, str, str]  # left right top bottom types
    fill: str  # faceColor or ""
    xml: str


@dataclass
class HeaderInfo:
    xml: str
    fonts: dict[str, str]  # HANGUL font id -> face
    char: dict[str, CharPr]
    para: dict[str, ParaPr]
    border: dict[str, BorderFill]
    faces: dict[str, dict[str, str]] = field(default_factory=dict)  # 언어(HANGUL/LATIN/…) -> {font id: face}

    def resolve_fonts(self, base: "CharPr | None", hangul: str) -> dict[str, str]:
        """폴백 charPr 이 쓸 **언어별** fontRef id — font id 공간은 언어별로 따로다(Codex R2 F5).

        hangul id 하나를 7개 언어에 그대로 복사하면 그 id 가 다른 언어 fontface 에 없을 때
        존재하지 않는 fontRef 가 생긴다. 본문 기준 charPr(base)의 언어별 값을 우선 쓰고,
        없으면 그 언어 fontface 에 **실재하는** id 로 떨어진다."""
        out: dict[str, str] = {}
        for lang in FONT_LANGS:
            avail = self.faces.get(lang.upper(), {})
            candidates = []
            if base is not None and base.fonts.get(lang):
                candidates.append(base.fonts[lang])
            candidates.append(hangul)
            pick = next((c for c in candidates if c in avail), None)
            if pick is None:
                pick = min(avail, key=lambda i: int(i) if i.isdigit() else 0) if avail else hangul
            out[lang] = pick
        return out

    def char_attrs(self, cid: str) -> dict:
        c = self.char.get(cid)
        if c is None:
            return {"missing": f"charPr {cid}"}
        return {"font": self.fonts.get(c.font, f"#{c.font}"), "height": c.height, "bold": c.bold, "italic": c.italic}

    def para_attrs(self, pid: str) -> dict:
        p = self.para.get(pid)
        if p is None:
            return {"missing": f"paraPr {pid}"}
        return {"align": p.align, "left": p.left, "intent": p.intent, "prev": p.prev, "next": p.next,
                "line": f"{p.line_type}:{p.line_value}"}

    def border_attrs(self, bid: str) -> dict:
        b = self.border.get(bid)
        if b is None:
            return {"missing": f"borderFill {bid}"}
        return {"sides": "/".join(b.sides), "fill": b.fill}

    def pair_attrs(self, para_id: str, char_id: str) -> dict:
        return {**self.para_attrs(para_id), **self.char_attrs(char_id)}


_INT = r"-?\d+"


def _attr(tag: str, name: str, default: str = "") -> str:
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return m.group(1) if m else default


def _int_attr(tag: str, name: str, default: int = 0) -> int:
    try:
        return int(_attr(tag, name, str(default)))
    except ValueError:
        return default


def parse_header(xml: str) -> HeaderInfo:
    faces: dict[str, dict[str, str]] = {}
    for fm in re.finditer(r'<hh:fontface\b([^>]*)>(.*?)</hh:fontface>', xml, re.S):
        lang = _attr(fm.group(1), "lang", "")
        block = faces.setdefault(lang, {})
        for m in re.finditer(r'<hh:font\b([^>]*)>', fm.group(2)):
            block[_attr(m.group(1), "id")] = _attr(m.group(1), "face")
    fonts: dict[str, str] = dict(faces.get("HANGUL", {}))
    chars: dict[str, CharPr] = {}
    for m in re.finditer(r'<hh:charPr\b[^>]*?/>|<hh:charPr\b.*?</hh:charPr>', xml, re.S):
        frag = m.group(0)
        open_tag = re.match(r"<hh:charPr\b[^>]*>", frag).group(0)
        cid = _attr(open_tag, "id")
        ref = re.search(r"<hh:fontRef\b[^>]*>", frag)
        lang_fonts = {lang: _attr(ref.group(0), lang, "") for lang in FONT_LANGS} if ref else {}
        chars[cid] = CharPr(
            id=cid,
            height=_int_attr(open_tag, "height", 1000),
            font=lang_fonts.get("hangul") or "0",
            bold="<hh:bold/>" in frag or "<hh:bold>" in frag,
            italic="<hh:italic/>" in frag or "<hh:italic>" in frag,
            color=_attr(open_tag, "textColor", "#000000"),
            border_fill=_attr(open_tag, "borderFillIDRef", ""),
            xml=frag,
            fonts=lang_fonts,
        )
    paras: dict[str, ParaPr] = {}
    for m in re.finditer(r'<hh:paraPr\b[^>]*?/>|<hh:paraPr\b.*?</hh:paraPr>', xml, re.S):
        frag = m.group(0)
        open_tag = re.match(r"<hh:paraPr\b[^>]*>", frag).group(0)
        pid = _attr(open_tag, "id")
        align = _attr(re.search(r"<hh:align\b[^>]*>", frag).group(0), "horizontal", "JUSTIFY") if "<hh:align" in frag else "JUSTIFY"
        # 여백은 <hp:default> 분기(HWPUNIT)를 정본으로 읽는다 — 없으면 첫 margin
        scope = re.search(r"<hp:default>(.*?)</hp:default>", frag, re.S)
        scope_xml = scope.group(1) if scope else frag

        def mval(name: str) -> int:
            mm = re.search(rf'<hc:{name}\b[^>]*value="({_INT})"', scope_xml)
            return int(mm.group(1)) if mm else 0

        ls = re.search(r'<hh:lineSpacing\b[^>]*type="(\w+)"[^>]*value="(-?\d+)"', scope_xml)
        border = re.search(r"<hh:border\b[^>]*>", frag)
        paras[pid] = ParaPr(
            id=pid, align=align, intent=mval("intent"), left=mval("left"), right=mval("right"), prev=mval("prev"),
            next=mval("next"), line_type=ls.group(1) if ls else "PERCENT", line_value=int(ls.group(2)) if ls else 160,
            border_fill=_attr(border.group(0), "borderFillIDRef", "") if border else "",
            tab_pr=_attr(open_tag, "tabPrIDRef", "0"), xml=frag,
        )
    borders: dict[str, BorderFill] = {}
    for m in re.finditer(r'<hh:borderFill\b[^>]*?/>|<hh:borderFill\b.*?</hh:borderFill>', xml, re.S):
        frag = m.group(0)
        bid = _attr(re.match(r"<hh:borderFill\b[^>]*>", frag).group(0), "id")
        sides = []
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            sm = re.search(rf"<hh:{side}\b[^>]*>", frag)
            sides.append(_attr(sm.group(0), "type", "NONE") if sm else "NONE")
        fill = re.search(r'<hc:winBrush\b[^>]*faceColor="([^"]*)"', frag)
        borders[bid] = BorderFill(id=bid, sides=tuple(sides), fill=fill.group(1) if fill else "", xml=frag)
    return HeaderInfo(xml=xml, fonts=fonts, char=chars, para=paras, border=borders, faces=faces)


def _bump_item_cnt(xml: str, tag: str, add: int) -> str:
    m = re.search(rf'<hh:{tag}\b([^>]*?)itemCnt="(\d+)"', xml)
    if not m:
        raise ProfileError(f"header.xml 에 <hh:{tag} itemCnt> 가 없다")
    new_tag = m.group(0).replace(f'itemCnt="{m.group(2)}"', f'itemCnt="{int(m.group(2)) + add}"')
    return xml.replace(m.group(0), new_tag, 1)


def append_header_items(xml: str, chars: list[str], paras: list[str], borders: list[str]) -> str:
    """header.xml 끝에 charPr/paraPr/borderFill 을 덧붙인다(기존 id 불변, itemCnt 갱신)."""
    if chars:
        xml = _bump_item_cnt(xml, "charProperties", len(chars)).replace("</hh:charProperties>", "".join(chars) + "</hh:charProperties>", 1)
    if paras:
        xml = _bump_item_cnt(xml, "paraProperties", len(paras)).replace("</hh:paraProperties>", "".join(paras) + "</hh:paraProperties>", 1)
    if borders:
        xml = _bump_item_cnt(xml, "borderFills", len(borders)).replace("</hh:borderFills>", "".join(borders) + "</hh:borderFills>", 1)
    return xml


def _ensure_namespaces(open_tag: str) -> str:
    """루트 태그에 우리 조판·헤더 합성이 쓰는 접두사가 선언돼 있게 한다(참고 문서가 빠뜨린 것만 추가)."""
    for decl in re.findall(r'xmlns:[\w-]+="[^"]+"', OWPML_NS):
        prefix = decl.split("=", 1)[0]
        if prefix + "=" not in open_tag:
            open_tag = open_tag[:-1] + " " + decl + ">"
    return open_tag


def _char_pr_xml(cid: int, base: CharPr | None, height: int, bold: bool, font: str, border_fill: str,
                 fonts: dict[str, str] | None = None) -> str:
    refs = dict(fonts) if fonts else {lang: font for lang in FONT_LANGS}
    refs["hangul"] = refs.get("hangul") or font
    ref_attrs = " ".join(f'{lang}="{refs.get(lang) or font}"' for lang in FONT_LANGS)
    bold_xml = "<hh:bold/>" if bold else ""
    return (
        f'<hh:charPr id="{cid}" height="{height}" textColor="#000000" shadeColor="none" useFontSpace="0" '
        f'useKerning="0" symMark="NONE" borderFillIDRef="{border_fill}">'
        f'<hh:fontRef {ref_attrs}/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f"{bold_xml}"
        '<hh:underline type="NONE" shape="SOLID" color="#000000"/><hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/><hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>'
    )


def _para_pr_xml(pid: int, align: str, left: int, intent: int, prev: int, next_: int, line: int, border_fill: str, tab_pr: str) -> str:
    margin = (
        f'<hh:margin><hc:intent value="{intent}" unit="HWPUNIT"/><hc:left value="{left}" unit="HWPUNIT"/>'
        f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{prev}" unit="HWPUNIT"/><hc:next value="{next_}" unit="HWPUNIT"/></hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{line}" unit="HWPUNIT"/>'
    )
    return (
        f'<hh:paraPr id="{pid}" tabPrIDRef="{tab_pr}" condense="0" fontLineHeight="0" snapToGrid="0" suppressLineNumbers="0" checked="0">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/><hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        f'<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case><hp:default>{margin}</hp:default></hp:switch>'
        f'<hh:border borderFillIDRef="{border_fill}" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>'
    )


def _border_fill_xml(bid: int, fill: str | None) -> str:
    w = _TABLE_FALLBACK["border_width"]
    sides = "".join(f'<hh:{n} type="SOLID" width="{w}" color="#000000"/>' for n in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"))
    brush = f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#000000" alpha="0"/></hc:fillBrush>' if fill else ""
    return (
        f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f'{sides}<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>{brush}</hh:borderFill>'
    )


# ── section0.xml 모델 ──────────────────────────────────────────────────────────

_T_RE = re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", re.S)
_INNER_TAG = re.compile(r"<[^>]+>")


def text_of(frag: str) -> str:
    return "".join(html.unescape(_INNER_TAG.sub("", t)) for t in _T_RE.findall(frag))


def _iter_outermost(inner: str, open_pat: str, close_pat: str):
    """깊이 추적으로 최상위(바깥) 요소 조각을 (start, end, xml) 로 산출한다 — 표 안 문단·표 안 표를 건너뛴다."""
    tok = re.compile(rf"{open_pat}|{close_pat}")
    depth = 0
    start = 0
    for m in tok.finditer(inner):
        is_open = not m.group(0).startswith("</")
        if is_open:
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                yield start, m.end(), inner[start:m.end()]
            if depth < 0:
                depth = 0


def iter_paragraph_blocks(inner: str):
    return _iter_outermost(inner, r"<hp:p\b", r"</hp:p>")


def iter_tables(frag: str):
    return _iter_outermost(frag, r"<hp:tbl\b", r"</hp:tbl>")


@dataclass
class CellInfo:
    row: int
    col: int
    border_fill: str
    para: str
    char: str
    width: int
    height: int
    row_span: int
    col_span: int
    text: str


@dataclass
class TableInfo:
    xml: str
    rows: int
    cols: int
    border_fill: str
    width: int
    text: str
    cells: list[CellInfo]
    behind_text: bool

    @property
    def merged(self) -> bool:
        return any(c.row_span > 1 or c.col_span > 1 for c in self.cells)


def parse_table(frag: str) -> TableInfo:
    open_tag = re.match(r"<hp:tbl\b[^>]*>", frag).group(0)
    body = frag[len(open_tag):]
    # 중첩 표는 지운 뒤 셀을 읽는다
    nested = list(iter_tables(body))
    for s, e, _ in reversed(nested):
        body = body[:s] + body[e:]
    sz = re.search(r"<hp:sz\b[^>]*>", body)
    cells: list[CellInfo] = []
    for tc in re.finditer(r"<hp:tc\b[^>]*>.*?</hp:tc>", body, re.S):
        tc_xml = tc.group(0)
        tc_open = re.match(r"<hp:tc\b[^>]*>", tc_xml).group(0)
        addr = re.search(r"<hp:cellAddr\b[^>]*>", tc_xml)
        span = re.search(r"<hp:cellSpan\b[^>]*>", tc_xml)
        csz = re.search(r"<hp:cellSz\b[^>]*>", tc_xml)
        p = re.search(r"<hp:p\b[^>]*>", tc_xml)
        run = re.search(r"<hp:run\b[^>]*>", tc_xml)
        cells.append(
            CellInfo(
                row=_int_attr(addr.group(0), "rowAddr") if addr else 0,
                col=_int_attr(addr.group(0), "colAddr") if addr else 0,
                border_fill=_attr(tc_open, "borderFillIDRef", ""),
                para=_attr(p.group(0), "paraPrIDRef", "") if p else "",
                char=_attr(run.group(0), "charPrIDRef", "") if run else "",
                width=_int_attr(csz.group(0), "width") if csz else 0,
                height=_int_attr(csz.group(0), "height") if csz else 0,
                row_span=_int_attr(span.group(0), "rowSpan", 1) if span else 1,
                col_span=_int_attr(span.group(0), "colSpan", 1) if span else 1,
                text=text_of(tc_xml).strip(),
            )
        )
    return TableInfo(
        xml=frag,
        rows=_int_attr(open_tag, "rowCnt"),
        cols=_int_attr(open_tag, "colCnt"),
        border_fill=_attr(open_tag, "borderFillIDRef", ""),
        width=_int_attr(sz.group(0), "width") if sz else 0,
        text="".join(c.text for c in cells),
        cells=cells,
        behind_text=_attr(open_tag, "textWrap") == "BEHIND_TEXT",
    )


@dataclass
class Block:
    index: int
    xml: str
    text: str
    para: str
    char: str
    has_secpr: bool
    has_pic: bool
    page_break: bool
    tables: list[TableInfo] = field(default_factory=list)

    @property
    def is_text(self) -> bool:
        return not self.tables and not self.has_pic and not self.has_secpr and bool(self.text.strip())

    @property
    def is_empty(self) -> bool:
        return not self.tables and not self.has_pic and not self.has_secpr and not self.text.strip()


# 그림·도형(제목 박스 rect 등)·수식·OLE 를 담은 문단은 텍스트 층위 분류에서 뺀다(개체 프로토타입 후보)
_DRAWING_RE = re.compile(r"<hp:(pic|rect|ellipse|arc|polygon|curve|line|connectLine|container|ole|equation|textart)\b")


def parse_blocks(inner: str) -> list[Block]:
    blocks: list[Block] = []
    for i, (_s, _e, frag) in enumerate(iter_paragraph_blocks(inner)):
        open_tag = re.match(r"<hp:p\b[^>]*>", frag).group(0)
        tables = [parse_table(t) for _a, _b, t in iter_tables(frag)]
        # 문단 자신의 텍스트(표 안 텍스트 제외)
        own = frag
        for _a, _b, t in reversed(list(iter_tables(frag))):
            own = own.replace(t, "", 1)
        # 텍스트가 있는 첫 run 의 charPr (secPr run 은 텍스트가 없다)
        char = ""
        for run in re.finditer(r"<hp:run\b[^>]*>(.*?)</hp:run>", own, re.S):
            if text_of(run.group(1)).strip():
                char = _attr(run.group(0), "charPrIDRef", "")
                break
        if not char:
            first_run = re.search(r"<hp:run\b[^>]*>", own)
            char = _attr(first_run.group(0), "charPrIDRef", "") if first_run else ""
        blocks.append(
            Block(
                index=i, xml=frag, text=text_of(own), para=_attr(open_tag, "paraPrIDRef", ""), char=char,
                has_secpr="<hp:secPr" in frag, has_pic=bool(_DRAWING_RE.search(own)), page_break=_attr(open_tag, "pageBreak", "0") == "1",
                tables=tables,
            )
        )
    return blocks


def classify(text: str) -> str:
    s = text.lstrip(" \t　 ")
    if not s:
        return "empty"
    for kind, pat in _KIND_PATTERNS:
        if pat.match(s):
            return kind
    if _BRACKET_CAPTION.match(s):
        return "caption"
    return "plain"


def split_section(xml: str) -> tuple[str, str, str, str]:
    """(xml 선언, <hs:sec …> 여는 태그, 안쪽, </hs:sec> 이후) — 없으면 ProfileError."""
    m = re.search(r"(.*?)(<hs:sec\b[^>]*>)(.*)(</hs:sec>.*)", xml, re.S)
    if not m:
        raise ProfileError("section0.xml 에 <hs:sec> 가 없다")
    return m.group(1), m.group(2), m.group(3), m.group(4)


def page_attrs_from_section(section_xml: str) -> dict:
    page = re.search(r"<hp:pagePr\b([^>]*)>", section_xml)
    margin = re.search(r"<hp:margin\b([^>]*)>", section_xml)
    out: dict = {}
    if page:
        out.update({"width": _int_attr(page.group(1), "width"), "height": _int_attr(page.group(1), "height"),
                    "landscape": _attr(page.group(1), "landscape", "")})
    if margin:
        out.update({f"margin_{k}": _int_attr(margin.group(1), k) for k in ("left", "right", "top", "bottom", "header", "footer", "gutter")})
    return out


# ── 분석 ───────────────────────────────────────────────────────────────────────


@dataclass
class StyleChoice:
    para: str
    char: str
    source: str  # 참고 문서 층위(kind) 또는 fallback:<이름>
    expected: dict  # 참고 문서(또는 폴백 계량값)에서 확정한 속성 — compare 의 기대값


@dataclass
class Analysis:
    ref_name: str
    sha12: str
    layout: str
    header: HeaderInfo  # 폴백 추가분이 반영된 최종 header
    header_xml: str
    styles: dict[str, StyleChoice]
    table: dict  # basic.xml 계량값 + expected
    page: dict
    body_width: int
    skel_secpr_run: str  # secPr(+colPr) 을 담은 run xml
    skel_para_open: str
    skel_sec_open: str
    skel_text_char: str
    fallback: list[str]
    warnings: list[str]
    objects: dict[str, str]
    stats: dict
    source_section: str = "section0"  # 본문 서식을 뽑은 섹션(Claude R2 C-F3)


def _most_common_pair(pairs: Counter) -> tuple[str, str] | None:
    if not pairs:
        return None
    (para, char), _n = pairs.most_common(1)[0]
    return para, char


def analyze_reference(ref_path: Path, layout: str) -> Analysis:
    if layout not in SUPPORTED_LAYOUTS:
        raise ProfileError(f"지원하지 않는 layout: {layout} (지원: {', '.join(SUPPORTED_LAYOUTS)})")
    try:
        zf = zipfile.ZipFile(ref_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProfileError(f"참고 문서를 열 수 없다: {ref_path}: {exc}") from exc
    names = zf.namelist()
    if "Contents/header.xml" not in names or "Contents/section0.xml" not in names:
        raise ProfileError(f"참고 문서에 Contents/header.xml·section0.xml 이 없다: {ref_path}")
    header_xml = zf.read("Contents/header.xml").decode("utf-8")
    sha12 = hashlib.sha256(ref_path.read_bytes()).hexdigest()[:12]
    warnings: list[str] = []
    fallback: list[str] = []
    objects: dict[str, str] = {}

    # ── 채택 섹션: **최상위 텍스트 문단이 가장 많은 섹션** ──
    # 정부 문서는 section0 이 표지(문단 1개·표만)이고 본문이 section1·2 인 형태가 흔하다 — section0 고정이면
    # text_blocks 0 → 스타일 12종 전부 폴백인데 compare 는 자기 폴백값을 기대값으로 삼아 ok 를 낸다(Claude R2 C-F3).
    sections = sorted(
        (n for n in names if re.match(r"Contents/section\d+\.xml$", n)),
        key=lambda n: int(re.search(r"\d+", n).group()),
    )
    section_texts = {n: zf.read(n).decode("utf-8") for n in sections}

    def _text_block_count(xml: str) -> int:
        try:
            _d, _o, inner_, _t = split_section(xml)
            return sum(1 for b in parse_blocks(inner_) if b.is_text)
        except (ProfileError, AttributeError, ValueError):
            return -1

    counts = {n: _text_block_count(section_texts[n]) for n in sections}
    source_section = max(sections, key=lambda n: (counts[n], -sections.index(n)))
    section_xml = section_texts[source_section]
    source_section = Path(source_section).stem  # "section2"
    if len(sections) > 1:
        detail = ", ".join(f"{Path(n).stem}:{counts[n]}" for n in sections)
        warnings.append(
            f"multi_section: 섹션 {len(sections)}개 — 본문 문단이 가장 많은 {Path(source_section).stem} 채택 (문단 수 {detail})"
        )
    if any(re.match(r"Contents/masterpage\d*\.xml$", n, re.I) for n in names) or re.search(r"<hp:masterPage\b", section_xml):
        warnings.append("master_page: 마스터페이지(바탕쪽)는 1차 범위 밖 — 버림")
    if re.search(r"<hp:header\b", section_xml):
        warnings.append("header: 머리말은 1차 범위 밖 — 버림")
    if re.search(r"<hp:footer\b", section_xml):
        warnings.append("footer: 꼬리말은 1차 범위 밖 — 버림")
    if re.search(r"<hp:pageNum\b|<hp:autoNum\b", section_xml):
        warnings.append("page_number: 쪽 번호 개체는 1차 범위 밖 — 버림")
    if re.search(r'<hh:font\b[^>]*isEmbedded="1"', header_xml):
        warnings.append("embedded_font: 참고 문서가 글꼴을 내장한다 — BinData 는 복사하지 않는다(글꼴 미설치 시 대체 글꼴)")

    header = parse_header(header_xml)
    decl, sec_open, inner, _tail = split_section(section_xml)
    blocks = parse_blocks(inner)
    if not blocks:
        raise ProfileError("section0.xml 에 최상위 문단이 없다")

    # 표지·결재란: 첫 몇 문단 안의 짧은 표 + 페이지 나눔 조합
    early = blocks[: min(6, len(blocks))]
    short_tables_early = any(t.rows <= 2 or len(t.text) <= 40 for b in early for t in b.tables)
    if short_tables_early and any(b.page_break for b in blocks):
        warnings.append("cover_or_approval: 표지·결재란(짧은 표 + 쪽 나눔)으로 보이는 개체 — objects/ 에 두고 조판에는 쓰지 않는다")

    # ── 첫 문단(secPr) 골격 ──
    first = blocks[0]
    secpr_block = next((b for b in blocks if b.has_secpr), None)
    if secpr_block is None and sections and section_texts[sections[0]] is not section_xml:
        # 채택 섹션에 secPr 이 없으면 용지 설정은 section0 에서 가져온다(문서 전체 용지 계약)
        _d0, _o0, inner0, _t0 = split_section(section_texts[sections[0]])
        secpr_block = next((b for b in parse_blocks(inner0) if b.has_secpr), None)
        if secpr_block is not None:
            warnings.append(f"secpr_from_section0: {source_section} 에 secPr 이 없어 용지 설정은 section0 에서 가져온다")
    if secpr_block is None:
        warnings.append("secpr_missing: 첫 문단에 secPr 이 없다 — ai-report 내장 용지 설정으로 대체")
        builtin_skel = (REPORT_DIR / "hwpx_report" / "assets" / "templates" / "ai-report" / "section0.skel.xml").read_text(encoding="utf-8")
        _d, _o, b_inner, _t = split_section(builtin_skel)
        secpr_block = parse_blocks(b_inner)[0]
    secpr = re.search(r"<hp:secPr\b.*?</hp:secPr>", secpr_block.xml, re.S)
    if not secpr:
        raise ProfileError("secPr 조각을 찾지 못했다")
    secpr_xml = secpr.group(0)
    if _int_attr(re.match(r"<hp:secPr\b[^>]*>", secpr_xml).group(0), "masterPageCnt") > 0:
        secpr_xml = re.sub(r'masterPageCnt="\d+"', 'masterPageCnt="0"', secpr_xml, count=1)
    run_open_m = None
    for rm in re.finditer(r"<hp:run\b[^>]*>", secpr_block.xml):
        if rm.start() < secpr.start():
            run_open_m = rm
    run_open = run_open_m.group(0) if run_open_m else '<hp:run charPrIDRef="0">'
    after = secpr_block.xml[secpr.end():]
    colpr = re.match(r"\s*<hp:ctrl>\s*<hp:colPr\b[^>]*?(?:/>|>.*?</hp:colPr>)\s*</hp:ctrl>", after, re.S)
    colpr_xml = colpr.group(0).strip() if colpr else '<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl>'
    if secpr_block is first and (first.tables or first.has_pic):
        stripped = re.sub(r"<hp:secPr\b.*?</hp:secPr>", "", first.xml, flags=re.S)
        objects["first_paragraph_objects.xml"] = stripped
        warnings.append("letterhead_objects: 첫 문단(secPr)에 붙은 표·그림 개체를 뗐다 — objects/first_paragraph_objects.xml")
    para_open = re.match(r"<hp:p\b[^>]*>", secpr_block.xml).group(0)
    para_open = re.sub(r'pageBreak="[^"]*"', 'pageBreak="0"', para_open)
    if 'id="' in para_open:
        para_open = re.sub(r'\bid="[^"]*"', 'id="0"', para_open, count=1)
    page = page_attrs_from_section(secpr_xml)

    # ── 문단 분류 ──
    text_blocks = [b for b in blocks if b.is_text]
    by_kind: dict[str, Counter] = {}
    kind_of: dict[int, str] = {}
    for b in text_blocks:
        kind = classify(b.text)
        kind_of[b.index] = kind
        by_kind.setdefault(kind, Counter())[(b.para, b.char)] += 1
    height_counter = Counter(header.char[b.char].height for b in text_blocks if b.char in header.char)
    body_height = height_counter.most_common(1)[0][0] if height_counter else 1000
    body_pair = None
    all_pairs = Counter((b.para, b.char) for b in text_blocks)
    if all_pairs:
        body_pair = all_pairs.most_common(1)[0][0]
    body_font = header.char[body_pair[1]].font if body_pair and body_pair[1] in header.char else (next(iter(header.fonts), "0"))
    body_char_bf = header.char[body_pair[1]].border_fill if body_pair and body_pair[1] in header.char else (next(iter(header.border), "0"))
    # 폴백 charPr 이 쓸 언어별 fontRef — 본문 기준 charPr 의 값을 그대로, 없으면 그 언어에 실재하는 id (Codex R2 F5)
    body_fonts = header.resolve_fonts(header.char.get(body_pair[1]) if body_pair else None, body_font)
    body_para = header.para.get(body_pair[0]) if body_pair else None
    body_para_bf = body_para.border_fill if body_para and body_para.border_fill else (next(iter(header.border), "0"))
    body_tab = body_para.tab_pr if body_para else "0"

    # 제목: 첫 6개 텍스트 문단 중 문서 최대 크기이면서 본문의 1.2배 이상, 60자 이하
    max_h = max(height_counter) if height_counter else body_height
    title_block = None
    if max_h >= body_height * 1.2:
        for b in text_blocks[:6]:
            if kind_of[b.index] == "plain" and b.char in header.char and header.char[b.char].height == max_h and len(b.text.strip()) <= 60:
                title_block = b
                break
    meta_block = None
    if title_block is not None:
        after_title = [b for b in text_blocks if b.index > title_block.index][:3]
        for b in after_title:
            if kind_of[b.index] == "plain" and len(b.text.strip()) <= 60 and b.para in header.para and header.para[b.para].align in ("CENTER", "RIGHT"):
                meta_block = b
                break
    plain_pairs = Counter()
    for b in text_blocks:
        if kind_of[b.index] == "plain" and b is not title_block and b is not meta_block and len(b.text.strip()) >= 25:
            plain_pairs[(b.para, b.char)] += 1
    empty_pairs = Counter((b.para, b.char) for b in blocks if b.is_empty)
    bold_short = Counter()
    for b in text_blocks:
        if kind_of[b.index] == "plain" and b is not title_block and b is not meta_block and b.char in header.char and header.char[b.char].bold and len(b.text.strip()) <= 40:
            bold_short[(b.para, b.char)] += 1

    # 제목축과 항목 사다리
    heading_kind = next((k for k in ("roman", "digit") if by_kind.get(k)), None)
    ladder_kinds = [k for k in by_kind if k not in ("plain", "caption", "empty") and k != heading_kind]

    def indent_key(kind: str) -> tuple[int, int]:
        pair = _most_common_pair(by_kind[kind])
        p = header.para.get(pair[0]) if pair else None
        left = p.left if p else 0
        return (left, _LADDER_RANK.index(kind) if kind in _LADDER_RANK else 99)

    ladder_kinds.sort(key=indent_key)

    stats = {
        "blocks": len(blocks), "text_blocks": len(text_blocks), "empty_blocks": sum(1 for b in blocks if b.is_empty),
        "table_blocks": sum(1 for b in blocks if b.tables), "image_blocks": sum(1 for b in blocks if b.has_pic),
        "kinds": {k: sum(v.values()) for k, v in by_kind.items()}, "body_height": body_height,
        "heading_kind": heading_kind, "ladder": ladder_kinds,
    }

    # ── style-map 채우기 ──
    styles: dict[str, StyleChoice] = {}
    pending_fallback: list[str] = []

    def pick(name: str, pair: tuple[str, str] | None, source: str) -> None:
        if pair is None:
            pending_fallback.append(name)
            return
        styles[name] = StyleChoice(para=pair[0], char=pair[1], source=source, expected=header.pair_attrs(pair[0], pair[1]))

    kind_pair = lambda k: _most_common_pair(by_kind[k]) if k in by_kind else None  # noqa: E731
    pick("doc_title", (title_block.para, title_block.char) if title_block else None, "title")
    pick("meta", (meta_block.para, meta_block.char) if meta_block else None, "meta")
    if heading_kind:
        pick("heading", kind_pair(heading_kind), heading_kind)
    else:
        pick("heading", _most_common_pair(bold_short), "bold_short")
    if layout == "ai-report":
        for i in range(1, 4):
            k = ladder_kinds[i - 1] if len(ladder_kinds) >= i else None
            pick(f"level{i}", kind_pair(k) if k else None, k or "")
        pick("prose", _most_common_pair(plain_pairs), "plain")
        pick("caption", kind_pair("caption"), "caption")
        if "level1" in styles:
            styles["body_box"] = StyleChoice(styles["level1"].para, styles["level1"].char, "level1", styles["level1"].expected)
        else:
            pending_fallback.append("body_box")
    else:
        k = ladder_kinds[0] if ladder_kinds else None
        pick("body_box", kind_pair(k) if k else _most_common_pair(plain_pairs), k or "plain")
    empty_pair = _most_common_pair(empty_pairs)
    pick("blank", empty_pair, "empty")
    pick("heading_spacer", empty_pair, "empty")

    # 폴백 합성 — 내장 계량값 + 참고 문서 본문 글꼴, header 끝에 덧붙인다(같은 계량값은 한 번만)
    new_chars: list[str] = []
    new_paras: list[str] = []
    new_borders: list[str] = []
    next_char = max((int(c) for c in header.char if c.isdigit()), default=-1) + 1
    next_para = max((int(p) for p in header.para if p.isdigit()), default=-1) + 1
    next_border = max((int(b) for b in header.border if b.isdigit()), default=-1) + 1
    char_cache: dict[tuple, str] = {}
    para_cache: dict[tuple, str] = {}
    metrics = _FALLBACK[layout]
    for name in pending_fallback:
        m = metrics.get(name) or _FALLBACK["ai-report"].get(name) or _FALLBACK["report"]["body_box"]
        height, bold, align, left, intent, prev, next_, line = m
        ck = (height, bold)
        if ck not in char_cache:
            char_cache[ck] = str(next_char)
            new_chars.append(_char_pr_xml(next_char, None, height, bold, body_font, body_char_bf, body_fonts))
            next_char += 1
        pk = (align, left, intent, prev, next_, line)
        if pk not in para_cache:
            para_cache[pk] = str(next_para)
            new_paras.append(_para_pr_xml(next_para, align, left, intent, prev, next_, line, body_para_bf, body_tab))
            next_para += 1
        styles[name] = StyleChoice(
            para=para_cache[pk], char=char_cache[ck], source=f"fallback:{layout}",
            expected={"align": align, "left": left, "intent": intent, "prev": prev, "next": next_, "line": f"PERCENT:{line}",
                      "font": header.fonts.get(body_font, f"#{body_font}"), "height": height, "bold": bold, "italic": False},
        )
        fallback.append(name)
    if fallback:
        warnings.append("style_fallback: 참고 문서에서 못 채운 스타일을 내장 계량값(본문 글꼴)으로 합성 — " + ", ".join(fallback))

    # ── 본문 폭 ──
    # ── 데이터 표 후보(행≥3·열 2~12·본문 안·글자 40자+) 와 본문 폭 ──
    # 본문 폭 = 가장 넓은 **데이터 표** 폭(용지 본문 폭 이내), 데이터 표가 없으면 secPr 로 계산한 본문 폭.
    # 결재란·서명 블록 같은 배치용 표(열 수가 많거나 글자 없음)는 폭 산정에서 뺀다.
    page_w = page.get("width", 59528) - page.get("margin_left", 0) - page.get("margin_right", 0) - page.get("margin_gutter", 0)
    data_tables = [t for b in blocks if not b.has_secpr for t in b.tables
                   if t.rows >= 3 and 2 <= t.cols <= 12 and len(t.text) > 40 and not t.behind_text]
    tbl_widths = [t.width for t in data_tables if 0 < t.width <= page_w]
    body_width = max(tbl_widths) if tbl_widths else page_w
    if body_width <= 0:
        body_width = 47849
    banners = [t for b in blocks for t in b.tables if (t.rows <= 2 or len(t.text) <= 40) and not b.has_secpr]
    for i, t in enumerate(banners[:3]):
        objects[f"banner_{t.rows}x{t.cols}_{i}.xml"] = t.xml
    drawings = [b for b in blocks if b.has_pic and not b.has_secpr]
    if drawings:
        objects["drawing_0.xml"] = drawings[0].xml  # 그림·제목 박스(rect) 등 첫 개체 문단 — 조판에 쓰지 않는다
    table: dict = {"source": "", "width": body_width}
    if data_tables:
        data_tables.sort(key=lambda t: (t.merged, -t.rows))
        t = data_tables[0]
        head_cells = [c for c in t.cells if c.row == 0]
        body_cells = [c for c in t.cells if c.row >= 1]
        hb = Counter(c.border_fill for c in head_cells).most_common(1)[0][0] if head_cells else t.border_fill
        hc = Counter(c.char for c in head_cells).most_common(1)[0][0] if head_cells else body_pair[1]
        hp = Counter(c.para for c in head_cells).most_common(1)[0][0] if head_cells else body_pair[0]
        bb = Counter(c.border_fill for c in body_cells).most_common(1)[0][0] if body_cells else hb
        bc = Counter(c.char for c in body_cells).most_common(1)[0][0] if body_cells else hc
        bp = Counter(c.para for c in body_cells).most_common(1)[0][0] if body_cells else hp
        header_h = Counter(c.height for c in head_cells).most_common(1)[0][0] if head_cells else _TABLE_FALLBACK["header_h"]
        body_h = Counter(c.height for c in body_cells).most_common(1)[0][0] if body_cells else _TABLE_FALLBACK["body_h"]
        table.update({"source": f"table_{t.rows}x{t.cols}", "container": t.border_fill or bb, "header": (hb, hc, hp),
                      "body": (bb, bc, bp), "header_h": header_h or _TABLE_FALLBACK["header_h"], "body_h": body_h or _TABLE_FALLBACK["body_h"],
                      "columns": [c.width for c in head_cells]})
        if t.merged:
            warnings.append(f"table_merged: 채택한 데이터 표({t.rows}x{t.cols})에 셀 병합이 있다 — 셀 서식만 근사")
    else:
        # 참고 문서 안의 아무 표 셀 서식이라도 있으면 그것을, 없으면 합성
        any_cells = [c for b in blocks for t in b.tables for c in t.cells]
        cell_bf_counter = Counter(c.border_fill for c in any_cells if c.border_fill in header.border and header.border[c.border_fill].sides.count("SOLID") == 4)
        if cell_bf_counter:
            bb = cell_bf_counter.most_common(1)[0][0]
        else:
            bb = str(next_border)
            new_borders.append(_border_fill_xml(next_border, None))
            next_border += 1
        filled = [bid for bid, b in header.border.items() if b.fill and b.sides.count("SOLID") == 4]
        if filled:
            hb = filled[0]
        else:
            hb = str(next_border)
            new_borders.append(_border_fill_xml(next_border, _TABLE_FALLBACK["header_fill"]))
            next_border += 1
        # 머리글 셀 글꼴: 본문 크기와 같은 굵은 charPr 이 표 셀에 있으면 그것(없으면 ±200 허용), 그것도 없으면 합성
        bold_cells = [c for c in any_cells if c.char in header.char and header.char[c.char].bold]
        bold_pair = next(((c.para, c.char) for c in bold_cells if header.char[c.char].height == body_height), None) or next(
            ((c.para, c.char) for c in bold_cells if abs(header.char[c.char].height - body_height) <= 200), None)
        bc = body_pair[1] if body_pair else str(next_char)
        if body_pair is None:
            new_chars.append(_char_pr_xml(next_char, None, body_height, False, body_font, body_char_bf, body_fonts))
            next_char += 1
        hc = bold_pair[1] if bold_pair else None
        if hc is None:
            hc = str(next_char)
            new_chars.append(_char_pr_xml(next_char, None, header.char[bc].height if bc in header.char else body_height, True, body_font, body_char_bf, body_fonts))
            next_char += 1
        center = next((pid for pid, p in header.para.items() if p.align == "CENTER" and p.left == 0 and p.intent == 0), None)
        if center is None:
            center = str(next_para)
            new_paras.append(_para_pr_xml(next_para, "CENTER", 0, 0, 0, 0, 160, body_para_bf, body_tab))
            next_para += 1
        table.update({"source": "fallback:gov-report", "container": bb, "header": (hb, hc, center), "body": (bb, bc, center),
                      "header_h": _TABLE_FALLBACK["header_h"], "body_h": _TABLE_FALLBACK["body_h"], "columns": []})
        fallback.append("tables/basic")
        warnings.append("table_fallback: 데이터 표(행≥3·열 2~12·본문 안)를 못 찾아 gov-report 표 계량값을 참고 문서 서식으로 합성")

    # 정렬·굵기 변형(table_body_left/right/justify, bold/italic) — 같은 여백의 paraPr / 같은 크기의 charPr 을 찾고 없으면 합성
    bb, bc, bp = table["body"]
    base_para = header.para.get(bp)
    variants: dict[str, str] = {}
    for vname, align in (("table_body_left", "LEFT"), ("table_body_right", "RIGHT"), ("table_body_justify", "JUSTIFY")):
        found = None
        if base_para is not None:
            found = next((pid for pid, p in header.para.items() if p.align == align and p.left == base_para.left and p.intent == base_para.intent
                          and p.prev == base_para.prev and p.line_value == base_para.line_value), None)
        if found is None:
            pk = ("variant", align, base_para.left if base_para else 0, base_para.intent if base_para else 0)
            if pk not in para_cache:
                para_cache[pk] = str(next_para)
                new_paras.append(_para_pr_xml(next_para, align, base_para.left if base_para else 0, base_para.intent if base_para else 0,
                                              base_para.prev if base_para else 0, base_para.next if base_para else 0,
                                              base_para.line_value if base_para else 160, body_para_bf, body_tab))
                next_para += 1
            found = para_cache[pk]
        variants[vname] = found
    base_char = header.char.get(bc)
    char_variants: dict[str, str] = {}
    for vname, want_bold, want_italic in (("table_body_bold", True, False), ("table_body_italic", False, True), ("table_body_bold_italic", True, True)):
        found = None
        if base_char is not None:
            found = next((cid for cid, c in header.char.items() if c.height == base_char.height and c.font == base_char.font
                          and c.bold == want_bold and c.italic == want_italic), None)
        if found is None:
            ck = ("variant", want_bold, want_italic)
            if ck not in char_cache:
                char_cache[ck] = str(next_char)
                xml_c = _char_pr_xml(next_char, None, base_char.height if base_char else body_height, want_bold,
                                     base_char.font if base_char else body_font, body_char_bf,
                                     header.resolve_fonts(base_char, base_char.font if base_char else body_font))
                if want_italic:
                    xml_c = xml_c.replace("<hh:underline", "<hh:italic/><hh:underline", 1)
                new_chars.append(xml_c)
                next_char += 1
            found = char_cache[ck]
        char_variants[vname] = found

    header_xml_out = re.sub(r'\bsecCnt="\d+"', 'secCnt="1"', header_xml, count=1)
    root_m = re.match(r"(.*?)(<hh:head\b[^>]*>)", header_xml_out, re.S)
    if root_m:
        header_xml_out = header_xml_out[: root_m.start(2)] + _ensure_namespaces(root_m.group(2)) + header_xml_out[root_m.end(2):]
    header_xml_out = append_header_items(header_xml_out, new_chars, new_paras, new_borders)
    final_header = parse_header(header_xml_out)

    hb, hc, hp = table["header"]
    bb, bc, bp = table["body"]
    for name, (bfid, cid, pid) in (("table_header", (hb, hc, hp)), ("table_body", (bb, bc, bp)), ("table_total", (hb, hc, hp))):
        styles[name] = StyleChoice(para=pid, char=cid, source=f"table:{table['source']}", expected={**final_header.pair_attrs(pid, cid), **final_header.border_attrs(bfid)})
        styles[name].expected["borderFillIDRef"] = bfid
    for vname, pid in variants.items():
        styles[vname] = StyleChoice(para=pid, char=bc, source="table_variant", expected={**final_header.pair_attrs(pid, bc), **final_header.border_attrs(bb)})
        styles[vname].expected["borderFillIDRef"] = bb
    for vname, cid in char_variants.items():
        styles[vname] = StyleChoice(para="", char=cid, source="table_variant", expected=final_header.char_attrs(cid))
    styles["table_container"] = StyleChoice(para="", char="", source="table", expected={**final_header.border_attrs(table["container"]), "borderFillIDRef": table["container"]})
    table["expected"] = {
        "width": body_width,
        # 셀 정렬은 서식이 아니라 내용(마크다운 열 정렬 `--:`)이 정하므로 대조 축에서 뺀다 — 넣으면 숫자 열이 있는 정상 산출이
        # 참고 문서의 첫 표 정렬과 달라 exit 2 가 난다(#1653 v1.3 샘플 09 실측: body.align RIGHT vs LEFT).
        "header": {**final_header.border_attrs(hb), **final_header.char_attrs(hc)},
        "body": {**final_header.border_attrs(bb), **final_header.char_attrs(bc)},
    }
    # 폴백 스타일의 기대값을 최종 header 로 다시 확정(합성 id 가 실재하는지 확인)
    for name, st in styles.items():
        if st.source.startswith("fallback:"):
            st.expected = final_header.pair_attrs(st.para, st.char)

    return Analysis(
        ref_name=ref_path.name, sha12=sha12, layout=layout, header=final_header, header_xml=header_xml_out, styles=styles, table=table,
        page=page, body_width=body_width, skel_secpr_run=run_open + secpr_xml + colpr_xml + "</hp:run>", skel_para_open=para_open,
        skel_sec_open=_ensure_namespaces(sec_open), skel_text_char=_attr(run_open, "charPrIDRef", "0") or "0",
        fallback=fallback, warnings=warnings, objects=objects, stats=stats, source_section=source_section,
    )


# ── 프로파일 쓰기 ────────────────────────────────────────────────────────────────


def _xml_attr_escape(v: str) -> str:
    return v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def build_skel(ana: Analysis) -> str:
    body = ""
    if ana.layout == "report":
        t = ana.styles["doc_title"]
        m = ana.styles["meta"]
        body = (
            f'<hp:p id="1" paraPrIDRef="{t.para}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{t.char}"><hp:t>보고자료 제목</hp:t></hp:run></hp:p>'
            f'<hp:p id="2" paraPrIDRef="{m.para}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{m.char}"><hp:t>(’YY. MM. DD., 부서명)</hp:t></hp:run></hp:p>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        + ana.skel_sec_open
        + ana.skel_para_open
        + ana.skel_secpr_run
        + f'<hp:run charPrIDRef="{_xml_attr_escape(ana.skel_text_char)}"><hp:t/></hp:run></hp:p>'
        + body
        + "</hs:sec>"
    )


def build_table_template_xml(ana: Analysis) -> str:
    t = ana.table
    hb, hc, hp = t["header"]
    bb, bc, bp = t["body"]
    cols = ""
    widths = [w for w in t.get("columns", []) if w > 0]
    if widths:
        total = sum(widths)
        cols = "".join(f'      <col index="{i}" width="{w * t["width"] // total}" align="center"/>\n' for i, w in enumerate(widths))
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        '<table-template xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">\n'
        "  <meta>\n"
        "    <name>basic</name>\n"
        f"    <description>참고 문서에서 추출한 표 서식 ({t['source']})</description>\n"
        f"    <table-width>{t['width']}</table-width>\n"
        f'    <row-height header="{t["header_h"]}" body="{t["body_h"]}" summary="{t["body_h"]}"/>\n'
        "    <styles>\n"
        f'      <table-border borderFillIDRef="{t["container"]}"/>\n'
        f'      <header-cell borderFillIDRef="{hb}" charPrIDRef="{hc}" paraPrIDRef="{hp}"/>\n'
        f'      <body-cell borderFillIDRef="{bb}" charPrIDRef="{bc}" paraPrIDRef="{bp}"/>\n'
        f'      <summary-cell borderFillIDRef="{hb}" charPrIDRef="{hc}" paraPrIDRef="{hp}"/>\n'
        "    </styles>\n"
        + (f"    <columns>\n{cols}    </columns>\n" if cols else "")
        + "  </meta>\n"
        "</table-template>\n"
    )


def build_manifest(ana: Analysis, profile_id: str) -> dict:
    builtin = json.loads((REPORT_DIR / "hwpx_report" / "assets" / "templates" / ("ai-report" if ana.layout == "ai-report" else "gov-report") / "manifest.json").read_text(encoding="utf-8"))
    manifest = {
        "id": profile_id,
        "name": f"서식 프로파일: {ana.ref_name}",
        "layout": ana.layout,
        "source": f"derive_profile.py analyze — 사용자 참고 문서 {ana.ref_name} 의 header.xml 을 그대로 쓰고 본문 층위 서식을 근사(#1652 P1 E)",
        "derived_from": {"file": ana.ref_name, "sha256": ana.sha12},
        "source_section": ana.source_section,
        "placeholders": [{"token": "YY", "kind": "year2"}, {"token": "보고자료 제목", "kind": "title"}, {"token": ". MM. DD., 부서명)", "kind": "date-dept"}] if ana.layout == "report" else [],
        "bodyRegion": {"after": "secPr"},
        "tables": ["basic"],
        "fields": builtin.get("fields", {}),
        "max_level": builtin.get("max_level", 3 if ana.layout == "ai-report" else 2),
        "body_width": ana.body_width,
        "fallback": list(ana.fallback),
        "warnings": list(ana.warnings),
        "profile": {
            "page": ana.page,
            "stats": ana.stats,
            "styles": {name: {"source": st.source, "expected": st.expected} for name, st in ana.styles.items()},
            "table": ana.table.get("expected", {}),
            "objects": sorted(ana.objects),
            "limits": "단일 섹션 본문 스타일 근사 — paraPr 이 줄마다 손조정된 문서는 대표 서식이 원본과 다를 수 있다. 표지·결재란·머리말/꼬리말은 조판하지 않는다.",
        },
    }
    return manifest


def write_profile(ana: Analysis, outdir: Path, profile_id: str) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "tables").mkdir(exist_ok=True)
    (outdir / "header.xml").write_text(ana.header_xml, encoding="utf-8")
    (outdir / "section0.skel.xml").write_text(build_skel(ana), encoding="utf-8")
    style_map = {}
    for name, st in ana.styles.items():
        entry: dict[str, str] = {}
        if st.char:
            entry["charPrIDRef"] = st.char
        if st.para:
            entry["paraPrIDRef"] = st.para
        if "borderFillIDRef" in st.expected:
            entry["borderFillIDRef"] = st.expected["borderFillIDRef"]
        style_map[name] = entry
    (outdir / "style-map.json").write_text(json.dumps(style_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = build_manifest(ana, profile_id)
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (outdir / "tables" / "basic.xml").write_text(build_table_template_xml(ana), encoding="utf-8")
    if ana.objects:
        (outdir / "objects").mkdir(exist_ok=True)
        for name, xml in ana.objects.items():
            (outdir / "objects" / name).write_text(xml, encoding="utf-8")
        (outdir / "objects" / "index.json").write_text(
            json.dumps({"note": "참고 문서에서 떼어 둔 개체 프로토타입 — 조판에 쓰지 않는다(1차 범위 밖)", "files": sorted(ana.objects)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


_SMOKE_SPEC = {
    "title": "프로파일 점검", "report_date": "2026-09-06", "dept": "점검",
    "sections": [{"heading": "1. 점검", "blocks": [
        {"item": {"level": 1, "text": "항목"}}, {"item": {"level": 2, "text": "하위"}},
        {"table": {"headers": ["구분", "내용"], "rows": [["가", "나"]], "caption": "점검표"}},
    ]}],
}


def self_check(profile_dir: Path) -> None:
    """산출 프로파일이 로더 검증을 통과하고 실제로 문서를 한 장 만들 수 있는지 확인한다(무성 실패 금지)."""
    # 디렉토리 로더로 직접 간다 — 프로파일 이름이 내장 id 와 같아도 내장이 선택되지 않는다(Claude R2 C-F2)
    load_report_template_dir(profile_dir)
    build_report(Path(profile_dir), DocSpec.from_json(_SMOKE_SPEC))


# ── compare ─────────────────────────────────────────────────────────────────────


def _read_hwpx_parts(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.read("Contents/header.xml").decode("utf-8"), zf.read("Contents/section0.xml").decode("utf-8")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ProfileError(f"hwpx 를 읽을 수 없다: {path}: {exc}") from exc


def _diff_attrs(expected: dict, actual: dict) -> list[str]:
    out = []
    for k, v in expected.items():
        if k in ("borderFillIDRef",):
            continue
        if actual.get(k) != v:
            out.append(f"{k}: expected {v!r}, actual {actual.get(k)!r}")
    if "missing" in actual and "missing" not in expected:
        out.append(f"missing: {actual['missing']}")
    return out


def compare_profile(profile_dir: Path, out_path: Path, ref_path: Path | None) -> dict:
    tmpl = load_report_template_dir(profile_dir)
    layout = tmpl.layout
    manifest = tmpl.manifest
    expected_styles: dict[str, dict]
    if ref_path is not None:
        ana = analyze_reference(ref_path, layout)
        expected_styles = {name: st.expected for name, st in ana.styles.items()}
        expected_page = ana.page
        expected_table = ana.table.get("expected", {})
        expected_source = f"ref:{ref_path.name}"
        style_sources = {name: st.source for name, st in ana.styles.items()}
    else:
        prof = manifest.get("profile", {})
        expected_styles = {name: v.get("expected", {}) for name, v in prof.get("styles", {}).items()}
        expected_page = prof.get("page", {})
        expected_table = prof.get("table", {})
        expected_source = "manifest"
        style_sources = {name: str(v.get("source", "")) for name, v in prof.get("styles", {}).items()}
    out_header_xml, out_section_xml = _read_hwpx_parts(out_path)
    out_header = parse_header(out_header_xml)
    _d, _o, inner, _t = split_section(out_section_xml)
    blocks = parse_blocks(inner)

    # 산출 문단이 실제로 쓰는 (paraPr, charPr) → style-map 역참조로 "쓰인 이름" 을 얻는다
    inverted: dict[tuple[str, str], list[str]] = {}
    for name, st in tmpl.styles.items():
        if st.paraPrIDRef and st.charPrIDRef:
            inverted.setdefault((st.paraPrIDRef, st.charPrIDRef), []).append(name)
    used: set[str] = set()
    for b in blocks:
        if b.has_secpr or b.tables or b.has_pic:
            continue
        for name in inverted.get((b.para, b.char), []):
            used.add(name)
    # 기대값이 참고 문서가 아니라 **내장 합성값**인 스타일 — ok 여도 "참고 서식대로" 를 뜻하지 않는다(Claude R2 C-F3).
    fallback_styles = sorted(
        name for name in LAYOUT_STYLE_NAMES.get(layout, []) if style_sources.get(name, "").startswith("fallback:")
    )
    result: dict = {"ok": True, "expected_source": expected_source, "layout": layout, "styles": {}, "unused": [],
                    "fallback_styles": fallback_styles, "page": {}, "table": {}}
    checked = 0
    for name in LAYOUT_STYLE_NAMES.get(layout, []):
        st = tmpl.styles.get(name)
        if st is None:
            result["styles"][name] = {"ok": False, "diff": ["style-map 에 없음"]}
            result["ok"] = False
            continue
        # 미사용 스타일도 **대조는 한다** — 산출물에서 역참조되지 않는다고 건너뛰면, 반드시 쓰여야 할
        # doc_title 의 style-map 을 다른 유효한(그러나 미사용) pair 로 바꿔도 compare 가 승인한다(Codex R2 F6).
        # used/unused 는 보고 필드일 뿐이고, checked 는 종전대로 **쓰인 스타일 수**를 뜻한다(빈 통과 판정에 쓴다).
        if name not in used:
            result["unused"].append(name)
        expected = expected_styles.get(name, {})
        actual = out_header.pair_attrs(st.paraPrIDRef, st.charPrIDRef)
        diff = _diff_attrs(expected, actual) if expected else ["기대값 없음"]
        result["styles"][name] = {"ok": not diff, "used": name in used, "expected": expected, "actual": actual, "diff": diff}
        if name in used:
            checked += 1
        if diff:
            result["ok"] = False

    actual_page = page_attrs_from_section(out_section_xml)
    page_diff = _diff_attrs(expected_page, actual_page) if expected_page else ["기대값 없음"]
    result["page"] = {"ok": not page_diff, "expected": expected_page, "actual": actual_page, "diff": page_diff}
    if page_diff:
        result["ok"] = False

    out_tables = [t for b in blocks if not b.has_secpr for t in b.tables]
    if out_tables and expected_table:
        t = out_tables[0]
        head_cells = [c for c in t.cells if c.row == 0]
        body_cells = [c for c in t.cells if c.row >= 1]
        actual_table = {"width": t.width}
        if head_cells:
            c = head_cells[0]
            actual_table["header"] = {**out_header.border_attrs(c.border_fill), **out_header.char_attrs(c.char)}
        if body_cells:
            c = body_cells[0]
            actual_table["body"] = {**out_header.border_attrs(c.border_fill), **out_header.char_attrs(c.char)}
        diff = []
        if expected_table.get("width") != actual_table["width"]:
            diff.append(f"width: expected {expected_table.get('width')!r}, actual {actual_table['width']!r}")
        for part in ("header", "body"):
            if part in expected_table and part in actual_table:
                diff += [f"{part}.{d}" for d in _diff_attrs(expected_table[part], actual_table[part])]
        result["table"] = {"ok": not diff, "expected": expected_table, "actual": actual_table, "diff": diff}
        checked += 1
        if diff:
            result["ok"] = False
    elif out_tables:
        result["table"] = {"ok": False, "diff": ["기대값 없음"]}
        result["ok"] = False
    if checked == 0:
        result["ok"] = False
        result["error"] = "대조할 스타일이 하나도 쓰이지 않았다 — 산출 문서가 이 프로파일로 만들어졌는지 확인"
    result["checked"] = checked
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────────


def _valid_id(value: str) -> bool:
    return bool(value) and not value.startswith(".") and "/" not in value and "\\" not in value


def cmd_analyze(args: argparse.Namespace) -> int:
    ref = Path(args.ref)
    outdir = Path(args.output)
    profile_id = args.id or outdir.resolve().name
    if not _valid_id(profile_id):
        print(f"오류: 프로파일 id 가 잘못됐다: {profile_id!r}", file=sys.stderr)
        return 1
    if args.id and args.id != outdir.resolve().name:
        print(f"오류: --id({args.id}) 는 출력 디렉토리 이름({outdir.resolve().name})과 같아야 한다 — 로더가 manifest id = 디렉토리명을 요구한다", file=sys.stderr)
        return 1
    if not ref.is_file():
        print(f"오류: 참고 문서가 없다: {ref}", file=sys.stderr)
        return 1
    try:
        ana = analyze_reference(ref, args.layout)
        manifest = write_profile(ana, outdir, profile_id)
        self_check(outdir)
    except (ProfileError, HWPXReportError, OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    for w in ana.warnings:
        print(f"경고: {w}", file=sys.stderr)
    summary = {
        "profile": str(outdir), "id": profile_id, "layout": ana.layout, "derived_from": manifest["derived_from"],
        "source_section": ana.source_section, "body_width": ana.body_width,
        "styles": {name: {"paraPrIDRef": st.para, "charPrIDRef": st.char, "source": st.source} for name, st in ana.styles.items()},
        "fallback": ana.fallback, "warnings": ana.warnings, "objects": sorted(ana.objects), "stats": ana.stats,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.strict and (ana.fallback or ana.warnings):
        print("오류: --strict — 경고/폴백이 있어 실패로 종료한다", file=sys.stderr)
        return 2
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        result = compare_profile(Path(args.profile), Path(args.output), Path(args.ref) if args.ref else None)
    except (ProfileError, HWPXReportError, OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        print("불일치: 산출 문서의 서식 속성이 참고 문서와 다르다(위 JSON diff 참조)", file=sys.stderr)
        return 2
    if result.get("fallback_styles"):
        print(
            "경고: 기대값이 참고 문서가 아니라 내장 합성값인 스타일 — " + ", ".join(result["fallback_styles"]),
            file=sys.stderr,
        )
        if args.strict:
            print("오류: --strict — 폴백 스타일이 있어 실패로 종료한다", file=sys.stderr)
            return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="derive_profile.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="참고 hwpx 에서 서식 프로파일(템플릿 디렉토리)을 추출")
    a.add_argument("ref", help="참고 .hwpx")
    a.add_argument("-o", "--output", required=True, help="프로파일 디렉토리(이름이 곧 템플릿 id)")
    a.add_argument("--layout", choices=SUPPORTED_LAYOUTS, default="ai-report", help="프로파일이 돌릴 조판(기본 ai-report)")
    a.add_argument("--id", default=None, help="템플릿 id(출력 디렉토리 이름과 같아야 한다)")
    a.add_argument("--strict", action="store_true", help="폴백·경고가 하나라도 있으면 exit 2")
    a.set_defaults(func=cmd_analyze)
    c = sub.add_parser("compare", help="산출 hwpx 의 서식 속성을 참고 문서(또는 manifest 기대값)와 대조")
    c.add_argument("profile", help="프로파일 디렉토리")
    c.add_argument("output", help="그 프로파일로 생성한 .hwpx")
    c.add_argument("--ref", default=None, help="참고 .hwpx(주면 manifest 대신 문서에서 기대값을 다시 뽑는다)")
    c.add_argument("--strict", action="store_true", help="기대값이 내장 합성값인 스타일(fallback_styles)이 있으면 exit 2")
    c.set_defaults(func=cmd_compare)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
