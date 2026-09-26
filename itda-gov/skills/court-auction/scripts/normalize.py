"""법원경매 WebSquare 응답 정규화 — raw 한국어/약어 키를 영문 키로.

순수 함수 모음(네트워크·IO 없음). 사이트 응답은 가격 셀에 ``<img>``·``<br>``이
섞여 오므로 HTML을 벗기고 금액(콤마)·일자(YYYYMMDD)·시각(HHMM)을 파싱한다.
응답 봉투는 ``{"data": {...}, "status": int, "message": str}`` 형태를 가정한다.
"""

from __future__ import annotations

import re

from codetables import describe_bid_type_code

_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_INT_RE = re.compile(r"-?\d+")
_YMD_RE = re.compile(r"\d{8}")
_HM_RE = re.compile(r"\d{3,4}")


def null_if_blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "" else text


def strip_html(value):
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"<img\b[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    text = re.sub(r"\s+", " ", text).strip()
    return None if text == "" else text


def parse_amount(value):
    """금액(정수) 추출. HTML/콤마 제거. 못 찾으면 None."""
    if value is None:
        return None
    stripped = strip_html(value)
    if not stripped or stripped == "-":
        return None
    match = _AMOUNT_RE.search(stripped)
    if not match:
        return None
    digits = match.group(0).replace(",", "").replace(" ", "")
    try:
        return int(digits)
    except ValueError:
        return None


def parse_number(value):
    """정수 또는 실수 파싱(면적·좌표). 숫자가 아니면 None."""
    if value is None:
        return None
    stripped = strip_html(value)
    if not stripped:
        return None
    normalized = stripped.replace(",", "").replace(" ", "")
    if not _NUMBER_RE.fullmatch(normalized):
        return None
    if _INT_RE.fullmatch(normalized):
        return int(normalized)
    return float(normalized)


def format_ymd(value):
    """YYYYMMDD → YYYY-MM-DD. 8자리 아니면 원문(공백은 None)."""
    if value is None:
        return None
    text = str(value).strip()
    if not _YMD_RE.fullmatch(text):
        return null_if_blank(text)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def format_hm(value):
    """HHMM(3~4자리) → HH:MM. 아니면 원문(공백은 None)."""
    if value is None:
        return None
    text = str(value).strip()
    if not _HM_RE.fullmatch(text):
        return null_if_blank(text)
    padded = text.zfill(4)
    return f"{padded[:2]}:{padded[2:4]}"


def _ensure_row(row):
    return row if isinstance(row, dict) else {}


