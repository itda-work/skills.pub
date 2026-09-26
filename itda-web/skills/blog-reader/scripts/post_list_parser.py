"""post_list_parser.py - 네이버 블로그 포스트 목록 JSON API 파싱.

REQ-BLOGREADER-002: 포스트 목록 조회
  - REQ-002.5: 각 항목 logNo, title, url(모바일), published_at(ISO 8601), category, summary
  - REQ-002.4: has_next, next_page 페이지네이션 정보

라이브 실측 결과 (2026-05-15):
  SPA HTML 스크래핑 → 합성 fixture 불일치로 완전 미동작 확인.
  JSON API 채택: https://m.blog.naver.com/api/blogs/{blogId}/post-list
  파라미터: categoryNo, itemCount, page
  Referer 헤더: https://m.blog.naver.com/{blogId}

실측 JSON 스키마:
  {"isSuccess": true, "result": {
    "page": 1, "categoryNo": 0, "categoryName": "전체글", "totalCount": N,
    "items": [{
      "domainIdOrBlogId": "astroyuji",
      "logNo": 224286211021,
      "titleWithInspectMessage": "제목텍스트",
      "commentCnt": 0, "sympathyCnt": 2,
      "briefContents": "요약 본문...",
      "categoryName": "시황정리", "categoryNo": 24,
      "addDate": 1778811181146,  # epoch milliseconds (KST)
      ...
    }, ...]
  }}

라이브 실측 결과 (2026-05-16):
  중첩 카테고리 블로그(onehouse79)에서 categoryName에 박스 그리기 문자 + NBSP 포함.
  예: '└\xa0일상-소확행', '┌ 부동산이야기', '│맛집탐방-뷰맛집'
  normalize_category() 헬퍼로 선행 글리프 + 공백류 제거 후 사용. (REQ-002.3/002.5)

TC-3: 표준 라이브러리(json)만 사용.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Any

_MOBILE_BASE = "https://m.blog.naver.com"
_KST = timezone(timedelta(hours=9))

# 유니코드 Box Drawing 블록: U+2500–U+257F (─ ━ │ ┃ … ╿)
# 추가로 흔히 쓰는 계층 표시 문자: ▶ ▷ ► ▸ ・ 등 포함 안 함 (카테고리명 내부에 등장 가능)
# 정책: 선행(leading) 위치에서만 제거, 카테고리명 내부 문자는 보존.
_RE_CATEGORY_LEADING_GLYPH = re.compile(
    r"^[─-╿"       # Box Drawing (─ │ ┌ └ ╔ ╿ 등)
    r" 　﻿"    # NBSP, 전각공백, BOM
    r"\s]+"                  # 일반 공백·탭·줄바꿈 포함
)


# @MX:ANCHOR: [AUTO] normalize_category — 카테고리명 글리프 정규화 공용 헬퍼
# @MX:REASON: post_list_parser(JSON list), search HTML parser, post_parser(blog_category) 3곳에서 호출 (REQ-002.3/002.5/005.2)
def normalize_category(raw: str) -> str:
    """카테고리명에서 선행 박스 그리기 글자와 공백류를 제거한다.

    중첩 카테고리(onehouse79 등) API 응답에서 categoryName에 계층 시각화 문자가
    포함된다. 예: '└\\xa0일상-소확행' → '일상-소확행'.

    제거 대상 (선행부에서만):
      - 유니코드 Box Drawing U+2500–U+257F (┌ └ │ ─ ╔ … ╿)
      - NBSP (\\xa0), 전각공백 (\\u3000), BOM (\\ufeff)
      - 일반 공백·탭·줄바꿈 (\\s)

    카테고리명 내부 문자는 절대 제거하지 않는다.
    결과 양끝 공백은 strip()으로 제거한다.

    Args:
        raw: 네이버 API가 반환한 원시 카테고리명 문자열.

    Returns:
        글리프 제거 후 정규화된 카테고리명. 입력이 빈 문자열이면 빈 문자열 반환.

    Examples:
        >>> normalize_category('└\\xa0일상-소확행')
        '일상-소확행'
        >>> normalize_category('┌ 부동산이야기')
        '부동산이야기'
        >>> normalize_category('│맛집탐방-뷰맛집')
        '맛집탐방-뷰맛집'
        >>> normalize_category('시황정리')  # 글리프 없으면 불변
        '시황정리'
        >>> normalize_category('전체글')
        '전체글'
    """
    if not raw:
        return raw
    result = _RE_CATEGORY_LEADING_GLYPH.sub("", raw).strip()
    return result


# # @MX:ANCHOR: [AUTO] parse_post_list_json — JSON API 파싱 단일 진입점
# # @MX:REASON: naver_adapter.list_posts 및 search가 직접 호출 (fan_in >= 3)


def _adddate_to_iso8601(add_date: int) -> str:
    """addDate(epoch milliseconds, KST)를 ISO 8601 문자열로 변환한다.

    실측: addDate = 1778811181146 (13자리 epoch ms)
    변환 결과: "2026-05-15T09:33:01+09:00"

    Args:
        add_date: epoch milliseconds 정수.

    Returns:
        ISO 8601 형식 문자열 (KST, +09:00).
    """
    dt = datetime.fromtimestamp(add_date / 1000, tz=_KST)
    return dt.isoformat()


def parse_post_list_json(raw: str | bytes, blog_id: str) -> dict[str, Any]:
    """네이버 블로그 포스트 목록 JSON API 응답을 파싱해서 dict를 반환한다.

    실측 엔드포인트:
        GET https://m.blog.naver.com/api/blogs/{blogId}/post-list
            ?categoryNo={N}&itemCount={M}&page={P}
        Referer: https://m.blog.naver.com/{blogId}

    Args:
        raw: JSON API 응답 문자열 또는 바이트.
        blog_id: 블로그 ID (모바일 URL 구성에 사용).

    Returns:
        {
            "posts": list[dict],  # 각 항목: logNo, title, url, published_at,
                                  #          category, summary
            "has_next": bool,     # 다음 페이지 존재 여부
            "next_page": int | None,
            "total_count": int,
            "page": int,
        }

    Raises:
        ValueError: JSON 파싱 실패 또는 isSuccess=false인 경우.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"포스트 목록 JSON 파싱 실패: {exc}") from exc

    if not data.get("isSuccess", False):
        raise ValueError(
            f"API 응답 실패 (isSuccess=false): {data}"
        )

    result = data.get("result", {})
    items = result.get("items", [])
    page = result.get("page", 1)
    total_count = result.get("totalCount", 0)

    posts: list[dict[str, Any]] = []
    for item in items:
        domain_id = item.get("domainIdOrBlogId") or blog_id
        log_no = item.get("logNo") or item.get("logNoObject")
        title = item.get("titleWithInspectMessage") or ""
        summary = item.get("briefContents") or ""
        # REQ-002.3/002.5: 중첩 카테고리 글리프 정규화 (onehouse79 등)
        category = normalize_category(item.get("categoryName") or "")
        add_date = item.get("addDate")

        if not log_no:
            continue

        url = f"{_MOBILE_BASE}/{domain_id}/{log_no}"

        # addDate: epoch ms → ISO 8601 KST
        published_at = ""
        if isinstance(add_date, int) and add_date > 0:
            try:
                published_at = _adddate_to_iso8601(add_date)
            except (OSError, OverflowError, ValueError):
                published_at = ""

        posts.append({
            "logNo": str(log_no),
            "title": title,
            "url": url,
            "published_at": published_at,
            "category": category,
            "summary": summary,
        })

    # 페이지네이션: totalCount 기반으로 다음 페이지 판정
    # items가 itemCount(기본 30)개 이고 누적수가 totalCount 미만이면 has_next
    # 실제로는 items 길이로 판정 (items=0이면 마지막 페이지)
    has_next = len(items) > 0 and (page * len(items) < total_count or len(items) == 30)
    # 더 정확한 판정: items가 비어있거나, totalCount를 다 채웠으면 False
    # API는 totalCount를 0으로 반환하는 경우도 있음 → items > 0이면 has_next
    if total_count > 0:
        # 페이지 * 페이지당(기본 itemCount) >= totalCount면 마지막
        # 실측: itemCount는 파라미터로 요청, 응답에서 len(items)로 추론
        collected_so_far = len(items)  # 이번 페이지까지 수집
        # 단일 페이지 응답에서는 페이지당 수량을 모름 → items > 0 + 누적 비교
        has_next = len(items) > 0  # 항상 다음 페이지 시도 → naver_adapter가 종료 판정
    else:
        # totalCount=0이면 빈 결과 → has_next=False
        has_next = False

    next_page = (page + 1) if has_next else None

    return {
        "posts": posts,
        "has_next": has_next,
        "next_page": next_page,
        "total_count": total_count,
        "page": page,
    }


