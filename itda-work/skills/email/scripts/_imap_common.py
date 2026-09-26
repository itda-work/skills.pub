#!/usr/bin/env python3
"""itda-email: _imap_common.py — shared IMAP helpers for mail management scripts.

Shared by move_email.py / manage_folder.py / mark_spam.py / trash_email.py /
flag_email.py. Owns three contracts that must stay identical to the Go
implementation (issue #1512 track B — do not change unilaterally):

1. Canonical Trash/Junk resolution: SPECIAL-USE (\\Trash / \\Junk) from IMAP
   LIST first; fallback table per provider when the server does not advertise
   SPECIAL-USE; custom provider has no fallback → ``canonical_folder_unresolved``.
2. MOVE with fallback: UID MOVE when CAPABILITY has MOVE; otherwise
   COPY → \\Deleted → UID EXPUNGE, and the fallback is refused with
   ``uidplus_unsupported`` when UIDPLUS is absent (a plain EXPUNGE would
   collateral-expunge unrelated \\Deleted messages).
3. Error keys: folder_not_empty / canonical_folder_protected /
   canonical_folder_unresolved / uidplus_unsupported.
"""
from __future__ import annotations

import email
import imaplib
import json
import re
import sys
from email.header import decode_header
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from email_imap_utf7 import decode_modified_utf7, encode_modified_utf7  # noqa: E402
from email_providers import detect_providers, get_provider, resolve_provider_name  # noqa: E402
from email_security import sanitize_for_llm  # noqa: E402
from env_loader import merged_env  # noqa: E402

# Fallback table when the server does not advertise SPECIAL-USE.
# Shared contract with track B (Go) — keep byte-identical.
# ⚠️ Gmail/daum folder names are locale-dependent (live 2026-08-20: Korean-locale
# Gmail advertises "[Gmail]/휴지통"/"[Gmail]/스팸함", daum trash is "Deleted Messages"
# via SPECIAL-USE). SPECIAL-USE detection is authoritative; this table is a last
# resort for servers that advertise neither — do not trust it as ground truth.
TRASH_FALLBACK = {
    "google": "[Gmail]/Trash",
    "naver": "Deleted Messages",
    "daum": "휴지통",
    "icloud": "Deleted Messages",
}
JUNK_FALLBACK = {
    "google": "[Gmail]/Spam",
    "naver": "Junk",
    "daum": "스팸편지함",
    "icloud": "Junk",
}

PROVIDER_CHOICES = ["naver", "google", "gmail", "daum", "icloud", "custom"]

# Canonical folder roles that manage_folder must never rename/delete.
_CANONICAL_SPECIAL_FLAGS = {"\\sent", "\\drafts", "\\trash", "\\junk"}
_CANONICAL_LITERAL_NAMES = {"inbox", "sent", "drafts", "trash", "junk"}

_AUTH_FAILED_RE = re.compile(r"AUTHENTICATION", re.IGNORECASE)

# Same LIST parsing contract as list_folders.py.
_LIST_RE = re.compile(
    rb'\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>[^"]*)"|(?P<nil_delim>NIL))\s+"?(?P<name>[^"]*)"?$',
    re.IGNORECASE,
)

_COPYUID_RE = re.compile(r"\[COPYUID\s+\d+\s+([0-9,:]+)\s+([0-9,:]+)\]")

# Safety cap when expanding COPYUID ranges (a:b) into explicit UID lists.
_MAX_UID_EXPANSION = 10000


class ImapOpError(Exception):
    """Structured operation error carrying a stable error key."""

    def __init__(self, key: str, detail: str | None = None) -> None:
        super().__init__(detail or key)
        self.key = key
        self.detail = detail


def emit_error(key: str, detail: str | None = None, *, extra: dict | None = None) -> None:
    """Print a JSON error to stdout and exit 1."""
    payload: dict = {"status": "error", "error": key}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


