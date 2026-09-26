"""Tavily 검색 클라이언트 — raw 결과.

POST https://api.tavily.com/search (api_key 는 요청 body 로 전달).
응답: {"results": [{"title","url","content","score","published_date"?}], "answer"?}
"""
from __future__ import annotations

from search_env import get_tavily_key
from search_http import request_json
from search_results import EngineResponse, SearchResult, source_from_url, strip_html

API_URL = "https://api.tavily.com/search"
MAX_RESULTS = 20


class TavilyClient:
    engine = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "TavilyClient":
        return cls(get_tavily_key())

    def search(self, query: str, count: int = 5) -> EngineResponse:
        body = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(count, MAX_RESULTS)),
            "search_depth": "basic",
            "include_answer": False,
        }
        data = request_json(API_URL, method="POST", json_body=body, engine=self.engine)
        results: list[SearchResult] = []
        for idx, item in enumerate(data.get("results") or [], start=1):
            url = item.get("url", "")
            results.append(
                SearchResult(
                    rank=idx,
                    title=strip_html(item.get("title")) or url,
                    url=url,
                    snippet=strip_html(item.get("content")),
                    source=source_from_url(url),
                    engine=self.engine,
                    score=item.get("score"),
                    published_at=item.get("published_date"),
                )
            )
        return EngineResponse(
            engine=self.engine,
            results=results,
            answer=data.get("answer") or None,
            meta={"search_depth": "basic"},
        )
