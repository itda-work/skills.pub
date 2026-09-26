"""가격지수·시세 통계 수집기.

한국부동산원 R-ONE 주간/월간 가격지수·전월세전환율 수집 + realty-deals 파생 통계.
KB 데이터허브는 공식 API가 없으므로 ToS-safe 파일/허용적 다운로드 경로만 사용하며
KB 사이트 스크래핑은 수행하지 않는다 (R21).

공개 API:
    PriceStatsAPIError  -- 이 모듈의 예외 클래스
    RONE_INDEX_TYPES    -- 지원하는 R-ONE 지수 유형
    RONE_BASE_URL       -- R-ONE API 기본 URL
    fetch_rone_index    -- R-ONE 가격지수 수집 (R19)
    derive_stats_from_deals -- realty-deals raw 파생 통계 (R20)
    build_stats_envelope    -- JSON envelope 생성
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 한국부동산원 R-ONE API 기본 URL
# https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do
RONE_BASE_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

# 지원하는 R-ONE 지수 유형 → 통계표 코드
RONE_INDEX_TYPES: dict[str, dict[str, str]] = {
    "weekly": {"tbl_id": "HPIWK", "label": "주간 아파트 가격지수"},
    "monthly": {"tbl_id": "HPIMON", "label": "월간 아파트 가격지수"},
    "jeonse_rate": {"tbl_id": "JRRATE", "label": "전월세전환율"},
}

_TIMEOUT = 15


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class PriceStatsAPIError(Exception):
    """가격통계 API 오류."""


# ---------------------------------------------------------------------------
# 내부 HTTP 유틸
# ---------------------------------------------------------------------------

def _fetch_rone_json(
    api_key: str,
    tbl_id: str,
    start_ym: str,
    end_ym: str,
) -> dict[str, Any]:
    """R-ONE API에서 통계 데이터를 JSON으로 가져온다.

    Args:
        api_key:  R-ONE API 키.
        tbl_id:   통계표 코드.
        start_ym: 시작 연월 (YYYYMM).
        end_ym:   종료 연월 (YYYYMM).

    Returns:
        R-ONE API 응답 JSON.

    Raises:
        PriceStatsAPIError: HTTP 오류 또는 응답 형식 오류.
    """
    params = {
        "apiKey": api_key,
        "statbl_id": tbl_id,
        "strtYymm": start_ym,
        "endYymm": end_ym,
        "format": "json",
    }
    url = RONE_BASE_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            raw = resp.read()
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        raise PriceStatsAPIError(f"R-ONE HTTP 오류: {e.code}") from e
    except urllib.error.URLError as e:
        raise PriceStatsAPIError(f"R-ONE 네트워크 오류: {e.reason}") from e
    except (json.JSONDecodeError, ValueError) as e:
        raise PriceStatsAPIError(f"R-ONE 응답 파싱 오류: {e}") from e


# ---------------------------------------------------------------------------
# 공개 API — R-ONE 지수 수집 (R19)
# ---------------------------------------------------------------------------

def fetch_rone_index(
    api_key: str,
    index_type: str,
    start_ym: str,
    end_ym: str,
) -> list[dict[str, Any]]:
    """한국부동산원 R-ONE 가격지수·전월세전환율을 수집한다.

    Args:
        api_key:    R-ONE API 키.
        index_type: RONE_INDEX_TYPES 키 (예: "weekly", "monthly", "jeonse_rate").
        start_ym:   시작 연월 (YYYYMM).
        end_ym:     종료 연월 (YYYYMM).

    Returns:
        [{"index_type": ..., "period": ..., "value": ...}, ...] 리스트.

    Raises:
        KeyError:           알 수 없는 index_type.
        PriceStatsAPIError: API 오류.
    """
    if index_type not in RONE_INDEX_TYPES:
        raise KeyError(f"지원하지 않는 지수 유형: {index_type}. 지원: {list(RONE_INDEX_TYPES)}")

    info = RONE_INDEX_TYPES[index_type]
    raw = _fetch_rone_json(api_key, tbl_id=info["tbl_id"],
                           start_ym=start_ym, end_ym=end_ym)

    # R-ONE API 응답은 statisticsData 키 아래에 있거나 리스트 직접
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = raw.get("statisticsData", [])
    else:
        rows = []

    if isinstance(rows, dict):
        rows = [rows]

    result = []
    for row in rows:
        period = str(row.get("PRD_DE", "")).strip()
        value_str = str(row.get("DT", "0")).replace(",", "").strip()
        try:
            value = float(value_str) if value_str else 0.0
        except ValueError:
            value = 0.0
        result.append({
            "index_type": index_type,
            "period": period,
            "value": value,
        })

    return result


# ---------------------------------------------------------------------------
# 공개 API — realty-deals 파생 통계 (R20)
# ---------------------------------------------------------------------------

def derive_stats_from_deals(
    items: list[dict[str, Any]],
    amount_field: str = "deal_amount",
    group_by: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """realty-deals raw 데이터에서 파생 통계를 산출한다.

    compute_summary 포팅 (realestate_api.py 498-529, data_go_client.py).
    정규화된 deal_amount 필드 기준으로 통계를 산출한다.

    Args:
        items:        normalize_trade_item() 정규화 항목 리스트.
        amount_field: 금액 필드명 (기본: "deal_amount").
        group_by:     그룹핑 기준 필드 (예: "apt_nm"). None이면 전체 통계.

    Returns:
        group_by=None: {"avg": N, "median": N, "max": N, "min": N, "count": N}
        group_by=field: {그룹값: 통계 dict, ...}
    """
    if group_by is not None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            key = str(item.get(group_by, ""))
            groups.setdefault(key, []).append(item)
        return {
            k: _compute_stats_from_list(v, amount_field)
            for k, v in groups.items()
        }

    return _compute_stats_from_list(items, amount_field)


def _compute_stats_from_list(
    items: list[dict[str, Any]],
    amount_field: str,
) -> dict[str, Any]:
    """항목 리스트에서 기술 통계를 계산한다."""
    if not items:
        return {"avg": 0, "median": 0, "max": 0, "min": 0, "count": 0}

    amounts = sorted(
        int(item.get(amount_field, 0) or 0)
        for item in items
    )
    n = len(amounts)
    total = sum(amounts)
    avg = total // n if n else 0

    mid = n // 2
    if n % 2 == 1:
        median = amounts[mid]
    else:
        median = (amounts[mid - 1] + amounts[mid]) // 2

    return {
        "avg": avg,
        "median": median,
        "max": amounts[-1],
        "min": amounts[0],
        "count": n,
    }


# ---------------------------------------------------------------------------
# JSON envelope
# ---------------------------------------------------------------------------

def build_stats_envelope(
    status: str,
    items: list[dict[str, Any]],
    *,
    derived_summary: dict[str, Any] | None = None,
    error: str | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """가격통계 JSON envelope 생성.

    Args:
        status:          "ok" 또는 에러 상태.
        items:           R-ONE 지수 항목 리스트.
        derived_summary: realty-deals 파생 통계 (선택).
        error:           에러 코드 (선택).
        detail:          에러 상세 (선택).
        **extra:         추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "count": len(items),
        "results": items,
    }

    if derived_summary is not None:
        env["derived_summary"] = derived_summary

    if error is not None:
        env["error"] = error
    if detail is not None:
        env["detail"] = detail

    env.update(extra)
    return env
