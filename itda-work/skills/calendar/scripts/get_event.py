#!/usr/bin/env python3
"""itda-calendar: get_event.py — UID 단건 상세 조회 (read-only, sanitized).

조회 목록에서 uid를 확보한 뒤 그 일정 하나만 자세히 볼 때 쓴다
(list_events 전량 재조회 불요). update/delete와 같은 uid 탐색 경로
(find_event_by_uid)를 재사용한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import find_calendar, find_event_by_uid  # noqa: E402
from cli_common import (connect_or_exit, emit, emit_error,  # noqa: E402
                        resolve_provider_or_exit)
from event_model import normalize_event  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Get one calendar event by UID.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", required=True)
    ap.add_argument("--uid", required=True)
    ap.add_argument("--no-sanitize", action="store_true",
                    help="raw text (unsafe for LLM)")
    args = ap.parse_args()

    prov = resolve_provider_or_exit(args.provider, args.account)
    _client, principal = connect_or_exit(prov)
    cal = find_calendar(principal, args.calendar)
    if cal is None:
        emit_error("calendar_not_found", args.calendar, code=1)
    ev = find_event_by_uid(cal, args.uid)
    if ev is None:
        emit_error("event_not_found", args.uid, code=1)

    san = None if args.no_sanitize else sanitize_for_llm
    out = normalize_event(
        ev.icalendar_component,
        sanitize_fn=san,
        url=str(ev.url),
        etag=getattr(ev, "etag", None),
    )
    out["calendar"] = args.calendar
    emit(out)


if __name__ == "__main__":
    main()
