#!/usr/bin/env python3
"""itda-work morning-brief: gather.py — itda-hyve 도구 응답에서 아침 브리핑 후보를 만든다.

이 스크립트는 **네트워크를 하지 않고, 자격증명·환경변수·형제 스킬 스크립트를 읽거나
실행하지 않는다.** 메일·일정·위치는 LLM 이 itda-hyve 의 `batch` 한 번으로 부르고, itda-hyve 가
응답을 입력 폴더에 **직접** 저장한다(`save_dir`·`save_as` — itda-hyve 0.9.3 `batch`). 이 스크립트는
그 파일만 읽어 판정한다(dart 의 `--input` 패턴).

두 모드:

* ``--plan`` — 입력 폴더를 보고 **아직 받지 않은 파일**을 itda-hyve `batch` 계획 파일(``plan-1.json``)로
  입력 폴더에 쓰고, `batch` 에 줄 인자 `{"plan_file": <호스트 경로>}` 한 줄만 낸다(itda-hyve 0.9.4 — 모델이
  호출 목록을 다시 출력하지 않는다, itda-work/skills#39). 보통 **한 바퀴**다(itda-hyve 0.9.5, itda-work/skills#40):
  계정 목록·현재 위치·모든 계정(`account: "*"`)의 오늘 일정·받은 메일(본문 앞부분 `include_snippet`)·보낸 메일
  (`\\Sent`). 0.9.2 의 하나씩 부르기(23회·약 35초) → 0.6.0 의 batch 세 번 → batch 한 번. 예외 바퀴는 `build_plan` 머리말.
* 기본(수집) — 입력 폴더 → ``candidates.json``(schema_version 2).

두 모드 모두 itda-hyve 가 요구 판보다 옛 판이면(`detect_hyve_outdated`) **업데이트 안내 한 줄만** 내고 exit 4 로 멈춘다 —
계획을 더 내지 않고 candidates 도 쓰지 않는다(itda-work/skills#43).

브리핑 구성(#38): ① 오늘 일정 전체(시간순) ② 일정별 관련 메일(참석자·주최자 주소, 다음으로 제목
키워드) ③ 일정과 무관한 미회신 메일. 목록·매칭·정렬은 이 스크립트가 정하고, 모델은 ③ 의 요약
문장만 쓴다.

역할 3상태: ready / not_configured(조용히 skip) / error(skip 하되 warnings 에 남기고
페이지가 한 줄로 말한다 — no-silent-fallback).
"""
from __future__ import annotations

import argparse
import json
import os   # 계획 파일 fsync 만 쓴다 — 격리 테스트가 쓰는 속성을 fsync·open·close·O_RDONLY 로 묶는다
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 2
# 샘플 모드 — 도구 응답 없이 시나리오 파일만으로 같은 candidates 를 만든다.
# 실데이터와 섞이지 않게 provider·account 를 상수로 박고, render·verify 가 그것을
# 근거로 띠와 상호 배타를 집행한다(v6).
SAMPLE_TOKEN = "sample"
SAMPLE_EMAIL_DEFAULT = "me@sample.example.com"
SAMPLE_SEED_ASSET = "assets/sample-seed.default.json"
SAMPLE_VERDICTS = ("unreplied", "replied_then_new", "replied", "unknown", "bulk", "group")
THREAD_VERDICTS = ("unreplied", "replied_then_new", "replied", "unknown")
DEFAULT_TZ = "Asia/Seoul"
SECTION_ALLOWLIST = ("날씨", "환율")
# 날씨는 기본으로 붙인다(마스터 결정 2026-09-03 — v4 "Sections 없음=0" 반전).
# 아침에 가장 먼저 궁금한 것이라 매번 요청하게 두지 않는다. 빼려면 `--sections none`.
SECTION_DEFAULT = ("날씨",)
SECTION_NONE = "none"

# 앵커·출처 절의 provider — 데이터를 가져온 경로다. 계정은 accounts_list 의 name.
PROVIDER = "itda-hyve"

# 메일 판정 창 — 받은편지함 2일, 보낸편지함 30일·200통(#34 에서 정한 근거는 README).
INBOX_DAYS = 2
SENT_DAYS = 30
SEARCH_LIMIT = 200          # imap_search 최대값
# 보낸편지함은 이름 대신 특수 용도로 지목한다(itda-hyve 0.9.2) — imap_list_mailboxes 라운드가 없어진다.
SENT_SPECIAL_USE = "\\Sent"
SENT_NOT_FOUND_CODE = "special_use_not_found"
UNREPLIED_LIMIT = 8         # 계정당 「일정과 무관한 미회신」 상한(최신순, 스레드당 1통)
RELATED_LIMIT = 5           # 일정당 관련 메일 상한(최신순, 스레드당 1통)
BODY_CHARS = 1000           # 요약용 본문 발췌(imap_fetch max_body_chars)
FETCH_UIDS_MAX = 50         # imap_fetch uids 최대값(itda-hyve 0.9.3)
EVENTS_LIMIT = 1000         # calendar_events 최대값
GROUP_RECIPIENT_THRESHOLD = 5
# --- 자동 발송 판정(itda-work/skills#40) -------------------------------------------------------
# 0.9.4 Cowork 실측에서 대량 발송 표지(List-Id 등)가 없는 자동 메일이 「미회신」 에 남았다 — Firebase
# `firebase-noreply@`, NHN KCP(표시 이름 「발신전용」, `pgadmcust@`), 쿠팡 결제 `easypay_noreturn@`, Apple `no_reply@`,
# Replicate `billing@`, AliExpress `@notice.aliexpress.com`. 규칙은 강약 두 층이다.
#
# 강한 표지 — 답장을 받지 않겠다고 스스로 밝힌 발신. 아는 상대여도 대량 발송이다(답장할 수 없는 주소다).
#   ① 로컬파트 **어디에든** noreply 류(구분자 `._-` 를 지우고 부분 문자열로 — `firebase-noreply`·`easypay_noreturn`)
#   ② 표시 이름에 「발신전용」·「회신불가」·no-reply 류(국내 PG·카드사는 로컬파트가 사람 이름 같은 코드다 — `pgadmcust`)
# 약한 표지 — 사람이 쓰기도 하는 주소 모양. **아는 상대**(최근 30일 보낸편지함의 받는 사람·참조)면 사람 메일로 둔다.
#   ③ 역할 주소 — 로컬파트를 구분자로 자른 낱말 중 하나가 아래 목록(`billing`·`order-status`·`security.alert`)
#   ④ 발송 서브도메인 — 도메인이 세 마디 이상이고 첫 마디가 아래 목록(`@notice.…`·`@email.…`)
#
# 역할 목록에 support·help·info·contact·sales·admin·hello·team 은 **넣지 않는다** — 사람이 받아 답하는 공용 창구라
# 그리로 온 메일은 답을 기다리는 메일일 수 있다. 목록은 "사람이 답하지 않는 기계 발송" 에 쓰는 이름만 담는다:
# 결제·청구(billing·invoice·receipt·payment·order), 계정·보안(account·security·verify), 알림(alert·notice·
# notification·notify·system·auto), 마케팅(newsletter·news·marketing·promo), 반송(bounce·mailer·postmaster).
NOREPLY_TOKENS = ("noreply", "noreturn", "donotreply", "mailerdaemon")   # 구분자를 지운 형태 — no_reply·do-not-reply 포함
NOREPLY_DISPLAY = re.compile(r"발신\s*전용|회신\s*불가|답장\s*불가|no[\s._-]?reply|do[\s._-]?not[\s._-]?reply",
                             re.IGNORECASE)
ROLE_LOCALPARTS = frozenset({
    "billing", "invoice", "invoices", "receipt", "receipts", "payment", "payments", "order", "orders",
    "account", "accounts", "security", "verify", "verification",
    "alert", "alerts", "notice", "notices", "notification", "notifications", "notify", "system", "auto",
    "newsletter", "newsletters", "news", "marketing", "promo", "promotion", "promotions",
    "bounce", "bounces", "mailer", "postmaster",
})
SENDER_SUBDOMAINS = frozenset({
    "notice", "notices", "notification", "notifications", "alert", "alerts", "email", "mail", "mails",
    "mailer", "mailing", "news", "newsletter", "em", "marketing", "mkt", "promo", "send", "bounce",
})
_NOREPLY_SEP = re.compile(r"[._\-+]")
# 광고 메일은 제목 첫머리에 「(광고)」 를 적어야 한다(정보통신망법 제50조 ④) — 대량 발송 헤더가 없는
# 네이버 발 광고도 이 표지는 있다.
_AD_SUBJECT = re.compile(r"^\s*[\(\[［（]\s*광고\s*[\)\]］）]")
# 결제·청구 알림 — 역할 낱말이나 제목 낱말로 가른다(종류 표시일 뿐, 대량 발송 여부는 위 규칙이 정한다).
BILLING_LOCALPARTS = frozenset({"billing", "invoice", "invoices", "receipt", "receipts", "payment",
                                "payments", "order", "orders", "pay", "easypay"})
_BILLING_SUBJECT = re.compile(r"결제|영수증|청구|승인|주문|구매|환불|납부|invoice|receipt|payment|order",
                              re.IGNORECASE)
_NEWSLETTER_WORDS = frozenset({"newsletter", "newsletters", "news", "marketing", "promo", "promotion",
                               "promotions", "mkt"})
# 대량 발송 메일의 종류 — 페이지의 「대량 발송 메일」 절이 이 순서로 묶는다.
BULK_KINDS = ("newsletter", "notice", "billing", "ad")
BULK_SENDERS_PER_KIND = 8   # 종류마다 발신자 상위 N곳(통수 많은 순) — 나머지는 "그 밖 N곳 M통"
BULK_SUBJECTS_PER_SENDER = 3   # 발신자마다 최신 제목 N개 — 나머지는 "외 N통"

# batch(itda-hyve 0.9.3) — 호출 40개·전체 60초가 서버 상한이다. Cowork 는 도구 호출 하나를 60초에서
# 끊으므로(references/netbridge.md) batch 가 먼저 돌려주도록 50초로 둔다. 넘긴 호출은 timeout 오류로 온다.
BATCH_MAX_CALLS = 40
BATCH_TIMEOUT_SEC = 50

