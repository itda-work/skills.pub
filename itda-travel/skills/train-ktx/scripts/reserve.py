"""예약 확인 게이트 + 예약 실행 (SAFE-1, REQ-004).

핵심 안전장치: ``execute_reservation`` 은 ``confirm=True`` 일 때만 실제 예약을
호출한다. ``--confirm`` 플래그가 없으면(미리보기) 어떤 경우에도 ``client.reserve``
가 호출되지 않는다 — 문서 규칙(AskUserQuestion)이 아니라 코드로 강제하는
게이트다(AC-2). 이 함수와 ``select_train`` 은 korail2 없이도 동작·테스트된다.

승객·좌석유형 상수는 korail2 에 의존하므로 지연 로드한다(라이브 전용).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from korail_adapter import load_korail_module  # noqa: E402


def select_train(trains: list, index: int):
    """검색 결과에서 index 번째 열차 선택. 범위 밖/빈 목록이면 IndexError."""
    if not trains:
        raise IndexError("검색 결과가 비어 있어 선택할 열차가 없습니다.")
    if index < 0 or index >= len(trains):
        raise IndexError(
            f"선택한 번호 {index} 가 범위를 벗어났습니다 (0 ~ {len(trains) - 1})."
        )
    return trains[index]


def execute_reservation(client, train, passengers=None, option=None, *, confirm: bool):
    """``confirm=True`` 일 때만 ``client.reserve`` 를 호출한다(SAFE-1 코드 게이트).

    ``confirm=False`` 면 None 을 반환하고 예약 호출을 하지 않는다. 호출자(main)는
    이 경우 미리보기만 출력하고, 사용자 확인 후 ``--confirm`` 으로 재호출한다.
    """
    if not confirm:
        return None
    return client.reserve(train, passengers=passengers, option=option)


# ---------------------------------------------------------------------------
# 아래는 korail2 상수에 의존(라이브 전용) — 지연 로드
# ---------------------------------------------------------------------------


def build_passengers(adults: int = 1, children: int = 0, seniors: int = 0):
    """승객 리스트 구성. 전원 0이면 None(기본 성인 1명은 호출부 책임)."""
    k = load_korail_module()
    out = []
    if adults > 0:
        out.append(k.AdultPassenger(adults))
    if children > 0:
        out.append(k.ChildPassenger(children))
    if seniors > 0:
        out.append(k.SeniorPassenger(seniors))
    return out or None


def train_type_code(name: str | None):
    """열차종 이름 → korail2 TrainType 코드. 기본 KTX."""
    k = load_korail_module()
    table = {
        "ktx": k.TrainType.KTX,
        "all": k.TrainType.ALL,
        "saemaeul": k.TrainType.SAEMAEUL,
        "mugunghwa": k.TrainType.MUGUNGHWA,
    }
    if not name:
        return k.TrainType.KTX
    return table.get(name.lower(), k.TrainType.KTX)


def reserve_option_code(seat: str | None, only: bool = False):
    """좌석유형 → korail2 ReserveOption. seat: 'general' | 'special'."""
    k = load_korail_module()
    seat = (seat or "general").lower()
    if seat == "special":
        return k.ReserveOption.SPECIAL_ONLY if only else k.ReserveOption.SPECIAL_FIRST
    return k.ReserveOption.GENERAL_ONLY if only else k.ReserveOption.GENERAL_FIRST
