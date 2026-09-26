"""HTTP client + HTML parser for airport.kr 항공사별 통계 페이지.

stdlib only — urllib + http.cookiejar + html.parser.

2-step workflow (라이브 검증으로 확정):
  Step 1: GET /co_ko/651/subview.do  → WMONID 쿠키 시드
  Step 2: GET /fsmFsn/co_ko/statisticCategoryOfAirline.do?... → 데이터 페이지

WMONID 쿠키 없이 Step 2 호출 시 HTTP 302 무한 리다이렉트 (SPEC §8 라이브 검증).
"""

from __future__ import annotations

import http.cookiejar
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

BASE_URL = "https://www.airport.kr"
NAV_PATH = "/co_ko/651/subview.do"
STATS_PATH = "/fsmFsn/co_ko/statisticCategoryOfAirline.do"
LAYOUT_TOKEN = "636f5f6b6f40403635314040666e637431"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "ko-KR,ko;q=0.9,en;q=0.8"

DISCLAIMER = (
    "본 데이터는 인천국제공항공사(airport.kr) 공개 웹페이지를 직접 스크래핑한 결과이며, "
    "통계는 인천공항공사 공식 통계 자료실의 원본을 우선으로 참조하시기 바랍니다."
)

DEFAULT_TIMEOUT = 10.0


class SessionSeedError(RuntimeError):
    """Raised when the navigation seed step fails."""


class FetchError(RuntimeError):
    """Raised when the data fetch step fails."""


class AirportSession:
    """2-step HTTP session with cookie jar persistence."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self.timeout = timeout
        self.cookies: http.cookiejar.CookieJar = http.cookiejar.CookieJar()
        if opener is None:
            self.opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.cookies),
                urllib.request.HTTPRedirectHandler(),
            )
        else:
            self.opener = opener
        self._seeded = False

    def _headers(self, referer: str) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept-Language": ACCEPT_LANGUAGE,
            "Referer": referer,
        }

    def seed_session(self) -> None:
        """Step 1: GET navigation page to receive WMONID session cookie."""
        url = BASE_URL + NAV_PATH
        req = urllib.request.Request(url, headers=self._headers("https://www.google.com/"))
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", resp.getcode())
                if status != 200:
                    raise SessionSeedError(
                        f"Navigation page returned HTTP {status}"
                    )
                resp.read()  # drain body
        except (SessionSeedError, Exception) as e:  # noqa: BLE001
            if isinstance(e, SessionSeedError):
                raise
            raise SessionSeedError(f"Navigation seed failed: {e}") from e
        self._seeded = True

    def fetch_airline_stats(
        self,
        year: int,
        month: int,
        *,
        route: str = "",
        arpln: str = "",
        terminal: str = "",
        nvg: str = "",
        airline: str = "",
    ) -> str:
        """Step 2: GET airline statistics page with filters. Returns raw HTML."""
        if not self._seeded:
            self.seed_session()
        params = {
            "layout": LAYOUT_TOKEN,
            "stYear": str(year),
            "stMonth": f"{month:02d}",
            "edYear": str(year),
            "edMonth": f"{month:02d}",
            "routeSe": route,
            "arplnSe": arpln,
            "nvgSe": nvg,
            "terminalId": terminal,
            "airline": airline,
            "firstYn": "N",
        }
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}{STATS_PATH}?{qs}"
        req = urllib.request.Request(url, headers=self._headers(BASE_URL + NAV_PATH))
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", resp.getcode())
                if status != 200:
                    raise FetchError(f"Stats page returned HTTP {status}")
                return resp.read().decode("utf-8", errors="replace")
        except FetchError:
            raise
        except Exception as e:  # noqa: BLE001
            raise FetchError(f"Stats fetch failed: {e}") from e


# ─── HTML Parser (stdlib html.parser) ───────────────────────────────────────


class _TableExtractor(HTMLParser):
    """Extract the first <table>...</table> verbatim from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.collecting = False
        self.chunks: list[str] = []
        self.tables: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self.depth == 0:
                self.collecting = True
                self.chunks = []
            self.depth += 1
        if self.collecting:
            attrs_str = "".join(
                f' {k}="{v}"' for k, v in attrs if v is not None
            )
            self.chunks.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        if self.collecting:
            self.chunks.append(f"</{tag}>")
        if tag == "table":
            self.depth -= 1
            if self.depth == 0 and self.collecting:
                self.tables.append("".join(self.chunks))
                self.collecting = False

    def handle_data(self, data: str) -> None:
        if self.collecting:
            self.chunks.append(data)


