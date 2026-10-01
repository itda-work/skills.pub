"""법원경매 코드테이블 — 입찰구분·용도·지역(시도).

용도와 시도는 **사이트 화면이 부르는 코드 목록 응답을 그대로 옮긴 것**이다(2026-10-01 aside — 물건상세검색
PGJ151F00 의 용도 cascade ``/pgj/pgj002/selectLclLst.on``·``selectMclLst.on``·``selectSclLst.on`` 와 시도 목록
``selectAdongSdLst.on``). 테스트가 저장한 응답(``tests/fixtures/usage-cascade.json``·``regions-sido.json``)과
전수 대조한다(``data-accuracy``). 차량및운송장비·기타(대분류)는 화면이 법원 검색에서만 열어 주며 하위 분류는
뜨지 않았다(동산은 이 스킬 범위 밖).

시군구·읍면동은 표를 두지 않는다 — 사이트는 시도를 뺀 **3자리**(해운대구 ``350``·좌동 ``107``)를 보내고,
이는 행정표준코드(해운대구 ``26350``)의 끝 3자리다. 행정표준코드를 받아 앞자리가 시도와 맞는지 보고 자른다.

모르는 값은 통과시키지 않는다(``ValueError``) — 사이트가 모르는 코드를 보내면 0건이 "없음"으로 둔갑하거나
조건이 무시된 행이 섞인다(W12 리뷰 M1: 옛 표의 ``아파트 21201`` 은 사이트에 없는 코드였다).
"""

from __future__ import annotations

import re

# 입찰구분: bidDvsCd. 화면의 "전체" 는 빈 문자열이다.
BID_TYPES: list[dict] = [
    {"code": "000331", "name": "기일입찰", "alias": "date"},
    {"code": "000332", "name": "기간입찰", "alias": "period"},
]

