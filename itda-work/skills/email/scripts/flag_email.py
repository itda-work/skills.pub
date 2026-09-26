#!/usr/bin/env python3
"""itda-email: flag_email.py — Set/unset IMAP flags (\\Seen, \\Flagged).

Usage:
    python3 scripts/flag_email.py --provider naver --uid 5,6 --set seen
    python3 scripts/flag_email.py --provider naver --uid 5 --unset flagged

Outputs JSON to stdout:
    {"status":"ok","uids":[5,6],"flag":"seen","op":"set"}

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
    parse_uids,
    require_uids_exist,
    select_folder,
)

_FLAG_MAP = {"seen": r"\Seen", "flagged": r"\Flagged"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Set/unset IMAP message flags.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--account", default=None)
    parser.add_argument("--uid", required=True, help="Comma-separated UID list")
    parser.add_argument("--folder", default="INBOX", help="Target folder (default INBOX)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", dest="set_flag", choices=sorted(_FLAG_MAP))
    group.add_argument("--unset", dest="unset_flag", choices=sorted(_FLAG_MAP))
    args = parser.parse_args()

    try:
        uids = parse_uids(args.uid)
    except ImapOpError as e:
        emit_error(e.key, e.detail)

    flag_name = args.set_flag or args.unset_flag
    op = "set" if args.set_flag else "unset"
    store_op = "+FLAGS" if op == "set" else "-FLAGS"

    imap, _provider = connect(args.provider, args.account)
    try:
        select_folder(imap, args.folder)
        require_uids_exist(imap, uids, args.folder)  # STORE 전 실재 확인 (#1512)
        typ, _ = imap.uid("STORE", ",".join(uids), store_op, f"({_FLAG_MAP[flag_name]})")
        if typ != "OK":
            raise ImapOpError("store_failed", f"STORE {store_op} returned {typ}")
        print(json.dumps({
            "status": "ok",
            "uids": [int(u) for u in uids],
            "flag": flag_name,
            "op": op,
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
