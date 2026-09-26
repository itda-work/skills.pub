#!/usr/bin/env python3
"""itda-email: send_draft.py — Drafts의 초안을 SMTP로 발송.

SPEC-EMAIL-DRAFTS-001 REQ-DRAFTS-003, REQ-DRAFTS-004, REQ-DRAFTS-005:
  - UID FETCH → SMTP 발송 → EXPUNGE (기본)
  - --keep: EXPUNGE 건너뜀
  - --dry-run: SMTP/EXPUNGE 없이 preview JSON 반환
  - UID 없음: exit code 1, stderr uid_not_found
  - SMTP 실패: EXPUNGE 안 함, exit code 1
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import smtplib
import ssl
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


def _send_via_smtp(
    provider_cfg: dict,
    recipients: list[str],
    raw_message: bytes,
) -> None:
    """SMTP 발송: smtp_port==587 → STARTTLS 직행, 그 외 → SSL(465) 후 587 fallback."""
    host = provider_cfg["smtp_host"]
    email_addr = provider_cfg["email"]
    password = provider_cfg["password"]
    smtp_port = provider_cfg.get("smtp_port", 465)
    ctx = ssl.create_default_context()

    # iCloud 등 smtp_port == 587인 provider는 465 시도 없이 STARTTLS 직행
    if smtp_port == 587:
        with smtplib.SMTP(host, 587, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(email_addr, password)
            smtp.sendmail(email_addr, recipients, raw_message)
        return

    try:
        with smtplib.SMTP_SSL(host, 465, timeout=20, context=ctx) as smtp:
            smtp.login(email_addr, password)
            smtp.sendmail(email_addr, recipients, raw_message)
        return
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
        raise
    except Exception:
        pass  # 465 실패 시 587 시도

    with smtplib.SMTP(host, 587, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.ehlo()
        smtp.login(email_addr, password)
        smtp.sendmail(email_addr, recipients, raw_message)


def send_draft(
    provider: str,
    uid: int,
    keep: bool = False,
    dry_run: bool = False,
    account: str | None = None,
) -> dict:
    """Drafts 폴더의 초안을 SMTP로 발송하고 결과를 반환한다.

    반환값:
        성공: {"status": "sent", "uid": N, "expunged": bool}
        dry-run: {"status": "dry_run", "uid": N, "preview": {...}}

    오류 시 SystemExit(1)을 발생시킨다.
    """
    env = merged_env()
    provider_cfg = get_provider(provider, env, account=account)
    require_credentials(provider_cfg, provider)

    drafts_folder = get_drafts_folder(provider)

    imap: imaplib.IMAP4_SSL | None = None
    try:
        imap = connect_drafts(provider_cfg, drafts_folder)

        raw_bytes = fetch_message(imap, uid)
        if raw_bytes is None:
            fail_uid_not_found(uid)

        # MIME 파싱
        msg = email.message_from_bytes(raw_bytes)
        subject = decode_header(msg.get("Subject", ""))
        to_raw = msg.get("To", "")
        cc_raw = msg.get("Cc", "")
        bcc_raw = msg.get("Bcc", "")

        recipients: list[str] = []
        for addr_field in (to_raw, cc_raw, bcc_raw):
            recipients += [a.strip() for a in addr_field.split(",") if a.strip()]

        if dry_run:
            # 본문 앞 200자 미리보기
            body_preview = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            charset = part.get_content_charset() or "utf-8"
                            body_preview = payload.decode(charset, errors="replace")[:200]
                            break
            else:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = msg.get_content_charset() or "utf-8"
                    body_preview = payload.decode(charset, errors="replace")[:200]

            attachments_preview = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_filename():
                        attachments_preview.append(part.get_filename())

            return {
                "status": "dry_run",
                "uid": uid,
                "preview": {
                    "to": to_raw,
                    "cc": cc_raw,
                    "bcc": bcc_raw,
                    "subject": subject,
                    "body_preview": body_preview,
                    "attachments": attachments_preview,
                },
            }

        # SMTP 발송
        try:
            _send_via_smtp(provider_cfg, recipients, raw_bytes)
        except smtplib.SMTPAuthenticationError as e:
            print(json.dumps({"error": "auth_failed", "detail": str(e)}), file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": "smtp_failed", "detail": str(e)}), file=sys.stderr)
            sys.exit(1)

        # 발송 성공 후 EXPUNGE (--keep 없을 때)
        expunged = False
        if not keep:
            imap.uid("STORE", str(uid).encode(), "+FLAGS", "(\\Deleted)")
            imap.uid("EXPUNGE", str(uid).encode())
            expunged = True

        return {
            "status": "sent",
            "uid": uid,
            "expunged": expunged,
        }

    except imaplib.IMAP4.error as e:
        fail("auth_failed", str(e))
    except (ConnectionError, TimeoutError, OSError) as e:
        fail("network_error", str(e))
    finally:
        safe_logout(imap)


def main() -> None:
    parser = argparse.ArgumentParser(description="Drafts 초안을 SMTP로 발송합니다.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--uid", required=True, type=int)
    parser.add_argument("--keep", action="store_true", help="발송 후 초안을 Drafts에 보존합니다.")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="SMTP/EXPUNGE 없이 MIME 파싱 결과만 출력합니다.")
    parser.add_argument("--account", default=None)
    args = parser.parse_args()

    result = send_draft(
        provider=args.provider,
        uid=args.uid,
        keep=args.keep,
        dry_run=args.dry_run,
        account=args.account,
    )
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
