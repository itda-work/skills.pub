"""Generic URL transforms for the curl_cffi fetch grid.

Adapted from fivetaku insane-search engine/url_transforms.py (MIT, Copyright
(c) 2026 fivetaku). Transforms are domain-agnostic rules.
"""
from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit


def _replace_host(url: str, new_host: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc=new_host))


def _original(url: str) -> Optional[str]:
    return url


def _mobile_subdomain(url: str) -> Optional[str]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host.startswith("www."):
        return None
    new_host = "m." + host[4:]
    if parts.port:
        new_host = f"{new_host}:{parts.port}"
    return _replace_host(url, new_host)


def _am_prefix(url: str) -> Optional[str]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host or host.startswith("m."):
        return None
    if host.count(".") >= 2 and not host.startswith("www."):
        return None
    if host.startswith("www."):
        return None
    return _replace_host(url, "m." + host)


def _drop_www(url: str) -> Optional[str]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host.startswith("www."):
        return None
    return _replace_host(url, host[4:])


TRANSFORMS: dict[str, Callable[[str], Optional[str]]] = {
    "original": _original,
    "mobile_subdomain": _mobile_subdomain,
    "am_prefix": _am_prefix,
    "drop_www": _drop_www,
}


def apply_transform(name: str, url: str) -> Optional[str]:
    fn = TRANSFORMS.get(name)
    if fn is None:
        raise ValueError(f"Unknown transform: {name!r}. Known: {list(TRANSFORMS)}")
    return fn(url)


def iter_transformed(url: str, order: list[str]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for name in order:
        transformed = apply_transform(name, url)
        if transformed is None or transformed in seen:
            continue
        seen.add(transformed)
        out.append((name, transformed))
    return out
