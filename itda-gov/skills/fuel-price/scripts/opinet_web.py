"""오피넷(한국석유공사) 주유소 평균 판매가격 — 키 불요 웹 통계 경로. 네트워크 없음.

요청은 itda-hyve ``http_request`` 가 보내고(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``),
이 모듈은 저장된 HTML 을 읽어 폼 본문을 만들고 응답을 판독만 한다.

오피넷 "국내유가통계 > 주유소 > 평균판매가격" 화면이 브라우저에서 보내는 폼 POST 를 **키 집합·순서 그대로**
재현한다(request-profile-first — 2026-09-02 aside 브라우저로 `form1`/`search_form` 의 FormData 를 직렬화해 박제,
`tests/test_payload_golden.py` 가 고정). 조회에 쓰이지 않는 셀렉트(분기, 월간·주간의 일)는 브라우저가 그날의
화면 기본값을 보내고 우리는 유효한 옵션 값을 보낸다 — 서버가 쓰지 않음을 2026-09-02·09-30 실측으로 확인했다.

- 전국 평균: GET ``dopOsPdrgSelect.do`` → 숨김 필드(h_max*) 판독 → POST 같은 URL
- 시도별 평균: GET ``dopOsPdrgAreaView.do`` → POST ``dopOsPdrgAreaSelect.do``
  (화면 JS 가 조회 시 action 을 AreaSelect 로 바꾼다)

응답 표(``table.tbl_type10``)의 ``<tbody>`` 행은 ``</tr>`` 닫힘 태그가 없다 — 정규식이 아니라
``html.parser`` 상태 기계로 읽는다. 응답 화면은 방금 조회한 폼 상태(기간 단위·시작/종료 셀렉트·
제품·지역 체크)를 되비친다 — :func:`parse_form_echo` 로 읽어 요청과 대조한다.

월간 평균은 Open API 에 없다(주간까지만) — 출장 유류비 정산 관행이 월평균 기준이라 이 경로가
정본이다. 인증키·NetFunnel 토큰·세션 쿠키 모두 불요(실측 2026-09-30 itda-hyve: GET 의 ``Set-Cookie`` 를
옮기지 않은 POST 가 전국·시도 모두 표를 돌려줬다. UA 는 범용 ``Mozilla/5.0`` 으로 성립).
"""
from __future__ import annotations

import datetime as _dt
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable

BASE = "https://www.opinet.co.kr"
NAT_VIEW_URL = f"{BASE}/user/dopospdrg/dopOsPdrgSelect.do"
AREA_VIEW_URL = f"{BASE}/user/dopospdrg/dopOsPdrgAreaView.do"
AREA_SELECT_URL = f"{BASE}/user/dopospdrg/dopOsPdrgAreaSelect.do"


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
    out = {n: p.values[n] for n in names}
    bad = [f"{n}={v!r}" for n, v in out.items() if not _hidden_value_ok(n, v)]
    if bad:
        raise OpinetWebError("오피넷 화면의 숨김 필드 값이 형식과 다릅니다 — " + ", ".join(bad))
    return out


# 숨김 필드 값 형식 — 계산에 쓰기 전에 거른다(빈 값·문구가 오면 int() 에서 죽지 않게)
_HIDDEN_DIGITS = {"h_maxYY": 4, "h_maxQQ": 5, "h_maxMM": 6, "h_maxDD": 8, "h_maxWW": 7}


def _hidden_value_ok(name: str, value: str) -> bool:
    if not value.isdigit():
        return False
    n = _HIDDEN_DIGITS.get(name)
    if n is None:  # all_chk_cnt·all_chk_area_cnt
        return True
    if len(value) != n:
        return False
    if name in ("h_maxMM", "h_maxWW") and not 1 <= int(value[4:6]) <= 12:
        return False
    if name == "h_maxWW" and not 1 <= int(value[6]) <= 6:
        return False
    if name == "h_maxDD":
        try:
            _dt.date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            return False
    return True


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
    digits = check_end_format(term, end)
    if term == "day":
        if digits > max_dd:
            raise OpinetWebError(f"오피넷 통계는 {max_dd[:4]}-{max_dd[4:6]}-{max_dd[6:8]} 까지만 있습니다 (요청: {end})")
        return digits
    mm = digits
    if mm > max_mm:
        raise OpinetWebError(f"오피넷 월간·주간 통계는 {max_mm[:4]}-{max_mm[4:6]} 까지만 있습니다 (요청: {end})")
    return mm


