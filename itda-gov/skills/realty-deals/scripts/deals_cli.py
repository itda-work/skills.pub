#!/usr/bin/env python3
"""부동산 실거래가 가공 CLI — 국토교통부 공공데이터 12유형 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(#1707). 이 스크립트는 그렇게 받아 둔
**응답 XML 파일을 읽어** 정규화·요약·전량 대조만 한다 — 직접 API 를 부르지 않는다.

사용법:
    python3 scripts/deals_cli.py collect --input a.xml b.xml \\
        --region "강남구" --type apt_trade --summary

    python3 scripts/deals_cli.py regions     # 지역명 → 법정동코드 (입력 불요)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from data_go_client import RealEstateAPIError, parse_response_xml
from deals_collector import (
    ENDPOINT_MAP,
    build_envelope,
    compute_summary,
    normalize_rent_item,
    normalize_trade_item,
)
from lawd_codes import LAWD_CD_MAP, resolve_lawd_cd


def _resolve_region(args: argparse.Namespace) -> tuple[str, str]:
    """args에서 (lawd_cd, region_label) 튜플 반환."""
    if getattr(args, "lawd_cd", None):
        return args.lawd_cd, args.lawd_cd
    if getattr(args, "region", None):
        return resolve_lawd_cd(args.region), args.region
    return "", ""


def _source_month(items: list[dict[str, str]]) -> str:
    """그 파일이 담은 거래월(YYYYMM). 항목이 없으면 빈 문자열.

    응답 XML 에는 조회 월(DEAL_YMD)이 없으므로 항목의 dealYear·dealMonth 최빈값으로 정한다.
    """
    months = [
        f"{(i.get('dealYear') or '').strip()}{(i.get('dealMonth') or '').strip().zfill(2)}"
        for i in items
        if (i.get("dealYear") or "").strip() and (i.get("dealMonth") or "").strip()
    ]
    if not months:
        return ""
    return Counter(months).most_common(1)[0][0]


def _read_sources(paths: list[str]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """입력 XML 파일들을 읽어 (원본 항목 누적, 파일별 메타) 를 돌려준다."""
    raw_items: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    for p in paths:
        path = Path(p).expanduser()
        if not path.is_file():
            raise ValueError(f"입력 파일이 없습니다: {p}")
        parsed = parse_response_xml(path.read_bytes())
        items = parsed["items"]
        raw_items.extend(items)
        sources.append({
            "path": str(path),
            "month": _source_month(items),
            "total_count": parsed["total_count"],
            "page": parsed["page"],
            "item_count": len(items),
        })
    return raw_items, sources


def _completeness(sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """월별 totalCount 와 수집 건수를 대조한다 (전량 수집 판정).

    같은 달의 여러 페이지는 같은 totalCount 를 싣는다 — 그 값이 그 달의 전체 건수다.
    수집이 모자라면 경고를 남기고 호출자가 status 를 incomplete 로 내린다.
    """
    months: dict[str, dict[str, Any]] = {}
    for s in sources:
        month = s["month"]
        if not month:
            continue  # 빈 페이지 — 어느 달인지 알 수 없다(대조에서 제외)
        entry = months.setdefault(month, {"month": month, "total_count": 0, "collected": 0})
        entry["total_count"] = max(entry["total_count"], s["total_count"])
        entry["collected"] += s["item_count"]

    rows = [months[m] for m in sorted(months)]
    warnings = [
        f"{r['month']}: totalCount={r['total_count']} 인데 수집={r['collected']} — 페이지를 더 받아야 합니다"
        for r in rows
        if r["collected"] < r["total_count"]
    ]
    return rows, warnings


def cmd_collect(args: argparse.Namespace) -> int:
    """저장된 응답 XML 을 읽어 정규화·요약한다."""
    lawd_cd, region = _resolve_region(args)

    ep = ENDPOINT_MAP[args.type]
    deal_type = ep["deal_type"]

    raw_items, sources = _read_sources(args.input)
    months, warnings = _completeness(sources)

    # 정규화
    if deal_type == "trade":
        items = [normalize_trade_item(i) for i in raw_items]
        amount_field_raw = "dealAmount"
    else:
        items = [normalize_rent_item(i) for i in raw_items]
        amount_field_raw = "deposit"

    # 단지명 필터
    if getattr(args, "name", None):
        name_lower = args.name.lower()
        items = [i for i in items if name_lower in i["apt_nm"].lower()]

    # 요약 통계
    summary = None
    if getattr(args, "summary", False):
        summary = compute_summary(raw_items, amount_field=amount_field_raw)

    envelope = build_envelope(
        status="incomplete" if warnings else "ok",
        region=region,
        items=items,
        lawd_cd=lawd_cd,
        summary=summary,
        type=args.type,
        sources=sources,
        months=months,
        warnings=warnings,
    )

    if getattr(args, "format", "json") == "table":
        _print_table(envelope, deal_type)
    else:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))

    return 0


def cmd_regions(args: argparse.Namespace) -> int:
    """내장 법정동코드 매핑 테이블 출력 (입력 불요)."""
    regions_list = [
        {"name": name, "lawd_cd": code}
        for name, code in sorted(LAWD_CD_MAP.items())
    ]
    result: dict[str, Any] = {
        "status": "ok",
        "count": len(regions_list),
        "regions": regions_list,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _print_table(result: dict[str, Any], deal_type: str) -> None:
    """테이블 형식으로 출력."""
    region = result.get("region", "")
    count = result.get("count", 0)
    months = result.get("months") or []
    span = f"{months[0]['month']}~{months[-1]['month']}" if months else ""
    label = "매매" if deal_type == "trade" else "전월세"

    print(f"\n{region} {label} 실거래가 ({span}) — {count}건\n")
    if deal_type == "trade":
        print(f"{'단지명':<20} {'면적':<8} {'금액(만원)':<12} {'층':<5} {'계약일':<12}")
        print("-" * 60)
        for item in result.get("results", [])[:30]:
            nm = item.get("apt_nm", "")[:20]
            ar = item.get("exclu_use_ar", "")
            amt = f"{item.get('deal_amount', 0):,}"
            floor_str = item.get("floor", "")
            day = f"{item.get('deal_year', '')}.{item.get('deal_month', '')}.{item.get('deal_day', '')}"
            print(f"{nm:<20} {ar:<8} {amt:<12} {floor_str:<5} {day:<12}")
    else:
        print(f"{'단지명':<20} {'면적':<8} {'보증금(만원)':<14} {'월세':<8} {'계약일':<12}")
        print("-" * 65)
        for item in result.get("results", [])[:30]:
            nm = item.get("apt_nm", "")[:20]
            ar = item.get("exclu_use_ar", "")
            dep = f"{item.get('deposit', 0):,}"
            rent = f"{item.get('monthly_rent', 0):,}"
            day = f"{item.get('deal_year', '')}.{item.get('deal_month', '')}.{item.get('deal_day', '')}"
            print(f"{nm:<20} {ar:<8} {dep:<14} {rent:<8} {day:<12}")

    if count > 30:
        print(f"... 외 {count - 30}건")

    summary = result.get("summary")
    if summary:
        print(f"\n  평균: {summary['avg']:,}만원  중위: {summary['median']:,}만원")

    for w in result.get("warnings", []):
        print(f"\n  ⚠️ {w}")


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성."""
    parser = argparse.ArgumentParser(
        description="부동산 실거래가 응답 XML 가공 (국토교통부 공공데이터 12유형)",
    )
    parser.add_argument(
        "--format", choices=["json", "table"], default="json",
        help="출력 형식 (기본: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # collect
    p_collect = sub.add_parser("collect", help="저장된 응답 XML 가공 (단일/다월·다페이지)")
    p_collect.add_argument(
        "--input", nargs="+", required=True, metavar="XML",
        help="itda-hyve 가 save_as 로 저장한 응답 XML 파일(들). 달·페이지마다 1개",
    )
    p_collect.add_argument("--region", default=None, help="한글 지역명 (출력 라벨용)")
    p_collect.add_argument("--lawd-cd", default=None, help="법정동코드 (출력 라벨용, 5자리)")
    p_collect.add_argument(
        "--type",
        choices=list(ENDPOINT_MAP.keys()),
        default="apt_trade",
        help="엔드포인트 유형 (기본: apt_trade)",
    )
    p_collect.add_argument("--name", default=None, help="단지명 부분 일치 필터")
    p_collect.add_argument("--summary", action="store_true", help="요약 통계 포함")

    # regions
    sub.add_parser("regions", help="지역명-법정동코드 목록 출력 (입력 불요)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "collect":
            return cmd_collect(args)
        elif args.command == "regions":
            return cmd_regions(args)
        else:
            parser.print_help()
            return 2

    except RealEstateAPIError as e:
        # 저장된 XML 이 성공 응답이 아니다(resultCode 20·30 등) — 그대로 표면화한다.
        print(json.dumps(
            {"status": "error", "error": "api", "detail": str(e)},
            ensure_ascii=False,
        ))
        return 1
    except ValueError as e:
        print(json.dumps(
            {"status": "error", "error": "args", "detail": str(e)},
            ensure_ascii=False,
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())
