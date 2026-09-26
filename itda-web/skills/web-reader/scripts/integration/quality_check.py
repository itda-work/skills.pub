"""Quality check script for itda-web-reader extraction pipeline.

Fetches real-world URLs and validates extraction quality.
NOT a pytest unit test — makes real network calls.

Usage:
    python3 scripts/integration/quality_check.py
    python3 scripts/integration/quality_check.py --url "Python"
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import types
from typing import Any

# ---------------------------------------------------------------------------
# 모듈 로딩
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_local_module(module_name: str, alias: str | None = None) -> types.ModuleType:
    """scripts/에서 모듈을 파일 경로로 로드하여 sys.modules에 등록한다."""
    filepath = os.path.join(_SCRIPTS_DIR, f"{module_name}.py")
    internal_name = alias if alias else module_name
    if internal_name in sys.modules:
        return sys.modules[internal_name]
    spec = importlib.util.spec_from_file_location(internal_name, filepath)
    assert spec is not None and spec.loader is not None, f"Cannot load {filepath}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[internal_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# 모든 로컬 모듈을 실제 이름으로 로드한다
_load_local_module("web_selectors")
_load_local_module("scorer")
_load_local_module("metadata")
_load_local_module("standardize")
_load_local_module("md_convert")
extract_content = _load_local_module("extract_content")

# ---------------------------------------------------------------------------
# URL catalog
# ---------------------------------------------------------------------------
QUALITY_URLS = [
    # -- Korean: Naver --------------------------------------------------------
    {
        "url": "https://m.blog.naver.com/astroyuji/224214898830",
        "label": "Naver blog mobile KO - finance",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://blog.naver.com/astroyuji/224214898830",
        "label": "Naver blog desktop->mobile rewrite",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
        "fetch_strategy": "naver_mobile",
    },
    {
        "url": "https://n.news.naver.com/mnews/article/001/0014568752",
        "label": "Naver news KO - article",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://n.news.naver.com/mnews/article/092/0002342210",
        "label": "Naver news KO - article 2",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    # -- Korean: Blogs / Communities ------------------------------------------
    {
        "url": "https://brunch.co.kr/@kakao-it/144",
        "label": "Brunch KO - tech blog",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://coding-factory.tistory.com/977",
        "label": "Tistory KO - Python tutorial",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://gall.dcinside.com/board/view/?id=programming&no=2418987",
        "label": "DC Inside KO - programming gallery",
        "min_words": 50,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://velog.io/@velopert/2022.log",
        "label": "Velog KO - dev blog (Next.js SSR)",
        "min_words": 300,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- Korean: News / Media -------------------------------------------------
    # National dailies
    {
        # Arc XP (React CSR) — article body rendered client-side only; requires Playwright.
        "url": "https://www.chosun.com/culture-life/k-culture/2026/03/16/IZM3R73KVNBDXNDKRHZNKFV5CQ/",
        "label": "Chosun Ilbo KO - culture",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
        "fetch_strategy": "dynamic",
    },
    {
        "url": "https://www.joongang.co.kr/article/25411965",
        "label": "JoongAng Ilbo KO - news",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.donga.com/news/It/article/all/20250523/131669350/1",
        "label": "Donga Ilbo KO - IT news",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.hani.co.kr/arti/culture/culture_general/1249506.html",
        "label": "Hankyoreh KO - culture",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        # Next.js CSR — requires Playwright (domcontentloaded + 3 s settle).
        "url": "https://www.hankookilbo.com/news/article/A2026031609390003723",
        "label": "Hankookilbo KO - politics",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
        "fetch_strategy": "dynamic",
    },
    # Broadcasting / news wire
    {
        # KBS: /news/view.do?ncd= is JS-injected; /news/pc/view/view.do?ncd= serves full static HTML.
        "url": "https://news.kbs.co.kr/news/pc/view/view.do?ncd=8509315",
        "label": "KBS News KO - national",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        # JTBC uses React CSR — body contains only 3 words (shell), article loaded via API; requires Playwright.
        "url": "https://news.jtbc.co.kr/article/NB12289804",
        "label": "JTBC News KO - entertainment",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
        "fetch_strategy": "dynamic",
    },
    {
        "url": "https://www.bloter.net/news/articleView.html?idxno=656697",
        "label": "Bloter KO - business",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://news.khan.co.kr/kh_news/khan_art_view.html?artid=202401010001001",
        "label": "Kyunghyang KO - news",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://www.yna.co.kr/view/AKR20240101000000001",
        "label": "Yonhap KO - news",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://www.etnews.com/20231225000023",
        "label": "ET News KO - tech",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://www.mk.co.kr/news/it/11212345",
        "label": "Maeil Economy KO - IT news",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://zdnet.co.kr/view/?no=20240101000000",
        "label": "ZDNet Korea KO - tech",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://www.itworld.co.kr/news/324025",
        "label": "ITWorld Korea KO - tech news",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    # -- Korean: Broadcasting / News Wire ------------------------------------
    # NOTE: news.kbs.co.kr and news.jtbc.co.kr block Anthropic crawler.
    {
        "url": "https://imnews.imbc.com/news/2026/society/article/6807734_36918.html",
        "label": "MBC News KO - society",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://news.sbs.co.kr/news/endPage.do?news_id=N1008478861",
        "label": "SBS News KO - society",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.ytn.co.kr/_ln/0103_202603161144318667",
        "label": "YTN KO - breaking news",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.newsis.com/view/NISX20260316_0003549855",
        "label": "Newsis KO - culture",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.news1.kr/world/middleeast-africa/6102133",
        "label": "News1 KO - international",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- Korean: Economy / Finance -------------------------------------------
    {
        "url": "https://www.hankyung.com/article/202603163041i",
        "label": "Hankyung KO - economy",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.sedaily.com/article/20019677",
        "label": "Seoul Economy KO - politics",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.edaily.co.kr/News/Read?newsId=03270166645383976&mediaCodeNo=257",
        "label": "Edaily KO - politics",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.mt.co.kr/world/2026/03/16/2026031610361896017",
        "label": "Moneytoday KO - international",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.fnnews.com/news/202603160928472616",
        "label": "Financial News KO - international",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://biz.heraldcorp.com/article/10691959",
        "label": "Herald Economy KO - business",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- Korean: Tech / IT ---------------------------------------------------
    # NOTE: bloter.net returns 403 for Anthropic crawler (bot protection).
    {
        "url": "https://www.inews24.com/view/1949432",
        "label": "iNews24 KO - politics",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    {
        "url": "https://www.ddaily.co.kr/page/view/2026031612035426587",
        "label": "Digital Daily KO - culture",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- Korean: Progressive / Citizen News ----------------------------------
    {
        # OhmyNews is ASP.NET WebForms — page body wrapped in <form runat="server">.
        # Fixed by removing "form" from EXACT_REMOVE_SELECTORS.
        "url": "https://www.ohmynews.com/NWS_Web/View/at_pg.aspx?CNTN_CD=A0003215260",
        "label": "OhmyNews KO - politics",
        "min_words": 200,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- Korean: Wikipedia ----------------------------------------------------
    {
        "url": "https://ko.wikipedia.org/wiki/%ED%8C%8C%EC%9D%B4%EC%8D%AC",
        "label": "Wikipedia KO - Python",
        "min_words": 500,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- English: Wikipedia ---------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/Large_language_model",
        "label": "Wikipedia EN - LLM",
        "min_words": 500,
        "expect_title": True,
        "expect_markdown_tables": False,
    },
    # -- English: ArXiv -------------------------------------------------------
    {
        "url": "https://arxiv.org/abs/1706.03762",
        "label": "ArXiv - Attention Is All You Need",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    # -- English: News --------------------------------------------------------
    {
        "url": "https://www.bbc.com/news/technology",
        "label": "BBC - Technology section",
        "min_words": 50,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://www.theguardian.com/technology",
        "label": "Guardian - Technology",
        "min_words": 50,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    # -- English: Blogs / Articles --------------------------------------------
    {
        "url": "https://realpython.com/python-concurrency/",
        "label": "Real Python - concurrency",
        "min_words": 300,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://stackoverflow.com/questions/11227809",
        "label": "StackOverflow - sorted array",
        "min_words": 100,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
    {
        "url": "https://news.ycombinator.com/",
        "label": "HackerNews - front page",
        "min_words": 30,
        "expect_title": True,
        "expect_markdown_tables": True,
    },
]

# ---------------------------------------------------------------------------
# URL rewrite helpers
# ---------------------------------------------------------------------------
_URL_REWRITES = {
    "naver_mobile": lambda u: u.replace("//blog.naver.com/", "//m.blog.naver.com/"),
}


def _rewrite_url(url: str, strategy: str) -> str:
    """Return the (possibly rewritten) URL for the given fetch strategy."""
    rewriter = _URL_REWRITES.get(strategy)
    return rewriter(url) if rewriter else url


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------
_SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)


def _fetch(url: str) -> str | None:
    """Fetch URL and return decoded HTML string, or None on failure."""
    try:
        from curl_cffi import requests as cffi
    except ImportError:
        print("  [skip] curl_cffi library not installed", file=sys.stderr)
        return None

    try:
        resp = cffi.get(
            url,
            timeout=10,
            allow_redirects=True,
            impersonate="safari",
            headers={"User-Agent": _SAFARI_UA},
        )
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [skip] network error: {exc}", file=sys.stderr)
        return None

    # Encoding detection: respect Content-Type header, fall back to chardet
    encoding = resp.encoding or "utf-8"
    try:
        return resp.content.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        try:
            import chardet
            detected = chardet.detect(resp.content)
            enc = detected.get("encoding") or "utf-8"
            return resp.content.decode(enc, errors="replace")
        except ImportError:
            return resp.content.decode("utf-8", errors="replace")


def _fetch_dynamic(url: str) -> str | None:
    """Playwright(fetch_dynamic.py 서브프로세스)로 JS 렌더링 페이지를 가져온다."""
    script = os.path.join(_SCRIPTS_DIR, "fetch_dynamic.py")
    if not os.path.exists(script):
        print(f"  [skip] fetch_dynamic.py not found at {script}", file=sys.stderr)
        return None

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = f.name
    try:
        proc = subprocess.run(
            [sys.executable, script, "--url", url, "--output", tmp, "--timeout", "30"],
            capture_output=True,
            timeout=50,
        )
        if proc.returncode != 0:
            stderr_msg = proc.stderr.decode(errors="replace").strip()
            print(f"  [skip] fetch_dynamic failed: {stderr_msg[:120]}", file=sys.stderr)
            return None
        with open(tmp, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as exc:
        print(f"  [skip] fetch_dynamic error: {exc}", file=sys.stderr)
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _check_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Run a single URL entry.  Returns a result dict."""
    strategy = entry.get("fetch_strategy", "static")
    url = entry["url"]
    fetch_url = _rewrite_url(url, strategy)

    if strategy == "dynamic":
        html = _fetch_dynamic(fetch_url)
    else:
        # Covers both "static" and "naver_mobile" (URL already rewritten above)
        html = _fetch(fetch_url)

    if html is None:
        return {"status": "SKIP", "words": 0, "title": False, "tables": False,
                "strategy": strategy}

    try:
        result = extract_content.extract_with_retry(html, url, fmt="markdown")
    except Exception as exc:
        return {"status": "FAIL", "words": 0, "title": False, "tables": False,
                "strategy": strategy, "error": str(exc)}

    content: str = result.get("content", "")
    word_count: int = result.get("word_count", 0)
    metadata: dict[str, Any] = result.get("metadata", {})

    # words check
    words_ok = word_count >= entry["min_words"]

    # title check
    if entry["expect_title"]:
        title_ok = bool(metadata.get("title", ""))
    else:
        title_ok = True  # not checked

    # tables check: expect_markdown_tables=True means no raw <table> in output
    if entry["expect_markdown_tables"]:
        tables_ok = "<table>" not in content
    else:
        tables_ok = True  # complex tables are expected; not checked

    passed = words_ok and title_ok and tables_ok
    return {
        "status": "PASS" if passed else "FAIL",
        "words": word_count,
        "title": title_ok,
        "tables": tables_ok,
        "words_ok": words_ok,
        "strategy": strategy,
    }


