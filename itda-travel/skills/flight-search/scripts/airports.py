"""flight-search 공항·IATA 해석 — 순수 모듈(네트워크 의존 0).

IATA 3-letter 코드 검증, 흔한 한국어 도시명→IATA 힌트, 동일 출도착 거부를
담당한다. fast-flights 등 네트워크 의존은 flights_adapter.py 에 격리하고,
이 모듈은 입력 해석만 한다(단위 테스트 100% 가능).

도시명 사전은 '편의용 힌트'이지 완전한 공항 DB 가 아니다. 기본 입력은 IATA
코드이며(예: --from ICN), 사전에 없는 도시는 IATA 직접 지정을 요구한다.
모호한 도시(도쿄=NRT/HND 등)는 AmbiguousCity 로 올려 Claude 가 사용자에게
어느 공항인지 확인하도록 한다(SKILL.md 라우팅 가이드 규칙 1).
"""
from __future__ import annotations

import re

__all__ = [
    "AirportError",
    "AmbiguousCity",
    "normalize_iata",
    "resolve_airport",
    "ensure_distinct",
]


class AirportError(ValueError):
    """공항 입력 오류 — 메시지는 사용자에게 그대로 보일 사유."""


class AmbiguousCity(AirportError):
    """도시명이 여러 공항에 대응 — Claude 가 사용자에게 확인해야 한다."""

    def __init__(self, city: str, candidates: list[str]):
        self.city = city
        self.candidates = list(candidates)
        super().__init__(
            f"'{city}' 는 여러 공항이 있습니다: {', '.join(self.candidates)}. "
            "어느 공항인지 IATA 코드로 지정해 주세요."
        )


_IATA_RE = re.compile(r"^[A-Za-z]{3}$")

# 흔한 한국어 도시명 → IATA 힌트(편의). 단일=대표공항, 다중=모호(확인 필요).
# 한국 출발 공항 + 한국발 인기 목적지 위주. 완전한 DB 아님(IATA 직접이 기본).
_CITY_HINTS: dict[str, list[str]] = {
    # 한국 출발
    "서울": ["ICN"],  # 국제선 기본 인천. 김포는 '김포'로 별도 지정.
    "인천": ["ICN"],
    "김포": ["GMP"],
    "부산": ["PUS"],
    "제주": ["CJU"],
    "대구": ["TAE"],
    "광주": ["KWJ"],
    "청주": ["CJJ"],
    "무안": ["MWX"],
    "양양": ["YNY"],
    # 일본
    "도쿄": ["NRT", "HND"],
    "오사카": ["KIX"],
    "후쿠오카": ["FUK"],
    "삿포로": ["CTS"],
    "오키나와": ["OKA"],
    "나고야": ["NGO"],
    # 동남아·중화권
    "방콕": ["BKK"],
    "싱가포르": ["SIN"],
    "홍콩": ["HKG"],
    "타이베이": ["TPE"],
    "다낭": ["DAD"],
    "하노이": ["HAN"],
    "호치민": ["SGN"],
    "마닐라": ["MNL"],
    "세부": ["CEB"],
    "상하이": ["PVG"],
    "베이징": ["PEK"],
    # 미주·대양주·중동·유럽
    "괌": ["GUM"],
    "사이판": ["SPN"],
    "로스앤젤레스": ["LAX"],
    "엘에이": ["LAX"],
    "뉴욕": ["JFK", "EWR", "LGA"],
    "샌프란시스코": ["SFO"],
    "런던": ["LHR", "LGW"],
    "파리": ["CDG"],
    "프랑크푸르트": ["FRA"],
    "두바이": ["DXB"],
    "시드니": ["SYD"],
}


def normalize_iata(code: str, field: str = "공항") -> str:
    """IATA 3-letter 코드를 대문자로 정규화·검증한다.

    형식이 아니면 AirportError(사용자에게 보일 사유)를 올린다.
    """
    norm = (code or "").strip().upper()
    if not _IATA_RE.match(norm):
        raise AirportError(
            f"{field}는 3-letter IATA 공항코드여야 합니다(예: ICN, NRT). 입력값: {code!r}"
        )
    return norm


def resolve_airport(value: str, field: str = "공항") -> str:
    """입력을 IATA 코드로 해석한다.

    - 이미 IATA(3 letter)면 대문자로 그대로.
    - 알려진 한국어 도시명이면 힌트 매핑(단일 후보).
    - 모호한 도시명(다중 후보)이면 AmbiguousCity(Claude 가 확인).
    - 알 수 없으면 AirportError(IATA 직접 지정 요구).
    """
    raw = (value or "").strip()
    if not raw:
        raise AirportError(f"{field}가 비어 있습니다. IATA 코드(예: ICN)를 지정하세요.")
    if _IATA_RE.match(raw):
        return raw.upper()
    hints = _CITY_HINTS.get(raw)
    if hints is None:
        raise AirportError(
            f"{field} '{raw}' 의 공항코드를 알 수 없습니다. IATA 코드로 지정하세요(예: ICN)."
        )
    if len(hints) > 1:
        raise AmbiguousCity(raw, hints)
    return hints[0]


def ensure_distinct(origin: str, dest: str) -> None:
    """출발·도착이 같으면 AirportError. fast-flights 호출 전 사전 검증."""
    if origin == dest:
        raise AirportError(
            f"출발과 도착 공항이 같습니다({origin}). 서로 다른 공항을 지정하세요."
        )
