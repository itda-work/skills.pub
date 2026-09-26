"""Main content extraction pipeline for itda-web-reader.

Combines content extraction, metadata extraction, HTML standardization,
Markdown conversion, and retry strategy into a single orchestrator.

CLI Usage:
    extract_content.py [INPUT_FILE] [--output FILE] [--format html|markdown|json]
                       [--metadata] [--url URL]

Exit codes:
    0: Success
    1: Parse or I/O error
    2: Invalid arguments
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


def main() -> None:
    """CLI entry point."""
    # Windows cp1252 환경에서도 한글 출력 가능하도록 UTF-8 강제
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):  # 파이프 입력도 UTF-8 (Windows cp1252 디코드로 해시·본문이 깨진다)
        sys.stdin.reconfigure(encoding="utf-8")

    # @MX:NOTE: [AUTO] 사이트 패턴 우선 → 일반 fallback → 진단 에러 — REQ-5, REQ-6, REQ-7.
    # CLI 표면은 안정적 유지: 새 인자는 옵션으로만 추가, 기존 호출 호환.
    # Backward-compat: test_url_and_file_are_mutually_exclusive (test_extract_content.py:971-987) 보존.
    # --url과 INPUT_FILE은 mutually-exclusive (REQ-7.1, REQ-7.3).
    parser = argparse.ArgumentParser(
        description=(
            "Extract main content from HTML files.\n\n"
            "NOTE: --url and INPUT_FILE are mutually exclusive. "
            "Provide only one of them at a time."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input", nargs="?", help="Input HTML file (default: stdin). Mutually exclusive with --url."
    )
    parser.add_argument(
        "--output", "-o", help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["html", "markdown", "json"],
        default="html",
    )
    parser.add_argument(
        "--metadata", action="store_true", help="Include metadata in output"
    )
    parser.add_argument(
        "--url",
        help=(
            "Base URL to fetch and extract content from. "
            "Mutually exclusive with INPUT_FILE. "
            "Static fetch with WAF retry grid (동적 렌더링은 v7.0.0에서 제거 — 브라우저 경로 itda-web:aside-browser-mcp 사용)."
        ),
    )
    parser.add_argument(
        "--lang", help="자막 언어 코드 (YouTube 전용, 기본값: 자동 선택)"
    )
    parser.add_argument(
        "--from-capture",
        dest="from_capture",
        metavar="FILE",
        help="JSONL 캡처 파일 경로. 지정 시 어댑터 필드 매핑을 적용하여 변환한다.",
    )
    parser.add_argument(
        "--adapter",
        dest="adapter",
        metavar="NAME",
        help="어댑터 이름 (--from-capture 사용 시 필드 매핑 적용)",
    )
    parser.add_argument(
        "--adapter-page",
        dest="adapter_page",
        metavar="KEY",
        help="어댑터 페이지 키 (기본값: 어댑터의 default_page)",
    )

    # REQ-2.4: 폴백 동작 비활성화 플래그 (SPEC-WEBREADER-008)
    fallback_group = parser.add_mutually_exclusive_group()
    fallback_group.add_argument(
        "--static-only",
        dest="static_only",
        action="store_true",
        default=False,
        help="정적 fetch만 실행. 품질 미달이어도 동적 시도 안 함.",
    )
    fallback_group.add_argument(
        "--dynamic-only",
        dest="dynamic_only",
        action="store_true",
        default=False,
        help="(v7.0.0에서 제거됨) 지정 시 exit 4 + 브라우저 경로(itda-web:aside-browser-mcp) 안내. legacy 호환 플래그.",
    )
    # --no-fallback은 --static-only의 alias (legacy 호환 별칭)
    parser.add_argument(
        "--no-fallback",
        dest="no_fallback",
        action="store_true",
        default=False,
        help="--static-only의 alias (legacy 호환). 정적 fetch만 실행.",
    )
    # REQ-3.3: 품질 임계값 오버라이드
    parser.add_argument(
        "--min-text-length",
        dest="min_text_length",
        type=int,
        default=None,
        metavar="INT",
        help="정적 품질 판정 텍스트 길이 임계값 (기본 500). 환경변수 WEBREADER_MIN_TEXT_LENGTH보다 우선.",
    )
    parser.add_argument(
        "--min-meaningful-tags",
        dest="min_meaningful_tags",
        type=int,
        default=None,
        metavar="INT",
        help="정적 품질 판정 의미 태그 수 임계값 (기본 3). 환경변수 WEBREADER_MIN_MEANINGFUL_TAGS보다 우선.",
    )
    # REQ-1/2/3 (SPEC-WEBREADER-009): CSS selector 직접 지정
    parser.add_argument(
        "--selector",
        type=str,
        default=None,
        metavar="CSS",
        help=(
            "CSS selector로 추출 범위를 한정한다. 지정 시 자동 본문 탐지를 건너뛴다. "
            "매칭 0건 → exit 1, 문법 오류 → exit 2."
        ),
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
    # AC-3 검증 키워드: "SPA 어댑터", "네이버 부동산", "aside-browser-mcp"
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

    # REQ-7.1: --url과 positional input은 상호 배타적 (Codex finding: backward-compat 보존)
    if args.url and args.input:
        print(
            "Error: --url과 INPUT_FILE은 동시에 사용할 수 없습니다. 하나만 지정하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --no-fallback은 --static-only의 alias (REQ-2.4)
    effective_static_only = getattr(args, "static_only", False) or getattr(args, "no_fallback", False)

    # REQ-3.3: 품질 임계값 우선순위 (CLI > env > default)
    import os as _os_env
    min_text_length = (
        getattr(args, "min_text_length", None)
        or int(_os_env.environ.get("WEBREADER_MIN_TEXT_LENGTH", 0) or 0)
        or 500
    )
    min_meaningful_tags = (
        getattr(args, "min_meaningful_tags", None)
        or int(_os_env.environ.get("WEBREADER_MIN_MEANINGFUL_TAGS", 0) or 0)
        or 3
    )

    # 최종 URL 추적 (redirect 후 final URL)
    final_url: str | None = None
    fetch_pipeline_result = None  # fetch_pipeline.FetchResult or None
    fallback_fetch_extra: dict[str, Any] | None = None  # fetch_html 직접 호출 폴백 경로의 봉투 재료

    # Read input
    try:
        if args.url:
            # SPEC-WEBREADER-YOUTUBE-REMOVE-001: YouTube 자막 기능은 v4.0.0에서 제거됨.
            # yt-dlp + Claude 위임으로 동등 결과를 얻을 수 있음 (이중 유지보수 비용이 사용자 가치를 초과).
            if re.search(
                r"(?:youtube\.com/(?:watch|shorts|live)|youtu\.be/|m\.youtube\.com/watch)",
                args.url,
            ):
                print(
                    "YouTube transcript extraction was removed in web-reader v4.0.0.\n"
                    "Use yt-dlp instead:\n"
                    "  yt-dlp --write-auto-sub --sub-lang ko --skip-download <URL>\n"
                    "See GUIDE.md '마이그레이션 안내 (v3 → v4)' for details.",
                    file=sys.stderr,
                )
                sys.exit(2)

            # 일반 URL: fetch_pipeline orchestrator 사용 (REQ-2, WI-2)
            from exceptions import StaticFetchEscalate  # type: ignore[import]
            try:
                _fp = _load_module("fetch_pipeline")
                _ws = _load_module("web_selectors")
                site_pattern = _ws.match_site_pattern(args.url)
                fetch_pipeline_result = _fp.fetch_with_fallback(
                    args.url,
                    static_only=effective_static_only,
                    dynamic_only=False,
                    min_text_length=min_text_length,
                    min_meaningful_tags=min_meaningful_tags,
                    site_pattern=site_pattern,
                )
                html = fetch_pipeline_result.html
                final_url = fetch_pipeline_result.final_url or args.url
            except StaticFetchEscalate as _esc:
                # P0: WAF 차단 소진 → exit 4 (브라우저 경로 에스컬레이트). broad fallback
                # 보다 먼저 catch.
                print(_esc.escalation_message(), file=sys.stderr)
                sys.exit(4)
            except Exception as _fp_err:
                # fetch_pipeline 미사용 환경 폴백: 기존 fetch_html 직접 호출
                _fh = _load_module("fetch_html")
                fetch_result = _fh.fetch_url(args.url)
                if fetch_result.get("must_escalate"):
                    # 폴백 경로에서도 정적 give-up 을 exit 4 로 surface (P0).
                    print(
                        StaticFetchEscalate(
                            url=args.url,
                            stop_reason=str(fetch_result.get("stop_reason", "")),
                            untried_routes=list(fetch_result.get("untried_routes") or []),
                        ).escalation_message(),
                        file=sys.stderr,
                    )
                    sys.exit(4)
                if not fetch_result.get("content") or fetch_result.get("error"):
                    error_msg = fetch_result.get("error", "empty response")
                    print(f"Error fetching URL: {error_msg}", file=sys.stderr)
                    sys.exit(1)
                html = str(fetch_result["content"])
                final_url = str(fetch_result.get("url") or args.url)
                fallback_fetch_extra = {
                    "status_code": fetch_result.get("status_code"),
                    "content_sha256": fetch_result.get("content_sha256"),
                    "encoding": fetch_result.get("encoding"),
                    "waf_profile": fetch_result.get("waf_profile"),
                    "fetch_phase": "static",
                }
        elif args.input:
            with open(args.input, encoding="utf-8") as f:
                html = f.read()
        else:
            html = sys.stdin.read()
    except (OSError, IOError) as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract content
    # REQ-4 (SPEC-WEBREADER-009): selector 지정 시 retry 전략 건너뛰고 직접 호출
    # REQ-002 (SPEC-WEBREADER-010): 도메인 예외 → exit code 매핑. SystemExit 핸들러 제거 (D13).
    from exceptions import SelectorNoMatchError
    from exceptions import SelectorSyntaxError as DomainSelectorSyntaxError
    user_selector = getattr(args, "selector", None)
    try:
        if user_selector is not None:
            # selector 경로: extract() 직접 호출 (retry 우회)
            result = extract(html, args.url, args.format, user_selector=user_selector)
        else:
            result = extract_with_retry(html, args.url, args.format)
    except DomainSelectorSyntaxError as e:
        # REQ-002: 문법 오류 → exit 2 + SPEC-009 AC-4 형식 메시지
        print(f"Error: Invalid CSS selector syntax: {e.cause}", file=sys.stderr)
        sys.exit(2)
    except SelectorNoMatchError as e:
        # REQ-002: 매칭 0건 → exit 1 + SPEC-009 AC-3 메시지 byte-level 동일
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

    metadata = result["metadata"]
    content = result["content"]

    # Format output
    def _yaml_str(value: str) -> str:
        """YAML double-quoted 문자열용 이스케이프 처리 (REQ-2.6: injection 방지).

        title, author 등의 값에 개행이나 특수문자가 있을 때 YAML 구조를 깨지 않도록
        double-quoted 형식으로 감싼다.
        """
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'

    # 최종 URL (redirect 후) 사용 - REQ-7.2 (REQ-3.3에서 이어짐)
    # final_url은 fetch 단계에서 이미 결정됨 (fetch_pipeline_result 또는 fetch_html 폴백)
    # final_url이 아직 None인 경우(INPUT_FILE 모드): args.url은 없음
    if final_url is None and args.url:
        final_url = args.url

    # 페이지 봉투(provenance) — v7.1.0 (#1600 T0). 기존 키는 불변, `provenance` 객체만 추가.
    _prov = _load_module("provenance")
    if fetch_pipeline_result is not None:
        provenance = _prov.provenance_from_fetch_extra(
            html, args.url, final_url or args.url, dict(getattr(fetch_pipeline_result, "extra", {}) or {})
        )
        if not provenance.get("fetch_phase") or provenance["fetch_phase"] == "static":
            provenance["fetch_phase"] = getattr(fetch_pipeline_result, "fetch_method", "static") or "static"
    elif fallback_fetch_extra is not None:
        provenance = _prov.provenance_from_fetch_extra(html, args.url, final_url or args.url, fallback_fetch_extra)
        provenance["fetched_at"] = _prov.now_utc_iso()
    else:
        # 파일·stdin 입력: fetch 사실이 없으므로 status/fetched_at/encoding 은 null (지어내지 않는다)
        provenance = _prov.build_provenance(html, requested_url=args.url or None, fetch_phase="input")

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
        # 봉투 축 (v7.1.0) — 값이 있는 것만 싣는다 (파일 입력은 fetched_at/status 부재)
        if provenance.get("fetched_at"):
            frontmatter_lines.append(f"fetched_at: {provenance['fetched_at']}")
        if provenance.get("status") is not None:
            frontmatter_lines.append(f"status: {provenance['status']}")
        frontmatter_lines.append(f"content_hash: {provenance['content_hash']}")
        frontmatter_lines.append("---")
        output = "\n".join(frontmatter_lines) + "\n\n" + content
    else:
        output = content

    # Write output
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
        else:
            print(output)
    except (OSError, IOError) as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

    # Stderr stats
    print(
        f"words={result['word_count']} "
        f"time={result['parse_time_ms']}ms "
        f"format={args.format}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
