"""Serper.dev 검색 클라이언트 — Google SERP raw 결과(국내 포함).

POST https://google.serper.dev/search (헤더 X-API-KEY).
응답: {"organic": [{"title","link","snippet","position","date"?}], ...}
"""
from __future__ import annotations

from search_env import get_serper_key
from search_http import request_json
from search_results import EngineResponse, SearchResult, source_from_url, strip_html

API_URL = "https://google.serper.dev/search"
MAX_RESULTS = 20


class SerperClient:
    engine = "serper"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "SerperClient":
        return cls(get_serper_key())

    def search(self, query: str, count: int = 5) -> EngineResponse:
        headers = {"X-API-KEY": self.api_key}
        body = {
            "q": query,
            "num": max(1, min(count, MAX_RESULTS)),
            "gl": "kr",
            "hl": "ko",
        }
        data = request_json(
            API_URL, method="POST", headers=headers, json_body=body, engine=self.engine
        )
        results: list[SearchResult] = []
        for idx, item in enumerate(data.get("organic") or [], start=1):
            url = item.get("link", "")
            results.append(
                SearchResult(
                    rank=idx,
                    title=strip_html(item.get("title")) or url,
                    url=url,
                    snippet=strip_html(item.get("snippet")),
                    source=source_from_url(url),
                    engine=self.engine,
                    published_at=item.get("date"),
                )
            )
        return EngineResponse(engine=self.engine, results=results, meta={"gl": "kr"})
