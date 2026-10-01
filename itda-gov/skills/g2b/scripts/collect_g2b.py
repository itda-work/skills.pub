"""나라장터 입찰공고 CLI — 호출 계획(plan)과 응답 가공(collect). 파일 입력 전용.

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 스크립트는
직접 API 를 부르지 않고 키 값을 보지 않는다.

사용법:
    python3 scripts/collect_g2b.py plan --from 2026-09-01 --to 2026-09-29 --write g2b/plan-1.json
    python3 scripts/collect_g2b.py collect --input g2b/bids-20260901-20260929-p1.json g2b/bids-20260901-20260929-p2.json
    python3 scripts/collect_g2b.py collect --input … --keyword "소프트웨어" --format table --detail
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import g2b_api


def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 구성."""
    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="나라장터 입찰공고 — 호출 계획과 응답 가공")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="기간을 1개월 창으로 나눈 http_request 호출 계획(창마다 1쪽)")
    p_plan.add_argument("--from", dest="from_date", default=week_ago,
                        help=f"조회 시작일 YYYY-MM-DD (기본: {week_ago}, 7일 전)")
    p_plan.add_argument("--to", default=today, help=f"조회 종료일 YYYY-MM-DD (기본: {today}, 오늘)")
    p_plan.add_argument("--rows", type=int, default=g2b_api.PAGE_SIZE,
                        help=f"쪽당 행 수 (기본·최대 {g2b_api.PAGE_SIZE})")
    p_plan.add_argument("--write", metavar="FILE", default=None,
                        help="itda-hyve batch 의 plan_file 로 쓸 계획 파일({calls, timeout_sec})을 쓴다")

    p_col = sub.add_parser("collect", help="itda-hyve 가 저장한 응답 파일을 창별로 전량 대조·가공")
    p_col.add_argument("--input", nargs="+", required=True, metavar="JSON",
                       help="save_as 로 저장한 응답 파일(들). 이름 규칙 bids-<시작>-<끝>-p<쪽>.json")
    p_col.add_argument("--keyword", default=None, help="공고명 키워드 필터 (부분 일치, 대소문자 무시)")
    p_col.add_argument("--max-pages", dest="max_pages", type=int, default=g2b_api.MAX_PAGES,
                       help=f"창마다 받을 쪽 상한 (기본: {g2b_api.MAX_PAGES}). 넘으면 truncated 로 표시")
    p_col.add_argument("--single-page", action="store_true",
                       help="전량 대조 없이 넘긴 쪽만 훑어본다(앞쪽 몇 건 미리보기)")
    p_col.add_argument("--format", choices=["table", "json"], default="json",
                       help="출력 형식 table/json (기본: json)")
    p_col.add_argument("--detail", action="store_true", default=False,
                       help="상세 출력 (입찰자격, 담당자, 일정 등 전체 정보)")
    p_col.add_argument("--next-plan", dest="next_plan", metavar="FILE", default=None,
                       help="전량 미달이면 더 받을 호출을 batch plan_file 로 쓴다")
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
        if kw_lower in (item.get("bidNtceNm") or "").lower()
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


def _output_error(error_type: str, detail: str, **extra: Any) -> None:
    """표준 에러 포맷으로 stdout에 출력."""
    print(json.dumps(
        {"status": "error", "error": error_type, "detail": detail, **extra},
        ensure_ascii=False,
    ))


# 계획 파일을 쓴 뒤 stdout 에 보여 줄 호출 수. 나머지는 파일에 있다(옮겨 적는 토큰을 없앤다).
_PREVIEW_CALLS = 3


def _chunk_suffix(i: int) -> str:
    """0 → a, 25 → z, 26 → aa … (계획 파일 이름 꼬리)."""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(ord("a") + r) + out
    return out


def _write_plan(path: str, calls: list[dict[str, Any]]) -> list[str]:
    """batch plan_file 형식으로 쓴다. save_dir 는 넣지 않는다 — batch 호출 인자로 준다.

    itda-hyve batch 는 호출이 40개를 넘으면 **하나도 실행하지 않는다**. 그래서 40개씩 나눠
    ``plan-1a.json``·``plan-1b.json`` … 로 쓴다(40개 이하면 준 이름 그대로 한 파일). 쓴 경로 목록을 돌려준다.
    """
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    limit = g2b_api.BATCH_LIMIT
    chunks = [calls[i:i + limit] for i in range(0, len(calls), limit)] or [[]]
    if len(chunks) == 1:
        targets = [out]
    else:
        targets = [out.with_name(f"{out.stem}{_chunk_suffix(i)}{out.suffix}") for i in range(len(chunks))]
    for target, chunk in zip(targets, chunks):
        target.write_text(json.dumps({"calls": chunk, "timeout_sec": 50}, ensure_ascii=False,
                                     separators=(",", ":")), encoding="utf-8")
    return [str(t) for t in targets]


def _cmd_plan(args: argparse.Namespace) -> int:
    result = g2b_api.plan(args.from_date, args.to, args.rows)
    result["call_count"] = len(result["calls"])
    if args.write:
        result["plan_files"] = _write_plan(args.write, result["calls"])
        # 호출은 계획 파일에 있다 — stdout 에는 앞 몇 개만 싣는다.
        result["calls_preview"] = result.pop("calls")[:_PREVIEW_CALLS]
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    result = g2b_api.collect(args.input, max_pages=args.max_pages, single_page=args.single_page)
    items = result["items"]
    total_count = result["total_count"]
    scanned_count = result["scanned_count"]
    warnings = result["warnings"]

    if args.keyword:
        items = _filter_by_keyword(items, args.keyword)

    if args.format == "json":
        payload = {
            "status": "ok",
            # count: 키워드 필터 후 결과 수.
            "count": len(items),
            # total_count: API가 보고한 필터 전 기간 전체 결과 수(창 합).
            "total_count": total_count,
            # scanned_count: 받은 쪽에서 중복을 없앤 항목 수. total_count보다 작은 경우는 셋이다 —
            # truncated, --single-page, 또는 받는 사이 공고가 바뀜(쪽마다 totalCount 가 달라 warnings 가 붙는다).
            "scanned_count": scanned_count,
            "truncated": result["truncated"],
            "page": result["page"],
            "windows": result["windows"],
            "results": items,
            "sources": result["sources"],
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


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. 종료 코드: 0 성공, 1 가공 실패(입력·API 오류·전량 미달), 2 인자 오류."""
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

    try:
        if args.command == "plan":
            return _cmd_plan(args)
        return _cmd_collect(args)
    except ValueError as exc:
        _output_error("argument", str(exc))
        return 2
    except g2b_api.G2BAPIError as exc:
        _output_error("api", str(exc), error_code=exc.error_code)
        return 1
    except g2b_api.InputFileError as exc:
        _output_error(exc.kind, str(exc))
        return 1
    except g2b_api.IncompleteError as exc:
        extra: dict[str, Any] = {
            "next_call_count": len(exc.next_calls),
            "will_truncate": exc.will_truncate,
            "windows": exc.windows,
        }
        if getattr(args, "next_plan", None) and exc.next_calls:
            extra["plan_files"] = _write_plan(args.next_plan, exc.next_calls)
            # 호출은 계획 파일에 있다 — stdout 에는 앞 몇 개만 싣는다(120개면 49KB 였다).
            extra["next_calls_preview"] = exc.next_calls[:_PREVIEW_CALLS]
        else:
            extra["next_calls"] = exc.next_calls
        _output_error("incomplete", str(exc), **extra)
        return 1


if __name__ == "__main__":
    sys.exit(main())
