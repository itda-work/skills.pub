#!/usr/bin/env python3
"""itda-email: mark_spam.py — Move a message to (or out of) the spam folder.

Usage:
    python3 scripts/mark_spam.py --provider naver --uid 12
    python3 scripts/mark_spam.py --provider naver --uid 12 --unmark

--unmark moves the message from the canonical Junk folder back to INBOX
(fixed destination — the original folder is not tracked).

Note: this is an IMAP MOVE only. Whether the provider's spam filter *learns*
from the move is provider-dependent and not guaranteed (the ``note`` field in
the output repeats this caveat).

Exit codes: 0 = success, 1 = error, 2 = ambiguous multi-account.
"""
from __future__ import annotations

import argparse
import imaplib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _imap_common import (  # noqa: E402
    PROVIDER_CHOICES,
    ImapOpError,
    connect,
    emit_error,
    logout_quiet,
    move_uids,
    parse_uids,
    require_uids_exist,
    resolve_canonical,
    select_folder,
)

_NOTE = (
    "IMAP 이동만 수행됨 — 제공자 스팸필터의 학습(분류 개선)은 보장되지 않습니다."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark/unmark a message as spam (IMAP move).")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--account", default=None)
    parser.add_argument("--uid", required=True, help="Comma-separated UID list")
    parser.add_argument(
        "--folder", default="INBOX", help="Source folder when marking (default INBOX)"
    )
    parser.add_argument(
        "--unmark",
        action="store_true",
        help="Move from canonical Junk back to INBOX",
    )
    args = parser.parse_args()

    try:
        uids = parse_uids(args.uid)
    except ImapOpError as e:
        emit_error(e.key, e.detail)

    imap, _provider = connect(args.provider, args.account)
    try:
        junk = resolve_canonical(imap, args.provider, "junk")
        if args.unmark:
            src, dest = junk, "INBOX"
        else:
            src, dest = args.folder, junk

        select_folder(imap, src)
        messages = require_uids_exist(imap, uids, src)
        method, new_uids = move_uids(imap, uids, dest)
        print(json.dumps({
            "status": "ok",
            "moved": [int(u) for u in uids],
            "to_folder": dest,
            "method": method,
            "new_uids": new_uids,
            "messages": messages,
            "note": _NOTE,
        }, ensure_ascii=False))
        sys.exit(0)
    except ImapOpError as e:
        emit_error(e.key, e.detail)
    except imaplib.IMAP4.error as e:
        emit_error("imap_error", str(e))
    except Exception as e:
        emit_error("unexpected", str(e))
    finally:
        logout_quiet(imap)


if __name__ == "__main__":
    main()
