"""법원경매 요청 빌더 — 입력 검증과 요청 본문(JSON) 만들기. 네트워크 없음.

요청은 itda-hyve ``http_request`` 가 보낸다(규칙 ``cowork-network-via-hyve``). 이 모듈은 사이트
화면이 보내는 것과 **같은 본문**을 만든다 — 키 집합·순서·값은 2026-10-01 aside 로 뜬 요청
프로파일(XHR ``send`` 본문) 그대로다(``request-profile-first``). 입력이 틀리면 ``ValueError``.
"""

from __future__ import annotations

import re
from datetime import date as _date, datetime, timedelta, timezone

from codetables import (
    REGION_USAGE_LARGE,
    resolve_bid_type_code,
    resolve_region_codes,
    resolve_usage,
)

PAGE_SIZE_VALUES = [10, 20, 50, 100]
KST = timezone(timedelta(hours=9))
# 물건상세검색 화면의 기간 기본값은 오늘 ~ 14일 뒤다(2026-10-01 aside — 20261001~20261015). 기간을 비우면 화면이
# "기간을 올바르게 입력해주세요." 로 거부해 요청이 나가지 않는다 — 빈 기간은 화면이 보내는 값이 아니다.
SEARCH_WINDOW_DAYS = 14
# 소재지 분기에서도 숨은 법원 셀렉트의 값이 실린다 — 화면 기본값은 서울중앙지방법원이다(서버는 cortStDvs "2" 에서
# 이 값을 쓰지 않는다: 2026-10-01 부산 조회 결과 3행 전부 B000412).
REGION_BRANCH_HIDDEN_COURT = "B000210"


# --- 입력 검증 (ValueError를 던지면 호출 함수가 reason으로 변환) ---


def _to_ymd(value, label):
    if value is None or value == "":
        raise ValueError(f"{label}이(가) 필요합니다 (YYYY-MM-DD 또는 YYYYMMDD).")
    compact = re.sub(r"[^0-9]", "", str(value))
    if not re.fullmatch(r"\d{8}", compact):
        raise ValueError(f"{label}은(는) YYYY-MM-DD 또는 YYYYMMDD 형식이어야 합니다: '{value}'")
    return compact


def _optional_ymd(value, label="날짜"):
    if value is None or value == "":
        return ""
    return _to_ymd(value, label)


def _to_notice_search_date(value):
    """매각공고 검색 날짜를 월(YYYYMM) + 선택적 일자(YYYYMMDD)로."""
    if value is None or value == "":
        raise ValueError("date가 필요합니다 (YYYY-MM, YYYYMM, YYYY-MM-DD, 또는 YYYYMMDD).")
    compact = re.sub(r"[^0-9]", "", str(value))
    if re.fullmatch(r"\d{6}", compact):
        return {"query_ymd": compact, "exact_ymd": None}
    if re.fullmatch(r"\d{8}", compact):
        return {"query_ymd": compact[:6], "exact_ymd": compact}
    raise ValueError(f"date는 YYYY-MM, YYYYMM, YYYY-MM-DD, 또는 YYYYMMDD 형식이어야 합니다: '{value}'")


def _normalize_case_number(value):
    if value is None:
        raise ValueError("사건번호가 필요합니다 (예: 2024타경100001).")
    text = str(value).strip()
    if text == "":
        raise ValueError("사건번호가 비어 있습니다.")
    if re.fullmatch(r"\d{4}타경\d+", text):
        return text
    match = re.fullmatch(r"(\d{4})\s*[-_\s]?\s*(\d+)", text)
    if match:
        return f"{match.group(1)}타경{match.group(2)}"
    return text


def _ensure_court_code(value):
    if value is None:
        raise ValueError("법원사무소코드가 필요합니다 (예: 서울중앙지방법원 B000210).")
    text = str(value).strip()
    if not re.fullmatch(r"B\d{6}", text):
        raise ValueError(f"법원사무소코드는 'B000210' 형식이어야 합니다: '{value}'")
    return text


def _to_positive_int(value, fallback, label, *, allowed=None):
    if value is None or value == "":
        return fallback
    try:
        num = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}은(는) 양의 정수여야 합니다: '{value}'") from None
    if num <= 0:
        raise ValueError(f"{label}은(는) 양의 정수여야 합니다: '{value}'")
    if allowed is not None and num not in allowed:
        raise ValueError(f"{label}은(는) {', '.join(map(str, allowed))} 중 하나여야 합니다: {num}")
    return num


def _range_value(rng, key, *, integer_only=False, label=""):
    if not isinstance(rng, dict):
        return ""
    value = rng.get(key)
    if value is None or value == "":
        return ""
    text = str(value).strip().replace(",", "")
    if integer_only:
        if not re.fullmatch(r"\d+", text):
            raise ValueError(f"{label or key} 범위 값은 0 이상 정수여야 합니다: '{value}'")
    elif not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError(f"{label or key} 범위 값은 숫자여야 합니다: '{value}'")
    return text


# --- 매각공고 목록 (PGJ143M01 "검색") ---


