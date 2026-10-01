"""공공기관 게시판 수집 공통부 — 계획·전량 대조·첨부 검사 (네트워크 없음).

요청은 itda-hyve 가 보낸다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``). 이 모듈은 호출 계획을
itda-hyve batch ``plan_file`` 형식으로 쓰고, itda-hyve 가 ``save_as`` 로 저장한 파일을 읽어 판정만 한다.

같은 파일이 ``customs-notice``·``fss-docs`` 두 스킬의 ``scripts/`` 에 **바이트 동일한 사본**으로 있다.
사이트마다 다른 것(목록·상세 판독, 허용 경로)은 어댑터 모듈(``customs_board``·``fss_board``)이 준다.
고치면 두 사본을 함께 고친다.

흐름(회차 폴더 ``--run-dir`` 하나에 한 번):
    plan list      → 목록 쪽 계획(plan-list-1.json)
    collect list   → 쪽마다 분모(전체 건수·마지막 쪽)·번호·중복을 대조해 ok / incomplete(다음 계획) / partial
    plan attach    → 고른 게시물의 첨부(또는 첨부 목록이 있는 상세) 계획
    collect attach → 첨부 파일 바이트 검사(형식·잘림·크기) — ok / incomplete / partial

회차 상태는 ``board-state.json`` 에 스크립트가 쓴다(모델이 고치지 않는다).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import struct
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from hyve_input import HyveInputError, read_input

STATE_NAME = "board-state.json"
LIST_RESULT = "list-result.json"
BATCH_LIMIT = 40            # itda-hyve batch 는 40개를 넘으면 하나도 실행하지 않는다
BATCH_TIMEOUT_SEC = 50      # Cowork 는 도구 호출 하나를 60초에서 끊는다
LIST_TIMEOUT_SEC = 30
ATTACH_TIMEOUT_SEC = 45
MAX_PAGES = 20              # 한 회차 목록 쪽 상한(쪽당 10건 → 200건)
MAX_ATTACH_POSTS = 10       # 한 번에 첨부를 받을 게시물 상한
MAX_TRIES = 3               # 같은 파일을 받으려는 시도 상한(없음·실패 자리·HTTP 오류·잘림)
MAX_RESYNC = 2              # 받는 사이 목록이 바뀌었을 때 전 쪽 다시 받기 상한
MAX_ATTACH_BYTES = 50 * 1024 * 1024  # itda-hyve save_as 상한 — 이 크기면 잘렸다고 본다
PREVIEW = 3


class BoardError(Exception):
    """판정 불가 — ``kind`` 가 출력 JSON 의 ``error`` 값이다."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class PageStructureError(Exception):
    """목록·상세 화면에서 기대한 구조를 못 찾았다(사이트 개편·오류 화면)."""


# ---------------------------------------------------------------------------
# 차단·오류 화면
# ---------------------------------------------------------------------------

_BLOCK_MARKERS = (
    "captcha", "access denied", "비정상적인 접근", "접근이 차단", "접근이 제한",
    "자동입력 방지", "일시적으로 차단", "시스템안내",
)


def looks_blocked(text: str) -> bool:
    low = (text or "")[:6000].lower()
    return any(m in low for m in _BLOCK_MARKERS)


# ---------------------------------------------------------------------------
# 계획 파일
# ---------------------------------------------------------------------------

