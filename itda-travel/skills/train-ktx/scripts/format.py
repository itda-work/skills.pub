"""검색결과·예약 표기 — korail2 객체를 사람이 읽을 한국어로 변환한다(REQ-002/010).

순수 모듈(네트워크 의존 없음, NFR-005). korail2 Train/Reservation 객체의 공개
속성·메서드만 읽으며, 단위 테스트는 동일 인터페이스의 가짜 객체로 검증한다.
좌석 가능 여부(일반/특실)와 운임을 표기하고, 매진/대기를 구분한다.
"""
from __future__ import annotations

from typing import Any


def format_time(hhmmss: str | None) -> str:
    """'HHMMSS'(또는 'HHMM')를 'HH:MM'으로. 형식 불명이면 원문 유지."""
    if not hhmmss:
        return ""
    digits = "".join(ch for ch in str(hhmmss) if ch.isdigit())
    if len(digits) >= 4:
        return f"{digits[0:2]}:{digits[2:4]}"
    return str(hhmmss)


def format_date(yyyymmdd: str | None) -> str:
    """'YYYYMMDD'를 'YYYY-MM-DD'로. 형식 불명이면 원문 유지."""
    if not yyyymmdd:
        return ""
    digits = "".join(ch for ch in str(yyyymmdd) if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return str(yyyymmdd)


def _seat_status(train: Any, kind: str) -> str:
    """좌석 상태 문자열. kind: 'general' | 'special'.

    예약가능 > 대기가능 > 매진 순으로 판별한다. 메서드가 없으면 '정보없음'.
    """
    has_seat = getattr(train, f"has_{kind}_seat", None)
    has_wait = getattr(train, f"has_{kind}_waiting_list", None)
    if callable(has_seat) and has_seat():
        return "예약가능"
    if callable(has_wait) and has_wait():
        return "대기가능"
    if callable(has_seat):
        return "매진"
    return "정보없음"


def train_to_dict(train: Any, index: int) -> dict:
    """Train 객체를 표준 dict로(REQ-002). --json 출력·표기 공통 입력."""
    return {
        "index": index,
        "train_type": getattr(train, "train_type_name", "") or "",
        "train_no": getattr(train, "train_no", "") or "",
        "dep_name": getattr(train, "dep_name", "") or "",
        "dep_time": format_time(getattr(train, "dep_time", "")),
        "arr_name": getattr(train, "arr_name", "") or "",
        "arr_time": format_time(getattr(train, "arr_time", "")),
        "general_seat": _seat_status(train, "general"),
        "special_seat": _seat_status(train, "special"),
    }


def format_train_line(info: dict) -> str:
    """train dict 한 건을 한 줄 한국어로."""
    return (
        f"[{info['index']}] {info['dep_time']} → {info['arr_time']}  "
        f"{info['train_type']} {info['train_no']}  "
        f"({info['dep_name']}→{info['arr_name']})  "
        f"일반실 {info['general_seat']} · 특실 {info['special_seat']}"
    )


def format_search_results(trains: list, dep: str, arr: str, date: str | None) -> str:
    """검색 결과 전체를 한국어 텍스트로(REQ-010). 빈 목록도 명시적으로 안내."""
    header = f"🚄 {dep} → {arr}"
    if date:
        header += f"  ({format_date(date)})"
    if not trains:
        return (
            header
            + "\n\n조건에 맞는 열차를 찾지 못했습니다. 날짜·시각·역명을 확인해 주세요."
        )
    lines = [header, ""]
    for i, train in enumerate(trains):
        lines.append(format_train_line(train_to_dict(train, i)))
    lines.append("")
    lines.append(
        "예약하려면 위 번호를 선택하세요. 예약 후 결제는 코레일 앱/웹에서 직접 진행합니다."
    )
    return "\n".join(lines)


def reservation_to_dict(reservation: Any) -> dict:
    """Reservation 객체를 표준 dict로(REQ-004). 결제기한·운임 포함."""
    return {
        "rsv_id": getattr(reservation, "rsv_id", "") or "",
        "train_type": getattr(reservation, "train_type_name", "") or "",
        "train_no": getattr(reservation, "train_no", "") or "",
        "dep_name": getattr(reservation, "dep_name", "") or "",
        "dep_time": format_time(getattr(reservation, "dep_time", "")),
        "arr_name": getattr(reservation, "arr_name", "") or "",
        "arr_time": format_time(getattr(reservation, "arr_time", "")),
        "price": getattr(reservation, "price", None),
        "buy_limit_time": format_time(getattr(reservation, "buy_limit_time", "")),
        "buy_limit_date": format_date(getattr(reservation, "buy_limit_date", "")),
        "seat_no_count": getattr(reservation, "seat_no_count", None),
    }


def format_reservation(info: dict) -> str:
    """예약 1건을 한국어로. 결제기한과 '결제는 직접' 안내를 항상 포함(SAFE-2)."""
    price = info.get("price")
    price_txt = f"{int(price):,}원" if price not in (None, "") else "운임 확인 필요"
    limit = " ".join(x for x in [info.get("buy_limit_date", ""), info.get("buy_limit_time", "")] if x)
    limit_txt = limit or "코레일 앱에서 확인"
    return (
        f"예약번호 {info['rsv_id']}\n"
        f"  {info['train_type']} {info['train_no']}  "
        f"{info['dep_name']} {info['dep_time']} → {info['arr_name']} {info['arr_time']}\n"
        f"  운임: {price_txt}\n"
        f"  ⏰ 결제기한: {limit_txt} (미결제 시 자동 취소됩니다)\n"
        f"  💳 결제는 코레일 앱/웹에서 직접 진행하세요(이 스킬은 결제하지 않습니다)."
    )
