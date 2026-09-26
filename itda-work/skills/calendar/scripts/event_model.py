#!/usr/bin/env python3
"""itda-calendar: event_model — icalendar VEVENT <-> normalized dict.

Timezone-aware (default Asia/Seoul). Handles all-day (VALUE=DATE) vs timed
events, RRULE, and DISPLAY alarms. Uses the `icalendar` library for RFC 5545
serialization (line-folding, escaping, VTIMEZONE).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar, Event
from icalendar.prop import vRecur

DEFAULT_TZ = "Asia/Seoul"
PRODID = "-//itda-skills//calendar//KO"


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------


def parse_dt(value: str, default_tz: str = DEFAULT_TZ):
    """Parse an ISO-ish string into date (all-day) or tz-aware datetime.

    'YYYY-MM-DD'              -> date  (all-day)
    'YYYY-MM-DDTHH:MM[:SS]'   -> datetime (naive -> default_tz applied)
    '...+09:00' / '...Z'      -> datetime (offset preserved)
    """
    value = value.strip()
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return date.fromisoformat(value)
    iso = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(default_tz))
    return dt


def _is_pure_date(value) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def parse_rrule(spec: str) -> vRecur:
    """'FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10' (or with 'RRULE:' prefix) -> vRecur."""
    spec = spec.strip()
    if spec.upper().startswith("RRULE:"):
        spec = spec[6:]
    return vRecur.from_ical(spec)


_MAILTO_PREFIX = "mailto:"


def normalize_mailto(value) -> str | None:
    """cal-address 값을 비교 가능한 순수 주소로 정규화한다.

    'MAILTO:Boss@Example.COM' -> 'boss@example.com'
    'boss@example.com'        -> 'boss@example.com'
    None / 빈 값               -> None

    `mailto:` 접두는 대소문자 무관하게 제거하고, 공백 트림 후 소문자화한다.
    소비자(morning-brief 등)가 계정 주소를 같은 규칙으로 정규화해 주최자
    일치를 판정하므로 **이 함수가 비교 키의 단일 정의**다 — 호출부에서
    별도 lower()/strip() 규칙을 복제하지 않는다.

    CN= 등 파라미터는 대상이 아니다(icalendar 가 params 로 분리하므로
    str(vCalAddress) 에는 주소만 들어온다 — 실측 확인).
    delegated organizer(SENT-BY 파라미터)는 **미지원**: 대리 발송자가 아니라
    ORGANIZER 주소 자체만 본다.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s[:len(_MAILTO_PREFIX)].lower() == _MAILTO_PREFIX:
        s = s[len(_MAILTO_PREFIX):]
    s = s.strip().lower()
    return s or None


# ---------------------------------------------------------------------------
# build (dict/args -> VEVENT)
# ---------------------------------------------------------------------------


def build_vevent(summary: str, start: str, end: str | None = None, *,
                 all_day: bool = False, tz: str = DEFAULT_TZ,
                 location: str | None = None, description: str | None = None,
                 rrule: str | None = None, alarm_minutes: int | None = None,
                 uid: str | None = None, sequence: int = 0) -> tuple[bytes, str]:
    """Build a VCALENDAR wrapping one VEVENT. Returns (ical_bytes, uid)."""
    ev = Event()
    uid = uid or f"{uuid.uuid4()}@itda-calendar"
    ev.add("uid", uid)
    ev.add("summary", summary)

    dtstart = parse_dt(start, tz)
    if all_day and not _is_pure_date(dtstart):
        dtstart = dtstart.date()

    if _is_pure_date(dtstart):
        ev.add("dtstart", dtstart)
        if end:
            dtend = parse_dt(end, tz)
            dtend = dtend if _is_pure_date(dtend) else dtend.date()
        else:
            dtend = dtstart + timedelta(days=1)
        ev.add("dtend", dtend)
    else:
        ev.add("dtstart", dtstart)
        if end:
            dtend = parse_dt(end, tz)
            if _is_pure_date(dtend):
                dtend = datetime.combine(dtend, dtstart.timetz())
        else:
            dtend = dtstart + timedelta(hours=1)
        ev.add("dtend", dtend)

    if location:
        ev.add("location", location)
    if description:
        ev.add("description", description)
    if rrule:
        ev.add("rrule", parse_rrule(rrule))
    ev.add("dtstamp", datetime.now(timezone.utc))
    ev.add("sequence", sequence)

    if alarm_minutes is not None:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", summary)
        alarm.add("trigger", timedelta(minutes=-abs(alarm_minutes)))
        ev.add_component(alarm)

    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add_component(ev)
    return cal.to_ical(), uid


# ---------------------------------------------------------------------------
# normalize (VEVENT component -> dict)
# ---------------------------------------------------------------------------


def _dt_to_iso(value) -> tuple[str | None, bool]:
    """Return (iso_string, is_all_day)."""
    if value is None:
        return None, False
    dt = value.dt if hasattr(value, "dt") else value
    if _is_pure_date(dt):
        return dt.isoformat(), True
    if isinstance(dt, datetime):
        return dt.isoformat(), False
    return str(dt), False


