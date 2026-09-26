#!/usr/bin/env python3
"""국가통계 수집 CLI — KOSIS 국가통계포털.

제안서/사업계획서에 필요한 통계 데이터를 수집하여 JSON/Table로 출력.

사용법:
    python3 scripts/collect_stats.py search --keyword "인구"
    python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --period year --recent 3
    python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --start 2020 --end 2024
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import env_loader
import kosis_api

# KOSIS API 키 환경변수
_KEY_VAR = "KOSIS_API_KEY"

_SETUP_GUIDE = (
    "KOSIS_API_KEY가 설정되지 않았습니다.\n\n"
    "KOSIS 인증키 발급 방법:\n"
    "  1. https://kosis.kr 회원가입\n"
    "  2. https://kosis.kr/openapi/ 에서 서비스 신청 (자동 승인)\n\n"
    "설정 방법: 작업 폴더 루트(예: outputs/)에 .env 파일을 만들고 키를 추가하세요.\n"
    "  KOSIS_API_KEY=발급받은_인증키\n"
)


def _get_api_key(cli_arg: str | None = None) -> str:
    """KOSIS API 키 해석."""
    return env_loader.resolve_api_key(_KEY_VAR, cli_arg, _SETUP_GUIDE)


def cmd_search(args: argparse.Namespace) -> int:
    """키워드로 통계표 검색."""
    api_key = _get_api_key(args.api_key)
    results = kosis_api.search_statistics(
        api_key, args.keyword, result_count=args.count,
    )

    if args.format == "table":
        _print_search_table(results, args.keyword)
    else:
        output: list[dict[str, str]] = []
        for r in results:
            output.append({
                "org_id": r.get("ORG_ID", ""),
                "org_name": r.get("ORG_NM", ""),
                "tbl_id": r.get("TBL_ID", ""),
                "tbl_name": r.get("TBL_NM", ""),
                "stat_name": r.get("STAT_NM", ""),
                "period_range": f"{r.get('STRT_PRD_DE', '')}~{r.get('END_PRD_DE', '')}",
            })
        print(json.dumps(
            {"status": "ok", "keyword": args.keyword, "count": len(output), "results": output},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    """통계자료 조회."""
    api_key = _get_api_key(args.api_key)
    prd_se = kosis_api.PERIOD_CODES.get(args.period, "Y")

    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "org_id": args.org_id,
        "tbl_id": args.tbl_id,
        "itm_id": args.item or "ALL",
        "obj_l1": args.obj1 or "ALL",
        "obj_l2": args.obj2 or "",
        "obj_l3": args.obj3 or "",
        "obj_l4": args.obj4 or "",
        "prd_se": prd_se,
    }

    if args.recent:
        kwargs["new_est_prd_cnt"] = args.recent
    else:
        if args.start:
            kwargs["start_prd_de"] = args.start
        if args.end:
            kwargs["end_prd_de"] = args.end

    raw_data, diag = kosis_api.get_statistics_data_ex(**kwargs)
    summarized = kosis_api.summarize_data(raw_data)

    if args.format == "table":
        _print_data_table(summarized, diag)
    else:
        print(json.dumps(
            {"status": "ok", "org_id": args.org_id, "tbl_id": args.tbl_id,
             "count": len(summarized), "source": diag.get("transport", "json"),
             "axis_slots": diag.get("axis_slots", []),
             "notes": diag.get("notes", []), "data": summarized},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """통계표 메타 조회 — objL·itmId 코드 발견 (getMeta)."""
    api_key = _get_api_key(args.api_key)
    rows = kosis_api.get_table_meta(
        api_key, args.org_id, args.tbl_id,
        meta_type=args.type, obj_id=args.obj_id or "", itm_id=args.item or "",
    )

    if args.format == "table":
        _print_info_table(rows, args.type)
    else:
        print(json.dumps(
            {"status": "ok", "org_id": args.org_id, "tbl_id": args.tbl_id,
             "type": args.type, "count": len(rows), "meta": rows},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """통계목록 트리 탐색 (statisticsList.do)."""
    api_key = _get_api_key(args.api_key)
    rows = kosis_api.list_statistics(
        api_key, vw_cd=args.vw_cd, parent_list_id=args.parent_id or "",
    )

    if args.format == "table":
        _print_list_table(rows, args.vw_cd)
    else:
        output = [{
            "list_id": r.get("LIST_ID", ""),
            "list_name": r.get("LIST_NM", ""),
            "org_id": r.get("ORG_ID", ""),
            "tbl_id": r.get("TBL_ID", ""),
            "tbl_name": r.get("TBL_NM", ""),
            "stat_id": r.get("STAT_ID", ""),
            "is_table": bool(r.get("TBL_ID", "")),
        } for r in rows]
        print(json.dumps(
            {"status": "ok", "vw_cd": args.vw_cd, "parent_id": args.parent_id or "",
             "count": len(output), "results": output},
            ensure_ascii=False, separators=(",", ":"),
        ))
    return 0


def cmd_meta(args: argparse.Namespace) -> int:
    """통계설명자료 조회 (작성목적·법적근거 등)."""
    api_key = _get_api_key(args.api_key)
    rows = kosis_api.get_stat_explanation(
        api_key, stat_id=args.stat_id or "",
        org_id=args.org_id or "", tbl_id=args.tbl_id or "",
        meta_itm=args.meta_item,
    )
    # KOSIS 통계설명은 필드마다 별도 행({"writingPurps":...},{"basisLaw":...})으로
    # 온다 — 소비 편의를 위해 하나의 객체로 병합(값 있는 필드만).
    merged: dict[str, Any] = {}
    for row in rows:
        for k, v in row.items():
            if str(v).strip():
                merged[k] = v
    print(json.dumps(
        {"status": "ok", "field_count": len(merged), "explanation": merged},
        ensure_ascii=False, separators=(",", ":"),
    ))
    return 0


def cmd_indicator(args: argparse.Namespace) -> int:
    """통계주요지표 설명자료 조회."""
    api_key = _get_api_key(args.api_key)
    rows = kosis_api.get_indicator(
        api_key, args.jipyo_id, page_no=args.page, num_of_rows=args.count,
    )
    print(json.dumps(
        {"status": "ok", "jipyo_id": args.jipyo_id, "count": len(rows), "indicator": rows},
        ensure_ascii=False, separators=(",", ":"),
    ))
    return 0


def cmd_region(args: argparse.Namespace) -> int:
    """자연어 지역명 → 통계표별 objL 분류 코드 매핑."""
    api_key = _get_api_key(args.api_key)
    matches = kosis_api.find_region_code(
        api_key, args.org_id, args.tbl_id, args.region,
    )
    print(json.dumps(
        {"status": "ok", "org_id": args.org_id, "tbl_id": args.tbl_id,
         "region": args.region, "count": len(matches), "matches": matches},
        ensure_ascii=False, separators=(",", ":"),
    ))
    return 0


# --- 테이블 출력 헬퍼 ---

def _print_search_table(results: list[dict[str, Any]], keyword: str) -> None:
    """검색 결과를 테이블로 출력."""
    print(f"\n통계표 검색: '{keyword}' — {len(results)}건\n")
    print(f"{'기관':<8} {'orgId':<8} {'tblId':<20} {'통계표명':<50}")
    print("-" * 86)
    for r in results:
        org = r.get("ORG_NM", "")[:6]
        org_id = r.get("ORG_ID", "")
        tbl_id = r.get("TBL_ID", "")
        tbl_nm = r.get("TBL_NM", "")[:48]
        print(f"{org:<8} {org_id:<8} {tbl_id:<20} {tbl_nm:<50}")
    print()


def _print_data_table(
    data: list[dict[str, Any]],
    diag: dict[str, Any] | None = None,
) -> None:
    """통계 데이터를 테이블로 출력."""
    notes = (diag or {}).get("notes") or []
    if not data:
        print("\n(데이터 없음)\n")
        for note in notes:
            print(f"  · {note}")
        if notes:
            print()
        return

    # 테이블명 출력
    tbl_name = data[0].get("table_name", "") if data else ""
    if tbl_name:
        print(f"\n{tbl_name}\n")

    print(f"{'시점':<10} {'분류':<15} {'항목':<20} {'값':>15} {'단위':<6}")
    print("-" * 66)
    for row in data:
        period = row.get("period", "")
        cat = row.get("category", "") or ""
        if row.get("category2"):
            cat = f"{cat}/{row['category2']}"
        cat = cat[:13]
        item = (row.get("item_name", "") or "")[:18]
        val = row.get("value")
        unit = row.get("unit", "")
        val_str = f"{val:,.0f}" if val is not None else "-"
        print(f"{period:<10} {cat:<15} {item:<20} {val_str:>15} {unit:<6}")
    print()
    for note in notes:
        print(f"  · {note}")
    if notes:
        print()


def _print_info_table(rows: list[dict[str, Any]], meta_type: str) -> None:
    """통계표 메타를 테이블로 출력 (type=ITM 코드 발견 중심)."""
    if not rows:
        print("\n(메타 없음)\n")
        return

    if meta_type == "ITM":
        print(f"\n분류/항목 코드 — {len(rows)}건\n")
        print(f"{'OBJ_ID':<12} {'분류명':<22} {'ITM_ID':<12} {'항목명':<24} {'단위':<8}")
        print("-" * 80)
        for r in rows:
            obj_id = (r.get("OBJ_ID", "") or "")[:11]
            obj_nm = (r.get("OBJ_NM", "") or "")[:20]
            itm_id = (r.get("ITM_ID", "") or "")[:11]
            itm_nm = (r.get("ITM_NM", "") or "")[:22]
            unit = (r.get("UNIT_NM", "") or "")[:7]
            print(f"{obj_id:<12} {obj_nm:<22} {itm_id:<12} {itm_nm:<24} {unit:<8}")
        print()
    else:
        print(f"\n메타 ({meta_type}) — {len(rows)}건\n")
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        print()


def _print_list_table(rows: list[dict[str, Any]], vw_cd: str) -> None:
    """통계목록 트리를 테이블로 출력."""
    if not rows:
        print("\n(목록 없음)\n")
        return

    print(f"\n통계목록 ({vw_cd}) — {len(rows)}건\n")
    print(f"{'LIST_ID':<14} {'목록/통계표명':<40} {'orgId':<8} {'tblId':<18}")
    print("-" * 82)
    for r in rows:
        list_id = (r.get("LIST_ID", "") or "")[:13]
        name = (r.get("TBL_NM", "") or r.get("LIST_NM", "") or "")[:38]
        org_id = r.get("ORG_ID", "") or ""
        tbl_id = (r.get("TBL_ID", "") or "")[:17]
        leaf = "📄" if r.get("TBL_ID") else "📁"
        print(f"{list_id:<14} {leaf} {name:<38} {org_id:<8} {tbl_id:<18}")
    print()


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성.

    공용 옵션(--api-key, --format)을 _add_common() 헬퍼로 메인 파서와 모든 서브파서에
    동시 등록하여 서브커맨드 앞/뒤 양쪽 위치에서 모두 동작하도록 한다 (REQ-1).
    """
    # 메인 파서: 서브커맨드 앞 위치 공용 옵션 (REQ-1.2, 하위 호환)
    parser = argparse.ArgumentParser(
        description="국가통계 수집 — KOSIS 국가통계포털",
    )
    parser.add_argument(
        "--api-key", default=None, dest="api_key", help="KOSIS API 키",
    )
    parser.add_argument(
        "--format", choices=["json", "table"], default="json",
        help="출력 형식 (기본: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # 서브파서 공용 옵션은 default=argparse.SUPPRESS로 두어 메인 파서 기본값을 보존한다.
    def _add_common(p: argparse.ArgumentParser) -> None:
        """서브파서에 공용 옵션 추가 (SUPPRESS default로 메인 파서 값 보존)."""
        p.add_argument(
            "--api-key", default=argparse.SUPPRESS, dest="api_key",
            help="KOSIS API 키",
        )
        p.add_argument(
            "--format", choices=["json", "table"], default=argparse.SUPPRESS,
            help="출력 형식 (기본: json)",
        )

    # search
    p_search = sub.add_parser("search", help="키워드로 통계표 검색")
    _add_common(p_search)
    p_search.add_argument("--keyword", "-k", required=True, help="검색 키워드")
    p_search.add_argument("--count", "-n", type=int, default=10, help="결과 수 (기본 10)")

    # data
    p_data = sub.add_parser("data", help="통계자료 조회")
    _add_common(p_data)
    p_data.add_argument("--org-id", required=True, help="기관 코드 (예: 101)")
    p_data.add_argument("--tbl-id", required=True, help="통계표 ID (예: DT_1B04005N)")
    p_data.add_argument("--item", default=None, help="항목 ID (기본: ALL)")
    p_data.add_argument("--obj1", default=None, help="1차 분류값 (기본: ALL)")
    p_data.add_argument("--obj2", default=None, help="2차 분류값")
    p_data.add_argument("--obj3", default=None, help="3차 분류값 (3중 분류표)")
    p_data.add_argument("--obj4", default=None, help="4차 분류값 (4중 분류표)")
    p_data.add_argument(
        "--period", "-p", choices=list(kosis_api.PERIOD_CODES.keys()),
        default="year", help="수록주기 (기본: year)",
    )
    p_data.add_argument("--start", default=None, help="시작 시점 (예: 2020)")
    p_data.add_argument("--end", default=None, help="종료 시점 (예: 2024)")
    p_data.add_argument("--recent", type=int, default=None, help="최근 N개 시점")

    # info — 통계표 메타(코드 발견). get_data 의 objL/itmId 를 모를 때 선행.
    p_info = sub.add_parser("info", help="통계표 메타 조회 (objL·itmId 코드 발견)")
    _add_common(p_info)
    p_info.add_argument("--org-id", required=True, help="기관 코드 (예: 101)")
    p_info.add_argument("--tbl-id", required=True, help="통계표 ID")
    p_info.add_argument(
        "--type", choices=list(kosis_api.META_TYPES), default="ITM",
        help="조회유형 (기본: ITM=분류항목 코드)",
    )
    p_info.add_argument("--obj-id", default=None, help="특정 분류 ID 필터 (선택)")
    p_info.add_argument("--item", default=None, help="특정 자료코드 ID 필터 (선택)")

    # list — 통계목록 트리 탐색 (국제·지자체 진입로)
    p_list = sub.add_parser("list", help="통계목록 트리 탐색")
    _add_common(p_list)
    p_list.add_argument(
        "--vw-cd", default="MT_ZTITLE",
        help="서비스뷰 (MT_ZTITLE=주제별, MT_RTITLE=국제, MT_ATITLE01=지역 등)",
    )
    p_list.add_argument("--parent-id", default=None, help="시작 목록 ID (생략 시 최상위)")

    # meta — 통계설명자료 (작성목적·법적근거)
    p_meta = sub.add_parser("meta", help="통계설명자료 조회 (작성목적·법적근거)")
    _add_common(p_meta)
    p_meta.add_argument("--stat-id", default=None, help="통계조사 ID (단독 사용 가능)")
    p_meta.add_argument("--org-id", default=None, help="기관 코드 (stat-id 없을 때)")
    p_meta.add_argument("--tbl-id", default=None, help="통계표 ID (stat-id 없을 때)")
    p_meta.add_argument("--meta-item", default="ALL", help="요청 항목 (기본: ALL)")

    # indicator — 통계주요지표 설명
    p_ind = sub.add_parser("indicator", help="통계주요지표 설명 조회")
    _add_common(p_ind)
    p_ind.add_argument("--jipyo-id", required=True, help="지표 ID")
    p_ind.add_argument("--page", type=int, default=1, help="페이지 번호")
    p_ind.add_argument("--count", "-n", type=int, default=10, help="페이지당 건수")

    # region — 자연어 지역명 → objL 코드 매핑
    p_region = sub.add_parser("region", help="자연어 지역명 → objL 분류 코드")
    _add_common(p_region)
    p_region.add_argument("--org-id", required=True, help="기관 코드")
    p_region.add_argument("--tbl-id", required=True, help="통계표 ID")
    p_region.add_argument("--region", required=True, help="지역명 (예: 인천 서구)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        commands = {
            "search": cmd_search,
            "data": cmd_data,
            "info": cmd_info,
            "list": cmd_list,
            "meta": cmd_meta,
            "indicator": cmd_indicator,
            "region": cmd_region,
        }
        return commands[args.command](args)

    except env_loader.MissingAPIKeyError as e:
        print(json.dumps(
            {"status": "error", "error": "config", "detail": str(e)},
            ensure_ascii=False,
        ))
        return 1
    except kosis_api.KOSISAPIError as e:
        print(json.dumps(
            {"status": "error", "error": "api", "detail": str(e),
             "error_code": e.error_code},
            ensure_ascii=False,
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())