def parse_post_search_json(raw: str | bytes, blog_id: str) -> dict[str, Any]:
    """네이버 블로그 포스트 검색 결과를 파싱한다.

    현재는 post-list API로 통일하고, query는 클라이언트 측
    title/briefContents 부분 일치로 필터링한다(REQ-005.5: 네이버 순서 유지).

    검색 전용 엔드포인트가 별도 확인되면 SPEC-BLOGREADER-SEARCH-002로 분리.

    Args:
        raw: JSON API 응답 문자열 또는 바이트.
        blog_id: 블로그 ID.

    Returns:
        parse_post_list_json과 동일한 구조.
    """
    # 동일 API 재사용 (REQ-005.5: 순서 유지, 필터는 naver_adapter에서)
    return parse_post_list_json(raw, blog_id)


# 하위 호환: HTML 파서 시그니처를 유지하되 내부는 ValueError 발생
# (기존 코드가 이 함수를 직접 호출하는 테스트가 있으면 parse_post_list_json 사용)
def parse_post_list_html(html: str, blog_id: str) -> dict[str, Any]:
    """[DEPRECATED] HTML 파서는 SPA 마크업 불일치로 폐기됨.

    JSON API(parse_post_list_json)를 사용하라.
    하위 호환을 위해 함수 시그니처를 유지하나, html을 JSON으로 파싱 시도한다.
    JSON 파싱에 실패하면 빈 결과를 반환한다(하위 호환 안전 처리).
    """
    try:
        return parse_post_list_json(html, blog_id)
    except (ValueError, json.JSONDecodeError):
        # HTML이 들어오면 빈 결과 반환 (하위 호환)
        return {
            "posts": [],
            "has_next": False,
            "next_page": None,
            "total_count": 0,
            "page": 1,
        }