def _render_bool(val: bool, applicable: bool = True) -> str:
    if not applicable:
        return "-"
    return "✓" if val else "✗"


def _strategy_short(strategy: str) -> str:
    """Return a short strategy label for table display."""
    mapping = {
        "static": "static",
        "naver_mobile": "naver_m",
        "dynamic": "dynamic",
    }
    return mapping.get(strategy, strategy[:7])


def run(urls: list[dict[str, Any]]) -> int:
    """Run all URL checks and print results table.  Returns exit code."""
    col_label = 38
    col_strategy = 8
    col_words = 7
    col_title = 6
    col_tables = 7
    col_status = 6

    header = (
        f" {'#':>2}  {'Label':<{col_label}}  "
        f"{'Strategy':<{col_strategy}}  "
        f"{'Words':>{col_words}}  {'Title':<{col_title}}  "
        f"{'Tables':<{col_tables}}  {'Status':<{col_status}}"
    )
    sep = "\u2500" * len(header)

    print(header)
    print(sep)

    passed = 0
    failed = 0
    skipped = 0
    results: list[dict[str, Any]] = []

    for i, entry in enumerate(urls, 1):
        label = entry["label"]
        short_label = label[:col_label] if len(label) > col_label else label
        print(f" {i:>2}  {short_label:<{col_label}}  ...", end="\r", flush=True)

        if entry.get("skip"):
            res = {"status": "SKIP", "words": 0, "title": True, "tables": True,
                   "strategy": entry.get("fetch_strategy", "static")}
        else:
            res = _check_entry(entry)
        results.append(res)

        status = res["status"]
        words = res["words"]
        strategy_str = _strategy_short(res.get("strategy", "static"))
        title_str = _render_bool(res["title"], entry["expect_title"])
        tables_str = _render_bool(res["tables"], entry["expect_markdown_tables"])

        if status == "SKIP":
            skipped += 1
        elif status == "PASS":
            passed += 1
        else:
            failed += 1

        line = (
            f" {i:>2}  {short_label:<{col_label}}  "
            f"{strategy_str:<{col_strategy}}  "
            f"{words:>{col_words}}  {title_str:<{col_title}}  "
            f"{tables_str:<{col_tables}}  {status:<{col_status}}"
        )
        print(line)

    print(sep)
    skipped_note = " (network)" if skipped else ""
    print(f"Result: {passed} passed, {failed} failed, {skipped} skipped{skipped_note}")

    return 0 if failed == 0 else 1


