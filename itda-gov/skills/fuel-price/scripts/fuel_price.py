#!/usr/bin/env python3
"""오피넷 평균 유가 — itda-hyve 가 받은 화면을 가공한다(네트워크 없음).

요청은 itda-hyve ``http_request`` 가 보낸다(itda-work/skills#45). 이 스크립트는 다음에 부를 호출을 만들고
(``plan``), 저장된 응답을 판독한다(``parse``).

웹 경로(기본, 키 불요) — 2회 왕복(같은 날 같은 종류 화면은 1회):
    python3 fuel_price.py plan [--region 인천] [--product 경유] [--term month] [--periods 3] [--end 2026-07]
        → 화면 GET 호출(JSON, save_as view-<nat|area>-<받은 날>.html). 오늘 받은 화면이 있으면 건너뛴다
    python3 fuel_price.py plan --input <view-….html> [같은 인자]
        → 조회 POST 호출(JSON — 폼 본문은 브라우저 FormData 와 키 집합·순서 동일). itda-hyve 로 받아 저장
    python3 fuel_price.py parse --input <avg-….html> [같은 인자] [--format json|table]
        → 평균 유가 요약(compact JSON)

API 경로(선택, itda-hyve 시크릿 OPINET_API_KEY — 최근 7일 일별만):
    python3 fuel_price.py plan --source api --term day [--region 서울] [--product 경유]
    python3 fuel_price.py parse --input <api-….json> [같은 인자]

저장 이름(``save_as``)은 식별 계약이다 — ``plan`` 이 짓고 ``parse`` 가 이름·응답 본문(화면이 되비친 조회 조건과
서버의 최신 시점 h_max*)·인자를 서로 대조한다. 어긋나면 실패로 끝낸다.

출력은 결정론적(같은 응답 → 같은 문자열)이며 stdout 만 쓴다. 실패는 ``{"status":"error","error":<종류>,"detail":…}``
를 stdout 에 쓰고 exit 1, 인자 오류는 exit 2.

유류비 정산 단가·공지문 생성은 스킬 범위 밖이다(마스터 결정 2026-09-02 — 조회에만 집중).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import opinet_api
import opinet_web as ow
from hyve_input import HyveInputError, read_input
from opinet_web import NATIONAL, OpinetWebError

SOURCE_NOTE = "출처: 오피넷(한국석유공사) https://www.opinet.co.kr — 평균판매가격(부가세 포함, 원/리터)"
TIMEOUT_SEC = 50  # Cowork 전송 상한 60초보다 짧게
SAVE_PREFIX = "fuel/"
TERM_BY_CODE = {v: k for k, v in ow.TERM_CODES.items()}

# 저장 이름 — plan 이 짓고 parse 가 읽는다. 끝의 8자리는 화면·API 를 받은 날(KST)이다 — 날이 바뀌면 이름이
# 갈려 어제 파일과 겹치지 않고, 같은 날의 화면은 질의가 달라도 다시 받지 않고 쓴다.
VIEW_NAME = re.compile(r"^view-(?P<kind>nat|area)-(?P<date>\d{8})\.html$")
AVG_NAME = re.compile(
    r"^avg-(?P<scope>nat|sido\d\d)-(?P<prod>[A-Z]\d{3})-(?P<term>[DWM])-(?P<sta>\d{6,8})-(?P<end>\d{6,8})-(?P<date>\d{8})\.html$"
)
API_NAME = re.compile(r"^api-(?P<scope>nat|sido\d\d)-(?P<prod>[A-Z]\d{3})-(?P<date>\d{8})\.json$")
API_DAYS = 7          # Open API 는 최근 7일 일별만 준다
API_FRESH_DAYS = 3    # API 최신 행이 받은 날보다 이만큼 넘게 묵었으면 묵은 파일로 본다
KST = _dt.timezone(_dt.timedelta(hours=9))


def _today_kst() -> _dt.date:
    """받은 날의 기준 — 오피넷 통계일과 같은 KST. 테스트는 이 함수를 바꿔 끼운다."""
    return _dt.datetime.now(KST).date()


class FuelError(Exception):
    """사용자에게 보일 실패 — ``kind`` 가 출력 ``error`` 값."""

    def __init__(self, kind: str, detail: str, **extra: Any):
        super().__init__(detail)
        self.kind = kind
        self.extra = extra


def fmt_won(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{digits}f}"


def diff_text(cur: float | None, prev: float | None) -> str:
    if cur is None or prev is None:
        return "—"
    d = cur - prev
    if abs(d) < 0.005:
        return "보합"
    return ("▲" if d > 0 else "▼") + f"{abs(d):,.2f}원"


PREV_WORD = {"day": "전일", "week": "전주", "month": "전월"}


@dataclass
class Briefing:
    term: str
    region: str
    product: str
    latest_label: str
    latest_price: float | None
    prev_label: str | None
    prev_price: float | None
    series: list[tuple[str, float | None]]
    as_of: str
    source: str
    missing_periods: list[str] = field(default_factory=list)  # 요청 구간 앞쪽에서 응답에 행이 없는 기간
    warnings: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        head = f"{self.latest_label} {self.region} 평균 {self.product} {fmt_won(self.latest_price)}원/L"
        if self.prev_label is not None:
            head += f" ({PREV_WORD.get(self.term, '전기')} {fmt_won(self.prev_price)} 대비 {diff_text(self.latest_price, self.prev_price)})"
        if self.missing_periods:
            head += f" — {compress_periods(self.missing_periods)} 응답에 행 없음"
        return head

    def detail_table(self) -> str:
        lines = [f"| 기간 | {self.region} {self.product} (원/L) | 증감 |", "|---|---:|---:|"]
        prev: float | None = None
        for label, price in self.series:
            lines.append(f"| {label} | {fmt_won(price)} | {diff_text(price, prev) if prev is not None else '—'} |")
            prev = price
        return "\n".join(lines)

    def to_json(self) -> str:
        d: dict[str, Any] = {"status": "ok", **asdict(self)}
        d["series"] = [{"period": l, "price": p} for l, p in self.series]
        # 결손은 늘 앞쪽의 이어진 한 구간이라 개수와 구간으로 충분하다 — 전부 나열하면 일간 장기 조회에서 수백 개가 된다(W7c c5)
        missing = d.pop("missing_periods")
        d["missing_count"] = len(missing)
        d["missing_range"] = period_span(missing)
        d["summary"] = self.summary_line()
        d["detail_table"] = self.detail_table()
        d["source_note"] = SOURCE_NOTE
        # itda-gov 규약: stdout JSON 은 compact — pretty-print 금지 (#438, dart test_response_compact_guard 가 팩 전체 스캔)
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def make_briefing(
    series: list[tuple[str, float | None]],
    *,
    term: str,
    region: str,
    product: str,
    as_of: str,
    source: str,
    missing_periods: list[str] | None = None,
    warnings: list[str] | None = None,
) -> Briefing:
    if not series:
        raise OpinetWebError("조회 결과가 비었습니다")
    latest_label, latest_price = series[-1]
    prev_label, prev_price = (series[-2] if len(series) >= 2 else (None, None))
    return Briefing(
        term=term, region=region, product=product,
        latest_label=latest_label, latest_price=latest_price,
        prev_label=prev_label, prev_price=prev_price,
        series=list(series), as_of=as_of, source=source, missing_periods=list(missing_periods or []),
        warnings=list(warnings or []),
    )


def compress_periods(labels: list[str]) -> str:
    """이어진 기간(입력은 기간 순서 그대로 — 연속 판정은 호출자가 한 것)을 ``처음~끝`` 으로 줄인다.

    결손은 늘 요청 구간의 **앞쪽에 연속으로** 난다(_check_period_rows) — 그래서 하나의 구간이다.
    """
    if len(labels) <= 2:
        return ", ".join(labels)
    return f"{labels[0]}~{labels[-1]}"


def period_span(labels: list[str]) -> str:
    """JSON ``missing_range`` 값 — 없으면 "", 하나면 그 기간, 둘 이상이면 늘 ``처음~끝``(W7m d5 — 표시용 compress_periods 는
    둘일 때 쉼표로 늘어놓아 필드 모양이 넷이 됐다)."""
    if not labels:
        return ""
    return labels[0] if len(labels) == 1 else f"{labels[0]}~{labels[-1]}"


# ---------------------------------------------------------------------------
# 질의 — 인자를 한 번 해석해 plan·parse 가 같은 값을 쓴다
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Query:
    term: str               # day|week|month
    periods: int
    region_code: str | None  # None = 전국
    product: str            # B027 등
    end: str | None         # 사용자 입력 그대로(형식은 build_query 가 이미 검사)

    @property
    def scope(self) -> str:
        return "nat" if self.region_code is None else f"sido{self.region_code}"

    @property
    def view_kind(self) -> str:
        return "nat" if self.region_code is None else "area"

    @property
    def term_code(self) -> str:
        return ow.TERM_CODES[self.term]


def build_query(args: argparse.Namespace, *, source: str = "web") -> Query:
    if args.periods < 1:
        raise FuelError("args", "--periods 는 1 이상이어야 합니다")
    q = Query(
        term=args.term,
        periods=args.periods,
        region_code=ow.resolve_region(args.region),
        product=ow.resolve_product(args.product),
        end=args.end,
    )
    if q.end:
        # 형식은 화면 없이 볼 수 있다 — 1단계에서 거른다("최신 이후" 만 화면을 받은 뒤 본다)
        ow.check_end_format(q.term, q.end)
    if source == "api":
        _check_api_query(q)
    return q


def _fetch_periods(q: Query) -> int:
    # 전기 대비를 늘 보이도록 최소 2개를 받는다(표시는 --periods 만큼)
    return max(q.periods, 2)


def _period_tag(pr: ow.PeriodRange, which: str) -> str:
    y, m, d, w = (pr.sta_y, pr.sta_m, pr.sta_d, pr.sta_w) if which == "sta" else (pr.end_y, pr.end_m, pr.end_d, pr.end_w)
    if pr.term == "day":
        return f"{y}{m}{d}"
    if pr.term == "week":
        return f"{y}{m}{w}"
    return f"{y}{m}"


def avg_name(q: Query, pr: ow.PeriodRange, date: str) -> str:
    return f"avg-{q.scope}-{q.product}-{q.term_code}-{_period_tag(pr, 'sta')}-{_period_tag(pr, 'end')}-{date}.html"


def _call(extra: dict[str, Any], save_as: str, save_dir: str | None) -> dict[str, Any]:
    call = dict(extra)
    call["timeout_sec"] = TIMEOUT_SEC
    if save_dir:
        call["save_dir"] = save_dir
    call["save_as"] = SAVE_PREFIX + save_as
    return call


# ---------------------------------------------------------------------------
# 입력 판독
# ---------------------------------------------------------------------------

def _read_text(path: str) -> tuple[str, Path]:
    try:
        body = read_input(path)
    except HyveInputError as e:
        extra = {"hyve_code": e.code} if hasattr(e, "code") else {}
        raise FuelError(e.kind, str(e), **extra) from e
    try:
        return body.text(), Path(path)
    except UnicodeDecodeError as e:
        raise FuelError("input", f"UTF-8 로 읽을 수 없습니다 — {Path(path).name}") from e


def _match_name(pattern: re.Pattern[str], path: Path, what: str) -> re.Match[str]:
    m = pattern.match(path.name)
    if not m:
        raise FuelError(
            "input",
            f"{what} 저장 이름이 아닙니다: {path.name} — plan 이 준 save_as 이름 그대로 저장한 파일을 넘기세요",
        )
    return m


def _check_name_vs_query(m: re.Match[str], q: Query, path: Path) -> None:
    got = (m.group("scope"), m.group("prod"))
    want = (q.scope, q.product)
    if got != want:
        raise FuelError(
            "input",
            f"파일({path.name})의 지역·제품이 인자와 다릅니다 — 파일 {got[0]}·{got[1]}, 인자 {want[0]}·{want[1]}. "
            "plan 과 같은 인자로 넘기세요",
        )
    if "term" in m.groupdict() and m.group("term") != q.term_code:
        raise FuelError(
            "input", f"파일({path.name})의 기간 단위({m.group('term')})가 인자(--term {q.term})와 다릅니다"
        )


def _site_error(e: OpinetWebError) -> FuelError:
    msg = str(e)
    if "기간 행이 없습니다" in msg:
        return FuelError("empty", msg)
    return FuelError("site", msg)


def _check_closed(text: str, path: Path) -> None:
    """본문이 ``</html>`` 로 끝나는가 — 표 뒤가 잘린 파일(되비침은 표 앞이라 살아 있다)을 막는다."""
    if not text.rstrip().lower().endswith("</html>"):
        raise FuelError(
            "truncated",
            f"응답 본문이 </html> 로 닫히지 않았습니다({path.name}) — 잘린 파일입니다. 같은 이름으로 다시 받으면 이 파일로 되돌아오니 --save-dir 를 새 하위 폴더로 바꿔 plan 부터 다시 받으세요",
        )


def _date_or_fail(tag: str, path: Path) -> _dt.date:
    try:
        return _dt.date(int(tag[:4]), int(tag[4:6]), int(tag[6:8]))
    except ValueError:
        raise FuelError("input", f"저장 이름의 받은 날짜({tag})가 날짜가 아닙니다 — {path.name}") from None


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> dict[str, Any]:
    q = build_query(args, source=args.source)
    today = _today_kst().strftime("%Y%m%d")
    if args.source == "api":
        if args.input:
            raise FuelError("args", "--source api 는 호출이 1회라 plan --input 이 없습니다 — parse --input 으로 넘기세요")
        return {
            "status": "ok", "stage": "api", "calls": 1,
            "call": _call(
                {"url": f"{opinet_api.API_BASE}/{opinet_api.endpoint_for(q.region_code)}.do",
                 "params": opinet_api.call_params(q.region_code, q.product)},
                f"api-{q.scope}-{q.product}-{today}.json", args.save_dir,
            ),
            "next": "parse",
        }
    if not args.input:
        url = ow.NAT_VIEW_URL if q.region_code is None else ow.AREA_VIEW_URL
        return {
            "status": "ok", "stage": "view", "calls": 2,
            "call": _call({"url": url}, f"view-{q.view_kind}-{today}.html", args.save_dir),
            "reuse": f"오늘 이미 받은 {SAVE_PREFIX}view-{q.view_kind}-{today}.html 이 있으면 이 GET 을 건너뛰고 그 파일로 plan --input",
            "next": "plan --input",
        }
    if len(args.input) != 1:
        raise FuelError("args", "plan --input 은 화면(view-…) 파일 하나만 받습니다")
    text, path = _read_text(args.input[0])
    m = _match_name(VIEW_NAME, path, "화면(view-…)")
    if m.group("kind") != q.view_kind:
        want = "전국(view-nat-…)" if q.view_kind == "nat" else "시도(view-area-…)"
        raise FuelError("input", f"화면 종류가 인자와 다릅니다({path.name}) — --region {args.region} 은 {want} 화면이 필요합니다")
    if m.group("date") != today:
        raise FuelError(
            "stale",
            f"화면({path.name})은 {m.group('date')} 에 받은 것입니다 — 오늘({today}) 화면을 받아 계획합니다. "
            "plan 을 다시 돌려 새 이름으로 받으세요",
        )
    fields = ow.HIDDEN_FIELDS_NAT if q.region_code is None else ow.HIDDEN_FIELDS_AREA
    try:
        hidden = ow.parse_hidden_fields(text, fields)
        years = ow.parse_form_echo(text).year_options
    except OpinetWebError as e:
        raise FuelError("site", str(e)) from e
    try:
        pr = ow.period_range(q.term, _fetch_periods(q), hidden, q.end)
    except OpinetWebError as e:
        raise FuelError("args", str(e)) from e
    numeric_years = [y for y in years if y.isdigit()]
    if numeric_years and pr.sta_y < min(numeric_years):
        raise FuelError(
            "args",
            f"조회 시작 연도 {pr.sta_y} 는 오피넷 화면이 고를 수 있는 범위({min(numeric_years)}년~) 밖입니다 — "
            "--end 를 늦추거나 --periods 를 줄이세요",
        )
    if q.region_code is None:
        body = ow.build_national_payload(pr, [q.product], hidden)
        url = referer = ow.NAT_VIEW_URL
    else:
        body = ow.build_area_payload(pr, [q.region_code], [q.product], q.product, hidden)
        url, referer = ow.AREA_SELECT_URL, ow.AREA_VIEW_URL
    return {
        "status": "ok", "stage": "select", "calls": 1,
        "call": _call(
            {"url": url, "method": "POST",
             "headers": {"Content-Type": "application/x-www-form-urlencoded", "Referer": referer},
             "body": body, "retry_unsafe": True},
            avg_name(q, pr, m.group("date")), args.save_dir,
        ),
        "as_of": hidden["h_maxDD"],
        "warnings": _freshness_warnings(hidden["h_maxDD"], m.group("date")),
        "next": "parse --input",
    }


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def _check_api_query(q: Query) -> None:
    if q.term != "day":
        raise FuelError(
            "args",
            "오피넷 Open API 에는 주간·월간 평균이 없습니다 — --source web(기본) 을 쓰거나 --term day 로 조회하세요",
        )
    if q.end:
        raise FuelError("args", "--source api 는 최근 7일만 제공합니다 — 특정 시점(--end)은 --source web(기본) 으로 조회하세요")
    if q.periods > API_DAYS:
        raise FuelError("args", f"--source api 는 최근 {API_DAYS}일만 제공합니다 — --periods {q.periods} 는 --source web(기본) 으로 조회하세요")


def _range_from_name(m: re.Match[str]) -> ow.PeriodRange:
    term = TERM_BY_CODE[m.group("term")]

    def split(tag: str) -> tuple[str, str, str, str]:
        if term == "day" and len(tag) == 8:
            return tag[:4], tag[4:6], tag[6:8], "1"
        if term == "week" and len(tag) == 7:
            return tag[:4], tag[4:6], "01", tag[6]
        if term == "month" and len(tag) == 6:
            return tag[:4], tag[4:6], "01", "1"
        raise FuelError("input", f"저장 이름의 기간 표기({tag})가 기간 단위({term})와 맞지 않습니다")

    sy, sm, sd, sw = split(m.group("sta"))
    ey, em, ed, ew = split(m.group("end"))
    return ow.PeriodRange(term, sy, sm, sd, sw, ey, em, ed, ew)


def _range_text(pr: ow.PeriodRange) -> str:
    return f"{_period_tag(pr, 'sta')}~{_period_tag(pr, 'end')}"


def _check_range_vs_args(q: Query, pr: ow.PeriodRange, hidden: dict[str, str], path: Path) -> None:
    """이 인자(--periods·--end)와 **응답이 알려 준 오늘의 최신 시점**(h_max*)으로 범위를 다시 계산해 이름과 대조한다.

    응답의 h_max* 는 요청에 실은 값이 아니라 서버의 현재 값이다(2026-09-30 실측 — 09-01 화면 값으로 보낸 POST 의
    응답이 h_maxDD=20260929 였다). 그래서 묵은 화면으로 계획한 조회는 여기서 드러난다.
    """
    try:
        want = ow.period_range(q.term, _fetch_periods(q), hidden, q.end)
    except OpinetWebError as e:
        raise FuelError("args", str(e)) from e
    if want == pr:
        return
    if _period_tag(want, "end") == _period_tag(pr, "end") and want.term == pr.term:
        # 끝이 최신 시점과 같다 — 화면은 묵지 않았고 --periods 만 plan 때와 다르다(다시 받을 일이 아니다)
        raise FuelError(
            "input",
            f"파일({path.name})의 조회 범위 {_range_text(pr)} 가 --periods {q.periods} 의 범위 {_range_text(want)} 와 "
            "시작만 다릅니다 — --periods 가 plan 때와 다릅니다. plan 과 같은 인자로 넘기세요",
        )
    if q.end is None:
        raise FuelError(
            "stale",
            f"파일({path.name})의 조회 범위 {_range_text(pr)} 가 최신 시점(응답 h_maxDD={hidden['h_maxDD']})으로 계산한 "
            f"범위 {_range_text(want)} 와 다릅니다 — 묵은 화면으로 계획했거나 --periods 가 plan 때와 다릅니다. "
            "plan 부터 다시 받으세요 — 오늘 받은 화면이 묵었으면(오피넷 새벽 갱신 전에 받음) --save-dir 를 새 하위 폴더로",
        )
    raise FuelError(
        "input",
        f"파일({path.name})의 조회 범위 {_range_text(pr)} 가 이 인자(--periods {q.periods} --end {q.end})의 범위 "
        f"{_range_text(want)} 와 다릅니다 — plan 과 같은 인자로 넘기세요",
    )


WEEK_TAIL_SLACK_DAYS = 7  # 최신 확정일(h_maxDD) 앞 이 날수 안에 수요일이 든 주는 표에 아직 없어도 된다


def _span_missing(names: list[str], labels: list[str]) -> list[str]:
    lo, hi = names.index(labels[0]), names.index(labels[-1])
    return [n for n in names[lo:hi + 1] if n not in labels]


def _check_period_rows(q: Query, pr: ow.PeriodRange, labels: list[str], hidden: dict[str, str],
                       path: Path) -> tuple[list[str], list[str]]:
    """기간 행을 기대 목록과 대조한다 — (요청 구간 앞쪽의 결손, 여유 안이라 아직 없는 최신 주)를 돌려주고,
    그 밖의 어긋남은 실패.

    기대 목록: 월간·일간은 범위의 모든 기간, 주간은 "그 달 N번째 수요일이 든 주" 규칙(ow.expected_weeks)으로 만든
    주 가운데 수요일이 최신 확정일(h_maxDD) 이전인 것. 표는 기대 목록의 **이어진 한 구간**이어야 하고
      · 뒤쪽: 반드시 있어야 할 주(월간·일간은 전부, 주간은 수요일이 h_maxDD − 7일 이전인 주)까지 닿아야 한다
      · 앞쪽: 비어도 된다(오피넷은 자료 없는 기간의 행을 뺀다 — 전남광주 2026-07 통합, 세종 주간 2012-11 3주부터)
    행 수는 따로 세지 않는다 — 범위 산식이 기대 목록을 늘 fetch 개 이상으로 잡으므로(앞 달마다 4주 이상), 위 두 검사를
    지난 표가 모자랄 수 있는 것은 여유 안의 최신 주 하나뿐이고 그것은 정상이다(호출자가 경고로 알린다). 이 전제가 깨지는 것은
    h_maxWW 의 달이 h_maxDD 를 앞질러 앞 달의 수요일이 기대 목록에서 떨어질 때뿐이다 — 조금 어긋나면 표가 짧아지고(호출자가
    "요청한 N주 중 M주만" 으로 알린다), 크게 어긋나 필수 주가 하나도 없으면 site 다(W7m d1).
    주간 뒤쪽의 7일 여유는 주간 행이 언제 올라오는지 두 표본(2026-09-02·09-30, 둘 다 수요일)만 봤기 때문이다 —
    두 날 모두 수요일이 h_maxDD − 6일인 주까지 있었다. 요일별 실측은 Cowork 실측 대기(references/opinet-web-contract.md).
    """
    fetch = _fetch_periods(q)
    latest = _dt.date(int(hidden["h_maxDD"][:4]), int(hidden["h_maxDD"][4:6]), int(hidden["h_maxDD"][6:8]))
    if pr.term == "week":
        weeks = [(l, w) for l, w in ow.expected_weeks(pr) if w <= latest]
        names = [l for l, _ in weeks]
        required = [i for i, (_, w) in enumerate(weeks) if w <= latest - _dt.timedelta(days=WEEK_TAIL_SLACK_DAYS)]
        if not required:
            # 범위(끝 달 = h_maxWW)가 최신 확정일(h_maxDD) 앞의 온 달을 덮지 못했다 — 정상 사이트 값에서는 생기지 않는다(W7m d1)
            raise FuelError(
                "site",
                f"응답의 최신 확정일 h_maxDD={hidden['h_maxDD']} 와 주간 끝 h_maxWW={hidden.get('h_maxWW', '?')} 가 서로 맞지 않습니다"
                f"({path.name}) — 조회 범위 {_range_text(pr)} 안에 반드시 있어야 할 주가 없습니다. 화면 구조가 바뀌었을 수 있습니다",
            )
        must_reach = required[-1]
    else:
        names = ow.expected_labels(pr) or []
        must_reach = len(names) - 1
    unexpected = [l for l in labels if l not in names]
    dup = sorted({l for l in labels if labels.count(l) > 1})
    if unexpected or dup:
        raise FuelError(
            "period",
            f"기간 행이 요청 범위와 다릅니다({path.name}) — 범위 밖·아직 없을 기간 {unexpected or '없음'}"
            + (f", 두 번 나온 기간 {dup}" if dup else ""),
            missing=[], unexpected=unexpected,
        )
    k = names.index(labels[0])
    end = k + len(labels)
    if labels != names[k:end]:
        raise FuelError(
            "period",
            f"기간 행이 이어지지 않습니다({path.name}) — 가운데 빠진 기간 {_span_missing(names, labels) or '없음(순서가 다름)'}",
            missing=_span_missing(names, labels), unexpected=[],
        )
    if end - 1 < must_reach:
        tail = names[end:must_reach + 1]
        raise FuelError(
            "period",
            f"기간 행이 요청 범위 끝까지 오지 않습니다({path.name}) — 뒤쪽에 빠진 기간 {tail}. 표가 잘렸을 수 있습니다",
            missing=tail, unexpected=[],
        )
    # 요청 구간 = 표가 끝난 곳에서 거꾸로 fetch 개. 그 안에서 응답에 없는 앞쪽 기간만 알린다(넉넉히 잡은 범위의 결손은 말하지 않는다)
    window = names[:end][-fetch:]
    return [n for n in window if n not in labels], names[end:]


def _parse_web(q: Query, text: str, path: Path) -> Briefing:
    m = _match_name(AVG_NAME, path, "조회 결과(avg-…)")
    _check_name_vs_query(m, q, path)
    got_on = _date_or_fail(m.group("date"), path)
    pr = _range_from_name(m)
    _check_closed(text, path)

    # 1) 응답 본문이 되비친 조회 조건이 저장 이름과 같은가 — 화면만 받은 파일·다른 질의의 응답을 막는다
    try:
        echo = ow.parse_form_echo(text)
    except OpinetWebError as e:
        raise FuelError("site", str(e)) from e
    want = ow.range_selects(pr)
    diffs = [f"{k} 응답 {echo.selects[k]} ≠ 요청 {v}" for k, v in want.items() if echo.selects[k] != v]
    if echo.term != q.term_code:
        diffs.insert(0, f"TERM 응답 {echo.term} ≠ 요청 {q.term_code}")
    if echo.products != (q.product,):
        diffs.append(f"제품 응답 {','.join(echo.products) or '없음'} ≠ 요청 {q.product}")
    if q.region_code is not None and echo.areas != (q.region_code,):
        diffs.append(f"지역 응답 {','.join(echo.areas) or '없음'} ≠ 요청 {q.region_code}")
    if diffs:
        raise FuelError(
            "mismatch",
            f"응답의 조회 조건이 요청과 다릅니다({path.name}) — " + "; ".join(diffs)
            + ". 화면(view-…) 파일을 넘겼거나 다른 질의의 응답입니다. 같은 이름으로 다시 받으면 이 파일로 되돌아오니 --save-dir 를 새 하위 폴더로 바꿔 plan 부터 다시 받으세요",
        )

    # 2) 이 인자와 응답의 최신 시점으로 다시 계산한 범위가 이름과 같은가(--periods·--end·묵은 화면)
    fields = ow.HIDDEN_FIELDS_NAT if q.region_code is None else ow.HIDDEN_FIELDS_AREA
    try:
        hidden = ow.parse_hidden_fields(text, fields)
    except OpinetWebError as e:
        raise FuelError("site", str(e)) from e
    _check_range_vs_args(q, pr, hidden, path)

    # 3) 표
    try:
        table = ow.parse_price_table(text)
        column = ow.PRODUCTS[q.product] if q.region_code is None else ow.SIDO_BY_CODE[q.region_code]
        series = table.series(column)
    except OpinetWebError as e:
        raise _site_error(e) from e

    # 4) 기간 행이 요청 범위와 같은가
    leading, pending = _check_period_rows(q, pr, [label for label, _ in series], hidden, path)
    series = series[-q.periods:] if q.periods >= 2 else series[-2:]  # 전기 대비를 늘 보인다
    if series[-1][1] is None:
        raise FuelError("empty", f"최신 기간({series[-1][0]})의 가격이 비었습니다({path.name}) — 통계가 아직 없거나 표가 바뀌었습니다")
    region = NATIONAL if q.region_code is None else ow.SIDO_BY_CODE[q.region_code]
    warnings = _row_warnings(q, leading, pending, series)
    warnings += _freshness_warnings(hidden["h_maxDD"], m.group("date"))
    latest = _dt.date(int(hidden["h_maxDD"][:4]), int(hidden["h_maxDD"][4:6]), int(hidden["h_maxDD"][6:8]))
    if latest > got_on:
        # 이름의 날짜는 plan 이 쓴 화면의 받은 날이다 — 그 계획으로 며칠 뒤 받은 응답이면 이렇게 된다. 범위가 맞으면(--end 지정)
        # 값은 응답 그대로 옳으니 실패시키지 않는다(API 는 이름의 날짜가 응답을 받은 날이라 같은 조합을 stale 로 막는다)
        warnings.append(
            f"응답의 최신 확정일({latest:%Y-%m-%d})이 저장 이름의 날짜({got_on:%Y-%m-%d})보다 뒤입니다 — plan 한 날보다 뒤에 받은 "
            "응답입니다. 값은 응답 기준입니다"
        )
    return make_briefing(
        series, term=q.term, region=region, product=ow.PRODUCTS[q.product],
        as_of=hidden["h_maxDD"], source="web",
        # --periods 1 의 앞 행은 요청한 기간이 아니라 전기 대비용이다 — 결손으로 세지 않고 경고로만 알린다(W7m d5)
        missing_periods=leading if q.periods >= 2 else [], warnings=warnings,
    )


def _row_warnings(q: Query, leading: list[str], pending: list[str],
                  series: list[tuple[str, float | None]]) -> list[str]:
    """기간 행 대조 결과의 경고 — 요청한 수보다 적게 보이면 **어떤 경고든 그 수를 말한다**(W7m d1)."""
    shown = min(len(series), q.periods)  # 요청한 기간 중 보이는 수(--periods 1 의 앞 행은 전기 대비용이다)
    unit = "주" if q.term == "week" else "기간"
    short = not leading and shown < q.periods
    count_note = f"요청한 {q.periods}{unit} 중 {shown}{unit}만 보입니다"
    out: list[str] = []
    if leading and q.periods == 1:
        out.append(
            f"전기 대비에 쓸 앞 기간({compress_periods(leading)})이 응답에 없습니다(자료 시작 전일 수 있다) · 전기 대비 없음"
        )
    elif leading:
        out.append(
            f"요청한 {q.periods}기간 중 {shown}기간만 응답에 있습니다 — 앞쪽 {len(leading)}기간은 응답에 행이 없습니다"
            "(자료 시작 전일 수 있다)" + (" · 전기 대비 없음" if len(series) < 2 else "")
        )
    if pending:
        out.append(
            f"최신 주({', '.join(pending)})가 응답에 없습니다 — 아직 집계 전일 수 있다. 최신은 {series[-1][0]}"
            + (f" · {count_note}" if short else "")
        )
    elif short:
        out.append(f"{count_note} — 조회 범위가 요청한 수만큼의 기간을 덮지 못했습니다"
                   + ("(최신 확정일 h_maxDD 와 주간 끝 h_maxWW 가 어긋났을 수 있다)" if q.term == "week" else ""))
    return out


def _freshness_warnings(max_dd: str, got_on: str) -> list[str]:
    """최신 확정일이 받은 날 − 1 보다 앞이면(오피넷 새벽 갱신 전에 받았거나 사이트 갱신이 멈춤) 알린다."""
    latest = _dt.date(int(max_dd[:4]), int(max_dd[4:6]), int(max_dd[6:8]))
    got = _dt.date(int(got_on[:4]), int(got_on[4:6]), int(got_on[6:8]))
    if (got - latest).days <= 1:
        return []
    return [
        f"오피넷 최신 확정일이 {latest:%Y-%m-%d} 로 받은 날({got:%Y-%m-%d}) 전전날 이전입니다 — 새벽 갱신 전에 받았거나 "
        "사이트 갱신이 늦습니다. 최신 값이 필요하면 --save-dir 를 새 하위 폴더로 바꿔 plan 부터 다시 받으세요"
    ]


def _parse_api(q: Query, text: str, path: Path) -> Briefing:
    m = _match_name(API_NAME, path, "API 응답(api-…)")
    _check_name_vs_query(m, q, path)
    got_on = _date_or_fail(m.group("date"), path)
    endpoint = opinet_api.endpoint_for(q.region_code)
    try:
        rows = opinet_api.parse_oil_array(text, endpoint)
        opinet_api.check_rows(rows, region_code=q.region_code, prodcd=q.product)
    except opinet_api.OpinetApiError as e:
        raise FuelError("api", str(e)) from e
    need = min(_fetch_periods(q), API_DAYS)
    if len(rows) < need:
        raise FuelError("period", f"API 응답이 {len(rows)}일뿐입니다(요청 {need}일) — {path.name}")
    series = opinet_api.rows_to_series(rows)
    latest = opinet_api.latest_date(rows)
    if latest > got_on or (got_on - latest).days > API_FRESH_DAYS:
        raise FuelError(
            "stale",
            f"API 응답의 최신 날짜 {latest:%Y-%m-%d} 가 받은 날({got_on:%Y-%m-%d})과 맞지 않습니다 — "
            "다른 날 받은 파일이거나 응답이 이상합니다. 같은 이름으로 다시 받으면 이 파일로 되돌아오니 --save-dir 를 새 하위 폴더로 "
            "바꿔 plan 부터 다시 받으세요",
        )
    series = series[-_fetch_periods(q):]
    return make_briefing(
        series, term="day", region=opinet_api.region_name(q.region_code, rows), product=ow.PRODUCTS[q.product],
        as_of=f"{latest:%Y%m%d}", source="api",
    )


def cmd_parse(args: argparse.Namespace) -> Briefing:
    if not args.input or len(args.input) != 1:
        raise FuelError("args", "parse --input 은 파일 하나를 받습니다(조회 결과 avg-… 또는 API 응답 api-…)")
    is_api = Path(args.input[0]).name.startswith("api-")
    q = build_query(args, source="api" if is_api else "web")
    text, path = _read_text(args.input[0])
    if is_api:
        return _parse_api(q, text, path)
    return _parse_web(q, text, path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_query_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--region", default=NATIONAL, help="전국(기본) 또는 시도명(서울·경기·인천…)")
    p.add_argument("--product", default="휘발유", help="휘발유(기본)·고급휘발유·경유·등유")
    p.add_argument("--term", choices=["day", "week", "month"], default="month", help="기간 단위(기본 month)")
    p.add_argument("--periods", type=int, default=3, help="보여 줄 기간 수(기본 3 — 전기 대비 계산용)")
    p.add_argument("--end", default=None,
                   help="조회 종료 시점 — 일간 YYYY-MM-DD, 주간·월간 YYYY-MM (기본: 오피넷 최신. 예: 2026-07 → 7월 평균)")
    p.add_argument("--input", nargs="+", default=None, metavar="FILE",
                   help="itda-hyve 가 save_as 로 저장한 파일 — plan: 화면(view-…), parse: 조회 결과(avg-…)·API 응답(api-…)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="오피넷 평균 유가 — itda-hyve 호출 계획(plan)과 응답 판독(parse)")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("plan", help="다음에 부를 itda-hyve http_request 인자(JSON)를 낸다")
    _add_query_args(pp)
    pp.add_argument("--source", choices=["web", "api"], default="web",
                    help="web(기본, 키 불요) | api(itda-hyve 시크릿 OPINET_API_KEY — day 만, 최근 7일)")
    pp.add_argument("--save-dir", default=None, help="호출 JSON 에 넣을 save_dir(Cowork 연결 폴더의 호스트 경로)")

    ps = sub.add_parser("parse", help="저장된 조회 결과를 요약한다")
    _add_query_args(ps)
    ps.add_argument("--format", choices=["json", "table"], default="json",
                    help="json(기본, compact — LLM·후처리용, summary 문자열 포함) | table(사람용 요약+표)")
    ps.add_argument("--detail", action="store_true", help="(table 형식) 기간별 표 포함 — --format table 을 함축")
    ps.add_argument("--json", action="store_true", help="(구식 별칭) --format json 과 동일")
    return p


def _emit_error(e: FuelError) -> int:
    print(json.dumps({"status": "error", "error": e.kind, "detail": str(e), **e.extra},
                     ensure_ascii=False, separators=(",", ":")))
    return 2 if e.kind == "args" else 1


def run(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            print(json.dumps(cmd_plan(args), ensure_ascii=False, separators=(",", ":")))
            return 0
        b = cmd_parse(args)
    except FuelError as e:
        return _emit_error(e)
    except OpinetWebError as e:  # 지역·제품 이름 해석 등
        return _emit_error(FuelError("args", str(e)))

    fmt = args.format
    if args.detail and not args.json:
        fmt = "table"
    if fmt == "json":
        print(b.to_json())
        return 0
    print(b.summary_line())
    print()
    print(b.detail_table())
    for w in b.warnings:  # JSON 의 warnings 와 같은 것 — 사람용 출력에서도 무음으로 두지 않는다(W7m d2)
        print(f"※ {w}")
    print(SOURCE_NOTE)
    return 0


if __name__ == "__main__":
    sys.exit(run())
