#!/usr/bin/env python3
"""itda-email: read_email.py — read email via IMAP SSL."""
from __future__ import annotations

import argparse
import email
import email.header
import imaplib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_imap_utf7 import encode_modified_utf7  # noqa: E402
from email_providers import detect_providers, get_provider, resolve_provider_name  # noqa: E402
from email_security import (  # noqa: E402
    build_auth_label,
    parse_auth_results,
    reply_to_differs,
    sanitize_for_llm,
    wrap_email_content,
)
from email_state import (  # noqa: E402
    get_account_state,
    load_state,
    reset_account_state,
    save_state,
    update_account_state,
)
from env_loader import merged_env  # noqa: E402
from itda_path import resolve_data_dir  # noqa: E402

DEFAULT_MAX_CHARS = 1500  # default body length for --max-chars (token-optimized: most emails fit in 1500 chars)
# @MX:NOTE: v0.21.0부터 본문은 opt-in(--body). 플래그 없으면 메타데이터만 반환한다.
# DEFAULT_MAX_CHARS는 --body가 켜졌고 --max-chars 미지정일 때만 적용. 전체 본문은 --max-chars -1.

# Headers required for sanitization, dates, and phishing signal extraction.
# Used by --headers-only mode to fetch only required header fields, not the full RFC822 body.
_HEADER_FIELDS = (
    "FROM SUBJECT DATE REPLY-TO TO CC AUTHENTICATION-RESULTS"
    " MESSAGE-ID IN-REPLY-TO REFERENCES"
)
# UID prefix in every FETCH (issue #692): the reply workflow (reply_context.py
# --uid) and the draft tools all key off the *stable* UID. All SEARCH/FETCH here
# are UID commands (issue #1018) — sequence numbers are per-session and some
# servers (ecount) reject sequence-number SEARCH outright.
_HEADERS_ONLY_FETCH_SPEC = f"(UID BODY.PEEK[HEADER.FIELDS ({_HEADER_FIELDS})])"
# Full message fetch via PEEK (does NOT mark \Seen flag, unlike RFC822).
_FULL_FETCH_SPEC = "(UID BODY.PEEK[])"
HEADER_FIELD_LIMIT = 500  # sanitize cap for header fields (from/subject/reply-to)

# Parses the UID token from a FETCH response envelope, e.g.
# b'12 (UID 33027 BODY[] {842}' -> b'33027'. Scanned only on the metadata
# prefix, never the message payload, so a "UID ..." string in a body can't spoof it.
_UID_RE = re.compile(rb"\bUID\s+(\d+)")

# Truncation notice appended when body exceeds max_chars (FR-03).
TRUNCATE_NOTICE_TEMPLATE = (
    "\n\n...[이하 {n}자 생략. --max-chars=-1로 재실행하면 전체 본문을 볼 수 있습니다.]"
)


def _strip_tags(html: str) -> str:
    """Remove HTML tags from string."""
    return re.sub(r"<[^>]+>", "", html)


