#!/usr/bin/env python3
"""군인공제회 복지포털(welfaremain.do) 공개 콘텐츠 수집기.

GNB에서 복지포털 메뉴 트리를 동적 발견하고, 각 페이지 본문을 추출해
data/pages.jsonl 스냅샷으로 저장한다. 게시판(특별할인소식)·제휴복지
카테고리 목록은 상세 페이지까지 순회한다.

로그인 벽 페이지는 auth_required=True 로 표시만 하고 본문을 저장하지
않는다(개인 영역 미수집). 저속 순차 수집(기본 0.7s 간격)만 지원한다.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다")

import argparse
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

BASE = "https://www.mmaa.or.kr"
ENTRY = f"{BASE}/web/contents/welfaremain.do"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 itda-skills-mmaa-welfare"
)
# 제휴복지 카테고리 목록 (schBdcode 코드 → 라벨)
CATEGORY_CODES = {
    "_categoryview01": "호텔/리조트",
    "_categoryview02": "의료/건강",
    "_categoryview03": "쇼핑",
    "_categoryview04": "교육",
    "_categoryview05": "자기계발",
    "_categoryview06": "생활/취미",
    "_categoryview07": "경조사",
    "_categoryview08": "기타",
}
BOARD_CODE = "_welfareboard01"  # 특별할인소식
# 회원 전용 페이지의 정적 HTML 은 본문 대신 최상위 <script> 에 무조건 리다이렉트를 싣는다:
#   alert("로그인 후 이용 가능합니다."); location.href='/web/contents/webLogin.do'
# 공개 페이지에도 같은 문자열이 ajax 오류 콜백·onclick 속성 안에 들어 있으므로(#1643 실측),
# "스크립트 본문이 alert → location.href 두 문장뿐" 인 형태만 로그인 벽으로 판정한다.
LOGIN_REDIRECT_RE = re.compile(
    r"^alert\([\"'][^\"']*[\"']\)\s*;?\s*"
    r"(?:window\.|top\.)?location\.href\s*=\s*[\"'][^\"']*webLogin\.do[^\"']*[\"']\s*;?$"
)
# 본문에서 제거할 잡음 셀렉터 (GNB·검색·SNS 공유 등)
NOISE_SELECTORS = [
    "header", "footer", "nav", "script", "style", "noscript",
    ".depth-bg", ".dep2-list", ".gnb", ".lnb", ".snb", ".location",
    ".sns", ".share", ".btn_share", ".skip", "#header", "#footer",
    ".quick", ".breadcrumb", ".paging", ".pagination",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class Collector:
    def __init__(self, out_dir: Path, delay: float = 0.7, limit: int | None = None):
        self.out_dir = out_dir
        self.delay = delay
        self.limit = limit
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.pages: list[dict] = []
        self.seen: set[str] = set()

    def fetch(self, url: str) -> str | None:
        time.sleep(self.delay)
        try:
            resp = self.session.get(url, timeout=30)
        except requests.RequestException as exc:
            log(f"  ! fetch 실패 {url}: {exc}")
            return None
        if resp.status_code != 200:
            log(f"  ! HTTP {resp.status_code} {url}")
            return None
        return resp.text

    # ---------- GNB 메뉴 트리 ----------

    def discover_menu(self, html: str) -> list[dict]:
        """GNB 의 복지포털 dep1 블록에서 (url, breadcrumb) 목록 추출."""
        soup = BeautifulSoup(html, "html.parser")
        anchor = soup.find(
            "a", class_="dep1a", title=re.compile("복지포털")
        )
        if anchor is None:
            raise RuntimeError(
                "GNB에서 복지포털 메뉴를 찾지 못했습니다 — 사이트 구조 변경 가능성. "
                "collect.py discover_menu 의 셀렉터를 재실측하세요."
            )
        block = anchor.find_parent("li", class_="dep1")
        entries: list[dict] = []
        for a in block.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#") or not href:
                continue
            url = urljoin(BASE, href)
            parsed = urlparse(url)
            if parsed.netloc != urlparse(BASE).netloc:
                continue  # 외부 링크 제외
            if not parsed.path.startswith("/web/contents/"):
                continue
            title = (a.get("title") or a.get_text(" ", strip=True)).strip()
            title = re.sub(r"\s*바로가기.*$", "", title)
            crumbs = ["복지포털"]
            for cls in ("dep2", "dep3", "dep4"):
                parent_li = a.find_parent("li", class_=cls)
                if parent_li:
                    head = parent_li.find("a")
                    if head and head is not a:
                        head_title = (head.get("title") or head.get_text(strip=True)).strip()
                        if head_title and head_title not in crumbs:
                            crumbs.append(head_title)
            crumbs.append(title)
            # 인접 중복 제거
            breadcrumb = []
            for c in crumbs:
                if not breadcrumb or breadcrumb[-1] != c:
                    breadcrumb.append(c)
            entries.append({"url": url, "breadcrumb": " > ".join(breadcrumb), "title": title})
        # URL 중복 제거 (첫 breadcrumb 우선)
        uniq: dict[str, dict] = {}
        for e in entries:
            uniq.setdefault(e["url"], e)
        return list(uniq.values())

    # ---------- 본문 추출 ----------

    def extract_content(self, html: str) -> tuple[str, str]:
        """(title, 본문 텍스트) 추출. 실패 시 ('', '')."""
        soup = BeautifulSoup(html, "html.parser")
        # div.content 폴백 금지 — 그 요소는 GNB 메뉴라 셸 페이지에서 37자 메뉴 문자열을
        # 본문으로 위장시켰다(#1643). 본문 컨테이너가 없으면 빈 본문이다.
        container = soup.select_one("section#container")
        if container is None:
            return "", ""
        for sel in NOISE_SELECTORS:
            for el in container.select(sel):
                el.decompose()
        title_el = container.select_one("h2.sub_tit") or container.find("h2")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        # 표를 행 단위로 보존
        for table in container.find_all("table"):
            rows_txt = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows_txt.append(" | ".join(cells))
            table.replace_with(soup.new_string("\n" + "\n".join(rows_txt) + "\n"))
        text = container.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return title, text.strip()

    @staticmethod
    def has_login_redirect(html: str) -> bool:
        """최상위 <script> 가 로그인 리다이렉트 두 문장뿐인 셸인지 판정(전문 대상).

        종전 판정은 html[:4000] + len(html) < 8000 조건이라 176KB 셸을 못 잡았고, 그 셸의
        GNB 문자열(37자)이 본문으로 계수됐다(#1643 — 22페이지 오분류).
        """
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            if script.get("src"):
                continue
            body = script.get_text()
            body = re.sub(r"//\s*<!\[CDATA\[|//\s*\]\]>|<!--|-->", " ", body)
            body = re.sub(r"\s+", " ", body).strip()
            if body and LOGIN_REDIRECT_RE.match(body):
                return True
        return False

    def is_login_wall(self, html: str, url: str) -> bool:
        if "webLogin.do" in url:
            return True
        return self.has_login_redirect(html)

    # ---------- 페이지 저장 ----------

    def add_page(self, url: str, breadcrumb: str, html: str, kind: str) -> None:
        title, text = self.extract_content(html)
        auth = self.is_login_wall(html, url) or (len(text) < 80 and any(
            k in url for k in ("Open.do", "Inquiry.do", "Apply.do", "Reservation")
        ))
        if not auth and not text:
            log(f"  ! 본문 컨테이너 없음(빈 본문으로 기록): {url}")
        record = {
            "url": url,
            "breadcrumb": breadcrumb,
            "title": title or breadcrumb.split(" > ")[-1],
            "kind": kind,
            "auth_required": bool(auth),
            "text": "" if auth else text,
            "chars": 0 if auth else len(text),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.pages.append(record)
        flag = " [로그인필요]" if auth else f" ({len(text)}자)"
        log(f"  + {record['title']}{flag}")

    def crawl_url(self, url: str, breadcrumb: str, kind: str = "page") -> str | None:
        if url in self.seen:
            return None
        self.seen.add(url)
        if self.limit and len(self.pages) >= self.limit:
            return None
        html = self.fetch(url)
        if html is None:
            return None
        self.add_page(url, breadcrumb, html, kind)
        return html

    # ---------- 목록형 순회 ----------

    def crawl_listing(self, list_url_tmpl: str, breadcrumb: str, view_path: str, kind: str,
                      max_pages: int = 20) -> None:
        """페이지네이션 목록 순회 → 상세(view) 전수 수집."""
        for page in range(1, max_pages + 1):
            list_url = list_url_tmpl.format(page=page)
            html = self.fetch(list_url)
            if html is None:
                break
            ids = []
            for m in re.finditer(
                re.escape(view_path) + r"\?schM=view[^\"'>]*?[?&]id=(\d+)|"
                + re.escape(view_path) + r"\?[^\"'>]*?schM=view[^\"'>]*?&(?:amp;)?id=(\d+)",
                html,
            ):
                pid = m.group(1) or m.group(2)
                if pid:
                    ids.append(pid)
            ids = list(dict.fromkeys(ids))
            if not ids:
                break
            new = 0
            for pid in ids:
                view_url = f"{BASE}{view_path}?schM=view&id={pid}"
                if view_url in self.seen:
                    continue
                new += 1
                self.crawl_url(view_url, breadcrumb, kind=kind)
                if self.limit and len(self.pages) >= self.limit:
                    return
            if new == 0:
                break  # 다음 페이지가 같은 목록 반복 → 종료

    # ---------- 실행 ----------

    def run(self) -> None:
        log(f"복지포털 수집 시작: {ENTRY}")
        entry_html = self.fetch(ENTRY)
        if entry_html is None:
            raise RuntimeError(
                "복지포털 메인 페이지 fetch 실패 — 네트워크 또는 WAF 차단. "
                "잠시 후 재시도하거나 브라우저 경유 수집을 검토하세요."
            )
        menu = self.discover_menu(entry_html)
        log(f"GNB 복지포털 메뉴 {len(menu)}개 발견")
        self.add_page(ENTRY, "복지포털 > 복지 한눈에 보기", entry_html, "page")
        self.seen.add(ENTRY)

        for entry in menu:
            self.crawl_url(entry["url"], entry["breadcrumb"])

        # 제휴복지 카테고리 상세 전수
        for code, label in CATEGORY_CODES.items():
            log(f"제휴복지 카테고리: {label}")
            tmpl = (f"{BASE}/web/contents/WFL-Category.do?schM=list&page={{page}}"
                    f"&viewCount=8&id=&schBdcode={code}&schGroupCode=")
            self.crawl_listing(tmpl, f"복지포털 > 제휴복지 > {label}",
                               "/web/contents/WFL-Category.do", kind="partner")

        # 특별할인소식 게시판 전수
        log("특별할인소식 게시판")
        tmpl = (f"{BASE}/web/contents/welfareboard.do?schM=list&page={{page}}"
                f"&schBdcode={BOARD_CODE}")
        self.crawl_listing(tmpl, "복지포털 > 제휴복지 > 특별할인소식",
                           "/web/contents/welfareboard.do", kind="board")

        self.save()

    def save(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        pages_path = self.out_dir / "pages.jsonl"
        with pages_path.open("w", encoding="utf-8") as f:
            for rec in self.pages:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        content_pages = [p for p in self.pages if not p["auth_required"] and p["chars"] > 0]
        meta = {
            "source": ENTRY,
            "generated_at": date.today().isoformat(),
            "page_count": len(self.pages),
            "content_page_count": len(content_pages),
            "auth_required_count": sum(1 for p in self.pages if p["auth_required"]),
        }
        (self.out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        log(f"저장 완료: {pages_path} ({meta['page_count']}페이지, "
            f"본문 {meta['content_page_count']}, 로그인영역 {meta['auth_required_count']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="군인공제회 복지포털 스냅샷 수집")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent.parent / "data"),
                        help="스냅샷 저장 경로 (기본: 스킬 data/)")
    parser.add_argument("--delay", type=float, default=0.7, help="요청 간격 초 (기본 0.7)")
    parser.add_argument("--limit", type=int, default=None, help="최대 수집 페이지 수 (스모크용)")
    args = parser.parse_args()
    Collector(Path(args.output_dir), delay=args.delay, limit=args.limit).run()


if __name__ == "__main__":
    main()
