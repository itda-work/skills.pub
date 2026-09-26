#!/usr/bin/env python3
"""export_prompt.py — 플레이북 → 프롬프트 팩(추출 템플릿 + 가공 템플릿, Claude.ai 프로젝트 지침용).

도구 없는 소비자(강의 참가자)를 위한 산출. A/B 정보원만 싣는다. 추출 템플릿은 web-reader 추출 레코드와
**같은 열 이름**을 쓴다 — 강사 도구 산출과 참가자 산출이 같은 모양이라 크로스 체크가 성립한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_common import SKILL_DIR, load_module  # noqa: E402

pbm = load_module("playbook")
TEMPLATE = SKILL_DIR / "references" / "prompt-pack-template.md"


def render(playbooks: list[dict], topic: str) -> str:
    rows = []
    for pb in playbooks:
        for l in pb.get("locations", []):
            if l.get("grade") in ("A", "B") and l.get("auth_state") == "none":
                hint = " (RSS — 항목이 바로 나옵니다)" if l["discovery_path"] == "feed" else (f" ({l['note']})" if l.get("note") else "")
                rows.append(f"- {pb.get('label', pb['host'])} · {l['item']}: {l['url']}{hint}")
    sources = "\n".join(rows) if rows else "- (A/B 정보원 없음)"
    return TEMPLATE.read_text(encoding="utf-8").replace("{{SOURCES}}", sources).replace("{{TOPIC}}", topic)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    p.add_argument("--topic", default="업계 동향")
    p.add_argument("--output")
    a = p.parse_args(argv)
    md = render([pbm.load(Path(x)) for x in a.paths], a.topic)
    (Path(a.output).write_text(md, encoding="utf-8") if a.output else sys.stdout.write(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
