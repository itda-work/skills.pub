#!/usr/bin/env python3
"""군인공제회 복지포털(welfaremain.do) 공개 콘텐츠 스냅샷 재수집 — 네트워크 없음.

요청은 itda-hyve 가 보낸다(itda-work/skills#45 — 규칙 ``cowork-network-via-hyve``). 이 스크립트는 회차 폴더의
상태 파일(``mmaa-state.json``)을 들고 바퀴마다 다음에 받을 페이지를 계획하고, itda-hyve 가 ``save_as`` 로 저장한
HTML 을 판독한다. 받을 것이 더 없고 전부 받았을 때만 스냅샷(``pages.jsonl``·``meta.json``)을 쓴다.

    python3 collect.py plan    --run-dir R --save-dir S [--limit N]
        → 진입 페이지 1개 계획(plan-01.json)
    python3 collect.py collect --run-dir R [--output-dir OUT]
        → 받은 파일 판독 → 다음 계획(plan-NNa.json …, 8개씩) 또는 스냅샷 저장

흐름: GNB 에서 복지포털 메뉴 트리를 동적으로 발견하고(진입 → 메뉴 페이지), 제휴복지 카테고리·특별할인소식 목록은
1쪽부터 상세까지 따라간다(2026-10-01 실측으로는 목록이 로그인 셸이라 상세가 나오지 않는다 — 열리면 따라간다).

로그인 벽 페이지는 auth_required=True 로 표시만 하고 본문을 저장하지 않는다(개인 영역 미수집).
전량 대조: 계획한 페이지가 전부 와야 저장한다. 한 페이지를 세 번 받지 못하거나(실패 자리 포함) 사이트 페이지가 아닌
본문(WAF 차단·잘림)이 세 번 오면 ``partial`` 로 끝내고 스냅샷을 쓰지 않는다(부분본을 전량으로 저장하지 않는다).

종료 코드: 0 planned·incomplete·ok / 1 입력·상태 오류 / 2 partial·인자 오류.
"""

import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다")

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from hyve_input import HyveFailure, HyveInputError, HyveReadError, read_input

BASE = "https://www.mmaa.or.kr"
ENTRY = f"{BASE}/web/contents/welfaremain.do"
HOST = urlparse(BASE).netloc
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
LISTINGS = [
    *[
        {
            "code": code,
            "tmpl": f"{BASE}/web/contents/WFL-Category.do?schM=list&page={{page}}&viewCount=8&id=&schBdcode={code}&schGroupCode=",
            "breadcrumb": f"복지포털 > 제휴복지 > {label}",
            "view_path": "/web/contents/WFL-Category.do",
            "kind": "partner",
        }
        for code, label in CATEGORY_CODES.items()
    ],
    {
        "code": BOARD_CODE,
        "tmpl": f"{BASE}/web/contents/welfareboard.do?schM=list&page={{page}}&schBdcode={BOARD_CODE}",
        "breadcrumb": "복지포털 > 제휴복지 > 특별할인소식",
        "view_path": "/web/contents/welfareboard.do",
        "kind": "board",
    },
]
MAX_LIST_PAGES = 20
MAX_ATTEMPTS = 3      # 한 페이지를 받지 못한(또는 나쁜 본문) 횟수 상한
MAX_ROUNDS = 30       # 바퀴 상한 — 나쁜 파일을 끝없이 다시 계획하지 않는다. 바퀴는 앞 계획이 전부 판정된(안 온 파일 0) collect 만 센다
MAX_IDLE = 5          # 새로 도착한 파일 없이 collect 를 연달아 부른 횟수 상한 — 상태는 그대로 두고 멈춘다(되살릴 수 있다)
CHUNK = 8             # 계획 파일 하나의 호출 수 = itda-hyve batch 동시 실행 한 번(저속 수집)
TIMEOUT_SEC = 45
BATCH_TIMEOUT_SEC = 50
STATE = "mmaa-state.json"
SAVE_PREFIX = "mmaa/"
# 호스트 절대 경로 — 스크립트가 도는 OS 가 아니라 itda-hyve 호스트 기준(Windows 호스트면 C:\… 가 온다)
_HOST_ABS = re.compile(r"^(/|[A-Za-z]:[\\/]|\\\\[^\\]+\\)")

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


class CollectError(Exception):
    """사용자에게 보일 실패 — ``kind`` 가 출력 ``error`` 값."""

    def __init__(self, kind: str, message: str, code: int = 1):
        super().__init__(message)
        self.kind = kind
        self.code = code


