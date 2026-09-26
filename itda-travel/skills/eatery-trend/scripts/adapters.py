"""adapters.py — 네이버 5개 공식/비공식 API 래퍼 (REQ-002/003/004/008/011).

§5 검증된 호출 패턴(2026-06-01 라이브 통과)을 fail-loud 계약으로 래핑한다.
모든 HTTP는 표준 라이브러리 urllib로 자체 수행한다 (WebFetch 금지).

각 어댑터는 ``(ok, data, reason)`` 튜플을 반환한다:
    ok=True  → data: 도메인 데이터, reason: ""
    ok=False → data: 빈값(빈 리스트/None), reason: 한국어 실패 사유

이 계약이 REQ-008(fail-loud)의 토대다 — API 차단·빈 응답·HMAC 실패·
자격증명 부재를 절대 성공으로 위장하지 않고 호출부로 표면화한다. 예외는
호출부로 전파하지 않으므로 상위 파이프라인이 소스별 도달 실패를 합성할 수 있다.

자동완성만 비공식·무인증 엔드포인트라 권위가 아닌 *힌트*로만 쓴다(REQ-011/OQ-8).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from env_loader import MissingAPIKeyError, resolve_api_key

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_UA = "Mozilla/5.0 (compatible; eatery-trend-skill; +itda-skills)"

_AC_URL = "https://ac.search.naver.com/nx/ac"
_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_SEARCHAD_BASE = "https://api.searchad.naver.com"
_SEARCHAD_URI = "/keywordstool"
_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

_LOCAL_DISPLAY_CAP = 5  # 지역검색 쿼리당 최대 5건(§10 라이브 확인)

_OPEN_GUIDE = (
    "{var}가 설정되지 않았습니다.\n"
    "네이버 개발자센터(https://developers.naver.com)에서 애플리케이션을 등록하고\n"
    "검색·데이터랩 API 사용 신청 후 발급받은 Client ID/Secret을 .env에 설정하세요:\n"
    "  NAVER_CLIENT_ID=...\n  NAVER_CLIENT_SECRET=...\n"
)
_SEARCHAD_GUIDE = (
    "{var}가 설정되지 않았습니다.\n"
    "네이버 검색광고(https://searchad.naver.com) > 도구 > API 관리자에서\n"
    "액세스 라이선스/비밀키/Customer ID를 발급받아 .env에 설정하세요:\n"
    "  NAVER_SEARCHAD_ACCESS_KEY=...\n  NAVER_SEARCHAD_SECRET_KEY=...\n  NAVER_SEARCHAD_CUSTOMER_ID=...\n"
)


# ---------------------------------------------------------------------------
# HTTP 경계 (테스트 mock seam)
# ---------------------------------------------------------------------------
def _classify_http_error(exc: Exception) -> str:
    """urllib 예외를 한국어 사유 문자열로 분류한다."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP 오류 {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"네트워크 연결 오류: {exc.reason}"
    if isinstance(exc, socket.timeout):
        return "요청 시간 초과(timeout)"
    if isinstance(exc, json.JSONDecodeError):
        return f"JSON 파싱 오류: {exc.msg}"
    return f"알 수 없는 오류: {exc}"


