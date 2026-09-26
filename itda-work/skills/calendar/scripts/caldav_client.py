#!/usr/bin/env python3
"""itda-calendar: caldav_client — thin wrapper over the caldav library.

Encapsulates connection, principal/calendar discovery, time-range search,
and event save/lookup. CRUD orchestration (ETag, confirmation) lives in the
individual scripts.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import caldav


def disable_http3(client: caldav.DAVClient) -> bool:
    """DAVClient 의 전송 세션에서 HTTP/3(QUIC) 을 끈다. 실제로 껐으면 True.

    caldav>=3 은 `niquests` 를 쓰고, `DAVClient.__init__` 이 `niquests.Session(multiplexed=…)`
    을 직접 만들며 HTTP/3 를 끌 인자를 주지 않는다. iCloud(`caldav.icloud.com`)는 응답에
    `alt-svc: h3=":443"` 을 실어 niquests 가 다음 요청부터 QUIC(UDP) 로 승격하는데, UDP GSO
    를 지원하지 않는 샌드박스(Claude Cowork 실측 2026-09-03 — `sendmsg()` `OSError: Errno 5`
    가 결정론적으로 재현, 같은 서버에 curl 은 성공)에서는 그 승격이 매번 죽는다. 재시도로는
    못 고치는 클래스라 세션을 `disable_http3=True` 로 다시 만들어 HTTP/2 이하로 고정한다.

    DAVClient 는 헤더·auth·verify 를 세션이 아니라 자기 속성(`self.headers`·`self.auth`·
    `self.ssl_verify_cert`)에 들고 요청마다 넘기므로 세션 교체는 상태를 잃지 않는다.
    `multiplexed` 는 원 세션 값을 그대로 잇는다. niquests 가 아닌 세션(requests 폴백)이면
    아무것도 하지 않는다 — 그쪽은 애초에 HTTP/3 를 시도하지 않는다.
    """
    session = getattr(client, "session", None)
    if session is None:
        return False
    try:
        import niquests
    except ImportError:  # requests 폴백 — HTTP/3 없음
        return False
    if not isinstance(session, niquests.Session):
        return False
    client.session = niquests.Session(
        multiplexed=bool(getattr(session, "multiplexed", False)),
        disable_http3=True,
    )
    return True


def connect(provider_cfg: dict, timeout: int = 30) -> caldav.DAVClient:
    """Create a DAVClient (no network I/O until a request is made).

    HTTP/3 는 항상 끈다(`disable_http3` 참조) — iCloud 의 alt-svc 승격이 UDP GSO 없는
    샌드박스에서 결정론적으로 실패한다.
    """
    client = caldav.DAVClient(
        url=provider_cfg["caldav_url"],
        username=provider_cfg["login"],
        password=provider_cfg["password"],
        timeout=timeout,
    )
    disable_http3(client)
    return client


def get_principal(client: caldav.DAVClient):
    """Authenticate and discover the current-user principal (first live call)."""
    return client.principal()


def list_calendars(principal, with_components: bool = True) -> list[dict]:
    """Return calendar info dicts; the live caldav object is under ``_obj``.

    ``with_components=False`` skips the per-calendar supported-components
    PROPFIND, which dominates latency (~0.4s each on iCloud, e.g. 4s for 10
    calendars). Event-reading callers don't need it: an ``event=True`` search
    returns nothing from a VTODO collection anyway. ``get_display_name`` is
    free because ``principal.calendars()`` already cached it.
    """
    out = []
    for cal in principal.calendars():
        try:
            name = cal.get_display_name()
        except Exception:
            name = None
        comps = []
        if with_components:
            try:
                comps = list(cal.get_supported_components())
            except Exception:
                comps = []
        url = str(cal.url)
        out.append({
            "name": name,
            "url": url,
            "id": url.rstrip("/").split("/")[-1],
            "components": comps,
            "_obj": cal,
        })
    return out


_DISCOVERY_TTL = 7 * 86400  # calendar-home url rarely changes


def _discovery_cache_path(prov: dict):
    from itda_path import resolve_cache_dir
    safe = f"{prov['name']}_{prov['account_id']}".replace("/", "_")
    return resolve_cache_dir("calendar") / f"discovery_{safe}.json"


def _wrap_calendars(cals) -> list[dict]:
    out = []
    for cal in cals:
        try:
            name = cal.get_display_name()
        except Exception:
            name = None
        url = str(cal.url)
        out.append({
            "name": name, "url": url,
            "id": url.rstrip("/").split("/")[-1],
            "components": [], "_obj": cal,
        })
    return out


def get_calendars_fast(prov: dict, refresh: bool = False, timeout: int = 30):
    """List calendars, caching the calendar-home url to skip principal discovery.

    On a warm cache, a client is built straight from the cached calendar-home
    url — skipping the current-user-principal round-trip (~1.7s on iCloud, whose
    host is also sharded to p{NN}-caldav). Falls back to full discovery on cache
    miss, ``refresh``, TTL expiry, or any error. Returns (calendars, client).
    """
    import json
    import time as _time

    cache_path = _discovery_cache_path(prov)
    if not refresh:
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            home_url = data.get("home_url")
            if home_url and _time.time() - data.get("cached_at", 0) < _DISCOVERY_TTL:
                client = caldav.DAVClient(url=home_url, username=prov["login"],
                                          password=prov["password"], timeout=timeout)
                cals = caldav.CalendarSet(client, url=home_url).calendars()
                if cals:
                    return _wrap_calendars(cals), client
        except Exception:
            pass  # fall through to full discovery

    client = connect(prov, timeout)
    principal = get_principal(client)
    try:
        home_url = str(principal.calendar_home_set.url)
        cache_path.write_text(
            json.dumps({"home_url": home_url, "cached_at": _time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass
    return list_calendars(principal, with_components=False), client


def find_calendar(principal, name_or_id: str):
    """Find a calendar object by display name, id (last URL segment), or full url."""
    for info in list_calendars(principal):
        if name_or_id in (info["name"], info["id"], info["url"]):
            return info["_obj"]
    return None


def search_events(calendar, start, end, expand: bool = False,
                  via_objects: bool = False):
    """time-range search for VEVENTs in [start, end).

    iCloud and standard CalDAV servers honor the calendar-query REPORT
    (comp-filter VEVENT + time-range), so an empty result is authoritative —
    use it directly. Naver's REPORT returns nothing even when objects exist, so
    for those providers (``via_objects=True``) enumerate objects and filter
    client-side. Per-provider control avoids a slow full-objects scan on
    standard servers whose empty result is real (e.g. a week with no events).
    """
    if via_objects:
        return _client_filter_events(calendar, start, end)
    return calendar.search(start=start, end=end, event=True, expand=expand)


def _component_of(obj):
    """Return the VEVENT/VTODO component of a caldav object, loading if needed."""
    try:
        comp = obj.icalendar_component
        if comp is not None:
            return comp
    except Exception:
        pass
    try:
        obj.load()
        return obj.icalendar_component
    except Exception:
        return None


def _as_aware(value):
    """Coerce date/naive-datetime to a tz-aware datetime (UTC assumed)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return value


