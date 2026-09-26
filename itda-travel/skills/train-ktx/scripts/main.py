#!/usr/bin/env python3
"""train-ktx CLI — KTX 열차 검색·예약·예약조회.

⚠️ 코레일 비공식 모바일 API(letskorail.com)를 사용한다. 전체 디스클레이머는
SKILL.md / GUIDE.md 참조. 서브커맨드: search / reserve / reservations / check.
예약(reserve)은 ``--confirm`` 없으면 미리보기만 수행한다(SAFE-1).
계정 확인(check)은 로그인 1회로 자격증명만 검증한다(read-only, 마스킹 출력).

실행 전제: shared/ 모듈을 import 하므로 ``PYTHONPATH=skills/shared`` 가 필요하다.
  예: PYTHONPATH=skills/shared python3 skills/itda-travel/skills/train-ktx/scripts/main.py search ...
공통 CLI 코어는 train_cli.py(정본 itda-travel/shared/, scripts/ 벤더링 사본)가 담당한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 이상이 필요합니다.")

sys.path.insert(0, str(Path(__file__).parent))

import format as fmt  # noqa: E402
import reserve as rsv  # noqa: E402
from korail_adapter import KtxError, connect  # noqa: E402
from stations import StationNotFound, normalize_station  # noqa: E402
from train_cli import (  # noqa: E402
    add_reserve_args,
    add_search_args,
    build_common_parser,
    emit_check,
    emit_reservation_result,
    emit_reservations,
    emit_reserve_preview,
    run_cli,
    validate_passengers,
)

_PAYMENT_NOTICE = (
    "⚠️ 예약 후 결제는 코레일 앱/웹에서 직접 진행해야 하며,"
    " 결제기한 내 미결제 시 좌석은 자동 취소됩니다."
)


def _resolve_stations(dep: str, arr: str) -> tuple[str, str]:
    return normalize_station(dep), normalize_station(arr)


def cmd_search(args) -> int:
    validate_passengers(args)
    dep, arr = _resolve_stations(args.dep, args.arr)
    client = connect(cli_id=args.id, cli_pw=args.pw)
    passengers = rsv.build_passengers(args.adults, args.children, args.seniors)
    trains = client.search(
        dep,
        arr,
        date=args.date,
        time=args.time,
        train_type=rsv.train_type_code(args.train_type),
        passengers=passengers,
        include_no_seats=args.include_no_seats,
    )
    if args.json:
        payload = [fmt.train_to_dict(t, i) for i, t in enumerate(trains)]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(fmt.format_search_results(trains, dep, arr, args.date))
    return 0


def cmd_reserve(args) -> int:
    validate_passengers(args)
    dep, arr = _resolve_stations(args.dep, args.arr)
    client = connect(cli_id=args.id, cli_pw=args.pw)
    passengers = rsv.build_passengers(args.adults, args.children, args.seniors)
    trains = client.search(
        dep,
        arr,
        date=args.date,
        time=args.time,
        train_type=rsv.train_type_code(args.train_type),
        passengers=passengers,
    )
    train = rsv.select_train(trains, args.index)
    info = fmt.train_to_dict(train, args.index)

    if not args.confirm:
        emit_reserve_preview(
            info,
            fmt.format_train_line,
            seat=args.seat,
            adults=args.adults,
            children=args.children,
            seniors=args.seniors,
            payment_notice=_PAYMENT_NOTICE,
        )
        return 0

    option = rsv.reserve_option_code(args.seat, only=args.seat_only)
    reservation = rsv.execute_reservation(
        client, train, passengers=passengers, option=option, confirm=True
    )
    emit_reservation_result(
        fmt.reservation_to_dict(reservation), fmt.format_reservation, args.json
    )
    return 0


def cmd_reservations(args) -> int:
    client = connect(cli_id=args.id, cli_pw=args.pw)
    reservations = client.reservations()
    infos = [fmt.reservation_to_dict(r) for r in reservations]
    emit_reservations(infos, fmt.format_reservation, args.json)
    return 0


def cmd_check(args) -> int:
    # 계정 확인 — 로그인 1회로 자격증명만 검증한다(read-only). 실패는 main()의
    # 기존 예외 처리로 fail-loud.
    client = connect(cli_id=args.id, cli_pw=args.pw)
    emit_check(
        client.masked_id,
        args.json,
        "✅ 코레일 로그인 성공 — 계정이 올바르게 설정되었습니다.",
    )
    return 0


def _add_ktx_search_args(sp: argparse.ArgumentParser) -> None:
    add_search_args(sp)
    sp.add_argument(
        "--train-type",
        choices=["ktx", "all", "saemaeul", "mugunghwa"],
        default="ktx",
        help="열차종",
    )


def build_parser() -> argparse.ArgumentParser:
    common = build_common_parser(
        id_help="KORAIL_USER_ID 덮어쓰기(보통 환경변수 사용)",
        pw_help="KORAIL_PASSWORD 덮어쓰기(보통 환경변수 사용)",
    )

    p = argparse.ArgumentParser(prog="train-ktx", description="KTX 열차 검색·예약")
    sub = p.add_subparsers(dest="command", required=True)

    sp_search = sub.add_parser("search", parents=[common], help="열차 검색")
    _add_ktx_search_args(sp_search)
    sp_search.add_argument(
        "--include-no-seats", action="store_true", help="매진 열차도 포함"
    )
    sp_search.set_defaults(func=cmd_search)

    sp_reserve = sub.add_parser("reserve", parents=[common], help="예약(--confirm 필요)")
    _add_ktx_search_args(sp_reserve)
    add_reserve_args(sp_reserve)
    sp_reserve.set_defaults(func=cmd_reserve)

    sp_rsv = sub.add_parser(
        "reservations", parents=[common], help="내 예약 조회(read-only)"
    )
    sp_rsv.set_defaults(func=cmd_reservations)

    sp_check = sub.add_parser(
        "check", parents=[common], help="계정 확인 — 로그인 1회로 자격증명 검증(read-only)"
    )
    sp_check.set_defaults(func=cmd_check)

    return p


def main(argv=None) -> int:
    return run_cli(
        build_parser(),
        argv,
        station_errors=(StationNotFound,),
        adapter_error=KtxError,
    )


if __name__ == "__main__":
    sys.exit(main())
