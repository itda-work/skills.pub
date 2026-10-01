#!/usr/bin/env python3
"""정부 지원사업 공고 전수 수집 — 호출 계획(plan)과 응답 가공(collect). 네트워크 없음.

요청은 itda-hyve 가 보낸다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``). 이 스크립트는
batch ``plan_file`` 로 넘길 호출 목록을 회차 폴더에 쓰고, itda-hyve 가 ``save_as`` 로 저장한 응답을
읽어 전량 대조·정규화만 한다. 모자라면 다음 계획을 쓴다 — 모델은 쪽 번호·저장 이름을 짓지 않는다.

    # 1) 계획 — 소스마다 1쪽. 받기 전에 예상 호출 수를 사용자에게 알린다
    python3 survey_crawl.py plan list kstartup --run-dir <회차> --save-dir <회차 호스트 경로>
    # 2) itda-hyve batch({"save_dir": …, "plan_file": "plan-list-1.json"})
    # 3) 판정 — 모자라면 다음 계획(plan-list-2*.json)을 쓰고 exit 1. 다 모이면 survey.jsonl·run_manifest.json
    python3 survey_crawl.py collect list --run-dir <회차> --next-plan

    # 상세·첨부 — 후보를 지목하면 상세를 받고, 상세가 알려 준 첨부(robots·정확한 호스트 통과분)를 다음 계획으로
    python3 survey_crawl.py plan detail kstartup:179329 bizinfo:PBLN_000000000126903 --run-dir <회차>
    python3 survey_crawl.py collect detail --run-dir <회차> --next-plan

계약 정본은 ../references/cli-contract.md 다.

종료코드: 0 전수 · 1 계획 더 받을 것(incomplete) 또는 입력 오류 · 2 partial(커버리지 불완전) · 3 차단(수동 확인).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import detailing  # noqa: E402
import listing  # noqa: E402
from plan_io import PlanLog, next_plan_name, write_plan  # noqa: E402
from run_manifest import make_run, update_manifest  # noqa: E402

KST = timezone(timedelta(hours=9))
STATE_LIST = "funding-list.json"
STATE_DETAIL = "funding-detail.json"
SURVEY = "survey.jsonl"


class CliError(Exception):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


def _emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def _today() -> str:
    return datetime.now(KST).date().isoformat()


def _run_dir(arg: str, *, create: bool = False) -> Path:
    d = Path(arg).expanduser()
    if create:
        d.mkdir(parents=True, exist_ok=True)
    if not d.is_dir():
        raise CliError("args", f"회차 폴더가 없다: {d}")
    return d


_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def _save_dir(arg: str) -> str:
    """itda-hyve 가 도는 **호스트**의 절대 경로 — 스크립트가 도는 곳의 규칙으로 판정하지 않는다.

    Cowork 는 리눅스 VM 에서 스크립트를 돌리고 호스트는 Windows 일 수 있다. 리눅스의 ``os.path.isabs`` 는
    ``C:\\Users\\…`` 를 상대 경로로 본다(W10 리뷰 M1). 값은 계획 파일에 문자열로만 실린다.
    """
    if not arg or not (arg.startswith("/") or _WIN_ABS.match(arg) or arg.startswith("\\\\")):
        raise CliError("args", "--save-dir 는 회차 폴더의 **호스트 절대 경로**다(/Users/…, C:\\Users\\…, \\\\서버\\… — "
                               "Cowork 는 연결 폴더의 호스트 경로 + 하위 경로)")
    root = len(arg) if len(arg) <= 3 and _WIN_ABS.match(arg) else 1
    return arg[:root] + arg[root:].rstrip("/\\")


def _load_state(run_dir: Path, name: str) -> dict[str, Any]:
    p = run_dir / name
    if not p.is_file():
        raise CliError("input", f"{name} 이 없다 — plan 을 먼저 실행한다")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError("input", f"{name} 을 읽을 수 없다: {exc}") from exc


def _planned(run_dir: Path) -> PlanLog:
    try:
        return PlanLog.read(run_dir)
    except ValueError as exc:
        raise CliError("input", str(exc)) from exc


def _plan_out(run_dir: Path, stem: str, calls: list[dict[str, Any]], save_dir: str, path_arg: str | None) -> dict[str, Any]:
    path = Path(path_arg).expanduser() if path_arg and path_arg != "auto" else next_plan_name(run_dir, stem)
    try:
        return write_plan(path, run_dir, calls, save_dir)
    except ValueError as exc:
        raise CliError("args", str(exc)) from exc


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def _sources(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in names:
        for s in (listing.ALL_SOURCES if n == "all" else [n]):
            if s not in out:
                out.append(s)
    return out


def cmd_plan_list(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_dir, create=True)
    save_dir = _save_dir(args.save_dir)
    if (run_dir / STATE_LIST).exists():
        raise CliError("args", f"이 회차 폴더에는 이미 목록 계획이 있다({STATE_LIST}) — 새 회차 폴더를 만든다")
    sources = _sources(args.sources)
    active = [s for s in sources if s in listing.ACTIVE_SOURCES]
    caps = {s: (args.max_pages or listing.DEFAULT_CAP[s]) for s in active}
    state = {"schema": 1, "sources": sources, "today": _today(), "smoke": bool(args.smoke),
             "caps": caps, "save_dir": save_dir}
    out: dict[str, Any] = {"status": "ok", "run_dir": str(run_dir), "sources": sources}
    if "kocca" in sources:
        out["inactive"] = {"kocca": listing.KOCCA_INACTIVE_REASON}
    def _typical(s: str) -> int:
        if args.smoke:
            return 1
        pages = min(listing.TYPICAL_PAGES[s], caps.get(s, 0))
        # 2회전의 1쪽 괄호(앞·끝)가 두 호출을 더한다(kstartup·bizinfo·nipa)
        return pages + (2 if s in listing.SNAPSHOT and pages > 1 else 0)
    typical = {s: _typical(s) for s in sources}
    total = sum(typical.values())
    out["estimate"] = {
        "typical_calls": typical, "total_calls": total,
        "note": "2026-09-30 실측 쪽 수 + 1쪽 괄호 2호출 기준 — 실제 분모는 1쪽을 받아 봐야 안다. 받는 사이 목록이 바뀌면 받은 쪽 전부를 한 번 더 받는다. 받기 전에 사용자에게 알린다",
    }
    if not active:
        (run_dir / STATE_LIST).write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        out["detail"] = "받을 소스가 없다 — collect list 로 매니페스트만 남긴다"
        _emit(out)
        return 0
    calls = [listing.page_call(s, 1) for s in active]
    out.update(_plan_out(run_dir, "plan-list", calls, save_dir, args.write))
    (run_dir / STATE_LIST).write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _emit(out)
    return 0


def cmd_collect_list(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_dir)
    state = _load_state(run_dir, STATE_LIST)
    try:
        files = listing.list_files(run_dir)
    except ValueError as exc:
        raise CliError("input", str(exc)) from exc
    planned = _planned(run_dir)
    results: list[listing.SourceResult] = []
    for s in state["sources"]:
        if s == "kocca":
            r = listing.SourceResult("kocca", "inactive", stop_reason="robots-disallowed", coverage="none")
            r.errors.append(listing.KOCCA_INACTIVE_REASON)
            results.append(r)
            continue
        results.append(listing.collect_source(
            s, files.get(s, {}), today=state["today"], cap=state["caps"][s], smoke=state["smoke"],
            log=planned))

    summary = {r.source: _summary(r) for r in results}
    pending = [r for r in results if r.status == "incomplete"]
    if pending:
        calls = [c for r in pending for c in r.calls]
        out: dict[str, Any] = {
            "status": "incomplete", "error": "incomplete",
            "detail": ("더 받을 쪽이 있다 — batch_args 를 **전부** 차례로 부른 뒤에(실패한 호출은 그 save_as 에 실패 자리를 쓰고) "
                       "collect list 를 다시 실행한다"),
            "sources": summary, "next_call_count": len(calls),
        }
        trunc = {r.source: r.need_pages for r in results if r.will_truncate}
        if trunc:
            out["will_truncate"] = True
            out["need_pages"] = trunc
            out["detail"] += (". 쪽 상한을 넘는 소스가 있다(need_pages) — 받기 전에 사용자에게 알리고, "
                              "전부 받으려면 새 회차에서 --max-pages 를 올린다")
        if args.next_plan:
            out.update(_plan_out(run_dir, "plan-list", calls, state["save_dir"], args.next_plan))
            out["next_calls_preview"] = out.pop("calls_preview")
        else:
            # 계획 파일을 쓰지 않으면 이력이 남지 않아 없는 파일 상한·재동기화 횟수·회전 상한·1쪽 대조가 동작하지
            # 않는다(3차 리뷰 P7) — 이 방식은 미리보기다. 받으려면 --next-plan 으로 계획 파일을 쓴다.
            out["next_calls"] = calls
            out["preview_only"] = True
            out["detail"] += (" — 미리보기: --next-plan 없이는 계획 이력이 남지 않아 상한·대조가 동작하지 않는다. "
                              "받을 때는 --next-plan 을 준다")
        _emit(out)
        return 1

    records = [rec for r in results for rec in r.records]
    runs = [_run_entry(r) for r in results]
    survey = run_dir / SURVEY
    present = None
    if records:
        tmp = survey.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, survey)
        present = {rec.get("source") for rec in records}
    manifest = update_manifest(str(survey), runs, present_sources=present)
    blocked = any(r.status == "manual" for r in results)
    partial = any(r.status == "partial" for r in results)
    code = 3 if blocked else (2 if partial else 0)
    out = {
        "status": "blocked" if blocked else ("partial" if partial else "ok"),
        "collected": len(records),
        "survey": str(survey) if records else None,
        "manifest": manifest,
        "sources": summary,
    }
    if not records:
        out["detail"] = "수집 0건 — survey.jsonl 을 쓰지 않았다(직전 파일 보존). 차단·점검·사이트 개편을 의심한다"
    warnings = [w for r in results for w in r.warnings]
    if warnings:
        out["warnings"] = warnings
    _emit(out)
    return code


def _summary(r: listing.SourceResult) -> dict[str, Any]:
    d: dict[str, Any] = {"status": r.status, "pages_fetched": r.pages_fetched}
    for k in ("last_page", "reported_total"):
        if getattr(r, k) is not None:
            d[k] = getattr(r, k)
    if r.status != "incomplete":
        d.update({"collected": len(r.records), "stop_reason": r.stop_reason, "coverage": r.coverage})
    else:
        d["pending_calls"] = len(r.calls)
    if r.counted:
        d["counted"] = r.counted
    if r.dropped:
        d["dropped"] = r.dropped
    if r.errors:
        d["errors"] = r.errors
    return d


def _run_entry(r: listing.SourceResult) -> dict[str, Any]:
    code = {"ok": 0, "inactive": 0, "partial": 2, "manual": 3}[r.status]
    run = make_run(r.source, r.status, code, pages_fetched=r.pages_fetched, collected=len(r.records),
                   stop_reason=r.stop_reason, errors=r.errors, reported_total=r.reported_total,
                   duplicates=r.duplicates)
    run["coverage"] = r.coverage
    if r.last_page is not None:
        run["last_page"] = r.last_page
    if r.counted:
        run["counted"] = dict(sorted(r.counted.items()))
    if r.dropped:
        run["dropped"] = dict(sorted(r.dropped.items()))
    return run


# ---------------------------------------------------------------------------
# detail
# ---------------------------------------------------------------------------

def cmd_plan_detail(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_dir)
    state_path = run_dir / STATE_DETAIL
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"schema": 1, "targets": []}
    save_dir = args.save_dir or state.get("save_dir")
    if not save_dir and (run_dir / STATE_LIST).is_file():
        save_dir = _load_state(run_dir, STATE_LIST).get("save_dir")
    save_dir = _save_dir(save_dir or "")
    try:
        records = detailing.load_records(run_dir / SURVEY)
    except ValueError as exc:
        raise CliError("input", f"{SURVEY} 을 읽을 수 없다: {exc}") from exc
    have = {(t["source"], t["id"]) for t in state["targets"]}
    added, refused, calls = [], [], []
    for spec in args.targets:
        try:
            t = detailing.resolve(spec, records)
        except detailing.TargetError as exc:
            refused.append({"target": spec, "reason": str(exc)})
            continue
        if (t.source, t.id) in have:
            continue
        have.add((t.source, t.id))
        added.append(t)
        calls.append(detailing.detail_call(t))
    out: dict[str, Any] = {"status": "ok", "run_dir": str(run_dir), "added": len(added),
                           "targets": [f"{t.source}:{t.id}" for t in added]}
    if refused:
        out["refused"] = refused
    if not added:
        if refused:
            raise CliError("args", "요청할 대상이 없다 — " + "; ".join(r["reason"] for r in refused[:3]))
        out["detail"] = "모두 이미 계획한 대상이다 — collect detail 을 실행한다"
        _emit(out)
        return 0
    out.update(_plan_out(run_dir, "plan-detail", calls, save_dir, args.write))
    out["note"] = "상세를 받은 뒤 collect detail 이 첨부(소스 계약상 받을 수 있는 것만)를 다음 계획으로 쓴다"
    state["save_dir"] = save_dir
    state["targets"].extend(t.to_json() for t in added)
    state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _emit(out)
    return 0


def cmd_collect_detail(args: argparse.Namespace) -> int:
    run_dir = _run_dir(args.run_dir)
    state = _load_state(run_dir, STATE_DETAIL)
    targets = [detailing.Target(**t) for t in state["targets"]]
    try:
        detailing.check_names(run_dir)
    except ValueError as exc:
        raise CliError("input", str(exc)) from exc
    planned = _planned(run_dir)
    results = [detailing.collect_one(run_dir, t, planned) for t in targets]
    pending = [r for r in results if r.calls]
    if pending:
        calls = [c for r in pending for c in r.calls]
        out: dict[str, Any] = {
            "status": "incomplete", "error": "incomplete",
            "detail": ("더 받을 것(첨부·KOCCA 첨부 목록·다시 받을 상세)이 있다 — batch_args 를 **전부** 차례로 부른 뒤에 "
                       "collect detail 을 다시 실행한다"),
            "pending": {f"{r.target.source}:{r.target.id}": len(r.calls) for r in pending},
            "next_call_count": len(calls),
        }
        if args.next_plan:
            out.update(_plan_out(run_dir, "plan-detail", calls, state["save_dir"], args.next_plan))
            out["next_calls_preview"] = out.pop("calls_preview")
        else:
            # 계획 파일을 쓰지 않으면 이력이 남지 않아 없는 파일 상한·재동기화 횟수·회전 상한·1쪽 대조가 동작하지
            # 않는다(3차 리뷰 P7) — 이 방식은 미리보기다. 받으려면 --next-plan 으로 계획 파일을 쓴다.
            out["next_calls"] = calls
            out["preview_only"] = True
            out["detail"] += (" — 미리보기: --next-plan 없이는 계획 이력이 남지 않아 상한·대조가 동작하지 않는다. "
                              "받을 때는 --next-plan 을 준다")
        _emit(out)
        return 1

    survey = run_dir / SURVEY
    rows = []
    for r in results:
        key = f"{r.target.source}:{r.target.id}"
        row: dict[str, Any] = {"target": key, "status": r.status}
        if r.status in ("ok", "partial"):
            row["details"] = str(detailing.write_detail(run_dir, r))
            row["hash_version"] = r.hash_version
            row["attachments"] = {s: sum(1 for a in r.attachments if a.get("download_status") == s)
                                  for s in sorted({a.get("download_status") for a in r.attachments})}
            if r.target.record:
                if not survey.is_file() or not detailing.merge_detail(survey, r):
                    r.status, r.reason = "fail", f"{SURVEY} 에서 {key} 레코드를 찾지 못해 병합하지 못했다"
                    row["status"] = "fail"
            else:
                row["merged"] = False
                r.warnings.append(f"{key} — 목록 레코드가 없어 {SURVEY} 에 병합하지 않았다(상세 파일만)")
        if r.reason:
            row["reason"] = r.reason
        if r.warnings:
            row["warnings"] = r.warnings
        rows.append(row)
    manual = any(r.status == "manual" for r in results)
    bad = any(r.status in ("fail", "partial") for r in results)
    code = 3 if manual else (2 if bad else 0)
    _emit({"status": "blocked" if manual else ("partial" if bad else "ok"), "results": rows})
    return code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="survey_crawl.py",
                                 description="정부 지원사업 공고 전수 수집 — itda-hyve 호출 계획과 응답 가공")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="호출 계획(batch plan_file)을 회차 폴더에 쓴다")
    plan_sub = p_plan.add_subparsers(dest="what", required=True)
    pl = plan_sub.add_parser("list", help="목록 1쪽 계획")
    pl.add_argument("sources", nargs="+", choices=[*listing.ALL_SOURCES, "all"],
                    help="수집 소스(all = 5종 — kocca 는 robots 불허라 inactive 로만 기록)")
    pl.add_argument("--run-dir", required=True, help="회차 폴더(이 스크립트가 읽고 쓰는 경로)")
    pl.add_argument("--save-dir", required=True, help="같은 회차 폴더의 호스트 절대 경로(batch save_dir)")
    pl.add_argument("--max-pages", type=int, default=None,
                    help="소스당 쪽 상한(기본 150, smtech 30). 넘으면 받기 전에 will_truncate 로 알린다")
    pl.add_argument("--smoke", action="store_true", help="1쪽만 받아 파서·차단만 확인(커버리지 판정 없음)")
    pl.add_argument("--write", nargs="?", const="auto", default="auto",
                    help="계획 파일 경로(기본: 회차 폴더의 plan-list-<n>.json)")
    pl.set_defaults(func=cmd_plan_list)

    p_col = sub.add_parser("collect", help="저장된 응답을 판정·가공한다")
    col_sub = p_col.add_subparsers(dest="what", required=True)
    cl = col_sub.add_parser("list", help="목록 전량 대조 → survey.jsonl·run_manifest.json")
    cl.add_argument("--run-dir", required=True, help="회차 폴더")
    cl.add_argument("--next-plan", nargs="?", const="auto", default=None,
                    help="모자라면 다음 계획을 쓴다(값 없이 주면 plan-list-<n>.json 자동 이름)")
    cl.set_defaults(func=cmd_collect_list)

    pd = plan_sub.add_parser("detail", help="상세 페이지 계획(첨부는 collect detail 이 계획)")
    pd.add_argument("targets", nargs="+",
                    help="<source>:<id>(survey.jsonl 에서 url 을 찾는다) · 상세 URL · K-Startup 공고번호")
    pd.add_argument("--run-dir", required=True, help="회차 폴더")
    pd.add_argument("--save-dir", help="회차 폴더의 호스트 절대 경로(기본: plan list 때 준 값)")
    pd.add_argument("--write", nargs="?", const="auto", default="auto",
                    help="계획 파일 경로(기본: 회차 폴더의 plan-detail-<n>.json)")
    pd.set_defaults(func=cmd_plan_detail)

    cd = col_sub.add_parser("detail", help="상세·첨부 판정 → details/·해시·survey.jsonl 병합")
    cd.add_argument("--run-dir", required=True, help="회차 폴더")
    cd.add_argument("--next-plan", nargs="?", const="auto", default=None,
                    help="모자라면 다음 계획(첨부·KOCCA 팝업·다시 받기)을 쓴다")
    cd.set_defaults(func=cmd_collect_detail)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except CliError as exc:
        _emit({"status": "error", "error": exc.kind, "detail": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
