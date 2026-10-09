"""Main content extraction pipeline for itda-web-reader.

Combines content extraction, metadata extraction, HTML standardization,
Markdown conversion, and retry strategy into a single orchestrator.
네트워크 없음 — itda-hyve 가 저장한 파일(또는 stdin)만 읽는다(web-reader 8.0.0).

CLI Usage:
    extract_content.py [INPUT_FILE] [--output FILE] [--format html|markdown|json]
                       [--url URL] [--final-url URL] [--status N] [--content-type CT]
                       [--fetched-at ISO] [--selector CSS]

Exit codes:
    0: Success
    1: Parse or I/O error, selector 0건, 404·5xx 등 받기 실패 상태
    2: Invalid arguments, selector 문법 오류, 최종 URL 이 사설·로컬 목적지
    3: HTML 이 아님(PDF·이미지·오피스 파일 등)
    4: 브라우저 경로로(챌린지·봇 차단·401/403·JS 셸·폐기 플래그)
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from typing import Any



def _load_module(name: str) -> Any:
    """이름으로 모듈을 로드한다. sys.modules를 먼저 확인하고, 없으면 파일 경로로 로드한다."""
    if name in sys.modules:
        return sys.modules[name]
    # 같은 디렉토리에서 로드 시도
    _dir = os.path.dirname(__file__)
    filepath = os.path.join(_dir, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, filepath)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    raise ImportError(f"Cannot load module: {name}")


def _get_selectors():  # type: ignore[return]
    """Get the selectors module, handling name conflict with stdlib.

    sys.modules 캐시에 있더라도 __file__이 scripts/ 디렉토리 내부인지 확인하여
    stdlib selectors 모듈과의 충돌을 방지한다.
    """
    _dir = os.path.dirname(os.path.abspath(__file__))
    # 캐시된 모듈이 로컬 파일인지 확인
    for alias in ("web_selectors", "selectors"):
        if alias in sys.modules:
            cached = sys.modules[alias]
            cached_file = getattr(cached, "__file__", None) or ""
            if cached_file and os.path.dirname(os.path.abspath(cached_file)) == _dir:
                return cached
    # 캐시에 없거나 외부 모듈이면 파일 경로 기반으로 로드
    filepath = os.path.join(_dir, "web_selectors.py")
    spec = importlib.util.spec_from_file_location("web_selectors", filepath)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["web_selectors"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    raise ImportError("Cannot load selectors module")


# Lazy module references populated on first use
_sel: Any = None
_scorer: Any = None
_meta: Any = None
_standardize: Any = None
_md_convert: Any = None


def _init_modules() -> None:
    global _sel, _scorer, _meta, _standardize, _md_convert
    if _sel is None:
        _sel = _get_selectors()
    if _scorer is None:
        _scorer = _load_module("scorer")
    if _meta is None:
        _meta = _load_module("metadata")
    if _standardize is None:
        _standardize = _load_module("standardize")
    if _md_convert is None:
        _md_convert = _load_module("md_convert")


def _find_main_content(soup: Any) -> Any:
    """Find the main content element using entry-point selectors + scoring."""
    best_element = None
    best_score = -1.0

    for selector in _sel.ENTRY_POINT_SELECTORS:
        try:
            elements = soup.select(selector)
        except Exception:
            continue
        for el in elements:
            score = _scorer.score_element(el)
            if score > best_score:
                best_score = score
                best_element = el

    return best_element


def _remove_low_score_blocks(element: Any) -> None:
    """Remove low-scoring child blocks from the main element."""
    block_tags = {"div", "section", "article", "aside", "header", "footer", "nav"}
    for child in list(element.find_all(block_tags, recursive=False)):
        if not _scorer.is_likely_content(child):
            penalty = _scorer.score_non_content_block(child)
            if penalty < 0:
                child.decompose()


def _remove_hidden_elements(soup: Any) -> None:
    """Remove elements with display:none or visibility:hidden CSS styles.

    REQ-2.4: skip_hidden_removal 옵션으로 이 단계를 건너뛸 수 있다.
    """
    import re
    hidden_style_re = re.compile(
        r"(display\s*:\s*none|visibility\s*:\s*hidden)",
        re.IGNORECASE,
    )
    for tag in list(soup.find_all(style=True)):
        # SPEC-WEBREADER-DYNAMIC-LIGHTPANDA-001: Lightpanda HTML 일부 태그가 attrs=None을 반환할 수 있어 방어
        if not getattr(tag, "attrs", None):
            continue
        style = tag.get("style", "") or ""
        if hidden_style_re.search(style):
            tag.decompose()


def _remove_content_patterns(soup: Any) -> None:
    """Remove elements matching content noise patterns."""
    import re
    originally_published_re = re.compile(
        r"(originally published|this article appeared|read more on)",
        re.IGNORECASE,
    )

    for tag in list(soup.find_all(string=originally_published_re)):
        parent = tag.parent
        if parent and parent.name in ("p", "div", "span"):
            parent.decompose()

    # Remove standalone <time> elements near start/end of content
    for time_el in list(soup.find_all("time")):
        preceding_text = time_el.get_text().strip()
        if not preceding_text or len(preceding_text) < 5:
            time_el.decompose()


def extract(
    html: str,
    url: str | None = None,
    fmt: str = "html",
    options: dict[str, Any] | None = None,
    user_selector: str | None = None,
) -> dict[str, Any]:
    """Main extraction function combining all pipeline phases.

    Args:
        html: Raw HTML content to process.
        url: Base URL for resolving relative URLs and domain extraction.
        fmt: Output format ('html', 'markdown', 'json').
        options: Pipeline options (e.g., skip_partial_selectors, skip_hidden_removal).
        user_selector: CSS selector. 지정 시 자동 본문 탐지를 건너뛰고 해당 요소만 추출.
                       매칭 0건 → SelectorNoMatchError raise.
                       문법 오류 → SelectorSyntaxError raise (alias: DomainSelectorSyntaxError).
                       호출자 프로세스를 종료하지 않음 (REQ-006).

    Returns:
        Dict with 'content', 'metadata', 'word_count', 'parse_time_ms'.
    """
    # @MX:NOTE: [AUTO] user_selector 분기 — 지정 시 자동 탐지 우회, 노이즈 제거는 유지.
    # REQ-001/006 (SPEC-WEBREADER-010): 도메인 예외 raise (프로세스 종료 없음).
    # main()에서 catch → exit code 1/2 매핑. 라이브러리 호출자는 예외로 수신.
    from exceptions import SelectorNoMatchError
    from exceptions import SelectorSyntaxError as DomainSelectorSyntaxError

    _init_modules()
    options = options or {}
    t0 = time.time()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    if user_selector is not None:
        # selector 유효성 및 매칭 검사 (노이즈 제거 전에 수행)
        try:
            from soupsieve import SelectorSyntaxError as _SelectorSyntaxError
        except ImportError:
            try:
                from soupsieve.util import SelectorSyntaxError as _SelectorSyntaxError  # type: ignore[assignment]
            except ImportError:
                _SelectorSyntaxError = Exception  # type: ignore[assignment,misc]

        # 빈 문자열은 문법 오류로 처리 (REQ-001)
        if not user_selector.strip():
            raise DomainSelectorSyntaxError(selector=user_selector, cause="empty selector")

        try:
            matched = soup.select(user_selector)
        except _SelectorSyntaxError as e:
            raise DomainSelectorSyntaxError(selector=user_selector, cause=str(e)) from e
        except Exception as e:
            # soupsieve가 다른 예외를 raise하는 경우 대비
            msg = str(e)
            if any(k in msg.lower() for k in ("syntax", "invalid", "parse")):
                raise DomainSelectorSyntaxError(selector=user_selector, cause=str(e)) from e
            raise

        if not matched:
            raise SelectorNoMatchError(selector=user_selector, target="document")

        # 매칭된 요소들을 새 wrapper div에 복사 (원본 tree 보존)
        import copy
        wrapper = BeautifulSoup("<div></div>", "html.parser")
        root = wrapper.div  # type: ignore[union-attr]
        for el in matched:
            root.append(copy.copy(el))

        # 메타데이터는 전체 soup에서 추출 (head의 meta 태그 접근)
        metadata = _meta.extract_metadata(soup, url)

        # 노이즈 제거를 wrapper subtree에 적용
        for sel in _sel.EXACT_REMOVE_SELECTORS:
            try:
                for el in root.select(sel):
                    el.decompose()
            except Exception:
                pass

        # hidden 요소 제거 — selector 경로와 자동 탐지 경로 정책 일관 (REQ-003)
        _remove_hidden_elements(root)

        # PARTIAL_REMOVE_PATTERNS 적용 — 사용자 명시 선택 직속 자식은 보호 (REQ-004)
        if _sel.PARTIAL_REMOVE_PATTERNS:
            for tag in list(root.find_all(True)):
                if not hasattr(tag, "attrs") or tag.attrs is None:
                    continue
                # 사용자가 명시 선택한 직속 자식은 보호 — 자손은 제거 허용 (방식 B)
                if tag.parent is root:
                    continue
                classes = " ".join(tag.get("class", []))
                el_id = tag.get("id", "") or ""
                combined = f"{classes} {el_id}"
                if combined.strip() and _sel.PARTIAL_REMOVE_PATTERNS.search(combined):
                    if not tag.find_parent(["pre", "code"]):
                        tag.decompose()

        content_soup = root
        _standardize.standardize_content(content_soup, metadata.get("title"))
        content_html = str(content_soup)
        word_count = _scorer.count_words(content_soup.get_text())
        parse_time_ms = int((time.time() - t0) * 1000)

        if fmt in ("markdown", "json"):
            md = _md_convert.html_to_markdown(content_html, metadata.get("title"))
            content = _md_convert.post_process_markdown(md, metadata.get("title"))
        else:
            content = content_html

        return {
            "content": content,
            "metadata": metadata,
            "word_count": word_count,
            "parse_time_ms": parse_time_ms,
        }

    # --- 기존 자동 탐지 경로 (user_selector=None) ---

    # Step 1: Remove exact selectors
    for selector in _sel.EXACT_REMOVE_SELECTORS:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            pass

    # Step 2: Remove partial class/ID patterns
    if not options.get("skip_partial_selectors") and _sel.PARTIAL_REMOVE_PATTERNS:
        for tag in list(soup.find_all(True)):
            if not hasattr(tag, "attrs") or tag.attrs is None:
                continue
            classes = " ".join(tag.get("class", []))
            el_id = tag.get("id", "") or ""
            combined = f"{classes} {el_id}"
            if combined.strip() and _sel.PARTIAL_REMOVE_PATTERNS.search(combined):
                if not tag.find_parent(["pre", "code"]):
                    tag.decompose()

    # Step 2.5: Remove hidden elements (unless skipped)
    if not options.get("skip_hidden_removal"):
        _remove_hidden_elements(soup)

    # Step 3: Find main content
    main_element = _find_main_content(soup)

    # Step 4: Remove low-score blocks (unless skipped)
    if main_element and not options.get("skip_scoring"):
        _remove_low_score_blocks(main_element)

    # Step 5: Remove content patterns
    _remove_content_patterns(soup)

    # Step 6: Extract metadata
    metadata = _meta.extract_metadata(soup, url)

    # Step 7: Get content element
    content_soup = main_element if main_element else soup

    # Step 8: Standardize
    _standardize.standardize_content(content_soup, metadata.get("title"))
    content_html = str(content_soup)

    word_count = _scorer.count_words(content_soup.get_text())
    parse_time_ms = int((time.time() - t0) * 1000)

    # Step 9: Format output
    if fmt in ("markdown", "json"):
        md = _md_convert.html_to_markdown(content_html, metadata.get("title"))
        content = _md_convert.post_process_markdown(md, metadata.get("title"))
    else:
        content = content_html

    return {
        "content": content,
        "metadata": metadata,
        "word_count": word_count,
        "parse_time_ms": parse_time_ms,
    }


def extract_with_retry(
    html: str,
    url: str | None = None,
    fmt: str = "html",
) -> dict[str, Any]:
    """Extract content with automatic retry on low word count.

    Retry 1: < 200 words -> skip partial selectors
    Retry 2a: < 50 words -> also skip hidden removal
    Retry 2b: < 50 words -> also skip scoring
    """
    # First pass
    result = extract(html, url, fmt)
    word_count = result["word_count"]

    # Retry 1: low word count
    if word_count < 200:
        result2 = extract(html, url, fmt, {"skip_partial_selectors": True})
        if result2["word_count"] >= word_count * 2:
            result = result2
            word_count = result2["word_count"]

    # Retry 2: very low word count
    if word_count < 50:
        result3 = extract(html, url, fmt, {
            "skip_partial_selectors": True,
            "skip_hidden_removal": True,
        })
        if result3["word_count"] > word_count:
            result = result3
            word_count = result3["word_count"]

        if word_count < 50:
            result4 = extract(html, url, fmt, {
                "skip_partial_selectors": True,
                "skip_hidden_removal": True,
                "skip_scoring": True,
            })
            if result4["word_count"] > word_count:
                result = result4

    return result


# NOTE: SPEC-WEBREADER-LIGHTEN-001 v3.0.0 — SPA 어댑터 / capture 처리 함수 일체 제거.
# (_load_adapter_for_capture, _format_date_yyyymmdd, _render_capture_as_markdown,
#  _render_capture_as_json, _process_from_capture)
# main() 진입 직후 fail-fast 가 --adapter / --adapter-page / --from-capture 호출을 차단하므로
# 본 함수들은 더 이상 호출되지 않는다. 마이그레이션 안내는 GUIDE.md 참조.


_SPA_ROOT_IDS = ("root", "app", "__next", "__nuxt", "___gatsby", "svelte")


def detect_js_shell(html: str) -> str | None:
    """본문이 JavaScript 로 그려지는 빈 셸이면 그 근거 문자열, 아니면 None.

    보이는 글자(스크립트·스타일 제외)가 200자 미만이고, SPA 루트 요소(``#root``·``#app``·``#__next`` …)가
    있거나 외부 스크립트가 3개 이상이면 셸로 본다. 추출 단어 수가 적을 때만 부른다.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    scripts = len(soup.find_all("script", src=True))
    for tag in soup.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    body = soup.find("body") or soup
    visible = len(body.get_text(" ", strip=True))
    if visible >= 200:
        return None
    root = next((i for i in _SPA_ROOT_IDS if soup.find(id=i) is not None), None)
    if root:
        return f"보이는 글자 {visible}자 + SPA 루트 #{root}"
    if scripts >= 3:
        return f"보이는 글자 {visible}자 + 외부 스크립트 {scripts}개"
    return None


_LOC = r"(?:(?:window|document|top|self|parent)\.)?location"
_STMT_ALERT = re.compile(r"""^alert\(\s*(['"])(.*?)\1\s*\)$""", re.S)
_STMT_ASSIGN = re.compile(rf"""^{_LOC}(?:\.href)?\s*=\s*(['"])(.*?)\1$""", re.S)
_STMT_CALL = re.compile(rf"""^{_LOC}\.(?:replace|assign)\(\s*(['"])(.*?)\1\s*\)$""", re.S)
_META_REFRESH = re.compile(r"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*>""", re.I)
_REFRESH_URL = re.compile(r"""url\s*=\s*['"]?([^'">\s]+)""", re.I)


def detect_script_redirect(html: str) -> tuple[str, str] | None:
    """본문 대신 곧바로 다른 곳으로 보내는 인라인 스크립트면 ``(목적지, 알림 문구)``, 아니면 None.

    스크립트 본문이 ``alert("…")``(선택) + ``location.href = "…"``·``location.replace("…")`` 문장**뿐**일 때만 본다 —
    조건문이 섞인 스크립트는 판정하지 않는다(규칙 ``skill-web-probe-aside`` §정적 200 셸, W14 리뷰 m2). 브라우저는 이 페이지를 보여 주지 않고
    곧바로 옮겨 가므로 남은 GNB·푸터 글자는 본문이 아니다.
    """
    # 실행되지 않는 곳의 스크립트는 빼고 본다 — HTML 주석(IE 조건부 주석 포함)·<template>·<textarea> 안(W14 재확인 N3)
    live = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    live = re.sub(r"<(template|textarea)\b[^>]*>.*?</\1\s*>", "", live, flags=re.S | re.I)
    for block in re.findall(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>", live, re.S | re.I):
        code = re.sub(r"/\*.*?\*/|^\s*//[^\n]*$", "", block, flags=re.S | re.M).strip()
        if not code:
            continue
        stmts = [x.strip() for x in re.split(r";|\n", code) if x.strip()]
        target, alert = None, ""
        for stmt in stmts:
            m = _STMT_ALERT.match(stmt)
            if m:
                alert = m.group(2)
                continue
            m = _STMT_ASSIGN.match(stmt) or _STMT_CALL.match(stmt)
            if m:
                target = m.group(2)
                continue
            target = None
            break
        else:
            if target:
                return target, alert
    return None


def meta_refresh_target(html: str) -> str | None:
    m = _META_REFRESH.search(html)
    if not m:
        return None
    u = _REFRESH_URL.search(m.group(0))
    return u.group(1) if u else ""


def _fail(kind: str, message: str, code: int, hint: str = "") -> None:
    print(f"Error[{kind}]: {message}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)
    sys.exit(code)


def main() -> None:
    """CLI entry point — itda-hyve 가 저장한 파일(또는 stdin)을 읽는다. 네트워크 없음(8.0.0)."""
    # Windows 콘솔(cp949)에서도 한국어 출력이 죽지 않게 UTF-8 로 재설정한다
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(
        description=(
            "Extract main content from a saved HTML page (itda-hyve save_as file or stdin).\n\n"
            "web-reader 8.0.0: 이 스크립트는 네트워크를 하지 않는다 — plan.py 가 계획한 itda-hyve 호출로 받은 파일을 읽는다."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="저장한 HTML 파일(기본: stdin)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--format", "-f", choices=["html", "markdown", "json"], default="html")
    parser.add_argument("--metadata", action="store_true", help="(호환용 — 메타데이터는 json·markdown 에 늘 실린다)")
    parser.add_argument("--url", help="요청한 URL — 상대 링크 해석·봉투(provenance)의 requested_url")
    parser.add_argument("--final-url", dest="final_url", help="마지막 홉 URL(plan.py done 출력 그대로). 없으면 --url")
    parser.add_argument("--status", type=int, help="도구 응답의 HTTP 상태. 2xx 가 아니면 본문으로 쓰지 않는다")
    parser.add_argument("--content-type", dest="content_type", default="", help="도구 응답의 content_type — charset·비HTML 판정")
    parser.add_argument("--fetched-at", dest="fetched_at", help="받은 시각(UTC ISO-8601, plan.py done 출력 그대로)")
    # 폐기 플래그 — 호출되면 exit 4 + 브라우저 경로 안내
    parser.add_argument("--dynamic-only", dest="dynamic_only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--from-capture", dest="from_capture", help=argparse.SUPPRESS)
    parser.add_argument("--adapter", dest="adapter", help=argparse.SUPPRESS)
    parser.add_argument("--adapter-page", dest="adapter_page", help=argparse.SUPPRESS)
    parser.add_argument(
        "--selector", type=str, default=None, metavar="CSS",
        help="CSS selector로 추출 범위를 한정한다. 지정 시 자동 본문 탐지를 건너뛴다. 매칭 0건 → exit 1, 문법 오류 → exit 2.",
    )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # --help → 0, argparse 오류 → 2. 코드를 삼키지 않는다.
        sys.exit(e.code if isinstance(e.code, int) else 2)

    # v7.0.0: 동적 fetch(Lightpanda) 제거 — Cowork 실측(#1298)에서 세션당 151MB 재설치 +
    # 진성 CSR SPA(wanted 등) SIGILL 크래시로 v5 재흡수 근거가 무너져 v3 fail-fast 체제 복귀.
    if getattr(args, "dynamic_only", False):
        print(
            "[web-reader v7.0.0] --dynamic-only (Lightpanda 동적 렌더링) 는 제거되었습니다.\n"
            "- JavaScript 동적 페이지: 브라우저 경로(itda-web:aside-browser-mcp, Aside 브라우저) 사용\n"
            "마이그레이션 안내: itda-web/skills/web-reader/GUIDE.md 참조.",
            file=sys.stderr,
        )
        sys.exit(4)

    # REQ-LIGHTEN-003.3: SPA 어댑터 플래그 fail-fast (web-reader v3.0.0)
    if (
        getattr(args, "from_capture", None)
        or getattr(args, "adapter", None)
        or getattr(args, "adapter_page", None)
    ):
        print(
            "[web-reader v3.0.0] SPA 어댑터 (--adapter / --adapter-page / --from-capture) 는 "
            "web-reader v3.0.0 에서 제거되었습니다.\n"
            "- 네이버 부동산 등 SPA: 브라우저 경로(itda-web:aside-browser-mcp)에서 페이지를 열어 확인\n"
            "마이그레이션 안내: itda-web/skills/web-reader/GUIDE.md 참조.",
            file=sys.stderr,
        )
        sys.exit(4)

    _pi = _load_module("page_input")
    _uv = _load_module("url_validator")

    final_url = args.final_url or args.url
    if final_url:
        try:
            _uv.check_url(final_url)
        except _uv.SSRFError as e:
            _fail("url_rejected", f"최종 URL 이 사설·로컬 목적지입니다: {e}", 2)
    if args.url and args.final_url:
        from urllib.parse import urlsplit
        if (urlsplit(args.url).hostname or "") != (urlsplit(args.final_url).hostname or ""):
            print(
                f"[web-reader] 경고: 최종 URL 의 호스트가 요청과 다릅니다 — {args.url} → {args.final_url}",
                file=sys.stderr,
            )

    try:
        page = _pi.read_page(args.input, content_type=args.content_type or "", status=args.status)
    except _pi.PageInputError as e:
        _fail(e.kind, str(e), e.exit_code, e.hint)
    for w in page.warnings:
        print(f"[web-reader] 경고: {w}", file=sys.stderr)
    html = page.text

    # 챌린지·봇 차단 본문 — 200 이어도 본문이 아니다
    _cv = _load_module("challenge_validators")
    verdict = _cv.validate_body(html, status=page.status or 200)
    if verdict.verdict == _cv.Verdict.CHALLENGE:
        _fail(
            "challenge",
            f"봇 차단·챌린지 페이지입니다({', '.join(verdict.reasons)}) — 정적 요청으로는 본문을 받을 수 없습니다",
            4,
            f"{_pi.BROWSER_ROUTE} 에서 사용자가 직접 열어 보세요. 사이트를 '도달 불가'로 단정하지 마세요.",
        )

    # Extract content
    from exceptions import SelectorNoMatchError
    from exceptions import SelectorSyntaxError as DomainSelectorSyntaxError
    user_selector = getattr(args, "selector", None)
    base_url = final_url
    try:
        if user_selector is not None:
            result = extract(html, base_url, args.format, user_selector=user_selector)
        else:
            result = extract_with_retry(html, base_url, args.format)
    except DomainSelectorSyntaxError as e:
        print(f"Error: Invalid CSS selector syntax: {e.cause}", file=sys.stderr)
        sys.exit(2)
    except SelectorNoMatchError as e:
        print(
            f"Error: CSS selector '{e.selector}' matched 0 elements in the document.",
            file=sys.stderr,
        )
        print("Verify the selector against the source HTML.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # REQ-5.5: 진단을 stderr로 출력하며 stdout JSON 오염 없음
        print(f"Error extracting content: {e}", file=sys.stderr)
        sys.exit(1)

    if user_selector is None:
        redirect = detect_script_redirect(html)
        if redirect:
            target, alert = redirect
            _fail(
                "script_redirect",
                f"이 페이지는 본문 대신 스크립트로 곧바로 다른 곳({target})으로 보냅니다"
                + (f" — 알림: {alert!r}" if alert else "") + ". 남은 글자는 메뉴·푸터라 본문으로 내지 않습니다",
                4,
                f"로그인 전용 페이지일 가능성이 큽니다 — {_pi.BROWSER_ROUTE} 에서 사용자가 직접 여세요. "
                "공개 페이지로 옮겨 가는 것이면 그 주소로 plan.py start 부터 다시 하세요.",
            )

    if user_selector is None and result["word_count"] < 50:
        shell = detect_js_shell(html)
        if shell:
            _fail(
                "js_rendered_shell",
                f"본문이 JavaScript 로 그려지는 페이지입니다({shell}) — 정적 HTML 에 본문이 없습니다",
                4,
                f"{_pi.BROWSER_ROUTE} 를 쓰세요.",
            )

    if user_selector is None and result["word_count"] == 0:
        refresh = meta_refresh_target(html)
        _fail(
            "empty_content",
            "추출한 본문이 0단어입니다"
            + (f" — 페이지가 meta refresh 로 {refresh or '(주소 없음)'} 로 옮겨 갑니다" if refresh is not None else ""),
            1,
            "옮겨 가는 주소가 있으면 그 주소로 plan.py start 부터 다시 하세요. 본문 위치를 알면 --selector 로 지정하세요."
            if refresh is not None else
            f"본문이 정적 HTML 에 없는 페이지일 수 있습니다 — {_pi.BROWSER_ROUTE}, 또는 본문 위치를 알면 --selector 로.",
        )

    metadata = result["metadata"]
    content = result["content"]

    def _yaml_str(value: str) -> str:
        """YAML double-quoted 문자열용 이스케이프 처리 (REQ-2.6: injection 방지)."""
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'

    # 페이지 봉투(provenance) — 도구 응답 값(상태·최종 URL·Content-Type·받은 시각)이 넘어왔으면 싣고, 없으면 null(지어내지 않는다)
    _prov = _load_module("provenance")
    fetched = args.status is not None or page.form == "envelope"
    provenance = _prov.build_provenance(
        html,
        raw_sha256=page.raw_sha256,
        requested_url=args.url or None,
        final_url=final_url,
        status=page.status,
        fetched_at=args.fetched_at if fetched else None,
        encoding=page.encoding,
        fetch_phase="hyve" if fetched else "input",
        content_type=page.content_type or None,
    )

    if args.format == "json":
        output_data = {
            "content": content,
            "title": metadata.get("title", "") or "",
            "author": metadata.get("author", "") or "",
            "published": metadata.get("published", "") or "",
            "description": metadata.get("description", "") or "",
            "image": metadata.get("image", "") or "",
            "language": metadata.get("language", "") or "",
            "favicon": metadata.get("favicon", "") or "",
            "site": metadata.get("site", "") or "",
            "domain": metadata.get("domain", "") or "",
            "wordCount": result["word_count"],
            "parseTime": result["parse_time_ms"],
            "provenance": provenance,
        }
        output = json.dumps(output_data, ensure_ascii=False, indent=2)
    elif args.format == "markdown":
        frontmatter_lines = ["---"]
        if metadata.get("title"):
            frontmatter_lines.append(f"title: {_yaml_str(metadata['title'])}")
        if metadata.get("author"):
            frontmatter_lines.append(f"author: {_yaml_str(metadata['author'])}")
        if metadata.get("published"):
            frontmatter_lines.append(f"date: {_yaml_str(metadata['published'])}")
        if final_url:
            frontmatter_lines.append(f"url: {final_url}")
        if provenance.get("fetched_at"):
            frontmatter_lines.append(f"fetched_at: {provenance['fetched_at']}")
        if provenance.get("status") is not None:
            frontmatter_lines.append(f"status: {provenance['status']}")
        frontmatter_lines.append(f"content_hash: {provenance['content_hash']}")
        frontmatter_lines.append("---")
        output = "\n".join(frontmatter_lines) + "\n\n" + content
    else:
        output = content

    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        else:
            print(output)
    except (OSError, IOError) as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"words={result['word_count']} "
        f"time={result['parse_time_ms']}ms "
        f"format={args.format} "
        f"encoding={page.encoding}({page.encoding_source})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
