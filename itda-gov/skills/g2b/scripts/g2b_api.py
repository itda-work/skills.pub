"""나라장터 공공데이터개방표준서비스 — 호출 계획과 응답 파서 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 모듈은
  1. 기간을 1개월 창으로 나눈 **호출 계획**(``http_request`` 인자 그대로)을 만들고
  2. 그렇게 저장한 **응답 JSON 파일을 읽어** 오류 판정·창별 전량 대조·중복 제거만 한다.
직접 API 를 부르지 않고, 키 값을 보지 않는다(``{{secret:KO_DATA_API_KEY}}`` 자리표시자만 싣는다).

응답 형태 (2026-09-30 itda-hyve 실측):
    성공      {"response": {"header": {"resultCode": "00"}, "body": {"items": [...], "totalCount": N, "pageNo": 1, "numOfRows": 999}}}
    API 오류  {"nkoneps.com.response.ResponseError": {"header": {"resultCode": "07", "resultMsg": "입력범위값 초과 에러"}}}
    게이트웨이 {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NULL", "returnReasonCode": "20", …}}}  (HTTP 401)
"""
from __future__ import annotations

import calendar
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from hyve_input import HyveHTTPError, HyveInputError, read_input

API_URL = (
    "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService"
    "/getDataSetOpnStdBidPblancInfo"
)
SECRET = "{{secret:KO_DATA_API_KEY}}"

# 한 쪽의 행 수(API 상한 999). 호출 수를 줄이려 가장 큰 값을 쓴다.
PAGE_SIZE = 999
# 창마다 받을 쪽 상한. 999 × 20 ≈ 2만 건. 넘으면 truncated 로 표시한다(호출 예산).
MAX_PAGES = 20
# itda-hyve batch 한 번에 넣을 수 있는 호출 수. 넘으면 하나도 실행하지 않는다(netbridge §batch).
BATCH_LIMIT = 40
# 단건 호출 제한 시간. Cowork 호출 하나 60초 상한보다 짧아야 한다(netbridge — 브리지가 먼저 끊으면
# itda-hyve 는 계속 돌아 나중에 파일을 쓰고, 재시도가 "같은 이름" 으로 거부된다).
CALL_TIMEOUT = 50

# 저장 이름 규칙 — 창(시작·끝)과 쪽을 이름에 싣는다. collect 가 이 이름으로 창을 가른다.
_NAME_RE = re.compile(r"bids-(\d{8})-(\d{8})-p(\d+)\.json$")

# data.go.kr 게이트웨이 returnReasonCode
_GATEWAY_HINTS = {
    "20": "서비스 접근 거부 — 활용신청 승인 전이거나(승인 뒤 동기화 5~30분) 키가 채워지지 않았다",
    "22": "일일 트래픽 초과 — 내일 다시 받는다",
    "30": "등록되지 않은 서비스키 — itda-hyve GUI 시크릿 탭에 **Decoding 키**로 다시 등록",
    "31": "서비스키 기간 만료 — 공공데이터포털에서 연장",
}
# 서비스 resultCode
_RESULT_HINTS = {
    "07": "입력범위값 초과 — 기간이 1개월을 넘거나 numOfRows 가 999 를 넘는다(plan 의 창을 그대로 쓴다)",
    "08": "필수 요청 파라미터 누락 — plan 이 준 params 를 그대로 보냈는지 확인",
}


class G2BAPIError(Exception):
    """저장된 응답이 성공 응답이 아니다 (본문의 오류 코드)."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class InputFileError(Exception):
    """입력 파일을 가공할 수 없다 — 없음·이름 규칙 위반·절단·HTTP 오류·itda-hyve 실패.

    ``kind`` 는 출력 JSON 의 ``error`` 값이다(``input``·``truncated``·``http``·``hyve``).
    """

    def __init__(self, message: str, kind: str = "input"):
        super().__init__(message)
        self.kind = kind


class IncompleteError(Exception):
    """창마다 받은 행이 totalCount 에 모자라다. ``next_calls`` 에 더 받을 호출이 담긴다.

    ``windows`` 는 창별 ``need_pages``(전량에 필요한 쪽)·``will_truncate``(상한을 넘어 잘릴 창)를 싣는다 —
    더 받기 **전에** 잘림을 알리기 위해서다.
    """

    def __init__(self, message: str, next_calls: list[dict[str, Any]],
                 windows: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.next_calls = next_calls
        self.windows = windows or []

    @property
    def will_truncate(self) -> bool:
        return any(w.get("will_truncate") for w in self.windows)


# --- 날짜·창 ---

def parse_date(date_str: str) -> date:
    """YYYY-MM-DD 를 date 로. 형식이 틀리면 ValueError."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"날짜 형식이 올바르지 않습니다: '{date_str}'. YYYY-MM-DD 형식으로 입력하세요."
        ) from exc


