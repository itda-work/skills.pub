"""Content scoring algorithm for main content detection.

Ported from Defuddle v0.13.0 (TypeScript) to Python.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import web_selectors as _sel

if TYPE_CHECKING:
    from bs4 import Tag

CJK_RANGES: re.Pattern[str] = re.compile(
    r"["
    r"\u4e00-\u9fff"   # CJK Unified Ideographs
    r"\u3040-\u309f"   # Hiragana
    r"\u30a0-\u30ff"   # Katakana
    r"\uac00-\ud7af"   # Hangul Syllables
    r"]"
)


def count_words(text: str) -> int:
    """Count words with CJK character support.

    Each CJK character (Hangul, CJK Ideographs, Hiragana, Katakana) counts as
    one word. Latin/ASCII text is split by whitespace.
    """
    cjk_count = len(CJK_RANGES.findall(text))
    non_cjk = CJK_RANGES.sub(" ", text)
    latin_words = [w for w in non_cjk.split() if w.strip()]
    return cjk_count + len(latin_words)


def score_element(element: "Tag") -> float:
    """Score a BeautifulSoup element for content relevance.

    Scoring factors:
    - +1 per word in element text
    - +10 per <p> tag
    - +1 per comma in text
    - +15 for content-class/id names
    - link density penalty (reduces score proportionally)
    - image density penalty (-3 * images / max(words, 1))
    """
    text = element.get_text()
    words = count_words(text)
    score = float(words)

    # Paragraph bonus
    score += len(element.find_all("p")) * 10

    # Comma bonus
    score += text.count(",")

    # Content class/id bonus
    classes = " ".join(element.get("class", []))  # type: ignore[arg-type]
    el_id = element.get("id", "") or ""
    combined = f"{classes} {el_id}".lower()
    if combined.strip() and _sel.CONTENT_CLASS_PATTERNS and _sel.CONTENT_CLASS_PATTERNS.search(combined):
        score += 15

    # Link density penalty: reduce by proportion of link text (capped at 50%)
    all_text_len = len(text)
    if all_text_len > 0:
        link_text_len = sum(len(a.get_text()) for a in element.find_all("a"))
        link_ratio = min(link_text_len / all_text_len, 0.5)
        score *= (1 - link_ratio)

    # Image density penalty (coefficient 1.0) with photo journalism detection.
    # Photo journalism pages (3+ images, <200 words) get a +20 bonus instead
    # of a penalty, since dense image content IS the article for those pages.
    image_count = len(element.find_all("img"))
    if image_count > 0:
        if image_count >= 3 and words < 200:
            # Photo journalism page: reward instead of penalizing
            score += 20
        else:
            score -= 1.0 * (image_count / max(words, 1))

    return max(score, 0.0)


def is_likely_content(element: "Tag") -> bool:
    """Check if a block element is likely content (not boilerplate).

    Checks (in order):
    1. ARIA role indicates content area
    2. Class/ID contains content-indicating keywords
    3. Word count > 100
    4. Word count > 50 AND has >= 2 paragraphs or list items
    5. Word count > 30 AND has >= 1 paragraph or list item
    """
    role = element.get("role", "") or ""
    if role in ("article", "main", "contentinfo"):
        return True

    classes = " ".join(element.get("class", []))  # type: ignore[arg-type]
    el_id = element.get("id", "") or ""
    combined = f"{classes} {el_id}".lower()
    if combined.strip() and _sel.CONTENT_CLASS_PATTERNS and _sel.CONTENT_CLASS_PATTERNS.search(combined):
        return True

    text = element.get_text()
    words = count_words(text)

    if words > 100:
        return True

    p_count = len(element.find_all("p"))
    li_count = len(element.find_all("li"))

    if words > 50 and (p_count >= 2 or li_count >= 2):
        return True

    if words > 30 and (p_count >= 1 or li_count >= 1):
        return True

    return False


def score_non_content_block(element: "Tag") -> float:
    """Calculate penalty score for potentially non-content blocks.

    Returns a negative score if the block appears to be non-content.
    Returns 0.0 if no penalties apply.
    """
    penalty = 0.0

    # Nav keyword penalty
    classes = " ".join(element.get("class", []))  # type: ignore[arg-type]
    el_id = element.get("id", "") or ""
    combined = f"{classes} {el_id}".lower()
    if _sel.NAV_KEYWORD_PATTERNS and _sel.NAV_KEYWORD_PATTERNS.search(combined):
        penalty -= 10

    # Link density checks
    text = element.get_text()
    total_text_len = len(text)
    if total_text_len > 0:
        link_text_len = sum(len(a.get_text()) for a in element.find_all("a"))
        link_density = link_text_len / total_text_len

        if link_density > 0.5:
            penalty -= 15
        if link_density > 0.8:
            penalty -= 15

        # List with mostly links
        li_count = len(element.find_all("li"))
        if li_count > 3 and link_density > 0.4:
            penalty -= 10

    # Author/profile/social links
    all_links = element.find_all("a", href=True)
    social_domains = ("twitter.com", "facebook.com", "linkedin.com", "instagram.com")
    profile_links = [
        a for a in all_links
        if "/author/" in (a.get("href") or "")
        or "/profile/" in (a.get("href") or "")
        or any(d in (a.get("href") or "") for d in social_domains)
    ]
    if len(profile_links) >= 3:
        penalty -= 15

    # Card grid detection: many headings + images, few prose words
    heading_count = len(element.find_all(["h2", "h3", "h4"]))
    image_count = len(element.find_all("img"))
    words = count_words(text)
    if heading_count >= 3 and image_count >= 2 and words < 50:
        penalty -= 15

    return penalty
