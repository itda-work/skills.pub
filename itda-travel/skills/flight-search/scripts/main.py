#!/usr/bin/env python3
"""flight-search CLI — Google Flights 항공권 검색·비교(조회 전용).

⚠️ Google Flights 공개 검색 표면을 fast-flights 로 조회한다(로그인·API key·결제·
CAPTCHA 우회 없음). 예약·결제는 하지 않으며 booking_search_url 은 Google Flights
검색 링크일 뿐이다. 전체 디스클레이머는 SKILL.md / GUIDE.md 참조.

서브커맨드: search / compare-month / compare-range / compare-years.
공통 옵션(--json·--adults·--seat·--limit)은 서브커맨드 "뒤"에서 받는다
(전역 위치 강제로 인한 "unrecognized arguments: --json" 함정 제거).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 이상이 필요합니다.")

sys.path.insert(0, str(Path(__file__).parent))

import airports  # noqa: E402
import compare  # noqa: E402
import flights_adapter as adapter  # noqa: E402
import format_out as fmt  # noqa: E402


class FlightUsageError(ValueError):
    """CLI 입력 오류(날짜·연도 형식 등). 사용자에게 그대로 보일 사유."""


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_MONTH_DAY_RE = re.compile(r"^\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# 입력 검증 helpers
# ---------------------------------------------------------------------------


def positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수여야 합니다")
    return n


def nonneg_float(value: str) -> float:
    f = float(value)
    if f < 0:
        raise argparse.ArgumentTypeError("0 이상의 수여야 합니다")
    return f


def _resolve_route(args) -> tuple[str, str]:
    origin = airports.resolve_airport(args.from_airport, "출발")
    dest = airports.resolve_airport(args.to_airport, "도착")
    airports.ensure_distinct(origin, dest)
    return origin, dest


def _valid_date(value: str, field: str) -> str:
    if not _DATE_RE.fullmatch(value or ""):
        raise FlightUsageError(f"{field} 형식이 올바르지 않습니다(YYYY-MM-DD): {value!r}")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise FlightUsageError(
            f"{field} 형식이 올바르지 않습니다(YYYY-MM-DD): {value!r}"
        ) from exc
    return value


def _valid_month(value: str) -> str:
    if not _MONTH_RE.fullmatch(value or ""):
        raise FlightUsageError(f"month 는 YYYY-MM 형식이어야 합니다: {value!r}")
    try:
        datetime.strptime(value + "-01", "%Y-%m-%d")
    except ValueError as exc:
        raise FlightUsageError(f"month 는 YYYY-MM 형식이어야 합니다: {value!r}") from exc
    return value


def _valid_month_day(value: str) -> str:
    if not _MONTH_DAY_RE.fullmatch(value or ""):
        raise FlightUsageError(f"month-day 는 MM-DD 형식이어야 합니다: {value!r}")
    try:
        datetime.strptime("2000-" + value, "%Y-%m-%d")
    except ValueError as exc:
        raise FlightUsageError(f"month-day 는 MM-DD 형식이어야 합니다: {value!r}") from exc
    return value


def _parse_years(value: str) -> list[int]:
    try:
        years = [int(x) for x in re.split(r"[,\s]+", value.strip()) if x]
    except ValueError as exc:
        raise FlightUsageError("years 는 쉼표로 구분된 연도여야 합니다(예: 2026,2027).") from exc
    if not years:
        raise FlightUsageError("years 가 비어 있습니다(예: 2026,2027).")
    if any(y < 1000 or y > 9999 for y in years):
        raise FlightUsageError("years 는 4자리 연도여야 합니다(예: 2026,2027).")
    return years


# ---------------------------------------------------------------------------
# 서브커맨드
# ---------------------------------------------------------------------------


def cmd_search(args) -> int:
    origin, dest = _resolve_route(args)
    date_s = _valid_date(args.date, "출발일")
    return_s = _valid_date(args.return_date, "귀국일") if args.return_date else None
    if return_s and return_s < date_s:
        raise FlightUsageError("귀국일은 출발일과 같거나 이후여야 합니다.")

    raw, band, url = adapter.search(
        origin, dest, date_s, return_s, adults=args.adults, seat=args.seat
    )
    payload = fmt.summarize_flights(raw, band=band, booking_url=url, limit=args.limit)
    query = {
        "from": origin,
        "to": dest,
        "date": date_s,
        "return_date": return_s,
        "trip": "round-trip" if return_s else "one-way",
        "adults": args.adults,
        "seat": args.seat,
    }
    payload["query"] = query
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(fmt.format_search_text(payload, query))
    return 0


def _run_compare(args, dates, label) -> int:
    stay = getattr(args, "stay", None)
    if stay:
        label += f" / 왕복 체류 {stay}일"
    capped, dropped = compare.cap_dates(dates)
    payload = compare.scan_dates(
        adapter.search,
        args._origin,
        args._dest,
        capped,
        adults=args.adults,
        seat=args.seat,
        limit=args.limit,
        sleep=args.sleep,
        stay=stay,
    )
    query = {
        "from": args._origin,
        "to": args._dest,
        "adults": args.adults,
        "seat": args.seat,
        "trip": "round-trip" if stay else "one-way",
        "stay_days": stay,
        "label": label,
    }
    payload["query"] = query
    if dropped:
        payload["meta"]["dropped_dates"] = dropped
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text = fmt.format_compare_text(payload, query)
        if dropped:
            text += (
                f"\n\n※ 요청량 가드로 {dropped}일이 제외되었습니다"
                f"(한 번에 최대 {compare.MAX_SCAN_DATES}일 조회)."
            )
        print(text)
    meta = payload["meta"]
    if meta.get("sampled_dates", 0) > 0 and meta.get("successful_dates", 0) == 0:
        # fail-loud 대칭(search 와 동일): 전 날짜 실패(의존성 미설치·전면 차단 등)는
        # 부분 성공이 아니라 실패로 보고한다(위 출력에 날짜별 사유가 이미 표시됨).
        print(
            "\n전 날짜 조회에 실패했습니다(의존성 미설치·전면 차단 가능). "
            "위 실패 사유를 확인하고 잠시 후 재시도하세요.",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_compare_month(args) -> int:
    args._origin, args._dest = _resolve_route(args)
    _valid_month(args.month)
    dates = compare.month_dates(args.month, args.sample)
    return _run_compare(args, dates, f"{args.month} {args.sample}")


def cmd_compare_range(args) -> int:
    args._origin, args._dest = _resolve_route(args)
    start = _valid_date(args.start_date, "시작일")
    end = _valid_date(args.end_date, "종료일")
    if end < start:
        raise FlightUsageError("종료일은 시작일과 같거나 이후여야 합니다.")
    dates = compare.range_dates(start, end, args.step_days)
    return _run_compare(args, dates, f"{start}~{end} ({args.step_days}일 간격)")


def _resolve_destinations(args) -> tuple[str, list[str]]:
    """--to 쉼표 목록 전수 해석(#1025) — 조회 전에 모호/중복/상한을 확정한다.

    1개라도 모호(AmbiguousCity)면 여기서 올라가 조회가 시작되지 않는다(AC).
    중복은 순서 보존 dedup, 목적지 수 상한 초과는 fail-loud.
    """
    origin = airports.resolve_airport(args.from_airport, "출발")
    dests: list[str] = []
    for token in [t for t in re.split(r"[,\s]+", args.to_airports.strip()) if t]:
        dest = airports.resolve_airport(token, "도착")
        airports.ensure_distinct(origin, dest)
        if dest not in dests:
            dests.append(dest)
    if not dests:
        raise FlightUsageError("도착 목적지가 비어 있습니다(쉼표 구분, 예: FCO,CDG,AMS).")
    if len(dests) > compare.MAX_DESTINATIONS:
        raise FlightUsageError(
            f"목적지가 {len(dests)}개입니다 — 한 번에 최대 "
            f"{compare.MAX_DESTINATIONS}개까지 비교합니다(요청량 가드). "
            "후보를 좁혀 다시 시도하세요."
        )
    return origin, dests


def cmd_compare_destinations(args) -> int:
    origin, dests = _resolve_destinations(args)
    if args.date:
        dates = [datetime.strptime(_valid_date(args.date, "조회일"), "%Y-%m-%d").date()]
        label = args.date
    else:
        _valid_month(args.month)
        dates = compare.month_dates(args.month, "weekly")  # weekly 샘플 강제(#1025)
        label = f"{args.month} weekly"
    payload = compare.scan_destinations(
        adapter.search,
        origin,
        dests,
        dates,
        adults=args.adults,
        seat=args.seat,
        limit=args.limit,
        sleep=args.sleep,
    )
    query = {
        "from": origin,
        "to": ",".join(dests),
        "adults": args.adults,
        "seat": args.seat,
        "label": label,
    }
    payload["query"] = query
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(fmt.format_destinations_text(payload, query))
    total = sum(d.get("sampled_dates", 0) for d in payload["destinations"])
    succeeded = sum(d.get("successful_dates", 0) for d in payload["destinations"])
    if total > 0 and succeeded == 0:
        # fail-loud 대칭(_run_compare 와 동일): 전 조회 실패는 실패로 보고.
        print(
            "\n전 목적지 조회에 실패했습니다(의존성 미설치·전면 차단 가능). "
            "위 실패 사유를 확인하고 잠시 후 재시도하세요.",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_compare_years(args) -> int:
    args._origin, args._dest = _resolve_route(args)
    years = _parse_years(args.years)
    _valid_month_day(args.month_day)
    try:
        dates = compare.year_dates(years, args.month_day)
    except ValueError as exc:
        raise FlightUsageError(
            f"years 와 month-day 조합이 올바르지 않습니다: {args.years} / {args.month_day}"
        ) from exc
    return _run_compare(args, dates, f"{args.month_day} 연도비교 {years}")


# ---------------------------------------------------------------------------
# 파서
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--adults", type=positive_int, default=1, help="성인 수(기본 1)")
    common.add_argument(
        "--seat",
        choices=["economy", "premium-economy", "business", "first"],
        default="economy",
    )
    common.add_argument("--limit", type=positive_int, default=5, help="표시 후보 수")
    common.add_argument("--json", action="store_true", help="JSON 출력")

    route = argparse.ArgumentParser(add_help=False)
    route.add_argument(
        "--from", dest="from_airport", required=True, help="출발(IATA 또는 한국어 도시명)"
    )
    route.add_argument(
        "--to", dest="to_airport", required=True, help="도착(IATA 또는 한국어 도시명)"
    )

    slow = argparse.ArgumentParser(add_help=False)
    slow.add_argument(
        "--sleep",
        type=nonneg_float,
        default=compare.MIN_SLEEP_SECONDS,
        help=f"조회 간 대기초(최소 {compare.MIN_SLEEP_SECONDS} 강제)",
    )
    slow.add_argument(
        "--stay",
        type=positive_int,
        default=None,
        help="왕복 체류일 — 출발일마다 +N일 귀국 왕복가 비교(미지정 시 편도)",
    )

    p = argparse.ArgumentParser(
        prog="flight-search",
        description="Google Flights 항공권 검색·비교(조회 전용, 예약·결제 없음)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", parents=[common, route], help="편도/왕복 단일 검색")
    s.add_argument("--date", required=True, help="출발일 YYYY-MM-DD")
    s.add_argument("--return-date", help="귀국일 YYYY-MM-DD(왕복)")
    s.set_defaults(func=cmd_search)

    m = sub.add_parser(
        "compare-month", parents=[common, route, slow], help="한 달 비교(최저가 날짜)"
    )
    m.add_argument("--month", required=True, help="YYYY-MM")
    m.add_argument("--sample", choices=["weekly", "daily"], default="weekly")
    m.set_defaults(func=cmd_compare_month)

    r = sub.add_parser(
        "compare-range", parents=[common, route, slow], help="날짜 범위 비교"
    )
    r.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    r.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    r.add_argument("--step-days", type=positive_int, default=7, help="간격(1=일별, 7=주별)")
    r.set_defaults(func=cmd_compare_range)

    y = sub.add_parser(
        "compare-years", parents=[common, route, slow], help="연도 비교(같은 월일)"
    )
    y.add_argument("--years", required=True, help="쉼표 구분(예: 2026,2027)")
    y.add_argument("--month-day", required=True, help="MM-DD(예: 06-01)")
    y.set_defaults(func=cmd_compare_years)

    # 관문 비교(#1025) — route/slow 부모 미사용: --to 는 쉼표 목록이고,
    # --stay(왕복) 조합은 cap 재검토 전까지 범위 밖이라 노출하지 않는다.
    dst = sub.add_parser(
        "compare-destinations", parents=[common],
        help="다중 목적지(관문) 최저가 비교",
    )
    dst.add_argument(
        "--from", dest="from_airport", required=True, help="출발(IATA 또는 한국어 도시명)"
    )
    dst.add_argument(
        "--to", dest="to_airports", required=True,
        help=f"도착 목적지들 — 쉼표 구분, 최대 {compare.MAX_DESTINATIONS}개(예: FCO,CDG,AMS)",
    )
    when = dst.add_mutually_exclusive_group(required=True)
    when.add_argument("--date", help="조회일 YYYY-MM-DD(단일 날짜)")
    when.add_argument("--month", help="YYYY-MM(주 1회 샘플 강제)")
    dst.add_argument(
        "--sleep",
        type=nonneg_float,
        default=compare.MIN_SLEEP_SECONDS,
        help=f"조회 간 대기초(최소 {compare.MIN_SLEEP_SECONDS} 강제)",
    )
    dst.set_defaults(func=cmd_compare_destinations)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except airports.AirportError as exc:  # AmbiguousCity 포함
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1
    except FlightUsageError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1
    except adapter.FlightError as exc:  # 미설치·조회 실패(fail-loud)
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
