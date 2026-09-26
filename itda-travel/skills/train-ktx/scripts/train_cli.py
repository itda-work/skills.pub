#!/usr/bin/env python3
"""train-ktx/train-srt CLI 공통 코어 — 검증기·파서 조각·출력·예외 엔벨로프.

정본: skills/itda-travel/shared/train_cli.py (#736). 각 train-* 스킬 scripts/ 에
byte-identical 로 벤더링된다(소스트리 standalone·테스트 경로 — itda-stocks
kis_client 동형). publish 주입(SPEC-SHARED-INJECT-001)과 test_shared_copy_sync
플러그인-로컬 가드가 동기화를 강제한다. 수정은 정본에서 하고 사본에 복제한다.

도메인 발산(어댑터 connect·좌석 옵션 코드·역명 데이터·format 속성 매핑·결제
안내문)은 각 스킬에 남긴다 — 이 모듈은 두 CLI 가 문자 그대로 공유하는 불변
코어만 담는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

from env_loader import MissingAPIKeyError  # (skills/shared/)


class TrainUsageError(ValueError):
    """CLI 입력 오류. 외부 예매처 호출 전에 사용자에게 그대로 보일 사유."""


_DATE_RE = re.compile(r"^\d{8}$")
_TIME_RE = re.compile(r"^\d{6}$")


def non_negative_int(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("0 이상의 정수여야 합니다")
    return n


def valid_date(value: str) -> str:
    if not _DATE_RE.fullmatch(value or ""):
        raise argparse.ArgumentTypeError("YYYYMMDD 형식이어야 합니다")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("존재하는 날짜여야 합니다") from exc
    return value


def valid_time(value: str) -> str:
    if not _TIME_RE.fullmatch(value or ""):
        raise argparse.ArgumentTypeError("HHMMSS 형식이어야 합니다")
    try:
        datetime.strptime(value, "%H%M%S")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("존재하는 시각이어야 합니다") from exc
    return value


def validate_passengers(args) -> None:
    if args.adults + args.children + args.seniors < 1:
        raise TrainUsageError("승객은 최소 1명 이상이어야 합니다.")


def build_common_parser(id_help: str, pw_help: str) -> argparse.ArgumentParser:
    """공통 옵션 parent parser — 각 서브커맨드 "뒤"에서 받는다.

    (예: `search --dep 서울 --arr 부산 --json`) — 전역 위치 강제로 인한
    "unrecognized arguments: --json" 함정을 제거한다.
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--id", help=id_help)
    common.add_argument("--pw", help=pw_help)
    common.add_argument("--json", action="store_true", help="JSON 출력")
    return common


def add_search_args(sp: argparse.ArgumentParser) -> None:
    """search/reserve 공통 검색 인자. 스킬 고유 인자(--train-type 등)는 호출측이 추가."""
    sp.add_argument("--dep", required=True, help="출발역(한글)")
    sp.add_argument("--arr", required=True, help="도착역(한글)")
    sp.add_argument("--date", type=valid_date, help="날짜 YYYYMMDD (미지정 시 오늘)")
    sp.add_argument("--time", type=valid_time, help="기준 시각 HHMMSS (이후 열차)")
    sp.add_argument("--adults", type=non_negative_int, default=1, help="성인 수(기본 1)")
    sp.add_argument("--children", type=non_negative_int, default=0, help="어린이 수")
    sp.add_argument("--seniors", type=non_negative_int, default=0, help="경로 수")


def add_reserve_args(sp: argparse.ArgumentParser) -> None:
    """reserve 서브커맨드 공통 인자(--index/--seat/--seat-only/--confirm)."""
    sp.add_argument("--index", type=non_negative_int, required=True, help="검색 결과 번호")
    sp.add_argument(
        "--seat", choices=["general", "special"], default="general", help="좌석유형"
    )
    sp.add_argument(
        "--seat-only", action="store_true", help="해당 좌석유형만(없으면 실패)"
    )
    sp.add_argument(
        "--confirm", action="store_true", help="실제 예약 실행(없으면 미리보기)"
    )


def emit_reserve_preview(
    info: dict,
    format_train_line,
    *,
    seat: str,
    adults: int,
    children: int,
    seniors: int,
    payment_notice: str,
) -> None:
    """SAFE-1 미리보기 — 실제 예약 호출 없음. Claude는 이 정보로 사용자에게
    AskUserQuestion 확인을 받은 뒤 --confirm 을 붙여 재호출한다."""
    print("아래 열차를 예약하려 합니다. (아직 예약하지 않았습니다)\n")
    print(format_train_line(info))
    print(
        f"\n좌석유형: {seat} · 인원: 성인 {adults}"
        f" / 어린이 {children} / 경로 {seniors}"
    )
    print("\n예약을 확정하려면 동일 명령에 --confirm 을 추가하세요.")
    print(payment_notice)


def emit_reservation_result(rinfo: dict, format_reservation, as_json: bool) -> None:
    if as_json:
        print(json.dumps(rinfo, ensure_ascii=False, indent=2))
    else:
        print("✅ 예약되었습니다.\n")
        print(format_reservation(rinfo))


def emit_reservations(infos: list[dict], format_reservation, as_json: bool) -> None:
    if as_json:
        print(json.dumps(infos, ensure_ascii=False, indent=2))
    elif not infos:
        print("예약 내역이 없습니다.")
    else:
        print("📋 예약 내역\n")
        for info in infos:
            print(format_reservation(info))
            print()


def emit_check(masked_id: str, as_json: bool, success_message: str) -> None:
    """계정 확인 출력 — 마스킹된 ID와 성공 여부만(SAFE-3)."""
    if as_json:
        print(json.dumps({"ok": True, "id": masked_id}, ensure_ascii=False))
    else:
        print(f"{success_message} (ID: {masked_id})")


def run_cli(parser: argparse.ArgumentParser, argv, *, station_errors, adapter_error) -> int:
    """공통 main 엔벨로프 — 서브커맨드 실행 + 예외 → exit code 매핑.

    station_errors: 역명 해석 예외 튜플(스킬별 전용역 예외 포함).
    adapter_error: 어댑터가 변환한 모든 예매처 측 실패(fail-loud).
    """
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except station_errors as exc:
        print(f"역명 오류: {exc}", file=sys.stderr)
        return 1
    except MissingAPIKeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except TrainUsageError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 2
    except adapter_error as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except IndexError as exc:
        print(f"선택 오류: {exc}", file=sys.stderr)
        return 1
