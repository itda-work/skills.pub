"""법원경매 고수준 워크플로우 — 입력 검증·body 빌드·정규화 조합.

``CourtAuctionClient``(transport)를 인자로 받아 5개 워크플로우 함수를 제공한다.
모두 ``(ok, result, reason)`` 계약을 따른다 — 입력 검증 실패와 사이트 차단/오류를
한국어 reason으로 fail-loud한다.
"""

from __future__ import annotations

import re

from codetables import (
    describe_bid_type_code,
    resolve_bid_type_code,
    resolve_region_codes,
    resolve_usage_code,
)
from normalize import (
    normalize_case_detail_response,
    normalize_court_codes_response,
    normalize_notice_detail_response,
    normalize_notice_list_response,
    normalize_property_search_response,
)

PAGE_SIZE_VALUES = [10, 20, 50, 100]


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


# --- Workflow A: 매각공고 목록 ---


def search_sale_notices(client, *, date, court_code=None, bid_type=None, include_raw=True):
    try:
        search_date = _to_notice_search_date(date)
        court = _ensure_court_code(court_code) if court_code else ""
    except ValueError as exc:
        return False, None, str(exc)
    bid_code = resolve_bid_type_code(bid_type)

    body = {
        "dma_srchDspslPbanc": {
            # PGJ143M01 "검색" 버튼은 월(YYYYMM) 키를 POST한다. 일자는 아래에서 로컬 필터.
            "srchYmd": search_date["query_ymd"],
            "cortOfcCd": court,
            "bidDvsCd": bid_code,
            "srchBtnYn": "Y",
        }
    }
    ok, payload, reason = client.post_json("notices", body)
    if not ok:
        return False, None, reason

    month = f"{search_date['query_ymd'][:4]}-{search_date['query_ymd'][4:6]}"
    requested_bid = {"code": bid_code, "name": describe_bid_type_code(bid_code)} if bid_code else None
    result = normalize_notice_list_response(
        payload,
        requested_date=(
            f"{search_date['exact_ymd'][:4]}-{search_date['exact_ymd'][4:6]}-{search_date['exact_ymd'][6:8]}"
            if search_date["exact_ymd"]
            else month
        ),
        requested_month=month,
        requested_court_code=court or None,
        requested_bid_type=requested_bid,
        include_raw=True,
    )

    if search_date["exact_ymd"]:
        result["items"] = [
            item
            for item in result["items"]
            if (item.get("raw") or {}).get("dspslDxdyYmd") == search_date["exact_ymd"]
        ]
        result["count"] = len(result["items"])

    if not include_raw:
        for item in result["items"]:
            item.pop("raw", None)
    return True, result, ""


# --- Workflow A: 공고 펼치기 ---


def _build_notice_detail_body(notice):
    if not isinstance(notice, dict):
        raise ValueError("공고 펼치기에는 공고 객체(또는 raw)가 필요합니다.")
    raw = notice.get("raw") if isinstance(notice.get("raw"), dict) else notice

    cort = raw.get("cortOfcCd") or notice.get("courtCode") or ""
    if not cort:
        raise ValueError("공고 펼치기에는 법원사무소코드(cortOfcCd)가 필요합니다.")

    sale_ymd = raw.get("dspslDxdyYmd") or notice.get("saleDate") or ""
    if not sale_ymd:
        raise ValueError("공고 펼치기에는 매각기일(dspslDxdyYmd)이 필요합니다.")

    jdbn = raw.get("jdbnCd") or notice.get("judgeDeptCode") or ""
    if not jdbn:
        raise ValueError(
            "공고 펼치기에는 jdbnCd(재판부 토큰)가 필요합니다 — 목록(notices) 응답의 raw를 그대로 넘겨주세요."
        )

    bid_dvs = raw.get("bidDvsCd") or raw.get("intgCd") or resolve_bid_type_code(notice.get("bidType")) or ""

    return {
        "dma_srchGnrlPbanc": {
            "cortOfcCd": _ensure_court_code(cort),
            "dspslDxdyYmd": _to_ymd(sale_ymd, "dspslDxdyYmd"),
            "bidBgngYmd": _optional_ymd(raw.get("bidBgngYmd"), "bidBgngYmd"),
            "bidEndYmd": _optional_ymd(raw.get("bidEndYmd"), "bidEndYmd"),
            "jdbnCd": jdbn,
            "cortAuctnJdbnNm": raw.get("cortAuctnJdbnNm") or notice.get("judgeDeptName") or "",
            "jdbnTelno": raw.get("jdbnTelno") or notice.get("judgeDeptPhone") or "",
            "dspslPlcNm": raw.get("dspslPlcNm") or notice.get("salePlace") or "",
            "fstDspslHm": raw.get("fstDspslHm") or "",
            "scndDspslHm": raw.get("scndDspslHm") or "",
            "thrdDspslHm": raw.get("thrdDspslHm") or "",
            "fothDspslHm": raw.get("fothDspslHm") or "",
            "bidDvsCd": bid_dvs,
        }
    }


