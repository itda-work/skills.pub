"""전세가율·갭 스크리너 CLI — 호출 계획(plan)과 응답 가공(screen). 파일 입력 전용.

네트워크는 itda-hyve 가 한다(itda-work/skills#45). ``plan`` 이 batch ``plan_file`` 로 쓸 호출 목록을
만들고, ``screen`` 이 그렇게 받아 둔 매매·전월세 응답 XML 을 읽어 전량 대조·조인·전세가율 계산만 한다.
모자라면 ``--next-plan`` 으로 다음 계획을 쓴다 — 모델이 쪽 번호·저장 이름을 손으로 옮기지 않는다.

사용법:
    python3 scripts/jeonse_gap_cli.py plan --region 강남구 --start-month 202607 --end-month 202608 \\
        --write "$D/plan-1.json"
    python3 scripts/jeonse_gap_cli.py screen --region 강남구 --start-month 202607 --end-month 202608 \\
        --trade-input "$D/apt_trade-*.xml" --rent-input "$D/apt_rent-*.xml" \\
        --next-plan "$D/plan-2.json" --min-jeonse-ratio 80 --max-gap 30000
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from data_go_client import RealEstateAPIError, error_fields
from deals_collector import (
    calls_preview,
    check_endpoint_fields,
    check_month_range,
    completeness,
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
from jeonse_gap import (
    build_gap_envelope,
    compute_gap_stats,
    filter_by_threshold,
    join_trade_rent,
)
from lawd_codes import LAWD_CD_MAP, resolve_lawd_cd

# 저장 폴더 머리 — 회차 폴더는 ``jeonse-gap/<코드>-<시작월>-<종료월>[-<tag>]``.
PREFIX = "jeonse-gap"


def _print_json(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _print_error(status: str, error: str | None = None, detail: str = "", rc: int = 1, **extra: Any) -> int:
    """에러 JSON을 출력하고 종료코드를 반환한다."""
    print(json.dumps({"status": status, "error": error, "detail": detail, **extra},
                     ensure_ascii=False))
    return rc


def _add_region(p: argparse.ArgumentParser, *, required: bool) -> None:
    g = p.add_mutually_exclusive_group(required=required)
    g.add_argument("--region", help="지역명 (예: 강남구) — regions 목록의 이름")
    g.add_argument("--lawd-cd", dest="lawd_cd", help="법정동코드 5자리")


def _add_span(p: argparse.ArgumentParser) -> None:
    p.add_argument("--start-month", required=True, metavar="YYYYMM", help="요청 기간 시작월")
    p.add_argument("--end-month", required=True, metavar="YYYYMM", help="요청 기간 종료월")
    p.add_argument("--prop-type", default="apt", choices=["apt", "offi", "rh", "sh"],
                   help="부동산 유형 (기본: apt) — 받은 엔드포인트와 같아야 한다")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="전세가율·갭 스크리너 (itda-hyve 호출 계획 + 저장한 응답 XML 가공)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", choices=["json", "table"], default="json",
                        help="출력 포맷 (기본: json)")
    sub = parser.add_subparsers(dest="command")

    # plan — 1차 호출 계획(달마다 매매·전월세 1쪽)
    plan = sub.add_parser("plan", help="itda-hyve batch 호출 계획(달마다 매매·전월세 1쪽)")
    _add_region(plan, required=True)
    _add_span(plan)
    plan.add_argument("--tag", default=None,
                      help="같은 지역·기간을 다시 받을 때 회차 폴더 끝에 붙일 영숫자(예: 2)")
    plan.add_argument("--write", metavar="FILE", default=None,
                      help="batch plan_file 로 쓸 계획 파일 — 회차 폴더 안(예: \"$D/plan-1.json\")")

    # screen 서브커맨드
    screen = sub.add_parser("screen", help="전세가율·갭 스크리닝")
    screen.add_argument("--trade-input", nargs="+", required=True, metavar="XML",
                        help="매매 응답 XML 파일(들)·글로브. 달·페이지마다 1개")
    screen.add_argument("--rent-input", nargs="+", required=True, metavar="XML",
                        help="전월세 응답 XML 파일(들)·글로브. 달·페이지마다 1개")
    _add_region(screen, required=False)
    _add_span(screen)
    screen.add_argument("--min-jeonse-ratio", type=float, default=None,
                        metavar="PCT", help="최소 전세가율")
    screen.add_argument("--max-gap", type=int, default=None,
                        metavar="MANWON", help="최대 갭 (만원 단위)")
    screen.add_argument("--include-cancelled", action="store_true",
                        help="해제된 매매(cdealType)도 조인에 넣는다 (기본: 뺀다)")
    screen.add_argument("--next-plan", dest="next_plan", metavar="FILE", default=None,
                        help="전량 미달이면 더 받을 호출을 batch plan_file 로 쓴다(회차 폴더 안)")
    screen.add_argument("--overwrite", action="store_true",
                        help="다시 받을 달(refetch)을 다음 계획에 넣고 덮어쓰기를 켠다 — 사용자 확인 뒤에만")

    # regions 서브커맨드 — 호출 전에 법정동코드를 확정한다(네트워크 불요)
    sub.add_parser("regions", help="지역명-법정동코드 목록 출력 (입력 불요)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. 종료 코드: 0 성공, 1 실패(인자·입력·API·hyve 오류, 전량 미달)."""
    # Windows 콘솔(cp949)에서 한국어 출력이 UnicodeEncodeError 로 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            return _cmd_plan(args)
        if args.command == "screen":
            return _cmd_screen(args)
    except RealEstateAPIError as e:
        # 저장된 파일이 성공 응답이 아니다(resultCode·게이트웨이·HTTP 오류·절단) 또는 hyve 실패 자리.
        return _print_error("error", detail=str(e), **error_fields(e))
    except ValueError as e:
        return _print_error("error", "args", str(e))
    if args.command == "regions":
        regions = [{"name": n, "lawd_cd": c} for n, c in sorted(LAWD_CD_MAP.items())]
        _print_json({"status": "ok", "count": len(regions), "regions": regions})
        return 0

    parser.print_help()
    return 1


