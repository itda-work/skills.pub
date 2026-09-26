"""geo_locator.py - 위치 결정 모듈 (v0.3.0 개정).

시나리오 A: IP 폴백 체인(ipapi.co → ipwho.is)으로 **위경도만** 반환 (REQ-001/002).
  - Open-Meteo 지오코딩 완전 제거(EXC-6 — 한국 부정확 실증).
  - 반환: (latitude, longitude) tuple 또는 None.
  - success:false 게이트 + _valid_coords() 유한·범위 검증 유지(REQ-002 견고화).

시나리오 B는 region_resolver.py가 담당(이 모듈 무관).
"""
from __future__ import annotations

import math

from http_util import fetch_json

# IP 지오로케이션 서비스 URLs (spec.md §4.4)
_IPAPI_URL = "https://ipapi.co/json/"
_IPWHO_URL = "https://ipwho.is/"


def locate_by_ip() -> tuple[float, float] | None:
    """IP 지오로케이션 폴백 체인으로 위경도를 탐지한다 (REQ-001/002).

    1차: ipapi.co → 실패 시 2차: ipwho.is
    둘 다 실패하면 None 반환.

    Returns:
        (latitude, longitude) float 쌍 또는 None (전부 실패).
        도시명은 반환하지 않음(외부 지오코더 미사용). v0.4.0: 이 위경도를
        Open-Meteo Forecast에 직접 전달(격자 변환 없음).
    """
    # 1차: ipapi.co
    ok, data, _ = fetch_json(_IPAPI_URL)
    if ok and data:
        loc = _extract_latlon(data, provider="ipapi")
        if loc is not None:
            return loc

    # 2차 폴백: ipwho.is
    ok, data, _ = fetch_json(_IPWHO_URL)
    if ok and data:
        loc = _extract_latlon(data, provider="ipwho")
        if loc is not None:
            return loc

    return None


def _extract_latlon(
    data: dict,
    provider: str,
) -> tuple[float, float] | None:
    """IP 서비스 응답에서 위경도를 추출한다.

    Args:
        data: 서비스 응답 dict.
        provider: "ipapi" 또는 "ipwho".

    Returns:
        (latitude, longitude) 또는 None.
    """
    # ipwho.is는 오류 시 {"success": false, ...}를 반환한다.
    # success:false 게이트: 오인하면 (0,0) 같은 무의미 좌표 위험(REQ-002 견고화).
    if provider == "ipwho" and data.get("success") is False:
        return None
    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (KeyError, ValueError, TypeError):
        return None
    if not _valid_coords(lat, lon):
        return None
    return lat, lon


def _valid_coords(lat: float, lon: float) -> bool:
    """위경도가 유한하고 지리적 범위 내인지 검증한다.

    inf/nan 또는 위도 [-90,90]·경도 [-180,180] 밖이면 거부 —
    무의미 좌표로 엉뚱한 위치 날씨를 보여주는 것을 방지(REQ-002 견고화).
    """
    return (
        math.isfinite(lat)
        and math.isfinite(lon)
        and -90.0 <= lat <= 90.0
        and -180.0 <= lon <= 180.0
    )
