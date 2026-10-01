# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: sources_crawl.py 의 목록 행 파서(page_*)·수집 루프(crawl)를 분모 기반 전량 대조로 다시 씀.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""목록 수집 — 쪽 판독·호출 계획·전량 대조 (네트워크 없음).

요청은 itda-hyve 가 보내고 ``save_as`` 로 회차 폴더 ``raw/list/`` 에 저장한다. 이 모듈은
저장된 쪽을 읽어 소스별로 **다 모았는지**를 판정하고, 모자라면 다음에 받을 쪽을 계획한다.

소스별 분모(2026-09-30 실측, ../references/sources.md):

  kstartup  모집중만 · 쪽당 15 · 1쪽의 "마지막페이지" 링크가 마지막 쪽 · 행 번호 없음
  bizinfo   모집중만 · 쪽당 15 · 행 번호 = 오래된 것부터 1, 1쪽 첫 행 번호 = 총건수
  nipa      이력 전체 · 쪽당 10 · 행 번호 = 오래된 것부터 1 · 모집중은 마감일로 가린다
  smtech    이력 전체 · 쪽당 15 · 행 번호 = 최신부터 1 · IRIS 행 섞임 · "모집중 0 인 쪽 3연속"에서 멈춤
  kocca     robots ``Disallow:/kocca/*/list.do`` — 목록을 받지 않는다(``inactive``)

저장 이름이 식별 계약이다: ``raw/list/<source>-p<NNN>[-r<k>].html``. ``-r<k>`` 는 같은 쪽을
다시 받은 것(받는 사이 목록이 밀렸거나 응답이 이상했을 때)이고 가장 큰 k 를 쓴다.
쪽 파일은 본문의 현재 쪽 표시와 이름의 쪽 번호가 같아야 한다.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import attach_download
from hyve_input import HyveFailure, HyveInputError, read_input
from kstartup_crawl import annotate as ks_annotate
from kstartup_crawl import parse_list as ks_parse_list
from plan_io import RESYNC_ID, PlanLog, http_call

ACTIVE_SOURCES = ("kstartup", "bizinfo", "nipa", "smtech")
ALL_SOURCES = (*ACTIVE_SOURCES, "kocca")
LIST_DIR = "raw/list"
MAX_RETAKE = 2          # 이상한 쪽을 다시 받는 횟수 상한 — 한 쪽의 나쁜 판이 3개면 그 쪽은 끝
MAX_PLANNED = 3         # 같은 저장 이름을 이만큼 **시도**했는데 파일이 없으면 받지 못한 것으로 확정한다(M1·N3)
MAX_RESYNC = 2          # 받는 사이 목록이 바뀌면 받은 쪽 전부를 한 회전에 다시 받는다 — 그 횟수 상한(N1)
ROUND_SLACK = 6         # 회전 상한 = 필요한 회전 + 이만큼. 넘으면 그때까지 받은 것으로 partial(N1)
SNAPSHOT = ("kstartup", "bizinfo", "nipa")  # 2회전에 1쪽을 다시 받아 나머지 쪽과 한 회전으로 맞추는 소스
SMTECH_CHUNK = 5        # SMTECH 한 번에 계획하는 쪽 수
CLOSED_STREAK = 3       # SMTECH: 모집중 0 인 쪽이 이만큼 이어지면 멈춘다(사용자 결정 D3)
DEFAULT_CAP = {"kstartup": 150, "bizinfo": 150, "nipa": 150, "smtech": 30}

# 2026-09-30 실측 쪽 수 — 받기 전에 사용자에게 알리는 예상치(분모는 받아 봐야 안다).
TYPICAL_PAGES = {"kstartup": 12, "bizinfo": 105, "nipa": 36, "smtech": 6, "kocca": 0}

URLS = {
    # 쿼리 순서는 사이트가 만드는 링크 그대로다(request-profile-first).
    "kstartup": "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?page={p}&schStr=&pbancEndYn=N",
    "bizinfo": "https://www.bizinfo.go.kr/sii/siia/selectSIIA200View.do?schEndAt=N&rows=15&cpage={p}",
    "nipa": "https://www.nipa.kr/home/2-2?curPage={p}",
    "smtech": "https://www.smtech.go.kr/front/ifg/no/notice02_list.do?pageIndex={p}",
}
ROWS = {"kstartup": 15, "bizinfo": 15, "nipa": 10, "smtech": 15}
HISTORY = {"nipa", "smtech"}  # 이력 전체를 넘기는 목록 — 마감 행은 싣지 않고 센다

KOCCA_INACTIVE_REASON = (
    "robots.txt 가 목록 경로를 막는다(Disallow:/kocca/*/list.do, 2026-09-30 확인) — 목록을 받지 않는다. "
    "KOCCA 공고는 https://www.kocca.kr/kocca/pims/list.do?menuNo=204104 를 브라우저로 직접 확인하고, "
    "상세 URL 을 가져오면 detail 로 받는다")

IRIS_URL = "https://www.iris.go.kr/"

_EMPTY = re.compile(r"(?:등록된|검색된|조회된)\s*(?:데이터|게시물|게시글|자료|내용|공고)(?:이|가)\s*없습니다")
_CURRENT = {
    "kstartup": re.compile(r'title="현재 페이지"[^>]*>\s*(\d+)'),
    "bizinfo": re.compile(r'class="page"\s+title="(\d+)페이지"'),
    "nipa": re.compile(r'<li class="active">\s*<span>\s*(\d+)\s*</span>'),
    "smtech": re.compile(r'id="pageIndex"[^>]*value="(\d+)"'),
}
_LAST = {
    "kstartup": re.compile(r'fn_egov_link_page\((\d+)\);[^"]*"\s*>\s*<span class="blind">마지막페이지'),
    "bizinfo": re.compile(r'cpage=(\d+)"\s+class="txt"\s+title="마지막페이지"'),
    "nipa": re.compile(r'curPage=(\d+)"\s+title="마지막 페이지"'),
    "smtech": re.compile(r'fn_search_test\((\d+)\);\s*return false;"\s*>\s*<img[^>]*alt="마지막페이지"'),
}
_NAME = re.compile(r"^(kstartup|bizinfo|nipa|smtech)-p(\d{3})(?:-r(\d+))?\.html$")


