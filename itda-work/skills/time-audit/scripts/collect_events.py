#!/usr/bin/env python3
"""time-audit 수집 — itda-hyve `calendar_events` 응답에서 timelog.json 초안을 만든다.

이 스크립트는 **네트워크를 하지 않고, 자격증명·환경변수·형제 스킬 스크립트를 읽거나
실행하지 않는다.** 일정은 LLM 이 itda-hyve 도구(`accounts_list`·`calendar_events`)로
받아 입력 폴더에 JSON 으로 저장하고, 이 스크립트는 그 파일만 읽는다(morning-brief
`gather.py` 의 `--plan`/`--input` 방식과 같다).

두 모드:

* ``--plan`` — 입력 폴더를 보고 **아직 부르지 않은 도구 호출**(도구·인자·저장 파일)을
  JSON 으로 낸다. 인자에 ``save_dir``(입력 폴더의 호스트 경로 — ``--save-dir``)·``save_as``·
  ``overwrite`` 가 들어 있어 itda-hyve 가 응답을 입력 폴더에 직접 쓴다(itda-hyve 0.9.2 —
  LLM 이 응답을 옮겨 적지 않는다, itda-work/skills#34). 다시 ``--plan`` 을 돌려
  ``status: complete`` 가 나오면 끝이다. 조회 창(요청 기간 그대로)을 LLM 이 고르지 않게
  하려는 단계다.
* 기본(수집) — 입력 폴더 → timelog.json 초안(``--out``). ``provisional: true``,
  카테고리 미배정 — 배정·제외·난이도는 매핑 인터뷰가 채운다.

부분본을 전량으로 쓰지 않는다: 대상 계정 하나라도 조회 실패·응답 누락·상한 초과·
캘린더 일부 실패·전개하지 못한 반복 규칙이 있으면 **파일을 쓰지 않고 exit 1** 로
전부 나열한다. 빠진 시간이 있는 초안으로 집계하면 리포트 수치가 조용히 틀린다.

exit: 0 = 초안 작성(또는 plan 출력) · 1 = 수집 불완전(파일 안 씀) ·
      2 = 사용법·입력 오류 · 3 = 요청 기간 일정 0건(파일 안 씀)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Seoul"
SOURCE = "itda-hyve"
EVENTS_LIMIT = 1000        # calendar_events 최대값
MAX_PERIOD_DAYS = 366      # calendar_events 조회 기간 상한(1년)
ACCOUNTS_FILE = "accounts.json"


def _f_calendar(i: int) -> str:
    # 계정은 이름 대신 accounts.json 의 순번으로 가리킨다(이름에 한글·공백·슬래시가 올 수 있다).
    return f"calendar-{i}.json"


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):  # pragma: no cover - 구버전/파이프 방어
            pass


class InputError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class Inputs:
    """저장된 도구 응답을 이름으로 읽는다. 각 항목은 없음·도구 실패·응답 셋 중 하나다."""

    def __init__(self, path: Path) -> None:
        if not path.is_dir():
            raise InputError("input_missing", f"{path}: 폴더가 아니다")
        self.path = path

    def exists(self, name: str) -> bool:
        return (self.path / name).is_file()

    def load(self, name: str) -> tuple[str, object]:
        """('missing'|'error'|'ok', 값). 도구 실패는 `{"error": {"code","message"}}`."""
        if not self.exists(name):
            return "missing", None
        try:
            data = json.loads((self.path / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return "error", {"code": "bad_json", "message": str(exc)[:200]}
        if isinstance(data, dict) and "error" in data:
            err = data.get("error")
            if isinstance(err, dict):
                return "error", {"code": str(err.get("code") or "tool_error"),
                                 "message": str(err.get("message") or "")[:200]}
            return "error", {"code": "tool_error", "message": str(err)[:200]}
        if not isinstance(data, dict):
            return "error", {"code": "bad_shape", "message": "객체가 아니다"}
        return "ok", data


def _accounts(inp: Inputs, only: list[str]) -> tuple[str, list[dict], dict | None]:
    """accounts.json → (상태, [{index,name,calendar,reason}], 오류)."""
    state, data = inp.load(ACCOUNTS_FILE)
    if state != "ok":
        return state, [], data if state == "error" else None
    rows = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return "error", [], {"code": "bad_shape", "message": "accounts 배열이 없다"}
    if rows and not any(isinstance(r, dict) and "calendar" in r for r in rows):
        # 캘린더 도구는 itda-hyve 0.9.0 에 들어왔고 그때부터 계정마다 calendar 필드가 있다.
        return "error", [], {"code": "itda_hyve_outdated",
                             "message": "accounts_list 에 calendar 필드가 없다 — itda-hyve 0.10.1 이상 필요"}
    out: list[dict] = []
    names = set()
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or not str(row.get("name") or "").strip():
            continue
        name = str(row["name"])
        names.add(name)
        if only and name not in only:
            continue
        cal = row.get("calendar") if isinstance(row.get("calendar"), dict) else {}
        out.append({"index": i, "name": name,
                    "calendar": cal.get("supported") is True,
                    "reason": str(cal.get("reason") or "")})
    unknown = [n for n in only if n not in names]
    if unknown:
        return "error", [], {"code": "account_not_found",
                             "message": "accounts_list 에 없는 계정: " + ", ".join(unknown)}
    return "ok", out, None


def _window(p_from: date, p_to: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    lo = datetime(p_from.year, p_from.month, p_from.day, tzinfo=tz)
    hi = datetime(p_to.year, p_to.month, p_to.day, tzinfo=tz) + timedelta(days=1)
    return lo, hi


def _parse_dt(raw, tz: ZoneInfo) -> datetime | None:
    """RFC 3339·ISO 시각. `Z` 도 받는다(3.10 fromisoformat 은 못 읽는다)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt


