"""post_parser.py - 네이버 블로그 포스트 페이지 HTML 파싱.

REQ-BLOGREADER-003: 포스트 본문 추출
  - REQ-003.1: 반환 dict 필수 필드 정의 (v0.7.0: body 단일 키)
  - REQ-003.2: body_format="markdown"(기본) → SmartEditor 마크다운 렌더
  - REQ-003.3: images 본문 등장 순서대로 {url, alt}
  - REQ-003.4: body_format="html" → 본문 영역 원본 HTML 스니펫
  - REQ-003.5: 광고/관련글/추천 블로거 영역 제외

TC-3: 표준 라이브러리(html.parser)만 사용.

설계 결정 (v0.5.3): post detail에서 published_at 제거.
  발행시각은 list/search (addDate 절대값) 경로로만 제공한다.
  post_parser는 발행시각 파싱 책임을 갖지 않는다.

설계 결정 (v0.7.0, BREAKING): body 단일 캐노니컬 필드.
  body_text/body_html/body_markdown 다중 키 폐지.
  include_html/include_markdown 파라미터 폐지 → body_format="markdown"|"html".
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from errors import BlogStructureChangedError
from post_list_parser import normalize_category

# # @MX:ANCHOR: [AUTO] parse_post_html — 포스트 파싱 단일 진입점
# # @MX:REASON: NaverBlogAdapter.get_post가 직접 호출하는 공개 API (fan_in >= 3 예상)

# 본문 영역 마커 클래스
_MAIN_CONTAINER_CLASSES = {"se-main-container", "se_main_container"}

# 제외할 영역 클래스 (광고, 관련 글, 추천 블로거)
_EXCLUDED_CLASSES = {
    "ad_container",
    "related_posts",
    "recommend_blogger",
    "post_ad",
    "blog_ad",
}

# 이미지 소스를 가져올 속성 우선순위.
# data-lazy-src 우선: 실 HTML에서 src=w80_blur(lazy thumb), data-lazy-src=w400(정상).
_IMG_SRC_ATTRS = ("data-lazy-src", "data-src", "src")

# 본문 이미지에서 제외할 URL 접두 패턴 (장식용 스티커 등).
# OGQ storep 스티커: storep-phinf.pstatic.net/ogq_
_EXCLUDED_IMG_URL_PREFIXES = (
    "storep-phinf.pstatic.net/ogq_",
)

# ISS-voiddepth: void 요소는 endtag가 없어 depth 증가 금지
_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


def _extract_url_parts(url: str) -> tuple[str, str]:
    """URL에서 blog_id와 log_no를 추출한다.

    m.blog.naver.com/{blog_id}/{log_no} 형식 가정.
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    blog_id = parts[0] if len(parts) > 0 else ""
    log_no = parts[1] if len(parts) > 1 else ""
    return blog_id, log_no