# ---------------------------------------------------------------------------
# 쪽 판독
# ---------------------------------------------------------------------------

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def norm_date(s: str) -> str:
    s = clean(s)
    m = re.search(r"(\d{4})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def split_period(s: str) -> tuple[str, str]:
    parts = re.split(r"~|∼|～", s or "")
    if len(parts) == 2:
        return norm_date(parts[0]), norm_date(parts[1])
    return "", norm_date(s)


def _tds(row: str) -> list[str]:
    return re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)


def _row_no(cells: list[str]) -> Optional[int]:
    if not cells:
        return None
    t = clean(cells[0]).replace(",", "")
    return int(t) if t.isdigit() else None


@dataclass
class Row:
    """목록 한 행. ``item`` 이 없으면 버린 행이고 ``drop`` 이 사유다."""
    no: Optional[int]
    item: Optional[dict[str, Any]]
    drop: Optional[str] = None
    open: bool = True


def rows_bizinfo(h: str) -> list[Row]:
    out = []
    for row in re.findall(r"<tr>[\s\S]*?</tr>", h):
        cells = _tds(row)
        no = _row_no(cells)
        m = re.search(r'href\s*=\s*"([^"]*pblancId=(PBLN_\d+)[^"]*)"[^>]*>\s*([\s\S]*?)</a>', row)
        if not m:
            if no is not None:
                out.append(Row(no, None, "no_link"))
            continue
        tds = [clean(c) for c in cells]
        start, end = split_period(tds[3]) if len(tds) > 3 else ("", "")
        out.append(Row(no, {
            "source": "bizinfo",
            "id": m.group(2),
            "title": clean(m.group(3)),
            "field": tds[1] if len(tds) > 1 else "",
            "org": " / ".join(x for x in tds[4:6] if x) if len(tds) > 5 else "",
            "apply_start": start,
            "apply_end": end,
            "reg_date": tds[6] if len(tds) > 6 else "",
            "url": f"https://www.bizinfo.go.kr/sii/siia/selectSIIA200Detail.do?pblancId={m.group(2)}",
        }))
    return out


def rows_nipa(h: str) -> list[Row]:
    out = []
    for row in re.findall(r"<tr>[\s\S]*?</tr>", h):
        cells = _tds(row)
        no = _row_no(cells)
        m = re.search(r'href="(/home/2-2/(\d+))"[^>]*>([\s\S]*?)</a>', row)
        if not m:
            if no is not None:
                out.append(Row(no, None, "no_link"))
            continue
        period = re.search(r"신청기간\s*:\s*([^<]+)", row)
        start, end = split_period(period.group(1)) if period else ("", "")
        prog = re.search(r'<span class="box[^"]*">([^<]+)</span>', row)
        reg = re.findall(r'<span class="bco">\s*(\d{4}-\d{2}-\d{2})\s*</span>', row)
        out.append(Row(no, {
            "source": "nipa",
            "id": m.group(2),
            "title": clean(re.sub(r"<!--[\s\S]*?-->", "", m.group(3))),
            "field": clean(prog.group(1)) if prog else "",
            "org": "NIPA",
            "apply_start": start,
            "apply_end": end,
            "reg_date": reg[-1] if reg else "",
            "url": f"https://www.nipa.kr{m.group(1)}",
        }))
    return out


def rows_smtech(h: str) -> list[Row]:
    """SMTECH 행. 식별자는 ``ancmId-dtlAncmSn`` — ``ancmId`` 하나로는 세부 공고가 겹친다
    (2026-09-30 실측: 1쪽에 S02847·S02871 이 각각 2행). IRIS 행(``goMove()`` — IRIS 로 이동)은
    상세 링크가 없어 제목·기간만 싣는다(사용자 결정 D3-㉠)."""
    out = []
    for row in re.findall(r"<tr>[\s\S]*?</tr>", h):
        cells = _tds(row)
        no = _row_no(cells)
        if no is None:
            continue
        tds = [clean(c) for c in cells]
        system = tds[1] if len(tds) > 1 else ""
        program = tds[2] if len(tds) > 2 else ""
        period = next((t for t in tds if "~" in t), "")
        start, end = split_period(period) if period else ("", "")
        reg = next((t for t in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t)), "")
        alt = re.search(r'<img[^>]*alt="(접수[^"]*|마감[^"]*)"', row)
        status = alt.group(1) if alt else ""
        a = re.search(r'<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>', row)
        title = clean(a.group(2)) if a else (tds[3] if len(tds) > 3 else "")
        base = {"source": "smtech", "title": title, "field": program, "system": system,
                "org": "SMTECH(중소기업기술정보진흥원)" if system != "IRIS" else "IRIS(범부처통합연구지원시스템)",
                "apply_start": start, "apply_end": end, "reg_date": reg, "recruit_status": status}
        if a and "notice02_detail.do" in a.group(1):
            href = htmllib.unescape(a.group(1))
            anc = re.search(r"ancmId=([A-Za-z0-9]+)", href)
            dtl = re.search(r"dtlAncmSn=(\d+)", href)
            if not anc:
                out.append(Row(no, None, "no_link"))
                continue
            path = re.sub(r";jsessionid=[^?]*", "", href)
            rid = f"{anc.group(1)}-{dtl.group(1) if dtl else '0'}"
            out.append(Row(no, {**base, "id": rid, "url": f"https://www.smtech.go.kr{path}"}))
        elif a and "goMove" in a.group(1):
            # IRIS 행은 식별자가 없다 — 같은 사업명·제목이 회차마다 되풀이되므로(2026-09-30 실측 3쌍)
            # 접수기간·공고일까지 넣어 가른다. 기간이 바뀌면 diff 에서 새 공고로 보인다.
            key = f"{program}|{title}|{start}|{end}|{reg}"
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
            out.append(Row(no, {**base, "id": f"iris-{digest}", "url": IRIS_URL, "detail": "iris"}))
        else:
            out.append(Row(no, None, "no_link"))
    return out