def get_sale_notice_detail(client, notice, *, include_raw=True):
    try:
        body = _build_notice_detail_body(notice)
    except ValueError as exc:
        return False, None, str(exc)
    ok, payload, reason = client.post_json("noticeDetail", body)
    if not ok:
        return False, None, reason
    return True, normalize_notice_detail_response(payload, include_raw=include_raw), ""


# --- Workflow B: 사건 단건 ---


def get_case(client, *, court_code, case_number, include_raw=True):
    try:
        court = _ensure_court_code(court_code)
        case = _normalize_case_number(case_number)
    except ValueError as exc:
        return False, None, str(exc)
    body = {"dma_srchCsDtlInf": {"cortOfcCd": court, "csNo": case}}
    ok, payload, reason = client.post_json("caseDetail", body)
    if not ok:
        return False, None, reason
    return True, normalize_case_detail_response(payload, include_raw=include_raw), ""


# --- Workflow C: 물건 자유검색 ---


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
    notify_location=False,
):
    page_no = _to_positive_int(page, 1, "page")
    size = _to_positive_int(page_size, 10, "pageSize", allowed=PAGE_SIZE_VALUES)
    court = _ensure_court_code(court_code) if court_code else ""
    reg = resolve_region_codes(region or {})
    usage = usage if isinstance(usage, dict) else {}
    sale = sale_date if isinstance(sale_date, dict) else {}
    has_region = bool(reg["sido"] or reg["sigungu"] or reg["dong"])

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
            "lclDspslGdsLstUsgCd": resolve_usage_code(usage.get("large"), "large"),
            "mclDspslGdsLstUsgCd": resolve_usage_code(usage.get("medium"), "medium"),
            "sclDspslGdsLstUsgCd": resolve_usage_code(usage.get("small"), "small"),
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
            "notifyLoc": "Y" if notify_location else "off",
            "lafjOrderBy": str(order_by) if order_by else "",
            "pgmId": "PGJ151F01",
            "csNo": "",
            "cortStDvs": "2" if has_region else "1",
            "statNum": 1,
            "bidBgngYmd": _optional_ymd(sale.get("from"), "saleDate.from"),
            "bidEndYmd": _optional_ymd(sale.get("to"), "saleDate.to"),
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


def search_properties(client, *, include_raw=True, **filters):
    try:
        body = build_property_search_body(**filters)
    except ValueError as exc:
        return False, None, str(exc)
    ok, payload, reason = client.post_json("propertySearch", body)
    if not ok:
        return False, None, reason
    return True, normalize_property_search_response(
        payload, requested_filters=body["dma_srchGdsDtlSrchInfo"], include_raw=include_raw
    ), ""


# --- 법원사무소코드 ---


def get_court_codes(client):
    ok, payload, reason = client.post_json("courts", {})
    if not ok:
        return False, None, reason
    return True, normalize_court_codes_response(payload), ""
