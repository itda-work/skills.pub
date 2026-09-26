"""국세법령정보시스템 검색 CLI.

사용법:
    python3 scripts/search_taxlaw.py "가상자산 양도소득"
    python3 scripts/search_taxlaw.py "부가가치세과-1196" --docno
    python3 scripts/search_taxlaw.py "세법" --domain precedent --limit 5 --page 2
    python3 scripts/search_taxlaw.py detail --domain precedent --id 200000000000009799
    python3 scripts/search_taxlaw.py detail --domain law --id <bsc>:<brkd>:<pmg> --article 제18조
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxlaw_api

_DEFAULT_DOMAINS = ["law", "interpretation", "precedent", "counsel"]


def _build_search_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="search_taxlaw.py",
        description="국세법령정보시스템(taxlaw.nts.go.kr) 통합검색.",
    )
    p.add_argument("query", help="검색어 (또는 --docno 와 함께 문서번호)")
    p.add_argument(
        "--domain",
        default="core",
        help=(
            "검색 도메인 (쉼표 구분). "
            "law|interpretation|precedent|counsel|form|library|all|core "
            "(기본 core = law,interpretation,precedent,counsel)"
        ),
    )
    p.add_argument("--limit", type=int, default=10, help="도메인당 결과 수 (기본 10)")
    p.add_argument("--page", type=int, default=1, help="페이지 번호 1-base (기본 1)")
    p.add_argument(
        "--sort",
        default="accuracy",
        choices=sorted(taxlaw_api.SORTS),
        help="정렬: accuracy(정확도)|registered(등록일)|produced(생산일)",
    )
    p.add_argument("--docno", action="store_true", help="문서번호 검색 모드")
    p.add_argument("--include", action="append", default=[], help="포함어 (반복 지정)")
    p.add_argument("--exclude", action="append", default=[], help="제외어 (반복 지정)")
    p.add_argument("--synonym", action="store_true", help="동의어 확장 활성화")
    p.add_argument(
        "--format",
        default="table",
        choices=["table", "json", "md"],
        help="출력 형식 (기본 table)",
    )
    return p


def _build_detail_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="search_taxlaw.py detail",
        description="문서 전문 조회 (검색 결과의 id 사용).",
    )
    p.add_argument(
        "--domain",
        required=True,
        choices=["law", "interpretation", "precedent", "counsel"],
        help="문서 도메인",
    )
    p.add_argument("--id", required=True, help="검색 결과의 id 값")
    p.add_argument("--article", help="law 전용: 특정 조문만 (예: 제18조)")
    p.add_argument(
        "--format", default="text", choices=["text", "json"], help="출력 형식"
    )
    return p


def _resolve_domains(raw: str) -> list[str]:
    if raw == "all":
        return list(taxlaw_api.DOMAINS)
    if raw == "core":
        return list(_DEFAULT_DOMAINS)
    return [d.strip() for d in raw.split(",") if d.strip()]


def _print_search_table(result: dict) -> None:
    print(f"검색어: {result['query']}  (페이지 {result['page']}, 도메인당 {result['limit']}건)")
    for domain, block in result["domains"].items():
        label = taxlaw_api.DOMAIN_LABELS.get(domain, domain)
        print()
        if block.get("missing"):
            print(f"■ {label} — ⚠ 응답에 이 도메인이 없습니다 (0건이 아니라 미수신 — 사이트 계약 변경 의심)")
            continue
        print(f"■ {label} — 총 {block['total']:,}건 중 {len(block['items'])}건 표시")
        if not block["items"]:
            print("  (결과 없음)")
            continue
        for i, it in enumerate(block["items"], 1):
            head = it["title"]
            meta = " / ".join(
                dict.fromkeys(  # 중복 제거 (통칙 행은 세목 약칭과 종류가 같은 "통칙")
                    x
                    for x in (
                        it.get("doc_no"),
                        it.get("date"),
                        it.get("tax_type"),
                        it.get("verdict"),
                        it.get("extra"),
                    )
                    if x
                )
            )
            print(f"  {i}. {head}")
            if meta:
                print(f"     {meta}")
            if it.get("summary"):
                summary = it["summary"]
                if len(summary) > 160:
                    summary = summary[:160] + "…"
                print(f"     {summary}")
            if it["id"]:
                print(f"     id: {it['id']}")
            else:
                print("     (전문 조회 미지원 — 원문 URL 참조)")
            if it.get("detail_url"):
                print(f"     {it['detail_url']}")


def _print_search_md(result: dict) -> None:
    print(f"# 국세법령정보시스템 검색: {result['query']}")
    for domain, block in result["domains"].items():
        label = taxlaw_api.DOMAIN_LABELS.get(domain, domain)
        if block.get("missing"):
            print(f"\n## {label}\n\n> ⚠ 응답에 이 도메인이 없습니다 (미수신 — 사이트 계약 변경 의심)")
            continue
        print(f"\n## {label} (총 {block['total']:,}건)\n")
        for it in block["items"]:
            meta = " · ".join(
                x
                for x in (it.get("doc_no"), it.get("date"), it.get("tax_type"), it.get("verdict"))
                if x
            )
            line = f"- **{it['title']}**"
            if meta:
                line += f" ({meta})"
            print(line)
            if it.get("summary"):
                print(f"  - {it['summary'][:200]}")
            if it.get("detail_url"):
                tail = f" · id `{it['id']}`" if it["id"] else " · (전문 조회 미지원)"
                print(f"  - [원문]({it['detail_url']}){tail}")


def _print_detail_text(doc: dict) -> None:
    if doc["domain"] == "law":
        name = doc["law_name"] or "법령 조문"
        print(f"{name} — 전체 {doc['article_count']}개 항목 중 {len(doc['articles'])}개 표시")
        for art in doc["articles"]:
            head = " ".join(x for x in (art["article"], art["title"]) if x)
            print(f"\n### {head}")
            if art["text"]:
                print(art["text"])
            if art["note"]:
                print(art["note"])
        # 원문 URL 은 도메인 무관 필수 (리뷰 R2 — law 분기 early return 이 푸터를 건너뛰었다)
        if doc.get("detail_url"):
            print(f"\n원문: {doc['detail_url']}")
        else:
            print("\n원문: (법령 구분코드 미해석 — 검색 결과에 표시된 원문 URL 을 사용하세요)")
        return
    print(doc["title"])
    meta = " / ".join(
        x for x in (doc.get("doc_no"), doc.get("date"), doc.get("tax_type")) if x
    )
    if meta:
        print(meta)
    if doc.get("gist"):
        print(f"\n[요지]\n{doc['gist']}")
    if doc.get("reply"):
        print(f"\n[회신]\n{doc['reply']}")
    if doc.get("answer"):
        print(f"\n[답변]\n{doc['answer']}")
    if doc.get("body"):
        print(f"\n[전문]\n{doc['body']}")
    if doc.get("related_laws"):
        print("\n[관련 법령]")
        for law in doc["related_laws"]:
            print(f"- {law}")
    print(f"\n원문: {doc['detail_url']}")


def _run_search(argv: list[str]) -> int:
    args = _build_search_parser().parse_args(argv)
    domains = _resolve_domains(args.domain)
    try:
        result = taxlaw_api.search(
            args.query,
            domains,
            limit=args.limit,
            page=args.page,
            sort=args.sort,
            doc_no=args.docno,
            include=args.include,
            exclude=args.exclude,
            use_synonym=args.synonym,
        )
    except taxlaw_api.TaxlawAPIError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        # compact 고정 — stdout JSON pretty-print 금지(#438 규율, tests/test_response_compact_guard.py)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    elif args.format == "md":
        _print_search_md(result)
    else:
        _print_search_table(result)
    return 0


def _run_detail(argv: list[str]) -> int:
    args = _build_detail_parser().parse_args(argv)
    if args.article and args.domain != "law":
        # 플래그 무음 무시 금지 (리뷰 R1 P2-3)
        print("오류: --article 은 --domain law 전용입니다.", file=sys.stderr)
        return 2
    try:
        if args.domain == "law":
            doc = taxlaw_api.detail_law(args.id, article=args.article)
        elif args.domain == "counsel":
            doc = taxlaw_api.detail_counsel(args.id)
        else:
            doc = taxlaw_api.detail_document(args.id, args.domain)
    except taxlaw_api.TaxlawAPIError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        # compact 고정 — #438 규율 (tests/test_response_compact_guard.py)
        print(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    else:
        _print_detail_text(doc)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "detail":
        return _run_detail(argv[1:])
    return _run_search(argv)


if __name__ == "__main__":
    sys.exit(main())