def rows_kstartup(h: str) -> list[Row]:
    return [Row(None, ks_annotate(it)) for it in ks_parse_list(h)]


ROW_PARSERS = {"kstartup": rows_kstartup, "bizinfo": rows_bizinfo, "nipa": rows_nipa, "smtech": rows_smtech}


def is_open(source: str, item: dict[str, Any], today: str) -> bool:
    """모집중 판정. 목록이 모집중만 주는 소스는 전부 참. 이력형은 상태 표시 → 마감일 순.
    마감일을 못 읽으면 모집중으로 둔다(보수적 — 빠뜨리는 쪽이 더 나쁘다)."""
    if source not in HISTORY:
        return True
    status = item.get("recruit_status") or ""
    if status.startswith("접수중") or status.startswith("접수예정"):
        return True
    if status.startswith(("접수완료", "마감")):
        return False
    end = item.get("apply_end") or ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
        return end >= today
    return True


@dataclass
class Page:
    source: str
    page: int
    retake: int
    path: Path
    kind: str = "ok"          # ok · empty · blocked · bad
    reason: str = ""
    rows: list[Row] = field(default_factory=list)
    current: Optional[int] = None
    last: Optional[int] = None
    round: Optional[int] = None       # 이 판을 받은 계획 회전(PlanLog.origin)
    plan: Optional[str] = None        # 이 판을 받은 계획 파일
    final: bool = False               # 받지 못함으로 확정(다시 계획하지 않는다)


def read_page(source: str, page: int, retake: int, path: Path) -> Page:
    """저장된 쪽 하나를 판독한다. 판정: ``blocked``(200 위장 차단) · ``bad``(hyve 실패·HTTP 오류·
    3xx 본문·구조 없음·쪽 번호 불일치) · ``empty``(마지막 쪽 너머) · ``ok``."""
    pg = Page(source, page, retake, path)
    try:
        body = read_input(path)
    except HyveFailure as exc:
        pg.kind, pg.reason = "bad", f"hyve:{exc.code}"
        return pg
    except HyveInputError as exc:
        pg.kind, pg.reason = "bad", f"{exc.kind}: {exc}"
        return pg
    h = body.data.decode("utf-8", errors="replace")
    if attach_download.looks_blocked(h):
        pg.kind, pg.reason = "blocked", "200 위장 차단(CAPTCHA/접근거부)"
        return pg
    pg.rows = ROW_PARSERS[source](h)
    cur = _CURRENT[source].search(h)
    pg.current = int(cur.group(1)) if cur else None
    last = _LAST[source].search(h)
    pg.last = int(last.group(1)) if last else None
    if not pg.rows:
        if _EMPTY.search(h):
            pg.kind = "empty"
        else:
            pg.kind, pg.reason = "bad", "목록 행도 '없습니다' 표시도 없다 — 리다이렉트·오류 본문이거나 사이트 개편"
        return pg
    if source in ("bizinfo", "nipa"):
        # 행 번호가 전량 대조의 근거다 — 번호 없는 행이 하나라도 있으면 대조 없이 넘길 수 없다(M5).
        unnumbered = sum(1 for r in pg.rows if r.item is not None and r.no is None)
        if unnumbered:
            pg.kind, pg.reason = "bad", f"행 번호를 읽지 못한 행 {unnumbered}개 — 분모 대조를 할 수 없다(사이트 개편 의심)"
            return pg
    if pg.current is None:
        pg.kind, pg.reason = "bad", "현재 쪽 표시가 없다 — 사이트 개편 의심"
    elif pg.current != page:
        pg.kind, pg.reason = "bad", f"이름은 {page}쪽인데 본문은 {pg.current}쪽이다"
    elif pg.last is None and page == 1:
        # 한 쪽뿐인 목록은 마지막 쪽 링크가 없을 수 있다 — 쪽당 행 수보다 적으면 1쪽이 끝이다.
        if len(pg.rows) < ROWS[source]:
            pg.last = 1
        else:
            pg.kind, pg.reason = "bad", "마지막 쪽 표시가 없다 — 분모를 읽을 수 없다(사이트 개편 의심)"
    return pg


def list_files(run_dir: Path) -> dict[str, dict[int, list[tuple[int, Path]]]]:
    """``raw/list`` 의 쪽 파일 → {소스: {쪽: [(retake, 경로)…]}}. 이름 규칙 밖 파일은 오류다."""
    out: dict[str, dict[int, list[tuple[int, Path]]]] = {}
    d = run_dir / LIST_DIR
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        if p.name.startswith("."):
            continue
        m = _NAME.match(p.name)
        if not m:
            raise ValueError(f"{LIST_DIR}/ 에 이름 규칙(<source>-p<NNN>[-r<k>].html) 밖 파일이 있다: {p.name}")
        src, page, retake = m.group(1), int(m.group(2)), int(m.group(3) or 1)
        out.setdefault(src, {}).setdefault(page, []).append((retake, p))
    for pages in out.values():
        for v in pages.values():
            v.sort()
    return out