def host_abs_path(raw: str) -> str:
    """``--save-dir`` 검사 — itda-hyve 호스트의 절대 경로(POSIX ``/…``·``C:\\…``·``C:/…``·UNC)."""
    value = (raw or "").strip()
    if not _HOST_ABS.match(value):
        raise CollectError("args", "--save-dir 는 회차 폴더의 호스트 절대 경로입니다(예: /Users/me/작업/mmaa-runs/20261001 · C:\\Users\\me\\…)", 2)
    stripped = value.rstrip("/\\")
    if re.fullmatch(r"[A-Za-z]:", stripped):
        return value[:3]
    return stripped or "/"


def allowed_url(url: str) -> bool:
    """요청해도 되는 주소 — https·복지포털 호스트·``/web/contents/`` 아래."""
    p = urlparse(url)
    return p.scheme == "https" and p.netloc == HOST and p.path.startswith("/web/contents/") and ".." not in p.path


def save_name(role: str, url: str) -> str:
    """저장 이름 — 역할 + 경로 이름 + URL 해시. 한글·대소문자만 다른 경로가 겹치지 않는다."""
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(urlparse(url).path).stem)[:40] or "root"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{SAVE_PREFIX}{role}-{stem}-{digest}.html"


class Collector:
    """HTML 판독과 스냅샷 기록 — 네트워크 없음."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.pages: list[dict] = []

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

    @staticmethod
    def is_site_page(html: str) -> bool:
        """복지포털 누리집이 그린 페이지인가 — 모든 페이지(로그인 셸 포함)가 GNB(``dep1a``)와 ``</html>`` 을 싣는다.

        아니면 WAF 차단 페이지("Page Not Found (wf)")·잘린 본문·오류 페이지다(2026-10-01 실측: robots.txt 자리가 그 모양).
        """
        tail = html.rstrip()[-200:].lower()
        return "</html>" in tail and 'class="dep1a"' in html

    # ---------- 페이지 저장 ----------

    def add_page(self, url: str, breadcrumb: str, html: str, kind: str, fetched_at: str | None = None) -> None:
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
            "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.pages.append(record)
        flag = " [로그인필요]" if auth else f" ({len(text)}자)"
        log(f"  + {record['title']}{flag}")

    # ---------- 목록 ----------

    @staticmethod
    def listing_ids(html: str, view_path: str) -> list[str]:
        """목록 HTML 에서 상세(view) id 를 순서대로(중복 제거)."""
        ids = []
        for m in re.finditer(
            re.escape(view_path) + r"\?schM=view[^\"'>]*?[?&]id=(\d+)|"
            + re.escape(view_path) + r"\?[^\"'>]*?schM=view[^\"'>]*?&(?:amp;)?id=(\d+)",
            html,
        ):
            pid = m.group(1) or m.group(2)
            if pid:
                ids.append(pid)
        return list(dict.fromkeys(ids))

    def save(self, source_counts: dict | None = None) -> dict:
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
            **(source_counts or {}),
        }
        (self.out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        log(f"저장 완료: {pages_path} ({meta['page_count']}페이지, "
            f"본문 {meta['content_page_count']}, 로그인영역 {meta['auth_required_count']})")
        return meta


# ---------------------------------------------------------------------------
# 회차 상태 — 계획한 호출 하나가 한 항목(저장 이름이 열쇠)
# ---------------------------------------------------------------------------

def _load_state(run_dir: Path) -> dict:
    p = run_dir / STATE
    if not p.is_file():
        raise CollectError("input", f"{STATE} 이 없습니다 — plan 을 먼저 실행하세요({run_dir})")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectError("input", f"{STATE} 을 읽을 수 없습니다: {exc}") from exc


def _write_state(run_dir: Path, state: dict) -> None:
    (run_dir / STATE).write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _add_item(state: dict, role: str, url: str, **meta) -> bool:
    """계획에 한 항목을 더한다. 이미 있거나(같은 URL) 허용 밖 주소면 False."""
    if not allowed_url(url):
        state.setdefault("skipped_urls", []).append(url)
        return False
    if url in state["seen"]:
        return False
    name = save_name(role, url)
    state["seen"][url] = name
    state["items"][name] = {"role": role, "url": url, "status": "pending", "attempts": 0, "bad": 0, **meta}
    return True


def _cycles(state: dict) -> int:
    """상한을 세는 바퀴 수 — 이 키가 없던 판의 상태 파일은 round 로 센다."""
    return int(state.get("cycles", state["round"]))


def _call(item_name: str, url: str) -> dict:
    return {"id": Path(item_name).stem, "tool": "http_request",
            "args": {"url": url, "timeout_sec": TIMEOUT_SEC, "save_as": item_name}}


def _write_plans(run_dir: Path, state: dict, names: list[str]) -> list[str]:
    """계획 파일을 CHUNK 개씩 쓴다 — 이름 plan-<바퀴>a.json, b.json …"""
    rnd = state["round"]
    files = []
    for i in range(0, len(names), CHUNK):
        chunk = names[i:i + CHUNK]
        fname = f"plan-{rnd:02d}{chr(ord('a') + i // CHUNK)}.json"
        # 회차 폴더는 이 스크립트 전용이라 덮어써도 안전하다 — 다시 받는 페이지(실패 자리·나쁜 본문)가 같은 이름으로 성립한다
        plan = {"calls": [_call(n, state["items"][n]["url"]) for n in chunk], "overwrite": True,
                "timeout_sec": BATCH_TIMEOUT_SEC}
        (run_dir / fname).write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        files.append(fname)
    return files


def _planned_out(run_dir: Path, state: dict, names: list[str], status: str, **extra) -> dict:
    files = _write_plans(run_dir, state, names)
    return {
        "status": status,
        "round": state["round"],
        "calls": len(names),
        "plan_files": files,
        "batch_args": [{"plan_file": f, "save_dir": state["save_dir"]} for f in files],
        "next": "batch_args 를 차례로(앞 batch 가 끝난 뒤 다음) batch 에 보내고, 끝나면 collect 를 다시 실행하세요",
        **extra,
    }


def cmd_plan(args) -> dict:
    save_dir = host_abs_path(args.save_dir)
    run_dir = Path(args.run_dir).expanduser()
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / STATE).exists():
        raise CollectError("args", f"이 회차 폴더에는 이미 {STATE} 가 있습니다 — collect 를 이어 가거나 새 회차 폴더를 만드세요", 2)
    state = {"schema": 1, "save_dir": save_dir, "round": 1, "cycles": 1, "limit": args.limit,
             "items": {}, "seen": {}, "listings": {}, "skipped_urls": []}
    _add_item(state, "p", ENTRY, kind="page", breadcrumb="복지포털 > 복지 한눈에 보기", entry=True)
    _write_state(run_dir, state)
    return _planned_out(run_dir, state, list(state["items"]), "planned",
                        estimate="진입 1 + 메뉴 약 38 + 목록 9 = 약 48호출(2026-10-01 기준, 8개씩 batch 약 7번). 받기 전에 사용자에게 알린다")


def _read_html(path: Path) -> tuple[str | None, str]:
    """(html | None, 사유). 사유: missing · hyve:<code> · bad:<설명>."""
    try:
        body = read_input(path)
    except HyveReadError:
        return None, "missing"
    except HyveFailure as exc:
        return None, f"hyve:{exc.code}"
    except HyveInputError as exc:
        return None, f"bad:{exc.kind}"
    try:
        html = body.data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "bad:encoding"
    if not Collector.is_site_page(html):
        return None, "bad:not_site_page"
    return html, ""


def cmd_collect(args) -> dict:
    run_dir = Path(args.run_dir).expanduser()
    state = _load_state(run_dir)
    col = Collector(Path(args.output_dir).expanduser() if args.output_dir else run_dir / "snapshot")

    progressed = False
    changed = False   # 이번 collect 가 무엇이라도 판정했는가(도착·나쁜 본문) — 아니면 batch 가 아직이다
    waiting = 0
    failures = {}
    for name, item in list(state["items"].items()):
        if item["status"] != "pending":
            continue
        html, why = _read_html(run_dir / name)
        if html is None:
            if why == "missing":
                # 아직 안 온 파일은 실패로 세지 않는다 — batch 가 끝나기 전에 collect 를 불러도 되살릴 수 없는 partial 이 되지 않게
                waiting += 1
                continue
            changed = True
            item["attempts"] += 1
            item["last_reason"] = why
            if item["attempts"] >= MAX_ATTEMPTS:
                item["status"] = "failed"
            continue
        changed = True
        progressed = True
        item["status"] = "done"
        mtime = datetime.fromtimestamp((run_dir / name).stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        item["fetched_at"] = mtime
        if item.get("entry"):
            try:
                menu = col.discover_menu(html)
            except RuntimeError as exc:
                raise CollectError("site", str(exc)) from exc
            state["menu_count"] = len(menu)
            for e in menu:
                _add_item(state, "p", e["url"], kind="page", breadcrumb=e["breadcrumb"])
            for lst in LISTINGS:
                _add_item(state, "l", lst["tmpl"].format(page=1), listing=lst["code"], page=1)
        elif item["role"] == "l":
            lst = next(x for x in LISTINGS if x["code"] == item["listing"])
            rec = state["listings"].setdefault(lst["code"], {"pages": 0, "ids": 0, "auth": False})
            rec["pages"] += 1
            if Collector.has_login_redirect(html):
                rec["auth"] = True  # 목록이 로그인 셸 — 따라갈 상세가 없다
                continue
            new = 0
            for pid in Collector.listing_ids(html, lst["view_path"]):
                if _add_item(state, "v", f"{BASE}{lst['view_path']}?schM=view&id={pid}",
                             kind=lst["kind"], breadcrumb=lst["breadcrumb"]):
                    new += 1
            rec["ids"] += new
            if item["page"] == 1 and not new:
                # 목록이 열렸는데(로그인 셸 아님) 1쪽에서 상세를 하나도 못 읽었다 — 구조 변경과 빈 게시판을 가를 수 없다
                state.setdefault("warnings", []).append(
                    f"{lst['breadcrumb']} 목록 1쪽에서 상세 id 를 못 읽었습니다(구조 변경 또는 빈 게시판) — 확인이 필요합니다")
            if new and item["page"] < MAX_LIST_PAGES:
                _add_item(state, "l", lst["tmpl"].format(page=item["page"] + 1), listing=lst["code"], page=item["page"] + 1)
            elif new and item["page"] >= MAX_LIST_PAGES:
                state.setdefault("warnings", []).append(f"{lst['breadcrumb']} 목록이 {MAX_LIST_PAGES}쪽을 넘습니다 — 그 뒤는 받지 않았습니다")

    # 스모크 상한 — 페이지(p·v) 수가 넘으면 더 계획하지 않는다
    limit = state.get("limit")
    if limit:
        pages = [n for n, it in state["items"].items() if it["role"] in ("p", "v")]
        for n in pages[limit:]:
            if state["items"][n]["status"] == "pending" and state["items"][n]["attempts"] == 0:
                state["items"][n]["status"] = "limited"

    pending = [n for n, it in state["items"].items() if it["status"] == "pending"]
    failed = {n: it for n, it in state["items"].items() if it["status"] == "failed"}
    for n, it in failed.items():
        failures[n] = {"url": it["url"], "reason": it.get("last_reason", "")}

    if pending:
        if changed:
            state["idle"] = 0
            # round 는 계획 파일 이름(plan-<round>a…)이라 판정이 있을 때마다 새로 오른다. 상한은 cycles 로 센다 —
            # batch 사이사이에 collect 를 불러 일부만 도착한 호출은 앞 계획이 아직 진행 중이라 세지 않는다(W13 재확인 b3)
            state["round"] += 1
            if not waiting:
                state["cycles"] = _cycles(state) + 1
            if _cycles(state) > MAX_ROUNDS:
                _write_state(run_dir, state)
                raise CollectError("partial", f"바퀴 상한({MAX_ROUNDS})을 넘었습니다 — 받지 못한 페이지 {len(pending)}개", 2)
        else:
            # 새로 온 파일이 하나도 없다 — 같은 계획을 다시 내되(바퀴를 올리지 않는다), 연달아 헛부르면 멈춘다
            state["idle"] = state.get("idle", 0) + 1
            if state["idle"] >= MAX_IDLE:
                _write_state(run_dir, state)
                raise CollectError(
                    "not_fetched",
                    f"collect 를 {state['idle']}번 연달아 불렀는데 새로 받은 파일이 없습니다 — batch 결과(ok·saved_path·save_dir)를 "
                    "확인하세요. 회차 상태는 그대로라 파일이 도착하면 collect 로 이어 갑니다")
        _write_state(run_dir, state)
        retry = [n for n in pending if state["items"][n]["attempts"] > 0]
        return _planned_out(run_dir, state, pending, "incomplete",
                            received=sum(1 for it in state["items"].values() if it["status"] == "done"),
                            retry=len(retry), waiting=waiting)
    state["idle"] = 0

    # 스냅샷 전에 받은 파일이 그대로 있는지 본다 — 회차 폴더는 사용자 폴더라 지워지거나 옮겨질 수 있다
    lost = []
    for name, item in state["items"].items():
        if item["role"] != "l" and item["status"] == "done" and _read_html(run_dir / name)[0] is None:
            item["status"] = "pending"
            item["last_reason"] = "lost"
            lost.append(name)
    if lost:
        state["round"] += 1
        state["cycles"] = _cycles(state) + 1
        if state["cycles"] > MAX_ROUNDS:
            _write_state(run_dir, state)
            raise CollectError("partial", f"바퀴 상한({MAX_ROUNDS})을 넘었습니다 — 사라진 페이지 {len(lost)}개", 2)
        _write_state(run_dir, state)
        return _planned_out(run_dir, state, lost, "incomplete",
                            received=sum(1 for it in state["items"].values() if it["status"] == "done"),
                            retry=0, lost=len(lost))
    _write_state(run_dir, state)
    if failures:
        raise CollectError(
            "partial",
            f"{len(failures)}개 페이지를 {MAX_ATTEMPTS}번 받지 못했습니다 — 스냅샷을 쓰지 않습니다(부분본 금지): "
            + json.dumps(failures, ensure_ascii=False)[:800], 2)
    if not progressed and not any(it["status"] == "done" for it in state["items"].values()):
        raise CollectError("input", "받은 페이지가 없습니다")

    # 전부 받았다 — 계획 순서(진입 → 메뉴 → 상세)대로 스냅샷을 쓴다
    for name, item in state["items"].items():
        if item["role"] == "l" or item["status"] != "done":
            continue
        html, _ = _read_html(run_dir / name)
        col.add_page(item["url"], item["breadcrumb"], html, item["kind"], fetched_at=item.get("fetched_at"))
    counts = {
        "menu_count": state.get("menu_count", 0),
        "listing_auth_count": sum(1 for r in state["listings"].values() if r["auth"]),
        "listing_ids": sum(r["ids"] for r in state["listings"].values()),
        "limited": sum(1 for it in state["items"].values() if it["status"] == "limited"),
    }
    meta = col.save(counts)
    # --limit 스모크는 전량이 아니다 — status 로 구분해 스킬 data/ 갱신에 쓰지 않게 한다
    return {"status": "smoke" if counts["limited"] else "ok", "output_dir": str(col.out_dir), "meta": meta,
            "warnings": state.get("warnings", []) + (
                [f"허용 밖 주소 {len(state['skipped_urls'])}개를 받지 않았습니다"] if state.get("skipped_urls") else []) + (
                [f"--limit 로 {counts['limited']}개 페이지를 받지 않았습니다(스모크)"] if counts["limited"] else [])}


def _reconfigure_stdio() -> None:
    """Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 UTF-8 로 바꾼다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="군인공제회 복지포털 스냅샷 재수집 (요청은 itda-hyve)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="회차 시작 — 진입 페이지 계획")
    p.add_argument("--run-dir", required=True, help="회차 폴더(이 스크립트가 보는 경로)")
    p.add_argument("--save-dir", required=True, help="같은 회차 폴더의 호스트 절대 경로(itda-hyve save_dir)")
    p.add_argument("--limit", type=int, default=None, help="최대 수집 페이지 수 (스모크용 — 스냅샷을 전량으로 쓰지 않는다)")
    c = sub.add_parser("collect", help="받은 파일 판독 → 다음 계획 또는 스냅샷 저장")
    c.add_argument("--run-dir", required=True)
    c.add_argument("--output-dir", default=None,
                   help="스냅샷 저장 경로 (기본: 회차 폴더/snapshot — 스킬 data/ 를 갱신하려면 그 경로를 준다)")
    return parser


def main(argv=None) -> int:
    _reconfigure_stdio()
    args = build_parser().parse_args(argv)
    try:
        out = cmd_plan(args) if args.cmd == "plan" else cmd_collect(args)
    except CollectError as exc:
        print(json.dumps({"status": "error" if exc.kind != "partial" else "partial", "error": exc.kind,
                          "detail": str(exc)}, ensure_ascii=False))
        return exc.code
    except OSError as exc:
        print(json.dumps({"status": "error", "error": "output", "detail": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