def check_end_format(term: str, end: str) -> str:
    """``--end`` 형식만 본다(화면 없이 가능한 검사) — 일간 ``YYYYMMDD``, 월간·주간 ``YYYYMM`` 으로 정규화.

    구분자는 ``-``·``.``·``/``·공백만 허용한다("7월"·"2026-7" 처럼 자릿수가 모자란 값은 거부).
    """
    raw = end.strip()
    if not raw or any(not (ch.isdigit() or ch in "-./ ") for ch in raw):
        raise OpinetWebError(
            f"--end 형식이 아닙니다: '{end}' — 일간 YYYY-MM-DD, 주간·월간 YYYY-MM"
        )
    parts = [x for x in raw.replace(".", "-").replace("/", "-").replace(" ", "-").split("-") if x]
    if len(parts) == 1:
        digits = parts[0]
    elif all(len(x) == n for x, n in zip(parts, (4, 2, 2))) and len(parts) in (2, 3):
        digits = "".join(parts)
    else:
        raise OpinetWebError(f"--end 형식이 아닙니다: '{end}' — 일간 YYYY-MM-DD, 주간·월간 YYYY-MM")
    if term == "day":
        if len(digits) != 8:
            raise OpinetWebError(f"일간 조회의 --end 는 YYYY-MM-DD 형식이어야 합니다: '{end}'")
        try:
            _dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            raise OpinetWebError(f"존재하지 않는 날짜입니다: '{end}'") from None
        return digits
    if len(digits) not in (6, 8) or not 1 <= int(digits[4:6]) <= 12:
        raise OpinetWebError(f"월간·주간 조회의 --end 는 YYYY-MM 형식이어야 합니다: '{end}'")
    return digits[:6]


