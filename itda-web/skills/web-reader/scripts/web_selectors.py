"""CSS selector definitions for itda-web-reader content extraction.

Ported from Defuddle v0.13.0 (TypeScript) to Python.
"""
from __future__ import annotations

import fnmatch
import re
from urllib.parse import urlparse

# Entry point selectors for main content detection (priority order)
# More specific selectors come first; 'body' is the final fallback.
ENTRY_POINT_SELECTORS: list[str] = [
    "#post",
    ".post-content",
    ".post-body",
    ".article-content",
    "#article-content",
    ".article_post",
    ".article-wrapper",
    ".entry-content",
    ".content-article",
    ".instapaper_body",
    ".post",
    ".markdown-body",
    "article",
    '[role="article"]',
    "main",
    '[role="main"]',
    "#content",
    "body",
]

# Exact CSS selectors for element removal (~100 selectors)
EXACT_REMOVE_SELECTORS: list[str] = [
    # Inline scripts and styles
    "noscript",
    "script",
    "style",
    # Structural chrome
    "header",
    "footer",
    "nav",
    # Note: "form" intentionally excluded — ASP.NET WebForms sites (e.g. OhmyNews)
    # wrap the entire page body in <form runat="server">, so removing <form> destroys content.
    "button",
    "dialog",
    "aside",
    # Generic ad/promotional classes
    ".ad",
    ".ads",
    ".advert",
    ".advertisement",
    # Layout helpers
    ".sidebar",
    ".side-bar",
    ".widget",
    ".banner",
    # Overlays and popups
    ".popup",
    ".modal",
    ".overlay",
    # Marketing noise
    ".cookie",
    ".promo",
    ".promotion",
    ".newsletter",
    # Social sharing
    ".social",
    ".share",
    ".sharing",
    # Content discovery noise
    ".related",
    ".recommended",
    ".tags",
    ".tag-list",
    # Comment sections
    ".comments",
    ".comment-section",
    # Author info
    ".author-bio",
    ".author-info",
    ".byline",
    # Navigation aids
    ".breadcrumb",
    ".breadcrumbs",
    # Table of contents
    ".toc",
    ".table-of-contents",
    # Post meta
    ".meta",
    ".post-meta",
    # ID-based selectors
    "#sidebar",
    "#header",
    "#footer",
    "#nav",
    "#navigation",
    "#comments",
    "#disqus_thread",
    # Pagination
    ".wp-pagenavi",
    ".pagination",
    ".page-nav",
    ".nav-links",
    # ARIA roles for structural chrome
    '[role="banner"]',
    '[role="navigation"]',
    '[role="complementary"]',
    # ARIA ad labels
    '[aria-label="advertisement"]',
    # Data attributes for ads
    "[data-ad]",
    "[data-ads]",
]

# Compiled regex for partial class/ID pattern matching (~40 key patterns)
# Matches class/ID substrings that indicate non-content elements.
PARTIAL_REMOVE_PATTERNS: re.Pattern[str] = re.compile(
    r"(?i)\b(?:"
    r"advert"
    r"|article-meta"
    r"|author-bio"
    r"|breadcrumb"
    r"|byline"
    r"|caption-side"
    r"|comments"
    r"|cookie"
    r"|footer"
    r"|header-widget"
    r"|masthead"
    r"|more-articles"
    r"|navbar"
    r"|newsletter"
    r"|paid-content"
    r"|paywall"
    r"|promo"
    r"|recommended"
    r"|related"
    r"|right-rail"
    r"|rss"
    r"|share-btn"
    r"|sidebar"
    r"|skip-to"
    r"|social"
    r"|sponsored"
    r"|subscribe"
    r"|tag-list"
    r"|toolbar"
    r"|trending"
    r"|widget"
    r")\b"
)

# Compiled regex for content-indicating class/ID patterns
# Matches class/ID substrings that indicate main content elements.
CONTENT_CLASS_PATTERNS: re.Pattern[str] = re.compile(
    r"(?i)\b(?:"
    r"content"
    r"|article"
    r"|post"
    r"|entry"
    r"|blog"
    r"|story"
    r"|main"
    r"|body"
    r"|text"
    r"|prose"
    r"|markdown"
    r")\b"
)

# Compiled regex for navigation/non-content keyword patterns
NAV_KEYWORD_PATTERNS: re.Pattern[str] = re.compile(
    r"(?i)\b(?:"
    r"advertisement"
    r"|cookie"
    r"|footer"
    r"|menu"
    r"|newsletter"
    r"|popup"
    r"|promo"
    r"|sidebar"
    r"|social"
    r"|sponsor"
    r")\b"
)