def parse_uids(raw: str) -> list[str]:
    """Parse a comma-separated UID argument ("5,6,7") into a validated list.

    Raises:
        ImapOpError("invalid_uid") on empty / non-numeric input.
    """
    uids: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ImapOpError("invalid_uid", f"UID must be numeric: {part!r}")
        if part not in seen:
            seen.add(part)
            uids.append(part)
    if not uids:
        raise ImapOpError("invalid_uid", "no UID given")
    return uids


def quote_folder(enc: str) -> str:
    """Quote a Modified-UTF-7-encoded folder name for IMAP commands."""
    return '"' + enc.replace("\\", "\\\\").replace('"', '\\"') + '"'


def encode_and_quote(name: str) -> str:
    return quote_folder(encode_modified_utf7(name))


def connect(provider_name: str, account: str | None) -> tuple[imaplib.IMAP4_SSL, dict]:
    """Resolve credentials and open an authenticated IMAP session.

    Exits the process with the same JSON/exit-code contract as
    list_folders.py (0 handled by caller, 1 = error, 2 = ambiguous account).
    """
    env = merged_env()
    provider = get_provider(provider_name, env, account=account)

    if not provider or not provider.get("email") or not provider.get("password"):
        all_providers = detect_providers(env)
        canonical = resolve_provider_name(provider_name)
        matching = next((p for p in all_providers if p["provider"] == canonical), None)
        if matching and len(matching["accounts"]) > 1 and account is None:
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
        emit_error("auth_failed" if _AUTH_FAILED_RE.search(str(e)) else "imap_error", str(e))
    except OSError as e:
        emit_error("connection_failed", str(e))

    try:
        imap.login(provider["email"], provider["password"])
    except imaplib.IMAP4.error as e:
        emit_error("auth_failed" if _AUTH_FAILED_RE.search(str(e)) else "imap_error", str(e))

    return imap, provider


def capabilities(imap: imaplib.IMAP4) -> set[str]:
    """Live post-auth CAPABILITY — never the imaplib pre-auth cache.

    imaplib's ``.capabilities`` attribute is captured at connect time
    (pre-auth). iCloud·Gmail advertise MOVE/UIDPLUS only **after** login, so
    reading the cache misclassifies them as unsupported and every move gets
    refused with ``uidplus_unsupported`` (#1512 live finding 2). This issues a
    fresh ``CAPABILITY`` command (callers run post-login) and caches the result
    on the connection. On command failure we fall back to the attribute cache
    (best effort) rather than crashing.
    """
    cached = getattr(imap, "_itda_live_caps", None)
    if isinstance(cached, set):
        return cached

    raw: tuple | list = ()
    try:
        typ, data = imap.capability()
        if typ == "OK" and data and data[0]:
            first = data[0]
            if isinstance(first, bytes):
                first = first.decode("ascii", errors="replace")
            raw = first.split()
    except Exception:
        raw = ()
    if not raw:
        raw = getattr(imap, "capabilities", None) or ()

    out: set[str] = set()
    for c in raw:
        if isinstance(c, bytes):
            c = c.decode("ascii", errors="replace")
        out.add(c.upper())
    imap._itda_live_caps = out
    return out


def list_folder_entries(imap: imaplib.IMAP4) -> list[dict]:
    """Return LIST entries: [{"name", "flags", "name_enc"}]."""
    typ, raw_lines = imap.list()
    if typ != "OK":
        raise ImapOpError("imap_error", "LIST command returned non-OK status")
    entries: list[dict] = []
    for raw in raw_lines or []:
        if not raw or not isinstance(raw, bytes):
            continue
        m = _LIST_RE.match(raw.strip())
        if not m:
            continue
        flags_str = m.group("flags").decode("ascii", errors="replace")
        flags = [f.strip() for f in flags_str.split() if f.strip()]
        name_enc = m.group("name")
        entries.append({
            "name": decode_modified_utf7(name_enc),
            "flags": flags,
            "name_enc": name_enc,
        })
    return entries


