#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brain-fixture verify — 자기 검증 게이트(thesis). 원장 ↔ 생성물 독립 재대조.

사용:
  python3 scripts/verify.py <ledger.json> <폴더>   # macOS/Linux
  py -3 scripts/verify.py <ledger.json> <폴더>      # Windows

exit 0 = 전 축 PASS / exit 2 = 하나라도 FAIL. findings 는 한국어로 stdout.

검증 5축(SPEC REQ-010 + REQ-050):
  ① 수치 정합 — 생성 문서를 독립 재파싱해 원장 선언값(정수) 전수 대조. traps 선언은
     문서 본문에 포함되므로 함께 검증된다(의도된 편차 외 불일치 0).
  ② 연계성   — documents 전건 파일 실재 + consistency 파생 계산 재계산·정본 문서 바인딩.
  ③ mtime    — 파일 수정시각 = 원장 내부 날짜(±0초).
  ④ 함정 실재 — 선언된 traps/baits 마커가 실제로 렌더됐는가(조용한 누락 = FAIL).
  ⑤ 합성 강제 — insights 선언 시(없으면 SKIP): evidence 문서 상이성·피연산자 실재·derivation
     재계산 + 스포일러 금지(파생 결과값이 어느 단일 문서에 직접 렌더되면 FAIL).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bf_common as bf  # noqa: E402


class Report:
    def __init__(self):
        self.axes: dict[str, list[str]] = {
            "①수치정합": [], "②연계성": [], "③mtime": [], "④함정실재": [], "⑤합성강제": []
        }
        self.checked: dict[str, int] = {k: 0 for k in self.axes}
        self.skipped: set[str] = set()

    def fail(self, axis: str, msg: str):
        self.axes[axis].append(msg)

    def ok(self, axis: str):
        self.checked[axis] += 1

    @property
    def failed(self) -> bool:
        return any(self.axes.values())


def _axis1_numbers(led: dict, out: Path, rep: Report):
    for doc in led["documents"]:
        dtype = doc["type"]
        path = bf.safe_join(out, doc["path"])
        if dtype in ("broken", "lock"):
            continue  # 구조적 함정 — 본문 재대조 대상 아님(④에서 검증)
        parsed = bf.reparse(path, dtype)
        rep.ok("①수치정합")
        if not parsed.readable:
            rep.fail("①수치정합", f"{doc['path']}: 정상 문서로 재파싱 실패(생성물 손상 의심).")
            continue
        want = bf.declared_ints(doc)
        missing = sorted(want - parsed.ints)
        if missing:
            rep.fail(
                "①수치정합",
                f"{doc['path']}: 원장 선언값 미검출 {missing} (렌더 누락·변조 의심).",
            )


def _axis2_linkage(led: dict, out: Path, rep: Report):
    # documents 전건 파일 실재
    for doc in led["documents"]:
        path = bf.safe_join(out, doc["path"])
        rep.ok("②연계성")
        if not path.exists():
            rep.fail("②연계성", f"{doc['path']}: 생성물 파일이 존재하지 않습니다.")

    # 재파싱 캐시(consistency expected_in 바인딩용)
    parsed_cache: dict[str, bf.ParsedDoc] = {}

    def _get(rel: str, dtype: str) -> bf.ParsedDoc:
        if rel not in parsed_cache:
            parsed_cache[rel] = bf.reparse(bf.safe_join(out, rel), dtype)
        return parsed_cache[rel]

    type_by_path = {d["path"]: d["type"] for d in led["documents"]}

    for i, c in enumerate(led.get("consistency", []) or []):
        rep.ok("②연계성")
        got = bf.as_int_if_integral(bf.compute_consistency(c["op"], c["operands"]))
        exp = bf.as_int_if_integral(c["expected"])
        cid = c.get("id", f"#{i}")
        if got != exp:
            rep.fail(
                "②연계성",
                f"consistency[{cid}] {c.get('desc', '')}: {c['op']}({c['operands']})={got} ≠ 기대 {exp}.",
            )
            continue
        # 정본 문서 바인딩 — 기대값이 실제 렌더 문서에 존재하는가
        dest = c.get("expected_in")
        if dest:
            parsed = _get(dest, type_by_path[dest])
            if not parsed.readable:
                rep.fail("②연계성", f"consistency[{cid}]: expected_in '{dest}' 재파싱 실패.")
            elif isinstance(exp, int) and exp not in parsed.ints:
                rep.fail(
                    "②연계성",
                    f"consistency[{cid}]: 기대값 {exp} 이 '{dest}' 에 렌더되지 않음(원장 계산 ↔ 문서 불일치).",
                )


