"""오피넷 Open API (선택 경로 — `OPINET_API_KEY` 가 있을 때만).

무료 일반 API: 오피넷 회원가입 → 유가정보 API → 키 즉시 자동 발급, 300회/일.
문서: https://www.opinet.co.kr/user/custapi/custApiInfo.do

⚠️ 실측(2026-09-02): 키가 없거나 틀려도 HTTP 200 + ``{"RESULT":{"OIL":[]}}`` **빈 배열**이
돌아온다 — 에러가 아니라 조용히 빈다. 그래서 빈 배열은 "데이터 없음"이 아니라 **키 오류 신호**로
표면화한다(no-silent-fallback).

지원: 전국 현재가(avgAllPrice) · 시도별 현재가(avgSidoPrice) · 최근 7일 전국 일별(avgRecentPrice).
월간 평균은 API 에 없다 — 웹 통계 경로(opinet_web) 가 정본.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from opinet_web import PRODUCTS, SIDO_BY_CODE, USER_AGENT, OpinetWebError

API_BASE = "https://www.opinet.co.kr/api"
KEY_VAR = "OPINET_API_KEY"
TIMEOUT_SEC = 30

SETUP_GUIDE = (
    "OPINET_API_KEY 가 설정되지 않았습니다.\n\n"
    "오피넷 무료 API 키 발급 (즉시 자동 승인):\n"
    "  1. https://www.opinet.co.kr/user/custapi/custApiInfo.do 접속\n"
    "  2. 페이지 아래 「일반 API 이용 신청」 (회원가입 필요 · 일반 API 300회/일)\n\n"
    "설정: 작업 폴더 루트 .env 에 한 줄 —  OPINET_API_KEY=발급받은_키\n"
    "키가 없어도 기본 경로(웹 통계, --source web)는 그대로 동작합니다."
)


class OpinetApiError(OpinetWebError):
    """Open API 경로 실패."""


def resolve_key(cli_arg: str | None = None) -> str:
    """CLI 인자 > 환경변수 > (가능하면) 공용 env_loader 순으로 키를 찾는다."""
    if cli_arg:
        return cli_arg
    try:  # publish 시 shared/ 에서 주입되는 공용 로더 (.env·settings.json 탐색)
        import env_loader  # type: ignore

        return env_loader.resolve_api_key(KEY_VAR, None, SETUP_GUIDE)
    except ImportError:
        val = os.environ.get(KEY_VAR)
        if val:
            return val
        raise OpinetApiError(SETUP_GUIDE) from None
    except Exception as e:  # env_loader.MissingAPIKeyError 등
        raise OpinetApiError(str(e)) from e


def _call(endpoint: str, key: str, **params: str) -> list[dict]:
    q = {"out": "json", "code": key, **params}
    url = f"{API_BASE}/{endpoint}.do?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        raise OpinetApiError(f"오피넷 API 접속 실패 ({endpoint}): {e}") from e
    return parse_oil_array(raw, endpoint)


def parse_oil_array(raw: str, endpoint: str = "") -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise OpinetApiError(f"오피넷 API 응답이 JSON 이 아닙니다 ({endpoint}): {raw[:120]!r}") from e
    oil = (data.get("RESULT") or {}).get("OIL")
    if oil is None:
        raise OpinetApiError(f"오피넷 API 응답 구조가 예상과 다릅니다 ({endpoint}): {raw[:120]!r}")
    if not oil:
        raise OpinetApiError(
            f"오피넷 API 가 빈 결과를 돌려줬습니다 ({endpoint}). "
            "키가 없거나 잘못됐을 때 오피넷은 에러 대신 빈 배열을 반환합니다 — "
            "OPINET_API_KEY 를 확인하세요. 키 없이 쓰려면 --source web (기본값)."
        )
    return oil


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def current_national(key: str) -> list[dict]:
    """전국 현재 평균가 — [{TRADE_DT, PRODCD, PRODNM, PRICE, DIFF}]."""
    return _call("avgAllPrice", key)


def current_sido(key: str, sido: str | None = None, prodcd: str | None = None) -> list[dict]:
    params: dict[str, str] = {}
    if sido:
        params["sido"] = sido
    if prodcd:
        params["prodcd"] = prodcd
    return _call("avgSidoPrice", key, **params)


def recent_7days_national(key: str, prodcd: str) -> list[dict]:
    """④ 최근 7일간 전국 일일 평균가격 — [{DATE, PRODCD, PRICE}] (가이드 p.7)."""
    return _call("avgRecentPrice", key, prodcd=prodcd)


def recent_7days_area(key: str, area: str, prodcd: str) -> list[dict]:
    """⑥ 최근 7일간 일일 지역별 평균가격 — [{DATE, AREA_CD, AREA_NM, PRODCD, PRICE}] (가이드 p.9)."""
    return _call("areaAvgRecentPrice", key, area=area, prodcd=prodcd)


def _date_label(d: str) -> str:
    d = str(d)
    return f"{d[:4]}년{d[4:6]}월{d[6:8]}일" if len(d) == 8 and d.isdigit() else d


def rows_to_series(rows: list[dict]) -> list[tuple[str, float | None]]:
    """DATE 오름차순 (기간 라벨, 가격) — 웹 경로와 같은 라벨 형식(YYYY년MM월DD일)."""
    rows = sorted(rows, key=lambda r: str(r.get("DATE") or ""))
    return [(_date_label(r.get("DATE", "")), _num(r.get("PRICE"))) for r in rows]


def series_from_api(key: str, *, region_code: str | None, prodcd: str) -> tuple[str, list[tuple[str, float | None]]]:
    """(지역명, 최근 7일 시계열). 전국=avgRecentPrice, 시도=areaAvgRecentPrice."""
    if region_code is None:
        return "전국", rows_to_series(recent_7days_national(key, prodcd))
    rows = recent_7days_area(key, region_code, prodcd)
    name = SIDO_BY_CODE.get(region_code) or str(rows[0].get("AREA_NM", region_code))
    return name, rows_to_series(rows)


__all__ = [
    "KEY_VAR", "OpinetApiError", "PRODUCTS", "resolve_key", "parse_oil_array",
    "current_national", "current_sido", "recent_7days_national", "recent_7days_area",
    "rows_to_series", "series_from_api",
]
