#!/usr/bin/env python3
"""itda-calendar: list_events.py — time-range event query (read-only, sanitized).

기본은 오늘부터 +7일. `--calendar` 미지정 시 모든 VEVENT 캘린더를 조회한다.
조회 결과의 SUMMARY/DESCRIPTION/LOCATION은 기본 sanitize(프롬프트 인젝션 방어).
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import get_calendars_fast, search_events  # noqa: E402
from cli_common import classify_error, emit, emit_error, resolve_provider_or_exit  # noqa: E402
from event_model import (DEFAULT_TZ, event_matches_query,  # noqa: E402
                         expand_recurrences, normalize_event, parse_dt)
from email_security import sanitize_for_llm  # noqa: E402


def _as_dt(value, tz) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=tz)
    return value


def main() -> None:
    ap = argparse.ArgumentParser(description="List calendar events in a time range.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", help="calendar name or id (default: all VEVENT calendars)")
    ap.add_argument("--from", dest="from_", help="ISO date/datetime (default: now)")
    ap.add_argument("--to", help="ISO date/datetime (default: +7 days)")
    ap.add_argument("--expand", action="store_true", help="expand recurring events")
    ap.add_argument("--query", help="클라이언트 측 텍스트 필터 — "
                                    "SUMMARY/DESCRIPTION/LOCATION substring, 대소문자 무시")
    ap.add_argument("--no-sanitize", action="store_true", help="raw text (unsafe for LLM)")
    ap.add_argument("--refresh", action="store_true",
                    help="디스커버리 캐시를 무시하고 캘린더 목록을 재탐색")
    args = ap.parse_args()

    tz = ZoneInfo(DEFAULT_TZ)
    start = _as_dt(parse_dt(args.from_), tz) if args.from_ else datetime.now(tz)
    end = _as_dt(parse_dt(args.to), tz) if args.to else start + timedelta(days=7)

    prov = resolve_provider_or_exit(args.provider, args.account)
    # 캘린더 목록을 캐싱된 calendar-home url로 가져온다(principal 디스커버리 skip).
    # components는 생략한다(병목): VTODO 캘린더는 event=True search가 0건이라 무해.
    try:
        cals, _client = get_calendars_fast(prov, refresh=args.refresh)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)
    if args.calendar:
        cals = [c for c in cals if args.calendar in (c["name"], c["id"])]
        if not cals:
            emit_error("calendar_not_found", args.calendar, code=1)

    san = None if args.no_sanitize else sanitize_for_llm
    via_objects = prov.get("list_via_objects", False)

    def _fetch(c):
        # 캘린더는 서로 독립 컬렉션이므로 병렬로 REPORT한다(순차 8회 → 동시).
        try:
            return c, search_events(c["_obj"], start, end, expand=args.expand,
                                    via_objects=via_objects)
        except Exception:  # noqa: BLE001
            return c, []

    # objects 경로(네이버)는 서버가 expand 를 안 해 준다 — RRULE 마스터만 온다.
    # --expand 를 무시하면 시작일이 과거인 주간·일간 반복이 오늘·내일 창에서
    # 통째로 빠지므로 클라이언트 전개한다(#1638 C2). search 경로(iCloud)는
    # 서버가 expand 를 처리하므로 동작 불변.
    client_expand = args.expand and via_objects
    expand_failures: list = []

    results = []
    if cals:
        with ThreadPoolExecutor(max_workers=min(8, len(cals))) as pool:
            for c, events in pool.map(_fetch, cals):
                for ev in events:
                    comp = ev.icalendar_component
                    nd = normalize_event(
                        comp,
                        sanitize_fn=san,
                        url=str(ev.url),
                        etag=getattr(ev, "etag", None),
                    )
                    nd["calendar"] = c["name"]
                    items = (expand_recurrences(nd, comp, start, end, tz,
                                                failures=expand_failures)
                             if client_expand else [nd])
                    for item in items:
                        # sanitize 이후 텍스트 기준 매칭 — 화면 표시와 필터가 일치
                        if args.query and not event_matches_query(item, args.query):
                            continue
                        results.append(item)

    if expand_failures:
        # 전개 실패는 마스터 1건으로 보수 폴백된다 — 이후 회차가 목록에서 새므로
        # 무음이면 안 된다. stdout 은 JSON 전용이라 stderr 로만 낸다.
        uids = ", ".join(str(f.get("uid")) for f in expand_failures[:5])
        print(f"warning: 반복 일정 {len(expand_failures)}건 전개 실패 — "
              f"마스터 1건만 표시됨 (uid: {uids})", file=sys.stderr)

    results.sort(key=lambda x: (x.get("start") or ""))
    emit(results)


if __name__ == "__main__":
    main()
