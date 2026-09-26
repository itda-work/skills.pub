"""wmo_codes.py - WMO weather_code → 한국어 매핑 (REQ-005).

§4.2 확정 테이블(WMO 4677 표준 기준):
  미지/미수신 코드는 "알 수 없음(코드 n)" 반환 — 예외 발생 금지.
"""
from __future__ import annotations

# § 4.2 WMO weather_code → 한국어 매핑 테이블 (SPEC §4.2 정본 그대로)
_WMO_TABLE: dict[int, str] = {
    0: "맑음",
    1: "대체로 맑음",
    2: "구름 조금",
    3: "흐림",
    45: "안개",
    48: "안개",
    51: "이슬비",
    53: "이슬비",
    55: "이슬비",
    56: "어는 이슬비",
    57: "어는 이슬비",
    61: "비",
    63: "비",
    65: "비",
    66: "어는 비",
    67: "어는 비",
    71: "눈",
    73: "눈",
    75: "눈",
    77: "싸락눈",
    80: "소나기",
    81: "소나기",
    82: "소나기",
    85: "소낙눈",
    86: "소낙눈",
    95: "뇌우",
    96: "우박 동반 뇌우",
    99: "우박 동반 뇌우",
}


def to_korean(code: int | None) -> str:
    """WMO weather_code를 한국어 날씨 상태 문자열로 변환한다.

    Args:
        code: Open-Meteo가 반환하는 WMO 4677 weather interpretation code.
              None 또는 미지 코드도 예외 없이 처리한다.

    Returns:
        한국어 날씨 상태 문자열.
        표에 없는 코드: "알 수 없음(코드 n)" 형태.
    """
    try:
        code_int = int(code)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return f"알 수 없음(코드 {code})"

    if code_int in _WMO_TABLE:
        return _WMO_TABLE[code_int]

    return f"알 수 없음(코드 {code_int})"