# 용도: lcl/mcl/sclDspslGdsLstUsgCd — 화면 cascade 응답 그대로(2026-10-01).
USAGE_CODES: list[dict] = [
    {"level": "large", "code": "10000", "name": "토지"},
    {"level": "large", "code": "20000", "name": "건물"},
    {"level": "large", "code": "30000", "name": "차량및운송장비"},
    {"level": "large", "code": "40000", "name": "기타"},
    {"level": "medium", "parentCode": "10000", "code": "10100", "name": "지목"},
    {"level": "medium", "parentCode": "20000", "code": "20100", "name": "주거용건물"},
    {"level": "medium", "parentCode": "20000", "code": "21100", "name": "상업용및업무용"},
    {"level": "medium", "parentCode": "20000", "code": "22100", "name": "산업용및기타특수용"},
    {"level": "medium", "parentCode": "20000", "code": "23100", "name": "용도복합용"},
    {"level": "small", "parentCode": "10100", "code": "10101", "name": "전"},
    {"level": "small", "parentCode": "10100", "code": "10102", "name": "답"},
    {"level": "small", "parentCode": "10100", "code": "10103", "name": "과수원"},
    {"level": "small", "parentCode": "10100", "code": "10104", "name": "목장용지"},
    {"level": "small", "parentCode": "10100", "code": "10105", "name": "임야"},
    {"level": "small", "parentCode": "10100", "code": "10106", "name": "광천지"},
    {"level": "small", "parentCode": "10100", "code": "10107", "name": "염전"},
    {"level": "small", "parentCode": "10100", "code": "10108", "name": "대지"},
    {"level": "small", "parentCode": "10100", "code": "10109", "name": "공장용지"},
    {"level": "small", "parentCode": "10100", "code": "10110", "name": "학교용지"},
    {"level": "small", "parentCode": "10100", "code": "10111", "name": "주차장"},
    {"level": "small", "parentCode": "10100", "code": "10112", "name": "주유소용지"},
    {"level": "small", "parentCode": "10100", "code": "10113", "name": "창고용지"},
    {"level": "small", "parentCode": "10100", "code": "10114", "name": "도로"},
    {"level": "small", "parentCode": "10100", "code": "10115", "name": "철도용지"},
    {"level": "small", "parentCode": "10100", "code": "10116", "name": "제방"},
    {"level": "small", "parentCode": "10100", "code": "10117", "name": "하천"},
    {"level": "small", "parentCode": "10100", "code": "10118", "name": "구거"},
    {"level": "small", "parentCode": "10100", "code": "10119", "name": "유지"},
    {"level": "small", "parentCode": "10100", "code": "10120", "name": "양어장"},
    {"level": "small", "parentCode": "10100", "code": "10121", "name": "수도용지"},
    {"level": "small", "parentCode": "10100", "code": "10122", "name": "공원"},
    {"level": "small", "parentCode": "10100", "code": "10123", "name": "체육용지"},
    {"level": "small", "parentCode": "10100", "code": "10124", "name": "유원지"},
    {"level": "small", "parentCode": "10100", "code": "10125", "name": "종교용지"},
    {"level": "small", "parentCode": "10100", "code": "10126", "name": "사적지"},
    {"level": "small", "parentCode": "10100", "code": "10127", "name": "묘지"},
    {"level": "small", "parentCode": "10100", "code": "10128", "name": "잡종지"},
    {"level": "small", "parentCode": "20100", "code": "20101", "name": "단독주택"},
    {"level": "small", "parentCode": "20100", "code": "20102", "name": "다가구주택"},
    {"level": "small", "parentCode": "20100", "code": "20103", "name": "다중주택"},
    {"level": "small", "parentCode": "20100", "code": "20104", "name": "아파트"},
    {"level": "small", "parentCode": "20100", "code": "20105", "name": "연립주택"},
    {"level": "small", "parentCode": "20100", "code": "20106", "name": "다세대주택"},
    {"level": "small", "parentCode": "20100", "code": "20107", "name": "기숙사"},
    {"level": "small", "parentCode": "20100", "code": "20108", "name": "빌라"},
    {"level": "small", "parentCode": "20100", "code": "20109", "name": "상가주택"},
    {"level": "small", "parentCode": "20100", "code": "20110", "name": "오피스텔"},
    {"level": "small", "parentCode": "20100", "code": "20111", "name": "주상복합"},
    {"level": "small", "parentCode": "21100", "code": "21101", "name": "근린생활시설"},
    {"level": "small", "parentCode": "21100", "code": "21102", "name": "문화및집회시설"},
    {"level": "small", "parentCode": "21100", "code": "21103", "name": "종교시설"},
    {"level": "small", "parentCode": "21100", "code": "21104", "name": "판매시설"},
    {"level": "small", "parentCode": "21100", "code": "21105", "name": "운수시설"},
    {"level": "small", "parentCode": "21100", "code": "21106", "name": "의료시설"},
    {"level": "small", "parentCode": "21100", "code": "21107", "name": "교육연구시설"},
    {"level": "small", "parentCode": "21100", "code": "21108", "name": "노유자시설"},
    {"level": "small", "parentCode": "21100", "code": "21109", "name": "수련시설"},
    {"level": "small", "parentCode": "21100", "code": "21110", "name": "운동시설"},
    {"level": "small", "parentCode": "21100", "code": "21111", "name": "업무시설"},
    {"level": "small", "parentCode": "21100", "code": "21112", "name": "숙박시설"},
    {"level": "small", "parentCode": "21100", "code": "21113", "name": "위락시설"},
    {"level": "small", "parentCode": "21100", "code": "21114", "name": "교정및군사시설"},
    {"level": "small", "parentCode": "21100", "code": "21115", "name": "방송통신시설"},
    {"level": "small", "parentCode": "21100", "code": "21116", "name": "발전시설"},
    {"level": "small", "parentCode": "21100", "code": "21117", "name": "묘지관련시설"},
    {"level": "small", "parentCode": "21100", "code": "21118", "name": "관광휴게시설"},
    {"level": "small", "parentCode": "22100", "code": "22101", "name": "공장"},
    {"level": "small", "parentCode": "22100", "code": "22102", "name": "창고시설"},
    {"level": "small", "parentCode": "22100", "code": "22103", "name": "위험물저장및처리시설"},
    {"level": "small", "parentCode": "22100", "code": "22104", "name": "자동차관련시설"},
    {"level": "small", "parentCode": "22100", "code": "22105", "name": "동물및식물관련시설"},
    {"level": "small", "parentCode": "22100", "code": "22106", "name": "분뇨및쓰레기처리시설"},
    {"level": "small", "parentCode": "23100", "code": "23101", "name": "주/상용건물"},
    {"level": "small", "parentCode": "23100", "code": "23102", "name": "주/산용건물"},
    {"level": "small", "parentCode": "23100", "code": "23103", "name": "기타복합용건물"},
]

# 소재지 분기에서 화면이 열어 주는 대분류(``selectLclLst.on`` dsignUsgDvsCd "ST").
REGION_USAGE_LARGE = ("10000", "20000")

