"""오피넷(한국석유공사) 주유소 평균 판매가격 — 키 불요 웹 통계 경로.

오피넷 "국내유가통계 > 주유소 > 평균판매가격" 화면이 브라우저에서 보내는 폼 POST 를
**바이트 순서까지 그대로** 재현한다(request-profile-first — 2026-09-02 aside 브라우저로
`form1`/`search_form` 의 FormData 를 직렬화해 박제, `tests/test_payload_golden.py` 가 고정).

- 전국 평균: GET ``dopOsPdrgSelect.do`` → 숨김 필드(h_max*) 판독 → POST 같은 URL
- 시도별 평균: GET ``dopOsPdrgAreaView.do`` → POST ``dopOsPdrgAreaSelect.do``
  (화면 JS 가 조회 시 action 을 AreaSelect 로 바꾼다)

응답 표(``table.tbl_type10``)의 ``<tbody>`` 행은 ``</tr>`` 닫힘 태그가 없다 — 정규식이 아니라
``html.parser`` 상태 기계로 읽는다.

월간 평균은 Open API 에 없다(주간까지만) — 출장 유류비 정산 관행이 월평균 기준이라 이 경로가
정본이다. 인증키·NetFunnel 토큰 모두 불요(실측: 쿠키 ``NetFunnel_ID`` 빈값으로도 성립).
"""
from __future__ import annotations

import datetime as _dt
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable

BASE = "https://www.opinet.co.kr"
NAT_VIEW_URL = f"{BASE}/user/dopospdrg/dopOsPdrgSelect.do"
AREA_VIEW_URL = f"{BASE}/user/dopospdrg/dopOsPdrgAreaView.do"
AREA_SELECT_URL = f"{BASE}/user/dopospdrg/dopOsPdrgAreaSelect.do"

# 브라우저와 같은 형태의 UA (outbound-identity-leak — 제품명을 싣지 않는다)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
TIMEOUT_SEC = 30

# 제품 코드 ↔ 화면 표기 (오피넷 평균판매가격 화면 4종. 보일러등유 C042 는 '11.7 규격 폐지)
PRODUCTS: dict[str, str] = {
    "B034": "고급휘발유",
    "B027": "보통휘발유",
    "D047": "자동차용경유",
    "C004": "실내등유",
}
PRODUCT_ALIASES: dict[str, str] = {
    "휘발유": "B027", "보통휘발유": "B027", "가솔린": "B027", "gasoline": "B027", "b027": "B027",
    "고급휘발유": "B034", "고급": "B034", "premium": "B034", "b034": "B034",
    "경유": "D047", "자동차용경유": "D047", "디젤": "D047", "diesel": "D047", "d047": "D047",
    "등유": "C004", "실내등유": "C004", "kerosene": "C004", "c004": "C004",
}

# 시도 코드 ↔ 화면 표기 (지역별 화면 체크박스 AREA_CD_xx 순서 = 화면 순서).
# 2026-07-01 광주+전남 → "전남광주"(20) 통합 — 구 코드 07(전남)·16(광주) 체크박스는 화면에
# 남아 있으나 기본 해제 상태(실측 2026-09-02).
SIDO_ORDER: list[tuple[str, str]] = [
    ("01", "서울"), ("10", "부산"), ("14", "대구"), ("15", "인천"), ("20", "전남광주"),
    ("17", "대전"), ("18", "울산"), ("02", "경기"), ("03", "강원"), ("04", "충북"),
    ("05", "충남"), ("06", "전북"), ("08", "경북"), ("09", "경남"), ("11", "제주"), ("19", "세종"),
]
SIDO_BY_CODE: dict[str, str] = dict(SIDO_ORDER)
SIDO_ALIASES: dict[str, str] = {
    "서울": "01", "서울시": "01", "서울특별시": "01",
    "경기": "02", "경기도": "02",
    "강원": "03", "강원도": "03", "강원특별자치도": "03",
    "충북": "04", "충청북도": "04",
    "충남": "05", "충청남도": "05",
    "전북": "06", "전라북도": "06", "전북특별자치도": "06",
    "경북": "08", "경상북도": "08",
    "경남": "09", "경상남도": "09",
    "부산": "10", "부산시": "10", "부산광역시": "10",
    "제주": "11", "제주도": "11", "제주특별자치도": "11",
    "대구": "14", "대구시": "14", "대구광역시": "14",
    "인천": "15", "인천시": "15", "인천광역시": "15",
    "대전": "17", "대전시": "17", "대전광역시": "17",
    "울산": "18", "울산시": "18", "울산광역시": "18",
    "세종": "19", "세종시": "19", "세종특별자치시": "19",
    "전남광주": "20", "광주": "20", "광주시": "20", "광주광역시": "20", "전남": "20", "전라남도": "20",
    "전남광주통합특별시": "20",
}
NATIONAL = "전국"

