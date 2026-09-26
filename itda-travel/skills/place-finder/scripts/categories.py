"""place-finder 카테고리 프리셋과 자연어 분류.

4개 묶음(먹거리·여행·편의·교통) 아래 엄선된 카테고리 프리셋을 정의하고,
사용자 자연어를 프리셋 키로 해석한다. 카카오맵 비공식 검색은 키워드 기반이므로
각 프리셋은 검색에 붙일 키워드(keyword)와 결과 후처리용 카테고리 매칭어
(cate_match)를 함께 가진다.
"""

from __future__ import annotations

# 프리셋 정의: key -> 메타
#   group:      4묶음 분류
#   label:      사용자 표시명
#   keyword:    검색어에 붙일 키워드 ("{위치} {keyword}")
#   cate_match: 결과 cate_name 후처리 필터어(부분 일치, 선택적)
#   amenity:    기본 강조 편의시설(없으면 None)
PRESETS: dict[str, dict] = {
    "맛집": {"group": "먹거리", "label": "맛집", "keyword": "맛집", "cate_match": ["음식점"], "amenity": None},
    "카페": {"group": "먹거리", "label": "카페", "keyword": "카페", "cate_match": ["카페", "커피"], "amenity": "wifi"},
    "술집": {"group": "먹거리", "label": "술집", "keyword": "술집", "cate_match": ["술집", "호프", "주점", "포차", "이자카야", "와인"], "amenity": None},
    "숙박": {"group": "여행", "label": "숙박", "keyword": "숙소", "cate_match": ["숙박", "호텔", "모텔", "게스트", "펜션", "여관", "리조트"], "amenity": None},
    "관광명소": {"group": "여행", "label": "관광명소", "keyword": "관광명소", "cate_match": ["관광", "명소", "공원", "유적", "문화"], "amenity": None},
    "편의점": {"group": "편의", "label": "편의점", "keyword": "편의점", "cate_match": ["편의점"], "amenity": None},
    "약국": {"group": "편의", "label": "약국", "keyword": "약국", "cate_match": ["약국"], "amenity": None},
    "은행": {"group": "편의", "label": "은행/ATM", "keyword": "은행", "cate_match": ["은행", "금융", "ATM"], "amenity": None},
    "주유소": {"group": "편의", "label": "주유소", "keyword": "주유소", "cate_match": ["주유", "충전"], "amenity": None},
    "지하철역": {"group": "교통", "label": "지하철역", "keyword": "지하철역", "cate_match": ["지하철", "전철"], "amenity": None},
    "주차장": {"group": "교통", "label": "주차장", "keyword": "주차장", "cate_match": ["주차"], "amenity": None},
}

# 자연어 별칭 -> 프리셋 key (Claude 라우팅이 1차로 처리하나, CLI 견고성용 보조 사전)
ALIASES: dict[str, str] = {
    "맛집": "맛집", "음식점": "맛집", "밥집": "맛집", "식당": "맛집", "먹을곳": "맛집", "먹거리": "맛집",
    "카페": "카페", "커피": "카페", "카공": "카페", "디저트": "카페",
    "술집": "술집", "호프": "술집", "이자카야": "술집", "와인바": "술집", "포차": "술집",
    "펍": "술집", "혼술": "술집", "맥주": "술집", "요리주점": "술집",
    "숙박": "숙박", "숙소": "숙박", "호텔": "숙박", "모텔": "숙박", "게스트하우스": "숙박",
    "펜션": "숙박", "잘곳": "숙박", "리조트": "숙박", "여관": "숙박",
    "관광명소": "관광명소", "명소": "관광명소", "관광": "관광명소", "가볼만한곳": "관광명소",
    "볼거리": "관광명소", "관광지": "관광명소",
    "편의점": "편의점", "씨유": "편의점", "지에스25": "편의점", "세븐일레븐": "편의점",
    "약국": "약국",
    "은행": "은행", "atm": "은행", "현금": "은행", "현금인출기": "은행",
    "주유소": "주유소", "기름": "주유소", "주유": "주유소", "충전소": "주유소",
    "지하철역": "지하철역", "지하철": "지하철역", "전철": "지하철역",
    "주차장": "주차장", "주차": "주차장",
}


def all_presets() -> list[str]:
    """모든 프리셋 key 목록."""
    return list(PRESETS)


def resolve_preset(text: str) -> str | None:
    """자연어/프리셋명을 프리셋 key로 해석한다. 못 찾으면 None.

    우선순위: (1) 프리셋 key 정확 일치 → (2) 별칭 정확 일치 →
    (3) 가장 긴 별칭의 부분 포함(오탐 최소화).
    """
    if not text:
        return None
    t = text.strip().lower()
    for key in PRESETS:
        if t == key.lower():
            return key
    if t in ALIASES:
        return ALIASES[t]
    for alias in sorted(ALIASES, key=len, reverse=True):
        if alias and alias in t:
            return ALIASES[alias]
    return None


def search_keyword(preset_key: str) -> str:
    """프리셋의 검색 키워드."""
    return PRESETS[preset_key]["keyword"]


def cate_match(preset_key: str) -> list[str]:
    """프리셋의 카테고리 후처리 매칭어."""
    return list(PRESETS[preset_key]["cate_match"])


def label_of(preset_key: str) -> str:
    """프리셋의 사용자 표시명."""
    return PRESETS[preset_key]["label"]


def group_of(preset_key: str) -> str:
    """프리셋이 속한 4묶음."""
    return PRESETS[preset_key]["group"]


def presets_in_group(group: str) -> list[str]:
    """묶음에 속한 프리셋 key 목록."""
    return [k for k, v in PRESETS.items() if v["group"] == group]
