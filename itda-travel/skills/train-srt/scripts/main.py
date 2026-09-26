#!/usr/bin/env python3
"""train-srt — 통합 안내 스텁 (기능 없음).

SRT 는 2026-09-01 부로 폐지되고 KTX 로 통합됐다. 9월 1일 이후 운행 열차는
코레일+ 앱·코레일 홈페이지에서만 예매할 수 있고, SR 앱 예매는 8월 31일
운행분까지였다. 따라서 이 스킬의 검색·예약 기능은 전부 제거하고, 어떤
서브커맨드도 통합 안내 후 비정상 종료(rc=2)한다 — 마스터 결정 2026-09-01, #1624.

**되돌리지 마라.** SR 조회 API 는 지금도 응답을 주지만(라이브 실측 확인), 그것을
되살리면 *공식적으로 예매가 중단된 경로*로 사용자를 보내게 된다. 예약 단계에서
조용히 실패하면 사용자는 좌석을 잡은 줄 안다. 옛 SRT 구간(수서·동탄·평택지제)은
train-ktx 가 담당하며, 코레일이 같은 재고를 판매함을 라이브로 실측했다
(열차번호·종별코드·요금 일치 — 수서→부산 06:00 SRT 303 = 코레일 "KTX-산천" 303,
52,400원).

의존 라이브러리 없음(구 SRTrain 의존 제거). 자격증명도 읽지 않는다.
"""
from __future__ import annotations

import json
import sys

#: 안내 종료 코드. 0 이 아니어야 호출자가 "기능 수행됨" 으로 오인하지 않는다.
EXIT_INTEGRATED = 2

INTEGRATION_DATE = "2026-09-01"
SUCCESSOR_SKILL = "train-ktx"
FORMER_SRT_STATIONS = ("수서", "동탄", "평택지제")

_NOTICE = f"""⚠ SRT는 {INTEGRATION_DATE}부터 KTX로 통합되었습니다.

  이 스킬(train-srt)은 더 이상 검색·예약을 수행하지 않습니다.
  {SUCCESSOR_SKILL} 스킬을 사용하세요 — {"·".join(FORMER_SRT_STATIONS)} 출발 열차를 지원합니다.

  예) python3 <train-ktx>/scripts/main.py search --dep 수서 --arr 부산 --date YYYYMMDD

  예매는 코레일+ 앱 / 코레일 홈페이지(letskorail.com)에서 진행합니다.
  {INTEGRATION_DATE} 이후 운행 열차는 SR 앱·etk.srail.kr 에서 예매할 수 없습니다.
  옛 SRT 열차는 코레일 표기로 "KTX" 또는 "KTX-산천"으로 나옵니다(같은 열차입니다)."""


def _payload() -> dict:
    return {
        "status": "integrated",
        "integration_date": INTEGRATION_DATE,
        "successor_skill": SUCCESSOR_SKILL,
        "former_srt_stations": list(FORMER_SRT_STATIONS),
        "message": (
            f"SRT는 {INTEGRATION_DATE}부터 KTX로 통합되었습니다. "
            f"{SUCCESSOR_SKILL} 스킬을 사용하세요."
        ),
        "booking_channel": "코레일+ 앱 / letskorail.com",
    }


def main(argv=None) -> int:
    """인자와 무관하게 통합 안내를 내고 EXIT_INTEGRATED 로 끝낸다.

    argparse 를 쓰지 않는다 — 구 서브커맨드(search/reserve/reservations/check)든
    미지 인자든 **똑같이 안내에 도달해야** 하기 때문이다(파서가 먼저 죽으면
    사용자는 안내 대신 usage 오류만 본다).
    """
    args = sys.argv[1:] if argv is None else list(argv)

    if "--json" in args:
        print(json.dumps(_payload(), ensure_ascii=False, indent=2))
    else:
        print(_NOTICE)
    return EXIT_INTEGRATED


if __name__ == "__main__":
    sys.exit(main())