def _event_overlaps(comp, start, end) -> bool:
    dtstart = comp.get("DTSTART")
    if dtstart is None:
        return False
    s = _as_aware(dtstart.dt)
    dtend = comp.get("DTEND")
    e = _as_aware(dtend.dt) if dtend is not None else s
    if comp.get("RRULE") is not None:
        return True  # recurring: include conservatively (no expansion in v1)
    return s < end and e > start


def _client_filter_events(calendar, start, end):
    """Fallback for servers without working comp-filter/time-range REPORT.

    Enumerate calendar objects and filter VEVENTs by time range client-side.
    """
    objs = None
    for getter in (lambda: calendar.objects(load_objects=True),
                   lambda: calendar.objects()):
        try:
            objs = list(getter())
            break
        except Exception:
            objs = None
    if not objs:
        return []
    s_aware, e_aware = _as_aware(start), _as_aware(end)
    out = []
    for obj in objs:
        comp = _component_of(obj)
        if comp is None or comp.name != "VEVENT":
            continue
        if _event_overlaps(comp, s_aware, e_aware):
            out.append(obj)
    return out


def find_event_by_uid(calendar, uid: str):
    """Return the Event with the given UID, or None.

    Tries native ``event_by_uid`` (a UID REPORT) first; iCloud rejects that
    with ``412 Precondition Failed``, so fall back to enumerating the
    calendar's events and matching the UID property (iCloud-compatible).
    """
    try:
        return calendar.event_by_uid(uid)
    except Exception:
        pass
    for getter in (lambda: calendar.events(),
                   lambda: calendar.objects(load_objects=True)):
        try:
            for obj in getter():
                comp = _component_of(obj)
                if (comp is not None and comp.name == "VEVENT"
                        and str(comp.get("UID")) == uid):
                    try:
                        obj.load()  # events()/objects() omit ETag; load() fills it
                    except Exception:
                        pass
                    return obj
        except Exception:
            continue
    return None


def save_event(calendar, ical_bytes):
    """PUT a new event from iCalendar text/bytes. Returns the caldav Event."""
    data = ical_bytes.decode() if isinstance(ical_bytes, bytes) else ical_bytes
    return calendar.save_event(data)


def put_event(calendar, ev, etag: str | None = None):
    """Write modified event data, compatible with both iCloud and Naver.

    Tries caldav's ``Event.save()`` first — iCloud forbids a bare client PUT
    (403) and requires this path. Naver instead answers a *successful* PUT with
    ``200 OK`` that caldav raises as PutError, so fall back to a direct
    ``client.put`` (idempotent re-PUT) that accepts the 200.
    """
    try:
        ev.save()
        return
    except Exception:
        pass
    url = str(ev.url)
    data = ev.icalendar_instance.to_ical()
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    headers = {"Content-Type": "text/calendar; charset=utf-8"}
    if etag:
        headers["If-Match"] = etag
    return calendar.client.put(url, data, headers)