def _point(raw, tz: ZoneInfo) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    if len(raw) == 10:
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            return None
        return datetime(d.year, d.month, d.day, tzinfo=tz)
    dt = _parse_dt(raw, tz)
    return dt.astimezone(tz) if dt else None


# --------------------------------------------------------------------------
# 반복 일정 전개 — morning-brief `scripts/gather.py` 와 바이트 동일한 사본이다.
# 한쪽을 고치면 다른 쪽도 고친다(tests/test_collect_events.py 가 동일성을 강제한다).
# 스킬마다 사본을 두는 이유: 단일 .skill 업로드·배포본이 형제 스킬 파일을 못 본다.
# --------------------------------------------------------------------------

_WEEKDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_BYDAY = re.compile(r"^([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)$")
_RRULE_KEYS = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY",
               "BYMONTH", "WKST"}
_MAX_STEPS = 20000


class RRuleUnsupported(Exception):
    pass


def _parse_rrule(text: str) -> dict:
    body = text.strip()
    if body.upper().startswith("RRULE:"):
        body = body[6:]
    rule: dict[str, str] = {}
    for part in body.split(";"):
        if not part.strip():
            continue
        key, _, value = part.partition("=")
        key = key.strip().upper()
        if key not in _RRULE_KEYS:
            raise RRuleUnsupported(key)
        rule[key] = value.strip().upper()
    if rule.get("FREQ") not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        raise RRuleUnsupported(rule.get("FREQ") or "FREQ")
    return rule


def _ints(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        return [int(v) for v in value.split(",") if v.strip()]
    except ValueError as exc:
        raise RRuleUnsupported(value) from exc


def _bydays(value: str | None) -> list[tuple[int | None, int]]:
    out = []
    for part in (value or "").split(","):
        if not part.strip():
            continue
        m = _BYDAY.match(part.strip())
        if not m:
            raise RRuleUnsupported(part)
        out.append((int(m.group(1)) if m.group(1) else None, _WEEKDAY[m.group(2)]))
    return out


def _until(value: str | None, tz: ZoneInfo, all_day: bool) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        if len(text) == 8:
            d = datetime.strptime(text, "%Y%m%d")
            return d.replace(hour=23, minute=59, second=59, tzinfo=tz)
        if text.endswith("Z"):
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=ZoneInfo("UTC")).astimezone(tz)
        return datetime.strptime(text, "%Y%m%dT%H%M%S").replace(tzinfo=tz)
    except ValueError as exc:
        raise RRuleUnsupported(value) from exc