# 한 번 수집(itda-hyve 0.9.5, itda-work/skills#40·itda-work/itda-hyve#21) — 계정별 도구는 account "*" 로 계정마다 펼치고
# save_as·id 의 {n}(accounts_list 순번, 1부터 — accounts.json 의 순번과 같다)으로 계정마다 파일을 나눈다.
# 받은편지함은 include_snippet 으로 본문 앞부분을 함께 받아 ③ 본문 바퀴를 없앤다 — snippet 이 없는 메일만 예외로 imap_fetch.
ALL_ACCOUNTS = "*"
SNIPPET_CHARS = 300         # 요약 한두 문장에 충분하고, 200·500자 실측 시간이 같다(itda-hyve#21 §2 — 비용은 통당 왕복)
# 미리보기는 사람 메일에만(itda-hyve 0.9.6, itda-work/itda-hyve#22) — bulk 표지·noreply 류 발신은 서버가 본문을 받지 않고
# `snippet_skipped` 를 단다(Gmail 45통 첫 호출 4.8초 → 2.1초 실측). 건너뛴 메일은 여기서도 반드시 대량 발송이어야 한다 —
# 아니면 미리보기 없는 미회신 후보가 생긴다. 그래서 `auto_reason` 이 `snippet_skipped` 를 강한 표지로 읽는다(서버 판정이 정본).
SNIPPET_FOR = "non_bulk"
# 0.9.5 이하는 모르는 인자를 호출 단위 invalid_input 으로 거부한다(batchtool.Adapt 의 DisallowUnknownFields) — 받은편지함만
# 실패하고 일정·보낸편지함은 받힌다. 그 실패를 「계정 확인 실패」 로 뭉뚱그리지 않고 업데이트 안내로 바꾼다(아래 HYVE_OUTDATED).
HYVE_MIN_VERSION = "0.9.6"
HYVE_OUTDATED = "hyve_outdated"

# 판정 자체를 못 했다는 코드. 역할은 ready 지만 목록이 비거나 모자라므로 빈 상태로
# 위장하지 않도록 페이지가 한 줄로 말한다(render DEGRADED_LINE 과 같은 목록).
DEGRADED_EMAIL_CODES = frozenset({
    "sent_folder_not_found",   # \Sent 메일함 없음 → 회신 여부 전건 모름
    "sent_read_failed",        # 보낸편지함 조회 실패·미저장 → 전건 모름(fail-closed)
    "inbox_truncated",         # 받은편지함이 조회 상한을 넘었다 → 목록 불완전
    "thread_headers_missing",  # 옛 itda-hyve — message_id 가 없어 전건 모름
})
DEGRADED_CALENDAR_CODES = frozenset({
    "calendar_partial",        # 캘린더 일부 실패(errors[])
    "calendar_truncated",      # 조회 상한 초과
    "recurrence_unsupported",  # 전개하지 못한 반복 규칙
    "attendees_missing",       # 옛 itda-hyve — 참석자·주최자 주소가 없어 관련 메일을 주소로 못 잇는다
})

# 입력 폴더의 파일 이름 — ``--plan`` 이 정하고 수집 모드가 같은 이름으로 읽는다.
# 계정은 이름 대신 accounts.json 의 **순번**으로 가리킨다(이름에 한글·공백·슬래시가
# 올 수 있다). 파일 안의 `account` 가 그 계정 이름과 같은지는 수집 모드가 대조한다.
ACCOUNTS_FILE = "accounts.json"
LOCATION_FILE = "location.json"
# `--plan` 이 쓰는 batch 계획 파일(itda-hyve 0.9.4 `plan_file`). 호출이 40개를 넘으면 plan-2.json … 로 나뉜다.
PLAN_FILE = "plan-{}.json"


def _f_calendar(i: int | str) -> str:
    return f"calendar-{i}.json"


def _f_inbox(i: int | str) -> str:
    return f"inbox-{i}.json"


def _f_sent(i: int | str) -> str:
    return f"sent-{i}.json"


# account "*" 호출의 파일 이름 — itda-hyve 가 {n} 을 계정 순번으로 바꾼다(_f_*(i) 와 같은 이름이 된다).
N = "{n}"


def _f_bodies(i: int) -> str:
    return f"bodies-{i}.json"


def _f_section(name: str) -> str:
    return f"section-{name}.txt"


def _utf8_stdio() -> None:
    """Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            try:
                stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            except AttributeError:  # pragma: no cover
                pass


# --------------------------------------------------------------------------
# 주소 정규화
# --------------------------------------------------------------------------

_ADDR_RE = re.compile(r"[\w.\-+]+@[\w.\-]+")


def normalize_address(value: str | None) -> str:
    """소문자 + plus-addressing 제거. mailto: 접두·표시 이름은 벗긴다."""
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


def _addrs(values) -> list[str]:
    """`["이름 <a@b>", "c@d"]` → 정규화 주소 목록(순서 보존·중복 제거)."""
    out: list[str] = []
    for raw in values or []:
        if not isinstance(raw, str):
            continue
        found = _ADDR_RE.findall(raw)
        for addr in (found or [raw]):
            a = normalize_address(addr)
            if a and "@" in a and a not in out:
                out.append(a)
    return out


# --------------------------------------------------------------------------
# 입력 — 폴더 또는 묶음 파일
# --------------------------------------------------------------------------

class Inputs:
    """저장된 도구 응답을 이름으로 읽는다.

    폴더면 그 안의 파일을, JSON 파일이면 `{"<파일 이름>": <내용>}` 묶음을 읽는다.
    각 항목은 셋 중 하나다: 없음(`missing`) · 도구 실패(`{"error": {...}}`) · 응답.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.bundle: dict | None = None
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InputError("input_unreadable", f"{path}: {exc}") from exc
            if not isinstance(data, dict):
                raise InputError("input_unreadable", f"{path}: 묶음 파일은 객체여야 한다")
            self.bundle = data
        elif not path.is_dir():
            raise InputError("input_missing", f"{path}: 폴더도 파일도 아니다")

    def exists(self, name: str) -> bool:
        if self.bundle is not None:
            return name in self.bundle
        return (self.path / name).is_file()

    def text(self, name: str) -> str | None:
        if self.bundle is not None:
            value = self.bundle.get(name)
            return value if isinstance(value, str) else None
        try:
            return (self.path / name).read_text(encoding="utf-8")
        except OSError:
            return None

    def load(self, name: str) -> tuple[str, object]:
        """('missing'|'error'|'ok', 값). 도구 실패는 `{"error": {"code","message"}}`."""
        if not self.exists(name):
            return "missing", None
        if self.bundle is not None:
            data = self.bundle.get(name)
        else:
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


class InputError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _accounts(inp: Inputs) -> tuple[str, list[dict], dict | None]:
    """accounts.json → (상태, [{index,name,email,calendar}], 오류)."""
    state, data = inp.load(ACCOUNTS_FILE)
    if state != "ok":
        return state, [], data if state == "error" else None
    rows = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return "error", [], {"code": "bad_shape", "message": "accounts 배열이 없다"}
    out: list[dict] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or not str(row.get("name") or "").strip():
            continue
        cal = row.get("calendar")
        out.append({
            "index": i,
            "name": str(row["name"]),
            "email": normalize_address(str(row.get("email") or "")),
            "calendar": bool(isinstance(cal, dict) and cal.get("supported") is True),
        })
    return "ok", out, None


# --------------------------------------------------------------------------
# 날짜 창
# --------------------------------------------------------------------------

def _windows(now: datetime) -> dict:
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "day0": day0,
        "day1": day0 + timedelta(days=1),
        "inbox_since": (day0 - timedelta(days=INBOX_DAYS)).date().isoformat(),
        "sent_since": (day0 - timedelta(days=SENT_DAYS)).date().isoformat(),
    }


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


# --------------------------------------------------------------------------
# 메일 판정 — 0.2.0 의 email 판정 규칙을 itda-hyve 요약 필드 위에 다시 쓴다
# --------------------------------------------------------------------------

def _msg_ids(msg: dict) -> list[str]:
    ids = [msg.get("message_id")]
    ids += list(msg.get("in_reply_to") or [])
    ids += list(msg.get("references") or [])
    out: list[str] = []
    for i in ids:
        if isinstance(i, str):
            i = i.strip().strip("<>").strip()
            if i and i not in out:
                out.append(i)
    return out


