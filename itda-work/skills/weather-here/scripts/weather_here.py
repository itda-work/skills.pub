"""weather_here.py - 날씨 조회 스킬 CLI 진입점. 네트워크 없음(itda-work/skills#45·#46).

요청은 itda-hyve 가 보내고, 이 스크립트는 호출 인자를 만들고 저장된 응답을 판독한다.

위치 결정 순서(#33·#37 — 앞이 이긴다):
  1. 지역명(위치 인자) → region_resolver → (lat, lon)
  2. --lat/--lon → 그대로
  3. --geo-input 파일 — itda-hyve `location` 응답(OS 위치·IP 합의)만 → (lat, lon) + 출처·장소.
     IP 서비스 응답(ipapi.co·ipwho.is)·1시간 넘은 위치 파일은 받지 않는다(W9 리뷰 m1·m2).
     `--location-request` 가 `location` 호출 인자(저장 이름)를 낸다.
  위치를 못 정하면 exit 3 — 틀린 위치로 날씨를 내지 않는다. 스크립트는 어떤 서비스도 부르지 않는다.

날씨 값(Open-Meteo): --weather-request 가 itda-hyve `http_request` 인자(`call`)를 내고,
저장한 응답을 --weather-input 으로 읽는다(이름의 좌표·응답 좌표 0.1°·관측 시각·예보 날짜 대조).
둘 다 없으면 exit 2(다음 할 일 안내).

종료 코드: 0 정상 · 1 지역명 미수록/날씨 응답 판독 실패 · 2 인자 오류 · 3 위치 미확정.

외부 인증키 없음 — 무키 Open-Meteo.
되묻기 0회, 비대화형, 한국어 출력 (REQ-006/007/008).
해외 위치: 동일 Open-Meteo + "(해외·대략·미검증)" 라벨 (REQ-020).
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import geo_locator
import openmeteo_client
import region_resolver
import wmo_codes
from hyve_input import HyveFailure, HyveInputError, read_input

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

# --weather-input 응답 좌표와 요청 좌표의 허용 차(도). Open-Meteo 는 격자에 맞춰 좌표를 조금 옮겨 돌려준다 —
# 2026-10-01 리뷰 실측 11점(국내 도서·해외 포함) 최대 0.053°, 그 두 배. 옛 0.5° 는 대전 파일이 세종·청주 등
# 7곳 이름으로 통과했다(W9 리뷰 M2). 저장 이름의 좌표(넷째 자리)도 따로 대조한다.
_WEATHER_COORD_TOLERANCE = 0.1
_OM_NAME = re.compile(r"^openmeteo-(-?\d+\.\d{4})_(-?\d+\.\d{4})-(\d{12})\.json$")

_LOCATION_HINT = (
    "itda-hyve 의 location 도구로 위치를 받아 --geo-input <저장한 파일> 로 넘기세요(--location-request 가 호출 인자를 낸다).\n"
    "location 이 실패했으면 지역명을 알려주세요(예: 서울). itda-hyve 가 없으면 날씨를 받을 수 없습니다 — "
    "itda-hyve 0.10.4 이상 설치·Claude Desktop 연결이 먼저입니다."
)

# --weather-input 응답의 current.time 이 이보다 오래되면 묵은 파일로 보고 거부한다.
_WEATHER_MAX_AGE = datetime.timedelta(hours=3)
# 반대로 이만큼 넘게 미래면(다른 시간대로 해석된 파일 등) 역시 거부한다.
_WEATHER_MAX_AHEAD = datetime.timedelta(hours=1)
_TIMEOUT_SEC = 50  # Cowork 전송 상한 60초보다 짧게
_KST = datetime.timezone(datetime.timedelta(hours=9))


def _now_utc() -> datetime.datetime:
    """지금(UTC). 테스트가 바꿔 끼우는 이음새."""
    return datetime.datetime.now(datetime.timezone.utc)


def is_host_abs_path(value: str) -> bool:
    """itda-hyve 가 쓸 **호스트** 절대 경로인가.

    Cowork 는 리눅스 VM 에서 스크립트를 돌리고 itda-hyve 는 사용자 PC 에서 돈다 — 호스트가 Windows 면
    `C:\\…`·`C:/…`·`\\\\서버\\…` 이고, 리눅스의 `Path.is_absolute()` 는 이것을 상대 경로로 본다(W10 M1).
    스크립트는 이 값을 경로로 쓰지 않고 호출 인자에 문자열로 싣기만 한다.
    """
    return value.startswith("/") or bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")


def weather_call(lat: float, lon: float, save_dir: str | None) -> dict:
    """itda-hyve `http_request` 에 그대로 넣을 인자. User-Agent 는 싣지 않는다(hyve 기본 UA)."""
    stamp = _now_utc().astimezone(_KST).strftime("%Y%m%d%H%M")
    call: dict[str, Any] = {
        "url": openmeteo_client.BASE_URL,
        "params": openmeteo_client.build_params(lat, lon),
        "timeout_sec": _TIMEOUT_SEC,
    }
    if save_dir:
        call["save_dir"] = save_dir
    call["save_as"] = f"weather-here/openmeteo-{lat:.4f}_{lon:.4f}-{stamp}.json"
    return call


def location_call(save_dir: str | None) -> dict:
    """itda-hyve `location` 에 그대로 넣을 인자 — 저장 이름을 스크립트가 정한다(W9 리뷰 m2)."""
    stamp = _now_utc().astimezone(_KST).strftime("%Y%m%d%H%M")
    call: dict[str, Any] = {}
    if save_dir:
        call["save_dir"] = save_dir
    call["save_as"] = f"weather-here/location-{stamp}.json"
    return call


def _basename(path: str) -> str:
    """`/`·`\\` 어느 구분자든 마지막 토막(Cowork 에 호스트 경로를 넘긴 경우도)."""
    return re.split(r"[\\/]", path)[-1]


def _close(a: float, b: float, wrap: bool = False) -> bool:
    """두 좌표 성분이 허용 차 안인가. NaN·무한은 늘 거짓, 경도는 날짜변경선에서 접는다."""
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    d = abs(a - b)
    if wrap:
        d = min(d, 360.0 - d)
    return d <= _WEATHER_COORD_TOLERANCE


# 위치 출처별 표시(#37). IP 한 곳·합의 실패는 시·도부터 틀릴 수 있다(KT 회선이 성남으로 잡힌 실측).
_APPROX_IP = "(대략·IP 기준)"
_REGION_LEVEL = "(시·도 기준)"


def _place_label(fix: geo_locator.GeoFix | None, lat: float, lon: float) -> tuple[str, str]:
    """좌표로 정한 위치의 (표시 이름, 라벨). 국내만 부른다."""
    coords = f"현재 위치 ({lat:.2f}°N, {lon:.2f}°E)"
    if fix is None:  # --lat/--lon — 출처를 모른다
        return coords, ""
    name = fix.place or coords
    if fix.source == "os" and fix.accuracy != "low":
        return name, ""
    if fix.source == "ip_consensus" and fix.accuracy != "low":
        return name, _REGION_LEVEL
    return name, _APPROX_IP


def _read_weather_file(path: str, lat: float, lon: float) -> tuple[dict | None, str]:
    """itda-hyve 가 저장한 Open-Meteo 응답 파일을 읽어 날씨 dict 로.

    저장 이름(`openmeteo-<위도>_<경도>-<시각>.json` — --weather-request 가 정한다)의 좌표가 요청 좌표와 넷째 자리까지
    같아야 하고, 응답의 latitude/longitude 도 요청 좌표와 0.1° 안이어야 한다(다른 위치의 파일 거부).
    """
    name = _basename(path)
    m = _OM_NAME.match(name)
    if not m:
        return None, (f"{name}: 저장 이름이 계약과 다름 — --weather-request 가 준 save_as 그대로 저장한 파일을 넘기세요")
    if (m.group(1), m.group(2)) != (f"{lat:.4f}", f"{lon:.4f}"):
        return None, (f"{name}: 이름의 좌표({m.group(1)}, {m.group(2)})가 요청 위치({lat:.4f}, {lon:.4f})와 다름 — "
                      "다른 위치의 파일")
    try:
        body = read_input(path)
    except HyveFailure as exc:
        return None, f"{name}: itda-hyve 호출 실패({exc.code})" + (f" — {exc.hyve_message}" if exc.hyve_message else "")
    except HyveInputError as exc:
        return None, f"{name}: {exc}"
    try:
        data = json.loads(body.text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"{name}: JSON 이 아님(차단·오류 페이지일 수 있음)"
    if isinstance(data, dict) and data.get("error") is True:
        return None, f"{name}: Open-Meteo 오류({data.get('reason') or '사유 없음'})"
    if not isinstance(data, dict):
        return None, f"{name}: 응답 형태가 객체가 아님"
    try:
        r_lat = float(data["latitude"])
        r_lon = float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, f"{name}: 응답에 좌표가 없어 어느 위치의 날씨인지 확인할 수 없음"
    if not (_close(r_lat, lat) and _close(r_lon, lon, wrap=True)):
        return None, (
            f"{name}: 응답 좌표({r_lat:.2f}, {r_lon:.2f})가 요청 위치({lat:.2f}, {lon:.2f})와 다름 — "
            "다른 위치의 파일"
        )
    why = _stale_reason(data)
    if why:
        return None, f"{name}: {why}"
    weather = openmeteo_client.parse(data)
    if weather is None:
        return None, f"{name}: current 필드가 없음"
    return weather, ""


def _stale_reason(data: dict) -> str:
    """응답의 관측 시각(`current.time` + `utc_offset_seconds`)이 지금과 너무 멀면 사유를 돌려준다."""
    current = data.get("current")
    if not isinstance(current, dict):
        return ""  # parse 가 "current 필드가 없음" 으로 거부한다
    try:
        local = datetime.datetime.fromisoformat(str(current["time"]))
        offset = datetime.timedelta(seconds=int(data["utc_offset_seconds"]))
    except (KeyError, TypeError, ValueError):
        return "응답에 관측 시각(current.time·utc_offset_seconds)이 없어 언제 날씨인지 확인할 수 없음"
    tz = datetime.timezone(offset)
    observed = local.replace(tzinfo=tz)
    now = _now_utc()
    if now - observed > _WEATHER_MAX_AGE:
        return f"관측 시각 {current['time']} 이 {int(_WEATHER_MAX_AGE.total_seconds() // 3600)}시간 넘게 지난 묵은 파일"
    if observed - now > _WEATHER_MAX_AHEAD:
        return f"관측 시각 {current['time']} 이 지금보다 미래 — 다른 시각의 파일"
    # "오늘" 요약(강수확률·최고·최저)은 daily 첫 날이다 — 자정을 넘긴 파일이면 어제의 오늘이다(W9 리뷰 m6)
    daily = data.get("daily")
    if isinstance(daily, dict) and daily.get("time") is not None:
        times = daily.get("time")
        today = now.astimezone(tz).date().isoformat()
        if not (isinstance(times, list) and times and str(times[0]) == today):
            first = times[0] if isinstance(times, list) and times else times
            return f"예보 날짜 {first} 가 오늘({today})이 아님 — 자정 전에 받은 파일"
    return ""


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
        fix, reasons = geo_locator.locate_fix_from_files(args.geo_input, now=_now_utc())
        if fix is None:
            detail = "\n".join(f"  - {r}" for r in reasons)
            return _stop_unresolved(
                "받아 둔 위치 응답에서 위치를 확정하지 못해 멈춥니다(틀린 위치로 날씨를 내지 않습니다).\n"
                f"{detail}\n"
                "지역명을 알려주세요(예: 서울)."
            ), 0.0, 0.0, "", False, None
        return EXIT_OK, fix.lat, fix.lon, "", True, fix

    # --- 위치 입력 없음 — 스크립트는 IP 를 조회하지 않는다(#46) ---
    return _stop_unresolved(
        "현재 위치를 받지 않아 멈춥니다(틀린 위치로 날씨를 내지 않습니다).\n" + _LOCATION_HINT
    ), 0.0, 0.0, "", False, None


def _location_args(args: argparse.Namespace) -> str:
    """--weather-input 단계에 다시 줄 위치 인자(같은 위치여야 이름·응답 좌표 대조가 맞는다). 셸에 그대로 쓸 수 있게 인용한다."""
    if args.location:
        return f"{shlex.quote(args.location)} "
    if args.lat is not None:
        return f"--lat {args.lat} --lon {args.lon} "
    return "".join(f"--geo-input {shlex.quote(g)} " for g in args.geo_input or [])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="현재 위치 또는 지정 지역의 날씨를 한국어로 조회합니다.",
        add_help=True,
    )
    parser.add_argument(
        "location",
        nargs="?",
        default=None,
        help="조회할 지역명 (생략 시 --lat/--lon 또는 --geo-input 의 현재 위치)",
    )
    parser.add_argument("--lat", type=float, default=None, help="위도 (itda-hyve 로 받은 위치)")
    parser.add_argument("--lon", type=float, default=None, help="경도 (--lat 과 함께)")
    parser.add_argument(
        "--geo-input",
        action="append",
        default=None,
        metavar="FILE",
        help="itda-hyve location 응답 파일(여러 번 주면 앞에서부터 첫 유효값)",
    )
    parser.add_argument(
        "--weather-input",
        default=None,
        metavar="FILE",
        help="itda-hyve 가 저장한 Open-Meteo 응답 파일",
    )
    parser.add_argument(
        "--weather-request",
        action="store_true",
        help="Open-Meteo 를 itda-hyve http_request 로 부를 인자(JSON call)를 출력하고 끝낸다",
    )
    parser.add_argument(
        "--location-request",
        action="store_true",
        help="itda-hyve location 도구에 그대로 넣을 인자(JSON call — 저장 이름)를 출력하고 끝낸다",
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        metavar="DIR",
        help="--weather-request·--location-request 의 save_dir — itda-hyve 가 쓸 호스트 절대 경로(Cowork 연결 폴더, Windows 호스트면 C:\\…)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="상세 출력(기온·습도·강수량·풍속+강수확률). 기본은 gist만",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. 종료 코드: 0 정상 · 1 지역 미수록/날씨 응답 판독 실패 · 2 인자 오류 · 3 위치 미확정."""
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게(windows-console-utf8-output).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.location_request:
        if args.save_dir is not None and not is_host_abs_path(args.save_dir):
            parser.error("--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로입니다(/Users/… 또는 C:\\…).")
        if args.location or args.lat is not None or args.geo_input or args.weather_request or args.weather_input:
            parser.error("--location-request 는 위치·날씨 인자 없이 씁니다(--save-dir 만).")
        call = location_call(args.save_dir)
        save = f" --save-dir {shlex.quote(args.save_dir)}" if args.save_dir else ""
        print(json.dumps({"status": "ok", "call": call,
                          "then": f"--geo-input <저장한 파일> --weather-request{save}"}, ensure_ascii=False))
        return EXIT_OK

    if (args.lat is None) != (args.lon is None):
        parser.error("--lat 과 --lon 은 함께 줘야 합니다.")
    if args.lat is not None and args.geo_input:
        parser.error("--lat/--lon 과 --geo-input 은 함께 쓸 수 없습니다.")
    if args.weather_request and args.weather_input:
        parser.error("--weather-request 와 --weather-input 은 함께 쓸 수 없습니다.")
    if args.save_dir is not None:
        if not args.weather_request:
            parser.error("--save-dir 는 --weather-request 와 함께 씁니다.")
        if not is_host_abs_path(args.save_dir):
            parser.error("--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로입니다(/Users/… 또는 C:\\…).")

    code, lat, lon, location_name, by_coords, fix = _resolve_location(args)
    if code != EXIT_OK:
        return code
    if not (args.weather_request or args.weather_input):
        # 위치는 정했지만 날씨를 받을 길이 없다 — 스크립트는 Open-Meteo 를 직접 부르지 않는다(#46)
        parser.error(
            "날씨는 itda-hyve 가 받습니다 — 같은 위치 인자에 --weather-request 를 붙여 호출 인자(call)를 받고, "
            "저장한 응답을 --weather-input <파일> 로 넘기세요."
        )

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
        call = weather_call(lat, lon, args.save_dir)
        loc_args = _location_args(args)
        print(json.dumps({
            "status": "ok",
            "call": call,
            "then": f"{loc_args}--weather-input <저장한 파일>".strip(),
        }, ensure_ascii=False))
        return EXIT_OK

    weather, reason = _read_weather_file(args.weather_input, lat, lon)
    if weather is None:
        print(
            "받아 둔 날씨 응답을 쓸 수 없습니다.\n"
            f"  - {reason}\n"
            "같은 위치 인자로 --weather-request 를 다시 뽑아 itda-hyve 로 받아 주세요.",
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
