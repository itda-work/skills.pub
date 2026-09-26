#!/usr/bin/env python3
"""itda-calendar: delete_event.py — delete a VEVENT with a confirmation gate.

`--yes` 없이 호출하면 삭제 대상 요약을 반환하고 삭제하지 않는다(되돌리기 어려운
작업 보호). `--etag`를 주면 If-Match 의미로 충돌을 감지한다.

`--occurrence <ISO>` 를 주면 반복 일정의 **그 회차만** EXDATE 로 제외한다
(시리즈는 유지). EXDATE 값은 마스터 DTSTART 와 같은 형(date/datetime·tz)으로
넣고, 수정 후 재조회로 반영을 검증한다 — 서버가 형식 불일치 EXDATE 를 조용히
무시하는 경우를 성공으로 보고하지 않기 위해서다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import find_calendar, find_event_by_uid, put_event  # noqa: E402
from cli_common import (classify_error, connect_or_exit, emit, emit_error,  # noqa: E402
                        resolve_provider_or_exit)
from event_model import DEFAULT_TZ, normalize_event, parse_dt  # noqa: E402
from free_slots import rrule_occurrences  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402


def _is_pure_date(value) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _resolve_occurrence(comp, occ_input, tz):
    """--occurrence 입력을 실제 반복 회차로 특정한다.

    반환 (exdate_value, error_code). exdate_value 는 마스터 DTSTART 와 같은 형
    (종일 반복=date, 시각 반복=aware datetime) — EXDATE 형식 정합의 핵심이다.
    입력이 날짜만이면 그 날짜의 회차를 찾고, 같은 날 여러 회차면 ambiguous.
    """
    if comp.get("RRULE") is None:
        return None, "not_recurring"
    dtstart_prop = comp.get("DTSTART")
    if dtstart_prop is None:
        return None, "not_recurring"
    master_is_date = _is_pure_date(dtstart_prop.dt)

    if isinstance(occ_input, datetime):
        window = (occ_input - timedelta(days=1), occ_input + timedelta(days=1))
    else:
        base = datetime(occ_input.year, occ_input.month, occ_input.day, tzinfo=tz)
        window = (base, base + timedelta(days=1))

    occs = rrule_occurrences(comp, window[0], window[1], tz)
    if occs is None:
        return None, "rrule_expand_failed"
    if isinstance(occ_input, datetime):
        cands = [o for o in occs if o == occ_input]
    else:
        cands = [o for o in occs if o.date() == occ_input]
    if not cands:
        return None, "occurrence_not_found"
    if len(cands) > 1:
        return None, "occurrence_ambiguous"
    occ = cands[0]
    return (occ.date() if master_is_date else occ), None


def _exdate_values(comp, tz) -> list:
    """comp 의 EXDATE 전체를 (date 또는 aware datetime) 목록으로."""
    exdates = comp.get("EXDATE")
    if exdates is None:
        return []
    if not isinstance(exdates, list):
        exdates = [exdates]
    out = []
    for exd in exdates:
        for d in getattr(exd, "dts", []):
            v = d.dt
            if isinstance(v, datetime) and v.tzinfo is None:
                v = v.replace(tzinfo=tz)
            out.append(v)
    return out


def _delete_occurrence(cal, ev, comp, args, tz, current_etag, target) -> None:
    occ_input = parse_dt(args.occurrence)
    exdate_value, err = _resolve_occurrence(comp, occ_input, tz)
    if err == "not_recurring":
        emit_error("not_recurring",
                   f"event {args.uid} has no RRULE — 단일 회차 삭제는 반복 일정 "
                   f"전용입니다(일반 일정은 --occurrence 없이 삭제)", code=1)
    if err == "rrule_expand_failed":
        emit_error("rrule_expand_failed",
                   "RRULE 전개에 실패해 회차를 특정할 수 없습니다", code=1)
    if err == "occurrence_not_found":
        emit_error("occurrence_not_found",
                   f"{args.occurrence} 에 해당하는 반복 회차가 없습니다 "
                   f"(list_events --expand 로 실제 회차를 확인하세요)", code=1)
    if err == "occurrence_ambiguous":
        emit_error("occurrence_ambiguous",
                   f"{args.occurrence} 에 회차가 여러 개입니다 — 시각까지 "
                   f"지정하세요(예: 2026-09-14T10:00:00)", code=1)

    occ_iso = exdate_value.isoformat()
    if not args.yes:
        emit({
            "status": "confirm_required",
            "action": "delete_occurrence",
            "occurrence": occ_iso,
            "target": target,
            "hint": "re-run with --yes to remove only this occurrence "
                    "(series is kept)",
        }, code=0)

    if args.etag and current_etag and args.etag != current_etag:
        emit_error("etag_conflict",
                   f"event changed on server (current etag={current_etag}); re-fetch",
                   code=2)

    comp.add("EXDATE", exdate_value)
    seq = int(comp.get("SEQUENCE", 0)) + 1
    comp.pop("SEQUENCE", None)
    comp.add("SEQUENCE", seq)

    try:
        put_event(cal, ev, etag=current_etag)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)

    # 재조회로 EXDATE 반영을 검증한다 — 형식 불일치 EXDATE 를 서버가 조용히
    # 무시하면 여기서 잡힌다(반영 안 된 삭제를 성공으로 보고하지 않는다).
    refreshed = find_event_by_uid(cal, args.uid)
    if refreshed is None:
        emit_error("exdate_not_applied",
                   "수정 후 이벤트 재조회에 실패했습니다 — 반영 미확인", code=1)
    # aware datetime 비교는 절대시각 기준이라 서버가 UTC 로 재직렬화해도 잡힌다
    applied = exdate_value in _exdate_values(refreshed.icalendar_component, tz)
    if not applied:
        emit_error("exdate_not_applied",
                   f"서버가 EXDATE({occ_iso})를 반영하지 않았습니다 — "
                   f"회차가 삭제되지 않았습니다", code=1)

    emit({
        "status": "occurrence_deleted",
        "uid": args.uid,
        "occurrence": occ_iso,
        "new_etag": getattr(refreshed, "etag", None),
        "sequence": seq,
        "calendar": args.calendar,
    })


def main() -> None:
    ap = argparse.ArgumentParser(description="Delete a calendar event by UID.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    ap.add_argument("--calendar", required=True)
    ap.add_argument("--uid", required=True)
    ap.add_argument("--occurrence",
                    help="반복 일정의 이 회차만 삭제(EXDATE) — ISO date 또는 "
                         "datetime. 시리즈 전체 삭제는 이 옵션 없이")
    ap.add_argument("--etag", help="If-Match etag for optimistic concurrency")
    ap.add_argument("--yes", action="store_true", help="confirm deletion (required)")
    args = ap.parse_args()

    prov = resolve_provider_or_exit(args.provider, args.account)
    _client, principal = connect_or_exit(prov)
    cal = find_calendar(principal, args.calendar)
    if cal is None:
        emit_error("calendar_not_found", args.calendar, code=1)
    ev = find_event_by_uid(cal, args.uid)
    if ev is None:
        emit_error("event_not_found", args.uid, code=1)

    comp = ev.icalendar_component
    target = normalize_event(
        comp,
        sanitize_fn=sanitize_for_llm,
        url=str(ev.url),
        etag=getattr(ev, "etag", None),
    )
    current_etag = getattr(ev, "etag", None)

    if args.occurrence:
        tz = ZoneInfo(DEFAULT_TZ)
        _delete_occurrence(cal, ev, comp, args, tz, current_etag, target)
        return  # _delete_occurrence 는 emit 으로 종료한다

    if not args.yes:
        emit({
            "status": "confirm_required",
            "action": "delete",
            "target": target,
            "hint": "re-run with --yes to delete this event",
        }, code=0)

    if args.etag and current_etag and args.etag != current_etag:
        emit_error("etag_conflict",
                   f"event changed on server (current etag={current_etag}); re-fetch",
                   code=2)

    try:
        ev.delete()
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)

    emit({"status": "deleted", "uid": args.uid, "calendar": args.calendar})


if __name__ == "__main__":
    main()
