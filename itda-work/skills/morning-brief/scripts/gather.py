#!/usr/bin/env python3
"""itda-work morning-brief: gather.py — 형제 스킬에서 아침 브리핑 후보를 모은다.

출력은 `candidates.json`(schema_version 1). LLM 은 이 파일만 읽고 content.json 을
쓴다. 형제 스킬 호출은 **argv 배열 subprocess** 로만 한다(셸 문자열 조립 금지 —
마운트 경로에 한글·공백이 있다).

역할 3상태: ready / not_configured(조용히 skip) / error(skip 하되 warnings 에 남기고
페이지가 한 줄로 말한다 — no-silent-fallback).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
# 샘플 모드 — 형제 스킬을 부르지 않고 시나리오 파일만으로 같은 candidates 를 만든다.
# 실데이터와 섞이지 않게 provider·account 를 상수로 박고, render·verify 가 그것을
# 근거로 띠와 상호 배타를 집행한다(v6).
SAMPLE_TOKEN = "sample"
SAMPLE_EMAIL_DEFAULT = "me@sample.example.com"
SAMPLE_SEED_ASSET = "assets/sample-seed.default.json"
SAMPLE_VERDICTS = ("unreplied", "replied_then_new", "unknown", "bulk", "group")
# thread_status 가 실제로 후보로 올리는 것과 같은 두 축만 목록에 오른다 —
# bulk·group·unknown 은 시나리오의 사실감을 위해 시드에 적되 후보가 아니다.
SAMPLE_CANDIDATE_VERDICTS = ("unreplied", "replied_then_new")
DEFAULT_TZ = "Asia/Seoul"
DEFAULT_TOTAL_TIMEOUT = 120.0
DEFAULT_CALL_TIMEOUT = 45.0
SECTION_ALLOWLIST = ("날씨", "환율")
# 날씨는 기본으로 붙인다(마스터 결정 2026-09-03 — v4 "Sections 없음=0" 반전).
# 아침에 가장 먼저 궁금한 것이라 매번 요청하게 두지 않는다. 빼려면 `--sections none`.
SECTION_DEFAULT = ("날씨",)
SECTION_NONE = "none"
UNREPLIED_LIMIT = 8
BODY_CHARS = 500

# thread_status 가 "판정 자체를 못 했다" 고 말하는 코드. 역할은 ready 지만 후보가
# 비므로, 빈 상태로 위장하지 않도록 페이지가 한 줄로 말해야 한다.
# thread_status.py 가 내는 코드 그대로(생산자 실측 — email/scripts/thread_status.py).
DEGRADED_EMAIL_CODES = frozenset({
    "sent_folder_not_found",  # \Sent 미발견 → 전건 unknown
    "sent_read_failed",       # Sent 읽기 실패 → 전건 unknown(fail-closed)
    "inbox_read_failed",      # INBOX 를 끝까지 못 읽음 → 후보 불완전
})

# 형제 스킬의 서드파티 의존이 없어 즉사한 경우. nonzero_exit 로 접으면 사용자는
# 원인을 모른다 — 코드로 갈라 페이지가 처방까지 말한다(no-silent-fallback).
DEPS_MISSING_CODE = "sibling_deps_missing"

for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover
            pass


# --------------------------------------------------------------------------
# subprocess — argv 배열 전용, 프로세스 그룹 단위 정리
# --------------------------------------------------------------------------

def _kill_group(proc: subprocess.Popen) -> None:
    """자식이 손자를 남기지 않도록 프로세스 그룹째 정리한다."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def run_argv(argv: list[str], timeout: float) -> dict:
    """argv 배열을 실행하고 {ok, rc, stdout, stderr, error} 를 돌려준다.

    셸을 거치지 않으므로 경로의 공백·한글이 그대로 전달된다.
    """
    if timeout <= 0:
        return {"ok": False, "error": "budget_exhausted", "rc": None,
                "stdout": "", "stderr": ""}
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except OSError as exc:
        return {"ok": False, "error": "spawn_failed", "rc": None,
                "stdout": "", "stderr": str(exc)[:300]}

    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - 방어
            out, err = "", ""
        return {"ok": False, "error": "timeout", "rc": None,
                "stdout": out or "", "stderr": (err or "")[:300]}

    if proc.returncode != 0:
        return {"ok": False, "error": "nonzero_exit", "rc": proc.returncode,
                "stdout": out, "stderr": (err or "")[:300]}
    return {"ok": True, "error": None, "rc": 0, "stdout": out,
            "stderr": err or ""}