class _RowsExtractor(HTMLParser):
    """Extract <tr> rows, each as a list of cell text strings."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            text = "".join(self._cell).strip()
            text = " ".join(text.split())
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def extract_first_table(html: str) -> str | None:
    """Return the first <table>...</table> as a string, or None."""
    p = _TableExtractor()
    p.feed(html)
    return p.tables[0] if p.tables else None


def extract_rows(table_html: str) -> list[list[str]]:
    """Parse a <table> string into a list of rows (each a list of cell strings)."""
    p = _RowsExtractor()
    p.feed(table_html)
    return [r for r in p.rows if r]


def to_int(s: str) -> int | None:
    """Convert a thousand-separated number string to int. None on failure."""
    if not s:
        return None
    cleaned = s.replace(",", "").replace(" ", "").replace("\xa0", "")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    try:
        return int(cleaned)
    except ValueError:
        return None


_SUMMARY_TOTAL_PREFIXES = ("합", "총계", "총 계", "총  계")


def _is_total_row(first_cell: str) -> bool:
    if not first_cell:
        return False
    if first_cell.startswith(_SUMMARY_TOTAL_PREFIXES) and "계" in first_cell:
        return True
    return first_cell in {"합계", "총계"}


def _is_yoy_row(first_cell: str, rest: list[str]) -> bool:
    if "전년" in first_cell or "증감" in first_cell:
        return True
    return any("%" in c for c in rest)


def _row_to_metrics(cells: list[str], *, as_int: bool) -> dict[str, Any]:
    """Convert 9 metric cells to flights/passengers/cargo dict.

    Cell order matches the response table:
      [0,1,2] = 운항 도착/출발/합계
      [3,4,5] = 여객 도착/출발/합계
      [6,7,8] = 화물 도착/출발/합계
    """
    def val(s: str) -> Any:
        return to_int(s) if as_int else s
    return {
        "flights": {
            "arrival": val(cells[0]),
            "departure": val(cells[1]),
            "total": val(cells[2]),
        },
        "passengers": {
            "arrival": val(cells[3]),
            "departure": val(cells[4]),
            "total": val(cells[5]),
        },
        "cargo": {
            "arrival": val(cells[6]),
            "departure": val(cells[7]),
            "total": val(cells[8]),
        },
    }


def parse_airline_stats_html(html: str) -> dict[str, Any]:
    """Parse the airline stats HTML response into a structured dict.

    Returns:
        {
            "results": [
                {"airline_name": str, "flights": {...}, "passengers": {...}, "cargo": {...}},
                ...
            ],
            "summary": {
                "total": {...},        # 합계 행 (int)
                "yoy_change": {...},   # 전년대비 증감률 행 (string with %)
            },
            "parse_warnings": [str, ...],
        }
    """
    warnings: list[str] = []
    table_html = extract_first_table(html)
    if table_html is None:
        return {"results": [], "summary": {}, "parse_warnings": ["no_data_table"]}
    all_rows = extract_rows(table_html)
    if len(all_rows) < 3:
        return {
            "results": [],
            "summary": {},
            "parse_warnings": ["table_too_short"],
        }
    # rows[0], rows[1] = headers; rows[2:] = body
    body_rows = all_rows[2:]
    expected = 10  # 1 airline name + 9 metric columns
    results: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for row in body_rows:
        if len(row) != expected:
            warnings.append(
                f"unexpected_cell_count_{len(row)}:{row[0] if row else '?'}"
            )
            continue
        first = row[0]
        rest = row[1:]
        if _is_total_row(first):
            summary["total"] = _row_to_metrics(rest, as_int=True)
            continue
        if _is_yoy_row(first, rest):
            summary["yoy_change"] = _row_to_metrics(rest, as_int=False)
            continue
        # regular airline row
        metrics = _row_to_metrics(rest, as_int=True)
        results.append({"airline_name": first, **metrics})
    return {
        "results": results,
        "summary": summary,
        "parse_warnings": warnings,
    }
