"""Metadata extraction from HTML documents.

Ported from Defuddle v0.13.0 (TypeScript) to Python.
Extracts title, author, published date, description, image, language, favicon, site.
"""
from __future__ import annotations

import json
import re
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse, urljoin

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

# Schema.org types that indicate article/content pages
SCHEMA_ARTICLE_TYPES = {"Article", "NewsArticle", "BlogPosting", "WebPage", "VideoObject"}


def _strip_ld_json_wrappers(raw: str) -> str:
    """LD+JSON 스크립트에서 HTML 주석 및 CDATA 래퍼를 제거한다.

    REQ-3.4: <!-- {...} --> 및 //<![CDATA[...//]]> 형식 지원.
    """
    text = raw.strip()
    # HTML 주석 제거: <!-- ... -->
    if text.startswith("<!--"):
        text = text[4:]
    if text.endswith("-->"):
        text = text[:-3]
    # CDATA 래퍼 제거: //<![CDATA[ ... //]]>
    if "//<![CDATA[" in text:
        text = text.replace("//<![CDATA[", "")
        text = text.replace("//]]>", "")
    elif "<![CDATA[" in text:
        text = text.replace("<![CDATA[", "")
        text = text.replace("]]>", "")
    return text.strip()


def parse_ld_json(soup: "BeautifulSoup") -> dict[str, Any] | None:
    """Parse Schema.org LD+JSON from HTML.

    Handles single objects, arrays, and @graph arrays.
    Matches @type: Article, NewsArticle, BlogPosting, WebPage, VideoObject.
    REQ-3.4: Also handles HTML comment-wrapped and CDATA-wrapped LD+JSON.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or ""
            # REQ-3.4: 래퍼 제거 후 파싱 시도
            cleaned = _strip_ld_json_wrappers(raw)
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, list):
            for item in data:
                result = _match_schema(item)
                if result:
                    return result
        elif isinstance(data, dict):
            # Check @graph
            if "@graph" in data:
                for item in data["@graph"]:
                    result = _match_schema(item)
                    if result:
                        return result
            result = _match_schema(data)
            if result:
                return result
    return None


def _match_schema(item: Any) -> dict[str, Any] | None:
    """Return item if its @type matches SCHEMA_ARTICLE_TYPES, else None."""
    if not isinstance(item, dict):
        return None
    item_type = item.get("@type", "")
    if isinstance(item_type, list):
        if any(t in SCHEMA_ARTICLE_TYPES for t in item_type):
            return item
    elif item_type in SCHEMA_ARTICLE_TYPES:
        return item
    return None


def extract_title(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    """Extract page title using fallback chain:
    og:title -> twitter:title -> schema headline -> meta name=title -> <title>
    """
    # 1. og:title
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    # 2. twitter:title
    tw = soup.find("meta", attrs={"name": "twitter:title"})
    if tw and tw.get("content"):
        return tw["content"].strip()

    # 3. Schema headline
    if schema_data and schema_data.get("headline"):
        return str(schema_data["headline"]).strip()

    # 4. meta name="title"
    meta_title = soup.find("meta", attrs={"name": "title"})
    if meta_title and meta_title.get("content"):
        return meta_title["content"].strip()

    # 5. <title> tag
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text():
        return title_tag.get_text().strip()

    return None


def clean_title(title: str, site_name: str | None) -> str:
    """Remove site name suffix from title (separated by |, -, or --)."""
    # Split on | - --
    parts = re.split(r"\s+[|\-]{1,2}\s+", title)
    if len(parts) <= 1:
        return title

    first_part = parts[0].strip()
    remainder = title[len(first_part):].strip()
    # Strip leading separator
    remainder = re.sub(r"^[|\-]+\s*", "", remainder).strip()

    # If site_name provided and last part matches
    if site_name and remainder.lower() == site_name.lower():
        return first_part

    # If remainder looks like a site name (short, <= 30 chars)
    if len(remainder) <= 30:
        return first_part

    return title


def extract_author(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    """Extract author using 7-level fallback chain."""
    # 1. sailthru.author
    sailthru = soup.find("meta", attrs={"name": "sailthru.author"})
    if sailthru and sailthru.get("content"):
        return sailthru["content"].strip()

    # 2. meta name="author"
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta and author_meta.get("content"):
        return author_meta["content"].strip()

    # 3. citation_author
    citation = soup.find("meta", attrs={"name": "citation_author"})
    if citation and citation.get("content"):
        return citation["content"].strip()

    # 4. Schema author
    if schema_data:
        author = schema_data.get("author")
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                return str(name).strip()
        elif isinstance(author, str) and author.strip():
            return author.strip()

    # 5. itemprop="author"
    itemprop_el = soup.find(attrs={"itemprop": "author"})
    if itemprop_el:
        text = itemprop_el.get_text().strip()
        if text:
            return text

    # 6. .author class
    author_el = soup.find(class_="author")
    if author_el:
        text = author_el.get_text().strip()
        if text:
            return text

    # 7. a[href*="/author/"]
    for a in soup.find_all("a", href=True):
        if "/author/" in (a.get("href") or ""):
            text = a.get_text().strip()
            if text:
                return text

    return None


def extract_published(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    """Extract published date using 5-level fallback chain."""
    # 1. Schema datePublished
    if schema_data and schema_data.get("datePublished"):
        return str(schema_data["datePublished"]).strip()

    # 2. meta name="publishDate"
    pub_meta = soup.find("meta", attrs={"name": "publishDate"})
    if pub_meta and pub_meta.get("content"):
        return pub_meta["content"].strip()

    # 3. article:published_time
    art_time = soup.find("meta", property="article:published_time")
    if art_time and art_time.get("content"):
        return art_time["content"].strip()

    # 4. time[itemprop="datePublished"]
    time_el = soup.find("time", attrs={"itemprop": "datePublished"})
    if time_el:
        dt = time_el.get("datetime")
        if dt:
            return str(dt).strip()

    # 5. Any time element with datetime attribute near content
    for time_el in soup.find_all("time", datetime=True):
        dt = time_el.get("datetime")
        if dt and len(str(dt)) >= 8:
            return str(dt).strip()

    return None


def _extract_description(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    # meta name="description"
    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta and desc_meta.get("content"):
        return desc_meta["content"].strip()

    # og:description
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()

    # Schema description
    if schema_data and schema_data.get("description"):
        return str(schema_data["description"]).strip()

    # twitter:description
    tw_desc = soup.find("meta", attrs={"name": "twitter:description"})
    if tw_desc and tw_desc.get("content"):
        return tw_desc["content"].strip()

    return None


def _extract_image(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    # og:image
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        return og_img["content"].strip()

    # twitter:image
    tw_img = soup.find("meta", attrs={"name": "twitter:image"})
    if tw_img and tw_img.get("content"):
        return tw_img["content"].strip()

    # Schema image
    if schema_data:
        img = schema_data.get("image")
        if isinstance(img, str):
            return img.strip()
        if isinstance(img, dict):
            url = img.get("url")
            if url:
                return str(url).strip()

    return None


def _normalize_locale(code: str) -> str:
    """Normalize a locale code to a 2-letter language tag.

    Examples:
        'ko_KR' -> 'ko'
        'en-US' -> 'en'
        'zh-CN' -> 'zh'
        'ja'    -> 'ja'
    """
    return code.split("_")[0].split("-")[0].lower()[:2]


def _extract_language(
    soup: "BeautifulSoup",
    headers: dict[str, Any] | None = None,
) -> str:
    """Extract and normalize language code from HTML document.

    Priority:
        1. <html lang="..."> attribute
        2. <meta property="og:locale" content="...">
        3. headers.get("Content-Language")
        4. Default: "ko"

    All detected values are normalized via _normalize_locale() so raw locale
    codes like 'ko_KR' or 'en-US' are never returned.
    """
    # Priority 1: html[lang]
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        return _normalize_locale(html_tag["lang"].strip())

    # Priority 2: og:locale
    og_locale = soup.find("meta", property="og:locale")
    if og_locale and og_locale.get("content"):
        return _normalize_locale(og_locale["content"].strip())

    # Priority 3: Content-Language header
    if headers:
        content_lang = headers.get("Content-Language", "")
        if content_lang:
            return _normalize_locale(content_lang.strip())

    # Priority 4: Default - REQ-3.5: 감지 불가 시 None 반환 (하드코딩 "ko" 제거)
    return None


def _extract_favicon(soup: "BeautifulSoup") -> str | None:
    # link[rel=icon]
    for rel in ("icon", "shortcut icon"):
        link = soup.find("link", rel=rel)
        if link and link.get("href"):
            return link["href"].strip()

    return "/favicon.ico"


def _extract_site(
    soup: "BeautifulSoup",
    schema_data: dict[str, Any] | None,
) -> str | None:
    # Schema publisher.name
    if schema_data:
        publisher = schema_data.get("publisher", {})
        if isinstance(publisher, dict) and publisher.get("name"):
            return str(publisher["name"]).strip()

    # og:site_name
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        return og_site["content"].strip()

    return None


def extract_metadata(
    soup: "BeautifulSoup",
    url: str | dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract all metadata fields from HTML document.

    # @MX:NOTE: [AUTO] None-safe 메타 접근 — REQ-1.1, REQ-1.2, REQ-1.3, REQ-1.4.
    # Singular extractor 시그니처 보존 (str | None), aggregator dict shape 안정 (9개 키 항상 present).
    # extract_content.py:631-639의 .get(key, "") or "" 패턴 의존 — 변경 시 다운스트림 영향.
    # 9개 키: title, author, published, description, image, language, favicon, site, domain.
    # metadata 추출 실패는 절대 hard-error 일으키지 않음 (REQ-1.4: silent skip → None 반환).

    Args:
        soup: Parsed HTML document.
        url: Base URL string for resolving domain, or HTTP response headers dict
             (for backward compatibility with callers that pass headers as second arg).
        headers: HTTP response headers dict for Content-Language detection.

    Returns dict with: title, author, published, description, image,
    language, favicon, site, domain.
    """
    # Handle backward-compat: second positional arg may be a headers dict
    _url: str | None = None
    _headers: dict[str, Any] | None = headers
    if isinstance(url, dict):
        _headers = url
    elif isinstance(url, str):
        _url = url

    schema_data = parse_ld_json(soup)

    site_name = _extract_site(soup, schema_data)
    title = extract_title(soup, schema_data)
    if title and site_name:
        title = clean_title(title, site_name)

    domain: str | None = None
    if _url:
        parsed = urlparse(_url)
        # REQ-2.7: netloc 대신 hostname을 사용해 포트 번호를 제외한다
        domain = parsed.hostname or None

    raw_image = _extract_image(soup, schema_data)
    raw_favicon = _extract_favicon(soup)

    # REQ-3.5: 상대 경로 image/favicon URL을 절대 URL로 변환
    if _url:
        if raw_image and not raw_image.startswith(("http://", "https://", "data:")):
            raw_image = urljoin(_url, raw_image)
        if raw_favicon and not raw_favicon.startswith(("http://", "https://", "data:")):
            raw_favicon = urljoin(_url, raw_favicon)

    return {
        "title": title,
        "author": extract_author(soup, schema_data),
        "published": extract_published(soup, schema_data),
        "description": _extract_description(soup, schema_data),
        "image": raw_image,
        "language": _extract_language(soup, _headers),
        "favicon": raw_favicon,
        "site": site_name,
        "domain": domain,
    }
