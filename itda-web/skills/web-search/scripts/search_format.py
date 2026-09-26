"""web-search 출력 렌더 — json / markdown.

``render(payload, fmt)`` 는 SPEC-WEB-SEARCH-001 §4 정규화 payload 를 받아
``--format json`` 은 그대로, ``--format markdown`` 은 사람이 읽기 좋은 목록으로 낸다.
"""
from __future__ import annotations

import json
from typing import Any


def render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return _render_markdown(payload)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    query = payload.get("query", "")
    lines.append(f"# 검색 결과: {query}")

    engines = payload.get("engines_used") or (
        [payload["engine"]] if payload.get("engine") else []
    )
    results = payload.get("results", [])
    if engines:
        lines.append(f"\n> 엔진: {', '.join(engines)} · 결과 {len(results)}건")

    answer = payload.get("answer")
    if answer:
        lines.append("\n## 요약 답변")
        lines.append(answer)

    if results:
        lines.append("\n## 결과")
        for item in results:
            title = item.get("title") or item.get("url") or "(제목 없음)"
            lines.append(f"\n**{item.get('rank')}. [{title}]({item.get('url')})**")
            meta_bits: list[str] = []
            if item.get("source"):
                meta_bits.append(str(item["source"]))
            if item.get("engine"):
                meta_bits.append(f"via {item['engine']}")
            if item.get("published_at"):
                meta_bits.append(str(item["published_at"]))
            if meta_bits:
                lines.append(f"<sub>{' · '.join(meta_bits)}</sub>")
            if item.get("snippet"):
                lines.append(str(item["snippet"]))
    elif not answer:
        lines.append("\n_검색 결과가 없습니다._")

    errors = payload.get("errors") or []
    if errors:
        lines.append("\n## 일부 엔진 오류")
        for err in errors:
            lines.append(
                f"- {err.get('engine')}: {err.get('message')} (`{err.get('code')}`)"
            )

    return "\n".join(lines)
