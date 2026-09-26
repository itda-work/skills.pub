#!/usr/bin/env python3
"""itda-email: manage_folder.py — Create / rename / delete IMAP folders.

Usage:
    python3 scripts/manage_folder.py --provider naver --create 업무
    python3 scripts/manage_folder.py --provider naver --rename 업무 --to 업무2026
    python3 scripts/manage_folder.py --provider naver --delete 옛폴더 [--force]

Rules:
- Canonical folders (INBOX/Sent/Drafts/Trash/Junk — SPECIAL-USE or provider
  fallback names) can never be renamed or deleted → ``canonical_folder_protected``.
- Delete refuses a non-empty folder with ``folder_not_empty``; with --force the
  contents are MOVEd to the canonical Trash first, then the folder is deleted.

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
    canonical_protected_names,
    connect,
    emit_error,
    encode_and_quote,
    logout_quiet,
    move_uids,
    resolve_canonical,
    select_folder,
)


def _check_ok(typ: str, data: list, action: str) -> None:
    if typ != "OK":
        detail = ""
        if data and data[0]:
            d = data[0]
            detail = d.decode("ascii", errors="replace") if isinstance(d, bytes) else str(d)
        raise ImapOpError(f"{action}_failed", detail or f"{action} returned {typ}")


def _guard_canonical(imap: imaplib.IMAP4, provider_name: str, name: str, action: str) -> None:
    if name.lower() in canonical_protected_names(imap, provider_name):
        raise ImapOpError(
            "canonical_folder_protected",
            f"canonical folder {name!r} cannot be {action}d",
        )


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Create / rename / delete IMAP folders.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--account", default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", metavar="NAME", help="Create a folder")
    group.add_argument("--rename", metavar="NAME", help="Rename a folder (requires --to)")
    group.add_argument("--delete", metavar="NAME", help="Delete a folder")
    parser.add_argument("--to", default=None, help="New name for --rename")
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --delete: move contents to Trash first, then delete",
    )
    args = parser.parse_args()

    if args.rename and not args.to:
        emit_error("invalid_arguments", "--rename requires --to NEW_NAME")

    imap, _provider = connect(args.provider, args.account)
    try:
        if args.create:
            typ, data = imap.create(encode_and_quote(args.create))
            _check_ok(typ, data, "create")
            print(json.dumps(
                {"status": "ok", "action": "create", "folder": args.create},
                ensure_ascii=False,
            ))
            sys.exit(0)

        if args.rename:
            _guard_canonical(imap, args.provider, args.rename, "rename")
            typ, data = imap.rename(encode_and_quote(args.rename), encode_and_quote(args.to))
            _check_ok(typ, data, "rename")
            print(json.dumps(
                {"status": "ok", "action": "rename", "folder": args.rename, "to": args.to},
                ensure_ascii=False,
            ))
            sys.exit(0)

        # --delete
        name = args.delete
        _guard_canonical(imap, args.provider, name, "delete")
        count = select_folder(imap, name, readonly=True)
        moved_to_trash = 0
        if count > 0:
            if not args.force:
                raise ImapOpError(
                    "folder_not_empty",
                    f"folder {name!r} has {count} message(s); use --force to move them "
                    "to Trash and delete",
                )
            trash = resolve_canonical(imap, args.provider, "trash")
            select_folder(imap, name)  # re-select read-write
            typ, data = imap.uid("SEARCH", None, "ALL")
            _check_ok(typ, data, "search")
            uids = [u.decode("ascii") for u in (data[0] or b"").split()] if data else []
            if uids:
                move_uids(imap, uids, trash)
                moved_to_trash = len(uids)
        try:
            imap.close()
        except Exception:
            pass
        typ, data = imap.delete(encode_and_quote(name))
        _check_ok(typ, data, "delete")
        result: dict = {"status": "ok", "action": "delete", "folder": name}
        if moved_to_trash:
            result["moved_to_trash"] = moved_to_trash
        print(json.dumps(result, ensure_ascii=False))
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
