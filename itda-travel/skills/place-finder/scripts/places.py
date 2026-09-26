"""카카오맵 검색 결과(raw place dict)를 표준 Place로 정규화.

거리는 카카오 ``distance`` 필드(서버 IP 추정 위치 기준이라 부정확 — 실측에서
강남역 결과가 152km로 나옴)를 버리고, anchor(검색 지명) 좌표 기준 haversine으로
직접 계산한다.

영업상태(``openoff_status``)는 의도적으로 노출하지 않는다 — 실측 결과 실시간 영업과
무관한 내부 플래그였다(호텔 다수가 'N'). 영업·메뉴는 카카오맵 링크로 위임한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# 편의시설 키 -> 카카오 addinfo 필드
AMENITY_FIELDS: dict[str, str] = {
    "parking": "addinfo_parking",
    "wifi": "addinfo_wifi",
    "pet": "addinfo_pet",
    "smoking": "addinfo_smokingroom",
    "reservation": "addinfo_appointment",
    "delivery": "addinfo_delivery",
    "package": "addinfo_package",
    "disabled": "addinfo_fordisabled",
}

# 편의시설 키 -> 한국어 라벨
AMENITY_LABEL: dict[str, str] = {
    "parking": "주차",
    "wifi": "와이파이",
    "pet": "반려동물",
    "smoking": "흡연실",
    "reservation": "예약",
    "delivery": "배달",
    "package": "포장",
    "disabled": "장애인편의",
}


@dataclass
class Place:
    """정규화된 장소 한 건."""

    confirm_id: str
    name: str
    category: str
    tel: str
    address: str
    lon: float
    lat: float
    rating: float
    review_count: int
    amenities: list[str] = field(default_factory=list)
    distance_m: int | None = None

    @property
    def place_url(self) -> str:
        """카카오맵 장소 상세 링크."""
        return f"https://place.map.kakao.com/{self.confirm_id}"

    def to_dict(self) -> dict:
        return {
            "confirm_id": self.confirm_id,
            "name": self.name,
            "category": self.category,
            "tel": self.tel,
            "address": self.address,
            "lon": self.lon,
            "lat": self.lat,
            "rating": self.rating,
            "review_count": self.review_count,
            "amenities": self.amenities,
            "distance_m": self.distance_m,
            "place_url": self.place_url,
        }


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """두 좌표(위경도) 사이 거리(미터, 반올림)."""
    r = 6371000.0
    rad = math.pi / 180.0
    a = (
        math.sin((lat2 - lat1) * rad / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin((lon2 - lon1) * rad / 2) ** 2
    )
    return round(2 * r * math.asin(math.sqrt(a)))


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _category_text(raw: dict) -> str:
    """cate_name_depth 들로 표시용 카테고리 문자열을 만든다."""
    last = (raw.get("last_cate_name") or "").strip()
    d2 = (raw.get("cate_name_depth2") or "").strip()
    if last and d2 and last != d2:
        return f"{d2} > {last}"
    return last or d2 or (raw.get("cate_name_depth1") or "").strip()


def _amenities(raw: dict) -> list[str]:
    """'Y'로 표시된 편의시설 키 목록('N'/공백은 제외)."""
    return [key for key, fld in AMENITY_FIELDS.items() if (raw.get(fld) or "").strip().upper() == "Y"]


def normalize(raw: dict, anchor: tuple[float, float] | None = None) -> Place:
    """raw place dict -> Place. anchor가 있으면 haversine 거리를 계산한다."""
    lon = _to_float(raw.get("lon"))
    lat = _to_float(raw.get("lat"))
    place = Place(
        confirm_id=str(raw.get("confirmid") or raw.get("confirm_id") or "").strip(),
        name=(raw.get("name") or "").strip(),
        category=_category_text(raw),
        tel=(raw.get("tel") or "").strip(),
        address=(raw.get("new_address") or raw.get("address") or "").strip(),
        lon=lon,
        lat=lat,
        rating=_to_float(raw.get("rating_average")),
        review_count=int(_to_float(raw.get("reviewCount"))),
        amenities=_amenities(raw),
    )
    if anchor and lat and lon:
        place.distance_m = haversine_m(anchor[0], anchor[1], lat, lon)
    return place


def build_results(
    raw_places: list[dict],
    anchor: tuple[float, float] | None = None,
    *,
    cate_match: list[str] | None = None,
    amenity_filter: list[str] | None = None,
    sort: str = "distance",
    limit: int = 5,
) -> list[Place]:
    """raw place 목록 -> 정규화·중복제거·필터·정렬된 Place 목록.

    - cate_match: category 부분 일치 필터(선택). 비우면 검색 키워드 결과를 신뢰.
    - amenity_filter: 모든 편의시설을 가진 곳만(AND).
    - sort: ``distance``(anchor 필요) 또는 ``rating``.
    """
    seen: set[str] = set()
    places: list[Place] = []
    for raw in raw_places:
        place = normalize(raw, anchor)
        if not place.confirm_id or place.confirm_id in seen:
            continue
        seen.add(place.confirm_id)
        places.append(place)

    if cate_match:
        places = [p for p in places if any(m in p.category for m in cate_match)]

    if amenity_filter:
        places = [p for p in places if all(a in p.amenities for a in amenity_filter)]

    if sort == "rating":
        places.sort(key=lambda p: p.rating, reverse=True)
    elif sort == "distance" and anchor:
        places.sort(key=lambda p: p.distance_m if p.distance_m is not None else float("inf"))

    if limit and limit > 0:
        places = places[:limit]
    return places
