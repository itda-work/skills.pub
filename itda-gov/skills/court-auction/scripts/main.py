#!/usr/bin/env python3
"""court-auction CLI — 대법원 법원경매정보(courtauction.go.kr) 조회. 네트워크 없음.

요청은 itda-hyve ``http_request`` 가 보내고(규칙 ``cowork-network-via-hyve``), 이 스크립트는 둘만 한다.

    plan <종류> …  → 보낼 호출(``http_request`` 인자 그대로)을 만든다. 호출 수는 회차 폴더에 센다.
    collect --input <파일> → itda-hyve 가 ``save_as`` 로 저장한 응답을 판정·정규화한다.
    codes bid-types|usages|regions → 로컬 코드표(호출 없음)

사이트 요청은 전부 JSON POST 다(WebSquare 화면의 submission). 쿠키·warmup 없이 성립한다(2026-10-01
itda-hyve 실측 — 목록·상세·사건·물건검색·법원목록). batch 는 GET 만 받으므로 호출은 하나씩 부른다.
사이트가 짧은 시간의 연속 조회를 IP 로 막으므로(≈16회/30초 → 약 1시간) 회차당 호출 상한을 둔다.

출력은 JSON(stdout). 성공 ``{"ok": true, "status": "planned"|"ok", …}`` exit 0,
실패 ``{"ok": false, "code": <종류>, "error": <한국어 사유>}`` exit 4(인자 오류 포함).
read-only — 입찰 자동화는 제공하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.version_info < (3, 10):  # pragma: no cover - 런타임 가드
    sys.exit("court-auction은 Python 3.10+ 가 필요합니다.")

from codetables import describe_bid_type_code, list_bid_types, list_region_codes, list_usage_codes
from hyve_input import HyveHTTPError, HyveInputError, read_input
from normalize import (
    normalize_case_detail_response,
    normalize_court_codes_response,
    normalize_notice_detail_response,
    normalize_notice_list_response,
    normalize_property_search_response,
    strip_html,
)
from queries import (
    build_case_body,
    build_courts_body,
    build_notice_detail_body,
    build_notices_body,
    build_property_search_body,
)

BASE_URL = "https://www.courtauction.go.kr"
STATE_NAME = "court-auction-state.json"
SAVE_PREFIX = "court-auction/"
TIMEOUT_SEC = 50  # Cowork 전송 상한 60초보다 짧게
DEFAULT_MAX_CALLS = 10
MAX_CALLS_CAP = 15  # 사이트 차단 문턱(≈16회/30초) 아래
MIN_INTERVAL_SEC = 2
KST = timezone(timedelta(hours=9))

# 화면 주소 — 그 XHR 을 뜬 화면의 location.href(2026-10-01 aside, 메뉴로 들어간 화면). 브라우저는 이 주소를 Referer 로
# 붙인다. aside 훅은 setRequestHeader 값만 보므로 Origin·Referer 는 캡처값이 아니라 화면 주소로 재현한 값이다.
_NOTICE_SCREEN = f"{BASE_URL}/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ141M00.xml&pgjId=143M01"  # 경매공고 › 부동산매각공고
_SEARCH_SCREEN = f"{BASE_URL}/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"  # 경매물건 › 물건상세검색
_CASE_SCREEN = f"{BASE_URL}/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"  # 경매물건 › 경매사건검색(법원 목록도 부른다)

# 종류별 요청 — 경로·헤더는 aside 로 뜬 XHR 의 setRequestHeader 그대로(Origin·Referer 는 브라우저가 붙이는 값).
# User-Agent·Cookie 는 싣지 않는다(itda-hyve 0.10.4 기본 UA, 쿠키 불요 실측).
ENDPOINTS = {
    "notices": {
        "path": "/pgj/pgj143/selectRletDspslPbanc.on",
        "screen": _NOTICE_SCREEN,
        "headers": {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "submissionid": "mf_wfm_mainFrame_sbm_selectRletDspslPbanc",
            "SC-Userid": "SYSTEM",
        },
    },
    "notice-detail": {
        "path": "/pgj/pgj143/selectRletDspslPbancDtl.on",
        "screen": _NOTICE_SCREEN,
        "headers": {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "submissionid": "mf_wfm_mainFrame_sbm_rletDspslPbancDtlInfo",
            "SC-Userid": "SYSTEM",
        },
    },
    "case": {
        "path": "/pgj/pgj15A/selectAuctnCsSrchRslt.on",
        "screen": _CASE_SCREEN,
        "headers": {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "submissionid": "mf_wfm_mainFrame_sbm_selectCsDtlInf",
            "SC-Pgmid": "PGJ15AF01",
            "SC-Userid": "NONUSER",
        },
    },
    "search": {
        "path": "/pgj/pgjsearch/searchControllerMain.on",
        "screen": _SEARCH_SCREEN,
        "headers": {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch",
            "SC-Userid": "SYSTEM",
        },
    },
    "courts": {
        "path": "/pgj/pgj002/selectCortOfcLst.on",
        "screen": _CASE_SCREEN,
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
    },
}

_BLOCKED = (
    "법원경매 사이트가 자동화 접근을 차단했습니다(ipcheck=false). 같은 IP 로는 약 1시간 뒤에 다시 시도하거나, "
    "사람이 브라우저로 접속해 차단 해제 화면을 거쳐야 합니다. 자동으로 다시 시도하지 않습니다."
)


class CourtError(Exception):
    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.extra = extra


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _fail(exc: CourtError) -> int:
    out = {"ok": False, "code": exc.code, "error": str(exc)}
    out.update(exc.extra)
    _print(out)
    return 4


class _JsonArgumentParser(argparse.ArgumentParser):
    """인자 오류도 JSON + exit 4 (stderr 한 줄 + exit 2 로 새지 않게)."""

    def error(self, message):  # noqa: D401
        raise CourtError("args", f"인자 오류: {message}")


# ---------------------------------------------------------------------------
# 회차 폴더 상태
# ---------------------------------------------------------------------------

_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def host_abs_path(path: str) -> bool:
    """itda-hyve 가 도는 **호스트**의 절대 경로인가 — 스크립트가 도는 곳의 규칙으로 판정하지 않는다.

    Cowork 는 리눅스 VM 에서 스크립트를 돌리고 호스트는 Windows 일 수 있다(``C:\\Users\\…``·``\\\\서버\\…``).
    이 값은 호출 인자에 문자열로만 실린다(W10 리뷰 M1 과 같은 자리).
    """
    return bool(path) and (path.startswith("/") or bool(_WIN_ABS.match(path)) or path.startswith("\\\\"))


def _load_state(run_dir: Path) -> dict | None:
    p = run_dir / STATE_NAME
    if not p.is_file():
        return None
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CourtError("input", f"회차 상태 파일을 읽을 수 없습니다: {p} ({exc})") from exc
    if not isinstance(state, dict) or state.get("skill") != "court-auction":
        raise CourtError("input", f"court-auction 회차 상태 파일이 아닙니다: {p}")
    return state


def _save_state(run_dir: Path, state: dict) -> None:
    (run_dir / STATE_NAME).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _open_run(run_dir: Path, save_dir: str, max_calls: int | None) -> dict:
    if not host_abs_path(save_dir):
        raise CourtError("args", "--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로다(/Users/…, C:\\Users\\…, \\\\서버\\…)")
    if max_calls is not None and not 1 <= max_calls <= MAX_CALLS_CAP:
        raise CourtError("args", f"--max-calls 는 1~{MAX_CALLS_CAP} 이다(사이트 차단 문턱 ≈16회/30초)")
    run_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(run_dir)
    if state is None:
        state = {"skill": "court-auction", "save_dir": save_dir,
                 "max_calls": max_calls or DEFAULT_MAX_CALLS, "used": 0, "blocked": False, "calls": {}}
    elif state.get("save_dir") != save_dir:
        raise CourtError("args", f"이 회차 폴더의 --save-dir 는 {state.get('save_dir')!r} 다 — 같은 값을 쓰거나 새 회차 폴더를 쓴다")
    elif max_calls is not None and max_calls != state.get("max_calls"):
        # 말없이 버리면 모델은 상한이 바뀐 줄 안다(W12 리뷰 m1).
        raise CourtError(
            "args",
            f"이 회차의 호출 상한은 첫 plan 에서 정한 {state.get('max_calls')}회다 — --max-calls 를 빼거나, "
            "상한을 바꾸려면 새 회차 폴더로 시작한다",
        )
    if state.get("blocked"):
        raise CourtError("blocked", "이 회차에서 사이트 차단(ipcheck=false)을 받았다. " + _BLOCKED)
    return state


def _call_args(kind: str, body: dict, save_as: str, save_dir: str) -> dict:
    ep = ENDPOINTS[kind]
    headers = dict(ep["headers"])
    headers["Origin"] = BASE_URL
    headers["Referer"] = ep["screen"]
    return {
        "url": BASE_URL + ep["path"],
        "method": "POST",
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        "follow_redirects": False,
        "timeout_sec": TIMEOUT_SEC,
        "save_dir": save_dir,
        "save_as": save_as,
    }


def _plan_one(run_dir: Path, state: dict, kind: str, body: dict, save_as: str, query: dict) -> dict:
    """한 호출을 계획한다. 이미 받은 파일이 있으면 호출하지 않는다(같은 질의 재사용)."""
    if not re.fullmatch(r"[A-Za-z0-9/_.-]+", save_as) or save_as.startswith(("/", ".")) or ".." in save_as:
        raise CourtError("args", f"저장 이름은 한글·공백 없는 상대 경로여야 한다: {save_as!r}")
    local = run_dir / save_as
    collect_cmd = f'collect --run-dir "$R" --input "$R/{save_as}"'
    base = {"ok": True, "kind": kind, "save_as": save_as, "local_path": str(local)}
    if local.is_file():
        # 같은 저장 이름 = 같은 요청 본문이라 파일은 그대로 쓰지만, 로컬에서 거르는 조건(공고 목록의 일자 등)은 질의마다
        # 다르다 — 이번 질의로 갈아 끼운다. 옛 질의를 두면 월을 물었는데 그날만 남긴다(W12 리뷰 M3).
        prev = state["calls"].get(save_as) or {}
        state["calls"][save_as] = {**prev, "kind": kind, "query": query}
        _save_state(run_dir, state)
        return {**base, "status": "fetched", "calls": [], "next": collect_cmd,
                "calls_used": state["used"], "calls_remaining": state["max_calls"] - state["used"],
                "detail": "이 회차에 이미 받은 파일이 있다 — 호출하지 않고 collect 한다."}
    if state["used"] >= state["max_calls"]:
        raise CourtError(
            "budget",
            f"이 회차의 호출 상한({state['max_calls']}회)을 다 썼다. 사이트 IP 차단을 피하기 위한 안전장치다 — "
            "정말 더 필요하면 사용자에게 알리고 잠시 쉰 뒤 새 회차 폴더로 시작한다.",
            calls_used=state["used"],
        )
    state["used"] += 1
    state["calls"][save_as] = {"kind": kind, "query": query,
                               "planned_at": datetime.now(KST).isoformat(timespec="seconds")}
    _save_state(run_dir, state)
    return {**base, "status": "planned", "calls": [_call_args(kind, body, save_as, state["save_dir"])],
            "next": collect_cmd, "min_interval_sec": MIN_INTERVAL_SEC,
            "calls_used": state["used"], "calls_remaining": state["max_calls"] - state["used"]}


def _token(value: str) -> str:
    """저장 이름 조각 — 영숫자만. 아니면 짧은 해시."""
    text = str(value or "")
    return text if re.fullmatch(r"[A-Za-z0-9]{1,16}", text) else "h" + hashlib.sha1(text.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def _find_notice_row(run_dir: Path, state: dict, notice_id: str) -> dict:
    """회차에서 받은 목록 파일에서 공고 행을 찾는다 — 모델이 행 값을 옮겨 적지 않는다."""
    seen = 0
    for save_as, meta in state.get("calls", {}).items():
        if meta.get("kind") != "notices" or not (run_dir / save_as).is_file():
            continue
        seen += 1
        payload = _read_payload(run_dir / save_as)
        for row in (payload.get("data") or {}).get("dlt_rletDspslPbancLst") or []:
            if isinstance(row, dict) and row.get("dspslRealId") == notice_id:
                return row
    if not seen:
        raise CourtError("input", "이 회차에 받은 공고 목록이 없다 — plan notices → 호출 → collect 로 목록을 먼저 받는다.")
    raise CourtError("input", f"받은 공고 목록에 noticeId {notice_id!r} 가 없다 — collect 결과의 items[].noticeId 를 그대로 쓴다.")


def cmd_plan(args) -> dict:
    run_dir = Path(args.run_dir)
    state = _open_run(run_dir, args.save_dir, getattr(args, "max_calls", None))
    try:
        return _plan_kind(args, run_dir, state)
    except CourtError as exc:
        # 계획 중에 읽은 저장 파일(공고 펼치기의 목록)이 차단 응답이어도 회차를 멈춘다 — collect 와 같다(W12 리뷰 m2).
        if exc.code == "blocked":
            state["blocked"] = True
            _save_state(run_dir, state)
        raise


def _plan_kind(args, run_dir: Path, state: dict) -> dict:
    kind = args.kind
    try:
        if kind == "courts":
            return _plan_one(run_dir, state, kind, build_courts_body(), f"{SAVE_PREFIX}courts.json", {})
        if kind == "notices":
            body, sd = build_notices_body(date=args.date, court_code=args.court_code, bid_type=args.bid_type)
            inner = body["dma_srchDspslPbanc"]
            name = f"notices-{inner['srchYmd']}-{inner['cortOfcCd'] or 'all'}-{inner['bidDvsCd'] or 'all'}.json"
            query = {"month": inner["srchYmd"], "exact_ymd": sd["exact_ymd"],
                     "court": inner["cortOfcCd"], "bid": inner["bidDvsCd"]}
            return _plan_one(run_dir, state, kind, body, SAVE_PREFIX + name, query)
        if kind == "notice-detail":
            row = _find_notice_row(run_dir, state, args.notice_id)
            body = build_notice_detail_body(row)
            inner = body["dma_srchGnrlPbanc"]
            name = (f"detail-{inner['cortOfcCd']}-{inner['dspslDxdyYmd']}-{_token(inner['jdbnCd'])}"
                    f"-{_token(inner['bidDvsCd']) if inner['bidDvsCd'] else 'none'}.json")
            query = {"court": inner["cortOfcCd"], "sale_ymd": inner["dspslDxdyYmd"], "jdbn": inner["jdbnCd"],
                     "notice_id": args.notice_id}
            return _plan_one(run_dir, state, kind, body, SAVE_PREFIX + name, query)
        if kind == "case":
            body, case_no = build_case_body(court_code=args.court_code, case_number=args.case_number)
            year, num = case_no.split("타경")
            name = f"case-{body['dma_srchCsDtlInf']['cortOfcCd']}-{year}-{num}.json"
            query = {"court": body["dma_srchCsDtlInf"]["cortOfcCd"], "case_number": case_no}
            return _plan_one(run_dir, state, kind, body, SAVE_PREFIX + name, query)
        if kind == "search":
            body = build_property_search_body(
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
            info = body["dma_pageInfo"]
            filters = body["dma_srchGdsDtlSrchInfo"]
            digest = hashlib.sha1(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:10]
            name = f"search-{digest}-p{info['pageNo']}-s{info['pageSize']}.json"
            # 소재지 분기의 cortOfcCd 는 숨은 셀렉트 값이라 행의 법원과 대조하지 않는다(서버가 쓰지 않는다).
            court = filters["cortOfcCd"] if filters["cortStDvs"] == "1" else ""
            # 기간을 주지 않은 쪽은 화면 기본값(오늘~14일 뒤)이다 — collect 가 warnings 로 되말한다(W12 재확인 n2).
            defaulted = [k for k, v in (("from", args.sale_from), ("to", args.sale_to)) if not v]
            query = {"page": info["pageNo"], "size": info["pageSize"], "court": court, "digest": digest,
                     "window_defaulted": defaulted, "filters": filters}
            return _plan_one(run_dir, state, kind, body, SAVE_PREFIX + name, query)
    except ValueError as exc:
        raise CourtError("args", str(exc)) from exc
    raise CourtError("args", f"알 수 없는 종류: {kind}")  # pragma: no cover - argparse choices


def _range(lo, hi) -> dict | None:
    out = {}
    if lo is not None:
        out["min"] = lo
    if hi is not None:
        out["max"] = hi
    return out or None


# ---------------------------------------------------------------------------
# collect — 응답 판정
# ---------------------------------------------------------------------------

def _read_payload(path: Path, ok_status: tuple = (200,)) -> dict:
    """hyve 층(실패 자리·HTTP 오류·절단)과 사이트 봉투(errors·status·ipcheck)를 판정해 JSON 을 돌려준다."""
    try:
        body = read_input(path)
    except HyveHTTPError as exc:
        site_msg = _site_error_message(exc.body)
        raise CourtError("http", f"HTTP {exc.status} — {site_msg or str(exc)}") from exc
    except HyveInputError as exc:
        extra = {"hyve_code": exc.code} if getattr(exc, "code", None) else {}
        raise CourtError(exc.kind, str(exc), **extra) from exc
    try:
        text = body.text()
        payload = json.loads(text)
    except (UnicodeDecodeError, ValueError) as exc:
        title = _html_title(body.data)
        why = f"JSON 이 아니다 — 차단·안내 화면일 수 있다" + (f"(제목: {title})" if title else "")
        if body.data.lstrip()[:1] in (b"{", b"["):
            why = "JSON 이 끝까지 오지 않았다(잘린 본문) — 이 파일을 쓰지 않고 새 회차로 다시 받는다"
            raise CourtError("truncated", f"{why}: {path.name}") from exc
        raise CourtError("site", f"{why}: {path.name}") from exc
    if not isinstance(payload, dict):
        raise CourtError("site", f"응답이 객체가 아니다: {path.name}")
    errors = payload.get("errors")
    if isinstance(errors, dict) and errors.get("errorMessage"):
        raise CourtError("site", f"법원경매 사이트 오류: {errors['errorMessage']}")
    status = payload.get("status")
    if status is not None and status not in ok_status:
        raise CourtError("site", f"법원경매 사이트 응답 status={status}: {payload.get('message')}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise CourtError("site", f"응답에 data 가 없다(요청이 거부됐을 수 있다): {payload.get('message')}")
    if data.get("ipcheck") is False:
        raise CourtError("blocked", _BLOCKED)
    return payload


def _site_error_message(raw: bytes) -> str:
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return ""
    if isinstance(obj, dict):
        err = obj.get("errors")
        if isinstance(err, dict) and err.get("errorMessage"):
            return str(err["errorMessage"])
        if obj.get("message"):
            return str(obj["message"])
    return ""


def _html_title(raw: bytes) -> str:
    m = re.search(rb"<title>([^<]{0,80})</title>", raw[:20000], re.IGNORECASE)
    return m.group(1).decode("utf-8", errors="replace").strip() if m else ""


def _mismatch(what: str, want, got) -> CourtError:
    return CourtError(
        "mismatch",
        f"받은 응답의 {what}({got!r})가 계획한 질의({want!r})와 다르다 — 다른 질의의 파일이다. "
        "파일을 고치지 말고 plan 이 준 호출을 그대로 부른다.",
    )


def _collect_courts(payload, query) -> dict:
    result = normalize_court_codes_response(payload)
    if not result["items"]:
        raise CourtError("site", "법원 목록이 비었다 — 사이트 응답 형태가 바뀌었을 수 있다")
    bad = [i for i in result["items"] if not re.fullmatch(r"B\d{6}", i["code"] or "")]
    if bad:
        raise CourtError("site", f"법원 코드 형식이 다른 행이 {len(bad)}개 있다 — 사이트 응답 형태가 바뀌었을 수 있다")
    return result


def _collect_notices(payload, query) -> dict:
    rows = (payload["data"]).get("dlt_rletDspslPbancLst")
    if not isinstance(rows, list):
        raise CourtError("site", "응답에 공고 목록(dlt_rletDspslPbancLst)이 없다")
    for r in rows:
        if query.get("court") and r.get("cortOfcCd") != query["court"]:
            raise _mismatch("법원", query["court"], r.get("cortOfcCd"))
        if query.get("bid") and r.get("bidDvsCd") != query["bid"]:
            raise _mismatch("입찰구분", query["bid"], r.get("bidDvsCd"))
    month = query["month"]
    exact = query.get("exact_ymd")
    bid = query.get("bid") or None
    result = normalize_notice_list_response(
        payload,
        requested_date=f"{exact[:4]}-{exact[4:6]}-{exact[6:8]}" if exact else f"{month[:4]}-{month[4:6]}",
        requested_month=f"{month[:4]}-{month[4:6]}",
        requested_court_code=query.get("court") or None,
        requested_bid_type={"code": bid, "name": describe_bid_type_code(bid)} if bid else None,
        include_raw=True,
    )
    if exact:
        result["items"] = [i for i in result["items"] if (i.get("raw") or {}).get("dspslDxdyYmd") == exact]
        result["count"] = len(result["items"])
    ids = [i["noticeId"] for i in result["items"]]
    warnings = ["사이트가 공고 총계를 주지 않아 전량 대조를 하지 않았다(받은 목록 그대로다)."]
    if len(ids) != len(set(ids)):
        warnings.append(f"같은 noticeId 가 {len(ids) - len(set(ids))}개 겹친다.")
    result["warnings"] = warnings
    return result


def _collect_notice_detail(payload, query) -> dict:
    result_data = payload["data"].get("result")
    if not isinstance(result_data, dict) or not isinstance(result_data.get("dspslPbanc"), dict):
        raise CourtError("site", "응답에 공고 상세(data.result.dspslPbanc)가 없다")
    echo = result_data.get("inputData") if isinstance(result_data.get("inputData"), dict) else None
    if echo is None:
        raise CourtError("site", "응답에 조회 조건 되비침(inputData)이 없어 질의를 대조할 수 없다")
    for key, qk in (("cortOfcCd", "court"), ("dspslDxdyYmd", "sale_ymd"), ("jdbnCd", "jdbn")):
        if str(echo.get(key) or "") != str(query[qk]):
            raise _mismatch(key, query[qk], echo.get(key))
    result = normalize_notice_detail_response(payload, include_raw=True)
    distinct = {strip_html(i["raw"].get("csNo")) for i in result["items"]} - {None}
    denom = result["caseCount"]
    warnings = []
    if denom is None:
        warnings.append("사이트가 사건 수(csCnt)를 주지 않아 전량 대조를 하지 않았다.")
    elif denom != len(distinct):
        why = ("부분본으로 보고" if len(distinct) < denom
               else "공고에 없는 사건이 섞인 것으로 보고")  # 초과본은 부분본이 아니다(W12 리뷰 m7)
        raise CourtError(
            "incomplete",
            f"공고의 사건 수는 {denom}건인데 받은 행의 사건은 {len(distinct)}건이다 — {why} 결과를 내지 않는다.",
            case_count=denom, received_cases=len(distinct),
        )
    result["receivedCaseCount"] = len(distinct)
    result["warnings"] = warnings
    return result


def _collect_case(payload, query) -> dict:
    if payload.get("status") == 204 and payload["data"].get("dma_csBasInf"):
        raise CourtError("site", "status 204 인데 사건 정보가 들어 있다 — 사이트 응답 형태가 바뀌었을 수 있다")
    result = normalize_case_detail_response(payload, include_raw=True)
    if result["found"]:
        info = result["caseInfo"]
        if info["courtCode"] != query["court"]:
            raise _mismatch("법원", query["court"], info["courtCode"])
        if info["userCaseNumber"] != query["case_number"]:
            raise _mismatch("사건번호", query["case_number"], info["userCaseNumber"])
    result["warnings"] = []
    return result


# 요청한 조건 ↔ 행의 값. ``srch*`` 는 행 자체의 값이고, 대조는 "사이트가 조건을 지켰는가" 를 잰다(2026-10-01 실측 —
# 법원 분기 2쪽 20행·소재지 분기 부산 3행, 23행 전부 요청과 같았다). 한 물건에 목록이 여럿일 때 ``srch*`` 가 조건에 걸린
# 목록의 값인지는 표본에 다중 목록 물건이 없어 미확인이다 — 어긋나면 mismatch(fail-loud)로 드러난다. 시군구·읍면동은 행에서 시도를 붙인 행정표준 꼴(``26350``·``26350107``)이다.
_SEARCH_ECHO = (
    ("bidDvsCd", "ipchalGbncd", "입찰구분", ()),
    ("rprsAdongSdCd", "srchHjguSidoCd", "시도", ()),
    ("rprsAdongSggCd", "srchHjguSiguCd", "시군구", ("rprsAdongSdCd",)),
    ("rprsAdongEmdCd", "srchHjguDongCd", "읍면동", ("rprsAdongSdCd", "rprsAdongSggCd")),
    ("lclDspslGdsLstUsgCd", "srchLclsUtilCd", "용도 대분류", ()),
    ("mclDspslGdsLstUsgCd", "srchMclsUtilCd", "용도 중분류", ()),
    ("sclDspslGdsLstUsgCd", "srchSclsUtilCd", "용도 소분류", ()),
)


def _check_search_rows(rows: list, query: dict) -> None:
    """행이 요청한 법원·입찰구분·지역·용도를 되비치는지 본다 — 사이트가 조건을 무시하거나 다른 질의의 파일이면 잡는다."""
    filters = query.get("filters") or {}
    for r in rows:
        if not isinstance(r, dict):
            raise CourtError("site", "검색 결과 행이 객체가 아니다")
        if query.get("court") and r.get("boCd") != query["court"]:
            raise _mismatch("법원", query["court"], r.get("boCd"))
        for fkey, rkey, label, prefix in _SEARCH_ECHO:
            want = filters.get(fkey) or ""
            if not want:
                continue
            want = "".join(filters.get(k) or "" for k in prefix) + want
            if rkey not in r:
                raise CourtError("site", f"검색 결과 행에 {label} 대조 값({rkey})이 없다 — 사이트 응답 형태가 바뀌었을 수 있다")
            if str(r.get(rkey) or "") != want:
                raise _mismatch(label, want, r.get(rkey))


def _collect_search(payload, query) -> dict:
    data = payload["data"]
    info = data.get("dma_pageInfo")
    rows = data.get("dlt_srchResult")
    if not isinstance(info, dict) or not isinstance(rows, list):
        raise CourtError("site", "응답에 쪽 정보(dma_pageInfo)·결과(dlt_srchResult)가 없다")
    page, size = query["page"], query["size"]
    try:
        got_page, got_size = int(info.get("pageNo")), int(info.get("pageSize"))
        total = int(str(info.get("totalCnt")).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise CourtError("site", f"쪽 정보를 읽을 수 없다(pageNo·pageSize·totalCnt): {info}") from exc
    if (got_page, got_size) != (page, size):
        raise _mismatch("쪽·쪽 크기", (page, size), (got_page, got_size))
    _check_search_rows(rows, query)
    # 쪽 넘김의 분모는 totalCnt(행 수)다 — 2026-10-01 실측: totalCnt 742·groupTotalCount 659 에서 70쪽(691~700행)이
    # 꽉 찼다. groupTotalCount 는 다른 집계라 분모로 쓰지 않는다.
    start = info.get("startRowNo")
    if rows and str(start) not in ("", "None") and str(start) != str((page - 1) * size + 1):
        raise _mismatch("시작 행 번호(startRowNo)", (page - 1) * size + 1, start)
    # 이 쪽에 와야 할 행 수 — 꽉 찬 쪽은 size, 마지막 쪽은 나머지, 마지막 너머는 0. 모자라도 넘쳐도 부분본이다
    # (W12 리뷰 M2: 마지막 쪽은 "비어 있지만 않으면" 통과해 741·742행이 빠져도 끝이라 말했다).
    expected = max(0, min(size, total - (page - 1) * size))
    if len(rows) != expected:
        where = f"{page}쪽은 {expected}행이어야 하는데(총 {total}건, 쪽 크기 {size}) {len(rows)}행이 왔다"
        raise CourtError(
            "incomplete",
            f"{where} — {'부분본' if len(rows) < expected else '총계보다 많은 행이 온 응답'}으로 보고 결과를 내지 않는다.",
            expected_rows=expected, received_rows=len(rows),
        )
    result = normalize_property_search_response(payload, requested_filters=query["filters"], include_raw=True)
    warnings = []
    if rows == [] and total == 0:
        warnings.append("조건에 맞는 물건이 없다(총 0건).")
    elif not rows:
        warnings.append(f"{page}쪽은 마지막 쪽 너머다(총 {total}건).")
    if query.get("window_defaulted"):
        f = query["filters"]
        b, e = f["bidBgngYmd"], f["bidEndYmd"]
        which = "·".join({"from": "시작", "to": "끝"}[k] for k in query["window_defaulted"])
        warnings.append(
            f"매각기일 기간 {b[:4]}-{b[4:6]}-{b[6:]} ~ {e[:4]}-{e[4:6]}-{e[6:]} 안의 물건만 찾았다"
            f"({which}을 주지 않아 화면 기본값 — 오늘부터 14일). 그 밖의 매각기일 물건은 이 결과에 없다."
        )
    pages = -(-total // size) if total else 0
    result["page"]["pageCount"] = pages
    result["page"]["hasMore"] = page < pages
    result["warnings"] = warnings
    return result


def _track_search_total(state: dict, query: dict, result: dict) -> None:
    """같은 조건의 앞선 쪽과 총계가 다르면 받는 사이 목록이 바뀐 것이다 — 쪽을 이어 붙이면 중복·결손이 생긴다(W12 리뷰 m6)."""
    digest = query.get("digest")
    if not digest:
        return
    total = result["page"]["totalCount"]
    seen = state.setdefault("search_totals", {}).setdefault(digest, {})
    others = {int(p): t for p, t in seen.items() if int(p) != query["page"] and t != total}
    if others:
        pages = ", ".join(f"{p}쪽 {t}건" for p, t in sorted(others.items()))
        result["warnings"].append(
            f"받는 사이 목록이 바뀌었다(이번 {query['page']}쪽 총 {total}건, 앞서 {pages}) — "
            "쪽을 이어 붙이면 겹치거나 빠진다. 전체가 필요하면 새 회차 폴더에서 1쪽부터 다시 받는다."
        )
    seen[str(query["page"])] = total


_COLLECTORS = {
    "courts": _collect_courts,
    "notices": _collect_notices,
    "notice-detail": _collect_notice_detail,
    "case": _collect_case,
    "search": _collect_search,
}


def cmd_collect(args) -> dict:
    run_dir = Path(args.run_dir)
    state = _load_state(run_dir)
    if state is None:
        raise CourtError("input", f"회차 상태 파일이 없다: {run_dir / STATE_NAME} — plan 을 먼저 부른다(--run-dir 가 같은지 확인)")
    path = Path(args.input)
    try:
        rel = path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError as exc:
        raise CourtError("input", f"--input 은 회차 폴더 안의 파일이어야 한다: {path}") from exc
    meta = state.get("calls", {}).get(rel)
    if meta is None:
        raise CourtError("input", f"이 회차가 계획하지 않은 파일이다: {rel} — plan 이 준 save_as 의 파일을 넘긴다")
    kind = meta["kind"]
    try:
        # 사건 조회는 없는 사건번호에 status 204 + dma_csBasInf null 을 준다(2026-10-01 실측 — 1 사건번호 1회차 관측).
        # found:false 로 낸다. 200 에 사건이 없어도 found:false 라 표본이 뒤집혀도 동작은 같다.
        payload = _read_payload(path, (200, 204) if kind == "case" else (200,))
    except CourtError as exc:
        if exc.code == "blocked":
            state["blocked"] = True
            _save_state(run_dir, state)
        raise
    result = _COLLECTORS[kind](payload, meta["query"])
    if kind == "search":
        _track_search_total(state, meta["query"], result)
        _save_state(run_dir, state)
    if getattr(args, "no_raw", False):
        _drop_raw(result)
    out = {"ok": True, "status": "ok", "kind": kind, "file": rel}
    out.update(result)
    out["calls_used"] = state["used"]
    out["calls_remaining"] = state["max_calls"] - state["used"]
    return out


def _drop_raw(obj) -> None:
    if isinstance(obj, dict):
        obj.pop("raw", None)
        for v in obj.values():
            _drop_raw(v)
    elif isinstance(obj, list):
        for v in obj:
            _drop_raw(v)


# ---------------------------------------------------------------------------
# codes (로컬)
# ---------------------------------------------------------------------------

def cmd_codes(args) -> dict:
    table = {"bid-types": list_bid_types, "usages": list_usage_codes, "regions": list_region_codes}[args.kind]()
    return {"ok": True, "status": "ok", "count": len(table), "items": table}


# ---------------------------------------------------------------------------
# 인자
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(
        prog="court-auction",
        description="대법원 법원경매정보 조회 — 요청은 itda-hyve, 이 스크립트는 계획·판정만 (참고용, 입찰 전 법원 원문 재확인)",
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_JsonArgumentParser)

    p_codes = sub.add_parser("codes", help="로컬 코드표 (입찰구분/용도/지역) — 법원 목록은 plan courts")
    p_codes.add_argument("kind", choices=["bid-types", "usages", "regions"])
    p_codes.set_defaults(func=cmd_codes)

    run = _JsonArgumentParser(add_help=False)
    run.add_argument("--run-dir", required=True, help="회차 폴더(스크립트가 보는 경로 — itda-hyve save_dir 와 같은 폴더)")
    run.add_argument("--save-dir", required=True, help="같은 폴더의 호스트 절대 경로(itda-hyve save_dir)")
    run.add_argument("--max-calls", type=int, help=f"이 회차의 호출 상한(첫 plan 에서만, 기본 {DEFAULT_MAX_CALLS}, 최대 {MAX_CALLS_CAP})")

    p_plan = sub.add_parser("plan", help="보낼 itda-hyve http_request 호출을 만든다")
    kinds = p_plan.add_subparsers(dest="kind", required=True, parser_class=_JsonArgumentParser)

    kinds.add_parser("courts", parents=[run], help="법원사무소 목록(코드)")

    k_notices = kinds.add_parser("notices", parents=[run], help="매각공고 목록")
    k_notices.add_argument("--date", required=True, help="매각기일 월(YYYY-MM) 또는 일(YYYY-MM-DD — 월로 받고 그날만 남긴다)")
    k_notices.add_argument("--court-code", help="법원사무소코드(예: B000210). 비우면 전체")
    k_notices.add_argument("--bid-type", choices=["date", "period"], help="기일입찰/기간입찰. 비우면 둘 다")

    k_detail = kinds.add_parser("notice-detail", parents=[run], help="공고 펼치기 — 이 회차에서 받은 목록의 noticeId")
    k_detail.add_argument("--notice-id", required=True, help="collect notices 결과의 items[].noticeId (예: B000210_1002_20261015)")

    k_case = kinds.add_parser("case", parents=[run], help="사건번호 조회")
    k_case.add_argument("--court-code", required=True, help="법원사무소코드(예: B000210)")
    k_case.add_argument("--case-number", required=True, help="사건번호(예: 2024타경100001 또는 2024-100001)")

    k_search = kinds.add_parser("search", parents=[run], help="물건 자유 조건검색(한 쪽)")
    k_search.add_argument("--sido", help="시도 이름 또는 코드(예: 서울특별시/11 — codes regions). 주면 소재지 분기(법원코드와 함께 못 준다)")
    k_search.add_argument("--sigungu", help="시군구 행정표준코드 5자리(예: 해운대구 26350) 또는 사이트 3자리(350)")
    k_search.add_argument("--dong", help="읍면동 8자리(예: 좌동 26350107) 또는 사이트 3자리(107)")
    k_search.add_argument("--usage-large", help="용도 대분류 이름 또는 코드(토지/건물 — codes usages)")
    k_search.add_argument("--usage-medium", help="용도 중분류 이름 또는 코드(예: 주거용건물/20100)")
    k_search.add_argument("--usage-small", help="용도 소분류 이름 또는 코드(예: 아파트/20104) — 상위 분류는 채워진다")
    k_search.add_argument("--price-min", help="최저매각가 하한(원)")
    k_search.add_argument("--price-max", help="최저매각가 상한(원)")
    k_search.add_argument("--appraised-min", help="감정평가액 하한(원)")
    k_search.add_argument("--appraised-max", help="감정평가액 상한(원)")
    k_search.add_argument("--area-min", help="면적 하한(㎡)")
    k_search.add_argument("--area-max", help="면적 상한(㎡)")
    k_search.add_argument("--flbd-min", help="유찰횟수 하한(정수)")
    k_search.add_argument("--flbd-max", help="유찰횟수 상한(정수)")
    k_search.add_argument("--sale-from", help="매각기일 시작 YYYYMMDD(기본 오늘 — 화면 기본값)")
    k_search.add_argument("--sale-to", help="매각기일 종료 YYYYMMDD(기본 오늘+14일 — 화면 기본값)")
    k_search.add_argument("--court-code", help="법원사무소코드")
    k_search.add_argument("--bid-type", choices=["date", "period"], help="기일입찰/기간입찰. 비우면 전체(화면의 전체)")
    k_search.add_argument("--page", type=int, default=1, help="쪽(기본 1)")
    k_search.add_argument("--page-size", type=int, default=10, help="쪽 크기(10/20/50/100, 기본 10)")
    p_plan.set_defaults(func=cmd_plan)

    p_collect = sub.add_parser("collect", help="itda-hyve 가 저장한 응답을 판정·정규화한다")
    p_collect.add_argument("--run-dir", required=True, help="plan 과 같은 회차 폴더")
    p_collect.add_argument("--input", required=True, help="plan 이 준 save_as 의 파일(회차 폴더 안)")
    p_collect.add_argument("--no-raw", action="store_true", help="raw 패스스루 필드 제외(출력 축소)")
    p_collect.set_defaults(func=cmd_collect)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    try:
        args = build_parser().parse_args(argv)
        _print(args.func(args))
        return 0
    except CourtError as exc:
        return _fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())