def normalize_event(component, *, sanitize_fn=None,
                    url: str | None = None, etag: str | None = None) -> dict:
    """icalendar VEVENT component -> normalized dict (LLM-safe if sanitize_fn given)."""
    def text(key):
        v = component.get(key)
        return str(v) if v is not None else None

    summary = text("SUMMARY") or ""
    description = text("DESCRIPTION")
    location = text("LOCATION")
    if sanitize_fn is not None:
        summary = sanitize_fn(summary)
        description = sanitize_fn(description) if description else None
        location = sanitize_fn(location) if location else None

    # ORGANIZER 는 자유 텍스트가 아니라 주소지만, 서버가 보낸 값이 그대로
    # LLM 컨텍스트로 들어가므로 sanitize_fn 이 있으면 먼저 태운다. 정상 주소는
    # ASCII 라 sanitize 가 항등이고(NFKC·패턴 미매칭), 인젝션이 실린 값만
    # [FILTERED] 로 바뀌어 계정 주소와 불일치 -> 주최자 아님으로 접힌다(fail-safe).
    # sanitize 를 먼저, 정규화를 나중에 두어 결과는 항상 소문자·트림 상태다.
    organizer_prop = component.get("ORGANIZER")
    if organizer_prop is None:
        organizer = None
    else:
        organizer_text = str(organizer_prop)
        if sanitize_fn is not None:
            organizer_text = sanitize_fn(organizer_text)
        organizer = normalize_mailto(organizer_text)

    start, all_day = _dt_to_iso(component.get("DTSTART"))
    end, _ = _dt_to_iso(component.get("DTEND"))

    rrule_prop = component.get("RRULE")
    rrule = rrule_prop.to_ical().decode() if rrule_prop is not None else None

    alarms = []
    for sub in getattr(component, "subcomponents", []):
        if sub.name == "VALARM":
            trig = sub.get("TRIGGER")
            if trig is not None:
                alarms.append(str(trig.dt) if hasattr(trig, "dt") else str(trig))

    out = {
        "uid": text("UID"),
        "summary": summary,
        "start": start,
        "end": end,
        "all_day": all_day,
        "location": location,
        "description": description,
        "organizer": organizer,
        "rrule": rrule,
        # 회차 구분자 — 전개 전(마스터·단발)은 None, expand_recurrences 가 채운다.
        "recurrence_start": None,
        "status": text("STATUS"),
        "alarms": alarms,
    }
    if url is not None:
        out["url"] = url
    if etag is not None:
        out["etag"] = etag
    return out


def _master_duration(normalized: dict) -> timedelta:
    """정규화 dict 의 start/end 로 마스터 1회차 길이를 구한다.

    end 가 없으면 종일=1일 / 시각=0 (RFC 5545 기본값과 동형).
    """
    start = normalized.get("start")
    end = normalized.get("end")
    if normalized.get("all_day"):
        ds = date.fromisoformat(start)
        de = date.fromisoformat(end) if end else ds + timedelta(days=1)
        return de - ds
    ds = datetime.fromisoformat(start)
    de = datetime.fromisoformat(end) if end else ds
    return de - ds


def expand_recurrences(normalized: dict, component, window_start: datetime,
                       window_end: datetime, tz, *,
                       failures: list | None = None) -> list[dict]:
    """RRULE 마스터 정규화 dict -> [window) 안 회차 dict 목록.

    서버가 expand 를 안 해 주는 경로(네이버 objects)에서 `list_events --expand`
    를 성립시킨다. 마스터만 돌려주면 시작일이 과거인 주간·일간 반복이 오늘·내일
    분류에서 통째로 빠진다(#1638 C2).

    - RRULE 이 없으면 `[normalized]` 그대로(단발 이벤트는 손대지 않는다).
    - 회차는 **마스터 UID 를 유지**하고 `recurrence_start` 로 구분한다 —
      uid 로 update/delete 하면 시리즈가 대상이므로 회차 삭제는
      `delete_event.py --occurrence` 를 쓴다.
    - **RECURRENCE-ID 오버라이드(회차 개별 이동·수정)는 미반영** — 마스터 규칙
      기준으로 전개한다(`free_slots` 의 기존 한계와 동일).
    - 전개 실패(UNTIL naive/aware 불일치 등)는 마스터 1건으로 보수 폴백하되
      무음이면 안 된다 — `failures` 에 list 를 주면 그 dict 가 담긴다.

    판정은 `free_slots.rrule_occurrences` 를 공유한다. 여기서 전개 규칙을
    복제하면 free-slots·conflicts·목록이 서로 다른 회차를 말하게 된다.
    """
    from free_slots import rrule_occurrences  # 지역 import — 순환 방지·경량 유지

    if component is None or component.get("RRULE") is None:
        return [normalized]
    if not normalized.get("start"):
        return [normalized]

    occs = rrule_occurrences(component, window_start, window_end, tz)
    if occs is None:
        if failures is not None:
            failures.append(normalized)
        return [normalized]
    if not occs:
        return []  # 창 안에 회차가 없다 — 마스터를 남기면 없는 일정이 보인다

    duration = _master_duration(normalized)
    all_day = bool(normalized.get("all_day"))
    out = []
    for occ in occs:
        item = dict(normalized)
        if all_day:
            d = occ.date()
            item["start"] = d.isoformat()
            item["end"] = (d + duration).isoformat()
            item["recurrence_start"] = d.isoformat()
        else:
            item["start"] = occ.isoformat()
            item["end"] = (occ + duration).isoformat()
            item["recurrence_start"] = occ.isoformat()
        out.append(item)
    return out


def event_matches_query(normalized: dict, query: str) -> bool:
    """정규화 dict의 SUMMARY/DESCRIPTION/LOCATION에 대한 대소문자 무시 substring 매칭.

    sanitize 이후의 정규화 결과를 대상으로 한다 — sanitize가 치환한 텍스트
    기준으로 매칭해, 사용자가 화면에서 본 것과 필터 결과가 일치한다.
    """
    q = query.casefold()
    return any(q in v.casefold()
               for v in (normalized.get("summary"),
                         normalized.get("description"),
                         normalized.get("location"))
               if v)
