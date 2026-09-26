#!/usr/bin/env python3
"""collect.py 산출 + 에이전트 요약 → 단일 HTML (Orca 브라우저 탭용).

  python3 render.py --data collect.json --summary summary.json --out out.html

summary.json 은 에이전트가 쓴다(없으면 요약층 없이 원문만 렌더한다):

  {
    "behavior_changes": [{"text": "...", "refs": [12884], "tag": "v1.4.177"}],
    "versions": {
      "v1.4.177": {"highlights": [{"text": "...", "refs": [13076]}]}
    }
  }
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fbfbfd; --panel:#fff; --ink:#16161a; --muted:#6b7180; --line:#e4e6eb;
  --accent:#3b6cf0; --warn-bg:#fff6ed; --warn-line:#f0b27a; --warn-ink:#8a4b12;
  --chip:#f1f3f7; --chip-ink:#4a5162; --pill:#eef2fd; --pill-ink:#2f52b5;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f1115; --panel:#171a21; --ink:#e7e9ee; --muted:#98a0b0; --line:#262b35;
  --accent:#7aa2ff; --warn-bg:#2a1e12; --warn-line:#7a5320; --warn-ink:#f0c08a;
  --chip:#212630; --chip-ink:#b3bccc; --pill:#1b2436; --pill-ink:#8fb0ff;
}}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Pretendard","Apple SD Gothic Neo",system-ui,sans-serif;
  padding:32px 20px 72px}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:21px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin:0 0 26px}
.sub b{color:var(--ink);font-weight:600}
section.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:18px 20px;margin:0 0 16px}
.warn{background:var(--warn-bg);border-color:var(--warn-line)}
.warn h2{color:var(--warn-ink)}
h2{font-size:15px;margin:0 0 12px;letter-spacing:-.01em}
h2 .tag{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:15px}
h2 .meta{color:var(--muted);font-weight:400;font-size:13px;margin-left:8px}
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;
  background:var(--pill);color:var(--pill-ink);margin-left:8px;vertical-align:2px}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  margin:16px 0 8px;font-weight:600}
h3:first-of-type{margin-top:0}
ul{margin:0;padding:0;list-style:none}
li{margin:0 0 7px;padding-left:15px;position:relative}
li::before{content:"·";position:absolute;left:3px;color:var(--muted)}
li.hl{font-size:14.5px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.pr{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
  color:var(--muted);margin-left:5px;white-space:nowrap}
.scopes{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.chip{background:var(--chip);color:var(--chip-ink);border-radius:6px;
  padding:2px 9px;font-size:12px;white-space:nowrap}
.chip b{font-weight:600;color:var(--ink)}
details{margin-top:16px;border-top:1px solid var(--line);padding-top:12px}
summary{cursor:pointer;color:var(--muted);font-size:13px;list-style:none;user-select:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ ";}
details[open] summary::before{content:"▾ ";}
summary:hover{color:var(--ink)}
details ul{margin-top:12px}
details li{color:var(--muted);font-size:13.5px}
.sc{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
  color:var(--chip-ink);background:var(--chip);border-radius:4px;padding:1px 6px;margin-right:6px}
.empty{color:var(--muted);font-size:13px;font-style:italic}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:28px}
"""


def esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def prlink(repo: str, num) -> str:
    return (
        f'<a class="pr" href="https://github.com/{repo}/pull/{num}" '
        f'target="_blank">#{num}</a>'
    )


def refs_html(repo: str, refs) -> str:
    return "".join(prlink(repo, n) for n in (refs or []))


def item_refs(it: dict) -> list:
    return it.get("prs") or ([it["pr"]] if it.get("pr") else [])