def resolve_canonical(imap: imaplib.IMAP4, provider_name: str, kind: str) -> str:
    """Resolve the canonical Trash/Junk folder (decoded, human-readable name).

    ① SPECIAL-USE attribute (\\Trash / \\Junk) from LIST wins.
    ② Fallback table per provider; custom has no fallback →
       ImapOpError("canonical_folder_unresolved").
    """
    assert kind in ("trash", "junk")
    want = "\\" + kind
    try:
        for entry in list_folder_entries(imap):
            if any(f.lower() == want for f in entry["flags"]):
                return entry["name"]
    except (imaplib.IMAP4.error, ImapOpError):
        pass  # fall through to the fallback table

    canonical = resolve_provider_name(provider_name)
    table = TRASH_FALLBACK if kind == "trash" else JUNK_FALLBACK
    name = table.get(canonical)
    if not name:
        raise ImapOpError(
            "canonical_folder_unresolved",
            f"SPECIAL-USE not advertised and no fallback for provider {canonical!r} ({kind})",
        )
    return name


def canonical_protected_names(imap: imaplib.IMAP4, provider_name: str) -> set[str]:
    """Set of lowercase folder names protected from rename/delete."""
    names = set(_CANONICAL_LITERAL_NAMES)
    canonical = resolve_provider_name(provider_name)
    for table in (TRASH_FALLBACK, JUNK_FALLBACK):
        if canonical in table:
            names.add(table[canonical].lower())
    try:
        for entry in list_folder_entries(imap):
            if any(f.lower() in _CANONICAL_SPECIAL_FLAGS for f in entry["flags"]):
                names.add(entry["name"].lower())
    except (imaplib.IMAP4.error, ImapOpError):
        pass
    return names


def select_folder(imap: imaplib.IMAP4, name: str, *, readonly: bool = False) -> int:
    """SELECT a folder (human-readable name). Returns the message count."""
    typ, data = imap.select(encode_and_quote(name), readonly=readonly)
    if typ != "OK":
        detail = ""
        if data and data[0]:
            d = data[0]
            detail = d.decode("ascii", errors="replace") if isinstance(d, bytes) else str(d)
        raise ImapOpError("folder_select_failed", f"cannot select {name!r}: {detail}")
    try:
        return int(data[0])
    except (TypeError, ValueError, IndexError):
        return 0


def _expand_uid_set(spec: str) -> list[int] | None:
    """Expand an IMAP uid-set ("10:12,15") into explicit ints. None if malformed."""
    out: list[int] = []
    for part in spec.split(","):
        if ":" in part:
            try:
                lo, hi = (int(x) for x in part.split(":", 1))
            except ValueError:
                return None
            if hi < lo or hi - lo + 1 > _MAX_UID_EXPANSION:
                return None
            out.extend(range(lo, hi + 1))
        else:
            if not part.isdigit():
                return None
            out.append(int(part))
        if len(out) > _MAX_UID_EXPANSION:
            return None
    return out


def parse_copyuid(data: list) -> list[int] | None:
    """Extract new destination UIDs from a COPYUID response. None when absent/malformed."""
    parts: list[str] = []
    for item in data or []:
        if isinstance(item, bytes):
            parts.append(item.decode("ascii", errors="replace"))
        elif isinstance(item, str):
            parts.append(item)
    m = _COPYUID_RE.search(" ".join(parts))
    if not m:
        return None
    return _expand_uid_set(m.group(2))


