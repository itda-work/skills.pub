"""flight-search 비교 스캔 — 월/범위/연도 날짜 생성 + 요청량 가드.

여러 날짜를 실제 조회해 최저가를 비교한다. '날짜당 1회 조회'라 요청이 누적되므로
(daily 월비교 ~30회), 매크로/차단 방지를 위해 일수 cap(MAX_SCAN_DATES)과 요청
간격 하한(MIN_SLEEP_SECONDS)을 코드로 강제한다(ktx 매크로 금지 정신을 조회에 적용).

네트워크 조회는 주입된 search 함수(flights_adapter.search)로 위임하고, 날짜 생성·
cap·집계는 순수하게 둔다(단위 테스트는 가짜 search 주입).
"""
from __future__ import annotations

import statistics
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterator

import format_out as fmt

# 요청량 가드(코드 강제) — 사용자 인자로 더 완화해도 이 한계 아래로 못 간다.
MAX_SCAN_DATES = 31  # 한 번의 비교에서 실제 조회할 최대 날짜 수
MIN_SLEEP_SECONDS = 1.0  # 조회 간 최소 대기(차단·rate limit 완화)
MAX_DESTINATIONS = 8  # 관문 비교(#1025)의 목적지 수 상한
MAX_DEST_QUERIES = 40  # 관문 비교의 총 조회 상한(목적지 × 날짜 샘플)

# search(origin, dest, date, return_date=None, *, adults, seat) -> (raw, band, url)
SearchFn = Callable[..., tuple[list[dict[str, Any]], str, str]]


def iter_dates(start: date, end: date, step_days: int) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=step_days)


def month_dates(month: str, sample: str = "weekly") -> list[date]:
    """'YYYY-MM' 한 달의 날짜들. weekly=7일 간격, daily=매일."""
    start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    step = 1 if sample == "daily" else 7
    return list(iter_dates(start, end, step))


def range_dates(start_s: str, end_s: str, step_days: int) -> list[date]:
    """'YYYY-MM-DD' 범위를 step_days 간격으로."""
    start = datetime.strptime(start_s, "%Y-%m-%d").date()
    end = datetime.strptime(end_s, "%Y-%m-%d").date()
    return list(iter_dates(start, end, step_days))


def year_dates(years: list[int], month_day: str) -> list[date]:
    """여러 연도의 같은 'MM-DD'."""
    return [datetime.strptime(f"{y}-{month_day}", "%Y-%m-%d").date() for y in years]


def cap_dates(dates: list[date]) -> tuple[list[date], int]:
    """MAX_SCAN_DATES 로 자른다. (잘린 수를 호출자가 안내하도록 함께 반환)"""
    capped = list(dates)[:MAX_SCAN_DATES]
    dropped = len(dates) - len(capped)
    return capped, dropped


def scan_dates(
    search: SearchFn,
    origin: str,
    dest: str,
    dates: list[date],
    *,
    adults: int = 1,
    seat: str = "economy",
    limit: int = 5,
    sleep: float = MIN_SLEEP_SECONDS,
    stay: int | None = None,
) -> dict[str, Any]:
    """각 날짜를 실제 조회해 최저가를 모은다. 개별 실패는 row 에 기록(견고).

    stay 지정 시 왕복 모드(#1024): 출발일 d 마다 귀국일 d+stay 로 왕복 1회 조회
    (체류일 고정 슬라이딩). 날짜당 1회 조회는 편도와 동일 — cap·sleep 가드 불변.
    출발×귀국 2D 전수 그리드는 하지 않는다(매크로 금지 계약).
    """
    dates = list(dates)[:MAX_SCAN_DATES]  # 방어적 cap(코드 강제)
    sleep = max(MIN_SLEEP_SECONDS, sleep)  # 요청간격 하한 강제
    rows: list[dict[str, Any]] = []
    for idx, d in enumerate(dates):
        return_iso = (d + timedelta(days=stay)).isoformat() if stay else None
        rows.append(
            _scan_one(
                search, origin, dest, d.isoformat(), return_iso,
                adults=adults, seat=seat, limit=limit,
            )
        )
        if idx != len(dates) - 1:
            time.sleep(sleep)
    return _aggregate(rows, limit)