def split_windows(from_date: str, to_date: str) -> list[tuple[date, date]]:
    """기간을 달력 달 단위 창으로 나눈다(API 는 한 요청에 1개월 이내만 받는다).

    예: 2026-08-20 ~ 2026-10-05 → (08-20~08-31), (09-01~09-30), (10-01~10-05)
    """
    begin, end = parse_date(from_date), parse_date(to_date)
    if begin > end:
        raise ValueError(f"시작일({from_date})이 종료일({to_date})보다 늦습니다.")
    windows = []
    cur = begin
    while cur <= end:
        last = date(cur.year, cur.month, calendar.monthrange(cur.year, cur.month)[1])
        stop = min(last, end)
        windows.append((cur, stop))
        cur = date.fromordinal(stop.toordinal() + 1)
    return windows


def save_name(w_from: str, w_to: str, page: int) -> str:
    """저장 이름: ``g2b/bids-<시작 YYYYMMDD>-<끝 YYYYMMDD>-p<쪽>.json``."""
    return f"g2b/bids-{w_from}-{w_to}-p{page}.json"


def build_call(w_from: str, w_to: str, page: int, rows: int = PAGE_SIZE) -> dict[str, Any]:
    """한 쪽을 받는 호출 — batch ``calls`` 한 칸 형태. 단독 호출은 ``args`` 만 쓴다."""
    return {
        "id": f"{w_from}-{w_to}-p{page}",
        "tool": "http_request",
        "args": {
            "url": API_URL,
            "params": {
                "serviceKey": SECRET,
                "type": "json",
                "pageNo": str(page),
                "numOfRows": str(rows),
                "bidNtceBgnDt": f"{w_from}0000",
                "bidNtceEndDt": f"{w_to}2359",
            },
            "timeout_sec": CALL_TIMEOUT,
            "save_as": save_name(w_from, w_to, page),
        },
    }


def plan(from_date: str, to_date: str, rows: int = PAGE_SIZE) -> dict[str, Any]:
    """창마다 1쪽을 받는 호출 계획. 2쪽 이후는 collect 가 totalCount 를 보고 ``next_calls`` 로 알려 준다."""
    rows = max(1, min(PAGE_SIZE, rows))
    windows = split_windows(from_date, to_date)
    out_windows = []
    calls = []
    for b, e in windows:
        wf, wt = b.strftime("%Y%m%d"), e.strftime("%Y%m%d")
        out_windows.append({"from": b.isoformat(), "to": e.isoformat()})
        calls.append(build_call(wf, wt, 1, rows))
    return {"status": "ok", "from": from_date, "to": to_date, "rows": rows,
            "windows": out_windows, "calls": calls}


# --- 응답 파일 ---

def _read_body(path: Path) -> bytes:
    """입력 파일에서 응답 본문을 꺼낸다 — hyve 층 판독은 공용 ``hyve_input`` 이 한다.

    세 형태(본문 그대로·``http_request`` 응답 JSON 전체·실패 자리 ``{"error": …}``)를 받는다. HTTP 오류면
    본문의 게이트웨이·서비스 오류 코드를 먼저 본다(그쪽이 더 구체적이다). 나머지는 :class:`InputFileError`.
    """
    try:
        return read_input(path).data
    except HyveHTTPError as exc:
        _raise_api_error(exc.body, path)
        raise InputFileError(str(exc), kind=exc.kind) from exc
    except HyveInputError as exc:
        raise InputFileError(str(exc), kind=exc.kind) from exc


