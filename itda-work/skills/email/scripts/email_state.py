"""Incremental fetch state for itda-email (SPEC-EMAIL-007).

Pure-function module for persisting IMAP UID cursors per (provider, email,
folder) tuple so read_email.py can return only newly-arrived messages via
``--since-last-run``.

Design goals
------------
* stdlib only (json, os, pathlib, datetime, sys).
* Never raise on corrupt input — always degrade to an empty state.
* Atomic writes: ``state.json.tmp`` -> ``os.replace(..., state.json)``.
* No locking: single-user assumption, last-writer-wins.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# @MX:ANCHOR: state schema entry point — touched by read_email.py on every
# --since-last-run invocation and by tests.
# @MX:REASON: Schema change would silently drop previously captured cursors;
# bump SCHEMA_VERSION and migrate explicitly when fields evolve.


def make_account_key(provider: str, email: str) -> str:
    """Build the canonical account key ``{provider_lower}:{email}``."""
    return f"{provider.lower()}:{email}"


def _empty_state() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "accounts": {}}


def load_state(path: Path) -> dict[str, Any]:
    """Load state from *path*, returning an empty state on any failure.

    Never raises: corrupt JSON, wrong schema, or filesystem errors all
    degrade to an empty state with a warning on stderr.
    """
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: state file corrupt, ignoring ({exc})", file=sys.stderr)
        return _empty_state()

    if not isinstance(data, dict):
        print("warning: state file corrupt, ignoring (not a dict)", file=sys.stderr)
        return _empty_state()

    if data.get("schema_version") != SCHEMA_VERSION:
        print(
            f"warning: state schema mismatch (got {data.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION}), ignoring",
            file=sys.stderr,
        )
        return _empty_state()

    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        data["accounts"] = {}
        return data

    # FR-12: migrate gmail: -> google: keys in-memory.
    # Keys starting with "gmail:" are copied to "google:" (if not already
    # present), then removed so the next save_state() persists only google:.
    migrated_keys = [k for k in list(accounts.keys()) if k.startswith("gmail:")]
    for old_key in migrated_keys:
        new_key = "google:" + old_key[len("gmail:"):]
        if new_key not in accounts:
            accounts[new_key] = accounts[old_key]
        del accounts[old_key]

    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically persist *state* to *path*.

    Writes to ``<path>.tmp`` then ``os.replace`` to avoid torn writes on
    concurrent reads. The parent directory is created if missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def get_account_state(
    state: dict[str, Any],
    provider: str,
    email: str,
    folder: str,
) -> dict[str, Any] | None:
    """Return the per-folder entry, or ``None`` if not tracked yet."""
    key = make_account_key(provider, email)
    accounts = state.get("accounts", {})
    folders = accounts.get(key)
    if not isinstance(folders, dict):
        return None
    entry = folders.get(folder)
    if not isinstance(entry, dict):
        return None
    return entry


def update_account_state(
    state: dict[str, Any],
    provider: str,
    email: str,
    folder: str,
    last_uid: int,
    uidvalidity: int,
) -> dict[str, Any]:
    """Upsert the entry for (provider, email, folder). Returns *state*."""
    key = make_account_key(provider, email)
    accounts = state.setdefault("accounts", {})
    folders = accounts.setdefault(key, {})
    folders[folder] = {
        "last_uid": int(last_uid),
        "uidvalidity": int(uidvalidity),
        "last_checked": datetime.now(timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds"),
    }
    return state


def reset_account_state(
    state: dict[str, Any],
    provider: str,
    email: str,
    folder: str,
) -> dict[str, Any]:
    """Remove the entry for (provider, email, folder). Returns *state*.

    Empty account containers are pruned so the file stays tidy.
    """
    key = make_account_key(provider, email)
    accounts = state.get("accounts", {})
    folders = accounts.get(key)
    if not isinstance(folders, dict):
        return state
    if folder in folders:
        del folders[folder]
    if not folders and key in accounts:
        del accounts[key]
    return state