def render(data: dict, summary: dict) -> str:
    repo = data.get("repo", "")
    product = data.get("product_label") or data.get("product") or repo
    labels = data.get("scope_labels", {})
    versions = (summary or {}).get("versions", {})
    behavior = (summary or {}).get("behavior_changes", [])

    out: list[str] = []
    add = out.append

    gen = data.get("generated_at", "")[:16].replace("T", " ")
    head = (
        f'기간 <b>{esc(data.get("window_label",""))}</b> · '
        f'릴리즈 <b>{data.get("release_count",0)}개</b> · '
        f'<b>{data.get("item_kept",0)}건</b>'
    )
    if data.get("item_dup"):
        head += f' <span>(이전 버전 재수록 {data["item_dup"]}건 포함)</span>'
    if data.get("item_excluded"):
        head += f' <span>(제외 표면 {data["item_excluded"]}건)</span>'
    if data.get("installed_version"):
        head += f' · 설치 버전 <b>{esc(data["installed_version"])}</b>'
    head += f" · {esc(gen)} UTC 기준"

    add('<div class="wrap">')
    add(f"<h1>{esc(product)} 업데이트 요약</h1>")
    add(f'<p class="sub">{head}</p>')

    if data.get("window_widened"):
        add(
            '<section class="card"><p class="empty">지정한 기간에 릴리즈가 없어 '
            "가장 최근 1개까지 범위를 넓혔습니다.</p></section>"
        )
    if data.get("range_truncated"):
        add(
            '<section class="card"><p class="empty">요청 구간이 수집 범위(최근 100개 태그)의 '
            "끝에 닿았습니다 — 더 과거는 포함되지 않았을 수 있습니다.</p></section>"
        )

    if behavior:
        add('<section class="card warn"><h2>⚠️ 동작 변경 · 되돌림</h2><ul>')
        for b in behavior:
            tag = f' <span class="pr">{esc(b["tag"])}</span>' if b.get("tag") else ""
            add(
                f'<li class="hl">{esc(b.get("text",""))}'
                f'{refs_html(repo, b.get("refs"))}{tag}</li>'
            )
        add("</ul></section>")

    for rel in data.get("releases", []):
        tag = rel["tag"]
        vsum = versions.get(tag, {})
        badge = "" if rel.get("installed") else '<span class="badge">미설치</span>'
        add("<section class='card'>")
        dup = rel.get("dup", 0)
        fresh = rel.get("total", 0) - dup
        meta = f'{esc(rel.get("date",""))} · {rel.get("total",0)}건'
        if dup:
            meta += f" (새 항목 {fresh} · 재수록 {dup})"
        add(
            f'<h2><span class="tag">{esc(tag)}</span>{badge}'
            f'<span class="meta">{meta}</span></h2>'
        )

        if rel.get("empty"):
            add('<p class="empty">릴리즈 노트에 항목이 없습니다.</p></section>')
            continue

        highlights = vsum.get("highlights") or []
        if highlights:
            add("<h3>눈에 띄는 변화</h3><ul>")
            for h in highlights:
                add(
                    f'<li class="hl">{esc(h.get("text",""))}'
                    f'{refs_html(repo, h.get("refs"))}</li>'
                )
            add("</ul>")

        counts = rel.get("scope_counts", {})
        if counts:
            add('<h3>표면별</h3><div class="scopes">')
            for scope, n in counts.items():
                name = labels.get(scope, scope)
                add(f'<span class="chip">{esc(name)} <b>{n}</b></span>')
            add("</div>")

        items = rel.get("items", [])
        if items:
            add(f"<details><summary>전체 {len(items)}건 펼치기</summary><ul>")
            for it in items:
                sc_key = it.get("scope") or it.get("kind")
                sc = (
                    f'<span class="sc">{esc(labels.get(sc_key, sc_key))}</span>'
                    if sc_key
                    else ""
                )
                mark = "↩︎ " if it.get("revert") else ("⚠︎ " if it.get("breaking") else "")
                pr = refs_html(repo, item_refs(it))
                dup_of = it.get("dup_of")
                tail = f'<span class="pr">↑{esc(dup_of)}</span>' if dup_of else ""
                add(f'<li>{sc}{mark}{esc(it.get("title",""))}{pr}{tail}</li>')
            add("</ul></details>")

        dump_items = rel.get("dump_items", [])
        if dump_items:
            add(
                f"<details><summary>PR 단위 전량 {len(dump_items)}건 펼치기 "
                "(릴리즈 노트 말미 덤프)</summary><ul>"
            )
            for it in dump_items:
                pr = prlink(repo, it["pr"]) if it.get("pr") else ""
                add(f'<li>{esc(it.get("title",""))}{pr}</li>')
            add("</ul></details>")

        if rel.get("excluded"):
            names = ", ".join(labels.get(s, s) for s in rel.get("excluded_scopes", []))
            add(
                f'<p class="empty">제외 표면 {rel["excluded"]}건'
                f'{" — " + esc(names) if names else ""} (--full 로 포함)</p>'
            )
        add("</section>")

    add(
        f'<footer>{esc(repo)} · /changelog 로 생성 · '
        f'{datetime.now().strftime("%Y-%m-%d %H:%M")}</footer>'
    )
    add("</div>")

    return (
        "<!doctype html>\n<html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(product)} 업데이트 · {esc(data.get('window_label',''))}</title>"
        f"<style>{CSS}</style></head><body>" + "".join(out) + "</body></html>"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--summary")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.data, encoding="utf-8") as fh:
        data = json.load(fh)
    summary = {}
    if args.summary and os.path.exists(args.summary):
        with open(args.summary, encoding="utf-8") as fh:
            summary = json.load(fh)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(data, summary))
    print(f"[changelog] HTML → {args.out}")


if __name__ == "__main__":
    main()