TERM_CODES = {"day": "D", "week": "W", "month": "M"}
TERM_LABEL = {"day": "일간", "week": "주간", "month": "월간"}
# 화면 숨김 필드 이름 (GET 응답에서 그대로 읽어 POST 로 되돌린다 — 값을 지어내지 않는다)
HIDDEN_FIELDS_NAT = ("all_chk_cnt", "h_maxYY", "h_maxQQ", "h_maxMM", "h_maxDD", "h_maxWW")
HIDDEN_FIELDS_AREA = HIDDEN_FIELDS_NAT + ("all_chk_area_cnt",)


class OpinetWebError(Exception):
    """오피넷 웹 통계 조회 실패 (사용자 표시용 한국어 메시지)."""


def resolve_product(text: str | None) -> str:
    if not text:
        return "B027"
    key = text.strip().lower()
    code = PRODUCT_ALIASES.get(key) or PRODUCT_ALIASES.get(text.strip())
    if not code:
        raise OpinetWebError(
            f"알 수 없는 제품 '{text}'. 사용 가능: 휘발유·고급휘발유·경유·등유"
        )
    return code


def resolve_region(text: str | None) -> str | None:
    """시도 코드(2자리)를 돌려준다. 전국이면 None."""
    if not text or text.strip() in (NATIONAL, "national", "all"):
        return None
    key = text.strip()
    code = SIDO_ALIASES.get(key)
    if not code and key in SIDO_BY_CODE:
        code = key
    if not code:
        raise OpinetWebError(
            f"알 수 없는 지역 '{text}'. 사용 가능: 전국 · " + " · ".join(n for _, n in SIDO_ORDER)
        )
    return code


# ---------------------------------------------------------------------------
# HTML 판독
# ---------------------------------------------------------------------------

class _HiddenInputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        a = dict(attrs)
        if a.get("type") == "hidden" and a.get("name"):
            self.values[a["name"]] = a.get("value") or ""


def parse_hidden_fields(html: str, names: Iterable[str]) -> dict[str, str]:
    p = _HiddenInputParser()
    p.feed(html)
    missing = [n for n in names if n not in p.values]
    if missing:
        raise OpinetWebError(
            "오피넷 화면 구조가 바뀐 것 같습니다 — 숨김 필드 미발견: " + ", ".join(missing)
        )
    return {n: p.values[n] for n in names}


