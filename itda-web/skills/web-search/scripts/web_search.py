#!/usr/bin/env python3
"""web-search — 다중 검색엔진 결과를 정규화·병합한다. 네트워크 없음 (SPEC-WEB-SEARCH-001).

요청은 itda-hyve 의 ``http_request`` 가 보낸다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``).

    plan    <질의> [엔진 선택]          엔진마다 그대로 보낼 http_request 인자(calls)를 낸다
    collect <질의> [엔진 선택] --input  itda-hyve 가 save_as 로 저장한 응답 파일들을 병합해 출력한다

``plan`` 과 ``collect`` 에는 같은 질의·엔진 선택·``--count``·``--naver-type`` 을 준다 —
저장 이름의 지문으로 파일이 그 질의의 응답인지 대조한다.

종료코드: 0 성공(엔진 1개 이상) · 2 인자·입력 파일 오류 · 3 모든 엔진 키 미등록(secret_missing)
· 4 모든 엔진 인증 실패 · 5 모든 엔진 한도 초과 · 6 그 밖의 전체 실패.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if sys.version_info < (3, 10):  # pragma: no cover - 런타임 가드
    sys.exit("web-search는 Python 3.10 이상이 필요합니다.")

import engines
from engines import AUTO_ENGINES, ENGINE_NAMES, ENGINE_SPECS, PAID_ENGINES, EngineError
from hyve_input import HyveFailure, HyveHTTPError, HyveInputError, HyveTruncatedError, read_input
from search_format import render
from search_results import merge_results

_CODE_EXIT = {"SECRET_MISSING": 3, "AUTH_FAILED": 4, "RATE_LIMITED": 5}


class InputProblem(Exception):
    """입력 파일 묶음이 질의와 맞지 않는다(exit 2)."""


def _utf8_stdio() -> None:
    """Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):  # pragma: no cover
                pass


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query", help="검색 질의어")
    parser.add_argument(
        "--engine", default="auto",
        help="auto(기본 — 무료 엔진 tavily·naver·serper) | tavily | naver | serper | exa(유료)",
    )
    parser.add_argument("--engines", default=None, help="쉼표로 구분한 엔진 목록(예: tavily,naver,exa)")
    parser.add_argument("--count", type=int, default=5, help="반환 결과 수(기본 5)")
    parser.add_argument("--naver-type", dest="naver_type", choices=list(engines.NAVER_TYPES), default="web",
                        help="네이버 검색 종류(기본 web)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="web_search.py", description="다중 검색엔진 결과 정규화 (네트워크 없음)")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="엔진별 itda-hyve http_request 인자를 낸다")
    _add_query_args(plan)
    collect = sub.add_parser("collect", help="저장한 응답 파일들을 병합·정규화한다")
    _add_query_args(collect)
    collect.add_argument("--input", nargs="+", required=True, help="itda-hyve 가 save_as 로 저장한 응답 파일들")
    collect.add_argument("--format", dest="fmt", choices=["json", "markdown"], default="markdown",
                         help="출력 포맷(기본 markdown)")
    return parser.parse_args(argv)


def resolve_engines(engine: str, engines_csv: str | None) -> list[str]:
    """실행할 엔진 목록. ``auto`` 는 무료 엔진만 — 유료(exa)는 지목해야 부른다."""
    if engines_csv:
        names = [name.strip() for name in engines_csv.split(",") if name.strip()]
        if not names:
            raise ValueError("--engines 가 비었습니다")
    elif engine == "auto":
        names = list(AUTO_ENGINES)
    else:
        names = [engine]
    for name in names:
        if name == "perplexity":
            raise ValueError("perplexity 는 0.3.0 에서 뺐습니다 — Sonar Chat Completions 지원 종료(2026-09-27). "
                             f"가능: auto, {', '.join(ENGINE_NAMES)}")
        if name not in ENGINE_NAMES:
            raise ValueError(f"알 수 없는 엔진: {name} (가능: auto, {', '.join(ENGINE_NAMES)})")
    if len(set(names)) != len(names):
        raise ValueError(f"같은 엔진을 두 번 지목했습니다: {','.join(names)}")
    return names


def _validate(args: argparse.Namespace) -> list[str] | None:
    if not args.query.strip():
        print("검색 질의어가 필요합니다.", file=sys.stderr)
        return None
    if args.count < 1:
        print("--count는 1 이상이어야 합니다.", file=sys.stderr)
        return None
    try:
        return resolve_engines(args.engine, args.engines)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def build_plan(query: str, names: list[str], count: int, naver_type: str) -> dict:
    calls = []
    for name in names:
        spec = ENGINE_SPECS[name]
        calls.append({
            "id": name,
            "engine": name,
            "paid": spec["paid"],
            "secrets": list(spec["secrets"]),
            "args": engines.build_call(name, query, count, naver_type),
        })
    paid = [name for name in names if ENGINE_SPECS[name]["paid"]]
    notes = [
        "calls[i].args 에 save_dir 만 더해 itda-hyve http_request 로 하나씩 보낸다(POST 는 batch 불가).",
        "실패한 호출은 그 save_as 자리에 {\"error\": {\"code\", \"message\"}} 를 써서 collect 에 함께 넘긴다.",
    ]
    if paid:
        notes.append(f"유료 엔진 포함({', '.join(paid)}) — 요청당 과금된다. 사용자가 지목·동의한 경우에만 보낸다.")
    return {
        "status": "ok",
        "query": query.strip(),
        "engines": names,
        "paid_engines": paid,
        "call_count": len(calls),
        "calls": calls,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

def match_inputs(paths: list[str], query: str, names: list[str], count: int, naver_type: str) -> dict[str, Path]:
    """입력 파일을 엔진에 짝짓는다 — 빠진 엔진·다른 질의·겹친 파일은 :class:`InputProblem`."""
    expected = {
        Path(engines.save_name(name, query, count, naver_type)).name: name for name in names
    }
    found: dict[str, Path] = {}
    problems: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser()
        base = path.name
        if base in expected:
            engine = expected[base]
            if engine in found:
                problems.append(f"{engine} 응답이 두 번 들어왔습니다: {found[engine]} · {path} — 한 폴더의 것 하나만 넘기세요")
            elif not path.is_file():
                problems.append(f"{engine} 응답 파일이 그 경로에 없습니다: {path} — saved_path 를 다시 확인하세요")
            else:
                found[engine] = path
            continue
        m = engines.SAVE_NAME_RE.match(base)
        if m and m.group("engine") in ENGINE_NAMES:
            if m.group("engine") in names:
                problems.append(
                    f"{base} 는 다른 질의(질의어·--count·--naver-type 중 하나가 다름)의 응답입니다 — "
                    f"plan 과 같은 인자로 collect 를 부르세요"
                )
            else:
                problems.append(f"{base} 는 이번에 고르지 않은 엔진({m.group('engine')})의 응답입니다")
        else:
            problems.append(f"{base} 는 plan 이 준 저장 이름(web-search/<엔진>-<지문>.json)이 아닙니다")
    missing = [name for name in names if name not in found]
    for name in missing:
        want = engines.save_name(name, query, count, naver_type)
        problems.append(
            f"{name} 응답 파일이 없습니다 — {want} 로 받거나, 호출이 실패했다면 그 자리에 "
            "{\"error\": {\"code\", \"message\"}} 를 써서 넘기세요"
        )
    if problems:
        raise InputProblem("\n".join(problems))
    return found


# itda-hyve http_request 의 실패 코드(shared/netbridge.md 실패 코드 표). 이 밖의 문자열 코드는 hyve 실패가 아니라
# 엔진 오류 본문(OpenAI 호환 꼴 ``{"error": {"code": "insufficient_quota"}}`` 등)이 실패 자리 모양과 겹친 것으로 읽는다.
HYVE_CODES = {
    "secret_missing", "secret_host_denied", "vault_locked", "invalid_input", "tls_error", "timeout",
    "network_error", "too_large", "io_error", "not_found", "internal_error",
}
_HTTP_PLACEHOLDER = re.compile(r"^http_(\d{3})$")


def failure_to_error(engine: str, code: str, message: str) -> EngineError:
    """실패 자리 ``{"error": {"code", "message"}}`` 를 엔진 오류로 옮긴다. 코드는 대소문자를 가리지 않는다."""
    code = code.strip().lower()
    if code == "secret_missing":
        return EngineError("SECRET_MISSING", engines.secret_guide(engine), hyve_code=code,
                           secrets=list(ENGINE_SPECS[engine]["secrets"]))
    m = _HTTP_PLACEHOLDER.match(code)
    if m:  # 본문 없는 HTTP 오류 — SKILL 이 모델에게 http_<status> 로 쓰게 한다
        status = int(m.group(1))
        kind = engines.classify(engine, message, status=status)
        return EngineError("HTTP_ERROR" if kind == "API_ERROR" else kind,
                           f"{engine}: HTTP {status} (본문 없음) {message}".rstrip(), http_status=status)
    if code in HYVE_CODES:
        return EngineError("HYVE_FAILURE", f"itda-hyve 호출 실패({code}): {message}", hyve_code=code)
    return EngineError(engines.classify(engine, f"{code} {message}"), f"{engine}: {code} {message}".rstrip())


def read_engine(engine: str, path: Path, count: int, naver_type: str):
    """파일 하나 → EngineResponse. 실패는 :class:`EngineError`."""
    try:
        body = read_input(path)
    except HyveFailure as exc:
        raise failure_to_error(engine, exc.code, exc.hyve_message) from None
    except HyveHTTPError as exc:
        # 오류 본문이 그 엔진의 오류 모양이면 그것으로 가르고, 아니면(HTML 등) HTTP 상태로 가른다.
        try:
            engines.check_body(engine, exc.body, exc.status)
        except EngineError as err:
            if err.code != "PARSE_ERROR":
                raise
        code = engines.classify(engine, "", status=exc.status if isinstance(exc.status, int) else None)
        raise EngineError(
            "HTTP_ERROR" if code == "API_ERROR" else code,
            f"{engine}: HTTP {exc.status} {exc.status_text}".rstrip(),
        ) from None
    except HyveTruncatedError as exc:
        raise EngineError("TRUNCATED", str(exc)) from None
    except HyveInputError as exc:
        raise EngineError("INPUT_ERROR", str(exc)) from None
    flat = flat_failure(body.data)
    if flat is not None:
        raise failure_to_error(engine, *flat)
    obj = engines.check_body(engine, body.data, body.status)
    response = engines.parse_response(engine, obj, count, naver_type)
    echoed = engines.echoed_query(engine, obj)
    if echoed is not None:
        response.meta["echoed_query"] = echoed
    return response


def flat_failure(data: bytes) -> tuple[str, str] | None:
    """itda-hyve 오류를 감싸지 않고 그대로 쓴 실패 자리(``{"code","message","hint"}``)면 (코드, 메시지).

    SKILL 은 ``{"error": {...}}`` 로 감싸 쓰라고 하지만, 도구가 돌려준 모양 그대로 쓴 경우에도 ``secret_missing`` 을
    놓치지 않는다(재리뷰 n2). 최상위 ``code`` 가 itda-hyve 실패 코드이거나 ``http_<status>`` 일 때만 — 엔진 오류 본문
    (Serper ``{"message","statusCode"}`` 등)과 겹치지 않는다.
    """
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("code"), str):
        return None
    code = obj["code"].strip().lower()
    if code in HYVE_CODES or _HTTP_PLACEHOLDER.match(code):
        return code, str(obj.get("message") or "")
    return None


def exit_code(engines_used: list[str], errors: list[dict]) -> int:
    """엔진 1개라도 성공하면 0(부분 실패 허용). 전부 실패면 대표 코드."""
    if engines_used:
        return 0
    codes = {_CODE_EXIT.get(err["code"], 6) for err in errors}
    return codes.pop() if len(codes) == 1 else 6


def collect(query: str, names: list[str], files: dict[str, Path], count: int,
            naver_type: str) -> tuple[dict, int]:
    per_engine: list[list] = []
    errors: list[dict] = []
    engines_used: list[str] = []
    answer: str | None = None
    engine_meta: dict = {}
    notes: list[str] = []

    for name in names:
        try:
            response = read_engine(name, files[name], count, naver_type)
        except EngineError as exc:
            errors.append({"engine": name, "code": exc.code, "message": str(exc), **exc.extra})
            continue
        engines_used.append(name)
        if response.results:
            per_engine.append(response.results)
        if response.answer and not answer:
            answer = response.answer
        if response.meta:
            engine_meta[name] = response.meta
        echoed = response.meta.pop("echoed_query", None)
        if echoed is not None and not engines.same_query(echoed, query):
            # 경고만 한다(재리뷰 n1) — 이름 지문이 다른 검색의 파일을 이미 막는다. 엔진이 따옴표·연산자·정규화를 바꿔
            # 되돌릴 수 있는데 그 모양은 키 있는 실측 전이라, 정상 결과를 버릴 근거가 없다.
            engine_meta.setdefault(name, response.meta)["echoed_query"] = echoed
            notes.append(f"{name}: 응답이 되돌려 준 질의어가 다릅니다({echoed!r}) — 엔진이 질의를 바꿔 실행했을 수 있습니다. 결과는 그대로 실었습니다")
        skipped = response.meta.get("skipped_no_url")
        if skipped:
            notes.append(f"{name}: URL 이 없는 결과 {skipped}건을 뺐습니다")

    missing_keys = [err["engine"] for err in errors if err["code"] == "SECRET_MISSING"]
    if missing_keys:
        registered = ", ".join(s for e in missing_keys for s in ENGINE_SPECS[e]["secrets"])
        notes.append(f"키 미등록 엔진: {', '.join(missing_keys)} — itda-hyve GUI 시크릿 탭에 {registered} 를 등록하면 함께 검색합니다")
    if not engines_used and missing_keys and len(missing_keys) == len(names):
        unused_free = [e for e in AUTO_ENGINES if e not in names]
        unused_paid = [e for e in PAID_ENGINES if e not in names]
        if unused_free:
            notes.append(
                f"이번에 부르지 않은 무료 엔진({', '.join(unused_free)}) 키를 등록해 두었다면 --engines 에 넣어 다시 검색하세요"
            )
        if unused_paid:
            notes.append(
                f"유료 엔진({', '.join(unused_paid)}) 키를 등록해 두었다면 --engines 로 지목하세요(요청당 과금 — 사용자에게 알린 뒤)"
            )

    merged = merge_results(per_engine, count)
    payload = {
        "query": query.strip(),
        "engine": names[0] if len(names) == 1 else "auto",
        "engines_used": engines_used,
        "results": [item.to_dict() for item in merged],
        "answer": answer,
        "engine_meta": engine_meta,
        "errors": errors,
    }
    if notes:
        payload["notes"] = notes
    return payload, exit_code(engines_used, errors)


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    args = parse_args(argv)
    names = _validate(args)
    if names is None:
        return 2

    if args.command == "plan":
        plan = build_plan(args.query, names, args.count, args.naver_type)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    try:
        files = match_inputs(args.input, args.query, names, args.count, args.naver_type)
    except InputProblem as exc:
        print(json.dumps({"status": "error", "error": "input", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    payload, code = collect(args.query, names, files, args.count, args.naver_type)
    print(render(payload, args.fmt))
    return code


if __name__ == "__main__":
    sys.exit(main())
