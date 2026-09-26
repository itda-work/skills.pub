#!/usr/bin/env python3
"""itda-calendar: update_event.py — ETag-aware optimistic update (read-modify-write).

`--etag`를 주면 If-Match 의미로 현재 etag와 비교해 다르면 412 의미의
etag_conflict(exit 2)를 반환한다(묻지마 덮어쓰기 방지). 변경 필드만 갱신한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import find_calendar, find_event_by_uid, put_event  # noqa: E402
from cli_common import (classify_error, connect_or_exit, emit, emit_error,  # noqa: E402
                        resolve_provider_or_exit)
from event_model import parse_dt, parse_rrule  # noqa: E402


def _set(comp, key, value) -> None:
    comp.pop(key, None)
    comp.add(key, value)


def main() -> None:
    ap = argparse.ArgumentParser(description="Update a calendar event by UID.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", required=True)
    ap.add_argument("--uid", required=True)
    ap.add_argument("--summary")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--location")
    ap.add_argument("--description")
    ap.add_argument("--rrule")
    ap.add_argument("--etag", help="If-Match etag for optimistic concurrency")
    args = ap.parse_args()

    prov = resolve_provider_or_exit(args.provider, args.account)
    _client, principal = connect_or_exit(prov)
    cal = find_calendar(principal, args.calendar)
    if cal is None:
        emit_error("calendar_not_found", args.calendar, code=1)
    ev = find_event_by_uid(cal, args.uid)
    if ev is None:
        emit_error("event_not_found", args.uid, code=1)

    current_etag = getattr(ev, "etag", None)
    if args.etag and current_etag and args.etag != current_etag:
        emit_error("etag_conflict",
                   f"event changed on server (current etag={current_etag}); re-fetch",
                   code=2)

    comp = ev.icalendar_component
    if args.summary is not None:
        _set(comp, "SUMMARY", args.summary)
    if args.start is not None:
        old_start = comp.get("DTSTART")
        old_end = comp.get("DTEND")
        new_start = parse_dt(args.start)
        _set(comp, "DTSTART", new_start)
        # --start만 옮기면 기존 길이(duration)를 유지해 DTEND도 함께 이동한다.
        # (DTSTART > DTEND 모순 방지 — iCloud는 모순 이벤트를 거부한다.)
        if args.end is None and old_start is not None and old_end is not None:
            try:
                _set(comp, "DTEND", new_start + (old_end.dt - old_start.dt))
            except Exception:
                pass
    if args.end is not None:
        _set(comp, "DTEND", parse_dt(args.end))
    if args.location is not None:
        _set(comp, "LOCATION", args.location)
    if args.description is not None:
        _set(comp, "DESCRIPTION", args.description)
    if args.rrule is not None:
        _set(comp, "RRULE", parse_rrule(args.rrule))
    seq = int(comp.get("SEQUENCE", 0)) + 1
    _set(comp, "SEQUENCE", seq)

    try:
        put_event(cal, ev, etag=current_etag)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)

    # re-read to report a fresh etag (Naver omits etag on the PUT response)
    refreshed = find_event_by_uid(cal, args.uid)
    new_etag = getattr(refreshed, "etag", None) if refreshed else None

    emit({
        "status": "ok",
        "uid": args.uid,
        "new_etag": new_etag,
        "sequence": seq,
        "calendar": args.calendar,
    })


if __name__ == "__main__":
    main()