def _axis3_mtime(led: dict, out: Path, rep: Report):
    for doc in led["documents"]:
        path = bf.safe_join(out, doc["path"])
        rep.ok("③mtime")
        if not path.exists():
            rep.fail("③mtime", f"{doc['path']}: 파일 부재로 mtime 확인 불가.")
            continue
        expected = bf.mtime_ts(doc["internal_date"])
        actual = os.stat(path).st_mtime
        if round(actual) != round(expected):
            rep.fail(
                "③mtime",
                f"{doc['path']}: mtime {actual:.0f} ≠ 내부 날짜 {doc['internal_date']}({expected:.0f}).",
            )


def _check_marker(out: Path, m: dict, type_by_path: dict, cache: dict) -> str | None:
    """마커 1건 검사. 통과=None, 실패=사유(한국어)."""
    rel = m["path"]
    dtype = type_by_path[rel]
    path = bf.safe_join(out, rel)
    if "unreadable" in m:
        import zipfile

        # 오피스 문서는 정상이면 항상 유효한 zip. 손상 파일(broken)은 시그니처만 있고
        # 중앙 디렉토리가 없어 is_zipfile=False. 이를 openable 판정의 구조 신호로 쓴다.
        openable = path.exists() and zipfile.is_zipfile(path)
        want_unreadable = bool(m["unreadable"])
        if openable == want_unreadable:
            if want_unreadable:
                return f"{rel}: 손상 파일이어야 하나 정상 zip 으로 열림(함정 미렌더)."
            return f"{rel}: 정상 파일이어야 하나 열리지 않음(손상)."
        return None
    if "name_prefix" in m:
        if not Path(rel).name.startswith(m["name_prefix"]):
            return f"{rel}: 파일명이 '{m['name_prefix']}' 로 시작하지 않음."
        return None
    # value / text — 재파싱 후 존재 확인
    if rel not in cache:
        cache[rel] = bf.reparse(path, dtype)
    parsed = cache[rel]
    if not parsed.readable:
        return f"{rel}: 재파싱 실패로 마커 확인 불가."
    if "value" in m:
        if int(m["value"]) not in parsed.ints:
            return f"{rel}: 함정 값 {m['value']} 미검출(함정이 렌더되지 않음)."
    elif "text" in m:
        if str(m["text"]) not in parsed.text:
            return f"{rel}: 함정 문구 '{m['text']}' 미검출."
    return None


def _axis4_traps(led: dict, out: Path, rep: Report):
    type_by_path = {d["path"]: d["type"] for d in led["documents"]}
    cache: dict[str, bf.ParsedDoc] = {}
    for kind, key in (("함정", "traps"), ("미끼", "baits")):
        for t in led.get(key, []) or []:
            rep.ok("④함정실재")
            markers = t.get("markers", []) or []
            if not markers:
                # 방어 심층(FIX-2) — 스키마 검증이 이미 markerless 를 거부하지만, 검증을 우회한
                # 원장이라도 marker 없는 함정은 실재를 확인할 수 없으므로 FAIL(유령 함정 차단).
                rep.fail(
                    "④함정실재",
                    f"{kind}[{t['id']}] {t['title']}: 검증 가능한 marker 부재 — 함정 실재 확인 불가.",
                )
                continue
            for m in markers:
                reason = _check_marker(out, m, type_by_path, cache)
                if reason:
                    rep.fail("④함정실재", f"{kind}[{t['id']}] {t['title']}: {reason}")


