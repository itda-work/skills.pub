"""web-search 결과 정규화 — 통일 스키마·HTML 제거·병합·중복 제거.

엔진별 raw 응답을 단일 ``SearchResult`` 스키마로 변환하고, 여러 엔진 결과를
round-robin interleave + URL dedup + count cap 으로 병합한다(SPEC-WEB-SEARCH-001 §3.1).
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# 발췌 최대 길이 — 일부 엔진(특히 Naver)이 표 전체 등 초장문 description 을 주므로
# 출력 비대를 막기 위해 캡한다(라이브 검증으로 확인 — SPEC-WEB-SEARCH-001 §3.1).
SNIPPET_MAX = 300


def strip_html(text: str | None) -> str:
    """``<b>`` 등 HTML 태그를 제거하고 엔티티를 디코드한다(네이버·일부 엔진)."""
    if not text:
        return ""
    no_tags = _TAG_RE.sub("", text)
    return _WS_RE.sub(" ", html.unescape(no_tags)).strip()


def source_from_url(url: str) -> str:
    """URL 에서 출처 도메인(``www.`` 제거)을 추출한다."""
    try:
        netloc = urllib.parse.urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


@dataclass
class SearchResult:
    """정규화된 단일 검색 결과(SPEC-WEB-SEARCH-001 §4 schema)."""

    rank: int
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    engine: str = ""
    score: float | None = None
    published_at: str | None = None

    def __post_init__(self) -> None:
        if self.snippet and len(self.snippet) > SNIPPET_MAX:
            self.snippet = self.snippet[:SNIPPET_MAX].rstrip() + "…"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "engine": self.engine,
            "score": self.score,
            "published_at": self.published_at,
        }


@dataclass
class EngineResponse:
    """엔진 1개의 검색 응답 — raw 목록(``results``) + 선택적 ``answer`` + meta."""

    engine: str
    results: list[SearchResult] = field(default_factory=list)
    answer: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _norm_url(url: str) -> str:
    """dedup 용 URL 정규화 — 스킴 소문자·``www.``/trailing slash 제거·쿼리 보존."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return url.strip()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    base = f"{parts.scheme.lower()}://{host}{path}"
    return f"{base}?{parts.query}" if parts.query else base


def dedup_results(results: list[SearchResult]) -> list[SearchResult]:
    """정규화 URL 기준 중복 제거(첫 등장 유지). URL 없는 결과는 버린다."""
    seen: set[str] = set()
    out: list[SearchResult] = []
    for item in results:
        if not item.url:
            continue
        key = _norm_url(item.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge_results(per_engine: list[list[SearchResult]], count: int) -> list[SearchResult]:
    """엔진별 결과를 round-robin interleave → URL dedup → count cap → 1..N 재랭크.

    interleave 로 엔진 다양성을 앞쪽에 보존하고, 같은 URL 이 여러 엔진에서 와도
    1 회만 남긴다.
    """
    interleaved: list[SearchResult] = []
    max_len = max((len(engine) for engine in per_engine), default=0)
    for i in range(max_len):
        for engine_results in per_engine:
            if i < len(engine_results):
                interleaved.append(engine_results[i])

    merged = dedup_results(interleaved)
    if count and count > 0:
        merged = merged[:count]
    for idx, item in enumerate(merged, start=1):
        item.rank = idx
    return merged
