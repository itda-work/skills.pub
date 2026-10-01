#!/usr/bin/env python3
"""경제지표 가공 CLI — 한국은행 ECOS (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 스크립트는 그렇게
저장한 **응답 JSON 파일을 읽어** 오류 판정·전량 대조·정리만 한다 — 직접 API 를 부르지 않는다.

사용법 (통계표코드는 라이브 검증 — 2026-06-09):
    python3 scripts/collect_econ.py key    --input ecos/key-r1.json
    python3 scripts/collect_econ.py search --input ecos/search-901Y009-A-2020-2024-r1.json
    python3 scripts/collect_econ.py search --input ecos/search-731Y003-D-20240102-20240131-0000003-r1.json
    python3 scripts/collect_econ.py items  --input ecos/items-901Y009-r1.json ecos/items-901Y009-r1001.json
    python3 scripts/collect_econ.py tables --input ecos/tables-r1.json
    python3 scripts/collect_econ.py word   --input ecos/word-1-r1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import ecos_api


def _collect(args: argparse.Namespace) -> dict[str, Any]:
    return ecos_api.collect_rows(args.input, ecos_api.SERVICES[args.command])


def _emit(payload: dict[str, Any], warnings: list[str] | None = None) -> None:
    if warnings:
        payload["warnings"] = warnings
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _print_warnings(warnings: list[str]) -> None:
    for w in warnings:
        print(f"  ⚠️ {w}")


def cmd_key(args: argparse.Namespace) -> int:
    """100대 주요 경제지표."""
    got = _collect(args)
    rows = got["rows"]

    if args.format == "table":
        _print_key_table(rows)
        _print_warnings(got["warnings"])
    else:
        items = [{
            "class_name": r.get("CLASS_NAME", ""),
            "indicator": r.get("KEYSTAT_NAME", ""),
            "value": r.get("DATA_VALUE", ""),
            "period": r.get("CYCLE", ""),
            "unit": r.get("UNIT_NAME", ""),
        } for r in rows]
        _emit({"status": "ok", "count": len(items), "total_count": got["total_count"],
               "items": items, "sources": got["sources"]}, got["warnings"])
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """통계 데이터."""
    got = _collect(args)
    rows = got["rows"]
    summarized = ecos_api.summarize_data(rows)
    # 값이 숫자가 아닌 행(-, … 등)은 정리에서 빠진다 — 몇 행을 뺐는지 남긴다(무음 유실 금지).
    skipped = len(rows) - len(summarized)
    warnings = list(got["warnings"])
    if skipped:
        warnings.append(f"값이 숫자가 아닌 행 {skipped}개를 뺐습니다(DATA_VALUE 가 -·… 등)")

    if args.format == "table":
        _print_search_table(summarized)
        _print_warnings(warnings)
    else:
        payload: dict[str, Any] = {
            "status": "ok",
            "stat_code": rows[0].get("STAT_CODE", "") if rows else "",
            "period": ecos_api.infer_period(rows),
            "count": len(summarized),
            "total_count": got["total_count"],
            "skipped_non_numeric": skipped,
            "data": summarized,
            "sources": got["sources"],
        }
        _emit(payload, warnings)
    return 0


def cmd_items(args: argparse.Namespace) -> int:
    """통계표 세부항목 목록."""
    got = _collect(args)
    rows = got["rows"]
    stat_code = rows[0].get("STAT_CODE", "") if rows else ""

    if args.format == "table":
        _print_items_table(rows, stat_code)
        _print_warnings(got["warnings"])
    else:
        items = [{
            "group_code": r.get("GRP_CODE", ""),
            "group_name": r.get("GRP_NAME", ""),
            "item_code": r.get("ITEM_CODE", ""),
            "item_name": r.get("ITEM_NAME", ""),
            "cycle": r.get("CYCLE", ""),
            "start_time": r.get("START_TIME", ""),
            "end_time": r.get("END_TIME", ""),
            "data_cnt": r.get("DATA_CNT", ""),
            "unit": r.get("UNIT_NAME", ""),
        } for r in rows]
        _emit({"status": "ok", "stat_code": stat_code, "count": len(items),
               "total_count": got["total_count"], "items": items, "sources": got["sources"]}, got["warnings"])
    return 0


def cmd_tables(args: argparse.Namespace) -> int:
    """서비스 통계 목록."""
    got = _collect(args)
    rows = got["rows"]

    if args.format == "table":
        _print_tables_table(rows)
        _print_warnings(got["warnings"])
    else:
        items = [{
            "stat_code": r.get("STAT_CODE", ""),
            "stat_name": r.get("STAT_NAME", ""),
            "parent_code": r.get("P_STAT_CODE", ""),
            "cycle": r.get("CYCLE", ""),
            "searchable": r.get("SRCH_YN", ""),
            "org_name": r.get("ORG_NAME", ""),
        } for r in rows]
        _emit({"status": "ok", "count": len(items), "total_count": got["total_count"],
               "items": items, "sources": got["sources"]}, got["warnings"])
    return 0


def cmd_word(args: argparse.Namespace) -> int:
    """통계용어사전."""
    got = _collect(args)
    rows = got["rows"]

    if args.format == "table":
        _print_word_table(rows)
        _print_warnings(got["warnings"])
    else:
        items = [{"word": r.get("WORD", ""), "definition": r.get("CONTENT", "")} for r in rows]
        _emit({"status": "ok", "count": len(items), "total_count": got["total_count"],
               "items": items, "sources": got["sources"]}, got["warnings"])
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
        cycle = r.get("CYCLE") or ""
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
        cycle = r.get("CYCLE") or ""
        print(f"{grp:<15} {code:<15} {name:<30} {cycle:<5}")
    print()


def _print_tables_table(rows: list[dict[str, Any]]) -> None:
    print(f"\n통계표 목록 — {len(rows)}건\n")
    print(f"{'코드':<12} {'통계명':<40} {'주기':<5} {'기관':<10}")
    print("-" * 67)
    for r in rows:
        code = r.get("STAT_CODE", "")
        name = (r.get("STAT_NAME", "") or "")[:38]
        cycle = r.get("CYCLE") or ""
        org = (r.get("ORG_NAME", "") or "")[:8]
        print(f"{code:<12} {name:<40} {cycle:<5} {org:<10}")
    print()


def _print_word_table(rows: list[dict[str, Any]]) -> None:
    print(f"\n통계용어사전 — {len(rows)}건\n")
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

    ``--format`` 은 메인 파서와 모든 서브파서에 함께 등록해 서브커맨드 앞/뒤 어디에 와도 동작한다.
    """
    parser = argparse.ArgumentParser(description="경제지표 응답 가공 — 한국은행 ECOS")
    parser.add_argument(
        "--format", choices=["json", "table"], default="json",
        help="출력 형식 (기본: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    helps = {
        "key": "100대 주요 경제지표 (KeyStatisticList 응답)",
        "search": "통계 데이터 (StatisticSearch 응답)",
        "items": "통계표 세부항목 목록 (StatisticItemList 응답)",
        "tables": "서비스 통계 목록 (StatisticTableList 응답)",
        "word": "통계용어사전 (StatisticWord 응답)",
    }
    for name, text in helps.items():
        p = sub.add_parser(name, help=text)
        # 서브파서 쪽은 SUPPRESS 로 두어 메인 파서 값(앞 위치)을 보존한다.
        p.add_argument(
            "--format", choices=["json", "table"], default=argparse.SUPPRESS,
            help="출력 형식 (기본: json)",
        )
        p.add_argument(
            "--input", nargs="+", required=True, metavar="JSON",
            help="itda-hyve 가 save_as 로 저장한 응답 JSON 파일(들). 쪽(행 범위)마다 1개, 이름 끝은 -r<시작행>.json",
        )

    return parser


def _error(kind: str, detail: str, **extra: Any) -> int:
    print(json.dumps({"status": "error", "error": kind, "detail": detail, **extra},
                     ensure_ascii=False))
    return 1


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "key": cmd_key,
        "search": cmd_search,
        "items": cmd_items,
        "tables": cmd_tables,
        "word": cmd_word,
    }
    try:
        return commands[args.command](args)
    except ecos_api.ECOSAPIError as e:
        return _error("api", str(e), error_code=e.error_code)
    except ecos_api.InputFileError as e:
        return _error(e.kind, str(e))
    except ecos_api.IncompleteError as e:
        return _error("incomplete", str(e), missing_ranges=e.missing, need_calls=len(e.missing),
                      confirm_first=len(e.missing) > ecos_api.CONFIRM_CALLS)


if __name__ == "__main__":
    sys.exit(main())
