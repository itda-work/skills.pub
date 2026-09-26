"""url_normalize.py - 네이버 블로그 URL 정규화.

REQ-BLOGREADER-001: 모든 입력 URL을 m.blog.naver.com 모바일 형식으로 변환한다.

- REQ-001.1: blog.naver.com/{id} → m.blog.naver.com/{id}
- REQ-001.2: blog.naver.com/{id}/{logNo} → m.blog.naver.com/{id}/{logNo}
- REQ-001.3: m.blog.naver.com/... → 그대로 유지
- REQ-001.4: blogId (또는 blogId + logNo) 조립
- REQ-001.5: PC PostView/PostList 변형 → 모바일 변환
R-7: 한글 blogId 등 특수문자 URL 인코딩
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse, urlencode, parse_qs, quote

from errors import UnsupportedPlatformError

_MOBILE_HOST = "m.blog.naver.com"
_MOBILE_BASE = f"https://{_MOBILE_HOST}"

# PC 도메인 패턴 (blog.naver.com 계열)
_PC_HOST = "blog.naver.com"

# ISS-naverwild: 허용 호스트 화이트리스트 — *.naver.com 과신뢰 방지
_ALLOWED_NAVER_HOSTS = frozenset({
    "blog.naver.com",
    "m.blog.naver.com",
    "apis.naver.com",
})

# PC 전용 엔드포인트 경로 (REQ-001.5)
_PC_ONLY_PATHS = {
    "/PostView.naver",
    "/PostList.naver",
    "/PostSearchList.naver",
}


def _is_naver_domain(host: str) -> bool:
    """도메인이 *.naver.com인지 확인한다 (하위 호환용)."""
    return host == "naver.com" or host.endswith(".naver.com")


def _is_allowed_naver_host(host: str) -> bool:
    """ISS-naverwild: 허용된 네이버 호스트인지 화이트리스트로 정확 매칭한다."""
    return host in _ALLOWED_NAVER_HOSTS


def _encode_path_segment(segment: str) -> str:
    """URL 경로 세그먼트를 안전하게 인코딩한다 (R-7).

    이미 percent-encoded된 문자는 그대로 두고,
    ASCII 알파벳/숫자/하이픈/밑줄/점은 인코딩하지 않는다.
    """
    # quote는 safe=''로 하면 이미 인코딩된 것도 다시 인코딩하므로
    # safe를 설정해서 슬래시 등은 보존한다
    return quote(segment, safe="")


def normalize_naver_blog_url(input_url: str) -> str:
    """입력 URL을 m.blog.naver.com 모바일 형식으로 정규화한다.

    Args:
        input_url: 정규화할 URL 문자열.

    Returns:
        정규화된 모바일 URL 문자열.

    Raises:
        UnsupportedPlatformError: 도메인이 *.naver.com이 아닌 경우.
    """
    # 스킴이 없는 경우 https:// 추가 (간단 처리)
    if not input_url.startswith("http://") and not input_url.startswith("https://"):
        input_url = "https://" + input_url

    parsed = urlparse(input_url)
    host = parsed.netloc.lower()

    # REQ-007.4 + ISS-naverwild: 허용 호스트 화이트리스트 정확 매칭
    # 그 외 *.naver.com도 UnsupportedPlatformError (과신뢰 방지)
    if not _is_allowed_naver_host(host):
        raise UnsupportedPlatformError(
            f"지원하지 않는 플랫폼입니다: {host!r} — "
            f"blog.naver.com, m.blog.naver.com, apis.naver.com만 지원합니다."
        )

    # REQ-001.3: 이미 모바일 도메인이면 그대로 반환
    if host == _MOBILE_HOST:
        return input_url

    # REQ-001.5: PC 전용 엔드포인트 처리
    path = parsed.path
    if any(path.startswith(pc_path) for pc_path in _PC_ONLY_PATHS):
        return _convert_pc_endpoint_to_mobile(path, parsed.query)

    # REQ-001.1 / REQ-001.2: blog.naver.com → m.blog.naver.com 도메인 교체
    # 경로 그대로 유지하되 스킴을 https로 강제
    new_url = urlunparse((
        "https",
        _MOBILE_HOST,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return new_url


def _convert_pc_endpoint_to_mobile(path: str, query: str) -> str:
    """PC 전용 엔드포인트를 모바일 URL로 변환한다 (REQ-001.5).

    PostView.naver?blogId=xxx&logNo=yyy → m.blog.naver.com/xxx/yyy
    PostList.naver?blogId=xxx → m.blog.naver.com/PostList.naver?blogId=xxx
    PostSearchList.naver?blogId=xxx&SearchText=q → m.blog.naver.com/PostSearchList.naver?blogId=xxx&SearchText=q
    """
    params = parse_qs(query)
    blog_id = (params.get("blogId") or params.get("blogid") or [""])[0]
    log_no = (params.get("logNo") or params.get("logno") or [None])[0]

    # PostView: 개별 포스트 → /blogId/logNo
    if path.startswith("/PostView.naver") and blog_id and log_no:
        blog_id_enc = _encode_path_segment(blog_id)
        return f"{_MOBILE_BASE}/{blog_id_enc}/{log_no}"

    # PostList / PostSearchList: 목록 → 모바일 도메인에 동일 경로+쿼리
    # path에서 파일명 추출 (예: /PostList.naver → PostList.naver)
    endpoint_name = path.lstrip("/")
    if blog_id:
        blog_id_enc = _encode_path_segment(blog_id)
        # 블로그 ID를 쿼리에서 경로로 옮기지 않고 모바일 도메인으로만 변환
        new_query = f"blogId={blog_id_enc}"
        # 추가 파라미터 보존
        for key, values in params.items():
            if key.lower() not in ("blogid",):
                for val in values:
                    new_query += f"&{key}={quote(val, safe='')}"
        return f"{_MOBILE_BASE}/{endpoint_name}?{new_query}"

    # blogId 없으면 그냥 모바일 도메인으로 변환
    new_url = urlunparse((
        "https",
        _MOBILE_HOST,
        path,
        "",
        query,
        "",
    ))
    return new_url


def build_url_from_id(blog_id: str, log_no: str | None = None) -> str:
    """blogId (및 선택적 logNo)로 모바일 URL을 조립한다 (REQ-001.4).

    Args:
        blog_id: 네이버 블로그 ID (한글 가능).
        log_no: 포스트 번호 (None이면 블로그 홈 URL).

    Returns:
        m.blog.naver.com/{blogId}[/{logNo}] 형식의 URL.
    """
    blog_id_enc = _encode_path_segment(blog_id)
    if log_no is not None:
        return f"{_MOBILE_BASE}/{blog_id_enc}/{log_no}"
    return f"{_MOBILE_BASE}/{blog_id_enc}"
