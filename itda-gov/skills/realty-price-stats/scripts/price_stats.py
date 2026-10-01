"""가격지수·시세 통계 — R-ONE 호출 계획·응답 파서와 realty-deals 파생 통계 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request``·``batch`` 가 한다(itda-work/skills#45). 이 모듈은
  1. 한국부동산원 R-ONE 통계 조회(``SttsApiTblData.do``)의 **호출 계획**(``http_request`` 인자 그대로)을 만들고
  2. 그렇게 저장한 **응답 JSON 파일을 읽어** 오류 판정·쪽 전량 대조·정리만 한다.
직접 API 를 부르지 않고, 키 값을 보지 않는다(``{{secret:RONE_API_KEY}}`` 자리표시자만 싣는다).
KB 데이터허브는 공식 API가 없으므로 KB 사이트 스크래핑은 수행하지 않는다 (R21).

R-ONE 요청 계약 (2026-09-30 판독 — R-ONE Open API 목록 > 통계 조회 조건 설정, 키 없는 sample 호출로 대조):
    GET https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do
    기본인자  KEY · Type(json) · pIndex · pSize(최대 1,000 — ERROR-336)
    요청인자  STATBL_ID(필수) · DTACYCLE_CD(필수) · START_WRTTIME · END_WRTTIME(양끝 포함) …
    주간 시점 ID 는 ISO 주차가 아니다 — 창을 앞뒤로 한 주 넓혀 받고 WRTTIME_DESC(월요일)로 거른다(W2 리뷰 M1).
응답 형태:
    성공      {"SttsApiTblData": [{"head": [{"list_total_count": N}, {"RESULT": {"CODE": "INFO-000", …}}]}, {"row": [...]}]}
    오류      {"RESULT": {"CODE": "ERROR-300", "MESSAGE": "…"}}   (HTTP 200 — 실측 ERROR-300·ERROR-290)

공개 API:
    RONE_INDEX_TYPES · rone_plan · build_rone_call · collect_rone · write_plans
    derive_stats_from_deals · build_stats_envelope
"""
from __future__ import annotations

