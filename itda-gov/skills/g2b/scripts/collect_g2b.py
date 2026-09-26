"""나라장터 입찰공고 조회 CLI.

표준 JSON 출력 포맷으로 나라장터 입찰공고를 조회.

사용법:
    python3 scripts/collect_g2b.py
    python3 scripts/collect_g2b.py --from 2026-03-01 --to 2026-03-18
    python3 scripts/collect_g2b.py --keyword "소프트웨어"
    python3 scripts/collect_g2b.py --rows 50 --format json
    python3 scripts/collect_g2b.py --detail
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

import env_loader
import g2b_api

# 공공데이터포털 API 키 환경변수
_KEY_VAR = "KO_DATA_API_KEY"

_SETUP_GUIDE = (
    "KO_DATA_API_KEY가 설정되지 않았습니다.\n\n"
    "공공데이터포털 API 키 발급 방법:\n"
    "  1. https://www.data.go.kr 회원가입\n"
    "  2. '조달청_나라장터 공공데이터개방표준서비스' 활용 신청\n"
    "  3. 발급된 일반 인증키(Decoding) 사용\n\n"
    "설정 방법: 작업 폴더 루트(예: outputs/)에 .env 파일을 만들고 키를 추가하세요.\n"
    "  KO_DATA_API_KEY=발급받은_키\n"
    '  (또는 일회성으로 --api-key "발급받은_키")\n'
)


def _resolve_key(cli_arg: str | None) -> str:
    return env_loader.resolve_api_key(_KEY_VAR, cli_arg, _SETUP_GUIDE, normalize=True)


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성."""
    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description="나라장터 입찰공고를 조회합니다."
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        default=week_ago,
        help=f"조회 시작일 YYYY-MM-DD (기본: {week_ago}, 7일 전)",
    )
    parser.add_argument(
        "--to",
        default=today,
        help=f"조회 종료일 YYYY-MM-DD (기본: {today}, 오늘)",
    )
    parser.add_argument(
        "--keyword",
        default=None,
        help="공고명 키워드 필터 (부분 일치, 대소문자 무시)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10,
        help=(
            "단일 페이지 조회 모드: 페이지당 결과 수 (기본: 10, 최대: 999). "
            "--rows 또는 --page를 명시하면 자동 전체 순회를 끄고 해당 페이지만 "
            "조회한다. 미지정 시(특히 키워드 검색) 날짜범위 전 페이지를 자동 순회."
        ),
    )
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help=(
            "단일 페이지 조회 모드: 페이지 번호 (기본: 1). --rows/--page 중 "
            "하나라도 명시하면 자동 전체 순회를 끄고 해당 페이지만 조회한다."
        ),
    )
    parser.add_argument(
        "--max-pages",
        dest="max_pages",
        type=int,
        default=g2b_api._MAX_PAGES,
        help=(
            f"자동 전체 순회 시 순회 상한 페이지 수 "
            f"(기본: {g2b_api._MAX_PAGES}, 페이지당 최대 999건). "
            "상한 도달 시 미조회분 경고를 출력한다."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="json",
        help="출력 형식 table/json (기본: json)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        default=False,
        help="상세 출력 (입찰자격, 담당자, 일정 등 전체 정보)",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="인증키 직접 지정 (기본: KO_DATA_API_KEY 환경변수)",
    )
    return parser


def _filter_by_keyword(items: list[dict], keyword: str) -> list[dict]:
    """공고명(bidNtceNm) 기준으로 키워드를 포함하는 항목만 반환.

    대소문자를 무시하는 부분 일치 필터링.

    Args:
        items: 입찰공고 목록.
        keyword: 검색 키워드.

    Returns:
        키워드가 공고명에 포함된 항목만 담은 리스트.
    """
    kw_lower = keyword.lower()
    return [
        item for item in items
        if kw_lower in item.get("bidNtceNm", "").lower()
    ]


# API 필드명 → 한국어 레이블 매핑
_FIELD_LABELS: dict[str, str] = {
    "bidNtceNo": "입찰공고번호",
    "bidNtceOrd": "입찰공고차수",
    "refNtceNo": "참조공고번호",
    "refNtceOrd": "참조공고차수",
    "ppsNtceYn": "조달청공고여부",
    "bidNtceNm": "공고명",
    "bidNtceSttusNm": "공고종류",
    "bidNtceDate": "입찰공고일",
    "bidNtceBgn": "입찰공고시각",
    "bsnsDivNm": "업무구분",
    "intrntnlBidYn": "국제입찰여부",
    "cmmnCntrctYn": "공동계약여부",
    "cmmnReciptMethdNm": "공동수급방식",
    "elctrnBidYn": "전자입찰여부",
    "cntrctCnclsSttusNm": "계약구분",
    "cntrctCnclsMthdNm": "계약방법",
    "bidwinrDcsnMthdNm": "낙찰방법",
    "ntceInsttNm": "공고기관",
    "ntceInsttCd": "공고기관코드",
    "ntceInsttOfclDeptNm": "공고담당부서",
    "ntceInsttOfclNm": "공고담당자",
    "ntceInsttOfclTel": "공고담당전화",
    "ntceInsttOfclEmailAdrs": "공고담당이메일",
    "dmndInsttNm": "수요기관",
    "dmndInsttCd": "수요기관코드",
    "dmndInsttOfclDeptNm": "수요담당부서",
    "dmndInsttOfclNm": "수요담당자",
    "dmndInsttOfclTel": "수요담당전화",
    "dmndInsttOfclEmailAdrs": "수요담당이메일",
    "presnatnOprtnYn": "현장설명여부",
    "presnatnOprtnDate": "현장설명일",
    "presnatnOprtnTm": "현장설명시각",
    "presnatnOprtnPlce": "현장설명장소",
    "bidPrtcptQlfctRgstClseDate": "입찰참가자격등록마감일",
    "bidPrtcptQlfctRgstClseTm": "입찰참가자격등록마감시각",
    "cmmnReciptAgrmntClseDate": "공동수급협정마감일",
    "cmmnReciptAgrmntClseTm": "공동수급협정마감시각",
    "bidBeginDate": "입찰시작일",
    "bidBeginTm": "입찰시작시각",
    "bidClseDate": "입찰마감일",
    "bidClseTm": "입찰마감시각",
    "opengDate": "개찰일",
    "opengTm": "개찰시각",
    "opengPlce": "개찰장소",
    "asignBdgtAmt": "배정예산액",
    "presmptPrce": "추정가격",
    "rsrvtnPrceDcsnMthdNm": "예정가격결정방법",
    "rgnLmtYn": "지역제한여부",
    "prtcptPsblRgnNm": "참가가능지역",
    "indstrytyLmtYn": "업종제한여부",
    "bidprcPsblIndstrytyNm": "참가가능업종",
    "bidNtceUrl": "공고상세URL",
    "bidNtceDtlUrl": "공고상세URL",
    "dataBssDate": "데이터기준일",
    "bidNtceDt": "입찰공고일시",
    "bidClseDt": "입찰마감일시",
    "opengDt": "개찰일시",
}

# 나라장터 웹사이트 구조에 맞춘 섹션 정의
_SECTIONS_SUMMARY: list[tuple[str, list[str]]] = [
    ("공고일반", [
        "bidNtceSttusNm", "bidNtceDate", "bidNtceBgn", "bidNtceDt",
        "bidNtceNo", "bidNtceOrd", "refNtceNo", "refNtceOrd",
        "bidNtceNm",
        "bsnsDivNm",
        "ntceInsttNm", "dmndInsttNm",
        "elctrnBidYn", "bidwinrDcsnMthdNm",
        "cntrctCnclsMthdNm", "cntrctCnclsSttusNm",
    ]),
    ("가격정보", [
        "asignBdgtAmt", "presmptPrce", "rsrvtnPrceDcsnMthdNm",
    ]),
    ("입찰일정", [
        "bidBeginDate", "bidBeginTm",
        "bidClseDate", "bidClseTm", "bidClseDt",
        "bidPrtcptQlfctRgstClseDate", "bidPrtcptQlfctRgstClseTm",
        "opengDate", "opengTm", "opengDt", "opengPlce",
    ]),
    ("공고링크", [
        "bidNtceUrl", "bidNtceDtlUrl",
    ]),
]

_SECTIONS_DETAIL: list[tuple[str, list[str]]] = [
    ("입찰자격", [
        "intrntnlBidYn", "cmmnCntrctYn", "cmmnReciptMethdNm",
        "rgnLmtYn", "prtcptPsblRgnNm",
        "indstrytyLmtYn", "bidprcPsblIndstrytyNm",
    ]),
    ("담당자정보", [
        "ntceInsttCd", "ntceInsttOfclDeptNm",
        "ntceInsttOfclNm", "ntceInsttOfclTel", "ntceInsttOfclEmailAdrs",
        "dmndInsttCd", "dmndInsttOfclDeptNm",
        "dmndInsttOfclNm", "dmndInsttOfclTel", "dmndInsttOfclEmailAdrs",
    ]),
    ("현장설명", [
        "presnatnOprtnYn", "presnatnOprtnDate",
        "presnatnOprtnTm", "presnatnOprtnPlce",
    ]),
    ("공동수급", [
        "cmmnReciptAgrmntClseDate", "cmmnReciptAgrmntClseTm",
    ]),
    ("기타", [
        "ppsNtceYn", "dataBssDate",
    ]),
]


def _get_field(item: dict, key: str) -> str:
    """항목에서 필드 값을 문자열로 가져옴. 빈 값이면 빈 문자열 반환."""
    val = item.get(key, "")
    if val is None:
        return ""
    return str(val)


def _format_amount(value: str) -> str:
    """금액 문자열에 쉼표 구분자를 추가. 숫자가 아니면 그대로 반환."""
    if not value or not value.isdigit():
        return value
    return f"{int(value):,}원"


def _print_section(item: dict, section_name: str, fields: list[str]) -> bool:
    """섹션 하나를 출력. 출력할 필드가 있으면 True 반환."""
    rows: list[tuple[str, str]] = []
    for key in fields:
        val = _get_field(item, key)
        if not val:
            continue
        label = _FIELD_LABELS.get(key, key)
        if key in ("asignBdgtAmt", "presmptPrce"):
            val = _format_amount(val)
        rows.append((label, val))

    if not rows:
        return False

    print(f"  [{section_name}]")
    max_label = max(len(r[0]) for r in rows)
    for label, val in rows:
        padding = " " * (max_label - len(label))
        print(f"    {label}{padding}  {val}")
    return True


def _print_table(items: list[dict], detail: bool = False) -> None:
    """입찰공고 목록을 나라장터 웹사이트 구조로 섹션별 출력.

    기본: 공고일반, 가격정보, 입찰일정, 공고링크
    --detail: 입찰자격, 담당자정보, 현장설명, 공동수급, 기타 추가

    Args:
        items: 출력할 입찰공고 목록.
        detail: True이면 상세 정보 포함.
    """
    if not items:
        return

    sections = list(_SECTIONS_SUMMARY)
    if detail:
        sections.extend(_SECTIONS_DETAIL)

    total = len(items)
    for idx, item in enumerate(items):
        print(f"━━━ [{idx + 1}/{total}] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        printed_any = False
        for section_name, fields in sections:
            if printed_any:
                print()
            if _print_section(item, section_name, fields):
                printed_any = True

        if not detail:
            shown_keys = set()
            for _, fields in _SECTIONS_SUMMARY:
                shown_keys.update(fields)
            remaining = [
                k for k in item
                if k not in shown_keys and _get_field(item, k)
            ]
            if remaining:
                print()
                print(f"    * --detail 옵션으로 {len(remaining)}개 추가 필드 확인 가능")

        if idx < total - 1:
            print()


def _output_error(error_type: str, detail: str) -> None:
    """표준 에러 포맷으로 stdout에 출력."""
    print(json.dumps(
        {"status": "error", "error": error_type, "detail": detail},
        ensure_ascii=False,
    ))


def _explicit_paging_requested(argv: list[str] | None) -> bool:
    """사용자가 --page 또는 --rows를 명시적으로 지정했는지 판정.

    argparse 기본값(page=1, rows=10)과 사용자가 동일 값을 명시한 경우를
    구별하기 위해 raw argv를 직접 검사한다. 명시 시 단일 페이지 모드로,
    미지정 시 자동 전체 순회 모드로 동작한다.
    """
    tokens = sys.argv[1:] if argv is None else argv
    for tok in tokens:
        if tok == "--page" or tok == "--rows":
            return True
        if tok.startswith("--page=") or tok.startswith("--rows="):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점.

    Args:
        argv: CLI 인자 목록. None이면 sys.argv[1:] 사용.

    Returns:
        종료 코드: 0 성공, 1 런타임 오류, 2 인자 오류.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    # 인증키 결정
    try:
        api_key = _resolve_key(args.api_key)
    except env_loader.MissingAPIKeyError as exc:
        _output_error("config", str(exc))
        return 1

    single_page_mode = _explicit_paging_requested(argv)

    warnings: list[str] = []
    truncated = False
    try:
        if single_page_mode:
            # 단일 페이지 조회 모드: 사용자가 --page/--rows로 명시한 페이지만.
            result = g2b_api.search_bids(
                api_key=api_key,
                begin_dt=args.from_date,
                end_dt=args.to,
                page=args.page,
                rows=args.rows,
            )
            items = result.get("items", [])
            total_count = int(result.get("totalCount", 0) or 0)
            page_label: int | str = args.page
        else:
            # 자동 전체 순회 모드: 날짜범위 내 모든 페이지를 순회 후 키워드 필터.
            # 키워드가 첫 페이지 밖에 있어도 수집되어 거짓 0건을 방지한다.
            result = g2b_api.collect_all_bids(
                api_key=api_key,
                begin_dt=args.from_date,
                end_dt=args.to,
                max_pages=args.max_pages,
            )
            items = result.get("items", [])
            total_count = int(result.get("totalCount", 0) or 0)
            truncated = bool(result.get("truncated", False))
            page_label = "all"
            if truncated:
                warnings.append(
                    f"전체 {total_count}건 중 {result.get('scanned_count', len(items))}건만 "
                    f"스캔했습니다(상한 {args.max_pages}페이지 도달). 미조회분이 남아 "
                    "있어 키워드가 미조회 구간에 있으면 누락될 수 있습니다. "
                    "기간을 좁히거나 --max-pages를 늘리세요."
                )
    except ValueError as exc:
        _output_error("argument", str(exc))
        return 1
    except g2b_api.G2BAPIError as exc:
        _output_error("api", str(exc))
        return 1

    # 필터 전 스캔 건수(중복 제거 후 누적). 키워드 필터 의미 구분용.
    scanned_count = len(items)

    # 키워드 필터링
    if args.keyword:
        items = _filter_by_keyword(items, args.keyword)

    # 결과 출력
    if args.format == "json":
        payload = {
            "status": "ok",
            # count: 키워드 필터 후 결과 수.
            "count": len(items),
            # total_count: API가 보고한 필터 전 날짜범위 전체 결과 수.
            "total_count": total_count,
            # scanned_count: 실제로 순회·스캔한(중복 제거 후) 항목 수.
            #   total_count보다 작으면 truncated이거나 단일 페이지 모드.
            "scanned_count": scanned_count,
            "truncated": truncated,
            "page": page_label,
            "results": items,
        }
        if warnings:
            payload["warnings"] = warnings
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        for w in warnings:
            print(f"⚠️ {w}")
        if not items:
            if args.keyword:
                print(
                    f"검색 결과가 없습니다. "
                    f"(스캔 {scanned_count}건 / 전체 {total_count}건 중 "
                    f"'{args.keyword}' 미발견)"
                )
            else:
                print("검색 결과가 없습니다.")
        else:
            if args.keyword:
                print(
                    f"'{args.keyword}' 검색 결과 {len(items)}건 "
                    f"(스캔 {scanned_count}건 / 전체 {total_count}건)"
                )
            _print_table(items, detail=args.detail)

    return 0


if __name__ == "__main__":
    sys.exit(main())
