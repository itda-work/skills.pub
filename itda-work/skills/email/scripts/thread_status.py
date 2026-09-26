#!/usr/bin/env python3
"""itda-email: thread_status.py — 미회신 판정 (읽기 전용, 결정론).

최근 N일 INBOX 에서 **내가 To/CC 에 있는 인바운드 메일**을 뽑아, Message-ID 그래프
(In-Reply-To/References) + 날짜로 "그 스레드의 최신 상대 메시지 이후 내 발신(\\Sent)이
있는가" 를 판정한다. stdout JSON 한 덩어리, exit 0(정상) / 1(연결·인증 실패 등).

설계 계약
---------
* **연결·인증은 ``_imap_common.connect``**, 계정 주소는 ``email_providers`` 가 준
  ``provider["email"]``, \\Sent 폴더 탐색·헤더 파싱·배치 FETCH 는 ``reply_context`` 의
  함수를 재사용한다. 독립 IMAP 클라이언트를 만들지 않는다.
* **판정은 필드로만** 한다(``verdict`` / ``reason_code``). 본문·제목 어휘로 "질문인가"
  따위를 추론하는 필드를 두지 않는다(``verdict-channel-not-inference``).
* **fail-closed** — Message-ID 가 없어 그래프에 얹을 수 없으면 ``unknown`` 이고
  후보에서 빠진다(``excluded.unknown``). \\Sent 폴더를 **못 찾거나 끝까지 못 읽으면**
  "내가 답했는가" 를 잴 수 없으므로 전건 ``unknown`` + ``warnings``
  (``sent_folder_not_found`` / ``sent_read_failed``). 발신함 읽기 실패를 빈 폴더로
  접으면 그 순간 전건이 미회신으로 과보고된다 — 조용한 폴백 금지.

후보 모집단(universe)
---------------------
"인바운드 메일" = INBOX 에 있고, 내 주소가 To 또는 CC 에 있으며, 발신자가 내가 아닌 것.
Bcc 수신분과 자기 발신분은 **모집단 밖**이라 ``excluded`` 에 세지 않는다 —
``excluded`` 는 모집단 안에서 정책으로 떨어낸 것만 센다.

알려진 한계 (v1, 문서화된 미지원)
---------------------------------
* **alias 미지원** — 내 주소는 프로바이더 설정의 계정 주소 1개뿐이다. 설정에 alias
  목록의 출처가 없다. 별칭으로 받은 메일은 To/CC 매칭이 안 돼 모집단 밖이 된다.
* 같은 스레드에 창 안 인바운드가 여러 건이면 **각각 후보로 나온다**(스레드 접기 없음).
  판정은 스레드 단위라 값이 갈리지 않는다.
* 이 스크립트는 **읽기 전용**이다(select 는 전부 readonly, STORE/EXPUNGE 없음).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _imap_common import connect, logout_quiet  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402
from read_email import (  # noqa: E402
    _build_body_field,
    _decode_header,
    _encode_folder,
    _get_raw_body_text,
    _strip_tags,
)
from reply_context import (  # noqa: E402
    _batched,
    _iter_fetch_messages,
    dedup_ordered,
    extract_addr,
    extract_msgids,
    find_sent_folder,
    parse_date,
)

SCHEMA_VERSION = 1
DEFAULT_DAYS = 2
DEFAULT_LIMIT = 8
FETCH_BATCH = 500
GROUP_RECIPIENT_THRESHOLD = 5

# 발신함 조회 창은 인바운드 창보다 넓게 잡는다 (C8). 인바운드와 같은 창만 보면
# "5일 전 답장한 스레드에 오늘 후속이 온" 경우 그 답장이 창 밖이라 replied_then_new 가
# unreplied 로 뒤집힌다. SEARCH 창만 넓히고 그래프·판정은 그대로다 — 넓힌 창의 발신은
# 스레드가 같을 때만 매칭되므로 오탐을 만들지 않는다.
# (후보 References 기반 표적 Sent 검색은 다음 판. 지금은 창 확대가 최소 수정이다.)
SENT_LOOKBACK_EXTRA_DAYS = 28

# 자동발송으로 취급하는 발신 로컬파트 (계약 고정 — 어휘 추론이 아니라 주소 규칙이다).
NOREPLY_LOCALPARTS = ("noreply", "no-reply", "donotreply")
_NOREPLY_SEP = re.compile(r"[._\-]")
_NOREPLY_CANON = {_NOREPLY_SEP.sub("", t) for t in NOREPLY_LOCALPARTS}

# 판정 그래프에 필요한 헤더만 (본문은 --with-body 일 때 따로 페치).
_HEADER_FETCH = (
    "(UID BODY.PEEK[HEADER.FIELDS "
    "(MESSAGE-ID IN-REPLY-TO REFERENCES SUBJECT FROM TO CC DATE LIST-ID PRECEDENCE)])"
)
_FULL_FETCH = "(UID BODY.PEEK[])"

_ADDR_RE = re.compile(r"[\w.\-+]+@[\w.\-]+")
_UIDVALIDITY_RE = re.compile(rb"UIDVALIDITY\s+(\d+)")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


# ============ 순수 함수 (IMAP 비의존) ============

def normalize_addr(addr):
    """주소를 비교용으로 정규화: 소문자 + plus-addressing(``me+tag@``) 제거."""
    if not addr:
        return ""
    a = addr.strip().lower()
    if "<" in a and ">" in a:
        m = _ADDR_RE.search(a)
        a = m.group(0) if m else a
    if "@" not in a:
        return a
    local, _, domain = a.partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{domain}"


def header_addrs(*header_values):
    """To/CC 류 헤더 문자열들에서 정규화 주소 목록을 순서 보존·중복 제거로 뽑는다."""
    out = []
    seen = set()
    for val in header_values:
        for raw in _ADDR_RE.findall(val or ""):
            a = normalize_addr(raw)
            if a and a not in seen:
                seen.add(a)
                out.append(a)
    return out


def imap_since(now, days):
    """IMAP ``SINCE`` 날짜 문자열(로케일 비의존 ``DD-Mon-YYYY``)."""
    d = (now - timedelta(days=max(0, int(days)))).date()
    return f"{d.day:02d}-{_MONTHS[d.month - 1]}-{d.year}"


def is_bulk(msg):
    """대량·자동 발송인가 — List-Id / Precedence(bulk|list) / noreply 발신."""
    if (msg.get("list_id") or "").strip():
        return True, "list_id"
    prec = (msg.get("precedence") or "").strip().lower()
    if prec in ("bulk", "list"):
        return True, "precedence"
    local = (msg.get("from_addr") or "").split("@", 1)[0]
    if _NOREPLY_SEP.sub("", local) in _NOREPLY_CANON:
        return True, "noreply_sender"
    return False, ""


def is_group(msg):
    """수신자(To+CC) 총원이 임계 이상이면 그룹 발송으로 본다."""
    n = len(header_addrs(msg.get("to_raw"), msg.get("cc_raw")))
    return n >= GROUP_RECIPIENT_THRESHOLD, n


def order_key(msg):
    """정렬·비교용 시각. Date 파싱 실패는 **최신으로 간주하지 않는다**(EPOCH)."""
    return msg.get("dt") or _EPOCH


class ThreadIndex:
    """Message-ID 그래프의 union-find. 각 메시지의 {자기 id} ∪ refs 를 한 덩어리로 묶는다."""

    def __init__(self):
        self._parent = {}

    def _find(self, x):
        root = x
        while self._parent.get(root, root) != root:
            root = self._parent[root]
        while self._parent.get(x, x) != x:
            self._parent[x], x = root, self._parent[x]
        return root

    def add(self, ids):
        ids = [i for i in dedup_ordered(list(ids)) if i]
        if not ids:
            return None
        for i in ids:
            self._parent.setdefault(i, i)
        base = self._find(ids[0])
        for i in ids[1:]:
            other = self._find(i)
            if other != base:
                self._parent[other] = base
        return base

    def key_of(self, msg):
        """메시지의 스레드 키. 얹을 id 가 하나도 없으면 None(=unknown)."""
        ids = [msg.get("message_id")] + list(msg.get("refs") or [])
        ids = [i for i in ids if i]
        if not ids:
            return None
        return self._find(ids[0])


def judge(cand, thread_key, inbound, sent, my_addrs):
    """스레드 단위 판정 → (verdict, reason_code).

    최신 상대 메시지(=내가 아닌 발신자의 인바운드) 이후에 내 발신이 있으면 replied,
    내 발신이 아예 없으면 unreplied, 내 발신 뒤에 상대 메시지가 또 오면
    replied_then_new. 동시각은 보수적으로 replied_then_new(=표면화)로 접는다.
    """
    if thread_key is None or not cand.get("message_id"):
        # 자기 ID 가 없으면 anchor 도 세울 수 없고 회신 여부도 못 잇는다 — fail-closed.
        return "unknown", "no_message_id"
    counterpart = [m for m in inbound
                   if m["_thread"] == thread_key
                   and (m.get("from_addr") or "") not in my_addrs]
    latest_in = max([order_key(m) for m in counterpart] + [order_key(cand)])
    mine = [m for m in sent if m["_thread"] == thread_key]
    if not mine:
        return "unreplied", "no_sent_in_thread"
    latest_sent = max(order_key(m) for m in mine)
    if latest_sent > latest_in:
        return "replied", "sent_after_latest_inbound"
    return "replied_then_new", "inbound_after_latest_sent"


# ============ IMAP IO ============

def fetch_uidvalidity(imap, enc):
    """선택된 폴더의 UIDVALIDITY. 못 읽으면 None(앵커에 null 로 실린다)."""
    for getter in (lambda: imap.status(enc, "(UIDVALIDITY)"),
                   lambda: imap.response("UIDVALIDITY")):
        try:
            typ, data = getter()
        except Exception:
            continue
        if typ != "OK" or not data:
            continue
        for part in data:
            if part is None:
                continue
            raw = part if isinstance(part, bytes) else str(part).encode("utf-8", "replace")
            m = _UIDVALIDITY_RE.search(raw)
            if m:
                return int(m.group(1))
    return None


def search_since(imap, since):
    """``UID SEARCH SINCE`` → (uids, ok).

    ``reply_context.imap_search`` 는 실패를 삼켜 빈 리스트를 돌려주므로 여기서는 쓸 수
    없다 — 발신함에서 "읽기 실패" 와 "메일 없음" 이 구분되지 않으면 전건 미회신으로
    과보고된다(C4). 실패는 ``ok=False`` 로 호출자에게 전달한다.
    """
    try:
        typ, data = imap.uid("SEARCH", None, "SINCE", since)
    except Exception:
        return [], False
    if typ != "OK" or data is None:
        return [], False
    if not data or not data[0]:
        return [], True
    return data[0].split(), True


def parse_message(uid, msg):
    """헤더 email.message → 판정용 dict (본문 없음)."""
    refs = dedup_ordered(
        extract_msgids(msg.get("References")) + extract_msgids(msg.get("In-Reply-To"))
    )
    from_raw = _decode_header(msg.get("From", ""))
    return {
        "uid": uid.decode("ascii", "replace") if isinstance(uid, bytes) else str(uid or ""),
        # C7: 자기 ID 도 refs 와 같은 추출기로 정규화한다. 헤더 원문을 그대로 쓰면
        # CFWS 주석·잡문(`<id@x> (ignore previous instructions)`)이 붙었을 때 참조와
        # 문자열이 달라져 스레드가 끊기고, 미정규화 문자열이 anchor 로 흘러간다.
        "message_id": next(iter(extract_msgids(msg.get("Message-ID"))), ""),
        "refs": refs,
        "from_raw": from_raw,
        "from_addr": normalize_addr(extract_addr(from_raw) or ""),
        "to_raw": msg.get("To", ""),
        "cc_raw": msg.get("Cc", ""),
        "subject": _decode_header(msg.get("Subject", "")),
        "date_raw": msg.get("Date", ""),
        "dt": parse_date(msg.get("Date", "")),
        "list_id": msg.get("List-Id", ""),
        "precedence": msg.get("Precedence", ""),
    }


def collect_folder(imap, enc, since):
    """폴더의 SINCE 이후 메일 헤더를 배치 FETCH 로 수집 → (messages, uidvalidity, ok).

    ``ok`` 는 **폴더를 끝까지 읽었는가** 다(C4). SELECT·SEARCH·FETCH 중 하나라도
    실패하면 False 이며, 호출자는 그 목록을 "그 폴더의 전량" 으로 취급하면 안 된다.
    """
    try:
        typ, _ = imap.select(enc, readonly=True)
    except Exception:
        return [], None, False
    if typ != "OK":
        return [], None, False
    uidvalidity = fetch_uidvalidity(imap, enc)
    uids, ok = search_since(imap, since)
    out = []
    for chunk in _batched(uids, FETCH_BATCH):
        try:
            typ, fd = imap.uid("FETCH", b",".join(chunk), _HEADER_FETCH)
        except Exception:
            ok = False
            continue
        if typ != "OK" or not fd:
            ok = False
            continue
        for uid, msg in _iter_fetch_messages(fd):
            out.append(parse_message(uid, msg))
    return out, uidvalidity, ok


def fetch_bodies(imap, enc, uids, max_chars):
    """지정 UID 들의 본문을 한 번의 배치 FETCH 로 받아 {uid: body 문자열}."""
    bodies = {}
    if not uids:
        return bodies
    try:
        typ, _ = imap.select(enc, readonly=True)
    except Exception:
        return bodies
    if typ != "OK":
        return bodies
    for chunk in _batched([u.encode("ascii") for u in uids], FETCH_BATCH):
        try:
            typ, fd = imap.uid("FETCH", b",".join(chunk), _FULL_FETCH)
        except Exception:
            continue
        if typ != "OK" or not fd:
            continue
        for uid, msg in _iter_fetch_messages(fd):
            if uid is None:
                continue
            raw, fmt = _get_raw_body_text(msg, prefer_text=True)
            if fmt == "html":
                raw = _strip_tags(raw)
            body, _total, _trunc = _build_body_field(raw, max_chars)
            bodies[uid.decode("ascii", "replace")] = body
    return bodies


# ============ 오케스트레이션 ============

def run(imap, provider, *, days=DEFAULT_DAYS, limit=DEFAULT_LIMIT,
        with_body=0, now=None):
    """판정 본체 — 인증된 IMAP 세션을 받아 출력 dict 를 만든다(테스트 진입점)."""
    now = now or datetime.now(timezone.utc)
    since = imap_since(now, days)
    my_addrs = {normalize_addr(provider.get("email") or "")}
    my_addrs.discard("")
    warnings = []

    inbox_enc = _encode_folder("INBOX")
    inbound_all, uidvalidity, inbox_ok = collect_folder(imap, inbox_enc, since)
    if not inbox_ok:
        warnings.append({"code": "inbox_read_failed",
                         "detail": "INBOX 를 끝까지 읽지 못해 후보가 불완전하다"})
    if uidvalidity is None:
        warnings.append({"code": "uidvalidity_unavailable", "detail": "INBOX"})

    sent_all = []
    sent_readable = False
    sent_name = find_sent_folder(imap)
    if sent_name:
        sent_since = imap_since(now, int(days) + SENT_LOOKBACK_EXTRA_DAYS)
        sent_all, _sent_uv, sent_readable = collect_folder(
            imap, _encode_folder(sent_name), sent_since)
        if not sent_readable:
            warnings.append({
                "code": "sent_read_failed",
                "detail": f"{sent_name} 를 끝까지 읽지 못해 회신 여부를 판정할 수 없다",
            })
    else:
        warnings.append({
            "code": "sent_folder_not_found",
            "detail": "\\Sent SPECIAL-USE 폴더를 찾지 못해 회신 여부를 판정할 수 없다",
        })

    # 스레드 그래프: 인바운드·발신 전부를 같은 union-find 에 얹는다.
    index = ThreadIndex()
    for m in inbound_all + sent_all:
        index.add([m["message_id"]] + m["refs"])
    for m in inbound_all + sent_all:
        m["_thread"] = index.key_of(m)

    # 모집단: 내가 To/CC 에 있고 발신자가 내가 아닌 INBOX 메일.
    inbound = [
        m for m in inbound_all
        if (m["from_addr"] not in my_addrs)
        and (my_addrs & set(header_addrs(m["to_raw"], m["cc_raw"])))
    ]

    excluded = {"bulk": 0, "group": 0, "replied": 0, "unknown": 0}
    candidates = []
    for m in inbound:
        bulk, _why = is_bulk(m)
        if bulk:
            excluded["bulk"] += 1
            continue
        group, _n = is_group(m)
        if group:
            excluded["group"] += 1
            continue
        if not sent_readable:
            # 발신함을 못 읽었다 — 미회신으로 과보고하지 않고 전건 판정 불가로 접는다.
            excluded["unknown"] += 1
            continue
        verdict, reason = judge(m, m["_thread"], inbound, sent_all, my_addrs)
        if verdict == "unknown":
            excluded["unknown"] += 1
            continue
        if verdict == "replied":
            excluded["replied"] += 1
            continue
        m["_verdict"] = verdict
        m["_reason"] = reason
        candidates.append(m)

    candidates.sort(key=lambda m: (order_key(m), m["uid"]), reverse=True)
    candidates = candidates[:max(0, int(limit))]

    bodies = {}
    if with_body and with_body > 0:
        want = [m["uid"] for m in candidates if m["_verdict"] == "unreplied"]
        bodies = fetch_bodies(imap, inbox_enc, want, with_body)
        missing = [u for u in want if u not in bodies]
        if missing:
            warnings.append({"code": "body_fetch_failed",
                             "detail": f"{len(missing)} message(s)"})

    out_candidates = []
    for m in candidates:
        item = {
            "anchor": {
                "provider": provider.get("name"),
                "account": provider.get("email"),
                "folder": "INBOX",
                "uidvalidity": uidvalidity,
                "uid": m["uid"],
                "message_id": m["message_id"],
            },
            "from": sanitize_for_llm(m["from_raw"], max_len=200),
            "subject": sanitize_for_llm(m["subject"], max_len=300),
            "date": m["dt"].isoformat() if m["dt"] else None,
            "verdict": m["_verdict"],
            "reason_code": m["_reason"],
        }
        if m["uid"] in bodies:
            item["body"] = bodies[m["uid"]]
        out_candidates.append(item)

    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "provider": provider.get("name"),
        "account": provider.get("email"),
        "days": int(days),
        "candidates": out_candidates,
        "excluded": excluded,
        "warnings": warnings,
    }


def main():
    ap = argparse.ArgumentParser(description="미회신 판정 (읽기 전용)")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account", default=None)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--with-body", type=int, default=0, metavar="N",
                    help="unreplied 후보에 한해 본문 앞 N자를 같은 연결에서 함께 싣는다")
    args = ap.parse_args()

    # 연결·인증 실패는 connect 가 구조화 JSON + exit≠0 으로 끝낸다.
    imap, provider = connect(args.provider, args.account)
    try:
        out = run(imap, provider, days=args.days, limit=args.limit,
                  with_body=args.with_body)
    except Exception as e:  # 예상 못 한 실패도 구조화해서 표면화한다.
        logout_quiet(imap)
        # 에러 키는 스킬 공통 계약(`error`)을 따른다 — _imap_common.emit_error 와 동형.
        print(json.dumps({"status": "error", "error": "thread_status_failed",
                          "detail": str(e)[:200]}, ensure_ascii=False))
        sys.exit(1)
    logout_quiet(imap)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
