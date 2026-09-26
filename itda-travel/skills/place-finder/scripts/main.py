#!/usr/bin/env python3
"""place-finder CLI — 카카오맵 비공식 검색으로 목적별 근처 장소 찾기.

사용 예 (저장소 루트 기준):
    python3 skills/itda-travel/skills/place-finder/scripts/main.py search --near 강남역 --category 술집
    python3 skills/itda-travel/skills/place-finder/scripts/main.py search --near 홍대입구역 --category 카페 --amenity wifi --json

옵션(--json·--amenity·--limit·--sort)은 모두 서브커맨드 ``search`` 뒤에 둔다.
"""

from __future__ import annotations

import argparse
import json
import sys

if sys.version_info < (3, 10):  # pragma: no cover - 런타임 가드
    sys.exit("place-finder는 Python 3.10+ 가 필요합니다.")

from categories import all_presets, label_of, resolve_preset, search_keyword
from format_output import format_results
from kakao_adapter import geocode_anchor, search_places
from places import AMENITY_FIELDS, build_results


def positive_int(value: str) -> int:
    """argparse용 1 이상 정수 검증."""
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수여야 합니다")
    return n


def _parse_amenity(raw: str) -> list[str]:
    """'--amenity parking,wifi' -> ['parking','wifi']. 잘못된 키는 ValueError를 던진다."""
    if not raw:
        return []
    keys = [token.strip().lower() for token in raw.split(",") if token.strip()]
    invalid = [key for key in keys if key not in AMENITY_FIELDS]
    if invalid:
        raise ValueError(
            f"알 수 없는 편의시설: {', '.join(invalid)}. 가능: {', '.join(AMENITY_FIELDS)}"
        )
    return keys


def _emit_error(message: str, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    else:
        print(f"⚠️ {message}", file=sys.stderr)


def cmd_search(args: argparse.Namespace) -> int:
    """search 서브커맨드. 종료코드: 0 성공 / 2 사용법 / 3 위치실패 / 4 검색실패."""
    # 프리셋이면 프리셋의 키워드/라벨을, 아니면 입력을 자유 키워드로 검색(예: 칼국수·돈까스)
    preset = resolve_preset(args.category)
    if preset:
        keyword = search_keyword(preset)
        label = label_of(preset)
    else:
        keyword = args.category.strip()
        if not keyword:
            _emit_error("카테고리(또는 검색어)를 입력해 주세요.", as_json=args.json)
            return 2
        label = keyword

    try:
        amenity_filter = _parse_amenity(args.amenity)
    except ValueError as exc:
        _emit_error(str(exc), as_json=args.json)
        return 2

    # 1) anchor(거리 기준점) 지오코딩 — 카카오 distance 필드 대신 직접 계산하기 위함
    ok, anchor, reason = geocode_anchor(args.near)
    if not ok:
        _emit_error(reason, as_json=args.json)
        return 3

    # 2) "{위치} {키워드}" 검색 (sort=0 관련도 — 1회성)
    query = f"{args.near} {keyword}"
    ok, raw, reason = search_places(query)
    if not ok:
        _emit_error(reason, as_json=args.json)
        return 4

    # 3) 정규화·필터·정렬 (거리는 anchor 기준 haversine)
    results = build_results(
        raw,
        (anchor["lat"], anchor["lon"]),
        amenity_filter=amenity_filter or None,
        sort=args.sort,
        limit=args.limit,
    )

    # 4) 출력
    if args.json:
        print(
            json.dumps(
                {
                    "anchor": anchor,
                    "preset": preset,
                    "query": query,
                    "count": len(results),
                    "places": [place.to_dict() for place in results],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_results(results, anchor_name=anchor["name"], preset_label=label))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON 출력")

    parser = argparse.ArgumentParser(
        prog="place-finder",
        description="카카오맵 비공식 검색으로 목적별 근처 장소 찾기",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", parents=[common], help="근처 장소 검색")
    search.add_argument("--near", required=True, help="기준 위치(역명/동네/랜드마크)")
    search.add_argument(
        "--category", required=True, help="카테고리(" + "/".join(all_presets()) + ") 또는 자연어"
    )
    search.add_argument(
        "--amenity", default="", help="편의시설 필터(쉼표 구분): " + ",".join(AMENITY_FIELDS)
    )
    search.add_argument("--limit", type=positive_int, default=5, help="결과 개수(기본 5)")
    search.add_argument(
        "--sort", choices=["distance", "rating"], default="distance", help="정렬(기본 거리순)"
    )
    search.set_defaults(func=cmd_search)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
