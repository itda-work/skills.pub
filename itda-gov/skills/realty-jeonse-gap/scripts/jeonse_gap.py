"""전세가율·갭 스크리너 — 매매×전월세 조인 + 임계값 필터.

realty-deals raw 데이터를 단지·면적 키로 조인하여
전세가율(전세보증금/매매가×100)과 갭(매매가-전세보증금)을 산출한다.

공개 API:
    join_trade_rent       -- 매매×전월세 단지·면적 조인
    compute_gap_stats     -- 전세가율·갭 산출
    filter_by_threshold   -- 임계값 스크린 필터
    build_gap_envelope    -- JSON envelope 생성
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# 조인 키 유틸
# ---------------------------------------------------------------------------

def _join_key(item: dict[str, Any]) -> str:
    """단지명 + 전용면적 기준 조인 키."""
    apt_nm = str(item.get("apt_nm", "")).strip()
    area = str(item.get("exclu_use_ar", "")).strip()
    return f"{apt_nm}||{area}"


# ---------------------------------------------------------------------------
# join_trade_rent — 매매×전월세 조인 (R15, AC-3)
# ---------------------------------------------------------------------------

def join_trade_rent(
    trade_items: list[dict[str, Any]],
    rent_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """매매 항목과 전월세 항목을 단지·면적 기준으로 조인한다.

    같은 단지·면적에 전월세 복수 건이 있으면 최고 전세보증금을 사용한다.

    Args:
        trade_items: 정규화된 매매 거래 항목 리스트.
        rent_items:  정규화된 전월세 거래 항목 리스트.

    Returns:
        조인된 항목 리스트. 조인 실패 항목은 제외된다.
    """
    if not trade_items or not rent_items:
        return []

    # 전월세 항목을 키별로 그룹핑 (최고 전세가 유지)
    rent_by_key: dict[str, dict[str, Any]] = {}
    for r in rent_items:
        key = _join_key(r)
        existing = rent_by_key.get(key)
        if existing is None or r.get("deposit", 0) > existing.get("deposit", 0):
            rent_by_key[key] = r

    # 매매 항목마다 전월세 항목 찾아 조인
    result = []
    for t in trade_items:
        key = _join_key(t)
        rent = rent_by_key.get(key)
        if rent is None:
            continue
        joined = dict(t)
        joined["deposit"] = rent.get("deposit", 0)
        joined["monthly_rent"] = rent.get("monthly_rent", 0)
        result.append(joined)

    return result


# ---------------------------------------------------------------------------
# compute_gap_stats — 전세가율·갭 산출 (R15)
# ---------------------------------------------------------------------------

def compute_gap_stats(
    joined_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """조인된 항목에서 전세가율과 갭을 산출한다.

    전세가율 = 전세보증금 / 매매가 × 100 (매매가 0이면 0.0)
    갭       = 매매가 − 전세보증금

    Args:
        joined_items: join_trade_rent() 결과 리스트.

    Returns:
        전세가율(jeonse_ratio)·갭(gap) 필드가 추가된 항목 리스트.
    """
    result = []
    for item in joined_items:
        deal_amount = item.get("deal_amount", 0) or 0
        deposit = item.get("deposit", 0) or 0

        if deal_amount > 0:
            jeonse_ratio = round(deposit / deal_amount * 100, 2)
        else:
            jeonse_ratio = 0.0

        gap = deal_amount - deposit

        enriched = dict(item)
        enriched["jeonse_ratio"] = jeonse_ratio
        enriched["gap"] = gap
        result.append(enriched)

    return result


# ---------------------------------------------------------------------------
# filter_by_threshold — 임계값 스크린 필터 (R16, AC-3)
# ---------------------------------------------------------------------------

def filter_by_threshold(
    items: list[dict[str, Any]],
    *,
    min_jeonse_ratio: float | None = None,
    max_gap: int | None = None,
) -> list[dict[str, Any]]:
    """전세가율·갭 임계값으로 항목을 필터링한다.

    Args:
        items:             compute_gap_stats() 결과 리스트.
        min_jeonse_ratio:  최소 전세가율(%). 미설정 시 필터 없음.
        max_gap:           최대 갭(만원). 미설정 시 필터 없음.

    Returns:
        조건을 만족하는 항목만 포함한 리스트.
    """
    result = items
    if min_jeonse_ratio is not None:
        result = [x for x in result if x.get("jeonse_ratio", 0) >= min_jeonse_ratio]
    if max_gap is not None:
        result = [x for x in result if x.get("gap", float("inf")) <= max_gap]
    return result


# ---------------------------------------------------------------------------
# build_gap_envelope — JSON envelope
# ---------------------------------------------------------------------------

def build_gap_envelope(
    status: str,
    region: str,
    items: list[dict[str, Any]],
    *,
    min_jeonse_ratio: float | None = None,
    max_gap: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """전세가율·갭 스크리닝 결과 JSON envelope 생성.

    Args:
        status:           "ok" 또는 에러 상태.
        region:           한글 지역명.
        items:            결과 항목 리스트.
        min_jeonse_ratio: 적용된 전세가율 필터 (선택).
        max_gap:          적용된 갭 필터 (선택).
        **extra:          추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "region": region,
        "count": len(items),
        "results": items,
    }
    filters: dict[str, Any] = {}
    if min_jeonse_ratio is not None:
        filters["min_jeonse_ratio"] = min_jeonse_ratio
    if max_gap is not None:
        filters["max_gap"] = max_gap
    if filters:
        env["filters"] = filters
    env.update(extra)
    return env
