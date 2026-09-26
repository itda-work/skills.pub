#!/usr/bin/env python3
"""복지포털 스냅샷(pages.jsonl) 키워드 검색.

토큰 매칭 점수(제목·breadcrumb 가중)로 상위 N건을 JSON 으로 출력한다.
에이전트는 이 결과의 text 를 근거로 답변하고, url·수집일을 함께 제시한다.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다")

import argparse
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def tokenize(s: str) -> list[str]:
    return [t for t in re.split(r"[^\w가-힣]+", s.lower()) if len(t) >= 2]


def score(record: dict, tokens: list[str]) -> float:
    title = record.get("title", "").lower()
    crumb = record.get("breadcrumb", "").lower()
    text = record.get("text", "").lower()
    s = 0.0
    for t in tokens:
        if t in title:
            s += 5.0
        if t in crumb:
            s += 3.0
        s += min(text.count(t), 10) * 0.5
    return s


def snippet(text: str, tokens: list[str], width: int = 200) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in tokens if t in low), default=-1)
    if pos < 0:
        return text[:width]
    start = max(0, pos - width // 3)
    return ("…" if start else "") + text[start:start + width] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(description="복지포털 스냅샷 검색")
    parser.add_argument("query", help="검색어 (공백 구분 다중 토큰)")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--full", action="store_true", help="본문 전체 포함 (기본: snippet)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    pages_path = data_dir / "pages.jsonl"
    if not pages_path.exists():
        sys.exit(f"스냅샷이 없습니다: {pages_path} — 먼저 collect.py 를 실행하세요")
    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))

    tokens = tokenize(args.query)
    if not tokens:
        sys.exit("검색 토큰이 없습니다 (2자 이상 단어 필요)")

    results = []
    with pages_path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            s = score(rec, tokens)
            if s > 0:
                results.append((s, rec))
    results.sort(key=lambda x: -x[0])

    out = {
        "query": args.query,
        "snapshot_date": meta["generated_at"],
        "total_matches": len(results),
        "results": [],
    }
    for s, rec in results[: args.top]:
        item = {
            "score": round(s, 1),
            "title": rec["title"],
            "breadcrumb": rec["breadcrumb"],
            "url": rec["url"],
            "auth_required": rec["auth_required"],
            "fetched_at": rec["fetched_at"],
        }
        if rec["auth_required"]:
            item["note"] = "로그인 필요 영역 — 본문 미수집"
        elif args.full:
            item["text"] = rec["text"]
        else:
            item["snippet"] = snippet(rec["text"], tokens)
        out["results"].append(item)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
