#!/usr/bin/env python3
"""itda-email: send_email.py — send email via SMTP SSL.

SPEC-EMAIL-RESILIENCE-001:
  REQ-001: TLS context 명시 (ssl.create_default_context())
  REQ-002: 포트별 재시도 + 지수 백오프 (1s, 4s)
  REQ-003: 다중 --to 분리 (쉼표 구분)
  REQ-004: 사전 TCP probe + outbox 저장
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import smtplib
import socket
import ssl
import sys
import time
import uuid
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from attachment_validator import validate_attachments  # noqa: E402
from email_providers import detect_providers, get_provider, resolve_provider_name  # noqa: E402
from env_loader import merged_env  # noqa: E402
from itda_path import resolve_data_dir  # noqa: E402


_TRANSIENT_ERRORS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPConnectError,
    ConnectionError,
    TimeoutError,
    OSError,
)

_BACKOFF_SEQ = (1, 4)


# @MX:NOTE: [AUTO] SMTP 포트 사전 탐색 — sandbox 환경에서 80초+ 타임아웃 방지 (SPEC-EMAIL-RESILIENCE-001 REQ-004)
def _probe_ports(host: str, ports: list[int], timeout: int = 3) -> list[int]:
    open_ports: list[int] = []
    for port in ports:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            open_ports.append(port)
        except OSError:
            pass
    return open_ports


def _sanitize_message_id(message_id: str) -> str:
    result = message_id
    for ch in "<>":
        result = result.replace(ch, "")
    result = result.replace("@", "_")
    return result.strip("_")


# @MX:NOTE: [AUTO] 아웃박스 저장 — meta dict에 password 필드 절대 포함 금지 (REQ-007)
def _save_to_outbox(
    msg,
    provider: dict,
    attempted_ports: list[int],
    reason: str,
) -> dict:
    outbox_dir = resolve_data_dir("email", "outbox")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sanitized_id = _sanitize_message_id(msg.get("Message-ID", str(uuid.uuid4())))
    base_name = f"{ts}_{sanitized_id}"
    eml_path = outbox_dir / f"{base_name}.eml"
    json_path = outbox_dir / f"{base_name}.json"

    eml_content = msg.as_string()

    meta: dict = {
        "provider": provider.get("name", "unknown"),
        "smtp_host": provider.get("smtp_host", ""),
        "from": provider.get("email", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "bcc": "",
        "subject": msg.get("Subject", ""),
        "message_id": msg.get("Message-ID", ""),
        "attempted_ports": attempted_ports,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "transport_intended": provider.get("name", "unknown"),
    }

    try:
        eml_path.write_text(eml_content, encoding="utf-8")
        json_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        return {
            "status": "error",
            "error": "outbox_save_failed",
            "detail": str(e),
            "raw_eml_base64": base64.b64encode(
                eml_content.encode("utf-8", errors="replace")
            ).decode("ascii"),
        }

    return {
        "status": "queued",
        "outbox_path": str(eml_path),
        "message_id": msg.get("Message-ID", ""),
        "reason": reason,
    }


def _send_with_retry(
    send_fn,
    *send_args,
    max_attempts: int = 2,
    backoff_seq: tuple = _BACKOFF_SEQ,
    port_label: str = "465",
) -> None:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            send_fn(*send_args)
            return
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
            raise
        except Exception as e:
            last_exc = e
            delay = backoff_seq[attempt] if attempt < len(backoff_seq) else backoff_seq[-1]
            if attempt < max_attempts - 1:
                print(
                    f"retrying {port_label} (attempt {attempt + 2}/{max_attempts} after {delay}s)...",
                    file=sys.stderr,
                )
            time.sleep(delay)

    assert last_exc is not None
    raise last_exc


# @MX:ANCHOR: [AUTO] SMTP 발송 통합 진입점 — main()과 send_outbox.py 양쪽에서 호출됨
# @MX:REASON: fan_in >= 3; 인터페이스 변경 시 send_outbox.py 동시 갱신 필요
def _send_message(
    provider: dict,
    recipients: list[int],
    msg_str: str,
    force_587: bool = False,
    skip_probe: bool = False,
) -> str:
    host = provider["smtp_host"]
    email = provider["email"]
    password = provider["password"]

    # iCloud 등 smtp_port == 587인 provider는 465 시도 없이 STARTTLS 직행
    if force_587 or provider.get("smtp_port") == 587:
        _send_with_retry(
            _send_via_587, host, email, password, recipients, msg_str,
            port_label="587",
        )
        return "starttls_587_forced" if force_587 else "starttls_587"

    primary_error: Exception | None = None
    try:
        _send_with_retry(
            _send_via_465, host, email, password, recipients, msg_str,
            port_label="465",
        )
        return "smtps_465"
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
        raise
    except Exception as e:
        primary_error = e
        print(
            f"warning: SMTPS(465) all retries failed ({type(e).__name__}: {e}); "
            f"retrying via STARTTLS(587)...",
            file=sys.stderr,
        )

    try:
        _send_with_retry(
            _send_via_587, host, email, password, recipients, msg_str,
            port_label="587",
        )
        return "starttls_587_fallback"
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
        raise
    except Exception as e:
        raise Exception(
            json.dumps({
                "_type": "send_failed_both_ports",
                "detail_465": f"{type(primary_error).__name__}: {primary_error}",
                "detail_587": f"{type(e).__name__}: {e}",
            })
        ) from e


def _send_via_465(host: str, email: str, password: str, recipients: list,
                  msg_str: str) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, 465, timeout=20, context=ctx) as smtp:
        smtp.login(email, password)
        smtp.sendmail(email, recipients, msg_str)


def _send_via_587(host: str, email: str, password: str, recipients: list,
                  msg_str: str) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, 587, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.ehlo()
        smtp.login(email, password)
        smtp.sendmail(email, recipients, msg_str)


def _build_attachment_part(filepath: str) -> MIMEBase:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email via SMTP SSL.")
    parser.add_argument("--provider", required=True, choices=["naver", "google", "gmail", "daum", "icloud", "custom"])
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--cc", default="")
    parser.add_argument("--bcc", default="")
    parser.add_argument("--from-name", dest="from_name", default=None,
                        help="발신자 표시 이름 (From 헤더 display name). 예: '현우테크 김민수'. 미지정 시 계정 이메일만 표시.")
    parser.add_argument("--in-reply-to", dest="in_reply_to", default=None,
                        help="회신 대상 Message-ID (reply_context.py의 reply_headers.in_reply_to)")
    parser.add_argument("--references", default=None,
                        help="회신 References 체인 (reply_context.py의 reply_headers.references)")
    parser.add_argument("--account", default=None)
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--attach", action="append", default=[], metavar="FILE")
    parser.add_argument("--force-587", action="store_true")
    parser.add_argument("--skip-probe", action="store_true",
                        help="사전 TCP probe를 건너뛰고 바로 SMTP 시도.")
    parser.add_argument("--save-as-draft", action="store_true", dest="save_as_draft",
                        help="SMTP 발송 대신 IMAP Drafts에 초안으로 저장합니다.")
    args = parser.parse_args()

    env = merged_env()
    provider = get_provider(args.provider, env, account=args.account)
    if not provider or not provider.get("email") or not provider.get("password"):
        all_providers = detect_providers(env)
        canonical = resolve_provider_name(args.provider)
        matching = next((p for p in all_providers if p["provider"] == canonical), None)
        if matching and len(matching["accounts"]) > 1 and args.account is None:
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

    if args.attach:
        violations, warnings = validate_attachments(args.provider, args.attach)
        for w in warnings:
            print(w, file=sys.stderr)
        if violations:
            detail = "; ".join(
                f"파일 '{v['file']}': {v['reason']}" for v in violations
            )
            print(json.dumps({
                "status": "error",
                "error": "attachment_validation_failed",
                "detail": detail,
                "violations": violations,
            }))
            sys.exit(1)

    # REQ-003: 다중 --to 분리
    to_list = [a.strip() for a in args.to.split(",") if a.strip()]
    if not to_list:
        print(json.dumps({
            "status": "error",
            "error": "invalid_recipient",
            "detail": "no valid 'to' addresses",
        }))
        sys.exit(1)

    mime_type = "html" if args.html else "plain"

    if args.attach:
        msg = MIMEMultipart("mixed")
        msg.attach(MIMEText(args.body, mime_type, "utf-8"))
        for fp in args.attach:
            msg.attach(_build_attachment_part(fp))
    else:
        msg = MIMEText(args.body, mime_type, "utf-8")

    msg["From"] = formataddr((args.from_name, provider["email"])) if args.from_name else provider["email"]
    msg["To"] = args.to  # 원본 문자열 유지 (RFC 5322)
    msg["Subject"] = args.subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = f"<{uuid.uuid4()}@itda-email>"
    # 회신 스레드 헤더 (SPEC-EMAIL-REPLY-CONTEXT-001): 받는 클라이언트가 같은
    # 대화로 묶도록 한다. reply_context.py 출력의 reply_headers를 그대로 넘긴다.
    if args.in_reply_to:
        msg["In-Reply-To"] = args.in_reply_to
    if args.references:
        msg["References"] = args.references
    if args.cc:
        msg["Cc"] = args.cc

    recipients = list(to_list)
    if args.cc:
        recipients += [a.strip() for a in args.cc.split(",") if a.strip()]
    if args.bcc:
        recipients += [a.strip() for a in args.bcc.split(",") if a.strip()]

    msg_str = msg.as_string()

    # REQ-DRAFTS-005: --save-as-draft 플래그 처리 — SMTP 발송 건너뛰고 Drafts에 저장
    if args.save_as_draft:
        from save_draft import save_draft as _save_draft  # noqa: PLC0415 (지연 import)
        result = _save_draft(
            provider=args.provider,
            to_addr=args.to,
            subject=args.subject,
            body=args.body,
            cc=args.cc,
            bcc=args.bcc,
            attachments=args.attach if args.attach else [],
            account=args.account,
        )
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    # REQ-004: 사전 TCP probe
    if not args.skip_probe:
        probe_ports = [587] if args.force_587 else [465, 587]
        open_ports = _probe_ports(provider["smtp_host"], probe_ports)
        if not open_ports:
            result = _save_to_outbox(msg, provider, probe_ports, "probe_blocked")
            print(json.dumps(result))
            sys.exit(0)

    try:
        transport_used = _send_message(
            provider, recipients, msg_str,
            force_587=args.force_587,
        )
    except smtplib.SMTPAuthenticationError as e:
        print(json.dumps({"status": "error", "error": "auth_failed", "detail": str(e)}))
        sys.exit(1)
    except smtplib.SMTPRecipientsRefused as e:
        print(json.dumps({"status": "error", "error": "invalid_recipient", "detail": str(e)}))
        sys.exit(1)
    except Exception as e:
        err_str = str(e)
        try:
            err_data = json.loads(err_str)
            if err_data.get("_type") == "send_failed_both_ports":
                attempted = [587] if args.force_587 else [465, 587]
                result = _save_to_outbox(msg, provider, attempted, "send_failed_all_attempts")
                print(json.dumps(result))
                sys.exit(0 if result["status"] == "queued" else 1)
        except (json.JSONDecodeError, KeyError):
            pass

        if args.force_587:
            print(json.dumps({
                "status": "error",
                "error": "send_failed_forced_587",
                "detail": f"{type(e).__name__}: {e}",
                "hint": (
                    f"`python3 scripts/diagnose_smtp.py --provider {args.provider}` "
                    "로 어느 레이어에서 실패했는지 확인하세요."
                ),
            }))
        else:
            print(json.dumps({
                "status": "error",
                "error": "send_failed",
                "detail": str(e),
                "hint": (
                    f"`python3 scripts/diagnose_smtp.py --provider {args.provider}` "
                    "로 어느 레이어에서 실패했는지 확인하세요."
                ),
            }))
        sys.exit(1)

    print(json.dumps({
        "status": "ok",
        "message_id": msg["Message-ID"],
        "to": args.to,
        "subject": args.subject,
        "transport": transport_used,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
