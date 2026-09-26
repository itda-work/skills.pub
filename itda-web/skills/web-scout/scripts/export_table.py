#!/usr/bin/env python3
"""export_table.py — 플레이북(들) → 정보원 등급표 md (축 4종 + 파생 등급 + 근거)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_common import load_module  # noqa: E402

pbm = load_module("playbook")


def render(playbooks: list[dict]) -> str:
    lines = ["| 정보원 | 항목 | URL | discovery | repeat | auth | 등급 | 근거(시점·표본·브라우저) |", "|---|---|---|---|---|---|---|---|"]
    for pb in playbooks:
        for loc in pb.get("locations", []):
            ev = loc.get("evidence", {})
            lines.append(f"| {pb.get('label', pb['host'])} | {loc['item']} | {loc['url']} | {loc['discovery_path']} | {loc['repeat_access']} | {loc['auth_state']} | **{loc['grade']}** | {ev.get('observed_at','')} · n={ev.get('samples','')} · {ev.get('browser','n/a')}{' · ' + loc['note'] if loc.get('note') else ''} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    p.add_argument("--output")
    a = p.parse_args(argv)
    pbs = [pbm.load(Path(x)) for x in a.paths]
    md = render(pbs)
    if a.output:
        Path(a.output).write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