class _PriceTableParser(HTMLParser):
    """``table.tbl_type10`` 의 th/td 텍스트를 행 단위로 모은다 (``</tr>`` 부재 허용)."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_table = False
        self._depth = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "table":
            if self._in_table:
                self._depth += 1
            elif "tbl_type10" in (a.get("class") or ""):
                self._in_table = True
                self._depth = 0
            return
        if not self._in_table or self._depth:
            return
        if tag == "tr":
            self._flush_row()
            self._row = []
        elif tag in ("th", "td"):
            if self._row is None:
                self._row = []
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            if self._depth:
                self._depth -= 1
            else:
                self._flush_row()
                self._in_table = False
            return
        if not self._in_table or self._depth:
            return
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            self._flush_row()

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def _flush_row(self) -> None:
        if self._row:
            self.rows.append(self._row)
        self._row = None


def _to_price(text: str) -> float | None:
    t = text.replace(",", "").strip()
    if not t or t in ("-", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


@dataclass
class PriceTable:
    """열 = 제품(전국) 또는 지역(시도별), 행 = 기간 라벨."""

    columns: list[str]
    rows: list[tuple[str, list[float | None]]] = field(default_factory=list)
    extra: dict[str, list[float | None]] = field(default_factory=dict)  # '전일대비' 등 비기간 행

    def series(self, column: str) -> list[tuple[str, float | None]]:
        if column not in self.columns:
            raise OpinetWebError(f"응답 표에 '{column}' 열이 없습니다 (열: {', '.join(self.columns)})")
        i = self.columns.index(column)
        return [(label, vals[i] if i < len(vals) else None) for label, vals in self.rows]


_PERIOD_MARKERS = ("년", "월", "일", "주")


def parse_price_table(html: str) -> PriceTable:
    p = _PriceTableParser()
    p.feed(html)
    if not p.rows:
        raise OpinetWebError("오피넷 응답에서 가격 표(tbl_type10)를 찾지 못했습니다")
    header, *body = p.rows
    if not header or header[0] != "구분":
        raise OpinetWebError(f"가격 표 머리행이 예상과 다릅니다: {header}")
    table = PriceTable(columns=header[1:])
    for row in body:
        if not row:
            continue
        label, cells = row[0], [_to_price(c) for c in row[1:]]
        if label.endswith(_PERIOD_MARKERS) and label[:4].isdigit():
            table.rows.append((label, cells))
        else:
            table.extra[label] = cells
    if not table.rows:
        raise OpinetWebError(
            "가격 표는 있으나 기간 행이 없습니다 — 조회 기간에 통계가 없거나 화면 계약이 바뀌었습니다"
        )
    return table


# ---------------------------------------------------------------------------
# 기간 계산 (오피넷 폼의 STA_*/END_* 셀렉트 값)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodRange:
    term: str          # day|week|month
    sta_y: str
    sta_m: str
    sta_d: str
    sta_w: str
    end_y: str
    end_m: str
    end_d: str
    end_w: str

    @property
    def sta_q(self) -> str:
        return str((int(self.sta_m) - 1) // 3 + 1)

    @property
    def end_q(self) -> str:
        return str((int(self.end_m) - 1) // 3 + 1)


def _shift_month(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def normalize_end(term: str, end: str | None, hidden: dict[str, str]) -> str:
    """조회 종료 시점을 화면 형식으로 — 미지정이면 화면의 최신 가용 시점(h_max*).

    입력 허용: `YYYY-MM-DD`·`YYYY.MM.DD`·`YYYYMMDD`·`YYYY-MM`·`YYYYMM`. 월간/주간은 연월까지만 쓴다.
    화면이 알려준 최신 시점보다 뒤면 거부한다(오피넷은 전일까지만 확정 통계를 낸다).
    """
    max_dd, max_mm = hidden["h_maxDD"], hidden["h_maxMM"]
    if not end:
        return max_dd if term == "day" else max_mm
    digits = "".join(ch for ch in end if ch.isdigit())
    if term == "day":
        if len(digits) != 8:
            raise OpinetWebError(f"일간 조회의 --end 는 YYYY-MM-DD 형식이어야 합니다: '{end}'")
        try:
            _dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            raise OpinetWebError(f"존재하지 않는 날짜입니다: '{end}'") from None
        if digits > max_dd:
            raise OpinetWebError(f"오피넷 통계는 {max_dd[:4]}-{max_dd[4:6]}-{max_dd[6:8]} 까지만 있습니다 (요청: {end})")
        return digits
    if len(digits) not in (6, 8) or not 1 <= int(digits[4:6]) <= 12:
        raise OpinetWebError(f"월간·주간 조회의 --end 는 YYYY-MM 형식이어야 합니다: '{end}'")
    mm = digits[:6]
    if mm > max_mm:
        raise OpinetWebError(f"오피넷 월간·주간 통계는 {max_mm[:4]}-{max_mm[4:6]} 까지만 있습니다 (요청: {end})")
    return mm


def period_range(term: str, periods: int, hidden: dict[str, str], end: str | None = None) -> PeriodRange:
    """종료 시점(기본 = 화면이 알려준 최신 가용 시점 h_max*)에서 거꾸로 periods 개를 덮는 범위.

    - month: h_maxMM=YYYYMM
    - day:   h_maxDD=YYYYMMDD
    - week:  h_maxWW=YYYYMMW (연·월·월내주차). 주차 산술이 화면 규칙(일~목 평균) 종속이라
      주는 **월 단위로 넉넉히** 잡고(START 1주 ~ END 5주) 호출자가 마지막 periods 개만 취한다.
    - end 를 주면 그 시점을 종료로 삼는다(과거 임의 시점 조회 — 폼이 1997년~ 지원).
    """
    if periods < 1:
        raise OpinetWebError("periods 는 1 이상이어야 합니다")
    if term not in TERM_CODES:
        raise OpinetWebError(f"알 수 없는 기간 단위 '{term}' (day|week|month)")
    end_norm = normalize_end(term, end, hidden)
    if term == "month":
        mm = end_norm
        ey, em = int(mm[:4]), int(mm[4:6])
        sy, sm = _shift_month(ey, em, -(periods - 1))
        return PeriodRange("month", f"{sy}", f"{sm:02d}", "01", "1", f"{ey}", f"{em:02d}", "01", "1")
    if term == "day":
        dd = end_norm
        end_d = _dt.date(int(dd[:4]), int(dd[4:6]), int(dd[6:8]))
        start = end_d - _dt.timedelta(days=periods - 1)
        return PeriodRange(
            "day", f"{start.year}", f"{start.month:02d}", f"{start.day:02d}", "1",
            f"{end_d.year}", f"{end_d.month:02d}", f"{end_d.day:02d}", "1",
        )
    # week — end 미지정이면 h_maxWW 의 연월, 지정이면 그 연월
    ww = hidden["h_maxWW"] if not end else end_norm
    ey, em = int(ww[:4]), int(ww[4:6])
    months_back = (periods + 4) // 5  # 한 달 최대 5주 → 넉넉히
    sy, sm = _shift_month(ey, em, -months_back)
    return PeriodRange("week", f"{sy}", f"{sm:02d}", "01", "1", f"{ey}", f"{em:02d}", "01", "5")


# ---------------------------------------------------------------------------
# payload 조립 — 브라우저 FormData 직렬화 순서와 바이트 동일 (골든 테스트로 고정)
# ---------------------------------------------------------------------------

def _encode(pairs: list[tuple[str, str]]) -> str:
    return urllib.parse.urlencode(pairs, encoding="utf-8")


def build_national_payload(pr: PeriodRange, products: list[str], hidden: dict[str, str]) -> str:
    pairs: list[tuple[str, str]] = [
        ("all_chk_cnt", hidden["all_chk_cnt"]),
        ("INIF_FLAG", "N"),
        ("chk_cnt", str(len(products))),
        ("h_maxYY", hidden["h_maxYY"]), ("h_maxQQ", hidden["h_maxQQ"]), ("h_maxMM", hidden["h_maxMM"]),
        ("h_maxDD", hidden["h_maxDD"]), ("h_maxWW", hidden["h_maxWW"]),
        ("sta_dt", ""), ("end_dt", ""),
        ("TERM", TERM_CODES[pr.term]),
        ("STA_Y", pr.sta_y), ("STA_M", pr.sta_m), ("STA_Q", pr.sta_q), ("STA_W", pr.sta_w), ("STA_D", pr.sta_d),
        ("END_Y", pr.end_y), ("END_M", pr.end_m), ("END_Q", pr.end_q), ("END_W", pr.end_w), ("END_D", pr.end_d),
    ]
    for code in PRODUCTS:  # 화면 체크박스 순서
        if code in products:
            pairs.append((f"OIL_CD_{code}", "Y"))
    pairs.append(("equal", "Y"))
    return _encode(pairs)


def build_area_payload(
    pr: PeriodRange, sido_codes: list[str], products: list[str], slt_prod: str, hidden: dict[str, str]
) -> str:
    pairs: list[tuple[str, str]] = [
        ("chkgu", "N"),
        ("all_chk_cnt", hidden["all_chk_cnt"]),
        ("all_chk_area_cnt", hidden["all_chk_area_cnt"]),
        ("INIF_FLAG", "N"),
        ("viewType", "AREA"),
        ("chk_cnt", str(len(products))),
        ("chk_area_cnt", str(len(sido_codes))),
        ("SIGUN_CHK", "N"), ("PROD_CHK", "N"),
        ("serch_sido_cd", ""), ("serch_sigun_cd", ""), ("sido_nm", ""), ("sigun_nm", ""),
        ("h_maxYY", hidden["h_maxYY"]), ("h_maxQQ", hidden["h_maxQQ"]), ("h_maxMM", hidden["h_maxMM"]),
        ("h_maxDD", hidden["h_maxDD"]), ("h_maxWW", hidden["h_maxWW"]),
        ("sta_dt", ""), ("end_dt", ""),
        ("TERM", TERM_CODES[pr.term]),
        ("STA_Y", pr.sta_y), ("STA_M", pr.sta_m), ("STA_Q", pr.sta_q), ("STA_W", pr.sta_w), ("STA_D", pr.sta_d),
        ("END_Y", pr.end_y), ("END_M", pr.end_m), ("END_Q", pr.end_q), ("END_W", pr.end_w), ("END_D", pr.end_d),
        ("searchType", "AREA"),
    ]
    for code, _ in SIDO_ORDER:  # 화면 체크박스 순서
        if code in sido_codes:
            pairs.append((f"AREA_CD_{code}", "Y"))
    pairs += [("sido_cd", ""), ("sigun_cd", "선택")]
    for code in PRODUCTS:
        if code in products:
            pairs.append((f"OIL_CD_{code}", "Y"))
    pairs += [("sltProdCd", slt_prod), ("equal", "Y")]
    return _encode(pairs)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _opener() -> urllib.request.OpenerDirector:
    import http.cookiejar

    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(opener: urllib.request.OpenerDirector, url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 사용자 표시용으로 접는다
        raise OpinetWebError(f"오피넷 접속 실패 ({url}): {e}") from e


def _post(opener: urllib.request.OpenerDirector, url: str, payload: str, referer: str) -> str:
    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with opener.open(req, timeout=TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        raise OpinetWebError(f"오피넷 조회 실패 ({url}): {e}") from e


@dataclass
class WebQueryResult:
    term: str
    region: str            # "전국" 또는 시도명
    product_code: str
    product_name: str
    series: list[tuple[str, float | None]]  # (기간 라벨, 원/L)
    payload: str           # 진단용 — 보낸 폼 원문
    as_of: str             # 화면이 알려준 최신 가용 시점(h_maxDD)


def fetch_average(
    *,
    term: str = "month",
    periods: int = 3,
    region: str | None = None,
    product: str | None = None,
    end: str | None = None,
) -> WebQueryResult:
    """전국(region=None) 또는 시도별 평균 판매가격 시계열을 조회한다.

    end: 종료 시점(`YYYY-MM-DD` 일간 / `YYYY-MM` 주간·월간). 미지정 = 최신.
    """
    prod = resolve_product(product)
    sido = resolve_region(region)
    opener = _opener()
    if sido is None:
        view = _get(opener, NAT_VIEW_URL)
        hidden = parse_hidden_fields(view, HIDDEN_FIELDS_NAT)
        pr = period_range(term, periods, hidden, end)
        payload = build_national_payload(pr, [prod], hidden)
        html = _post(opener, NAT_VIEW_URL, payload, NAT_VIEW_URL)
        table = parse_price_table(html)
        series = table.series(PRODUCTS[prod])
        region_name = NATIONAL
    else:
        view = _get(opener, AREA_VIEW_URL)
        hidden = parse_hidden_fields(view, HIDDEN_FIELDS_AREA)
        pr = period_range(term, periods, hidden, end)
        payload = build_area_payload(pr, [sido], [prod], prod, hidden)
        html = _post(opener, AREA_SELECT_URL, payload, AREA_VIEW_URL)
        table = parse_price_table(html)
        series = table.series(SIDO_BY_CODE[sido])
        region_name = SIDO_BY_CODE[sido]
    series = series[-periods:]
    return WebQueryResult(
        term=term,
        region=region_name,
        product_code=prod,
        product_name=PRODUCTS[prod],
        series=series,
        payload=payload,
        as_of=hidden["h_maxDD"],
    )
