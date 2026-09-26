"""Perplexity Sonar 클라이언트 — 요약 답변(answer) + 인용(citations).

POST https://api.perplexity.ai/chat/completions (헤더 Authorization: Bearer).
응답: {"choices":[{"message":{"content"}}], "citations":[url...], "search_results"?:[{title,url,date}]}
raw 결과 목록과 형태가 다르므로 answer 는 top-level, 인용은 results 로 매핑한다(§3.3).
"""
from __future__ import annotations

from search_env import get_perplexity_key
from search_http import request_json
from search_results import EngineResponse, SearchResult, source_from_url

API_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar"
TIMEOUT = 30


class PerplexityClient:
    engine = "perplexity"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_env(cls, model: str = DEFAULT_MODEL) -> "PerplexityClient":
        return cls(get_perplexity_key(), model)

    def search(self, query: str, count: int = 5) -> EngineResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
        }
        data = request_json(
            API_URL,
            method="POST",
            headers=headers,
            json_body=body,
            engine=self.engine,
            timeout=TIMEOUT,
            retries=1,
        )

        choices = data.get("choices") or []
        answer = ""
        if choices:
            answer = (choices[0].get("message") or {}).get("content") or ""

        results: list[SearchResult] = []
        search_results = data.get("search_results")
        if isinstance(search_results, list) and search_results:
            for idx, item in enumerate(search_results[:count], start=1):
                url = item.get("url", "") if isinstance(item, dict) else ""
                if not url:
                    continue
                results.append(
                    SearchResult(
                        rank=idx,
                        title=(item.get("title") if isinstance(item, dict) else None)
                        or source_from_url(url)
                        or url,
                        url=url,
                        source=source_from_url(url),
                        engine=self.engine,
                        published_at=item.get("date") if isinstance(item, dict) else None,
                    )
                )
        else:
            for idx, url in enumerate((data.get("citations") or [])[:count], start=1):
                if not isinstance(url, str) or not url:
                    continue
                results.append(
                    SearchResult(
                        rank=idx,
                        title=source_from_url(url) or url,
                        url=url,
                        source=source_from_url(url),
                        engine=self.engine,
                    )
                )

        return EngineResponse(
            engine=self.engine,
            results=results,
            answer=answer or None,
            meta={"model": self.model},
        )
