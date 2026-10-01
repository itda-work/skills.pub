"""가격지수·시세 통계 CLI (파일 입력 전용).

사용법:
    python3 scripts/price_stats_cli.py rone-plan --index-type weekly --start-month 202601 --end-month 202606 \\
        --write plan-1.json
    python3 scripts/price_stats_cli.py rone --input rone/weekly-202601-202606-p1.json [--region 서울] \\
        --next-plan plan-next-1.json
    python3 scripts/price_stats_cli.py plan --region 강남구 --type apt_trade \\
        --start-month 202601 --end-month 202603 --write "$D/plan-1.json"
    python3 scripts/price_stats_cli.py derive --region 강남구 --type apt_trade \\
        --start-month 202601 --end-month 202603 --input "$D/apt_trade-*.xml" --next-plan "$D/plan-2.json"

네트워크는 하지 않는다 — itda-hyve 의 ``http_request``·``batch`` 가 ``save_as`` 로 저장한 응답을 읽어
가공만 한다(itda-work/skills#45). rone-plan·plan 이 호출 계획(batch ``plan_file``)을 만들고, rone 은 R-ONE
응답 JSON, derive 는 실거래 매매 응답 XML 을 읽어 전량 대조·통계를 낸다.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from data_go_client import RealEstateAPIError, error_fields
from deals_collector import (
    ENDPOINT_MAP,
    calls_preview,
    check_endpoint_fields,
    check_month_range,
    completeness,
    is_cancelled,
    next_calls,
    normalize_trade_item,
    plan_calls,
    read_sources,
    run_dir_name,
    run_dir_of,
    write_plan_files,
)
from lawd_codes import resolve_lawd_cd
from price_stats import (
    RONE_INDEX_TYPES,
    RONE_MAX_PAGES,
    IncompleteError,
    InputFileError,
    PriceStatsAPIError,
    build_stats_envelope,
    collect_rone,
    derive_stats_from_deals,
    rone_plan,
    write_plans,
)

# --next-plan 을 줬을 때 stdout 에 싣는 next_calls 앞부분 개수(전체는 계획 파일에 있다).
_NEXT_CALLS_PREVIEW = 3


# derive 저장 폴더 머리 — 회차 폴더는 ``price-stats/<코드>-<시작월>-<종료월>[-<tag>]``.
PREFIX = "price-stats"
_TRADE_TYPES = [k for k, v in ENDPOINT_MAP.items() if v["deal_type"] == "trade"]


def _print_error(status: str, error: str | None = None, detail: str = "", rc: int = 1, **extra: Any) -> int:
    print(json.dumps({"status": status, "error": error, "detail": detail, **extra},
                     ensure_ascii=False))
    return rc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="가격지수·시세 통계")
    sub = parser.add_subparsers(dest="command")

    # rone-plan — R-ONE 호출 계획(1쪽)
    rplan = sub.add_parser("rone-plan", help="R-ONE 가격지수 호출 계획 (http_request 인자)")
    rplan.add_argument("--index-type", required=True, choices=list(RONE_INDEX_TYPES.keys()),
                       help="지수 유형")
    rplan.add_argument("--start-month", required=True, metavar="YYYYMM")
    rplan.add_argument("--end-month", required=True, metavar="YYYYMM")
    rplan.add_argument("--write", metavar="FILE", default=None,
                       help="itda-hyve batch 의 plan_file 로 쓸 계획 파일({calls, timeout_sec})을 쓴다")

    # rone — 저장된 R-ONE 응답 가공
    rone = sub.add_parser("rone", help="R-ONE 가격지수 (저장된 응답 JSON 가공)")
    rone.add_argument("--input", nargs="+", required=True, metavar="JSON",
                      help="itda-hyve 가 save_as 로 저장한 응답 JSON 파일(들). 쪽마다 1개")
    rone.add_argument("--region", default=None,
                      help="지역 필터 (분류 전체명 부분일치, 예: 서울·강남구 / 전국은 정확일치)")
    rone.add_argument("--max-pages", type=int, default=RONE_MAX_PAGES,
                      help=f"받을 쪽 상한 (기본 {RONE_MAX_PAGES}, 쪽당 1000행). 넘으면 truncated")
    rone.add_argument("--next-plan", metavar="FILE", default=None,
                      help="쪽이 모자라면 더 받을 호출을 batch plan_file 로 쓴다(40개 단위로 나눔)")
    rone.add_argument("--format", choices=["json", "table"], default="json", help="출력 형식")

    # plan 서브커맨드 — derive 입력을 받을 1차 호출 계획(달마다 1쪽)
    plan = sub.add_parser("plan", help="derive 입력을 받을 itda-hyve batch 호출 계획(달마다 1쪽)")
    pg = plan.add_mutually_exclusive_group(required=True)
    pg.add_argument("--region", help="지역명 (예: 강남구)")
    pg.add_argument("--lawd-cd", dest="lawd_cd", help="법정동코드 5자리")
    plan.add_argument("--type", dest="endpoint_type", default="apt_trade", choices=_TRADE_TYPES,
                      help="매매 엔드포인트 유형 (기본: apt_trade)")
    plan.add_argument("--start-month", required=True, metavar="YYYYMM")
    plan.add_argument("--end-month", required=True, metavar="YYYYMM")
    plan.add_argument("--tag", default=None, help="같은 지역·기간을 다시 받을 때 회차 폴더 끝에 붙일 영숫자")
    plan.add_argument("--write", metavar="FILE", default=None,
                      help="batch plan_file 로 쓸 계획 파일 — 회차 폴더 안(예: \"$D/plan-1.json\")")

    # derive 서브커맨드
    derive = sub.add_parser("derive", help="실거래 파생 통계 (저장된 응답 XML 가공)")
    derive.add_argument("--input", nargs="+", required=True, metavar="XML",
                        help="itda-hyve 가 save_as 로 저장한 매매 응답 XML 파일(들)·글로브. 달·페이지마다 1개")
    dg = derive.add_mutually_exclusive_group()
    dg.add_argument("--region", help="지역명 (예: 강남구)")
    dg.add_argument("--lawd-cd", dest="lawd_cd", help="법정동코드 (5자리)")
    derive.add_argument("--type", dest="endpoint_type", default="apt_trade",
                        choices=_TRADE_TYPES,
                        help="매매 엔드포인트 유형 (기본: apt_trade) — 받은 파일과 같아야 한다")
    derive.add_argument("--start-month", required=True, metavar="YYYYMM", help="요청 기간 시작월")
    derive.add_argument("--end-month", required=True, metavar="YYYYMM", help="요청 기간 종료월")
    derive.add_argument("--group-by", dest="group_by", default=None,
                        help="그룹핑 필드 (예: apt_nm)")
    derive.add_argument("--include-cancelled", action="store_true",
                        help="해제된 거래(cdealType)도 통계에 넣는다 (기본: 뺀다)")
    derive.add_argument("--next-plan", dest="next_plan", metavar="FILE", default=None,
                        help="전량 미달이면 더 받을 호출을 batch plan_file 로 쓴다(회차 폴더 안)")
    derive.add_argument("--overwrite", action="store_true",
                        help="다시 받을 달(refetch)을 다음 계획에 넣고 덮어쓰기를 켠다 — 사용자 확인 뒤에만")

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한국어 출력이 UnicodeEncodeError 로 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "rone-plan":
        return _cmd_rone_plan(args)
    if args.command == "rone":
        return _cmd_rone(args)
    try:
        if args.command == "plan":
            return _cmd_plan(args)
        if args.command == "derive":
            return _cmd_derive(args)
    except RealEstateAPIError as e:
        # 저장된 파일이 성공 응답이 아니다(resultCode·게이트웨이·HTTP 오류·절단) 또는 hyve 실패 자리.
        return _print_error("error", detail=str(e), **error_fields(e))
    except ValueError as e:
        return _print_error("error", "args", str(e))

    parser.print_help()
    return 1


def _cmd_rone_plan(args: argparse.Namespace) -> int:
    try:
        plan = rone_plan(args.index_type, args.start_month, args.end_month)
    except ValueError as e:
        return _print_error("error", "argument", str(e), rc=2)
    if args.write:
        plan["plan_files"] = write_plans(args.write, plan["calls"])
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def _cmd_rone(args: argparse.Namespace) -> int:
    if args.max_pages < 1:
        return _print_error("error", "argument", "--max-pages 는 1 이상", rc=2)
    try:
        got = collect_rone(args.input, max_pages=args.max_pages, region=args.region)
    except PriceStatsAPIError as e:
        return _print_error("error", "api", str(e), error_code=e.error_code)
    except InputFileError as e:
        return _print_error("error", e.kind, str(e))
    except IncompleteError as e:
        extra: dict[str, Any] = {
            "total_count": e.total_count,
            "need_pages": e.need_pages,
            "will_truncate": e.will_truncate,
            "max_pages": args.max_pages,
            "next_call_count": len(e.next_calls),
        }
        if args.next_plan:
            extra["plan_files"] = write_plans(args.next_plan, e.next_calls)
            extra["next_calls"] = e.next_calls[:_NEXT_CALLS_PREVIEW]
            extra["next_calls_preview_only"] = len(e.next_calls) > _NEXT_CALLS_PREVIEW
        else:
            extra["next_calls"] = e.next_calls
        return _print_error("error", "incomplete", str(e), **extra)

    results = got.pop("results")
    env = build_stats_envelope("ok", results, **got)
    if args.format == "table":
        _print_rone_table(env)
    else:
        print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def _print_rone_table(env: dict[str, Any]) -> None:
    # 머리는 요청 기간이다 — start_wrttime·end_wrttime 은 앞뒤로 넓힌 요청 창이라 기간으로 옮기면 틀린다(재리뷰 minor 6).
    pf = env.get("period_filter") or {}
    span = f"{pf['from']}~{pf['to']}" if pf.get("from") else f"{env['start_month']}~{env['end_month']}"
    print(f"\n{env['label']} ({span}) — {env['count']}행"
          f" / 받은 {env['scanned_count']}행(요청 창 {env['start_wrttime']}~{env['end_wrttime']})\n")
    print(f"{'시점':<12} {'지역':<30} {'값':>12} {'단위':<6}")
    print("-" * 64)
    for r in env["results"]:
        val = "-" if r["value"] is None else f"{r['value']:,.2f}"
        print(f"{r['period_desc'] or r['period']:<12} {r['region'][:28]:<30} {val:>12} {r['unit']:<6}")
    for w in env.get("warnings") or []:
        print(f"  ⚠️ {w}")
    print()


def _resolve_region(args: argparse.Namespace) -> tuple[str, str]:
    if args.lawd_cd:
        return args.lawd_cd, args.region or args.lawd_cd
    if args.region:
        return resolve_lawd_cd(args.region), args.region
    return "", ""


def _cmd_plan(args: argparse.Namespace) -> int:
    check_month_range(args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)
    run_dir = run_dir_name(PREFIX, lawd_cd, args.start_month, args.end_month, args.tag)
    calls = plan_calls([args.endpoint_type], lawd_cd, args.start_month, args.end_month, run_dir)
    out: dict[str, Any] = {
        "status": "ok", "region": region, "lawd_cd": lawd_cd, "type": args.endpoint_type,
        "start_month": args.start_month, "end_month": args.end_month, "run_dir": run_dir,
        "call_count": len(calls),
    }
    if args.write:
        out.update(write_plan_files(args.write, calls, run_dir))
        out["calls_preview"] = calls_preview(calls)
    else:
        out["calls"] = calls
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _cmd_derive(args: argparse.Namespace) -> int:
    check_month_range(args.start_month, args.end_month)
    span = (args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)

    raw, sources = read_sources(args.input, deal_type="trade", endpoint_type=args.endpoint_type,
                                lawd_cd=lawd_cd or None, month_span=span)
    check_endpoint_fields(args.endpoint_type, raw)
    codes = {s["sgg_cd"] for s in sources} - {""}
    if len(codes) > 1:
        raise ValueError(f"파일의 지역코드가 섞였다({sorted(codes)}) — 한 지역의 파일만 넘긴다")
    lawd_cd = lawd_cd or next(iter(codes), "")
    region = region or lawd_cd

    rep = completeness(sources, month_span=span)
    if not rep["complete"]:
        # 일부 페이지만으로 낸 평균·중위는 조용히 틀린다 — 전량이 아니면 통계를 내지 않는다.
        return _incomplete(args, rep, lawd_cd)

    # 해제 거래(cdealType)는 기본으로 뺀다(W1 리뷰 M6).
    all_items = [normalize_trade_item(x) for x in raw]
    cancelled = sum(1 for x in all_items if is_cancelled(x))
    deal_items = all_items if args.include_cancelled else [x for x in all_items if not is_cancelled(x)]
    stats = derive_stats_from_deals(deal_items, group_by=args.group_by)
    common = dict(region=region, lawd_cd=lawd_cd, type=args.endpoint_type,
                  start_month=args.start_month, end_month=args.end_month, months=rep["months"],
                  excluded={"cancelled": 0 if args.include_cancelled else cancelled},
                  include_cancelled=args.include_cancelled)

    # 그룹 통계면 dict, 전체 통계면 단일 dict
    if isinstance(stats, dict) and args.group_by:
        # 그룹별 결과를 리스트로 변환
        items_list = [{"group": k, **v} for k, v in stats.items()]
        env = build_stats_envelope("ok", items_list, derived_summary=None, **common)
    else:
        env = build_stats_envelope("ok", [], derived_summary=stats, **common)

    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def _incomplete(args: argparse.Namespace, rep: dict[str, Any], lawd_cd: str) -> int:
    """전량 미달 — 더 받을 쪽·다시 받을 달을 알리고, 되면 다음 계획을 쓴다."""
    extra: dict[str, Any] = {
        "warnings": rep["warnings"],
        "missing_pages": {**{m: [1] for m in rep["absent"]}, **rep["missing_pages"]},
        "months": rep["months"],
    }
    detail = "받은 쪽이 전량이 아니다 — 다음 계획의 호출을 받아 폴더의 파일을 전부 넘겨 다시 실행한다"
    if rep["refetch"]:
        extra["refetch"] = rep["refetch"]
        if not args.overwrite:
            extra["need_overwrite"] = True
            detail += (". refetch 의 달은 받는 사이 목록이 바뀌어 1쪽부터 다시 받아야 한다 — 같은 이름을 덮어쓰므로"
                       " 사용자에게 알리고 확인받은 뒤 --overwrite 를 붙여 다시 실행한다")
    try:
        run_dir = run_dir_of(list(args.input), PREFIX)
    except ValueError:
        if args.next_plan:
            raise
        run_dir = ""
    if run_dir and lawd_cd:
        calls = next_calls(rep, args.endpoint_type, lawd_cd, run_dir, refetch=args.overwrite)
        extra["next_call_count"] = len(calls)
        if args.next_plan and calls:
            extra.update(write_plan_files(args.next_plan, calls, run_dir, overwrite=args.overwrite))
            extra["next_calls_preview"] = calls_preview(calls)
        elif calls:
            extra["next_calls"] = calls
    elif args.next_plan:
        raise ValueError("지역코드를 알 수 없어 다음 계획을 쓸 수 없다 — --region 또는 --lawd-cd 를 준다")
    return _print_error("incomplete", "incomplete", detail, **extra)


if __name__ == "__main__":
    sys.exit(main())
