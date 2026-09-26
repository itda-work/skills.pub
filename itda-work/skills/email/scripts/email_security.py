#!/usr/bin/env python3
"""email_security — Prompt Injection defense (shared canonical).

Provides sanitize_for_llm() and wrap_email_content() for safe LLM output.
stdlib-only (re module). O(n × p) linear complexity.

정본: skills/shared/email_security.py (#736 — email·calendar 가 byte-identical
사본을 각자 보유하던 것을 승격). 소비 스킬은 소스트리 사본 없이 publish 주입
(SPEC-SHARED-INJECT-001)·conftest·PYTHONPATH=shared 로 해석한다.
"""
from __future__ import annotations

import re
import unicodedata

# Zero-width / invisible characters commonly used to bypass regex filters.
# Covers ZWSP, ZWNJ, ZWJ, LRM, RLM, LSEP, PSEP, BOM, soft-hyphen,
# WJ (U+2060), variation selectors (U+FE00-FE0F), MVS (U+180E), CGJ (U+034F).
_ZERO_WIDTH = re.compile(
    r"[\u00ad\u034f\u180e\u200b-\u200f\u2028\u2029\u2060\ufeff\ufe00-\ufe0f]"
)

# Cyrillic and Greek characters that are visually indistinguishable from Latin.
# Applied after NFKC normalization (which handles fullwidth and mathematical
# alphanumerics) to defeat cross-script homoglyph injection bypasses.
_HOMOGLYPH_MAP: dict[int, int] = {
    # Cyrillic uppercase → Latin
    0x0410: ord("A"),  # А → A
    0x0412: ord("B"),  # В → B
    0x0415: ord("E"),  # Е → E
    0x041A: ord("K"),  # К → K
    0x041C: ord("M"),  # М → M
    0x041D: ord("H"),  # Н → H
    0x041E: ord("O"),  # О → O
    0x0420: ord("P"),  # Р → P
    0x0421: ord("C"),  # С → C
    0x0422: ord("T"),  # Т → T
    0x0425: ord("X"),  # Х → X
    # Cyrillic lowercase → Latin
    0x0430: ord("a"),  # а → a
    0x0435: ord("e"),  # е → e
    0x043E: ord("o"),  # о → o
    0x0440: ord("p"),  # р → p
    0x0441: ord("c"),  # с → c
    0x0443: ord("y"),  # у → y
    0x0445: ord("x"),  # х → x
    # Greek uppercase → Latin
    0x0391: ord("A"),  # Α → A
    0x0392: ord("B"),  # Β → B
    0x0395: ord("E"),  # Ε → E
    0x0396: ord("Z"),  # Ζ → Z
    0x0397: ord("H"),  # Η → H
    0x0399: ord("I"),  # Ι → I
    0x039A: ord("K"),  # Κ → K
    0x039C: ord("M"),  # Μ → M
    0x039D: ord("N"),  # Ν → N
    0x039F: ord("O"),  # Ο → O
    0x03A1: ord("P"),  # Ρ → P
    0x03A4: ord("T"),  # Τ → T
    0x03A5: ord("Y"),  # Υ → Y
    0x03A7: ord("X"),  # Χ → X
    # Greek lowercase
    0x03BF: ord("o"),  # ο → o
}
_HOMOGLYPH_TABLE = str.maketrans(_HOMOGLYPH_MAP)

# Overhead added by wrap_email_content() in characters.
# "===EMAIL_CONTENT_START===\n" + "\n===EMAIL_CONTENT_END===" = 50 chars.
WRAPPER_OVERHEAD: int = 50

