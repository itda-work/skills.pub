"""weather_here.py - 날씨 조회 스킬 CLI 진입점 (v0.4.0 Open-Meteo 무키 재설계).

시나리오 A (지역명 없음): IP 자동탐지 → (lat,lon) → 한국 bbox 판별(라벨용)
  → openmeteo_client.fetch(lat, lon) → 출력
시나리오 B (지역명 있음): region_resolver → (lat, lon) → openmeteo_client → 출력

외부 인증키 없음 — 무키 Open-Meteo.
되묻기 0회, 비대화형, 한국어 출력 (REQ-006/007/008).
해외 위치: 동일 Open-Meteo + "(해외·대략·미검증)" 라벨 (REQ-020).
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import geo_locator
import openmeteo_client
import region_resolver
import wmo_codes

# --- 한국 bbox 상수 (REQ-020) ---
# 한반도·제주·독도 포함 근사 범위
_KR_LAT_MIN = 33.0
_KR_LAT_MAX = 39.0
_KR_LON_MIN = 124.0
_KR_LON_MAX = 132.0

_OVERSEA_LABEL = "(해외·대략·미검증)"


def _is_korea_bbox(lat: float, lon: float) -> bool:
    """위경도가 한국 bbox 내인지 판별한다 (REQ-020)."""
    return (
        _KR_LAT_MIN <= lat <= _KR_LAT_MAX
        and _KR_LON_MIN <= lon <= _KR_LON_MAX
    )


def _fmt(value: Any, unit: str = "", fallback: str = "정보 없음") -> str:
    """값이 있으면 값+단위, 없으면 fallback 반환."""
    if value is None:
        return fallback
    return f"{value}{unit}"


def _rain_gloss(prob: Any) -> str:
    """강수확률을 '비 올 듯/낮음' 거친 한마디로 변환한다 (REQ-006).

    정확한 결정(우산 챙겨라 등)을 내리지 않는다 — 대략의 가늠만 제공.
    숫자가 아니면 빈 문자열(생략). POP 임계: 60/30 (REQ-006).
    """
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return ""
    if p >= 60:
        return "비 올 듯해요"
    if p >= 30:
        return "비 올 수 있어요"
    return "비 올 가능성 낮아요"


def _build_gist(location_name: str, weather: dict) -> str:
    """기본 출력: 위치 + 날씨 상태 + 강수확률 + 거친 한마디 (REQ-006).

    아침 현관의 '비 와?' 순간에 맞춘 gist. 습도·풍속·기온 상세는 미포함.
    해외 위치인 경우 OVERSEA_LABEL 포함(REQ-020).
    """
    code = weather.get("weather_code")
    condition = wmo_codes.to_korean(code)
    pop = weather.get("pop")

    # 해외 라벨 (REQ-020)
    label = weather.get("label", "")
    location_display = f"{location_name} {label}".strip()

    head = f"{location_display} · 오늘 {condition}"
    if pop is not None:
        head += f", 강수확률 {pop}%"
    gloss = _rain_gloss(pop)
    if gloss:
        head += f" — {gloss}"
    return head


def _build_detail(location_name: str, weather: dict) -> str:
    """상세 출력 (--detail): 현재 블록 + 오늘 요약 (REQ-006).

    첫 줄: 지역명 명시.
    현재 날씨 블록: 날씨상태·기온·습도·강수량·풍속.
    오늘 요약: 강수확률·최고·최저 기온.
    """
    code = weather.get("weather_code")
    condition = wmo_codes.to_korean(code)

    temp = _fmt(weather.get("temperature"), "°C")
    humidity = _fmt(weather.get("humidity"), "%")
    precip = _fmt(weather.get("precipitation"), "mm")
    wind = _fmt(weather.get("wind"), "m/s")
    pop = _fmt(weather.get("pop"), "%")

    # 해외 라벨 (REQ-020)
    label = weather.get("label", "")
    location_display = f"{location_name} {label}".strip()

    lines = [
        f"[{location_display}] 현재 날씨",
        f"날씨 상태: {condition}",
        f"기온: {temp}",
        f"습도: {humidity}",
        f"강수량: {precip}",
        f"풍속: {wind}",
        "",
        f"오늘 강수확률: {pop}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점.

    Args:
        argv: 인자 목록 (기본: sys.argv[1:]).

    Returns:
        종료 코드 (0 = 정상, 1 = 오류/안내).
    """
    parser = argparse.ArgumentParser(
        description="현재 위치 또는 지정 지역의 날씨를 한국어로 조회합니다.",
        add_help=True,
    )
    parser.add_argument(
        "location",
        nargs="?",
        default=None,
        help="조회할 지역명 (생략 시 IP 자동탐지)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="상세 출력(기온·습도·강수량·풍속+강수확률). 기본은 gist만",
    )
    args = parser.parse_args(argv)

    location_name: str
    weather: dict | None = None

    if args.location:
        # --- 시나리오 B: 지역명 명시 (REQ-003/017) ---
        result = region_resolver.resolve(args.location)
        if result is None:
            print(
                f"'{args.location}'에 해당하는 지역을 찾을 수 없습니다. "
                "(지원 범위: 시·도 및 시군구 단위, 한국어·주요 영문 별칭)\n"
                "다른 지역명으로 다시 시도해 주세요.",
                file=sys.stderr,
            )
            return 1
        lat, lon, location_name = result
        weather = openmeteo_client.fetch(lat, lon)

    else:
        # --- 시나리오 A: IP 자동탐지 (REQ-001/007) ---
        # 되묻기 금지 — 실패 시 비대화형 안내만 출력하고 종료 (REQ-007/008)
        coords = geo_locator.locate_by_ip()
        if coords is None:
            print(
                "현재 위치를 자동으로 파악할 수 없습니다.\n"
                "지역명을 알려주시면 해당 지역 날씨를 조회합니다.\n"
                "예: python3 weather_here.py 서울",
                file=sys.stderr,
            )
            return 1

        lat, lon = coords

        # 한국 bbox 판별 — 라벨 결정용 (REQ-020)
        if _is_korea_bbox(lat, lon):
            location_name = f"현재 위치 ({lat:.2f}°N, {lon:.2f}°E)"
            weather = openmeteo_client.fetch(lat, lon)
        else:
            # 해외 best-effort — 동일 Open-Meteo, 라벨만 부가 (REQ-020)
            location_name = f"{lat:.2f}°N, {lon:.2f}°E"
            weather = openmeteo_client.fetch(lat, lon)
            if weather is not None:
                weather = {**weather, "label": _OVERSEA_LABEL}

    if weather is None:
        # 일반 네트워크/응답 실패 (REQ-013)
        print(
            "날씨 정보를 가져오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.\n"
            "(네트워크 오류 또는 서버 응답 비정상)",
            file=sys.stderr,
        )
        return 1

    # --- 출력 (REQ-006) ---
    if args.detail:
        print(_build_detail(location_name, weather))
    else:
        print(_build_gist(location_name, weather))

    return 0


if __name__ == "__main__":
    sys.exit(main())
