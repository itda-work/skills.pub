"""geo_locator.py - 위치 파일 판독(itda-hyve `location` 응답).

네트워크를 열지 않는다(itda-work/skills#45·#46, 규칙 ``cowork-network-via-hyve``). 위치는 itda-hyve 가
받아 저장한 파일을 ``--geo-input`` 으로 읽는다 — 스크립트가 직접 IP 를 조회하던 경로(``locate_by_ip``)는
0.15.0 에서 지웠다. hyve 층(본문 그대로·응답 JSON 전체·실패 자리)은 공용 ``shared/hyve_input.py`` 가 판독한다.

IP 서비스 응답(ipapi.co·ipwho.is — ``location`` 도구 이전 옛 판의 경로)은 **받지 않는다**(W9 리뷰 m1): 요구 판(itda-hyve
0.10.4)에는 ``location`` 이 늘 있고, ``location`` 이 실패했을 때 IP 서비스를 따로 부르지 않는다는 규칙을 코드로도 지킨다.
``location`` 응답의 ``as_of`` 가 1시간 넘게 지났으면 받지 않는다(W9 리뷰 m2). _valid_coords() 유한·범위 검증 유지.

itda-hyve `location` 도구 응답(#37, itda-hyve 0.9.3): `source`(`os`·`ip_consensus`·`ip`)·`place`·
  `lat`·`lon`(0.05° 격자)·`accuracy`. 같은 `--geo-input` 으로 받고, 출처·장소는 `GeoFix` 에 실어
  날씨 줄의 표시(장소 이름·"대략" 표시)에 쓴다.

시나리오 B는 region_resolver.py가 담당(이 모듈 무관).
"""
from __future__ import annotations

import json
import math
import datetime
import re
from dataclasses import dataclass

from hyve_input import HyveFailure, HyveInputError, read_input


# itda-hyve location 의 출처 값(itda-hyve 0.9.3 `internal/location`). 모르는 값도 받되 "대략" 으로 표시한다.
LOCATION_SOURCES = ("os", "ip_consensus", "ip")

# location 응답(as_of)이 이보다 오래되면 현재 위치가 아니다. itda-hyve 는 10분 캐시한다.
LOCATION_MAX_AGE = datetime.timedelta(hours=1)


@dataclass(frozen=True)
class GeoFix:
    """확정한 위치와 그 출처.

    source: `os`·`ip_consensus`·`ip`(itda-hyve location).
    place: 사람이 읽는 장소(location 만 준다, 예: "대전광역시 중구"). accuracy: location 의 등급.
    """

    lat: float
    lon: float
    source: str
    place: str = ""
    accuracy: str = ""
    country: str = ""
    note: str = ""


def _basename(path: str) -> str:
    return re.split(r"[\\/]", path)[-1]


def _age_reason(data: dict, now: datetime.datetime | None) -> str:
    """`as_of` 가 있으면 지금과의 차를 본다 — 1시간 넘게 지났거나 미래면 사유."""
    raw = data.get("as_of")
    if now is None or raw is None:
        return ""
    try:
        # itda-hyve 는 RFC3339(`time.RFC3339`)로 쓴다 — 호스트 시간대가 UTC 면 `…Z`. Python 3.10 의 fromisoformat 은
        # `Z` 를 못 읽는다(3.11 부터) — Cowork 샌드박스가 3.10 이다(W9 재확인 m1).
        text = str(raw).strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        as_of = datetime.datetime.fromisoformat(text)
    except ValueError:
        return f"as_of({raw})를 읽을 수 없음"
    if as_of.tzinfo is None:
        return f"as_of({raw})에 시간대가 없음"
    if now - as_of > LOCATION_MAX_AGE:
        return f"위치가 {raw} 것 — 1시간 넘게 지나 현재 위치가 아님(location 을 다시 받으세요)"
    if as_of - now > LOCATION_MAX_AGE:
        return f"위치 시각 {raw} 이 지금보다 미래"
    return ""


def locate_from_files(
    paths: list[str], now: datetime.datetime | None = None,
) -> tuple[tuple[float, float] | None, list[str]]:
    """`locate_fix_from_files` 의 좌표만 돌려주는 판(기존 호출자용)."""
    fix, reasons = locate_fix_from_files(paths, now=now)
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
    paths: list[str], now: datetime.datetime | None = None,
) -> tuple[GeoFix | None, list[str]]:
    """저장된 위치 응답 파일을 차례로 읽어 첫 유효 위치를 돌려준다.

    받는 것은 itda-hyve `location` 응답(`source`·`lat`·`lon`·`place`·`as_of`)뿐이다(hyve 층 세 형태는 공용 판독).
    itda-hyve 실패를 기록한 `{"error": {...}}` 파일은 사유로 센다. IP 서비스 응답(ipapi.co·ipwho.is)과
    `now` 기준 1시간 넘은 `as_of` 는 사유와 함께 거부한다.

    Returns:
        (위치 또는 None, 파일별 실패 사유 목록). 조용히 버린 파일은 없다 —
        유효 좌표를 못 얻은 파일은 전부 사유가 남는다.
    """
    reasons: list[str] = []
    for raw_path in paths:
        name = _basename(raw_path)
        try:
            body = read_input(raw_path)
        except HyveFailure as exc:
            msg = exc.hyve_message
            reasons.append(f"{name}: itda-hyve 호출 실패({exc.code})" + (f" — {msg}" if msg else ""))
            continue
        except HyveInputError as exc:
            reasons.append(f"{name}: {exc}")
            continue
        try:
            data = json.loads(body.text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            reasons.append(f"{name}: JSON 이 아님(차단·오류 페이지일 수 있음)")
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
            why = _age_reason(data, now)
            if why:
                reasons.append(f"{name}: {why}")
                continue
            return fix, reasons
        if "latitude" in data or "success" in data or "ip" in data:
            reasons.append(f"{name}: IP 서비스 응답(ipapi.co·ipwho.is)은 받지 않음 — itda-hyve location 도구로 받은 파일을 넘기세요")
            continue
        reasons.append(f"{name}: 위경도 없음 — location 응답이 아님(저장 요약이면 saved_path 의 파일을 넘기세요)")
    return None, reasons


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
