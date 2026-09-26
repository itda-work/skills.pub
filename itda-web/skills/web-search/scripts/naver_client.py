"""Naver 검색 OpenAPI 클라이언트 — 국내 web/news/blog raw 결과.

GET https://openapi.naver.com/v1/search/{type}.json (헤더 X-Naver-Client-Id/Secret).
응답: {"items": [{"title","link","description","pubDate"?,"postdate"?,"bloggername"?}]}
제목·설명의 ``<b>`` 태그는 제거한다(§3.3).
"""
from __future__ import annotations

from search_env import get_naver_keys
from search_http import request_json
from search_results import EngineResponse, SearchResult, source_from_url, strip_html

BASE_URL = "https://openapi.naver.com/v1/search"
MAX_DISPLAY = 100
TYPE_MAP = {"web": "webkr", "news": "news", "blog": "blog"}


class NaverClient:
    engine = "naver"

    def __init__(self, client_id: str, client_secret: str, naver_type: str = "web") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.naver_type = naver_type if naver_type in TYPE_MAP else "web"

    @classmethod
    def from_env(cls, naver_type: str = "web") -> "NaverClient":
        client_id, client_secret = get_naver_keys()
        return cls(client_id, client_secret, naver_type)

    def search(self, query: str, count: int = 5) -> EngineResponse:
        api_type = TYPE_MAP[self.naver_type]
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": query,
            "display": max(1, min(count, MAX_DISPLAY)),
            "start": 1,
            "sort": "sim",
        }
        data = request_json(
            f"{BASE_URL}/{api_type}.json",
            method="GET",
            headers=headers,
            params=params,
            engine=self.engine,
        )
        results: list[SearchResult] = []
        for idx, item in enumerate(data.get("items") or [], start=1):
            url = item.get("link", "")
            results.append(
                SearchResult(
                    rank=idx,
                    title=strip_html(item.get("title")) or url,
                    url=url,
                    snippet=strip_html(item.get("description")),
                    source=source_from_url(url) or item.get("bloggername", ""),
                    engine=self.engine,
                    published_at=item.get("pubDate") or item.get("postdate"),
                )
            )
        return EngineResponse(
            engine=self.engine, results=results, meta={"naver_type": self.naver_type}
        )