def _month_days(year: int, month: int) -> int:
    nxt = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return (nxt - date(year, month, 1)).days


def _days_in_month(year: int, month: int, rule: dict, start: datetime) -> list[int]:
    """그 달에서 규칙에 맞는 날(1..말일). BYDAY 는 서수(2MO·-1FR)도 받는다."""
    last = _month_days(year, month)
    days: set[int] = set()
    bydays = _bydays(rule.get("BYDAY"))
    monthdays = _ints(rule.get("BYMONTHDAY"))
    if bydays:
        for nth, wd in bydays:
            hits = [d for d in range(1, last + 1)
                    if date(year, month, d).weekday() == wd]
            if nth is None:
                days.update(hits)
            elif 0 < nth <= len(hits):
                days.add(hits[nth - 1])
            elif nth < 0 and -nth <= len(hits):
                days.add(hits[nth])
        if monthdays:  # 둘 다 있으면 교집합(RFC 5545)
            want = {d if d > 0 else last + 1 + d for d in monthdays}
            days &= want
    elif monthdays:
        for d in monthdays:
            d = d if d > 0 else last + 1 + d
            if 1 <= d <= last:
                days.add(d)
    else:
        if start.day <= last:  # 31일 시작 월간 반복은 짧은 달을 건너뛴다
            days.add(start.day)
    return sorted(days)


def expand_rrule(rrule: str, start: datetime, lo: datetime, hi: datetime,
                 tz: ZoneInfo, all_day: bool) -> list[datetime]:
    """[lo, hi) 이전까지의 회차 시작 시각(시작 시각순). 규칙을 못 읽으면 RRuleUnsupported.

    지원: FREQ=DAILY|WEEKLY|MONTHLY|YEARLY · INTERVAL · COUNT · UNTIL · BYDAY
    (월간은 서수 포함) · BYMONTHDAY · BYMONTH. 그 밖의 키는 지원하지 않는다고 말한다
    — 추측으로 회차를 만들지 않는다. 제외일(EXDATE)은 itda-hyve 응답에 없어 반영하지 못한다.
    """
    rule = _parse_rrule(rrule)
    freq = rule["FREQ"]
    interval = max(1, (_ints(rule.get("INTERVAL")) or [1])[0])
    count = (_ints(rule.get("COUNT")) or [None])[0]
    until = _until(rule.get("UNTIL"), tz, all_day)
    months = _ints(rule.get("BYMONTH"))
    bydays = _bydays(rule.get("BYDAY"))
    if freq == "YEARLY" and bydays:
        raise RRuleUnsupported("YEARLY+BYDAY")
    if freq in ("DAILY", "WEEKLY") and any(n is not None for n, _ in bydays):
        raise RRuleUnsupported("BYDAY ordinal")
    hms = (start.hour, start.minute, start.second)

    def at(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, *hms, tzinfo=tz)

    def periods():
        d0 = start.date()
        if freq == "DAILY":
            step = 0
            while True:
                yield [d0 + timedelta(days=step * interval)]
                step += 1
        elif freq == "WEEKLY":
            wds = sorted({wd for _, wd in bydays}) or [d0.weekday()]
            week0 = d0 - timedelta(days=d0.weekday())
            step = 0
            while True:
                base = week0 + timedelta(weeks=step * interval)
                yield [base + timedelta(days=wd) for wd in wds]
                step += 1
        elif freq == "MONTHLY":
            step = 0
            while True:
                total = d0.month - 1 + step * interval
                y, m = d0.year + total // 12, total % 12 + 1
                yield [date(y, m, d) for d in _days_in_month(y, m, rule, start)]
                step += 1
        else:  # YEARLY
            step = 0
            while True:
                y = d0.year + step * interval
                out = []
                for m in (months or [d0.month]):
                    for d in _days_in_month(y, m, rule, start):
                        out.append(date(y, m, d))
                yield sorted(out)
                step += 1

    result: list[datetime] = []
    seen = 0
    steps = 0
    for days in periods():
        steps += 1
        if steps > _MAX_STEPS:  # 창까지 못 갔다 — 빠진 회차를 조용히 두지 않는다
            raise RRuleUnsupported("too_many_steps")
        for d in days:
            occ = at(d)
            if occ < start:
                continue
            if months and d.month not in months:
                continue
            if freq == "DAILY" and bydays and d.weekday() not in {w for _, w in bydays}:
                continue
            if until is not None and occ > until:
                return result
            seen += 1
            if count is not None and seen > count:
                return result
            if occ >= hi:
                return result
            if occ >= lo:
                result.append(occ)
        if days and at(days[-1]) >= hi:
            return result
    return result



