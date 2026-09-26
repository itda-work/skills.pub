#!/usr/bin/env python3
"""itda-email: email_imap_utf7 — RFC 3501 §5.1.3 Modified UTF-7 codec.

Modified UTF-7 differences from standard UTF-7:
- Uses '&' as shift character (not '+')
- Uses ',' instead of '/' in base64 alphabet
- Literal '&' is encoded as '&-'
"""
from __future__ import annotations

import base64
import binascii


def decode_modified_utf7(s: bytes | str) -> str:
    """Decode an IMAP Modified UTF-7 folder name to a UTF-8 string.

    RFC 3501 §5.1.3. Never raises — returns original span on malformed input.

    Args:
        s: Raw folder name from IMAP LIST response (bytes or str).

    Returns:
        Human-readable folder name as str.
    """
    if isinstance(s, bytes):
        try:
            s = s.decode("ascii", errors="replace")
        except Exception:
            return ""

    out: list[str] = []
    i = 0
    length = len(s)

    while i < length:
        ch = s[i]
        if ch != "&":
            out.append(ch)
            i += 1
            continue

        # Find closing '-'
        end = s.find("-", i + 1)
        if end == -1:
            # No closing '-': append rest as-is
            out.append(s[i:])
            break

        chunk = s[i + 1 : end]

        if not chunk:
            # '&-' → literal '&'
            out.append("&")
        else:
            # Replace ',' back to '/' for standard base64, then pad
            b64 = chunk.replace(",", "/")
            pad = (4 - len(b64) % 4) % 4
            b64_padded = b64 + "=" * pad
            try:
                decoded = base64.b64decode(b64_padded).decode("utf-16-be")
                out.append(decoded)
            except (binascii.Error, UnicodeDecodeError, ValueError):
                # Malformed: return the original span
                out.append(s[i : end + 1])

        i = end + 1

    return "".join(out)


def encode_modified_utf7(s: str) -> str:
    """Encode a UTF-8 string to IMAP Modified UTF-7 folder name.

    RFC 3501 §5.1.3.

    Args:
        s: Human-readable folder name.

    Returns:
        Modified UTF-7 encoded string safe for IMAP commands.
    """
    out: list[str] = []
    non_ascii_buf: list[str] = []

    def _flush_non_ascii() -> None:
        if not non_ascii_buf:
            return
        text = "".join(non_ascii_buf)
        utf16 = text.encode("utf-16-be")
        b64 = base64.b64encode(utf16).decode("ascii").replace("/", ",")
        # Strip trailing padding
        b64 = b64.rstrip("=")
        out.append("&" + b64 + "-")
        non_ascii_buf.clear()

    for ch in s:
        code = ord(ch)
        if ch == "&":
            _flush_non_ascii()
            out.append("&-")
        elif 0x20 <= code <= 0x7E:
            _flush_non_ascii()
            out.append(ch)
        else:
            non_ascii_buf.append(ch)

    _flush_non_ascii()
    return "".join(out)
