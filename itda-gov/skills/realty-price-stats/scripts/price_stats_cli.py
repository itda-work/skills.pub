"""가격지수·시세 통계 CLI.

사용법:
    python3 scripts/price_stats_cli.py rone --index-type weekly --start-month 202601 --end-month 202606
    python3 scripts/price_stats_cli.py derive --region 강남구 --start-month 202601 --end-month 202601 --type apt_trade
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from data_go_client import RealEstateAPIError
from deals_collector import collect_deals_range, normalize_trade_item
from env_loader import MissingAPIKeyError, resolve_api_key
from lawd_codes import resolve_lawd_cd
from price_stats import (
    RONE_INDEX_TYPES,
    PriceStatsAPIError,
    build_stats_envelope,
    derive_stats_from_deals,
    fetch_rone_index,
)

_SETUP_GUIDE_RONE = (
    "RONE_API_KEY가 설정되지 않았습니다.\n\n"
    "R-ONE 부동산통계 인증키 발급 방법:\n"
    "  1. https://www.r-one.co.kr 회원가입\n"
    "  2. 오픈API → API 신청 → 인증키 발급\n\n"
    "설정 방법 (택 1):\n"
    '  claude config set env.RONE_API_KEY "발급받은_키"\n'
    "  또는 .env 파일에: RONE_API_KEY=발급받은_키\n"
)

_SETUP_GUIDE_KODATA = (
    "KO_DATA_API_KEY가 설정되지 않았습니다.\n\n"
    "공공데이터포털 인증키 발급 방법:\n"
    "  1. https://www.data.go.kr 회원가입\n"
    "  2. 사용할 데이터셋(예: 부동산 실거래가)에서 \"활용신청\" 자동 승인\n"
    "  3. 마이페이지 → 오픈API → 인증키 확인\n\n"
    "설정 방법 (택 1):\n"
    '  claude config set env.KO_DATA_API_KEY "발급받은_키"\n'
    "  또는 .env 파일에: KO_DATA_API_KEY=발급받은_키\n"
)


def _print_error(status: str, error: str, detail: str, rc: int = 1) -> int:
    print(json.dumps({"status": status, "error": error, "detail": detail},
                     ensure_ascii=False))
    return rc


def _load_deals_items(
    api_key: str,
    lawd_cd: str,
    start_month: str,
    end_month: str,
    endpoint_key: str,
) -> list[dict[str, Any]]:
    """realty-deals에서 정규화된 매매 항목을 수집한다."""
    raw = collect_deals_range(api_key, lawd_cd, start_month, end_month, endpoint_key)
    return [normalize_trade_item(x) for x in raw]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="가격지수·시세 통계")
    sub = parser.add_subparsers(dest="command")

    # rone 서브커맨드
    rone = sub.add_parser("rone", help="R-ONE 가격지수 수집")
    rone.add_argument("--index-type", required=True,
                      choices=list(RONE_INDEX_TYPES.keys()),
                      help="지수 유형")
    rone.add_argument("--start-month", required=True, metavar="YYYYMM")
    rone.add_argument("--end-month", required=True, metavar="YYYYMM")

    # derive 서브커맨드
    derive = sub.add_parser("derive", help="realty-deals 파생 통계")
    derive.add_argument("--region", help="지역명 (예: 강남구)")
    derive.add_argument("--lawd-cd", dest="lawd_cd", help="법정동코드 직접 지정")
    derive.add_argument("--start-month", required=True, metavar="YYYYMM")
    derive.add_argument("--end-month", required=True, metavar="YYYYMM")
    derive.add_argument("--type", dest="endpoint_type", default="apt_trade",
                        help="엔드포인트 유형 (기본: apt_trade)")
    derive.add_argument("--group-by", dest="group_by", default=None,
                        help="그룹핑 필드 (예: apt_nm)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "rone":
        return _cmd_rone(args)
    if args.command == "derive":
        return _cmd_derive(args)

    parser.print_help()
    return 1


def _cmd_rone(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key("RONE_API_KEY", guide_msg=_SETUP_GUIDE_RONE)
    except MissingAPIKeyError as e:
        return _print_error("error", "config", str(e))

    try:
        items = fetch_rone_index(api_key, args.index_type,
                                 args.start_month, args.end_month)
    except PriceStatsAPIError as e:
        return _print_error("error", "api", str(e))
    except KeyError as e:
        return _print_error("error", "args", str(e))

    env = build_stats_envelope("ok", items)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def _cmd_derive(args: argparse.Namespace) -> int:
    try:
        api_key = resolve_api_key("KO_DATA_API_KEY", guide_msg=_SETUP_GUIDE_KODATA, normalize=True)
    except MissingAPIKeyError as e:
        return _print_error("error", "config", str(e))

    lawd_cd = args.lawd_cd
    region = lawd_cd or ""
    if not lawd_cd:
        if not args.region:
            return _print_error("error", "args", "--region 또는 --lawd-cd 중 하나를 지정하세요.")
        try:
            lawd_cd = resolve_lawd_cd(args.region)
            region = args.region
        except ValueError as e:
            return _print_error("error", "args", str(e))

    try:
        deal_items = _load_deals_items(
            api_key, lawd_cd, args.start_month, args.end_month, args.endpoint_type,
        )
    except RealEstateAPIError as e:
        return _print_error("error", "api", str(e))
    except KeyError as e:
        return _print_error("error", "args", str(e))

    stats = derive_stats_from_deals(deal_items, group_by=args.group_by)

    # 그룹 통계면 dict, 전체 통계면 단일 dict
    if isinstance(stats, dict) and args.group_by:
        # 그룹별 결과를 리스트로 변환
        items_list = [{"group": k, **v} for k, v in stats.items()]
        env = build_stats_envelope("ok", items_list, derived_summary=None)
    else:
        env = build_stats_envelope("ok", [], derived_summary=stats,
                                    region=region,
                                    start_month=args.start_month,
                                    end_month=args.end_month)

    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
