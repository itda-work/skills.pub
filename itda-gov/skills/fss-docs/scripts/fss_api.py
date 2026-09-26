"""금융감독원 공통업무자료 게시판 수집 모듈.

https://www.fss.or.kr/fss/bbs/B0000079/list.do?menuNo=200111
서버렌더 HTML 테이블을 브라우저 UA로 받아 파싱한다.
"""
from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.fss.or.kr"
LIST_URL = f"{BASE_URL}/fss/bbs/B0000079/list.do"
MENU_NO = "200111"

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


class FssError(RuntimeError):
    """금감원 수집 실패 (네트워크·마크업 변경 등)."""


def fetch_list_html(page: int = 1, max_retries: int = 3, timeout: int = 30) -> str:
    """공통업무자료 목록 페이지 HTML을 가져온다 (pageIndex 페이지네이션)."""
    params = {"menuNo": MENU_NO, "pageIndex": str(page)}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                LIST_URL, params=params, headers=HEADERS, timeout=timeout
            )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"서버 오류 HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise FssError(f"금감원 요청 거부 HTTP {resp.status_code}")
            if not resp.content:
                raise ValueError("0바이트 응답")
            return resp.content.decode("utf-8", errors="replace")
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    raise FssError(f"금감원 목록 요청 실패 (재시도 초과): {last_exc}") from last_exc


def parse_list(html: str) -> list[dict]:
    """게시판 테이블 행을 파싱한다.

    반환 필드: no, title, dept, date(YYYY-MM-DD), attachments(list[str]), views, link
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for tr in soup.select("table tbody tr"):
        title_a = tr.select_one("td.title a[href]")
        if title_a is None:
            continue
        href = title_a["href"]
        tds = tr.find_all("td")
        # 관측 구조: num | title | 부서 | 날짜 | 첨부 | 조회수
        no = tds[0].get_text(strip=True) if tds else ""
        dept = ""
        date = ""
        views = ""
        for td in tds:
            text = td.get_text(strip=True)
            if not date and len(text) == 10 and text[4] == "-" and text[7] == "-":
                date = text
        plain = [td.get_text(strip=True) for td in tds]
        if len(plain) >= 3:
            dept = plain[2]
        if plain and plain[-1].replace(",", "").isdigit():
            views = plain[-1]
        attachments = [
            (a.get("title") or a.get_text(" ", strip=True)).removesuffix(" 다운로드")
            for a in tr.select("a.file-single")
        ]
        rows.append(
            {
                "no": no,
                "title": title_a.get_text(" ", strip=True),
                "dept": dept,
                "date": date,
                "views": views,
                "attachments": attachments,
                "link": BASE_URL + href if href.startswith("/") else href,
            }
        )
    if not rows:
        raise FssError(
            "목록 행을 1건도 파싱하지 못했습니다 — 사이트 개편으로 마크업이 "
            "바뀌었을 수 있습니다. 스킬 업데이트가 필요합니다."
        )
    return rows
