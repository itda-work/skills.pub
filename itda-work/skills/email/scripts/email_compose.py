#!/usr/bin/env python3
"""itda-email: email_compose.py — MIME 메시지 조립 헬퍼.

SPEC-EMAIL-DRAFTS-001 구현 지원:
  - send_email.py 기존 MIME 조립 로직을 모듈로 추출
  - save_draft.py, send_draft.py에서 import하여 중복 없이 재사용
"""
from __future__ import annotations

import mimetypes
import uuid
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path


# @MX:ANCHOR: [AUTO] MIME 메시지 조립 통합 진입점 — save_draft.py, send_draft.py, send_email.py에서 호출됨
# @MX:REASON: fan_in >= 3; 인터페이스 변경 시 모든 호출 사이트 동시 갱신 필요


def build_attachment_part(filepath: str) -> MIMEBase:
    """파일 경로로부터 첨부파일 MIME 파트를 조립한다.

    send_email.py의 _build_attachment_part와 동일한 로직을 공유한다.
    """
    path = Path(filepath)
    mime_guess, _ = mimetypes.guess_type(filepath)
    if mime_guess:
        maintype, subtype = mime_guess.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    part = MIMEBase(maintype, subtype)
    with open(filepath, "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=("utf-8", "", path.name),
    )
    return part


def build_mime_message(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    body_html: str = "",
    attachments: list[str] | None = None,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> MIMEMultipart | MIMEText:
    """MIME 메시지를 조립하여 반환한다.

    첨부파일이 있으면 multipart/mixed, HTML 본문만 있으면 multipart/alternative,
    텍스트만 있으면 MIMEText로 조립한다.
    """
    attachments = attachments or []
    msg_id = message_id or f"<{uuid.uuid4()}@itda-email>"

    if attachments:
        # multipart/mixed: 텍스트(또는 alternative) + 첨부파일
        msg = MIMEMultipart("mixed")

        if body_html:
            # 텍스트+HTML을 alternative로 묶어 mixed에 첨부
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body, "plain", "utf-8"))
            alt_part.attach(MIMEText(body_html, "html", "utf-8"))
            msg.attach(alt_part)
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        for fp in attachments:
            msg.attach(build_attachment_part(fp))

    elif body_html:
        # 첨부 없이 HTML: multipart/alternative
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    else:
        # 순수 텍스트
        msg = MIMEText(body, "plain", "utf-8")

    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = msg_id
    # 회신 스레드 헤더 (SPEC-EMAIL-REPLY-CONTEXT-001): 받는 클라이언트가 같은
    # 대화로 묶도록 함. reply_context.py 출력의 reply_headers를 그대로 넘긴다.
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    if cc:
        msg["Cc"] = cc
    # BCC는 헤더에 포함하지 않고 SMTP sendmail 인자로만 사용됨

    return msg
