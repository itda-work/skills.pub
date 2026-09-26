"""공급·청약 데이터 수집기.

KOSIS 기반 미분양·인허가·착공·준공·입주 timeseries 와
청약홈(data.go.kr) 기반 청약경쟁률·분양·당첨 데이터를 수집한다.

공개 API:
    SupplyAPIError             -- 이 모듈의 예외 클래스
    KOSIS_INDICATORS           -- 지원하는 KOSIS 지표 키 목록
    SUBSCRIPTION_DATA_START_YM -- 청약경쟁률 데이터 시작점 (R18, AC-4)
    fetch_kosis_supply         -- KOSIS API 지표 수집
    fetch_subscription         -- 청약홈 경쟁률·분양·당첨 수집
    build_supply_envelope      -- JSON envelope 생성
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 청약경쟁률 데이터 시작점 (R18, AC-4 — 이전 구간 보간 금지)
SUBSCRIPTION_DATA_START_YM = "202002"

# 지원하는 KOSIS 지표 키 → (통계표ID, 분류코드)
# KOSIS 통계 데이터 API: https://kosis.kr/openapi/
KOSIS_INDICATORS: dict[str, dict[str, str]] = {
    "unsold":     {"orgId": "116", "tblId": "DT_MLTM_5209", "label": "미분양"},
    "permitted":  {"orgId": "116", "tblId": "DT_MLTM_5140", "label": "인허가"},
    "started":    {"orgId": "116", "tblId": "DT_MLTM_5141", "label": "착공"},
    "completed":  {"orgId": "116", "tblId": "DT_MLTM_5142", "label": "준공"},
}

# 청약홈 API 기본 URL (data.go.kr)
_SUBSCRIPTION_API_URL = (
    "https://apis.data.go.kr/B552555/APTInfoSearchService2/getAPTLttotPblancDetail"
)

# KOSIS API 기본 URL
_KOSIS_API_URL = "https://kosis.kr/openapi/Param/statisticsParamData.do"

_TIMEOUT = 15


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class SupplyAPIError(Exception):
    """공급·청약 API 오류."""


# ---------------------------------------------------------------------------
# 내부 HTTP 유틸
# ---------------------------------------------------------------------------

def _fetch_kosis_json(
    api_key: str,
    org_id: str,
    tbl_id: str,
    start_ym: str,
    end_ym: str,
) -> list[dict[str, Any]]:
    """KOSIS API에서 통계 데이터를 JSON으로 가져온다.

    Args:
        api_key: KOSIS API 키.
        org_id:  기관 ID.
        tbl_id:  통계표 ID.
        start_ym: 시작 연월 (YYYYMM).
        end_ym:   종료 연월 (YYYYMM).

    Returns:
        KOSIS API 응답 JSON 리스트.

    Raises:
        SupplyAPIError: HTTP 오류 또는 응답 형식 오류.
    """
    params = {
        "method": "getList",
        "apiKey": api_key,
        "itmId": "T10+",
        "objL1": "ALL",
        "format": "json",
        "jsonVD": "Y",
        "prdSe": "M",
        "startPrdDe": start_ym,
        "endPrdDe": end_ym,
        "orgId": org_id,
        "tblId": tbl_id,
    }
    url = _KOSIS_API_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            raw = resp.read()
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        raise SupplyAPIError(f"KOSIS HTTP 오류: {e.code}") from e
    except urllib.error.URLError as e:
        raise SupplyAPIError(f"KOSIS 네트워크 오류: {e.reason}") from e
    except (json.JSONDecodeError, ValueError) as e:
        raise SupplyAPIError(f"KOSIS 응답 파싱 오류: {e}") from e


def _fetch_subscription_xml(
    api_key: str,
    start_ym: str,
    end_ym: str,
) -> dict[str, Any]:
    """청약홈 API에서 XML 데이터를 가져온다.

    Returns:
        {"items": [...], "total_count": N}
    """
    # 청약홈 API는 yyyy-MM 형식 사용
    start_date = f"{start_ym[:4]}-{start_ym[4:6]}"
    end_date = f"{end_ym[:4]}-{end_ym[4:6]}"
    params = {
        "serviceKey": api_key,
        "startDate": start_date,
        "endDate": end_date,
        "pageNo": "1",
        "numOfRows": "100",
    }
    url = _SUBSCRIPTION_API_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise SupplyAPIError(f"청약홈 HTTP 오류: {e.code}") from e
    except urllib.error.URLError as e:
        raise SupplyAPIError(f"청약홈 네트워크 오류: {e.reason}") from e

    return _parse_subscription_xml(raw)


def _parse_subscription_xml(xml_bytes: bytes) -> dict[str, Any]:
    """청약홈 XML 응답을 파싱한다."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise SupplyAPIError(f"청약홈 XML 파싱 실패: {e}") from e

    body = root.find("body")
    if body is None:
        return {"items": [], "total_count": 0}

    total_el = body.find("totalCount")
    total_count = int(total_el.text or "0") if total_el is not None else 0

    items = []
    items_el = body.find("items")
    if items_el is not None:
        for item_el in items_el.findall("item"):
            item = {child.tag: (child.text or "").strip() for child in item_el}
            items.append(item)

    return {"items": items, "total_count": total_count}


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def fetch_kosis_supply(
    api_key: str,
    indicator: str,
    start_ym: str,
    end_ym: str,
) -> list[dict[str, Any]]:
    """KOSIS에서 공급 지표 timeseries를 수집한다.

    Args:
        api_key:   KOSIS API 키.
        indicator: KOSIS_INDICATORS 키 (예: "unsold", "permitted").
        start_ym:  시작 연월 (YYYYMM).
        end_ym:    종료 연월 (YYYYMM).

    Returns:
        [{"indicator": ..., "period": ..., "value": ...}, ...] 리스트.

    Raises:
        KeyError:       알 수 없는 indicator.
        SupplyAPIError: API 오류.
    """
    if indicator not in KOSIS_INDICATORS:
        raise KeyError(f"지원하지 않는 지표: {indicator}. 지원: {list(KOSIS_INDICATORS)}")

    info = KOSIS_INDICATORS[indicator]
    raw = _fetch_kosis_json(
        api_key,
        org_id=info["orgId"],
        tbl_id=info["tblId"],
        start_ym=start_ym,
        end_ym=end_ym,
    )

    result = []
    for row in raw:
        period = str(row.get("PRD_DE", "")).strip()
        value_str = str(row.get("DT", "0")).replace(",", "").strip()
        try:
            value = int(float(value_str)) if value_str else 0
        except ValueError:
            value = 0
        result.append({"indicator": indicator, "period": period, "value": value})

    return result