def run_json(argv: list[str], timeout: float) -> dict:
    """run_argv + JSON 파싱. 부분 stdout·비 JSON 은 bad_json 으로 갈린다."""
    res = run_argv(argv, timeout)
    if not res["ok"]:
        return res
    try:
        res["data"] = json.loads(res["stdout"])
    except (json.JSONDecodeError, ValueError) as exc:
        res["ok"] = False
        res["error"] = "bad_json"
        res["stderr"] = str(exc)[:300]
    return res


def classify_failure(res: dict) -> tuple[str, str]:
    """(code, detail) — stderr 에 ModuleNotFoundError 가 있으면 의존성 부재로 간다.

    형제 스킬의 `check_env.py` 는 stdlib 만 쓰므로 성공하는데 `list_events.py` 는
    `caldav`·`icalendar` import 로 즉사한다. 둘을 같은 nonzero_exit 로 접으면
    "계정 확인 실패" 로 잘못 안내한다."""
    stderr = str(res.get("stderr") or "")
    if "ModuleNotFoundError" in stderr:
        module = ""
        for line in stderr.splitlines():
            if "ModuleNotFoundError" in line and "'" in line:
                module = line.split("'")[1]
                break
        return DEPS_MISSING_CODE, module or stderr[:200]
    return str(res.get("error") or "error"), stderr[:200]


class Budget:
    """전체 시간 예산. 호출마다 남은 시간과 상한 중 작은 값을 쓴다."""

    def __init__(self, total: float, per_call: float) -> None:
        self.deadline = time.monotonic() + total
        self.per_call = per_call

    def slice(self) -> float:
        return min(self.per_call, self.deadline - time.monotonic())


# --------------------------------------------------------------------------
# 주소 정규화
# --------------------------------------------------------------------------

def normalize_address(value: str | None) -> str:
    """소문자 + plus-addressing 제거. mailto: 접두는 벗긴다."""
    if not value:
        return ""
    text = value.strip()
    if text.lower().startswith("mailto:"):
        text = text[7:]
    if "<" in text and ">" in text:  # "이름 <a@b.c>" 형태
        text = text[text.rfind("<") + 1:text.rfind(">")]
    text = text.strip().lower()
    if "@" not in text:
        return text
    local, _, domain = text.partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{domain}"


# --------------------------------------------------------------------------
# 역할 수집
# --------------------------------------------------------------------------

def _ready_accounts(check_env_data: object) -> list[tuple[str, str, str]]:
    """check_env 출력에서 (provider, account_id, login) 목록을 뽑는다."""
    out: list[tuple[str, str, str]] = []
    if not isinstance(check_env_data, dict):
        return out
    for prov in check_env_data.get("providers") or []:
        if not isinstance(prov, dict):
            continue
        name = str(prov.get("provider") or "")
        for acc in prov.get("accounts") or []:
            if not isinstance(acc, dict) or acc.get("status") != "ready":
                continue
            login = acc.get("login") or acc.get("email") or ""
            out.append((name, str(acc.get("account_id") or "default"), str(login)))
    return out


def _script(siblings: Path, skill: str, name: str) -> str:
    return str(siblings / skill / "scripts" / name)


