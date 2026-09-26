"""관세청 공지사항 게시판 수집 모듈.

https://www.customs.go.kr/kcs/na/ntt/selectNttList.do?mi=2889&bbsId=1341
서버렌더 HTML(table.bbsList)을 브라우저 UA로 받아 파싱한다.
기본 WebFetch류 도구는 UA 차단으로 빈 페이지("시스템안내")를 받으므로
Chrome Desktop UA 고정이 이 스킬의 핵심이다.
"""
from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.customs.go.kr"
LIST_URL = f"{BASE_URL}/kcs/na/ntt/selectNttList.do"
MI = "2889"
BBS_ID = "1341"

CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


class CustomsError(RuntimeError):
    """관세청 수집 실패 (네트워크·마크업 변경 등)."""


def fetch_list_html(page: int = 1, max_retries: int = 3, timeout: int = 30) -> str:
    """공지사항 목록 페이지 HTML을 가져온다 (currPage 페이지네이션)."""
    params = {"mi": MI, "bbsId": BBS_ID, "currPage": str(page)}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                LIST_URL, params=params, headers=HEADERS, timeout=timeout
            )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"서버 오류 HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise CustomsError(f"관세청 요청 거부 HTTP {resp.status_code}")
            if not resp.content:
                raise ValueError("0바이트 응답")
            return resp.content.decode("utf-8", errors="replace")
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    raise CustomsError(f"관세청 목록 요청 실패 (재시도 초과): {last_exc}") from last_exc


def parse_list(html: str) -> list[dict]:
    """table.bbsList 행을 파싱한다.

    반환 필드: no, title, writer, date(YYYY-MM-DD), views, link
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.bbsList")
    if table is None:
        raise CustomsError(
            "목록 테이블(table.bbsList)을 찾지 못했습니다 — "
            "UA 차단(빈 안내 페이지) 또는 사이트 개편 가능성"
        )
    rows: list[dict] = []
    for tr in table.select("tbody tr"):
        a = tr.select_one("td[data-table=subject] a.nttInfoBtn")
        if a is None:
            continue
        ntt_sn = a.get("data-id", "")
        ntt_url = a.get("data-url", "")
        title = (a.get("title") or a.get_text(" ", strip=True)).strip()
        number_tds = tr.select("td[data-table=number]")
        date_td = tr.select_one("td[data-table=date]")
        write_td = tr.select_one("td[data-table=write]")
        no = number_tds[0] if number_tds else None
        date = (date_td.get_text(strip=True) if date_td else "").replace(".", "-")
        views = number_tds[1].get_text(strip=True) if len(number_tds) >= 2 else ""
        link = (
            f"{LIST_URL.replace('selectNttList', 'selectNttInfo')}"
            f"?mi={MI}&bbsId={BBS_ID}&nttSn={ntt_sn}&nttSnUrl={ntt_url}"
        )
        rows.append(
            {
                "no": no.get_text(strip=True) if no else "",
                "title": title,
                "writer": write_td.get_text(strip=True) if write_td else "",
                "date": date,
                "views": views,
                "link": link,
            }
        )
    if not rows:
        raise CustomsError(
            "목록 행을 1건도 파싱하지 못했습니다 — 사이트 개편으로 마크업이 "
            "바뀌었을 수 있습니다. 스킬 업데이트가 필요합니다."
        )
    return rows
