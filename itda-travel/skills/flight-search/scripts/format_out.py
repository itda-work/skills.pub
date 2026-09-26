"""flight-search 출력·집계 — 순수 모듈(네트워크 의존 0).

fast-flights Result/Flight(asdict 한 dict)를 받아 KRW 가격 파싱·정규화·통계·
한국어 텍스트로 변환한다. 네트워크/라이브러리 의존은 flights_adapter.py 에
격리하므로 이 모듈은 단위 테스트 100% 가능하다.

Flight dict 필드(fast-flights 2.2 실측):
  is_best, name, departure, arrival, arrival_time_ahead, duration, stops,
  delay, price("₩135500")
"""
from __future__ import annotations

import re
import statistics
from typing import Any

PROVIDER = "google-flights-fast-flights"
CURRENCY = "KRW"
BOOKING_NOTE = (
    "예약 링크는 특정 판매자 결제 deep link 가 아니라 Google Flights 검색 결과 "
    "링크입니다. 실제 구매·결제·좌석 선택은 브라우저에서 직접 진행하세요."
)
COMPARE_NOTE = (
    "월/범위/연도 비교는 지정 날짜들을 실제 조회한 샘플 기반이며 Google Flights "
    "가격은 수시 변동됩니다. 표시 가격은 조회 시점 기준입니다."
)


def parse_price(price_text: str | None) -> int | None:
    """'₩135500' → 135500. 'unavailable'·빈값·숫자없음·0 → None.

    fast-flights 파서는 가격 노드가 없으면 price 를 리터럴 '0' 으로 채운다(라이브
    검증). ₩0 항공권은 비현실적이므로 0 이하는 '가격 없음'(None)으로 취급해 거짓
    최저가가 통계·정렬을 오염시키지 않게 한다.
    """
    if not price_text or "unavailable" in str(price_text).lower():
        return None
    digits = re.sub(r"[^0-9]", "", str(price_text))
    if not digits:
        return None
    value = int(digits)
    return value if value > 0 else None


def money_krw(value: int | float | None) -> str:
    """KRW 금액 표기. None → '확인 불가'."""
    if value is None:
        return "확인 불가"
    return f"₩{int(round(value)):,}"


def stops_label(stops: Any) -> str:
    """경유 수를 한국어로. 0=직항, 1+=N회 경유, 그 외=정보 없음."""
    if stops == 0:
        return "직항"
    if isinstance(stops, int) and stops > 0:
        return f"{stops}회 경유"
    return "경유 정보 없음"


def normalize_flight(raw: dict[str, Any]) -> dict[str, Any]:
    """asdict(Flight) 한 건에 price_value·price_text·quality 를 덧붙인다."""
    out = dict(raw)
    price_value = parse_price(raw.get("price"))
    out["price_value"] = price_value
    out["price_text"] = (
        money_krw(price_value)
        if price_value is not None
        else (raw.get("price") or "확인 불가")
    )
    out["quality"] = (
        "complete"
        if raw.get("name") and raw.get("departure") and raw.get("arrival")
        else "partial"
    )
    return out


