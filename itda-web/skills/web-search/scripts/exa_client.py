"""Exa 검색 클라이언트 — 임베딩 기반 시맨틱 raw 결과(옵션 엔진).

POST https://api.exa.ai/search (헤더 x-api-key).
응답: {"results": [{"title","url","score","publishedDate"?,"highlights"?,"text"?}]}
"""
from __future__ import annotations

from search_env import get_exa_key
from search_http import request_json
from search_results import EngineResponse, SearchResult, source_from_url, strip_html

API_URL = "https://api.exa.ai/search"
MAX_RESULTS = 20


class ExaClient:
    engine = "exa"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "ExaClient":
        return cls(get_exa_key())

    def search(self, query: str, count: int = 5) -> EngineResponse:
        headers = {"x-api-key": self.api_key}
        body = {
            "query": query,
            "numResults": max(1, min(count, MAX_RESULTS)),
            "type": "auto",
            "contents": {
                "highlights": {"numSentences": 3, "highlightsPerUrl": 1},
                "text": {"maxCharacters": 500},
            },
        }
        data = request_json(
            API_URL, method="POST", headers=headers, json_body=body, engine=self.engine
        )
        results: list[SearchResult] = []
        for idx, item in enumerate(data.get("results") or [], start=1):
            url = item.get("url", "")
            highlights = item.get("highlights") or []
            snippet = strip_html(" ".join(highlights)) or strip_html(
                (item.get("text") or "")[:500]
            )
            results.append(
                SearchResult(
                    rank=idx,
                    title=strip_html(item.get("title")) or url,
                    url=url,
                    snippet=snippet,
                    source=source_from_url(url),
                    engine=self.engine,
                    score=item.get("score"),
                    published_at=item.get("publishedDate"),
                )
            )
        return EngineResponse(engine=self.engine, results=results, meta={"type": "auto"})
