"""naver_adapter.py - 네이버 블로그 어댑터 인터페이스 및 구현.

REQ-BLOGREADER-007: BlogAdapter ABC 정의 및 NaverBlogAdapter 구현.

Stage 1: 인터페이스 + 빈 스켈레톤
Stage 2: list_posts, get_post 구현 (완료)
Stage 3: get_comments 구현 (cbox JSONP API, 실측 파라미터) (완료)
Stage 4: search 구현 (PostSearchList.naver)
Stage 5: throttle 구현 (SPEC R-3, REQ-009.1 — 연속 요청 사이 최소 지연)

# 실측 2026-05-15 (v0.4.1):
# cbox 정확 파라미터 확보 — pool=blogid, objectId={blogNo}_201_{logNo},
# groupId={blogNo}, ticket=blog. 정적 subprocess 페치로 댓글 트리 완전 동작.
"""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import quote as _url_quote

import web_reader_client
from comment_parser import build_comment_tree, filter_comments_by_author, strip_jsonp_callback
from errors import AntiBotBlockError, BlogNotFoundError, BlogReaderError, EmptyResultError
from post_list_parser import (
    parse_post_list_json,
    parse_post_search_html,
)
from post_parser import parse_post_html
from section_search_parser import parse_section_search_json
from tag_parser import parse_tag_list_json
from url_normalize import normalize_naver_blog_url

# @MX:NOTE: [AUTO] BlogAdapter — 플랫폼 확장 진입점 (REQ-007.3)
# 향후 TistoryAdapter, VelogAdapter, BrunchAdapter가 이 인터페이스를 준수해야 한다.


def _now() -> datetime:
    """현재 UTC 시각을 반환한다. 테스트에서 patch 가능."""
    return datetime.now(tz=timezone.utc)


# 라이브 실측 2026-05-15: SPA HTML 스크래핑 폐기 → JSON API 채택
# REQ-002.1: 실제 엔드포인트
_POST_LIST_API_TEMPLATE = (
    "https://m.blog.naver.com/api/blogs/{blog_id}/post-list"
    "?categoryNo={category_no}&itemCount=30&page={page}"
)
_POST_LIST_REFERER_TEMPLATE = "https://m.blog.naver.com/{blog_id}"

# 하위 호환: 기존 HTML 엔드포인트 (현재 미사용 — JSON API로 대체됨)
_POST_LIST_URL_TEMPLATE = (
    "https://m.blog.naver.com/PostList.naver?blogId={blog_id}&currentPage={page}"
)

# REQ-005.1: 블로그 내 검색 전용 엔드포인트
# 실측 2026-05-15: PostSearchList.naver — 레거시 테이블 HTML 응답
# 파라미터 대소문자 정확 준수: blogId, categoryNo, SearchText(S/T 대문자), orderBy, range, currentPage
_POST_SEARCH_PC_URL = "https://blog.naver.com/PostSearchList.naver"
_POST_SEARCH_REFERER_TEMPLATE = "https://blog.naver.com/{blog_id}"
_POST_SEARCH_DEFAULT_ORDER = "sim"  # 관련도순 (date 선택 가능)
_POST_SEARCH_DEFAULT_RANGE = "all"  # 전체 히스토리 검색

# 데스크탑 Chrome UA (search 경로 기본값 — 실측: 모바일 UA로도 동작하나 PC 페이지 권장)
_SEARCH_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# REQ-015 (#1334): 네이버 블로그 전역 검색 (섹션 검색) 엔드포인트
# 실측 2026-07-30: 무자격(쿠키·로그인 없음) UA+Referer 만으로 JSON 응답.
_SECTION_SEARCH_URL = "https://section.blog.naver.com/ajax/SearchList.naver"
_SECTION_SEARCH_REFERER = "https://section.blog.naver.com/Search/Post.naver"
_SECTION_SEARCH_PAGE_SIZE = 20          # 실측 동작 확인 페이지 크기
_SECTION_SEARCH_MAX_PAGE = 50           # totalCount 상한 1000 관측 → 20×50
_SECTION_SEARCH_ORDER_MAP = {
    "sim": "sim",           # 관련도순
    "date": "recentdate",   # 최신순 (실측 파라미터명: recentdate)
}

# REQ-004.1: cbox 댓글 JSONP API 엔드포인트
# 실측 2026-05-15: pool=blogid, objectId={blogNo}_201_{logNo}, groupId={blogNo}
_CBOX_API_URL = (
    "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
)
_CBOX_DEFAULT_PAGE_SIZE = 100
_CBOX_MAX_PAGE = 20

# REQ-003.x: 태그 API 엔드포인트 (실측 2026-05-18, v0.9.3)
# 태그는 본문 HTML에 없고 이 API로만 제공된다 (cbox 댓글과 동형).
_TAG_API_URL = "https://blog.naver.com/BlogTagListInfo.naver"

