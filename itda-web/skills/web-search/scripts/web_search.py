#!/usr/bin/env python3
"""web-search 진입점 — 다중 검색엔진 통합 조회 CLI (SPEC-WEB-SEARCH-001).

질의어를 받아 1개 이상 검색엔진을 호출하고, 결과를 단일 스키마로 정규화해
``--format json|markdown`` 으로 출력한다. ``--engine auto`` 는 키 보유 엔진을
fan-out 해 병합·중복 제거한다.

종료코드: 0 성공 · 2 인자오류 · 3 엔진/키 없음 · 4 인증실패 · 5 쿼터초과 · 6 네트워크.
"""
from __future__ import annotations

import argparse
import sys

if sys.version_info < (3, 10):  # pragma: no cover - 런타임 가드
    sys.exit("web-search는 Python 3.10 이상이 필요합니다.")

# Windows locale(cp949) stdio 고정 해제 — ✓/✗·em-dash 출력 크래시와
# utf-8 부모 프로세스의 파이프 디코드 실패 방지 (#1036).
for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - Python < 3.7
            pass

from search_env import ENGINE_NAMES, all_guides, available_engines
from search_format import render
from search_http import SearchError
from search_results import merge_results

# code → 종료코드 (전 엔진 실패 시 대표 코드 산출용)
_CODE_EXIT = {
    "MISSING_API_KEY": 3,
    "AUTH_FAILED": 4,
    "RATE_LIMITED": 5,
}


def _build_client(engine: str, opts: dict):
    """엔진명을 실제 클라이언트로 구성(지연 import — 미사용 엔진 import 회피)."""
    if engine == "tavily":
        from tavily_client import TavilyClient

        return TavilyClient.from_env()
    if engine == "serper":
        from serper_client import SerperClient

        return SerperClient.from_env()
    if engine == "exa":
        from exa_client import ExaClient

        return ExaClient.from_env()
    if engine == "perplexity":
        from perplexity_client import PerplexityClient

        return PerplexityClient.from_env(opts.get("model", "sonar"))
    if engine == "naver":
        from naver_client import NaverClient

        return NaverClient.from_env(opts.get("naver_type", "web"))
    raise ValueError(f"알 수 없는 엔진: {engine}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="web_search.py",
        description="다중 검색엔진 통합 조회 (조회 전용)",
    )
    parser.add_argument("query", nargs="?", help="검색 질의어")
    parser.add_argument(
        "--engine",
        default="auto",
        help="auto(기본) | perplexity | tavily | serper | exa | naver",
    )
    parser.add_argument(
        "--engines",
        default=None,
        help="쉼표로 구분한 엔진 서브셋 (auto 대신 특정 엔진들만 fan-out)",
    )
    parser.add_argument("--count", type=int, default=5, help="반환 결과 수(기본 5)")
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=["json", "markdown"],
        default="markdown",
        help="출력 포맷(기본 markdown)",
    )
    parser.add_argument(
        "--naver-type",
        dest="naver_type",
        choices=["web", "news", "blog"],
        default="web",
        help="네이버 검색 종류(기본 web)",
    )
    parser.add_argument("--model", default="sonar", help="Perplexity 모델(기본 sonar)")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="엔진별 키 보유 여부만 진단(네트워크 호출 없음)",
    )
    return parser.parse_args(argv)


def _resolve_engines(args: argparse.Namespace) -> tuple[list[str] | None, bool]:
    """실행할 엔진 목록과 '단일 강제' 여부를 반환. 잘못된 엔진명은 (None, _)."""
    if args.engines:
        names = [name.strip() for name in args.engines.split(",") if name.strip()]
        for name in names:
            if name not in ENGINE_NAMES:
                print(f"알 수 없는 엔진: {name}", file=sys.stderr)
                return None, False
        return names, False

    engine = args.engine
    if engine == "auto":
        avail = available_engines()
        return [name for name in ENGINE_NAMES if avail[name]], False
    if engine in ENGINE_NAMES:
        return [engine], True
    print(f"알 수 없는 엔진: {engine}", file=sys.stderr)
    return None, False


def _run(query: str, engines: list[str], count: int, opts: dict) -> tuple[dict, int]:
    """선택 엔진을 fan-out 호출하고 (payload, exit_code) 를 반환한다."""
    per_engine: list[list] = []
    errors: list[dict] = []
    engines_used: list[str] = []
    answer: str | None = None
    engine_meta: dict = {}

    for engine in engines:
        try:
            client = _build_client(engine, opts)
            response = client.search(query, count)
        except SearchError as exc:
            errors.append({"engine": engine, "code": exc.code, "message": str(exc)})
            continue
        except Exception:  # noqa: BLE001 - 예상치 못한 응답 shape 등; traceback·키 누출 차단(P5)
            errors.append(
                {
                    "engine": engine,
                    "code": "INTERNAL_ERROR",
                    "message": f"{engine} 결과 처리 중 오류가 발생했습니다.",
                }
            )
            continue

        engines_used.append(engine)
        if response.results:
            per_engine.append(response.results)
        if response.answer and not answer:
            answer = response.answer
        if response.meta:
            engine_meta[engine] = response.meta

    merged = merge_results(per_engine, count)
    payload = {
        "query": query,
        "engine": engines[0] if len(engines) == 1 else "auto",
        "engines_used": engines_used,
        "results": [item.to_dict() for item in merged],
        "answer": answer,
        "engine_meta": engine_meta,
        "errors": errors,
    }
    return payload, _exit_code(engines_used, errors)


def _exit_code(engines_used: list[str], errors: list[dict]) -> int:
    """엔진 1개라도 성공하면 0(부분실패 허용). 전부 실패면 대표 코드."""
    if engines_used:
        return 0
    if not errors:
        return 6
    exit_codes = {_CODE_EXIT.get(err["code"], 6) for err in errors}
    return exit_codes.pop() if len(exit_codes) == 1 else 6


def _no_engine_payload(query: str) -> dict:
    message = (
        "사용 가능한 검색 엔진이 없습니다. 아래 키 중 하나 이상을 설정하세요.\n"
        + all_guides()
    )
    return {
        "query": query,
        "engine": "auto",
        "engines_used": [],
        "results": [],
        "answer": None,
        "engine_meta": {},
        "errors": [{"engine": "-", "code": "MISSING_API_KEY", "message": message}],
    }


def _print_check_env() -> None:
    avail = available_engines()
    print("엔진 키 보유 현황:")
    for engine in ENGINE_NAMES:
        print(f"  {'✓' if avail[engine] else '✗'} {engine}")
    ready = [engine for engine in ENGINE_NAMES if avail[engine]]
    if ready:
        print(f"\n사용 가능: {', '.join(ready)}")
    else:
        print("\n사용 가능한 엔진이 없습니다. 키를 설정하세요:")
        print(all_guides())


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.check_env:
        _print_check_env()
        return 0

    if not args.query or not args.query.strip():
        print("검색 질의어가 필요합니다. 예: web_search.py \"검색어\"", file=sys.stderr)
        return 2
    if args.count < 1:
        print("--count는 1 이상이어야 합니다.", file=sys.stderr)
        return 2

    engines, _forced = _resolve_engines(args)
    if engines is None:
        return 2

    if not engines:  # auto 인데 키 보유 엔진 0개
        print(render(_no_engine_payload(args.query), args.fmt))
        return 3

    opts = {"naver_type": args.naver_type, "model": args.model}
    payload, exit_code = _run(args.query.strip(), engines, args.count, opts)
    print(render(payload, args.fmt))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
