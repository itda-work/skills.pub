"""openmeteo_client.py - Open-Meteo Forecast 요청 인자·응답 해석 (REQ-004/020). 네트워크 없음.

§4.1 확정 명세 그대로:
  base: https://api.open-meteo.com/v1/forecast
  고정 query: current=temperature_2m,...,weather_code,wind_speed_10m
              daily=weather_code,temperature_2m_max,...,precipitation_probability_max
              timezone=Asia/Seoul forecast_days=1

무키 — 인증키·헤더 인증·활용신청 없음.
요청은 itda-hyve `http_request` 가 보낸다(itda-work/skills#46 — 스크립트 직접 호출 `fetch` 는 0.15.0 에서 지웠다).
`build_params()` 가 인자를, `parse()` 가 저장된 응답 해석을 맡는다.
국내·해외 단일 클라이언트 (REQ-020 통합).
"""
from __future__ import annotations

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

    itda-hyve `http_request` 의 `params`(값은 문자열)로 그대로 쓴다(request-profile-first).
    """
    return {
        "latitude": str(lat),
        "longitude": str(lon),
        "current": _CURRENT_FIELDS,
        "daily": _DAILY_FIELDS,
        "timezone": "Asia/Seoul",
        "forecast_days": "1",
    }


# 풍속 단위 → m/s 환산 계수. Open-Meteo 기본은 km/h 다(2026-10-01 실측 `current_units.wind_speed_10m`).
_WIND_TO_MS = {"km/h": 1 / 3.6, "m/s": 1.0, "mp/h": 0.44704, "kn": 0.514444}


def _wind_ms(value: object, units: object) -> float | None:
    """풍속을 m/s 로. 단위를 모르면 None(정보 없음) — 단위를 짐작해 틀린 값을 내지 않는다.

    0.14.x 까지는 km/h 값을 그대로 "m/s" 로 표시했다(3.6배 과대).
    """
    if value is None:
        return None
    unit = units.get("wind_speed_10m") if isinstance(units, dict) else None
    factor = _WIND_TO_MS.get(unit) if isinstance(unit, str) else None
    if factor is None:
        return None
    try:
        return round(float(value) * factor, 1)
    except (TypeError, ValueError):
        return None


def parse(data: object) -> dict | None:
    """Open-Meteo 응답 JSON(dict)을 날씨 dict 로 바꾼다.

    itda-hyve 가 `save_as` 로 저장한 응답을 읽는다.

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
        "wind": _wind_ms(current.get("wind_speed_10m"), data.get("current_units")),
        "pop": _first(daily.get("precipitation_probability_max")),
        "wcode_daily": _first(daily.get("weather_code")),
        "tmax": _first(daily.get("temperature_2m_max")),
        "tmin": _first(daily.get("temperature_2m_min")),
    }
