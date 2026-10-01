#!/usr/bin/env python3
"""부동산 실거래가 CLI — 국토교통부 공공데이터 12유형. 호출 계획(plan)과 응답 가공(collect), 파일 입력 전용.

네트워크는 itda-hyve 가 한다(#1707, itda-work/skills#45). ``plan`` 이 batch ``plan_file`` 로 쓸 호출
목록을 만들고, ``collect`` 가 그렇게 받아 둔 **응답 XML 파일을 읽어** 정규화·요약·전량 대조만 한다.
모자라면 ``--next-plan`` 으로 다음 계획을 쓴다 — 모델이 쪽 번호·저장 이름을 손으로 옮기지 않는다.

사용법:
    python3 scripts/deals_cli.py plan --region 강남구 --type apt_trade \\
        --start-month 202601 --end-month 202603 --write "$D/plan-1.json"
    python3 scripts/deals_cli.py collect --region 강남구 --type apt_trade \\
        --start-month 202601 --end-month 202603 --input "$D/apt_trade-*.xml" --next-plan "$D/plan-2.json" --summary

    python3 scripts/deals_cli.py regions     # 지역명 → 법정동코드 (입력 불요)
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from data_go_client import RealEstateAPIError, error_fields
from deals_collector import (
    ENDPOINT_MAP,
    build_envelope,
    calls_preview,
    check_endpoint_fields,
    check_month_range,
    completeness,
    compute_summary,
    is_cancelled,
    next_calls,
    normalize_rent_item,
    normalize_trade_item,
    plan_calls,
    read_sources,
    run_dir_name,
    run_dir_of,
    write_plan_files,
)
from lawd_codes import LAWD_CD_MAP, resolve_lawd_cd

# 저장 폴더 머리 — 회차 폴더는 ``realty/<코드>-<시작월>-<종료월>[-<tag>]``.
PREFIX = "realty"


def _print(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _resolve_region(args: argparse.Namespace) -> tuple[str, str]:
    """args에서 (lawd_cd, region_label) 튜플 반환."""
    if getattr(args, "lawd_cd", None):
        return args.lawd_cd, args.region or args.lawd_cd
    if getattr(args, "region", None):
        return resolve_lawd_cd(args.region), args.region
    return "", ""


def cmd_plan(args: argparse.Namespace) -> int:
    """1차 호출 계획 — 달마다 1쪽. 2쪽 이후는 collect 가 totalCount 를 보고 정한다."""
    check_month_range(args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)
    run_dir = run_dir_name(PREFIX, lawd_cd, args.start_month, args.end_month, args.tag)
    calls = plan_calls([args.type], lawd_cd, args.start_month, args.end_month, run_dir)
    out: dict[str, Any] = {
        "status": "ok", "region": region, "lawd_cd": lawd_cd, "type": args.type,
        "start_month": args.start_month, "end_month": args.end_month, "run_dir": run_dir,
        "call_count": len(calls),
    }
    if args.write:
        out.update(write_plan_files(args.write, calls, run_dir))
        out["calls_preview"] = calls_preview(calls)
    else:
        out["calls"] = calls
    _print(out)
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """저장된 응답 XML 을 읽어 전량 대조·정규화·요약한다. 전량이 아니면 결과 없이 exit 1."""
    check_month_range(args.start_month, args.end_month)
    span = (args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)

    ep = ENDPOINT_MAP[args.type]
    deal_type = ep["deal_type"]

    raw_items, sources = read_sources(args.input, deal_type=deal_type, endpoint_type=args.type,
                                      lawd_cd=lawd_cd or None, month_span=span)
    check_endpoint_fields(args.type, raw_items)
    codes = {s["sgg_cd"] for s in sources} - {""}
    if len(codes) > 1:
        raise ValueError(f"파일의 지역코드가 섞였다({sorted(codes)}) — 한 지역의 파일만 넘긴다")
    lawd_cd = lawd_cd or next(iter(codes), "")
    region = region or lawd_cd

    rep = completeness(sources, month_span=span)
    if not rep["complete"]:
        # 부분본을 전량으로 내지 않는다(collection-completeness ②) — 형제 스킬과 같은 계약(W1 리뷰 m2).
        return _incomplete(args, rep, lawd_cd)

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

    # 요약 통계 — 해제 거래(cdealType)는 기본으로 뺀다(W1 리뷰 M6). 원본 행(results)은 그대로 싣는다.
    cancelled = sum(1 for i in raw_items if is_cancelled(i))
    summary = None
    if getattr(args, "summary", False):
        basis = raw_items if args.include_cancelled else [i for i in raw_items if not is_cancelled(i)]
        summary = compute_summary(basis, amount_field=amount_field_raw)

    envelope = build_envelope(
        status="ok",
        region=region,
        items=items,
        lawd_cd=lawd_cd,
        summary=summary,
        type=args.type,
        start_month=args.start_month,
        end_month=args.end_month,
        sources=sources,
        months=rep["months"],
        # summary 에서 뺀 해제 거래 수 — results 에는 cdeal_type 을 실은 채 남는다.
        excluded={"cancelled": 0 if (args.include_cancelled or summary is None) else cancelled},
        warnings=[],
    )

    if getattr(args, "format", "json") == "table":
        _print_table(envelope, deal_type)
    else:
        _print(envelope)

    return 0


def _incomplete(args: argparse.Namespace, rep: dict[str, Any], lawd_cd: str) -> int:
    """전량 미달 — 더 받을 쪽·다시 받을 달을 알리고, 되면 다음 계획을 쓴다."""
    out: dict[str, Any] = {
        "status": "incomplete",
        "error": "incomplete",
        "detail": "받은 쪽이 전량이 아니다 — 다음 계획의 호출을 받아 폴더의 파일을 전부 넘겨 다시 실행한다",
        "warnings": rep["warnings"],
        "missing_pages": {**{m: [1] for m in rep["absent"]}, **rep["missing_pages"]},
        "months": rep["months"],
    }
    if rep["refetch"]:
        out["refetch"] = rep["refetch"]
        if not args.overwrite:
            out["need_overwrite"] = True
            out["detail"] += (". refetch 의 달은 받는 사이 목록이 바뀌어 1쪽부터 다시 받아야 한다 — 같은 이름을"
                              " 덮어쓰므로 사용자에게 알리고 확인받은 뒤 --overwrite 를 붙여 다시 실행한다")
    try:
        run_dir = run_dir_of(list(args.input), PREFIX)
    except ValueError:
        if args.next_plan:
            raise
        run_dir = ""
    if run_dir and lawd_cd:
        calls = next_calls(rep, args.type, lawd_cd, run_dir, refetch=args.overwrite)
        out["next_call_count"] = len(calls)
        if args.next_plan and calls:
            out.update(write_plan_files(args.next_plan, calls, run_dir, overwrite=args.overwrite))
            out["next_calls_preview"] = calls_preview(calls)
        elif calls:
            out["next_calls"] = calls
    elif args.next_plan:
        raise ValueError("지역코드를 알 수 없어 다음 계획을 쓸 수 없다 — --region 또는 --lawd-cd 를 준다")
    print(json.dumps(out, ensure_ascii=False))
    return 1


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
    span = f"{result.get('start_month', '')}~{result.get('end_month', '')}"
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
        print(f"\n  평균: {summary['avg']:,}만원  중위: {summary['median']:,}만원"
              f"  (해제 {result.get('excluded', {}).get('cancelled', 0)}건 제외)")

    for w in result.get("warnings", []):
        print(f"\n  ⚠️ {w}")


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성."""
    parser = argparse.ArgumentParser(
        description="부동산 실거래가 호출 계획·응답 XML 가공 (국토교통부 공공데이터 12유형)",
    )
    parser.add_argument(
        "--format", choices=["json", "table"], default="json",
        help="출력 형식 (기본: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    def region_args(p: argparse.ArgumentParser, *, required: bool) -> None:
        g = p.add_mutually_exclusive_group(required=required)
        g.add_argument("--region", default=None, help="한글 지역명 (regions 목록의 이름)")
        g.add_argument("--lawd-cd", default=None, help="법정동코드 (5자리)")

    def common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--type", choices=list(ENDPOINT_MAP.keys()), default="apt_trade",
                       help="엔드포인트 유형 (기본: apt_trade)")
        p.add_argument("--start-month", required=True, metavar="YYYYMM", help="요청 기간 시작월")
        p.add_argument("--end-month", required=True, metavar="YYYYMM", help="요청 기간 종료월")

    # plan
    p_plan = sub.add_parser("plan", help="itda-hyve batch 호출 계획(달마다 1쪽)")
    region_args(p_plan, required=True)
    common_args(p_plan)
    p_plan.add_argument("--tag", default=None, help="같은 지역·기간을 다시 받을 때 회차 폴더 끝에 붙일 영숫자")
    p_plan.add_argument("--write", metavar="FILE", default=None,
                        help="batch plan_file 로 쓸 계획 파일 — 회차 폴더 안(예: \"$D/plan-1.json\")")

    # collect
    p_collect = sub.add_parser("collect", help="저장된 응답 XML 가공 (단일/다월·다페이지)")
    p_collect.add_argument(
        "--input", nargs="+", required=True, metavar="XML",
        help="itda-hyve 가 save_as 로 저장한 응답 XML 파일(들)·글로브. 달·페이지마다 1개",
    )
    region_args(p_collect, required=False)
    common_args(p_collect)
    p_collect.add_argument("--name", default=None, help="단지명 부분 일치 필터")
    p_collect.add_argument("--summary", action="store_true", help="요약 통계 포함(해제 거래 제외)")
    p_collect.add_argument("--include-cancelled", action="store_true",
                           help="요약 통계에 해제 거래(cdealType)도 넣는다 (기본: 뺀다)")
    p_collect.add_argument("--next-plan", dest="next_plan", metavar="FILE", default=None,
                           help="전량 미달이면 더 받을 호출을 batch plan_file 로 쓴다(회차 폴더 안)")
    p_collect.add_argument("--overwrite", action="store_true",
                           help="다시 받을 달(refetch)을 다음 계획에 넣고 덮어쓰기를 켠다 — 사용자 확인 뒤에만")

    # regions
    sub.add_parser("regions", help="지역명-법정동코드 목록 출력 (입력 불요)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    # Windows 콘솔(cp949)에서 한국어 출력이 UnicodeEncodeError 로 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            return cmd_plan(args)
        if args.command == "collect":
            return cmd_collect(args)
        if args.command == "regions":
            return cmd_regions(args)
        parser.print_help()
        return 2

    except RealEstateAPIError as e:
        # 저장된 XML 이 성공 응답이 아니다(resultCode 20·30 등) 또는 hyve 실패 자리 — 그대로 표면화한다.
        print(json.dumps({"status": "error", **error_fields(e), "detail": str(e)}, ensure_ascii=False))
        return 1
    except ValueError as e:
        print(json.dumps(
            {"status": "error", "error": "args", "detail": str(e)},
            ensure_ascii=False,
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())
