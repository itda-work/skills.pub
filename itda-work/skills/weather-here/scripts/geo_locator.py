"""geo_locator.py - 위치 결정 모듈 (v0.3.0 개정).

시나리오 A: IP 폴백 체인(ipapi.co → ipwho.is)으로 **위경도만** 반환 (REQ-001/002).
  - Open-Meteo 지오코딩 완전 제거(EXC-6 — 한국 부정확 실증).
  - 반환: (latitude, longitude) tuple 또는 None.
  - success:false 게이트 + _valid_coords() 유한·범위 검증 유지(REQ-002 견고화).

입력 경로(#33): itda-hyve `http_request` 가 받아 저장한 ipapi.co·ipwho.is 응답 파일을
  `locate_from_files()` 로 읽는다 — Cowork 처럼 스크립트가 도는 곳의 IP 가 사용자 PC 가
  아닐 때 쓰는 경로. 스크립트는 이 경로에서 네트워크를 하지 않는다.

itda-hyve `location` 도구 응답(#37, itda-hyve 0.9.3): `source`(`os`·`ip_consensus`·`ip`)·`place`·
  `lat`·`lon`(0.05° 격자)·`accuracy`. 같은 `--geo-input` 으로 받고, 출처·장소는 `GeoFix` 에 실어
  날씨 줄의 표시(장소 이름·"대략" 표시)에 쓴다.

시나리오 B는 region_resolver.py가 담당(이 모듈 무관).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from http_util import fetch_json

# IP 지오로케이션 서비스 URLs (spec.md §4.4)
_IPAPI_URL = "https://ipapi.co/json/"
_IPWHO_URL = "https://ipwho.is/"


# itda-hyve location 의 출처 값(itda-hyve 0.9.3 `internal/location`). 모르는 값도 받되 "대략" 으로 표시한다.
LOCATION_SOURCES = ("os", "ip_consensus", "ip")


@dataclass(frozen=True)
class GeoFix:
    """확정한 위치와 그 출처.

    source: `os`·`ip_consensus`·`ip`(itda-hyve location) · `ipapi`·`ipwho`(받아 둔 IP 서비스 응답) · `ip_single`(스크립트 직접 IP 조회).
    place: 사람이 읽는 장소(location 만 준다, 예: "대전광역시 중구"). accuracy: location 의 등급.
    """

    lat: float
    lon: float
    source: str
    place: str = ""
    accuracy: str = ""
    country: str = ""
    note: str = ""


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


def unwrap_response(data: object) -> tuple[object, str]:
    """itda-hyve `http_request` 응답 봉투(`status`·`body`)면 본문 JSON 을 꺼낸다.

    `save_as` 로 저장한 파일은 API 본문 그대로지만, 도구 응답 전체를 그대로 파일에 쓰는
    소비자(morning-brief `$IN`)도 있다. 둘 다 같은 결과가 되게 한다.

    Returns:
        (본문 데이터, 실패 사유). 사유가 빈 문자열이 아니면 본문을 쓸 수 없다.
    """
    if not (isinstance(data, dict) and isinstance(data.get("body"), str)
            and isinstance(data.get("status"), int)):
        return data, ""
    status = data["status"]
    if data.get("body_truncated"):
        return None, f"응답 본문이 잘림(HTTP {status})"
    try:
        inner = json.loads(data["body"])
    except json.JSONDecodeError:
        return None, f"HTTP {status}, 본문이 JSON 이 아님(차단·오류 페이지일 수 있음)"
    if status != 200:
        reason = (inner.get("reason") or inner.get("message")) if isinstance(inner, dict) else None
        return None, f"HTTP {status}" + (f"({reason})" if reason else "")
    return inner, ""


def locate_from_files(
    paths: list[str],
) -> tuple[tuple[float, float] | None, list[str]]:
    """`locate_fix_from_files` 의 좌표만 돌려주는 판(기존 호출자용)."""
    fix, reasons = locate_fix_from_files(paths)
    return ((fix.lat, fix.lon) if fix else None), reasons


def _location_fix(data: dict) -> tuple[GeoFix | None, str]:
    """itda-hyve `location` 응답이면 GeoFix 로. 아니면 (None, "")."""
    if not ("source" in data and "lat" in data and "lon" in data):
        return None, ""
    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (TypeError, ValueError):
        return None, "location 응답의 위경도가 숫자가 아님"
    if not _valid_coords(lat, lon):
        return None, "location 응답의 위경도가 무효"

    def text(key: str) -> str:
        v = data.get(key)
        return v.strip() if isinstance(v, str) else ""

    return GeoFix(lat=lat, lon=lon, source=text("source") or "unknown", place=text("place"),
                  accuracy=text("accuracy"), country=text("country"), note=text("note")), ""


def locate_fix_from_files(
    paths: list[str],
) -> tuple[GeoFix | None, list[str]]:
    """저장된 위치 응답 파일을 차례로 읽어 첫 유효 위치를 돌려준다.

    파일 내용은 ① itda-hyve `location` 응답(0.9.3 — `source`·`lat`·`lon`·`place`) ② ipapi.co(`/json/`)
    또는 ipwho.is 응답 본문 그대로 ③ 그 본문을 담은 itda-hyve `http_request` 응답 전체(`status`·`body`)다.
    IP 서비스는 `success` 키 유무로 가른다(ipwho.is 만 싣는다). itda-hyve 실패를 기록한
    `{"error": {...}}` 파일도 받아 실패 사유로 센다.

    Returns:
        (위치 또는 None, 파일별 실패 사유 목록). 조용히 버린 파일은 없다 —
        유효 좌표를 못 얻은 파일은 전부 사유가 남는다.
    """
    reasons: list[str] = []
    for raw_path in paths:
        name = Path(raw_path).name
        try:
            text = Path(raw_path).read_text(encoding="utf-8-sig")
        except OSError as exc:
            reasons.append(f"{name}: 파일을 읽을 수 없음({exc.strerror or exc})")
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            reasons.append(f"{name}: JSON 이 아님(차단·오류 페이지일 수 있음)")
            continue
        data, why = unwrap_response(data)
        if why:
            reasons.append(f"{name}: {why}")
            continue
        if not isinstance(data, dict):
            reasons.append(f"{name}: 응답 형태가 객체가 아님")
            continue
        err = data.get("error")
        if isinstance(err, dict):
            code = err.get("code") or "error"
            msg = err.get("message")
            reasons.append(f"{name}: itda-hyve 호출 실패({code})" + (f" — {msg}" if isinstance(msg, str) and msg else ""))
            continue
        if err is True:
            reasons.append(f"{name}: 위치 서비스 오류({data.get('reason') or '사유 없음'})")
            continue
        fix, why = _location_fix(data)
        if why:
            reasons.append(f"{name}: {why}")
            continue
        if fix is not None:
            return fix, reasons
        provider = "ipwho" if "success" in data else "ipapi"
        if provider == "ipwho" and data.get("success") is False:
            reasons.append(f"{name}: 위치 서비스 오류({data.get('message') or '사유 없음'})")
            continue
        loc = _extract_latlon(data, provider=provider)
        if loc is None:
            reasons.append(f"{name}: 위경도 없음 또는 무효")
            continue
        return GeoFix(lat=loc[0], lon=loc[1], source=provider), reasons
    return None, reasons


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