import calendar
import json
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from hyve_input import HyveHTTPError, HyveInputError, read_input


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 한국부동산원 R-ONE 통계 조회 URL (https://www.reb.or.kr/r-one/ → Open API)
RONE_BASE_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
RONE_SECRET = "{{secret:RONE_API_KEY}}"

# 지원하는 R-ONE 지수 유형 → 통계표 ID·주기 (R-ONE 통계코드 검색 2026-09-30 판독)
RONE_INDEX_TYPES: dict[str, dict[str, str]] = {
    "weekly": {"statbl_id": "T244183132827305", "cycle": "WK",
               "label": "주간 아파트 매매가격지수(주간아파트동향)"},
    "monthly": {"statbl_id": "A_2024_00045", "cycle": "MM",
                "label": "월간 아파트 매매가격지수(월간동향)"},
    "jeonse_rate": {"statbl_id": "A_2024_00156", "cycle": "MM",
                    "label": "지역별 전월세 전환율_아파트"},
}

# 한 쪽의 행 수 — R-ONE 상한(ERROR-336: 한 번에 1,000건을 넘을 수 없다).
RONE_PAGE_SIZE = 1000
# 한 질의에서 받을 쪽 상한(1,000 × 20 = 2만 행). 넘으면 truncated 로 표시한다(호출 예산).
RONE_MAX_PAGES = 20
# itda-hyve batch 한 번의 호출 상한 — 넘으면 하나도 실행하지 않는다.
BATCH_LIMIT = 40
# 단건 timeout — Cowork 전송 상한(60초)보다 짧게.
CALL_TIMEOUT_SEC = 50

# 저장 이름 규칙 — 질의(지수 유형·시작월·종료월)와 쪽을 이름에 싣는다. 응답 본문은 pIndex 를 되돌려주지 않는다.
_NAME_RE = re.compile(r"(weekly|monthly|jeonse_rate)-(\d{6})-(\d{6})-p(\d+)\.json$")

# R-ONE 메시지 코드 (Open API 목록 > 메시지 설명, 2026-09-30 판독)
_RONE_HINTS = {
    "ERROR-300": "필수 값 누락 — rone-plan 이 준 params 를 그대로 보냈는지 확인",
    "ERROR-290": "인증키가 유효하지 않다 — itda-hyve GUI 시크릿 탭의 RONE_API_KEY 를 확인(https://www.reb.or.kr/r-one/ 로그인 → Open API 에서 인증키 신청)",
    "ERROR-336": "한 번에 1,000건을 넘게 요청했다 — pSize 는 1000 이하",
    "ERROR-337": "일별 트래픽 제한 초과 — 오늘은 더 부르지 않는다",
    "ERROR-333": "요청위치(pIndex) 값이 정수가 아니다",
    "ERROR-310": "해당 서비스를 찾을 수 없다 — URL 을 확인",
    "ERROR-500": "R-ONE 서버 오류 — 잠시 뒤 다시",
    "ERROR-600": "R-ONE 데이터베이스 연결 오류 — 잠시 뒤 다시",
    "ERROR-601": "R-ONE SQL 오류 — 잠시 뒤 다시",
    "INFO-300": "관리자에 의해 인증키 사용이 제한됐다 — R-ONE 고객지원에 문의",
}


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class PriceStatsAPIError(Exception):
    """저장된 응답이 성공 응답이 아니다 (본문의 R-ONE 메시지 코드)."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class InputFileError(Exception):
    """입력 파일을 가공할 수 없다 — 없음·이름 규칙 위반·절단·HTTP 오류·itda-hyve 실패·전량 대조 모순.

    ``kind`` 는 출력 JSON 의 ``error`` 값이다(``input``·``truncated``·``http``·``hyve``).
    """

    def __init__(self, message: str, kind: str = "input"):
        super().__init__(message)
        self.kind = kind


class IncompleteError(Exception):
    """받은 쪽이 모자라다. ``next_calls`` 에 더 받을 호출이 담긴다."""

    def __init__(self, message: str, next_calls: list[dict[str, Any]],
                 need_pages: int, will_truncate: bool, total_count: int):
        super().__init__(message)
        self.next_calls = next_calls
        self.need_pages = need_pages
        self.will_truncate = will_truncate
        self.total_count = total_count


# ---------------------------------------------------------------------------
# 호출 계획
# ---------------------------------------------------------------------------

def parse_month(value: str) -> tuple[int, int]:
    """YYYYMM → (연, 월). 형식이 틀리면 ValueError."""
    if not re.fullmatch(r"\d{6}", value or ""):
        raise ValueError(f"월 형식이 올바르지 않습니다: '{value}'. YYYYMM 형식으로 입력하세요.")
    year, month = int(value[:4]), int(value[4:])
    if not 1 <= month <= 12:
        raise ValueError(f"월 형식이 올바르지 않습니다: '{value}'. 월은 01~12.")
    return year, month


def _rone_week_estimate(day: date) -> tuple[int, int]:
    """``day`` 가 든 주의 R-ONE 주간 시점 ID 를 **어림**한다 — (연, 주).

    31표본(2015~2026, 2026-09-30 재리뷰 실측 — tests ``RONE_WEEK_GOLDEN``)에 맞는 규칙: 주를 일~토로 끊고 1월 1일이 든 주를 1주로 센다
    (엑셀 ``WEEKNUM(토요일, 1)``). ISO 주차와는 1월 1일이 금·토인 해(2016·2021·2022, 앞으로 2027·2028)에 한 주 갈린다.
    공표 규칙이 아니라 표본에서 세운 규칙이라 요청 창을 앞뒤로 한 주씩 넓히는 데만 쓴다 — 기간을 가르는 것은
    본문의 ``WRTTIME_DESC`` 다(:func:`collect_rone`).
    """
    saturday = day + timedelta(days=(5 - day.weekday()) % 7)
    year = saturday.year
    jan1 = date(year, 1, 1)
    first_sunday = jan1 - timedelta(days=(jan1.weekday() + 1) % 7)
    this_sunday = saturday - timedelta(days=6)
    return year, (this_sunday - first_sunday).days // 7 + 1


def _week_id(year: int, week: int) -> str:
    return f"{year}{week:02d}"


def rone_period_range(index_type: str, start_month: str, end_month: str) -> tuple[str, str]:
    """요청 월 범위를 R-ONE ``START_WRTTIME``·``END_WRTTIME`` 로 바꾼다.

    월간(MM)은 ``YYYYMM`` 그대로. 주간(WK)은 시점 ID 를 달력으로 확정하지 않는다 — 시작월 1일·종료월 말일이 든 주를
    어림한 뒤(:func:`_rone_week_estimate`) **앞뒤로 한 주씩 넓힌다.** 연 경계에서는 시작 쪽을 전년 ``52``(52·53주를
    모두 덮는다), 끝 쪽을 다음 해 ``01`` 로 잡는다. 넓혀 받은 행은 :func:`collect_rone` 이 ``WRTTIME_DESC``
    (그 주 월요일)로 요청 기간에 맞게 거른다.
    """
    info = _index_info(index_type)
    sy, sm = parse_month(start_month)
    ey, em = parse_month(end_month)
    if (sy, sm) > (ey, em):
        raise ValueError(f"시작월({start_month})이 종료월({end_month})보다 늦습니다.")
    if info["cycle"] != "WK":
        return start_month, end_month
    y1, w1 = _rone_week_estimate(date(sy, sm, 1))
    y2, w2 = _rone_week_estimate(date(ey, em, calendar.monthrange(ey, em)[1]))
    start = _week_id(y1 - 1, 52) if w1 <= 1 else _week_id(y1, w1 - 1)
    end = _week_id(y2 + 1, 1) if w2 >= 52 else _week_id(y2, w2 + 1)
    return start, end


def month_span(start_month: str, end_month: str) -> tuple[date, date]:
    """요청 월 범위의 첫날·마지막 날."""
    sy, sm = parse_month(start_month)
    ey, em = parse_month(end_month)
    return date(sy, sm, 1), date(ey, em, calendar.monthrange(ey, em)[1])


def _index_info(index_type: str) -> dict[str, str]:
    if index_type not in RONE_INDEX_TYPES:
        raise ValueError(f"지원하지 않는 지수 유형: {index_type}. 지원: {list(RONE_INDEX_TYPES)}")
    return RONE_INDEX_TYPES[index_type]


def rone_save_name(index_type: str, start_month: str, end_month: str, page: int) -> str:
    """저장 이름: ``rone/<지수 유형>-<시작월>-<종료월>-p<쪽>.json`` (질의를 가르는 인자를 모두 싣는다)."""
    return f"rone/{index_type}-{start_month}-{end_month}-p{page}.json"


def build_rone_call(index_type: str, start_month: str, end_month: str, page: int) -> dict[str, Any]:
    """한 쪽을 받는 호출 — batch ``calls`` 한 칸 형태. 단독 호출은 ``args`` 만 쓴다."""
    info = _index_info(index_type)
    start, end = rone_period_range(index_type, start_month, end_month)
    return {
        "id": f"{index_type}-{start_month}-{end_month}-p{page}",
        "tool": "http_request",
        "args": {
            "url": RONE_BASE_URL,
            "params": {
                "KEY": RONE_SECRET,
                "Type": "json",
                "pIndex": str(page),
                "pSize": str(RONE_PAGE_SIZE),
                "STATBL_ID": info["statbl_id"],
                "DTACYCLE_CD": info["cycle"],
                "START_WRTTIME": start,
                "END_WRTTIME": end,
            },
            "timeout_sec": CALL_TIMEOUT_SEC,
            "save_as": rone_save_name(index_type, start_month, end_month, page),
        },
    }


def rone_plan(index_type: str, start_month: str, end_month: str) -> dict[str, Any]:
    """1쪽을 받는 호출 계획. 2쪽 이후는 collect 가 ``list_total_count`` 를 보고 ``next_calls`` 로 알려 준다."""
    info = _index_info(index_type)
    start, end = rone_period_range(index_type, start_month, end_month)
    return {
        "status": "ok",
        "index_type": index_type,
        "label": info["label"],
        "statbl_id": info["statbl_id"],
        "cycle": info["cycle"],
        "start_month": start_month,
        "end_month": end_month,
        "start_wrttime": start,
        "end_wrttime": end,
        "page_size": RONE_PAGE_SIZE,
        "calls": [build_rone_call(index_type, start_month, end_month, 1)],
    }


def write_plans(path: str | Path, calls: list[dict[str, Any]]) -> list[str]:
    """itda-hyve batch ``plan_file`` 을 쓴다 — 40개 단위로 나눈다(넘으면 batch 가 하나도 실행하지 않는다).

    40개 이하면 ``path`` 하나, 넘으면 ``<이름>a.json``·``<이름>b.json``… 을 쓴다. ``save_dir`` 는 넣지 않는다 —
    batch 호출 인자로 준다. 쓴 경로 목록을 돌려준다.
    """
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    chunks = [calls[i:i + BATCH_LIMIT] for i in range(0, len(calls), BATCH_LIMIT)] or [[]]
    if len(chunks) > 26:
        raise ValueError(f"호출이 {len(calls)}개라 계획 파일이 26개를 넘는다 — 기간을 나눠 받는다")
    targets = [out] if len(chunks) == 1 else [
        out.with_name(f"{out.stem}{chr(ord('a') + i)}{out.suffix}") for i in range(len(chunks))
    ]
    written = []
    for target, chunk in zip(targets, chunks):
        target.write_text(json.dumps({"calls": chunk, "timeout_sec": CALL_TIMEOUT_SEC},
                                     ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written.append(str(target))
    return written


# ---------------------------------------------------------------------------
# 응답 파일
# ---------------------------------------------------------------------------

def _raise_rone_error(body: bytes, path: Path) -> None:
    """본문이 최상위 ``{"RESULT": …}`` 오류면 PriceStatsAPIError. ``INFO-200``(데이터 없음)이나 다른 형태면 돌아온다."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if isinstance(data, dict) and isinstance(data.get("RESULT"), dict):
        _check_code(data["RESULT"], path)


def _check_code(result: dict[str, Any], path: Path) -> str:
    code = str(result.get("CODE", "")).strip()
    if code in ("INFO-000", "INFO-200"):
        return code
    raise PriceStatsAPIError(
        f"R-ONE 오류 ({code}, {result.get('MESSAGE', '')}): "
        f"{_RONE_HINTS.get(code, '요청 파라미터를 확인')} ({path.name})",
        error_code=code or None,
    )


def _read_body(path: Path) -> bytes:
    """입력 파일에서 응답 본문을 꺼낸다 — hyve 층 판독은 공용 ``hyve_input`` 이 한다.

    HTTP 오류면 본문의 R-ONE 메시지 코드를 먼저 본다(그쪽이 더 구체적이다).
    """
    try:
        return read_input(path).data
    except HyveHTTPError as exc:
        _raise_rone_error(exc.body, path)
        raise InputFileError(str(exc), kind=exc.kind) from exc
    except HyveInputError as exc:
        raise InputFileError(str(exc), kind=exc.kind) from exc


def parse_rone_page(path: str | Path) -> dict[str, Any]:
    """저장된 응답 한 쪽을 읽는다.

    Returns:
        ``{"total_count": N, "rows": [...], "code": "INFO-000"|"INFO-200"}``
    Raises:
        InputFileError, PriceStatsAPIError
    """
    p = Path(path).expanduser()
    body = _read_body(p)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputFileError(
            f"JSON 이 아닙니다 — 본문이 잘렸거나 R-ONE 응답이 아닙니다({p.name}): {exc}"
        ) from exc

    if isinstance(data, dict) and isinstance(data.get("RESULT"), dict):
        code = _check_code(data["RESULT"], p)  # INFO-200 만 돌아온다
        return {"total_count": 0, "rows": [], "code": code}

    blocks = data.get("SttsApiTblData") if isinstance(data, dict) else None
    if not isinstance(blocks, list):
        raise InputFileError(f"R-ONE 통계 조회 응답 형태가 아닙니다(SttsApiTblData 없음, {p.name})")

    head: list[Any] = []
    rows: list[Any] = []
    for block in blocks:
        if isinstance(block, dict) and isinstance(block.get("head"), list):
            head = block["head"]
        if isinstance(block, dict) and isinstance(block.get("row"), list):
            rows = block["row"]

    total = None
    result = None
    for item in head:
        if isinstance(item, dict) and "list_total_count" in item:
            total = item["list_total_count"]
        if isinstance(item, dict) and isinstance(item.get("RESULT"), dict):
            result = item["RESULT"]
    if result is None:
        raise InputFileError(f"R-ONE 응답에 RESULT 가 없습니다({p.name})")
    code = _check_code(result, p)
    if code == "INFO-200":
        return {"total_count": 0, "rows": [], "code": code}
    # 분모가 없으면 받은 행 수를 분모로 삼아 조용히 ok 가 된다 — 없으면 실패로 둔다.
    try:
        total_count = int(total)
    except (TypeError, ValueError) as exc:
        raise InputFileError(f"R-ONE 응답에 list_total_count 가 없습니다({p.name})") from exc
    return {"total_count": total_count, "rows": [r for r in rows if isinstance(r, dict)], "code": code}


def _query_of(path: str) -> tuple[str, str, str, int]:
    m = _NAME_RE.search(Path(path).name)
    if not m:
        raise InputFileError(
            f"파일 이름이 규칙(<지수 유형>-<시작월 YYYYMM>-<종료월 YYYYMM>-p<쪽>.json)과 다릅니다: "
            f"{Path(path).name} — rone-plan 이 준 save_as 를 그대로 쓰세요"
        )
    return m.group(1), m.group(2), m.group(3), int(m.group(4))


def _row_key(row: dict[str, Any]) -> tuple:
    return tuple(str(row.get(k)) for k in ("WRTTIME_IDTFR_ID", "GRP_ID", "CLS_ID", "ITM_ID"))


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _match_region(row: dict[str, Any], region: str) -> bool:
    name = str(row.get("CLS_NM") or "")
    if region == "전국":
        return name == "전국"
    return region in str(row.get("CLS_FULLNM") or "") or region in name


PERIOD_RULE_WK = "주간: WRTTIME_DESC(그 주 월요일)가 시작월 1일~종료월 말일 안인 주만 남긴다"
PERIOD_RULE_MM = "월간: WRTTIME_IDTFR_ID(YYYYMM)가 시작월~종료월 안이어야 한다(밖이면 input 오류)"


# 기간 끝 뒤 이만큼 지났으면 그다음 주는 공표됐다고 본다 — 주간 동향은 조사기준일(월요일) 며칠 뒤 공표된다.
END_PUBLISH_GRACE = timedelta(days=14)


def _filter_period(rows: list[dict[str, Any]], cycle: str, start_month: str, end_month: str,
                   today: date | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """본문 행의 시점을 요청 기간과 대조한다.

    주간은 요청 창을 앞뒤로 한 주씩 넓혀 받으므로(:func:`rone_period_range`) 창 밖 행이 오는 것이 정상이다 —
    ``WRTTIME_DESC``(그 주 월요일)가 요청 기간 안인 주만 남기고, 거른 행 수를 사유별로 센다. 요청 기간의 월요일 중
    결과에 없는 주가 있으면(가장 늦게 공표된 주까지) 경고한다 — 이것은 **안쪽** 결손만 본다. 기간 **끝** 결손(넓힌 창의
    끝이 모자라 마지막 주와 그 뒤 주가 함께 빠짐)은 ``dropped_after == 0`` 으로 본다: 창이 충분했다면 기간 뒤 한 주가
    반드시 잘려 나온다. 기간 끝에서 ``END_PUBLISH_GRACE`` 가 지나지 않았으면(그 주가 아직 미공표일 수 있다) 경고하지 않는다.
    월간은 요청 그대로 받으므로 기간 밖 행은 다른 질의의 응답이다 — ``input`` 오류.
    """
    period_from, period_to = month_span(start_month, end_month)
    kept: list[dict[str, Any]] = []
    before = after = 0
    warnings: list[str] = []
    if cycle != "WK":
        for r in rows:
            pid = str(r.get("WRTTIME_IDTFR_ID") or "")
            if not start_month <= pid <= end_month:
                raise InputFileError(
                    f"본문 행의 시점({pid or '없음'})이 요청 기간 {start_month}~{end_month} 밖입니다 — "
                    "다른 질의의 응답이 이 이름으로 저장됐습니다"
                )
            kept.append(r)
        rule = PERIOD_RULE_MM
    else:
        mondays_seen: set[date] = set()
        for r in rows:
            desc = str(r.get("WRTTIME_DESC") or "")
            try:
                monday = date.fromisoformat(desc[:10])
            except ValueError as exc:
                raise InputFileError(
                    f"주간 행의 WRTTIME_DESC({desc or '없음'}, 시점 {r.get('WRTTIME_IDTFR_ID')})를 날짜로 읽을 수 없어 "
                    "요청 기간에 드는지 가를 수 없습니다"
                ) from exc
            if monday < period_from:
                before += 1
            elif monday > period_to:
                after += 1
            else:
                kept.append(r)
                mondays_seen.add(monday)
        rule = PERIOD_RULE_WK
        if mondays_seen:
            latest = max(mondays_seen)
            first = period_from + timedelta(days=(7 - period_from.weekday()) % 7)
            expected = [first + timedelta(weeks=i) for i in range((latest - first).days // 7 + 1)]
            missing = [d.isoformat() for d in expected if d not in mondays_seen]
            if missing:
                warnings.append(
                    f"요청 기간의 주 중 결과에 없는 주(월요일) {len(missing)}개: {missing[:10]} — "
                    "R-ONE 이 그 주를 공표하지 않았거나 요청 창이 모자랐습니다"
                )
            today = today or date.today()
            if after == 0 and today >= period_to + END_PUBLISH_GRACE:
                last_monday = period_to - timedelta(days=period_to.weekday())
                warnings.append(
                    f"기간 뒤 주가 한 행도 오지 않았습니다(dropped_after 0) — 요청 창 끝이 모자랐을 수 있습니다. "
                    f"기간 마지막 주({last_monday.isoformat()})가 결과({latest.isoformat()}까지)에 있는지 확인하세요"
                )
        elif rows:
            warnings.append(
                f"받은 {len(rows)}행 중 요청 기간({period_from}~{period_to})에 드는 주가 없습니다"
            )
    return kept, {
        "rule": rule,
        "from": period_from.isoformat(),
        "to": period_to.isoformat(),
        "kept": len(kept),
        "dropped_before": before,
        "dropped_after": after,
    }, warnings


def collect_rone(paths: list[str], max_pages: int = RONE_MAX_PAGES,
                 region: str | None = None, today: date | None = None) -> dict[str, Any]:
    """저장된 쪽 파일들을 전량 대조하고 행을 정리한다.

    대조 축(하나라도 어긋나면 결과를 내지 않는다):
      - 한 번에 한 질의(이름의 지수 유형·시작월·종료월)만 — 섞이면 ``input``
      - 모든 쪽의 ``list_total_count`` 가 같다 — 다르면 ``input``. R-ONE 은 확정 기간의 공표 통계라
        받는 사이 건수가 바뀌지 않는다고 본다(바뀌었다면 공표 순간에 걸친 것 — 1쪽부터 다시 받는다)
      - 같은 쪽이 두 번 들어오지 않는다 · 필요한 쪽 1..min(need, max_pages) 가 빈틈없이 있다
      - 마지막이 아닌 쪽은 정확히 1,000행, 마지막 쪽은 나머지 행이다(sample 키·pSize 변조를 잡는다)
      - 본문의 STATBL_ID·DTACYCLE_CD 가 이름의 지수 유형과 같다 · 행 키가 겹치지 않는다
    전량 대조를 마친 뒤 행 시점을 요청 기간과 대조한다(:func:`_filter_period` — 주간은 거르고 ``period_filter`` 에
    거른 수를 싣는다, 월간은 기간 밖이면 ``input``).
    쪽이 모자라면 :class:`IncompleteError` (``next_calls``·``need_pages``·``will_truncate``).
    """
    if not paths:
        raise InputFileError("입력 파일이 없습니다")
    max_pages = max(1, max_pages)
    queries: set[tuple[str, str, str]] = set()
    pages: dict[int, dict[str, Any]] = {}
    sources = []
    for p in paths:
        index_type, start, end, page = _query_of(p)
        queries.add((index_type, start, end))
        if len(queries) > 1:
            raise InputFileError(
                f"다른 질의의 파일이 섞였습니다({sorted(queries)}) — 한 번에 한 질의(지수 유형·기간)만 넘기세요"
            )
        if page in pages:
            raise InputFileError(f"같은 쪽이 두 번 들어왔습니다(p{page}: {Path(p).name})")
        parsed = parse_rone_page(p)
        pages[page] = parsed
        sources.append({"path": str(Path(p).expanduser()), "page": page,
                        "total_count": parsed["total_count"], "row_count": len(parsed["rows"])})

    index_type, start_month, end_month = queries.pop()
    info = _index_info(index_type)
    totals = {pp["total_count"] for pp in pages.values()}
    if len(totals) > 1:
        raise InputFileError(
            f"쪽마다 list_total_count 가 다릅니다({sorted(totals)}) — 받는 사이 통계가 공표됐거나 다른 질의의 "
            "응답입니다. 이 질의를 1쪽부터 새 하위 폴더에 다시 받으세요"
        )
    total = totals.pop()
    need = math.ceil(total / RONE_PAGE_SIZE) if total else 1
    upto = min(need, max_pages)
    will_truncate = need > max_pages

    extra = sorted(n for n in pages if n > upto)
    if extra:
        raise InputFileError(
            f"필요한 쪽(1~{upto})을 넘는 쪽이 들어왔습니다({extra}) — list_total_count={total} 기준"
        )
    missing = [n for n in range(1, upto + 1) if n not in pages]
    if missing:
        next_calls = [build_rone_call(index_type, start_month, end_month, n) for n in missing]
        raise IncompleteError(
            f"{index_type} {start_month}~{end_month}: list_total_count={total} → 필요한 쪽 {need}"
            f"(상한 {max_pages}), 받은 쪽 {sorted(pages)} → 더 받을 쪽 {missing}",
            next_calls, need, will_truncate, total,
        )

    for n, pp in sorted(pages.items()):
        expected = RONE_PAGE_SIZE if n < need else total - (need - 1) * RONE_PAGE_SIZE
        got = len(pp["rows"])
        if got != expected:
            raise InputFileError(
                f"p{n} 행 수가 {got} 인데 {expected} 여야 합니다(list_total_count={total}, 쪽당 {RONE_PAGE_SIZE}) — "
                "pSize 를 바꿨거나 인증키 없이(sample, 5행) 받은 응답입니다. rone-plan 의 호출을 그대로 쓰세요"
            )
        for row in pp["rows"]:
            if (str(row.get("STATBL_ID")) != info["statbl_id"]
                    or str(row.get("DTACYCLE_CD")) != info["cycle"]):
                raise InputFileError(
                    f"p{n} 본문의 통계표({row.get('STATBL_ID')}/{row.get('DTACYCLE_CD')})가 이름의 지수 유형 "
                    f"{index_type}({info['statbl_id']}/{info['cycle']})과 다릅니다"
                )

    raw_rows = [r for _, pp in sorted(pages.items()) for r in pp["rows"]]
    dup = sum(c - 1 for c in Counter(_row_key(r) for r in raw_rows).values() if c > 1)
    if dup:
        raise InputFileError(
            f"쪽 사이에 같은 행이 {dup}개 겹칩니다 — 받는 사이 순서가 바뀌었습니다. 1쪽부터 새 하위 폴더에 다시 받으세요"
        )

    warnings: list[str] = []
    if will_truncate:
        warnings.append(
            f"전체 {total}행 중 {upto * RONE_PAGE_SIZE}행까지만 받았습니다(상한 {max_pages}쪽) — "
            "기간을 좁히거나 --max-pages 를 늘려 쪽을 더 받으세요"
        )
    in_period, period_filter, period_warnings = _filter_period(raw_rows, info["cycle"], start_month, end_month, today)
    warnings.extend(period_warnings)
    selected = in_period
    if region:
        selected = [r for r in in_period if _match_region(r, region)]
        if not selected:
            warnings.append(
                f"지역 '{region}' 에 맞는 행이 없습니다 — 지역 이름은 R-ONE 분류 전체명(예: 서울>강남지역>동남권>강남구)과 대조합니다"
            )
    results = [{
        "index_type": index_type,
        "period": str(r.get("WRTTIME_IDTFR_ID") or ""),
        "period_desc": str(r.get("WRTTIME_DESC") or ""),
        "region": str(r.get("CLS_FULLNM") or r.get("CLS_NM") or ""),
        "region_code": r.get("CLS_ID"),
        "item": str(r.get("ITM_NM") or ""),
        "value": _to_float(r.get("DTA_VAL")),
        "unit": str(r.get("UI_NM") or ""),
    } for r in selected]
    results.sort(key=lambda x: (x["period"], x["region"], x["item"]))

    start, end = rone_period_range(index_type, start_month, end_month)
    return {
        "index_type": index_type,
        "label": info["label"],
        "statbl_id": info["statbl_id"],
        "cycle": info["cycle"],
        "start_month": start_month,
        "end_month": end_month,
        "start_wrttime": start,
        "end_wrttime": end,
        "total_count": total,
        "scanned_count": len(raw_rows),
        "period_filter": period_filter,
        "need_pages": need,
        "truncated": will_truncate,
        "region": region or "",
        "results": results,
        "sources": sources,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 공개 API — realty-deals 파생 통계 (R20)
# ---------------------------------------------------------------------------

def derive_stats_from_deals(
    items: list[dict[str, Any]],
    amount_field: str = "deal_amount",
    group_by: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """realty-deals raw 데이터에서 파생 통계를 산출한다.

    compute_summary 포팅 (realestate_api.py 498-529, data_go_client.py).
    정규화된 deal_amount 필드 기준으로 통계를 산출한다.

    Args:
        items:        normalize_trade_item() 정규화 항목 리스트.
        amount_field: 금액 필드명 (기본: "deal_amount").
        group_by:     그룹핑 기준 필드 (예: "apt_nm"). None이면 전체 통계.

    Returns:
        group_by=None: {"avg": N, "median": N, "max": N, "min": N, "count": N}
        group_by=field: {그룹값: 통계 dict, ...}
    """
    if group_by is not None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            key = str(item.get(group_by, ""))
            groups.setdefault(key, []).append(item)
        return {
            k: _compute_stats_from_list(v, amount_field)
            for k, v in groups.items()
        }

    return _compute_stats_from_list(items, amount_field)


def _compute_stats_from_list(
    items: list[dict[str, Any]],
    amount_field: str,
) -> dict[str, Any]:
    """항목 리스트에서 기술 통계를 계산한다."""
    if not items:
        return {"avg": 0, "median": 0, "max": 0, "min": 0, "count": 0}

    amounts = sorted(
        int(item.get(amount_field, 0) or 0)
        for item in items
    )
    n = len(amounts)
    total = sum(amounts)
    avg = total // n if n else 0

    mid = n // 2
    if n % 2 == 1:
        median = amounts[mid]
    else:
        median = (amounts[mid - 1] + amounts[mid]) // 2

    return {
        "avg": avg,
        "median": median,
        "max": amounts[-1],
        "min": amounts[0],
        "count": n,
    }


# ---------------------------------------------------------------------------
# JSON envelope
# ---------------------------------------------------------------------------

def build_stats_envelope(
    status: str,
    items: list[dict[str, Any]],
    *,
    derived_summary: dict[str, Any] | None = None,
    error: str | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """가격통계 JSON envelope 생성.

    Args:
        status:          "ok" 또는 에러 상태.
        items:           R-ONE 지수 항목 리스트.
        derived_summary: realty-deals 파생 통계 (선택).
        error:           에러 코드 (선택).
        detail:          에러 상세 (선택).
        **extra:         추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "count": len(items),
        "results": items,
    }

    if derived_summary is not None:
        env["derived_summary"] = derived_summary

    if error is not None:
        env["error"] = error
    if detail is not None:
        env["detail"] = detail

    env.update(extra)
    return env