def _is_playwright_available() -> bool:
    """Return True if the playwright package is importable."""
    import importlib.util
    return importlib.util.find_spec("playwright") is not None


def _ensure_playwright(entries: list[dict[str, Any]]) -> None:
    """Install Playwright + Chromium if any entry uses fetch_strategy='dynamic'.

    Prints a clear user-facing notice before installing so the user knows
    why the process is taking time (Chromium browser download is ~150 MB).
    """
    needs_dynamic = any(e.get("fetch_strategy") == "dynamic" for e in entries)
    if not needs_dynamic:
        return

    if _is_playwright_available():
        return

    print(
        "\n"
        "[Playwright] 일부 테스트 URL은 JS 렌더링(React/Next.js CSR)이 필요합니다.\n"
        "  대상: 조선일보(Arc XP), 한국일보(Next.js), JTBC(React)\n"
        "  이 사이트들은 정적 HTML에 본문이 없으며,\n"
        "  헤드리스 Chromium 브라우저로 JS 실행 후 파싱해야 합니다.\n"
        "\n"
        "[Playwright] playwright 패키지와 Chromium 브라우저를 설치합니다.\n"
        "  Chromium 다운로드는 약 150~200 MB이므로 수 분이 걸릴 수 있습니다.\n"
        "  설치가 완료되면 자동으로 테스트를 재개합니다.\n",
        flush=True,
    )

    print("[Playwright] pip install playwright ...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright", "-q"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("[Playwright] 패키지 설치 실패. dynamic 항목은 SKIP됩니다.", flush=True)
        return

    print("[Playwright] playwright install chromium ...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("[Playwright] Chromium 설치 실패. dynamic 항목은 SKIP됩니다.", flush=True)
        return

    print("[Playwright] 설치 완료. 테스트를 재개합니다.\n", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quality check: fetch real URLs and validate extraction"
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Test a single URL from catalog by substring match on label or url",
    )
    args = parser.parse_args()

    catalog = QUALITY_URLS
    if args.url:
        needle = args.url.lower()
        catalog = [
            e for e in QUALITY_URLS
            if needle in e["label"].lower() or needle in e["url"].lower()
        ]
        if not catalog:
            print(f"No catalog entry matched '{args.url}'")
            sys.exit(2)

    _ensure_playwright(catalog)
    sys.exit(run(catalog))


if __name__ == "__main__":
    main()
