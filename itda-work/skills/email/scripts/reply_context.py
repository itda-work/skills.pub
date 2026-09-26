#!/usr/bin/env python3
"""itda-email: reply_context.py — 회신용 컨텍스트 결정론 수집 (SPEC-EMAIL-REPLY-CONTEXT-001).

대상 메일 1건(UID)을 주면 코드가 결정론적으로 다음을 수행해
회신용 컨텍스트 묶음 JSON을 stdout으로 반환한다:
  - 스레드 재구성 (References 정/역참조, INBOX+Sent 교차)
  - 발신자 히스토리 (FROM SEARCH)
  - 결정론 스코어링·랭킹·시간순·budget 제한

중복 내용 판단·제거는 하지 않는다(LLM 책임). 영속 저장 없음. stdlib only.

탐색(IMAP IO)은 토큰 0, Claude가 읽는 출력 묶음만 budget으로 제한한다.
"""
from __future__ import annotations

import argparse
import email
import email.header
import email.utils
import imaplib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_providers import get_provider  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402
from env_loader import merged_env  # noqa: E402
from read_email import (  # noqa: E402
    _build_body_field,
    _decode_address_header,
    _decode_header,
    _encode_folder,
    _get_raw_body_text,
    _strip_tags,
)

DEFAULT_TOP_N = 5
DEFAULT_BUDGET = 8000
MIN_PER_ITEM = 400
# 관련 메일 배치 FETCH 청크 크기 (#694): 후보 UID 를 한 번의 UID FETCH 로 묶되
# 서버 명령 길이 안전선에서 분할. 청크당 왕복 1회 → 순차 N회 왕복 제거.
RELATED_FETCH_BATCH = 500

# UID prefix 포함 (#694): 배치 FETCH 응답을 메시지별로 UID 매핑하려면 prefix 에
# UID 가 필요하다. UID FETCH 응답은 RFC 3501 상 UID 를 포함해야 하나 명시 요청으로
# 서버 차이를 방어한다. payload 는 여전히 HEADER.FIELDS 뿐이라 기존 파싱은 불변.
_HEADER_FETCH = "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID IN-REPLY-TO REFERENCES SUBJECT FROM TO DATE)])"
_FULL_FETCH = "(BODY.PEEK[])"

_RE_PREFIX = re.compile(r"^\s*((re|fwd|fw|답장|회신|전달)\s*:\s*)+", re.I)
_MSGID = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[0-9a-z가-힣]{2,}")
_ADDR = re.compile(r"[\w.\-+]+@[\w.\-]+")
_UID_RE = re.compile(rb"\bUID\s+(\d+)")
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


# ============ 순수 함수 (IMAP 비의존 — 단위 테스트 대상) ============

def norm_subject(s: str) -> str:
    """Re:/Fwd:/답장: 등 회신 prefix를 (중첩 포함) 제거한 제목."""
    if not s:
        return ""
    prev, out = None, s
    while prev != out:
        prev, out = out, _RE_PREFIX.sub("", out)
    return out.strip()


def subject_tokens(s: str) -> set[str]:
    return set(_TOKEN.findall(norm_subject(s).lower()))


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_msgids(header_val: str | None) -> list[str]:
    """References/In-Reply-To 헤더에서 <...> Message-ID들을 순서대로 추출."""
    if not header_val:
        return []
    return _MSGID.findall(header_val)