def http_call(call_id: str, url: str, save_as: str, timeout_sec: int, *,
              method: str = "GET", body: Optional[str] = None, headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """``http_request`` 한 칸. User-Agent·Cookie 는 싣지 않는다(itda-hyve 0.10.4 기본 UA).

    리다이렉트는 따라가지 않는다 — 허용 경로 밖으로 요청이 나가지 않게, 3xx 는 받은 파일로 실패 판정한다.
    POST(사이트가 폼으로 보내는 조회)는 ``method``·``body``·``headers``(Content-Type·Referer)를 싣고 ``retry_unsafe`` 를 켠다 —
    조회 전용이라 다시 보내도 안전하다. batch 는 GET 만 받으므로 POST 칸은 ``http_request`` 로 하나씩 부른다.
    """
    if save_as.startswith(("/", ".")) or ".." in save_as.split("/") or re.search(r"[^\x00-\x7f]", save_as):
        raise ValueError(f"save_as 는 한글 없는 회차 폴더 기준 상대 경로다: {save_as!r}")
    args: dict[str, Any] = {"url": url}
    if method != "GET":
        args.update({"method": method, "headers": dict(headers or {}), "body": body or "", "retry_unsafe": True})
    args.update({"follow_redirects": False, "timeout_sec": timeout_sec, "save_as": save_as})
    return {"id": call_id, "tool": "http_request", "args": args}


def _is_batchable(call: dict[str, Any]) -> bool:
    return call["args"].get("method", "GET") == "GET"


def write_plan(run_dir: Path, stem: str, calls: list[dict[str, Any]], save_dir: str) -> dict[str, Any]:
    """``<stem>.json`` (40개를 넘으면 ``<stem>a.json``·``<stem>b.json`` …)을 회차 폴더 바로 아래에 쓴다."""
    parts = [calls[i:i + BATCH_LIMIT] for i in range(0, len(calls), BATCH_LIMIT)] or [[]]
    names, batch_args = [], []
    for i, part in enumerate(parts):
        name = f"{stem}.json" if len(parts) == 1 else f"{stem}{chr(ord('a') + i)}.json"
        target = run_dir / name
        if target.exists():
            raise BoardError("input", f"계획 파일이 이미 있다: {name} — 회차 폴더를 손으로 고치지 않았는지 확인")
        payload = {"calls": part, "save_dir": save_dir, "timeout_sec": BATCH_TIMEOUT_SEC}
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        names.append(name)
        batch_args.append({"save_dir": save_dir, "plan_file": name})
    return {"plan_files": names, "batch_args": batch_args, "call_count": len(calls), "calls_preview": calls[:PREVIEW]}


def attempt_name(base: str, attempt: int) -> str:
    """첫 시도는 ``base``, 그다음은 ``<stem>-r<n><ext>`` — 받은 파일을 덮어쓰지 않는다."""
    if attempt <= 1:
        return base
    p = Path(base)
    return str(p.with_name(f"{p.stem}-r{attempt}{p.suffix}"))


# ---------------------------------------------------------------------------
# 회차 상태
# ---------------------------------------------------------------------------

def load_state(run_dir: Path) -> dict[str, Any]:
    p = run_dir / STATE_NAME
    if not p.is_file():
        raise BoardError("input", f"{STATE_NAME} 가 없다 — 이 폴더에서 plan list 부터 한다: {run_dir}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoardError("input", f"{STATE_NAME} 를 읽을 수 없다({exc})") from exc


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    (run_dir / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _round_attempted(run_dir: Path, rnd: dict[str, Any]) -> bool:
    """그 회전의 파일(응답 또는 실패 자리)이 하나라도 있으면 batch 를 부른 것으로 본다."""
    return any((run_dir / n).exists() for n in rnd["names"].values())


def _new_round(state: dict[str, Any], stage: str, tasks: dict[str, dict[str, Any]], keys: list[str],
               full: bool = False) -> dict[str, Any]:
    n = sum(1 for r in state["rounds"] if r["stage"] == stage) + 1
    names = {}
    for k in keys:
        t = tasks[k]
        t["tries"] = t.get("tries", 0) + 1
        names[k] = attempt_name(t["base"], t["tries"])
    rnd = {"stage": stage, "n": n, "names": names, "full": full}
    state["rounds"].append(rnd)
    return rnd


def _plan_round(run_dir: Path, state: dict[str, Any], stage: str, keys: list[str],
                full: bool = False) -> dict[str, Any]:
    tasks = state["tasks"][stage]
    rnd = _new_round(state, stage, tasks, keys, full)
    timeout = LIST_TIMEOUT_SEC if stage == "list" else ATTACH_TIMEOUT_SEC
    calls = []
    for k in keys:
        req = tasks[k].get("req") or {"url": tasks[k]["url"]}
        calls.append(http_call(f"{stage}-{k}-r{rnd['n']}", req["url"], rnd["names"][k], timeout,
                               method=req.get("method", "GET"), body=req.get("body"), headers=req.get("headers")))
    batch = [c for c in calls if _is_batchable(c)]
    single = [c for c in calls if not _is_batchable(c)]
    if batch:
        out = write_plan(run_dir, f"plan-{stage}-{rnd['n']}", batch, state["save_dir"])
    else:
        out = {"plan_files": [], "batch_args": [], "calls_preview": []}
    out["call_count"] = len(calls)
    # POST 는 batch 가 못 받는다 — 모델이 http_request 로 하나씩, 이 인자 그대로(save_dir 포함) 부른다
    out["single_calls"] = [dict(c["args"], save_dir=state["save_dir"]) for c in single]
    rnd["plan_files"] = out["plan_files"]
    rnd["single"] = len(single)
    rnd["single_calls"] = out["single_calls"]
    return out


def _base_index(state: dict[str, Any], stage: str) -> int:
    """그 단계에서 가장 늦은 "전 쪽" 회전(첫 회전·재동기화)의 위치. 그 앞 회전의 파일은 쓰지 않는다(리뷰 m2)."""
    base = 0
    for i, rnd in enumerate(state["rounds"]):
        if rnd["stage"] == stage and rnd.get("full"):
            base = i
    return base


def _latest(run_dir: Path, state: dict[str, Any], stage: str, key: str, since: int = 0) -> tuple[Optional[Path], int]:
    """그 작업의 파일 중 ``since`` 뒤 가장 늦은 회전의 것(있는 것만)과 그 회전 위치."""
    for i in range(len(state["rounds"]) - 1, since - 1, -1):
        rnd = state["rounds"][i]
        if rnd["stage"] == stage and key in rnd["names"] and (run_dir / rnd["names"][key]).exists():
            return run_dir / rnd["names"][key], i
    return None, -1


def _mark_bad(task: dict[str, Any], rel: str) -> None:
    """나쁜 파일(실패 자리·HTTP 오류·잘림·판독 실패)을 상태에 남긴다 — 회전을 넘어 시도 수를 센다."""
    if rel not in task.setdefault("bad", []):
        task["bad"].append(rel)


def _failed_tries(run_dir: Path, state: dict[str, Any], stage: str, key: str, since: int = 0) -> int:
    """``since`` 뒤 시도된 회전 중 그 작업의 파일이 없거나 나빴던 회수.

    목록은 ``since`` 가 가장 늦은 전 쪽 회전이라 재동기화 뒤에는 새로 센다(리뷰 m5).
    """
    bad = set(state["tasks"][stage][key].get("bad", []))
    n = 0
    for rnd in state["rounds"][since:]:
        if rnd["stage"] != stage or key not in rnd["names"] or not _round_attempted(run_dir, rnd):
            continue
        name = rnd["names"][key]
        if not (run_dir / name).exists() or name in bad:
            n += 1
    return n


def _round_calls(state: dict[str, Any], rnd: dict[str, Any]) -> dict[str, Any]:
    """그 회전을 부르는 방법 — 계획을 낸 출력을 잃어도 다시 부를 수 있게(재확인 N2)."""
    return {"batch_args": [{"save_dir": state["save_dir"], "plan_file": n} for n in rnd.get("plan_files") or []],
            "single_calls": list(rnd.get("single_calls") or [])}


def _check_fetched(run_dir: Path, state: dict[str, Any], stage: str) -> tuple[Optional[dict[str, Any]], set]:
    """마지막 회전의 파일이 하나도 없으면 ``not_fetched``(그 회전의 호출을 다시 싣는다). 같은 회전에서 세 번째면 끝낸다(리뷰 m1).

    회전의 호출이 전부 실패했는데 실패 자리를 쓰지 않으면 파일이 영영 없다 — 그 끝이 필요하다.
    목록은 ``partial: not_received`` 로 끝내고, 첨부는 그 회전의 작업만 "받지 못함" 으로 두고 이미 난 판정과 함께 결과를 낸다
    — 반환값의 둘째가 그 작업 집합이다(재확인 N2).
    """
    rounds = [r for r in state["rounds"] if r["stage"] == stage]
    if not rounds:
        raise BoardError("input", f"{stage} 계획이 없다 — plan {stage} 부터 한다")
    last = rounds[-1]
    if _round_attempted(run_dir, last):
        return None, set()
    last["unfetched"] = last.get("unfetched", 0) + 1
    save_state(run_dir, state)
    what = "계획의 호출(" + (", ".join(last.get("plan_files") or []) or "") + \
           (" + " if last.get("plan_files") and last.get("single") else "") + \
           (f"단건 {last.get('single')}개" if last.get("single") else "") + ")"
    if last["unfetched"] >= MAX_TRIES:
        if stage == "attach":
            return None, set(last["names"])
        return {"status": "partial", "stage": stage, "stop_reason": "not_received",
                "errors": [f"{what}을 {MAX_TRIES}번 확인했는데 받은 파일이 하나도 없다 — 호출이 전부 실패했다면 호출마다 실패 자리를 써야 한다"]}, set()
    return {"status": "error", "error": "not_fetched",
            "detail": f"{what}의 파일이 하나도 없다 — 아래 batch_args·single_calls 를 전부 부른 뒤 collect 한다."
                      " 불렀는데 전부 실패했다면 호출마다 실패 자리를 쓴다"
                      " (Cowork 는 --run-dir 이 itda-hyve save_dir 와 같은 폴더인지 확인)",
            **_round_calls(state, last)}, set()


# ---------------------------------------------------------------------------
# 입력 파일
# ---------------------------------------------------------------------------

def read_file(path: Path) -> tuple[Optional[bytes], str]:
    """hyve 층 판독. (본문, "") 또는 (None, 실패 사유)."""
    try:
        body = read_input(path)
    except HyveInputError as exc:
        return None, f"{exc.kind}: {exc}"
    return body.data, ""


# ---------------------------------------------------------------------------
# 목록 — 계획·전량 대조
# ---------------------------------------------------------------------------

_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def host_abs_path(path: str) -> bool:
    """itda-hyve 가 도는 **호스트**의 절대 경로인가 — 스크립트가 도는 곳의 규칙으로 판정하지 않는다(리뷰 M1).

    Cowork 는 리눅스 VM 에서 스크립트를 돌리고 호스트는 Windows 일 수 있다. 리눅스의 ``Path.is_absolute`` 는
    ``C:\\Users\\…`` 를 상대 경로로 본다. 이 값은 계획 파일에 문자열로만 실린다.
    """
    return bool(path) and (path.startswith("/") or bool(_WIN_ABS.match(path)) or path.startswith("\\\\"))


def cmd_plan_list(adapter, run_dir: Path, save_dir: str, pages: int) -> dict[str, Any]:
    if not 1 <= pages <= MAX_PAGES:
        raise BoardError("args", f"--pages 는 1~{MAX_PAGES} 이다")
    if not host_abs_path(save_dir):
        raise BoardError("args", "--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로다(/Users/…, C:\\Users\\…, \\\\서버\\…)")
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / STATE_NAME).exists():
        raise BoardError("input", "이 회차 폴더에는 이미 목록 계획이 있다 — 다시 받으려면 새 회차 폴더를 쓴다")
    tasks = {f"p{p:03d}": {"page": p, "url": adapter.list_url(p), "base": f"raw/list/p{p:03d}.html",
                           **({"req": adapter.list_request(p)} if hasattr(adapter, "list_request") else {})}
             for p in range(1, pages + 1)}
    state = {"skill": adapter.SKILL, "save_dir": save_dir, "pages": pages, "resyncs": 0,
             "tasks": {"list": tasks, "attach": {}}, "rounds": []}
    out = _plan_round(run_dir, state, "list", list(tasks), full=True)
    save_state(run_dir, state)
    est = {"calls": pages, "batches": len(out["plan_files"]), "single_calls": len(out["single_calls"])}
    return {"status": "planned", "stage": "list", "estimate": est, **out}


def _reconcile(pages: dict[int, dict[str, Any]], size: int) -> list[str]:
    """받은 쪽들이 한 목록의 이어진 조각인지 본다. 어긋남 사유 목록(빈 목록이면 전량 일치)."""
    why: list[str] = []
    totals = {p: pg["total"] for p, pg in pages.items()}
    if len(set(totals.values())) > 1:
        why.append(f"쪽마다 전체 건수가 다르다 {sorted(totals.items())}")
    lasts = {pg["last_page"] for pg in pages.values()}
    if len(lasts) > 1:
        why.append("쪽마다 마지막 쪽 번호가 다르다")
    seen: dict[str, int] = {}
    for p, pg in sorted(pages.items()):
        total = pg["total"]
        start = total - (p - 1) * size
        expect = max(0, min(size, start))
        if len(pg["rows"]) != expect:
            why.append(f"{p}쪽 행이 {len(pg['rows'])}개다(전체 {total}건이면 {expect}개)")
        for i, r in enumerate(pg["rows"]):
            if r["no"] != start - i:
                why.append(f"{p}쪽 {i + 1}번째 행 번호가 {r['no']} 다({start - i} 이어야 한다)")
                break
        for r in pg["rows"]:
            if r["id"] in seen:
                why.append(f"게시물 {r['id']} 가 {seen[r['id']]}쪽과 {p}쪽에 함께 있다")
            seen[r["id"]] = p
    return why


def _filter(rows: list[dict[str, Any]], keyword: Optional[str], date_from: Optional[str], date_to: Optional[str]):
    out = []
    for r in rows:
        if keyword and keyword not in r["title"]:
            continue
        if date_from and r["date"] < date_from:
            continue
        if date_to and r["date"] > date_to:
            continue
        out.append(r)
    return out


def cmd_collect_list(adapter, run_dir: Path, *, next_plan: bool, limit: int, keyword: Optional[str],
                     date_from: Optional[str], date_to: Optional[str], xlsx: Optional[str]) -> dict[str, Any]:
    state = load_state(run_dir)
    stop, _ = _check_fetched(run_dir, state, "list")
    if stop:
        return stop
    tasks = state["tasks"]["list"]
    since = _base_index(state, "list")
    parsed: dict[int, tuple[dict[str, Any], str]] = {}
    used_rounds: set[int] = set()
    first_text = ""
    retry: list[str] = []
    errors: list[str] = []
    for key, t in sorted(tasks.items()):
        p = t["page"]
        path, where = _latest(run_dir, state, "list", key, since)
        why = "파일 없음"
        if path is not None:
            data, why = read_file(path)
            if data is not None:
                text = data.decode("utf-8", errors="replace")
                try:
                    parsed[p] = (adapter.parse_list(text), path.name)
                    used_rounds.add(where)
                    if p == 1:
                        first_text = text
                    continue
                except PageStructureError as exc:
                    if looks_blocked(text):
                        return {"status": "blocked", "stage": "list", "detail": f"{p}쪽이 차단·안내 화면이다({path.name})"}
                    why = f"화면 구조를 못 읽었다 — {exc}"
            _mark_bad(t, path.relative_to(run_dir).as_posix())
        if _failed_tries(run_dir, state, "list", key, since) < MAX_TRIES:
            retry.append(key)
        else:
            errors.append(f"{p}쪽을 {MAX_TRIES}번 받지 못했다 — {why}")

    if errors:
        save_state(run_dir, state)
        return {"status": "partial", "stage": "list", "stop_reason": "not_received", "errors": errors}
    if retry:
        if len(tasks) > 1 and state["resyncs"] < MAX_RESYNC:
            # 그 쪽만 다시 받으면 곧 회전이 섞여 전 쪽을 또 받는다 — 한 번에 전 쪽을 다시 계획한다(재확인 N5)
            return _resync(run_dir, state, sorted(tasks), next_plan,
                           f"{len(retry)}쪽을 받지 못했다 — 쪽들이 한 시점이 되게 전 쪽을 한 회전에 다시 받는다")
        return _next(run_dir, state, "list", retry, next_plan, f"{len(retry)}쪽을 다시 받는다")

    if hasattr(adapter, "check_profile"):
        # 스킬이 보내는 폼 본문(상수)이 지금 화면의 폼과 같은가 — 다르면 옛 본문을 계속 보내게 된다(재확인 N3)
        changed = adapter.check_profile(first_text)
        if changed:
            return {"status": "error", "error": "profile_changed", "stage": "list",
                    "detail": "사이트의 요청 폼이 바뀌었다 — 스킬 업데이트가 필요하다(요청 프로파일을 다시 뜬다): " + "; ".join(changed)}
    last_page = parsed[1][0]["last_page"]
    pages: dict[int, dict[str, Any]] = {}
    beyond = []
    for p, (pg, name) in sorted(parsed.items()):
        if p > max(last_page, 1):
            beyond.append(p)      # 마지막 쪽 너머 — 사이트가 어떻게 그리든 쓰지 않는다
            continue
        if pg["page"] != p:
            return {"status": "partial", "stage": "list", "stop_reason": "mismatch",
                    "errors": [f"{name} 는 {pg['page']}쪽 화면이다({p}쪽이어야 한다)"]}
        pages[p] = pg

    first = pages[1]
    if not first["rows"]:
        return {"status": "partial", "stage": "list", "stop_reason": "empty",
                "errors": [f"1쪽에 게시물이 없다(전체 {first['total']}건 표시) — 사이트 점검·구조 변경일 수 있다"]}
    size = adapter.PAGE_SIZE
    if first["last_page"] != -(-first["total"] // size):
        return {"status": "partial", "stage": "list", "stop_reason": "structure",
                "errors": [f"전체 {first['total']}건 · 마지막 {first['last_page']}쪽이 쪽당 {size}건과 맞지 않는다 — 쪽 크기가 바뀌었다"]}
    drift = _reconcile(pages, size)
    if drift:
        if state["resyncs"] >= MAX_RESYNC:
            return {"status": "partial", "stage": "list", "stop_reason": "drift", "errors": drift}
        return _resync(run_dir, state, sorted(tasks), next_plan,
                       "받는 사이 목록이 바뀌었다 — 전 쪽을 다시 받는다: " + "; ".join(drift[:3]))
    warnings = []
    if len(used_rounds) > 1:
        # 쪽마다 받은 시점이 다르다 — 그 사이 한 건 등록 + 한 건 삭제가 겹치면 분모·번호로는 못 잡는다(리뷰 m2)
        if state["resyncs"] < MAX_RESYNC:
            return _resync(run_dir, state, sorted(tasks), next_plan,
                           "쪽들을 서로 다른 회전에서 받았다 — 같은 시점이 되게 전 쪽을 한 회전에 다시 받는다")
        warnings.append("쪽들을 서로 다른 시점에 받았다 — 그 사이 등록과 삭제가 겹쳤다면 목록이 한 건 어긋날 수 있다")

    rows = [dict(r, page=p) for p in sorted(pages) for r in pages[p]["rows"]]
    total = first["total"]
    result = {"board": adapter.BOARD_NAME, "total": total, "last_page": first["last_page"],
              "pages": sorted(pages), "rows": rows}
    (run_dir / LIST_RESULT).write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    matched = _filter(rows, keyword, date_from, date_to)
    shown = matched[:limit]
    if beyond:
        warnings.append(f"게시판은 {last_page}쪽까지라 {beyond[0]}쪽부터는 쓰지 않았다")
    covered_all = len(rows) >= total
    oldest = rows[-1]["date"] if rows else ""
    if not covered_all and date_from and oldest and date_from < oldest:
        warnings.append(f"--from {date_from} 가 받은 범위(가장 오래된 {oldest})보다 이르다 — --pages 를 늘려 새 회차로 받는다")
    # 기간이 받은 범위 안에 온전히 들어 있으면 받은 쪽 밖에 더 있을 수 없다(리뷰 m9 — 거짓 경보)
    inside = bool(date_from and oldest and date_from >= oldest)
    if not covered_all and len(matched) < limit and (keyword or date_from or date_to) and not inside:
        warnings.append(f"받은 {len(pages)}쪽({len(rows)}건) 안에서만 찾았다 — 전체 {total}건")
    out = {"status": "ok", "stage": "list", "board": adapter.BOARD_NAME, "total": total,
           "last_page": first["last_page"], "pages": len(pages), "collected": len(rows),
           "matched": len(matched), "shown": len(shown), "rows": shown,
           "table": adapter.render_markdown(shown) if shown else "",
           "warnings": warnings, "source": adapter.SOURCE_NOTE}
    if not shown:
        out["note"] = "조건에 맞는 게시물이 없습니다"
    if xlsx and shown:
        try:
            adapter.write_xlsx(shown, xlsx)
        except OSError as exc:
            raise BoardError("output", f"xlsx 를 저장하지 못했다({exc}) — 폴더가 있는지·쓸 수 있는지 확인") from exc
        out["xlsx"] = xlsx
    return out


def _resync(run_dir: Path, state: dict[str, Any], keys: list[str], next_plan: bool, why: str) -> dict[str, Any]:
    """전 쪽을 한 회전에 다시 받는다. 그 회전이 새 기준이 되어 앞 회전의 파일은 쓰지 않는다."""
    if next_plan:
        state["resyncs"] += 1
    return _next(run_dir, state, "list", keys, next_plan, why, full=True)


def _next(run_dir: Path, state: dict[str, Any], stage: str, keys: list[str], next_plan: bool, why: str,
          full: bool = False, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    extra = extra or {}
    if not next_plan:
        return {"status": "incomplete", "stage": stage, "preview_only": True, "detail": why,
                "next_count": len(keys), "hint": "--next-plan 으로 다시 부르면 다음 계획을 쓴다", **extra}
    out = _plan_round(run_dir, state, stage, keys, full)
    save_state(run_dir, state)
    return {"status": "incomplete", "stage": stage, "detail": why, **extra, **out}


# ---------------------------------------------------------------------------
# 첨부 — 계획·검사
# ---------------------------------------------------------------------------

def host_path_allowed(url: str, host: str, prefixes: tuple[str, ...]) -> bool:
    """https + 정확한 호스트 + 허용 경로만. userinfo·다른 포트·이중 인코딩 위장은 거절.

    ``/`` 로 끝나는 항목은 접두, 아니면 경로 전체가 같아야 한다(``…/fileDown.doX`` 를 막는다 — 리뷰 m9).
    """
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https" or parts.hostname != host or parts.port not in (None, 443) or "@" in parts.netloc:
        return False
    path = parts.path
    if "%" in path or ";" in path or "/../" in path or path.endswith("/.."):
        return False
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes)


def ext_of(filename: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{1,5})\s*$", filename or "")
    return m.group(1).lower() if m else "bin"


def _load_list_result(run_dir: Path) -> dict[str, Any]:
    p = run_dir / LIST_RESULT
    if not p.is_file():
        raise BoardError("input", "목록을 ok 로 끝낸 뒤에 첨부를 계획한다(list-result.json 없음)")
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_plan_attach(adapter, run_dir: Path, numbers: list[str]) -> dict[str, Any]:
    state = load_state(run_dir)
    if state["tasks"]["attach"]:
        raise BoardError("input", "이 회차에는 이미 첨부 계획이 있다 — 다른 게시물은 새 회차 폴더에서 목록부터 받는다")
    listing = _load_list_result(run_dir)
    by_no = {str(r["no"]): r for r in listing["rows"]}
    wanted = list(dict.fromkeys(str(n) for n in numbers))
    if not 1 <= len(wanted) <= MAX_ATTACH_POSTS:
        raise BoardError("args", f"게시물 번호를 1~{MAX_ATTACH_POSTS}개 준다")
    refused, tasks, posts = [], {}, {}
    for n in wanted:
        row = by_no.get(n)
        if row is None:
            refused.append({"no": n, "reason": "받은 목록에 없는 번호다"})
            continue
        stage_tasks, why = adapter.attach_tasks(row)
        if why:
            refused.append({"no": n, "reason": why})
            continue
        posts[n] = {"id": row["id"], "title": row["title"], "keys": list(stage_tasks)}
        tasks.update(stage_tasks)
    if not tasks:
        return {"status": "refused", "stage": "attach", "refused": refused,
                "detail": "받을 첨부가 없다" if not refused else "요청할 수 있는 대상이 없다"}
    state["tasks"]["attach"] = tasks
    state["posts"] = posts
    out = _plan_round(run_dir, state, "attach", list(tasks))
    save_state(run_dir, state)
    return {"status": "planned", "stage": "attach", "refused": refused, **out}


def cmd_collect_attach(adapter, run_dir: Path, *, next_plan: bool) -> dict[str, Any]:
    state = load_state(run_dir)
    stop, gave_up = _check_fetched(run_dir, state, "attach")
    if stop:
        return stop
    tasks = state["tasks"]["attach"]
    posts = state["posts"]
    retry: list[str] = []
    added: dict[str, dict[str, Any]] = {}
    verdicts: dict[str, dict[str, Any]] = {}
    for key, t in list(tasks.items()):
        if _too_large(t):
            verdicts[key] = _too_large(t)
            continue
        path, _ = _latest(run_dir, state, "attach", key)
        verdict: Optional[dict[str, Any]] = None
        why = "파일 없음"
        if path is not None:
            rel = path.relative_to(run_dir).as_posix()
            data, why = read_file(path)
            if data is not None and t["kind"] == "detail":
                try:
                    found = adapter.parse_detail(data.decode("utf-8", errors="replace"), t)
                    verdict = {"status": "ok", "attachments": len(found)}
                    for nk, nt in found.items():
                        if nk not in tasks:
                            added[nk] = nt
                except PageStructureError as exc:
                    verdict = {"status": "failed", "reason": f"상세 화면 판독 실패 — {exc}"}
            elif data is not None:
                ok, reason, digest = verify_attachment(data, t["ext"], t.get("size"))
                verdict = {"status": {True: "ok", False: "failed", None: "unverified_format"}[ok],
                           "reason": reason, "sha256": digest, "size": len(data), "local_path": rel}
            if verdict is None or verdict["status"] == "failed":
                _mark_bad(t, rel)
        if verdict is not None and verdict["status"] != "failed":
            verdicts[key] = verdict
        elif key in gave_up:
            verdicts[key] = verdict or {"status": "failed",
                                        "reason": f"계획의 호출을 {MAX_TRIES}번 확인했는데 파일이 오지 않았다 — 실패 자리도 없다"}
        elif _failed_tries(run_dir, state, "attach", key) < MAX_TRIES:
            retry.append(key)
        else:
            verdicts[key] = verdict or {"status": "failed", "reason": f"{MAX_TRIES}번 받지 못했다 — {why}"}
    for nk, nt in added.items():
        tasks[nk] = nt
        posts[nt["post"]]["keys"].append(nk)
        if _too_large(nt):
            verdicts[nk] = _too_large(nt)       # 받기 전에 실패가 정해져 있다 — 계획에 넣지 않는다(리뷰 m3)
        else:
            retry.append(nk)
    if retry:
        atts = [tasks[k] for k in retry if tasks[k]["kind"] == "att"]
        known = [t["size"] for t in atts if isinstance(t.get("size"), int)]
        extra = {"attach_files": len(atts), "attach_bytes_known": sum(known),
                 "attach_size_unknown": len(atts) - len(known)}
        return _next(run_dir, state, "attach", retry, next_plan,
                     f"받을 파일 {len(retry)}개" + (f"(상세에서 찾은 첨부 {len(added)}개 포함)" if added else ""),
                     extra=extra)

    results, all_ok = [], True
    for n, post in posts.items():
        files = []
        for k in post["keys"]:
            t, v = tasks[k], verdicts.get(k, {"status": "failed", "reason": "판정 없음"})
            if t["kind"] == "detail":
                if v["status"] != "ok":
                    files.append({"name": "(상세 화면)", **v})
                continue
            files.append({"name": t["name"], **v})
        status = "ok" if all(f["status"] == "ok" for f in files) else "partial"
        all_ok &= status == "ok"
        results.append({"no": n, "id": post["id"], "title": post["title"], "status": status, "files": files})
    save_state(run_dir, state)
    return {"status": "ok" if all_ok else "partial", "stage": "attach", "results": results,
            "note": "원래 파일 이름은 files[].name, 받은 파일은 회차 폴더 기준 files[].local_path"}


def _too_large(t: dict[str, Any]) -> Optional[dict[str, Any]]:
    size = t.get("size")
    if t["kind"] == "att" and isinstance(size, int) and size >= MAX_ATTACH_BYTES:
        return {"status": "failed", "reason": f"too_large — 게시판 표시 크기 {size}바이트가 itda-hyve 저장 상한(50MiB) 이상이라 받지 않았다"}
    return None


_OLE_UNCHECKED = "unchecked"


_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP = b"PK\x03\x04"
MAGIC = {
    "pdf": (b"%PDF-",),
    "hwp": (_OLE,), "doc": (_OLE,), "xls": (_OLE,), "ppt": (_OLE,),
    "hwpx": (_ZIP,), "docx": (_ZIP,), "xlsx": (_ZIP,), "pptx": (_ZIP,), "zip": (_ZIP,), "odt": (_ZIP,),
    "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",),
}


def _ole_truncated(data: bytes) -> str:
    """OLE(HWP·XLS 등) 잘림 — FAT 가 쓰는 마지막 섹터까지 파일 안에 있는지. 잘렸으면 사유."""
    size = len(data)
    if size < 512:
        return f"머리(512바이트)보다 짧다({size})"
    shift = struct.unpack_from("<H", data, 0x1E)[0]
    if shift not in (9, 12):
        return f"섹터 크기 표지가 이상하다({shift})"
    ss = 1 << shift
    if size % ss:
        return f"크기 {size} 가 섹터 크기 {ss} 의 배수가 아니다"
    n_sectors = size // ss - 1
    n_fat = struct.unpack_from("<I", data, 0x2C)[0]
    fat_secs = [x for x in struct.unpack_from("<109I", data, 0x4C) if x < 0xFFFFFFFA]
    if n_fat == 0 or n_fat > 109 or len(fat_secs) < n_fat:
        # 109개를 넘는 FAT(DIFAT 사슬, 약 7MB 이상 HWP)는 따라가지 않는다 — 끝까지 받았는지 모른다(리뷰 m3)
        return _OLE_UNCHECKED if n_fat > 109 else f"FAT 섹터 목록이 모자란다({len(fat_secs)}/{n_fat})"
    per = ss // 4
    last_used = -1
    for k, fs in enumerate(fat_secs[:n_fat]):
        if fs >= n_sectors:
            return f"FAT 섹터 {fs} 가 파일 밖이다(섹터 {n_sectors}개)"
        entries = struct.unpack_from(f"<{per}I", data, (fs + 1) * ss)
        for i, v in enumerate(entries):
            if v != 0xFFFFFFFF:
                last_used = max(last_used, k * per + i)
    if last_used >= n_sectors:
        return f"FAT 는 섹터 {last_used} 까지 쓰는데 파일에는 {n_sectors}개뿐이다"
    return ""


def verify_attachment(data: bytes, ext: str, declared_size: Optional[int] = None):
    """받은 첨부 바이트 검사. (ok, 사유, sha256) — ok 는 True·False·None(형식 규칙 없음)."""
    size = len(data)
    if size == 0:
        return False, "빈 파일", None
    if size >= MAX_ATTACH_BYTES:
        return False, "too_large — itda-hyve 저장 상한(50MiB)에 닿아 잘렸을 수 있다", None
    head = data[:512].lstrip(b"\xef\xbb\xbf").lstrip()
    if ext not in ("html", "htm", "xml", "svg") and head[:1] == b"<":
        return False, "soft_block_html — 첨부가 아닌 HTML 오류·안내 화면", None
    if declared_size is not None and declared_size != size:
        return False, f"크기 불일치 — 게시판은 {declared_size}바이트, 받은 파일은 {size}바이트", None
    magics = MAGIC.get(ext)
    if not magics:
        return None, f"unverified_format — .{ext} 는 형식 검사 규칙이 없다", None
    if not any(data.startswith(m) for m in magics):
        return False, f"형식 불일치 — .{ext} 인데 머리가 {data[:8].hex()}", None
    tail = data[-1024:]
    if ext == "pdf" and b"%%EOF" not in tail:
        return False, "잘린 PDF — 끝 표지(%%EOF)가 없다", None
    if magics[0] == _ZIP and b"PK\x05\x06" not in tail:
        return False, "잘린 ZIP 계열 — 중앙 디렉터리 끝이 없다", None
    if magics[0] == _OLE:
        why = _ole_truncated(data)
        if why == _OLE_UNCHECKED:
            return None, "unverified_format — FAT 섹터가 109개를 넘는 큰 OLE 는 끝 검사를 하지 않는다", None
        if why:
            return False, f"잘린 OLE — {why}", None
    if ext in ("jpg", "jpeg") and b"\xff\xd9" not in tail:
        return False, "잘린 JPEG — 끝 표지가 없다", None
    if ext == "png" and b"IEND" not in tail:
        return False, "잘린 PNG — IEND 가 없다", None
    return True, "", hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date(s: str) -> str:
    try:
        ok = bool(_DATE.match(s)) and datetime.date.fromisoformat(s).isoformat() == s
    except ValueError:
        ok = False
    if not ok:
        raise argparse.ArgumentTypeError(f"날짜는 있는 날의 YYYY-MM-DD 여야 합니다: {s}")
    return s


class _Parser(argparse.ArgumentParser):
    """인자 오류도 stdout JSON(``error: args``, exit 1)으로 — stderr 글·exit 2 는 partial 과 겹친다(리뷰 m6)."""

    def error(self, message: str):
        raise BoardError("args", message)


def build_parser(adapter) -> argparse.ArgumentParser:
    ap = _Parser(prog=adapter.PROG, description=f"{adapter.BOARD_NAME} 수집 — itda-hyve 가 받은 파일 가공")
    sub = ap.add_subparsers(dest="command", required=True, parser_class=_Parser)
    plan = sub.add_parser("plan", help="itda-hyve batch 계획을 쓴다")
    psub = plan.add_subparsers(dest="stage", required=True, parser_class=_Parser)
    pl = psub.add_parser("list")
    pl.add_argument("--run-dir", required=True, type=Path)
    pl.add_argument("--save-dir", required=True, help="itda-hyve save_dir(호스트 절대 경로)")
    pl.add_argument("--pages", type=int, default=1, help=f"받을 목록 쪽 수(1~{MAX_PAGES}, 쪽당 {adapter.PAGE_SIZE}건)")
    pa = psub.add_parser("attach")
    pa.add_argument("numbers", nargs="+", help="첨부를 받을 게시물 번호(목록의 no)")
    pa.add_argument("--run-dir", required=True, type=Path)
    col = sub.add_parser("collect", help="받은 파일을 판정한다")
    csub = col.add_subparsers(dest="stage", required=True, parser_class=_Parser)
    cl = csub.add_parser("list")
    cl.add_argument("--run-dir", required=True, type=Path)
    cl.add_argument("--next-plan", action="store_true", help="모자라면 다음 계획을 쓴다")
    cl.add_argument("--limit", type=int, default=10)
    cl.add_argument("--keyword", help="제목 키워드(받은 쪽 안에서)")
    cl.add_argument("--from", dest="date_from", type=_date)
    cl.add_argument("--to", dest="date_to", type=_date)
    cl.add_argument("--xlsx", help="xlsx 저장 경로")
    ca = csub.add_parser("attach")
    ca.add_argument("--run-dir", required=True, type=Path)
    ca.add_argument("--next-plan", action="store_true")
    return ap


EXIT = {"ok": 0, "planned": 0, "incomplete": 1, "error": 1, "partial": 2, "refused": 2, "blocked": 3}


def main(adapter, argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    try:
        args = build_parser(adapter).parse_args(argv)
        run_dir = args.run_dir.expanduser()
        if args.command == "plan" and args.stage == "list":
            out = cmd_plan_list(adapter, run_dir, args.save_dir, args.pages)
        elif args.command == "plan":
            out = cmd_plan_attach(adapter, run_dir, args.numbers)
        elif args.stage == "list":
            if args.limit < 1:
                raise BoardError("args", "--limit 은 1 이상이다")
            out = cmd_collect_list(adapter, run_dir, next_plan=args.next_plan, limit=args.limit,
                                   keyword=args.keyword, date_from=args.date_from, date_to=args.date_to,
                                   xlsx=args.xlsx)
        else:
            out = cmd_collect_attach(adapter, run_dir, next_plan=args.next_plan)
    except BoardError as exc:
        out = {"status": "error", "error": exc.kind, "detail": str(exc)}
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return EXIT.get(out["status"], 1)
