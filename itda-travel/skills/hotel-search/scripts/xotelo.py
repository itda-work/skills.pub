#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xotelo.py - Xotelo API(트립어드바이저 메타서치) 요청 계획과 응답 판독 — 네트워크 없음.

요청은 itda-hyve ``http_request`` 가 보낸다(itda-work/skills#45 — 규칙 ``cowork-network-via-hyve``).
이 모듈은 부를 호출(``rates_call``·``heatmap_call``)과 저장 이름을 만들고, itda-hyve 가 ``save_as`` 로 저장한
파일을 판독한다(``read_rates``·``read_heatmap``).

## 엔드포인트 (무료 data.xotelo.com — 실측 #1013 2026-07-09 · itda-hyve 2026-10-01)

- `/rates`   hotel_key,chk_in,chk_out,currency[,adults,rooms] → OTA별 {code,name,rate,tax}
             `rate` = 그 OTA 최저 예약가능 객실의 **1박 평균가**(객실 타입 구분 없음).
             응답이 chk_in·chk_out·currency 를 되비친다 → 요청과 대조(다르면 mismatch).
- `/heatmap` hotel_key,chk_out → 싼날/평균/비싼날 달력. chk_out 을 되비친다.
- `/list`·`/search` 는 무료 티어에서 쓸 수 없다(400·401) — 미사용.
- 헤더 없이(범용 UA) 성립한다. robots.txt 는 404(규칙 없음, 2026-10-01).
- hotel_key 는 응답에 없다 → 저장 이름이 식별 계약이다(``plan`` 이 짓고 판독이 대조).

## 제약
- KRW 미지원(허용 14종: USD·GBP·EUR·CAD·CHF·AUD·JPY·CNY·INR·THB·BRL·HKD·RUB·BZD).
  → USD 등으로 수집 후 fx.py 로 원화 환산 표시(#1013 결정).
- OTA 노출 개수는 호텔·날짜별 편차(1~5개). tax 는 대부분 null.
- 출처가 TripAdvisor 메타값 — 실제 예약가와 다를 수 있음(data-accuracy).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from errors import ArgsError, HotelSearchError, NoResultError
from hyve_input import HyveFailure, HyveHTTPError, HyveInputError, HyveReadError, read_input

API_RATES = "https://data.xotelo.com/api/rates"
API_HEATMAP = "https://data.xotelo.com/api/heatmap"
TIMEOUT_SEC = 45  # batch timeout_sec(50)·Cowork 전송 상한(60초)보다 짧게
SAVE_PREFIX = "hotel/"

# Xotelo /rates 허용 통화(실측 — KRW 없음).
SUPPORTED_CURRENCIES = frozenset(
    {"USD", "GBP", "EUR", "CAD", "CHF", "AUD", "JPY", "CNY", "INR", "THB", "BRL", "HKD", "RUB", "BZD"}
)

# TripAdvisor hotel_key: geo(g숫자) + hotel(d숫자). URL·순수키 양쪽에서 추출.
#   Hotel_Review-g294197-d5250436-Reviews-Summit_Hotel_Seoul...  → g294197-d5250436
#   g294197-d5250436                                             → g294197-d5250436
_HOTEL_KEY_RE = re.compile(r"g(\d+)-d(\d+)")
KST = _dt.timezone(_dt.timedelta(hours=9))


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


# ---------------------------------------------------------------------------
# 호출 계획 — 저장 이름이 식별 계약이다(hotel_key·인원·객실은 응답에 없다)
# ---------------------------------------------------------------------------

def _d8(iso: str) -> str:
    return iso.replace("-", "")


def rates_name(hotel_key: str, chk_in: str, chk_out: str, currency: str, adults: int, rooms: int) -> str:
    return f"{SAVE_PREFIX}rates-{hotel_key}-{_d8(chk_in)}-{_d8(chk_out)}-{currency}-a{adults}-r{rooms}.json"


def heatmap_name(hotel_key: str, chk_out: str) -> str:
    return f"{SAVE_PREFIX}heatmap-{hotel_key}-{_d8(chk_out)}.json"


def rates_call(hotel_key: str, chk_in: str, chk_out: str, currency: str, adults: int, rooms: int) -> dict:
    """itda-hyve ``http_request`` 인자 — 옛판 직접 호출과 같은 파라미터(값은 문자열)."""
    return {
        "url": API_RATES,
        "params": {
            "hotel_key": hotel_key, "chk_in": chk_in, "chk_out": chk_out, "currency": currency,
            "adults": str(adults), "rooms": str(rooms),
        },
        "timeout_sec": TIMEOUT_SEC,
        "save_as": rates_name(hotel_key, chk_in, chk_out, currency, adults, rooms),
    }


def heatmap_call(hotel_key: str, chk_out: str) -> dict:
    return {
        "url": API_HEATMAP,
        "params": {"hotel_key": hotel_key, "chk_out": chk_out},
        "timeout_sec": TIMEOUT_SEC,
        "save_as": heatmap_name(hotel_key, chk_out),
    }


# ---------------------------------------------------------------------------
# 판독
# ---------------------------------------------------------------------------

def _load_envelope(path: Path) -> dict:
    """저장 파일 → Xotelo 응답 봉투(dict). hyve 층 실패는 타입 있는 오류로."""
    http_status = None
    try:
        body = read_input(path)
        raw = body.data
    except HyveReadError as exc:
        raise HotelSearchError(
            f"받은 파일이 없습니다: {path.name} — batch 결과를 확인하세요(plan 과 같은 인자인지)",
            kind="not_fetched",
        ) from exc
    except HyveFailure as exc:
        raise HotelSearchError(str(exc), kind="hyve", hyve_code=exc.code) from exc
    except HyveHTTPError as exc:
        # Xotelo 는 파라미터 오류를 4xx + 본문 error JSON 으로 주기도 한다 — 그 사유를 먼저 읽는다
        raw, http_status = exc.body, exc.status
        if not raw:
            raise HotelSearchError(str(exc), kind="http") from exc
    except HyveInputError as exc:
        raise HotelSearchError(str(exc), kind=exc.kind) from exc
    try:
        env = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if http_status is not None:
            # 오류 상태에 JSON 아닌 본문(점검 HTML 등) — 상태를 지우지 않는다
            raise HotelSearchError(
                f"Xotelo 가 HTTP {http_status} 를 JSON 아닌 본문으로 돌려줬습니다({path.name}) — plan 을 다시 실행하면 다시 받는다",
                kind="http",
            ) from exc
        raise HotelSearchError(
            f"Xotelo 응답이 JSON 이 아닙니다({path.name}) — 본문 잘림·점검 페이지. plan 을 다시 실행하면 다시 받는다",
            kind="site",
        ) from exc
    if not isinstance(env, dict):
        raise HotelSearchError(
            f"Xotelo 응답이 객체가 아닙니다({path.name})",
            kind="site",
        )
    return env


def _result_or_raise(envelope: dict) -> dict:
    """Xotelo 응답 봉투에서 result 를 꺼낸다. error 객체는 조용히 삼키지 않고 표면화한다."""
    err = envelope.get("error")
    if err:
        code = err.get("status_code") if isinstance(err, dict) else None
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        if code == 400:
            raise ArgsError(f"Xotelo 요청 오류(400): {msg}")
        raise HotelSearchError(
            f"Xotelo 오류({code}): {msg}",
            kind="api",
        )
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise NoResultError("Xotelo 응답에 result 가 없습니다")
    return result


def fetched_at(envelope: dict) -> str | None:
    """응답 ``timestamp``(epoch ms) → KST ``YYYY-MM-DD HH:MM``. 없으면 None."""
    ts = envelope.get("timestamp")
    try:
        return _dt.datetime.fromtimestamp(int(ts) / 1000, KST).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def read_rates(path: Path, chk_in: str, chk_out: str, currency: str) -> tuple[dict, str | None]:
    """/rates 저장 파일 → (result, 조회 시각). 되비친 조건이 요청과 다르면 mismatch."""
    env = _load_envelope(path)
    result = _result_or_raise(env)
    echoed = (result.get("chk_in"), result.get("chk_out"), (result.get("currency") or "").upper())
    if echoed != (chk_in, chk_out, currency):
        raise HotelSearchError(
            f"응답의 조회 조건 {echoed} 이 요청 {(chk_in, chk_out, currency)} 과 다릅니다({path.name}) — 다른 조회의 파일입니다",
            kind="mismatch",
        )
    if not isinstance(result.get("rates"), list):
        raise HotelSearchError(
            f"Xotelo 응답에 rates 목록이 없습니다({path.name}) — 구조 변경 가능성",
            kind="site",
        )
    return result, fetched_at(env)


def read_heatmap(path: Path, chk_out: str) -> tuple[dict, str | None]:
    env = _load_envelope(path)
    result = _result_or_raise(env)
    if result.get("chk_out") != chk_out:
        raise HotelSearchError(
            f"응답의 체크아웃({result.get('chk_out')}) 이 요청({chk_out})과 다릅니다({path.name})",
            kind="mismatch",
        )
    if not isinstance(result.get("heatmap"), dict):
        raise HotelSearchError(
            f"Xotelo 응답에 heatmap 이 없습니다({path.name}) — 구조 변경 가능성",
            kind="site",
        )
    return result, fetched_at(env)


def parse_rates(result: dict, *, nights: int, fx_rate: float | None = None) -> tuple[list[dict], str, int]:
    """/rates result 를 OTA offer 리스트 + 수집 통화 + 버린 행 수로 정제한다(1박가 오름차순).

    Xotelo `rate` = 1박 평균가 → total = rate × nights.
    fx_rate(수집통화 1단위당 KRW) 주면 원화 환산 필드를 채운다.
    rate 가 없거나 숫자가 아닌 행은 버리되 그 수를 센다(무음 폐기 금지 — collection-completeness ③).
    """
    currency = result.get("currency", "")
    offers: list[dict] = []
    dropped = 0
    for r in result.get("rates") or []:
        if not isinstance(r, dict):
            dropped += 1
            continue
        try:
            per_night = float(r.get("rate"))
        except (TypeError, ValueError):
            dropped += 1
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
    return offers, currency, dropped


def parse_heatmap(result: dict) -> dict:
    """/heatmap result 를 {chk_out, cheap_days, average_days, high_days} 로 정제한다."""
    hm = result.get("heatmap") or {}
    return {
        "chk_out": result.get("chk_out"),
        "cheap_days": list(hm.get("cheap_price_days") or []),
        "average_days": list(hm.get("average_price_days") or []),
        "high_days": list(hm.get("high_price_days") or []),
    }