def page_call(source: str, page: int, retake: int = 1, *, resync: bool = False) -> dict[str, Any]:
    """쪽 호출 한 칸. 재동기화 회전의 호출은 id 에 ``resync-`` 표식을 단다 — 그 횟수를 계획 이력에서 센다(P6)."""
    suffix = f"-r{retake}" if retake > 1 else ""
    name = f"{source}-p{page:03d}{suffix}"
    return http_call(f"{RESYNC_ID if resync else ''}list-{name}", URLS[source].format(p=page), f"{LIST_DIR}/{name}.html")


# ---------------------------------------------------------------------------
# 소스별 판정
# ---------------------------------------------------------------------------

@dataclass
class SourceResult:
    source: str
    status: str                       # ok · partial · manual · inactive · incomplete
    records: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    coverage: str = "exhaustive"      # exhaustive · window
    pages_fetched: int = 0
    last_page: Optional[int] = None
    reported_total: Optional[int] = None
    duplicates: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    need_pages: Optional[int] = None
    will_truncate: bool = False
    counted: dict[str, int] = field(default_factory=dict)   # 정상 계수 — 마감 행·IRIS 행

    def drop(self, key: str, n: int = 1) -> None:
        """결손 계수(링크·구조를 못 읽은 행). 0 이 아니면 그 소스는 partial 이다."""
        if n:
            self.dropped[key] = self.dropped.get(key, 0) + n

    def count(self, key: str, n: int = 1) -> None:
        if n:
            self.counted[key] = self.counted.get(key, 0) + n


def _missing_pages(source: str, log: PlanLog, have: dict[int, set[int]]) -> dict[int, Page]:
    """``MAX_PLANNED`` 번 시도했는데 파일이 끝내 없는 저장 이름 → 받지 못한 판(``bad``·``final``).

    itda-hyve 는 실패한 호출의 파일을 쓰지 않는다. SKILL 이 그 자리에 ``{"error"}`` 를 쓰게 하지만 그 쓰기가
    빠지거나 다른 경로에 떨어지면 스크립트는 "아직 안 받음" 으로 보고 같은 계획을 끝없이 다시 낸다(M1).
    """
    out: dict[int, Page] = {}
    for rnd, names in log.rounds(f"{LIST_DIR}/{source}-p").items():
        for save_as in names:
            m = _NAME.match(save_as[len(LIST_DIR) + 1:])
            if not m:
                continue
            p, k = int(m.group(2)), int(m.group(3) or 1)
            n = log.count(save_as)
            if n < MAX_PLANNED or k in have.get(p, set()):
                continue  # 아직 덜 시도했거나, 그 이름의 파일이 왔다
            if p not in out or k > out[p].retake:
                out[p] = Page(source, p, k, Path(save_as), kind="bad", final=True,
                              reason=f"hyve:missing — {save_as} 를 {n}번 시도했는데 파일이 없다(받지 못함)")
    return out


def _resyncs(source: str, log: PlanLog) -> int:
    """받은 쪽 전부를 다시 받은 회전 수 — 재동기화 표식이 든 **시도된** 회전만 센다(3차 리뷰 P6).
    이름 모양(1쪽·2쪽이 둘 다 -r)으로 추정하면 괄호 회전에 2쪽 다시 받기가 섞인 것도 세어진다."""
    return log.resync_rounds(f"{LIST_DIR}/{source}-p")


def _p1_planned(source: str, log: PlanLog) -> dict[int, list[int]]:
    """회전 → 그 회전에 계획한 1쪽 판 번호(k) 목록."""
    out: dict[int, list[int]] = {}
    for rnd, names in log.rounds(f"{LIST_DIR}/{source}-p001").items():
        for n in names:
            m = _NAME.match(n[len(LIST_DIR) + 1:])
            if m:
                out.setdefault(rnd, []).append(int(m.group(3) or 1))
    return out


def _round_limit(source: str, last: Optional[int], cap: int) -> int:
    if last is None:
        base = 1
    elif source == "smtech":
        base = 1 + math.ceil(max(0, min(last, cap) - 1) / SMTECH_CHUNK)
    else:
        base = 2 if last > 1 else 1
    return base + ROUND_SLACK


