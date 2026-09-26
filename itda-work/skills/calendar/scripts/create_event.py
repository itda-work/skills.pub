#!/usr/bin/env python3
"""itda-calendar: create_event.py — create a VEVENT (PUT).

`--check-conflicts` (옵트인) 를 주면 생성 전에 전 캘린더에서 같은 시간대 겹침을
조회해 응답 `conflicts:[...]` 로 표면화한다 — 겹침이 있어도 생성은 막지 않는다.
플래그 미지정 시 조회 왕복 없이 기존과 동일하게 동작한다.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import (find_calendar, list_calendars, save_event,  # noqa: E402
                           search_events)
from cli_common import (classify_error, connect_or_exit, emit, emit_error,  # noqa: E402
                        resolve_provider_or_exit)
from event_model import build_vevent, normalize_event  # noqa: E402
from free_slots import overlapping_components  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402


def _event_window(ical_bytes, tz) -> tuple[datetime, datetime]:
    """생성할 VEVENT 의 실제 [DTSTART, DTEND) 창 (기본 +1h/+1d 반영, tz-aware)."""
    from icalendar import Calendar

    comp = next(c for c in Calendar.from_ical(ical_bytes).walk("VEVENT"))

    def aware(value):
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=tz)
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day, tzinfo=tz)
        return value

    return aware(comp["DTSTART"].dt), aware(comp["DTEND"].dt)


def _find_conflicts(cals, via_objects, window_start, window_end, tz
                    ) -> tuple[list[dict], list[dict]]:
    """전 캘린더에서 [window) 와 겹치는 이벤트를 조회한다.

    반환 (conflicts, failed) — failed 는 [{"calendar","error"}]. 조회 실패
    캘린더를 빈 목록으로 접으면 그쪽의 겹침이 '무충돌'로 위장되므로, 실패를
    수집해 호출자가 부분 결과임을 표면화하게 한다. 반복 일정은 서버 expand 를
    요청하고(iCloud/custom), 전개가 안 오는 경로(네이버 objects)는
    overlapping_components 가 클라이언트 전개로 판정한다.
    """
    def _fetch(c):
        try:
            return c, search_events(c["_obj"], window_start, window_end,
                                    expand=True, via_objects=via_objects), None
        except Exception as e:  # noqa: BLE001
            return c, [], e

    conflicts, failed = [], []
    if cals:
        with ThreadPoolExecutor(max_workers=min(8, len(cals))) as pool:
            for c, events, err in pool.map(_fetch, cals):
                if err is not None:
                    failed.append({"calendar": c["name"],
                                   "error": classify_error(err)})
                    continue
                comps = []
                for ev in events:
                    try:
                        comps.append(ev.icalendar_component)
                    except Exception:  # noqa: BLE001
                        failed.append({"calendar": c["name"],
                                       "error": "component_parse_failed"})
                for comp in overlapping_components(comps, window_start,
                                                   window_end, tz):
                    nd = normalize_event(comp, sanitize_fn=sanitize_for_llm)
                    conflicts.append({
                        "uid": nd["uid"], "summary": nd["summary"],
                        "start": nd["start"], "end": nd["end"],
                        "all_day": nd["all_day"], "calendar": c["name"],
                    })
    conflicts.sort(key=lambda x: (x.get("start") or ""))
    return conflicts, failed


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a calendar event.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", required=True, help="target calendar name or id")
    ap.add_argument("--summary", required=True)
    ap.add_argument("--start", required=True, help="ISO date (all-day) or datetime")
    ap.add_argument("--end", help="ISO date/datetime (default: +1h, or +1d for all-day)")
    ap.add_argument("--all-day", action="store_true")
    ap.add_argument("--tz", default="Asia/Seoul")
    ap.add_argument("--location")
    ap.add_argument("--description")
    ap.add_argument("--rrule", help="e.g. 'FREQ=WEEKLY;BYDAY=MO'")
    ap.add_argument("--alarm-minutes", type=int, help="DISPLAY alarm N minutes before")
    ap.add_argument("--check-conflicts", action="store_true",
                    help="생성 전 같은 시간대 겹침을 조회해 conflicts 로 표면화 "
                         "(생성은 막지 않음 — 조회 왕복이 추가됨)")
    args = ap.parse_args()

    prov = resolve_provider_or_exit(args.provider, args.account)
    _client, principal = connect_or_exit(prov)
    cal = find_calendar(principal, args.calendar)
    if cal is None:
        emit_error("calendar_not_found", args.calendar, code=1)

    ical, uid = build_vevent(
        args.summary, args.start, args.end,
        all_day=args.all_day, tz=args.tz,
        location=args.location, description=args.description,
        rrule=args.rrule, alarm_minutes=args.alarm_minutes,
    )

    conflicts = None
    conflicts_error = None
    conflict_failed: list = []
    if args.check_conflicts:
        # 저장 전에 조회하므로 지금 만드는 이벤트 자신은 결과에 없다.
        # RRULE 생성 이벤트는 첫 회차 창만 검사한다(문서화된 한계).
        try:
            tz = ZoneInfo(args.tz)
            window_start, window_end = _event_window(ical, tz)
            cal_infos = list_calendars(principal, with_components=False)
            conflicts, conflict_failed = _find_conflicts(
                cal_infos, prov.get("list_via_objects", False),
                window_start, window_end, tz)
        except Exception as e:  # noqa: BLE001
            # 부가 관측의 실패가 주 작업(생성)을 막지 않는다 — 단 무음 금지:
            # conflicts=null + conflicts_error 로 명시 표면화한다.
            conflicts_error = classify_error(e)

    try:
        ev = save_event(cal, ical)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)

    out = {
        "status": "ok",
        "uid": uid,
        "url": str(ev.url),
        "etag": getattr(ev, "etag", None),
        "calendar": args.calendar,
        "summary": args.summary,
        "start": args.start,
    }
    if args.check_conflicts:
        out["conflicts"] = conflicts
        if conflicts_error is not None:
            out["conflicts_error"] = conflicts_error
        if conflict_failed:
            # 일부 캘린더 조회 실패 — conflicts 를 전체-무충돌로 위장하지
            # 않는다: 부분 결과임을 명시해 소비자가 단서를 달게 한다.
            out["conflict_check"] = "partial"
            out["failed_calendars"] = conflict_failed
    emit(out)


if __name__ == "__main__":
    main()