def collect_calendar(siblings: Path, budget: Budget, py: str,
                     start: datetime, end: datetime,
                     warnings: list[dict]) -> dict:
    """calendar 역할: check_env → ready 계정마다 list_events."""
    res = run_json([py, _script(siblings, "calendar", "check_env.py")],
                   budget.slice())
    if not res["ok"]:
        warnings.append({"role": "calendar", "severity": "error",
                         "code": res["error"],
                         "detail": (res.get("stderr") or "")[:200]})
        return {"state": "error", "accounts": [], "events": [], "logins": []}

    accounts = _ready_accounts(res.get("data"))
    if not accounts:
        return {"state": "not_configured", "accounts": [], "events": [],
                "logins": []}

    events: list[dict] = []
    listed: list[dict] = []
    logins: list[str] = []
    failed = 0
    for provider, account_id, login in accounts:
        listed.append({"provider": provider, "account": account_id,
                       "login": normalize_address(login)})
        if login:
            logins.append(normalize_address(login))
        # `--account` 는 언제나 명시한다 — calendar `cli_common.resolve_provider_
        # _or_exit` 도 다계정+미지정이면 `account_required` exit 2 이고,
        # `caldav_providers.get_provider` 는 "default" 명시 조회를 정상 처리한다.
        argv = [py, _script(siblings, "calendar", "list_events.py"),
                "--provider", provider, "--account", account_id,
                "--from", start.isoformat(), "--to", end.isoformat(), "--expand"]
        sub = run_json(argv, budget.slice())
        if not sub["ok"]:
            failed += 1
            code, detail = classify_failure(sub)
            warnings.append({"role": "calendar", "severity": "error",
                             "code": code, "provider": provider,
                             "account": account_id, "rc": sub.get("rc"),
                             "detail": detail})
            continue
        data = sub.get("data")
        if isinstance(data, dict) and data.get("status") == "error":
            failed += 1
            warnings.append({"role": "calendar", "severity": "error",
                             "code": str(data.get("error") or "error"),
                             "provider": provider, "account": account_id,
                             "detail": str(data.get("detail") or "")[:200]})
            continue
        rows = data if isinstance(data, list) else (data or {}).get("events") or []
        for row in rows:
            if isinstance(row, dict):
                row["_provider"] = provider
                row["_account"] = account_id
                events.append(row)
    # 전 계정이 실패하면 그 역할은 ready 가 아니다 — 빈 이벤트를 "조용한 하루" 로
    # 렌더하면 실패가 정상으로 위장된다(email 과 같은 규칙).
    state = "error" if accounts and failed == len(accounts) else "ready"
    return {"state": state, "accounts": listed, "events": events,
            "logins": logins}


def collect_email(siblings: Path, budget: Budget, py: str,
                  warnings: list[dict]) -> dict:
    """email 역할: check_env → ready 계정마다 thread_status."""
    res = run_json([py, _script(siblings, "email", "check_env.py")],
                   budget.slice())
    if not res["ok"]:
        warnings.append({"role": "email", "severity": "error",
                         "code": res["error"],
                         "detail": (res.get("stderr") or "")[:200]})
        return {"state": "error", "accounts": [], "candidates": []}

    accounts = _ready_accounts(res.get("data"))
    if not accounts:
        return {"state": "not_configured", "accounts": [], "candidates": []}

    listed: list[dict] = []
    cands: list[dict] = []
    failed = 0
    for provider, account_id, login in accounts:
        listed.append({"provider": provider, "account": account_id,
                       "login": normalize_address(login)})
        # `--account` 는 언제나 명시한다 — 다계정에서 생략하면 thread_status 가
        # exit 2 로 끝난다(T1 계약).
        argv = [py, _script(siblings, "email", "thread_status.py"),
                "--provider", provider, "--account", account_id,
                "--days", "2", "--with-body", str(BODY_CHARS),
                "--limit", str(UNREPLIED_LIMIT)]
        sub = run_json(argv, budget.slice())
        if not sub["ok"]:
            failed += 1
            code, detail = classify_failure(sub)
            warnings.append({"role": "email", "severity": "error",
                             "code": code, "provider": provider,
                             "account": account_id, "rc": sub.get("rc"),
                             "detail": detail})
            continue
        data = sub.get("data")
        if not isinstance(data, dict):
            failed += 1
            warnings.append({"role": "email", "severity": "error",
                             "code": "bad_shape", "provider": provider,
                             "account": account_id})
            continue
        # 공통 IMAP 계약: 실패는 {"status":"error","error":"<코드>"} 로 온다.
        if data.get("status") == "error":
            failed += 1
            warnings.append({"role": "email", "severity": "error",
                             "code": str(data.get("error") or "error"),
                             "provider": provider, "account": account_id,
                             "detail": str(data.get("detail") or "")[:200]})
            continue
        for row in data.get("candidates") or []:
            if isinstance(row, dict):
                cands.append(row)
        for warn in data.get("warnings") or []:
            code = warn.get("code") if isinstance(warn, dict) else None
            detail = warn.get("detail") if isinstance(warn, dict) else warn
            code = str(code or "thread_status")
            warnings.append({
                "role": "email",
                # 판정을 못 한 것은 "경고" 가 아니라 **결손**이다 — 페이지가 말해야 한다.
                "severity": "degraded" if code in DEGRADED_EMAIL_CODES else "warning",
                "code": code, "provider": provider, "account": account_id,
                "detail": str(detail or "")[:200]})
    # 모든 계정이 실패하면 그 역할은 ready 가 아니다(부분 실패는 격리한다).
    state = "error" if accounts and failed == len(accounts) else "ready"
    return {"state": state, "accounts": listed, "candidates": cands}