def _raise_api_error(body: bytes, path: Path) -> None:
    """본문이 게이트웨이·서비스 오류 형태면 G2BAPIError 를 올린다. 아니면 조용히 돌아온다."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        text = body.decode("utf-8", "replace")
        m = re.search(r"<returnReasonCode>\s*(\d+)\s*</returnReasonCode>", text)
        if m:
            code = m.group(1)
            auth = re.search(r"<returnAuthMsg>(.*?)</returnAuthMsg>", text, re.S)
            raise G2BAPIError(
                f"공공데이터포털 게이트웨이 거부 (returnReasonCode={code}, "
                f"{(auth.group(1).strip() if auth else '')}): {_GATEWAY_HINTS.get(code, '')} ({path.name})",
                error_code=f"gateway-{code}",
            )
        return
    if not isinstance(data, dict):
        return
    gw = data.get("OpenAPI_ServiceResponse")
    if isinstance(gw, dict):
        hdr = gw.get("cmmMsgHeader") or {}
        code = str(hdr.get("returnReasonCode", ""))
        raise G2BAPIError(
            f"공공데이터포털 게이트웨이 거부 (returnReasonCode={code}, {hdr.get('errMsg', '')}, "
            f"{hdr.get('returnAuthMsg', '')}): {_GATEWAY_HINTS.get(code, '')} ({path.name})",
            error_code=f"gateway-{code}",
        )
    for key, val in data.items():
        if key.endswith("ResponseError") and isinstance(val, dict):
            hdr = val.get("header") or {}
            code = str(hdr.get("resultCode", ""))
            raise G2BAPIError(
                f"API 오류 (resultCode={code}, {hdr.get('resultMsg', '')}): "
                f"{_RESULT_HINTS.get(code, '요청 파라미터를 확인')} ({path.name})",
                error_code=code,
            )


def parse_page(path: str | Path) -> dict[str, Any]:
    """저장된 응답 파일 한 쪽을 읽는다.

    Returns:
        ``{"items": [...], "total_count": N, "page": n, "rows": r}``
    Raises:
        InputFileError, G2BAPIError
    """
    p = Path(path).expanduser()
    body = _read_body(p)
    _raise_api_error(body, p)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputFileError(
            f"JSON 이 아닙니다 — 본문이 잘렸거나 HTTP 오류 페이지일 수 있다({p.name}): {exc}"
        ) from exc
    try:
        header = data["response"]["header"]
        body_obj = data["response"]["body"]
    except (KeyError, TypeError) as exc:
        raise InputFileError(f"입찰공고 응답 형태가 아닙니다({p.name}): {exc}") from exc

    code = str(header.get("resultCode", ""))
    if code != "00":
        raise G2BAPIError(
            f"API 오류 (resultCode={code}, {header.get('resultMsg', '')}): "
            f"{_RESULT_HINTS.get(code, '요청 파라미터를 확인')} ({p.name})",
            error_code=code,
        )

    items = body_obj.get("items") or []
    if isinstance(items, dict):  # 공공데이터포털 일부 서비스의 {"item": [...]} 형태 대비
        items = items.get("item") or []
        items = [items] if isinstance(items, dict) else items
    return {
        "items": items,
        "total_count": int(body_obj.get("totalCount") or 0),
        "page": int(body_obj.get("pageNo") or 1),
        "rows": int(body_obj.get("numOfRows") or PAGE_SIZE),
    }


def _item_key(item: dict) -> tuple:
    """페이지 경계 중복 제거용 안정 키.

    한 입찰공고(bidNtceNo)가 차수(bidNtceOrd)별로 여러 행을 가질 수 있고, 페이지 간 중복이
    관측된 적이 있다. (공고번호, 차수, 참조공고번호, 참조차수)로 행을 식별한다. 식별 필드가
    모두 비면 항목 전체를 정렬된 튜플로 쓴다.
    """
    parts = (
        str(item.get("bidNtceNo", "")),
        str(item.get("bidNtceOrd", "")),
        str(item.get("refNtceNo", "")),
        str(item.get("refNtceOrd", "")),
    )
    if any(parts):
        return parts
    return tuple(sorted((str(k), str(v)) for k, v in item.items()))


def _name_of(path: str) -> tuple[str, str, int]:
    """저장 이름에서 (창 시작, 창 끝, 쪽)을 읽는다."""
    m = _NAME_RE.search(Path(path).name)
    if not m:
        raise InputFileError(
            f"파일 이름이 규칙(bids-<시작 YYYYMMDD>-<끝 YYYYMMDD>-p<쪽>.json)과 다릅니다: {Path(path).name} "
            "— plan 이 준 save_as 를 그대로 쓰세요"
        )
    return m.group(1), m.group(2), int(m.group(3))


def collect(paths: list[str], max_pages: int = MAX_PAGES, single_page: bool = False) -> dict[str, Any]:
    """저장된 쪽 파일들을 창별로 묶어 전량 대조하고 중복을 없앤다.

    창마다 필요한 쪽 = ceil(totalCount / numOfRows). ``max_pages`` 안에서 빠진 쪽이 있으면
    그 쪽을 받는 호출을 ``next_calls`` 에 담아 :class:`IncompleteError` 를 올린다.
    필요한 쪽이 ``max_pages`` 를 넘으면 상한까지만 요구하고 ``truncated`` 로 표시한다 — 첫 incomplete 에서
    이미 창별 ``need_pages``·``will_truncate`` 로 알린다(다 받은 뒤에야 알면 사용자가 모르고 승인한다).
    ``single_page`` 면 대조하지 않는다(한 쪽만 훑어보기).

    분모는 창 안 쪽들의 totalCount **최댓값**이다. 이 API 는 받는 사이에도 공고가 늘고 줄어(실측: 하루 약
    1,900건이 계속 올라온다) 쪽마다 값이 다를 수 있으므로 오류가 아니라 경고로 둔다. 최댓값을 쓰는 이유 —
    쪽 사이에 **삭제**가 있으면 뒤쪽이 앞으로 밀려 1건을 건너뛴다(T1=5·T2=4). 최솟값이면 필요한 쪽이 줄어
    그 1건이 빠진 채 완료로 판정되고, 최댓값이면 한 쪽을 더 요구하거나 "다시 받으라" 로 실패한다.

    Returns:
        ``{"items", "total_count", "scanned_count", "truncated", "windows", "sources", "warnings", "page"}``
    """
    max_pages = max(1, max_pages)
    windows: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    sources = []
    for p in paths:
        parsed = parse_page(p)
        if single_page:
            key = ("", "")
        else:
            wf, wt, name_page = _name_of(p)
            key = (wf, wt)
            if name_page != parsed["page"]:
                raise InputFileError(
                    f"파일 이름의 쪽(p{name_page})과 본문 pageNo({parsed['page']})가 다릅니다: {Path(p).name} "
                    "— 다른 호출의 응답을 이 이름으로 저장했다. plan·next_calls 의 save_as 를 그대로 쓰세요"
                )
        windows.setdefault(key, []).append((p, parsed))
        sources.append({"path": str(Path(p).expanduser()), "page": parsed["page"],
                        "total_count": parsed["total_count"], "item_count": len(parsed["items"])})

    warnings: list[str] = []
    next_calls: list[dict[str, Any]] = []
    short: list[str] = []
    truncated = False
    total_count = 0
    raw_items: list[dict] = []
    window_rows = []

    for (wf, wt), pages in sorted(windows.items()):
        totals = {pp["total_count"] for _, pp in pages}
        total = max(totals)
        total_count += total
        for _, pp in pages:
            raw_items.extend(pp["items"])
        collected = sum(len(pp["items"]) for _, pp in pages)
        window = {"from": wf, "to": wt, "total_count": total,
                  "pages": sorted(pp["page"] for _, pp in pages), "collected": collected}
        window_rows.append(window)
        if single_page:
            continue

        label = f"{wf}~{wt}"
        if len(totals) > 1:
            warnings.append(f"{label}: 쪽마다 totalCount 가 다릅니다({sorted(totals)}) — 받는 사이 공고가 바뀌었습니다")
        sizes = {pp["rows"] for _, pp in pages}
        if len(sizes) > 1:
            raise InputFileError(f"{label}: 쪽마다 numOfRows 가 다릅니다({sorted(sizes)}) — 한 창은 같은 numOfRows 로 받으세요")
        rows = sizes.pop()
        got = [pp["page"] for _, pp in pages]
        dup = sorted({g for g in got if got.count(g) > 1})
        if dup:
            raise InputFileError(f"{label}: 같은 쪽이 두 번 들어왔습니다({dup})")

        need = math.ceil(total / rows) if total else 1
        upto = min(need, max_pages)
        window["need_pages"] = need
        window["will_truncate"] = need > max_pages
        missing = [n for n in range(1, upto + 1) if n not in got]
        if missing:
            cut = (f" — 전량은 {need}쪽이라 상한 {max_pages}쪽에서 잘린다(will_truncate)"
                   if need > max_pages else "")
            short.append(f"{label} totalCount={total}, 받은 쪽 {sorted(got)} → 더 받을 쪽 {missing}{cut}")
            next_calls += [build_call(wf, wt, n, rows) for n in missing]
            continue
        if need > max_pages:
            truncated = True
            warnings.append(
                f"{label}: 전체 {total}건 중 {collected}건만 받았습니다(상한 {max_pages}쪽). 미조회분에 있는 "
                "공고는 결과에 없습니다 — 기간을 좁히거나 --max-pages 를 늘려 쪽을 더 받으세요"
            )
        elif collected < total:
            short.append(f"{label} totalCount={total} 인데 {collected}건 — 받는 사이 공고가 밀렸습니다, 이 창을 1쪽부터 다시 받으세요")

    if short:
        raise IncompleteError("창마다 전량을 받지 못했습니다: " + " / ".join(short), next_calls,
                              windows=window_rows)

    accumulated = []
    seen: set[tuple] = set()
    for item in raw_items:
        k = _item_key(item)
        if k in seen:
            continue
        seen.add(k)
        accumulated.append(item)
    dups = len(raw_items) - len(accumulated)
    if dups:
        warnings.append(f"쪽 경계에서 겹친 공고 {dups}건을 하나로 합쳤습니다")

    page_label: int | str = "all"
    if single_page:
        page_label = sources[0]["page"] if len(sources) == 1 else "partial"
    return {
        "items": accumulated,
        "total_count": total_count,
        "scanned_count": len(accumulated),
        "truncated": truncated,
        "windows": window_rows,
        "sources": sources,
        "warnings": warnings,
        "page": page_label,
    }
