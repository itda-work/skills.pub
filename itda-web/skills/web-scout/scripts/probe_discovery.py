#!/usr/bin/env python3
"""probe_discovery.py — S3 발견 프로브: 사이트 루트 1개 → 후보 위치 목록 (브라우저 없이).

무엇을 보나: 루트 JS 리다이렉트(최종 URL 재시도) · install_gate · robots.txt Sitemap · sitemap.xml ·
RSS/Atom <link> · llms.txt · /.well-known/openapi.json · JSON-LD · 메뉴 링크(보도|뉴스|공지|공시|자료|알림).
사이트 고유 경로(`/rss/allArticle.xml` 류)를 **추측하지 않는다** — 표준 관례 위치와 페이지가 스스로 드러낸 링크만.

HTTP 는 web-reader `fetch_html.fetch_url` 재사용(SSRF·크기 가드 포함). 예산: 호스트당 요청 ≤ --budget(기본 12).
출력: {"root": …, "final_url": …, "diag": …, "candidates": [{kind, url, label, source}], "requests": n}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_common import load_module, web_reader  # noqa: E402

grade = load_module("grade")
MENU_RE = re.compile(r"보도|뉴스|공지|공시|자료|알림|소식|press|news|notice|release", re.I)
TRACK_RE = re.compile(r"login|logout|join|member|cart|search\?|javascript:", re.I)


class Budget:
    """물리 요청 예산. fetch_html 내부 재시도(WAF 격자·리다이렉트)는 trace 길이로 사후 집계한다 (R-impl P1)."""

    def __init__(self, n: int) -> None:
        self.limit, self.used, self.exceeded = n, 0, False

    def can(self) -> bool:
        return self.used < self.limit

    def account(self, result: dict | None) -> None:
        trace = (result or {}).get("trace")
        self.used += max(1, len(trace)) if isinstance(trace, list) else 1
        if self.used > self.limit:
            self.exceeded = True


def _vis(html: str) -> int:
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html or "", flags=re.S | re.I)
    return len(re.sub(r"\s+", " ", t).strip())


def fetch(fh, url: str, budget: Budget) -> dict | None:
    if not budget.can():
        return None
    try:
        r = fh.fetch_url(url)
    except Exception as e:  # SSRF 차단 등은 명시 실패로
        budget.account(None)
        return {"error": str(e), "url": url, "status_code": None, "content": ""}
    budget.account(r)
    return r


def _origin(u: str) -> str:
    s = urlsplit(u)
    return f"{s.scheme}://{s.netloc}".lower()


def discover(root: str, budget_n: int = 12, follow_redirect: bool = True) -> dict:
    fh = web_reader("fetch_html")
    budget = Budget(budget_n)
    out: dict = {"root": root, "final_url": root, "diag": None, "candidates": [], "requests": 0, "notes": []}
    r = fetch(fh, root, budget)
    if r is None or r.get("error"):
        out["diag"] = "fetch_error"; out["notes"].append(str((r or {}).get("error", "budget")))
        out["requests"] = budget.used
        return out
    html, final = str(r.get("content") or ""), str(r.get("url") or root)
    sig = grade.Signal(status=r.get("status_code"), content_type="", html=html, visible_len=_vis(html))
    diag = grade.diagnose(sig)
    if diag == "js_redirect" and follow_redirect:
        target = urljoin(final, grade.js_redirect_target(html) or "")
        out["notes"].append(f"js_redirect → {target}")
        r2 = fetch(fh, target, budget)
        if r2 and not r2.get("error"):
            html, final = str(r2.get("content") or ""), str(r2.get("url") or target)
            sig = grade.Signal(status=r2.get("status_code"), content_type="", html=html, visible_len=_vis(html))
            diag = grade.diagnose(sig)
    out["final_url"], out["diag"], out["final_visible_len"] = final, diag, sig.visible_len
    if diag == "install_gate":
        out["notes"].append("install_gate: 이 경로 폐쇄 — 브라우저 에스컬레이션 금지(설치 불가·불요)")
    if _origin(final) != _origin(root):
        # origin 이탈(HTTP/JS 리다이렉트로 다른 호스트) — 새 origin 의 표준 위치를 자동 탐색하지 않는다 (R-impl P1)
        out["diag"] = "origin_changed"
        out["notes"].append(f"origin_changed: {_origin(root)} → {_origin(final)} — 사용자 확인 전 표준 위치 탐색 중단")
        out["requests"] = budget.used
        return out
    base = f"{urlsplit(final).scheme}://{urlsplit(final).netloc}/"
    cands: list[dict] = []
    from bs4 import BeautifulSoup  # type: ignore[import]
    soup = BeautifulSoup(html, "html.parser")
    # 페이지가 드러낸 피드·메뉴 링크 (속성 순서 무관 — 파서 사용)
    for ln in soup.find_all("link"):
        if (ln.get("type") or "").lower() in ("application/rss+xml", "application/atom+xml") and ln.get("href"):
            cands.append({"kind": "feed", "url": urljoin(final, ln["href"]), "label": "link[rel=alternate]", "source": "html_link"})
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href, txt = a["href"], re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if len(txt) > 24 or not MENU_RE.search(txt) or TRACK_RE.search(href):
            continue
        u = urljoin(final, href)
        if u in seen or urlsplit(u).netloc != urlsplit(final).netloc:
            continue
        seen.add(u)
        cands.append({"kind": "menu", "url": u, "label": txt, "source": "menu_link"})
    for sc_ in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
        try:
            data = json.loads(sc_.get_text() or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("url"), str) and _origin(urljoin(final, it["url"])) == _origin(final):
                cands.append({"kind": "jsonld", "url": urljoin(final, it["url"]), "label": str(it.get("@type", ""))[:40], "source": "jsonld"})
    # 표준 관례 위치
    rob = fetch(fh, urljoin(base, "robots.txt"), budget)
    if rob and rob.get("status_code") == 200:
        for sm in re.findall(r"(?im)^sitemap:\s*(\S+)", str(rob.get("content") or "")):
            cands.append({"kind": "sitemap", "url": sm, "label": "robots.txt Sitemap", "source": "robots"})
    for path, kind in (("sitemap.xml", "sitemap"), ("llms.txt", "llms"), (".well-known/openapi.json", "openapi")):
        rr = fetch(fh, urljoin(base, path), budget)
        if not rr or rr.get("status_code") != 200:
            continue
        body = str(rr.get("content") or "")
        ok = (kind == "sitemap" and ("<urlset" in body or "<sitemapindex" in body)) or (kind == "llms" and not body.lstrip().startswith("<")) or (kind == "openapi" and body.lstrip().startswith("{"))
        if not ok:
            out["notes"].append(f"{path}: 200 이지만 형식 불일치(HTML 오류 페이지 등) — 채택 안 함")
            continue
        cands.append({"kind": kind, "url": urljoin(base, path), "label": path, "source": "well_known"})
        if kind == "sitemap":
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)[:50]:
                cands.append({"kind": "sitemap_url", "url": loc, "label": "", "source": "sitemap"})
    out["candidates"], out["requests"] = cands, budget.used
    if budget.exceeded:
        out["notes"].append(f"budget_exceeded: 물리 요청 {budget.used} > {budget.limit}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="사이트 루트 → 후보 위치(발견 프로브)")
    p.add_argument("root")
    p.add_argument("--budget", type=int, default=12)
    p.add_argument("--no-follow", action="store_true")
    a = p.parse_args(argv)
    print(json.dumps(discover(a.root, a.budget, not a.no_follow), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
