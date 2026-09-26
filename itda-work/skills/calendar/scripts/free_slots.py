#!/usr/bin/env python3
"""itda-calendar: free_slots — 빈 시간 계산 순수 로직 (네트워크 없음).

전 캘린더에서 조회한 VEVENT들을 busy 구간으로 병합하고, 근무시간 창 안에서
지정 길이 이상의 빈 구간(gap)을 결정론적으로 계산한다. 겹침 계산은 LLM이
자주 틀리는 영역이라 코드가 담당한다(서버 free-busy REPORT 비의존 —
iCloud·네이버·custom 전부 성립).

반복 일정: 서버 expand가 안 되는 경로(네이버 objects)를 위해 RRULE 마스터를
dateutil로 클라이언트 전개한다(EXDATE 반영). RECURRENCE-ID 오버라이드(회차
개별 이동)는 미지원 — 마스터 규칙 기준으로 보수적으로 busy 처리한다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

# 최대 전개 회차 수 — 폭주 RRULE(초 단위 반복 등) 방어
_MAX_OCCURRENCES = 1000


def parse_work_hours(spec: str) -> tuple[int, int]:
    """'09:00-18:00' -> (분 단위 시작, 분 단위 끝). '24:00' 끝은 자정(1440)."""
    try:
        start_s, end_s = spec.split("-", 1)
        sh, sm = start_s.strip().split(":")
        eh, em = end_s.strip().split(":")
        start = int(sh) * 60 + int(sm)
        end = int(eh) * 60 + int(em)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"invalid work-hours '{spec}' (expected HH:MM-HH:MM)") from e
    if not (0 <= start < end <= 1440):
        raise ValueError(f"invalid work-hours '{spec}' (start < end, within 00:00-24:00)")
    return start, end


def _as_aware(value, tz) -> datetime:
    """date/naive-datetime -> tz-aware datetime (naive는 tz 부여)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=tz)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=tz)
    return value


def _event_duration(comp, dtstart) -> timedelta:
    """DTEND 우선, 없으면 DURATION, 둘 다 없으면 종일=1일 / 시각=0."""
    dtend = comp.get("DTEND")
    if dtend is not None:
        try:
            return dtend.dt - dtstart
        except TypeError:
            pass
    dur = comp.get("DURATION")
    if dur is not None:
        try:
            return dur.dt
        except Exception:  # noqa: BLE001
            pass
    if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
        return timedelta(days=1)
    return timedelta(0)


def _expand_rrule(comp, dtstart_aware, duration, window_start, window_end):
    """RRULE 마스터를 dateutil로 [window) 안에서 전개. 실패 시 None(호출자가 폴백)."""
    from dateutil.rrule import rruleset, rrulestr

    rrule_prop = comp.get("RRULE")
    rrule_str = rrule_prop.to_ical().decode()
    try:
        rs = rruleset()
        rs.rrule(rrulestr(rrule_str, dtstart=dtstart_aware))
        exdates = comp.get("EXDATE")
        if exdates is not None:
            if not isinstance(exdates, list):
                exdates = [exdates]
            for exd in exdates:
                for d in exd.dts:
                    rs.exdate(_as_aware(d.dt, dtstart_aware.tzinfo))
        # 이벤트가 창 시작 전에 시작해 창에 걸치는 회차도 잡는다
        search_from = window_start - duration
        out = []
        for occ in rs.between(search_from, window_end, inc=True):
            out.append((occ, occ + duration))
            if len(out) >= _MAX_OCCURRENCES:
                break
        return out
    except Exception:  # noqa: BLE001
        return None  # UNTIL naive/aware 불일치 등 — 호출자가 마스터 1건 폴백