# 실측 확인된 cbox 고정 상수
_CBOX_TICKET = "blog"
_CBOX_TEMPLATE_ID = "default"
_CBOX_POOL = "blogid"
# 네이버 블로그 objectId 중간 구분자 (고정값)
_CBOX_OBJECT_ID_SEP = "_201_"

# blogNo 추출 정규식: HTML 내 var blogNo = '56598388'; 또는 JSON "blogNo":56598388
_RE_BLOGNO_VAR = re.compile(r"""var\s+blogNo\s*=\s*['"](\d+)['"]""")
_RE_BLOGNO_JSON = re.compile(r"""["']?blogNo["']?\s*:\s*(\d+)""")

# ISS-d0e3e9ba: list_posts / search 루프 상한 — 무한 페치 방지
# has_next가 영구 True로 반환되는 파서 미스매치 상황에서도 종료를 보장한다.
_POST_LIST_MAX_PAGE = 100
_POST_SEARCH_MAX_PAGE = 100

_DEFAULT_LIMIT = 20

# REQ-009.1 / SPEC R-3: 연속 요청 사이 최소 지연 상수
# 사용자가 --throttle로 지정하되 _THROTTLE_FLOOR 밑으로 내릴 수 없다.
# interval <= 0 은 blog_reader.py에서 _exit_arg_error(exit 2)로 처리.
_DEFAULT_THROTTLE: float = 0.5   # SPEC R-3 기본값 (초)
_THROTTLE_FLOOR: float = 0.3     # 절대 하한선 (초)