def fetch_subscription(
    api_key: str,
    start_ym: str,
    end_ym: str,
) -> list[dict[str, Any]]:
    """청약홈 경쟁률·분양·당첨 데이터를 수집한다.

    청약경쟁률 데이터 시작점: SUBSCRIPTION_DATA_START_YM (2020-02).
    그 이전 구간은 보간하지 않는다 (R18).

    Args:
        api_key:   공공데이터포털 API 키 (KO_DATA_API_KEY).
        start_ym:  시작 연월 (YYYYMM).
        end_ym:    종료 연월 (YYYYMM).

    Returns:
        청약 항목 정규화 리스트.
    """
    result_raw = _fetch_subscription_xml(api_key, start_ym, end_ym)
    items = result_raw.get("items", [])

    normalized = []
    for item in items:
        normalized.append({
            "house_nm": item.get("houseNm", "").strip(),
            "rcrit_pblanc_de": item.get("rcritPblancDe", "").strip(),
            "cmptt_rate": item.get("cmpttRate", "0").strip(),
            "tot_suply_hshldco": item.get("totSuplyHshldco", "0").strip(),
        })

    return normalized


# ---------------------------------------------------------------------------
# JSON envelope
# ---------------------------------------------------------------------------

def build_supply_envelope(
    status: str,
    items: list[dict[str, Any]],
    *,
    start_month: str | None = None,
    subscription_items: list[dict[str, Any]] | None = None,
    error: str | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """공급 데이터 JSON envelope 생성.

    AC-4: meta에 청약경쟁률 데이터 시작점(2020-02)을 명시한다.
    2020-02 이전 start_month 요청 시 경고 메시지를 note에 기재한다.

    Args:
        status: "ok" 또는 에러 상태.
        items:  수집된 공급 지표 항목 리스트.
        start_month: 요청 시작 연월 (선택).
        subscription_items: 청약 데이터 항목 (선택).
        error:  에러 코드 (선택).
        detail: 에러 상세 (선택).
        **extra: 추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "count": len(items),
        "results": items,
        "meta": {
            "subscription_data_start": SUBSCRIPTION_DATA_START_YM,
        },
    }

    # 2020-02 이전 요청 시 경고 추가 (R18, AC-4)
    if start_month and start_month < SUBSCRIPTION_DATA_START_YM:
        env["note"] = (
            f"청약경쟁률 데이터는 {SUBSCRIPTION_DATA_START_YM}부터 제공됩니다. "
            f"요청 시작월({start_month})은 데이터 시작 이전으로, "
            f"해당 구간은 보간 없이 공백으로 처리됩니다."
        )

    if subscription_items is not None:
        env["subscription_count"] = len(subscription_items)
        env["subscription_results"] = subscription_items

    if error is not None:
        env["error"] = error
    if detail is not None:
        env["detail"] = detail

    env.update(extra)
    return env
