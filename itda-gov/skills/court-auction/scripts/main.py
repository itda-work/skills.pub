#!/usr/bin/env python3
"""court-auction CLI — 대법원 법원경매정보(courtauction.go.kr) read-only 조회.

사용 예 (저장소 루트 기준):
    python3 itda-gov/skills/court-auction/scripts/main.py codes courts
    python3 itda-gov/skills/court-auction/scripts/main.py notices --date 2026-04 --court-code B000210
    python3 itda-gov/skills/court-auction/scripts/main.py case --court-code B000210 --case-number 2024타경100001
    python3 itda-gov/skills/court-auction/scripts/main.py search --sido 서울특별시 --usage-large 건물 --price-max 500000000

모든 옵션은 서브커맨드 **뒤**에 둔다. 결과는 JSON(stdout)이며 Claude가 한국어로
요약해 전달한다. 차단/오류는 ``{"ok": false, "error": ...}`` + 종료코드 4.
read-only — 입찰 자동화는 제공하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys

if sys.version_info < (3, 10):  # pragma: no cover - 런타임 가드
    sys.exit("court-auction은 Python 3.10+ 가 필요합니다.")

from codetables import list_bid_types, list_region_codes, list_usage_codes
from courtauction_adapter import CourtAuctionClient
from queries import (
    get_case,
    get_court_codes,
    get_sale_notice_detail,
    search_properties,
    search_sale_notices,
)


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _finish(ok: bool, result, reason: str) -> int:
    """조회 결과를 JSON으로 출력하고 종료코드 반환(0 성공 / 4 실패)."""
    if not ok:
        _print({"ok": False, "error": reason})
        return 4
    payload = {"ok": True}
    if isinstance(result, dict):
        payload.update(result)
    else:
        payload["result"] = result
    _print(payload)
    return 0


def _range(lo, hi) -> dict | None:
    out = {}
    if lo is not None:
        out["min"] = lo
    if hi is not None:
        out["max"] = hi
    return out or None


def cmd_codes(args: argparse.Namespace, client: CourtAuctionClient) -> int:
    if args.kind == "courts":
        return _finish(*get_court_codes(client))
    table = {
        "bid-types": list_bid_types,
        "usages": list_usage_codes,
        "regions": list_region_codes,
    }[args.kind]()
    _print({"ok": True, "count": len(table), "items": table})
    return 0


def cmd_notices(args: argparse.Namespace, client: CourtAuctionClient) -> int:
    return _finish(
        *search_sale_notices(
            client,
            date=args.date,
            court_code=args.court_code,
            bid_type=args.bid_type,
            include_raw=not args.no_raw,
        )
    )


def cmd_notice_detail(args: argparse.Namespace, client: CourtAuctionClient) -> int:
    raw = {
        "cortOfcCd": args.court_code,
        "dspslDxdyYmd": args.sale_date,
        "jdbnCd": args.jdbn_cd,
        "bidDvsCd": args.bid_dvs or "",
        "bidBgngYmd": args.bid_bgng or "",
        "bidEndYmd": args.bid_end or "",
    }
    return _finish(*get_sale_notice_detail(client, {"raw": raw}, include_raw=not args.no_raw))


def cmd_case(args: argparse.Namespace, client: CourtAuctionClient) -> int:
    return _finish(
        *get_case(
            client,
            court_code=args.court_code,
            case_number=args.case_number,
            include_raw=not args.no_raw,
        )
    )


def cmd_search(args: argparse.Namespace, client: CourtAuctionClient) -> int:
    return _finish(
        *search_properties(
            client,
            include_raw=not args.no_raw,
            page=args.page,
            page_size=args.page_size,
            court_code=args.court_code or "",
            bid_type=args.bid_type,
            region={"sido": args.sido, "sigungu": args.sigungu, "dong": args.dong},
            usage={"large": args.usage_large, "medium": args.usage_medium, "small": args.usage_small},
            sale_date={"from": args.sale_from, "to": args.sale_to},
            price_range=_range(args.price_min, args.price_max),
            appraised_price_range=_range(args.appraised_min, args.appraised_max),
            area=_range(args.area_min, args.area_max),
            flbd_count=_range(args.flbd_min, args.flbd_max),
        )
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--min-delay", type=float, default=2.0, help="호출 간 최소 지연(초, 기본 2.0)")
    common.add_argument("--max-calls", type=int, default=10, help="세션 호출 budget(기본 10)")
    common.add_argument("--timeout", type=int, default=15, help="요청 타임아웃(초, 기본 15)")
    common.add_argument("--no-raw", action="store_true", help="raw 패스스루 필드 제외(출력 축소)")

    parser = argparse.ArgumentParser(
        prog="court-auction",
        description="대법원 법원경매정보 read-only 조회 (참고용 — 입찰 전 법원 원문 재확인 필수)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_codes = sub.add_parser("codes", parents=[common], help="코드표 (법원/입찰구분/용도/지역)")
    p_codes.add_argument("kind", choices=["courts", "bid-types", "usages", "regions"])
    p_codes.set_defaults(func=cmd_codes)

    p_notices = sub.add_parser("notices", parents=[common], help="매각공고 목록")
    p_notices.add_argument("--date", required=True, help="매각기일 월(YYYY-MM) 또는 일(YYYY-MM-DD)")
    p_notices.add_argument("--court-code", help="법원사무소코드(예: B000210). 비우면 전체")
    p_notices.add_argument("--bid-type", choices=["date", "period"], help="기일입찰/기간입찰. 비우면 둘 다")
    p_notices.set_defaults(func=cmd_notices)

    p_detail = sub.add_parser("notice-detail", parents=[common], help="공고 펼치기(사건/물건) — notices의 raw 토큰 사용")
    p_detail.add_argument("--court-code", required=True, help="법원사무소코드(raw.cortOfcCd)")
    p_detail.add_argument("--sale-date", required=True, help="매각기일 YYYYMMDD(raw.dspslDxdyYmd)")
    p_detail.add_argument("--jdbn-cd", required=True, help="재판부 토큰(raw.jdbnCd — notices 응답에서 복사)")
    p_detail.add_argument("--bid-dvs", help="입찰구분 코드(raw.bidDvsCd)")
    p_detail.add_argument("--bid-bgng", help="입찰시작일 YYYYMMDD")
    p_detail.add_argument("--bid-end", help="입찰종료일 YYYYMMDD")
    p_detail.set_defaults(func=cmd_notice_detail)

    p_case = sub.add_parser("case", parents=[common], help="사건번호 직접 조회")
    p_case.add_argument("--court-code", required=True, help="법원사무소코드(예: B000210)")
    p_case.add_argument("--case-number", required=True, help="사건번호(예: 2024타경100001 또는 2024-100001)")
    p_case.set_defaults(func=cmd_case)

    p_search = sub.add_parser("search", parents=[common], help="물건 자유 조건검색")
    p_search.add_argument("--sido", help="시도명 또는 코드(예: 서울특별시/11)")
    p_search.add_argument("--sigungu", help="시군구 코드(5자리, 예: 11680)")
    p_search.add_argument("--dong", help="읍면동 코드(8자리, 예: 11680101)")
    p_search.add_argument("--usage-large", help="용도 대분류(토지/건물/기타 또는 코드 — 부동산 한정, 동산 미지원)")
    p_search.add_argument("--usage-medium", help="용도 중분류(코드)")
    p_search.add_argument("--usage-small", help="용도 소분류(아파트 또는 코드)")
    p_search.add_argument("--price-min", help="최저매각가 하한(원)")
    p_search.add_argument("--price-max", help="최저매각가 상한(원)")
    p_search.add_argument("--appraised-min", help="감정평가액 하한(원)")
    p_search.add_argument("--appraised-max", help="감정평가액 상한(원)")
    p_search.add_argument("--area-min", help="면적 하한(㎡)")
    p_search.add_argument("--area-max", help="면적 상한(㎡)")
    p_search.add_argument("--flbd-min", help="유찰횟수 하한(정수)")
    p_search.add_argument("--flbd-max", help="유찰횟수 상한(정수)")
    p_search.add_argument("--sale-from", help="매각기일 시작 YYYYMMDD")
    p_search.add_argument("--sale-to", help="매각기일 종료 YYYYMMDD")
    p_search.add_argument("--court-code", help="법원사무소코드")
    p_search.add_argument("--bid-type", choices=["date", "period"], help="기일입찰/기간입찰")
    p_search.add_argument("--page", type=int, default=1, help="페이지(기본 1)")
    p_search.add_argument("--page-size", type=int, default=10, help="페이지 크기(10/20/50/100, 기본 10)")
    p_search.set_defaults(func=cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = CourtAuctionClient(min_delay=args.min_delay, max_calls=args.max_calls, timeout=args.timeout)
    return args.func(args, client)


if __name__ == "__main__":
    raise SystemExit(main())