def _data_of(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return None


def _list_at(container, key):
    if isinstance(container, dict) and isinstance(container.get(key), list):
        return container[key]
    return []


def collect_sale_times(row):
    out = []
    for key in ("fstDspslHm", "scndDspslHm", "thrdDspslHm", "fothDspslHm"):
        formatted = format_hm(row.get(key))
        if formatted:
            out.append(formatted)
    return out


# --- Workflow A: 매각공고 목록 ---


def normalize_notice_row(raw_row, include_raw):
    row = _ensure_row(raw_row)
    out = {
        "noticeId": null_if_blank(row.get("dspslRealId")),
        "courtCode": null_if_blank(row.get("cortOfcCd")),
        "courtName": null_if_blank(row.get("cortOfcNm")),
        "courtBranchName": null_if_blank(row.get("cortSptNm")),
        "judgeDeptCode": null_if_blank(row.get("jdbnCd")),
        "judgeDeptName": null_if_blank(row.get("cortAuctnJdbnNm")),
        "printJudgeDeptName": null_if_blank(row.get("printJdbnNm")),
        "judgeDeptPhone": null_if_blank(row.get("jdbnTelno")),
        "bidTypeCode": null_if_blank(row.get("bidDvsCd")) or null_if_blank(row.get("intgCd")),
        "bidTypeName": (
            null_if_blank(row.get("intgCdNm"))
            or describe_bid_type_code(null_if_blank(row.get("bidDvsCd")) or "")
            or None
        ),
        "saleDate": format_ymd(row.get("dspslDxdyYmd")),
        "bidStartDate": format_ymd(row.get("bidBgngYmd")),
        "bidEndDate": format_ymd(row.get("bidEndYmd")),
        "bidPeriodLabel": null_if_blank(row.get("realBidPerd")),
        "salePlace": null_if_blank(row.get("dspslPlcNm")),
        "saleTimes": collect_sale_times(row),
        "correctionCount": parse_amount(row.get("corCnt")) or 0,
        "cancellationCount": parse_amount(row.get("canCnt")) or 0,
    }
    if include_raw:
        out["raw"] = dict(row)
    return out


def normalize_notice_list_response(
    raw_payload,
    *,
    requested_date=None,
    requested_month=None,
    requested_court_code=None,
    requested_bid_type=None,
    include_raw=True,
):
    data = _data_of(raw_payload)
    rows = _list_at(data, "dlt_rletDspslPbancLst")
    items = [normalize_notice_row(r, include_raw) for r in rows]
    return {
        "requestedDate": requested_date,
        "requestedMonth": requested_month,
        "requestedCourtCode": requested_court_code,
        "requestedBidType": requested_bid_type,
        "count": len(items),
        "items": items,
    }


# --- Workflow A: 공고 펼치기(사건/물건) ---


def normalize_notice_detail_row(raw_row, include_raw):
    row = _ensure_row(raw_row)
    out = {
        "caseNumber": strip_html(row.get("csNo")),
        "itemSeq": null_if_blank(row.get("dspslSeq")),
        "usage": strip_html(row.get("usgNm")),
        "address": strip_html(row.get("st")),
        "appraisedPrice": parse_amount(row.get("aeeEvlAmt")),
        "minimumSalePrice": parse_amount(row.get("lwsDspslPrc")),
        "remarks": strip_html(row.get("dspslRmk")),
    }
    if include_raw:
        out["raw"] = dict(row)
    return out


def normalize_notice_detail_response(raw_payload, *, include_raw=True):
    data = _data_of(raw_payload)
    result_data = data.get("result") if isinstance(data, dict) and isinstance(data.get("result"), dict) else None
    nested_input = (
        result_data.get("inputData")
        if result_data and isinstance(result_data.get("inputData"), dict)
        else None
    )
    meta = nested_input or (
        data.get("dma_srchGnrlPbanc")
        if isinstance(data, dict) and isinstance(data.get("dma_srchGnrlPbanc"), dict)
        else {}
    )
    nested_pbanc = None
    if (
        result_data
        and isinstance(result_data.get("dspslPbanc"), dict)
        and isinstance(result_data["dspslPbanc"].get("pbancInfo"), dict)
    ):
        nested_pbanc = result_data["dspslPbanc"]["pbancInfo"]

    if nested_pbanc and isinstance(nested_pbanc.get("lst"), list):
        rows = nested_pbanc["lst"]
    else:
        rows = _list_at(data, "dlt_gnrlPbancLst")

    notice_meta = {
        "courtCode": null_if_blank(meta.get("cortOfcCd")),
        "saleDate": format_ymd(meta.get("dspslDxdyYmd")),
        "bidStartDate": format_ymd(meta.get("bidBgngYmd")),
        "bidEndDate": format_ymd(meta.get("bidEndYmd")),
        "judgeDeptCode": null_if_blank(meta.get("jdbnCd")),
        "judgeDeptName": (
            null_if_blank(meta.get("cortAuctnJdbnNm"))
            or null_if_blank(nested_pbanc.get("chargDept") if nested_pbanc else None)
        ),
        "judgeDeptPhone": null_if_blank(meta.get("jdbnTelno")),
        "salePlace": null_if_blank(meta.get("dspslPlcNm")),
        "saleTimes": collect_sale_times(meta),
        "bidTypeCode": null_if_blank(meta.get("bidDvsCd")),
        "bidTypeName": describe_bid_type_code(null_if_blank(meta.get("bidDvsCd")) or "") or None,
    }
    items = [normalize_notice_detail_row(r, include_raw) for r in rows]
    result = {"notice": notice_meta, "count": len(items), "items": items}
    if include_raw:
        result["raw"] = (
            {"inputData": dict(meta), "pbancInfo": dict(nested_pbanc)}
            if nested_pbanc
            else {"dma_srchGnrlPbanc": dict(meta)}
        )
    return result


# --- 법원사무소코드 ---


def normalize_court_codes_response(raw_payload):
    data = _data_of(raw_payload)
    rows = _list_at(data, "result")
    items = []
    for raw in rows:
        r = _ensure_row(raw)
        items.append(
            {
                "code": null_if_blank(r.get("cortOfcCd")),
                "name": null_if_blank(r.get("cortOfcNm")),
                "branchName": null_if_blank(r.get("cortSptNm")),
            }
        )
    return {"count": len(items), "items": items}


# --- Workflow B: 사건 단건 ---


def normalize_case_detail_response(raw_payload, *, include_raw=True):
    data = _data_of(raw_payload)
    status = raw_payload.get("status") if isinstance(raw_payload, dict) and isinstance(raw_payload.get("status"), int) else None
    message = raw_payload.get("message") if isinstance(raw_payload, dict) and isinstance(raw_payload.get("message"), str) else None

    if not data or not data.get("dma_csBasInf"):
        out = {
            "found": False,
            "status": status,
            "message": message,
            "caseInfo": None,
            "items": [],
            "schedule": [],
            "claimDeadline": None,
            "relatedCases": [],
            "appeals": [],
            "stakeholders": [],
        }
        if include_raw:
            out["raw"] = raw_payload if isinstance(raw_payload, dict) else None
        return out

    basis = data["dma_csBasInf"]
    case_info = {
        "courtCode": null_if_blank(basis.get("cortOfcCd")),
        "courtName": null_if_blank(basis.get("cortOfcNm")),
        "courtBranchName": null_if_blank(basis.get("cortSptNm")),
        "caseNumber": null_if_blank(basis.get("csNo")),
        "caseName": null_if_blank(basis.get("csNm")),
        "caseReceiptDate": format_ymd(basis.get("csRcptYmd")),
        "caseStartDate": format_ymd(basis.get("csCmdcYmd")),
        "claimAmount": parse_amount(basis.get("clmAmt")),
        "appealFlag": null_if_blank(basis.get("rletApalYn")),
        "suspensionStatusCode": null_if_blank(basis.get("auctnSuspStatCd")),
        "finalDispositionCode": null_if_blank(basis.get("ultmtDvsCd")),
        "finalDispositionDate": format_ymd(basis.get("csUltmtYmd")),
        "progressStatusCode": null_if_blank(basis.get("csProgStatCd")),
        "progressSuspensionReason": null_if_blank(basis.get("csProgSuspRsn")),
        "judgeOrAuxiliaryName": null_if_blank(basis.get("jdgeAojAsstnNm")),
        "judgeDeptCode": null_if_blank(basis.get("jdbnCd")),
        "judgeDeptName": null_if_blank(basis.get("cortAuctnJdbnNm")),
        "judgeDeptPhone": null_if_blank(basis.get("jdbnTelno")),
        "executorOfficePhone": null_if_blank(basis.get("execrCsTelno")),
        "courtTypeCode": null_if_blank(basis.get("cortTypCd")),
        "userCaseNumber": null_if_blank(basis.get("userCsNo")),
        "movableRealEstateCode": null_if_blank(basis.get("mvprpRletDvsCd")),
    }

    items = []
    for raw in _list_at(data, "dlt_rletCsDspslObjctLst"):
        r = _ensure_row(raw)
        items.append(
            {
                "itemSeq": null_if_blank(r.get("dspslObjctSeq")),
                "address": null_if_blank(r.get("userSt")),
                "claimDeadlineDate": format_ymd(r.get("userLstprdYmd")),
                "caseNumber": null_if_blank(r.get("csNo")),
                "courtCode": null_if_blank(r.get("cortOfcCd")),
            }
        )

    schedule = []
    for raw in _list_at(data, "dlt_rletCsGdsDtsDxdyInf"):
        r = _ensure_row(raw)
        schedule.append(
            {
                "itemSeq": null_if_blank(r.get("dspslGdsSeq")),
                "eventSeq": null_if_blank(r.get("dxdySeq")),
                "saleDate": format_ymd(r.get("dspslDxdyYmd")),
                "minimumSalePrice": parse_amount(r.get("lwsDspslPrc")),
                "appraisedPrice": parse_amount(r.get("aeeEvlAmt")),
                "resultCode": null_if_blank(r.get("rsltCd")),
            }
        )

    deadline_rows = _list_at(data, "dlt_dstrtDemnLstprdDts")
    claim_deadline = None
    if deadline_rows:
        first = _ensure_row(deadline_rows[0])
        claim_deadline = {
            "deadlineDate": format_ymd(first.get("dstrtDemnLstprdYmd")),
            "announcementDate": format_ymd(first.get("dstrtDemnLstprdPbancYmd")),
        }

    related_cases = []
    for raw in _list_at(data, "dlt_rletReltCsLst"):
        r = _ensure_row(raw)
        related_cases.append(
            {
                "caseNumber": null_if_blank(r.get("userReltCsNo")) or null_if_blank(r.get("reltCsNo")),
                "courtCode": null_if_blank(r.get("reltCortOfcCd")),
                "courtName": null_if_blank(r.get("cortOfcNm")),
                "courtBranchName": null_if_blank(r.get("cortSptNm")),
                "relationCode": null_if_blank(r.get("reltCsDvsCd")),
            }
        )

    appeals = []
    for raw in _list_at(data, "dlt_csApalRaplDts"):
        r = _ensure_row(raw)
        appeals.append(
            {
                "appellant": null_if_blank(r.get("apalPrpndr")),
                "appealCaseNumber": null_if_blank(r.get("apalCsNo")),
                "appealResult": null_if_blank(r.get("apalRslt")),
                "reAppealCaseNumber": null_if_blank(r.get("raplCsNo")),
                "reAppealResult": null_if_blank(r.get("raplRslt")),
                "filedDate": format_ymd(r.get("printApalAplyYmd")),
                "confirmationFlag": null_if_blank(r.get("cfmtnYnRslt")),
            }
        )

    stakeholders = []
    for raw in _list_at(data, "dlt_rletCsIntrpsLst"):
        r = _ensure_row(raw)
        stakeholders.append(
            {
                "kind": null_if_blank(r.get("auctnIntrpsDvsNm1")) or null_if_blank(r.get("auctnIntrpsDvsNm2")),
                "name": null_if_blank(r.get("intrpsNm1")) or null_if_blank(r.get("intrpsNm2")),
            }
        )

    result = {
        "found": True,
        "status": status,
        "message": message,
        "caseInfo": case_info,
        "items": items,
        "schedule": schedule,
        "claimDeadline": claim_deadline,
        "relatedCases": related_cases,
        "appeals": appeals,
        "stakeholders": stakeholders,
    }
    if include_raw:
        result["raw"] = raw_payload
    return result


# --- Workflow C: 물건 자유검색 ---


def build_address(row):
    parts = [
        strip_html(row.get(key))
        for key in ("hjguSido", "hjguSigu", "hjguDong", "hjguRd", "daepyoLotno", "buldNm")
    ]
    parts = [p for p in parts if p]
    if not parts:
        return strip_html(row.get("realSt")) or strip_html(row.get("printSt"))
    return " ".join(parts)


def normalize_property_search_row(raw_row, include_raw):
    row = _ensure_row(raw_row)
    x = parse_number(row.get("xCordi"))
    y = parse_number(row.get("yCordi"))
    wgs_x = parse_number(row.get("wgs84Xcordi"))
    wgs_y = parse_number(row.get("wgs84Ycordi"))
    item_seq = null_if_blank(row.get("mokmulSer")) or null_if_blank(row.get("maemulSer"))
    out = {
        "caseNumber": null_if_blank(row.get("saNo")),
        "displayCaseNumber": null_if_blank(row.get("srnSaNo")) or null_if_blank(row.get("printCsNo")),
        "itemNumber": item_seq,
        "itemSeq": item_seq,
        "address": build_address(row),
        "appraisedPrice": parse_amount(row.get("gamevalAmt")),
        "minimumSalePrice": parse_amount(row.get("minmaePrice")),
        "flbdCount": parse_amount(row.get("yuchalCnt")) or 0,
        "statusCode": null_if_blank(row.get("mulStatcd")),
        "progressStatusCode": null_if_blank(row.get("jinstatCd")),
        "courtCode": null_if_blank(row.get("boCd")),
        "courtName": null_if_blank(row.get("jiwonNm")),
        "judgeDeptCode": null_if_blank(row.get("jpDeptCd")),
        "judgeDeptName": null_if_blank(row.get("jpDeptNm")),
        "documentId": null_if_blank(row.get("docid")),
        "saleDate": format_ymd(row.get("maeGiil")),
        "salePlace": null_if_blank(row.get("maePlace")),
        "bidTypeCode": null_if_blank(row.get("ipchalGbncd")),
        "usageCodes": {
            "large": null_if_blank(row.get("lclsUtilCd")),
            "medium": null_if_blank(row.get("mclsUtilCd")),
            "small": null_if_blank(row.get("sclsUtilCd")),
        },
        "regionCodes": {
            "sido": null_if_blank(row.get("srchHjguSidoCd")) or null_if_blank(row.get("daepyoSidoCd")),
            "sigungu": null_if_blank(row.get("srchHjguSiguCd")) or null_if_blank(row.get("daepyoSiguCd")),
            "dong": null_if_blank(row.get("srchHjguDongCd")) or null_if_blank(row.get("daepyoDongCd")),
        },
        "coordinates": None if x is None and y is None else {"x": x, "y": y},
        "coordinatesWgs84": None if wgs_x is None and wgs_y is None else {"x": wgs_x, "y": wgs_y},
        "buildingList": strip_html(row.get("buldList")),
        "areaList": strip_html(row.get("areaList")),
        "landCategoryList": strip_html(row.get("jimokList")),
        "propertyDescription": strip_html(row.get("pjbBuldList")),
        "areaRange": {"min": parse_number(row.get("minArea")), "max": parse_number(row.get("maxArea"))},
        "remarks": strip_html(row.get("mulBigo")),
    }
    if include_raw:
        out["raw"] = dict(row)
    return out


def normalize_property_search_response(raw_payload, *, requested_filters=None, include_raw=True):
    data = _data_of(raw_payload)
    page_info = data.get("dma_pageInfo") if isinstance(data, dict) and isinstance(data.get("dma_pageInfo"), dict) else {}
    rows = _list_at(data, "dlt_srchResult")
    items = [normalize_property_search_row(r, include_raw) for r in rows]
    return {
        "requestedFilters": requested_filters,
        "page": {
            "pageNo": parse_amount(page_info.get("pageNo")) or 1,
            "pageSize": parse_amount(page_info.get("pageSize")) or len(items),
            "totalCount": parse_amount(page_info.get("totalCnt")) or len(items),
            "totalYn": null_if_blank(page_info.get("totalYn")),
            "groupTotalCount": parse_amount(page_info.get("groupTotalCount")),
        },
        "count": len(items),
        "items": items,
    }
