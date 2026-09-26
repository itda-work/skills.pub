"""flight-search fast-flights 어댑터 — Google Flights 조회를 한 곳에 격리.

fast-flights(Google Flights 공개 표면 스크래퍼)의 지연 import·예외 변환·
fetch 모드 폴백·예약검색 URL 생성을 담당한다. 순수 로직(가격·출력·집계)은
format_out.py 에, 입력 해석은 airports.py 에 둔다. 이 모듈은 fast-flights 가
설치되지 않은 환경에서도 import 가능해야 한다(단위 테스트는 mock 사용).
따라서 fast_flights 는 함수 안에서 지연 import 한다.

⚠️ Google Flights 공개 검색 표면만 사용한다(로그인·API key·결제·CAPTCHA
우회 없음). Google 측 HTML/프론트 변경 시 파싱이 깨질 수 있으며, 모든 실패는
사람이 읽을 FlightError 하위로 표면화한다(fail-loud).

fetch 모드(사용자 결정: 직접 우선 + 폴백):
- common  : primp(Rust TLS impersonation)로 직접 조회. 추가 브라우저 불필요. 기본.
- fallback: 외부 fetch 서버 경유(검색 조건이 그 서버로 전달됨). common 차단 시에만.
- local   : playwright. 사용하지 않음(미설치 의존).
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.parse import urlencode

__all__ = [
    "FlightError",
    "FlightDependencyMissing",
    "FlightFetchError",
    "DEFAULT_FETCH_ORDER",
    "FLIGHT_KEYS",
    "build_flight_data",
    "fetch_result",
    "result_to_dicts",
    "current_band",
    "build_booking_url",
    "search",
]

# Flight dataclass 필드(fast-flights 2.2 실측). non-dataclass 폴백 키로도 사용.
FLIGHT_KEYS = (
    "is_best",
    "name",
    "departure",
    "arrival",
    "arrival_time_ahead",
    "duration",
    "stops",
    "delay",
    "price",
)

# 직접(common) 우선, 차단 시 외부서버(fallback) 폴백 — 사용자 결정.
DEFAULT_FETCH_ORDER = ("common", "fallback")


# ---------------------------------------------------------------------------
# 예외 계층 — 모든 실패는 사유를 담아 FlightError 하위로 표면화(fail-loud)
# ---------------------------------------------------------------------------


class FlightError(Exception):
    """flight-search 공통 예외. 메시지는 사용자에게 그대로 보일 사유."""


class FlightDependencyMissing(FlightError):
    """fast-flights 미설치."""


class FlightFetchError(FlightError):
    """Google Flights 조회 실패(차단·네트워크·파싱·먼 미래 등)."""


_INSTALL_GUIDE = (
    "fast-flights 라이브러리를 불러올 수 없습니다.\n\n"
    "항공권 검색은 Google Flights 공개 표면을 fast-flights 로 조회합니다.\n"
    "설치 후 다시 시도하세요:\n"
    "  python3 -m pip install fast-flights\n"
    "  (또는: python3 -m pip install fast-flights==2.2)\n"
)


def _load_fast_flights():
    """fast_flights 모듈을 지연 import. 부재 시 FlightDependencyMissing."""
    try:
        import fast_flights  # type: ignore  # noqa: F401
    except ImportError as exc:
        raise FlightDependencyMissing(_INSTALL_GUIDE) from exc
    return fast_flights


# ---------------------------------------------------------------------------
# 조회 — common 직접 우선, 차단 시 fallback(외부서버) 폴백
# ---------------------------------------------------------------------------


def build_flight_data(origin: str, dest: str, date: str, return_date: str | None = None):
    """FlightData 리스트 + trip 문자열 생성(origin/dest 는 검증된 IATA 가정)."""
    ff = _load_fast_flights()
    flight_data_cls = ff.FlightData
    data = [flight_data_cls(date=date, from_airport=origin, to_airport=dest)]
    if return_date:
        data.append(flight_data_cls(date=return_date, from_airport=dest, to_airport=origin))
        return data, "round-trip"
    return data, "one-way"


def _translate_fetch_failure(errors: list[str]) -> str:
    """모드별 실패 메시지를 사람이 읽을 사유로 변환(원문 보존)."""
    joined = " | ".join(errors)
    upper = joined.upper()
    if "NO FLIGHTS" in upper:
        # 먼 미래·운항 없음 등 — 차단이 아니라 '결과 없음'(fallback 토큰오류가
        # 섞여도 근본 원인은 결과 없음이므로 우선 판별).
        return (
            "해당 날짜·노선의 항공편을 찾지 못했습니다"
            "(너무 먼 미래이거나 운항이 없을 수 있습니다)."
        )
    if "403" in joined or "429" in joined or "BLOCK" in upper or "CAPTCHA" in upper:
        # 차단 신호를 토큰오류보다 먼저 판별 — 둘 다일 때 더 actionable 한 차단을
        # 헤드라인에 둔다(common 차단 + fallback 토큰오류 공존 케이스).
        head = "Google Flights 에 일시 차단되었을 수 있습니다. 잠시 후 재시도하세요."
    elif "NO TOKEN" in upper or "401" in joined:
        head = (
            "Google Flights 조회에 실패했습니다(외부 fetch 서버 토큰 오류). "
            "잠시 후 다시 시도하세요."
        )
    else:
        head = (
            "Google Flights 조회에 실패했습니다. 노선·날짜를 확인하거나 잠시 후 "
            "재시도하세요."
        )
    return f"{head}\n(상세: {joined})"


def fetch_result(
    flight_data: list,
    trip: str,
    adults: int,
    seat: str,
    *,
    fetch_order: tuple[str, ...] = DEFAULT_FETCH_ORDER,
):
    """get_flights 를 fetch_order 순으로 시도(앞 모드 실패 시 다음으로 폴백).

    빈 결과(0편)는 '차단'이 아니라 '결과 없음'으로 보고 폴백하지 않는다(불필요한
    외부서버 노출·중복요청 회피). 모든 모드가 예외면 FlightFetchError 로 표면화.
    """
    ff = _load_fast_flights()
    get_flights = ff.get_flights
    passengers_cls = ff.Passengers
    errors: list[str] = []
    for mode in fetch_order:
        try:
            return get_flights(
                flight_data=flight_data,
                trip=trip,
                passengers=passengers_cls(adults=adults),
                seat=seat,
                fetch_mode=mode,
            )
        except Exception as exc:  # noqa: BLE001 — 모든 실패를 사유와 함께 모은다
            errors.append(f"{mode}: {type(exc).__name__}: {str(exc)[:120]}")
            continue
    raise FlightFetchError(_translate_fetch_failure(errors))


def result_to_dicts(result: Any) -> list[dict[str, Any]]:
    """Result.flights(Flight dataclass)를 순수 dict 리스트로(경계 변환)."""
    out: list[dict[str, Any]] = []
    for f in getattr(result, "flights", []) or []:
        if is_dataclass(f) and not isinstance(f, type):
            out.append(asdict(f))
        else:
            out.append({k: getattr(f, k, None) for k in FLIGHT_KEYS})
    return out


def current_band(result: Any) -> str:
    """Result.current_price(low/typical/high band) 안전 추출."""
    return getattr(result, "current_price", "") or ""


# ---------------------------------------------------------------------------
# 예약 검색 URL — Google Flights 검색 링크(특정 판매자 deep link 아님)
# ---------------------------------------------------------------------------


def _encode_tfs(
    origin: str, dest: str, date: str, return_date: str | None, adults: int, seat: str
) -> str:
    """TFSData base64(라이브러리 의존). url 조립과 분리해 테스트 가능하게 둔다."""
    ff = _load_fast_flights()
    from fast_flights.flights_impl import Passengers as PImpl  # noqa: PLC0415
    from fast_flights.flights_impl import TFSData  # noqa: PLC0415

    flight_data_cls = ff.FlightData
    data = [flight_data_cls(date=date, from_airport=origin, to_airport=dest)]
    trip = "one-way"
    if return_date:
        data.append(flight_data_cls(date=return_date, from_airport=dest, to_airport=origin))
        trip = "round-trip"
    return (
        TFSData.from_interface(
            flight_data=data, trip=trip, passengers=PImpl(adults=adults), seat=seat
        )
        .as_b64()
        .decode("utf-8")
    )


def build_booking_url(
    origin: str,
    dest: str,
    date: str,
    return_date: str | None = None,
    *,
    adults: int = 1,
    seat: str = "economy",
) -> str:
    """Google Flights 예약 검색 URL(tfs base64). deep link 아님(검색 링크)."""
    tfs = _encode_tfs(origin, dest, date, return_date, adults, seat)
    params = {"tfs": tfs, "hl": "ko", "tfu": "EgQIABABIgA", "curr": "KRW"}
    return "https://www.google.com/travel/flights?" + urlencode(params)


def search(
    origin: str,
    dest: str,
    date: str,
    return_date: str | None = None,
    *,
    adults: int = 1,
    seat: str = "economy",
    fetch_order: tuple[str, ...] = DEFAULT_FETCH_ORDER,
) -> tuple[list[dict[str, Any]], str, str]:
    """조회 한 번 — (raw_flight_dicts, price_band, booking_url) 반환.

    origin/dest 는 검증된 IATA 라고 가정한다(airports.resolve_airport 통과 후).
    """
    data, trip = build_flight_data(origin, dest, date, return_date)
    result = fetch_result(data, trip, adults, seat, fetch_order=fetch_order)
    url = build_booking_url(origin, dest, date, return_date, adults=adults, seat=seat)
    return result_to_dicts(result), current_band(result), url