# --------------------------------------------------------------------------
# calendar_events 응답 → timelog 이벤트
# --------------------------------------------------------------------------

def _bounds(ev: dict, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    all_day = bool(ev.get("all_day"))
    start = _point(ev.get("start"), tz)
    if start is None:
        return None
    end = _point(ev.get("end"), tz)
    if end is None or end < start:
        end = start + timedelta(days=1) if all_day else start
    return start, end


def _occurrences(rows: list, tz: ZoneInfo, lo: datetime, hi: datetime,
                 errors: list[dict], acc: dict) -> list[tuple[dict, datetime, datetime]]:
    """응답 행 → (원본 행, 시작, 끝). 서버가 전개하지 않은 반복 마스터는 창 안 회차로 펼친다.

    같은 uid 의 회차 수정본(recurrence_id)이 있으면 그 회차는 수정본이 대신한다.
    규칙을 못 읽는 반복은 회차를 지어내지 않고 오류로 남긴다(수집 불완전).
    """
    overrides: dict[str, set[datetime]] = {}
    for ev in rows:
        if isinstance(ev, dict) and ev.get("recurrence_id"):
            rid = _point(ev.get("recurrence_id"), tz)
            if rid is not None:
                overrides.setdefault(str(ev.get("uid") or ""), set()).add(rid)
    out: list[tuple[dict, datetime, datetime]] = []
    for ev in rows:
        if not isinstance(ev, dict):
            continue
        bounds = _bounds(ev, tz)
        if bounds is None:
            errors.append({"account": acc["name"], "code": "bad_event",
                           "message": f"{ev.get('uid') or '?'}: start 를 읽을 수 없다"})
            continue
        start, end = bounds
        if ev.get("rrule") and not ev.get("recurrence_id"):
            try:
                starts = expand_rrule(str(ev["rrule"]), start, lo, hi, tz,
                                      bool(ev.get("all_day")))
            except RRuleUnsupported as exc:
                errors.append({"account": acc["name"], "code": "recurrence_unsupported",
                               "message": f"{ev.get('summary') or ev.get('uid') or '?'}: {exc}"})
                continue
            skip = overrides.get(str(ev.get("uid") or ""), set())
            out.extend((ev, occ, occ + (end - start)) for occ in starts if occ not in skip)
            continue
        out.append((ev, start, end))
    return out


def _to_event(ev: dict, start: datetime, end: datetime, acc: dict) -> dict:
    all_day = bool(ev.get("all_day"))
    row = {"summary": str(ev.get("summary") or "").strip() or "(제목 없음)",
           "start": start.date().isoformat() if all_day else start.isoformat()}
    if all_day:
        row["all_day"] = True
    else:
        row["end"] = end.isoformat()
    row["calendar"] = str(ev.get("calendar") or "")
    row["account"] = acc["name"]
    return row


def collect(inp: Inputs, p_from: date, p_to: date, tz: ZoneInfo,
            only: list[str]) -> tuple[int, dict, dict | None]:
    """(exit, 요약, timelog). 불완전이면 timelog 는 None."""
    lo, hi = _window(p_from, p_to, tz)
    period = {"from": p_from.isoformat(), "to": p_to.isoformat()}
    st, accounts, err = _accounts(inp, only)
    if st != "ok":
        err = err or {"code": "input_missing", "message": ACCOUNTS_FILE}
        return 1, {"status": "incomplete", "period": period,
                   "errors": [{"account": None, **err}]}, None

    targets = [a for a in accounts if a["calendar"]]
    skipped = [{"account": a["name"], "reason": a["reason"] or "calendar.supported=false"}
               for a in accounts if not a["calendar"]]
    if not targets:
        return 1, {"status": "incomplete", "period": period, "skipped_accounts": skipped,
                   "errors": [{"account": None, "code": "no_calendar_account",
                               "message": "캘린더를 쓸 수 있는 계정이 없다"}]}, None

    errors: list[dict] = []
    dropped = {"cancelled": 0, "out_of_period": 0, "zero_length": 0}
    events: list[tuple[datetime, dict]] = []
    per_account: list[dict] = []
    for acc in targets:
        name = _f_calendar(acc["index"])
        st, data = inp.load(name)
        if st == "missing":
            errors.append({"account": acc["name"], "code": "input_missing",
                           "message": f"{name} 이 없다 — --plan 을 다시 돌려 빠진 호출을 채운다"})
            continue
        if st == "error":
            errors.append({"account": acc["name"], **data})
            continue
        if str(data.get("account") or "") != acc["name"]:
            errors.append({"account": acc["name"], "code": "account_mismatch",
                           "message": f"{name} 의 account 가 {acc['name']} 가 아니다"})
            continue
        rows = data.get("events")
        if not isinstance(rows, list):
            errors.append({"account": acc["name"], "code": "bad_shape",
                           "message": f"{name}: events 배열이 없다"})
            continue
        if data.get("truncated"):
            errors.append({"account": acc["name"], "code": "calendar_truncated",
                           "message": f"{len(rows)}건에서 잘렸다 — 기간을 나눠 다시 조회한다"})
        for e in data.get("errors") or []:
            if isinstance(e, dict):
                errors.append({"account": acc["name"], "code": "calendar_partial",
                               "message": f"{e.get('calendar') or ''}: {e.get('code') or ''}"})
        kept = 0
        for ev, start, end in _occurrences(rows, tz, lo, hi, errors, acc):
            if str(ev.get("status") or "").upper() == "CANCELLED":
                dropped["cancelled"] += 1
                continue
            if not (p_from <= start.date() <= p_to):
                # 기간 앞에서 시작해 걸친 일정 — 집계 게이트가 기간 밖으로 거부하므로 싣지 않고 센다.
                dropped["out_of_period"] += 1
                continue
            if not ev.get("all_day") and end <= start:
                dropped["zero_length"] += 1
                continue
            events.append((start, _to_event(ev, start, end, acc)))
            kept += 1
        per_account.append({"account": acc["name"], "events": kept})

    if errors:
        return 1, {"status": "incomplete", "period": period, "errors": errors,
                   "skipped_accounts": skipped}, None
    summary = {"status": "ok", "period": period, "accounts": per_account,
               "skipped_accounts": skipped, "events": len(events), "dropped": dropped}
    if not events:
        summary["status"] = "empty"
        summary["note"] = ("요청 기간에 일정 0건 — 다른 기간으로 대체하지 말고 "
                           "사용자에게 기간을 확인한다")
        return 3, summary, None
    events.sort(key=lambda x: (x[0], x[1]["summary"]))
    timelog = {"period": period, "source": SOURCE, "provisional": True,
               "categories": {}, "events": [e for _, e in events]}
    return 0, summary, timelog


def build_plan(inp: Inputs, p_from: date, p_to: date, tz: ZoneInfo,
               only: list[str], save_dir: str) -> dict:
    lo, hi = _window(p_from, p_to, tz)

    def saving(save: str) -> dict:
        return {"save_dir": save_dir, "save_as": save, "overwrite": True}

    st, accounts, err = _accounts(inp, only)
    if st == "missing":
        return {"status": "pending",
                "calls": [{"tool": "accounts_list", "args": saving(ACCOUNTS_FILE),
                           "save": ACCOUNTS_FILE, "why": "계정 목록"}]}
    if st == "error":
        return {"status": "complete", "calls": [],
                "note": f"accounts_list 확인 실패({err['code']}: {err['message']}) — "
                        "수집 모드가 불완전으로 멈춘다"}
    calls = []
    for acc in accounts:
        if acc["calendar"] and not inp.exists(_f_calendar(acc["index"])):
            save = _f_calendar(acc["index"])
            calls.append({"tool": "calendar_events",
                          "args": {"account": acc["name"], "from": lo.isoformat(),
                                   "to": hi.isoformat(), "expand": True,
                                   "limit": EVENTS_LIMIT, **saving(save)},
                          "save": save,
                          "why": f"{p_from}~{p_to} 일정"})
    return {"status": "pending" if calls else "complete", "calls": calls}


def _is_abs_host_path(value: str) -> bool:
    """호스트 절대 경로인가 — 스크립트는 리눅스 샌드박스에서 돌아도 호스트는 Windows 일 수 있다."""
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _date_arg(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"YYYY-MM-DD 가 아니다: {value!r}") from exc


def _fail(code: str, detail: str) -> int:
    print(json.dumps({"status": "error", "error": code, "detail": detail},
                     ensure_ascii=False))
    return 2


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(
        description="time-audit 수집 — itda-hyve calendar_events 응답 폴더 → timelog.json 초안")
    ap.add_argument("--input", required=True, metavar="DIR",
                    help="itda-hyve 도구 응답을 저장한 폴더")
    ap.add_argument("--from", dest="p_from", required=True, type=_date_arg,
                    help="요청 기간 시작(YYYY-MM-DD, 사용자가 말한 그대로)")
    ap.add_argument("--to", dest="p_to", required=True, type=_date_arg,
                    help="요청 기간 끝(YYYY-MM-DD, 그날 포함)")
    ap.add_argument("--account", action="append", default=[],
                    help="이 계정만(accounts_list 의 name, 여러 번 가능). 생략하면 캘린더 계정 전부")
    ap.add_argument("--plan", action="store_true",
                    help="아직 부르지 않은 도구 호출(도구·인자·저장 파일)을 낸다")
    ap.add_argument("--save-dir", metavar="HOST_DIR",
                    help="--plan 전용. 입력 폴더의 호스트 절대 경로(itda-hyve 가 응답을 쓸 곳 — "
                         "Cowork 는 연결 폴더의 호스트 경로 아래, Claude Code 는 입력 폴더 그대로)")
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--out", help="timelog.json 초안 경로(수집 모드에서 필수)")
    args = ap.parse_args(argv)

    if args.p_to < args.p_from:
        return _fail("bad_period", f"--to({args.p_to}) < --from({args.p_from})")
    if (args.p_to - args.p_from).days + 1 > MAX_PERIOD_DAYS:
        return _fail("period_too_long",
                     f"{MAX_PERIOD_DAYS}일 이하로 나눠 조회한다(calendar_events 상한 1년)")
    tz = ZoneInfo(args.tz)
    try:
        inp = Inputs(Path(args.input))
    except InputError as exc:
        return _fail(exc.code, exc.detail)

    if args.plan:
        if not args.save_dir or not _is_abs_host_path(args.save_dir):
            return _fail("save_dir_required",
                         "--plan 에는 --save-dir <입력 폴더의 호스트 절대 경로> 가 필요하다 — "
                         "itda-hyve 가 응답을 그 폴더에 직접 쓴다")
        print(json.dumps(build_plan(inp, args.p_from, args.p_to, tz, args.account,
                                    args.save_dir),
                         ensure_ascii=False, indent=2))
        return 0
    if not args.out:
        return _fail("out_required", "--out <timelog.json> 이 필요하다")

    rc, summary, timelog = collect(inp, args.p_from, args.p_to, tz, args.account)
    if timelog is not None:
        out = Path(args.out)
        try:
            out.write_text(json.dumps(timelog, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        except OSError as exc:
            return _fail("write_failed", f"{out}: {exc}")
        summary["out"] = str(out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
