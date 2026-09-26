#!/usr/bin/env python3
"""경제지표 수집 CLI — 한국은행 ECOS.

제안서/사업계획서에 필요한 거시경제 지표를 수집하여 JSON/Table로 출력.

사용법 (통계표코드는 모두 라이브 검증 — 2026-06-09):
    python3 scripts/collect_econ.py key                              # 100대 주요 경제지표
    python3 scripts/collect_econ.py search --stat 901Y009 --start 2020 --end 2024  # 소비자물가지수
    python3 scripts/collect_econ.py items --stat 901Y009            # 항목코드 확인
    python3 scripts/collect_econ.py tables                           # 전체 통계표 목록
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import ecos_api
import env_loader

_KEY_VAR = "ECOS_API_KEY"

_SETUP_GUIDE = (
    "ECOS_API_KEY가 설정되지 않았습니다.\n\n"
    "한국은행 ECOS 인증키 발급 방법:\n"
    "  1. https://ecos.bok.or.kr/api/ 회원가입\n"
    "  2. 인증키 신청 (가입 시 자동 부여)\n\n"
    "설정 방법: 작업 폴더 루트(예: outputs/)에 .env 파일을 만들고 키를 추가하세요.\n"
    "  ECOS_API_KEY=발급받은_인증키\n"
)


def _get_api_key(cli_arg: str | None = None) -> str:
    return env_loader.resolve_api_key(_KEY_VAR, cli_arg, _SETUP_GUIDE)


def cmd_key(args: argparse.Namespace) -> int:
    """100대 주요 경제지표 조회."""
    api_key = _get_api_key(args.api_key)
    rows = ecos_api.get_key_statistics(api_key)

    if args.format == "table":
        _print_key_table(rows)
    else:
        items = []
        for r in rows:
            items.append({
                "class_name": r.get("CLASS_NAME", ""),
                "indicator": r.get("KEYSTAT_NAME", ""),
                "value": r.get("DATA_VALUE", ""),
                "period": r.get("CYCLE", ""),
                "unit": r.get("UNIT_NAME", ""),
            })
        print(json.dumps(
            {"status": "ok", "count": len(items), "items": items},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """통계 데이터 조회."""
    api_key = _get_api_key(args.api_key)
    period = ecos_api.PERIOD_CODES.get(args.period, "A")

    rows = ecos_api.search_statistics(
        api_key=api_key,
        stat_code=args.stat,
        period=period,
        start_date=args.start,
        end_date=args.end,
        item_code1=args.item1 or "",
        item_code2=args.item2 or "",
    )
    summarized = ecos_api.summarize_data(rows)

    if args.format == "table":
        _print_search_table(summarized)
    else:
        print(json.dumps(
            {"status": "ok", "stat_code": args.stat, "period": args.period,
             "count": len(summarized), "data": summarized},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_items(args: argparse.Namespace) -> int:
    """통계표 세부항목 목록 조회."""
    api_key = _get_api_key(args.api_key)
    rows = ecos_api.get_item_list(api_key, args.stat)

    if args.format == "table":
        _print_items_table(rows, args.stat)
    else:
        items = []
        for r in rows:
            items.append({
                "group_code": r.get("GRP_CODE", ""),
                "group_name": r.get("GRP_NAME", ""),
                "item_code": r.get("ITEM_CODE", ""),
                "item_name": r.get("ITEM_NAME", ""),
                "cycle": r.get("CYCLE", ""),
                "start_time": r.get("START_TIME", ""),
                "end_time": r.get("END_TIME", ""),
                "data_cnt": r.get("DATA_CNT", ""),
                "unit": r.get("UNIT_NAME", ""),
            })
        print(json.dumps(
            {"status": "ok", "stat_code": args.stat,
             "count": len(items), "items": items},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_tables(args: argparse.Namespace) -> int:
    """전체 통계표 목록 조회."""
    api_key = _get_api_key(args.api_key)
    rows = ecos_api.get_table_list(api_key, end=args.count)

    if args.format == "table":
        _print_tables_table(rows)
    else:
        items = []
        for r in rows:
            items.append({
                "stat_code": r.get("STAT_CODE", ""),
                "stat_name": r.get("STAT_NAME", ""),
                "cycle": r.get("CYCLE", ""),
                "org_name": r.get("ORG_NAME", ""),
            })
        print(json.dumps(
            {"status": "ok", "count": len(items), "items": items},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_word(args: argparse.Namespace) -> int:
    """통계용어사전 검색."""
    api_key = _get_api_key(args.api_key)
    rows = ecos_api.search_word(api_key, args.word)

    if args.format == "table":
        _print_word_table(rows, args.word)
    else:
        items = []
        for r in rows:
            items.append({
                "word": r.get("WORD", ""),
                "definition": r.get("CONTENT", ""),
            })
        print(json.dumps(
            {"status": "ok", "query": args.word,
             "count": len(items), "items": items},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


# --- 테이블 출력 헬퍼 ---

def _print_key_table(rows: list[dict[str, Any]]) -> None:
    print(f"\n100대 주요 경제지표 — {len(rows)}건\n")
    print(f"{'분류':<12} {'지표명':<30} {'값':>15} {'시점':<10} {'단위':<10}")
    print("-" * 77)
    for r in rows:
        cls = (r.get("CLASS_NAME", "") or "")[:10]
        name = (r.get("KEYSTAT_NAME", "") or "")[:28]
        val = r.get("DATA_VALUE", "-")
        cycle = r.get("CYCLE", "")
        unit = (r.get("UNIT_NAME", "") or "")[:8]
        print(f"{cls:<12} {name:<30} {val:>15} {cycle:<10} {unit:<10}")
    print()


def _print_search_table(data: list[dict[str, Any]]) -> None:
    if not data:
        print("\n(데이터 없음)\n")
        return

    stat_name = data[0].get("stat_name", "") if data else ""
    print(f"\n{stat_name}\n")
    print(f"{'시점':<10} {'항목':<25} {'값':>15} {'단위':<10}")
    print("-" * 60)
    for row in data:
        time = row.get("time", "")
        item = (row.get("item_name", "") or "")[:23]
        val = row.get("value")
        unit = (row.get("unit", "") or "")[:8]
        val_str = f"{val:,.2f}" if val is not None else "-"
        print(f"{time:<10} {item:<25} {val_str:>15} {unit:<10}")
    print()


def _print_items_table(rows: list[dict[str, Any]], stat_code: str) -> None:
    print(f"\n통계표 {stat_code} 세부항목 — {len(rows)}건\n")
    print(f"{'그룹':<15} {'항목코드':<15} {'항목명':<30} {'주기':<5}")
    print("-" * 65)
    for r in rows:
        grp = (r.get("GRP_NAME", "") or "")[:13]
        code = r.get("ITEM_CODE", "")
        name = (r.get("ITEM_NAME", "") or "")[:28]
        cycle = r.get("CYCLE", "")
        print(f"{grp:<15} {code:<15} {name:<30} {cycle:<5}")
    print()


def _print_tables_table(rows: list[dict[str, Any]]) -> None:
    print(f"\n통계표 목록 — {len(rows)}건\n")
    print(f"{'코드':<12} {'통계명':<40} {'주기':<5} {'기관':<10}")
    print("-" * 67)
    for r in rows:
        code = r.get("STAT_CODE", "")
        name = (r.get("STAT_NAME", "") or "")[:38]
        cycle = r.get("CYCLE", "")
        org = (r.get("ORG_NAME", "") or "")[:8]
        print(f"{code:<12} {name:<40} {cycle:<5} {org:<10}")
    print()


def _print_word_table(rows: list[dict[str, Any]], query: str) -> None:
    print(f"\n통계용어사전: '{query}' — {len(rows)}건\n")
    for r in rows:
        word = r.get("WORD", "")
        content = r.get("CONTENT", "")
        print(f"  [{word}]")
        # 내용을 80자 단위로 줄바꿈
        for i in range(0, len(content), 80):
            print(f"    {content[i:i+80]}")
        print()


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성.

    공용 옵션(--api-key, --format)을 _add_common() 헬퍼로 메인 파서와 모든 서브파서에
    동시 등록하여 서브커맨드 앞/뒤 양쪽 위치에서 모두 동작하도록 한다 (REQ-1).
    """
    # 메인 파서: 서브커맨드 앞 위치 공용 옵션 (REQ-1.2, 하위 호환)
    parser = argparse.ArgumentParser(
        description="경제지표 수집 — 한국은행 ECOS",
    )
    parser.add_argument(
        "--api-key", default=None, dest="api_key", help="ECOS API 키",
    )
    parser.add_argument(
        "--format", choices=["json", "table"], default="json",
        help="출력 형식 (기본: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # 서브파서 공용 옵션은 default=argparse.SUPPRESS로 두어 메인 파서 기본값을 보존한다.
    def _add_common(p: argparse.ArgumentParser) -> None:
        """서브파서에 공용 옵션 추가 (SUPPRESS default로 메인 파서 값 보존)."""
        p.add_argument(
            "--api-key", default=argparse.SUPPRESS, dest="api_key",
            help="ECOS API 키",
        )
        p.add_argument(
            "--format", choices=["json", "table"], default=argparse.SUPPRESS,
            help="출력 형식 (기본: json)",
        )

    # key - 100대 주요 경제지표
    p_key = sub.add_parser("key", help="100대 주요 경제지표 조회")
    _add_common(p_key)

    # search - 통계 데이터 조회
    p_search = sub.add_parser("search", help="통계 데이터 조회")
    _add_common(p_search)
    p_search.add_argument("--stat", "-s", required=True, help="통계표코드 (예: 901Y009)")
    p_search.add_argument("--start", required=True, help="시작일 (예: 2020)")
    p_search.add_argument("--end", required=True, help="종료일 (예: 2024)")
    p_search.add_argument(
        "--period", "-p", choices=list(ecos_api.PERIOD_CODES.keys()),
        default="year", help="주기 (기본: year)",
    )
    p_search.add_argument("--item1", default=None, help="항목코드1")
    p_search.add_argument("--item2", default=None, help="항목코드2")

    # items - 세부항목 목록
    p_items = sub.add_parser("items", help="통계표 세부항목 목록")
    _add_common(p_items)
    p_items.add_argument("--stat", "-s", required=True, help="통계표코드")

    # tables - 통계표 목록
    p_tables = sub.add_parser("tables", help="전체 통계표 목록")
    _add_common(p_tables)
    p_tables.add_argument("--count", "-n", type=int, default=100, help="조회 건수 (기본 100)")

    # word - 통계용어사전
    p_word = sub.add_parser("word", help="통계용어사전 검색")
    _add_common(p_word)
    p_word.add_argument("--word", "-w", required=True, help="검색할 용어")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        commands = {
            "key": cmd_key,
            "search": cmd_search,
            "items": cmd_items,
            "tables": cmd_tables,
            "word": cmd_word,
        }
        return commands[args.command](args)

    except env_loader.MissingAPIKeyError as e:
        print(json.dumps(
            {"status": "error", "error": "config", "detail": str(e)},
            ensure_ascii=False,
        ))
        return 1
    except ecos_api.ECOSAPIError as e:
        print(json.dumps(
            {"status": "error", "error": "api", "detail": str(e),
             "error_code": e.error_code},
            ensure_ascii=False,
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())