class ThreadIndex:
    """Message-ID 그래프의 union-find. 각 메시지의 {자기 id} ∪ 참조를 한 덩어리로 묶는다."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def _find(self, x: str) -> str:
        root = x
        while self._parent.get(root, root) != root:
            root = self._parent[root]
        while self._parent.get(x, x) != x:
            self._parent[x], x = root, self._parent[x]
        return root

    def add(self, ids: list[str]) -> None:
        if not ids:
            return
        for i in ids:
            self._parent.setdefault(i, i)
        base = self._find(ids[0])
        for i in ids[1:]:
            other = self._find(i)
            if other != base:
                self._parent[other] = base

    def key_of(self, ids: list[str]) -> str | None:
        return self._find(ids[0]) if ids else None


def _sender(msg: dict) -> tuple[str, str]:
    """(표시 이름, 정규화 주소) — 보낸 사람 첫 항목. `"이름" <a@b>` 의 따옴표는 벗긴다."""
    for raw in msg.get("from") or []:
        if not isinstance(raw, str):
            continue
        addrs = _addrs([raw])
        name = raw[:raw.find("<")].strip().strip('"').strip() if "<" in raw else ""
        return name, (addrs[0] if addrs else "")
    return "", ""


def _local_words(addr: str) -> list[str]:
    return [w for w in _NOREPLY_SEP.split(addr.split("@", 1)[0]) if w]


def auto_reason(msg: dict, known: frozenset[str] | set[str] = frozenset()) -> str | None:
    """대량·자동 발송이면 그 근거 코드, 사람 메일이면 None(규칙과 근거는 상수 절 머리말).

    `known` 은 아는 상대(최근 30일 보낸편지함의 받는 사람·참조, 정규화 주소)다 — 약한 표지(역할 주소·발송
    서브도메인)만 덮는다. 강한 표지(광고 표지·대량 발송 헤더·noreply 류 주소·「발신전용」 이름)는 덮지 않는다.
    """
    if _AD_SUBJECT.match(str(msg.get("subject") or "")):
        return "ad_subject"
    if msg.get("bulk") is True:
        return "bulk_header"
    skipped = msg.get("snippet_skipped")
    if isinstance(skipped, str) and skipped.strip():
        # 서버가 미리보기를 건너뛴 메일(0.9.6 snippet_for non_bulk) — 서버 판정이 정본이다. 서버의 noreply 는 보낸 사람
        # **중 하나**를 보므로 첫 주소만 보는 아래 규칙보다 넓을 수 있다. 모르는 사유도 대량 발송으로 둔다(미리보기가 없다).
        return {"bulk": "bulk_header", "noreply": "noreply_address"}.get(skipped.strip(), "snippet_skipped")
    name, addr = _sender(msg)
    if addr and any(t in _NOREPLY_SEP.sub("", addr.split("@", 1)[0]) for t in NOREPLY_TOKENS):
        return "noreply_address"
    if name and NOREPLY_DISPLAY.search(name):
        return "noreply_name"
    if not addr or addr in known:
        return None
    if any(w in ROLE_LOCALPARTS for w in _local_words(addr)):
        return "role_address"
    labels = addr.split("@", 1)[1].split(".")
    if len(labels) >= 3 and labels[0] in SENDER_SUBDOMAINS:
        return "sender_subdomain"
    return None


def bulk_kind(msg: dict, known: frozenset[str] | set[str] = frozenset()) -> str | None:
    """대량·자동 발송이면 종류(`newsletter`·`notice`·`billing`·`ad`), 아니면 None.

    1. 제목 첫머리 「(광고)」 → `ad`(법정 표지 — 헤더가 없는 광고도 잡는다).
    2. 보낸 사람 로컬파트 낱말이 결제·청구(billing·receipt·order·pay …) → `billing`.
    3. itda-hyve 0.9.4 `bulk: true` 에 `Auto-Submitted` 가 없거나(List-Id·List-Unsubscribe·Precedence), 주소에
       뉴스레터 낱말(newsletter·news·marketing·promo)이 있으면 → `newsletter`.
    4. 제목에 결제·영수증·청구·주문 … → `billing`. 5. 그 밖 → `notice`(자동 알림).

    `bulk` 필드가 없는 응답(0.9.3 이하)은 헤더 근거를 건너뛴다 — 헤더를 보지 않은 옛 판과 같은 판정이다.
    """
    reason = auto_reason(msg, known)
    if reason is None:
        return None
    if reason == "ad_subject":
        return "ad"
    _, addr = _sender(msg)
    words = _local_words(addr) if addr else []
    domain_words = addr.split("@", 1)[1].split(".")[:1] if "@" in addr else []
    if any(w in BILLING_LOCALPARTS for w in words):
        return "billing"
    auto_submitted = any(str(r).lower().startswith("auto-submitted")
                         for r in msg.get("bulk_reason") or [] if isinstance(r, str))
    if (reason == "bulk_header" and not auto_submitted) \
            or any(w in _NEWSLETTER_WORDS for w in words + domain_words):
        return "newsletter"
    if _BILLING_SUBJECT.search(str(msg.get("subject") or "")):
        return "billing"
    return "notice"


def known_contacts(sent: list[dict] | None) -> frozenset[str]:
    """아는 상대 — 최근 30일 보낸편지함에서 받는 사람·참조로 쓴 주소(정규화)."""
    out: set[str] = set()
    for m in sent or []:
        out.update(m.get("to_addrs") or [])
        out.update(m.get("cc_addrs") or [])
    return frozenset(out)


def _is_bulk(m: dict) -> bool:
    """준비된 메일(`_prepare` + `collect_email`)이 대량·자동 발송인가 — 판정은 `m["bulk_kind"]` 에 있다."""
    return m.get("bulk_kind") is not None


def _prepare(msgs: list, tz: ZoneInfo) -> list[dict]:
    out = []
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        try:
            uid = int(m.get("uid"))
        except (TypeError, ValueError):
            continue
        mid = m.get("message_id")
        out.append({
            "raw": m, "uid": uid,
            "message_id": mid.strip().strip("<>").strip() if isinstance(mid, str) else "",
            "ids": _msg_ids(m),
            "from_addrs": _addrs(m.get("from")),
            "to_addrs": _addrs(m.get("to")),
            "cc_addrs": _addrs(m.get("cc")),
            "dt": _parse_dt(m.get("date"), tz),
        })
    return out


_EPOCH = datetime(1970, 1, 1, tzinfo=ZoneInfo("UTC"))


def _when(m: dict) -> datetime:
    """날짜를 못 읽은 메일은 최신으로 간주하지 않는다."""
    return m["dt"] or _EPOCH



def judge_threads(inbox: list[dict], sent: list[dict] | None, mine: set[str]) -> None:
    """받은 메일마다 스레드 판정을 단다 — `m["verdict"]`·`m["reason"]`·`m["thread"]`·`m["mine"]`.

    unreplied(그 스레드에 내가 보낸 메일 없음) · replied_then_new(내 답장 뒤 상대 메일이 왔다) ·
    replied(내 답장이 마지막) · unknown(보낸편지함을 못 읽었거나 message_id 가 없다 — fail-closed).
    """
    index = ThreadIndex()
    for m in inbox + (sent or []):
        index.add(m["ids"])
    for m in inbox + (sent or []):
        m["thread"] = index.key_of(m["ids"]) or f"uid:{m['uid']}"
    for m in inbox:
        m["mine"] = bool(set(m["from_addrs"]) & mine)
    theirs = [m for m in inbox if not m["mine"]]
    for m in inbox:
        if sent is None:
            m["verdict"], m["reason"] = "unknown", "sent_unavailable"
            continue
        if not m["message_id"]:
            m["verdict"], m["reason"] = "unknown", "no_message_id"
            continue
        key = m["thread"]
        latest_in = max([_when(x) for x in theirs if x["thread"] == key] + [_when(m)])
        replies = [x for x in sent if x["thread"] == key]
        if not replies:
            m["verdict"], m["reason"] = "unreplied", "no_sent_in_thread"
        elif max(_when(x) for x in replies) > latest_in:
            m["verdict"], m["reason"] = "replied", "sent_after_latest_inbound"
        else:
            m["verdict"], m["reason"] = "replied_then_new", "inbound_after_latest_sent"


def exclusion(m: dict, mine: set[str]) -> str | None:
    """「미회신」 모집단 밖이면 그 이유. 모집단은 내가 받는 사람(To)에 있는, 목록형·단체가 아닌 남의 메일.

    itda-hyve `imap_search` 요약에는 참조(CC)가 없어 참조로만 받은 메일은 `not_addressed` 다.
    대량 메일은 받는 사람과 무관하게 `bulk` 다 — 리스트 주소로 온 뉴스레터가 「참조 수신」 경고에 섞이지 않고
    「대량 발송 메일」 절로 간다.
    """
    if m.get("mine"):
        return "mine"
    if _is_bulk(m):
        return "bulk"
    if not (set(m["to_addrs"]) & mine):
        return "not_addressed"
    if len(m["to_addrs"]) >= GROUP_RECIPIENT_THRESHOLD:
        return "group"
    return None


def latest_per_thread(msgs: list[dict]) -> list[dict]:
    """스레드마다 가장 늦은 한 통(최신순). 같은 요청이 목록에 두 번 세 번 쌓이지 않게."""
    best: dict[str, dict] = {}
    for m in msgs:
        key = m.get("thread") or f"uid:{m['uid']}"
        cur = best.get(key)
        if cur is None or (_when(m), m["uid"]) > (_when(cur), cur["uid"]):
            best[key] = m
    return sorted(best.values(), key=lambda m: (_when(m), m["uid"]), reverse=True)


# --------------------------------------------------------------------------
# 일정–메일 잇기 — 참석자·주최자 주소가 먼저, 그다음 제목 키워드
# --------------------------------------------------------------------------

# 일정 제목에서 키워드로 쓰지 않는 말 — 어느 일정에나 붙어 매칭이 무의미해진다.
KEYWORD_STOPWORDS = frozenset({
    "회의", "미팅", "일정", "주간", "월간", "정기", "회의실", "점검", "공유", "논의", "보고",
    "검토", "리뷰", "약속", "준비", "관련", "오전", "오후", "온라인", "오프라인", "팀", "전체",
    "업무", "확인", "요청", "자료", "통화", "전화", "면담", "상담", "방문", "외근", "출장",
    "점심", "저녁", "식사", "회식", "휴가", "연차", "반차",
    "meeting", "call", "sync", "review", "weekly", "daily", "standup", "the", "and",
    "for", "with", "zoom", "teams", "re", "fw", "fwd",
})
_WORD = re.compile(r"[0-9A-Za-z가-힣]+")


def event_keywords(summary: str) -> list[str]:
    """일정 제목의 키워드 — 두 글자 이상, 숫자만인 말·흔한 말 제외(순서 보존·중복 제거)."""
    out: list[str] = []
    for word in _WORD.findall(summary or ""):
        w = word.casefold()
        if len(w) < 2 or w.isdigit() or w in KEYWORD_STOPWORDS or w in out:
            continue
        out.append(w)
    return out


def keyword_hits(keywords: list[str], subject: str) -> list[str]:
    """메일 제목에 든 키워드. 세 글자 이상 하나 또는 서로 다른 둘 이상일 때만 잇는다
    (두 글자 한 단어 — 예: "설계" — 만으로 이으면 무관한 메일이 딸려 온다)."""
    text = (subject or "").casefold()
    hits = [k for k in keywords if k in text]
    if any(len(k) >= 3 for k in hits) or len(hits) >= 2:
        return hits
    return []


def match_event(people: dict[str, str], keywords: list[str], mail_addrs: list[str],
                subject: str) -> dict | None:
    """메일이 일정과 이어지면 `{"match": "attendee"|"organizer"|"keyword", "match_detail": …}`.

    people: 주소 → "organizer"|"attendee"(내 주소는 뺐다). 주소가 먼저다 — 같은 사람과 주고받은 메일이
    제목이 달라도 그 자리의 준비일 가능성이 가장 크다.
    """
    roles = {people[a] for a in mail_addrs if a in people}
    if "organizer" in roles:
        return {"match": "organizer", "match_detail": "주최자와 주고받은 메일"}
    if roles:
        return {"match": "attendee", "match_detail": "참석자와 주고받은 메일"}
    hits = keyword_hits(keywords, subject)
    if hits:
        return {"match": "keyword", "match_detail": f"제목에 ‘{hits[0]}’"}
    return None


def _person_email(value) -> str:
    """itda-hyve 0.9.3 의 `organizer`·`attendees[]` 는 `{email, name, …}` 다. 옛 문자열도 받는다."""
    if isinstance(value, dict):
        value = value.get("email")
    return normalize_address(value) if isinstance(value, str) else ""


def event_people(ev: dict, mine: set[str]) -> dict[str, str]:
    people: dict[str, str] = {}
    for att in ev.get("attendees") or []:
        a = _person_email(att)
        if a and "@" in a and a not in mine:
            people[a] = "attendee"
    org = _person_email(ev.get("organizer"))
    if org and "@" in org and org not in mine:
        people[org] = "organizer"
    return people


def _search_rows(data: object) -> tuple[list, bool]:
    """imap_search 응답 → (messages, 잘렸는가)."""
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return [], False
    msgs = data["messages"]
    try:
        truncated = int(data.get("total_matched") or 0) > len(msgs)
    except (TypeError, ValueError):
        truncated = False
    return msgs, truncated


def _account_matches(data: object, name: str) -> bool:
    """응답의 account 가 그 순번의 계정인가 — 파일을 바꿔 저장한 실수를 잡는다."""
    return isinstance(data, dict) and str(data.get("account") or "") == name


def _warn(warnings: list[dict], role: str, severity: str, code: str,
          acc: dict | None = None, detail: str = "") -> None:
    row = {"role": role, "severity": severity, "code": code}
    if acc is not None:
        row["provider"] = PROVIDER
        row["account"] = acc["name"]
    row["detail"] = str(detail or "")[:200]
    warnings.append(row)


def hyve_outdated(err: object) -> bool:
    """받은편지함 호출이 `snippet_for` 를 모르는 옛 itda-hyve(0.9.5 이하)에 거부됐는가.

    0.9.5 의 거부 문구: `invalid_input` · "args 를 해석하지 못함: json: unknown field \"snippet_for\""."""
    if not isinstance(err, dict) or err.get("code") != "invalid_input":
        return False
    return "snippet_for" in str(err.get("message") or "")


# 옛 판이면 브리핑을 그리지 않는다(itda-work/skills#43) — 0.9.5 로 받은 메일이 빈 브리핑을 끝까지 만들었고, 사용자는 업데이트 뒤
# 두 번 만들었다(Cowork 실측 13.0.0-test.7). 업데이트 안내만 내고 candidates 를 쓰지 않는다 → render 가 불릴 재료가 없다.
UPDATE_URL = "https://itda.work/hyve/"
UPDATE_STEPS = (
    f"{UPDATE_URL} 에서 itda-hyve {HYVE_MIN_VERSION} 이상 설치본을 받아 지금 설치본을 바꾼다",
    "Claude Desktop 을 완전히 끝냈다가 다시 연다(itda-hyve 가 새 판으로 다시 뜬다)",
    "브리핑을 다시 요청한다",
)
EXIT_HYVE_OUTDATED = 4
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def _version_tuple(raw: object) -> tuple[int, int, int] | None:
    m = _VERSION.match(str(raw or "").strip()) if isinstance(raw, str) else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def server_version(inp: Inputs) -> str | None:
    """accounts.json 최상위 `server_version` — 서버 판. 0.9.5 도 이미 준다(itda-work/itda-hyve#26 계약). 없거나 형식을 못 읽으면 None."""
    st, data = inp.load(ACCOUNTS_FILE)
    if st != "ok" or not isinstance(data, dict):
        return None
    ver = data.get("server_version")
    return ver if _version_tuple(ver) is not None else None


# 브라우저로 열기(SKILL 5절) — itda-hyve 0.10.1 부터 `accounts_list` 가 `server_features` 로 기능을 알린다(itda-work/itda-hyve#26).
# 판 번호가 아니라 기능 목록으로 가른다: 기능 이름이 있으면 그 도구가 있다.
OPEN_FILE_FEATURE = "open_file"


def server_features(inp: Inputs) -> list[str]:
    """accounts.json 최상위 `server_features`(문자열 배열, 0.10.1+). 없거나 모양이 다르면 빈 목록(= 기능 없음)."""
    st, data = inp.load(ACCOUNTS_FILE)
    if st != "ok" or not isinstance(data, dict):
        return []
    feats = data.get("server_features")
    return [f for f in feats if isinstance(f, str)] if isinstance(feats, list) else []


def detect_hyve_outdated(inp: Inputs) -> dict | None:
    """itda-hyve 가 요구 판보다 옛 판인가 — 근거는 둘이다.

    ① 1차: `accounts_list` 최상위 `server_version` 이 `HYVE_MIN_VERSION` 보다 낮다(0.9.5 도 이 필드를 준다).
    ② 2차: 받은편지함 호출이 `snippet_for` 거부(`hyve_outdated`)로 끝났다 — 판 필드가 없거나 형식을 못 읽을 때의 근거.
    판 형식을 못 읽으면 ① 은 판정하지 않는다(모르는 것을 옛 판으로 단정하지 않는다) — ② 는 그대로 본다.
    ① 이 0.9.6 이상이라고 해도 ② 가 있으면 멈춘다(받은 메일이 비는 것은 같다)."""
    evidence: list[str] = []
    found = server_version(inp)
    need = _version_tuple(HYVE_MIN_VERSION)
    if found is not None and _version_tuple(found) < need:
        evidence.append("server_version")
    rejected: list[str] = []
    st, accounts, _ = _accounts(inp)
    if st == "ok":
        for acc in accounts:
            est, data = inp.load(_f_inbox(acc["index"]))
            if est == "error" and hyve_outdated(data):
                rejected.append(acc["name"])
    if rejected:
        evidence.append("inbox_rejected")
    if not evidence:
        return None
    return {"status": HYVE_OUTDATED, "required": HYVE_MIN_VERSION, "found": found,
            "evidence": evidence, "rejected_accounts": rejected,
            "update_url": UPDATE_URL, "steps": list(UPDATE_STEPS)}


def _mail_state(inp: Inputs, acc: dict, tz: ZoneInfo) -> dict:
    """계정 하나의 메일 입력 상태 — plan 과 수집이 같은 해석을 쓴다.

    보낸편지함은 `mailbox: "\\Sent"` 로 받는다(itda-hyve 0.9.2). 응답의 `mailbox` 는 서버가 찾은
    실제 이름이고 `special_use` 는 준 이름이다 — `special_use` 가 `\\Sent` 가 아닌 파일은 계획과
    다른 호출의 응답이므로 받지 않는다. 서버가 보낸편지함을 못 찾으면 도구 에러
    `special_use_not_found` 이고, 그것은 "보낸편지함 없음" 이다(읽기 실패와 구별).
    """
    i = acc["index"]
    out: dict = {"inbox": None, "inbox_err": None, "inbox_truncated": False,
                 "sent": None, "sent_err": None, "sent_state": "missing",
                 "sent_not_found": False}
    st, data = inp.load(_f_inbox(i))
    if st == "ok" and not _account_matches(data, acc["name"]):
        st, data = "error", {"code": "account_mismatch",
                             "message": f"{_f_inbox(i)} 의 account 가 {acc['name']} 가 아니다"}
    if st == "ok":
        msgs, out["inbox_truncated"] = _search_rows(data)
        out["inbox"] = _prepare(msgs, tz)
        out["inbox_raw"] = msgs
    else:
        out["inbox_err"] = data if st == "error" else {"code": "input_missing",
                                                         "message": _f_inbox(i)}
        if hyve_outdated(out["inbox_err"]):
            out["inbox_err"] = {"code": HYVE_OUTDATED,
                                "message": f"itda-hyve 가 snippet_for 를 모른다 — {HYVE_MIN_VERSION} 이상 필요"}
    st, data = inp.load(_f_sent(i))
    if st == "ok" and not _account_matches(data, acc["name"]):
        st, data = "error", {"code": "account_mismatch",
                             "message": f"{_f_sent(i)} 의 account 가 {acc['name']} 가 아니다"}
    if st == "ok" and str(data.get("special_use") or "").lower() != SENT_SPECIAL_USE.lower():
        st, data = "error", {"code": "sent_mailbox_mismatch",
                             "message": f"{_f_sent(i)} 의 special_use 가 {SENT_SPECIAL_USE} 가 아니다"}
    out["sent_state"] = st
    if st == "ok":
        msgs, out["sent_truncated"] = _search_rows(data)
        out["sent"] = _prepare(msgs, tz)
        out["sent_mailbox"] = str(data.get("mailbox") or "")
    elif st == "error":
        out["sent_err"] = data
        out["sent_not_found"] = data.get("code") == SENT_NOT_FOUND_CODE
    return out


# --------------------------------------------------------------------------
# 반복 일정 전개 — itda-hyve 는 네이버 반복 일정을 마스터 1건 + rrule 로 준다
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
# 일정 — calendar_events 응답 → 이벤트 행
# --------------------------------------------------------------------------

def _event_bounds(ev: dict, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    all_day = bool(ev.get("all_day"))
    start = _point(ev.get("start"), tz)
    if start is None:
        return None
    end = _point(ev.get("end"), tz)
    if end is None or end < start:
        end = start + timedelta(days=1) if all_day else start
    return start, end


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


def _fmt(dt: datetime, all_day: bool) -> str:
    return dt.date().isoformat() if all_day else dt.isoformat()


def expand_events(rows: list, tz: ZoneInfo, lo: datetime, hi: datetime,
                  acc: dict, warnings: list[dict]) -> list[dict]:
    """calendar_events 의 events → gather 이벤트 행(`_provider`·`_account` 부착).

    rrule 이 있고 recurrence_id 가 없는 것은 서버가 전개하지 않은 마스터다 — 창 안의
    회차로 펼친다. 같은 uid 의 회차 수정본(recurrence_id)이 있으면 그 회차는 수정본이 대신한다.
    """
    overrides: dict[str, set[datetime]] = {}
    for ev in rows:
        if isinstance(ev, dict) and ev.get("recurrence_id"):
            rid = _point(ev.get("recurrence_id"), tz)
            if rid is not None:
                overrides.setdefault(str(ev.get("uid") or ""), set()).add(rid)

    out: list[dict] = []
    unsupported = 0
    for ev in rows:
        if not isinstance(ev, dict):
            continue
        base = {k: v for k, v in ev.items()}
        base["_provider"] = PROVIDER
        base["_account"] = acc["name"]
        if ev.get("rrule") and not ev.get("recurrence_id"):
            bounds = _event_bounds(ev, tz)
            if bounds is None:
                continue
            start, end = bounds
            all_day = bool(ev.get("all_day"))
            try:
                # 창 앞에서 시작해 창에 걸치는 회차도 잡도록 길이만큼 앞당겨 연다.
                starts = expand_rrule(str(ev["rrule"]), start, lo - (end - start), hi,
                                      tz, all_day)
            except RRuleUnsupported as exc:
                unsupported += 1
                _warn(warnings, "calendar", "degraded", "recurrence_unsupported",
                      acc, f"{ev.get('uid') or ''}: {exc}")
                out.append(base)  # 마스터만 — 창과 겹치면 그대로 실린다
                continue
            skip = overrides.get(str(ev.get("uid") or ""), set())
            for occ in starts:
                if occ in skip:
                    continue
                row = dict(base)
                row["start"] = _fmt(occ, all_day)
                row["end"] = _fmt(occ + (end - start), all_day)
                row["recurrence_start"] = row["start"]
                out.append(row)
            continue
        if ev.get("recurrence_id"):
            base["recurrence_start"] = ev.get("recurrence_id")
        out.append(base)
    return out


# --------------------------------------------------------------------------
# 역할 수집 (입력 폴더 → 역할 dict)
# --------------------------------------------------------------------------

def collect_calendar(inp: Inputs, accounts: list[dict], tz: ZoneInfo,
                     win: dict, warnings: list[dict]) -> dict:
    targets = [a for a in accounts if a["calendar"]]
    if not targets:
        return {"state": "not_configured", "accounts": [], "events": []}
    events: list[dict] = []
    listed: list[dict] = []
    failed = 0
    for acc in targets:
        listed.append({"provider": PROVIDER, "account": acc["name"],
                       "login": acc["email"]})
        st, data = inp.load(_f_calendar(acc["index"]))
        if st == "ok" and not _account_matches(data, acc["name"]):
            st, data = "error", {"code": "account_mismatch",
                                 "message": f"{_f_calendar(acc['index'])}"}
        if st != "ok":
            failed += 1
            err = data if st == "error" else {"code": "input_missing",
                                               "message": _f_calendar(acc["index"])}
            _warn(warnings, "calendar", "error", err["code"], acc, err["message"])
            continue
        rows = data.get("events")
        if not isinstance(rows, list):
            failed += 1
            _warn(warnings, "calendar", "error", "bad_shape", acc, "events 가 없다")
            continue
        for err in data.get("errors") or []:
            if isinstance(err, dict):
                _warn(warnings, "calendar", "degraded", "calendar_partial", acc,
                      f"{err.get('calendar') or ''}: {err.get('code') or ''}")
        if data.get("truncated"):
            _warn(warnings, "calendar", "degraded", "calendar_truncated", acc,
                  f"{len(rows)}건에서 잘림")
        if any(isinstance(ev, dict) and ev.get("has_attendees") and "attendees" not in ev
               for ev in rows):
            _warn(warnings, "calendar", "degraded", "attendees_missing", acc,
                  "calendar_events 응답에 attendees 가 없다(itda-hyve 0.9.3 미만)")
        events.extend(expand_events(rows, tz, win["day0"], win["day1"], acc,
                                    warnings))
    # 전 계정이 실패하면 그 역할은 ready 가 아니다 — 빈 이벤트를 "조용한 하루" 로
    # 렌더하면 실패가 정상으로 위장된다(email 과 같은 규칙).
    state = "error" if failed == len(targets) else "ready"
    return {"state": state, "accounts": listed, "events": events}


def collect_email(inp: Inputs, accounts: list[dict], tz: ZoneInfo,
                  warnings: list[dict]) -> dict:
    """계정마다 받은 메일을 읽고 스레드 판정을 단다. 목록 고르기는 `assemble` 이 한다."""
    if not accounts:
        return {"state": "not_configured", "accounts": [], "msgs": [], "mine": set()}
    mine = {a["email"] for a in accounts if a["email"]}
    listed: list[dict] = []
    msgs: list[dict] = []
    failed = 0
    known: set[str] = set()
    for acc in accounts:
        listed.append({"provider": PROVIDER, "account": acc["name"],
                       "login": acc["email"]})
        ms = _mail_state(inp, acc, tz)
        if ms["inbox"] is None:
            failed += 1
            err = ms["inbox_err"]
            _warn(warnings, "email", "error", err["code"], acc, err["message"])
            continue
        if ms["inbox_truncated"]:
            _warn(warnings, "email", "degraded", "inbox_truncated", acc,
                  f"받은편지함 최근 {len(ms['inbox'])}통만 봤다")
        sent = ms["sent"]
        if ms["inbox"] and not any(m["message_id"] for m in ms["inbox"]) \
                and not any("message_id" in m for m in ms.get("inbox_raw") or []):
            # 옛 itda-hyve — 스레드 헤더가 없어 회신 여부를 잴 수 없다.
            _warn(warnings, "email", "degraded", "thread_headers_missing", acc,
                  "imap_search 응답에 message_id 가 없다")
            sent = None
        elif ms["sent_not_found"]:
            _warn(warnings, "email", "degraded", "sent_folder_not_found", acc,
                  "\\Sent 메일함이 없다(special_use_not_found)")
            sent = None
        elif sent is None:
            err = ms["sent_err"] or {"code": "input_missing",
                                     "message": _f_sent(acc["index"])}
            _warn(warnings, "email", "degraded", "sent_read_failed", acc,
                  f"{err['code']}: {err['message']}")
        elif ms.get("sent_truncated"):
            _warn(warnings, "email", "warning", "sent_truncated", acc,
                  f"보낸편지함 최근 {len(sent)}통만 봤다")
        judge_threads(ms["inbox"], sent, mine)
        for m in ms["inbox"]:
            m["acc"] = acc
        msgs.extend(ms["inbox"])
        known |= known_contacts(ms["sent"])
    # 아는 상대는 계정을 가리지 않는다 — 다른 계정으로 주고받은 상대도 사람이다.
    known -= mine
    for m in msgs:
        m["bulk_kind"] = bulk_kind(m["raw"], known)
    state = "error" if failed == len(accounts) else "ready"
    return {"state": state, "accounts": listed, "msgs": msgs, "mine": mine}


def _read_bodies(inp: Inputs, acc: dict) -> tuple[dict[int, str], dict | None]:
    """bodies-<n>.json(imap_fetch `uids` 응답) → (uid → 본문 발췌, 파일 오류)."""
    st, data = inp.load(_f_bodies(acc["index"]))
    if st != "ok":
        return {}, (data if st == "error" else None)
    if not _account_matches(data, acc["name"]):
        return {}, {"code": "account_mismatch", "message": _f_bodies(acc["index"])}
    out: dict[int, str] = {}
    for row in data.get("messages") or []:
        if not isinstance(row, dict):
            continue
        try:
            uid = int(row.get("uid"))
        except (TypeError, ValueError):
            continue
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            out[uid] = text.strip()[:BODY_CHARS]
    return out, None


def collect_sections(inp: Inputs, names: list[str],
                     warnings: list[dict]) -> dict:
    """Sections 는 LLM 이 형제 스킬(weather-here·exchange-rate)로 받아 둔 평문."""
    out: dict[str, dict] = {}
    for name in names:
        text = (inp.text(_f_section(name)) or "").strip()
        if not text:
            warnings.append({"role": "sections", "severity": "warning",
                             "code": "section_missing", "section": name,
                             "detail": f"{_f_section(name)} 가 없거나 비었다"})
            continue
        out[name] = {"kind": "text", "text": text}
    return out


# --------------------------------------------------------------------------
# 목록 만들기 — 오늘 일정 · 일정별 관련 메일 · 일정과 무관한 미회신
# --------------------------------------------------------------------------

def _to_tz(raw, tz: ZoneInfo, all_day: bool) -> str:
    """tz-aware 시각을 브리핑 시간대로 변환해 싣는다(C5).

    `00:00Z` 일정을 그대로 실으면 표기가 아홉 시간 어긋난다. 종일
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


def _akey(cand: dict) -> str:
    return json.dumps(cand["anchor"], sort_keys=True, ensure_ascii=False)


def _attendee_count(ev: dict) -> int | None:
    """참석자 수. 참석자가 있다는데 목록이 없으면(옛 itda-hyve) 모른다 — None."""
    if isinstance(ev.get("attendees"), list):
        return len(ev["attendees"])
    return None if ev.get("has_attendees") else 0


def _event_candidate(ev: dict, tz: ZoneInfo) -> dict:
    all_day = bool(ev.get("all_day"))
    start = _to_tz(ev.get("start"), tz, all_day)
    return {
        # 앵커에 account 와 start 가 있어야 계정이 다른 같은 UID, 그리고 같은
        # UID 의 반복 회차(마스터 UID 유지 — expand_events)가 서로 갈린다(C6).
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
        "organizer": _person_email(ev.get("organizer")),
        "attendee_count": _attendee_count(ev),
        "attendees_truncated": bool(ev.get("attendees_truncated")),
        "related": [],
        "related_more": 0,
    }


def _event_sort_key(c: dict) -> tuple:
    # 종일 일정이 먼저, 그다음 시작 시각순(같으면 제목).
    return (0 if c["all_day"] else 1, c["start"], c["summary"])


def _mail_item(m: dict, tz: ZoneInfo) -> dict:
    raw = m["raw"]
    acc = m["acc"]
    return {
        "anchor": {
            "provider": PROVIDER, "account": acc["name"], "folder": "INBOX",
            "uidvalidity": None, "uid": str(m["uid"]),
            "message_id": m["message_id"],
        },
        "from": ", ".join(str(x) for x in raw.get("from") or []),
        "subject": str(raw.get("subject") or ""),
        "date": m["dt"].astimezone(tz).isoformat() if m["dt"] else "",
        "verdict": m["verdict"],
        "reason_code": m["reason"],
    }


def assemble(calendar: dict, email: dict, tz: ZoneInfo, win: dict) -> dict:
    """역할 dict → 오늘 일정(관련 메일 포함)·일정과 무관한 미회신·본문이 필요한 uid.

    - 오늘 일정: [오늘 00:00, 내일 00:00) 과 겹치는 것, 종일 먼저 그다음 시각순.
    - 관련 메일: 받은 메일 중 내가 보내지 않은 것에서 참석자·주최자 주소가 보낸 사람·받는 사람에 있거나
      제목 키워드가 맞는 것. 스레드당 최신 1통, 일정당 5통. 참조로만 받은 메일·단체 메일도 관련 메일은 될 수
      있다(판정 모집단과 다르다). **대량 메일은 주소로 이어질 때만** 붙는다 — 참석자가 메일링 리스트로 보낸
      안내는 그 자리의 준비지만, 제목 키워드만 맞는 뉴스레터는 우연이다.
    - 일정과 무관한 미회신: 모집단(`exclusion`) 안에서 unreplied·replied_then_new 인데 그 스레드가 어느
      일정과도 이어지지 않은 것. 계정마다 스레드당 최신 1통, 8통.
    - 대량 발송(`bulk_kind` — 아는 상대 반영): 관련 메일로 붙지 않은 것을 계정 → 종류 → 발신자별로 묶는다 — 페이지의
      「대량 발송 메일」 절(제목만, itda-work/skills#41).
    """
    mine: set[str] = email.get("mine") or set()
    events: list[dict] = []
    for ev in calendar.get("events", []):
        cand = _event_candidate(ev, tz)
        span = _event_span(cand, tz)
        if span is None or not _overlaps(span, win["day0"], win["day1"]):
            continue
        cand["_people"] = event_people(ev, mine)
        cand["_keywords"] = event_keywords(cand["summary"])
        events.append(cand)
    events.sort(key=_event_sort_key)
    # 한 일정이 두 번 실리지 않게(같은 앵커) — 반복 전개·수정본이 겹칠 때.
    seen: set[str] = set()
    events = [c for c in events if not (_akey(c) in seen or seen.add(_akey(c)))]

    msgs = email.get("msgs") or []
    pool = [m for m in msgs if not m.get("mine")]
    related_threads: set[tuple[int, str]] = set()
    related_ids: set[int] = set()
    for cand in events:
        hits: list[dict] = []
        for m in pool:
            addrs = [a for a in m["from_addrs"] + m["to_addrs"] + m.get("cc_addrs", [])
                     if a not in mine]
            found = match_event(cand["_people"], cand["_keywords"], addrs,
                                str(m["raw"].get("subject") or ""))
            if found and found["match"] == "keyword" and _is_bulk(m):
                found = None
            if found:
                related_ids.add(id(m))
                m["_match"] = found
                hits.append(m)
        picked = latest_per_thread(hits)
        for m in hits:
            related_threads.add((m["acc"]["index"], m["thread"]))
        # 대량 메일은 회신 판정 대신 "bulk" — 리스트 공지에 「미회신」 을 달면 답장을 재촉하는 셈이다.
        cand["related"] = [{**_mail_item(m, tz), **m["_match"],
                            **({"verdict": "bulk", "reason_code": "bulk"} if _is_bulk(m) else {})}
                           for m in picked[:RELATED_LIMIT]]
        cand["related_more"] = max(0, len(picked) - RELATED_LIMIT)
        for m in hits:
            m.pop("_match", None)

    unreplied: list[dict] = []
    more = 0
    body_targets: dict[int, list[int]] = {}
    by_acc: dict[int, list[dict]] = {}
    for m in msgs:
        if exclusion(m, mine) or m["verdict"] not in ("unreplied", "replied_then_new"):
            continue
        if (m["acc"]["index"], m["thread"]) in related_threads:
            continue
        by_acc.setdefault(m["acc"]["index"], []).append(m)
    for idx in sorted(by_acc):
        picked = latest_per_thread(by_acc[idx])
        more += max(0, len(picked) - UNREPLIED_LIMIT)
        for m in picked[:UNREPLIED_LIMIT]:
            unreplied.append(m)
            body_targets.setdefault(idx, []).append(m["uid"])
    unreplied.sort(key=lambda m: (_when(m), m["uid"]), reverse=True)
    for cand in events:
        cand.pop("_people", None)
        cand.pop("_keywords", None)
    bulk = bulk_by_account(
        (m["acc"], {"kind": m["bulk_kind"], "from": ", ".join(str(x) for x in m["raw"].get("from") or []),
                    "subject": str(m["raw"].get("subject") or ""),
                    "date": m["dt"].astimezone(tz).isoformat() if m["dt"] else "", "when": _when(m)})
        for m in pool if id(m) not in related_ids and _is_bulk(m))
    return {"events": events, "unreplied": unreplied, "unreplied_more": more,
            "body_targets": body_targets, "bulk": bulk}


def bulk_by_account(pairs) -> dict:
    """(계정, 행) → 「대량 발송 메일」 절의 재료 — **계정마다** `bulk_digest`(itda-work/skills#41).

    업무용·개인용 계정이 섞이면 한 목록으로는 어느 계정의 메일인지 모른다. 발신자·종류 상한도 계정마다 따로 건다.
    `{"count", "kinds", "accounts": [{"account", "login", "count", "kinds", "groups"}]}` — `accounts` 는 accounts_list
    순번 순서이고 대량 메일이 **있는** 계정만 싣는다. 전체 `count`·`kinds` 는 계정 값의 합이다(verify 가 대조)."""
    by_acc: dict[int, tuple[dict, list[dict]]] = {}
    for acc, row in pairs:
        by_acc.setdefault(acc["index"], (acc, []))[1].append(row)
    accounts: list[dict] = []
    for idx in sorted(by_acc):
        acc, rows = by_acc[idx]
        digest = bulk_digest(rows)
        if digest["count"]:
            accounts.append({"account": acc["name"], "login": acc.get("email") or "", **digest})
    kinds = {k: sum(a["kinds"][k] for a in accounts) for k in BULK_KINDS}
    return {"count": sum(kinds.values()), "kinds": kinds, "accounts": accounts}


def empty_bulk() -> dict:
    return bulk_by_account(())


def bulk_digest(rows) -> dict:
    """대량·자동 발송 메일 → 「대량 발송 메일」 절의 재료(itda-work/skills#40 — 모델 요약 없이 제목 목록만).

    rows: `{"kind", "from", "subject", "date", "when"?}`. 발신자(주소 기준)로 먼저 묶고, **발신자마다 종류 하나**를
    정한다 — 메일마다 종류가 갈리면(같은 콘솔의 로그인 알림과 「결제 계정」 알림) 한 발신자가 두 줄로 쪼개진다.
    발신자의 종류는 그 메일들의 다수 종류(같으면 `BULK_KINDS` 뒤쪽 — 광고·결제가 알림보다 구체적이다).
    그다음 종류(`BULK_KINDS` 순) → 발신자(통수 많은 순, 같으면 최신순) → 제목(최신순 `BULK_SUBJECTS_PER_SENDER` 개,
    나머지는 `more`). 종류마다 발신자 `BULK_SENDERS_PER_KIND` 곳까지 싣고 나머지는 `senders_more`(곳)·
    `senders_more_count`(통)로 센다. `from` 이 빈 행은 발신자 없이 수만 센다.
    """
    by = {k: 0 for k in BULK_KINDS}
    slots: dict[str, dict] = {}
    for row in rows:
        kind = row.get("kind")
        if kind not in by:
            continue
        frm = str(row.get("from") or "")
        if not frm:
            by[kind] += 1
            continue
        name, addr = _sender({"from": [frm]})
        key = addr or name or frm
        label = name or addr or frm
        if name and addr and NOREPLY_DISPLAY.search(name):
            # 「발신전용」 은 누가 보냈는지 말하지 않는다 — 도메인을 곁들인다(NHN KCP 실측).
            label = f"{name} ({addr.split('@', 1)[1]})"
        slot = slots.setdefault(key, {"sender": label, "address": addr, "rows": []})
        slot["rows"].append(row)
    per_kind: dict[str, list[dict]] = {k: [] for k in BULK_KINDS}
    for slot in slots.values():
        tally = {k: sum(1 for r in slot["rows"] if r.get("kind") == k) for k in BULK_KINDS}
        kind = max(reversed(BULK_KINDS), key=lambda k: tally[k])
        rows_ = sorted(slot["rows"], key=lambda r: (r.get("when") or _EPOCH, r.get("subject") or ""),
                       reverse=True)
        by[kind] += len(rows_)
        per_kind[kind].append({
            "sender": slot["sender"], "address": slot["address"], "count": len(rows_),
            "subjects": [{"subject": r.get("subject") or "", "date": r.get("date") or ""}
                         for r in rows_[:BULK_SUBJECTS_PER_SENDER]],
            "more": max(0, len(rows_) - BULK_SUBJECTS_PER_SENDER),
            "_latest": rows_[0].get("when") or _EPOCH})
    groups: list[dict] = []
    for kind in BULK_KINDS:
        ranked = per_kind[kind]
        if not ranked:
            continue
        ranked.sort(key=lambda x: (-x["count"], -x["_latest"].timestamp(), x["sender"]))
        for x in ranked:
            x.pop("_latest")
        rest = ranked[BULK_SENDERS_PER_KIND:]
        groups.append({"kind": kind, "count": sum(x["count"] for x in ranked),
                       "senders": ranked[:BULK_SENDERS_PER_KIND],
                       "senders_more": len(rest), "senders_more_count": sum(x["count"] for x in rest)})
    return {"count": sum(by.values()), "kinds": by, "groups": groups}


def exclusion_counts(email: dict) -> dict[int, dict[str, int]]:
    """계정별 모집단 제외 수 — 참조 수신 경고에 쓴다."""
    mine = email.get("mine") or set()
    out: dict[int, dict[str, int]] = {}
    for m in email.get("msgs") or []:
        why = exclusion(m, mine)
        if why:
            row = out.setdefault(m["acc"]["index"], {})
            row[why] = row.get(why, 0) + 1
    return out


# --------------------------------------------------------------------------
# 계획 — 아직 받지 않은 파일을 batch 하나로
# --------------------------------------------------------------------------

def _chunks(rows: list, size: int) -> list[list]:
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def _inbox_args(account: str, win: dict) -> dict:
    # References 는 받지 않는다 — 판정은 message_id·in_reply_to 로 한다(itda-work/itda-hyve#9).
    return {"account": account, "mailbox": "INBOX", "since": win["inbox_since"],
            "limit": SEARCH_LIMIT, "include_snippet": SNIPPET_CHARS, "snippet_for": SNIPPET_FOR}


def _sent_args(account: str, win: dict) -> dict:
    return {"account": account, "mailbox": SENT_SPECIAL_USE, "since": win["sent_since"],
            "limit": SEARCH_LIMIT}


def _calendar_args(account: str, win: dict) -> dict:
    return {"account": account, "from": win["day0"].isoformat(), "to": win["day1"].isoformat(),
            "expand": True, "limit": EVENTS_LIMIT}


def has_snippet(msg: dict) -> bool:
    """imap_search `include_snippet` 이 본문 앞부분을 실었는가. 본문 파트가 없거나 비었으면(HTML 앞머리가 16KB 를
    넘는 메일 등) 필드가 빠진다 — 그때만 예외로 imap_fetch 로 본문을 받는다."""
    snip = msg.get("snippet")
    return isinstance(snip, str) and bool(snip.strip())


def build_plan(inp: Inputs, now: datetime, tz: ZoneInfo, *, save_dir: str,
               section_names: list[str] | None = None,
               weather_place: bool = False) -> dict:
    """아직 받지 않은 파일을 itda-hyve `batch` 인자로 묶는다(40개씩). 파일로 쓰는 것은 `write_plan` 이다.

    보통 **한 바퀴**다(itda-hyve 0.9.5): 계정 목록·현재 위치·오늘 일정·받은 메일(본문 앞부분 포함)·보낸 메일을
    account "*" 로 한꺼번에. 계정 목록을 모르는 첫 바퀴라 계정별 파일은 `{n}` 자리표시자로 나눈다.
    예외 바퀴(있을 때만): ⓐ 앞 바퀴에서 빠진 계정별 파일(계정이 새로 생겨 순번이 밀린 경우 등)을 계정 이름으로
    ⓑ 일정과 무관한 미회신 중 snippet 이 없는 메일의 본문(계정당 `imap_fetch` `uids` 한 호출).

    **location 은 같은 바퀴에 넣는다**(판단 — 근거는 README D17): OS 위치의 긴 대기(권한 창 25초 + 위치 8초)는 위치 권한을
    아직 정하지 않았을 때만, itda-hyve 프로세스당 한 번 생긴다. 권한이 정해진 뒤에는 최근 위치(10분)면 바로, 아니면 8초 안에
    끝나 메일 수집(첫 로그인 최대 6.5초 실측)과 겹친다. 따로 부르면 매일 바퀴 하나(모델 대기 33~72초 실측)가 늘고, `ip_only` 로
    바꾸면 매일 위치가 시·도부터 틀릴 수 있다(#37 — 대전 KT 회선이 성남). 날씨 예보는 batch 에 넣지 않는다 — 좌표가 location
    결과에 달려 있어 한 바퀴에 못 넣는다. 스크립트(weather-here)가 샌드박스에서 Open-Meteo 를 직접 부르고, 실패할 때만
    `http_request` 한 번(SKILL 1-4).
    """
    win = _windows(now)
    calls: list[dict] = []
    files: list[dict] = []

    def add(tool: str, args: dict, save: str, why: str) -> None:
        calls.append({"id": save.rsplit(".", 1)[0], "tool": tool,
                      "args": {**args, "save_as": save}})
        files.append({"save": save, "tool": tool, "why": why})

    want_weather = "날씨" in (section_names or []) and not weather_place
    st, accounts, err = _accounts(inp)
    if st == "missing":
        add("accounts_list", {}, ACCOUNTS_FILE, "계정 목록")
    if want_weather and not inp.exists(LOCATION_FILE):
        add("location", {}, LOCATION_FILE, "날씨 절의 현재 위치")
    note = ""
    if st == "missing":
        # 첫 바퀴 — 계정을 모르므로 "*" 로 펼친다(캘린더를 지원하지 않는 계정은 itda-hyve 가 skipped 로 돌려준다).
        add("calendar_events", _calendar_args(ALL_ACCOUNTS, win), _f_calendar(N),
            "오늘 일정(참석자·주최자 포함) — 계정마다")
        add("imap_search", _inbox_args(ALL_ACCOUNTS, win), _f_inbox(N),
            "최근 받은 메일(본문 앞부분 포함) — 계정마다")
        add("imap_search", _sent_args(ALL_ACCOUNTS, win), _f_sent(N),
            "내가 보낸 메일(회신 판정·아는 상대) — 계정마다")
    elif st == "ok":
        mail_done = True
        for acc in accounts:
            i, name = acc["index"], acc["name"]
            if acc["calendar"] and not inp.exists(_f_calendar(i)):
                mail_done = False
                add("calendar_events", _calendar_args(name, win), _f_calendar(i),
                    "오늘 일정(참석자·주최자 포함)")
            if not inp.exists(_f_inbox(i)):
                mail_done = False
                add("imap_search", _inbox_args(name, win), _f_inbox(i), "최근 받은 메일(본문 앞부분 포함)")
            if not inp.exists(_f_sent(i)):
                mail_done = False
                add("imap_search", _sent_args(name, win), _f_sent(i), "내가 보낸 메일(회신 판정)")
        if mail_done:
            # 본문은 「일정과 무관한 미회신」 중 snippet 이 없는 것만 — 그 판정에 일정과 메일이 모두 필요하다.
            scratch: list[dict] = []
            picked = assemble(collect_calendar(inp, accounts, tz, win, scratch),
                              collect_email(inp, accounts, tz, scratch), tz, win)
            need: dict[int, list[int]] = {}
            for m in picked["unreplied"]:
                if not has_snippet(m["raw"]):
                    need.setdefault(m["acc"]["index"], []).append(m["uid"])
            for acc in accounts:
                uids = need.get(acc["index"]) or []
                if uids and not inp.exists(_f_bodies(acc["index"])):
                    add("imap_fetch",
                        {"account": acc["name"], "mailbox": "INBOX",
                         "uids": uids[:FETCH_UIDS_MAX], "max_body_chars": BODY_CHARS},
                        _f_bodies(acc["index"]), "본문 앞부분이 없는 미회신 메일의 본문(예외)")
    elif st == "error":
        note = f"accounts_list 실패({err['code']}) — 수집 모드가 두 역할을 error 로 둔다"

    out: dict = {"status": "pending" if calls else "complete", "batches": [], "files": files}
    for chunk in _chunks(calls, BATCH_MAX_CALLS):
        out["batches"].append({"calls": chunk, "save_dir": save_dir, "overwrite": True,
                               "timeout_sec": BATCH_TIMEOUT_SEC})
    if note:
        out["note"] = note
    return out


def _host_join(host_dir: str, name: str) -> str:
    """호스트 폴더 + 파일 이름. 스크립트가 리눅스 샌드박스에서 돌아도 호스트는 Windows 일 수 있다."""
    if not PurePosixPath(host_dir).is_absolute() and PureWindowsPath(host_dir).is_absolute():
        return str(PureWindowsPath(host_dir) / name)
    return str(PurePosixPath(host_dir) / name)


def _host_name(host_dir: str) -> str:
    """호스트 경로의 마지막 이름(POSIX·Windows 모두)."""
    if not PurePosixPath(host_dir).is_absolute() and PureWindowsPath(host_dir).is_absolute():
        return PureWindowsPath(host_dir).name
    return PurePosixPath(host_dir.rstrip("/")).name


def same_folder_name(input_dir: Path, save_dir: str) -> bool:
    """입력 폴더(샌드박스 쪽)와 `--save-dir`(호스트 쪽)의 마지막 이름이 같은가 — 같은 폴더의 두 경로여야 한다.

    macOS 는 한글 파일 이름을 NFD(자모 분리)로 돌려줄 때가 있고 샌드박스·모델은 대개 NFC 로 쓴다 — 「클로드 실습」 이
    두 모양으로 갈려도 같은 이름이다(itda-work/skills#40). 그래서 NFC 로 맞춰 비교한다."""
    host = unicodedata.normalize("NFC", _host_name(save_dir))
    here = unicodedata.normalize("NFC", input_dir.resolve().name)
    return bool(host) and host == here


def write_plan(plan: dict, folder: Path, save_dir: str) -> dict:
    """계획을 입력 폴더의 `plan-<k>.json` 으로 쓰고, 모델이 `batch` 에 그대로 줄 인자만 돌려준다.

    모델이 호출 목록을 batch 인자로 다시 출력하던 시간(0.9.3 Cowork 실측 84초)을 없앤다 — itda-hyve 0.9.4 가
    `plan_file` 을 직접 읽는다(itda-work/itda-hyve#17). 파일 내용은 batch 인자와 같은 JSON 이고 허용 도구·검사도
    같다. 이름은 숨김이 아니어야 한다(itda-hyve 가 `.` 시작 이름을 거부). 같은 바퀴를 다시 부르면 덮어쓴다.

    첫 batch 가 `not_found` 로 한 바퀴를 날린 실측(0.6.0 Cowork, itda-work/skills#40) 뒤로 쓰기를 **확정**한다 —
    임시 이름에 쓰고 fsync 한 뒤 이름을 바꾸고(반쯤 쓴 파일이 보이지 않게), 폴더도 fsync 하고, 다시 읽어 같은
    내용인지 확인한 다음에야 경로를 낸다. 확인에 실패하면 `OSError` — 경로를 내지 않는다.
    """
    out: dict = {"status": plan["status"], "batch": []}
    for k, args in enumerate(plan["batches"], start=1):
        name = PLAN_FILE.format(k)
        text = json.dumps(args, ensure_ascii=False) + "\n"
        target = folder / name
        tmp = folder / f"{name}.part"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            _fsync(fh.fileno())
        tmp.replace(target)
        _fsync_dir(folder)
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            raise OSError(f"{target}: 쓴 계획 파일을 다시 읽지 못했다")
        out["batch"].append({"plan_file": _host_join(save_dir, name)})
    if plan.get("note"):
        out["note"] = plan["note"]
    return out


def _fsync(fd: int) -> None:
    os.fsync(fd)


def _fsync_dir(folder: Path) -> None:
    """폴더 항목을 디스크에 확정한다. Windows·일부 마운트는 폴더를 열 수 없다 — 그때는 건너뛴다."""
    try:
        fd = os.open(str(folder), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def collect_from_input(inp: Inputs, *, tz_name: str, now: datetime,
                       buttons: bool, section_names: list[str]) -> dict:
    tz = ZoneInfo(tz_name)
    win = _windows(now)
    warnings: list[dict] = []
    st, accounts, err = _accounts(inp)
    if st != "ok":
        err = err or {"code": "input_missing", "message": ACCOUNTS_FILE}
        for role in ("calendar", "email"):
            _warn(warnings, role, "error", err["code"], None, err["message"])
        calendar = {"state": "error", "accounts": [], "events": []}
        email = {"state": "error", "accounts": [], "msgs": [], "mine": set()}
        accounts = []
    else:
        calendar = collect_calendar(inp, accounts, tz, win, warnings)
        email = collect_email(inp, accounts, tz, warnings)
    picked = assemble(calendar, email, tz, win)

    unreplied: list[dict] = []
    missing: dict[int, int] = {}
    bodies: dict[int, tuple[dict[int, str], dict | None]] = {}
    for m in picked["unreplied"]:
        idx = m["acc"]["index"]
        if idx not in bodies:
            bodies[idx] = _read_bodies(inp, m["acc"])
        item = _mail_item(m, tz)
        # 본문 = 예외 바퀴의 imap_fetch 가 있으면 그것, 없으면 imap_search snippet(itda-hyve 0.9.5).
        text = bodies[idx][0].get(m["uid"])
        if text:
            item["body"] = text
            item["body_partial"] = False
        elif has_snippet(m["raw"]):
            item["body"] = m["raw"]["snippet"].strip()[:BODY_CHARS]
            item["body_partial"] = m["raw"].get("snippet_truncated") is True
        else:
            missing[idx] = missing.get(idx, 0) + 1
        unreplied.append(item)
    by_index = {a["index"]: a for a in accounts}
    for idx, n in sorted(missing.items()):
        err = bodies[idx][1]
        _warn(warnings, "email", "warning", "body_missing", by_index[idx],
              f"{n} message(s)" + (f" — {err['code']}" if err else ""))
    for idx, counts in sorted(exclusion_counts(email).items()):
        if counts.get("not_addressed"):
            _warn(warnings, "email", "warning", "not_addressed_skipped", by_index[idx],
                  f"받는 사람에 내가 없는 메일 {counts['not_addressed']}통"
                  "(참조 수신 포함 — imap_search 요약에 참조가 없다)")
    if picked["unreplied_more"]:
        warnings.append({"role": "email", "severity": "warning", "code": "unreplied_truncated",
                         "detail": f"계정당 {UNREPLIED_LIMIT}통을 넘은 {picked['unreplied_more']}통은 "
                                   "목록에 없다"})
    sections = collect_sections(inp, section_names, warnings)
    return build_candidates(tz_name=tz_name, now=now, buttons=buttons,
                            section_names=section_names, calendar=calendar,
                            email=email, events=picked["events"], unreplied=unreplied,
                            unreplied_more=picked["unreplied_more"],
                            bulk=picked["bulk"] if email["state"] == "ready" else empty_bulk(),
                            sections=sections, warnings=warnings)


def build_candidates(*, tz_name: str, now: datetime, buttons: bool,
                     section_names: list[str], calendar: dict, email: dict,
                     events: list[dict], unreplied: list[dict], unreplied_more: int,
                     bulk: dict, sections: dict, warnings: list[dict]) -> dict:
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
        "calendar": {"today": events},
        "email": {"unreplied": unreplied, "unreplied_more": unreplied_more, "bulk": bulk},
        "sections": sections,
        "warnings": warnings,
    }


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


def _seed_addrs(parent: dict, key: str, where: str) -> list[str]:
    value = parent.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and "@" in v for v in value):
        raise SeedError(f"{where}.{key}: 주소 문자열 배열이어야 한다")
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
    if "tomorrow" in seed:
        raise SeedError("seed.tomorrow: 이 판(0.5.0)은 오늘 일정만 싣는다 — tomorrow 를 지워라")

    for i, ev in enumerate(_seed_list(seed, "today", "seed")):
        where = f"seed.today[{i}]"
        ev = _seed_obj(ev, where)
        _seed_str(ev, "summary", where)
        _seed_str(ev, "calendar", where)
        _seed_str(ev, "status", where)
        _seed_str(ev, "organizer", where, required=False)
        _seed_str(ev, "location", where, required=False)
        _seed_addrs(ev, "attendees", where)
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
    """`09:30` 은 실행일에 얹는다 — 샘플은 언제 열어도 오늘이어야 한다.
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
    """검증된 시드 → 실데이터와 **같은 형식**의 candidates. 도구 응답 0.

    일정–메일 잇기는 실데이터와 같은 함수(`match_event`)를 쓴다. 날짜가 자유 표기("어제 17:40")라
    정렬은 시드 순서 그대로다."""
    tz = ZoneInfo(tz_name)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    persona = seed["persona"]
    me = normalize_address(persona.get("email") or SAMPLE_EMAIL_DEFAULT)
    mine = {me}

    events: list[dict] = []
    for i, ev in enumerate(seed.get("today") or [], start=1):
        all_day = bool(ev["all_day"])
        start = _sample_time(ev.get("start") or "", day0, tz, all_day,
                             f"seed.today[{i - 1}].start")
        end = _sample_time(ev.get("end") or "", day0, tz, all_day,
                           f"seed.today[{i - 1}].end")
        attendees = [{"email": a} for a in ev.get("attendees") or []]
        raw = {"organizer": ev.get("organizer") or "", "attendees": attendees}
        events.append({
            "anchor": {"provider": SAMPLE_TOKEN, "account": SAMPLE_TOKEN,
                       "calendar": ev["calendar"], "uid": f"{SAMPLE_TOKEN}-today-{i}",
                       "start": start},
            "summary": ev["summary"], "start": start, "end": end, "all_day": all_day,
            "location": ev.get("location") or "", "status": ev["status"],
            "organizer": normalize_address(ev.get("organizer")),
            "attendee_count": len(attendees), "attendees_truncated": False,
            "related": [], "related_more": 0,
            "_people": event_people(raw, mine),
            "_keywords": event_keywords(ev["summary"]),
        })
    events.sort(key=_event_sort_key)

    related_mail: set[int] = set()
    items: dict[int, dict] = {}
    for i, mail in enumerate(seed.get("mails") or [], start=1):
        item = {
            "anchor": {"provider": SAMPLE_TOKEN, "account": SAMPLE_TOKEN,
                       "folder": "INBOX", "uidvalidity": "1", "uid": str(i),
                       "message_id": f"{SAMPLE_TOKEN}-{i}@sample.example.com"},
            "from": mail["from"], "subject": mail["subject"], "date": mail["date"],
            "verdict": mail["verdict"],
            "reason_code": {"unreplied": "no_sent_in_thread",
                            "replied_then_new": "inbound_after_latest_sent",
                            "replied": "sent_after_latest_inbound"}.get(mail["verdict"],
                                                                         mail["verdict"]),
        }
        items[i] = item
        addrs = [a for a in _addrs([mail["from"]]) if a not in mine]
        for cand in events:
            found = match_event(cand["_people"], cand["_keywords"], addrs, mail["subject"])
            if found and found["match"] == "keyword" and mail["verdict"] == "bulk":
                found = None   # 대량 메일은 주소로 이어질 때만(실데이터와 같은 규칙)
            if found:
                related_mail.add(i)
                if len(cand["related"]) < RELATED_LIMIT:
                    # 단체 메일(group)은 실제 경로에서 스레드 판정을 받는다 — 샘플은 판정이 없어 "모름".
                    shown = item if item["verdict"] in THREAD_VERDICTS + ("bulk",) else \
                        {**item, "verdict": "unknown"}
                    cand["related"].append({**shown, **found})
                else:
                    cand["related_more"] += 1
    for cand in events:
        cand.pop("_people")
        cand.pop("_keywords")
    # 시나리오의 bulk 메일은 헤더가 없다 — 종류는 제목·보낸 사람 규칙으로, 그래도 모르면 뉴스레터.
    # 날짜가 자유 표기라 시나리오 순서(앞이 최신)를 시각 대신 쓴다.
    mails = seed.get("mails") or []
    sample_acc = {"index": 1, "name": SAMPLE_TOKEN, "email": me}
    bulk = bulk_by_account(
        (sample_acc,
         {"kind": bulk_kind({"from": [mail["from"]], "subject": mail["subject"]}) or "newsletter",
          "from": mail["from"], "subject": mail["subject"], "date": mail["date"],
          "when": _EPOCH + timedelta(seconds=len(mails) - i)})
        for i, mail in enumerate(mails, start=1)
        if mail["verdict"] == "bulk" and i not in related_mail)

    unreplied: list[dict] = []
    for i, mail in enumerate(seed.get("mails") or [], start=1):
        # bulk·group·unknown·replied 는 실제 경로에서도 「미회신」 이 아니다.
        if i in related_mail or mail["verdict"] not in ("unreplied", "replied_then_new"):
            continue
        item = dict(items[i])
        body = mail.get("body")
        if isinstance(body, str) and body.strip():
            item["body"] = body
        unreplied.append(item)

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
        "calendar": {"today": events},
        "email": {"unreplied": unreplied, "unreplied_more": 0, "bulk": bulk},
        "sections": sections,
        "warnings": warnings,
        "sample_persona": {"name": persona["name"], "role": persona["role"]},
        "sample_notes": notes if notes is not None else "",
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


def _is_abs_host_path(value: str) -> bool:
    """호스트 절대 경로인가 — 스크립트는 리눅스 샌드박스에서 돌아도 호스트는 Windows 일 수 있다."""
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _fail(code: str, detail: str, rc: int = 2) -> int:
    print(json.dumps({"status": "error", "error": code, "detail": detail},
                     ensure_ascii=False), file=sys.stderr)
    return rc


def _emit(payload: dict, out: str | None, compact: bool = False) -> int:
    text = json.dumps(payload, ensure_ascii=False, indent=None if compact else 2)
    if out:
        try:
            Path(out).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"status": "error", "error": "write_failed",
                              "path": out, "detail": str(exc)[:300]},
                             ensure_ascii=False), file=sys.stderr)
            return 3
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(
        description="아침 브리핑 후보 수집(candidates.json) — itda-hyve 도구 응답 폴더를 읽는다")
    ap.add_argument("--input", metavar="DIR|FILE",
                    help="itda-hyve 도구 응답을 저장한 폴더(또는 {파일 이름: 내용} 묶음 JSON)")
    ap.add_argument("--plan", action="store_true",
                    help="아직 받지 않은 파일을 itda-hyve batch 호출로 낸다")
    ap.add_argument("--save-dir", metavar="HOST_DIR",
                    help="--plan 전용. 입력 폴더의 호스트 절대 경로(itda-hyve 가 응답을 쓸 곳 — "
                         "Cowork 는 연결 폴더의 호스트 경로 아래, Claude Code 는 입력 폴더 그대로)")
    ap.add_argument("--weather-place", action="store_true",
                    help="--plan 전용. 사용자가 날씨 지역을 말했으면 준다(위치·예보 호출을 내지 않는다)")
    ap.add_argument("--skill-dir", help="morning-brief 스킬 디렉토리 절대경로(샘플 시나리오 위치)")
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--sections",
                    help="쉼표 구분. 허용: 날씨, 환율. 미지정이면 날씨, "
                         "빼려면 none")
    ap.add_argument("--sample", nargs="?", const="", metavar="SEED",
                    help="시나리오 파일로 샘플 브리핑을 만든다(도구 응답 불요). "
                         "경로를 생략하면 동봉 기본 시나리오를 쓴다")
    ap.add_argument("--include-buttons", action="store_true",
                    help="정확 문구 '액션 버튼 포함' 이 호출에 있을 때만 준다")
    ap.add_argument("--now", help="ISO 기준 시각(테스트용)")
    ap.add_argument("--out", help="출력 파일(기본 stdout)")
    args = ap.parse_args(argv)

    section_names = parse_sections(args.sections)

    skill_dir = Path(args.skill_dir).resolve() if args.skill_dir \
        else Path(__file__).resolve().parent.parent

    tz = ZoneInfo(args.tz)
    now = datetime.fromisoformat(args.now).replace(tzinfo=tz) \
        if args.now else datetime.now(tz)

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
            payload = build_sample_candidates(
                seed, tz_name=args.tz, now=now, buttons=args.include_buttons,
                section_names=section_names)
        except SeedError as exc:
            # 기본 시나리오로 조용히 대체하지 않는다 — 시드가 틀렸다는 사실이
            # 사라지면 다음 회차에 또 틀린다(no-silent-fallback).
            return _fail("sample_seed_invalid", f"{seed_path}: {exc.detail}")
        return _emit(payload, args.out)

    if not args.input:
        return _fail("input_required",
                     "--input <itda-hyve 응답 폴더> 가 필요하다(샘플은 --sample)")
    try:
        inp = Inputs(Path(args.input))
    except InputError as exc:
        return _fail(exc.code, exc.detail)

    if args.plan:
        if not args.save_dir or not _is_abs_host_path(args.save_dir):
            return _fail("save_dir_required",
                         "--plan 에는 --save-dir <입력 폴더의 호스트 절대 경로> 가 필요하다 — "
                         "itda-hyve 가 응답을 그 폴더에 직접 쓴다(Cowork 는 연결 폴더의 "
                         "호스트 경로 아래, Claude Code 는 입력 폴더 그대로)")
        if inp.bundle is None and not same_folder_name(inp.path, args.save_dir):
            return _fail("save_dir_mismatch",
                         f"--input 폴더 이름({inp.path.resolve().name})과 --save-dir 의 마지막 이름"
                         f"({_host_name(args.save_dir)})이 다르다 — 둘은 같은 폴더여야 한다. Cowork 는 "
                         "HOST_IN = <연결 폴더의 호스트 경로>/<연결 폴더 안 상대 경로>, IN = $HOME/mnt/<연결 폴더 이름>/<같은 상대 경로>")
        if inp.bundle is not None:
            return _fail("plan_needs_folder",
                         "--plan 의 --input 은 폴더여야 한다 — 계획 파일(plan-<k>.json)을 그 폴더에 쓴다")
        outdated = detect_hyve_outdated(inp)
        if outdated is not None:
            # 계획을 더 내지 않는다 — 날씨·환율·요약·렌더로 넘어갈 이유가 없다.
            _emit(outdated, None, compact=True)
            return EXIT_HYVE_OUTDATED
        plan = build_plan(inp, now, tz, save_dir=args.save_dir,
                          section_names=section_names, weather_place=args.weather_place)
        try:
            payload = write_plan(plan, inp.path, args.save_dir)
        except OSError as exc:
            return _fail("write_failed", f"{inp.path}: {str(exc)[:300]}", rc=3)
        return _emit(payload, args.out, compact=True)

    outdated = detect_hyve_outdated(inp)
    if outdated is not None:
        # candidates 를 쓰지 않는다 — 빈 브리핑을 만들지 않는다(#43). 작업 폴더에 지난 회차의 candidates 가 남아 있으면
        # 지운다: 그대로 두면 render 가 어제 것을 그린다.
        if args.out:
            try:
                Path(args.out).unlink(missing_ok=True)
            except OSError:
                pass
        _emit(outdated, None, compact=True)
        return EXIT_HYVE_OUTDATED
    payload = collect_from_input(inp, tz_name=args.tz, now=now,
                                 buttons=args.include_buttons,
                                 section_names=section_names)
    rc = _emit(payload, args.out)
    if rc == 0 and args.out:
        # 파일로 썼으면 한 줄만 낸다 — SKILL 5절이 `open_file` 로 열 수 있는지를 여기서 안다(candidates 에는 싣지 않는다).
        print(json.dumps({"status": "ok", "path": args.out, "server_version": server_version(inp),
                          "open_file": OPEN_FILE_FEATURE in server_features(inp)},
                         ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
