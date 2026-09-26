#!/usr/bin/env python3
"""감사원 통합공지 수집 CLI.

사용 예:
  python3 collect_bai.py --limit 10
  python3 collect_bai.py --keyword 채용 --pages 2
  python3 collect_bai.py --from 2026-07-01 --to 2026-07-27 --format json
  python3 collect_bai.py --xlsx bai.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sys

if sys.version_info[0] < 3:
    sys.exit("Python 3.10+ 가 필요합니다")

import bai_api

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(s: str) -> str:
    if not DATE_RE.match(s):
        raise argparse.ArgumentTypeError(f"날짜는 YYYY-MM-DD 형식이어야 합니다: {s}")
    return s


def render_markdown(rows: list[dict]) -> str:
    lines = ["| 날짜 | 제목 | 담당 | 요약 | 링크 |", "|---|---|---|---|---|"]
    for r in rows:
        title = r["title"].replace("|", "\\|")
        summary = (r["summary"] or "-").replace("|", "\\|")
        lines.append(
            f"| {r['date']} | {title} | {r['dept']} | {summary} | [보기]({r['link']}) |"
        )
    return "\n".join(lines)


def write_xlsx(rows: list[dict], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        sys.exit("xlsx 저장에는 openpyxl 이 필요합니다: pip install openpyxl")
    wb = Workbook()
    ws = wb.active
    ws.title = "감사원 통합공지"
    ws.append(["날짜", "제목", "담당", "요약", "링크"])
    for r in rows:
        ws.append([r["date"], r["title"], r["dept"], r["summary"], r["link"]])
    wb.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="감사원 통합공지 수집")
    parser.add_argument("--limit", type=int, default=10, help="최근 N건 (기본 10)")
    parser.add_argument("--pages", type=int, default=1, help="조회 페이지 수 상한 (기본 1)")
    parser.add_argument("--keyword", default="", help="제목·내용 검색 키워드 (서버측 검색)")
    parser.add_argument("--from", dest="date_from", type=_valid_date, help="시작일 YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", type=_valid_date, help="종료일 YYYY-MM-DD")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--xlsx", help="xlsx 저장 경로")
    args = parser.parse_args(argv)

    if args.limit < 1 or args.pages < 1:
        parser.error("--limit/--pages 는 1 이상이어야 합니다")

    rows: list[dict] = []
    try:
        for page in range(args.pages):  # API 는 0-base
            payload = bai_api.fetch_list(
                page=page,
                size=args.limit,
                keyword=args.keyword,
                date_from=args.date_from or "",
                date_to=args.date_to or "",
            )
            rows.extend(bai_api.parse_rows(payload))
            total_pages = (payload.get("page") or {}).get("totalPages", 1)
            if page + 1 >= total_pages:
                break
    except bai_api.BaiError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        print("사이트 개편 시 스킬 업데이트가 필요할 수 있습니다.", file=sys.stderr)
        return 1

    rows = rows[: args.limit]

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
