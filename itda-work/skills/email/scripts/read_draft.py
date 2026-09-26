#!/usr/bin/env python3
"""itda-email: read_draft.py — IMAP Drafts 폴더에서 초안 본문 조회.

SPEC-EMAIL-DRAFTS-001 REQ-DRAFTS-001:
  - UID로 본문(text/plain, text/html, 첨부 메타) 조회
  - UID 없으면 exit code 1, stderr에 uid_not_found
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from email_providers import get_provider  # noqa: E402
from env_loader import merged_env  # noqa: E402
from _draft_imap import (  # noqa: E402
    PROVIDER_CHOICES,
    connect_drafts,
    decode_header,
    fail,
    fail_uid_not_found,
    fetch_message,
    get_drafts_folder,
    require_credentials,
    safe_logout,
)


def _extract_body_and_attachments(msg: email.message.Message) -> tuple[str, str | None, list[dict]]:
    """MIME 메시지에서 본문(text), HTML 본문, 첨부파일 메타를 추출한다."""
    body_text = ""
    body_html: str | None = None
    attachments: list[dict] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get("Content-Disposition", "")
            filename = part.get_filename()

            if filename or "attachment" in disposition.lower():
                # 첨부파일 메타데이터
                payload = part.get_payload(decode=True)
                size = len(payload) if isinstance(payload, bytes) else 0
                attachments.append({
                    "filename": filename or "unknown",
                    "size": size,
                    "content_type": content_type,
                })
            elif content_type == "text/plain" and not body_text:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and body_html is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    body_html = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                body_html = decoded
            else:
                body_text = decoded

    return body_text, body_html, attachments


def read_draft(
    provider: str,
    uid: int,
    account: str | None = None,
) -> dict:
    """UID로 Drafts 폴더에서 초안 본문을 조회한다.

    반환값:
        uid, subject, from, to, cc, bcc, date, body_text, body_html, attachments

    UID가 없으면 SystemExit(1)을 발생시킨다.
    """
    env = merged_env()
    provider_cfg = get_provider(provider, env, account=account)
    require_credentials(provider_cfg, provider)

    drafts_folder = get_drafts_folder(provider)

    imap: imaplib.IMAP4_SSL | None = None
    try:
        imap = connect_drafts(provider_cfg, drafts_folder, readonly=True)

        raw_bytes = fetch_message(imap, uid)
        if raw_bytes is None:
            fail_uid_not_found(uid)

        msg = email.message_from_bytes(raw_bytes)

        subject = decode_header(msg.get("Subject", ""))
        from_ = decode_header(msg.get("From", ""))
        to_raw = msg.get("To", "")
        to_list = [a.strip() for a in to_raw.split(",") if a.strip()]
        cc_raw = msg.get("Cc", "")
        cc_list = [a.strip() for a in cc_raw.split(",") if a.strip()]
        bcc_raw = msg.get("Bcc", "")
        bcc_list = [a.strip() for a in bcc_raw.split(",") if a.strip()]
        date_str = msg.get("Date", "")

        body_text, body_html, attachments = _extract_body_and_attachments(msg)

        return {
            "uid": uid,
            "subject": subject,
            "from": from_,
            "to": to_list,
            "cc": cc_list,
            "bcc": bcc_list,
            "date": date_str,
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
        }

    except imaplib.IMAP4.error as e:
        fail("auth_failed", str(e))
    except (ConnectionError, TimeoutError, OSError) as e:
        fail("network_error", str(e))
    finally:
        safe_logout(imap)


def main() -> None:
    parser = argparse.ArgumentParser(description="IMAP Drafts 폴더에서 초안 본문을 조회합니다.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--uid", required=True, type=int)
    parser.add_argument("--account", default=None)
    args = parser.parse_args()

    result = read_draft(
        provider=args.provider,
        uid=args.uid,
        account=args.account,
    )
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