def _resolve_region(args: argparse.Namespace) -> tuple[str, str]:
    """(법정동코드, 라벨). 지역명이면 코드로 푼다(없는 이름은 ValueError)."""
    if args.lawd_cd:
        return args.lawd_cd, args.region or args.lawd_cd
    if args.region:
        return resolve_lawd_cd(args.region), args.region
    return "", ""


def _cmd_plan(args: argparse.Namespace) -> int:
    """plan — 달마다 매매·전월세 1쪽을 받는 batch 호출 목록."""
    check_month_range(args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)
    run_dir = run_dir_name(PREFIX, lawd_cd, args.start_month, args.end_month, args.tag)
    types = [f"{args.prop_type}_trade", f"{args.prop_type}_rent"]
    calls = plan_calls(types, lawd_cd, args.start_month, args.end_month, run_dir)
    out: dict[str, Any] = {
        "status": "ok", "region": region, "lawd_cd": lawd_cd, "prop_type": args.prop_type,
        "start_month": args.start_month, "end_month": args.end_month, "run_dir": run_dir,
        "call_count": len(calls),
    }
    if args.write:
        out.update(write_plan_files(args.write, calls, run_dir))
        out["calls_preview"] = calls_preview(calls)
    else:
        out["calls"] = calls
    _print_json(out)
    return 0


def _cmd_screen(args: argparse.Namespace) -> int:
    """screen 커맨드 — 저장된 매매·전월세 응답으로 전세가율·갭 스크리닝."""
    check_month_range(args.start_month, args.end_month)
    span = (args.start_month, args.end_month)
    lawd_cd, region = _resolve_region(args)
    trade_type, rent_type = f"{args.prop_type}_trade", f"{args.prop_type}_rent"

    trade_raw, trade_sources = read_sources(
        args.trade_input, deal_type="trade", endpoint_type=trade_type, lawd_cd=lawd_cd or None, month_span=span)
    rent_raw, rent_sources = read_sources(
        args.rent_input, deal_type="rent", endpoint_type=rent_type, lawd_cd=lawd_cd or None, month_span=span)
    check_endpoint_fields(trade_type, trade_raw, "--prop-type")
    check_endpoint_fields(rent_type, rent_raw, "--prop-type")
    codes = {s["sgg_cd"] for s in trade_sources + rent_sources} - {""}
    if len(codes) > 1:
        raise ValueError(f"매매·전월세 파일의 지역코드가 섞였다({sorted(codes)}) — 한 지역의 파일만 넘긴다")
    lawd_cd = lawd_cd or next(iter(codes), "")
    region = region or lawd_cd

    trade_rep = completeness(trade_sources, month_span=span)
    rent_rep = completeness(rent_sources, month_span=span)
    if not (trade_rep["complete"] and rent_rep["complete"]):
        # 전량이 아니면 결과를 내지 않는다 — 부분 조인은 전세가율을 조용히 틀리게 만든다.
        return _incomplete(args, trade_rep, rent_rep, lawd_cd, trade_type, rent_type)

    # 정규화 — 해제 거래(cdealType)는 기본으로 뺀다(W1 리뷰 M6).
    trade_all = [normalize_trade_item(x) for x in trade_raw]
    cancelled = sum(1 for t in trade_all if is_cancelled(t))
    trade_items = trade_all if args.include_cancelled else [t for t in trade_all if not is_cancelled(t)]
    rent_items = [normalize_rent_item(x) for x in rent_raw]
    jeonse = sum(1 for r in rent_items if r.get("monthly_rent", 0) == 0)

    # 조인(전세만·보증금 중위값) + 갭 산출
    joined = join_trade_rent(trade_items, rent_items)
    stats_items = compute_gap_stats(joined)

    # 필터 적용
    filtered = filter_by_threshold(
        stats_items,
        min_jeonse_ratio=args.min_jeonse_ratio,
        max_gap=args.max_gap,
    )

    warnings = []
    unkeyed = sum(1 for t in trade_items if not (t.get("apt_nm") and t.get("exclu_use_ar")))
    if unkeyed:
        warnings.append(
            f"매매 {unkeyed}건은 단지명이나 전용면적이 없어 조인하지 않았다"
            + (" — 단독다가구(sh) 응답에는 단지명·전용면적이 없을 수 있다" if args.prop_type == "sh" else "")
        )
    envelope = build_gap_envelope(
        "ok", region, filtered,
        min_jeonse_ratio=args.min_jeonse_ratio,
        max_gap=args.max_gap,
        lawd_cd=lawd_cd,
        start_month=args.start_month,
        end_month=args.end_month,
        prop_type=args.prop_type,
        months={"trade": trade_rep["months"], "rent": rent_rep["months"]},
        counts={
            "trade": len(trade_all), "trade_used": len(trade_items),
            "rent": len(rent_items), "rent_jeonse": jeonse, "joined": len(joined),
        },
        excluded={"cancelled_trade": 0 if args.include_cancelled else cancelled},
        include_cancelled=args.include_cancelled,
        deposit_basis="전세(월세 0) 보증금 중위값",
        warnings=warnings,
    )

    if args.format == "table":
        _print_table(filtered, envelope)
    else:
        _print_json(envelope)

    return 0


