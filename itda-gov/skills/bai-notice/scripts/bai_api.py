"""감사원 통합공지 수집 모듈.

감사원 사이트는 Nuxt SPA 라 HTML 파싱이 불가하지만, 화면이 쓰는 내부 JSON API
(`/api/boards/notice/list`)를 직접 호출한다 (2026-07-27 번들 분석으로 확정).

- 파라미터: brdId=notice, page(0-base), size, searchText, fromRegiDt/toRegiDt
- 응답: HAL JSON — _embedded.boardDtoList[], page{totalElements,...}
"""
from __future__ import annotations

import re
import time

import requests

BASE_URL = "https://www.bai.go.kr"
LIST_API = f"{BASE_URL}/api/boards/notice/list"
LIST_PAGE = f"{BASE_URL}/bai/notice/notification/tab01"

CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": LIST_PAGE,
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[\s ]+")


class BaiError(RuntimeError):
    """감사원 수집 실패 (네트워크·API 변경 등)."""


def strip_html(text: str | None, max_len: int = 120) -> str:
    """smmTxt 의 HTML 조각을 평문 요약으로 정리한다."""
    if not text:
        return ""
    plain = _TAG_RE.sub(" ", text)
    plain = plain.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    plain = plain.replace("&amp;", "&").replace("&quot;", '"')
    plain = _WS_RE.sub(" ", plain).strip()
    # HTML 주석 잔재(StartFragment 등) 제거
    plain = re.sub(r"<!--[^>]*-->", "", plain).strip()
    if len(plain) > max_len:
        plain = plain[: max_len - 1] + "…"
    return plain


def fetch_list(
    page: int = 0,
    size: int = 10,
    keyword: str = "",
    date_from: str = "",
    date_to: str = "",
    max_retries: int = 3,
    timeout: int = 30,
) -> dict:
    """통합공지 목록 JSON을 가져온다 (page 는 0-base)."""
    params = {
        "brdId": "notice",
        "searchType": "0",
        "searchText": keyword,
        "fromRegiDt": date_from,
        "toRegiDt": date_to,
        "searchYear": "",
        "size": str(size),
        "index": "0",
        "page": str(page),
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                LIST_API, params=params, headers=HEADERS, timeout=timeout
            )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"서버 오류 HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise BaiError(f"감사원 API 요청 거부 HTTP {resp.status_code}")
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    raise BaiError(f"감사원 API 요청 실패 (재시도 초과): {last_exc}") from last_exc


def parse_rows(payload: dict) -> list[dict]:
    """HAL JSON 응답에서 목록 행을 추출한다.

    반환 필드: no, title, dept, date(YYYY-MM-DD), summary, link
    """
    embedded = payload.get("_embedded")
    if embedded is None:
        if "errorMessage" in payload:
            raise BaiError(f"감사원 API 오류 응답: {payload['errorMessage']}")
        # 검색 결과 0건이면 _embedded 자체가 빠질 수 있다 — 정상 빈 목록
        return []
    dtos = embedded.get("boardDtoList")
    if dtos is None:
        raise BaiError(
            "응답에서 boardDtoList 를 찾지 못했습니다 — API 스키마가 "
            "바뀌었을 수 있습니다. 스킬 업데이트가 필요합니다."
        )
    rows: list[dict] = []
    for d in dtos:
        regi = (d.get("regiDt") or "")[:10]
        brd_id = d.get("brdId", "")
        post_no = d.get("postNo", "")
        rows.append(
            {
                "no": str(post_no),
                "title": (d.get("titNm") or "").strip(),
                "dept": (d.get("chgrNm") or "").strip(),
                "date": regi,
                "summary": strip_html(d.get("smmTxt")),
                "link": (
                    f"{BASE_URL}/bai/notice/notification/detail"
                    f"?tabId=tab01&brdId={brd_id}&postNo={post_no}"
                ),
            }
        )
    return rows
