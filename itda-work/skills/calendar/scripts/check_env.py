#!/usr/bin/env python3
"""itda-calendar: check_env.py — detect configured CalDAV providers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows locale(cp949) stdio 고정 해제 — cli_common 미사용 진입점이라 별도 적용 (#1036).
for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - Python < 3.7
            pass

sys.path.insert(0, str(Path(__file__).parent))
from caldav_providers import detect_providers  # noqa: E402
from env_loader import merged_env  # noqa: E402


def main() -> None:
    providers = detect_providers(merged_env())
    ready = [p for p in providers if p["status"] == "ready"]
    print(json.dumps({
        "providers": providers,
        "ready_count": len(ready),
        "summary": (f"{len(ready)} provider(s) ready"
                    if ready else "No CalDAV providers configured"),
    }, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
