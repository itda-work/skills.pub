#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xotelo.py - Xotelo API(트립어드바이저 메타서치) 클라이언트 — 순수 표준 라이브러리.

Xotelo(https://xotelo.com/)는 TripAdvisor 메타서치를 감싼 무료 JSON API 다.
`data.xotelo.com/api/rates` 가 hotel_key + 날짜 + 통화로 **여러 OTA(Booking·Agoda·
Trip.com·공식사이트)의 실시간 요금을 한 번에**, **API 키 없이** 반환한다. 브라우저·MCP
없이 `urllib` 로 직접 호출된다(라이브 실측 확인, #1013) — 이 스킬이 hyve web_browse 의존을
벗고 standalone 이 되는 근거다.

## 엔드포인트 (무료 data.xotelo.com — 실측 확인 2026-07-09, #1013)

- `/rates`   hotel_key,chk_in,chk_out,currency[,adults,rooms] → OTA별 {code,name,rate,tax}
             `rate` = 그 OTA 최저 예약가능 객실의 **1박 평균가**(객실 타입 구분 없음).
- `/heatmap` hotel_key,chk_out → 싼날/평균/비싼날 달력.
- `/list`    무료 티어 사실상 폐기(유효 geo 로도 400). 미사용.
- `/search`  RapidAPI(유료 키) 전용(401). 미사용 — 이름→hotel_key 해소는 에이전트
             web_search 또는 사용자 URL 직접입력으로 처리(SKILL.md).

## 제약
- KRW 미지원(허용 14종: USD·GBP·EUR·CAD·CHF·AUD·JPY·CNY·INR·THB·BRL·HKD·RUB·BZD).
  → USD 등으로 수집 후 fx.py 로 원화 환산 표시(#1013 결정).
- OTA 노출 개수는 호텔·날짜별 편차(1~4개). tax 는 대부분 null.
- 출처가 TripAdvisor 메타값 — 실제 예약가와 다를 수 있음(data-accuracy).
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from errors import ArgsError, HotelSearchError, NoResultError

API_RATES = "https://data.xotelo.com/api/rates"
API_HEATMAP = "https://data.xotelo.com/api/heatmap"

# Xotelo /rates 허용 통화(실측 — KRW 없음).
SUPPORTED_CURRENCIES = frozenset(
    {"USD", "GBP", "EUR", "CAD", "CHF", "AUD", "JPY", "CNY", "INR", "THB", "BRL", "HKD", "RUB", "BZD"}
)

# TripAdvisor hotel_key: geo(g숫자) + hotel(d숫자). URL·순수키 양쪽에서 추출.
#   Hotel_Review-g294197-d5250436-Reviews-Summit_Hotel_Seoul...  → g294197-d5250436
#   g294197-d5250436                                             → g294197-d5250436
_HOTEL_KEY_RE = re.compile(r"g(\d+)-d(\d+)")

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 hotel-search/1.0"
_TIMEOUT = 30


def extract_hotel_key(text: str) -> str:
    """TripAdvisor URL 또는 순수 키 문자열에서 hotel_key(`g<geo>-d<hotel>`)를 추출한다.

    에이전트 web_search 해소 경로(URL 확보)와 사용자 URL/키 직접입력 경로 공용.
    실패 시 조용히 넘기지 않고 ArgsError 로 표면화한다(no-silent-fallback).
    """
    if not text or not isinstance(text, str):
        raise ArgsError("hotel_key 또는 TripAdvisor URL 이 필요합니다")
    m = _HOTEL_KEY_RE.search(text)
    if not m:
        raise ArgsError(
            f"hotel_key(g<geo>-d<hotel>)를 찾지 못했습니다: {text!r} "
            "— TripAdvisor 호텔 페이지 URL 이나 g294197-d5250436 형식을 주세요"
        )
    return f"g{m.group(1)}-d{m.group(2)}"


def validate_currency(currency: str) -> str:
    """Xotelo 지원 통화인지 검증하고 대문자로 정규화한다. KRW 등 미지원은 ArgsError."""
    cur = (currency or "").upper()
    if cur not in SUPPORTED_CURRENCIES:
        raise ArgsError(
            f"Xotelo 미지원 수집 통화: {currency!r} (KRW 미지원). "
            f"지원: {', '.join(sorted(SUPPORTED_CURRENCIES))} — 원화는 수집 후 환산 표시됩니다"
        )
    return cur


def fetch_json(url: str) -> dict:
    """URL 을 GET 해 JSON 을 dict 로 반환한다(네트워크 경계 — 테스트가 monkeypatch).

    Xotelo 는 파라미터 오류도 HTTP 200 + 본문 error 객체로 주는 경우가 많으나,
    4xx 로 오는 경우도 있어 HTTPError 본문의 error JSON 도 회수한다.
    """
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=_TIMEOUT) as r:
            body = r.read()
    except HTTPError as e:  # 4xx/5xx — 본문에 error JSON 이 있을 수 있음
        raw = e.read()
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            raise HotelSearchError(f"Xotelo HTTP {e.code}: {raw[:200]!r}")
    except URLError as e:
        raise HotelSearchError(f"Xotelo 연결 실패: {e.reason}")
    try:
        return json.loads(body)
    except ValueError:
        raise HotelSearchError("Xotelo 응답이 JSON 이 아닙니다")


def _result_or_raise(envelope: dict) -> dict:
    """Xotelo 응답 봉투에서 result 를 꺼낸다. error 객체는 조용히 삼키지 않고 표면화한다."""
    if not isinstance(envelope, dict):
        raise HotelSearchError("Xotelo 응답이 객체가 아닙니다")
    err = envelope.get("error")
    if err:
        code = err.get("status_code") if isinstance(err, dict) else None
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        if code == 400:
            raise ArgsError(f"Xotelo 요청 오류(400): {msg}")
        raise HotelSearchError(f"Xotelo 오류({code}): {msg}")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise NoResultError("Xotelo 응답에 result 가 없습니다")
    return result


def fetch_rates(
    hotel_key: str,
    chk_in: str,
    chk_out: str,
    currency: str = "USD",
    adults: int | None = None,
    rooms: int | None = None,
) -> dict:
    """/rates 를 호출해 result dict({chk_in,chk_out,currency,rates:[...]})를 반환한다."""
    params = {"hotel_key": hotel_key, "chk_in": chk_in, "chk_out": chk_out, "currency": currency}
    if adults:
        params["adults"] = adults
    if rooms:
        params["rooms"] = rooms
    return _result_or_raise(fetch_json(f"{API_RATES}?{urlencode(params)}"))


def fetch_heatmap(hotel_key: str, chk_out: str) -> dict:
    """/heatmap 을 호출해 result dict({chk_out, heatmap:{...}})를 반환한다."""
    params = {"hotel_key": hotel_key, "chk_out": chk_out}
    return _result_or_raise(fetch_json(f"{API_HEATMAP}?{urlencode(params)}"))


def parse_rates(result: dict, *, nights: int, fx_rate: float | None = None) -> tuple[list[dict], str]:
    """/rates result 를 OTA offer 리스트 + 수집 통화로 정제한다(1박가 오름차순).

    Xotelo `rate` = 1박 평균가 → total = rate × nights.
    fx_rate(수집통화 1단위당 KRW) 주면 원화 환산 필드를 채운다.
    """
    currency = result.get("currency", "")
    offers: list[dict] = []
    for r in result.get("rates") or []:
        if not isinstance(r, dict):
            continue
        rate = r.get("rate")
        if rate is None:
            continue
        try:
            per_night = float(rate)
        except (TypeError, ValueError):
            continue
        total = per_night * nights
        offers.append(
            {
                "ota_code": r.get("code"),
                "ota_name": r.get("name") or r.get("code"),
                "per_night": round(per_night),
                "total": round(total),
                "tax": r.get("tax"),
                "per_night_krw": round(per_night * fx_rate) if fx_rate else None,
                "total_krw": round(total * fx_rate) if fx_rate else None,
            }
        )
    offers.sort(key=lambda o: o["per_night"])
    return offers, currency


def parse_heatmap(result: dict) -> dict:
    """/heatmap result 를 {chk_out, cheap_days, average_days, high_days} 로 정제한다."""
    hm = result.get("heatmap") or {}
    return {
        "chk_out": result.get("chk_out"),
        "cheap_days": list(hm.get("cheap_price_days") or []),
        "average_days": list(hm.get("average_price_days") or []),
        "high_days": list(hm.get("high_price_days") or []),
    }
