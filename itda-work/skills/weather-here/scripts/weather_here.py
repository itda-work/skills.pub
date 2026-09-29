"""weather_here.py - 날씨 조회 스킬 CLI 진입점 (v0.4.0 Open-Meteo 무키 재설계).

위치 결정 순서(#33·#37 — 앞이 이긴다):
  1. 지역명(위치 인자) → region_resolver → (lat, lon)
  2. --lat/--lon → 그대로
  3. --geo-input 파일 — itda-hyve `location` 응답(0.9.3, OS 위치·IP 합의) 또는
     옛 판의 `http_request` 로 받은 ipapi.co·ipwho.is 응답 → (lat, lon) + 출처·장소
  4. 스크립트 직접 IP 조회(ipapi.co → ipwho.is) — Cowork 작업 공간에서는 하지 않는다
     (스크립트가 클라우드에서 돌아 IP 가 사용자 PC 가 아니다. 틀린 위치로 날씨를 내지 않고
     exit 3 으로 멈춘다).

날씨 값: 기본은 Open-Meteo 직접 호출. --weather-input 이면 itda-hyve 가 받아 둔 응답
파일을 읽는다(네트워크 없음). --weather-request 는 그 호출 인자를 JSON 으로 낸다.

종료 코드: 0 정상 · 1 지역명 미수록/날씨 조회 실패 · 2 인자 오류 · 3 위치 미확정.

외부 인증키 없음 — 무키 Open-Meteo.
되묻기 0회, 비대화형, 한국어 출력 (REQ-006/007/008).
해외 위치: 동일 Open-Meteo + "(해외·대략·미검증)" 라벨 (REQ-020).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
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

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_LOCATION_UNRESOLVED = 3

# --weather-input 응답 좌표와 요청 좌표의 허용 차(도). Open-Meteo 는 격자에 맞춰
# 좌표를 조금 옮겨 돌려준다 — 그보다 크게 어긋나면 다른 위치의 응답 파일이다.
_WEATHER_COORD_TOLERANCE = 0.5

_IP_SOURCES_HINT = (
    "itda-hyve 의 location 도구(0.9.3 이상)로 위치를 받아 --geo-input <저장한 파일> 로 넘기세요.\n"
    "location 이 없는 옛 itda-hyve 면 http_request 로 https://ipapi.co/json/ (실패하면 https://ipwho.is/) 를 받아\n"
    "--geo-input <저장한 파일> 또는 --lat <위도> --lon <경도> 로 넘기세요."
)

# 위치 출처별 표시(#37). IP 한 곳·합의 실패는 시·도부터 틀릴 수 있다(KT 회선이 성남으로 잡힌 실측).
_APPROX_IP = "(대략·IP 기준)"
_REGION_LEVEL = "(시·도 기준)"


def _place_label(fix: geo_locator.GeoFix | None, lat: float, lon: float) -> tuple[str, str]:
    """좌표로 정한 위치의 (표시 이름, 라벨). 국내만 부른다."""
    coords = f"현재 위치 ({lat:.2f}°N, {lon:.2f}°E)"
    if fix is None:  # --lat/--lon — 출처를 모른다
        return coords, ""
    if fix.source in ("ipapi", "ipwho", "ip_single"):  # IP 서비스 한 곳
        return coords, _APPROX_IP
    name = fix.place or coords
    if fix.source == "os" and fix.accuracy != "low":
        return name, ""
    if fix.source == "ip_consensus" and fix.accuracy != "low":
        return name, _REGION_LEVEL
    return name, _APPROX_IP


def _in_cowork_sandbox(script_path: Path | None = None) -> bool:
    """이 스크립트가 Cowork 작업 공간(클라우드 샌드박스)에서 도는지.

    Cowork 는 플러그인·업로드 스킬을 모두 `/sessions/<id>/mnt/…` 아래에 둔다
    (capability map §3 — 플러그인 `.remote-plugins`, 단일 `.skill` `.claude/skills`).
    Claude Code 표준 환경변수는 Cowork 에 주입되지 않고 `HOME` 도 회차마다 달라
    (`/sessions/<id>`·`/root` 실측) 환경변수로는 가를 수 없다 — 스크립트 파일 위치가 정본.
    """
    path = (script_path or Path(__file__)).resolve()
    parts = path.parts
    return len(parts) > 2 and parts[1] == "sessions"


def _read_weather_file(path: str, lat: float, lon: float) -> tuple[dict | None, str]:
    """itda-hyve 가 저장한 Open-Meteo 응답 파일을 읽어 날씨 dict 로.

    응답의 latitude/longitude 가 요청 좌표와 어긋나면(다른 위치의 파일) 거부한다.
    """
    name = Path(path).name
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return None, f"{name}: 파일을 읽을 수 없음({exc.strerror or exc})"
    except json.JSONDecodeError:
        return None, f"{name}: JSON 이 아님"
    data, why = geo_locator.unwrap_response(data)
    if why:
        return None, f"{name}: {why}"
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return None, f"{name}: itda-hyve 호출 실패({data['error'].get('code') or 'error'})"
    if isinstance(data, dict) and data.get("error") is True:
        return None, f"{name}: Open-Meteo 오류({data.get('reason') or '사유 없음'})"
    if not isinstance(data, dict):
        return None, f"{name}: 응답 형태가 객체가 아님"
    try:
        r_lat = float(data["latitude"])
        r_lon = float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, f"{name}: 응답에 좌표가 없어 어느 위치의 날씨인지 확인할 수 없음"
    if (abs(r_lat - lat) > _WEATHER_COORD_TOLERANCE
            or abs(r_lon - lon) > _WEATHER_COORD_TOLERANCE):
        return None, (
            f"{name}: 응답 좌표({r_lat:.2f}, {r_lon:.2f})가 요청 위치({lat:.2f}, {lon:.2f})와 다름 — "
            "다른 위치의 파일"
        )
    weather = openmeteo_client.parse(data)
    if weather is None:
        return None, f"{name}: current 필드가 없음"
    return weather, ""


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


def _stop_unresolved(message: str) -> int:
    """위치를 확정하지 못했다 — 틀린 위치로 날씨를 내지 않고 멈춘다."""
    print(message, file=sys.stderr)
    return EXIT_LOCATION_UNRESOLVED


_Resolved = tuple[int, float, float, str, bool, "geo_locator.GeoFix | None"]


def _resolve_location(args: argparse.Namespace) -> _Resolved:
    """(exit_code, lat, lon, 표시 이름, 좌표로 정했는지, 출처)를 돌려준다.

    exit_code 가 0 이 아니면 이미 사유를 stderr 에 썼다. 출처는 위치 응답 파일·직접 IP 조회일 때만.
    """
    if args.location:
        # --- 지역명 명시 (REQ-003/017) — 다른 위치 입력보다 우선 ---
        result = region_resolver.resolve(args.location)
        if result is None:
            print(
                f"'{args.location}'에 해당하는 지역을 찾을 수 없습니다. "
                "(지원 범위: 시·도 및 시군구 단위, 한국어·주요 영문 별칭)\n"
                "다른 지역명으로 다시 시도해 주세요.",
                file=sys.stderr,
            )
            return EXIT_FAIL, 0.0, 0.0, "", False, None
        lat, lon, name = result
        return EXIT_OK, lat, lon, name, False, None

    if args.lat is not None:
        # --- 위경도 직접 (itda-hyve 응답에서 옮김) ---
        if not geo_locator._valid_coords(args.lat, args.lon):
            return _stop_unresolved(
                f"위경도 값이 올바르지 않습니다({args.lat}, {args.lon}). 위치를 확정하지 못해 멈춥니다."
            ), 0.0, 0.0, "", False, None
        return EXIT_OK, args.lat, args.lon, "", True, None

    if args.geo_input:
        # --- itda-hyve 가 받아 저장한 IP 위치 응답 ---
        fix, reasons = geo_locator.locate_fix_from_files(args.geo_input)
        if fix is None:
            detail = "\n".join(f"  - {r}" for r in reasons)
            return _stop_unresolved(
                "받아 둔 위치 응답에서 위치를 확정하지 못해 멈춥니다(틀린 위치로 날씨를 내지 않습니다).\n"
                f"{detail}\n"
                "옛 itda-hyve 의 ipapi.co 가 실패했으면 https://ipwho.is/ 를 받아 --geo-input 을 하나 더 붙이거나, "
                "지역명을 알려주세요."
            ), 0.0, 0.0, "", False, None
        return EXIT_OK, fix.lat, fix.lon, "", True, fix

    if _in_cowork_sandbox():
        # --- Cowork: 스크립트의 IP 는 클라우드 IP 다 (#33 — 샌프란시스코 실측) ---
        return _stop_unresolved(
            "Cowork 작업 공간에서는 스크립트가 클라우드에서 돌아 IP 위치가 사용자 위치가 아닙니다.\n"
            "현재 위치를 확정하지 못해 멈춥니다(틀린 위치로 날씨를 내지 않습니다).\n"
            + _IP_SOURCES_HINT
            + "\nitda-hyve 가 없으면 지역명을 알려주세요(예: 서울)."
        ), 0.0, 0.0, "", False, None

    # --- 로컬: 스크립트 직접 IP 자동탐지 (REQ-001/007) ---
    # 되묻기 금지 — 실패 시 비대화형 안내만 출력하고 종료 (REQ-007/008)
    coords = geo_locator.locate_by_ip()
    if coords is None:
        return _stop_unresolved(
            "현재 위치를 자동으로 파악할 수 없습니다.\n"
            "지역명을 알려주시면 해당 지역 날씨를 조회합니다.\n"
            "예: python3 weather_here.py 서울"
        ), 0.0, 0.0, "", False, None
    return EXIT_OK, coords[0], coords[1], "", True, geo_locator.GeoFix(coords[0], coords[1], "ip_single")


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점.

    Args:
        argv: 인자 목록 (기본: sys.argv[1:]).

    Returns:
        종료 코드 (0 정상 · 1 지역 미수록/날씨 조회 실패 · 2 인자 오류 · 3 위치 미확정).
    """
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게(windows-console-utf8-output).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(
        description="현재 위치 또는 지정 지역의 날씨를 한국어로 조회합니다.",
        add_help=True,
    )
    parser.add_argument(
        "location",
        nargs="?",
        default=None,
        help="조회할 지역명 (생략 시 현재 위치 — 아래 위치 입력 또는 IP 자동탐지)",
    )
    parser.add_argument("--lat", type=float, default=None, help="위도 (itda-hyve 로 받은 위치)")
    parser.add_argument("--lon", type=float, default=None, help="경도 (--lat 과 함께)")
    parser.add_argument(
        "--geo-input",
        action="append",
        default=None,
        metavar="FILE",
        help="itda-hyve 가 저장한 ipapi.co·ipwho.is 응답 파일(여러 번 주면 앞에서부터 첫 유효값)",
    )
    parser.add_argument(
        "--weather-input",
        default=None,
        metavar="FILE",
        help="itda-hyve 가 저장한 Open-Meteo 응답 파일(직접 호출 대신)",
    )
    parser.add_argument(
        "--weather-request",
        action="store_true",
        help="Open-Meteo 를 itda-hyve http_request 로 부를 인자(JSON)를 출력하고 끝낸다",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="상세 출력(기온·습도·강수량·풍속+강수확률). 기본은 gist만",
    )
    args = parser.parse_args(argv)

    if (args.lat is None) != (args.lon is None):
        parser.error("--lat 과 --lon 은 함께 줘야 합니다.")
    if args.lat is not None and args.geo_input:
        parser.error("--lat/--lon 과 --geo-input 은 함께 쓸 수 없습니다.")

    code, lat, lon, location_name, by_coords, fix = _resolve_location(args)
    if code != EXIT_OK:
        return code

    label = ""
    if by_coords:
        # 한국 bbox 판별 — 라벨 결정용 (REQ-020)
        if _is_korea_bbox(lat, lon) and (fix is None or fix.country in ("", "KR")):
            location_name, label = _place_label(fix, lat, lon)
            if fix is not None and label == _APPROX_IP and fix.note:
                # 합의 실패 — itda-hyve 가 사용자 확인을 권한다. 날씨 줄은 그대로 내고 사유는 stderr 에.
                print(f"위치 참고: {fix.note}", file=sys.stderr)
        else:
            # 해외 best-effort — 동일 Open-Meteo, 라벨만 부가 (REQ-020)
            location_name = f"{lat:.2f}°N, {lon:.2f}°E"
            label = _OVERSEA_LABEL

    if args.weather_request:
        print(json.dumps(openmeteo_client.request_spec(lat, lon), ensure_ascii=False))
        return EXIT_OK

    weather: dict | None
    if args.weather_input:
        weather, reason = _read_weather_file(args.weather_input, lat, lon)
        if weather is None:
            print(
                "받아 둔 날씨 응답을 쓸 수 없습니다.\n"
                f"  - {reason}\n"
                "같은 위치 인자로 --weather-request 를 다시 뽑아 itda-hyve 로 받아 주세요.",
                file=sys.stderr,
            )
            return EXIT_FAIL
    else:
        weather = openmeteo_client.fetch(lat, lon)
        if weather is None:
            # 일반 네트워크/응답 실패 (REQ-013)
            print(
                "날씨 정보를 가져오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.\n"
                "(네트워크 오류 또는 서버 응답 비정상)\n"
                "작업 공간의 네트워크가 막혀 있으면 같은 위치 인자에 --weather-request 를 붙여 "
                "itda-hyve 호출 인자를 받은 뒤, 저장한 응답을 --weather-input 으로 넘기세요.",
                file=sys.stderr,
            )
            return EXIT_FAIL

    if label:
        weather = {**weather, "label": label}

    # --- 출력 (REQ-006) ---
    if args.detail:
        print(_build_detail(location_name, weather))
    else:
        print(_build_gist(location_name, weather))

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
