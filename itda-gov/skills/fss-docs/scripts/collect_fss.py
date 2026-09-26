#!/usr/bin/env python3
"""금융감독원 공통업무자료 수집 CLI.

사용 예:
  python3 collect_fss.py --limit 10
  python3 collect_fss.py --keyword 사모 --pages 2
  python3 collect_fss.py --from 2026-07-01 --to 2026-07-27 --format json
  python3 collect_fss.py --xlsx fss.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sys

if sys.version_info[0] < 3:
    sys.exit("Python 3.10+ 가 필요합니다")

import fss_api

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(s: str) -> str:
    if not DATE_RE.match(s):
        raise argparse.ArgumentTypeError(f"날짜는 YYYY-MM-DD 형식이어야 합니다: {s}")
    return s


def filter_rows(
    rows: list[dict],
    keyword: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    out = []
    for r in rows:
        if keyword and keyword not in r["title"]:
            continue
        if date_from and r["date"] and r["date"] < date_from:
            continue
        if date_to and r["date"] and r["date"] > date_to:
            continue
        out.append(r)
    return out


def render_markdown(rows: list[dict]) -> str:
    lines = ["| 날짜 | 제목 | 담당부서 | 첨부 | 링크 |", "|---|---|---|---|---|"]
    for r in rows:
        title = r["title"].replace("|", "\\|")
        att = f"{len(r['attachments'])}건" if r["attachments"] else "-"
        lines.append(
            f"| {r['date']} | {title} | {r['dept']} | {att} | [보기]({r['link']}) |"
        )
    return "\n".join(lines)


def write_xlsx(rows: list[dict], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        sys.exit("xlsx 저장에는 openpyxl 이 필요합니다: pip install openpyxl")
    wb = Workbook()
    ws = wb.active
    ws.title = "금감원 공통업무자료"
    ws.append(["날짜", "제목", "담당부서", "첨부파일", "조회수", "링크"])
    for r in rows:
        ws.append(
            [r["date"], r["title"], r["dept"], "; ".join(r["attachments"]), r["views"], r["link"]]
        )
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="금융감독원 공통업무자료 수집")
    parser.add_argument("--limit", type=int, default=10, help="최근 N건 (기본 10)")
    parser.add_argument("--pages", type=int, default=1, help="조회 페이지 수 상한 (기본 1)")
    parser.add_argument("--keyword", help="제목 키워드 필터")
    parser.add_argument("--from", dest="date_from", type=_valid_date, help="시작일 YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", type=_valid_date, help="종료일 YYYY-MM-DD")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--xlsx", help="xlsx 저장 경로")
    args = parser.parse_args(argv)

    if args.limit < 1 or args.pages < 1:
        parser.error("--limit/--pages 는 1 이상이어야 합니다")

    rows: list[dict] = []
    try:
        for page in range(1, args.pages + 1):
            html = fss_api.fetch_list_html(page=page)
            rows.extend(fss_api.parse_list(html))
    except fss_api.FssError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        print("사이트 개편 시 스킬 업데이트가 필요할 수 있습니다.", file=sys.stderr)
        return 1

    rows = filter_rows(rows, args.keyword, args.date_from, args.date_to)[: args.limit]

    if not rows:
        print("조건에 맞는 게시물이 없습니다 (필터를 완화하거나 --pages 를 늘려보세요).")
        return 0

    if args.xlsx:
        write_xlsx(rows, args.xlsx)
        print(f"xlsx 저장 완료: {args.xlsx} ({len(rows)}건)")

    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