def collect_source(source: str, files: dict[int, list[tuple[int, Path]]], *, today: str,
                   cap: int, smoke: bool, log: Optional[PlanLog] = None) -> SourceResult:
    """한 소스의 저장된 쪽을 판정한다. 모자라면 ``status=incomplete`` 와 다음 호출(``calls``).

    다시 받기 규칙(재리뷰 N1·N2):
      - 이상한 쪽(``bad``)은 그 쪽만 다시 받는다(쪽마다 나쁜 판 3개까지). kstartup 은 행 번호가 없어 혼자 늦게 받은
        쪽이 받는 사이의 변화를 숨기므로, 2회전 뒤에는 **받은 쪽 전부**를 한 회전에 다시 받는다.
      - 받는 사이 목록이 바뀐 흔적(빈 번호·중복·모자란 쪽)이 보이면 쪽을 골라 받지 않고 **받은 쪽 전부**를 한 회전에
        다시 받는다(``MAX_RESYNC`` 번). 쪽을 골라 받으면 새 판과 옛 판의 경계가 회전마다 한 쪽씩 옮겨 회전이 수십 번 든다.
      - 이 소스의 계획 회전이 ``_round_limit`` 에 닿으면 더 계획하지 않고 그때까지 받은 것으로 partial.

    ``log`` 는 회차 폴더의 계획 이력(``plan_io.PlanLog``) — 없는 파일의 시도 횟수·파일이 온 회전을 준다."""
    log = log or PlanLog([])
    res = SourceResult(source, "incomplete")
    versions: dict[int, list[Page]] = {}
    have: dict[int, set[int]] = {}
    for p, lst in files.items():
        for k, path in lst:
            pg = read_page(source, p, k, path)
            pg.round, pg.plan = log.origin(f"{LIST_DIR}/{path.name}")
            versions.setdefault(p, []).append(pg)
            have.setdefault(p, set()).add(k)
    res.pages_fetched = len(files)
    for p, pg in _missing_pages(source, log, have).items():
        if not versions.get(p) or pg.retake > versions[p][-1].retake:
            versions.setdefault(p, []).append(pg)
    # 1쪽 다시 받기가 빈 쪽이면(앞 판에는 행이 있었다) 목록이 비었다기보다 이상한 응답이다
    for pg in versions.get(1, [])[1:]:
        if pg.kind == "empty" and any(v.kind == "ok" for v in versions[1] if v.retake < pg.retake):
            pg.kind, pg.reason = "bad", "1쪽 다시 받기가 빈 쪽이다(앞 판에는 행이 있었다)"
    pages = {p: v[-1] for p, v in versions.items()}
    attempts = {p: v[-1].retake for p, v in versions.items()}
    nbad = {p: sum(1 for x in v if x.kind == "bad") for p, v in versions.items()}
    rounds_used = len(log.rounds(f"{LIST_DIR}/{source}-p"))

    def retryable(p: int) -> bool:
        return pages[p].kind == "bad" and not pages[p].final and nbad[p] <= MAX_RETAKE

    def call(p: int, resync: bool = False) -> dict[str, Any]:
        return page_call(source, p, attempts.get(p, 0) + 1, resync=resync)

    blocked = [pg for pg in pages.values() if pg.kind == "blocked"]
    if blocked:
        pg = blocked[0]
        res.status, res.stop_reason, res.coverage = "manual", "blocked", "none"
        res.errors.append(f"p{pg.page}: {pg.reason} — 우회하지 않고 수동 확인")
        res.records = _records(source, pages, today, res)
        return res

    capped = False

    def plan_or_cap(calls: list[dict[str, Any]], last: Optional[int]) -> bool:
        """계획을 싣는다(True). 회전 상한이면 싣지 않고 capped 를 세운다(False)."""
        nonlocal capped
        if not calls:
            return False
        if rounds_used >= _round_limit(source, last, cap):
            capped = True
            return False
        res.calls.extend(calls)
        return True

    if 1 not in pages:
        if plan_or_cap([page_call(source, 1)], None):
            return res
        return _finish_unreadable(res, "fetch-failure", f"p1: 회전 상한 {_round_limit(source, None, cap)}에 닿도록 1쪽을 받지 못했다")

    # 1쪽 괄호 — SNAPSHOT 소스는 회전 앞뒤로 1쪽을 받는다(``_bracket``). 뒤 1쪽이 실패했으면 같은 회전의 앞 1쪽을 쓴다.
    same1 = _same_round(versions[1])
    if pages[1].kind == "bad" and len(same1) > 1 and any(v.kind == "ok" for v in same1):
        pages[1] = [v for v in same1 if v.kind == "ok"][-1]  # 끝 확인은 뒤의 1쪽 창 대조가 한 호출로 채운다(P2)
    p1 = pages[1]
    fallback = ""
    if p1.kind == "bad" and retryable(1):
        if plan_or_cap([call(1)], None):
            return res  # 분모를 모른다 — 1쪽부터
    if p1.kind == "bad":
        earlier = [v for v in versions[1] if v.kind == "ok"]
        if earlier and len(pages) > 1:
            # 2회전의 1쪽 다시 받기만 실패했다 — 1회전 1쪽으로 분모를 잡고 나머지와 함께 싣되 partial(N4)
            fallback = p1.reason
            p1 = pages[1] = earlier[-1]
        else:
            return _finish_unreadable(res, "fetch-failure" if p1.reason.startswith("hyve:") else "parse-failure",
                                      f"p1: {p1.reason}")
    if p1.kind == "empty":
        # 모집중이 수백 건인 소스에서 1쪽 0건은 점검·필터 뜻 변경·오류 화면일 가능성이 훨씬 크다(M3) —
        # 성공으로 적지 않는다. 정말 0건인 날은 사람이 사이트를 보고 확인한다.
        res.last_page = 0
        return _finish_unreadable(res, "empty", "p1: '없습니다' 표시 — 1쪽이 0건이다. 점검·조회 조건 변경·오류 화면을 "
                                  "의심하고 사이트에서 직접 확인한다(0건을 성공으로 적지 않는다)")

    last = p1.last or 1
    res.last_page = last
    if source in ("bizinfo", "nipa"):
        res.reported_total = max((r.no for r in p1.rows if r.no is not None), default=None)

    if smoke:
        res.status, res.stop_reason, res.coverage = "ok", "smoke", "window"
        res.records = _records(source, {1: p1}, today, res)
        return res

    # 받을 쪽 — 분모가 정한다. SMTECH 는 모집중이 끊길 때까지 5쪽씩.
    upto = min(last, cap)
    if last > cap and source != "smtech":
        # SMTECH 는 모집중이 끊기면 멈추므로 마지막 쪽(이력 전체)이 상한을 넘어도 잘림 예고가 아니다.
        res.need_pages, res.will_truncate = last, True
    if source == "smtech":
        prefix = _contiguous(pages)
        streak = _closed_streak(source, pages, prefix, today)
        if streak >= CLOSED_STREAK or prefix >= upto:
            upto = prefix
        else:
            upto = min(prefix + SMTECH_CHUNK, min(last, cap))
    missing = [p for p in range(1, upto + 1) if p not in pages]
    retry = [p for p in sorted(pages) if p > 1 and p <= max(upto, 1) and retryable(p)]
    resyncs = _resyncs(source, log)
    filled = any(p > 1 and p in pages for p in range(2, upto + 1))

    def bracket(body: list[dict[str, Any]], resync: bool = False) -> list[dict[str, Any]]:
        """1쪽을 회전 앞과 끝에 둔다(SNAPSHOT). 계획 파일이 나뉘면 앞 1쪽은 첫 파일, 끝 1쪽은 마지막 파일에 들어가
        파일 사이에서는 그 회전을 감싼다 — 한 파일 안의 호출 순서는 batch 가 보장하지 않는다(동시 8칸, 3차 리뷰 P2).
        앞뒤 1쪽이 다르면 그 회전 동안 목록이 바뀐 것이다. 맨 위 추가 + 경계 부근 제거가 겹치면 행 번호가
        빈틈없이 맞아 한 건이 조용히 빠지는데(시뮬레이터 실측 — nipa 2회전 파일 a·b 사이), 그것을 이 비교가 잡는다."""
        k = attempts.get(1, 0)
        rest = [c for c in body if not c["args"]["save_as"].startswith(f"{LIST_DIR}/{source}-p001")]
        return ([page_call(source, 1, k + 1, resync=resync)] + rest
                + [page_call(source, 1, k + 2, resync=resync)])

    def resync_calls() -> list[dict[str, Any]]:
        """받은 쪽 전부(분모까지)를 한 회전에 다시 — 받지 못함으로 확정된 쪽·나쁜 판이 다 찬 쪽은 뺀다."""
        out = [call(p, resync=True) for p in range(1, upto + 1)
               if not (p in pages and (pages[p].final or nbad[p] > MAX_RETAKE))]
        return bracket(out, resync=True) if source in SNAPSHOT and upto > 1 else out

    calls = [call(p) for p in retry] + [page_call(source, p) for p in missing]
    if source in SNAPSHOT and missing and last > 1 and not fallback and not pages[1].final:
        # 1쪽을 나머지 쪽과 같은 회전에 다시 받는다 — 1회전과 2회전 사이에 공고가 **내려가면** 중복도
        # 모자란 쪽도 생기지 않아 한 건이 조용히 빠진다(M6). 같은 회전의 1쪽으로 분모·번호를 다시 잡는다(m1).
        calls = bracket(calls)
    elif (source in SNAPSHOT and not calls and last > 1 and not fallback and len(versions[1]) == 1
          and not pages[1].final):
        # 나머지 쪽만 오고 1쪽 다시 받기가 계획된 적이 없다 — 1회전 1쪽으로 대조하지 않는다
        calls = [call(1)]
    if source == "kstartup" and filled and calls:
        # 행 번호가 없다 — 2회전 뒤에 쪽을 혼자 늦게 받으면 받는 사이의 변화(1쪽 추가·마지막 쪽 쪽 제거)가 숨는다
        # (재리뷰 N2). 어떤 쪽이든 다시 받게 되면 전 쪽을 한 회전에. 그 횟수를 다 썼으면 받지 못한 쪽만 채운다.
        # 다 썼으면 이상한 쪽은 그 쪽만 다시 받는다(3차 리뷰 P4) — 쪽마다 나쁜 판 3개까지는 kstartup 도 같다.
        # 쪽들이 여러 회전에 걸치므로 뒤의 1쪽 창 대조가 받는 사이의 변화를 본다.
        calls = (resync_calls() if resyncs < MAX_RESYNC
                 else [call(p) for p in retry] + [page_call(source, p) for p in missing])
    if plan_or_cap(calls, last):
        return res

    use = {p: pg for p, pg in pages.items() if source != "smtech" or p <= upto}
    failed = [p for p in sorted(use) if use[p].kind == "bad"]
    for p in failed:
        why = use[p].reason
        res.errors.append(f"p{p}: {why}" + (" (다시 받아도 같다)" if nbad.get(p, 0) >= 2 and not why.startswith("hyve:missing") else ""))
    for p in missing:
        res.errors.append(f"p{p}: 받지 못했다" + ("(회전 상한)" if capped else ""))
    if fallback:
        res.errors.append(f"p1: 1쪽을 같은 회전에 다시 받지 못해({fallback}) 받는 사이의 변화를 대조하지 못했다 — "
                          "1회전 1쪽으로 분모를 잡았다")

    # 전량 대조 — 받는 사이 목록이 밀렸으면 받은 쪽 전부를 한 회전에 다시 받는다(N1).
    # 받지 못한 쪽이 있으면 빈 번호·모자란 쪽은 그 탓이다 — 다시 받아도 채워지지 않으니 밀림으로 보지 않는다
    drift = _drift(source, use, res) if not (capped or failed or missing) else []
    rounds_seen = {pg.round for pg in use.values() if pg.kind == "ok" and pg.round is not None}
    window_drift, need_check = False, False
    if source in SNAPSHOT and last > 1 and not (fallback or capped or failed or missing or drift):
        window_drift, need_check = _p1_window(source, use, versions[1], log)
    if window_drift:
        drift = [1]
        res.warnings.append(f"{source}: 쪽들을 받는 사이에 1쪽이 바뀌었다(1쪽 판 대조) — 받은 쪽 전부를 다시 받는다")
    # kstartup 은 행 번호가 없어 쪽들이 한 회전에 모이지 않으면 그 사이의 제거를 볼 수 없다(N2) — 1쪽 판 대조는
    # 1쪽 밖의 제거를 못 보므로 재동기화할 수 있는 동안은 무조건 한 회전으로 모은다(3차 리뷰 P3 판단)
    mismatch = (not drift and not capped and not fallback and source == "kstartup" and len(rounds_seen) > 1)
    if (drift or mismatch) and resyncs < MAX_RESYNC and plan_or_cap(resync_calls(), last):
        if mismatch:
            res.warnings.append("kstartup: 쪽들을 한 회전에 받지 못했다 — 전 쪽을 한 회전에 다시 받는다")
        return res
    if need_check and not drift and not capped:
        # 쓴 쪽들을 받은 뒤의 1쪽이 없다(괄호 한쪽 실패·쪽을 늦게 따로 받음) — 1쪽 한 호출만 더 받아 앞 판과 대조한다(P2)
        if not pages[1].final and nbad[1] <= MAX_RETAKE and plan_or_cap([call(1)], last):
            return res
        res.warnings.append(f"{source}: 쪽들을 받은 뒤의 1쪽 확인을 받지 못했다 — 받는 사이 맨 위 추가를 1쪽 판으로 "
                            "대조하지 못했다(행 번호 대조는 했다)")
    if mismatch and not capped and not drift:
        res.warnings.append("kstartup: 쪽들을 한 회전에 받지 못했으나 그 사이 1쪽 판들이 같다 — 변화 없음으로 봤다"
                            "(1쪽 밖의 제거는 대조하지 못했다)")
    if drift:
        res.errors.append(f"받는 사이 목록이 바뀌어 다시 받아도 맞지 않는다({len(drift)}개 쪽): "
                          + ", ".join(f"p{p}" for p in drift[:10]))
    if capped:
        res.errors.append(f"회전 상한 {_round_limit(source, last, cap)} — 그때까지 받은 것으로 끝냈다")

    res.records = _records(source, use, today, res)
    if res.dropped:
        res.errors.append(f"{source}: 읽지 못한 행 {sum(res.dropped.values())}개({', '.join(sorted(res.dropped))}) — "
                          "링크·구조를 못 읽은 행은 공고가 빠진 것이다(사이트 개편 의심)")
    first = versions[1][0]
    if source in SNAPSHOT and not fallback and first.kind == "ok" and first is not pages[1]:
        before = [r.item["id"] for r in first.rows if r.item]
        after = [r.item["id"] for r in pages[1].rows if r.item]
        if before != after:
            plans = {pg.plan for pg in use.values() if pg.kind == "ok"}
            where = ("같은 계획 파일로 받은 쪽들로 대조했다" if len(plans) == 1 and None not in plans
                     else "마지막으로 받은 판들로 대조했다")
            res.warnings.append(f"{source}: 1회전 뒤 1쪽이 바뀌었다 — {where}")
    if source == "smtech":
        _check_deadline_order(use, res)
    if source == "smtech" and upto < min(last, cap) and not capped:
        res.stop_reason, res.coverage = "closed-streak", "window"
        res.warnings.append(f"smtech: 모집중 0 인 쪽 {CLOSED_STREAK}개 연속에서 멈췄다 — {upto}/{last}쪽까지 "
                            "(이력형 목록의 최근 구간 — 오래 열린 공고가 더 뒤에 있을 수 있다)")
    elif capped:
        # 회전 상한이 먼저다 — SMTECH 는 마지막 쪽(이력 전체)이 늘 쪽 상한을 넘어 page-cap 으로 가려졌다(P5)
        res.stop_reason, res.coverage = "round-cap", "window"
    elif last > cap:
        res.stop_reason, res.coverage = "page-cap", "window"
        res.errors.append(f"쪽 상한 {cap} — 전체 {last}쪽 중 {cap}쪽만 받았다")
    else:
        res.stop_reason = "last-page"
    res.status = "partial" if res.errors else "ok"
    return res