class BlogAdapter(ABC):
    """블로그 플랫폼 어댑터 추상 기반 클래스.

    REQ-007.1: 최소 5개 메서드(list_posts, get_post, get_comments, search, read_post)를 정의한다.
    각 플랫폼 어댑터(NaverBlogAdapter 등)는 이 클래스를 상속하고 모든 메서드를 구현해야 한다.
    """

    @abstractmethod
    def list_posts(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """포스트 목록을 조회한다.

        Args:
            filters: 필터 조건 딕셔너리.
                - blog_id: 블로그 ID (필수)
                - days: 최근 N일 (선택)
                - limit: 최대 반환 수 (선택, 기본 20)
                - category: 카테고리명 또는 categoryNo (선택)

        Returns:
            포스트 정보 딕셔너리 리스트.
            각 항목은 최소 logNo, title, url, published_at, category, summary 포함.
        """

    @abstractmethod
    def get_post(self, url: str, *, body_format: str = "markdown") -> dict[str, Any]:
        """포스트 본문을 조회한다.

        Args:
            url: 모바일 포스트 URL (자동 정규화됨).
            body_format: "markdown"(기본) 또는 "html" (REQ-003.1/.2).

        Returns:
            포스트 정보 딕셔너리.
            최소 blog_id, log_no, title, author, body, images 포함.
            body 키에 body_format에 따라 마크다운 또는 HTML 본문 반환.
        """

    @abstractmethod
    def get_comments(self, url: str, options: dict[str, Any]) -> dict[str, Any]:
        """댓글/대댓글 트리를 조회한다.

        Args:
            url: 모바일 포스트 URL.
            options: 옵션 딕셔너리.
                - max_depth: 최대 댓글 깊이 (None이면 무제한)
                - max_comments: 최대 댓글 수 (None이면 무제한)

        Returns:
            댓글 트리 딕셔너리. comments 키에 루트 노드 리스트 포함.
            각 노드는 comment_id, parent_id, author, body, created_at, depth, children 포함.
        """

    @abstractmethod
    def search(self, query: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        """블로그 내 검색을 수행한다.

        Args:
            query: 검색 키워드.
            options: 옵션 딕셔너리.
                - blog_id: 검색 대상 블로그 ID (필수)
                - limit: 최대 반환 수 (선택, 기본 20)

        Returns:
            포스트 정보 딕셔너리 리스트 (REQ-002.5와 동일한 필드 셋).
        """

    @abstractmethod
    def read_post(
        self, url: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """포스트 본문과 댓글 트리를 한 번에 조회한다 (REQ-014).

        Args:
            url: 포스트 URL (PC 또는 모바일).
            options: 옵션 딕셔너리 (모두 선택).
                - max_depth: 댓글 최대 깊이 (REQ-014.3)
                - max_comments: 최대 댓글 수 (REQ-014.3)
                - filter_author: 댓글 작성자 필터 (REQ-014.3)
                - body_format: "markdown"(기본) 또는 "html" (REQ-003.1/.2)

        Returns:
            {"article": {...}, "comments": {...}} (REQ-014.2).
            댓글 페치 실패 시 comments에 error 필드 포함 (REQ-014.6).
        """


def _extract_blog_id_log_no(mobile_url: str) -> tuple[str, str]:
    """모바일 URL에서 blog_id와 log_no를 추출한다.

    m.blog.naver.com/{blog_id}/{log_no} 형식을 파싱한다.

    Args:
        mobile_url: 정규화된 모바일 포스트 URL.

    Returns:
        (blog_id, log_no) 튜플.

    Raises:
        ValueError: URL에서 blog_id 또는 log_no를 추출할 수 없을 때.
    """
    from urllib.parse import urlparse
    parsed = urlparse(mobile_url)
    # 경로: /{blog_id}/{log_no}
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(
            f"URL에서 blog_id/log_no를 추출할 수 없습니다: {mobile_url!r}"
        )
    return parts[0], parts[1]


def _parse_published_at(pub_str: str) -> datetime | None:
    """ISO 8601 문자열을 datetime으로 변환한다. 실패 시 None 반환."""
    if not pub_str:
        return None
    try:
        # +09:00 형식 처리
        pub_str = pub_str.replace("Z", "+00:00")
        return datetime.fromisoformat(pub_str)
    except (ValueError, TypeError):
        return None


def _is_within_days(pub_str: str, days: int, now: datetime) -> bool:
    """published_at 문자열이 now 기준 days일 이내인지 확인한다.

    ISS-e6b751e9: timedelta(days=N) 정확 비교로 ~1일 윈도우 오차 제거.
    tz-aware 일관성 보장.
    """
    pub_dt = _parse_published_at(pub_str)
    if pub_dt is None:
        return False
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    # ISS-e6b751e9: .days 속성이 아닌 timedelta 직접 비교로 시각 오차 제거
    cutoff = now - timedelta(days=days)
    return pub_dt >= cutoff


def _matches_category(post_category: str, filter_category: str) -> bool:
    """카테고리 부분 일치 확인 (대소문자 무시). REQ-002.3."""
    return filter_category.lower() in post_category.lower()


# @MX:ANCHOR: [AUTO] NaverBlogAdapter.list_posts — 포스트 목록 단일 진입점
# @MX:REASON: 페이지네이션, days/limit/category 필터 로직의 공개 API (fan_in >= 3)

class NaverBlogAdapter(BlogAdapter):
    """네이버 블로그 어댑터 구현체.

    REQ-007.2: 본 SPEC의 모든 EARS 요구사항을 만족해야 한다.

    Stage 2: list_posts, get_post 구현 (완료)
    Stage 3: get_comments 구현 (cbox JSONP API) — 미구현
    Stage 4: search 구현 (PostSearchList.naver) — 미구현
    """

    def __init__(self, web_reader_client: Any = None, options: dict[str, Any] | None = None) -> None:  # noqa: F811
        """NaverBlogAdapter 초기화.

        Args:
            web_reader_client: HTTP 페치 클라이언트 모듈 (테스트 주입용).
                               None이면 기본 web_reader_client 모듈 사용.
            options: 공통 옵션 딕셔너리 (선택).
                - user_agent: HTTP User-Agent 문자열
                - timeout: HTTP 타임아웃 (초)
                - throttle: 연속 요청 사이 최소 지연 (초, 기본 0.5, 하한 0.3)
        """
        import web_reader_client as _wrc
        self._client = web_reader_client if web_reader_client is not None else _wrc
        # ISS-e3551b8f: --user-agent / --timeout 공통 옵션 보관
        self._options: dict[str, Any] = options or {}
        # SPEC R-3: 연속 요청 사이 최소 지연 추적
        # _last_request_ts: 마지막 fetch_html 호출 시각 (time.monotonic 기준)
        # None이면 첫 요청 — 즉시 실행 (sleep 없음)
        self._last_request_ts: float | None = None
        # throttle 값은 options에서 가져오되 FLOOR 하한 적용 (CLI에서 이미 검증됨)
        raw_throttle: float = float(self._options.get("throttle", _DEFAULT_THROTTLE))
        self._throttle: float = max(raw_throttle, _THROTTLE_FLOOR)

    def _build_fetch_kwargs(self, extra_headers: "dict[str, str] | None" = None) -> dict[str, Any]:
        """fetch_html 호출용 kwargs를 단일 헬퍼로 조립한다.

        ISS-e3551b8f: 5개 호출부에서 if 블록을 반복하던 옵션 조립을 단일화.
        추가 헤더(extra_headers)가 있으면 "headers" 키에 병합한다.
        """
        kwargs: dict[str, Any] = {}
        if "user_agent" in self._options:
            kwargs["user_agent"] = self._options["user_agent"]
        if "timeout" in self._options:
            kwargs["timeout"] = self._options["timeout"]
        if extra_headers:
            kwargs["headers"] = extra_headers
        return kwargs

    # @MX:WARN: [AUTO] _throttle_gate — 전역 상태(monotonic clock) 변이, 모든 fetch 경유
    # @MX:REASON: SPEC R-3 필수 게이트. 우회 시 rate-limit/자가차단 위험(R-9). side-effect 있는 메서드.
    def _throttle_gate(self) -> None:
        """다음 fetch_html 호출 전에 최소 간격을 보장한다.

        SPEC R-3 / REQ-009.1: 연속된 두 HTTP 요청 사이 최소 self._throttle 초 이상.

        동작:
        - 첫 요청: _last_request_ts is None → 즉시 반환 (sleep 없음)
        - 연속 요청: 경과 시간 < throttle이면 차액만큼 sleep
        - 호출 후 _last_request_ts를 현재 시각으로 갱신

        이 메서드는 fetch_html 호출 직전 모든 경로에서 반드시 경유해야 한다.
        메서드 경계(list→get_comments 등)에서도 자동으로 간격이 적용된다.
        """
        now = time.monotonic()
        if self._last_request_ts is not None:
            elapsed = now - self._last_request_ts
            remaining = self._throttle - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_ts = time.monotonic()

    def list_posts(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """포스트 목록 조회.

        REQ-002.1: --days N 필터
        REQ-002.2: --limit N 필터 (기본 20)
        REQ-002.3: --category {name} 필터 (부분 일치, 대소문자 무시)
        REQ-002.4: 페이지네이션 자동 진행
        REQ-002.6: days + limit AND 조건

        Args:
            filters: {blog_id, days?, limit?, category?}

        Returns:
            포스트 딕셔너리 리스트.

        Raises:
            EmptyResultError: 결과가 0건일 때.
        """
        from urllib.parse import quote as _quote

        blog_id: str = filters["blog_id"]
        days: int | None = filters.get("days")
        limit: int = filters.get("limit", _DEFAULT_LIMIT)
        category_filter: str | None = filters.get("category")

        now = _now()
        results: list[dict[str, Any]] = []
        # ISS-d0e3e9ba: 상한 도달로 종료 추적 (무한 페치 방지)
        stop_fetching = False
        prev_count = 0  # 신규 항목 0건 연속 감지용

        # 카테고리 번호 결정: category_filter가 숫자면 categoryNo로 직접 사용,
        # 문자열이면 categoryNo=0 (전체)로 가져온 뒤 후처리 필터링
        category_no = 0
        if category_filter is not None and str(category_filter).isdigit():
            category_no = int(category_filter)

        for page in range(1, _POST_LIST_MAX_PAGE + 1):
            if stop_fetching:
                break

            # 라이브 실측 2026-05-15: JSON API 사용
            # ISS-blogidenc: blog_id를 URL-인코딩해서 파라미터 인젝션 방지
            encoded_blog_id = _quote(blog_id, safe="")
            url = _POST_LIST_API_TEMPLATE.format(
                blog_id=encoded_blog_id,
                category_no=category_no,
                page=page,
            )
            referer = _POST_LIST_REFERER_TEMPLATE.format(blog_id=encoded_blog_id)
            self._throttle_gate()
            raw = self._client.fetch_html(
                url,
                **self._build_fetch_kwargs({"Referer": referer}),
            )
            parsed = parse_post_list_json(raw, blog_id)
            posts_on_page = parsed["posts"]

            count_before = len(results)
            raw_count = len(posts_on_page)  # ISS-catfilter: 필터 적용 전 raw parse 수
            for post in posts_on_page:
                # days 필터 확인 (REQ-002.1)
                if days is not None:
                    if not _is_within_days(post["published_at"], days, now):
                        # 포스트는 날짜 내림차순 — days 범위 벗어나면 이후도 불필요
                        stop_fetching = True
                        break

                # category 필터 확인 (REQ-002.3)
                if category_filter is not None:
                    if not _matches_category(post["category"], category_filter):
                        continue

                results.append(post)

                # limit 조건 만족 시 즉시 중단 (REQ-002.2, REQ-002.6)
                if len(results) >= limit:
                    stop_fetching = True
                    break

            if stop_fetching:
                break

            # JSON API 종료 판정:
            # 1. items가 비어있으면 마지막 페이지
            # 2. 누적 수 >= totalCount이면 완전 수집 완료
            # 3. raw_count > 0 이면 category 필터로 0건이어도 계속 진행 (ISS-catfilter)
            total_count = parsed.get("total_count", 0)
            if raw_count == 0:
                break

            if total_count > 0 and len(results) >= total_count:
                break

        if not results:
            raise EmptyResultError(
                f"블로그 {blog_id!r}에서 조건에 맞는 포스트를 찾지 못했습니다."
            )

        return results

    def get_post(
        self,
        url: str,
        *,
        body_format: str = "markdown",
        strip_image_urls: bool = False,
    ) -> dict[str, Any]:
        """포스트 본문 조회.

        REQ-001.1~1.2: PC URL을 모바일 URL로 자동 정규화.
        REQ-003: 포스트 본문 구조화 반환.
        REQ-003.1: body 단일 키 반환 (v0.7.0 BREAKING).
        REQ-003.2: body_format="markdown"(기본) → SmartEditor 마크다운.
        REQ-003.4: body_format="html" → 원본 HTML 스니펫.

        Args:
            url: 포스트 URL (PC 또는 모바일).
            body_format: "markdown"(기본) 또는 "html".
            strip_image_urls: True면 본문 이미지 URL을 플레이스홀더로 치환하고
                              images 배열을 비운다 (REQ-003.9, v0.11.0).

        Returns:
            포스트 정보 딕셔너리. body 단일 키 포함.
        """
        mobile_url = normalize_naver_blog_url(url)
        self._throttle_gate()
        html = self._client.fetch_html(mobile_url, **self._build_fetch_kwargs())
        result = parse_post_html(
            html,
            mobile_url,
            body_format=body_format,
            strip_image_urls=strip_image_urls,
        )
        # REQ-003.x (v0.9.3): 태그는 본문 HTML에 없으므로 별도 API로 보강.
        # post_parser의 parser.tags는 죽은 경로(빈 리스트)이며 여기서 덮어쓴다.
        blog_id, log_no = _extract_blog_id_log_no(mobile_url)
        result["tags"] = self._fetch_post_tags(blog_id, log_no)
        return result

    def _fetch_post_tags(self, blog_id: str, log_no: str) -> list[str]:
        """BlogTagListInfo.naver API로 포스트 태그를 조회한다 (REQ-003.x).

        실측 2026-05-18 (v0.9.3): 태그는 본문 HTML(모바일/PC)에 없고
        이 API로만 제공된다 (댓글 cbox와 동형). web_reader_client 경유
        (REQ-006: 직접 HTTP import 0 유지), throttle 게이트 적용.

        실패 시 빈 리스트 반환 (graceful) — 태그는 부가 정보이며
        실패가 본문 조회를 깨면 안 된다.

        Args:
            blog_id: 블로그 문자열 ID.
            log_no: 포스트 번호.

        Returns:
            태그 리스트. 실패·빈 응답 시 빈 리스트.
        """
        tag_url = (
            f"{_TAG_API_URL}"
            f"?blogId={_url_quote(blog_id, safe='')}"
            f"&logNo={_url_quote(log_no, safe='')}"
        )
        try:
            self._throttle_gate()
            raw = self._client.fetch_html(
                tag_url, **self._build_fetch_kwargs()
            )
        except Exception:  # noqa: BLE001
            # 태그 API 실패는 비치명 — 본문 우선 정책
            return []
        return parse_tag_list_json(raw, log_no)

    def _extract_blog_no(self, mobile_url: str, blog_id: str, log_no: str) -> str:
        """포스트 HTML에서 blogNo(숫자 ID)를 추출한다.

        실측 2026-05-15: HTML 내 `var blogNo = '56598388';` 또는
        JSON 필드 `"blogNo":56598388` 패턴 중 하나로 추출.

        Args:
            mobile_url: 이미 페치된 포스트의 모바일 URL.
            blog_id: URL에서 파싱한 블로그 문자열 ID (예: "astroyuji").
            log_no: URL에서 파싱한 로그 번호.

        Returns:
            blogNo 숫자 문자열 (예: "56598388").

        Raises:
            BlogReaderError: 페치/파싱 실패 시.
        """
        referer = f"https://m.blog.naver.com/{_url_quote(blog_id, safe='')}/{log_no}"
        try:
            self._throttle_gate()
            html = self._client.fetch_html(
                mobile_url,
                **self._build_fetch_kwargs({"Referer": referer}),
            )
        except BlogReaderError:
            raise
        except Exception as exc:
            raise BlogReaderError(f"blogNo 추출용 페이지 페치 실패: {exc}") from exc

        m = _RE_BLOGNO_VAR.search(html)
        if m:
            return m.group(1)
        m = _RE_BLOGNO_JSON.search(html)
        if m:
            return m.group(1)
        raise BlogReaderError(
            f"포스트 HTML에서 blogNo를 찾을 수 없습니다 (url={mobile_url!r})"
        )

    # @MX:ANCHOR: [AUTO] NaverBlogAdapter.get_comments — cbox 댓글 단일 진입점
    # @MX:REASON: CLI comments/read 서브커맨드, read_post에서 호출 (fan_in >= 3)
    def get_comments(self, url: str, options: dict[str, Any]) -> dict[str, Any]:
        """댓글 트리 조회.

        실측 2026-05-15 (v0.4.1): 실제 cbox JSONP API 호출 복원.
        pool=blogid, objectId={blogNo}_201_{logNo}, groupId={blogNo} 사용.

        Args:
            url: 모바일 포스트 URL (PC URL도 자동 정규화).
            options: {
                "max_depth": int|None,
                "max_comments": int|None,
                "filter_author": str|None,
            }

        Returns:
            {"comments": [...], "total_count": N, "truncated": bool}
            실패 시: {"comments": [], "total_count": 0, "truncated": False, "error": str}

        Raises:
            AntiBotBlockError: anti-bot 차단 감지 시.
            BlogNotFoundError: 비공개/삭제 포스트 접근 시.
        """
        max_depth: int | None = options.get("max_depth")
        max_comments: int | None = options.get("max_comments")
        filter_author: str | None = options.get("filter_author")

        mobile_url = normalize_naver_blog_url(url)
        blog_id, log_no = _extract_blog_id_log_no(mobile_url)

        # ISS-blogidenc: blog_id, log_no URL-인코딩
        encoded_blog_id = _url_quote(blog_id, safe="")
        encoded_log_no = _url_quote(log_no, safe="")

        # blogNo(숫자) 추출 — post HTML 1회 페치
        blog_no = self._extract_blog_no(mobile_url, blog_id, log_no)

        # objectId = "{blogNo}_201_{logNo}" (네이버 블로그 고정 형식)
        object_id = f"{blog_no}{_CBOX_OBJECT_ID_SEP}{log_no}"

        # cbox 페이지네이션: 모든 페이지 수집
        merged_list: list[dict[str, Any]] = []
        last_more_page = False

        for page in range(1, _CBOX_MAX_PAGE + 1):
            cbox_url = (
                f"{_CBOX_API_URL}"
                f"?ticket={_CBOX_TICKET}"
                f"&templateId={_CBOX_TEMPLATE_ID}"
                f"&pool={_CBOX_POOL}"
                f"&_callback=jsonp_cb"
                f"&lang=ko"
                f"&country="
                f"&objectId={_url_quote(object_id, safe='')}"
                f"&groupId={_url_quote(blog_no, safe='')}"
                f"&pageSize={_CBOX_DEFAULT_PAGE_SIZE}"
                f"&indexSize=10"
                f"&page={page}"
                f"&listType=OBJECT"
                f"&pageType=more"
                f"&initialize=true"
                f"&followSize=5"
                f"&useAltSort=true"
                f"&replyPageSize=10"
                f"&showReply=true"
            )
            referer = f"https://m.blog.naver.com/{encoded_blog_id}/{encoded_log_no}"

            self._throttle_gate()
            raw = self._client.fetch_html(
                cbox_url,
                **self._build_fetch_kwargs({"Referer": referer}),
            )

            try:
                payload = strip_jsonp_callback(raw)
            except ValueError as exc:
                # JSONP 파싱 실패 — graceful
                return {
                    "comments": [],
                    "total_count": 0,
                    "truncated": False,
                    "error": f"cbox JSONP 파싱 실패: {exc}",
                }

            # success 확인
            if not payload.get("success", False):
                return {
                    "comments": [],
                    "total_count": 0,
                    "truncated": False,
                    "error": (
                        f"cbox API 오류: code={payload.get('code')}, "
                        f"message={payload.get('message')}"
                    ),
                }

            result = payload.get("result", {})
            comment_list: list[dict[str, Any]] = result.get("commentList") or []
            merged_list.extend(comment_list)

            # 페이지 모델 기반 종료 판정
            page_model = result.get("pageModel", {})
            next_page = page_model.get("nextPage", 0)
            has_more = bool(next_page and next_page > page)
            last_more_page = has_more

            if not has_more:
                break

            if not comment_list:
                break

        # 단일 merged payload로 트리 구성
        merged_payload: dict[str, Any] = {
            "result": {"commentList": merged_list, "morePage": last_more_page}
        }

        tree = build_comment_tree(
            merged_payload,
            max_depth=max_depth,
            max_comments=max_comments,
        )

        if filter_author:
            tree = filter_comments_by_author(tree, filter_author)

        return tree

    # @MX:ANCHOR: [AUTO] NaverBlogAdapter.read_post — 통합 조회 단일 진입점
    # @MX:REASON: get_post + get_comments 합성 공개 API, CLI read 서브커맨드가 직접 호출 (fan_in >= 3 예상)
    def read_post(
        self, url: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """포스트 본문과 댓글 트리를 한 번에 조회한다.

        REQ-014.1: get_post + get_comments 합성 조회.
        REQ-014.2: {"article": {...}, "comments": {...}} 반환.
        REQ-014.3: options의 max_depth/max_comments/filter_author → get_comments 전달.
        REQ-014.4: options의 body_format → get_post 전달.
        REQ-014.5: URL 정규화는 get_post 내부에서 처리.
        REQ-014.6: 댓글 일반 실패 → graceful, AntiBotBlockError/BlogNotFoundError → 재raise.

        Args:
            url: 포스트 URL (PC 또는 모바일).
            options: 옵션 딕셔너리 (선택).
                - max_depth: 댓글 최대 깊이
                - max_comments: 최대 댓글 수
                - filter_author: 댓글 작성자 필터
                - body_format: "markdown"(기본) 또는 "html" (REQ-003.1/.2)
                - strip_image_urls: 이미지 URL 제거 (REQ-003.9, v0.11.0)

        Returns:
            {"article": {...}, "comments": {...}}
        """
        if options is None:
            options = {}

        # REQ-014.4: body_format 분리 (REQ-003.1/.2)
        body_format: str = options.get("body_format", "markdown")
        # REQ-003.9 (v0.11.0): 이미지 URL 제거 옵션 전달
        strip_image_urls: bool = bool(options.get("strip_image_urls", False))

        # REQ-014.3: 댓글 전달 옵션 구성
        comments_options: dict[str, Any] = {}
        if "max_depth" in options:
            comments_options["max_depth"] = options["max_depth"]
        if "max_comments" in options:
            comments_options["max_comments"] = options["max_comments"]
        if "filter_author" in options:
            comments_options["filter_author"] = options["filter_author"]

        # REQ-014.1(a): 본문 조회 — BlogNotFoundError 등은 그대로 전파
        article = self.get_post(
            url, body_format=body_format, strip_image_urls=strip_image_urls
        )

        # REQ-014.1(b): 댓글 조회 — REQ-014.6 graceful 처리
        # v1: get_comments가 unsupported 딕셔너리를 반환하므로 예외는 드물다.
        try:
            comments = self.get_comments(url, comments_options)
        except (AntiBotBlockError, BlogNotFoundError):
            # 본문 우선 정책 예외: anti-bot(exit 4), 비공개/삭제(exit 6) 즉시 재raise
            raise
        except Exception as exc:  # noqa: BLE001
            # 비치명 파싱 예외 graceful 처리
            if isinstance(exc, (AntiBotBlockError, BlogNotFoundError)):
                raise
            comments = {
                "comments": [],
                "total_count": 0,
                "truncated": False,
                "error": f"댓글 페치 실패: {exc}",
            }

        # REQ-014.2: 최상위 두 키
        return {"article": article, "comments": comments}

    # @MX:ANCHOR: [AUTO] NaverBlogAdapter.search — 블로그 내 검색 단일 진입점
    # @MX:REASON: CLI search 서브커맨드가 직접 호출, 페이지네이션/limit 로직 집중 (fan_in >= 3)
    def search(self, query: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        """블로그 내 검색.

        실측 2026-05-15: PostSearchList.naver 전용 엔드포인트 사용.
        REQ-005.1: 실 검색 엔드포인트(PostSearchList.naver, SearchText 대문자) 사용.
        REQ-005.2: REQ-002.5와 동일한 필드 셋 반환 (logNo, title, url, published_at,
                   category, summary).
        REQ-005.3: --limit N 최대 N개 반환 (기본 20).
        REQ-005.4: 페이지네이션 자동 진행 (currentPage 증가), limit 도달 또는 결과
                   0건 시 중단. 상한 _POST_SEARCH_MAX_PAGE(100) 유지.
        REQ-005.5: 네이버 반환 순서 그대로 유지 (재정렬 금지).

        엔드포인트:
            GET https://blog.naver.com/PostSearchList.naver
                ?blogId={id}&categoryNo=0&SearchText={query}(대문자 S,T)
                &orderBy=sim&range=all&currentPage={N}
            Referer: https://blog.naver.com/{blogId}
            UA: 데스크탑 Chrome (options.user_agent로 override 가능)

        Args:
            query: 검색 키워드 (URL 인코딩 필수, 한글 포함).
            options: {
                "blog_id": 검색 대상 블로그 ID (필수),
                "limit": 최대 반환 수 (선택, 기본 20),
                "order_by": 정렬 (선택, 기본 "sim" — "date" 가능),
            }

        Returns:
            포스트 딕셔너리 리스트 (REQ-002.5와 동일한 필드 셋).

        Raises:
            EmptyResultError: 검색 결과가 0건일 때.
        """
        from urllib.parse import quote as _quote

        blog_id: str = options["blog_id"]
        limit: int = options.get("limit", _DEFAULT_LIMIT)
        order_by: str = options.get("order_by", _POST_SEARCH_DEFAULT_ORDER)

        # ISS-blogidsearch: blog_id, query 모두 safe="" 인코딩 (인젝션 방지)
        encoded_blog_id = _quote(blog_id, safe="")
        encoded_query = _quote(query, safe="")  # 한글 포함 URL 인코딩

        results: list[dict[str, Any]] = []

        # search UA: 기본 데스크탑 Chrome (options.user_agent override 가능)
        search_ua = self._options.get("user_agent", _SEARCH_DEFAULT_UA)
        referer = _POST_SEARCH_REFERER_TEMPLATE.format(blog_id=blog_id)
        extra_headers = {"Referer": referer}

        # ISS-d0e3e9ba: for range로 상한 보장 (무한 루프 방지)
        for page in range(1, _POST_SEARCH_MAX_PAGE + 1):
            # 실측 2026-05-15: SearchText 파라미터는 대문자 S,T 정확 준수
            search_url = (
                f"{_POST_SEARCH_PC_URL}"
                f"?blogId={encoded_blog_id}"
                f"&categoryNo=0"
                f"&SearchText={encoded_query}"
                f"&orderBy={order_by}"
                f"&range={_POST_SEARCH_DEFAULT_RANGE}"
                f"&currentPage={page}"
            )

            # user_agent를 kwargs로 직접 전달 (search 전용 UA 우선)
            fetch_kwargs = dict(self._build_fetch_kwargs(extra_headers))
            fetch_kwargs["user_agent"] = search_ua

            self._throttle_gate()
            raw = self._client.fetch_html(search_url, **fetch_kwargs)
            parsed = parse_post_search_html(raw, blog_id)
            posts_on_page = parsed["posts"]

            # REQ-005.5: 네이버 반환 순서 유지 (재정렬 금지)
            for post in posts_on_page:
                results.append(post)
                # REQ-005.3: limit 도달 시 즉시 중단
                if len(results) >= limit:
                    break

            # limit 도달 후 루프 탈출
            if len(results) >= limit:
                break

            # 결과 0건 → 마지막 페이지
            if not posts_on_page:
                break

        if not results:
            raise EmptyResultError(
                f"블로그 {blog_id!r}에서 {query!r} 검색 결과가 없습니다."
            )

        return results

    # @MX:ANCHOR: [AUTO] NaverBlogAdapter.discover — 전역 검색 단일 진입점
    # @MX:REASON: CLI discover 서브커맨드가 직접 호출 (#1334), read 이어읽기의 발견 단계
    def discover(self, query: str, options: dict[str, Any]) -> dict[str, Any]:
        """네이버 블로그 전역 키워드 검색 (REQ-015, #1334).

        section.blog.naver.com 섹션 검색 ajax 로 네이버 블로그 전체에서
        키워드에 매칭되는 포스트의 **메타데이터만** 반환한다 (제목·요약·URL·
        blog_id·log_no). 본문은 read 서브커맨드로 이어읽는다.

        실측 2026-07-30: 무자격(쿠키·로그인 없음), UA + Referer 만으로 응답.
        차단 신호(blockedByBifrostShield)는 파서에서 AntiBotBlockError(exit 4)로
        표면화하며 우회하지 않는다.

        Args:
            query: 검색 키워드.
            options: {
                "limit": 최대 반환 수 (선택, 기본 20),
                "order_by": "sim"(관련도, 기본) | "date"(최신순),
            }

        Returns:
            {"posts": [...], "total_count": N}
            posts 항목: blog_id, log_no, title, url, published_at, summary,
                        blog_name, nickname.

        Raises:
            EmptyResultError: 검색 결과가 0건일 때 (exit 3).
            AntiBotBlockError: 차단 감지 시 (exit 4, 우회 없음).
            BlogStructureChangedError: 응답 구조 변경 시 (exit 1).
        """
        limit: int = options.get("limit", _DEFAULT_LIMIT)
        order_by: str = options.get("order_by", "sim")
        naver_order = _SECTION_SEARCH_ORDER_MAP.get(order_by, "sim")

        encoded_query = _url_quote(query, safe="")
        search_ua = self._options.get("user_agent", _SEARCH_DEFAULT_UA)

        posts: list[dict[str, Any]] = []
        total_count = 0

        for page in range(1, _SECTION_SEARCH_MAX_PAGE + 1):
            url = (
                f"{_SECTION_SEARCH_URL}"
                f"?countPerPage={_SECTION_SEARCH_PAGE_SIZE}"
                f"&currentPage={page}"
                f"&keyword={encoded_query}"
                f"&orderBy={naver_order}"
                f"&type=post"
            )
            fetch_kwargs = dict(
                self._build_fetch_kwargs({"Referer": _SECTION_SEARCH_REFERER})
            )
            fetch_kwargs["user_agent"] = search_ua

            self._throttle_gate()
            raw = self._client.fetch_html(url, **fetch_kwargs)
            parsed = parse_section_search_json(raw, query)
            page_posts = parsed["posts"]
            total_count = parsed["total_count"]

            for post in page_posts:
                posts.append(post)
                if len(posts) >= limit:
                    break

            if len(posts) >= limit:
                break
            # 결과 0건 또는 전체 수집 완료 → 종료
            if not page_posts:
                break
            if total_count > 0 and len(posts) >= total_count:
                break

        if not posts:
            raise EmptyResultError(
                f"네이버 블로그 전역에서 {query!r} 검색 결과가 없습니다."
            )

        return {"posts": posts, "total_count": total_count}