# 지역 시도: rprsAdongSdCd — 화면 ``selectAdongSdLst.on`` 응답 그대로(2026-10-01).
REGION_CODES: list[dict] = [
    {"sidoCode": "11", "sidoName": "서울특별시"},
    {"sidoCode": "12", "sidoName": "전남광주통합특별시"},
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
_LEVELS = ("large", "medium", "small")
_LEVEL_KO = {"large": "대분류", "medium": "중분류", "small": "소분류"}


def resolve_bid_type_code(value: str | None) -> str:
    """입찰구분 입력(alias/code/한글명)을 raw ``bidDvsCd``로. 빈값→"" (화면의 "전체").

    알 수 없는 값은 원문을 통과시킨다(CLI 는 ``date|period`` 만 받는다).
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
    """raw ``bidDvsCd``를 한글명으로. 미인식은 원문 통과."""
    if code is None:
        return ""
    text = str(code).strip()
    if text == "":
        return ""
    match = _BID_BY_CODE.get(text)
    return match["name"] if match else text


def _usage_entry(value, level: str) -> dict | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    hits = [e for e in USAGE_CODES if e["level"] == level and text in (e["code"], e["name"])]
    if not hits:
        raise ValueError(
            f"용도 {_LEVEL_KO[level]} '{text}' 는 사이트 코드표에 없다 — `codes usages` 로 이름·코드를 확인한다."
        )
    return hits[0]


def resolve_usage(large=None, medium=None, small=None) -> dict:
    """용도 입력(이름 또는 코드)을 ``{"large","medium","small"}`` 코드로.

    화면은 cascade 라 소분류를 고르면 대·중분류가 함께 실린다 — 준 가장 아래 분류에서 부모를 채운다.
    함께 준 상위 분류가 그 부모와 다르면 ``ValueError``.
    """
    given = {lv: _usage_entry(v, lv) for lv, v in (("large", large), ("medium", medium), ("small", small))}
    out = {lv: (e["code"] if e else "") for lv, e in given.items()}
    for child, parent in (("small", "medium"), ("medium", "large")):
        if not out[child]:
            continue
        want = _USAGE_BY_CODE[out[child]]["parentCode"]
        if out[parent] and out[parent] != want:
            name = _USAGE_BY_CODE[out[child]]["name"]
            raise ValueError(
                f"용도 {_LEVEL_KO[child]} '{name}' 는 {_LEVEL_KO[parent]} {want}({_USAGE_BY_CODE[want]['name']}) 아래다 "
                f"— {_LEVEL_KO[parent]} {out[parent]} 와 함께 쓸 수 없다."
            )
        out[parent] = want
    return out


def _resolve_sido(value: str) -> str:
    for entry in REGION_CODES:
        if value in (entry["sidoCode"], entry["sidoName"]):
            return entry["sidoCode"]
    raise ValueError(f"시도 '{value}' 는 사이트 목록에 없다 — `codes regions` 로 이름·코드를 확인한다.")


def _local_code(value: str, prefix: str, label: str, example: str) -> str:
    """행정표준코드(앞자리 = 상위 지역) 또는 사이트의 3자리 코드를 3자리로."""
    if re.fullmatch(r"\d{3}", value):
        return value
    if re.fullmatch(r"\d+", value) and len(value) == len(prefix) + 3:
        if not value.startswith(prefix):
            raise ValueError(f"{label} '{value}' 의 앞자리가 상위 지역({prefix})과 다르다.")
        return value[-3:]
    raise ValueError(f"{label}은(는) 행정표준코드 또는 사이트 3자리 코드다(예: {example}): '{value}'")


def resolve_region_codes(region: dict | None) -> dict:
    """지역 입력을 사이트 본문 값 ``{"sido","sigungu","dong"}`` 으로.

    - 시도: 이름 또는 2자리 코드(사이트 목록).
    - 시군구: 행정표준코드 5자리(해운대구 ``26350``) 또는 3자리(``350``) → 3자리. 시도가 있어야 한다.
    - 읍면동: 8자리(``26350107``) 또는 3자리(``107``) → 3자리. 시군구가 있어야 한다.
    - 셋 다 비면 ``{"","",""}`` — 지역 필터 없음(법원 분기, cortStDvs "1").
    """
    if not isinstance(region, dict):
        region = {}

    def _clean(key: str) -> str:
        raw = region.get(key)
        return "" if raw is None else str(raw).strip()

    sido, sgg, emd = _clean("sido"), _clean("sigungu"), _clean("dong")
    if (sgg and not sido) or (emd and not sgg):
        raise ValueError("지역은 시도 → 시군구 → 읍면동 순서로 고른다(화면과 같다) — 상위 지역을 함께 준다.")
    if sido:
        sido = _resolve_sido(sido)
    if sgg:
        sgg = _local_code(sgg, sido, "시군구", "해운대구 26350")
    if emd:
        emd = _local_code(emd, sido + sgg, "읍면동", "좌동 26350107")
    return {"sido": sido, "sigungu": sgg, "dong": emd}


def list_bid_types() -> list[dict]:
    return [dict(e) for e in BID_TYPES]


def list_usage_codes() -> list[dict]:
    return [dict(e) for e in USAGE_CODES]


def list_region_codes() -> list[dict]:
    return [dict(e) for e in REGION_CODES]