def busy_intervals(components, window_start: datetime, window_end: datetime,
                   tz, *, ignore_all_day: bool = False,
                   expand_failures: list | None = None
                   ) -> list[tuple[datetime, datetime]]:
    """VEVENT 컴포넌트들 -> [window) 와 겹치는 busy (start,end) 목록.

    제외: STATUS=CANCELLED, TRANSP=TRANSPARENT(캘린더 앱의 '한가함' 표시 —
    iOS 종일 이벤트 기본값), ignore_all_day 시 종일 이벤트 전부.

    RRULE 전개 실패는 마스터 1건 busy 로 보수 폴백하는데, 그러면 이후 회차가
    빈 시간으로 새므로 무음이면 안 된다 — ``expand_failures`` 에 list 를 주면
    폴백된 컴포넌트가 담긴다(호출자가 경고로 표면화).
    """
    out: list[tuple[datetime, datetime]] = []
    for comp in components:
        if comp is None or comp.name != "VEVENT":
            continue
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if str(comp.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue
        dtstart_prop = comp.get("DTSTART")
        if dtstart_prop is None:
            continue
        raw_start = dtstart_prop.dt
        all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)
        if all_day and ignore_all_day:
            continue
        duration = _event_duration(comp, raw_start)
        start = _as_aware(raw_start, tz)

        if comp.get("RRULE") is not None:
            occs = _expand_rrule(comp, start, duration, window_start, window_end)
            if occs is None:
                if expand_failures is not None:
                    expand_failures.append(comp)
                occs = [(start, start + duration)]
        else:
            occs = [(start, start + duration)]

        for s, e in occs:
            if e <= s:
                continue  # 0-length(point-in-time)는 시간을 점유하지 않는다
            if s < window_end and e > window_start:
                out.append((s, e))
    return out


def rrule_occurrences(comp, window_start: datetime, window_end: datetime,
                      tz) -> list[datetime] | None:
    """RRULE 마스터의 회차 시작 시각들을 [window) 에서 전개한다.

    RRULE 이 없으면 None(호출자가 먼저 분기하는 것이 정상), 전개 실패
    (UNTIL naive/aware 불일치 등)도 None — busy_intervals 의 보수 폴백과 달리
    회차 특정이 목적이라 폴백이 없다(틀린 회차를 지우면 안 된다).
    """
    if comp is None or comp.get("RRULE") is None:
        return None
    dtstart_prop = comp.get("DTSTART")
    if dtstart_prop is None:
        return None
    start = _as_aware(dtstart_prop.dt, tz)
    occs = _expand_rrule(comp, start, timedelta(0), window_start, window_end)
    if occs is None:
        return None
    return [s for s, _ in occs if window_start <= s < window_end]


def overlapping_components(components, window_start: datetime, window_end: datetime,
                           tz) -> list:
    """[window) 와 실제로 겹치는 VEVENT 컴포넌트만 돌려준다 (겹침 표면화용).

    busy_intervals 와 같은 판정을 공유한다 — CANCELLED·TRANSPARENT 제외,
    RRULE 은 클라이언트 전개로 실제 회차가 창에 있는지 본다. 판정을 복제하면
    free-slots 와 conflicts 가 갈라지므로 반드시 이 경유로 쓴다.
    """
    return [c for c in components
            if busy_intervals([c], window_start, window_end, tz)]


def merge_intervals(intervals: list[tuple[datetime, datetime]]
                    ) -> list[tuple[datetime, datetime]]:
    """겹치거나 맞닿은 구간을 병합해 정렬된 목록으로."""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for s, e in ordered[1:]:
        ls, le = merged[-1]
        if s <= le:
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged


def compute_free_slots(busy: list[tuple[datetime, datetime]],
                       range_start: datetime, range_end: datetime,
                       *, duration_minutes: int,
                       work_start_min: int, work_end_min: int,
                       include_weekends: bool = False,
                       limit: int | None = None) -> list[dict]:
    """근무시간 창 안에서 duration 이상의 빈 구간을 찾는다.

    반환 슬롯은 gap 전체(잘라내지 않음) — Claude가 그 안에서 시각을 제안한다.
    """
    merged = merge_intervals(busy)
    slots: list[dict] = []
    need = timedelta(minutes=duration_minutes)
    tz = range_start.tzinfo

    day = range_start.date()
    last_day = range_end.date()
    while day <= last_day:
        if not include_weekends and day.weekday() >= 5:
            day += timedelta(days=1)
            continue
        day_base = datetime(day.year, day.month, day.day, tzinfo=tz)
        win_s = max(day_base + timedelta(minutes=work_start_min), range_start)
        win_e = min(day_base + timedelta(minutes=work_end_min), range_end)
        if win_e - win_s >= need:
            cursor = win_s
            for bs, be in merged:
                if be <= cursor or bs >= win_e:
                    continue
                if bs - cursor >= need:
                    slots.append(_slot(cursor, bs))
                cursor = max(cursor, be)
                if cursor >= win_e:
                    break
            if win_e - cursor >= need:
                slots.append(_slot(cursor, win_e))
        day += timedelta(days=1)
        if limit is not None and len(slots) >= limit:
            slots = slots[:limit]
            break
    return slots


def _slot(start: datetime, end: datetime) -> dict:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_minutes": int((end - start).total_seconds() // 60),
    }
