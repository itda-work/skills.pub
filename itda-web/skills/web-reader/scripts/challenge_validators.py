"""Generic challenge / success validator.

Adapted from fivetaku insane-search engine/validators.py (MIT, Copyright
(c) 2026 fivetaku). Site-specific names and domains are intentionally absent.
Standalone tiny-body detection is intentionally excluded to avoid false
positives on legitimate web-reader HTTP 200 pages; small bodies only matter
when paired with low-specificity challenge markers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:  # bs4 is only needed when success_selectors are supplied
    BeautifulSoup = None  # type: ignore


HIGH_CHALLENGE_MARKERS: list[str] = [
    "sec-if-cpt-container",
    "Powered and protected by Akamai",
    "Just a moment...",
    "cf-chl-bypass",
    "Attention Required! | Cloudflare",
    "<title>Bot Challenge</title>",
    "Request unsuccessful. Incapsula",
    "The requested URL was rejected",
    "Please enable JS and disable any ad blocker",
]

LOW_CHALLENGE_MARKERS: list[str] = [
    "Access Denied",
    "Checking your browser",
    "DataDome",
    "captcha",
]

CHALLENGE_MARKERS: list[str] = HIGH_CHALLENGE_MARKERS + LOW_CHALLENGE_MARKERS
LOW_MARKER_SMALL_BODY_BYTES = 8 * 1024


class Verdict(Enum):
    STRONG_OK = "strong_ok"
    WEAK_OK = "weak_ok"
    CHALLENGE = "challenge"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    matched_selectors: list[str] = field(default_factory=list)
    body_size: int = 0
    status: int = 0

    @property
    def ok(self) -> bool:
        return self.verdict in (Verdict.STRONG_OK, Verdict.WEAK_OK)

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict.value,
            "reasons": self.reasons,
            "matched_selectors": self.matched_selectors,
            "body_size": self.body_size,
            "status": self.status,
        }


def _marker_hits(body_lower: str, markers: list[str]) -> list[str]:
    return [m for m in markers if m.lower() in body_lower]


def _set_marker_challenge(
    result: ValidationResult,
    markers: list[str],
    *,
    reason: str | None = None,
) -> ValidationResult:
    result.verdict = Verdict.CHALLENGE
    result.reasons.extend(f"marker:{marker}" for marker in markers[:3])
    if reason:
        result.reasons.append(reason)
    return result


def _extract_cookies(resp) -> dict[str, str]:
    try:
        return {c.name: c.value for c in resp.cookies.jar}
    except Exception:
        try:
            return dict(resp.cookies) if hasattr(resp, "cookies") else {}
        except Exception:
            return {}


def _abck_unresolved(cookies: dict[str, str]) -> bool:
    abck = cookies.get("_abck", "")
    return bool(abck) and "~-1~" in abck


def _selector_hits(body: str, selectors: list[str]) -> Optional[list[str]]:
    if BeautifulSoup is None:
        return None
    try:
        soup = BeautifulSoup(body, "html.parser")
    except Exception:
        return []
    hits: list[str] = []
    for selector in selectors:
        try:
            if soup.select(selector):
                hits.append(selector)
        except Exception:
            continue
    return hits


def validate(
    resp,
    *,
    success_selectors: Optional[list[str]] = None,
    known_bad_sizes: Optional[list[int]] = None,
    size_tolerance: int = 20,
    low_marker_small_body_bytes: int = LOW_MARKER_SMALL_BODY_BYTES,
) -> ValidationResult:
    """Validate a curl_cffi-like response with generic anti-bot signals.

    HTTP 200 is never returned directly by fetch_html.py; callers inspect this
    result first. Without positive selectors, a marker-free 2xx response is
    classified as WEAK_OK instead of STRONG_OK.
    """
    try:
        status = int(getattr(resp, "status_code", 0) or 0)
        text = getattr(resp, "text", "") or ""
        explicit_size = int(getattr(resp, "body_size", 0) or 0)
        size = explicit_size or len(text.encode("utf-8", errors="replace"))
    except Exception as exc:
        return ValidationResult(verdict=Verdict.UNKNOWN, reasons=[f"parse_error:{exc}"])

    result = ValidationResult(verdict=Verdict.UNKNOWN, body_size=size, status=status)

    lowered = text.lower()
    high_markers = _marker_hits(lowered, HIGH_CHALLENGE_MARKERS)
    if high_markers:
        return _set_marker_challenge(result, high_markers)

    low_markers = _marker_hits(lowered, LOW_CHALLENGE_MARKERS)
    if low_markers:
        if status != 200:
            return _set_marker_challenge(result, low_markers, reason=f"status={status}")
        if size < low_marker_small_body_bytes:
            return _set_marker_challenge(result, low_markers, reason=f"small_body:{size}")

    if status == 0 or status >= 400:
        result.verdict = Verdict.BLOCKED
        result.reasons.append(f"status={status}")
        return result

    if known_bad_sizes:
        for bad_size in known_bad_sizes:
            if abs(size - bad_size) <= size_tolerance:
                result.verdict = Verdict.CHALLENGE
                result.reasons.append(f"size_fp:{size}~{bad_size}")
                return result

    cookies = _extract_cookies(resp)
    if _abck_unresolved(cookies):
        result.verdict = Verdict.CHALLENGE
        result.reasons.append("abck_unresolved")
        return result

    if success_selectors:
        hits = _selector_hits(text, success_selectors)
        if hits is None:
            result.verdict = Verdict.UNKNOWN
            result.reasons.append("bs4_missing")
            return result
        if hits:
            result.verdict = Verdict.STRONG_OK
            result.matched_selectors = hits
            return result
        result.verdict = Verdict.CHALLENGE
        result.reasons.append("no_success_selector")
        return result

    result.verdict = Verdict.WEAK_OK
    return result
