#!/usr/bin/env python3
"""국가통계 가공 CLI — KOSIS 국가통계포털 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 스크립트는
  1. ``plan <명령> …`` 으로 부를 호출(``http_request`` 인자 그대로)을 내고
  2. ``<명령> --input <파일…>`` 으로 그렇게 저장한 응답을 읽어 오류 판정·정리만 한다.
직접 API 를 부르지 않고 키 값을 보지 않는다.

사용법:
    python3 scripts/collect_stats.py plan search --keyword "인구"
    python3 scripts/collect_stats.py search --input kosis/search-1a2b3c4d.json
    python3 scripts/collect_stats.py plan data --org-id 101 --tbl-id DT_1B04005N --recent 3
    python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --recent 3 \\
        --input kosis/data-101-DT_1B04005N-<지문>-json1.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import kosis_api


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _one_input(args: argparse.Namespace, prefix: str) -> str:
    """응답 파일 1개 — 이름이 그 명령의 저장 이름(``<prefix>-…``)이어야 한다(다른 명령의 응답을 막는다)."""
    if len(args.input) != 1:
        raise kosis_api.InputFileError(f"{args.command} 은 응답 파일 1개를 받습니다(받은 수 {len(args.input)})")
    path = args.input[0]
    name = Path(path).name
    if not name.startswith(prefix + "-"):
        raise kosis_api.InputFileError(
            f"{args.command} 의 응답 파일이 아닙니다: {name} — plan {args.command} 가 준 save_as({prefix}-…)를 그대로 쓰세요"
        )
    if args.command == "region" and not name.endswith("-ITM.json"):
        raise kosis_api.InputFileError(f"region 은 분류항목 메타(info-…-ITM.json)를 받습니다: {name}")
    return path


def _data_query(args: argparse.Namespace) -> kosis_api.DataQuery:
    return kosis_api.DataQuery(
        org_id=args.org_id,
        tbl_id=args.tbl_id,
        itm_id=args.item or "ALL",
        obj_l1=args.obj1 or "ALL",
        obj_l2=args.obj2 or "",
        obj_l3=args.obj3 or "",
        obj_l4=args.obj4 or "",
        prd_se=kosis_api.PERIOD_CODES.get(args.period, "Y"),
        start_prd_de=args.start or "",
        end_prd_de=args.end or "",
        new_est_prd_cnt=args.recent,
    )


# --- plan ---

def cmd_plan(args: argparse.Namespace) -> int:
    """부를 호출을 낸다 — ``calls[i].args`` 가 ``http_request`` 인자 그대로다."""
    target = args.target
    if target == "search":
        calls = [kosis_api.plan_search(args.keyword, args.count)]
    elif target == "data":
        calls = [_data_query(args).first_call()]
    elif target == "info":
        calls = [kosis_api.plan_info(args.org_id, args.tbl_id, args.type, args.obj_id or "", args.item or "")]
    elif target == "list":
        calls = [kosis_api.plan_list(args.vw_cd, args.parent_id or "")]
    elif target == "meta":
        calls = [kosis_api.plan_meta(args.stat_id or "", args.org_id or "", args.tbl_id or "", args.meta_item)]
    elif target == "indicator":
        calls = [kosis_api.plan_indicator(args.jipyo_id, args.page, args.count)]
    else:  # region — 분류항목 메타(getMeta ITM)만 받으면 된다
        calls = [kosis_api.plan_info(args.org_id, args.tbl_id, "ITM")]
    _emit({"status": "ok", "command": target, "calls": calls})
    return 0


# --- 가공 ---

def cmd_search(args: argparse.Namespace) -> int:
    """키워드 검색 응답."""
    results = kosis_api._as_list(kosis_api.load_json(_one_input(args, "search")))

    if args.format == "table":
        _print_search_table(results, args.keyword or "")
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
        _emit({"status": "ok", "keyword": args.keyword or "", "count": len(output), "results": output})
    return 0


def cmd_data(args: argparse.Namespace) -> int:
    """통계자료 — 적응형 흐름. 모자라면 ``next_calls`` 와 함께 incomplete."""
    raw_data, diag = kosis_api.resolve_data(_data_query(args), args.input)
    summarized = kosis_api.summarize_data(raw_data)
    # 값이 숫자가 아닌 행(-, … 등)은 정리에서 빠진다 — 몇 행을 뺐는지 남긴다(무음 유실 금지).
    skipped = len(raw_data) - len(summarized)
    notes = list(diag.get("notes", []))
    if skipped:
        notes.append(f"값이 숫자가 아닌 행 {skipped}개를 뺐습니다(DT 가 -·… 등)")

    if args.format == "table":
        _print_data_table(summarized, {**diag, "notes": notes})
    else:
        _emit({"status": "ok", "org_id": args.org_id, "tbl_id": args.tbl_id,
               "count": len(summarized), "raw_count": len(raw_data), "skipped_non_numeric": skipped,
               "source": diag.get("transport", "json"),
               "axis_slots": diag.get("axis_slots", []),
               "notes": notes, "data": summarized})
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """통계표 메타 — objL·itmId 코드 발견 (getMeta 응답)."""
    rows = kosis_api._as_list(kosis_api.load_json(_one_input(args, "info")))

    if args.format == "table":
        _print_info_table(rows, args.type)
    else:
        _emit({"status": "ok", "org_id": args.org_id or "", "tbl_id": args.tbl_id or "",
               "type": args.type, "count": len(rows), "meta": rows})
    return 0


_LIST_NAME = re.compile(r"^list-([A-Za-z0-9_.]+)-(.+)\.json$")


def _list_query(args: argparse.Namespace, path: str) -> tuple[str, str]:
    """저장 이름 ``list-<서비스뷰>-<시작 목록 ID|root>.json`` 에서 질의를 읽는다.

    인자를 주지 않아도 이름이 정본이다(옛 판은 기본값 MT_ZTITLE 을 에코해 다른 서비스뷰 파일에 틀린 라벨을 달았다 — W2 리뷰 m6).
    인자를 줬는데 이름과 다르면 다른 질의의 파일이다.
    """
    m = _LIST_NAME.match(Path(path).name)
    if not m:
        raise kosis_api.InputFileError(
            f"list 의 저장 이름이 규칙(list-<서비스뷰>-<시작 목록 ID|root>.json)과 다릅니다: {Path(path).name}"
        )
    vw_cd, parent = m.group(1), m.group(2)
    parent = "" if parent == "root" else parent
    if args.vw_cd and args.vw_cd != vw_cd:
        raise kosis_api.InputFileError(f"--vw-cd {args.vw_cd} 인데 파일은 {vw_cd} 의 응답입니다: {Path(path).name}")
    if args.parent_id and kosis_api._safe(args.parent_id) != parent:
        raise kosis_api.InputFileError(
            f"--parent-id {args.parent_id} 인데 파일은 {parent or '최상위'} 의 응답입니다: {Path(path).name}"
        )
    return vw_cd, parent


def cmd_list(args: argparse.Namespace) -> int:
    """통계목록 트리 응답 (statisticsList.do)."""
    path = _one_input(args, "list")
    vw_cd, parent_id = _list_query(args, path)
    rows = kosis_api._as_list(kosis_api.load_json(path))

    if args.format == "table":
        _print_list_table(rows, vw_cd)
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
        _emit({"status": "ok", "vw_cd": vw_cd, "parent_id": parent_id, "count": len(output), "results": output})
    return 0


def cmd_meta(args: argparse.Namespace) -> int:
    """통계설명자료 응답 (작성목적·법적근거 등)."""
    rows = kosis_api._as_list(kosis_api.load_json(_one_input(args, "meta")))
    # KOSIS 통계설명은 필드마다 별도 행({"writingPurps":...},{"basisLaw":...})으로
    # 온다 — 소비 편의를 위해 하나의 객체로 병합(값 있는 필드만).
    merged: dict[str, Any] = {}
    for row in rows:
        for k, v in row.items():
            if str(v).strip():
                merged[k] = v
    _emit({"status": "ok", "field_count": len(merged), "explanation": merged})
    return 0


def cmd_indicator(args: argparse.Namespace) -> int:
    """통계주요지표 설명자료 응답."""
    rows = kosis_api._as_list(kosis_api.load_json(_one_input(args, "indicator")))
    _emit({"status": "ok", "count": len(rows), "indicator": rows})
    return 0


def cmd_region(args: argparse.Namespace) -> int:
    """자연어 지역명 → objL 분류 코드 (getMeta ITM 응답에서만 찾는다)."""
    rows = kosis_api._as_list(kosis_api.load_json(_one_input(args, "info")))
    matches = kosis_api.find_region_code(rows, args.region)
    _emit({"status": "ok", "region": args.region, "count": len(matches), "matches": matches})
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


def _add_format(p: argparse.ArgumentParser, main: bool = False) -> None:
    """--format 은 메인·서브 어디에 와도 동작한다(서브는 SUPPRESS 로 메인 값을 보존)."""
    p.add_argument(
        "--format", choices=["json", "table"], default="json" if main else argparse.SUPPRESS,
        help="출력 형식 (기본: json)",
    )


def _add_query_args(name: str, p: argparse.ArgumentParser, for_input: bool) -> None:
    """명령별 질의 인자. plan 과 가공이 같은 인자를 쓴다(가공 쪽은 라벨·필터용으로 선택)."""
    if name == "search":
        p.add_argument("--keyword", "-k", required=not for_input, help="검색 키워드")
        p.add_argument("--count", "-n", type=int, default=10, help="결과 수 (기본 10)")
    elif name == "data":
        p.add_argument("--org-id", required=True, help="기관 코드 (예: 101)")
        p.add_argument("--tbl-id", required=True, help="통계표 ID (예: DT_1B04005N)")
        p.add_argument("--item", default=None, help="항목 ID (기본: ALL)")
        p.add_argument("--obj1", default=None, help="1번째 분류축 값 (기본: ALL)")
        p.add_argument("--obj2", default=None, help="2번째 분류축 값")
        p.add_argument("--obj3", default=None, help="3번째 분류축 값 (3중 분류표)")
        p.add_argument("--obj4", default=None, help="4번째 분류축 값 (4중 분류표)")
        p.add_argument(
            "--period", "-p", choices=list(kosis_api.PERIOD_CODES.keys()),
            default="year", help="수록주기 (기본: year)",
        )
        p.add_argument("--start", default=None, help="시작 시점 (예: 2020)")
        p.add_argument("--end", default=None, help="종료 시점 (예: 2024)")
        p.add_argument("--recent", type=int, default=None, help="최근 N개 시점")
    elif name == "info":
        p.add_argument("--org-id", required=not for_input, help="기관 코드 (예: 101)")
        p.add_argument("--tbl-id", required=not for_input, help="통계표 ID")
        p.add_argument(
            "--type", choices=list(kosis_api.META_TYPES), default="ITM",
            help="조회유형 (기본: ITM=분류항목 코드)",
        )
        p.add_argument("--obj-id", default=None, help="특정 분류 ID 필터 (선택)")
        p.add_argument("--item", default=None, help="특정 자료코드 ID 필터 (선택)")
    elif name == "list":
        p.add_argument(
            "--vw-cd", default=None if for_input else "MT_ZTITLE",
            help="서비스뷰 (MT_ZTITLE=주제별, MT_RTITLE=국제, MT_ATITLE01=지역 등). 가공 때는 생략하면 저장 이름에서 읽는다",
        )
        p.add_argument("--parent-id", default=None, help="시작 목록 ID (생략 시 최상위)")
    elif name == "meta":
        p.add_argument("--stat-id", default=None, help="통계조사 ID (단독 사용 가능)")
        p.add_argument("--org-id", default=None, help="기관 코드 (stat-id 없을 때)")
        p.add_argument("--tbl-id", default=None, help="통계표 ID (stat-id 없을 때)")
        p.add_argument("--meta-item", default="ALL", help="요청 항목 (기본: ALL)")
    elif name == "indicator":
        p.add_argument("--jipyo-id", required=not for_input, help="지표 ID")
        p.add_argument("--page", type=int, default=1, help="페이지 번호")
        p.add_argument("--count", "-n", type=int, default=10, help="페이지당 건수")
    elif name == "region":
        p.add_argument("--org-id", required=not for_input, help="기관 코드")
        p.add_argument("--tbl-id", required=not for_input, help="통계표 ID")
        if for_input:
            p.add_argument("--region", required=True, help="지역명 (예: 인천 서구)")


_HELPS = {
    "search": "키워드로 통계표 검색 (statisticsSearch.do 응답)",
    "data": "통계자료 (statisticsParameterData.do 응답 — 적응형 흐름)",
    "info": "통계표 메타 — objL·itmId 코드 발견 (getMeta 응답)",
    "list": "통계목록 트리 (statisticsList.do 응답)",
    "meta": "통계설명자료 — 작성목적·법적근거 (statisticsExplData.do 응답)",
    "indicator": "통계주요지표 설명 (pkNumberService.do 응답)",
    "region": "자연어 지역명 → objL 분류 코드 (getMeta ITM 응답)",
}


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성.

    ``--format`` 은 메인 파서와 모든 서브파서에 함께 등록해 서브커맨드 앞/뒤 어디에 와도 동작한다.
    """
    parser = argparse.ArgumentParser(description="국가통계 응답 가공 — KOSIS 국가통계포털")
    _add_format(parser, main=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="부를 호출(http_request 인자)을 낸다 — 네트워크 불요")
    _add_format(p_plan)
    plan_sub = p_plan.add_subparsers(dest="target", required=True)
    for name, text in _HELPS.items():
        pp = plan_sub.add_parser(name, help=text)
        _add_query_args(name, pp, for_input=False)

    for name, text in _HELPS.items():
        p = sub.add_parser(name, help=text)
        _add_format(p)
        p.add_argument(
            "--input", nargs="+", required=True, metavar="FILE",
            help="itda-hyve 가 save_as 로 저장한 응답 파일(들). data 는 지금까지 받은 파일 전부",
        )
        _add_query_args(name, p, for_input=True)

    return parser


def _error(kind: str, detail: str, **extra: Any) -> int:
    print(json.dumps({"status": "error", "error": kind, "detail": detail, **extra}, ensure_ascii=False))
    return 1


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "plan": cmd_plan,
        "search": cmd_search,
        "data": cmd_data,
        "info": cmd_info,
        "list": cmd_list,
        "meta": cmd_meta,
        "indicator": cmd_indicator,
        "region": cmd_region,
    }
    try:
        return commands[args.command](args)
    except kosis_api.IncompleteError as e:
        return _error("incomplete", str(e), stage=e.stage, next_calls=e.next_calls)
    except kosis_api.KOSISAPIError as e:
        return _error("api", str(e), error_code=e.error_code)
    except kosis_api.InputFileError as e:
        return _error(e.kind, str(e))
    except ValueError as e:
        print(json.dumps({"status": "error", "error": "argument", "detail": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
