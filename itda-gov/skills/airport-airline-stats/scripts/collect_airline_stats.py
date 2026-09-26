#!/usr/bin/env python3
"""airport-airline-stats — 인천공항 항공사별 월별 통계 조회 CLI.

Usage:
  python3 collect_airline_stats.py --year 2025 --month 3 --route I --format json
  py -3 collect_airline_stats.py --year 2025 --month 3 --route I --format json
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
from typing import Any

# Allow `from airline_stats_api import ...` when running standalone.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from airline_codes import AIRLINE_CODES  # noqa: E402
from airline_stats_api import (  # noqa: E402
    BASE_URL,
    DISCLAIMER,
    LAYOUT_TOKEN,
    STATS_PATH,
    AirportSession,
    FetchError,
    SessionSeedError,
    parse_airline_stats_html,
)

ROUTE_CHOICES = ["all", "I", "D"]
ARPLN_CHOICES = ["all", "Y", "N"]
TERMINAL_CHOICES = ["all", "P01", "P03"]
NVG_CHOICES = ["all", "0", "1"]
FORMAT_CHOICES = ["json", "csv", "table"]

_ROUTE_LABEL = {"all": "전체", "I": "국제선", "D": "국내선"}
_ARPLN_LABEL = {"all": "전체", "Y": "여객기", "N": "화물기"}
_TERMINAL_LABEL = {"all": "전체", "P01": "T1", "P03": "T2"}
_NVG_LABEL = {"all": "전체", "0": "정기", "1": "부정기"}


def _norm_enum(value: str) -> str:
    return "" if value == "all" else value


def _meta(
    *,
    year: int,
    month: int,
    row_count: int,
    parse_warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": "인천국제공항공사 (airport.kr)",
        "source_url": f"{BASE_URL}{STATS_PATH}?layout={LAYOUT_TOKEN}",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "period": f"{year:04d}-{month:02d}",
        "row_count": row_count,
        "disclaimer": DISCLAIMER,
        "parse_warnings": parse_warnings or [],
    }


def collect(
    year: int,
    month: int,
    *,
    route: str = "all",
    airline_type: str = "all",
    terminal: str = "all",
    schedule: str = "all",
    airline: str = "",
    session: AirportSession | None = None,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Orchestrate the 2-step fetch + parse and return a payload dict.

    Error payloads always contain `error` + `message` + `meta`.
    Success payloads contain `query` + `results` + `summary` + `meta`.
    """
    # REQ-010: future month guard
    today = today or dt.date.today()
    try:
        requested = dt.date(year, month, 1)
    except ValueError:
        return {
            "error": "invalid_month",
            "message": f"잘못된 연/월: {year}-{month}",
            "meta": _meta(year=year, month=month, row_count=0),
        }
    cutoff = dt.date(today.year, today.month, 1)
    if requested > cutoff:
        return {
            "error": "future_month",
            "message": (
                f"미래 월({year:04d}-{month:02d}) 조회는 차단됩니다. "
                f"현재 기준: {cutoff.isoformat()}"
            ),
            "meta": _meta(year=year, month=month, row_count=0),
        }
    # airline whitelist validation
    if airline and airline not in AIRLINE_CODES:
        return {
            "error": "unknown_airline_code",
            "message": (
                f"항공사 코드 {airline!r}이(가) 화이트리스트에 없습니다. "
                "--list-airlines 로 확인하세요."
            ),
            "meta": _meta(year=year, month=month, row_count=0),
        }
    s = session or AirportSession()
    try:
        s.seed_session()
        html = s.fetch_airline_stats(
            year,
            month,
            route=_norm_enum(route),
            arpln=_norm_enum(airline_type),
            terminal=_norm_enum(terminal),
            nvg=_norm_enum(schedule),
            airline=airline,
        )
    except SessionSeedError as e:
        return {
            "error": "session_seed_failed",
            "message": str(e),
            "meta": _meta(year=year, month=month, row_count=0),
        }
    except FetchError as e:
        return {
            "error": "fetch_failed",
            "message": str(e),
            "meta": _meta(year=year, month=month, row_count=0),
        }
    parsed = parse_airline_stats_html(html)
    if not parsed["results"]:
        return {
            "error": "no_data",
            "message": "조회 결과가 비어 있습니다.",
            "meta": _meta(
                year=year,
                month=month,
                row_count=0,
                parse_warnings=parsed["parse_warnings"],
            ),
        }
    return {
        "query": {
            "year": year,
            "month": month,
            "route": route,
            "airline_type": airline_type,
            "terminal": terminal,
            "schedule": schedule,
            "airline": airline or "all",
        },
        "results": parsed["results"],
        "summary": parsed["summary"],
        "meta": _meta(
            year=year,
            month=month,
            row_count=len(parsed["results"]),
            parse_warnings=parsed["parse_warnings"],
        ),
    }


# ─── Formatters ──────────────────────────────────────────────────────────────


