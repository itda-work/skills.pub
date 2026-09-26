#!/usr/bin/env python3
"""itda-email: move_email.py — Move messages between IMAP folders.

Usage:
    python3 scripts/move_email.py --provider naver --uid 5,6,7 \
        --from-folder INBOX --to-folder 업무

Outputs JSON to stdout:
    {"status":"ok","moved":[5,6,7],"to_folder":"업무","method":"move"|"copy_expunge",
     "new_uids":[...]|null,"messages":[{"uid","from","subject","date"}]}

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
    select_folder,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Move emails between IMAP folders.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--account", default=None)
    parser.add_argument("--uid", required=True, help="Comma-separated UID list (e.g. 5,6,7)")
    parser.add_argument("--from-folder", default="INBOX", help="Source folder (default INBOX)")
    parser.add_argument("--to-folder", required=True, help="Destination folder")
    args = parser.parse_args()

    try:
        uids = parse_uids(args.uid)
    except ImapOpError as e:
        emit_error(e.key, e.detail)

    imap, _provider = connect(args.provider, args.account)
    try:
        select_folder(imap, args.from_folder)
        messages = require_uids_exist(imap, uids, args.from_folder)
        method, new_uids = move_uids(imap, uids, args.to_folder)
        print(json.dumps({
            "status": "ok",
            "moved": [int(u) for u in uids],
            "to_folder": args.to_folder,
            "method": method,
            "new_uids": new_uids,
            "messages": messages,
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
