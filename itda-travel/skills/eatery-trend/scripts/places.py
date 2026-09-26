"""places.py — 장소 해결: 지역검색 + 음식 카테고리 필터 + geo assert (REQ-004/023).

뜬 키워드를 *파는 집*으로 해결한다. 장소 해결 1차 = 네이버 공식 지역검색 API
(우리 키·무활성화·무스크래핑). 지도 스크래핑 의존 0(REQ-004/AC-7).

음식 카테고리 필터(REQ-023)로 비음식(쇼핑·숙박·충전소)과 비음식 바이럴
(뉴뉴=패션)을 차단한다 — 옷가게를 식당으로 추천하지 않는다(§8.12 PoC#6).
주소 geo assert로 동명 가게의 타지역 누출을 막는다(REQ-013).

OQ-3 잔여는 v1에서 graceful 마커로 처리한다:
  - 0매칭(팝업/미등록/이름불일치 빵빵런·미영이네식당) → 웹/블로그 폴백 마커.
  - 동음 다수(올레국수 5곳) → 리뷰수 tiebreak/클러스터 표기 마커.
"""
from __future__ import annotations

import html
import re
from typing import Callable

# 음식 카테고리 화이트리스트(REQ-023). category 부분 문자열 매칭("한식>국수" ← "한식").
FOOD_CAT: tuple[str, ...] = (
    "음식점", "카페", "한식", "일식", "중식", "양식", "분식", "디저트",
    "베이커리", "회", "국수", "국밥", "치킨", "호프", "술집", "주점",
    "뷔페", "고기", "해물", "제과", "퓨전요리", "요리주점", "패스트푸드",
    "포장마차", "생선요리", "조개", "찌개", "전골", "곱창", "닭",
)

_TAG_RE = re.compile(r"<[^>]+>")


def clean_title(title: str) -> str:
    """지역검색 title의 <b> 등 HTML 태그·엔티티를 제거한다."""
    if not title:
        return ""
    return html.unescape(_TAG_RE.sub("", title)).strip()


def is_food_category(category: str) -> bool:
    """카테고리가 음식군에 속하는가(REQ-023). 부분 문자열 매칭."""
    if not category:
        return False
    return any(f in category for f in FOOD_CAT)


def geo_assert(item: dict, tokens: list[str]) -> bool:
    """가게 주소(roadAddress/address)가 geo 토큰을 포함하는가(REQ-013 타지역 차단)."""
    addr = f"{item.get('roadAddress', '')} {item.get('address', '')}"
    return any(t and t in addr for t in tokens)


def resolve_places(
    keyword: str,
    tokens: list[str],
    search_fn: Callable[[str], tuple[bool, list[dict], str]],
    *,
    geo_required: bool = True,
) -> dict:
    """키워드를 음식 카테고리 + geo 통과 가게 목록으로 해결한다.

    Args:
        keyword: 검색 키워드(예: "제주 올레국수").
        tokens: geo 토큰(geo assert용).
        search_fn: (ok, items, reason) 반환하는 지역검색 함수(adapters.local_search).
        geo_required: True면 주소 geo assert 적용.

    Returns:
        dict {keyword, status, places, homonym, note, reason}.
          status: "ok"(음식+geo 통과 ≥1) / "no_food_match"(매칭은 있으나 음식 0)
                  / "no_match"(지역검색 0건) / "source_error"(소스 차단, fail-loud).
          places: [{title, category, roadAddress, mapx, mapy}, ...].
          homonym: 음식 가게 ≥2(동음 다수 → 리뷰수 tiebreak 권장).
    """
    out = {
        "keyword": keyword,
        "status": "ok",
        "places": [],
        "homonym": False,
        "note": "",
        "reason": "",
    }

    ok, items, reason = search_fn(keyword)
    if not ok:
        out["status"] = "source_error"
        out["reason"] = reason or "지역검색 도달 실패"
        out["note"] = "지역검색 차단/오류 — 결과 없음을 성공으로 보고하지 않음(REQ-008)"
        return out

    if not items:
        out["status"] = "no_match"
        out["note"] = (
            "지역검색 0매칭 — 팝업/미등록/이름불일치 가능. "
            "블로그/웹 폴백으로 실제 가게명 해결 권장(OQ-3 잔여)"
        )
        return out

    # 음식 카테고리 + geo 필터
    kept: list[dict] = []
    for it in items:
        if not is_food_category(it.get("category", "")):
            continue
        if geo_required and not geo_assert(it, tokens):
            continue
        kept.append({
            "title": clean_title(it.get("title", "")),
            "category": it.get("category", ""),
            "roadAddress": it.get("roadAddress", ""),
            "address": it.get("address", ""),
            "mapx": it.get("mapx", ""),
            "mapy": it.get("mapy", ""),
        })

    if not kept:
        out["status"] = "no_food_match"
        out["note"] = (
            "매칭된 장소가 음식 카테고리 아님(또는 타지역) — "
            "비음식 바이럴(예: 뉴뉴=패션) 차단. 블로그/웹 폴백 권장(OQ-3 잔여)"
        )
        return out

    out["places"] = kept
    if len(kept) >= 2:
        out["homonym"] = True
        out["note"] = (
            f"동음 가게 {len(kept)}곳 — 리뷰수 tiebreak/클러스터 표기 권장(OQ-3 잔여)"
        )
    return out
