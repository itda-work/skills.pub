"""HTML standardization for content extraction pipeline.

Ported from Defuddle v0.13.0 (TypeScript) to Python.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

# Void elements that should never be removed even when "empty"
_VOID_ELEMENTS = frozenset(
    ["area", "base", "br", "col", "embed", "hr", "img", "input",
     "link", "meta", "param", "source", "track", "wbr"]
)

# Elements that may contain meaningful children even with no text
_PRESERVE_IF_HAS_CHILDREN = frozenset(["img", "svg", "video", "audio", "picture"])

# Attribute whitelist
ATTR_WHITELIST = frozenset([
    "alt", "href", "src", "srcset", "id", "class", "colspan", "rowspan",
    "role", "lang", "title", "width", "height", "data-lang",
])

# Language detection patterns for code blocks
_LANG_PATTERNS = [
    re.compile(r"language-(\w+)"),
    re.compile(r"lang-(\w+)"),
    re.compile(r"highlight-source-(\w+)"),
]


def _make_tag(soup: object, name: str) -> "Tag":
    """Create a new BS4 Tag using the document root as factory.

    Works even when soup is a detached Tag (not a BeautifulSoup document).
    Falls back to a fresh BeautifulSoup when no document root is found.
    """
    from bs4 import BeautifulSoup, Tag
    if isinstance(soup, BeautifulSoup):
        return soup.new_tag(name)
    # Walk up the parent chain to find the BeautifulSoup document root.
    # Avoids find_parent(BeautifulSoup) which triggers BS4 filter bugs in some versions.
    if isinstance(soup, Tag):
        node = soup.parent
        while node is not None:
            if isinstance(node, BeautifulSoup):
                return node.new_tag(name)
            node = getattr(node, "parent", None)
    return BeautifulSoup("", "html.parser").new_tag(name)


def normalize_headings(soup: "BeautifulSoup", title: str | None = None) -> None:
    """Convert all H1 to H2. Remove first H2 if it matches extracted title."""
    # Convert all h1 -> h2
    for h1 in list(soup.find_all("h1")):
        h1.name = "h2"

    # Remove first h2 that matches the title (case-insensitive)
    if title:
        title_clean = title.strip().lower()
        for h2 in soup.find_all("h2"):
            if h2.get_text().strip().lower() == title_clean:
                h2.decompose()
                break


def standardize_code_blocks(soup: "BeautifulSoup") -> None:
    """Detect language and normalize code blocks to standard format."""
    # Handle GitHub-style highlight divs first:
    # <div class="highlight highlight-source-{lang}"><pre>...</pre></div>
    for div in list(soup.find_all("div", class_=True)):
        classes = " ".join(div.get("class", []))
        lang = None
        for pat in _LANG_PATTERNS:
            m = pat.search(classes)
            if m:
                lang = m.group(1)
                break
        if lang:
            pre = div.find("pre")
            if pre:
                # Wrap content in <code class="language-{lang}">
                code_text = pre.get_text()
                code_tag = _make_tag(soup, "code")
                code_tag["class"] = f"language-{lang}"
                code_tag.string = code_text
                pre.clear()
                pre.append(code_tag)
                # Replace the wrapper div with just the <pre>
                div.replace_with(pre)

    # Normalize existing <pre><code> blocks
    for pre in list(soup.find_all("pre")):
        code = pre.find("code")
        if code:
            # Detect language from code's attributes
            lang = _detect_lang(pre, code)
            if lang and not any(
                cls.startswith("language-") for cls in (code.get("class") or [])
            ):
                existing_classes = list(code.get("class") or [])
                # Remove old lang- classes
                existing_classes = [
                    c for c in existing_classes
                    if not c.startswith("lang-") and not c.startswith("language-")
                ]
                existing_classes.insert(0, f"language-{lang}")
                code["class"] = existing_classes
        else:
            # <pre> without <code>: check for data-lang attribute
            lang = None
            data_lang = pre.get("data-lang") or pre.get("data-language") or pre.get("language")
            if data_lang:
                lang = str(data_lang)
            if not lang:
                for pat in _LANG_PATTERNS:
                    m = pat.search(" ".join(pre.get("class") or []))
                    if m:
                        lang = m.group(1)
                        break
            # Wrap bare text in <code>
            content = pre.get_text()
            pre.clear()
            code_tag = _make_tag(soup, "code")
            if lang:
                code_tag["class"] = [f"language-{lang}"]
            code_tag.string = content
            pre.append(code_tag)


def _detect_lang(pre: "Tag", code: "Tag") -> str | None:
    """Detect language from element attributes and classes."""
    # Check code element attributes
    for attr in ("data-lang", "data-language", "language"):
        val = code.get(attr)
        if val:
            return str(val)

    # Check code element classes
    for cls in (code.get("class") or []):
        for pat in _LANG_PATTERNS:
            m = pat.match(cls)
            if m:
                return m.group(1)

    # Check pre element attributes
    for attr in ("data-lang", "data-language", "language"):
        val = pre.get(attr)
        if val:
            return str(val)

    # Check pre element classes
    for cls in (pre.get("class") or []):
        for pat in _LANG_PATTERNS:
            m = pat.match(cls)
            if m:
                return m.group(1)

    # Check parent classes
    parent = pre.parent
    if parent:
        for cls in (parent.get("class") or []):
            for pat in _LANG_PATTERNS:
                m = pat.match(cls)
                if m:
                    return m.group(1)

    return None


def standardize_images(soup: "BeautifulSoup") -> None:
    """Resolve lazy-loaded images, remove base64 placeholders, simplify picture elements."""
    for img in soup.find_all("img"):
        # Promote data-src -> src
        if img.get("data-src") and not img.get("src"):
            img["src"] = img["data-src"]
            del img["data-src"]

        # Promote data-srcset -> srcset
        if img.get("data-srcset") and not img.get("srcset"):
            img["srcset"] = img["data-srcset"]
            del img["data-srcset"]

        # Remove short base64 placeholder src
        src = img.get("src", "")
        if src.startswith("data:") and len(src) < 200:
            del img["src"]

    # Handle picture elements
    for picture in list(soup.find_all("picture")):
        img = picture.find("img")
        if img:
            # Try to promote srcset from first source
            source = picture.find("source")
            if source and source.get("srcset") and not img.get("srcset"):
                img["srcset"] = source["srcset"]
            # Replace picture with just img
            picture.replace_with(img)
        else:
            picture.decompose()


def remove_empty_elements(soup: "BeautifulSoup") -> None:
    """Remove elements with no text content and no meaningful children."""
    changed = True
    while changed:
        changed = False
        for tag in list(soup.find_all(True)):
            if tag.name in _VOID_ELEMENTS:
                continue
            # Keep if has text
            if tag.get_text().strip():
                continue
            # Keep if has meaningful child elements
            has_meaningful = any(
                child.name in _PRESERVE_IF_HAS_CHILDREN
                for child in tag.find_all(True, recursive=False)
                if hasattr(child, "name")
            )
            if has_meaningful:
                continue
            # Also keep void element children
            has_void_child = any(
                child.name in _VOID_ELEMENTS
                for child in tag.find_all(True, recursive=False)
                if hasattr(child, "name")
            )
            if has_void_child:
                continue
            tag.decompose()
            changed = True


def flatten_wrappers(soup: "BeautifulSoup") -> None:
    """Flatten wrapper div elements that serve only as single-child containers."""
    changed = True
    while changed:
        changed = False
        for div in list(soup.find_all("div")):
            # Check for direct text content
            direct_text = "".join(
                str(c) for c in div.children if isinstance(c, str)
            ).strip()
            if direct_text:
                continue
            # Get direct element children
            children = [c for c in div.children if hasattr(c, "name")]
            if len(children) == 1:
                div.replace_with(children[0])
                changed = True


def normalize_table_cells(soup: "BeautifulSoup") -> None:
    """Unwrap single block-child inside <td>/<th> to avoid markdown artifacts.

    Many CMSes wrap cell text in <p> or <div>. When markdownify encounters
    <td><p>text</p></td>, it emits line breaks that break the pipe-table format.
    This step unwraps single block children, making cells flat before conversion.
    Only unwraps when the cell has exactly one block-level child element.
    """
    _UNWRAP_BLOCKS = {"p", "div"}
    for cell in soup.find_all(["td", "th"]):
        block_children = [
            c for c in cell.children
            if getattr(c, "name", None) in _UNWRAP_BLOCKS
        ]
        if len(block_children) == 1 and len(list(cell.children)) == 1:
            block_children[0].unwrap()


def strip_attributes(soup: "BeautifulSoup") -> None:
    """Remove non-whitelisted attributes from all elements."""
    for tag in soup.find_all(True):
        attrs_to_remove = [k for k in list(tag.attrs.keys()) if k not in ATTR_WHITELIST]
        for attr in attrs_to_remove:
            del tag[attr]


def normalize_spaces(soup: "BeautifulSoup") -> None:
    """Convert non-breaking spaces to regular spaces in text nodes."""
    from bs4 import NavigableString
    for string in soup.find_all(string=True):
        if "\u00a0" in string:
            string.replace_with(string.replace("\u00a0", " "))


def standardize_content(soup: "BeautifulSoup", title: str | None = None) -> None:
    """Apply all standardization rules in correct order.

    Order: headings -> code blocks -> images -> cleanup operations
    """
    normalize_headings(soup, title)
    standardize_code_blocks(soup)
    standardize_images(soup)
    remove_empty_elements(soup)
    flatten_wrappers(soup)
    normalize_table_cells(soup)
    strip_attributes(soup)
    normalize_spaces(soup)
