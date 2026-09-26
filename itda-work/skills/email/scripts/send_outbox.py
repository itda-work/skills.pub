#!/usr/bin/env python3
"""itda-email: send_outbox.py — outbox 재발송 CLI.

SPEC-EMAIL-RESILIENCE-001 REQ-EMAIL-RES-005.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_providers import get_provider  # noqa: E402
from env_loader import merged_env  # noqa: E402
from itda_path import resolve_data_dir  # noqa: E402
from send_email import _send_message  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Resend queued messages from outbox.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, metavar="N")
    parser.add_argument("--purge-on-success", action="store_true")
    args = parser.parse_args()

    outbox_dir = resolve_data_dir("email", "outbox")
    sent_dir = outbox_dir / "sent"

    eml_files = sorted(outbox_dir.glob("*.eml"), key=lambda p: p.stat().st_mtime)
    if args.limit is not None:
        eml_files = eml_files[: args.limit]

    items = []

    if args.dry_run:
        for eml_path in eml_files:
            items.append({"file": str(eml_path), "status": "pending"})
        print(json.dumps({
            "status": "ok",
            "processed": len(items),
            "sent": 0,
            "failed": 0,
            "items": items,
        }))
        sys.exit(0)

    env = merged_env()
    sent_count = 0
    failed_count = 0

    for eml_path in eml_files:
        json_path = eml_path.with_suffix(".json")
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            items.append({"file": str(eml_path), "status": "failed", "detail": f"metadata error: {e}"})
            failed_count += 1
            print(f"warning: metadata missing for {eml_path.name}: {e}", file=sys.stderr)
            continue

        provider_name = meta.get("provider", "naver")
        provider = get_provider(provider_name, env)
        if not provider or not provider.get("email") or not provider.get("password"):
            items.append({
                "file": str(eml_path),
                "status": "failed",
                "detail": "credentials_missing",
            })
            failed_count += 1
            print(f"warning: credentials missing for provider '{provider_name}'", file=sys.stderr)
            continue

        to_raw = meta.get("to", "")
        cc_raw = meta.get("cc", "")
        bcc_raw = meta.get("bcc", "")
        recipients = [a.strip() for a in to_raw.split(",") if a.strip()]
        if cc_raw:
            recipients += [a.strip() for a in cc_raw.split(",") if a.strip()]
        if bcc_raw:
            recipients += [a.strip() for a in bcc_raw.split(",") if a.strip()]

        if not recipients:
            items.append({"file": str(eml_path), "status": "failed", "detail": "no recipients"})
            failed_count += 1
            continue

        eml_content = eml_path.read_text(encoding="utf-8")

        try:
            transport = _send_message(provider, recipients, eml_content)
            if args.purge_on_success:
                eml_path.unlink(missing_ok=True)
                json_path.unlink(missing_ok=True)
            else:
                sent_dir.mkdir(parents=True, exist_ok=True)
                eml_path.rename(sent_dir / eml_path.name)
                if json_path.exists():
                    json_path.rename(sent_dir / json_path.name)

            items.append({"file": str(eml_path), "status": "sent", "detail": transport})
            sent_count += 1
        except Exception as e:
            items.append({"file": str(eml_path), "status": "failed", "detail": str(e)})
            failed_count += 1
            print(f"warning: send failed for {eml_path.name}: {e}", file=sys.stderr)

    print(json.dumps({
        "status": "ok",
        "processed": len(items),
        "sent": sent_count,
        "failed": failed_count,
        "items": items,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