def _p1_window(source: str, use: dict[int, Page], v1: list[Page], log: PlanLog) -> tuple[bool, bool]:
    """1쪽 창 대조(3차 리뷰 P2·P3) → (1쪽이 바뀌었다, 끝 확인이 없다).

    쓴 쪽들(2쪽 이상)이 받힌 회전의 범위 [a, b] 를 감싸는 1쪽 판들 — a 회전의 앞 1쪽(없으면 그 전 회전의 마지막 1쪽)부터
    b 회전 뒤의 1쪽까지 — 의 id 목록이 모두 같아야 한다. 쪽들이 여러 회전에 걸쳐도(쪽 하나를 늦게 따로 받음) 그 사이의
    "맨 위 추가 + 상쇄하는 제거" 가 여기서 보인다. b 회전의 끝 1쪽도 그 뒤의 1쪽도 없으면 끝 확인이 없다."""
    rounds = {pg.round for p, pg in use.items() if p > 1 and pg.kind == "ok" and pg.round is not None}
    oks = [v for v in v1 if v.kind == "ok" and v.round is not None]
    if not rounds or not oks:
        return False, False
    a, b = min(rounds), max(rounds)
    planned = _p1_planned(source, log)
    head = min(planned[a]) if planned.get(a) else None
    if head is not None and any(v.round == a and v.retake == head for v in oks):
        start = a
    else:
        start = max((v.round for v in oks if v.round < a), default=a)
    window = [v for v in oks if v.round >= start]
    tail = planned.get(b, [])
    end_ok = (any(v.round > b for v in oks)
              or (len(tail) >= 2 and any(v.round == b and v.retake == max(tail) for v in oks)))
    changed = len({tuple(_ids(v)) for v in window}) > 1
    return changed, (not changed and not end_ok)