def build_notices_body(*, date, court_code=None, bid_type=None):
    """``(body, search_date)`` — 사이트는 월(YYYYMM)만 보낸다. 일자는 받은 뒤 로컬로 거른다."""
    search_date = _to_notice_search_date(date)
    court = _ensure_court_code(court_code) if court_code else ""
    body = {
        "dma_srchDspslPbanc": {
            "srchYmd": search_date["query_ymd"],
            "cortOfcCd": court,
            "bidDvsCd": resolve_bid_type_code(bid_type),
            "srchBtnYn": "Y",
        }
    }
    return body, search_date


# --- 공고 펼치기 (PGJ143M02/M03 — 목록 행을 그대로 넘긴다) ---


def _blank(value):
    return "" if value is None else str(value)


def build_notice_detail_body(row):
    """목록(``dlt_rletDspslPbancLst``) 한 행으로 상세 본문을 만든다.

    화면(``scwin.sch_calendar_onclick``)은 행의 값을 그대로 옮기고 ``cortAuctnJdbnNm`` 은 비워 보낸다
    (2026-10-01 aside 실측 — 목록 행에 담당계 이름이 있어도 빈 문자열). ``null`` 은 빈 문자열이 된다.
    """
    if not isinstance(row, dict):
        raise ValueError("공고 펼치기에는 목록(notices) 행이 필요합니다.")
    cort = _ensure_court_code(row.get("cortOfcCd"))
    sale_ymd = _to_ymd(row.get("dspslDxdyYmd"), "dspslDxdyYmd")
    jdbn = _blank(row.get("jdbnCd")).strip()
    if not jdbn:
        raise ValueError("목록 행에 담당계 코드(jdbnCd)가 없습니다.")
    return {
        "dma_srchGnrlPbanc": {
            "cortOfcCd": cort,
            "dspslDxdyYmd": sale_ymd,
            "bidBgngYmd": _optional_ymd(row.get("bidBgngYmd"), "bidBgngYmd"),
            "bidEndYmd": _optional_ymd(row.get("bidEndYmd"), "bidEndYmd"),
            "jdbnCd": jdbn,
            "cortAuctnJdbnNm": "",
            "jdbnTelno": _blank(row.get("jdbnTelno")),
            "dspslPlcNm": _blank(row.get("dspslPlcNm")),
            "fstDspslHm": _blank(row.get("fstDspslHm")),
            "scndDspslHm": _blank(row.get("scndDspslHm")),
            "thrdDspslHm": _blank(row.get("thrdDspslHm")),
            "fothDspslHm": _blank(row.get("fothDspslHm")),
            "bidDvsCd": _blank(row.get("bidDvsCd")),
        }
    }


# --- 사건 단건 (PGJ15AF01) ---


def build_case_body(*, court_code, case_number):
    """``(body, 사건번호)`` — 화면은 ``{연도}타경{번호}`` 로 보낸다."""
    court = _ensure_court_code(court_code)
    case = _normalize_case_number(case_number)
    if not re.fullmatch(r"\d{4}타경\d+", case):
        raise ValueError(f"사건번호는 '2024타경100001' 형식이어야 합니다: '{case_number}'")
    return {"dma_srchCsDtlInf": {"cortOfcCd": court, "csNo": case}}, case


# --- 법원사무소 목록 (물건상세검색 화면이 부른다) ---


def build_courts_body():
    return {"cortExecrOfcDvsCd": "00079B"}


# --- 물건상세검색 (PGJ151F00 "검색") ---


