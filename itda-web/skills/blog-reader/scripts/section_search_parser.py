"""section_search_parser.py - 네이버 블로그 전역 검색(SearchList.naver) JSON 파서.

REQ-BLOGREADER-015 (#1334): discover 서브커맨드 — 네이버 블로그 전역 키워드 검색.

실측 2026-07-30 (#1334):
  GET https://section.blog.naver.com/ajax/SearchList.naver
      ?countPerPage=20&currentPage={N}&keyword={q}&orderBy={sim|recentdate}&type=post
  응답: ")]}'," 프리픽스 + JSON.
  - result.searchList[]: domainIdOrBlogId, logNo, postUrl, title(하이라이트
    <strong class="search_keyword"> 포함), noTagTitle(null 가능), contents(요약,
    하이라이트 포함), nickName, blogName, addDate(epoch ms)
  - result.totalCount: 전체 건수 (상한 1000 관측)
  - result.searchDisplayInfo.blockedByBifrostShield: 차단 여부 (false 관측)
  - searchDisplayInfo.authUrlType="LOGIN"은 정상 응답에도 항상 포함되는 로그인
    유도 링크 메타이며 차단 신호가 아니다 (실측: searchList 정상 동봉).
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime, timezone
from typing import Any

from errors import AntiBotBlockError, BlogStructureChangedError

# 네이버 ajax XSSI 방어 프리픽스 (실측: ")]}',\n")
_XSSI_PREFIX = ")]}'"

# 하이라이트 등 HTML 태그 제거용 (title/contents 공통)
_RE_TAG = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    """검색 하이라이트(<strong class="search_keyword">) 등 태그를 제거하고
    HTML 엔티티를 복원한다."""
    return _html.unescape(_RE_TAG.sub("", text or "")).strip()


def _epoch_ms_to_iso(value: Any) -> str:
    """addDate(epoch ms)를 ISO 8601(UTC) 문자열로 변환한다. 실패 시 빈 문자열."""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def parse_section_search_json(raw: str, query: str) -> dict[str, Any]:
    """SearchList.naver 응답을 파싱해 정규화된 결과를 반환한다.

    Args:
        raw: HTTP 응답 원문 (XSSI 프리픽스 포함 가능).
        query: 검색 키워드 (에러 메시지용).

    Returns:
        {"posts": [{blog_id, log_no, title, url, published_at, summary,
                    blog_name, nickname}, ...],
         "total_count": int}

    Raises:
        AntiBotBlockError: blockedByBifrostShield=true 감지 시 (우회 없음, exit 4).
        BlogStructureChangedError: JSON 파싱 실패·구조 변경 시 (exit 1).
    """
    body = raw.lstrip()
    if body.startswith(_XSSI_PREFIX):
        # 프리픽스 라인 제거 — 첫 개행 이후가 JSON 본문
        _, _, body = body.partition("\n")

    try:
        payload = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise BlogStructureChangedError(
            f"전역 검색 응답 JSON 파싱 실패 (query={query!r}): {exc}"
        ) from exc

    result = payload.get("result")
    if not isinstance(result, dict):
        raise BlogStructureChangedError(
            f"전역 검색 응답에 result 객체가 없습니다 (query={query!r})"
        )

    display_info = result.get("searchDisplayInfo") or {}
    if display_info.get("blockedByBifrostShield"):
        raise AntiBotBlockError(
            f"네이버 Bifrost Shield 차단 감지 (query={query!r}) — 우회하지 않습니다."
        )

    search_list = result.get("searchList")
    if search_list is None:
        raise BlogStructureChangedError(
            f"전역 검색 응답에 searchList가 없습니다 (query={query!r})"
        )

    posts: list[dict[str, Any]] = []
    for item in search_list:
        blog_id = str(item.get("domainIdOrBlogId") or "")
        log_no = str(item.get("logNo") or "")
        # noTagTitle이 오면 우선 사용, 없으면(null 관측) title에서 태그 제거
        title = item.get("noTagTitle") or _strip_tags(item.get("title") or "")
        url = item.get("postUrl") or (
            f"https://blog.naver.com/{blog_id}/{log_no}" if blog_id and log_no else ""
        )
        posts.append(
            {
                "blog_id": blog_id,
                "log_no": log_no,
                "title": title,
                "url": url,
                "published_at": _epoch_ms_to_iso(item.get("addDate")),
                "summary": _strip_tags(item.get("contents") or ""),
                "blog_name": str(item.get("blogName") or ""),
                "nickname": str(item.get("nickName") or ""),
            }
        )

    total_count = result.get("totalCount")
    return {
        "posts": posts,
        "total_count": int(total_count) if isinstance(total_count, (int, float)) else 0,
    }
