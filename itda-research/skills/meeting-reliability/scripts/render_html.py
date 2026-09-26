"""render_html.py — 구조화 결과 → 단일 자족 HTML(근거 tooltip).

각 행의 '근거' 셀에 hover하면 원문 발화 + 앞뒤 대화 맥락(±2) + 판정 근거를
보여준다. inline CSS만 사용(JS·외부 CDN 0) → 오프라인·아티팩트 친화(NFR-8).
표현 계층일 뿐 — 검증은 selfcheck/reliability_rules가 담당(표현/검증 분리).
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from meeting_adapter import Turn, context_window, load_transcript
from reliability_rules import Row, rows_from_dicts

_STATUS_CLASS = {"확정": "ok", "미정": "pend", "확인필요": "check", "확인 필요": "check"}

_CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;
 margin:2rem auto;max-width:62rem;color:#111827;line-height:1.5;padding:0 1rem}
h1{font-size:1.4rem;margin:.2rem 0}
.meta{color:#6b7280;font-size:.85rem;margin-bottom:1.2rem}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border:1px solid #e5e7eb;padding:.5rem .6rem;text-align:left;vertical-align:top}
th{background:#f9fafb;font-weight:600}
.cat{font-size:.78rem;padding:.1rem .5rem;border-radius:999px;background:#eef2ff;color:#3730a3;white-space:nowrap}
.cat.risk{background:#fef2f2;color:#991b1b}
.cat.task{background:#f0fdf4;color:#166534}
.st{font-weight:600}.st.ok{color:#166534}.st.pend{color:#b45309}.st.check{color:#9333ea}
.unset{color:#9ca3af;font-style:italic}
.check{color:#9333ea}
.ev{position:relative;cursor:help;color:#2563eb;border-bottom:1px dotted #93c5fd;white-space:nowrap}
/* 근거는 항상 최우측 열 → tooltip을 우측 기준(right:0)으로 왼쪽으로 펼쳐 화면 밖으로 나가지 않게.
   폭은 뷰포트 기준(min(32rem,80vw))으로 제한, 높이는 60vh + 스크롤. */
.ev .tip{visibility:hidden;opacity:0;transition:opacity .12s;position:absolute;z-index:20;
 right:0;left:auto;top:1.6em;width:min(32rem,80vw);max-height:60vh;overflow-y:auto;
 background:#1f2937;color:#f3f4f6;
 padding:.7rem .9rem;border-radius:8px;font-size:.82rem;line-height:1.55;font-weight:400;
 white-space:pre-wrap;box-shadow:0 6px 20px rgba(0,0,0,.28)}
.ev:hover .tip{visibility:visible;opacity:1}
/* 하단 가까운 행은 tooltip을 위로 펼쳐 화면 아래로 넘치지 않게. */
tbody tr:nth-last-child(-n+4) .ev .tip{top:auto;bottom:1.6em}
.tip .cur{color:#fcd34d;font-weight:700}
.tip .basis{display:block;margin-top:.5rem;padding-top:.5rem;border-top:1px solid #374151;color:#d1d5db}
.legend{margin-top:1rem;font-size:.8rem;color:#6b7280}
""".strip()

_CAT_CLASS = {"리스크": "risk", "실무": "task"}


def _tooltip(row: Row, turns: list[Turn], radius: int = 2) -> str:
    parts: list[str] = []
    n = len(turns)
    seen: set[int] = set()
    for idx in row.evidence:
        if idx < 0 or idx >= n:
            continue
        block: list[str] = []
        for t in context_window(turns, idx, radius):
            if t.idx in seen:
                continue
            seen.add(t.idx)
            spk = html.escape(t.speaker or "—")
            txt = html.escape(t.text)
            if t.idx == idx:
                block.append(f"<span class='cur'>▶ {spk}: {txt}</span>")
            else:
                block.append(f"{spk}: {txt}")
        if block:
            parts.append("\n".join(block))
    tip = "\n\n".join(parts)
    if row.basis:
        tip += f"<span class='basis'>판정 근거: {html.escape(row.basis)}</span>"
    if row.risk_note:
        tip += f"<span class='basis'>⚠ {html.escape(row.risk_note)}</span>"
    return tip


def _cell(val: str | None) -> str:
    if val is None or str(val).strip() == "":
        return "<span class='unset'>—</span>"
    s = str(val)
    if "확인" in s or "미지정" in s:
        return f"<span class='check'>{html.escape(s)}</span>"
    return html.escape(s)


def render_html(rows: list[Row], turns: list[Turn], title: str = "회의 신뢰성 검수") -> str:
    trs: list[str] = []
    for r in rows:
        stcls = _STATUS_CLASS.get(r.status, "")
        catcls = _CAT_CLASS.get(r.category, "")
        ev_n = len([i for i in r.evidence if 0 <= i < len(turns)])
        if ev_n:
            ev_cell = f"<span class='ev'>📎 근거 {ev_n}<span class='tip'>{_tooltip(r, turns)}</span></span>"
        else:
            ev_cell = "<span class='unset'>—</span>"
        trs.append(
            "<tr>"
            f"<td>{html.escape(r.item)}</td>"
            f"<td><span class='cat {catcls}'>{html.escape(r.category)}</span></td>"
            f"<td><span class='st {stcls}'>{html.escape(r.status)}</span></td>"
            f"<td>{_cell(r.owner)}</td>"
            f"<td>{_cell(r.due)}</td>"
            f"<td>{ev_cell}</td>"
            "</tr>"
        )
    body = "\n".join(trs)
    t = html.escape(title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ko"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{t}</title>\n"
        f"<style>{_CSS}</style></head>\n"
        "<body>\n"
        f"<h1>{t}</h1>\n"
        '<div class="meta">신뢰성 검수 — 확정/미정/확인필요를 근거와 함께. '
        "각 행의 <b>📎 근거</b>에 hover하면 원문 발화·맥락·판정 근거가 보입니다.</div>\n"
        "<table>\n"
        "<thead><tr><th>항목</th><th>분류</th><th>상태</th><th>담당</th><th>기한</th><th>근거</th></tr></thead>\n"
        f"<tbody>\n{body}\n</tbody>\n"
        "</table>\n"
        '<div class="legend">📎 근거 = 원문 발화 인덱스 기반 추적. 상대표현 기한은 캘린더 환산 없이 보존. '
        "빈 칸(—)은 원문에 근거 없음(추정 금지).</div>\n"
        "</body></html>\n"
    )


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python render_html.py <result.json> <transcript.md> [out.html]", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    is_obj = isinstance(data, dict)
    rows = rows_from_dicts(data["rows"] if is_obj else data)
    title = data.get("title", "회의 신뢰성 검수") if is_obj else "회의 신뢰성 검수"
    turns = load_transcript(argv[1])
    out_html = render_html(rows, turns, title)
    if len(argv) >= 3:
        Path(argv[2]).write_text(out_html, encoding="utf-8")
        print(f"wrote {argv[2]} ({len(rows)} rows)")
    else:
        sys.stdout.write(out_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
