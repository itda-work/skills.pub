#!/usr/bin/env python3
"""extract_records.py — 목록 페이지·RSS/Atom 1장 → 항목 레코드 N행 (web-reader v7.1.0, hyve #1600 T0).

수집의 1차 산출은 요약이 아니라 **검증 가능한 추출 레코드**다. 각 행은 출처 URL 과
원문 발췌를 가지며, 발췌는 페이지 텍스트의 부분문자열임을 코드로 검증한다(아니면 거부).
판단(선별·요약)은 이 레코드 위에서만 일어난다.

출력(JSON):
  {"page": <provenance 봉투>, "records": [행…], "stats": {...}}
행 계약(키 추가만 허용):
  source_url  항목 링크(절대 URL). javascript: 링크면 null + link_raw 에 원문
  title       링크 텍스트(원문, 공백 정규화)
  published   YYYY-MM-DD (컨테이너 텍스트의 첫 날짜; 없으면 "" — 지어내지 않는다)
  excerpt     컨테이너의 제목 외 텍스트, 원문 그대로 최대 --max-excerpt 자 (없으면 "")
  page_final_url / page_fetched_at  봉투 참조(행 단독 유통 시 출처 앵커)

HTML 목록 감지(MVP): 구조 서명이 같은 <a> 그룹 중 **컨테이너에 날짜가 있는 비율이 가장 높은**
그룹을 목록으로 본다. 날짜 없는 그룹만 있으면 레코드 0건(내비게이션을 목록으로 오인하지 않기 위함) —
빈 결과도 봉투는 나간다("안 읽힘"과 "없음"의 구분은 상위(web-scout)가 봉투·기대 shape 로 판정).

이 스크립트는 HTTP 를 하지 않는다. 입력은 파일/stdin 이고 봉투 재료(--url·--final-url·--status·
--fetched-at·--encoding·--fetch-phase)는 호출자가 fetch 결과에서 넘긴다(fetch_html.py 재사용).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any
from urllib.parse import urljoin

_scripts_dir = os.path.dirname(os.path.abspath(__file__))


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, os.path.join(_scripts_dir, f"{name}.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_WS = re.compile(r"\s+")
_DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_DATE_YM = re.compile(r"(?<![\d.\-/])(20\d{2})\s*[.\-/년]\s*(\d{1,2})(?![\d.\-/]|\s*[.\-/월]?\s*\d)")  # YYYY-MM 만 있는 목록(보험연구원 CEO Brief 실측)
_SENT_END = re.compile(r"(?<=[.!?。])\s*")


def norm(s: str) -> str:
    return _WS.sub(" ", s or "").strip()


def first_date(text: str) -> str:
    """YYYY-MM-DD 우선, 없으면 YYYY-MM(일 없음 — 지어내지 않고 월까지만)."""
    m = _DATE.search(text)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = _DATE_YM.search(text)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return ""


def clip_excerpt(text: str, max_chars: int) -> str:
    """원문을 **자르기만** 한다(문장 경계 우선) — 치환·요약 금지."""
    text = norm(text)
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    cut = list(_SENT_END.finditer(head))
    if cut and cut[-1].start() >= max_chars // 3:
        return head[: cut[-1].start()].rstrip()
    return head[: head.rfind(" ")].rstrip() if " " in head else head


def verify_excerpt(excerpt: str, page_text_norm: str) -> bool:
    """발췌 원문성 계약: 정규화된 발췌가 정규화된 페이지 텍스트의 부분문자열이어야 한다."""
    e = norm(excerpt)
    return e == "" or e in page_text_norm


def finalize_records(records: list[dict[str, Any]], page_text_norm: str) -> tuple[list[dict[str, Any]], int]:
    """원문성 검증을 통과한 행만 남긴다. 반환: (accepted, rejected_count).

    별도 함수로 둔 이유: 레코드가 외부에서 편집·합성됐을 가능성을 같은 게이트로 재검증하기 위함
    (테스트는 발췌 한 글자를 변조해 이 게이트가 RED 인지 잰다 — gate-must-be-able-to-fail).
    """
    ok: list[dict[str, Any]] = []
    rejected = 0
    for r in records:
        if verify_excerpt(r.get("excerpt", ""), page_text_norm):
            ok.append(r)
        else:
            rejected += 1
    return ok, rejected


# ---------------------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------------------

def is_feed(raw: str) -> bool:
    head = raw.lstrip("﻿ \t\r\n")[:400].lower()
    return head.startswith("<?xml") and ("<rss" in head or "<feed" in head or "<rdf" in head) or head.startswith("<rss") or head.startswith("<feed")


def _strip_tags(s: str) -> str:
    return norm(unescape(re.sub(r"<[^>]+>", " ", s or "")))


def _et_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "") + "".join(ET.tostring(c, encoding="unicode") for c in el)


def records_from_feed(raw: str, base_url: str | None, max_excerpt: int) -> tuple[list[dict[str, Any]], str]:
    root = ET.fromstring(raw.lstrip("﻿"))
    ns = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}
    items: list[dict[str, Any]] = []
    tag = root.tag.lower()
    if tag.endswith("feed"):  # Atom
        for e in root.findall("atom:entry", ns):
            link_el = e.find("atom:link", ns)
            href = link_el.get("href") if link_el is not None else ""
            pub = _et_text(e.find("atom:published", ns)) or _et_text(e.find("atom:updated", ns))
            body = _et_text(e.find("atom:summary", ns)) or _et_text(e.find("atom:content", ns))
            items.append({"title": _strip_tags(_et_text(e.find("atom:title", ns))), "href": href, "date": pub, "body": _strip_tags(body)})
    else:  # RSS 2.0 / RDF
        for it in root.iter():
            if it.tag.lower().split("}")[-1] != "item":
                continue
            get = lambda n: next((c for c in it if c.tag.lower().split("}")[-1] == n), None)  # noqa: E731
            pub = _et_text(get("pubdate")) or _et_text(get("date"))
            items.append({"title": _strip_tags(_et_text(get("title"))), "href": (_et_text(get("link")) or "").strip(), "date": pub, "body": _strip_tags(_et_text(get("description")))})
    page_text = norm(" ".join(f"{i['title']} {i['body']}" for i in items))
    out = []
    for i in items:
        if not i["title"]:
            continue
        out.append({
            "source_url": urljoin(base_url or "", i["href"]) if i["href"] else None,
            "link_raw": None if i["href"] else "",
            "title": i["title"],
            "published": first_date(i["date"]) or _rfc_date(i["date"]),
            "excerpt": clip_excerpt(i["body"], max_excerpt),
        })
    return out, page_text


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _rfc_date(s: str) -> str:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\w*\s+(20\d{2})", s or "")
    if not m:
        return ""
    d, mon, y = m.groups()
    mo = _MONTHS.get(mon.lower())
    return f"{y}-{mo:02d}-{int(d):02d}" if mo else ""


# ---------------------------------------------------------------------------
# HTML 목록
# ---------------------------------------------------------------------------

def _signature(a: Any) -> tuple:
    sig = []
    node = a.parent
    for _ in range(3):
        if node is None or getattr(node, "name", None) is None:
            break
        sig.append((node.name, tuple(node.get("class") or [])))
        node = node.parent
    return tuple(sig)


def _container(a: Any, group_ids: set[int]) -> Any:
    """그룹 앵커를 자기 하나만 포함하는 가장 높은 조상 = 항목 컨테이너."""
    best = a
    node = a.parent
    while node is not None and getattr(node, "name", None) not in (None, "body", "html", "[document]"):
        cnt = sum(1 for x in node.find_all("a") if id(x) in group_ids)
        if cnt > 1:
            break
        best = node
        node = node.parent
    return best


def _dated_container_records(soup: Any, base_url: str | None, max_excerpt: int, min_title: int) -> list[dict[str, Any]]:
    """컨테이너(li/tr/article/div) 단위 폴백: 직계 텍스트에 날짜가 있고 제목이 링크가 아닌 카드형 목록.
    같은 구조 서명이 ≥3 개인 그룹 중 최대를 취한다. 제목 = 날짜를 제외한 가장 긴 텍스트 노드, 링크 = 첫 GET href."""
    groups: dict[tuple, list[Any]] = {}
    for el in soup.find_all(["li", "tr", "article", "div"]):
        own = norm(" ".join(str(x) for x in el.find_all(string=True, recursive=True) if x.parent is not None))
        if not own or not first_date(own) or len(own) < min_title + 8 or len(own) > 2000:
            continue
        if any(c.name in ("li", "tr", "article") for c in el.find_all(["li", "tr", "article"], recursive=True)):
            continue  # 자기 안에 또 항목이 있으면 컨테이너가 아니라 목록 전체다
        groups.setdefault(((el.name, tuple(el.get("class") or [])), _signature(el)), []).append(el)
    best = max((g for g in groups.values() if len(g) >= 3), key=len, default=None)
    if not best:
        return []
    from bs4 import NavigableString  # type: ignore[import]
    out, seen = [], set()
    for el in best:
        texts = [norm(str(t)) for t in el.descendants if isinstance(t, NavigableString) and norm(str(t))]
        ctext = norm(el.get_text(" "))
        published = first_date(ctext)
        cands = [t for t in texts if len(t) >= min_title and not first_date(t) == t and not _DATE.fullmatch(t) and not re.fullmatch(r"(저자|작성자|등록일|조회)\s*[:：].*", t)]
        if not cands:
            continue
        title = max(cands, key=len)
        href = next((a["href"] for a in el.find_all("a", href=True) if not a["href"].lower().startswith(("javascript:", "#"))), "")
        source_url = urljoin(base_url or "", href) if href else None
        key = (source_url or title, title)
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_url": source_url, "link_raw": None if source_url else "", "title": title, "published": published, "excerpt": ""})
    return out


def _longest_text_node(container: Any, *, exclude: Any, min_len: int = 20) -> str:
    """컨테이너 안에서 **연속된 단일 텍스트 노드** 중 가장 긴 것 — 구성상 원문 부분문자열이 보장된다.

    제목 앵커 자신·날짜만 있는 노드는 제외. 없으면 ""(지어내지 않는다). 표 목록은 대개 ""이고
    요약문이 있는 카드형 목록에서 값이 나온다.
    """
    from bs4 import NavigableString  # type: ignore[import]

    best = ""
    for node in container.descendants:
        if not isinstance(node, NavigableString) or node.parent is None:
            continue
        if exclude is not None and (node.parent is exclude or exclude in node.parents):
            continue
        # 다른 링크(첨부 파일명·다운로드 버튼)의 텍스트는 발췌가 아니다
        if node.parent.name == "a" or any(getattr(p, "name", None) == "a" for p in node.parents):
            continue
        s = norm(str(node))
        if len(s) < min_len or _DATE.fullmatch(s):
            continue
        if len(s) > len(best):
            best = s
    return best


def resolve_js_link(href: str, pattern: str | None, template: str | None, base_url: str | None) -> str | None:
    """플레이북이 실측으로 박제한 패턴으로 javascript: 링크를 GET URL 로 해소한다(추측 금지 — 패턴은 호출자가 준다).
    예: pattern=r"goBoardView\\('([^']+)','View','([^']+)'\\)"  template="{1}?View&boardNo={2}" (보험개발원 실측)."""
    if not pattern or not template:
        return None
    m = re.search(pattern, href)
    if not m:
        return None
    try:
        rel = template.format(*(("",) + m.groups()))
    except (IndexError, KeyError):
        return None
    return urljoin(base_url or "", rel)


def records_from_html(html: str, base_url: str | None, max_excerpt: int, min_title: int, js_link: str | None = None, js_link_template: str | None = None) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    from bs4 import BeautifulSoup  # type: ignore[import]

    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    page_text = norm(soup.get_text(" "))

    anchors = [a for a in soup.find_all("a") if len(norm(a.get_text(" "))) >= min_title]
    groups: dict[tuple, list[Any]] = {}
    for a in anchors:
        groups.setdefault(_signature(a), []).append(a)

    best_key, best_score = None, (-1.0, 0)
    scored: dict[tuple, tuple[float, int]] = {}
    for key, members in groups.items():
        if len(members) < 3:
            continue
        ids = {id(m) for m in members}
        dated = sum(1 for m in members if first_date(norm(_container(m, ids).get_text(" "))))
        ratio = dated / len(members)
        scored[key] = (ratio, len(members))
        if (ratio, len(members)) > best_score:
            best_key, best_score = key, (ratio, len(members))

    stats: dict[str, Any] = {"anchor_groups": len(scored), "candidates": 0, "dated_ratio": best_score[0] if best_key else 0.0}
    if best_key is None or best_score[0] < 0.5:
        # 앵커 기반 목록이 없다 → 날짜 달린 컨테이너 폴백(제목이 <p> 에 있고 링크가 "다운로드/요약보기" 인 카드형 — CEO Brief 실측)
        fb = _dated_container_records(soup, base_url, max_excerpt, min_title)
        if fb:
            stats.update({"candidates": len(fb), "group_signature": ["container_fallback"], "records_without_url": sum(1 for r in fb if not r["source_url"]), "records_with_excerpt": sum(1 for r in fb if r["excerpt"])})
            return fb, page_text, stats
        # 날짜 달린 목록이 없다 — 내비게이션을 목록으로 오인하지 않기 위해 0건 (봉투는 나간다; 상위는 no_dated_list 를 재탐색 신호로 본다)
        stats["reason"] = "no_dated_list"
        return [], page_text, stats

    members = groups[best_key]
    ids = {id(m) for m in members}
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for a in members:
        title = norm(a.get_text(" "))
        href = (a.get("href") or "").strip()
        cont = _container(a, ids)
        ctext = norm(cont.get_text(" "))
        published = first_date(ctext)
        excerpt = clip_excerpt(_longest_text_node(cont, exclude=a), max_excerpt)
        is_js = href.lower().startswith(("javascript:", "#")) or href == ""
        # javascript 링크의 식별자는 href 가 아니라 onclick 에 있는 경우가 많다(공시실 goDetail('id') 실측) — 둘을 이어 붙여 패턴 대조
        js_src = f"{href} {a.get('onclick') or ''}"
        source_url = (resolve_js_link(js_src, js_link, js_link_template, base_url) if is_js else urljoin(base_url or "", href))
        key = (source_url or href, title)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "source_url": source_url,
            "link_raw": (js_src.strip() if is_js else None),
            "title": title,
            "published": published,
            "excerpt": excerpt,
        })
    stats["candidates"] = len(members)
    stats["group_signature"] = [f"{n}.{'.'.join(c)}" if c else n for n, c in best_key]
    stats["records_without_url"] = sum(1 for r in out if not r["source_url"])  # 0 이 아니면 플레이북에 js 링크 패턴이 필요하다는 신호
    stats["records_with_excerpt"] = sum(1 for r in out if r["excerpt"])
    return out, page_text, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def extract_records(raw: str, *, base_url: str | None, max_excerpt: int = 300, min_title: int = 8, js_link: str | None = None, js_link_template: str | None = None) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    if is_feed(raw):
        recs, page_text = records_from_feed(raw, base_url, max_excerpt)
        return recs, page_text, {"kind": "feed", "candidates": len(recs), "records_without_url": sum(1 for r in recs if not r["source_url"]), "records_with_excerpt": sum(1 for r in recs if r["excerpt"])}
    recs, page_text, stats = records_from_html(raw, base_url, max_excerpt, min_title, js_link, js_link_template)
    stats["kind"] = "html"
    return recs, page_text, stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="목록 페이지·RSS → 항목 레코드 (출처 URL + 원문 발췌, 원문성 검증)")
    p.add_argument("input", nargs="?", help="HTML/XML 파일 (생략 시 stdin)")
    p.add_argument("--url", help="요청 URL (상대 링크 해석·봉투 requested_url)")
    p.add_argument("--final-url", help="리다이렉트 후 최종 URL (fetch_html 결과)")
    p.add_argument("--status", type=int, help="HTTP 상태코드 (fetch_html 결과)")
    p.add_argument("--fetched-at", help="수집 시각 UTC ISO-8601 (fetch_html 결과)")
    p.add_argument("--encoding", help="감지 인코딩")
    p.add_argument("--fetch-phase", default=None, help="static|degraded_static (기본: input)")
    p.add_argument("--content-sha256", dest="content_sha256", help="fetch_html 이 계산한 raw bytes sha256 (있으면 봉투 content_hash 로 사용)")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--max-excerpt", type=int, default=300)
    p.add_argument("--min-title", type=int, default=8)
    p.add_argument("--js-link", help="javascript: 링크 해소용 정규식(플레이북 실측 패턴)")
    p.add_argument("--js-link-template", help="해소 템플릿, 그룹은 {1},{2}… (예: '{1}?View&boardNo={2}')")
    p.add_argument("--output")
    args = p.parse_args(argv)
    # Windows 기본 코드페이지(cp1252)에서 한글 출력이 UnicodeEncodeError 로 죽는다 —
    # extract_content.py 선례와 동일하게 표준 스트림을 UTF-8 로 고정 (skills-v8.54.0 windows RED).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    try:
        raw = open(args.input, encoding="utf-8", errors="replace").read() if args.input else sys.stdin.read()
    except OSError as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return 1

    prov = _load("provenance")
    base = args.final_url or args.url
    page = prov.build_provenance(
        raw,
        raw_sha256=getattr(args, "content_sha256", None),
        requested_url=args.url,
        final_url=args.final_url,
        status=args.status,
        fetched_at=args.fetched_at,
        encoding=args.encoding,
        fetch_phase=args.fetch_phase or "input",
    )
    try:
        recs, page_text, stats = extract_records(raw, base_url=base, max_excerpt=args.max_excerpt, min_title=args.min_title, js_link=args.js_link, js_link_template=args.js_link_template)
    except ET.ParseError as e:
        print(f"Error: feed XML parse failed: {e}", file=sys.stderr)
        return 1
    accepted, rejected = finalize_records(recs, page_text)  # 호출부 — 이 줄을 no-op 으로 바꾸면 test_cli_rejects_tampered_excerpt 가 RED
    for r in accepted:
        r["page_final_url"] = page["final_url"]
        r["page_fetched_at"] = page["fetched_at"]
    stats.update({"accepted": len(accepted), "rejected_excerpt": rejected})

    if args.format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["source_url", "link_raw", "title", "published", "excerpt", "page_final_url", "page_fetched_at"])
        w.writeheader()
        for r in accepted:
            w.writerow(r)
        out = buf.getvalue()
    else:
        out = json.dumps({"page": page, "records": accepted, "stats": stats}, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out + ("" if out.endswith("\n") else "\n"))
    print(f"records={len(accepted)} rejected={rejected} kind={stats.get('kind')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
