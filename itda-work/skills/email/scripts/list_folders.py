#!/usr/bin/env python3
"""itda-email: list_folders.py — List IMAP folders with message counts.

Usage:
    python3 scripts/list_folders.py --provider naver
    python3 scripts/list_folders.py --provider gmail --no-status

Outputs a JSON array to stdout. Each element has:
    name       — folder name (UTF-8, sanitized)
    delimiter  — folder hierarchy delimiter
    flags      — IMAP flags list
    messages   — total message count (omitted with --no-status)
    unseen     — unread count (omitted with --no-status)

Exit codes: 0 = success, 1 = error (credentials, IMAP, connection).
"""
from __future__ import annotations

import argparse
import imaplib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from email_imap_utf7 import decode_modified_utf7  # noqa: E402
from email_providers import detect_providers, get_provider, resolve_provider_name  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402
from env_loader import merged_env  # noqa: E402

# IMAP LIST response pattern:
#   (\HasNoChildren) "/" "INBOX"
#   (\HasNoChildren) "/" &u4Lvk-
_LIST_RE = re.compile(
    rb'\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>[^"]*)"|(?P<nil_delim>NIL))\s+"?(?P<name>[^"]*)"?$',
    re.IGNORECASE,
)

# Matches AUTHENTICATIONFAILED in IMAP error strings.
_AUTH_FAILED_RE = re.compile(r"AUTHENTICATION", re.IGNORECASE)


def _parse_list_line(raw: bytes) -> tuple[list[str], str | None, bytes]:
    """Parse a single IMAP LIST response line.

    Returns:
        (flags, delimiter, name_enc) where name_enc is the raw encoded bytes
        and delimiter is None when the server reports NIL (RFC 3501 §6.3.8).
    """
    m = _LIST_RE.match(raw.strip())
    if not m:
        return ([], "/", raw.strip())

    flags_str = m.group("flags").decode("ascii", errors="replace")
    flags = [f.strip() for f in flags_str.split() if f.strip()]
    # RFC 3501 §6.3.8: NIL means no hierarchy — do not fabricate a delimiter.
    if m.group("nil_delim") is not None:
        delim: str | None = None
    else:
        delim = (m.group("delim") or b"").decode("ascii", errors="replace") or None
    name_enc = m.group("name")
    return (flags, delim, name_enc)


def _query_status(imap: imaplib.IMAP4_SSL, name_enc: bytes) -> tuple[int, int]:
    """Fetch MESSAGES and UNSEEN counts for a folder.

    Returns:
        (messages, unseen) counts; (0, 0) on any error.
    """
    try:
        quoted = b'"' + name_enc.replace(b'\\', b'\\\\').replace(b'"', b'\\"') + b'"'
        typ, data = imap.status(quoted, "(MESSAGES UNSEEN)")
        if typ != "OK" or not data or not data[0]:
            return (0, 0)
        text = data[0].decode("ascii", errors="replace")
        m_msgs = re.search(r"MESSAGES\s+(\d+)", text)
        m_unseen = re.search(r"UNSEEN\s+(\d+)", text)
        msgs = int(m_msgs.group(1)) if m_msgs else 0
        unseen = int(m_unseen.group(1)) if m_unseen else 0
        return (msgs, unseen)
    except imaplib.IMAP4.error:
        return (0, 0)


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="List IMAP folders with message counts.")
    parser.add_argument(
        "--provider",
        required=True,
        choices=["naver", "google", "gmail", "daum", "icloud", "custom"],
        help="Email provider",
    )
    parser.add_argument(
        "--account",
        default=None,
        help="Account suffix (default, work, personal, 1, 2, ...)",
    )
    parser.add_argument(
        "--no-status",
        action="store_true",
        help="Skip MESSAGES/UNSEEN counts (faster, omits messages/unseen fields)",
    )
    args = parser.parse_args()

    env = merged_env()
    provider = get_provider(args.provider, env, account=args.account)

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
        print(json.dumps({"status": "error", "error": "imap_not_supported"}))
        sys.exit(1)

    try:
        imap = imaplib.IMAP4_SSL(provider["imap_host"], provider["imap_port"], timeout=30)
    except imaplib.IMAP4.error as e:
        if _AUTH_FAILED_RE.search(str(e)):
            print(json.dumps({"status": "error", "error": "auth_failed", "detail": str(e)}))
        else:
            print(json.dumps({"status": "error", "error": "imap_error", "detail": str(e)}))
        sys.exit(1)
    except OSError as e:
        print(json.dumps({"status": "error", "error": "connection_failed", "detail": str(e)}))
        sys.exit(1)

    logged_in = False
    try:
        try:
            imap.login(provider["email"], provider["password"])
            logged_in = True
        except imaplib.IMAP4.error as e:
            if _AUTH_FAILED_RE.search(str(e)):
                print(json.dumps({"status": "error", "error": "auth_failed", "detail": str(e)}))
            else:
                print(json.dumps({"status": "error", "error": "imap_error", "detail": str(e)}))
            sys.exit(1)

        # Naver IMAP rejects ``LIST  *`` (unquoted empty reference) with a
        # "bad syntax" error. imaplib's default arguments (directory='""',
        # pattern='*') produce the RFC-compliant ``LIST "" *`` form which
        # all tested providers accept.
        typ, raw_lines = imap.list()
        if typ != "OK":
            raise imaplib.IMAP4.error("LIST command returned non-OK status")

        results: list[dict] = []
        for raw in raw_lines:
            if not raw:
                continue
            flags, delim, name_enc = _parse_list_line(raw)
            # errors="replace" replaces non-ASCII bytes with U+FFFD. Ideally
            # we would use errors="surrogateescape" to preserve the exact bytes,
            # but Python's json.dumps rejects surrogate characters with
            # "surrogates not allowed", making the output unserializable.
            # Using "replace" is an acknowledged limitation: non-compliant IMAP
            # servers that send raw non-ASCII folder names (without Modified
            # UTF-7 encoding) will have those bytes replaced in raw_name.
            name_raw_str = name_enc.decode("ascii", errors="replace")
            sanitized_raw = sanitize_for_llm(name_raw_str, max_len=512)
            name = decode_modified_utf7(name_enc)
            sanitized_name = sanitize_for_llm(name, max_len=200)

            entry: dict = {
                "name": sanitized_name,
                "raw_name": sanitized_raw,
                "delimiter": delim,  # may be None → JSON null (RFC 3501 NIL)
                "flags": flags,
            }
            if not args.no_status:
                msgs, unseen = _query_status(imap, name_enc)
                entry["messages"] = msgs
                entry["unseen"] = unseen

            results.append(entry)

        print(json.dumps(results, ensure_ascii=False))
        sys.exit(0)

    except imaplib.IMAP4.error as e:
        print(json.dumps({"status": "error", "error": "imap_error", "detail": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "error": "unexpected", "detail": str(e)}))
        sys.exit(1)
    finally:
        if logged_in:
            try:
                imap.logout()
            except Exception:
                pass


if __name__ == "__main__":
    main()
