"""국토교통부 실거래가 통합 수집기 — 12개 유형 + 다중 페이지네이션.

구 itda-gov 팩 realestate 스킬(collect_realestate.py)의
page=1 단일 호출 절단 버그(cmd_trade ~103-107)를 교정한 상위호환 구현.

공개 API:
    ENDPOINT_MAP            -- 12개 엔드포인트 유형 매핑 테이블
    month_range             -- 시작월~종료월 YYYYMM 리스트 생성기
    collect_deals_for_month -- 단일 월·단일 엔드포인트 수집 (페이지네이션 포함)
    collect_deals_range     -- 다월 루프 수집
    normalize_trade_item    -- 매매 항목 snake_case 정규화
    normalize_rent_item     -- 전월세 항목 snake_case 정규화
    build_envelope          -- JSON envelope 생성
    items_to_csv            -- items → CSV 문자열
    save_results            -- .json + .csv 저장
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

# RealEstateAPIError·compute_summary는 deals_cli.py가 import하는 의도된 재노출 (ruff F401 제외)
from data_go_client import (  # noqa: F401
    RealEstateAPIError,
    compute_summary,
    fetch_xml,
    parse_amount,
)

# ---------------------------------------------------------------------------
# 12개 엔드포인트 유형 매핑 테이블 (R10)
# ---------------------------------------------------------------------------
# 형식: { endpoint_key: {"url": ..., "service_name": ..., "deal_type": "trade"|"rent"} }
#
# 국토부 data.go.kr 실거래가 서비스 12종:
#   8 부동산 유형 × (매매 + 전월세) = 16 조합이지만
#   토지·상업업무용·공장창고·분양입주권은 전월세(rent) API 미제공 → 12개
#
#   매매(trade) 8종: 아파트, 오피스텔, 연립다세대, 단독다가구,
#                    토지, 상업업무용, 공장창고, 분양입주권
#   전월세(rent) 4종: 아파트, 오피스텔, 연립다세대, 단독다가구

_BASE_URL = "https://apis.data.go.kr/1613000"

ENDPOINT_MAP: dict[str, dict[str, str]] = {
    # ---- 매매 (trade) 8종 ----
    "apt_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
        "service_name": "RTMSDataSvcAptTrade",
        "deal_type": "trade",
        "prop_label": "아파트",
        "apply_url": "https://www.data.go.kr/data/15126469/openapi.do",
    },
    "offi_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
        "service_name": "RTMSDataSvcOffiTrade",
        "deal_type": "trade",
        "prop_label": "오피스텔",
        "apply_url": "https://www.data.go.kr/data/15126464/openapi.do",
    },
    "rh_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
        "service_name": "RTMSDataSvcRHTrade",
        "deal_type": "trade",
        "prop_label": "연립다세대",
        "apply_url": "https://www.data.go.kr/data/15058017/openapi.do",
    },
    "sh_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
        "service_name": "RTMSDataSvcSHTrade",
        "deal_type": "trade",
        "prop_label": "단독다가구",
        "apply_url": "https://www.data.go.kr/data/15058022/openapi.do",
    },
    "land_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
        "service_name": "RTMSDataSvcLandTrade",
        "deal_type": "trade",
        "prop_label": "토지",
        "apply_url": "https://www.data.go.kr/data/15126472/openapi.do",
    },
    "biz_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
        "service_name": "RTMSDataSvcNrgTrade",
        "deal_type": "trade",
        "prop_label": "상업업무용",
        "apply_url": "https://www.data.go.kr/data/15126471/openapi.do",
    },
    "factory_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcFctTrade/getRTMSDataSvcFctTrade",
        "service_name": "RTMSDataSvcFctTrade",
        "deal_type": "trade",
        "prop_label": "공장창고",
        "apply_url": "https://www.data.go.kr/data/15055660/openapi.do",
    },
    "presale_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade",
        "service_name": "RTMSDataSvcSilvTrade",
        "deal_type": "trade",
        "prop_label": "분양입주권",
        "apply_url": "https://www.data.go.kr/data/15126467/openapi.do",
    },
    # ---- 전월세 (rent) 4종 ----
    "apt_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
        "service_name": "RTMSDataSvcAptRent",
        "deal_type": "rent",
        "prop_label": "아파트",
        "apply_url": "https://www.data.go.kr/data/15126474/openapi.do",
    },
    "offi_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
        "service_name": "RTMSDataSvcOffiRent",
        "deal_type": "rent",
        "prop_label": "오피스텔",
        "apply_url": "https://www.data.go.kr/data/15126475/openapi.do",
    },
    "rh_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
        "service_name": "RTMSDataSvcRHRent",
        "deal_type": "rent",
        "prop_label": "연립다세대",
        "apply_url": "https://www.data.go.kr/data/15058020/openapi.do",
    },
    "sh_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
        "service_name": "RTMSDataSvcSHRent",
        "deal_type": "rent",
        "prop_label": "단독다가구",
        "apply_url": "https://www.data.go.kr/data/15058023/openapi.do",
    },
}


# ---------------------------------------------------------------------------
# 월 범위 유틸리티
# ---------------------------------------------------------------------------

def month_range(start_ymd: str, end_ymd: str):
    """시작월~종료월(YYYYMM) 범위의 월 목록을 순서대로 생성한다.

    Args:
        start_ymd: 시작 연월 (YYYYMM, 예: "202601").
        end_ymd: 종료 연월 (YYYYMM, 예: "202606").

    Yields:
        YYYYMM 형식의 문자열.
    """
    start_y = int(start_ymd[:4])
    start_m = int(start_ymd[4:6])
    end_y = int(end_ymd[:4])
    end_m = int(end_ymd[4:6])

    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# 단일 월·엔드포인트 수집 (페이지네이션 루프 포함)
# ---------------------------------------------------------------------------

# @MX:WARN: [AUTO] 다중 페이지네이션 루프 -- 절단 버그 재발 위험 구역.
# @MX:REASON: 기존 realestate cmd_trade(~103-107)는 page=1만 요청하여
#             totalCount>numOfRows인 경우 나머지 데이터를 사용자에게
#             무음(silent)으로 유실했다. 이 루프가 totalCount 전량을 보장한다.
#             절대로 단일 페이지 fetch로 대체하지 말 것.
def collect_deals_for_month(
    api_key: str,
    lawd_cd: str,
    deal_ymd: str,
    endpoint_key: str,
    *,
    rows_per_page: int = 100,
) -> list[dict[str, Any]]:
    """단일 월·단일 엔드포인트에 대해 전량 페이지네이션 수집.

    totalCount > numOfRows인 경우에도 모든 페이지를 순회하여 절단 없이 전량 수집한다.
    (기존 page=1 절단 버그 교정 — spec.md §5 @MX:WARN 대상)

    Args:
        api_key: 공공데이터포털 API 키.
        lawd_cd: 법정동코드 5자리.
        deal_ymd: 계약년월 (YYYYMM).
        endpoint_key: ENDPOINT_MAP 키 (예: "apt_trade", "rh_rent").
        rows_per_page: 페이지당 행 수 (기본 100).

    Returns:
        해당 월의 모든 거래 항목 리스트.

    Raises:
        KeyError: 알 수 없는 endpoint_key.
        RealEstateAPIError: API 오류 발생 시.
    """
    ep = ENDPOINT_MAP[endpoint_key]
    url = ep["url"]
    apply_url = ep.get("apply_url")

    all_items: list[dict[str, Any]] = []
    page = 1

    while True:
        params = {
            "serviceKey": api_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": str(page),
            "numOfRows": str(rows_per_page),
        }

        result = fetch_xml(url, params, apply_url=apply_url)
        all_items.extend(result["items"])

        total_count = result["total_count"]
        fetched_so_far = len(all_items)

        # 전량 수집 완료 조건
        if fetched_so_far >= total_count or not result["items"]:
            break

        page += 1

    return all_items


# ---------------------------------------------------------------------------
# 다월 루프 수집
# ---------------------------------------------------------------------------

def collect_deals_range(
    api_key: str,
    lawd_cd: str,
    start_ymd: str,
    end_ymd: str,
    endpoint_key: str,
    *,
    rows_per_page: int = 100,
) -> list[dict[str, Any]]:
    """시작월~종료월 범위에 대해 전월 수집한다.

    Args:
        api_key: 공공데이터포털 API 키.
        lawd_cd: 법정동코드 5자리.
        start_ymd: 시작 연월 (YYYYMM).
        end_ymd: 종료 연월 (YYYYMM).
        endpoint_key: ENDPOINT_MAP 키.
        rows_per_page: 페이지당 행 수.

    Returns:
        전 기간 거래 항목 통합 리스트.
    """
    all_items: list[dict[str, Any]] = []
    for ymd in month_range(start_ymd, end_ymd):
        items = collect_deals_for_month(
            api_key=api_key,
            lawd_cd=lawd_cd,
            deal_ymd=ymd,
            endpoint_key=endpoint_key,
            rows_per_page=rows_per_page,
        )
        all_items.extend(items)
    return all_items


# ---------------------------------------------------------------------------
# 정규화 (collect_realestate.py 41-88 snake_case 패턴 포팅)
# ---------------------------------------------------------------------------

def _normalize_common_fields(item: dict[str, str]) -> dict[str, Any]:
    """매매·전월세 공통 필드를 snake_case로 정규화.

    아파트는 aptNm, 오피스텔은 offiNm, 연립은 mhouseNm 등 유형별 상이.
    소비자에게 통일된 apt_nm 키로 노출.
    """
    return {
        "apt_nm": (
            item.get("aptNm") or item.get("offiNm") or
            item.get("mhouseNm") or item.get("sggNm") or ""
        ).strip(),
        "exclu_use_ar": item.get("excluUseAr", "").strip(),
        "deal_year": item.get("dealYear", "").strip(),
        "deal_month": item.get("dealMonth", "").strip(),
        "deal_day": item.get("dealDay", "").strip(),
        "floor": item.get("floor", "").strip(),
        "build_year": item.get("buildYear", "").strip(),
        "umd_nm": item.get("umdNm", "").strip(),
        "jibun": item.get("jibun", "").strip(),
    }


def normalize_trade_item(item: dict[str, str]) -> dict[str, Any]:
    """매매 API 응답 항목을 snake_case로 정규화.

    Args:
        item: API 원본 항목.

    Returns:
        정규화된 딕셔너리 (deal_amount 필드 포함).
    """
    return {
        **_normalize_common_fields(item),
        "deal_amount": parse_amount(item.get("dealAmount", "0")),
    }


def normalize_rent_item(item: dict[str, str]) -> dict[str, Any]:
    """전월세 API 응답 항목을 snake_case로 정규화.

    Args:
        item: API 원본 항목.

    Returns:
        정규화된 딕셔너리 (deposit, monthly_rent 필드 포함).
    """
    return {
        **_normalize_common_fields(item),
        "deposit": parse_amount(item.get("deposit", "0")),
        "monthly_rent": parse_amount(item.get("monthlyRent", "0")),
    }


# ---------------------------------------------------------------------------
# 출력 포맷 (collect_realestate.py 117-137 envelope 패턴 포팅)
# ---------------------------------------------------------------------------

def build_envelope(
    status: str,
    region: str,
    items: list[dict[str, Any]],
    lawd_cd: str,
    *,
    summary: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """JSON envelope을 생성한다.

    envelope 스키마: status / region / count / results / [summary]
    (spec.md R13)

    Args:
        status: "ok" 또는 에러 상태.
        region: 한글 지역명.
        items: 수집된 거래 항목 리스트.
        lawd_cd: 법정동코드.
        summary: 요약 통계 (선택).
        **extra: 추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "region": region,
        "lawd_cd": lawd_cd,
        "count": len(items),
        "results": items,
    }
    if summary is not None:
        env["summary"] = summary
    env.update(extra)
    return env


