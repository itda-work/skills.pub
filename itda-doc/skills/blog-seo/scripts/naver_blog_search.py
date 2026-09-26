"""
네이버 블로그 검색 API 클라이언트

FR-002: 블로그 문서수 조회 (/v1/search/blog.json의 total 필드)
NFR-002: 배치 처리 (0.1s 딜레이), 캐시 (.itda-skills/blog-seo-cache.json, 1hr TTL)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from naver_searchad import MissingApiKeyError, RateLimitError

BASE_URL = "https://openapi.naver.com"
BLOG_SIGNUP_URL = "https://developers.naver.com/apps/#/register"
BATCH_DELAY = 0.1  # 배치 요청 간 딜레이 (초)
CACHE_TTL = 3600   # 캐시 유효 시간 (초, 1시간)
MAX_RETRIES = 3

# 이전 경로 (마이그레이션용)
_OLD_CACHE_PATH = os.path.join(".itda-skills", "blog-seo-cache.json")


def _default_cache_path() -> str:
    """환경에 따라 캐시 경로를 결정한다 (lazy 해석)."""
    from itda_path import resolve_cache_dir
    new_path = str(resolve_cache_dir("blog-seo") / "blog-seo-cache.json")
    # 이전 경로 마이그레이션
    if os.path.exists(_OLD_CACHE_PATH) and not os.path.exists(new_path):
        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            os.rename(_OLD_CACHE_PATH, new_path)
        except OSError:
            pass
    return new_path


DEFAULT_CACHE_PATH = _default_cache_path()


class NaverBlogSearchClient:
    """네이버 블로그 검색 API 클라이언트"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cache_path: str | None = None,
    ) -> None:
        if not client_id:
            raise MissingApiKeyError(
                f"NAVER_CLIENT_ID가 설정되지 않았습니다. "
                f"발급 URL: {BLOG_SIGNUP_URL}"
            )
        if not client_secret:
            raise MissingApiKeyError(
                f"NAVER_CLIENT_SECRET이 설정되지 않았습니다. "
                f"발급 URL: {BLOG_SIGNUP_URL}"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self._cache: dict[str, dict] = {}
        self._load_cache()

    @classmethod
    def from_env(cls) -> "NaverBlogSearchClient":
        """환경변수로 클라이언트 생성 (CLI > environ > .env, SPEC-ENV-ERROR-001)."""
        from _env_setup import get_naver_client_id, get_naver_client_secret
        client_id = get_naver_client_id()
        client_secret = get_naver_client_secret()
        return cls(client_id=client_id, client_secret=client_secret)

    def _load_cache(self) -> None:
        """캐시 파일 로드"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self) -> None:
        """캐시 파일 저장"""
        cache_dir = os.path.dirname(self.cache_path)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _get_from_cache(self, keyword: str) -> int | None:
        """캐시에서 문서수 조회 (만료 확인 포함)"""
        entry = self._cache.get(keyword)
        if entry is None:
            return None
        if time.time() > entry.get("expires_at", 0):
            return None  # 만료됨
        return entry.get("doc_count")

    def _set_cache(self, keyword: str, doc_count: int) -> None:
        """캐시에 문서수 저장"""
        self._cache[keyword] = {
            "doc_count": doc_count,
            "expires_at": time.time() + CACHE_TTL,
        }
        self._save_cache()

    def _fetch_doc_count(self, keyword: str) -> int:
        """API에서 문서수 조회 (지수 백오프 재시도)"""
        params = urllib.parse.urlencode({
            "query": keyword,
            "display": 1,
            "start": 1,
            "sort": "sim",
        })
        url = f"{BASE_URL}/v1/search/blog.json?{params}"
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", self.client_id)
        req.add_header("X-Naver-Client-Secret", self.client_secret)

        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return int(data.get("total", 0))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = 2 ** attempt  # 1, 2, 4초
                        time.sleep(wait_time)
                        continue
                    raise RateLimitError(
                        f"네이버 블로그 검색 API 요청 한도 초과. {MAX_RETRIES}회 재시도 후 실패."
                    )
                raise
        raise RateLimitError("최대 재시도 횟수 초과")

    def get_doc_count(self, keyword: str) -> int:
        """키워드의 블로그 문서수 조회 (캐시 우선)"""
        cached = self._get_from_cache(keyword)
        if cached is not None:
            return cached

        doc_count = self._fetch_doc_count(keyword)
        self._set_cache(keyword, doc_count)
        return doc_count

    def batch_get_doc_counts(
        self,
        keywords: list[str],
        top_n: int = 50,
    ) -> dict[str, int]:
        """여러 키워드의 블로그 문서수 배치 조회

        Args:
            keywords: 키워드 목록
            top_n: 최대 처리 키워드 수 (기본값 50)

        Returns:
            {keyword: doc_count} 딕셔너리
        """
        results: dict[str, int] = {}
        target = keywords[:top_n]

        for i, keyword in enumerate(target):
            if i > 0:
                time.sleep(BATCH_DELAY)
            results[keyword] = self.get_doc_count(keyword)

        return results