def _incomplete(
    args: argparse.Namespace, trade_rep: dict[str, Any], rent_rep: dict[str, Any],
    lawd_cd: str, trade_type: str, rent_type: str,
) -> int:
    """전량 미달 — 더 받을 쪽·다시 받을 달을 알리고, 되면 다음 계획을 쓴다."""
    warnings = [f"매매 {w}" for w in trade_rep["warnings"]] + [f"전월세 {w}" for w in rent_rep["warnings"]]
    todo = {
        "trade": {**{m: [1] for m in trade_rep["absent"]}, **trade_rep["missing_pages"]},
        "rent": {**{m: [1] for m in rent_rep["absent"]}, **rent_rep["missing_pages"]},
    }
    refetch = {"trade": trade_rep["refetch"], "rent": rent_rep["refetch"]}
    extra: dict[str, Any] = {
        "warnings": warnings,
        "missing_pages": todo,
        "months": {"trade": trade_rep["months"], "rent": rent_rep["months"]},
    }
    detail = "받은 쪽이 전량이 아니다 — 다음 계획의 호출을 받아 폴더의 파일을 전부 넘겨 다시 실행한다"
    if refetch["trade"] or refetch["rent"]:
        extra["refetch"] = refetch
        if not args.overwrite:
            extra["need_overwrite"] = True
            detail += (". refetch 의 달은 받는 사이 목록이 바뀌어 1쪽부터 다시 받아야 한다 — 같은 이름을 덮어쓰므로"
                       " 사용자에게 알리고 확인받은 뒤 --overwrite 를 붙여 다시 실행한다")
    try:
        run_dir = run_dir_of(list(args.trade_input) + list(args.rent_input), PREFIX)
    except ValueError:
        if args.next_plan:
            raise
        run_dir = ""
    if run_dir and lawd_cd:
        calls = (next_calls(trade_rep, trade_type, lawd_cd, run_dir, refetch=args.overwrite)
                 + next_calls(rent_rep, rent_type, lawd_cd, run_dir, refetch=args.overwrite))
        extra["next_call_count"] = len(calls)
        if args.next_plan and calls:
            extra.update(write_plan_files(args.next_plan, calls, run_dir, overwrite=args.overwrite))
            extra["next_calls_preview"] = calls_preview(calls)
        elif calls:
            extra["next_calls"] = calls
    elif args.next_plan:
        raise ValueError("지역코드를 알 수 없어 다음 계획을 쓸 수 없다 — --region 또는 --lawd-cd 를 준다")
    return _print_error("incomplete", "incomplete", detail, **extra)


def _print_table(items: list[dict[str, Any]], envelope: dict[str, Any]) -> None:
    """테이블 형식 출력."""
    region = envelope.get("region", "")
    count = envelope.get("count", 0)
    print(f"지역: {region} | 총 {count}건")
    print("-" * 70)
    print(f"{'단지명':<20} {'면적':>8} {'매매가(만)':>12} {'전세가(만)':>12} {'전세가율':>8} {'갭(만)':>10} {'전세건':>6}")
    print("-" * 70)
    for item in items:
        print(
            f"{item.get('apt_nm',''):<20}"
            f"{item.get('exclu_use_ar',''):>8}"
            f"{item.get('deal_amount',0):>12,}"
            f"{item.get('deposit',0):>12,}"
            f"{item.get('jeonse_ratio',0):>7.1f}%"
            f"{item.get('gap',0):>10,}"
            f"{item.get('jeonse_count',0):>6}"
        )
    print("-" * 70)
    print(f"전세가 = {envelope.get('deposit_basis', '')} · 해제 매매 제외 {envelope.get('excluded', {}).get('cancelled_trade', 0)}건")


if __name__ == "__main__":
    sys.exit(main())