def format_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def format_csv(payload: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    if "error" in payload:
        w.writerow(["error", "message", "disclaimer"])
        w.writerow(
            [
                payload["error"],
                payload.get("message", ""),
                payload["meta"]["disclaimer"],
            ]
        )
        return buf.getvalue()
    w.writerow(
        [
            "airline_name",
            "flights.arrival",
            "flights.departure",
            "flights.total",
            "passengers.arrival",
            "passengers.departure",
            "passengers.total",
            "cargo.arrival",
            "cargo.departure",
            "cargo.total",
        ]
    )
    for r in payload["results"]:
        f = r["flights"]
        p = r["passengers"]
        c = r["cargo"]
        w.writerow(
            [
                r["airline_name"],
                f["arrival"],
                f["departure"],
                f["total"],
                p["arrival"],
                p["departure"],
                p["total"],
                c["arrival"],
                c["departure"],
                c["total"],
            ]
        )
    w.writerow([])
    w.writerow([f"# {payload['meta']['disclaimer']}"])
    return buf.getvalue()


def _fmt_int(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def format_table(payload: dict[str, Any]) -> str:
    if "error" in payload:
        return (
            f"ERROR: {payload['error']} — {payload.get('message', '')}\n\n"
            f"{payload['meta']['disclaimer']}"
        )
    lines: list[str] = []
    q = payload["query"]
    lines.append(
        f"인천공항 항공사별 통계 ({q['year']}-{q['month']:02d}, "
        f"노선={_ROUTE_LABEL[q['route']]}, "
        f"항공기={_ARPLN_LABEL[q['airline_type']]}, "
        f"터미널={_TERMINAL_LABEL[q['terminal']]}, "
        f"운항={_NVG_LABEL[q['schedule']]})"
    )
    lines.append("=" * 120)
    header = (
        f"{'항공사':<26} "
        f"{'운항(도)':>8} {'운항(출)':>8} {'운항(합)':>9} "
        f"{'여객(도)':>11} {'여객(출)':>11} {'여객(합)':>12} "
        f"{'화물(도)':>11} {'화물(출)':>11} {'화물(합)':>12}"
    )
    lines.append(header)
    lines.append("-" * 120)
    for r in payload["results"]:
        f = r["flights"]
        p = r["passengers"]
        c = r["cargo"]
        name = r["airline_name"][:26]
        lines.append(
            f"{name:<26} "
            f"{_fmt_int(f['arrival']):>8} {_fmt_int(f['departure']):>8} {_fmt_int(f['total']):>9} "
            f"{_fmt_int(p['arrival']):>11} {_fmt_int(p['departure']):>11} {_fmt_int(p['total']):>12} "
            f"{_fmt_int(c['arrival']):>11} {_fmt_int(c['departure']):>11} {_fmt_int(c['total']):>12}"
        )
    summary = payload.get("summary") or {}
    if summary.get("total"):
        t = summary["total"]
        lines.append("-" * 120)
        lines.append(
            f"{'합계':<26} "
            f"{_fmt_int(t['flights']['arrival']):>8} {_fmt_int(t['flights']['departure']):>8} {_fmt_int(t['flights']['total']):>9} "
            f"{_fmt_int(t['passengers']['arrival']):>11} {_fmt_int(t['passengers']['departure']):>11} {_fmt_int(t['passengers']['total']):>12} "
            f"{_fmt_int(t['cargo']['arrival']):>11} {_fmt_int(t['cargo']['departure']):>11} {_fmt_int(t['cargo']['total']):>12}"
        )
    if summary.get("yoy_change"):
        y = summary["yoy_change"]
        lines.append(
            f"{'전년대비':<26} "
            f"{y['flights']['arrival']:>8} {y['flights']['departure']:>8} {y['flights']['total']:>9} "
            f"{y['passengers']['arrival']:>11} {y['passengers']['departure']:>11} {y['passengers']['total']:>12} "
            f"{y['cargo']['arrival']:>11} {y['cargo']['departure']:>11} {y['cargo']['total']:>12}"
        )
    lines.append("")
    lines.append(payload["meta"]["disclaimer"])
    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="airport-airline-stats",
        description="인천공항 항공사별 월별 통계 조회 (운항·여객·화물)",
    )
    p.add_argument("--year", type=int, help="조회 연도 (YYYY)")
    p.add_argument(
        "--month",
        type=int,
        choices=range(1, 13),
        metavar="{1..12}",
        help="조회 월 (1-12)",
    )
    p.add_argument(
        "--route",
        choices=ROUTE_CHOICES,
        default="all",
        help="노선 구분: all|I(국제선)|D(국내선)",
    )
    p.add_argument(
        "--airline-type",
        choices=ARPLN_CHOICES,
        default="all",
        help="항공기 구분: all|Y(여객기)|N(화물기)",
    )
    p.add_argument(
        "--terminal",
        choices=TERMINAL_CHOICES,
        default="all",
        help="터미널: all|P01(T1)|P03(T2)",
    )
    p.add_argument(
        "--schedule",
        choices=NVG_CHOICES,
        default="all",
        help="운항 구분: all|0(정기)|1(부정기)",
    )
    p.add_argument(
        "--airline",
        default="",
        help="항공사 코드 (IATA, 예: KE, OZ). 미지정 시 전체.",
    )
    p.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="json",
        help="출력 포맷",
    )
    p.add_argument(
        "--list-airlines",
        action="store_true",
        help="지원되는 항공사 코드 목록 출력 후 종료",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_airlines:
        for code, name in sorted(AIRLINE_CODES.items()):
            print(f"{code:6s}  {name}")
        return 0
    if args.year is None or args.month is None:
        parser.error("--year and --month are required (or use --list-airlines)")
    payload = collect(
        args.year,
        args.month,
        route=args.route,
        airline_type=args.airline_type,
        terminal=args.terminal,
        schedule=args.schedule,
        airline=args.airline,
    )
    if args.format == "json":
        print(format_json(payload))
    elif args.format == "csv":
        print(format_csv(payload), end="")
    else:  # table
        print(format_table(payload))
    return 0 if "error" not in payload else 2


if __name__ == "__main__":
    sys.exit(main())