def _ids(pg: Page) -> list[str]:
    return [r.item["id"] for r in pg.rows if r.item]


def _same_round(vs: list[Page]) -> list[Page]:
    """마지막 판과 같은 회전에 받은 판들(받은 순). 회전을 모르면 빈 목록."""
    rnd = vs[-1].round if vs else None
    return [v for v in vs if rnd is not None and v.round == rnd]


def _finish_unreadable(res: SourceResult, stop_reason: str, error: str) -> SourceResult:
    """1쪽을 못 받았거나 못 읽었거나 0건 — 분모가 없다. partial·coverage none(N5)."""
    res.calls = []
    res.status, res.stop_reason, res.coverage = "partial", stop_reason, "none"
    res.errors.append(error)
    return res


def _contiguous(pages: dict[int, Page]) -> int:
    n = 0
    while (n + 1) in pages:
        n += 1
    return n


def _closed_streak(source: str, pages: dict[int, Page], prefix: int, today: str) -> int:
    """받은 앞 구간 끝에서 모집중 행이 0 인 쪽이 몇 개 이어지는가. 이상한 쪽은 끊는다."""
    streak = 0
    for p in range(prefix, 0, -1):
        pg = pages[p]
        if pg.kind != "ok":
            break
        if any(r.item and is_open(source, r.item, today) for r in pg.rows):
            break
        streak += 1
    return streak


