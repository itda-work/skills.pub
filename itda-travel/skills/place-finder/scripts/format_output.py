"""검색 결과를 한국어 텍스트로 요약한다."""

from __future__ import annotations

from places import AMENITY_LABEL, Place


def _distance_str(meters: int | None) -> str:
    if meters is None:
        return ""
    if meters < 1000:
        return f"{meters}m"
    return f"{meters / 1000:.1f}km"


def _amenity_str(keys: list[str]) -> str:
    labels = [AMENITY_LABEL.get(key, key) for key in keys]
    return " ".join(f"#{label}" for label in labels)


def format_place(place: Place, idx: int) -> str:
    """장소 한 건을 여러 줄 블록으로."""
    head = f"{idx}. {place.name}"
    dist = _distance_str(place.distance_m)
    if dist:
        head += f" ({dist})"
    lines = [head]

    meta: list[str] = []
    if place.category:
        meta.append(place.category)
    if place.rating > 0:
        rating = f"평점 {place.rating:.1f}"
        if place.review_count:
            rating += f"({place.review_count})"
        meta.append(rating)
    if meta:
        lines.append("   " + " · ".join(meta))

    amenity = _amenity_str(place.amenities)
    if amenity:
        lines.append("   " + amenity)
    if place.tel:
        lines.append(f"   ☎ {place.tel}")
    lines.append(f"   🗺 {place.place_url}")
    return "\n".join(lines)


def format_results(
    places: list[Place],
    *,
    anchor_name: str,
    preset_label: str,
    total: int | None = None,
) -> str:
    """검색 결과 전체를 사용자용 한국어 요약으로."""
    if not places:
        return (
            f"'{anchor_name}' 근처에서 {preset_label} 결과를 찾지 못했습니다. "
            "위치를 더 구체적으로(가까운 역·동 이름) 알려주시면 다시 찾아볼게요."
        )

    header = f"📍 {anchor_name} 근처 {preset_label} {len(places)}곳"
    if total and total > len(places):
        header += f" (전체 {total}곳 중 가까운 순)"

    body = "\n\n".join(format_place(place, i + 1) for i, place in enumerate(places))
    footer = "\n\n※ 영업상태·메뉴는 실시간이 아닐 수 있어요. 정확한 정보는 카카오맵 링크에서 확인하세요."
    return f"{header}\n\n{body}{footer}"
