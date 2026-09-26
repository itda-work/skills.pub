#!/usr/bin/env python3
"""itda-email: check_connection.py — test SMTP/IMAP connectivity."""
from __future__ import annotations

import argparse
import imaplib
import json
import smtplib
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_providers import detect_providers, get_provider, resolve_provider_name  # noqa: E402
from env_loader import merged_env  # noqa: E402

TIMEOUT = 10


def test_smtp(host: str, port: int, email: str, password: str) -> dict:
    """Test SMTP connection. port=587 → STARTTLS, else → SMTP_SSL."""
    try:
        if port == 587:
            # iCloud 등: STARTTLS 직행 (465 SSL 시도 금지)
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=TIMEOUT) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ctx)
                smtp.ehlo()
                smtp.login(email, password)
            return {"status": "ok", "host": host, "port": port, "transport": "starttls_587"}
        with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT) as smtp:
            smtp.login(email, password)
        return {"status": "ok", "host": host, "port": port, "transport": "smtps_465"}
    except TimeoutError as e:
        return {
            "status": "error", "error": "timeout", "detail": str(e),
            "hint": "Run `python3 scripts/diagnose_smtp.py --provider <name>` for layered diagnosis.",
        }
    except smtplib.SMTPAuthenticationError as e:
        return {"status": "error", "error": "auth_failed", "detail": str(e)}
    except Exception as e:
        return {
            "status": "error", "error": "connection_failed", "detail": str(e),
            "hint": "Run `python3 scripts/diagnose_smtp.py --provider <name>` for layered diagnosis.",
        }


def test_imap(host: str, port: int, email: str, password: str) -> dict:
    """Test IMAP SSL connection. Returns status dict."""
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.socket().settimeout(TIMEOUT)
        imap.login(email, password)
        imap.logout()
        return {"status": "ok", "host": host, "port": port}
    except TimeoutError as e:
        return {"status": "error", "error": "timeout", "detail": str(e)}
    except imaplib.IMAP4.error as e:
        return {"status": "error", "error": "auth_failed", "detail": str(e)}
    except Exception as e:
        return {"status": "error", "error": "connection_failed", "detail": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test email server connectivity.")
    parser.add_argument("--provider", required=True, choices=["naver", "google", "gmail", "daum", "icloud", "custom"])
    parser.add_argument("--account", default=None,
                        help="Account suffix (default, work, personal, 1, 2, ...)")
    args = parser.parse_args()

    env = merged_env()
    provider = get_provider(args.provider, env, account=args.account)
    if not provider:
        # Check if failure is due to ambiguous multi-account selection (AC-04, FR-05 rule #3)
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
        print(json.dumps({"status": "error", "error": "provider_not_found"}))
        sys.exit(1)

    if not provider.get("email") or not provider.get("password"):
        print(json.dumps({"status": "error", "error": "credentials_missing"}))
        sys.exit(1)

    result: dict = {"provider": args.provider}
    smtp_result = test_smtp(
        provider["smtp_host"], provider["smtp_port"], provider["email"], provider["password"]
    )
    result["smtp"] = smtp_result

    if "read" in provider.get("capabilities", []) and provider.get("imap_host"):
        imap_result = test_imap(
            provider["imap_host"], provider["imap_port"], provider["email"], provider["password"]
        )
        result["imap"] = imap_result

    overall_ok = smtp_result["status"] == "ok" and result.get("imap", {}).get("status", "ok") == "ok"
    result["status"] = "ok" if overall_ok else "error"

    print(json.dumps(result, indent=2))
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