def _drift(source: str, pages: dict[int, Page], res: SourceResult) -> list[int]:
    """전량 대조. 어긋난 쪽 번호(다시 받을 쪽) 목록을 돌려주고, 계수는 ``res`` 에 싣는다."""
    ok = {p: pg for p, pg in pages.items() if pg.kind in ("ok", "empty")}
    ids: dict[str, int] = {}
    dup_pages: set[int] = set()
    for p in sorted(ok):
        for r in ok[p].rows:
            if r.item is None:
                continue
            if r.item["id"] in ids:
                res.duplicates += 1
                dup_pages.update({p, ids[r.item["id"]]})
            else:
                ids[r.item["id"]] = p
    rows = ROWS[source]
    if source in ("bizinfo", "nipa"):
        # 행 번호는 오래된 것부터 1 — 새 공고가 위에 붙어도 기존 번호는 그대로다. 1..최대 번호가 빠짐없이
        # 한 번씩 있어야 한다. 빠진 번호는 지금 기준으로 그 번호가 있을 쪽을 다시 받는다.
        seen: dict[int, str] = {}
        clash: set[int] = set()
        top = 0
        for p, pg in ok.items():
            for r in pg.rows:
                if r.no is None:
                    continue
                top = max(top, r.no)
                key = r.item["id"] if r.item else f"drop:{r.no}"
                if r.no in seen and seen[r.no] != key:
                    clash.add(p)
                seen.setdefault(r.no, key)
        # 쪽 상한으로 잘랐으면 받은 쪽이 덮는 번호(최대 번호부터 아래로)만 대조한다.
        low = 1
        if res.last_page and res.last_page > max(ok):
            low = max(1, top - rows * max(ok) + 1)
        missing = [n for n in range(low, top + 1) if n not in seen]
        want = {min(max(1, math.ceil((top - n + 1) / rows)), max(ok) + 1) for n in missing}
        if missing:
            res.warnings.append(f"{source}: 행 번호 {len(missing)}개가 비었다(받는 사이 목록이 바뀜) — 받은 쪽 전부를 다시 받는다")
        return sorted(want | clash | dup_pages)
    if source == "kstartup":
        last = res.last_page or 1
        short = [p for p in range(1, last) if p in ok and len([r for r in ok[p].rows if r.item]) < rows]
        if dup_pages or short:
            res.warnings.append("kstartup: 쪽 사이 중복·모자란 쪽 — 받는 사이 목록이 바뀜, 전 쪽을 한 회전에 다시 받는다")
            return list(range(1, last + 1))
        return []
    # smtech — 행 번호가 최신부터 1 이라 쪽 p 는 15(p-1)+1..15p 여야 한다. 마지막 쪽이 아니면 정확히 15행(M4) —
    # 번호가 위치 번호라 범위만 보면 행이 빠진 짧은 쪽도 통과한다.
    last = res.last_page or 1
    wrong = []
    for p, pg in ok.items():
        nos = [r.no for r in pg.rows if r.no is not None]
        n = rows if p < last else len(nos)
        if nos != list(range(rows * (p - 1) + 1, rows * (p - 1) + 1 + n)):
            wrong.append(p)
    if wrong:
        res.warnings.append("smtech: 행 번호가 쪽 위치와 맞지 않거나 행이 모자란 쪽 — 받은 쪽 전부를 다시 받는다: "
                            + ", ".join(f"p{p}" for p in sorted(wrong)[:10]))
    return sorted(set(wrong) | dup_pages)


def _check_deadline_order(pages: dict[int, Page], res: SourceResult) -> None:
    """SMTECH 목록은 마감일 내림차순이다(2026-09-30 실측 1~7쪽 105행 위반 0). 그래야 모집중이 앞쪽에 모여
    closed-streak 멈춤이 공고를 빠뜨리지 않는다. 이 정렬은 사이트가 약속한 계약이 아니므로 받은 구간에서
    깨지면 경고한다 — 멈춘 뒤쪽에 모집중이 남아 있을 수 있다."""
    prev: Optional[str] = None
    broken: list[str] = []
    for p in sorted(pages):
        if pages[p].kind != "ok":
            continue
        for r in pages[p].rows:
            end = (r.item or {}).get("apply_end") or ""
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
                continue
            if prev is not None and end > prev:
                broken.append(f"p{p} #{r.no}")
            prev = end
    if broken:
        res.warnings.append(f"smtech: 마감일 내림차순이 {len(broken)}곳에서 깨졌다({', '.join(broken[:5])}) — "
                            "closed-streak 멈춤의 전제가 흔들린다. 멈춘 뒤쪽에 모집중 공고가 있을 수 있다")


def _records(source: str, pages: dict[int, Page], today: str, res: SourceResult) -> list[dict[str, Any]]:
    """쪽들의 행을 레코드로 — 버린 행은 사유별로 센다(collection-completeness ③).

    ``dropped``(결손 — 링크·구조를 못 읽은 행)와 ``counted``(정상 — 마감 행·IRIS 행)를 가른다(M4)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(pages):
        if pages[p].kind not in ("ok", "empty"):
            continue
        for r in pages[p].rows:
            if r.item is None:
                res.drop(r.drop or "parse_skip")
                continue
            if not is_open(source, r.item, today):
                res.count("closed_rows")
                continue
            if r.item["id"] in out:
                continue
            if r.item.get("detail") == "iris":
                res.count("iris_rows")  # 버린 것이 아니라 링크 없이 실은 행 — 보고서가 따로 적도록 센다
            out[r.item["id"]] = r.item
    return list(out.values())