def _search_window(sale, today):
    base = today or datetime.now(KST).date()
    frm = _optional_ymd(sale.get("from"), "saleDate.from") or base.strftime("%Y%m%d")
    to = _optional_ymd(sale.get("to"), "saleDate.to") or (base + timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y%m%d")
    if frm > to:
        if not _optional_ymd(sale.get("to"), "saleDate.to"):
            # 사용자는 끝을 준 적이 없다 — 무엇을 썼는지와 고칠 인자를 말한다(W12 재확인 n1).
            raise ValueError(
                f"매각기일 시작({frm})이 끝({to})보다 늦다 — 끝을 주지 않아 화면 기본값(오늘+{SEARCH_WINDOW_DAYS}일 = {to})을 썼다. "
                "--sale-to 도 준다."
            )
        raise ValueError(f"매각기일 시작({frm})이 끝({to})보다 늦다.")
    return frm, to


def build_property_search_body(
    *,
    page=1,
    page_size=10,
    court_code="",
    region=None,
    usage=None,
    sale_date=None,
    bid_type=None,
    judge_dept_code="",
    price_range=None,
    appraised_price_range=None,
    area=None,
    flbd_count=None,
    total_yn="Y",
    order_by="",
    today: _date | None = None,
):
    """화면이 보내는 본문. 두 분기가 있다(2026-10-01 aside 로 둘 다 떴다 — ``request-profile.json``).

    - 법원 분기(``cortStDvs`` "1"): 법원·담당계로 고른다. ``notifyLoc`` "off".
    - 소재지 분기(``cortStDvs`` "2"): 시도·시군구·읍면동으로 고른다. 공고중소재지 체크(기본)가 ``notifyLoc`` "on",
      숨은 법원 셀렉트의 기본값이 ``cortOfcCd`` 에 실린다. 화면은 두 분기를 라디오로 가르므로 법원과 지역을 함께 받지 않는다.

    기간(``bidBgngYmd``·``bidEndYmd``)은 화면에서 비울 수 없다 — 주지 않으면 화면 기본값(오늘 ~ 14일 뒤, KST).
    입찰구분을 주지 않으면 화면의 "전체"(빈 문자열).
    """
    page_no = _to_positive_int(page, 1, "page")
    size = _to_positive_int(page_size, 10, "pageSize", allowed=PAGE_SIZE_VALUES)
    reg = resolve_region_codes(region or {})
    usage = usage if isinstance(usage, dict) else {}
    use = resolve_usage(usage.get("large"), usage.get("medium"), usage.get("small"))
    sale = sale_date if isinstance(sale_date, dict) else {}
    has_region = bool(reg["sido"])
    if has_region and (court_code or judge_dept_code):
        raise ValueError("화면은 법원/담당계와 소재지 중 하나로 고른다 — 법원코드와 지역을 함께 줄 수 없다.")
    if has_region and use["large"] and use["large"] not in REGION_USAGE_LARGE:
        raise ValueError("차량및운송장비·기타 용도는 법원으로만 검색할 수 있다(사이트 안내) — 지역 대신 법원코드를 준다.")
    if has_region:
        court = REGION_BRANCH_HIDDEN_COURT
    else:
        court = _ensure_court_code(court_code) if court_code else ""
    bgng, end = _search_window(sale, today)

    return {
        "dma_pageInfo": {
            "pageNo": page_no,
            "pageSize": size,
            "bfPageNo": "",
            "startRowNo": "",
            "totalCnt": "",
            "totalYn": "N" if total_yn == "N" else "Y",
            "groupTotalCount": "",
        },
        "dma_srchGdsDtlSrchInfo": {
            "rletDspslSpcCondCd": "",
            "bidDvsCd": resolve_bid_type_code(bid_type),
            "mvprpRletDvsCd": "00031R",
            "cortAuctnSrchCondCd": "0004601",
            "rprsAdongSdCd": reg["sido"],
            "rprsAdongSggCd": reg["sigungu"],
            "rprsAdongEmdCd": reg["dong"],
            "rdnmSdCd": "",
            "rdnmSggCd": "",
            "rdnmNo": "",
            "mvprpDspslPlcAdongSdCd": "",
            "mvprpDspslPlcAdongSggCd": "",
            "mvprpDspslPlcAdongEmdCd": "",
            "rdDspslPlcAdongSdCd": "",
            "rdDspslPlcAdongSggCd": "",
            "rdDspslPlcAdongEmdCd": "",
            "cortOfcCd": court,
            "jdbnCd": str(judge_dept_code).strip() if judge_dept_code else "",
            "execrOfcDvsCd": "",
            "lclDspslGdsLstUsgCd": use["large"],
            "mclDspslGdsLstUsgCd": use["medium"],
            "sclDspslGdsLstUsgCd": use["small"],
            "cortAuctnMbrsId": "",
            "aeeEvlAmtMin": _range_value(appraised_price_range, "min", label="appraisedPriceRange.min"),
            "aeeEvlAmtMax": _range_value(appraised_price_range, "max", label="appraisedPriceRange.max"),
            "lwsDspslPrcRateMin": "",
            "lwsDspslPrcRateMax": "",
            "flbdNcntMin": _range_value(flbd_count, "min", integer_only=True, label="flbdCount.min"),
            "flbdNcntMax": _range_value(flbd_count, "max", integer_only=True, label="flbdCount.max"),
            "objctArDtsMin": _range_value(area, "min", label="area.min"),
            "objctArDtsMax": _range_value(area, "max", label="area.max"),
            "mvprpArtclKndCd": "",
            "mvprpArtclNm": "",
            "mvprpAtchmPlcTypCd": "",
            "notifyLoc": "on" if has_region else "off",
            "lafjOrderBy": str(order_by) if order_by else "",
            "pgmId": "PGJ151F01",
            "csNo": "",
            "cortStDvs": "2" if has_region else "1",
            "statNum": 1,
            "bidBgngYmd": bgng,
            "bidEndYmd": end,
            "dspslDxdyYmd": "",
            "fstDspslHm": "",
            "scndDspslHm": "",
            "thrdDspslHm": "",
            "fothDspslHm": "",
            "dspslPlcNm": "",
            "lwsDspslPrcMin": _range_value(price_range, "min", label="priceRange.min"),
            "lwsDspslPrcMax": _range_value(price_range, "max", label="priceRange.max"),
            "grbxTypCd": "",
            "gdsVendNm": "",
            "fuelKndCd": "",
            "carMdyrMax": "",
            "carMdyrMin": "",
            "carMdlNm": "",
            "sideDvsCd": "",
        },
    }
