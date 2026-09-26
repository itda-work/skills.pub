"""카카오맵 비공식 검색 어댑터.

공식 로컬 REST API와 달리 평점·영업상태·편의시설(addinfo_*)을 제공하는 모바일
검색 엔드포인트(``search.map.kakao.com/mapsearch/map.daum``)를 사용한다. 인증 키는
필요 없고, 모바일 User-Agent + Referer 헤더로 읽기 전용 GET만 한다.

모든 외부 호출은 ``(ok, data, reason)`` 계약을 따른다(eatery-trend ``adapters.py``
패턴) — 예외를 전파하지 않고 한국어 실패 사유를 reason으로 돌려준다(fail-loud).

설계 메모: 어댑터는 카카오 의존을 한 곳에 가둔다. 향후 공식 로컬 API 백엔드를
추가하려면 동일한 ``(ok, list, reason)`` 시그니처의 함수를 더하면 된다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://search.map.kakao.com/mapsearch/map.daum"

# 모바일 Safari UA — 데스크톱 UA보다 차단이 적고 모바일 검색 응답과 정합
_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://m.map.kakao.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_BLOCK_HINT = "카카오맵 접근이 일시 제한됐을 수 있습니다. 잠시 후 다시 시도해 주세요."


def _request(params: dict, *, timeout: int = 15) -> tuple[bool, dict | None, str]:
    """엔드포인트 GET → JSON. (ok, data, reason). 예외 비전파."""
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https 고정)
            status = getattr(resp, "status", resp.getcode())
            if status != 200:
                return False, None, f"카카오맵 응답 오류(HTTP {status}). {_BLOCK_HINT}"
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return False, None, f"카카오맵 차단/오류(HTTP {exc.code}). {_BLOCK_HINT}"
    except urllib.error.URLError as exc:
        return False, None, f"네트워크 오류로 카카오맵에 닿지 못했습니다: {exc.reason}"
    except TimeoutError:
        return False, None, "카카오맵 응답이 시간 초과됐습니다. 잠시 후 다시 시도해 주세요."

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, None, f"카카오맵 응답을 해석하지 못했습니다(차단 가능성). {_BLOCK_HINT}"

    if not isinstance(data, dict) or "place" not in data:
        return False, None, f"카카오맵 응답 형식이 예상과 다릅니다(차단/변경 가능성). {_BLOCK_HINT}"
    return True, data, ""


def geocode_anchor(location: str, *, timeout: int = 15) -> tuple[bool, dict | None, str]:
    """위치명을 검색해 거리 기준점(anchor) 좌표를 얻는다.

    반환 data: ``{"name": str, "lat": float, "lon": float}``.
    """
    location = (location or "").strip()
    if not location:
        return False, None, "기준 위치가 비어 있습니다. 역명·동네·랜드마크를 알려주세요."

    ok, data, reason = _request({"q": location, "msFlag": "A", "sort": 0}, timeout=timeout)
    if not ok:
        return False, None, reason

    places = data.get("place") or []
    if not places:
        return False, None, (
            f"'{location}' 위치를 카카오맵에서 찾지 못했습니다. "
            "가까운 역명이나 동 이름으로 한 번 더 알려주세요."
        )
    top = places[0]
    try:
        anchor = {
            "name": (top.get("name") or location).strip(),
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
        }
    except (KeyError, TypeError, ValueError):
        return False, None, f"'{location}' 위치 좌표를 읽지 못했습니다. 다른 표현으로 알려주세요."
    return True, anchor, ""


def search_places(
    query: str, *, page: int = 1, sort: int = 0, timeout: int = 15
) -> tuple[bool, list | None, str]:
    """``query``("{위치} {키워드}")로 장소를 검색해 raw place 목록을 돌려준다.

    sort=0(관련도)로 받아 호출 측에서 거리/평점 재정렬한다(1회성 — 매크로 금지).
    """
    query = (query or "").strip()
    if not query:
        return False, None, "검색어가 비어 있습니다."

    ok, data, reason = _request(
        {"q": query, "msFlag": "A", "sort": sort, "page": page}, timeout=timeout
    )
    if not ok:
        return False, None, reason
    return True, list(data.get("place") or []), ""
