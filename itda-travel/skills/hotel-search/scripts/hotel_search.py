#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotel_search.py - 호텔 가격 비교 CLI (조회 전용, standalone).

Xotelo API(트립어드바이저 메타서치)로 한 호텔의 여러 OTA(Booking·Agoda·Trip.com·
공식사이트) 실시간 요금을 한 번에 모아 비교한다. 브라우저·MCP·hyve 없이 표준
라이브러리만으로 Xotelo 를 직접 호출한다(#1013 — web_browse·attach 경로 폐기).

hotel_key 해소(이름→g<geo>-d<hotel>)는 Xotelo 무료 티어에 없으므로(search=유료·
list=고장) 두 경로로 처리한다(SKILL.md):
  1) 에이전트 web_search 로 TripAdvisor 호텔 URL 확보 → --url 전달
  2) 사용자가 TripAdvisor URL/키 직접 제공 → --url / --hotel-key

서브커맨드:
  rates    OTA별 요금 비교표 (원화 환산 병기)
  heatmap  가격 달력(싼날/평균/비싼날)
  resolve  URL/텍스트 → hotel_key 추출(에이전트 해소 보조)

사용 예:
  python3 hotel_search.py resolve "https://www.tripadvisor.com/Hotel_Review-g294197-d5250436-...html"
  python3 hotel_search.py rates --hotel-key g294197-d5250436 \
      --checkin 2026-08-15 --checkout 2026-08-16 --name "써미트 호텔 서울"
  python3 hotel_search.py heatmap --url "<TripAdvisor URL>" --checkout 2026-08-16
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

import fx as fx_mod
import links
import output
import xotelo
from errors import ArgsError, EXIT_OK, HotelSearchError

_META_NOTE = (
    "TripAdvisor 메타서치 요금 · OTA별 최저 예약가능 객실의 1박 대표값(객실 타입 구분 없음) · "
    "실제 예약가와 다를 수 있음 · OTA 노출 개수는 호텔·날짜별로 다름"
)


def _validate_date(value: str, label: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ArgsError(f"{label} 는 YYYY-MM-DD 형식이어야 합니다 (받음: {value!r})")


def _nights(checkin: str, checkout: str) -> int:
    ci = _validate_date(checkin, "--checkin")
    co = _validate_date(checkout, "--checkout")
    n = (co - ci).days
    if n <= 0:
        raise ArgsError(f"--checkout({checkout}) 는 --checkin({checkin}) 보다 이후여야 합니다")
    return n


def _resolve_key(args) -> str:
    """--hotel-key 또는 --url 에서 hotel_key 를 확정한다(정확히 하나 필요)."""
    src = getattr(args, "hotel_key", None) or getattr(args, "url", None)
    if not src:
        raise ArgsError("--hotel-key 또는 --url 중 하나가 필요합니다")
    return xotelo.extract_hotel_key(src)


def _emit(text: str, output_path: str | None) -> int:
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"저장: {output_path}", file=sys.stderr)
    else:
        print(text)
    return EXIT_OK


def cmd_resolve(args) -> int:
    """URL/텍스트에서 hotel_key 를 추출해 출력한다(에이전트 해소 보조)."""
    print(xotelo.extract_hotel_key(args.source))
    return EXIT_OK


