#!/usr/bin/env python3
"""국세법령정보시스템 검색·전문 조회 — itda-hyve 가 받은 응답을 가공한다(네트워크 없음).

요청은 itda-hyve ``http_request`` 가 보낸다(itda-work/skills#45). 이 스크립트는 부를 호출을 만들고(``plan``),
저장된 응답을 판독한다(``parse``). 두 단계에 **같은 인자**를 준다.

    python3 search_taxlaw.py plan search "가상자산 양도소득" [--domain …] [--limit N] [--page N] [--save-dir S]
        → POST 호출 1개(JSON). itda-hyve 로 보내 save_as 로 저장
    python3 search_taxlaw.py parse search "가상자산 양도소득" [같은 인자] --input <search-….json> [--format table|json|md]

    python3 search_taxlaw.py plan detail --domain precedent --id 200000000000009799 [--save-dir S]
    python3 search_taxlaw.py parse detail --domain precedent --id 200000000000009799 --input <precedent-….json>
    # law 는 호출 2개(조문 전문 + 법령 목록) — parse 에 --input 두 개
    python3 search_taxlaw.py parse detail --domain law --id <id> --input <law-….json> --input <lawlist-….json> [--article 제18조]

식별은 두 층이다 — ① 저장 이름(``save_as``) ``<종류>-<요청 본문 지문 12자>-<받은 날>.json`` 을 인자로 다시 만든 본문의
지문과 대조하고, ② 응답이 되비친 요청 값(검색어·시작 번호·건수·정렬…, 문서·법령 id)을 계획과 대조한다. 이름은 plan 이
지었다는 것만 증명하고, 실제로 보낸 본문은 ② 가 확인한다(모델이 POST 본문을 옮겨 적는다). 어긋나면 실패로 끝낸다.

실패는 stdout 에 ``{"status":"error","error":<종류>,"detail":…}`` 를 쓰고 exit 1(인자 오류 ``args`` 는 exit 2).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxlaw_api  # noqa: E402
from hyve_input import HyveInputError, read_input  # noqa: E402

_DEFAULT_DOMAINS = ["law", "interpretation", "precedent", "counsel"]
_KST = _dt.timezone(_dt.timedelta(hours=9))
_SAVE_PREFIX = "taxlaw/"
_NAME_RE = re.compile(r"^(?P<kind>[a-z]+)-(?P<key>[0-9a-f]{12})-(?P<day>\d{8})\.json$")


class CliError(Exception):
    def __init__(self, kind: str, detail: str, **extra):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.extra = extra


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 오류도 JSON 으로
        raise CliError("args", message)


# ── 인자 ────────────────────────────────────────────────────────────────────


def _add_search_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("query", help="검색어 (또는 --docno 와 함께 문서번호)")
    p.add_argument(
        "--domain",
        default="core",
        help="law|interpretation|precedent|counsel|form|library 쉼표 구분, all, core(기본 = 앞의 넷)",
    )
    p.add_argument("--limit", type=int, default=10, help="도메인당 결과 수 (기본 10, 최대 100)")
    p.add_argument("--page", type=int, default=1, help="페이지 번호 1-base (기본 1)")
    p.add_argument("--sort", default="accuracy", choices=sorted(taxlaw_api.SORTS))
    p.add_argument("--docno", action="store_true", help="문서번호 검색 모드")
    p.add_argument("--include", action="append", default=[], help="포함어 (반복 지정)")
    p.add_argument("--exclude", action="append", default=[], help="제외어 (반복 지정)")
    p.add_argument("--synonym", action="store_true", help="동의어 확장")


def _add_detail_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--domain", required=True, choices=["law", "interpretation", "precedent", "counsel"])
    p.add_argument("--id", required=True, help="검색 결과의 id 값")


def build_parser() -> argparse.ArgumentParser:
    root = _Parser(prog="search_taxlaw.py", description="국세법령정보시스템 검색 — 호출 계획·응답 판독")
    top = root.add_subparsers(dest="command", required=True, parser_class=_Parser)
    for cmd in ("plan", "parse"):
        sp = top.add_parser(cmd)
        sub = sp.add_subparsers(dest="target", required=True, parser_class=_Parser)
        s = sub.add_parser("search")
        _add_search_args(s)
        d = sub.add_parser("detail")
        _add_detail_args(d)
        for q in (s, d):
            if cmd == "plan":
                q.add_argument("--save-dir", help="itda-hyve 가 쓸 저장 폴더(호스트 절대 경로)")
            else:
                q.add_argument("--input", action="append", required=True, help="itda-hyve 가 저장한 응답 파일")
        if cmd == "parse":
            s.add_argument("--format", default="table", choices=["table", "json", "md"])
            d.add_argument("--article", help="law 전용: 특정 조문만 (예: 제18조)")
            d.add_argument("--format", default="text", choices=["text", "json"])
    return root


def _resolve_domains(raw: str) -> list[str]:
    if raw == "all":
        return list(taxlaw_api.DOMAINS)
    if raw == "core":
        return list(_DEFAULT_DOMAINS)
    return [d.strip() for d in raw.split(",") if d.strip()]


def _host_abs_path(value: str) -> bool:
    """itda-hyve 가 도는 호스트의 절대 경로 — 스크립트가 도는 OS 와 다를 수 있다(Cowork 리눅스 ↔ Windows 호스트)."""
    return bool(re.match(r"^/|^[A-Za-z]:[\\/]|^\\\\", value))


# ── 호출 ────────────────────────────────────────────────────────────────────


def _search_kw(a) -> dict:
    return dict(
        limit=a.limit,
        page=a.page,
        sort=a.sort,
        doc_no=a.docno,
        include=a.include,
        exclude=a.exclude,
        use_synonym=a.synonym,
    )


def _search_call(a) -> dict:
    return taxlaw_api.search_call(a.query, _resolve_domains(a.domain), **_search_kw(a))


def _calls(a) -> list[tuple[str, dict]]:
    """(종류, 호출) 목록 — 종류는 저장 이름의 앞머리이자 판독할 actionId 를 정한다."""
    if a.target == "search":
        return [("search", _search_call(a))]
    if a.domain == "law":
        mr03, mr01 = taxlaw_api.law_detail_calls(a.id)
        return [("law", mr03), ("lawlist", mr01)]
    if not re.fullmatch(r"[0-9A-Za-z]{1,40}", a.id):
        raise taxlaw_api.TaxlawAPIError("id 는 검색 결과의 id 를 그대로 쓴다(영숫자).", "args")
    if a.domain == "counsel":
        return [("counsel", taxlaw_api.counsel_detail_call(a.id))]
    return [(a.domain, taxlaw_api.dcm_detail_call(a.id, a.domain))]


_ACTION_OF = {
    "search": taxlaw_api.ACTION_SEARCH,
    "interpretation": taxlaw_api.ACTION_DCM_DETAIL,
    "precedent": taxlaw_api.ACTION_DCM_DETAIL,
    "counsel": taxlaw_api.ACTION_COUNSEL_DETAIL,
    "law": taxlaw_api.ACTION_LAW_DETAIL,
    "lawlist": taxlaw_api.ACTION_LAW_LIST,
}


def cmd_plan(a) -> dict:
    if a.save_dir is not None and not _host_abs_path(a.save_dir):
        raise CliError("args", "--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로다(/Users/…·C:\\Users\\… 등)")
    day = _dt.datetime.now(_KST).strftime("%Y%m%d")
    out = []
    for kind, call in _calls(a):
        c = dict(call)
        if a.save_dir is not None:
            c["save_dir"] = a.save_dir
        c["save_as"] = f"{_SAVE_PREFIX}{kind}-{taxlaw_api.call_key(call)}-{day}.json"
        out.append(c)
    return {"status": "planned", "count": len(out), "calls": out}


# ── 판독 ────────────────────────────────────────────────────────────────────


def _read(path: str, kind: str, call: dict) -> dict:
    name = Path(path).name
    m = _NAME_RE.match(name)
    if not m or m.group("kind") != kind:
        raise CliError("input", f"{name}: 저장 이름이 계약({kind}-<지문>-<YYYYMMDD>.json)과 다르다 — plan 이 준 save_as 그대로 저장한다")
    if m.group("key") != taxlaw_api.call_key(call):
        raise CliError(
            "input",
            f"{name}: 이 인자로 만든 요청과 다른 호출의 응답이다 — plan 과 parse 에 같은 인자를 준다",
        )
    try:
        body = read_input(path)
    except HyveInputError as exc:
        extra = {"hyve_code": exc.code} if getattr(exc, "code", None) else {}
        raise CliError(exc.kind, str(exc), **extra) from exc
    return taxlaw_api.unwrap_action(body.data, _ACTION_OF[kind])


def cmd_parse(a) -> dict:
    calls = _calls(a)
    if len(a.input) != len(calls):
        raise CliError("args", f"--input 은 {len(calls)}개다({', '.join(k for k, _ in calls)} 순)")
    datas = [_read(p, kind, call) for p, (kind, call) in zip(a.input, calls)]
    if a.target == "search":
        domains = _resolve_domains(a.domain)
        param = taxlaw_api.search_param(a.query, domains, **_search_kw(a))
        parsed = taxlaw_api.parse_search_response(datas[0], domains, limit=a.limit, page=a.page, param=param)
        return {"status": "ok", "query": a.query, "page": a.page, "limit": a.limit, **parsed}
    if a.article and a.domain != "law":
        raise CliError("args", "--article 은 --domain law 전용입니다.")  # 플래그 무음 무시 금지
    if a.domain == "law":
        doc = taxlaw_api.parse_law_detail(datas[0], datas[1], a.id, article=a.article)
    elif a.domain == "counsel":
        doc = taxlaw_api.parse_counsel_detail(datas[0], a.id)
    else:
        doc = taxlaw_api.parse_dcm_detail(datas[0], a.id, a.domain)
    return {"status": "ok", **doc}


# ── 사람용 출력 ─────────────────────────────────────────────────────────────


def _print_search_table(result: dict) -> None:
    print(f"검색어: {result['query']}  (페이지 {result['page']}, 도메인당 {result['limit']}건)")
    for domain, block in result["domains"].items():
        label = taxlaw_api.DOMAIN_LABELS.get(domain, domain)
        print()
        if block.get("missing"):
            print(f"■ {label} — ⚠ 응답에 이 도메인이 없습니다 (0건이 아니라 미수신 — 사이트 계약 변경 의심)")
            continue
        print(f"■ {label} — 총 {block['total']:,}건 중 {len(block['items'])}건 표시")
        if not block["items"]:
            print("  (결과 없음)")
            continue
        for i, it in enumerate(block["items"], 1):
            meta = " / ".join(
                dict.fromkeys(  # 중복 제거 (통칙 행은 세목 약칭과 종류가 같은 "통칙")
                    x
                    for x in (it.get("doc_no"), it.get("date"), it.get("tax_type"), it.get("verdict"), it.get("extra"))
                    if x
                )
            )
            print(f"  {i}. {it['title']}")
            if meta:
                print(f"     {meta}")
            if it.get("summary"):
                summary = it["summary"]
                if len(summary) > 160:
                    summary = summary[:160] + "…"
                print(f"     {summary}")
            if it["id"]:
                print(f"     id: {it['id']}")
            else:
                print("     (전문 조회 미지원 — 원문 URL 참조)")
            if it.get("detail_url"):
                print(f"     {it['detail_url']}")
    for w in result.get("warnings") or []:
        print(f"※ {w}")


def _print_search_md(result: dict) -> None:
    print(f"# 국세법령정보시스템 검색: {result['query']}")
    for domain, block in result["domains"].items():
        label = taxlaw_api.DOMAIN_LABELS.get(domain, domain)
        if block.get("missing"):
            print(f"\n## {label}\n\n> ⚠ 응답에 이 도메인이 없습니다 (미수신 — 사이트 계약 변경 의심)")
            continue
        print(f"\n## {label} (총 {block['total']:,}건)\n")
        for it in block["items"]:
            meta = " · ".join(
                x for x in (it.get("doc_no"), it.get("date"), it.get("tax_type"), it.get("verdict")) if x
            )
            line = f"- **{it['title']}**"
            if meta:
                line += f" ({meta})"
            print(line)
            if it.get("summary"):
                print(f"  - {it['summary'][:200]}")
            if it.get("detail_url"):
                tail = f" · id `{it['id']}`" if it["id"] else " · (전문 조회 미지원)"
                print(f"  - [원문]({it['detail_url']}){tail}")
    for w in result.get("warnings") or []:
        print(f"\n> ※ {w}")


def _print_detail_text(doc: dict) -> None:
    if doc["domain"] == "law":
        name = doc["law_name"] or "법령 조문"
        print(f"{name} — 전체 {doc['article_count']}개 항목 중 {len(doc['articles'])}개 표시")
        for art in doc["articles"]:
            head = " ".join(x for x in (art["article"], art["title"]) if x)
            print(f"\n### {head}")
            if art["text"]:
                print(art["text"])
            if art["note"]:
                print(art["note"])
        for w in doc.get("warnings") or []:
            print(f"\n※ {w}")
        print(f"\n원문: {doc['detail_url']}")
        return
    print(doc["title"])
    meta = " / ".join(x for x in (doc.get("doc_no"), doc.get("date"), doc.get("tax_type")) if x)
    if meta:
        print(meta)
    if doc.get("gist"):
        print(f"\n[요지]\n{doc['gist']}")
    if doc.get("reply"):
        print(f"\n[회신]\n{doc['reply']}")
    if doc.get("answer"):
        print(f"\n[답변]\n{doc['answer']}")
    if doc.get("body"):
        print(f"\n[전문]\n{doc['body']}")
    if doc.get("related_laws"):
        print("\n[관련 법령]")
        for law in doc["related_laws"]:
            print(f"- {law}")
    print(f"\n원문: {doc['detail_url']}")


def _dump(obj: dict) -> None:
    # compact 고정 — stdout JSON pretty-print 금지(#438 규율, tests/test_response_compact_guard.py)
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    try:
        a = build_parser().parse_args(argv)
        if a.command == "plan":
            _dump(cmd_plan(a))
            return 0
        try:
            result = cmd_parse(a)
        except (AttributeError, TypeError, KeyError, ValueError) as exc:
            # 판독 함수가 못 막은 형태 — traceback 대신 계약대로 JSON 으로 멈춘다(결과를 말하지 않는다).
            raise taxlaw_api.TaxlawAPIError(f"응답 형식이 계약과 다릅니다({type(exc).__name__}: {exc}).") from exc
    except CliError as exc:
        _dump({"status": "error", "error": exc.kind, "detail": exc.detail, **exc.extra})
        return 2 if exc.kind == "args" else 1
    except taxlaw_api.TaxlawAPIError as exc:
        _dump({"status": "error", "error": exc.kind, "detail": str(exc)})
        return 2 if exc.kind == "args" else 1
    fmt = a.format
    if fmt == "json":
        _dump(result)
    elif a.target == "search":
        (_print_search_md if fmt == "md" else _print_search_table)(result)
    else:
        _print_detail_text(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
