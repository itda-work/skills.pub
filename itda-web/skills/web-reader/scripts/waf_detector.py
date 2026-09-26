"""WAF-product detection from a live response.

Adapted from fivetaku insane-search engine/waf_detector.py (MIT, Copyright
(c) 2026 fivetaku). Detectors operate on WAF vendor artifacts, never hostnames.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


PROFILES_PATH = os.path.join(os.path.dirname(__file__), "waf_profiles.yaml")

_DEFAULT_PROFILES: dict[str, dict] = {
    "unknown_challenge": {
        "detectors": {},
        "confidence_rules": {"strong": 0, "weak": 0},
        "capabilities_needed": ["needs_js_exec"],
        "tls_impersonate_candidates": [
            ["safari", "chrome", "firefox"],
            ["safari_ios", "chrome_android"],
        ],
        "referer_strategies": ["self_root", "google_search", "none"],
        "url_transform_order": ["original", "mobile_subdomain"],
        "fallback_when_challenge": ["browser"],
        "notes": "in-code default — waf_profiles.yaml unavailable",
    },
}

_LAST_LOAD_ERROR: Optional[str] = None


@dataclass
class DetectionHit:
    profile_id: str
    confidence: float
    signals: list[str]


def last_load_error() -> Optional[str]:
    return _LAST_LOAD_ERROR


def _load_profiles(path: str = PROFILES_PATH) -> dict:
    """Load profiles with graceful fallback."""
    global _LAST_LOAD_ERROR
    _LAST_LOAD_ERROR = None

    if yaml is None:
        _LAST_LOAD_ERROR = "PyYAML not installed — using in-code default profile"
        return dict(_DEFAULT_PROFILES)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except FileNotFoundError:
        _LAST_LOAD_ERROR = f"waf_profiles.yaml not found at {path}"
        return dict(_DEFAULT_PROFILES)
    except yaml.YAMLError as exc:
        _LAST_LOAD_ERROR = f"YAML parse error: {type(exc).__name__}: {str(exc)[:200]}"
        return dict(_DEFAULT_PROFILES)
    except Exception as exc:
        _LAST_LOAD_ERROR = f"profile loader: {type(exc).__name__}: {str(exc)[:200]}"
        return dict(_DEFAULT_PROFILES)

    if not isinstance(loaded, dict) or not any(k for k in loaded if not k.startswith("_")):
        _LAST_LOAD_ERROR = "waf_profiles.yaml has no usable profiles"
        return dict(_DEFAULT_PROFILES)
    return loaded


def _cookies_dict(resp) -> dict[str, str]:
    try:
        return {c.name: c.value for c in resp.cookies.jar}
    except Exception:
        try:
            return dict(resp.cookies) if hasattr(resp, "cookies") else {}
        except Exception:
            return {}


def _headers_dict(resp) -> dict[str, str]:
    try:
        return {str(k).lower(): str(v) for k, v in dict(resp.headers).items()}
    except Exception:
        return {}


def _match_patterns(haystack_keys: list[str], patterns: list[str]) -> list[str]:
    hits: list[str] = []
    lowered_keys = [key.lower() for key in haystack_keys]
    for pattern in patterns or []:
        pattern_l = pattern.lower()
        if any(char in pattern for char in "*?["):
            for key in lowered_keys:
                if fnmatch.fnmatchcase(key, pattern_l):
                    hits.append(pattern)
                    break
        elif pattern_l in lowered_keys:
            hits.append(pattern)
    return hits


def _score_profile(profile_id: str, profile: dict, resp) -> Optional[DetectionHit]:
    if profile_id.startswith("_"):
        return None
    detectors = profile.get("detectors") or {}
    if not detectors and profile_id != "unknown_challenge":
        return None

    cookies = _cookies_dict(resp)
    headers = _headers_dict(resp)
    body = (getattr(resp, "text", "") or "").lower()
    server = headers.get("server", "")
    signals: list[str] = []

    for hit in _match_patterns(list(cookies.keys()), detectors.get("cookie") or []):
        signals.append(f"cookie:{hit}")
    for hit in _match_patterns(list(headers.keys()), detectors.get("header") or []):
        signals.append(f"header:{hit}")
    for needle in detectors.get("server_contains") or []:
        if needle.lower() in server:
            signals.append(f"server:{needle}")
    for needle in detectors.get("body") or []:
        if needle.lower() in body:
            signals.append(f"body:{needle}")

    if not signals:
        return None

    rules = profile.get("confidence_rules") or {"strong": 2, "weak": 1}
    count = len(signals)
    if count >= rules.get("strong", 2):
        confidence = 0.9
    elif count >= rules.get("weak", 1):
        confidence = 0.6
    else:
        confidence = 0.3
    return DetectionHit(profile_id=profile_id, confidence=confidence, signals=signals)


def detect(resp, *, profiles: Optional[dict] = None, min_confidence: float = 0.0) -> list[DetectionHit]:
    """Return ranked WAF profile hits, best first."""
    if profiles is None:
        profiles = _load_profiles()

    hits: list[DetectionHit] = []
    for profile_id, profile in profiles.items():
        if profile_id.startswith("_"):
            continue
        hit = _score_profile(profile_id, profile, resp)
        if hit and hit.confidence >= min_confidence:
            hits.append(hit)

    hits.sort(key=lambda item: item.confidence, reverse=True)
    if not hits:
        hits.append(
            DetectionHit(
                profile_id="unknown_challenge",
                confidence=0.1,
                signals=["fallback"],
            )
        )
    return hits


def load_profile(profile_id: str, *, profiles: Optional[dict] = None) -> dict:
    if profiles is None:
        profiles = _load_profiles()
    return profiles.get(profile_id) or profiles.get("unknown_challenge") or {}
