#!/usr/bin/env python3
"""itda-calendar: list_calendars.py — list calendar collections."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from caldav_client import list_calendars  # noqa: E402
from cli_common import connect_or_exit, emit, resolve_provider_or_exit  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="List CalDAV calendars.")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--account")
    args = ap.parse_args()

    prov = resolve_provider_or_exit(args.provider, args.account)
    _client, principal = connect_or_exit(prov)
    cals = list_calendars(principal)
    emit([{
        "name": c["name"],
        "id": c["id"],
        "url": c["url"],
        "components": c["components"],
    } for c in cals])


if __name__ == "__main__":
    main()