def _axis5_insights(led: dict, out: Path, rep: Report):
    """합성 강제(REQ-050) — insights 선언 시에만 호출된다."""
    type_by_path = {d["path"]: d["type"] for d in led["documents"]}
    cache: dict[str, bf.ParsedDoc] = {}

    def _p(rel: str) -> bf.ParsedDoc:
        if rel not in cache:
            cache[rel] = bf.reparse(bf.safe_join(out, rel), type_by_path[rel])
        return cache[rel]

    rendered = [doc for doc in led["documents"] if doc["type"] not in ("broken", "lock")]

    for ins in led["insights"]:
        rep.ok("⑤합성강제")
        iid = ins["id"]
        d = ins["derivation"]
        op = d["op"]
        result = ins["result"]

        # 1. evidence 파일 실재(상이성 ≥2 는 스키마가 보장)
        for e in ins["evidence"]:
            if not bf.safe_join(out, e).exists():
                rep.fail("⑤합성강제", f"인사이트[{iid}] evidence '{e}' 파일 부재.")

        # 2. 피연산자 값이 선언 출처 문서에 실재
        operand_ok = True
        for o in d["operands"]:
            parsed = _p(o["from"])
            if not parsed.readable:
                rep.fail("⑤합성강제", f"인사이트[{iid}] operand 출처 '{o['from']}' 재파싱 실패.")
                operand_ok = False
                continue
            if int(o["value"]) not in parsed.ints:
                rep.fail("⑤합성강제", f"인사이트[{iid}] 피연산자 {o['value']} 이 '{o['from']}' 에 없음(합성 근거 결손).")
                operand_ok = False

        # G3. 합성 강제 실검사 — 어느 단일 정상 문서도 필요한 피연산자 전체를 공존 보유하면 안 됨.
        operand_vals = {int(o["value"]) for o in d["operands"]}
        for doc in rendered:
            parsed = _p(doc["path"])
            if parsed.readable and operand_vals <= parsed.ints:
                rep.fail(
                    "⑤합성강제",
                    f"인사이트[{iid}] 피연산자 {sorted(operand_vals)} 가 문서 '{doc['path']}' 에 공존"
                    " — 합성 불필요(스포일러형). 피연산자를 서로 다른 문서로 분산하도록 원장을 조정하라.",
                )
                break

        # 3. result 기반 기계 검증(G2 — op 이 아니라 result.kind 로 분기).
        if result["kind"] == "numeric":
            res = bf.derivation_result(d)
            val = result["value"]
            if abs(res - val) > 1e-9:
                rep.fail("⑤합성강제", f"인사이트[{iid}] derivation {op} 결과 {res} ≠ 선언 result.value {val}.")
                continue  # 계산 불일치면 스포일러 검사 무의미
            # 4. 스포일러 금지 — 정수 인코딩 + 소수 문자열(G1) 이중 검사.
            sp_ints, sp_strs = bf.spoiler_signatures(d, val)
            for doc in rendered:
                parsed = _p(doc["path"])
                if not parsed.readable:
                    continue
                if sp_ints & parsed.ints or any(s in parsed.text for s in sp_strs):
                    rep.fail(
                        "⑤합성강제",
                        f"인사이트[{iid}] 파생 결과값 {val}(정수 {sorted(sp_ints)}·소수 {sorted(sp_strs)}) 이"
                        f" 문서 '{doc['path']}' 에 직접 렌더됨(스포일러) — 원장 수치를 조정해 파생값 충돌을 피하라.",
                    )
                    break
        else:  # relation — 부등호 성립만(스포일러 비대상)
            if operand_ok:
                a, b = d["operands"][0]["value"], d["operands"][1]["value"]
                if not bf._relation_holds(d["relation"], a, b):
                    rep.fail(
                        "⑤합성강제",
                        f"인사이트[{iid}] {op} {a} {d['relation']} {b} 부등호 불성립.",
                    )


def verify(ledger_path: str, out_dir: str) -> tuple[int, str]:
    led = bf.load_ledger(ledger_path)
    out = Path(out_dir)
    if not out.is_dir():
        raise bf.BFError(f"데이터셋 폴더가 없습니다: {out}")

    rep = Report()
    _axis1_numbers(led, out, rep)
    _axis2_linkage(led, out, rep)
    _axis3_mtime(led, out, rep)
    _axis4_traps(led, out, rep)
    # G5 — 키 부재만 SKIP. 빈 배열 []는 "0건 PASS"(로드 시 list 타입 강제됨).
    if "insights" in led:
        _axis5_insights(led, out, rep)
    else:
        rep.skipped.add("⑤합성강제")  # 하위호환 — insights 미선언 원장은 5축 생략

    lines: list[str] = []
    lines.append(f"brain-fixture verify — {led['profile']['company']}")
    n_ins = len(led.get("insights", []) or [])
    lines.append(f"대상: {out}  (문서 {len(led['documents'])}개, 인사이트 {n_ins}개)")
    lines.append("")
    for axis, fails in rep.axes.items():
        if axis in rep.skipped:
            lines.append(f"[SKIP] {axis} — insights 미선언(하위호환)")
            continue
        status = "PASS" if not fails else f"FAIL({len(fails)})"
        lines.append(f"[{status}] {axis} — 검사 {rep.checked[axis]}건")
        for f in fails:
            lines.append(f"    ✗ {f}")
    lines.append("")
    if rep.failed:
        total = sum(len(v) for v in rep.axes.values())
        lines.append(f"게이트 FAIL — 총 {total}건. 원장 보정 후 재생성하세요.")
        return 2, "\n".join(lines)
    lines.append("게이트 PASS — 원장 ↔ 생성물 정합. 정답지 생성 가능.")
    return 0, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="brain-fixture 자기 검증 게이트")
    ap.add_argument("ledger", help="원장 JSON 경로")
    ap.add_argument("out", help="검증할 데이터셋 폴더")
    args = ap.parse_args(argv)
    try:
        code, text = verify(args.ledger, args.out)
    except bf.BFError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 2
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
