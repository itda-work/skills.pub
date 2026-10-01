"""관세청 공지사항 게시판 판독 — 목록·상세·첨부 경로 (네트워크 없음).

https://www.customs.go.kr/kcs/na/ntt/selectNttList.do?mi=2889&bbsId=1341
요청은 itda-hyve 가 보낸다. 이 모듈은 받은 HTML 을 읽기만 한다(공통부 ``board_common``).

실측(2026-09-30, itda-hyve 기본 UA ``Mozilla/5.0``):
  - 목록: ``p.page_num`` "전체 <span>1,626</span> 건 <span>1/163</span> 페이지", ``table.bbsList`` 쪽당 10행,
    행 번호(``td[data-table=number]`` 첫 칸)가 전체 건수에서 1씩 줄어든다. 공지 고정 행은 없었다.
  - 상세: 화면은 링크 대신 클릭 스크립트로 ``srchForm`` 을 POST 한다(``detail_request``). 목록 표에 싣는 GET 주소
    (``selectNttInfo.do?…&nttSn=…&nttSnUrl=…``)는 사람이 여는 주소이고 그것으로 열어도 같은 본문이 뜬다.
    ``table.bbsView`` caption 에 제목, ``ul.list_file`` 에 첨부 — 파일마다 ``[바이트 수]`` 가 붙어 있다.
  - 첨부: ``/common/nttFileDownload.do?fileKey=…`` GET → 파일 본문(받은 바이트 = 표시 바이트).
  - robots.txt 는 Googlebot·Yeti·Daum·Bingbot 에만 ``/*/na/ntt/`` 를 막는다(``User-agent: *`` 묶음 없음).
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from board_common import BoardError, PageStructureError, ext_of, host_path_allowed

SKILL = "customs-notice"
PROG = "collect_customs.py"
BOARD_NAME = "관세청 공지사항"
SOURCE_NOTE = "출처: 관세청 공지사항 https://www.customs.go.kr/kcs/na/ntt/selectNttList.do?mi=2889&bbsId=1341"
HOST = "www.customs.go.kr"
BASE_URL = f"https://{HOST}"
LIST_PATH = "/kcs/na/ntt/selectNttList.do"
DETAIL_PATH = "/kcs/na/ntt/selectNttInfo.do"
FILE_PATH = "/common/nttFileDownload.do"
MI = "2889"
BBS_ID = "1341"
PAGE_SIZE = 10

_PAGE_NUM = re.compile(r"전체\s*([\d,]+)\s*건\s*(\d+)\s*/\s*(\d+)\s*페이지")


# 요청 프로파일(2026-10-01 aside 폼 직렬화 · itda-hyve 실측, 사용자 결정 — W10 리뷰 M2):
#   1쪽   GET  메뉴 링크 그대로 ``selectNttList.do?mi=2889&bbsId=1341``
#   N쪽   POST ``pagingForm``(1쪽 화면의 폼, ``goPaging(N)`` 이 currPage 만 바꿔 제출) — 필드·순서는 브라우저 FormData 그대로
#   상세  POST ``srchForm``(``.nttInfoBtn`` 클릭이 nttSn·nttSnUrl 을 넣고 action 을 selectNttInfo.do 로 바꿔 제출)
# 쿠키 없이 성립한다(2쪽 행·상세 크기 표시가 GET 판과 같다). 싣는 헤더는 Content-Type·Referer 둘이다 — 브라우저가 싣는
# Origin 등은 싣지 않는다(없이도 성립, 실측). aside 는 요청 헤더를 잡지 못해 헤더 쪽은 실측이 아니라 고른 것이다.
# 12쪽부터는 1쪽 화면에서 바로 누를 수 없는 쪽이다 — 1쪽 폼에 쪽 번호만 바꿔 보낸다(서버는 currPage 로만 쪽을 정한다).
LIST_ENTRY = f"{BASE_URL}{LIST_PATH}?mi={MI}&bbsId={BBS_ID}"
FORM_TYPE = "application/x-www-form-urlencoded"
PAGING_FIELDS = (  # 1쪽 화면의 pagingForm, currPage 만 바뀐다(minSn·maxSn 은 1쪽 값 — 서버는 currPage 로 쪽을 정한다, 실측)
    ("currPage", None), ("confmUseAt", "N"), ("bbsId", BBS_ID), ("minSn", "0"), ("menuId", MI), ("newHour", "24"),
    ("cntntsId", BBS_ID), ("maxSn", "10"), ("manageAt", "N"), ("wrterId", "1"), ("sysId", "kcs"), ("menuTy", "BBS"),
    ("openAt", "Y"), ("listUseAt", "Y"), ("authChk", "false"), ("bbsTy", "NORMAL"), ("useAt", "Y"), ("mi", MI),
    ("noticeAt", "Y"),
)


def _form(fields) -> str:
    return urllib.parse.urlencode(list(fields))


def list_url(page: int) -> str:
    """사람이 여는 목록 주소(1쪽 메뉴 링크). 2쪽부터는 사이트가 POST 로 넘긴다 — ``list_request``."""
    return LIST_ENTRY


def list_request(page: int) -> dict:
    if page == 1:
        return {"url": LIST_ENTRY}
    body = _form((k, str(page) if k == "currPage" else v) for k, v in PAGING_FIELDS)
    return {"url": f"{BASE_URL}{LIST_PATH}", "method": "POST", "body": body,
            "headers": {"Content-Type": FORM_TYPE, "Referer": LIST_ENTRY}}


def _form_data(form) -> list[tuple[str, str]]:
    """브라우저 ``new FormData(form)`` 과 같은 순서·값(이 두 폼에 있는 요소만: input·select·textarea)."""
    out = []
    for el in form.find_all(["input", "select", "textarea"]):
        name = el.get("name")
        if not name or el.has_attr("disabled"):
            continue
        if el.name == "input":
            kind = (el.get("type") or "text").lower()
            if kind in ("button", "submit", "reset", "image", "file"):
                continue
            if kind in ("checkbox", "radio") and not el.has_attr("checked"):
                continue
            out.append((name, el.get("value", "on" if kind in ("checkbox", "radio") else "")))
        elif el.name == "select":
            opts = el.find_all("option")
            pick = next((o for o in opts if o.has_attr("selected")), opts[0] if opts else None)
            if pick is not None:
                out.append((name, pick.get("value", pick.get_text())))
        else:
            out.append((name, el.get_text()))
    return out


# 게시물마다·쪽마다 바뀌는 칸 — 값은 대조하지 않고 이름·자리만 본다
_VARIES = {"currPage", "nttSn", "nttSnUrl"}
_DETAIL_FIELDS = (("bbsId", BBS_ID), ("nttSn", None), ("nttSnUrl", None), ("mi", MI), ("currPage", None),
                  ("listCo", "10"), ("searchType", "all"), ("searchValue", ""))


def check_profile(html: str) -> list[str]:
    """1쪽 화면의 pagingForm·srchForm 을 이 스킬이 보내는 폼 상수와 대조한다(재확인 N3).

    사이트가 숨은 필드를 더하거나 값을 바꾸면 스킬은 옛 본문을 계속 보내게 된다 — 다르면 사유 목록, 같으면 빈 목록.
    """
    soup = BeautifulSoup(html, "html.parser")
    why = []
    for label, form, want in (("pagingForm", soup.find("form", attrs={"name": "pagingForm"}), PAGING_FIELDS),
                              ("srchForm", soup.find("form", id="srchForm"), _DETAIL_FIELDS)):
        if form is None:
            why.append(f"{label} 가 1쪽 화면에 없다")
            continue
        got = _form_data(form)
        if [k for k, _ in got] != [k for k, _ in want]:
            why.append(f"{label} 필드가 바뀌었다: 화면 {[k for k, _ in got]} · 스킬 {[k for k, _ in want]}")
            continue
        diff = [f"{k}={g!r}(스킬 {w!r})" for (k, g), (_, w) in zip(got, want) if k not in _VARIES and g != w]
        if diff:
            why.append(f"{label} 값이 바뀌었다: " + ", ".join(diff))
    return why


def detail_request(ntt_sn: str, ntt_url: str, page: int) -> dict:
    """상세 진입 — 그 게시물이 있던 쪽 화면의 srchForm(currPage 는 그 쪽). Referer 는 그 쪽 화면의 주소."""
    body = _form([("bbsId", BBS_ID), ("nttSn", ntt_sn), ("nttSnUrl", ntt_url), ("mi", MI), ("currPage", str(page)),
                  ("listCo", "10"), ("searchType", "all"), ("searchValue", "")])
    referer = LIST_ENTRY if page == 1 else f"{BASE_URL}{LIST_PATH}"
    return {"url": f"{BASE_URL}{DETAIL_PATH}", "method": "POST", "body": body,
            "headers": {"Content-Type": FORM_TYPE, "Referer": referer}}


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def parse_list(html: str) -> dict[str, Any]:
    """목록 한 쪽 → {total, page, last_page, rows[{no,id,title,writer,date,views,link}]}."""
    soup = _soup(html)
    num = soup.select_one("p.page_num")
    m = _PAGE_NUM.search(num.get_text(" ", strip=True)) if num else None
    if m is None:
        raise PageStructureError("전체 건수·쪽 표시(p.page_num)를 찾지 못했다")
    total, page, last = int(m.group(1).replace(",", "")), int(m.group(2)), int(m.group(3))
    table = soup.select_one("table.bbsList")
    if table is None:
        raise PageStructureError("목록 표(table.bbsList)를 찾지 못했다")
    rows = []
    for i, tr in enumerate(table.select("tbody tr"), 1):
        a = tr.select_one("td[data-table=subject] a.nttInfoBtn")
        nums = tr.select("td[data-table=number]")
        if a is None or not nums:
            if tr.get_text(strip=True) in ("", "게시물이 없습니다.", "등록된 게시물이 없습니다."):
                continue
            raise PageStructureError(f"{i}번째 행에서 제목 링크·번호를 못 읽었다")
        no_text = nums[0].get_text(strip=True)
        if not no_text.isdigit():
            raise PageStructureError(f"{i}번째 행 번호를 숫자로 못 읽었다({no_text!r})")
        ntt_sn, ntt_url = a.get("data-id", ""), a.get("data-url", "")
        if not ntt_sn.isdigit() or not re.fullmatch(r"[0-9a-f]{16,64}", ntt_url):
            raise PageStructureError(f"{i}번째 행의 게시물 식별자(data-id·data-url)가 이상하다")
        date_td = tr.select_one("td[data-table=date]")
        write_td = tr.select_one("td[data-table=write]")
        rows.append({
            "no": int(no_text),
            "id": ntt_sn,
            "title": (a.get("title") or a.get_text(" ", strip=True)).strip(),
            "writer": write_td.get_text(strip=True) if write_td else "",
            "date": (date_td.get_text(strip=True) if date_td else "").replace(".", "-"),
            "views": nums[1].get_text(strip=True) if len(nums) > 1 else "",
            "ntt_url": ntt_url,
            # 사람이 브라우저로 여는 링크 — 스킬은 이 GET 을 보내지 않는다(상세는 detail_request 의 POST). 화면은 링크 대신
            # 클릭 스크립트를 쓴다. 이 주소로 열어도 같은 상세가 뜬다(2026-09-30 200 확인).
            "link": f"{BASE_URL}{DETAIL_PATH}?mi={MI}&bbsId={BBS_ID}&nttSn={ntt_sn}&nttSnUrl={ntt_url}",
        })
    return {"total": total, "page": page, "last_page": last, "rows": rows}


def attach_tasks(row: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    """첨부 목록은 상세 화면에만 있다 — 먼저 상세를 받는다(사이트와 같은 srchForm POST)."""
    if not host_path_allowed(row["link"], HOST, (DETAIL_PATH,)):
        return {}, "상세 링크가 관세청 상세 화면 경로가 아니다"
    if not str(row.get("id", "")).isdigit() or not re.fullmatch(r"[0-9a-f]{16,64}", str(row.get("ntt_url", ""))):
        return {}, "게시물 식별자(nttSn·nttSnUrl)가 목록 결과에 없다 — 목록부터 새 회차로 받는다"
    key = f"d{row['id']}"
    req = detail_request(str(row["id"]), row["ntt_url"], int(row.get("page") or 1))
    return {key: {"kind": "detail", "post": str(row["no"]), "url": req["url"], "req": req,
                  "title": row["title"], "base": f"raw/detail/{row['id']}.html"}}, ""


def parse_detail(html: str, task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """상세 화면 → 받을 첨부 작업. 제목이 목록과 다르면 다른 게시물이다."""
    soup = _soup(html)
    view = soup.select_one("table.bbsView")
    if view is None:
        raise PageStructureError("상세 표(table.bbsView)를 찾지 못했다")
    cap = view.select_one("caption")
    cap_text = " ".join(cap.get_text(" ", strip=True).split()) if cap else ""
    title = " ".join(task["title"].split())
    if not cap_text.startswith(title):
        raise PageStructureError("상세 화면의 제목이 목록의 제목과 다르다 — 다른 게시물이다")
    ul = view.select_one("ul.list_file")
    if ul is None:
        raise PageStructureError("첨부 목록(ul.list_file)을 찾지 못했다")
    out: dict[str, dict[str, Any]] = {}
    post_id = task["base"].rsplit("/", 1)[-1].split(".")[0]
    for k, a in enumerate(ul.select("li > a[href]:not(.btnFile_view)"), 1):
        href = urllib.parse.urljoin(BASE_URL + "/", a["href"])
        if not host_path_allowed(href, HOST, (FILE_PATH,)):
            raise PageStructureError(f"첨부 {k} 의 경로가 관세청 첨부 경로가 아니다")
        span = a.select_one("span")
        if span is None or not span.get_text(strip=True).isdigit():
            # 크기 대조가 관세청 첨부 ok 의 근거다 — 표시를 못 읽으면 대조 없이 넘어가지 않는다(리뷰 m3)
            raise PageStructureError(f"첨부 {k} 의 크기 표시([바이트])를 읽지 못했다")
        size = int(span.get_text(strip=True))
        name = (a.get("title") or "").removesuffix(" 다운로드").strip()
        if not name:
            name = re.split(r"\s*\[", a.get_text(" ", strip=True))[0].strip()
        ext = ext_of(name)
        out[f"a{post_id}-{k}"] = {"kind": "att", "post": task["post"], "url": href, "name": name,
                                  "ext": ext, "size": size, "base": f"raw/att/{post_id}-{k}.{ext}"}
    return out


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["| 번호 | 날짜 | 제목 | 작성자 | 링크 |", "|---|---|---|---|---|"]
    for r in rows:
        title = r["title"].replace("|", "\\|")
        lines.append(f"| {r['no']} | {r['date']} | {title} | {r['writer']} | [보기]({r['link']}) |")
    return "\n".join(lines)


def write_xlsx(rows: list[dict[str, Any]], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise BoardError("args", "xlsx 저장에는 openpyxl 이 필요합니다: python3 -m pip install --user openpyxl")
    wb = Workbook()
    ws = wb.active
    ws.title = "관세청 공지사항"
    ws.append(["번호", "날짜", "제목", "작성자", "조회수", "링크"])
    for r in rows:
        ws.append([r["no"], r["date"], r["title"], r["writer"], r["views"], r["link"]])
    wb.save(path)
