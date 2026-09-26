"""공급·청약 데이터 수집기 CLI.

사용법:
    python3 scripts/supply_cli.py kosis --indicator unsold --start-month 202601 --end-month 202606
    python3 scripts/supply_cli.py subscription --start-month 202601 --end-month 202606
"""
from __future__ import annotations

import argparse
import json
import sys

from env_loader import MissingAPIKeyError, resolve_api_key
from supply import (
    KOSIS_INDICATORS,
    SupplyAPIError,
    build_supply_envelope,
    fetch_kosis_supply,
    fetch_subscription,
)

_SETUP_GUIDE_KOSIS = (
    "KOSIS_API_KEY가 설정되지 않았습니다.\n\n"
    "KOSIS 인증키 발급 방법:\n"
    "  1. https://kosis.kr 회원가입\n"
    "  2. https://kosis.kr/openapi/ 에서 서비스 신청 (자동 승인)\n\n"
    "설정 방법 (택 1):\n"
    '  claude config set env.KOSIS_API_KEY "발급받은_인증키"\n'
    "  또는 .env 파일에: KOSIS_API_KEY=발급받은_인증키\n"
)

_SETUP_GUIDE_KODATA = (
    "KO_DATA_API_KEY가 설정되지 않았습니다.\n\n"
    "공공데이터포털 인증키 발급 방법:\n"
    "  1. https://www.data.go.kr 회원가입\n"
    "  2. 사용할 데이터셋(예: 청약홈)에서 \"활용신청\" 자동 승인\n"
    "  3. 마이페이지 → 오픈API → 인증키 확인\n\n"
    "설정 방법 (택 1):\n"
    '  claude config set env.KO_DATA_API_KEY "발급받은_키"\n'
    "  또는 .env 파일에: KO_DATA_API_KEY=발급받은_키\n"
)


def _print_error(status: str, error: str, detail: str, rc: int = 1) -> int:
    print(json.dumps({"status": status, "error": error, "detail": detail},
                     ensure_ascii=False))
    return rc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="공급·청약 데이터 수집기")
    sub = parser.add_subparsers(dest="command")

    # kosis 서브커맨드
    kosis = sub.add_parser("kosis", help="KOSIS 공급 지표 수집")
    kosis.add_argument("--indicator", required=True,
                       choices=list(KOSIS_INDICATORS.keys()),
                       help="지표 종류")
    kosis.add_argument("--start-month", required=True, metavar="YYYYMM")
    kosis.add_argument("--end-month", required=True, metavar="YYYYMM")

    # subscription 서브커맨드
    sub_cmd = sub.add_parser("subscription", help="청약홈 경쟁률·분양 수집")
    sub_cmd.add_argument("--start-month", required=True, metavar="YYYYMM")
    sub_cmd.add_argument("--end-month", required=True, metavar="YYYYMM")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "kosis":
        return _cmd_kosis(args)
    if args.command == "subscription":
        return _cmd_subscription(args)

    parser.print_help()
    return 1


def _cmd_kosis(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key("KOSIS_API_KEY", guide_msg=_SETUP_GUIDE_KOSIS)
    except MissingAPIKeyError as e:
        return _print_error("error", "config", str(e))

    try:
        items = fetch_kosis_supply(api_key, args.indicator,
                                   args.start_month, args.end_month)
    except SupplyAPIError as e:
        return _print_error("error", "api", str(e))
    except KeyError as e:
        return _print_error("error", "args", str(e))

    env = build_supply_envelope("ok", items, start_month=args.start_month)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def _cmd_subscription(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key("KO_DATA_API_KEY", guide_msg=_SETUP_GUIDE_KODATA, normalize=True)
    except MissingAPIKeyError as e:
        return _print_error("error", "config", str(e))

    try:
        items = fetch_subscription(api_key, args.start_month, args.end_month)
    except SupplyAPIError as e:
        return _print_error("error", "api", str(e))

    env = build_supply_envelope("ok", [], start_month=args.start_month,
                                subscription_items=items)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