# ---------------------------------------------------------------------------
# CSV 변환
# ---------------------------------------------------------------------------

# CSV 출력 시 사용할 기본 컬럼 순서
_TRADE_CSV_FIELDS = [
    "apt_nm", "deal_amount", "deal_year", "deal_month", "deal_day",
    "exclu_use_ar", "floor", "build_year", "umd_nm", "jibun",
]

_RENT_CSV_FIELDS = [
    "apt_nm", "deposit", "monthly_rent", "deal_year", "deal_month", "deal_day",
    "exclu_use_ar", "floor", "build_year", "umd_nm", "jibun",
]


def items_to_csv(
    items: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> str:
    """items 리스트를 CSV 문자열로 변환한다.

    Args:
        items: 거래 항목 리스트.
        fields: CSV 컬럼 순서. None이면 첫 항목의 키 또는 기본 필드 사용.

    Returns:
        CSV 형식 문자열 (헤더 포함).
    """
    if fields is None:
        if items:
            fields = list(items[0].keys())
        else:
            fields = _TRADE_CSV_FIELDS

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(item)
    return output.getvalue()


# ---------------------------------------------------------------------------
# 결과 저장 (.json + .csv)
# ---------------------------------------------------------------------------

def save_results(
    envelope: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    base_path: str,
) -> tuple[str, str]:
    """JSON envelope과 CSV를 파일로 저장한다.

    Args:
        envelope: JSON envelope 딕셔너리.
        items: 거래 항목 리스트 (CSV 저장용).
        base_path: 파일 기반 경로 (확장자 없이). .json / .csv가 자동 부여된다.

    Returns:
        (json_path, csv_path) 튜플.
    """
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)

    json_path = str(base) + ".json"
    csv_path = str(base) + ".csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    csv_str = items_to_csv(items)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_str)

    return json_path, csv_path