def collect_sections(siblings: Path, budget: Budget, py: str,
                     names: list[str], today: datetime,
                     warnings: list[dict]) -> dict:
    """Sections allowlist 2종. 산출은 평문(스크립트가 JSON 을 내지 않는다)."""
    out: dict[str, dict] = {}
    for name in names:
        if name == "날씨":
            argv = [py, _script(siblings, "weather-here", "weather_here.py")]
        elif name == "환율":
            argv = [py, _script(siblings, "exchange-rate", "exchange_rate.py"),
                    "--currency", "USD", "--date", today.strftime("%Y-%m-%d")]
        else:  # pragma: no cover - parse_args 가 먼저 막는다
            continue
        res = run_argv(argv, budget.slice())
        text = (res.get("stdout") or "").strip()
        if not res["ok"] or not text:
            warnings.append({"role": "sections", "severity": "warning",
                             "code": res["error"] or "empty", "section": name,
                             "detail": (res.get("stderr") or "")[:200]})
            continue
        out[name] = {"kind": "text", "text": text}
    return out


# --------------------------------------------------------------------------
# 샘플 모드 — 시드 검증과 변환
# --------------------------------------------------------------------------

class SeedError(Exception):
    """시드 스키마 위반. 기본 시나리오로 조용히 대체하지 않는다 —
    에이전트가 쓴 시나리오가 틀렸다는 사실이 사라지면 다음에 또 틀린다."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _seed_obj(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise SeedError(f"{where}: 객체여야 한다")
    return value


def _seed_list(parent: dict, key: str, where: str) -> list:
    value = parent.get(key)
    if not isinstance(value, list):
        raise SeedError(f"{where}.{key}: 배열이어야 한다")
    return value


def _seed_str(parent: dict, key: str, where: str, *, required: bool = True) -> str:
    value = parent.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise SeedError(f"{where}.{key}: 문자열이어야 한다")
    if required and not value.strip():
        raise SeedError(f"{where}.{key}: 비어 있으면 안 된다")
    return value


def validate_seed(raw: object) -> dict:
    """시드 스키마 검증. 통과하면 그대로 돌려준다(변환은 하지 않는다)."""
    seed = _seed_obj(raw, "seed")
    persona = _seed_obj(seed.get("persona"), "seed.persona")
    _seed_str(persona, "name", "seed.persona")
    _seed_str(persona, "role", "seed.persona")
    email = _seed_str(persona, "email", "seed.persona", required=False)
    if email and "@" not in email:
        raise SeedError("seed.persona.email: 주소 형태여야 한다")

    for bucket in ("today", "tomorrow"):
        for i, ev in enumerate(_seed_list(seed, bucket, "seed")):
            where = f"seed.{bucket}[{i}]"
            ev = _seed_obj(ev, where)
            _seed_str(ev, "summary", where)
            _seed_str(ev, "calendar", where)
            _seed_str(ev, "status", where)
            _seed_str(ev, "organizer", where, required=False)
            if not isinstance(ev.get("all_day"), bool):
                raise SeedError(f"{where}.all_day: 참/거짓이어야 한다")
            _seed_str(ev, "start", where, required=not ev["all_day"])
            _seed_str(ev, "end", where, required=False)

    for i, mail in enumerate(_seed_list(seed, "mails", "seed")):
        where = f"seed.mails[{i}]"
        mail = _seed_obj(mail, where)
        for key in ("from", "subject", "date"):
            _seed_str(mail, key, where)
        _seed_str(mail, "body", where, required=False)
        verdict = _seed_str(mail, "verdict", where)
        if verdict not in SAMPLE_VERDICTS:
            raise SeedError(f"{where}.verdict: {verdict!r} 는 허용값이 아니다 "
                            f"(허용: {', '.join(SAMPLE_VERDICTS)})")

    sections = seed.get("sections")
    if sections is not None:
        sections = _seed_obj(sections, "seed.sections")
        for name, text in sections.items():
            if name not in SECTION_ALLOWLIST:
                raise SeedError(f"seed.sections.{name}: 허용 섹션이 아니다 "
                                f"(허용: {', '.join(SECTION_ALLOWLIST)})")
            if not isinstance(text, str) or not text.strip():
                raise SeedError(f"seed.sections.{name}: 비지 않은 문자열이어야 한다")

    notes = seed.get("notes")
    if notes is not None and not isinstance(notes, (str, list)):
        raise SeedError("seed.notes: 문자열이거나 문자열 배열이어야 한다")
    return seed


_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def _sample_time(raw: str, day: datetime, tz: ZoneInfo, all_day: bool,
                 where: str) -> str:
    """`09:30` 은 그 버킷의 실제 날짜에 얹는다 — 샘플은 언제 열어도 오늘이어야 한다.
    전체 ISO·날짜를 주면 그대로 쓴다(변환만)."""
    if all_day:
        if not raw:
            return day.date().isoformat()
        if len(raw) == 10:
            try:
                date.fromisoformat(raw)
            except ValueError as exc:
                raise SeedError(f"{where}: 날짜 형식이 아니다({raw})") from exc
            return raw
        raise SeedError(f"{where}: 종일 일정은 YYYY-MM-DD 여야 한다({raw})")
    if not raw:
        return ""
    m = _HHMM.match(raw)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if hour > 23 or minute > 59:
            raise SeedError(f"{where}: 시각 범위를 벗어났다({raw})")
        return day.replace(hour=hour, minute=minute, second=0,
                           microsecond=0).isoformat()
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SeedError(f"{where}: HH:MM 또는 ISO 시각이어야 한다({raw})") from exc
    dt = dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
    return dt.isoformat()


def build_sample_candidates(seed: dict, *, tz_name: str, now: datetime,
                            buttons: bool,
                            section_names: list[str] | None = None) -> dict:
    """검증된 시드 → 실데이터와 **같은 형식**의 candidates. 형제 호출 0."""
    tz = ZoneInfo(tz_name)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"today": day0, "tomorrow": day0 + timedelta(days=1)}
    persona = seed["persona"]
    me = normalize_address(persona.get("email") or SAMPLE_EMAIL_DEFAULT)

    buckets: dict[str, list[dict]] = {"today": [], "tomorrow": []}
    for name, day in days.items():
        for i, ev in enumerate(seed.get(name) or [], start=1):
            all_day = bool(ev["all_day"])
            start = _sample_time(ev.get("start") or "", day, tz, all_day,
                                 f"seed.{name}[{i - 1}].start")
            end = _sample_time(ev.get("end") or "", day, tz, all_day,
                               f"seed.{name}[{i - 1}].end")
            buckets[name].append({
                "anchor": {
                    "provider": SAMPLE_TOKEN, "account": SAMPLE_TOKEN,
                    "calendar": ev["calendar"],
                    "uid": f"{SAMPLE_TOKEN}-{name}-{i}", "start": start,
                },
                "summary": ev["summary"], "start": start, "end": end,
                "all_day": all_day, "location": ev.get("location") or "",
                "status": ev["status"],
                "organizer": normalize_address(ev.get("organizer")),
                "recurrence_start": None,
            })

    for rows in buckets.values():
        rows.sort(key=lambda c: (c["start"], c["summary"]))

    prep = [c for c in buckets["tomorrow"]
            if c["organizer"] and c["organizer"] == me
            and c["status"].upper() != "CANCELLED"]
    cancelled = [c for c in buckets["today"] + buckets["tomorrow"]
                 if c["status"].upper() == "CANCELLED"]

    unreplied: list[dict] = []
    replied: list[dict] = []
    for i, mail in enumerate(seed.get("mails") or [], start=1):
        verdict = mail["verdict"]
        if verdict not in SAMPLE_CANDIDATE_VERDICTS:
            continue  # bulk·group·unknown 은 실제 경로에서도 후보가 아니다
        item = {
            "anchor": {
                "provider": SAMPLE_TOKEN, "account": SAMPLE_TOKEN,
                "folder": "INBOX", "uidvalidity": "1", "uid": str(i),
                "message_id": f"<{SAMPLE_TOKEN}-{i}@sample.example.com>",
            },
            "from": mail["from"], "subject": mail["subject"],
            "date": mail["date"], "verdict": verdict,
            "reason_code": ("no_sent_after_inbound" if verdict == "unreplied"
                            else "inbound_after_sent"),
        }
        body = mail.get("body")
        if isinstance(body, str) and body.strip():
            item["body"] = body
        (unreplied if verdict == "unreplied" else replied).append(item)

    # 요청된 섹션만 싣는다(실데이터와 같은 규칙). 시드에 그 문구가 없으면
    # 기본 시나리오의 것을 끌어다 쓰지 않는다 — 그것은 지어내는 것이다.
    requested = list(section_names) if section_names is not None \
        else list(SECTION_DEFAULT)
    seed_sections = seed.get("sections") or {}
    sections: dict[str, dict] = {}
    warnings: list[dict] = []
    for name in requested:
        text = seed_sections.get(name)
        if isinstance(text, str) and text.strip():
            sections[name] = {"kind": "text", "text": text}
        else:
            warnings.append({"role": "sections", "severity": "warning",
                             "code": "section_missing", "section": name,
                             "detail": "시나리오에 그 섹션 문구가 없다"})

    role = {"state": SAMPLE_TOKEN,
            "accounts": [{"provider": SAMPLE_TOKEN, "account": SAMPLE_TOKEN,
                          "login": me}]}
    notes = seed.get("notes")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),   # 시각은 실제다 — 시나리오만 가짜다
        "tz": tz_name,
        "controls": {"buttons": bool(buttons), "sections": requested,
                     "sample": True},
        "roles": {"calendar": dict(role), "email": dict(role)},
        "calendar": {"today": buckets["today"], "tomorrow": buckets["tomorrow"],
                     "prep": prep, "cancelled": cancelled},
        "email": {"unreplied": unreplied, "replied_then_new": replied},
        "sections": sections,
        "warnings": warnings,
        "sample_persona": {"name": persona["name"], "role": persona["role"]},
        "sample_notes": notes if notes is not None else "",
    }


# --------------------------------------------------------------------------
# 후보 조립
# --------------------------------------------------------------------------

def _to_tz(raw, tz: ZoneInfo, all_day: bool) -> str:
    """tz-aware 시각을 브리핑 시간대로 변환해 싣는다(C5).

    `00:00Z` 일정을 그대로 실으면 표기도 지형도 아홉 시간 어긋난다. 종일
    일정(날짜)과 naive 시각은 그대로 둔다 — 붙일 근거가 없다."""
    if all_day or not isinstance(raw, str) or not raw:
        return raw if isinstance(raw, str) else ""
    if len(raw) == 10:
        return raw
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    if dt.tzinfo is None:
        return raw
    return dt.astimezone(tz).isoformat()


def _parse_point(raw, tz: ZoneInfo) -> datetime | None:
    """비교용 한 점. 날짜는 그 날 00:00, naive 는 tz 를 붙여 읽는다."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        if len(raw) == 10:
            d = date.fromisoformat(raw)
            return datetime(d.year, d.month, d.day, tzinfo=tz)
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)


