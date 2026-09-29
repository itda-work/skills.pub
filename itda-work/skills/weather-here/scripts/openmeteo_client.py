"""openmeteo_client.py - Open-Meteo Forecast 호출 (REQ-004/009/013/020).

§4.1 확정 명세 그대로:
  base: https://api.open-meteo.com/v1/forecast
  고정 query: current=temperature_2m,...,weather_code,wind_speed_10m
              daily=weather_code,temperature_2m_max,...,precipitation_probability_max
              timezone=Asia/Seoul forecast_days=1

무키 — 인증키·헤더 인증·활용신청 없음.
http_util.fetch_json 재사용. 같은 요청을 itda-hyve `http_request` 로 보낼 때는
`request_spec()` 이 인자를, `parse()` 가 저장된 응답 해석을 맡는다.
국내·해외 단일 클라이언트 (REQ-020 통합).
"""
from __future__ import annotations

import urllib.parse

from http_util import fetch_json

BASE_URL = "https://api.open-meteo.com/v1/forecast"

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


def build_params(lat: float, lon: float) -> dict[str, str]:
    """§4.1 고정 query 를 문자열 값 dict 로 만든다.

    직접 호출(`fetch`)과 itda-hyve `http_request` 의 `params`(값은 문자열)가
    **같은 요청**이 되도록 한 곳에서 만든다(request-profile-first).
    """
    return {
        "latitude": str(lat),
        "longitude": str(lon),
        "current": _CURRENT_FIELDS,
        "daily": _DAILY_FIELDS,
        "timezone": "Asia/Seoul",
        "forecast_days": "1",
    }


def request_spec(lat: float, lon: float) -> dict:
    """itda-hyve `http_request` 에 그대로 넣을 인자(url·params)."""
    return {"url": BASE_URL, "params": build_params(lat, lon)}


def fetch(lat: float, lon: float) -> dict | None:
    """Open-Meteo Forecast API를 호출하여 current+daily 데이터를 반환한다.

    §4.1 고정 query(current/daily/timezone=Asia/Seoul/forecast_days=1)로
    단일 HTTP 콜을 수행한다. 무키 — 인증키 없음.

    Args:
        lat: 위도(float) — 시나리오 A=IP 위경도, B=정적표 lat.
        lon: 경도(float) — 시나리오 A=IP 위경도, B=정적표 lon.

    Returns:
        `parse()` 결과. 네트워크 실패·current 미수신 시 None.
    """
    url = f"{BASE_URL}?{urllib.parse.urlencode(build_params(lat, lon))}"

    ok, data, _ = fetch_json(url)
    if not ok or not data:
        return None
    return parse(data)


def parse(data: object) -> dict | None:
    """Open-Meteo 응답 JSON(dict)을 날씨 dict 로 바꾼다.

    직접 호출 응답과 itda-hyve 가 `save_as` 로 저장한 응답을 같은 규칙으로 읽는다.

    Returns:
        temperature, apparent, humidity, precipitation, weather_code, wind,
        pop, wcode_daily, tmax, tmin. current 필드가 없으면 None.
        개별 필드 누락은 None 으로 채운다.
    """
    if not isinstance(data, dict):
        return None
    current = data.get("current")
    if not current or not isinstance(current, dict):
        return None

    daily = data.get("daily") or {}
    if not isinstance(daily, dict):
        daily = {}

    def _first(lst: list | None, default=None):
        """리스트 첫 원소 또는 default 반환."""
        if isinstance(lst, list) and lst:
            return lst[0]
        return default

    return {
        "temperature": current.get("temperature_2m"),
        "apparent": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind": current.get("wind_speed_10m"),
        "pop": _first(daily.get("precipitation_probability_max")),
        "wcode_daily": _first(daily.get("weather_code")),
        "tmax": _first(daily.get("temperature_2m_max")),
        "tmin": _first(daily.get("temperature_2m_min")),
    }