def _dedup_flights(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Google Flights 응답의 best/all 섹션 중복을 제거한다.

    응답은 추천(best) 섹션과 전체(all) 섹션을 모두 담아 같은 항공편이 2회
    나온다(라이브 ICN-NRT 87건 중 고유 44건). (항공사·출발·도착·가격) 키로
    첫 등장만 남겨 '최저가 TOP'에 동일 편이 중복 노출되지 않게 한다.
    """
    seen: set = set()
    out: list[dict[str, Any]] = []
    for f in flights:
        key = (f.get("name"), f.get("departure"), f.get("arrival"), f.get("price"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def summarize_flights(
    raw_flights: list[dict[str, Any]], *, band: str, booking_url: str, limit: int
) -> dict[str, Any]:
    """검색결과 dict 리스트를 정규화·정렬·집계한다(순수).

    최저가 우선 정렬은 정보가 온전한(complete) 후보를 우선하되, 전부 partial
    이면 가격만이라도 있는 후보를 쓴다. 통계는 가격이 있는 모든 후보 기준.
    """
    flights = _dedup_flights([normalize_flight(f) for f in raw_flights])
    priced = [f for f in flights if f["price_value"] is not None]
    complete = [f for f in priced if f["quality"] == "complete"]
    best_pool = sorted(complete or priced, key=lambda x: x["price_value"])
    values = [f["price_value"] for f in priced]
    return {
        "meta": {
            "provider": PROVIDER,
            "currency": CURRENCY,
            "price_band": band or "",
            "booking_search_url": booking_url,
            "note": BOOKING_NOTE,
        },
        "stats": {
            "result_count": len(flights),
            "priced_count": len(priced),
            "complete_count": len(complete),
            "min_price": min(values) if values else None,
            "avg_price": statistics.mean(values) if values else None,
            "max_price": max(values) if values else None,
        },
        "flights": best_pool[:limit],
    }


# ---------------------------------------------------------------------------
# 한국어 텍스트 출력
# ---------------------------------------------------------------------------


def format_flight_line(idx: int, f: dict[str, Any]) -> str:
    """정규화된 항공편 한 건을 한 줄 한국어로."""
    name = f.get("name") or "항공편 상세 확인 불가"
    dep = f.get("departure") or "시간 확인 불가"
    arr = f.get("arrival") or "시간 확인 불가"
    ahead = f.get("arrival_time_ahead") or ""
    arr_disp = f"{arr} ({ahead})" if ahead else arr
    dur = f.get("duration") or "소요시간 확인 불가"
    return (
        f"{idx}. {name} — {dep} → {arr_disp} / {dur} / "
        f"{stops_label(f.get('stops'))} / {f.get('price_text', '확인 불가')}"
    )


def format_search_text(payload: dict[str, Any], query: dict[str, Any]) -> str:
    """단일 검색 결과를 한국어 텍스트로(REQ 출력)."""
    meta = payload["meta"]
    stats = payload["stats"]
    seg = str(query.get("date", ""))
    if query.get("return_date"):
        seg += f" ~ {query['return_date']}"
    lines = [
        f"✈️ {query.get('from')} → {query.get('to')} / {seg} / "
        f"성인 {query.get('adults')} / {query.get('seat')}",
        f"가격 band: {meta.get('price_band') or '확인 불가'}",
        f"최저/평균/최고: {money_krw(stats['min_price'])} / "
        f"{money_krw(stats['avg_price'])} / {money_krw(stats['max_price'])}",
        f"예약 검색 링크: {meta.get('booking_search_url')}",
    ]
    if not payload["flights"]:
        lines.append(
            "\n조건에 맞는 항공편을 찾지 못했습니다. 날짜·공항코드·노선을 확인해 주세요."
        )
        return "\n".join(lines)
    lines.append("")
    for i, f in enumerate(payload["flights"], 1):
        lines.append(format_flight_line(i, f))
    if any(f.get("quality") == "partial" for f in payload["flights"]):
        # complete 후보가 없어 가격만 있는 후보를 표시하는 경우(전체 partial).
        # fast-flights/Google Flights 는 같은 노선도 호출에 따라 항공사·시간
        # 상세 포함 여부가 달라진다(가격·band·링크는 유효).
        lines.append(
            "\n⚠️ 이 시점 Google Flights 응답에 항공사·시간 상세가 빠졌습니다"
            "(가격·예약 검색 링크는 유효). 링크에서 직접 확인하거나 잠시 후 다시 "
            "시도해 주세요 — 같은 노선도 호출에 따라 상세 포함 여부가 달라집니다."
        )
    return "\n".join(lines)


GATEWAY_NOTE = (
    "관문 최저가 ≠ 여정 총비용 — 관문 도시에서 최종 목적지까지의 기차/저가항공 "
    "비용·시간을 더해 비교하세요."
)


def format_destinations_text(payload: dict[str, Any], query: dict[str, Any]) -> str:
    """다중 목적지(관문) 비교 결과를 한국어 텍스트로(#1025)."""
    meta = payload["meta"]
    dests = payload.get("destinations", [])
    lines = [
        f"✈️ {query.get('from')} → 관문 비교({query.get('to')}) / "
        f"{query.get('label', '')} / 성인 {query.get('adults')} / {query.get('seat')}",
        f"표본: 목적지 {meta.get('destinations')} × "
        f"날짜 {meta.get('sampled_dates_per_destination')} = "
        f"조회 {meta.get('total_queries')}회",
    ]
    priced = [d for d in dests if d.get("min_price") is not None]
    unpriced = [d for d in dests if d.get("min_price") is None]
    if priced:
        lines.append("\n관문 최저가 순위")
        for i, d in enumerate(priced, 1):
            url = d.get("booking_search_url", "")
            lines.append(
                f"{i}. {d['to']} — {money_krw(d['min_price'])} "
                f"({d.get('cheapest_date')})  {url}".rstrip()
            )
    if unpriced:
        names = ", ".join(d["to"] for d in unpriced)
        lines.append(f"\n확인 불가: {names} (조회 실패 또는 가격 없음)")
    failures = [
        (d["to"], r)
        for d in dests
        for r in d.get("rows", [])
        if not r.get("ok")
    ]
    if failures:
        lines.append(f"\n실패 {len(failures)}건:")
        for to, r in failures[:5]:
            lines.append(f"- {to} {r['date']}: {r.get('error')}")
    if priced:
        lines.append(f"\n※ {GATEWAY_NOTE}")
    return "\n".join(lines)


def format_compare_text(payload: dict[str, Any], query: dict[str, Any]) -> str:
    """월/범위/연도 비교 결과를 한국어 텍스트로."""
    meta = payload["meta"]
    stats = payload["stats"]
    lines = [
        f"✈️ {query.get('from')} → {query.get('to')} / {query.get('label', '비교')} / "
        f"성인 {query.get('adults')} / {query.get('seat')}",
        f"표본: 성공 {meta.get('successful_dates')} / 시도 {meta.get('sampled_dates')}일",
        f"최저 / 일자별최저 평균 / 최고: {money_krw(stats['min_price'])} / "
        f"{money_krw(stats['avg_of_daily_min'])} / {money_krw(stats['max_of_daily_min'])}",
    ]
    cheapest = payload.get("cheapest_dates", [])
    if cheapest:
        lines.append("\n싼 날짜 TOP")
        for i, r in enumerate(cheapest, 1):
            url = r.get("booking_search_url", "")
            seg = r["date"]
            if r.get("return_date"):
                seg += f" ~ {r['return_date']}"
            lines.append(f"{i}. {seg} — {money_krw(r.get('min_price'))}  {url}".rstrip())
    failures = [r for r in payload.get("rows", []) if not r.get("ok")]
    if failures:
        lines.append(f"\n실패 {len(failures)}건:")
        for r in failures[:5]:
            lines.append(f"- {r['date']}: {r.get('error')}")
    return "\n".join(lines)