def dedup_ordered(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def extract_addr(from_header: str | None) -> str | None:
    if not from_header:
        return None
    m = _ADDR.search(from_header)
    return m.group(0).lower() if m else None


def parse_date(date_header: str | None) -> datetime | None:
    if not date_header:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def parse_sent_folder(list_lines: list[str]) -> str | None:
    r"""IMAP LIST 응답에서 \Sent SPECIAL-USE 플래그를 가진 폴더명 추출."""
    for s in list_lines:
        if "\\Sent" in s:
            m = re.search(r'"([^"]*)"\s*$', s)
            if m:
                return m.group(1)
            parts = s.split()
            if parts:
                return parts[-1].strip('"')
    return None


def score_related(cand_addr, cand_tokens, cand_dt,
                  target_addr, target_tokens, newest_dt):
    """관련 메일 결정론 스코어 + 사유. (스레드>발신자>제목>최근성 가중)"""
    score, reasons = 0.0, []
    if cand_addr and target_addr and cand_addr == target_addr:
        score += 2.0
        reasons.append("same_sender")
    ov = jaccard(cand_tokens, target_tokens)
    if ov > 0:
        score += round(ov, 3)
        reasons.append("subject_overlap")
    if cand_dt and newest_dt:
        days = abs((newest_dt - cand_dt).days)
        if days <= 30:
            score += round(0.5 * (1 - days / 30), 3)
            reasons.append("recent")
    return round(score, 3), reasons


def build_reply_headers(target_mid: str, refs_chain: list[str]) -> dict:
    """회신 발송용 In-Reply-To/References (RFC 5322): 조상 체인 + 부모 Message-ID."""
    refs = dedup_ordered(list(refs_chain) + ([target_mid] if target_mid else []))
    return {
        "in_reply_to": target_mid or None,
        "references": " ".join(refs) if refs else None,
    }


def allocate_budget(used: int, remaining_items: int, total_budget: int) -> int:
    """남은 budget을 남은 항목 수로 균등 분배 (최소 MIN_PER_ITEM)."""
    if remaining_items <= 0:
        return MIN_PER_ITEM
    return max(MIN_PER_ITEM, (total_budget - used) // remaining_items)


def rank_related(scored: list, top_n: int) -> list:
    """(score, ..., dt) 튜플 리스트를 점수→최근성 내림차순 정렬 후 top_n."""
    scored = sorted(scored, key=lambda x: (x[0], x[-1] or _EPOCH), reverse=True)
    return scored[:top_n]


# ============ IMAP IO ============

def connect(prov):
    imap = imaplib.IMAP4_SSL(prov["imap_host"], prov["imap_port"])
    imap.login(prov["email"], prov["password"])
    return imap


def imap_search(imap, *crit) -> list:
    try:
        typ, d = imap.uid("SEARCH", None, *crit)
        if typ != "OK" or not d or not d[0]:
            return []
        return d[0].split()
    except Exception:
        return []


def fetch_msg(imap, uid, spec):
    try:
        typ, fd = imap.uid("FETCH", uid, spec)
    except Exception:
        return None
    if typ != "OK" or not fd:
        return None
    raw = b"".join(p[1] for p in fd if isinstance(p, tuple))
    return email.message_from_bytes(raw) if raw else None


def _batched(seq, n):
    """리스트를 길이 n 청크로 나눠 순서대로 yield (서버 명령 길이 안전선)."""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _iter_fetch_messages(fetch_data):
    """배치 FETCH 응답에서 (uid_bytes|None, email.message) 쌍을 순서대로 yield (#694).

    배치 응답은 메시지마다 ``(envelope_prefix, literal)`` 튜플 + 구분자 ``b')'`` 가
    섞여 온다. 각 튜플의 prefix 에서 UID 를 뽑고 그 메시지의 literal 만 파싱한다
    (다른 메시지 payload 와 절대 합치지 않는다 — fetch_msg 의 단건 join 과 다른 점).
    """
    for part in fetch_data or []:
        if not isinstance(part, tuple):
            continue
        prefix, raw = part[0], part[1]
        if not raw:
            continue
        m = _UID_RE.search(prefix or b"")
        uid = m.group(1) if m else None
        yield uid, email.message_from_bytes(raw)


def find_sent_folder(imap) -> str | None:
    try:
        typ, data = imap.list()
        lines = [(ln.decode("utf-8", "replace") if isinstance(ln, bytes) else str(ln))
                 for ln in (data or [])]
        return parse_sent_folder(lines)
    except Exception:
        return None


def msg_summary(msg) -> dict:
    """email.message → 파싱된 헤더 dict (본문 제외)."""
    return {
        "message_id": (msg.get("Message-ID") or "").strip(),
        "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
        "references": (msg.get("References") or "").strip(),
        "from": _decode_header(msg.get("From", "")),
        "to": msg.get("To", ""),
        "subject": _decode_header(msg.get("Subject", "")),
        "date": msg.get("Date", ""),
    }


def collect_thread(imap, folders, target_mid, refs_chain) -> dict:
    """스레드 메일을 INBOX+Sent에서 수집. {message_id: (folder_name, uid_bytes)}."""
    root_mid = refs_chain[0] if refs_chain else target_mid
    known = set(refs_chain) | ({target_mid} if target_mid else set())
    found: dict = {}
    for folder, enc in folders:
        try:
            typ, _ = imap.select(enc, readonly=True)
        except imaplib.IMAP4.error:
            continue
        if typ != "OK":
            continue
        uids = set()
        for anchor in {m for m in (target_mid, root_mid) if m}:
            uids.update(imap_search(imap, "HEADER", "REFERENCES", anchor))
            uids.update(imap_search(imap, "HEADER", "IN-REPLY-TO", anchor))
        for mid in known:
            uids.update(imap_search(imap, "HEADER", "MESSAGE-ID", mid))
        for u in uids:
            m = fetch_msg(imap, u, _HEADER_FETCH)
            if not m:
                continue
            mid = (m.get("Message-ID") or "").strip()
            if mid and mid not in found:
                found[mid] = (folder, u)
    return found


def collect_related(imap, folders, target_addr, exclude_mids) -> list:
    """상대방과의 왕복 메일을 배치 FETCH 로 수집 (#694). [(folder, uid, summary)].

    방향 교정: 받은 폴더는 ``FROM target_addr``(상대→나), 보낸 폴더(Sent)는
    ``TO target_addr``(나→상대)로 검색해 '그 사람과의 대화'를 정확히 잡는다.
    (기존엔 Sent 도 FROM 이라 외부 상대 회신 시 내 과거 답장이 0건이었고,
    self-target 시 보낸함 전체가 잡혀 블로업했다.)

    성능: 후보 UID 전체를 한 번의 ``UID FETCH``(청크당 1회)로 묶어 받아, 1건마다
    순차 FETCH 하던 N회 왕복을 제거한다. 의미·스코어링은 불변(전 히스토리 대상).
    스레드(exclude_mids)는 제외한다.
    """
    out, seen = [], set(exclude_mids)
    if not target_addr:
        return out
    for folder, enc in folders:
        try:
            typ, _ = imap.select(enc, readonly=True)
        except imaplib.IMAP4.error:
            continue
        if typ != "OK":
            continue
        header = "TO" if folder == "Sent" else "FROM"
        uids = imap_search(imap, header, target_addr)
        for chunk in _batched(uids, RELATED_FETCH_BATCH):
            try:
                typ, fd = imap.uid("FETCH", b",".join(chunk), _HEADER_FETCH)
            except Exception:
                continue
            if typ != "OK" or not fd:
                continue
            for u, m in _iter_fetch_messages(fd):
                s = msg_summary(m)
                mid = s["message_id"]
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                out.append((folder, u, s))
    return out


# ============ 오케스트레이션 ============

def _err(error, **kw):
    print(json.dumps({"status": "error", "error": error, **kw}), file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="회신용 컨텍스트 결정론 수집")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account", default=None)
    ap.add_argument("--uid", required=True, help="대상 메일 UID")
    ap.add_argument("--folder", default="INBOX", help="대상 메일이 있는 폴더 (기본 INBOX)")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    ap.add_argument("--max-chars-total", type=int, default=DEFAULT_BUDGET)
    args = ap.parse_args()

    env = merged_env()
    prov = get_provider(args.provider, env, account=args.account)
    if not prov:
        _err("account_required_or_missing", provider=args.provider)
        sys.exit(2)
    if not prov.get("imap_host"):
        _err("imap_not_supported", provider=args.provider)
        sys.exit(1)
    try:
        imap = connect(prov)
    except Exception as e:
        _err("connection_failed", detail=str(e)[:200])
        sys.exit(1)

    inbox_enc = _encode_folder("INBOX")
    target_enc = _encode_folder(args.folder)

    # 대상 메일 (full fetch)
    imap.select(target_enc, readonly=True)
    target_full = fetch_msg(imap, args.uid.encode(), _FULL_FETCH)
    if not target_full:
        _err("target_not_found", uid=args.uid, folder=args.folder)
        try:
            imap.logout()
        except Exception:
            pass
        sys.exit(1)

    tsum = msg_summary(target_full)
    target_mid = tsum["message_id"]
    refs_chain = dedup_ordered(
        extract_msgids(tsum["references"]) + extract_msgids(tsum["in_reply_to"])
    )
    target_addr = extract_addr(tsum["from"])
    target_tokens = subject_tokens(tsum["subject"])

    # 폴더 집합 (INBOX + \Sent)
    sent = find_sent_folder(imap)
    folders = [("INBOX", inbox_enc)]
    enc_by_folder = {"INBOX": inbox_enc}
    if sent:
        sent_enc = _encode_folder(sent)
        folders.append(("Sent", sent_enc))
        enc_by_folder["Sent"] = sent_enc

    # 스레드 수집 + 대상 자신
    thread_map = collect_thread(imap, folders, target_mid, refs_chain)
    if target_mid:
        thread_map.setdefault(target_mid, (args.folder, args.uid.encode()))
        enc_by_folder.setdefault(args.folder, target_enc)

    # 스레드 본문 페치 + 시간순 정렬
    thread_items = []
    for mid, (folder, u) in thread_map.items():
        if mid == target_mid:
            m = target_full
        else:
            imap.select(enc_by_folder.get(folder, inbox_enc), readonly=True)
            m = fetch_msg(imap, u, _FULL_FETCH)
        if not m:
            continue
        s = msg_summary(m)
        s["_folder"] = folder
        s["_dt"] = parse_date(s["date"])
        s["_msg"] = m
        thread_items.append(s)
    thread_items.sort(key=lambda x: (x["_dt"] or _EPOCH))

    # budget 분배 (thread 우선)
    budget = args.max_chars_total
    used, truncated_items, thread_out = 0, 0, []
    n = len(thread_items)
    for i, s in enumerate(thread_items):
        per = allocate_budget(used, n - i, budget)
        # 토큰 효율: HTML 본문은 태그를 벗겨 평문화한 뒤 budget 적용
        # (raw HTML은 태그가 budget을 잠식한다). text/plain 파트가 있으면 우선.
        raw_body, fmt = _get_raw_body_text(s["_msg"], prefer_text=True)
        if fmt == "html":
            raw_body = _strip_tags(raw_body)
            fmt = "text"
        body_str, total, trunc = _build_body_field(raw_body, per)
        used += min(total, per)
        truncated_items += 1 if trunc else 0
        thread_out.append({
            "message_id": s["message_id"],
            "from": sanitize_for_llm(s["from"], max_len=200),
            "to": _decode_address_header(s["to"]),
            "subject": sanitize_for_llm(s["subject"], max_len=300),
            "date": sanitize_for_llm(s["date"], max_len=100),
            "folder": s["_folder"],
            "body": body_str,
            "body_format": fmt,
            "truncated": trunc,
        })

    # 관련 메일 (스레드 제외, FROM 히스토리) + 스코어링
    related_raw = collect_related(imap, folders, target_addr, set(thread_map.keys()))
    newest_dt = thread_items[-1]["_dt"] if thread_items else None
    scored = []
    for folder, u, s in related_raw:
        sc, reasons = score_related(
            extract_addr(s["from"]), subject_tokens(s["subject"]), parse_date(s["date"]),
            target_addr, target_tokens, newest_dt,
        )
        scored.append((sc, reasons, folder, s, parse_date(s["date"])))
    related_out = []
    for sc, reasons, folder, s, _dt in rank_related(scored, args.top_n):
        related_out.append({
            "message_id": s["message_id"],
            "from": sanitize_for_llm(s["from"], max_len=200),
            "subject": sanitize_for_llm(s["subject"], max_len=300),
            "date": sanitize_for_llm(s["date"], max_len=100),
            "folder": folder,
            "score": sc,
            "reason": reasons,
        })

    try:
        imap.logout()
    except Exception:
        pass

    out = {
        "status": "ok",
        "target": {
            "uid": args.uid, "provider": args.provider, "folder": args.folder,
            "message_id": target_mid,
            "from": sanitize_for_llm(tsum["from"], max_len=200),
            "subject": sanitize_for_llm(tsum["subject"], max_len=300),
            "date": sanitize_for_llm(tsum["date"], max_len=100),
        },
        "thread": thread_out,
        "related": related_out,
        "reply_headers": build_reply_headers(target_mid, refs_chain),
        "budget": {
            "max_chars_total": budget, "used_chars": used,
            "truncated_items": truncated_items,
        },
        "stats": {
            "thread_count": len(thread_out),
            "related_count": len(related_out),
            "folders_searched": [f[0] for f in folders],
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
