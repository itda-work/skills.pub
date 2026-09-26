#!/usr/bin/env python3
"""itda-calendar: find_free_slots.py — 빈 시간 제안 (read-only, 결정론 계산).

전 캘린더를 조회해 클라이언트 측에서 busy를 병합하고, 근무시간 창 안에서
--duration 이상의 빈 구간을 찾는다. 서버 free-busy REPORT에 의존하지 않으므로
iCloud·네이버·custom 전부에서 성립한다. 범위는 **내 캘린더의 빈 시간** 한정 —
타인 free/busy 조회는 CalDAV 구조상 불가.
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
from event_model import DEFAULT_TZ, parse_dt  # noqa: E402
from free_slots import (busy_intervals, compute_free_slots,  # noqa: E402
                        parse_work_hours)
from email_security import sanitize_for_llm  # noqa: E402


def _as_dt(value, tz) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=tz)
    return value


def _collect_components(cals, start, end, via_objects) -> tuple[list, list]:
    """전 캘린더에서 VEVENT 컴포넌트를 수집한다. 반환 (comps, failed).

    failed 는 [{"calendar","error"}] — 조회 실패를 빈 목록으로 접지 않는다.
    실패 캘린더의 일정이 통째로 '빈 시간'으로 제안되는 조용한 실패를 막는
    fail-closed 의 재료다(호출자가 failed 비었음을 게이트로 판정).
    """
    def _fetch(c):
        try:
            return c, search_events(c["_obj"], start, end, expand=True,
                                    via_objects=via_objects), None
        except Exception as e:  # noqa: BLE001
            return c, [], e

    comps, failed = [], []
    if cals:
        with ThreadPoolExecutor(max_workers=min(8, len(cals))) as pool:
            for c, events, err in pool.map(_fetch, cals):
                if err is not None:
                    failed.append({"calendar": c["name"],
                                   "error": classify_error(err)})
                    continue
                for ev in events:
                    try:
                        comps.append(ev.icalendar_component)
                    except Exception:  # noqa: BLE001
                        failed.append({"calendar": c["name"],
                                       "error": "component_parse_failed"})
    return comps, failed


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Find free time slots across all calendars (my availability only).")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", help="calendar name or id (default: all VEVENT calendars)")
    ap.add_argument("--from", dest="from_", help="ISO date/datetime (default: now)")
    ap.add_argument("--to", help="ISO date/datetime (default: +7 days)")
    ap.add_argument("--duration", type=int, default=60,
                    help="required slot length in minutes (default: 60)")
    ap.add_argument("--work-hours", default="09:00-18:00",
                    help="daily window HH:MM-HH:MM (default: 09:00-18:00; "
                         "전일은 00:00-24:00)")
    ap.add_argument("--include-weekends", action="store_true",
                    help="include Saturday/Sunday (default: weekdays only)")
    ap.add_argument("--ignore-all-day", action="store_true",
                    help="treat all-day events as free")
    ap.add_argument("--limit", type=int, default=20,
                    help="max slots to return (default: 20)")
    ap.add_argument("--refresh", action="store_true",
                    help="디스커버리 캐시를 무시하고 캘린더 목록을 재탐색")
    args = ap.parse_args()

    if args.duration <= 0:
        emit_error("invalid_argument", "--duration must be a positive number of minutes",
                   code=1)
    try:
        work_start_min, work_end_min = parse_work_hours(args.work_hours)
    except ValueError as e:
        emit_error("invalid_argument", e, code=1)
    if args.duration > work_end_min - work_start_min:
        emit_error("invalid_argument",
                   f"--duration {args.duration}m exceeds the daily work-hours window "
                   f"({args.work_hours})", code=1)

    tz = ZoneInfo(DEFAULT_TZ)
    start = _as_dt(parse_dt(args.from_), tz) if args.from_ else datetime.now(tz)
    end = _as_dt(parse_dt(args.to), tz) if args.to else start + timedelta(days=7)
    if end <= start:
        emit_error("invalid_argument", "--to must be after --from", code=1)

    prov = resolve_provider_or_exit(args.provider, args.account)
    try:
        cals, _client = get_calendars_fast(prov, refresh=args.refresh)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)
    if args.calendar:
        cals = [c for c in cals if args.calendar in (c["name"], c["id"])]
        if not cals:
            emit_error("calendar_not_found", args.calendar, code=1)

    via_objects = prov.get("list_via_objects", False)
    # 반복 일정은 서버 expand를 요청하고(iCloud/custom), 전개가 안 오면
    # (네이버 objects 경로의 RRULE 마스터) free_slots가 클라이언트 전개한다.
    comps, failed = _collect_components(cals, start, end, via_objects)
    if failed:
        # fail-closed — 조회 실패 캘린더의 일정이 빠진 채 그 시간을 '빈 시간'
        # 으로 제안하지 않는다 (hyve Go executeCalendarFreeSlots 와 동일 계약).
        emit_error("calendar_fetch_failed",
                   "빈 시간 계산 중단 — 조회 실패 캘린더: "
                   + ", ".join(f"{f['calendar']}({f['error']})" for f in failed)
                   + ". 일부 일정이 누락된 부분 결과로는 제안하지 않는다",
                   code=1)

    expand_failures: list = []
    busy = busy_intervals(comps, start, end, tz,
                          ignore_all_day=args.ignore_all_day,
                          expand_failures=expand_failures)
    slots = compute_free_slots(
        busy, start, end,
        duration_minutes=args.duration,
        work_start_min=work_start_min, work_end_min=work_end_min,
        include_weekends=args.include_weekends,
        limit=args.limit,
    )

    out = {
        "status": "ok",
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "duration_minutes": args.duration,
        "work_hours": args.work_hours,
        "include_weekends": args.include_weekends,
        "busy_count": len(busy),
        "slots": slots,
        "note": "내 캘린더 기준 빈 시간입니다(타인 일정 미반영).",
    }
    if expand_failures:
        # 전개 실패 반복 이벤트는 첫 회차만 busy 반영됨 — 이후 회차와 겹칠 수
        # 있으므로 소비자(Claude)가 제안에 단서를 달 수 있게 표면화한다.
        out["rrule_expand_failures"] = [
            {"uid": str(c.get("UID")) if c.get("UID") is not None else None,
             "summary": sanitize_for_llm(str(c.get("SUMMARY") or ""))}
            for c in expand_failures
        ]
        out["warning"] = (
            f"반복 일정 {len(expand_failures)}건의 전개에 실패해 첫 회차만 "
            f"busy 로 반영했습니다 — 제안 슬롯이 이 일정들의 이후 회차와 겹칠 "
            f"수 있으니 사용자에게 단서를 달아 안내하세요."
        )
    emit(out)


if __name__ == "__main__":
    main()
