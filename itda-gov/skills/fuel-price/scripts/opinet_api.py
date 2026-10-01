"""오피넷 Open API (선택 경로 — itda-hyve 시크릿 `OPINET_API_KEY`). 네트워크 없음.

요청은 itda-hyve ``http_request`` 가 보낸다. 키는 ``params`` 의 ``{{secret:OPINET_API_KEY}}`` 자리표시자로만
가리킨다 — 스크립트는 키를 보지 않는다(itda-work/skills#45). 이 모듈은 호출 인자를 만들고 저장된 응답을 판독한다.

무료 일반 API: 오피넷 회원가입 → 유가정보 API → 키 즉시 자동 발급, 300회/일.
문서: https://www.opinet.co.kr/user/custapi/custApiInfo.do

⚠️ 실측(2026-09-02): 키가 없거나 틀려도 HTTP 200 + ``{"RESULT":{"OIL":[]}}`` **빈 배열**이
돌아온다 — 에러가 아니라 조용히 빈다. 그래서 빈 배열은 "데이터 없음"이 아니라 **키 오류 신호**로
표면화한다(no-silent-fallback).

지원: 최근 7일 전국 일별(avgRecentPrice) · 최근 7일 시도 일별(areaAvgRecentPrice).
월간 평균은 API 에 없다 — 웹 통계 경로(opinet_web) 가 정본.
"""
from __future__ import annotations

import datetime as _dt
import json
import re

from hyve_input import snippet
from opinet_web import PRODUCTS, SIDO_BY_CODE, OpinetWebError

API_BASE = "https://www.opinet.co.kr/api"
KEY_VAR = "OPINET_API_KEY"
KEY_PLACEHOLDER = "{{secret:" + KEY_VAR + "}}"

KEY_GUIDE = (
    "오피넷 API 키는 itda-hyve GUI 시크릿 탭에 OPINET_API_KEY 로 등록한다 "
    "(발급: https://www.opinet.co.kr/user/custapi/custApiInfo.do 하단 「일반 API 이용 신청」, 무료·즉시). "
    "키 없이 쓰려면 기본 웹 경로(--source web)."
)


class OpinetApiError(OpinetWebError):
    """Open API 응답 판정 실패."""


def endpoint_for(region_code: str | None) -> str:
    return "avgRecentPrice" if region_code is None else "areaAvgRecentPrice"


def call_params(region_code: str | None, prodcd: str) -> dict[str, str]:
    """``http_request`` 의 ``params`` — 키는 자리표시자로만(URL 쿼리 문자열에 쓰지 않는다)."""
    params = {"out": "json", "code": KEY_PLACEHOLDER}
    if region_code is not None:
        params["area"] = region_code
    params["prodcd"] = prodcd
    return params


_CODE_IN_TEXT = re.compile(r"(?<![A-Za-z0-9_])(code=)[^&\s\"'<>]*", re.IGNORECASE)


def _excerpt(raw: str) -> str:
    """오류 메시지용 본문 발췌 — 공용 가림(키 이름들)에 더해 오피넷 키 파라미터 ``code=`` 도 가린다."""
    return snippet(_CODE_IN_TEXT.sub(lambda m: m.group(1) + "••••", raw).encode("utf-8"), 120)


def parse_oil_array(raw: str, endpoint: str = "") -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise OpinetApiError(f"오피넷 API 응답이 JSON 이 아닙니다 ({endpoint}): {_excerpt(raw)}") from e
    if not isinstance(data, dict):
        raise OpinetApiError(f"오피넷 API 응답 구조가 예상과 다릅니다 ({endpoint}): {_excerpt(raw)}")
    oil = (data.get("RESULT") or {}).get("OIL")
    if not isinstance(oil, list):
        raise OpinetApiError(f"오피넷 API 응답 구조가 예상과 다릅니다 ({endpoint}): {_excerpt(raw)}")
    if not oil:
        raise OpinetApiError(
            f"오피넷 API 가 빈 결과를 돌려줬습니다 ({endpoint}). "
            "키가 없거나 잘못됐을 때 오피넷은 에러 대신 빈 배열을 반환합니다 — " + KEY_GUIDE
        )
    if not all(isinstance(r, dict) for r in oil):
        raise OpinetApiError(f"오피넷 API 응답 행이 객체가 아닙니다 ({endpoint})")
    return oil


def _row_date(r: dict) -> _dt.date:
    d = str(r.get("DATE") or "")
    try:
        if len(d) != 8 or not d.isdigit():
            raise ValueError
        return _dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    except ValueError:
        raise OpinetApiError(f"응답 행의 DATE 가 YYYYMMDD 가 아닙니다: {d!r}") from None


def check_rows(rows: list[dict], *, region_code: str | None, prodcd: str) -> None:
    """행의 제품·지역·날짜가 요청과 명세에 맞는지 — 다른 질의의 응답·빠진 필드·빈 날짜를 막는다.

    명세(Opinet_API_Free.pdf): 전국 ④ ``{DATE, PRODCD, PRICE}`` · 시도 ⑥ ``{DATE, AREA_CD, AREA_NM, PRODCD, PRICE}``.
    필드가 없으면 요청값으로 채워 보지 않는다(없는 것을 맞다고 하지 않는다).
    """
    for r in rows:
        if "PRODCD" not in r:
            raise OpinetApiError("응답 행에 PRODCD 가 없습니다 — 명세와 다른 응답입니다")
        if str(r["PRODCD"]) != prodcd:
            raise OpinetApiError(f"응답 제품코드({r['PRODCD']})가 요청({prodcd})과 다릅니다")
        if region_code is not None:
            if "AREA_CD" not in r:
                raise OpinetApiError("응답 행에 AREA_CD 가 없습니다 — 명세와 다른 응답입니다")
            if str(r["AREA_CD"]) != region_code:
                raise OpinetApiError(f"응답 지역코드({r['AREA_CD']})가 요청({region_code})과 다릅니다")
    dates = sorted(_row_date(r) for r in rows)
    if len(set(dates)) != len(dates):
        raise OpinetApiError("응답에 같은 날짜 행이 두 번 있습니다 — 다른 질의의 응답이 섞였습니다")
    gaps = [f"{a:%Y-%m-%d}→{b:%Y-%m-%d}" for a, b in zip(dates, dates[1:]) if (b - a).days != 1]
    if gaps:
        raise OpinetApiError("응답 날짜가 하루씩 이어지지 않습니다: " + ", ".join(gaps))


def latest_date(rows: list[dict]) -> _dt.date:
    return max(_row_date(r) for r in rows)


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _date_label(d: str) -> str:
    d = str(d)
    return f"{d[:4]}년{d[4:6]}월{d[6:8]}일" if len(d) == 8 and d.isdigit() else d


def rows_to_series(rows: list[dict]) -> list[tuple[str, float | None]]:
    """DATE 오름차순 (기간 라벨, 가격) — 웹 경로와 같은 라벨 형식(YYYY년MM월DD일)."""
    rows = sorted(rows, key=lambda r: str(r.get("DATE") or ""))
    return [(_date_label(r.get("DATE", "")), _num(r.get("PRICE"))) for r in rows]


def region_name(region_code: str | None, rows: list[dict]) -> str:
    if region_code is None:
        return "전국"
    return SIDO_BY_CODE.get(region_code) or str(rows[0].get("AREA_NM", region_code))


__all__ = [
    "API_BASE", "KEY_VAR", "KEY_PLACEHOLDER", "OpinetApiError", "PRODUCTS", "endpoint_for", "call_params",
    "parse_oil_array", "check_rows", "latest_date", "rows_to_series", "region_name",
]
