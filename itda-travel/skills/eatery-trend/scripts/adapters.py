"""adapters.py — 네이버 Open API 요청 모양과 응답 판독 (네트워크 없음).

요청은 itda-hyve 가 보낸다(규칙 ``cowork-network-via-hyve``, itda-work/skills#46 W17). 이 모듈은
``http_request`` 인자(요청 모양)를 만들고, itda-hyve 가 ``save_as`` 로 저장한 본문을 판독한다.
키는 itda-hyve 시크릿에만 있다 — 헤더에 ``{{secret:NAVER_CLIENT_ID}}``·``{{secret:NAVER_CLIENT_SECRET}}``
자리표시만 싣는다(web-search 와 같은 이름).

| 소스 | 지금 |
|---|---|
| 데이터랩 검색어트렌드(POST) | itda-hyve ``http_request`` 하나씩(batch 는 GET 만) |
| 지역검색(GET) | itda-hyve ``batch`` ``plan_file`` |
| 검색광고 키워드도구 | **쓰지 않는다** — 요청마다 HMAC 서명이 필요해 itda-hyve 서명 기능(itda-work/itda-hyve#34)을 기다린다 |
| 블로그 검색 total | **부르지 않는다** — 거품 비율(블로그/월검색량)의 분모가 검색광고라 그것과 함께 돌아온다 |
| 자동완성(ac.search.naver.com) | **부르지 않는다** — robots ``User-agent: *`` 전면 불허(2026-10-06 확인) |

판독 함수는 ``(ok, data, reason)`` 을 돌려준다(REQ-008 fail-loud — 실패를 성공으로 위장하지 않는다).
"""
from __future__ import annotations

import json
from typing import Any

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"

LOCAL_DISPLAY_CAP = 5  # 지역검색 쿼리당 최대 5건(§10 라이브 확인)
TIMEOUT_SEC = 50       # Cowork 는 도구 호출 하나를 60초에서 끊는다

NAVER_HEADERS = {
    "X-Naver-Client-Id": "{{secret:NAVER_CLIENT_ID}}",
    "X-Naver-Client-Secret": "{{secret:NAVER_CLIENT_SECRET}}",
}

SEARCHAD_UNAVAILABLE = (
    "사용 안 함 — 네이버 검색광고 API 는 요청마다 서명이 필요해 itda-hyve 서명 기능"
    "(itda-work/itda-hyve#34)을 기다린다. 월검색량(레벨)·연관 키워드가 빠진다"
)

# 네이버 Open API 오류 본문의 errorCode 중 키·앱 설정 문제(다시 보내도 같다 — 사용자가 고칠 것).
AUTH_ERROR_CODES = {
    "024": "Client ID 나 Secret 이 맞지 않는다 — itda-hyve 시크릿 탭의 NAVER_CLIENT_ID·NAVER_CLIENT_SECRET 을 확인",
    "028": "등록되지 않은 애플리케이션이다 — 네이버 개발자센터 애플리케이션을 확인",
    "010": "API 사용 신청이 안 돼 있다 — 애플리케이션 사용 API 에 검색·데이터랩(검색어트렌드)을 넣는다",
}