def move_uids(imap: imaplib.IMAP4, uids: list[str], to_folder: str) -> tuple[str, list[int] | None]:
    """Move UIDs (in the currently selected folder) to ``to_folder``.

    Returns (method, new_uids) where method is "move" | "copy_expunge".
    Contract: UID MOVE when CAPABILITY has MOVE; otherwise the COPY fallback is
    refused up-front when UIDPLUS is absent (uidplus_unsupported) — a plain
    EXPUNGE would destroy unrelated \\Deleted messages.
    """
    caps = capabilities(imap)
    uid_set = ",".join(uids)
    dest = encode_and_quote(to_folder)

    if "MOVE" in caps:
        typ, data = imap.uid("MOVE", uid_set, dest)
        if typ != "OK":
            raise ImapOpError("move_failed", f"UID MOVE returned {typ}")
        return "move", parse_copyuid(data)

    if "UIDPLUS" not in caps:
        raise ImapOpError(
            "uidplus_unsupported",
            "server lacks both MOVE and UIDPLUS — COPY fallback refused "
            "(plain EXPUNGE would remove unrelated \\Deleted messages)",
        )

    typ, data = imap.uid("COPY", uid_set, dest)
    if typ != "OK":
        raise ImapOpError("move_failed", f"UID COPY returned {typ}")
    new_uids = parse_copyuid(data)

    typ, _ = imap.uid("STORE", uid_set, "+FLAGS", r"(\Deleted)")
    if typ != "OK":
        raise ImapOpError("move_failed", "STORE +FLAGS \\Deleted failed after COPY")
    typ, _ = imap.uid("EXPUNGE", uid_set)
    if typ != "OK":
        raise ImapOpError("move_failed", "UID EXPUNGE failed after COPY")
    return "copy_expunge", new_uids


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        out: list[str] = []
        for chunk, enc in decode_header(raw):
            if isinstance(chunk, bytes):
                out.append(chunk.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(chunk)
        return "".join(out)
    except Exception:
        return raw


def fetch_meta(imap: imaplib.IMAP4, uids: list[str]) -> list[dict]:
    """Fetch {"uid","from","subject","date"} per UID (BODY.PEEK — no \\Seen).

    Returns entries **only for UIDs whose FETCH actually returned data** — a
    missing UID yields no row. Never fabricate an empty-meta row for an absent
    UID: the IMAP server answers ``OK`` with an empty payload for a FETCH on a
    nonexistent UID, and a fabricated row would let a later no-op STORE/EXPUNGE
    forge success (#1512 live finding).
    """
    messages: list[dict] = []
    for uid in uids:
        try:
            typ, data = imap.uid(
                "FETCH", uid, "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
            )
        except imaplib.IMAP4.error:
            continue  # unverifiable → treated as missing (caller decides)
        if typ != "OK" or not data:
            continue
        raw_header = b""
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                raw_header = item[1]
                break
        if not raw_header:
            continue
        msg = email.message_from_bytes(raw_header)
        messages.append({
            "uid": int(uid),
            "from": sanitize_for_llm(_decode_header_value(msg.get("From")), max_len=200),
            "subject": sanitize_for_llm(_decode_header_value(msg.get("Subject")), max_len=300),
            "date": sanitize_for_llm(msg.get("Date") or "", max_len=100),
        })
    return messages


def require_uids_exist(imap: imaplib.IMAP4, uids: list[str], folder_name: str) -> list[dict]:
    """Verify every requested UID exists in the selected folder; return meta.

    Raises ImapOpError("uid_not_found") listing the missing UIDs and the folder
    name when any UID is absent — no partial success, and callers must invoke
    this **before issuing any write command**. Shared contract with track B (Go).
    """
    messages = fetch_meta(imap, uids)
    found = {str(m["uid"]) for m in messages}
    missing = [u for u in uids if u not in found]
    if missing:
        raise ImapOpError(
            "uid_not_found",
            f"UID(s) not found in folder {folder_name!r}: {', '.join(missing)} "
            "— 대상 메일이 이 폴더에 없습니다(다른 폴더에 있을 수 있음)",
        )
    return messages


def logout_quiet(imap: imaplib.IMAP4) -> None:
    try:
        imap.logout()
    except Exception:
        pass