def _scan_one(
    search: SearchFn,
    origin: str,
    dest: str,
    iso: str,
    return_iso: str | None = None,
    *,
    adults: int,
    seat: str,
    limit: int,
) -> dict[str, Any]:
    """단일 (목적지, 날짜) 조회 → row. 실패는 error row 로(스캔 견고성)."""
    try:
        raw, band, url = search(origin, dest, iso, return_iso, adults=adults, seat=seat)
        summary = fmt.summarize_flights(raw, band=band, booking_url=url, limit=limit)
        row = {
            "date": iso,
            "ok": True,
            "min_price": summary["stats"]["min_price"],
            "avg_price": summary["stats"]["avg_price"],
            "priced_count": summary["stats"]["priced_count"],
            "price_band": summary["meta"]["price_band"],
            "booking_search_url": url,
        }
    except Exception as e:  # noqa: BLE001 — 스캔은 개별 실패에 견고해야
        row = {"date": iso, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    if return_iso:
        row["return_date"] = return_iso
    return row


def scan_destinations(
    search: SearchFn,
    origin: str,
    dests: list[str],
    dates: list[date],
    *,
    adults: int = 1,
    seat: str = "economy",
    limit: int = 5,
    sleep: float = MIN_SLEEP_SECONDS,
) -> dict[str, Any]:
    """같은 날짜(들)를 목적지별로 조회해 관문 최저가를 비교한다(#1025).

    Explore(목적지 자동 발견) 표면이 아니라 호출자가 제시한 후보 열거다. 총 조회
    상한(MAX_DEST_QUERIES)은 날짜 축을 잘라 지킨다(목적지 축 보존 — 관문 비교의
    목적은 목적지 커버리지). 목적지 수 fail-loud 는 호출자(main) 몫이고 여기는
    방어적 cap 만 둔다.
    """
    dests = list(dests)[:MAX_DESTINATIONS]  # 방어적 cap(코드 강제)
    max_dates = max(1, MAX_DEST_QUERIES // max(1, len(dests)))
    dropped_dates = max(0, len(dates) - max_dates)
    dates = list(dates)[:max_dates]
    sleep = max(MIN_SLEEP_SECONDS, sleep)  # 요청간격 하한 강제
    total = len(dests) * len(dates)
    per_dest: list[dict[str, Any]] = []
    n = 0
    for dest in dests:
        rows: list[dict[str, Any]] = []
        for d in dates:
            n += 1
            rows.append(
                _scan_one(
                    search, origin, dest, d.isoformat(),
                    adults=adults, seat=seat, limit=limit,
                )
            )
            if n != total:  # 목적지 경계 포함 모든 조회 사이 대기
                time.sleep(sleep)
        priced = [r for r in rows if r.get("ok") and r.get("min_price") is not None]
        best = min(priced, key=lambda r: r["min_price"]) if priced else None
        prices = [r["min_price"] for r in priced]
        per_dest.append(
            {
                "to": dest,
                "min_price": best["min_price"] if best else None,
                "cheapest_date": best["date"] if best else None,
                "avg_of_daily_min": statistics.mean(prices) if prices else None,
                "successful_dates": len([r for r in rows if r.get("ok")]),
                "sampled_dates": len(rows),
                "booking_search_url": best["booking_search_url"] if best else None,
                "rows": rows,
            }
        )
    ranked = sorted(
        per_dest,
        key=lambda x: (x["min_price"] is None, x["min_price"] or 0),
    )
    return {
        "meta": {
            "provider": fmt.PROVIDER,
            "currency": fmt.CURRENCY,
            "destinations": len(dests),
            "sampled_dates_per_destination": len(dates),
            "total_queries": total,
            **({"dropped_dates": dropped_dates} if dropped_dates else {}),
            "note": fmt.COMPARE_NOTE,
        },
        "destinations": ranked,
    }


def _aggregate(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    prices = [r["min_price"] for r in ok_rows if r.get("min_price") is not None]
    cheapest = sorted(
        (r for r in ok_rows if r.get("min_price") is not None),
        key=lambda r: r["min_price"],
    )[:limit]
    return {
        "meta": {
            "provider": fmt.PROVIDER,
            "currency": fmt.CURRENCY,
            "sampled_dates": len(rows),
            "successful_dates": len(ok_rows),
            "note": fmt.COMPARE_NOTE,
        },
        "stats": {
            "min_price": min(prices) if prices else None,
            "avg_of_daily_min": statistics.mean(prices) if prices else None,
            "max_of_daily_min": max(prices) if prices else None,
        },
        "cheapest_dates": [
            {
                "date": r["date"],
                **({"return_date": r["return_date"]} if r.get("return_date") else {}),
                "min_price": r["min_price"],
                "avg_price": r.get("avg_price"),
                "price_band": r.get("price_band"),
                "booking_search_url": r.get("booking_search_url"),
            }
            for r in cheapest
        ],
        "rows": rows,
    }
