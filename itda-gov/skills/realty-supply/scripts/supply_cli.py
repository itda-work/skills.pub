"""주택 공급·청약 CLI — 호출 계획(plan)과 응답 가공. 파일 입력 전용.

네트워크는 itda-hyve 의 ``http_request``·``batch`` 가 한다(itda-work/skills#45). 이 스크립트는
직접 API 를 부르지 않고 키 값을 보지 않는다.

사용법:
    python3 scripts/supply_cli.py kosis-plan --indicator unsold --start-month 202601 --end-month 202606
    python3 scripts/supply_cli.py kosis --input supply/kosis-unsold-202601-202606.json --region 서울
    python3 scripts/supply_cli.py subscription-plan --start-month 202601 --end-month 202606 --write supply/plan-1.json
    python3 scripts/supply_cli.py subscription --input supply/subscription-202601-202606-p1.json --next-plan supply/plan-next-1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import supply

# --next-plan 을 줬을 때 stdout 에 싣는 호출 수(나머지는 계획 파일에 있다).
_PREVIEW = 3


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _error(kind: str, detail: str, **extra: Any) -> None:
    print(json.dumps({"status": "error", "error": kind, "detail": detail, **extra}, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="주택 공급·청약 — 호출 계획과 응답 가공")
    sub = parser.add_subparsers(dest="command", required=True)

    kp = sub.add_parser("kosis-plan", help="KOSIS 공급 지표를 받을 http_request 호출")
    kp.add_argument("--indicator", required=True, choices=list(supply.KOSIS_INDICATORS), help="지표 종류")
    kp.add_argument("--start-month", required=True, metavar="YYYYMM")
    kp.add_argument("--end-month", required=True, metavar="YYYYMM")

    kc = sub.add_parser("kosis", help="저장한 KOSIS 응답 가공")
    kc.add_argument("--input", required=True, metavar="JSON",
                    help="save_as 로 저장한 응답. 이름 규칙 kosis-<지표>-<시작>-<끝>.json")
    kc.add_argument("--region", default=None, help="지역·분류 이름 부분일치 필터 (예: 서울, 강남구)")

    sp = sub.add_parser("subscription-plan", help="청약홈 분양정보 1쪽 호출")
    sp.add_argument("--start-month", required=True, metavar="YYYYMM")
    sp.add_argument("--end-month", required=True, metavar="YYYYMM")
    sp.add_argument("--per-page", dest="per_page", type=int, default=supply.PER_PAGE,
                    help=f"쪽당 행 수 (기본 {supply.PER_PAGE})")
    sp.add_argument("--write", metavar="FILE", default=None,
                    help="itda-hyve batch 의 plan_file 로 쓸 계획 파일({calls, timeout_sec})을 쓴다")

    sc = sub.add_parser("subscription", help="저장한 청약홈 쪽 파일을 전량 대조·가공")
    sc.add_argument("--input", nargs="+", required=True, metavar="JSON",
                    help="save_as 로 저장한 쪽 파일(들). 이름 규칙 subscription-<시작>-<끝>-p<쪽>.json")
    sc.add_argument("--max-pages", dest="max_pages", type=int, default=supply.MAX_PAGES,
                    help=f"받을 쪽 상한 (기본 {supply.MAX_PAGES}). 넘으면 truncated")
    sc.add_argument("--next-plan", dest="next_plan", metavar="FILE", default=None,
                    help="쪽이 모자라면 더 받을 호출을 batch plan_file 로 쓴다(40개 단위로 나눈다)")
    return parser


def _cmd_kosis_plan(args: argparse.Namespace) -> int:
    _emit(supply.kosis_plan(args.indicator, args.start_month, args.end_month))
    return 0


def _cmd_kosis(args: argparse.Namespace) -> int:
    got = supply.parse_kosis(args.input, region=args.region)
    _emit({
        "status": "ok",
        "indicator": got["indicator"],
        "table": got["table"],
        "start_month": got["start_month"],
        "end_month": got["end_month"],
        "count": len(got["results"]),
        "completeness": "no_baseline",
        "results": got["results"],
        "warnings": got["warnings"],
        "source": got["source"],
    })
    return 0


def _cmd_subscription_plan(args: argparse.Namespace) -> int:
    result = supply.subscription_plan(args.start_month, args.end_month, args.per_page)
    if args.write:
        result["plan_files"] = supply.write_plans(args.write, result["calls"])
    note = supply.subscription_note(args.start_month)
    if note:
        result["note"] = note
    _emit(result)
    return 0


def _cmd_subscription(args: argparse.Namespace) -> int:
    got = supply.collect_subscription(args.input, max_pages=args.max_pages)
    payload: dict[str, Any] = {
        "status": "ok",
        "start_month": got["start_month"],
        "end_month": got["end_month"],
        "count": len(got["items"]),
        "total_count": got["total_count"],
        "need_pages": got["need_pages"],
        "truncated": got["truncated"],
        "pages": got["pages"],
        "results": got["items"],
        "sources": got["sources"],
        "meta": {"subscription_data_start": supply.SUBSCRIPTION_DATA_START_YM},
    }
    note = supply.subscription_note(got["start_month"])
    if note:
        payload["note"] = note
    if got["warnings"]:
        payload["warnings"] = got["warnings"]
    _emit(payload)
    return 0


def _incomplete(args: argparse.Namespace, exc: supply.IncompleteError) -> None:
    extra: dict[str, Any] = dict(exc.extra)
    extra["next_call_count"] = len(exc.next_calls)
    if getattr(args, "next_plan", None) and exc.next_calls:
        extra["plan_files"] = supply.write_plans(args.next_plan, exc.next_calls)
        extra["next_calls_preview"] = exc.next_calls[:_PREVIEW]
    else:
        extra["next_calls"] = exc.next_calls
    _error("incomplete", str(exc), **extra)


def main(argv: list[str] | None = None) -> int:
    """종료 코드: 0 성공, 1 가공 실패(입력·API 오류·쪽 모자람), 2 인자 오류."""
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    commands = {
        "kosis-plan": _cmd_kosis_plan,
        "kosis": _cmd_kosis,
        "subscription-plan": _cmd_subscription_plan,
        "subscription": _cmd_subscription,
    }
    try:
        return commands[args.command](args)
    except ValueError as exc:
        _error("argument", str(exc))
        return 2
    except supply.SupplyAPIError as exc:
        _error("api", str(exc), error_code=exc.error_code)
        return 1
    except supply.InputFileError as exc:
        _error(exc.kind, str(exc))
        return 1
    except supply.IncompleteError as exc:
        _incomplete(args, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
