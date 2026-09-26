#!/usr/bin/env python3
"""itda-email: check_env.py — detect configured email providers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_providers import detect_providers  # noqa: E402
from env_loader import merged_env  # noqa: E402


def main() -> None:
    providers = detect_providers(merged_env())
    ready = [p for p in providers if p["status"] == "ready"]
    print(json.dumps({
        "providers": providers,
        "ready_count": len(ready),
        "summary": f"{len(ready)} provider(s) ready" if ready else "No providers configured",
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