def _http_get_json(
    url: str, headers: dict[str, str], timeout: int = 15
) -> tuple[bool, Any | None, str]:
    """GET 요청 → JSON 파싱. (ok, data, reason) 반환, 예외 비전파."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return True, json.loads(raw), ""
    except Exception as exc:  # noqa: BLE001  (graceful fail-loud)
        return False, None, _classify_http_error(exc)


def _http_post_json(
    url: str, body: bytes, headers: dict[str, str], timeout: int = 20
) -> tuple[bool, Any | None, str]:
    """POST(JSON body) 요청 → JSON 파싱. (ok, data, reason) 반환, 예외 비전파."""
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return True, json.loads(raw), ""
    except Exception as exc:  # noqa: BLE001
        return False, None, _classify_http_error(exc)


# ---------------------------------------------------------------------------
# 자격증명
# ---------------------------------------------------------------------------
def _open_creds() -> tuple[str, str]:
    """네이버 OpenAPI(데이터랩·검색·블로그) Client ID/Secret. 부재 시 MissingAPIKeyError."""
    cid = resolve_api_key("NAVER_CLIENT_ID", guide_msg=_OPEN_GUIDE.format(var="NAVER_CLIENT_ID"))
    sec = resolve_api_key("NAVER_CLIENT_SECRET", guide_msg=_OPEN_GUIDE.format(var="NAVER_CLIENT_SECRET"))
    return cid, sec


def _searchad_creds() -> tuple[str, str, str]:
    """네이버 검색광고 API(HMAC) 액세스키/비밀키/Customer ID. 부재 시 MissingAPIKeyError."""
    acc = resolve_api_key(
        "NAVER_SEARCHAD_ACCESS_KEY", guide_msg=_SEARCHAD_GUIDE.format(var="NAVER_SEARCHAD_ACCESS_KEY")
    )
    sec = resolve_api_key(
        "NAVER_SEARCHAD_SECRET_KEY", guide_msg=_SEARCHAD_GUIDE.format(var="NAVER_SEARCHAD_SECRET_KEY")
    )
    cust = resolve_api_key(
        "NAVER_SEARCHAD_CUSTOMER_ID", guide_msg=_SEARCHAD_GUIDE.format(var="NAVER_SEARCHAD_CUSTOMER_ID")
    )
    return acc, sec, cust


def _sign(secret: str, ts: str, method: str, uri: str) -> str:
    """검색광고 API X-Signature 생성.

    base64( HMAC-SHA256(secret, '{ts}.{method}.{uri}') ).
    """
    msg = f"{ts}.{method}.{uri}".encode()
    return base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()


# ---------------------------------------------------------------------------
# 1) 자동완성 (REQ-011) — 조기경보·신상 발굴, 비공식·무인증
# ---------------------------------------------------------------------------
def autocomplete(q: str, *, timeout: int = 10) -> tuple[bool, list[str], str]:
    """네이버 자동완성 후보를 반환한다.

    비공식 엔드포인트이므로 권위가 아닌 *힌트*로만 사용한다(REQ-011). 실패는
    예외가 아니라 (False, [], 사유)로 graceful 처리한다(OQ-8).
    """
    url = _AC_URL + "?" + urllib.parse.urlencode(
        {"q": q, "con": "0", "frm": "nv", "ans": "2",
         "r_format": "json", "r_enc": "UTF-8", "st": "100"}
    )
    ok, data, reason = _http_get_json(
        url, {"User-Agent": _UA, "Referer": "https://www.naver.com/"}, timeout
    )
    if not ok or not isinstance(data, dict):
        return False, [], reason or "자동완성 응답 형식 오류"
    items: list[str] = []
    for grp in data.get("items", []) or []:
        for row in grp or []:
            if row and isinstance(row, list) and row[0]:
                items.append(row[0])
    return True, items, ""


# ---------------------------------------------------------------------------
# 2) SearchAd 키워드도구 (REQ-002) — 연관 breadth + 절대 월검색량
# ---------------------------------------------------------------------------
def keywordstool(hints: list[str], *, timeout: int = 15) -> tuple[bool, list[dict], str]:
    """연관키워드 목록을 반환한다. hintKeywords는 공백 제거 후 콤마 결합(최대 5).

    keywordList[].{relKeyword, monthlyPcQcCnt, monthlyMobileQcCnt, compIdx}.
    """
    try:
        acc, sec, cust = _searchad_creds()
    except MissingAPIKeyError as exc:
        return False, [], str(exc)

    ts = str(int(time.time() * 1000))
    sig = _sign(sec, ts, "GET", _SEARCHAD_URI)
    url = _SEARCHAD_BASE + _SEARCHAD_URI + "?" + urllib.parse.urlencode(
        {"hintKeywords": ",".join(h.replace(" ", "") for h in hints), "showDetail": "1"}
    )
    headers = {"X-Timestamp": ts, "X-API-KEY": acc, "X-Customer": cust, "X-Signature": sig}
    ok, data, reason = _http_get_json(url, headers, timeout)
    if not ok or not isinstance(data, dict):
        return False, [], reason or "SearchAd 응답 형식 오류"
    return True, data.get("keywordList", []) or [], ""


def monthly_volume(row: dict) -> int:
    """월검색량(PC+모바일) 정수화. '< 10'·None은 0, 콤마 제거(§5 vol)."""
    def _n(v: Any) -> int:
        if v in ("< 10", None):
            return 0
        try:
            return int(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0
    return _n(row.get("monthlyPcQcCnt")) + _n(row.get("monthlyMobileQcCnt"))


# ---------------------------------------------------------------------------
# 3) 데이터랩 검색트렌드 (REQ-003) — velocity/YoY
# ---------------------------------------------------------------------------
def datalab(
    keywords: list[str],
    start: str,
    end: str,
    unit: str = "week",
    *,
    timeout: int = 20,
) -> tuple[bool, dict | None, str]:
    """키워드그룹 시계열을 반환한다(최대 5그룹). results[].data[].{period, ratio}.

    ratio는 그룹별 max=100 정규화값. 데이터랩은 검색량 0인 주를 생략하므로
    짧은 시리즈 = 신상 출현 신호로 해석한다(§8.6).
    """
    try:
        cid, sec = _open_creds()
    except MissingAPIKeyError as exc:
        return False, None, str(exc)

    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": unit,
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
    }
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": sec,
        "Content-Type": "application/json",
    }
    ok, data, reason = _http_post_json(_DATALAB_URL, json.dumps(body).encode(), headers, timeout)
    if not ok or not isinstance(data, dict):
        return False, None, reason or "데이터랩 응답 형식 오류"
    return True, data, ""


# ---------------------------------------------------------------------------
# 4) 지역검색 (REQ-004) — 가게 좌표·카테고리·주소
# ---------------------------------------------------------------------------
def local_search(q: str, display: int = 5, *, timeout: int = 15) -> tuple[bool, list[dict], str]:
    """지역검색 결과를 반환한다. display는 5로 cap(§10).

    items[].{title(<b>포함), category, roadAddress, address, mapx, mapy}.
    title의 <b> 태그 제거·카테고리 음식 필터는 places.py 책임.
    """
    try:
        cid, sec = _open_creds()
    except MissingAPIKeyError as exc:
        return False, [], str(exc)

    capped = min(max(int(display), 1), _LOCAL_DISPLAY_CAP)
    url = _LOCAL_URL + "?" + urllib.parse.urlencode({"query": q, "display": capped})
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
    ok, data, reason = _http_get_json(url, headers, timeout)
    if not ok or not isinstance(data, dict):
        return False, [], reason or "지역검색 응답 형식 오류"
    return True, data.get("items", []) or [], ""


# ---------------------------------------------------------------------------
# 5) 블로그 total (REQ-007) — 협찬 거품 비율 분자
# ---------------------------------------------------------------------------
def blog_total(q: str, *, timeout: int = 15) -> tuple[bool, int | None, str]:
    """블로그 검색 결과 총건수(total)를 반환한다. 거품 비율(blog/검색)의 분자."""
    try:
        cid, sec = _open_creds()
    except MissingAPIKeyError as exc:
        return False, None, str(exc)

    url = _BLOG_URL + "?" + urllib.parse.urlencode({"query": q, "display": 1, "sort": "sim"})
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
    ok, data, reason = _http_get_json(url, headers, timeout)
    if not ok or not isinstance(data, dict):
        return False, None, reason or "블로그검색 응답 형식 오류"
    total = data.get("total")
    if not isinstance(total, int):
        try:
            total = int(total)
        except (ValueError, TypeError):
            return False, None, "블로그 total 파싱 실패"
    return True, total, ""
