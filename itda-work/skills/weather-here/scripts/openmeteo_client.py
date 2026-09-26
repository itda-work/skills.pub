"""openmeteo_client.py - Open-Meteo Forecast 호출 (REQ-004/009/013/020).

§4.1 확정 명세 그대로:
  base: https://api.open-meteo.com/v1/forecast
  고정 query: current=temperature_2m,...,weather_code,wind_speed_10m
              daily=weather_code,temperature_2m_max,...,precipitation_probability_max
              timezone=Asia/Seoul forecast_days=1

무키 — 인증키·헤더 인증·활용신청 없음.
http_util.fetch_json 재사용.
국내·해외 단일 클라이언트 (REQ-020 통합).
"""
from __future__ import annotations

import urllib.parse

from http_util import fetch_json

_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# 고정 current 필드 (§4.1)
_CURRENT_FIELDS = (
    "temperature_2m,"
    "relative_humidity_2m,"
    "apparent_temperature,"
    "precipitation,"
    "weather_code,"
    "wind_speed_10m"
)

# 고정 daily 필드 (§4.1)
_DAILY_FIELDS = (
    "weather_code,"
    "temperature_2m_max,"
    "temperature_2m_min,"
    "precipitation_probability_max"
)


def fetch(lat: float, lon: float) -> dict | None:
    """Open-Meteo Forecast API를 호출하여 current+daily 데이터를 반환한다.

    §4.1 고정 query(current/daily/timezone=Asia/Seoul/forecast_days=1)로
    단일 HTTP 콜을 수행한다. 무키 — 인증키 없음.

    Args:
        lat: 위도(float) — 시나리오 A=IP 위경도, B=정적표 lat.
        lon: 경도(float) — 시나리오 A=IP 위경도, B=정적표 lon.

    Returns:
        파싱된 날씨 dict:
          temperature, apparent, humidity, precipitation, weather_code, wind
          pop, wcode_daily, tmax, tmin
        current 필드 미수신 시 None.
        개별 필드 누락은 None으로 채워 반환.
    """
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": _CURRENT_FIELDS,
            "daily": _DAILY_FIELDS,
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        }
    )
    url = f"{_BASE_URL}?{params}"

    ok, data, _ = fetch_json(url)
    if not ok or not data:
        return None

    current = data.get("current")
    if not current:
        return None

    daily = data.get("daily") or {}

    def _first(lst: list | None, default=None):
        """리스트 첫 원소 또는 default 반환."""
        if isinstance(lst, list) and lst:
            return lst[0]
        return default

    pop = _first(daily.get("precipitation_probability_max"))
    wcode_daily = _first(daily.get("weather_code"))
    tmax = _first(daily.get("temperature_2m_max"))
    tmin = _first(daily.get("temperature_2m_min"))

    return {
        "temperature": current.get("temperature_2m"),
        "apparent": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind": current.get("wind_speed_10m"),
        "pop": pop,
        "wcode_daily": wcode_daily,
        "tmax": tmax,
        "tmin": tmin,
    }