# ---------------------------------------------------------------------------
# SITE_PATTERNS — 도메인별 옵트인 우선 셀렉터 레지스트리
# SPEC-WEBREADER-008 REQ-6
# ---------------------------------------------------------------------------

# @MX:NOTE: [AUTO] SITE_PATTERNS — 도메인별 옵트인 우선 셀렉터, 일반 fallback 보존.
# SPEC-WEBREADER-008 REQ-6. 추가 도메인 등록은 후속 PR로 확장.
# @MX:NOTE: [AUTO] SPEC-WEBREADER-007 도메인 중립화 정책과의 관계 —
# SITE_PATTERNS는 어댑터(SPEC-006 영역)가 아니라 "이 도메인에는 이런 본문 셀렉터가 통한다"는
# 옵트인 hint. 어댑터 레이어와 다른 추상화 수준.
# @MX:NOTE: [AUTO] fnmatch 한계 — medium.com과 *.medium.com 모두 등록 필요 (REQ-6.5).
# fnmatch.fnmatch('medium.com', '*.medium.com')는 False를 반환함.
SITE_PATTERNS: dict[str, dict] = {
    # Naver 모바일 뉴스
    "n.news.naver.com": {
        "content_selectors": ["#dic_area", ".article_body", "._article_content"],
        "title_fallback": "h2.media_end_head_headline",
        "dynamic": True,
    },
    # Naver 뉴스 (일반)
    "news.naver.com": {
        "content_selectors": ["#dic_area", ".article_body", "._article_content"],
        "title_fallback": "h2.media_end_head_headline",
        "dynamic": True,
    },
    # Medium 본 도메인 — exact match 필요 (D14: fnmatch('medium.com', '*.medium.com')는 False)
    "medium.com": {
        "content_selectors": ["article", "section[data-field='body']"],
        "title_fallback": "h1",
        "dynamic": False,
    },
    # Medium 서브도메인 (username.medium.com 형태) — wildcard match
    "*.medium.com": {
        "content_selectors": ["article", "section[data-field='body']"],
        "title_fallback": "h1",
        "dynamic": False,
    },
    # Hacker News
    "news.ycombinator.com": {
        "content_selectors": [".athing", ".storytext", "table.fatitem"],
        "title_fallback": "title",
        "dynamic": False,
    },
    # ---------- JS-필수 SNS/SPA 도메인 (정적 HTML이 빈 셸) ----------
    # @MX:NOTE: [AUTO] SNS 도메인은 정적 fetch가 거의 빈 페이지를 반환 →
    # 자동 폴백을 거치며 한 라운드 낭비. dynamic=True로 즉시 동적 진입.
    # 본문 추출 가치는 og:description (metadata.py)에서 회수.
    "www.instagram.com": {
        "content_selectors": ["main", "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "instagram.com": {
        "content_selectors": ["main", "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "x.com": {
        "content_selectors": ['article[data-testid="tweet"]', "main"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "twitter.com": {
        "content_selectors": ['article[data-testid="tweet"]', "main"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "www.threads.net": {
        "content_selectors": ["main", "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "threads.net": {
        "content_selectors": ["main", "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "www.tiktok.com": {
        "content_selectors": ["main", '[data-e2e="user-post-item"]'],
        "title_fallback": "title",
        "dynamic": True,
    },
    "www.linkedin.com": {
        "content_selectors": ["main", "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
    "www.facebook.com": {
        "content_selectors": ['div[role="main"]', "article"],
        "title_fallback": "title",
        "dynamic": True,
    },
}


def match_site_pattern(url: str) -> dict | None:
    """URL의 도메인을 SITE_PATTERNS에 매칭하여 site pattern dict를 반환한다.

    매칭 알고리즘 (REQ-6.5):
      1. 정확 매칭 우선 (domain == pattern_key)
      2. 와일드카드 fallback (fnmatch.fnmatch 사용)
      3. 매칭 없으면 None 반환

    Args:
        url: 처리할 URL 문자열.

    Returns:
        매칭된 site pattern dict, 또는 None.
    """
    try:
        domain = urlparse(url).hostname
    except Exception:
        return None
    if not domain:
        return None

    # 1) 정확 매칭 우선
    if domain in SITE_PATTERNS:
        return SITE_PATTERNS[domain]

    # 2) 와일드카드 fallback (패턴에 * 포함된 것만 시도)
    for pattern_key, pattern_val in SITE_PATTERNS.items():
        if "*" in pattern_key and fnmatch.fnmatch(domain, pattern_key):
            return pattern_val

    return None