def _decode_header(raw: str) -> str:
    """Decode RFC 2047 encoded email header."""
    parts = []
    for chunk, charset in email.header.decode_header(raw):
        if isinstance(chunk, bytes):
            for enc in [charset or "utf-8", "utf-8", "euc-kr", "cp949", "latin-1"]:
                try:
                    parts.append(chunk.decode(enc))
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                parts.append(chunk.decode("latin-1", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _get_raw_body_text(
    msg: email.message.Message,
    prefer_text: bool = False,
) -> tuple[str, str]:
    """Extract full raw text body from email message.

    Returns (raw_body, body_format) tuple where body_format is 'html', 'text', or ''.
    Callers are responsible for applying max_chars limits via _build_body_field().

    SPEC-EMAIL-MULTIPART-001 정합성:
    - Content-Disposition: attachment 파트는 본문 후보에서 제외 (D-1 수정)
    - multipart/alternative 내 HTML 우선 정책 (D-4 수정, OQ-1 권장안)
    - prefer_text=True 시 text/plain 우선 (--prefer-text opt-out 지원)
    """
    if not msg.is_multipart():
        # 단순 메일: 기존 동작 유지 (회귀 보장)
        payload = msg.get_payload(decode=True)
        if not payload:
            return "", ""
        charset = msg.get_content_charset() or "utf-8"
        raw_text = payload.decode(charset, errors="replace")
        if msg.get_content_type() == "text/html":
            return _strip_tags(raw_text), "html"
        return raw_text, "text"

    # multipart: Content-Disposition:attachment 제외 후 두 패스로 후보 수집
    html_candidate = ""
    text_candidate = ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue  # 컨테이너 파트, 건너뜀
        cd = (part.get("Content-Disposition") or "").lower()
        if "attachment" in cd:
            continue  # 첨부 파트 제외 (D-1 수정)
        ct = part.get_content_type()
        # text/* 타입만 본문 후보로 허용 (non-text inline은 건너뜀)
        if not ct.startswith("text/"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if ct == "text/html" and not html_candidate:
            html_candidate = text
        elif ct == "text/plain" and not text_candidate:
            text_candidate = text

    # OQ-1 권장안 (a): HTML 우선 / prefer_text=True 시 text 우선
    if prefer_text:
        if text_candidate:
            return text_candidate, "text"
        if html_candidate:
            return html_candidate, "html"
    else:
        if html_candidate:
            return html_candidate, "html"  # raw HTML 유지 (EXC-4)
        if text_candidate:
            return text_candidate, "text"
    return "", ""


def _extract_attachments(msg: email.message.Message) -> list[dict]:
    """Walk message and collect attachment/inline metadata.

    Returns list of {"filename", "content_type", "size_bytes", "content_id"}.
    Content-Disposition: attachment 및 inline(with Content-ID) 파트 수집.
    SPEC-EMAIL-MULTIPART-001 REQ-004/005/008, OQ-4.
    """
    attachments: list[dict] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        cd = (part.get("Content-Disposition") or "").lower()
        cid_raw = part.get("Content-ID") or ""
        is_attachment = "attachment" in cd
        is_inline = "inline" in cd and cid_raw.strip()

        if not (is_attachment or is_inline):
            continue

        # filename: get_filename()은 RFC 2047/5987 인코딩도 처리
        filename_raw = part.get_filename()
        if filename_raw:
            filename: str | None = _decode_header(filename_raw)
        else:
            filename = None

        payload = part.get_payload(decode=True)
        size = len(payload) if payload else 0
        # Content-ID의 꺾쇠 괄호 제거: <logo123> → logo123
        cid = cid_raw.strip().strip("<>") or None

        attachments.append({
            "filename": filename,
            "content_type": part.get_content_type(),
            "size_bytes": size,
            "content_id": cid,
        })
    return attachments


def _decode_address_header(raw: str | None) -> list[dict]:
    """Decode RFC 2047 encoded address header and parse multiple addresses.

    Returns [{"name": str, "addr": str}, ...] or [] for empty/None input.
    SPEC-EMAIL-MULTIPART-001 REQ-003/006, OQ-3 (c) 채택.
    """
    import email.utils as _eu

    if not raw:
        return []
    # getaddresses는 복수 주소 파싱 (RFC 2822)
    addrs = _eu.getaddresses([raw])
    result: list[dict] = []
    for name, addr in addrs:
        if not addr:
            continue
        # RFC 2047 인코딩된 이름 디코딩
        decoded_name = _decode_header(name) if name else ""
        result.append({
            "name": sanitize_for_llm(decoded_name, max_len=200),
            "addr": sanitize_for_llm(addr, max_len=200),
        })
    return result


def _build_body_field(
    raw: str,
    max_chars: int,
) -> tuple[str, int, bool]:
    """Build the body JSON field with sanitization, wrapping, and truncation.

    Args:
        raw: Full raw text body (from _get_raw_body_text).
        max_chars: Maximum content characters. -1 = unlimited, 0 = empty.

    Returns:
        (wrapped_body, total_chars, truncated) tuple where:
        - wrapped_body: wrap_email_content(sanitized_body [+ notice])
        - total_chars: length of raw before any sanitize/truncation
        - truncated: True if raw exceeded max_chars
    """
    total = len(raw)

    if max_chars == 0:
        # Return empty wrapped body; truncated only when there was content.
        return wrap_email_content(""), total, total > 0

    if max_chars < 0:
        # Unlimited — pass full length to sanitize (at most total chars).
        sanitized = sanitize_for_llm(raw, max_len=max(total, 1))
        return wrap_email_content(sanitized), total, False

    # Bounded mode: sanitize to max_chars, then check if original was longer.
    sanitized = sanitize_for_llm(raw, max_len=max_chars)
    is_truncated = total > max_chars

    if is_truncated:
        n_omitted = total - max_chars
        notice = TRUNCATE_NOTICE_TEMPLATE.format(n=n_omitted)
        body_text = sanitized + notice
    else:
        body_text = sanitized

    return wrap_email_content(body_text), total, is_truncated


def _encode_folder(folder: str) -> str:
    """Prepare *folder* for the IMAP wire protocol.

    Applies, in order:
    1. Modified UTF-7 encoding for non-ASCII names (RFC 3501 §5.1.3).
    2. Double-quote wrapping when the result contains a space or other
       IMAP atom-unsafe characters. imaplib's ``select`` / ``status`` do
       NOT quote arguments, so callers must hand them wire-ready strings.
    3. Backslash escaping of embedded quotes and backslashes inside the
       quoted form.

    Naver's canonical folders (``Sent Messages``, ``Deleted Messages``)
    require this because imaplib would otherwise emit ``SELECT Sent
    Messages`` — two tokens — and the server returns ``BAD Invalid
    arguments``. Modified UTF-7 output never contains spaces so the
    quoting only kicks in for ASCII-with-spaces names.
    """
    try:
        folder.encode("ascii")
        encoded = folder
    except UnicodeEncodeError:
        encoded = encode_modified_utf7(folder)

    # Quote if the name contains any character outside the IMAP "atom-specials"
    # safe set. Spaces and double-quotes are the common offenders here.
    if re.search(r'[\s"\\(){}%*\]]', encoded):
        escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return encoded


def _fetch_uidvalidity(imap: imaplib.IMAP4, folder_enc: str) -> int:
    """Return the UIDVALIDITY for the selected folder, or ``0`` if unavailable.

    Tries ``imap.response('UIDVALIDITY')`` first (populated by the preceding
    SELECT), falling back to an explicit ``STATUS`` call on *folder_enc*.
    """
    try:
        typ, data = imap.response("UIDVALIDITY")
        if typ == "OK" and data:
            for item in data:
                if item is None:
                    continue
                try:
                    return int(item)
                except (TypeError, ValueError):
                    continue
    except imaplib.IMAP4.error:
        pass

    try:
        typ, data = imap.status(folder_enc, "(UIDVALIDITY)")
        if typ == "OK" and data and data[0]:
            raw = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
            match = re.search(r"UIDVALIDITY\s+(\d+)", raw)
            if match:
                return int(match.group(1))
    except imaplib.IMAP4.error:
        pass
    return 0


def _ensure_ok(typ: str, data: list, command: str) -> None:
    """Surface a failed IMAP command instead of parsing its error text.

    Servers like ecount (wmbox3.ecount.com) reject sequence-number SEARCH with
    ``NO [CANNOT] Search command must send messages with UID``. imaplib hands
    that tagged error text back as the response *data*, so skipping this check
    would let ``.split()`` turn the error words into bogus message ids
    (issue #1018).
    """
    if typ == "OK":
        return
    detail = ""
    if data and data[0] is not None:
        first = data[0]
        detail = first.decode(errors="replace") if isinstance(first, bytes) else str(first)
    raise imaplib.IMAP4.error(f"{command} failed: {typ} {detail}".strip())


def _parse_uid_search_result(data: list) -> list[bytes]:
    """Normalize an imap.uid('SEARCH', ...) response into a list of UID bytes.

    Every token must be numeric — a non-digit token means the response is not
    a UID list (e.g. server error text), which must surface as an error rather
    than flow into FETCH as a message id (issue #1018).
    """
    if not data or data[0] is None:
        return []
    first = data[0]
    if isinstance(first, str):
        first = first.encode()
    if not isinstance(first, bytes):
        return []
    tokens = first.split()
    for token in tokens:
        if not token.isdigit():
            raise imaplib.IMAP4.error(
                f"SEARCH returned a non-numeric token: {token.decode(errors='replace')!r}"
            )
    return tokens


def _extract_uid_from_fetch(fetch_data: list) -> str | None:
    """Extract the stable UID from an imap FETCH response (issue #692).

    A FETCH response part is a ``(envelope_prefix, literal_payload)`` tuple; the
    UID lives in the prefix (``b'12 (UID 33027 BODY[] {842}'``). We scan only the
    prefix (and any standalone bytes parts), never the literal payload, so a
    ``UID 999`` string inside a message body cannot be mistaken for the real UID.
    Returns the UID as a decoded string, or ``None`` if absent.
    """
    for part in fetch_data or []:
        if isinstance(part, tuple):
            head = part[0]
        elif isinstance(part, (bytes, bytearray)):
            head = part
        else:
            continue
        if head:
            m = _UID_RE.search(head)
            if m:
                return m.group(1).decode()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Read email via IMAP SSL.")
    parser.add_argument("--provider", required=True, choices=["naver", "google", "gmail", "daum", "icloud", "custom"])
    parser.add_argument("--account", default=None,
                        help="Account suffix (default, work, personal, 1, 2, ...)")
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--search", default="ALL")
    parser.add_argument("--unread-only", action="store_true")
    parser.add_argument(
        "--body",
        action="store_true",
        help=(
            "Fetch the message body. Default off: only metadata "
            "(from/subject/date/reply-to/auth) is returned. Pass --body when "
            "the user asks to read message content. Implied when --max-chars "
            "is given explicitly."
        ),
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help=(
            "Maximum body characters to return (implies --body). "
            f"Default when --body without --max-chars: {DEFAULT_MAX_CHARS}. "
            "-1 = full body. 0 = empty body."
        ),
    )
    parser.add_argument(
        "--prefer-text",
        action="store_true",
        help=(
            "When a message has both HTML and plain-text alternatives, prefer "
            "text/plain over text/html. Default: HTML preferred (OQ-1)."
        ),
    )
    parser.add_argument(
        "--headers-only",
        action="store_true",
        help=(
            "DEPRECATED (v0.21.0): metadata-only is now the default, so this "
            "flag is a no-op kept for backward compatibility. When combined "
            "with --body/--max-chars it still forces metadata-only."
        ),
    )
    parser.add_argument(
        "--since-last-run",
        action="store_true",
        help=(
            "Only fetch messages with UID greater than the last seen UID. "
            "State is kept at .itda-skills/email/state.json per "
            "(provider, email, folder). UIDVALIDITY changes trigger an "
            "automatic reset."
        ),
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help=(
            "Drop the incremental state entry for this (provider, email, "
            "folder) before fetching. Combine with --since-last-run to "
            "reseed from a clean slate."
        ),
    )
    args = parser.parse_args()

    if args.max_chars is not None and args.max_chars < -1:
        parser.error("--max-chars must be >= -1")

    # v0.21.0: 본문은 opt-in. --max-chars 명시는 --body를 함의(편의).
    # --headers-only(deprecated)는 함께 와도 메타데이터-only를 강제한다.
    want_body = (args.body or args.max_chars is not None) and not args.headers_only
    effective_max_chars = (
        (args.max_chars if args.max_chars is not None else DEFAULT_MAX_CHARS)
        if want_body
        else 0
    )


    env = merged_env()
    provider = get_provider(args.provider, env, account=args.account)
    provider_name = str((provider or {}).get("name", args.provider)).lower()

    if not provider or not provider.get("email") or not provider.get("password"):
        # Check if failure is due to ambiguous multi-account selection (AC-04, FR-05 rule #3)
        all_providers = detect_providers(env)
        canonical = resolve_provider_name(args.provider)
        matching = next((p for p in all_providers if p["provider"] == canonical), None)
        if matching and len(matching["accounts"]) > 1 and args.account is None:
            available = ", ".join(
                a["account_id"] for a in matching["accounts"] if a["status"] == "ready"
            )
            print(
                json.dumps({
                    "status": "error",
                    "error": "account_required",
                    "detail": f"Multiple accounts configured. Use --account. Available: {available}",
                }),
                file=sys.stderr,
            )
            sys.exit(2)
        print(json.dumps({"status": "error", "error": "credentials_missing"}))
        sys.exit(1)

    if not provider.get("imap_host"):
        error = f"{provider_name} provider does not support reading email via IMAP."
        print(json.dumps({
            "status": "error",
            "provider": provider_name,
            "error": error,
        }))
        sys.exit(1)

    search_criteria = "UNSEEN" if args.unread_only else args.search

    # --since-last-run state bookkeeping (SPEC-EMAIL-007)
    state_path = resolve_data_dir("email") / "state.json"
    state = load_state(state_path)
    account_email = provider["email"]

    if args.reset_state:
        state = reset_account_state(state, provider_name, account_email, args.folder)

    prev_entry = get_account_state(state, provider_name, account_email, args.folder)
    prev_uid = int(prev_entry["last_uid"]) if prev_entry else None
    prev_validity = int(prev_entry["uidvalidity"]) if prev_entry else None
    uidvalidity_changed = False

    # Non-ASCII folder names (Korean mailboxes like "보낸메일함") must be
    # Modified UTF-7 encoded before being handed to imaplib (RFC 3501 §5.1.3).
    folder_enc = _encode_folder(args.folder)

    try:
        imap = imaplib.IMAP4_SSL(provider["imap_host"], provider["imap_port"])
        imap.login(provider["email"], provider["password"])
        imap.select(folder_enc)
        current_validity = _fetch_uidvalidity(imap, folder_enc)

        if (
            args.since_last_run
            and prev_validity is not None
            and current_validity
            and prev_validity != current_validity
        ):
            uidvalidity_changed = True
            print(
                f"warning: UIDVALIDITY changed for {args.folder}, resetting state",
                file=sys.stderr,
            )
            prev_uid = None  # Fall back to normal fetch with fresh cursor.

        incremental_fetch = (
            args.since_last_run and prev_uid is not None and not uidvalidity_changed
        )
        # Every path operates on UIDs: the since-last-run cursor needs a value
        # that is stable across sessions, and some servers (ecount) reject
        # sequence-number SEARCH outright — UID SEARCH is the only portable
        # form (issue #1018).
        if incremental_fetch:
            typ, uid_data = imap.uid("SEARCH", None, f"UID {prev_uid + 1}:*")
            _ensure_ok(typ, uid_data, "UID SEARCH")
            all_ids = _parse_uid_search_result(uid_data)
            # ``UID n:*`` always returns the highest UID even when none qualify,
            # so filter defensively to UIDs strictly greater than the cursor.
            all_ids = [uid for uid in all_ids if int(uid) > prev_uid]
        else:
            typ, uid_data = imap.uid("SEARCH", None, search_criteria)
            _ensure_ok(typ, uid_data, "UID SEARCH")
            all_ids = _parse_uid_search_result(uid_data)

        fetch_ids = all_ids[-args.count :] if len(all_ids) > args.count else all_ids

        results = []
        fetched_uids: list[int] = []
        # @MX:NOTE: BODY.PEEK[] avoids marking \Seen flag (unlike RFC822).
        # HEADER.FIELDS variant only transfers required headers — major token saver.
        fetch_spec = _FULL_FETCH_SPEC if want_body else _HEADERS_ONLY_FETCH_SPEC
        for mid in reversed(fetch_ids):
            typ, data = imap.uid("FETCH", mid, fetch_spec)
            _ensure_ok(typ, data, "UID FETCH")
            if not data or data[0] is None:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)
            # Stable UID (issue #692). Parsed from the FETCH envelope; ``mid``
            # already IS the UID, so it is the fallback when a server omits
            # UID from the response.
            uid_val = _extract_uid_from_fetch(data)
            if uid_val is None:
                uid_val = mid.decode() if isinstance(mid, (bytes, bytearray)) else str(mid)
            try:
                fetched_uids.append(int(mid))
            except (TypeError, ValueError):
                pass
            raw_from = _decode_header(msg.get("From", ""))
            raw_subject = _decode_header(msg.get("Subject", ""))
            if want_body:
                raw_body_text, body_format = _get_raw_body_text(msg, prefer_text=args.prefer_text)
                body_str, total_chars, truncated = _build_body_field(
                    raw_body_text, effective_max_chars
                )
            # Phishing signal extraction (SPEC-EMAIL-005)
            raw_auth = msg.get("Authentication-Results")
            auth = parse_auth_results(raw_auth)
            auth_label = build_auth_label(auth)
            raw_reply_to = msg.get("Reply-To", "")
            differs = reply_to_differs(raw_from, raw_reply_to)
            warnings_list: list[str] = []
            if differs:
                warnings_list.append("reply_to_differs")
            if auth.get("spf") == "fail":
                warnings_list.append("spf_fail")
            if auth.get("dmarc") == "fail":
                warnings_list.append("dmarc_fail")
            entry: dict = {
                "id": mid.decode(),
                "uid": uid_val,
                "from": sanitize_for_llm(raw_from, max_len=HEADER_FIELD_LIMIT),
                "to": _decode_address_header(msg.get("To", "")),
                "cc": _decode_address_header(msg.get("Cc", "")),
                "bcc": _decode_address_header(msg.get("Bcc", "")),
                "subject": sanitize_for_llm(raw_subject, max_len=HEADER_FIELD_LIMIT),
                "date": sanitize_for_llm(msg.get("Date", ""), max_len=100),
                "message_id": sanitize_for_llm(msg.get("Message-ID", ""), max_len=400) or None,
                "in_reply_to": sanitize_for_llm(msg.get("In-Reply-To", ""), max_len=400) or None,
                "references": sanitize_for_llm(msg.get("References", ""), max_len=2000) or None,
                "attachments": _extract_attachments(msg),
            }
            # Body keys present only when fetched (v0.21.0). Their absence is
            # the metadata-only signal — no fake empty content envelope.
            if want_body:
                entry["body"] = body_str
                entry["body_format"] = body_format
                entry["total_chars"] = total_chars
                entry["truncated"] = truncated
            entry.update({
                "spf": auth.get("spf"),
                "dkim": auth.get("dkim"),
                "dmarc": auth.get("dmarc"),
                "auth_label": auth_label,
                "reply_to": sanitize_for_llm(raw_reply_to, max_len=200) or None,
                "reply_to_differs": differs,
                "warnings": warnings_list,
            })
            results.append(entry)

        imap.logout()

        if args.since_last_run:
            # Persist a cursor that advances to the highest UID we actually
            # saw (fetched in this run OR the previous cursor if nothing new).
            if fetched_uids:
                new_last_uid = max(fetched_uids)
            elif prev_uid is not None and not uidvalidity_changed:
                new_last_uid = prev_uid
            else:
                new_last_uid = 0

            state = update_account_state(
                state,
                provider_name,
                account_email,
                args.folder,
                new_last_uid,
                current_validity,
            )
            try:
                save_state(state_path, state)
            except OSError as exc:
                print(f"warning: failed to save state ({exc})", file=sys.stderr)

            output: object = {
                "since_last_run": True,
                "previous_last_uid": prev_uid,
                "current_last_uid": new_last_uid,
                "uidvalidity_changed": uidvalidity_changed,
                "new_count": len(results),
                "messages": results,
            }
        else:
            output = results

        print(json.dumps(output, ensure_ascii=False))
        sys.exit(0)
    except imaplib.IMAP4.error as e:
        print(json.dumps({"status": "error", "error": "imap_error", "detail": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "error": "unexpected", "detail": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
