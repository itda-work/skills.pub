#!/usr/bin/env python3
"""export_targets.py — 플레이북 → competitor-watch targets.yaml.

target = 조직(호스트) 단위, 정보원 = 그 target 의 pages. export_eligible = A 전건 + 값 없는 URL 로
축약되는 L2(`repeat_access` L1|L2 이고 url 에 쿼리 값이 없거나 고정) — L3·C·D 는 내보내지 않는다(R2 결정).
competitor-watch 는 pages 를 WebFetch 로 읽으므로 브라우저 필요 위치를 넣으면 무음 실패가 된다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_common import load_module  # noqa: E402

pbm = load_module("playbook")
KIND = {"press": "press", "notice": "notice", "news": "press", "feed": "press", "report": "blog", "disclosure": "notice"}


def eligible(loc: dict) -> bool:
    """명시 계약: 플레이북이 `export_eligible: true` 로 선언한 위치만(기본 false). 선언이 있어도 축이 어긋나면 거부."""
    return bool(loc.get("export_eligible")) and loc.get("auth_state") == "none" and loc.get("repeat_access") in ("L1", "L2") and loc.get("grade") in ("A", "B")


def build(playbooks: list[dict]) -> list[dict]:
    targets = []
    for pb in playbooks:
        pages = [{"url": l["url"], "kind": KIND.get(l.get("item_kind", ""), "press")} for l in pb.get("locations", []) if eligible(l)]
        if not pages and not pb.get("queries"):
            continue  # pages 도 queries 도 없는 조직은 competitor-watch 가 할 일이 없다 — 그 외(C 조직 + queries)는 target 유지
        targets.append({"id": pb.get("target_id") or pb["host"].replace(".", "-"), "name": pb.get("label", pb["host"]), "group": pb.get("group", "institution"), "queries": pb.get("queries", []), "tags": pb.get("tags", []), "pages": pages, "note": f"web-scout 플레이북({pb['domain']}/{pb['host']})에서 내보냄"})
    return targets


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    p.add_argument("--output")
    a = p.parse_args(argv)
    t = build([pbm.load(Path(x)) for x in a.paths])
    text = yaml.safe_dump(t, allow_unicode=True, sort_keys=False)
    (Path(a.output).write_text(text, encoding="utf-8") if a.output else sys.stdout.write(text))
    print(f"targets={len(t)} pages={sum(len(x['pages']) for x in t)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
