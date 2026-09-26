"""법원경매 코드테이블 — 입찰구분·용도·지역(시도)·법원사무소.

법원사무소코드는 동적 조회(`queries.get_court_codes`)지만, 입찰구분(2종)·용도
대분류(+대표 중·소분류)·지역 시도(19종)는 사이트 PGJ151F00 초기 XHR에서 캡처한
정적 표로 보존한다(2026-05-08 기준). 시군구(5자리)/읍면동(8자리)과 망라되지 않은
중·소 용도는 사이트 cascade XHR이 안정적으로 노출되지 않으므로 정적 표에 넣지 않고,
raw 코드를 그대로 통과시킨다(fail-open).

resolver는 모두 fail-open이다 — 알 수 없는 입력은 원문을 그대로 돌려보내 사이트가
판정하게 한다(우리가 임의로 코드를 바꿔치기해 요청을 조용히 오염시키지 않는다).
"""

from __future__ import annotations

# 입찰구분: bidDvsCd
BID_TYPES: list[dict] = [
    {"code": "000331", "name": "기일입찰", "alias": "date"},
    {"code": "000332", "name": "기간입찰", "alias": "period"},
]

# 용도: lcl/mcl/sclDspslGdsLstUsgCd. 대분류 4 + 대표 중·소분류(망라 아님).
USAGE_CODES: list[dict] = [
    {"level": "large", "code": "10000", "name": "토지"},
    {"level": "large", "code": "20000", "name": "건물"},
    {"level": "large", "code": "40000", "name": "기타"},
    {"level": "medium", "parentCode": "20000", "code": "21100", "name": "단독주택"},
    {"level": "medium", "parentCode": "20000", "code": "21200", "name": "공동주택"},
    {"level": "small", "parentCode": "21100", "code": "21101", "name": "단독주택(소분류)"},
    {"level": "small", "parentCode": "21200", "code": "21201", "name": "아파트"},
]

# 지역 시도: rprsAdongSdCd. 시군구/읍면동은 raw 통과(아래 resolve_region_codes 주석).
REGION_CODES: list[dict] = [
    {"sidoCode": "11", "sidoName": "서울특별시"},
    {"sidoCode": "26", "sidoName": "부산광역시"},
    {"sidoCode": "27", "sidoName": "대구광역시"},
    {"sidoCode": "28", "sidoName": "인천광역시"},
    {"sidoCode": "29", "sidoName": "광주광역시"},
    {"sidoCode": "30", "sidoName": "대전광역시"},
    {"sidoCode": "31", "sidoName": "울산광역시"},
    {"sidoCode": "36", "sidoName": "세종특별자치시"},
    {"sidoCode": "41", "sidoName": "경기도"},
    {"sidoCode": "42", "sidoName": "강원도"},
    {"sidoCode": "43", "sidoName": "충청북도"},
    {"sidoCode": "44", "sidoName": "충청남도"},
    {"sidoCode": "45", "sidoName": "전라북도"},
    {"sidoCode": "46", "sidoName": "전라남도"},
    {"sidoCode": "47", "sidoName": "경상북도"},
    {"sidoCode": "48", "sidoName": "경상남도"},
    {"sidoCode": "50", "sidoName": "제주특별자치도"},
    {"sidoCode": "51", "sidoName": "강원특별자치도"},
    {"sidoCode": "52", "sidoName": "전북특별자치도"},
]

_BID_BY_ALIAS = {e["alias"]: e for e in BID_TYPES}
_BID_BY_CODE = {e["code"]: e for e in BID_TYPES}
_BID_BY_NAME = {e["name"]: e for e in BID_TYPES}
_USAGE_BY_CODE = {e["code"]: e for e in USAGE_CODES}
_USAGE_BY_NAME: dict[str, dict] = {}
for _e in USAGE_CODES:
    _USAGE_BY_NAME.setdefault(_e["name"], _e)  # 첫 등록 우선(level 없는 조회용)


def resolve_bid_type_code(value: str | None) -> str:
    """입찰구분 입력(alias/code/한글명)을 raw ``bidDvsCd``로. 빈값→"" (전체).

    알 수 없는 값은 fail-open으로 원문을 통과시킨다.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if text == "":
        return ""
    alias = _BID_BY_ALIAS.get(text.lower())
    if alias:
        return alias["code"]
    if text in _BID_BY_CODE:
        return text
    name = _BID_BY_NAME.get(text)
    if name:
        return name["code"]
    return text


def describe_bid_type_code(code: str | None) -> str:
    """raw ``bidDvsCd``를 한글명으로. 미인식은 원문 통과(fail-open)."""
    if code is None:
        return ""
    text = str(code).strip()
    if text == "":
        return ""
    match = _BID_BY_CODE.get(text)
    return match["name"] if match else text


def resolve_usage_code(value: str | None, level: str | None = None) -> str:
    """용도 입력(코드/한글명)을 raw ``lcl/mcl/sclDspslGdsLstUsgCd``로. 빈값→"".

    - 5자리 코드는 level 무관하게 그대로 인정한다(사이트가 유효성 판정).
    - ``level``이 주어지면 그 레벨에 정확히 등록된 이름만 매칭한다. 다른 레벨에만
      있는 동명("아파트"는 small에만)이면 **fail-open**(원문 통과) — 엉뚱한 레벨
      코드로 조용히 바꿔치기하지 않는다.
    - ``level``이 없으면 첫 등록 이름과 매칭한다.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if text == "":
        return ""
    if text in _USAGE_BY_CODE:
        return text
    if level:
        for entry in USAGE_CODES:
            if entry["name"] == text and entry["level"] == level:
                return entry["code"]
        return text  # fail-open
    name = _USAGE_BY_NAME.get(text)
    return name["code"] if name else text


def resolve_region_codes(region: dict | None) -> dict:
    """지역 입력을 ``{"sido","sigungu","dong"}`` raw 코드로.

    - 시도는 정적 표에서 코드 또는 한글명으로 해석한다.
    - 시군구(5자리)/읍면동(8자리)은 정적 표가 없어 raw 코드를 그대로 통과시킨다
      (예: ``{"sido":"11","sigungu":"11680","dong":"11680101"}``).
    - 셋 다 비면 ``{"","",""}`` — "지역 필터 없음" 상태(cortStDvs:"1" 분기).
    """
    if not isinstance(region, dict):
        return {"sido": "", "sigungu": "", "dong": ""}

    def _clean(key: str) -> str:
        raw = region.get(key)
        return "" if raw is None else str(raw).strip()

    sido = _clean("sido")
    if sido:
        for entry in REGION_CODES:
            if entry["sidoCode"] == sido or entry["sidoName"] == sido:
                sido = entry["sidoCode"]
                break
    return {"sido": sido, "sigungu": _clean("sigungu"), "dong": _clean("dong")}


def list_bid_types() -> list[dict]:
    return [dict(e) for e in BID_TYPES]


def list_usage_codes() -> list[dict]:
    return [dict(e) for e in USAGE_CODES]


def list_region_codes() -> list[dict]:
    return [dict(e) for e in REGION_CODES]