class _TextExtractor(HTMLParser):
    """HTML에서 텍스트만 추출하는 간단한 파서."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0  # 제외 영역 깊이 추적

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        classes = set((attr_dict.get("class") or "").split())
        if classes & _EXCLUDED_CLASSES:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


class _PostPageParser(HTMLParser):
    """네이버 블로그 포스트 페이지 전체 파서.

    - 메타 정보 수집 (title, author, category, tags 등 — published_at 제외, v0.5.3)
    - se-main-container 내 본문 텍스트 + 이미지 수집
    - 광고/관련글 영역 자동 제외
    """

    def __init__(self, include_html: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.include_html = include_html

        # 메타 정보
        self.og_title: str = ""
        self.og_image: str = ""
        self.blog_author: str = ""

        # 구조 추적
        self._in_main_container = False
        self._main_depth = 0  # se-main-container 깊이 추적
        self._in_excluded = False
        self._excluded_depth = 0
        # ISS-adleak: 내부 제외 영역 진입 시 main_depth 저장 (탈출 판정용)
        self._excluded_entry_depth = 0

        # 일반 DOM 깊이 추적 (외부 제외 영역용)
        self._current_outer_excluded_tag: str | None = None
        self._outer_excluded_depth = 0

        # 본문 수집
        self._body_parts: list[str] = []
        self._body_html_parts: list[str] = []
        self._images: list[dict[str, str]] = []

        # 태그/카테고리/author/댓글 수 등
        self.title: str = ""
        self.author: str = ""
        self.author_nickname: str | None = None
        self.updated_at: str | None = None
        self.category: str = ""
        self.tags: list[str] = []
        self.comment_count: int = 0
        self.like_count: int | None = None

        # 내부 수집 상태
        self._collecting_title = False
        self._collecting_author = False
        self._collecting_nick = False
        self._collecting_category = False
        self._collecting_tag = False
        self._collecting_comment_count = False
        self._collecting_like_count = False

        # ISS-endtagreset: 각 수집 상태에 대응하는 시작 depth 기록
        # handle_endtag에서 해당 depth에서만 플래그 해제
        self._collecting_title_depth: int = 0
        self._collecting_author_depth: int = 0
        self._collecting_nick_depth: int = 0
        self._collecting_category_depth: int = 0
        self._collecting_tag_depth: int = 0
        self._collecting_comment_count_depth: int = 0
        self._collecting_like_count_depth: int = 0

        # 본문 밖 DOM depth (수집 상태의 endtag 매칭용)
        self._outer_depth: int = 0

        # 제외 영역 추적 (본문 밖)
        self._outer_skip_depth = 0

        # 현재 태그 클래스 추적 (nested exclude 처리)
        self._tag_stack: list[set[str]] = []  # 각 태그의 클래스 셋 스택

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        classes = set((attr_dict.get("class") or "").split())

        # 메타 태그 처리
        if tag == "meta":
            prop = attr_dict.get("property") or attr_dict.get("name") or ""
            content = attr_dict.get("content") or ""
            if prop == "og:title" and content:
                self.og_title = content
            elif prop == "og:image" and content:
                self.og_image = content
            elif prop == "blog:author" and content:
                self.blog_author = content
            # 실측 마커: <meta property="naverblog:nickname" content="그린캐롯"/>
            # 이것이 author_nickname의 가장 안정적인 소스
            elif prop == "naverblog:nickname" and content and not self.author_nickname:
                self.author_nickname = content

        # 외부 제외 영역 진입
        if classes & _EXCLUDED_CLASSES and not self._in_main_container:
            self._outer_skip_depth += 1

        if self._outer_skip_depth > 0 and not self._in_main_container:
            return

        # se-main-container 진입
        if classes & _MAIN_CONTAINER_CLASSES:
            self._in_main_container = True
            self._main_depth = 1
            if self.include_html:
                self._body_html_parts.append(f"<{tag}>")
            return

        if self._in_main_container:
            # ISS-adleak 완전 수정: se-main-container 내부 중첩 광고/관련글 블록도 제외.
            # 외부(_outer_skip_depth)와 동일한 depth 기반 skip 메커니즘을 내부에 적용.
            # _in_excluded/_excluded_depth는 이미 선언되어 있었으나 미사용 상태였음.

            # 내부 제외 영역 중 → depth만 추적하고 수집/이미지 처리 건너뜀
            if self._in_excluded:
                if tag not in _VOID_ELEMENTS:
                    self._main_depth += 1
                return

            # 내부 제외 영역 진입 감지 (이미 진입 중이 아닌 경우에만)
            if classes & _EXCLUDED_CLASSES:
                self._in_excluded = True
                self._excluded_depth += 1
                # 진입 직전의 main_depth를 저장 (탈출 시 이 depth 아래로 내려가면 탈출)
                if tag not in _VOID_ELEMENTS:
                    self._main_depth += 1
                self._excluded_entry_depth = self._main_depth
                return

            # ISS-voiddepth: void 요소는 endtag가 없으므로 depth 증가 금지
            if tag not in _VOID_ELEMENTS:
                self._main_depth += 1

            # 이미지 처리
            if tag == "img":
                src = ""
                for attr_name in _IMG_SRC_ATTRS:
                    src = attr_dict.get(attr_name) or ""
                    if src:
                        break
                alt = attr_dict.get("alt") or ""
                if src:
                    # OGQ 스티커 등 장식용 URL 제외
                    is_excluded = any(
                        pat in src for pat in _EXCLUDED_IMG_URL_PREFIXES
                    )
                    if not is_excluded:
                        self._images.append({"url": src, "alt": alt})

            if self.include_html:
                attr_str = " ".join(
                    f'{k}="{v}"' for k, v in attrs if v is not None
                )
                self._body_html_parts.append(
                    f"<{tag} {attr_str}>" if attr_str else f"<{tag}>"
                )
            return

        # 본문 밖 메타 정보 수집
        # ISS-voiddepth: 본문 밖 void 요소도 depth 증가 금지
        is_void = tag in _VOID_ELEMENTS
        if not is_void:
            self._outer_depth += 1

        # ISS-voidcollect 근본 수정: void 요소에 트리거 클래스가 붙으면 endtag가 없어
        # _collecting_*_depth 해제 조건이 절대 미성립 → 플래그 영구 leak.
        # void 요소는 자식을 가질 수 없으므로 플래그를 set하지 않고 즉시 단발 처리한다.
        if is_void:
            # like_count는 data-count 속성으로만 값을 얻음 (void에도 동일)
            if "like_count" in classes:
                count_str = attr_dict.get("data-count") or ""
                if count_str.isdigit():
                    self.like_count = int(count_str)
            # 그 외 트리거 클래스는 void 요소에 붙지 않음 (span/div 계열이 일반적)
            return

        if "se_textarea" in classes or "post_title" in classes:
            self._collecting_title = True
            self._collecting_title_depth = self._outer_depth
        if "author_name" in classes:
            self._collecting_author = True
            self._collecting_author_depth = self._outer_depth
        if "author_nick" in classes:
            self._collecting_nick = True
            self._collecting_nick_depth = self._outer_depth
        if "post_category" in classes or "post_category_name" in classes:
            self._collecting_category = True
            self._collecting_category_depth = self._outer_depth
        if "post_tag" in classes:
            self._collecting_tag = True
            self._collecting_tag_depth = self._outer_depth
        if "u_cnt" in classes:
            # 댓글 수 span
            self._collecting_comment_count = True
            self._collecting_comment_count_depth = self._outer_depth
        if "like_count" in classes:
            # like_count 속성 우선
            count_str = attr_dict.get("data-count") or ""
            if count_str.isdigit():
                self.like_count = int(count_str)
            else:
                self._collecting_like_count = True
                self._collecting_like_count_depth = self._outer_depth

        # ── 실 HTML 마커 (라이브 실측 2026-05-15) ──────────────────────────────
        # author: <div class="blog_authorArea"> ... <strong class="ell">그린캐롯</strong>
        # blog_author_area에 진입하면 내부 strong.ell 텍스트를 author로 수집
        if "blog_authorArea" in classes:
            self._in_blog_author_area = True  # type: ignore[attr-defined]
        if "ell" in classes and tag == "strong" and getattr(self, "_in_blog_author_area", False):
            # author는 이 strong 텍스트 — _collecting_author로 수집
            if not self.author:
                self._collecting_author = True
                self._collecting_author_depth = self._outer_depth

        # category: <div class="blog_category"><a href="...">시황정리</a></div>
        if "blog_category" in classes:
            self._in_blog_category = True  # type: ignore[attr-defined]
        if getattr(self, "_in_blog_category", False) and tag == "a" and not self.category:
            self._collecting_category = True
            self._collecting_category_depth = self._outer_depth

        # nickname: <strong class="nick"><span class="ell">그린캐롯(astroyuji)</span></strong>
        # naverblog:nickname meta가 우선; 없으면 nick > span.ell 텍스트에서 추출
        if "nick" in classes and tag == "strong":
            self._in_nick_strong = True  # type: ignore[attr-defined]
        if getattr(self, "_in_nick_strong", False) and tag == "span" and "ell" in classes:
            if not self.author_nickname:
                self._collecting_nick = True
                self._collecting_nick_depth = self._outer_depth

    def handle_endtag(self, tag: str) -> None:
        if self._outer_skip_depth > 0 and not self._in_main_container:
            self._outer_skip_depth -= 1
            return

        if self._in_main_container:
            # ISS-voiddepth: void 요소는 handle_starttag에서 depth 증가 안 했으므로 감소도 없음
            if tag not in _VOID_ELEMENTS:
                self._main_depth -= 1

            # ISS-adleak: 내부 제외 영역 종료 처리
            if self._in_excluded:
                if tag not in _VOID_ELEMENTS:
                    # 제외 영역 진입 시 depth를 초과 증가했으므로 _excluded_depth로 추적
                    pass  # main_depth는 위에서 이미 감소
                # 내부 제외 영역의 닫힘을 _excluded_depth로 감지
                # 단: 제외 영역 내부 중첩 태그들도 동일하게 main_depth 감소 후 여기 도달
                # _excluded_depth는 별도로 추적해야 정확함
                # 각 태그의 클래스를 저장하지 않으므로 depth 기반으로만 판정:
                # 제외 영역 진입 시의 _main_depth+1에서 현재 _main_depth가 그것보다 작으면 탈출
                # 구현: _excluded_entry_depth 저장 패턴 적용
                if self._main_depth < self._excluded_entry_depth:
                    self._in_excluded = False
                    self._excluded_depth = 0
                if self._main_depth <= 0:
                    self._in_main_container = False
                return

            if self._main_depth <= 0:
                self._in_main_container = False
                if self.include_html:
                    self._body_html_parts.append(f"</{tag}>")
            elif self.include_html:
                self._body_html_parts.append(f"</{tag}>")
            return

        # ISS-endtagreset: 본문 밖 — depth 감소 + 해당 depth에서만 수집 플래그 해제
        if tag not in _VOID_ELEMENTS:
            self._outer_depth -= 1

        # 각 수집 상태의 시작 depth와 현재 depth가 일치할 때만 플래그 해제
        if self._collecting_title and self._outer_depth < self._collecting_title_depth:
            self._collecting_title = False
        if self._collecting_author and self._outer_depth < self._collecting_author_depth:
            self._collecting_author = False
            # blog_authorArea 종료 추적
            if tag == "div":
                self._in_blog_author_area = False  # type: ignore[attr-defined]
        if self._collecting_nick and self._outer_depth < self._collecting_nick_depth:
            self._collecting_nick = False
        if self._collecting_category and self._outer_depth < self._collecting_category_depth:
            self._collecting_category = False
            # blog_category div 종료
            if tag == "div":
                self._in_blog_category = False  # type: ignore[attr-defined]
        if self._collecting_tag and self._outer_depth < self._collecting_tag_depth:
            self._collecting_tag = False
        if self._collecting_comment_count and self._outer_depth < self._collecting_comment_count_depth:
            self._collecting_comment_count = False
        if self._collecting_like_count and self._outer_depth < self._collecting_like_count_depth:
            self._collecting_like_count = False

        # 실 HTML 마커 수집 종료
        if tag == "strong" and getattr(self, "_in_nick_strong", False):
            self._in_nick_strong = False  # type: ignore[attr-defined]

    def handle_data(self, data: str) -> None:
        stripped = data.strip()

        if self._outer_skip_depth > 0 and not self._in_main_container:
            return

        if self._in_main_container:
            # ISS-adleak: 내부 제외 영역 중이면 본문에 수집하지 않음
            if self._in_excluded:
                return
            if stripped:
                self._body_parts.append(stripped)
            if self.include_html:
                self._body_html_parts.append(data)
            return

        # 본문 밖 메타 수집
        if not stripped:
            return
        if self._collecting_title and not self.title:
            self.title = stripped
        if self._collecting_author and not self.author:
            self.author = stripped
        if self._collecting_nick and not self.author_nickname:
            # nick 수집: "그린캐롯(astroyuji)" → "그린캐롯" (괄호 앞 부분)
            # naverblog:nickname meta가 이미 있으면 그것을 우선 사용 (handle_starttag에서 처리)
            nick_text = stripped
            if "(" in nick_text:
                nick_text = nick_text[:nick_text.index("(")].strip()
            if nick_text:
                self.author_nickname = nick_text
        if self._collecting_category and not self.category:
            self.category = stripped
        if self._collecting_tag:
            tag_text = stripped.lstrip("#").strip()
            if tag_text and tag_text not in self.tags:
                self.tags.append(tag_text)
        if self._collecting_comment_count:
            if stripped.isdigit():
                self.comment_count = int(stripped)
        if self._collecting_like_count:
            if stripped.isdigit():
                self.like_count = int(stripped)

    def get_body_text(self) -> str:
        return "\n".join(self._body_parts)

    def get_body_html(self) -> str:
        return "".join(self._body_html_parts)


def strip_image_urls_from_body(body: str, *, is_html: bool) -> str:
    """본문에서 이미지 URL을 제거하고 [이미지: alt] 플레이스홀더로 치환한다.

    SPEC-BLOGREADER-001 REQ-003.9 (v0.11.0): --no-image-urls 옵션의 본문 변환.
    토큰 절감을 위해 이미지 URL은 버리되 alt 텍스트는 보존해 글 맥락을 유지한다.

    Args:
        body: 렌더된 본문 (markdown 또는 html).
        is_html: body가 html 스니펫이면 True (<img> 태그 치환),
                 markdown이면 False (![alt](url) 치환).

    Returns:
        이미지 URL이 제거된 본문. alt가 있으면 [이미지: alt], 없으면 [이미지].
    """
    if not body:
        return body

    def _placeholder(alt: str) -> str:
        alt = (alt or "").strip()
        return f"[이미지: {alt}]" if alt else "[이미지]"

    if is_html:
        # <img ...> 태그 → 플레이스홀더. alt 속성 보존.
        def _repl_img(m: re.Match[str]) -> str:
            attrs = m.group(1)
            alt_m = re.search(r'\balt="([^"]*)"', attrs)
            return _placeholder(alt_m.group(1) if alt_m else "")

        return re.sub(r"<img\b([^>]*)>", _repl_img, body, flags=re.DOTALL)

    # markdown: ![alt](url) → 플레이스홀더 (se-image / se-imageGroup 산출)
    def _repl_md(m: re.Match[str]) -> str:
        return _placeholder(m.group(1))

    return re.sub(r"!\[([^\]]*)\]\([^)]*\)", _repl_md, body)


def parse_post_html(
    html: str,
    url: str,
    *,
    body_format: str = "markdown",
    strip_image_urls: bool = False,
) -> dict[str, Any]:
    """네이버 블로그 포스트 HTML을 파싱해서 구조화된 dict를 반환한다.

    REQ-003.1: 단일 `body` 키 반환 (v0.7.0 BREAKING).
    REQ-003.2: body_format="markdown"(기본) → SmartEditor 마크다운 렌더.
    REQ-003.4: body_format="html" → 본문 영역 원본 HTML 스니펫.

    Args:
        html: m.blog.naver.com/{id}/{logNo} 페이지 HTML.
        url: 포스트 URL (blog_id, log_no 추출용).
        body_format: "markdown"(기본) 또는 "html". 그 외 값은 "markdown" 동작.
        strip_image_urls: True면 본문 이미지 URL을 [이미지: alt] 플레이스홀더로
                          치환하고 images 배열을 비운다 (REQ-003.9, v0.11.0).

    Returns:
        REQ-003.1 필드를 포함하는 딕셔너리.
        `body` 단일 키만 포함. body_text/body_html/body_markdown 키 없음.

    Raises:
        BlogStructureChangedError: 본문 영역(se-main-container)을 찾지 못할 때.
    """
    blog_id, log_no = _extract_url_parts(url)

    use_html_body = (body_format == "html")
    parser = _PostPageParser(include_html=use_html_body)
    parser.feed(html)

    # 본문 영역 존재 여부 확인 (이미지로 대체 가능)
    _body_text_raw = parser.get_body_text()
    if not _body_text_raw and not parser._images:
        # se-main-container가 없거나 완전히 비어 있음
        if "se-main-container" not in html and "se_main_container" not in html:
            raise BlogStructureChangedError(
                f"포스트 본문 영역(se-main-container)을 찾지 못했습니다: {url}"
            )

    # title 폴백: og:title 사용
    title = parser.title or parser.og_title

    # author 폴백: blog:author 메타 사용
    author = parser.author or parser.blog_author

    # 설계 결정 (v0.5.3): published_at은 post detail에 포함하지 않는다.
    # 발행시각은 list/search (REQ-002.5/005) 경로의 addDate 절대값으로만 제공.

    # REQ-003.1/003.2/003.4: body 단일 캐노니컬 필드 (v0.7.0 BREAKING)
    if use_html_body:
        body: str = parser.get_body_html()
    else:
        # 기본: markdown (REQ-003.2)
        from se_markdown import render_smarteditor_markdown
        body = render_smarteditor_markdown(html)

    # REQ-003.1 / REQ-002.3: 중첩 카테고리 글리프 정규화 (post HTML blog_category에도 동일 오염)
    category = normalize_category(parser.category)

    result: dict[str, Any] = {
        "blog_id": blog_id,
        "log_no": log_no,
        "title": title,
        "author": author,
        "updated_at": parser.updated_at,
        "category": category,
        "tags": parser.tags,
        "body": body,
        "images": parser._images,
        "comment_count": parser.comment_count,
    }

    # REQ-003.9 (v0.11.0): --no-image-urls — 토큰 절감용 이미지 URL 제거.
    # 본문 인라인 이미지는 [이미지: alt] 플레이스홀더로, images 배열은 비운다.
    if strip_image_urls:
        result["body"] = strip_image_urls_from_body(
            result["body"], is_html=use_html_body
        )
        result["images"] = []

    if parser.author_nickname:
        result["author_nickname"] = parser.author_nickname

    if parser.like_count is not None:
        result["like_count"] = parser.like_count

    return result
