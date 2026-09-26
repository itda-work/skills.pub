#!/usr/bin/env python3
"""itda-email: trash_email.py — Move messages to Trash, restore, or expunge.

Usage:
    python3 scripts/trash_email.py --provider naver --uid 5,6            # → Trash
    python3 scripts/trash_email.py --provider naver --uid 5 --restore    # Trash → INBOX
    python3 scripts/trash_email.py --provider naver --uid 5 --expunge --dry-run
    python3 scripts/trash_email.py --provider naver --uid 5 --expunge    # 영구 삭제

--expunge permanently deletes messages inside the canonical Trash folder.
--dry-run prints target metadata only and issues **no IMAP write command**.
Real expunge requires UIDPLUS (UID EXPUNGE); without it the operation is
refused with ``uidplus_unsupported`` — a plain EXPUNGE would also destroy
unrelated \\Deleted messages.

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
    capabilities,
    connect,
    emit_error,
    logout_quiet,
    move_uids,
    parse_uids,
    require_uids_exist,
    resolve_canonical,
    select_folder,
)


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Trash / restore / expunge emails.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--account", default=None)
    parser.add_argument("--uid", required=True, help="Comma-separated UID list")
    parser.add_argument(
        "--folder", default="INBOX", help="Source folder for the default trash move"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--restore", action="store_true", help="Move from Trash back to INBOX")
    mode.add_argument(
        "--expunge", action="store_true", help="Permanently delete inside Trash"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --expunge: print target metadata only (no IMAP write commands)",
    )
    args = parser.parse_args()

    if args.dry_run and not args.expunge:
        emit_error("invalid_arguments", "--dry-run is only valid with --expunge")

    try:
        uids = parse_uids(args.uid)
    except ImapOpError as e:
        emit_error(e.key, e.detail)

    imap, _provider = connect(args.provider, args.account)
    try:
        if args.expunge:
            trash = resolve_canonical(imap, args.provider, "trash")
            if args.dry_run:
                # Read-only path: SELECT (readonly) + FETCH meta only.
                select_folder(imap, trash, readonly=True)
                targets = require_uids_exist(imap, uids, trash)
                print(json.dumps(
                    {"status": "dry_run", "targets": targets},
                    ensure_ascii=False,
                ))
                sys.exit(0)

            if "UIDPLUS" not in capabilities(imap):
                raise ImapOpError(
                    "uidplus_unsupported",
                    "server lacks UIDPLUS — expunge refused (plain EXPUNGE would "
                    "remove unrelated \\Deleted messages)",
                )
            select_folder(imap, trash)
            targets = require_uids_exist(imap, uids, trash)
            uid_set = ",".join(uids)
            typ, _ = imap.uid("STORE", uid_set, "+FLAGS", r"(\Deleted)")
            if typ != "OK":
                raise ImapOpError("expunge_failed", "STORE +FLAGS \\Deleted failed")
            typ, _ = imap.uid("EXPUNGE", uid_set)
            if typ != "OK":
                raise ImapOpError("expunge_failed", "UID EXPUNGE failed")
            print(json.dumps({
                "status": "ok",
                "expunged": [int(u) for u in uids],
                "messages": targets,
            }, ensure_ascii=False))
            sys.exit(0)

        if args.restore:
            trash = resolve_canonical(imap, args.provider, "trash")
            src, dest = trash, "INBOX"
        else:
            src = args.folder
            dest = resolve_canonical(imap, args.provider, "trash")

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
