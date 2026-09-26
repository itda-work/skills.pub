#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fx.py - 환율 조회(수집 통화 → KRW) — 순수 표준 라이브러리.

Xotelo 는 KRW 미지원이라 USD 등으로 수집한 뒤 원화로 환산 표시한다(#1013 결정,
astroyuji-invest/hotel-price-watch 참조 패턴). open.er-api.com 은 무료·API 키 불필요다.

조용한 폴백 금지(no-silent-fallback): 환율 조회 실패는 0/추정으로 덮지 않고 None 을
반환한다. 호출부(hotel_search)는 None 을 받으면 원화 환산을 생략하고 그 사실을
출력에 **명시**한다(사용자가 실패를 인지).
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# {base} 1단위당 각 통화 환율. .rates.KRW 가 base→KRW 환산율.
FX_URL = "https://open.er-api.com/v6/latest/{base}"
_UA = "Mozilla/5.0 hotel-search/1.0"
_TIMEOUT = 15


def _fetch(url: str) -> dict:
    """네트워크 경계 — 테스트가 monkeypatch 한다."""
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read())


def krw_rate(base: str = "USD") -> float | None:
    """base 통화 1단위당 KRW 환율. 조회 실패 시 None(조용한 0 폴백 금지)."""
    if (base or "").upper() == "KRW":
        return 1.0
    try:
        data = _fetch(FX_URL.format(base=(base or "USD").upper()))
    except (HTTPError, URLError, ValueError, TimeoutError, OSError):
        return None
    if not isinstance(data, dict) or data.get("result") != "success":
        return None
    rate = (data.get("rates") or {}).get("KRW")
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return None
    return rate if rate > 0 else None