def parse_post_search_html(html: str, blog_id: str) -> dict[str, Any]:
    """PostSearchList.naver 응답 HTML을 파싱해서 검색 결과를 반환한다.

    실측 2026-05-15: PostSearchList.naver 레거시 테이블 HTML 구조 기반.
    - 각 검색 결과 블록: <!-- 검색결과 --> ~ <!-- //검색결과 --> 주석 사이
    - 제목/logNo: class="s_link" 앵커 (href에 logNo=(\\d+))
    - 날짜: class="eng" td 텍스트 (예: " 2026/05/12 10:43 ")
    - 카테고리: class="ct" span 중 두 번째 (첫 번째는 "|" 구분자 역할)
    - 스니펫: title td 다음 행의 padding:6px td 텍스트 (HTML 태그 제거)
    - 페이지네이션: goPage(N) 패턴에서 최대 페이지 번호 추출

    TC-3: 표준 라이브러리(re, html.parser)만 사용.

    Args:
        html: PostSearchList.naver 응답 HTML 문자열.
        blog_id: 블로그 ID (URL 정규화에 사용).

    Returns:
        {
            "posts": list[dict],  # logNo, title, url, published_at,
                                  # category, summary
            "has_next": bool,
            "next_page": int | None,
            "total_count": int,   # 블록 수 (HTML에 totalCount 없음)
            "page": int,
        }
    """
    import html as _html_module

    _RE_LOG_NO = re.compile(r"logNo=(\d+)")
    _RE_DATE = re.compile(r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})")
    _RE_TAGS = re.compile(r"<[^>]+>")
    _RE_PAGE = re.compile(r"goPage\((\d+)\)")

    # 검색결과 블록 추출: <!-- 검색결과 --> ~ <!-- //검색결과 -->
    blocks = re.split(r"<!-- 검색결과\s+-->", html)[1:]

    posts: list[dict[str, Any]] = []
    for block in blocks:
        # 블록 끝(//검색결과) 이전까지만 사용
        block_content = block.split("<!-- //검색결과 -->")[0]

        # logNo 추출: class="s_link" 앵커 href 우선, 이미지 앵커 fallback
        log_no = ""
        m = _RE_LOG_NO.search(block_content)
        if m:
            log_no = m.group(1)
        if not log_no:
            continue

        # 제목: class="s_link" 앵커 텍스트 (HTML 태그 제거)
        title_raw = ""
        s_link_match = re.search(
            r'class="s_link"[^>]*>(.*?)</a>',
            block_content,
            re.DOTALL,
        )
        if s_link_match:
            title_raw = _RE_TAGS.sub("", s_link_match.group(1))
            title_raw = _html_module.unescape(title_raw).strip()

        # 날짜: class="eng" td 내 날짜 텍스트
        published_at = ""
        eng_match = re.search(r'class="eng"[^>]*>(.*?)</td>', block_content, re.DOTALL)
        if eng_match:
            date_m = _RE_DATE.search(eng_match.group(1))
            if date_m:
                # "2026/05/12 10:43" → "2026-05-12T10:43:00+09:00" (KST)
                raw_date = date_m.group(1).strip()
                try:
                    date_part, time_part = raw_date.split()
                    y, mo, d = date_part.split("/")
                    hh, mm = time_part.split(":")
                    published_at = f"{y}-{mo}-{d}T{hh}:{mm}:00+09:00"
                except (ValueError, AttributeError):
                    published_at = raw_date  # 파싱 실패 시 원문 보존

        # 카테고리: class="ct" span — 첫 span("|")은 구분자, 두 번째 span이 카테고리
        # REQ-005.2: 중첩 카테고리 글리프 정규화 적용
        category = ""
        ct_spans = re.findall(r'class="ct"[^>]*>(.*?)</span>', block_content, re.DOTALL)
        if len(ct_spans) >= 2:
            # 두 번째 span이 카테고리명
            category = normalize_category(_RE_TAGS.sub("", ct_spans[1]).strip())
        elif ct_spans:
            # 두 번째 span이 없는 경우 → 첫 번째가 카테고리 ("|" 제외)
            candidate = _RE_TAGS.sub("", ct_spans[0]).strip()
            if candidate != "|":
                category = normalize_category(candidate)

        # 스니펫: padding:6px td 텍스트 (태그 제거)
        summary = ""
        snippet_match = re.search(
            r'padding:6px[^>]*>(.*?)</td>',
            block_content,
            re.DOTALL,
        )
        if snippet_match:
            summary = _RE_TAGS.sub("", snippet_match.group(1))
            summary = _html_module.unescape(summary).strip()
            # 타원(…) 정리
            summary = re.sub(r"\s+", " ", summary).strip()

        url = f"{_MOBILE_BASE}/{blog_id}/{log_no}"

        posts.append({
            "logNo": log_no,
            "title": title_raw,
            "url": url,
            "published_at": published_at,
            "category": category,
            "summary": summary,
        })

    # 페이지네이션: goPage(N) 최대값에서 현재 페이지 판정
    # 현재 페이지는 HTML에 명시되지 않으므로 posts 수 > 0이면 has_next 판단 불가
    # → 상위(naver_adapter)에서 결과 0건 여부로 종료 판단
    page_numbers = [int(m) for m in _RE_PAGE.findall(html)]
    max_page = max(page_numbers) if page_numbers else 1
    # currentPage는 파라미터로 전달받지 않으므로 page=1 기본값
    has_next = len(posts) > 0  # 결과 있으면 다음 페이지 시도 (adapter가 0건 감지 후 중단)

    return {
        "posts": posts,
        "has_next": has_next,
        "next_page": 2 if has_next else None,  # adapter가 currentPage를 관리
        "total_count": len(posts),
        "page": 1,
    }