# Injection patterns based on k-mail-mcp INJECTION_PATTERNS (FR-03).
# Patterns are applied to the full text before truncation to avoid
# boundary-split bypasses (ISS-ffb63cdd).
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"\[/?INST\]", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
    re.compile(r"</?instruction>", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?", re.IGNORECASE),
    re.compile(r"new\s+(system\s+)?instructions?:", re.IGNORECASE),
    re.compile(r"###\s*instruction", re.IGNORECASE),
    re.compile(r"\[OVERRIDE\]", re.IGNORECASE),
    re.compile(r"\[JAILBREAK\]", re.IGNORECASE),
    re.compile(r"assistant:\s*i\s+will", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(prior|previous|above)", re.IGNORECASE),
    # Guard against delimiter forgery: strip wrap_email_content markers so
    # an attacker cannot embed ===EMAIL_CONTENT_END=== in their message to
    # escape the trusted-data zone (ISS-27c3b46f).
    re.compile(r"===EMAIL_CONTENT_(START|END)===", re.IGNORECASE),
]

_REPLACEMENT = "[FILTERED]"

# Baseline cap for small max_len values (headers, subjects).
# 65 536 chars covers email bodies well beyond RFC 2822 typical limits.
_MAX_INPUT = 65_536

# Hard ceiling for pattern matching to prevent O(n) blowup on huge bodies.
# 10 MB is the practical maximum for email body content (SPEC-EMAIL-004 §4.2).
_ABSOLUTE_MAX_INPUT = 10_000_000


def sanitize_for_llm(text: str | None, max_len: int = 500) -> str:
    """Sanitize email field text for safe LLM consumption.

    Replaces known Prompt Injection patterns with [FILTERED] and truncates
    to max_len characters. O(n × p) where n=text length, p=pattern count.

    Patterns are applied before truncation to avoid boundary-split bypasses
    where a pattern straddling the pre-truncation boundary escapes detection.

    Args:
        text: Raw email field value (from, subject, or body).
        max_len: Maximum output length in characters (default: 500).
            For full-body mode pass max_len=len(text). Must be >= 0.

    Returns:
        Sanitized string, empty string for None/non-string input.
    """
    if not text or not isinstance(text, str):
        return ""
    # Dynamic cap: 3× max_len (to see patterns near the boundary) but at least
    # _MAX_INPUT for small values, capped at _ABSOLUTE_MAX_INPUT to bound work.
    cap = min(max(max_len * 3, _MAX_INPUT), _ABSOLUTE_MAX_INPUT)
    s = text[:cap]
    # Step 1: NFKC normalization + zero-width stripping applied to output buffer.
    # NFKC is standard unicode normalization (converts fullwidth/math/ligatures).
    # ZWSP/ZWNJ/ZWJ etc. are stripped to prevent keyword splitting attacks.
    s = unicodedata.normalize("NFKC", s)
    s = _ZERO_WIDTH.sub("", s)

    # Step 2: Homoglyph detection uses a separate folded copy so that legitimate
    # Cyrillic/Greek content is preserved in output unless an injection is found.
    folded = s.translate(_HOMOGLYPH_TABLE)
    # Snapshot the normalized-but-unfiltered buffer for comparison in Step 3b.
    # Must snapshot BEFORE Step 3a mutates `s`, otherwise the comparison in
    # Step 3b would always be True when any ASCII pattern also matched (ISS-2a54cb78).
    original_normalized = s

    # Step 3a: Apply patterns to the original output buffer.
    for pat in _INJECTION_PATTERNS:
        s = pat.sub(_REPLACEMENT, s)

    # Step 3b: If homoglyphs were present, check whether any homoglyph-based
    # injection survived Step 3a (which only matched ASCII patterns).
    # Strategy: fold the Step-3a output buffer and re-apply patterns. If that
    # finds a new match, it means a Cyrillic/Greek lookalike bypass survived.
    # This correctly handles the mixed-attack case "[SYSTEM] [SYST\u0415M]":
    # Step 3a catches the ASCII copy; Step 3b catches the homoglyph copy.
    if folded != original_normalized:
        s_folded = s.translate(_HOMOGLYPH_TABLE)
        s_folded_check = s_folded
        for pat in _INJECTION_PATTERNS:
            s_folded_check = pat.sub(_REPLACEMENT, s_folded_check)
        if s_folded_check != s_folded:
            # Homoglyph injection survived Step 3a — return the fully
            # folded+filtered buffer (built from original folded, not s).
            folded_filtered = folded
            for pat in _INJECTION_PATTERNS:
                folded_filtered = pat.sub(_REPLACEMENT, folded_filtered)
            return folded_filtered[:max_len].strip()

    return s[:max_len].strip()


def wrap_email_content(body: str) -> str:
    """Wrap email body with content delimiters (FR-04).

    Signals to the LLM that the enclosed text is external email data,
    not an instruction or system directive.

    Args:
        body: Sanitized email body text.

    Returns:
        Body wrapped with ===EMAIL_CONTENT_START=== / ===EMAIL_CONTENT_END=== markers.
    """
    return f"===EMAIL_CONTENT_START===\n{body}\n===EMAIL_CONTENT_END==="


# ---------------------------------------------------------------------------
# Phishing signal functions (SPEC-EMAIL-005)
# ---------------------------------------------------------------------------

# Accepted Authentication-Results status values (RFC 7601 §2.7.1).
_AUTH_VALUES = r"(pass|fail|softfail|none|neutral|temperror|permerror|bestguesspass)"

_AUTH_RE: dict[str, re.Pattern[str]] = {
    "spf":   re.compile(rf"\bspf={_AUTH_VALUES}\b",   re.IGNORECASE),
    "dkim":  re.compile(rf"\bdkim={_AUTH_VALUES}\b",  re.IGNORECASE),
    "dmarc": re.compile(rf"\bdmarc={_AUTH_VALUES}\b", re.IGNORECASE),
}

# Extract the domain part from an email address (including display-name format).
_ADDR_DOMAIN_RE = re.compile(r"[\w.\-+]+@([\w.\-]+)")


def parse_auth_results(raw_header: str | None) -> dict[str, str | None]:
    """Parse SPF/DKIM/DMARC results from an Authentication-Results header.

    Args:
        raw_header: Raw Authentication-Results header value, or None if absent.

    Returns:
        Dict with keys 'spf', 'dkim', 'dmarc' — each a lowercase result string
        or None if not found in the header.
    """
    if not raw_header:
        return {"spf": None, "dkim": None, "dmarc": None}
    out: dict[str, str | None] = {}
    for key, pat in _AUTH_RE.items():
        m = pat.search(raw_header)
        out[key] = m.group(1).lower() if m else None
    return out


def build_auth_label(parsed: dict[str, str | None]) -> str:
    """Build a human-readable auth summary string.

    Args:
        parsed: Output of parse_auth_results().

    Returns:
        Pipe-separated label such as "SPF:pass | DKIM:pass | DMARC:fail",
        or "인증정보없음" when all values are None.
    """
    parts = [
        f"{key.upper()}:{val}"
        for key in ("spf", "dkim", "dmarc")
        if (val := parsed.get(key))
    ]
    return " | ".join(parts) if parts else "인증정보없음"


def extract_domain(address: str | None) -> str:
    """Extract the lowercase domain from an email address.

    Supports plain ("user@domain.com") and display-name ("Name <user@domain.com>") formats.

    Args:
        address: Email address string, or None.

    Returns:
        Lowercase domain string, or empty string if not found.
    """
    if not address:
        return ""
    m = _ADDR_DOMAIN_RE.search(address)
    return m.group(1).lower() if m else ""


def reply_to_differs(from_addr: str, reply_to_addr: str | None) -> bool:
    """Return True when the Reply-To domain differs from the From domain.

    A domain mismatch is a common indicator of reply-path phishing.
    Comparison is case-insensitive and exact (sub-domains are treated as different).

    Args:
        from_addr: From header value (plain or display-name format).
        reply_to_addr: Reply-To header value, or None / empty if absent.

    Returns:
        True if Reply-To domain differs from From domain, False otherwise.
    """
    if not reply_to_addr:
        return False
    from_domain = extract_domain(from_addr)
    reply_domain = extract_domain(reply_to_addr)
    if not from_domain or not reply_domain:
        return False
    return from_domain != reply_domain
