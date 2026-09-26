#!/usr/bin/env python3
"""itda-email: save_draft.py — IMAP Drafts 폴더에 초안 저장.

SPEC-EMAIL-DRAFTS-001 REQ-DRAFTS-002, REQ-DRAFTS-006, REQ-DRAFTS-007, REQ-DRAFTS-008:
  - IMAP APPEND + \\Draft 플래그 + INTERNALDATE 명시
  - 첨부파일: attachment_validator 통과 후 multipart/mixed 조립
  - APPEND 실패 시 outbox fallback 없음, exit code 1
  - 인증 정보 누락 시 exit code 1
"""
from __future__ import annotations

import argparse
import imaplib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from attachment_validator import validate_attachments  # noqa: E402
from email_compose import build_mime_message  # noqa: E402
from email_providers import get_provider, resolve_provider_name  # noqa: E402
from env_loader import merged_env  # noqa: E402
from _draft_imap import (  # noqa: E402
    PROVIDER_CHOICES,
    connect_drafts,
    fail,
    get_drafts_folder,
    require_credentials,
    safe_logout,
)

# APPENDUID 응답 파싱 패턴: [APPENDUID <validity> <uid>]
_APPENDUID_RE = re.compile(rb"\[APPENDUID\s+\d+\s+(\d+)\]", re.IGNORECASE)

# IMAP 오류 분류 패턴
_AUTH_RE = re.compile(r"AUTHENTICATE|AUTH|LOGIN", re.IGNORECASE)
_QUOTA_RE = re.compile(r"QUOTA|OVER|FULL", re.IGNORECASE)
_REJECT_RE = re.compile(r"NO\s+\[", re.IGNORECASE)


def _classify_error(err: Exception) -> str:
    """IMAP 예외를 분류 키로 매핑한다."""
    msg = str(err)
    if _AUTH_RE.search(msg):
        return "auth_failed"
    if _QUOTA_RE.search(msg):
        return "quota_exceeded"
    if isinstance(err, (ConnectionError, TimeoutError, OSError)):
        return "network_error"
    if _REJECT_RE.search(msg):
        return "server_rejected"
    return "unknown"


def _extract_uid_from_append(resp_data: list) -> int | None:
    """APPEND 응답에서 APPENDUID UID를 추출한다.

    RFC 4315 UIDPLUS capability 응답 형식:
        (OK, [b'[APPENDUID 12345 42]'])
    """
    for item in resp_data:
        if isinstance(item, bytes):
            m = _APPENDUID_RE.search(item)
            if m:
                return int(m.group(1))
    return None


def save_draft(
    provider: str,
    to_addr: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    body_html: str = "",
    attachments: list[str] | None = None,
    account: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """MIME 메시지를 조립하고 IMAP Drafts 폴더에 APPEND 한다.

    반환값:
        {"status": "draft_saved", "uid": <int>, "provider": "<name>", "folder": "<folder>"}

    실패 시 SystemExit(1)을 발생시킨다.
    """
    env = merged_env()
    provider_cfg = get_provider(provider, env, account=account)
    require_credentials(provider_cfg, provider)

    # 첨부파일 유효성 검사 (REQ-DRAFTS-007)
    if attachments:
        violations, warnings = validate_attachments(provider, attachments)
        for w in warnings:
            print(w, file=sys.stderr)
        if violations:
            detail = "; ".join(
                f"파일 '{v['file']}': {v['reason']}" for v in violations
            )
            print(
                json.dumps({
                    "error": "attachment_validation_failed",
                    "detail": detail,
                }),
                file=sys.stderr,
            )
            sys.exit(1)

    # MIME 메시지 조립
    canonical = resolve_provider_name(provider)
    msg = build_mime_message(
        from_addr=provider_cfg["email"],
        to_addr=to_addr,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        body_html=body_html,
        attachments=attachments or [],
        in_reply_to=in_reply_to,
        references=references,
    )

    drafts_folder = get_drafts_folder(canonical)
    flags = "(\\Draft)"
    internal_date = imaplib.Time2Internaldate(time.time())
    raw_bytes = msg.as_bytes()

    imap: imaplib.IMAP4_SSL | None = None
    try:
        # APPEND 경로는 select 불필요 — folder=None 으로 login 까지만 수행
        imap = connect_drafts(provider_cfg)

        # APPEND: flags, INTERNALDATE, 메시지 바이트
        status, resp_data = imap.append(drafts_folder, flags, internal_date, raw_bytes)

        if status != "OK":
            # 서버가 실패 응답을 반환한 경우
            resp_str = (resp_data[0] if resp_data else b"").decode("utf-8", errors="replace")
            error_key = "server_rejected"
            if _QUOTA_RE.search(resp_str):
                error_key = "quota_exceeded"
            print(
                json.dumps({"error": error_key, "detail": resp_str}),
                file=sys.stderr,
            )
            sys.exit(1)

        # UID 추출
        uid = _extract_uid_from_append(resp_data)
        if uid is None:
            # APPENDUID를 지원하지 않는 서버 fallback: UID SEARCH UNSEEN
            imap.select(drafts_folder)
            _s, search_data = imap.uid("SEARCH", None, "ALL")
            if search_data and search_data[0]:
                uid_list = search_data[0].split()
                uid = int(uid_list[-1]) if uid_list else 0
            else:
                uid = 0

        return {
            "status": "draft_saved",
            "uid": uid,
            "provider": canonical,
            "folder": drafts_folder,
        }

    except imaplib.IMAP4.error as e:
        fail(_classify_error(e), str(e))
    except (ConnectionError, TimeoutError, OSError) as e:
        fail("network_error", str(e))
    finally:
        safe_logout(imap)


def main() -> None:
    parser = argparse.ArgumentParser(description="IMAP Drafts 폴더에 초안을 저장합니다.")
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES)
    parser.add_argument("--to", required=True, dest="to_addr")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--cc", default="")
    parser.add_argument("--bcc", default="")
    parser.add_argument("--body-html", default="", dest="body_html")
    parser.add_argument("--attachment", action="append", default=[], metavar="FILE")
    parser.add_argument("--account", default=None)
    # 회신 스레드 헤더 (issue #692): reply_context.py 출력 reply_headers를 그대로 넘기면
    # 임시보관함 초안도 발송 시 같은 대화로 묶인다. send_email.py와 동일한 계약.
    parser.add_argument("--in-reply-to", dest="in_reply_to", default=None,
                        help="회신 대상 Message-ID (reply_context.py의 reply_headers.in_reply_to)")
    parser.add_argument("--references", default=None,
                        help="회신 References 체인 (reply_context.py의 reply_headers.references)")
    args = parser.parse_args()

    result = save_draft(
        provider=args.provider,
        to_addr=args.to_addr,
        subject=args.subject,
        body=args.body,
        cc=args.cc,
        bcc=args.bcc,
        body_html=args.body_html,
        attachments=args.attachment,
        account=args.account,
        in_reply_to=args.in_reply_to,
        references=args.references,
    )
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