# ---------------------------------------------------------------------------
# 요청 모양 (itda-hyve http_request 인자 — save_as·save_dir 는 호출부가 붙인다)
# ---------------------------------------------------------------------------
def datalab_args(keywords: list[str], start: str, end: str, unit: str = "week") -> dict[str, Any]:
    """데이터랩 검색어트렌드 POST. 키워드 그룹 최대 5(그룹마다 키워드 1개). 조회 전용이라 ``retry_unsafe``."""
    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": unit,
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords],
    }
    return {
        "url": DATALAB_URL,
        "method": "POST",
        "headers": {**NAVER_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        "retry_unsafe": True,
        "follow_redirects": False,
        "timeout_sec": TIMEOUT_SEC,
    }


def local_args(q: str, display: int = LOCAL_DISPLAY_CAP) -> dict[str, Any]:
    """지역검색 GET. display 는 5로 cap(§10)."""
    capped = min(max(int(display), 1), LOCAL_DISPLAY_CAP)
    return {
        "url": LOCAL_URL,
        "params": {"query": q, "display": str(capped)},
        "headers": dict(NAVER_HEADERS),
        "follow_redirects": False,
        "timeout_sec": TIMEOUT_SEC,
    }


# ---------------------------------------------------------------------------
# 응답 판독
# ---------------------------------------------------------------------------
class NaverAPIError(Exception):
    """네이버 Open API 가 본문에 오류를 돌려줬다(``errorCode``·``errorMessage``)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{message} (errorCode {code})")
        self.code = code
        self.auth = code in AUTH_ERROR_CODES


def naver_error(obj: Any) -> NaverAPIError | None:
    """``{"errorMessage": "…", "errorCode": "024"}`` 꼴이면 그 오류."""
    if isinstance(obj, dict) and (obj.get("errorCode") or obj.get("errorMessage")):
        code = str(obj.get("errorCode") or "?")
        msg = str(obj.get("errorMessage") or "")
        hint = AUTH_ERROR_CODES.get(code)
        return NaverAPIError(code, f"{msg} — {hint}" if hint else msg)
    return None


def parse_datalab(obj: Any, keywords: list[str], *, start: str | None = None, end: str | None = None,
                  unit: str | None = None) -> tuple[bool, dict | None, str]:
    """데이터랩 응답 → (ok, payload, reason). 요청한 그룹이 전부 실려 있어야 성공이다(빠짐 = 실패).

    응답이 되비치는 조회 조건(``startDate``·``endDate``·``timeUnit``, 그룹별 ``keywords``)이 요청과 다르면 실패다 —
    저장 이름만 지키고 본문을 고쳐 보낸 응답이 성공으로 들어오지 않게(W17 리뷰 m4). 실패는 같은 요청을 다시 받는다.
    """
    err = naver_error(obj)
    if err is not None:
        raise err
    if not isinstance(obj, dict) or not isinstance(obj.get("results"), list):
        return False, None, "데이터랩 응답 형식 오류(results 없음)"
    for field, want in (("startDate", start), ("endDate", end), ("timeUnit", unit)):
        if want is not None and obj.get(field) != want:
            return False, None, f"데이터랩 응답의 {field}={obj.get(field)!r} 가 요청({want!r})과 다르다 — 요청 본문을 고치지 않고 다시 받는다"
    groups = {r.get("title"): r for r in obj["results"] if isinstance(r, dict)}
    missing = [k for k in keywords if k not in groups]
    if missing:
        return False, None, f"데이터랩 응답에 요청한 그룹이 빠졌다: {', '.join(missing)}"
    for k in keywords:
        got = groups[k].get("keywords")
        if got is not None and list(got) != [k]:
            return False, None, f"데이터랩 그룹 {k!r} 의 keywords={got!r} 가 요청([{k!r}])과 다르다"
    return True, obj, ""


def parse_local(obj: Any) -> tuple[bool, list[dict], str]:
    """지역검색 응답 → (ok, items, reason). items[].{title(<b>포함), category, roadAddress, address, mapx, mapy}."""
    err = naver_error(obj)
    if err is not None:
        raise err
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        return False, [], "지역검색 응답 형식 오류(items 없음)"
    return True, obj["items"], ""


def monthly_volume(row: dict) -> int:
    """월검색량(PC+모바일) 정수화. '< 10'·None은 0, 콤마 제거(§5 vol). 검색광고가 돌아오면 쓴다."""
    def _n(v: Any) -> int:
        if v in ("< 10", None):
            return 0
        try:
            return int(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return 0
    return _n(row.get("monthlyPcQcCnt")) + _n(row.get("monthlyMobileQcCnt"))