def period_range(term: str, periods: int, hidden: dict[str, str], end: str | None = None) -> PeriodRange:
    """종료 시점(기본 = 화면이 알려준 최신 가용 시점 h_max*)에서 거꾸로 periods 개를 덮는 범위.

    - month: h_maxMM=YYYYMM
    - day:   h_maxDD=YYYYMMDD
    - week:  h_maxWW=YYYYMMW (연·월·월내주차) 의 연월을 끝 달로 삼는다. 주 라벨은 "그 달 N번째 수요일이 든 주"
      (expected_weeks)라 한 달의 주 수가 4 또는 5 로 갈리므로, 주는 **월 단위로 넉넉히** 잡고(START 1주 ~ END 5주)
      호출자가 기대 목록과 대조한 뒤 마지막 periods 개만 취한다.
      끝 달은 아직 한 주도 없을 수 있고(실측: h_maxWW=2026095 인데 표는 09월4주까지), 한 달이
      4주뿐인 달도 있다(2026-08 — 수요일이 넷) — 그래서 끝 달을 0주로 치고 앞 달마다 4주로 센다.
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
    months_back = -(-periods // 4)  # ceil(periods / 4) — 끝 달 0주 + 앞 달 최소 4주
    sy, sm = _shift_month(ey, em, -months_back)
    return PeriodRange("week", f"{sy}", f"{sm:02d}", "01", "1", f"{ey}", f"{em:02d}", "01", "5")


# ---------------------------------------------------------------------------
# payload 조립 — 브라우저 FormData 직렬화와 키 집합·순서 동일 (골든 테스트로 고정)
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
# 응답이 되비친 폼 상태 — 요청과 대조한다
# ---------------------------------------------------------------------------

PERIOD_SELECTS = ("STA_Y", "STA_M", "STA_W", "STA_D", "END_Y", "END_M", "END_W", "END_D")


class _FormEchoParser(HTMLParser):
    """조회 폼(``form1``·``search_form``)의 TERM 라디오·기간 셀렉트·제품/지역 체크박스 상태."""

    def __init__(self) -> None:
        super().__init__()
        self.term: list[str] = []
        self.products: list[str] = []
        self.areas: list[str] = []
        self.selected: dict[str, list[str]] = {}
        self.year_options: list[str] = []
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        name = a.get("name") or ""
        if tag == "select":
            self._select = name if name in PERIOD_SELECTS else None
            return
        if tag == "option":
            if self._select == "STA_Y":
                self.year_options.append(a.get("value") or "")
            if self._select and "selected" in a:
                self.selected.setdefault(self._select, []).append(a.get("value") or "")
            return
        if tag != "input" or "checked" not in a:
            return
        if name == "TERM" and a.get("type") == "radio":
            self.term.append(a.get("value") or "")
        elif name.startswith("OIL_CD_") and a.get("type") == "checkbox":
            self.products.append(name[len("OIL_CD_"):])
        elif name.startswith("AREA_CD_") and a.get("type") == "checkbox":
            self.areas.append(name[len("AREA_CD_"):])

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._select = None


@dataclass(frozen=True)
class FormEcho:
    term: str                      # D|W|M (화면 라디오 값)
    selects: dict[str, str]        # STA_Y … END_D 선택값
    products: tuple[str, ...]      # 체크된 제품 코드(화면 순서)
    areas: tuple[str, ...]         # 체크된 시도 코드(화면 순서, 전국 화면은 빈 값)
    year_options: tuple[str, ...] = ()  # 시작 연도 셀렉트가 허용하는 값(화면 하한 판정용)


def parse_form_echo(html: str) -> FormEcho:
    p = _FormEchoParser()
    p.feed(html)
    if len(p.term) != 1:
        raise OpinetWebError(f"응답 화면에서 선택된 기간 단위를 읽지 못했습니다(TERM 선택 {len(p.term)}개)")
    missing = [n for n in PERIOD_SELECTS if n not in p.selected]
    if missing:
        raise OpinetWebError("응답 화면에서 조회 기간 셀렉트를 읽지 못했습니다: " + ", ".join(missing))
    many = [f"{n}({','.join(v)})" for n, v in p.selected.items() if len(v) != 1]
    if many:
        # 한 셀렉트에 선택이 둘 이상이면 무엇을 조회했는지 확정할 수 없다 — 추측하지 않는다
        raise OpinetWebError("응답 화면의 기간 셀렉트에 선택값이 여럿입니다: " + ", ".join(many))
    return FormEcho(
        term=p.term[0], selects={n: v[0] for n, v in p.selected.items()},
        products=tuple(p.products), areas=tuple(p.areas), year_options=tuple(p.year_options),
    )


def range_selects(pr: PeriodRange) -> dict[str, str]:
    """PeriodRange 를 응답 셀렉트와 같은 꼴로 — 분기(Q)는 서버가 무시하는 필드라 뺀다."""
    return {
        "STA_Y": pr.sta_y, "STA_M": pr.sta_m, "STA_W": pr.sta_w, "STA_D": pr.sta_d,
        "END_Y": pr.end_y, "END_M": pr.end_m, "END_W": pr.end_w, "END_D": pr.end_d,
    }


def expected_labels(pr: PeriodRange) -> list[str] | None:
    """월간·일간 범위가 덮는 기간 라벨(화면 형식). 주간은 None — 수요일 규칙으로 만드는 expected_weeks 를 쓴다."""
    if pr.term == "month":
        y, m = int(pr.sta_y), int(pr.sta_m)
        end = (int(pr.end_y), int(pr.end_m))
        out = []
        while (y, m) <= end:
            out.append(f"{y}년{m:02d}월")
            y, m = _shift_month(y, m, 1)
        return out
    if pr.term == "day":
        d = _dt.date(int(pr.sta_y), int(pr.sta_m), int(pr.sta_d))
        e = _dt.date(int(pr.end_y), int(pr.end_m), int(pr.end_d))
        out = []
        while d <= e:
            out.append(f"{d.year}년{d.month:02d}월{d.day:02d}일")
            d += _dt.timedelta(days=1)
        return out
    return None


def month_wednesdays(y: int, m: int) -> list[_dt.date]:
    d = _dt.date(y, m, 1)
    d += _dt.timedelta(days=(2 - d.weekday()) % 7)  # 첫 수요일
    out = []
    while d.month == m:
        out.append(d)
        d += _dt.timedelta(days=7)
    return out


def expected_weeks(pr: PeriodRange) -> list[tuple[str, _dt.date]]:
    """주간 범위(시작월 1주 ~ 종료월 끝 주)가 덮는 (라벨, 그 주의 수요일).

    오피넷 주간 라벨 ``YYYY년MM월N주`` 는 **그 달의 N번째 수요일이 든 주**다 — 실측 응답 8종(2012-11~12 세종,
    2025-08~2026-08 전국 56주, 2026-07~09 전국·인천·전남광주, 09-02·09-30 두 시점)의 라벨이 전부 이 규칙과 같았다
    (W7 재리뷰 대조 + 구현자 재확인 2026-09-30), 리뷰 3차 라이브(2026-09-30) 전국 918주·세종 432주·제주 439주 전수 대조도
    어긋남 0 이었다(전국 주간은 2008년 1월 1주부터). 어긋나는 응답이 나오면 이 함수부터 의심한다.
    """
    out: list[tuple[str, _dt.date]] = []
    y, m = int(pr.sta_y), int(pr.sta_m)
    end = (int(pr.end_y), int(pr.end_m))
    while (y, m) <= end:
        for n, wed in enumerate(month_wednesdays(y, m), start=1):
            out.append((f"{y}년{m:02d}월{n}주", wed))
        y, m = _shift_month(y, m, 1)
    return out
