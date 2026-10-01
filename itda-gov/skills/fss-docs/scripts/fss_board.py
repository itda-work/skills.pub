"""금융감독원 공통업무자료 게시판 판독 — 목록·첨부 경로 (네트워크 없음).

https://www.fss.or.kr/fss/bbs/B0000079/list.do?menuNo=200111
요청은 itda-hyve 가 보낸다. 이 모듈은 받은 HTML 을 읽기만 한다(공통부 ``board_common``).

실측(2026-09-30, itda-hyve 기본 UA ``Mozilla/5.0``):
  - 목록: ``div.total-count`` "전체 <em>1351</em> 건 | 페이지 <em>1</em> / 136", 쪽당 10행,
    열은 번호·제목·담당부서·등록일·첨부파일·조회수. 행 번호(``td.num``)가 전체 건수에서 1씩 줄어든다.
  - 첨부: 목록 행 안의 ``ul.list-board-attach-file`` 에 ``/fss/cmmn/file/fileDown.do?…`` 링크와 파일 이름이 있다
    (2026-07 판의 ``a.file-single`` 은 사라졌다 — 옛 판은 첨부를 0건으로 셌다). 상세 화면을 받지 않아도 된다.
    다운로드 응답에는 크기 표시가 없어 크기 대조는 못 하고, 형식·끝 표지 검사만 한다.
  - robots.txt 는 Yeti 에만 ``/bos/``·``/upload/`` 등을 막는다(``User-agent: *`` 묶음 없음).
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from board_common import BoardError, PageStructureError, ext_of, host_path_allowed

SKILL = "fss-docs"
PROG = "collect_fss.py"
BOARD_NAME = "금융감독원 공통업무자료"
SOURCE_NOTE = "출처: 금융감독원 공통업무자료 https://www.fss.or.kr/fss/bbs/B0000079/list.do?menuNo=200111"
HOST = "www.fss.or.kr"
BASE_URL = f"https://{HOST}"
LIST_PATH = "/fss/bbs/B0000079/list.do"
VIEW_PATH = "/fss/bbs/B0000079/view.do"
FILE_PATH = "/fss/cmmn/file/fileDown.do"
MENU_NO = "200111"
PAGE_SIZE = 10

_TOTAL = re.compile(r"전체\s*([\d,]+)\s*건.*?페이지\s*(\d+)\s*/\s*(\d+)")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def list_url(page: int) -> str:
    # 사이트의 쪽 넘김은 GET 폼(frm) 전체를 싣는다 — 2026-10-01 aside 실측 2쪽 주소:
    #   list.do?menuNo=200111&bbsId=&viewType=&cl1Cd=&pageIndex=2&sdate=&edate=&searchCnd=1&searchWrd=
    # 이 스킬은 그중 menuNo·pageIndex 만 싣는다(나머지는 빈 값·검색 기본값). 두 키만으로 같은 목록이 온다(1~3·20·136쪽 실측,
    # 게시물 번호·분모 일치) — 사용자 결정(W10 리뷰 M2)으로 이 부분집합을 유지한다.
    return f"{BASE_URL}{LIST_PATH}?menuNo={MENU_NO}&pageIndex={page}"


def parse_list(html: str) -> dict[str, Any]:
    """목록 한 쪽 → {total, page, last_page, rows[{no,id,title,dept,date,views,attachments,link}]}."""
    soup = BeautifulSoup(html, "html.parser")
    tc = soup.select_one("div.total-count")
    m = _TOTAL.search(tc.get_text(" ", strip=True)) if tc else None
    if m is None:
        raise PageStructureError("전체 건수·쪽 표시(div.total-count)를 찾지 못했다")
    total, page, last = int(m.group(1).replace(",", "")), int(m.group(2)), int(m.group(3))
    heads = [th.get_text(strip=True) for th in soup.select("table thead th")]
    if heads[:6] != ["번호", "제목", "담당부서", "등록일", "첨부파일", "조회수"]:
        raise PageStructureError(f"목록 표의 열이 바뀌었다: {heads}")
    rows = []
    for i, tr in enumerate(soup.select("table tbody tr"), 1):
        tds = tr.find_all("td", recursive=False)
        a = tr.select_one("td.title a[href]")
        if a is None or len(tds) < 6:
            if tr.get_text(strip=True) in ("", "게시물이 없습니다.", "등록된 게시물이 없습니다."):
                continue
            raise PageStructureError(f"{i}번째 행에서 제목 링크·열을 못 읽었다")
        no_text = tds[0].get_text(strip=True)
        if not no_text.isdigit():
            raise PageStructureError(f"{i}번째 행 번호를 숫자로 못 읽었다({no_text!r})")
        link = urllib.parse.urljoin(BASE_URL + "/", a["href"])
        ntt = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("nttId", [""])[0]
        if not ntt.isdigit():
            raise PageStructureError(f"{i}번째 행의 게시물 식별자(nttId)를 못 읽었다")
        date = tds[3].get_text(strip=True)
        if not _DATE.match(date):
            raise PageStructureError(f"{i}번째 행 등록일이 날짜가 아니다({date!r})")
        attachments = []
        for fa in tds[4].select("ul.list-board-attach-file li a[href]"):
            name_el = fa.select_one("span.name")
            attachments.append({"name": (name_el or fa).get_text(" ", strip=True),
                                "url": urllib.parse.urljoin(BASE_URL + "/", fa["href"])})
        cell = tds[4]
        if not attachments and (cell.find(True) is not None or cell.get_text(strip=True) not in ("", "-")):
            # class 이름에 기대지 않는다 — 첨부 칸에 무엇이든 있는데 읽은 첨부가 0 이면 구조가 바뀐 것이다(리뷰 m4).
            # 첨부 없는 행의 실물 표본은 아직 없다(2026-09-30·10-01 실측 41행 모두 첨부 있음)
            raise PageStructureError(f"{i}번째 행 첨부 칸에 내용이 있는데 파일 목록을 못 읽었다")
        rows.append({
            "no": int(no_text),
            "id": ntt,
            "title": a.get_text(" ", strip=True),
            "dept": tds[2].get_text(strip=True),
            "date": date,
            "views": tds[5].get_text(strip=True),
            "attachments": attachments,
            "link": link,
        })
    return {"total": total, "page": page, "last_page": last, "rows": rows}


def attach_tasks(row: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    """첨부 링크가 목록에 있다 — 바로 받는다."""
    if not row["attachments"]:
        return {}, "첨부가 없는 게시물이다"
    out = {}
    for k, att in enumerate(row["attachments"], 1):
        if not host_path_allowed(att["url"], HOST, (FILE_PATH,)):
            return {}, f"첨부 {k} 의 경로가 금감원 첨부 경로가 아니다"
        ext = ext_of(att["name"])
        out[f"a{row['id']}-{k}"] = {"kind": "att", "post": str(row["no"]), "url": att["url"], "name": att["name"],
                                    "ext": ext, "size": None, "base": f"raw/att/{row['id']}-{k}.{ext}"}
    return out, ""


def parse_detail(html: str, task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raise PageStructureError("fss-docs 는 상세 화면을 받지 않는다")


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["| 번호 | 날짜 | 제목 | 담당부서 | 첨부 | 링크 |", "|---|---|---|---|---|---|"]
    for r in rows:
        title = r["title"].replace("|", "\\|")
        att = f"{len(r['attachments'])}건" if r["attachments"] else "-"
        lines.append(f"| {r['no']} | {r['date']} | {title} | {r['dept']} | {att} | [보기]({r['link']}) |")
    return "\n".join(lines)


def write_xlsx(rows: list[dict[str, Any]], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise BoardError("args", "xlsx 저장에는 openpyxl 이 필요합니다: python3 -m pip install --user openpyxl")
    wb = Workbook()
    ws = wb.active
    ws.title = "금감원 공통업무자료"
    ws.append(["번호", "날짜", "제목", "담당부서", "첨부파일", "조회수", "링크"])
    for r in rows:
        ws.append([r["no"], r["date"], r["title"], r["dept"], "; ".join(a["name"] for a in r["attachments"]),
                   r["views"], r["link"]])
    wb.save(path)
