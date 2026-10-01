"""매매기준율 조회 — 서울외국환중개(SMBS, www.smbs.biz) 일별·월평균 원화 환율.

네트워크는 열지 않는다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``). 요청은 itda-hyve
``http_request``(여럿이면 ``batch`` ``plan_file``)가 보내고 ``save_as`` 로 저장한다. 이 스크립트는

- ``plan``: 보낼 호출(url·params·save_as)을 만든다 — 날짜 창·저장 이름·조각을 모델이 계산하지 않게.
- ``show``: 저장된 응답을 ``--input`` 으로 읽어 판독·대조·출력한다.

질의(``plan``·``show`` 에 같은 인자를 준다):

    --date D                 D 의 매매기준율. D 에 고시가 없으면(주말·공휴일·고시 전) 직전 영업일로 폴백한다.
                             창은 [D-14일, D] 한 번의 호출. D 는 today·yesterday 도 된다(KST).
    --month M                M 의 월평균(this·last 도 된다). 진행 중인 달이면 그날까지의 평균 — 경고로 알린다.
    --month-from A --month-to B   A~B 월평균 표(최대 60개월, 호출 1회).
    --from A --to B          A~B 일별 매매기준율 표. 366일마다 한 조각(호출), 최대 10조각. B 는 today 도 된다.
    --last-days N            오늘까지 N일 일별 표(--from/--to 의 줄임).

공백 상한 14일(= 폴백 창): 실측 최장 공백은 2017 추석 연휴 11일(2017-09-29 → 10-10, 2026-10-01 itda-hyve 실측).

Usage:
    python3 exchange_rate.py plan --date today --currency USD [--save-dir DIR]
    python3 exchange_rate.py show --date 2025-10-05 --currency USD --input exrate/daily-USD-20250921-20251005-20260930.xml
    python3 exchange_rate.py plan --from 2020-01-01 --to 2024-12-31 --save-dir DIR --write-dir <연결 폴더의 샌드박스 경로>
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hyve_input import HyveFailure, HyveHTTPError, HyveInputError, read_input, snippet

_SCRIPT_DIR = Path(__file__).parent
_SKILL_DIR = _SCRIPT_DIR.parent
_CURRENCIES_FILE = _SKILL_DIR / "data" / "currencies.json"

# SMBS 엔드포인트 — 사이트 화면이 부르는 XML(FusionCharts) 그대로(화면 `StdExRate.jsp` 가
# `chart.setDataURL("StdExRate_xml.jsp?arr_value=USD_<시작>_<끝>")` 을 쓴다 — 2026-10-01 리뷰 실측).
# https 는 인증서가 m.smbs.biz 전용이라 www 로는 검증에 실패한다(2026-09-30 실측) — http 를 쓴다.
DAILY_URL = "http://www.smbs.biz/ExRate/StdExRate_xml.jsp"
MONTHLY_USD_URL = "http://www.smbs.biz/ExRate/MonAvgStdExRateUSD_xml.jsp"
MONTHLY_URL = "http://www.smbs.biz/ExRate/MonAvgStdExRate_xml.jsp"

DAILY_CAPTION = "기간별 매매기준율"
MONTHLY_CAPTION = "월평균 매매기준율"

LOOKBACK_DAYS = 14    # --date 폴백이 거슬러 가는 최대 일수(창 = [D-14, D])
MAX_GAP_DAYS = 14     # 이어진 두 고시일 사이 허용 공백 — 폴백 창과 같은 근거("이 안에 고시가 한 번은 있다")
LONGEST_SEEN_GAP = 11  # 실측 최장 공백(2017-09-29 → 10-10). 폴백이 이보다 멀면 경고한다
MAX_RANGE_DAYS = 366  # 일별 한 조각(호출)
MAX_CHUNKS = 10       # 일별 표 조각 상한(약 10년)
MAX_MONTHS = 60       # 월평균 표 상한(호출 1회)
MIN_DATE = datetime.date(2000, 1, 1)  # 일별 라벨이 YY.MM.DD 라 2000년 전은 20YY 로 잘못 읽힌다
TIMEOUT_SEC = 50      # Cowork 전송 상한 60초보다 짧게
BATCH_TIMEOUT_SEC = 50
SAVE_PREFIX = "exrate/"
SOURCE_NOTE = "출처: 서울외국환중개 (www.smbs.biz) — 매매기준율"
WEEKDAY_LIST_LIMIT = 10

KST = datetime.timezone(datetime.timedelta(hours=9))

# 저장 이름 — 끝이 받은 날 당일인 질의(오늘 환율·이번 달 평균·오늘까지 표)만 받은 시각(HHMM)을 싣는다.
# 고시 전에 받은 파일이 "같은 이름 = 이미 받은 파일" 규칙으로 그날 종일 재사용되지 않게(리뷰 W9 M3).
_NAME_RE = re.compile(
    r"^(?P<kind>daily|monthly)-(?P<cur>[A-Z]{3})-(?P<start>\d{6}(?:\d{2})?)-(?P<end>\d{6}(?:\d{2})?)"
    r"-(?P<fetched>\d{8})(?P<hm>\d{4})?\.xml$"
)

_currencies_cache: list[dict[str, Any]] | None = None


class ExRateError(Exception):
    """사용자에게 보일 실패. ``kind`` 가 출력 JSON 의 ``error`` 값이다."""

    def __init__(self, kind: str, detail: str, **extra: Any):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.extra = extra


def now_kst() -> datetime.datetime:
    """지금(KST). 테스트가 바꿔 끼우는 이음새."""
    return datetime.datetime.now(KST)


def today_kst() -> datetime.date:
    return now_kst().date()


# ---------------------------------------------------------------------------
# 통화·입력
# ---------------------------------------------------------------------------

def load_currencies() -> list[dict[str, Any]]:
    """currencies.json(사이트 통화 선택 목록 58종 — 2026-10-01 전수 대조)을 읽어 캐시한다."""
    global _currencies_cache
    if _currencies_cache is None:
        with open(_CURRENCIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _currencies_cache = data.get("currencies", []) or []
        else:
            _currencies_cache = data or []
    return _currencies_cache


def find_currency(query: str) -> dict[str, Any] | None:
    """통화 코드(대소문자 무관) 또는 한국어 별칭으로 찾는다."""
    query_upper = query.strip().upper()
    query_stripped = query.strip()
    for currency in load_currencies():
        if currency["code"].upper() == query_upper:
            return currency
        if query_stripped in currency.get("aliases_ko", []):
            return currency
    return None


def parse_date(value: str, today: datetime.date | None = None) -> datetime.date:
    """YYYY-MM-DD·YYYY.MM.DD, 또는 today·yesterday(KST)."""
    word = value.strip().lower()
    if today is not None and word in ("today", "오늘"):
        return today
    if today is not None and word in ("yesterday", "어제"):
        return today - datetime.timedelta(days=1)
    parts = value.strip().replace(".", "-").split("-")
    try:
        if len(parts) != 3 or len(parts[0]) != 4:
            raise ValueError
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError, OverflowError):
        raise ExRateError(
            "args", f"올바르지 않은 날짜입니다: '{value}' — YYYY-MM-DD·YYYY.MM.DD 또는 today·yesterday"
        ) from None


def parse_month(value: str, today: datetime.date | None = None) -> tuple[int, int]:
    """YYYY-MM·YYYY.MM, 또는 this·last(KST)."""
    word = value.strip().lower()
    if today is not None and word in ("this", "이번달"):
        return today.year, today.month
    if today is not None and word in ("last", "지난달"):
        prev = today.replace(day=1) - datetime.timedelta(days=1)
        return prev.year, prev.month
    parts = value.strip().replace(".", "-").split("-")
    try:
        if len(parts) != 2 or len(parts[0]) != 4:
            raise ValueError
        year, month = int(parts[0]), int(parts[1])
        if not 1 <= month <= 12:
            raise ValueError
        return year, month
    except (ValueError, TypeError):
        raise ExRateError("args", f"올바르지 않은 월입니다: '{value}' — YYYY-MM 또는 this·last") from None


def is_host_abs_path(value: str) -> bool:
    """itda-hyve 가 쓸 **호스트** 절대 경로인가 — `/…`·`C:\\…`·`C:/…`·`\\\\서버\\…`.

    Cowork 는 리눅스 VM 에서 스크립트를 돌리고 itda-hyve 는 사용자 PC 에서 돈다. 호스트가 Windows 면 리눅스의
    `Path.is_absolute()` 는 `C:\\…` 를 상대 경로로 본다(W10 M1). 이 값은 경로로 쓰지 않고 문자열로 싣기만 한다.
    """
    return value.startswith("/") or bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


# ---------------------------------------------------------------------------
# 질의 → 호출 계획
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Chunk:
    """호출 하나. 저장 이름 앞부분(stem)이 조각을 가른다."""

    kind: str                 # daily | monthly
    code: str
    start: datetime.date      # monthly 는 그 달 1일
    end: datetime.date        # monthly 는 그 달 1일

    def arr_value(self) -> str:
        if self.kind == "monthly":
            return f"{self.code}_{self.start:%Y-%m}_{self.end:%Y-%m}"
        return f"{self.code}_{self.start:%Y-%m-%d}_{self.end:%Y-%m-%d}"

    def url(self) -> str:
        if self.kind == "monthly":
            return MONTHLY_USD_URL if self.code == "USD" else MONTHLY_URL
        return DAILY_URL

    def stem(self) -> str:
        fmt = "%Y%m" if self.kind == "monthly" else "%Y%m%d"
        return f"{self.kind}-{self.code}-{self.start.strftime(fmt)}-{self.end.strftime(fmt)}"


@dataclass(frozen=True)
class Query:
    """``plan``·``show`` 가 같은 인자에서 만드는 질의."""

    mode: str                 # lookup | range | monthly
    currency: dict[str, Any]
    start: datetime.date      # monthly 는 첫 달 1일
    end: datetime.date        # lookup 은 요청일, monthly 는 끝 달 1일

    @property
    def code(self) -> str:
        return self.currency["code"]

    @property
    def kind(self) -> str:
        return "monthly" if self.mode == "monthly" else "daily"

    def chunks(self) -> list[Chunk]:
        if self.mode != "range":
            return [Chunk(self.kind, self.code, self.start, self.end)]
        out: list[Chunk] = []
        cur = self.start
        while cur <= self.end:
            stop = min(self.end, cur + datetime.timedelta(days=MAX_RANGE_DAYS - 1))
            out.append(Chunk("daily", self.code, cur, stop))
            cur = stop + datetime.timedelta(days=1)
        return out

    def ends_today(self, today: datetime.date) -> bool:
        """끝이 받은 날 당일(이번 달)인가 — 나중에 다시 받으면 값이 달라질 수 있는 질의."""
        if self.mode == "monthly":
            return (self.end.year, self.end.month) == (today.year, today.month)
        return self.end >= today

    def flag(self) -> str:
        if self.mode == "lookup":
            return f"--date {self.end}"
        if self.mode == "monthly":
            if self.start == self.end:
                return f"--month {self.start:%Y-%m}"
            return f"--month-from {self.start:%Y-%m} --month-to {self.end:%Y-%m}"
        return f"--from {self.start} --to {self.end}"


def build_query(args: argparse.Namespace, today: datetime.date) -> Query:
    """인자를 질의로. 미래·하한·범위 초과는 호출 전에 거부한다(``args``)."""
    currency = find_currency(args.currency)
    if currency is None:
        raise ExRateError(
            "args", f"지원하지 않는 통화입니다: '{args.currency}' — data/currencies.json 의 58종 코드·한국어 별칭"
        )

    def floor(d: datetime.date, what: str) -> None:
        if d < MIN_DATE:
            raise ExRateError("args", f"{what}({d})가 {MIN_DATE} 보다 앞입니다 — 2000년 전 고시는 조회하지 않습니다")

    if args.date:
        day = parse_date(args.date, today)
        floor(day, "--date")
        if day > today:
            raise ExRateError("args", f"{day} 는 오늘({today}) 이후입니다 — 고시된 환율이 없습니다")
        start = max(MIN_DATE, day - datetime.timedelta(days=LOOKBACK_DAYS))
        return Query("lookup", currency, start, day)
    if args.month or args.month_from:
        if args.month:
            y1, m1 = parse_month(args.month, today)
            y2, m2 = y1, m1
        else:
            if not args.month_to:
                raise ExRateError("args", "--month-from 과 --month-to 는 함께 줘야 합니다")
            y1, m1 = parse_month(args.month_from, today)
            y2, m2 = parse_month(args.month_to, today)
        first, last = datetime.date(y1, m1, 1), datetime.date(y2, m2, 1)
        floor(first, "시작 달")
        if first > last:
            raise ExRateError("args", f"시작 달({first:%Y-%m})이 끝 달({last:%Y-%m})보다 늦습니다")
        if last > today:
            raise ExRateError("args", f"{last:%Y-%m} 은 이번 달 이후입니다 — 월평균이 없습니다")
        n = (y2 * 12 + m2) - (y1 * 12 + m1) + 1
        if n > MAX_MONTHS:
            raise ExRateError("args", f"월평균 표는 {MAX_MONTHS}개월까지입니다(요청 {n}개월) — 기간을 줄이세요")
        return Query("monthly", currency, first, last)
    if args.last_days is not None:
        if not 1 <= args.last_days <= MAX_RANGE_DAYS * MAX_CHUNKS:
            raise ExRateError("args", f"--last-days 는 1~{MAX_RANGE_DAYS * MAX_CHUNKS} 입니다")
        start, end = today - datetime.timedelta(days=args.last_days - 1), today
    else:
        if not (args.date_from and args.date_to):
            raise ExRateError("args", "--from 과 --to 는 함께 줘야 합니다")
        start, end = parse_date(args.date_from, today), parse_date(args.date_to, today)
    floor(start, "시작일")
    if start > end:
        raise ExRateError("args", f"시작일({start})이 끝일({end})보다 늦습니다")
    if end > today:
        raise ExRateError("args", f"끝일({end})이 오늘({today}) 이후입니다")
    q = Query("range", currency, start, end)
    if len(q.chunks()) > MAX_CHUNKS:
        raise ExRateError(
            "args", f"일별 표는 {MAX_CHUNKS}조각({MAX_CHUNKS * MAX_RANGE_DAYS}일 남짓)까지입니다 — 기간을 줄이거나 월평균 표(--month-from)를 쓰세요"
        )
    return q


def save_name(chunk: Chunk, query: Query, now: datetime.datetime) -> str:
    stamp = f"{now:%Y%m%d}" + (f"{now:%H%M}" if query.ends_today(now.date()) else "")
    return f"{SAVE_PREFIX}{chunk.stem()}-{stamp}.xml"


def plan_calls(query: Query, now: datetime.datetime, save_dir: str | None) -> list[dict[str, Any]]:
    """itda-hyve `http_request` 에 그대로 넣을 인자 목록. User-Agent 는 싣지 않는다(hyve 기본 UA)."""
    calls = []
    for chunk in query.chunks():
        call: dict[str, Any] = {
            "url": chunk.url(),
            "params": {"arr_value": chunk.arr_value()},
            "timeout_sec": TIMEOUT_SEC,
        }
        if save_dir:
            call["save_dir"] = save_dir
        call["save_as"] = save_name(chunk, query, now)
        calls.append(call)
    return calls


# ---------------------------------------------------------------------------
# 응답 판독
# ---------------------------------------------------------------------------

def decode_body(data: bytes, form: str) -> str:
    """본문 바이트를 문자열로. 저장 파일(원본)은 EUC-KR, 응답 JSON 에서 꺼낸 본문은 UTF-8 이다."""
    order = ("utf-8", "euc-kr") if form == "envelope" else ("euc-kr", "utf-8")
    for enc in order:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ExRateError("site", "응답 본문을 EUC-KR·UTF-8 어느 쪽으로도 읽을 수 없습니다")


def parse_chart(text: str, kind: str) -> dict[str, str]:
    """FusionCharts XML 을 {날짜|월: 값} 으로. 형태가 어긋나면 명시 에러다(조용히 빈 결과로 두지 않는다).

    - 절단: 본문이 ``</chart>`` 로 끝나지 않으면 ``truncated``.
    - 오류·점검 페이지(``오류가 발생하였습니다`` 등): ``<chart>`` 가 없으면 ``site``.
    - 종류: caption 이 일별("기간별 매매기준율")·월평균("월평균 매매기준율") 중 기대한 것이어야 한다(``mismatch``).
    - 라벨·값 형식 오류, 날짜가 아닌 라벨, 같은 라벨 두 번: ``site``.
    """
    body = text.strip()
    if "<chart" not in body:
        raise ExRateError("site", f"환율 차트 XML 이 아닙니다(점검·오류 페이지일 수 있음): {snippet(body.encode(), 80)}")
    if not body.endswith("</chart>"):
        raise ExRateError("truncated", "응답이 </chart> 로 끝나지 않습니다 — 본문이 잘렸습니다")
    xml = re.sub(r"^<\?xml[^>]*\?>", "", body).strip()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ExRateError("site", f"XML 을 읽을 수 없습니다({exc})") from None
    caption = (root.get("caption") or "").strip()
    expected = MONTHLY_CAPTION if kind == "monthly" else DAILY_CAPTION
    if caption != expected:
        raise ExRateError(
            "mismatch", f"응답 종류가 다릅니다 — caption '{caption}', 기대 '{expected}'(일별·월평균 파일이 바뀌었을 수 있음)"
        )
    rates: dict[str, str] = {}
    label_re = re.compile(r"^(\d{4})\.(\d{2})$") if kind == "monthly" else re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})$")
    for elem in root.iter("set"):
        label = (elem.get("label") or "").strip()
        value = (elem.get("value") or "").strip()
        m = label_re.match(label)
        if not m:
            raise ExRateError("site", f"알 수 없는 라벨 형식: '{label}'")
        try:
            float(value)
        except ValueError:
            raise ExRateError("site", f"{label} 의 값이 숫자가 아닙니다: '{value}'") from None
        if kind == "monthly":
            key = f"{m.group(1)}-{m.group(2)}"
            if not 1 <= int(m.group(2)) <= 12:
                raise ExRateError("site", f"달이 아닌 라벨: '{label}'")
        else:
            key = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
            try:
                datetime.date.fromisoformat(key)
            except ValueError:
                raise ExRateError("site", f"날짜가 아닌 라벨: '{label}'") from None
        if key in rates:
            raise ExRateError("site", f"같은 라벨이 두 번 왔습니다: {label}")
        rates[key] = value
    return rates


def _basename(path: str) -> str:
    """`/`·`\\` 어느 쪽 구분자든 마지막 토막. Cowork 에 호스트 경로(C:\\…)를 넘기면 POSIX 의 Path.name 이 못 가른다."""
    return re.split(r"[\\/]", path)[-1]


def check_name(chunk: Chunk, query: Query, path: str, today: datetime.date) -> datetime.datetime:
    """저장 이름이 조각과 같은지(식별 계약). 받은 시각(없으면 그날 00:00)을 돌려준다."""
    name = _basename(path)
    m = _NAME_RE.match(name)
    if not m:
        raise ExRateError(
            "input", f"저장 이름이 계약과 다릅니다: {name} — plan 이 준 save_as 그대로 저장한 파일을 넘기세요"
        )
    got = f"{m.group('kind')}-{m.group('cur')}-{m.group('start')}-{m.group('end')}"
    if got != chunk.stem():
        raise ExRateError(
            "input", f"파일({got})과 인자({chunk.stem()})가 다른 질의입니다 — plan·show 에 같은 인자를 주세요"
        )
    try:
        fetched = datetime.datetime.strptime(m.group("fetched") + (m.group("hm") or "0000"), "%Y%m%d%H%M")
    except ValueError:
        raise ExRateError("input", f"저장 이름의 받은 날이 날짜가 아닙니다: {name}") from None
    if fetched.date() < chunk.end:
        raise ExRateError("input", f"받은 날({fetched.date()})이 조회 끝({chunk.end})보다 앞입니다 — 이름을 고쳐 쓴 파일입니다")
    if fetched.date() > today:
        raise ExRateError("input", f"받은 날({fetched.date()})이 오늘({today}) 이후입니다 — 이름을 고쳐 쓴 파일입니다")
    return fetched


def read_chunk(chunk: Chunk, query: Query, path: str, today: datetime.date) -> tuple[dict[str, str], datetime.datetime]:
    """``--input`` 파일 하나 → (환율, 받은 시각). hyve 층 실패·절단·HTTP 오류는 명시 에러."""
    fetched = check_name(chunk, query, path, today)
    try:
        body = read_input(Path(path).expanduser())
    except HyveFailure as exc:
        raise ExRateError("hyve", str(exc), hyve_code=exc.code) from None
    except HyveHTTPError as exc:
        raise ExRateError("http", str(exc)) from None
    except HyveInputError as exc:
        raise ExRateError(exc.kind, str(exc)) from None
    rates = parse_chart(decode_body(body.data, body.form), chunk.kind)
    lo, hi = (f"{chunk.start:%Y-%m}", f"{chunk.end:%Y-%m}") if chunk.kind == "monthly" else (
        f"{chunk.start:%Y-%m-%d}", f"{chunk.end:%Y-%m-%d}")
    outside = sorted(k for k in rates if not lo <= k <= hi)
    if outside:
        raise ExRateError("mismatch", f"요청 기간({lo}~{hi}) 밖의 행이 있습니다: {', '.join(outside[:3])} — 다른 질의의 응답")
    return rates, fetched


def read_inputs(query: Query, paths: list[str], today: datetime.date) -> tuple[dict[str, str], datetime.datetime]:
    """조각마다 파일이 정확히 하나 — 빠진 조각·남는 파일·겹친 파일은 ``input``. 받은 시각은 가장 이른 것."""
    chunks = query.chunks()
    by_stem = {c.stem(): c for c in chunks}
    seen: dict[str, str] = {}
    for p in paths:
        m = _NAME_RE.match(_basename(p))
        stem = f"{m.group('kind')}-{m.group('cur')}-{m.group('start')}-{m.group('end')}" if m else None
        if stem is None or stem not in by_stem:
            if len(chunks) == 1:
                check_name(chunks[0], query, p, today)  # 사유를 한 파일 기준으로 낸다
            raise ExRateError("input", f"이 질의의 조각이 아닌 파일: {_basename(p)} — plan 이 준 save_as 그대로 넘기세요")
        if stem in seen:
            raise ExRateError("input", f"같은 조각을 두 번 넘겼습니다: {_basename(seen[stem])}, {_basename(p)}")
        seen[stem] = p
    missing = [s for s in by_stem if s not in seen]
    if missing:
        raise ExRateError("input", f"빠진 조각 {len(missing)}개: {', '.join(missing[:3])} — plan 의 호출을 전부 받아 넘기세요",
                          missing=missing)
    rates: dict[str, str] = {}
    fetched_all: list[datetime.datetime] = []
    for stem, p in seen.items():
        r, f = read_chunk(by_stem[stem], query, p, today)
        rates.update(r)
        fetched_all.append(f)
    return rates, min(fetched_all)


# ---------------------------------------------------------------------------
# 질의별 판정
# ---------------------------------------------------------------------------

@dataclass
class Result:
    query: Query
    fetched: datetime.datetime
    rows: list[tuple[str, str]]
    result_date: datetime.date | None = None
    fallback: bool = False
    refetch: bool = False       # 당일 고시 전일 수 있다 — 나중에 다시 받으면 달라진다
    warnings: list[str] = field(default_factory=list)


def _cny_hint(query: Query) -> str:
    if query.code == "CNY" and query.end >= datetime.date(2016, 1, 1):
        return " — CNY 는 2016-01-01부터 고시하지 않습니다(사이트 공지). 위안은 CNH 로 조회하세요"
    return ""


def _missing_weekdays(start: datetime.date, end: datetime.date, have: set[str]) -> list[datetime.date]:
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in have:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def evaluate(query: Query, rates: dict[str, str], fetched: datetime.datetime) -> Result:
    """빈틈을 대조하고 결과를 만든다(기간 밖 행은 조각 판독에서 이미 걸렀다)."""
    fday = fetched.date()
    if query.mode == "monthly":
        months: list[str] = []
        y, m = query.start.year, query.start.month
        while (y, m) <= (query.end.year, query.end.month):
            months.append(f"{y:04d}-{m:02d}")
            y, m = _add_months(y, m, 1)
        current = f"{fday:%Y-%m}"
        have = [k for k in months if k in rates]
        if not have:
            if months == [current]:
                raise ExRateError(
                    "empty",
                    f"{current} 월평균은 아직 집계되지 않았습니다(받은 날 {fday}) — "
                    f"이번 달은 일별 표(--from {fday.replace(day=1)} --to {fday})로 보세요",
                )
            raise ExRateError(
                "empty", f"{months[0]}~{months[-1]} 월평균이 없습니다({query.code}) — 통화 코드·기간을 확인하세요" + _cny_hint(query)
            )
        first = months.index(have[0])
        holes = [k for k in months[first:] if k not in rates and k != current]
        if holes:
            raise ExRateError("gap", f"월평균 표 가운데·끝이 비었습니다: {', '.join(holes[:6])} — 응답이 일부만 왔을 수 있어 결과를 내지 않습니다",
                              gaps=holes)
        res = Result(query, fetched, [(k, rates[k]) for k in have])
        if first:
            res.warnings.append(f"{months[0]}~{months[first - 1]} 월평균이 없습니다(응답의 첫 달 {have[0]}) — 원인은 단정하지 않습니다")
        if current in months:
            if current in rates:
                res.warnings.append(f"{current} 는 받은 날({fday}) 기준 진행 중인 달입니다 — 그날까지의 평균이며 달이 끝나면 바뀝니다")
            else:
                res.warnings.append(f"{current} 월평균은 아직 집계되지 않았습니다(받은 날 {fday})")
            res.refetch = True
        return res

    days = sorted(rates)
    lo, hi = f"{query.start:%Y-%m-%d}", f"{query.end:%Y-%m-%d}"

    if query.mode == "lookup":
        if not days:
            raise ExRateError(
                "empty",
                f"{query.end} 부터 {LOOKBACK_DAYS}일 거슬러 올라가도 고시된 {query.code} 환율이 없습니다 — "
                "통화 코드가 다르거나 그 기간에 고시가 없었습니다(더 거슬러 가지 않습니다)" + _cny_hint(query),
            )
        last = days[-1]
        result_date = datetime.date.fromisoformat(last)
        res = Result(query, fetched, [(last, rates[last])], result_date=result_date,
                     fallback=result_date != query.end)
        if res.fallback and query.end == fday and query.end.weekday() < 5:
            res.warnings.append(
                f"{query.end} 은 받은 날 당일입니다 — 휴일이 아니라 아직 고시 전일 수 있습니다(다시 조회하면 새로 받습니다)"
            )
            res.refetch = True
        gap = (query.end - result_date).days
        if gap > LONGEST_SEEN_GAP:
            res.warnings.append(
                f"직전 고시일({result_date})이 요청일보다 {gap}일 앞입니다 — 실측 최장 공백({LONGEST_SEEN_GAP}일)보다 멉니다"
            )
        return res

    # range — 고시일 사이 공백으로 빈틈을 본다(총건수가 응답에 없다)
    if not days:
        raise ExRateError(
            "empty", f"{lo}~{hi} 에 고시된 {query.code} 환율이 없습니다 — 통화 코드나 기간을 확인하세요" + _cny_hint(query)
        )
    dates = [datetime.date.fromisoformat(d) for d in days]
    gaps = [(a, b) for a, b in zip(dates, dates[1:]) if (b - a).days > MAX_GAP_DAYS]
    tail = (query.end - dates[-1]).days
    if gaps or tail > MAX_GAP_DAYS:
        where = [f"{a}→{b}" for a, b in gaps] + ([f"{dates[-1]}→{query.end}(끝)"] if tail > MAX_GAP_DAYS else [])
        raise ExRateError(
            "gap",
            f"고시일 사이 공백이 {MAX_GAP_DAYS}일을 넘습니다: {', '.join(where)} — 응답이 일부만 왔을 수 있어 결과를 내지 않습니다",
            gaps=where,
        )
    res = Result(query, fetched, [(d, rates[d]) for d in days])
    head = (dates[0] - query.start).days
    if head > MAX_GAP_DAYS:
        res.warnings.append(
            f"{query.start}~{dates[0] - datetime.timedelta(days=1)} 에는 고시가 없습니다(응답의 첫 날 {dates[0]}) — 원인은 단정하지 않습니다"
        )
        scan_from = dates[0]
    else:
        scan_from = query.start
    scan_to = query.end
    if query.end >= fday and dates[-1] < query.end:
        if query.end.weekday() < 5:
            res.warnings.append(f"{query.end} 은 받은 날 당일입니다 — 아직 고시 전일 수 있습니다(다시 조회하면 새로 받습니다)")
            res.refetch = True
        scan_to = query.end - datetime.timedelta(days=1)
    missing = _missing_weekdays(scan_from, scan_to, set(days))
    if missing:
        shown = "·".join(f"{d:%m-%d}" for d in missing[:WEEKDAY_LIST_LIMIT])
        more = f" 외 {len(missing) - WEEKDAY_LIST_LIMIT}일" if len(missing) > WEEKDAY_LIST_LIMIT else ""
        res.warnings.append(f"평일 {len(missing)}일 고시 없음: {shown}{more} — 공휴일이 아니면 응답이 빠진 것입니다")
    return res


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def _format_rate(rate_str: str) -> str:
    """천 단위 구분, 소수 끝 0 제거(예: 1,468.3)."""
    formatted = f"{float(rate_str):,.2f}"
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted


def _weekday_ko(date: datetime.date) -> str:
    return "월화수목금토일"[date.weekday()]


def _unit(currency: dict[str, Any]) -> str:
    code = currency["code"]
    return f"KRW / 100 {code}" if currency["unit"] == 100 else f"KRW/{code}"


def _unit_label(rate: str, currency: dict[str, Any]) -> str:
    return f"{_format_rate(rate)} {_unit(currency)}"


def format_markdown(res: Result) -> str:
    q = res.query
    cur = q.currency
    lines: list[str]
    if q.mode == "lookup":
        rd = res.result_date
        assert rd is not None
        rate_label = _unit_label(res.rows[0][1], cur)
        lines = ["# 매매기준율 조회 결과", ""]
        if res.fallback:
            lines += [
                f"📅 요청일: {q.end} ({_weekday_ko(q.end)})",
                f"💱 통화: {cur['name_ko']} ({cur['code']})",
                "",
                f"⚠️ {q.end} 에는 고시된 환율이 없습니다(휴일 또는 고시 전).",
                f"→ 직전 영업일 {rd} ({_weekday_ko(rd)}) 환율을 적용합니다.",
                "",
                "| 항목 | 값 |",
                "|------|-----|",
                f"| 매매기준율 | {rate_label} |",
                f"| 기준일 | {rd} ({_weekday_ko(rd)}) |",
            ]
        else:
            lines += [
                f"📅 조회일: {rd} ({_weekday_ko(rd)})",
                f"💱 통화: {cur['name_ko']} ({cur['code']})",
                "",
                "| 항목 | 값 |",
                "|------|-----|",
                f"| 매매기준율 | {rate_label} |",
                f"| 기준일 | {rd} |",
            ]
    elif q.mode == "monthly" and q.start == q.end:
        y, m = q.start.year, q.start.month
        lines = [
            "# 월평균 매매기준율 조회 결과",
            "",
            f"📅 조회월: {y}년 {m}월",
            f"💱 통화: {cur['name_ko']} ({cur['code']})",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 월평균 매매기준율 | {_unit_label(res.rows[0][1], cur)} |",
            f"| 기준월 | {y}년 {m}월 |",
        ]
    elif q.mode == "monthly":
        lines = [
            "# 월평균 매매기준율",
            "",
            f"📅 기간: {q.start:%Y-%m} ~ {q.end:%Y-%m} ({len(res.rows)}개월)",
            f"💱 통화: {cur['name_ko']} ({cur['code']}) · 단위 {_unit(cur)}",
            "",
            "| 월 | 월평균 매매기준율 |",
            "|------|-----|",
        ]
        lines += [f"| {k} | {_format_rate(v)} |" for k, v in res.rows]
    else:
        lines = [
            "# 기간별 매매기준율",
            "",
            f"📅 기간: {q.start} ~ {q.end} (고시일 {len(res.rows)}일)",
            f"💱 통화: {cur['name_ko']} ({cur['code']}) · 단위 {_unit(cur)}",
            "",
            "| 날짜 | 매매기준율 |",
            "|------|-----|",
        ]
        lines += [
            f"| {d} ({_weekday_ko(datetime.date.fromisoformat(d))}) | {_format_rate(v)} |" for d, v in res.rows
        ]
    if res.warnings:
        lines.append("")
        lines += [f"⚠️ {w}" for w in res.warnings]
    lines += ["", "---", f"*{SOURCE_NOTE}*"]
    return "\n".join(lines)


def format_json(res: Result) -> dict[str, Any]:
    q = res.query
    monthly = q.mode == "monthly"
    out: dict[str, Any] = {
        "status": "ok",
        "mode": q.mode,
        "currency": q.code,
        "unit": q.currency["unit"],
        "start": f"{q.start:%Y-%m}" if monthly else q.start.isoformat(),
        "end": f"{q.end:%Y-%m}" if monthly else q.end.isoformat(),
        "fetched": res.fetched.strftime("%Y-%m-%dT%H:%M"),
        "rates": [{"date": d, "rate": float(v)} for d, v in res.rows],
        "refetch": res.refetch,
        "warnings": res.warnings,
        "source_note": SOURCE_NOTE,
    }
    if q.mode == "lookup":
        out["requested"] = q.end.isoformat()
        out["result_date"] = res.result_date.isoformat() if res.result_date else None
        out["fallback"] = res.fallback
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _emit_error(err: ExRateError) -> int:
    payload = {"status": "error", "error": err.kind, "detail": err.detail, **err.extra}
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if err.kind == "args" else 1


class _JsonArgParser(argparse.ArgumentParser):
    """인자 오류도 stdout JSON(`error: args`) + exit 2 — SKILL 의 오류 계약을 한 모양으로."""

    def error(self, message: str) -> None:  # type: ignore[override]
        print(json.dumps({"status": "error", "error": "args", "detail": message}, ensure_ascii=False))
        sys.exit(2)


def _add_query_args(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--date", help="YYYY-MM-DD·today·yesterday — 그날(휴일이면 직전 영업일) 환율")
    g.add_argument("--month", help="YYYY-MM·this·last — 월평균")
    g.add_argument("--month-from", dest="month_from", help="YYYY-MM — 월평균 표의 시작(--month-to 와 함께)")
    g.add_argument("--from", dest="date_from", help="YYYY-MM-DD — 일별 표의 시작(--to 와 함께)")
    g.add_argument("--last-days", dest="last_days", type=int, help="N — 오늘까지 N일 일별 표")
    p.add_argument("--month-to", dest="month_to", help="YYYY-MM·this — 월평균 표의 끝")
    p.add_argument("--to", dest="date_to", help="YYYY-MM-DD·today — 일별 표의 끝")
    p.add_argument("--currency", default="USD", help="통화 코드 또는 한국어 별칭(기본 USD)")


def build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgParser(description="매매기준율 조회 — 요청은 itda-hyve, 이 스크립트는 계획·판독만")
    sub = parser.add_subparsers(dest="cmd", required=True, parser_class=_JsonArgParser)
    p_plan = sub.add_parser("plan", help="itda-hyve 로 보낼 호출을 만든다")
    _add_query_args(p_plan)
    p_plan.add_argument("--save-dir", help="save_dir — itda-hyve 가 쓸 호스트 절대 경로(Cowork 연결 폴더; /Users/… 또는 C:\\…)")
    p_plan.add_argument("--write-dir", help="호출이 둘 이상일 때 batch 계획 파일을 쓸 폴더 — --save-dir 와 같은 폴더의 이 환경 경로")
    p_show = sub.add_parser("show", help="저장된 응답(--input)을 판독해 보여 준다")
    _add_query_args(p_show)
    p_show.add_argument("--input", action="append", required=True, help="plan 의 save_as 로 저장된 파일(조각마다 한 번)")
    p_show.add_argument("--format", choices=["markdown", "json"], default="markdown")
    return parser


def _cross_check(args: argparse.Namespace) -> None:
    if args.date_to and not args.date_from:
        raise ExRateError("args", "--to 는 --from 과 함께 씁니다")
    if args.month_to and not args.month_from:
        raise ExRateError("args", "--month-to 는 --month-from 과 함께 씁니다")


def _plan(query: Query, args: argparse.Namespace) -> dict[str, Any]:
    if args.save_dir is not None and not is_host_abs_path(args.save_dir):
        raise ExRateError("args", "--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로입니다(/Users/… 또는 C:\\…)")
    now = now_kst()
    calls = plan_calls(query, now, args.save_dir)
    inputs = " ".join("--input <저장한 파일>" for _ in calls) if len(calls) <= 3 else f"--input <저장한 파일> ×{len(calls)}"
    out: dict[str, Any] = {
        "status": "ok",
        "mode": query.mode,
        "calls": len(calls),
        "then": f"show {query.flag()} --currency {query.code} {inputs}",
    }
    if len(calls) == 1:
        out["call"] = calls[0]
        return out
    out["save_as"] = [c["save_as"] for c in calls]
    if args.write_dir:
        if not args.save_dir:
            raise ExRateError("args", "--write-dir 는 --save-dir 와 함께 씁니다(계획 파일의 호출이 그 폴더에 저장된다)")
        rel = f"{SAVE_PREFIX}plan-{query.chunks()[0].stem()}-{now:%Y%m%d%H%M}.json"
        plan = {
            "calls": [{"id": Path(c["save_as"]).stem, "tool": "http_request",
                       "args": {k: v for k, v in c.items() if k != "save_dir"}} for c in calls],
            "save_dir": args.save_dir,
            "overwrite": False,
            "timeout_sec": BATCH_TIMEOUT_SEC,
        }
        target = Path(args.write_dir).expanduser() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        # plan_file 상대 경로는 batch 인자의 save_dir(없으면 itda-hyve 기본 저장 폴더) 기준으로 풀린다 — 같은 save_dir 를
        # 함께 싣는다(funding plan_io.write_plan 의 batch_args 와 같은 꼴, shared/netbridge.md "plan_file", W9 재확인 M2).
        out["batch"] = {"save_dir": args.save_dir, "plan_file": rel}
    else:
        out["call_list"] = calls
    return out


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게(windows-console-utf8-output).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    args = build_parser().parse_args(argv)
    today = today_kst()
    try:
        _cross_check(args)
        query = build_query(args, today)
        if args.cmd == "plan":
            print(json.dumps(_plan(query, args), ensure_ascii=False))
            return 0
        rates, fetched = read_inputs(query, args.input, today)
        res = evaluate(query, rates, fetched)
    except ExRateError as err:
        return _emit_error(err)
    if args.format == "json":
        print(json.dumps(format_json(res), ensure_ascii=False))
    else:
        print(format_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