def _event_span(cand: dict, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """[시작, 끝) 구간. 끝이 없거나 뒤집혀 있으면 종일은 하루, 시각은 길이 0."""
    start = _parse_point(cand.get("start"), tz)
    if start is None:
        return None
    end = _parse_point(cand.get("end"), tz)
    if end is None or end < start:
        end = start + timedelta(days=1) if cand.get("all_day") else start
    return start, end


def _overlaps(span: tuple[datetime, datetime], lo: datetime,
              hi: datetime) -> bool:
    """구간이 [lo, hi) 와 겹치는가. 길이 0 인 시각은 점 포함으로 본다(C9).

    시작일만 비교하면 전날 시작해 오늘 끝나는 야간 일정과 며칠짜리 종일
    휴가가 오늘 목록에서 통째로 빠진다."""
    start, end = span
    if end <= start:
        return lo <= start < hi
    return start < hi and end > lo


def _event_candidate(ev: dict, tz: ZoneInfo) -> dict:
    all_day = bool(ev.get("all_day"))
    start = _to_tz(ev.get("start"), tz, all_day)
    return {
        # 앵커에 account 와 start 가 있어야 계정이 다른 같은 UID, 그리고 같은
        # UID 의 반복 회차(마스터 UID 유지 — event_model.expand_recurrences)가
        # 서로 갈린다. 갈리지 않으면 verify 앵커 인덱스에 2건 이상 매칭돼
        # **어떤 항목도** 통과하지 못한다(C6).
        "anchor": {
            "provider": ev.get("_provider") or "",
            "account": ev.get("_account") or "",
            "calendar": ev.get("calendar") or "",
            "uid": ev.get("uid") or "",
            "start": start,
        },
        "summary": ev.get("summary") or "",
        "start": start,
        "end": _to_tz(ev.get("end"), tz, all_day),
        "all_day": all_day,
        "location": ev.get("location") or "",
        "status": ev.get("status") or "",
        # organizer 정규화의 정본은 calendar `event_model.normalize_mailto` 다
        # (mailto 제거·trim·소문자). 여기서 다시 정규화하면 정의가 두 벌이 된다
        # — 생산자 값을 그대로 쓴다.
        "organizer": ev.get("organizer") or "",
        # 생산자가 None 을 주면 None 그대로 — 빈 문자열은 우리가 지어낸 값이다.
        "recurrence_start": _to_tz(ev.get("recurrence_start"), tz, all_day) or None,
    }


def build_candidates(*, tz_name: str, now: datetime, buttons: bool,
                     section_names: list[str], calendar: dict, email: dict,
                     sections: dict, warnings: list[dict]) -> dict:
    tz = ZoneInfo(tz_name)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day1 = day0 + timedelta(days=1)
    day2 = day0 + timedelta(days=2)

    today_events: list[dict] = []
    tomorrow_events: list[dict] = []
    for ev in calendar.get("events", []):
        cand = _event_candidate(ev, tz)
        span = _event_span(cand, tz)
        if span is None:
            continue
        # 한 일정이 두 날에 걸치면 양쪽에 담는다 — 앵커가 같으므로 verify·출처
        # 쪽 접기에서 한 건으로 합쳐진다.
        if _overlaps(span, day0, day1):
            today_events.append(cand)
        if _overlaps(span, day1, day2):
            tomorrow_events.append(cand)

    today_events.sort(key=lambda c: (c["start"], c["summary"]))
    tomorrow_events.sort(key=lambda c: (c["start"], c["summary"]))

    # 계정 주소만 여기서 정규화한다(소문자·plus 제거). 이벤트 organizer 는
    # calendar 가 이미 정규화해 보낸 값이다.
    mine = {a for a in calendar.get("logins", []) if a}
    prep = [c for c in tomorrow_events
            if c["organizer"] and c["organizer"] in mine
            and c["status"].upper() != "CANCELLED"]

    cancelled: list[dict] = []
    seen_cancelled: set[str] = set()
    for c in today_events + tomorrow_events:
        if c["status"].upper() != "CANCELLED":
            continue
        key = json.dumps(c["anchor"], sort_keys=True, ensure_ascii=False)
        if key in seen_cancelled:  # 두 날에 걸친 일정은 한 번만
            continue
        seen_cancelled.add(key)
        cancelled.append(c)

    unreplied: list[dict] = []
    replied_then_new: list[dict] = []
    for row in email.get("candidates", []):
        verdict = str(row.get("verdict") or "")
        item = {
            "anchor": row.get("anchor") or {},
            "from": row.get("from") or "",
            "subject": row.get("subject") or "",
            "date": row.get("date") or "",
            "verdict": verdict,
            "reason_code": row.get("reason_code") or "",
        }
        if isinstance(row.get("body"), str) and row["body"]:
            item["body"] = row["body"]
        if verdict == "unreplied":
            unreplied.append(item)
        elif verdict == "replied_then_new":
            replied_then_new.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "tz": tz_name,
        "controls": {"buttons": bool(buttons), "sections": list(section_names),
                     "sample": False},
        "roles": {
            "calendar": {"state": calendar["state"],
                         "accounts": calendar.get("accounts", [])},
            "email": {"state": email["state"],
                      "accounts": email.get("accounts", [])},
        },
        "calendar": {
            "today": today_events,
            "tomorrow": tomorrow_events,
            "prep": prep,
            "cancelled": cancelled,
        },
        "email": {"unreplied": unreplied,
                  "replied_then_new": replied_then_new},
        "sections": sections,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_sections(raw: str | None) -> list[str]:
    """미지정이면 기본(날씨). `none` 이면 0개. 그 밖은 allowlist 파싱."""
    if raw is None:
        return list(SECTION_DEFAULT)
    if raw.strip().lower() == SECTION_NONE:
        return []
    if not raw.strip():
        return list(SECTION_DEFAULT)
    names: list[str] = []
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        if name not in SECTION_ALLOWLIST:
            raise SystemExit(json.dumps(
                {"status": "error", "error": "unsupported_section",
                 "detail": name, "allowed": list(SECTION_ALLOWLIST)},
                ensure_ascii=False))
        if name not in names:
            names.append(name)
    return names


VENDORED_SIBLINGS_DIR = "siblings"


def resolve_siblings_dir(skill_dir: Path, explicit: str | None) -> Path:
    """형제 스킬 루트를 정한다 — 명시 인자 > 동봉 `siblings/` > 플러그인 형제(부모).

    플러그인 배포본에서는 형제가 `<plugin>/skills/<skill>` 로 옆에 있다(부모).
    단일 `.skill` 패키지에는 형제가 없으므로 패키저가 형제 스크립트를
    `<skill>/siblings/<skill>/scripts/` 로 동봉한다 — 그 디렉토리가 **실재할 때만**
    그쪽을 쓴다(없으면 종전대로 부모). 둘 다 없는 상황은 조용히 넘기지 않는다:
    check_env 호출이 spawn_failed 로 error 상태가 되어 페이지가 한 줄로 말한다.
    """
    if explicit:
        return Path(explicit).resolve()
    vendored = skill_dir / VENDORED_SIBLINGS_DIR
    if vendored.is_dir():
        return vendored
    return skill_dir.parent


def _fail(code: str, detail: str, rc: int = 2) -> int:
    print(json.dumps({"status": "error", "error": code, "detail": detail},
                     ensure_ascii=False), file=sys.stderr)
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="아침 브리핑 후보 수집(candidates.json)")
    ap.add_argument("--skill-dir", help="morning-brief 스킬 디렉토리 절대경로")
    ap.add_argument("--siblings-dir",
                    help="형제 스킬 루트(기본: skill-dir 의 부모)")
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--sections",
                    help="쉼표 구분. 허용: 날씨, 환율. 미지정이면 날씨, "
                         "빼려면 none")
    ap.add_argument("--sample", nargs="?", const="", metavar="SEED",
                    help="시나리오 파일로 샘플 브리핑을 만든다(형제 스킬 호출 0). "
                         "경로를 생략하면 동봉 기본 시나리오를 쓴다")
    ap.add_argument("--include-buttons", action="store_true",
                    help="정확 문구 '액션 버튼 포함' 이 호출에 있을 때만 준다")
    ap.add_argument("--now", help="ISO 기준 시각(테스트용)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TOTAL_TIMEOUT)
    ap.add_argument("--call-timeout", type=float, default=DEFAULT_CALL_TIMEOUT)
    ap.add_argument("--out", help="출력 파일(기본 stdout)")
    args = ap.parse_args(argv)

    section_names = parse_sections(args.sections)

    skill_dir = Path(args.skill_dir).resolve() if args.skill_dir \
        else Path(__file__).resolve().parent.parent
    siblings = resolve_siblings_dir(skill_dir, args.siblings_dir)

    tz = ZoneInfo(args.tz)
    now = datetime.fromisoformat(args.now).replace(tzinfo=tz) \
        if args.now else datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=2)

    if args.sample is not None:
        seed_path = Path(args.sample) if args.sample \
            else skill_dir / SAMPLE_SEED_ASSET
        try:
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
        except OSError as exc:
            return _fail("sample_seed_unreadable", f"{seed_path}: {exc}")
        except json.JSONDecodeError as exc:
            return _fail("sample_seed_bad_json", f"{seed_path}: {exc}")
        try:
            seed = validate_seed(raw)
        except SeedError as exc:
            # 기본 시나리오로 조용히 대체하지 않는다 — 시드가 틀렸다는 사실이
            # 사라지면 다음 회차에 또 틀린다(no-silent-fallback).
            return _fail("sample_seed_invalid", f"{seed_path}: {exc.detail}")
        try:
            payload = build_sample_candidates(
                seed, tz_name=args.tz, now=now, buttons=args.include_buttons,
                section_names=section_names)
        except SeedError as exc:
            return _fail("sample_seed_invalid", f"{seed_path}: {exc.detail}")
    else:
        budget = Budget(args.timeout, args.call_timeout)
        py = sys.executable or "python3"
        warnings: list[dict] = []

        calendar = collect_calendar(siblings, budget, py, start, end, warnings)
        email = collect_email(siblings, budget, py, warnings)
        sections = collect_sections(siblings, budget, py, section_names, start,
                                    warnings)

        payload = build_candidates(
            tz_name=args.tz, now=now, buttons=args.include_buttons,
            section_names=section_names, calendar=calendar, email=email,
            sections=sections, warnings=warnings)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        try:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"status": "error", "error": "write_failed",
                              "path": args.out, "detail": str(exc)[:300]},
                             ensure_ascii=False), file=sys.stderr)
            return 3
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
