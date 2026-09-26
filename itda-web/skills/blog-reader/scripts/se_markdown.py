"""se_markdown.py - SmartEditor 컴포넌트 인식 마크다운 렌더러.

REQ-BLOGREADER-003.6: SmartEditor 컴포넌트 인식 마크다운 변환.
REQ-BLOGREADER-003.7: 추정 헤딩 생성 절대 금지.

실 fixture 기준 확인된 컴포넌트 (se_post.html, astroyuji/224286211021):
  - se-quotation (21개): blockquote → > 라인
  - se-table (18개): markdown 표 (첫 행=헤더, colspan best-effort)
  - se-text (15개): 단락, <b>/<strong> → **...**
  - se-image (4개): 본문 위치에 inline ![alt](url)

표준 SE 컴포넌트이나 fixture에 미존재 (방어적 구현):
  - se-horizontalLine → ---
  - se-list → - / 1.
  - se-oglink → [제목](url)

TC-3: 표준 라이브러리(html.parser)만 사용. 직접 HTTP import 금지.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


# ---------------------------------------------------------------------------
# 내부 파싱 유틸리티
# ---------------------------------------------------------------------------

def _strip_tags(html: str) -> str:
    """HTML 태그를 모두 제거하고 텍스트만 반환한다."""
    return re.sub(r"<[^>]+>", "", html)


def _unescape_html(text: str) -> str:
    """기본 HTML 엔티티를 디코딩한다 (표준 라이브러리 활용)."""
    import html
    return html.unescape(text)


class _SimpleHTMLParser(HTMLParser):
    """단순 텍스트 추출 파서 (볼드 마크업 처리 포함).

    REQ-003.8(b): bold 범위 텍스트를 버퍼링해 종료 시 내용 유무를 판단.
    내부가 공백·U+200B·개행만이면 마커를 생성하지 않는다.
    """

    # zero-width 문자 집합
    _ZWCHARS: frozenset[str] = frozenset("​‌‍﻿­")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        # 볼드 구간 버퍼 스택: 각 원소는 (볼드 진입 전 parts 길이, 버퍼 내용 리스트)
        self._bold_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("b", "strong"):
            # 새 볼드 버퍼 시작
            self._bold_stack.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag in ("b", "strong") and self._bold_stack:
            buf = self._bold_stack.pop()
            inner = "".join(buf)
            # zero-width + 공백 + 개행 제거 후 내용 유무 판단
            stripped = inner.strip()
            stripped = "".join(ch for ch in stripped if ch not in self._ZWCHARS)
            if stripped:
                # 마커 바깥으로 공백 이동
                leading = " " if inner and inner[0] == " " else ""
                trailing = " " if inner and inner[-1] == " " else ""
                self._append(f"{leading}**{inner.strip()}**{trailing}")
            else:
                # 빈 bold → 의미 있는 텍스트(공백)만 보존
                # 순수 공백/ZWS만이면 아무것도 출력하지 않음
                # (인접 텍스트 흐름 유지를 위해 공백 1개 보존 — 단, 마커는 없음)
                if inner.strip(" \t\n\r") == "":
                    # 공백/개행뿐 → 아무것도 추가 안 함 (인접 span 텍스트로 충분)
                    pass
                # else: ZWS뿐 → 역시 무시

    def handle_data(self, data: str) -> None:
        self._append(data)

    def _append(self, text: str) -> None:
        """현재 활성 버퍼(볼드 스택 상단) 또는 parts에 텍스트를 추가한다."""
        if self._bold_stack:
            self._bold_stack[-1].append(text)
        else:
            self._parts.append(text)

    def get_text(self) -> str:
        # 스택에 남은 미닫힌 버퍼 처리 (비정상 HTML 대비)
        while self._bold_stack:
            buf = self._bold_stack.pop()
            inner = "".join(buf)
            self._parts.append(inner)
        return "".join(self._parts)


def _extract_text_with_bold(html: str) -> str:
    """HTML에서 텍스트를 추출하되 <b>/<strong>을 **...**로 변환한다.

    REQ-003.8(b): 빈 bold 마커(**...**) 생성 금지.
    - U+200B(​), U+FEFF, U+200C/D, 공백, 개행뿐인 bold → 마커 없이 무시.
    - 의미 있는 텍스트가 있을 때만 ** 마커 생성.
    - 안전망: 최종 결과에 \\*\\*\\s*\\*\\* 패턴이 남으면 제거.
    """
    parser = _SimpleHTMLParser()
    parser.feed(html)
    text = parser.get_text()

    # 안전망 후처리: 버퍼링 로직에서 놓친 빈 마커 쌍 제거
    # 정상 **a** **b** 인접 패턴은 손상하지 않음
    # 대상: ** \n ** / **​** / ** ** / **** 등
    def _remove_empty_bold(m: re.Match) -> str:
        inner = m.group(1)
        # zero-width 제거 후 판단
        zw = frozenset("​‌‍﻿­")
        clean = "".join(ch for ch in inner if ch not in zw).strip()
        if not clean:
            # 빈 bold — 내부 텍스트(공백/개행)도 제거 (인접 텍스트 흐름에서 불필요)
            return ""
        # 정상 bold — leading/trailing 공백 마커 바깥으로
        leading = " " if inner != inner.lstrip() else ""
        trailing = " " if inner != inner.rstrip() else ""
        return f"{leading}**{inner.strip()}**{trailing}"

    text = re.sub(r"\*\*((?:[^*]|\*(?!\*))*)\*\*", _remove_empty_bold, text)

    # 이중 적용 잔재 (**** 류) 제거
    text = re.sub(r"\*{4,}", "", text)

    return text.strip()


# ---------------------------------------------------------------------------
# SE 컴포넌트별 렌더러
# ---------------------------------------------------------------------------

def _render_se_text(component_html: str) -> str:
    """se-text 컴포넌트 → 단락 텍스트 마크다운.

    구조: se-component-content > se-section > se-module-text > p.se-text-paragraph > span
    <b>/<strong> → **...**
    폰트/색상/정렬 클래스·style 속성은 무시.
    빈 단락(공백 문자만)은 빈 줄로 변환.
    """
    # p.se-text-paragraph 단위로 분리
    paragraphs: list[str] = []

    # p 태그 내용 추출 (단순 정규식으로 p 태그 내용 추출)
    p_contents = re.findall(r"<p\b[^>]*>(.*?)</p>", component_html, re.DOTALL)

    for p_html in p_contents:
        text = _extract_text_with_bold(p_html)
        # 완전히 비어 있거나 제로폭 공백(​)만 있는 경우 빈 줄로 처리
        cleaned = re.sub(r"[​ \s]", "", text)
        if not cleaned:
            paragraphs.append("")
        else:
            paragraphs.append(text)

    # 빈 단락이 연속되면 하나로 합치지 않고 그대로 유지 (내용 보존)
    # 단, 전체가 비어 있으면 빈 문자열 반환
    if all(p == "" for p in paragraphs):
        return ""

    return "\n".join(paragraphs)


def _extract_cell_text(cell_html: str) -> str:
    """td.se-cell 내부에서 텍스트를 추출한다.

    한 셀에 se-module-text 여러 개 가능 → 줄바꿈으로 합침 → 셀 내 개행은 공백치환.
    마크다운 표 파이프 | 는 \\|로 이스케이프.
    """
    # se-module-text 단위로 분리해서 각각 추출 후 공백으로 결합
    module_texts: list[str] = []

    # div.se-module.se-module-text 내용 추출
    module_contents = re.findall(
        r'<div\b[^>]*class="[^"]*se-module[^"]*se-module-text[^"]*"[^>]*>(.*?)</div>',
        cell_html,
        re.DOTALL,
    )

    if module_contents:
        for module_html in module_contents:
            text = _extract_text_with_bold(module_html)
            if text:
                module_texts.append(text)
        cell_text = " ".join(module_texts)
    else:
        # 폴백: 전체 HTML에서 텍스트 추출
        cell_text = _extract_text_with_bold(cell_html)

    # 셀 내 개행 → 공백 치환 (마크다운 표는 셀 내 개행 미지원)
    cell_text = re.sub(r"\s*\n\s*", " ", cell_text).strip()

    # 파이프 이스케이프
    cell_text = cell_text.replace("|", "\\|")

    return cell_text


def _is_single_cell_layout_box(component_html: str) -> bool:
    """se-table이 1행×1열 레이아웃 박스인지 판정한다.

    REQ-003.8(a): SmartEditor가 강조 박스로 사용하는 1행 1열 se-table 패턴 감지.
    tr.se-tr 개수 == 1 이고 그 안에 td.se-cell(또는 <td>) 개수 == 1이면 단일 셀 박스.
    colspan 속성 값은 무시하고 실제 td 태그 개수로만 판정한다.

    Args:
        component_html: se-table 컴포넌트 전체 HTML.

    Returns:
        True이면 단일 셀 박스 → blockquote로 렌더.
        False이면 다열/다행 표 → 마크다운 표로 렌더.
    """
    tr_blocks = re.findall(
        r"<tr\b[^>]*class=\"[^\"]*se-tr[^\"]*\"[^>]*>(.*?)</tr>",
        component_html,
        re.DOTALL,
    )
    if len(tr_blocks) != 1:
        return False

    # 단일 tr 안의 td 개수 확인
    td_matches = re.findall(r"<td\b[^>]*>", tr_blocks[0])
    return len(td_matches) == 1


def _render_se_table(component_html: str) -> str:
    """se-table 컴포넌트 → 마크다운 표 또는 blockquote.

    REQ-003.8(a): 1행×1열 단일 셀 박스 → blockquote로 렌더링.
                  SmartEditor가 강조 박스로 쓰는 패턴이며, 1열 표는 생성하지 않는다.
    다열/다행 표 → 마크다운 표.

    구조: table.se-table-content > tbody > tr.se-tr > td.se-cell
    첫 행을 헤더로 처리하고 |---|구분선 삽입.
    colspan > 1: 해당 칸수만큼 빈 셀 추가 (best-effort, 마크다운 병합 미지원).
    rowspan > 1: 다음 행 동일 열에 빈 셀 삽입 (best-effort, 현재는 무시하고 값 유지).
    열 수는 첫 행 기준 정규화.
    """
    # REQ-003.8(a): 단일 셀 레이아웃 박스 → blockquote
    if _is_single_cell_layout_box(component_html):
        # td 내용 추출 후 blockquote로 렌더
        tr_blocks = re.findall(
            r"<tr\b[^>]*class=\"[^\"]*se-tr[^\"]*\"[^>]*>(.*?)</tr>",
            component_html,
            re.DOTALL,
        )
        if tr_blocks:
            td_blocks = re.findall(r"<td\b[^>]*>(.*?)</td>", tr_blocks[0], re.DOTALL)
            if td_blocks:
                cell_text = _extract_text_with_bold(td_blocks[0])
                cleaned = re.sub(r"[​ \s]", "", cell_text)
                if cleaned:
                    lines = [f"> {line}" for line in cell_text.splitlines() if line.strip()]
                    return "\n".join(lines)
        return ""

    # tr.se-tr 블록 추출
    tr_blocks = re.findall(
        r"<tr\b[^>]*class=\"[^\"]*se-tr[^\"]*\"[^>]*>(.*?)</tr>",
        component_html,
        re.DOTALL,
    )

    if not tr_blocks:
        return ""

    rows: list[list[str]] = []

    for tr_html in tr_blocks:
        # td.se-cell 블록 추출
        # colspan, rowspan 속성 추출 포함
        td_blocks = re.findall(
            r"<td\b([^>]*)>(.*?)</td>",
            tr_html,
            re.DOTALL,
        )
        row: list[str] = []
        for td_attrs_str, td_html in td_blocks:
            # colspan 추출
            colspan_match = re.search(r'colspan="(\d+)"', td_attrs_str)
            colspan = int(colspan_match.group(1)) if colspan_match else 1

            cell_text = _extract_cell_text(td_html)
            row.append(cell_text)

            # colspan > 1: 빈 셀 추가 (best-effort)
            for _ in range(colspan - 1):
                row.append("")

        if row:
            rows.append(row)

    if not rows:
        return ""

    # 열 수 정규화: 첫 행 기준
    col_count = len(rows[0])
    normalized_rows: list[list[str]] = []
    for row in rows:
        if len(row) < col_count:
            row = row + [""] * (col_count - len(row))
        elif len(row) > col_count:
            row = row[:col_count]
        normalized_rows.append(row)

    # 마크다운 표 생성: 첫 행이 헤더
    lines: list[str] = []

    # 헤더 행
    header = normalized_rows[0]
    lines.append("| " + " | ".join(header) + " |")

    # 구분선
    lines.append("| " + " | ".join(["---"] * col_count) + " |")

    # 나머지 행
    for row in normalized_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _render_se_quotation(component_html: str) -> str:
    """se-quotation 컴포넌트 → blockquote (> 라인).

    구조: blockquote.se-quotation-container > div.se-module-text > p > span
    """
    # blockquote 내용 추출
    blockquote_match = re.search(
        r"<blockquote\b[^>]*>(.*?)</blockquote>",
        component_html,
        re.DOTALL,
    )
    if not blockquote_match:
        # 폴백: 전체 텍스트 추출
        text = _extract_text_with_bold(component_html)
        if not text:
            return ""
        return "\n".join(f"> {line}" for line in text.splitlines())

    inner_html = blockquote_match.group(1)

    # p.se-text-paragraph 단위로 분리해서 텍스트 추출
    p_contents = re.findall(r"<p\b[^>]*>(.*?)</p>", inner_html, re.DOTALL)

    lines: list[str] = []
    if p_contents:
        for p_html in p_contents:
            text = _extract_text_with_bold(p_html)
            cleaned = re.sub(r"[​ \s]", "", text)
            if cleaned:
                lines.append(f"> {text}")
    else:
        # 폴백: 전체 텍스트
        text = _extract_text_with_bold(inner_html)
        if text:
            lines.append(f"> {text}")

    return "\n".join(lines)


def _render_se_image(component_html: str) -> str:
    """se-image 컴포넌트 → inline 이미지 마크다운.

    src 우선순위: data-lazy-src > src
    본문 등장 위치 그대로 인라인.
    """
    # img 태그 찾기
    img_match = re.search(r"<img\b([^>]*)>", component_html, re.DOTALL)
    if not img_match:
        return ""

    attrs_str = img_match.group(1)

    # data-lazy-src 우선
    lazy_src_match = re.search(r'data-lazy-src="([^"]*)"', attrs_str)
    src_match = re.search(r'\bsrc="([^"]*)"', attrs_str)

    url = ""
    if lazy_src_match and lazy_src_match.group(1):
        url = lazy_src_match.group(1)
    elif src_match and src_match.group(1):
        url = src_match.group(1)

    if not url:
        return ""

    # alt 추출
    alt_match = re.search(r'\balt="([^"]*)"', attrs_str)
    alt = alt_match.group(1) if alt_match else ""

    return f"![{alt}]({url})"


def _render_se_horizontal_line(_component_html: str) -> str:
    """se-horizontalLine → --- (방어적, fixture 미검증)."""
    return "---"


def _render_se_list(component_html: str) -> str:
    """se-list → - / 1. 마크다운 리스트 (방어적, fixture 미검증)."""
    # ul/ol 감지
    is_ordered = bool(re.search(r"<ol\b", component_html, re.IGNORECASE))
    li_contents = re.findall(r"<li\b[^>]*>(.*?)</li>", component_html, re.DOTALL)

    lines: list[str] = []
    for i, li_html in enumerate(li_contents, 1):
        text = _extract_text_with_bold(li_html)
        if text:
            prefix = f"{i}." if is_ordered else "-"
            lines.append(f"{prefix} {text}")

    return "\n".join(lines)


def _render_se_material(component_html: str) -> str:
    """se-material 글감카드 → > [타입] 제목 — 링크 한 줄.

    REQ-003.6 신규: se-material(영화/책/장소/상품 등 글감카드) 렌더러.

    추출 전략:
    1. <a ... data-linkdata='...'> 속성값 → HTML unescape → json.loads
    2. 키: type(타입), title(제목), link(URL)
    3. 출력: > [{type_kr}] {title} — {link}  (link 없으면 — {link} 생략)
    4. 파싱 실패 시: 가시 텍스트 정규화 (알려진 UI 부속 제거), 크래시 없음.

    type_kr 매핑:
    - movie → 영화
    - book → 책/도서
    - place → 장소
    - product / shopping → 상품
    - tv → TV프로그램
    - music → 음악
    미지 type → 원문 그대로 (추정 날조 금지)

    REQ-003.7 불변: 추정 헤딩 생성 절대 금지.
    TC-3: 표준 라이브러리(html.parser, html.unescape, json, re)만 사용.
    """
    import html as _html_mod
    import json

    _TYPE_KR: dict[str, str] = {
        "movie": "영화",
        "book": "책/도서",
        "place": "장소",
        "product": "상품",
        "shopping": "상품",
        "tv": "TV프로그램",
        "music": "음악",
    }

    # data-linkdata 속성 추출 (단따옴표 래핑)
    linkdata_match = re.search(r"data-linkdata='([^']*)'", component_html, re.DOTALL)
    if not linkdata_match:
        # 이중따옴표 래핑 시도
        linkdata_match = re.search(r'data-linkdata="([^"]*)"', component_html, re.DOTALL)

    if linkdata_match:
        raw_linkdata = linkdata_match.group(1)
        # HTML 엔티티 디코딩 (&#x3D; → =, &amp; → &, &quot; → " 등)
        decoded = _html_mod.unescape(raw_linkdata)
        try:
            data = json.loads(decoded)
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    if data:
        type_raw = str(data.get("type", "") or "").strip()
        type_kr = _TYPE_KR.get(type_raw, type_raw) if type_raw else ""
        title = str(data.get("title", "") or "").strip()
        link = str(data.get("link", "") or "").strip()

        type_label = f"[{type_kr}]" if type_kr else "[글감]"

        if title:
            if link:
                return f"> {type_label} {title} — {link}"
            else:
                return f"> {type_label} {title}"
        # title 없으면 폴백으로 가시 텍스트 시도
        # (data가 파싱됐지만 title이 비어 있는 경우)

    # 폴백: 가시 텍스트 정규화 (data-linkdata 없거나 title 없을 때)
    # UI 부속 제거 후 첫 비공백 라인만
    _UI_ARTIFACTS = re.compile(
        r"블로그\s*글\s*더보기|블로그\s*더보기|더보기",
        re.IGNORECASE,
    )
    text = _extract_text_with_bold(component_html)
    # 알려진 UI 부속 제거
    text = _UI_ARTIFACTS.sub("", text)
    # 연속 공백/개행 정규화
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    # 각 줄에서 비어 있지 않은 첫 줄만 사용
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        return lines[0]
    return ""


def _render_se_oglink(component_html: str) -> str:
    """se-oglink → [제목](url) 또는 url 한 줄 (방어적, fixture 미검증)."""
    # og:url 또는 href 추출
    url_match = re.search(r'href="([^"]*)"', component_html)
    title_match = re.search(r'class="[^"]*og-title[^"]*"[^>]*>(.*?)</[^>]+>', component_html, re.DOTALL)

    url = url_match.group(1) if url_match else ""
    title = _strip_tags(title_match.group(1)).strip() if title_match else ""

    if url and title:
        return f"[{title}]({url})"
    elif url:
        return url
    return ""


def _render_se_placesmap(component_html: str) -> str:
    """se-placesMap (장소 임베드) → > [장소] 이름 — 주소 한 줄.

    data-linkdata JSON에서 name/address를 추출한다.
    checkin_button_wrap 등 UI chrome은 일절 포함하지 않는다.

    실 fixture 검증 (todaytravels/224287192534, 2026-05-16):
      <a data-linkdata='{"name":"광화문광장","address":"서울특별시 종로구 세종대로 175 세종이야기",...}'>
    """
    import html as _html_mod
    import json

    # data-linkdata JSON 우선
    linkdata_match = re.search(r"data-linkdata='([^']*)'", component_html, re.DOTALL)
    if not linkdata_match:
        linkdata_match = re.search(r'data-linkdata="([^"]*)"', component_html, re.DOTALL)

    name = ""
    address = ""

    if linkdata_match:
        raw = linkdata_match.group(1)
        decoded = _html_mod.unescape(raw)
        try:
            data = json.loads(decoded)
            name = str(data.get("name", "") or "").strip()
            address = str(data.get("address", "") or "").strip()
        except (json.JSONDecodeError, ValueError):
            pass

    # JSON 실패 폴백: se-map-title / se-map-address 태그
    if not name:
        title_m = re.search(r'class="se-map-title"[^>]*>(.*?)</strong>', component_html, re.DOTALL)
        if title_m:
            name = _strip_tags(title_m.group(1)).strip()
    if not address:
        addr_m = re.search(r'class="se-map-address"[^>]*>(.*?)</p>', component_html, re.DOTALL)
        if addr_m:
            address = _strip_tags(addr_m.group(1)).strip()

    if name and address:
        return f"> [장소] {name} — {address}"
    elif name:
        return f"> [장소] {name}"
    return ""


def _render_se_imagegroup(component_html: str) -> str:
    """se-imageGroup (캐러셀/콜라주 갤러리) → 각 이미지 inline 마크다운.

    se-imageGroup 내 개별 se-module-image를 모두 추출한다.
    navigation 버튼(se-imageGroup-navigation) 텍스트("Previous image", "Next image")는
    렌더러 내부에서 완전히 무시한다 — data-lazy-src (정상 해상도) 우선.

    실 fixture 검증 (todaytravels/224287192534, 2026-05-16):
      <img src="...?type=w80_blur" data-lazy-src="...?type=w400" ...>
    """
    lines: list[str] = []

    # se-module-image 단위로 img 태그 추출
    module_pattern = re.compile(
        r'<div\b[^>]*class="[^"]*se-module-image[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    for module_m in module_pattern.finditer(component_html):
        module_html = module_m.group(1)
        img_m = re.search(r"<img\b([^>]*)>", module_html, re.DOTALL)
        if not img_m:
            continue
        attrs_str = img_m.group(1)

        # data-lazy-src 우선, src 폴백
        lazy_m = re.search(r'data-lazy-src="([^"]*)"', attrs_str)
        src_m = re.search(r'\bsrc="([^"]*)"', attrs_str)

        url = ""
        if lazy_m and lazy_m.group(1):
            url = lazy_m.group(1)
        elif src_m and src_m.group(1):
            url = src_m.group(1)

        if not url:
            continue

        alt_m = re.search(r'\balt="([^"]*)"', attrs_str)
        alt = alt_m.group(1) if alt_m else ""
        lines.append(f"![{alt}]({url})")

    return "\n".join(lines)


def _render_se_sticker(_component_html: str) -> str:
    """se-sticker → 빈 문자열 (본문 텍스트/이미지에 포함 안 함).

    스티커는 장식적 요소로 콘텐츠 가치 없음.
    OGQ storep 스티커 URL이 images[] 또는 body에 누출되지 않도록 명시적으로 차단.
    """
    return ""


def _render_unknown_component(component_html: str) -> str:
    """미지(未知) se-component → 내부 텍스트 평탄화 폴백. 절대 크래시 없음."""
    text = _extract_text_with_bold(component_html)
    cleaned = re.sub(r"[​ \s]", "", text)
    if not cleaned:
        return ""
    return text.strip()


# ---------------------------------------------------------------------------
# 컴포넌트 타입 → 렌더러 매핑
# ---------------------------------------------------------------------------

# # @MX:ANCHOR: [AUTO] render_smarteditor_markdown — SmartEditor 마크다운 렌더러 공개 API
# # @MX:REASON: post_parser.parse_post_html, output_format.format_markdown_post 등에서 직접 호출 (fan_in >= 3 예상)

_COMPONENT_RENDERERS: dict[str, Any] = {
    "se-text": _render_se_text,
    "se-table": _render_se_table,
    "se-quotation": _render_se_quotation,
    "se-image": _render_se_image,
    "se-imageGroup": _render_se_imagegroup,
    "se-material": _render_se_material,
    "se-horizontalLine": _render_se_horizontal_line,
    "se-list": _render_se_list,
    "se-oglink": _render_se_oglink,
    "se-placesMap": _render_se_placesmap,
    "se-sticker": _render_se_sticker,
}


def _detect_component_type(component_classes: str) -> str | None:
    """div.se-component의 class 문자열에서 컴포넌트 타입을 감지한다.

    예: "se-component se-text se-l-default" → "se-text"
    """
    for comp_type in _COMPONENT_RENDERERS:
        # 정확한 클래스 매칭 (공백 구분)
        if re.search(r"(?:^|\s)" + re.escape(comp_type) + r"(?:\s|$)", component_classes):
            return comp_type
    return None


def render_smarteditor_markdown(html: str) -> str:
    """SmartEditor 컴포넌트를 인식해 마크다운으로 변환한다.

    REQ-003.6: SmartEditor 컴포넌트 인식 렌더러.
    REQ-003.7: 추정 헤딩(#/##) 생성 절대 금지.

    Args:
        html: 네이버 블로그 포스트 페이지 HTML.
             se-main-container 내부 또는 전체 페이지 HTML 모두 허용.

    Returns:
        마크다운 문자열. 컴포넌트 사이 빈 줄 1개로 구분.
        비어 있거나 se-main-container가 없으면 빈 문자열.

    Notes:
        - 표준 라이브러리만 사용 (html.parser, re). 직접 HTTP import 없음.
        - 미지 컴포넌트는 내부 텍스트 평탄화 폴백 (크래시 없음).
        - se-horizontalLine / se-list / se-oglink: 방어적 구현, 라이브 미검증.
    """
    if not html:
        return ""

    # se-main-container 추출
    main_match = re.search(
        r'<div\b[^>]*class="[^"]*se-main-container[^"]*"[^>]*>(.*)',
        html,
        re.DOTALL,
    )
    if not main_match:
        return ""

    main_html = main_match.group(1)

    # se-component 블록 순차 추출
    # 중첩이 없는 최상위 se-component div 단위로 분리
    # 전략: div.se-component 시작 태그를 찾고, 그 depth가 0으로 돌아올 때까지의 내용 추출
    rendered_blocks: list[str] = []

    # se-component div 위치 순차 탐색
    pos = 0
    html_len = len(main_html)

    # 정규식으로 div.se-component 시작 위치 목록 생성
    # <div class="se-component ..."> 또는 <div class="... se-component ...">
    comp_start_pattern = re.compile(
        r'<div\b([^>]*class="[^"]*\bse-component\b[^"]*"[^>]*)>',
        re.DOTALL,
    )

    while pos < html_len:
        m = comp_start_pattern.search(main_html, pos)
        if not m:
            break

        comp_attrs = m.group(1)
        comp_start = m.start()
        tag_end = m.end()

        # 컴포넌트 타입 감지
        class_match = re.search(r'class="([^"]*)"', comp_attrs)
        comp_classes = class_match.group(1) if class_match else ""
        comp_type = _detect_component_type(comp_classes)

        # se-component의 종료 div 위치 탐색 (depth tracking)
        depth = 1
        search_pos = tag_end

        while depth > 0 and search_pos < html_len:
            next_open = main_html.find("<div", search_pos)
            next_close = main_html.find("</div>", search_pos)

            if next_close == -1:
                # 종료 태그 없음 → 끝까지
                search_pos = html_len
                break

            if next_open != -1 and next_open < next_close:
                depth += 1
                search_pos = next_open + 4  # "<div" 다음으로
            else:
                depth -= 1
                search_pos = next_close + 6  # "</div>" 다음으로

        comp_end = search_pos
        component_html = main_html[comp_start:comp_end]

        # 렌더링
        try:
            if comp_type is not None:
                renderer = _COMPONENT_RENDERERS[comp_type]
                rendered = renderer(component_html)
            else:
                rendered = _render_unknown_component(component_html)
        except Exception:  # noqa: BLE001 — 절대 크래시 없음
            rendered = _render_unknown_component(component_html)

        if rendered:
            rendered_blocks.append(rendered)

        pos = comp_end

    return "\n\n".join(rendered_blocks)
