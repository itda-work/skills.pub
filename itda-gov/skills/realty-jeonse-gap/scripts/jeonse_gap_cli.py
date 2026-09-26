"""전세가율·갭 스크리너 CLI.

사용법:
    python3 scripts/jeonse_gap_cli.py screen --region 강남구 --start-month 202601 --end-month 202606
    python3 scripts/jeonse_gap_cli.py screen --region 강남구 --start-month 202601 --end-month 202606 \\
        --min-jeonse-ratio 80 --max-gap 30000
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from data_go_client import RealEstateAPIError
from deals_collector import (
    collect_deals_range,
    normalize_rent_item,
    normalize_trade_item,
)
from env_loader import MissingAPIKeyError, resolve_api_key
from jeonse_gap import (
    build_gap_envelope,
    compute_gap_stats,
    filter_by_threshold,
    join_trade_rent,
)
from lawd_codes import resolve_lawd_cd

_KEY_VAR = "KO_DATA_API_KEY"

_SETUP_GUIDE = (
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
    """에러 JSON을 출력하고 종료코드를 반환한다."""
    print(json.dumps({"status": status, "error": error, "detail": detail},
                     ensure_ascii=False))
    return rc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="전세가율·갭 스크리너",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", choices=["json", "table"], default="json",
                        help="출력 포맷 (기본: json)")
    sub = parser.add_subparsers(dest="command")

    # screen 서브커맨드
    screen = sub.add_parser("screen", help="전세가율·갭 스크리닝")
    screen.add_argument("--region", help="지역명 (예: 강남구)")
    screen.add_argument("--lawd-cd", dest="lawd_cd", help="법정동코드 직접 지정")
    screen.add_argument("--start-month", required=True, metavar="YYYYMM",
                        help="시작 연월")
    screen.add_argument("--end-month", required=True, metavar="YYYYMM",
                        help="종료 연월")
    screen.add_argument("--prop-type", default="apt",
                        choices=["apt", "offi", "rh", "sh"],
                        help="부동산 유형 (기본: apt)")
    screen.add_argument("--min-jeonse-ratio", type=float, default=None,
                        metavar="PCT", help="최소 전세가율")
    screen.add_argument("--max-gap", type=int, default=None,
                        metavar="MANWON", help="최대 갭 (만원 단위)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "screen":
        return _cmd_screen(args)

    parser.print_help()
    return 1


def _cmd_screen(args: argparse.Namespace) -> int:
    """screen 커맨드 — 전세가율·갭 스크리닝 수행."""
    # API 키 확인
    try:
        api_key = resolve_api_key(_KEY_VAR, guide_msg=_SETUP_GUIDE, normalize=True)
    except MissingAPIKeyError as e:
        return _print_error("error", "config", str(e))

    # 지역 코드 확인
    lawd_cd = args.lawd_cd
    region = lawd_cd  # 기본값
    if not lawd_cd:
        if not args.region:
            return _print_error("error", "args", "--region 또는 --lawd-cd 중 하나를 지정하세요.")
        try:
            lawd_cd = resolve_lawd_cd(args.region)
            region = args.region
        except ValueError as e:
            return _print_error("error", "args", str(e))

    prop_type = args.prop_type  # "apt", "offi", "rh", "sh"
    trade_key = f"{prop_type}_trade"
    rent_key = f"{prop_type}_rent"

    try:
        # 매매 수집
        trade_raw = collect_deals_range(
            api_key, lawd_cd, args.start_month, args.end_month, trade_key,
        )
        # 전월세 수집
        rent_raw = collect_deals_range(
            api_key, lawd_cd, args.start_month, args.end_month, rent_key,
        )
    except RealEstateAPIError as e:
        return _print_error("error", "api", str(e))
    except KeyError as e:
        return _print_error("error", "args", f"지원하지 않는 부동산 유형: {e}")

    # 정규화
    trade_items = [normalize_trade_item(x) for x in trade_raw]
    rent_items = [normalize_rent_item(x) for x in rent_raw]

    # 조인 + 갭 산출
    joined = join_trade_rent(trade_items, rent_items)
    stats_items = compute_gap_stats(joined)

    # 필터 적용
    filtered = filter_by_threshold(
        stats_items,
        min_jeonse_ratio=args.min_jeonse_ratio,
        max_gap=args.max_gap,
    )

    # envelope 생성
    envelope = build_gap_envelope(
        "ok", region, filtered,
        min_jeonse_ratio=args.min_jeonse_ratio,
        max_gap=args.max_gap,
        start_month=args.start_month,
        end_month=args.end_month,
        prop_type=prop_type,
    )

    if args.format == "table":
        _print_table(filtered, envelope)
    else:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))

    return 0


def _print_table(items: list[dict[str, Any]], envelope: dict[str, Any]) -> None:
    """테이블 형식 출력."""
    region = envelope.get("region", "")
    count = envelope.get("count", 0)
    print(f"지역: {region} | 총 {count}건")
    print("-" * 70)
    print(f"{'단지명':<20} {'면적':>8} {'매매가(만)':>12} {'전세가(만)':>12} {'전세가율':>8} {'갭(만)':>10}")
    print("-" * 70)
    for item in items:
        print(
            f"{item.get('apt_nm',''):<20}"
            f"{item.get('exclu_use_ar',''):>8}"
            f"{item.get('deal_amount',0):>12,}"
            f"{item.get('deposit',0):>12,}"
            f"{item.get('jeonse_ratio',0):>7.1f}%"
            f"{item.get('gap',0):>10,}"
        )


if __name__ == "__main__":
    sys.exit(main())