def cmd_rates(args) -> int:
    hotel_key = _resolve_key(args)
    nights = _nights(args.checkin, args.checkout)
    currency = xotelo.validate_currency(args.currency)

    fx_rate = None
    fx_note = ""
    if not args.no_krw:
        fx_rate = fx_mod.krw_rate(currency)
        if fx_rate is None:
            # 조용한 폴백 금지 — 환산 실패를 출력에 명시(원화 컬럼만 생략)
            fx_note = " · ⚠️ 환율 조회 실패로 원화 환산 생략"
        else:
            fx_note = f" · 원화는 {fx_rate:,.0f}원/{currency} 환산 참고값(예약가 아님)"

    result = xotelo.fetch_rates(
        hotel_key, args.checkin, args.checkout,
        currency=currency, adults=args.adults, rooms=args.rooms,
    )
    offers, collected_currency = xotelo.parse_rates(result, nights=nights, fx_rate=fx_rate)

    # OTA별 예약 딥링크(호텔명 필요 — 없으면 링크 생략을 명시)
    link_note = ""
    if args.name:
        for o in offers:
            o["url"] = links.ota_deeplink(
                o.get("ota_code"), args.name, args.checkin, args.checkout,
                adults=args.adults, rooms=args.rooms,
            )
    else:
        link_note = " · 예약 링크는 --name(호텔명) 지정 시 제공"

    data = {
        "hotel_key": hotel_key,
        "hotel_name": args.name,
        "checkin": args.checkin,
        "checkout": args.checkout,
        "nights": nights,
        "adults": args.adults,
        "rooms": args.rooms,
        "currency": collected_currency or currency,
        "fx_rate": fx_rate,
        "offers": offers,
        "_disclaimer": _META_NOTE + fx_note + link_note,
    }
    text = output.to_json(data) if args.format == "json" else output.rates_to_markdown(data)
    return _emit(text, args.output)


def cmd_heatmap(args) -> int:
    hotel_key = _resolve_key(args)
    _validate_date(args.checkout, "--checkout")
    result = xotelo.fetch_heatmap(hotel_key, args.checkout)
    parsed = xotelo.parse_heatmap(result)
    data = {"hotel_key": hotel_key, "hotel_name": args.name, **parsed}
    text = output.to_json(data) if args.format == "json" else output.heatmap_to_markdown(data)
    return _emit(text, args.output)


# --- 인자 정의 --------------------------------------------------------------

def _add_key_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--hotel-key", help="TripAdvisor hotel_key (예: g294197-d5250436)")
    p.add_argument("--url", help="TripAdvisor 호텔 페이지 URL (키를 자동 추출)")
    p.add_argument("--name", help="호텔 표시명(선택 — /rates 는 이름 미제공)")
    p.add_argument("--format", choices=["json", "markdown"], default="markdown", help="출력 형식(기본 markdown)")
    p.add_argument("--output", help="결과 저장 경로(기본 stdout)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hotel-search", description="호텔 가격 비교 (Xotelo, 조회 전용)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("rates", help="OTA별 요금 비교(원화 환산 병기)")
    _add_key_args(pr)
    pr.add_argument("--checkin", required=True, help="체크인 YYYY-MM-DD")
    pr.add_argument("--checkout", required=True, help="체크아웃 YYYY-MM-DD")
    pr.add_argument("--currency", default="USD", help="Xotelo 수집 통화(기본 USD — KRW 미지원, 원화는 환산 표시)")
    pr.add_argument("--adults", type=int, default=2, help="성인 수(기본 2)")
    pr.add_argument("--rooms", type=int, default=1, help="객실 수(기본 1)")
    pr.add_argument("--no-krw", action="store_true", help="원화 환산 생략(수집 통화만 표시)")
    pr.set_defaults(func=cmd_rates)

    ph = sub.add_parser("heatmap", help="가격 달력(싼날/평균/비싼날)")
    _add_key_args(ph)
    ph.add_argument("--checkout", required=True, help="체크아웃 YYYY-MM-DD")
    ph.set_defaults(func=cmd_heatmap)

    pv = sub.add_parser("resolve", help="URL/텍스트 → hotel_key 추출")
    pv.add_argument("source", help="TripAdvisor URL 또는 g<geo>-d<hotel> 문자열")
    pv.set_defaults(func=cmd_resolve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HotelSearchError as e:
        print(f"오류: {e}", file=sys.stderr)
        return e.code
    except Exception as e:  # noqa: BLE001
        print(f"예기치 못한 오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
