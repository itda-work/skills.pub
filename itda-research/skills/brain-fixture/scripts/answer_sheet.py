#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brain-fixture answer_sheet — 원장 traps/baits 에서 강사용 정답지(md) 생성.

사용:
  python3 scripts/answer_sheet.py <ledger.json> --out <경로.md>   # macOS/Linux
  py -3 scripts/answer_sheet.py <ledger.json> --out <경로.md>      # Windows

한빛오피스 정답지_함정과숫자.md 양식 준용: 세계관 요약 · 함정 표 · 정본 숫자 ·
기대 검수 결과 · 오탐 경계. 원장이 SSoT 이므로 정답지가 구조적으로 정확하다.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bf_common as bf  # noqa: E402


def _md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _worldview(led: dict) -> list[str]:
    p = led["profile"]
    out = ["## 세계관 요약", ""]
    out.append(f"**{p['company']}** — {p.get('description', '')}")
    meta = []
    for label, key in (("대표", "ceo"), ("설립", "founded"), ("임직원", "headcount"), ("매출", "annual_revenue")):
        if p.get(key):
            meta.append(f"{label} {p[key]}")
    if meta:
        out.append("- " + " / ".join(str(m) for m in meta))
    ent = led.get("entities", {}) or {}
    for label, key in (("매출처", "customers"), ("매입처", "suppliers"), ("제품", "products")):
        items = ent.get(key) or []
        if not items:
            continue
        names = []
        for it in items:
            if isinstance(it, dict):
                nm = it.get("name") or it.get("company") or it.get("code") or ""
                if it.get("unit_price") is not None:
                    nm = f"{nm}({it['unit_price']:,}원)" if isinstance(it["unit_price"], int) else f"{nm}({it['unit_price']})"
                names.append(str(nm))
            else:
                names.append(str(it))
        out.append(f"- **{label}**: " + " / ".join(names))
    out.append("")
    return out


def _traps_table(led: dict) -> list[str]:
    traps = led.get("traps", []) or []
    out = [f"## 함정 {len(traps)}종 (검수가 잡아야 하는 것)", ""]
    if not traps:
        out.append("_(선언된 함정 없음)_")
        out.append("")
        return out
    out.append("| ID | 유형 | 제목 | 대상 문서 | 정본 vs 편차 | 기대 검출 |")
    out.append("|----|------|------|-----------|--------------|-----------|")
    for t in traps:
        targets = ", ".join(t.get("targets", []) or []) or "—"
        canon = t.get("canon", "") or "—"
        out.append(
            f"| {t['id']} | `{t['type']}` | {_md_escape(t['title'])} | {_md_escape(targets)} "
            f"| {_md_escape(canon)} | {_md_escape(t['detection'])} |"
        )
    out.append("")
    return out


def _canon_numbers(led: dict) -> list[str]:
    out = ["## 정본 숫자 (수치 재대조용)", ""]
    canon = led.get("canon", {}) or {}
    if canon:
        for k, v in canon.items():
            vs = f"{v:,}" if isinstance(v, int) else str(v)
            out.append(f"- `{k}` = **{vs}**")
    series = led.get("series", {}) or {}
    for sname, sval in series.items():
        if isinstance(sval, dict):
            pairs = " / ".join(f"{k} {v:,}" if isinstance(v, int) else f"{k} {v}" for k, v in sval.items())
            out.append(f"- **{sname}**: {pairs}")
    cons = led.get("consistency", []) or []
    for c in cons:
        exp = c["expected"]
        exps = f"{int(exp):,}" if isinstance(exp, (int, float)) and float(exp).is_integer() else str(exp)
        out.append(f"- {c.get('desc', c.get('id', ''))} → **{exps}**")
    if len(out) == 2:
        out.append("_(정본 숫자 미선언)_")
    out.append("")
    return out


def _expected_audit(led: dict) -> list[str]:
    traps = led.get("traps", []) or []
    baits = led.get("baits", []) or []
    ndoc = len(led["documents"])
    tally = intake_tally(led)
    out = ["## 기대 검수 결과 (체크리스트)", ""]
    out.append("| 항목 | 기준 |")
    out.append("|------|------|")
    out.append(
        f"| 전수성 | 원본 {ndoc}개 전건 커버, 읽기 불가 {tally['installed']['unreadable']}개 문제파일 기록"
        " (분류는 아래 「문제파일 기대 분류」) |"
    )
    if traps:
        must = ", ".join(t["id"] for t in traps)
        out.append(f"| 함정 검출 | {must} 전부 검출 |")
    if baits:
        out.append(f"| 오탐 경계 | {', '.join(b['id'] for b in baits)} 를 모순으로 오인하지 않아야 함 |")
    out.append("")
    return out


def intake_tally(led: dict) -> dict:
    """적재 집계 기대값 — itda-doc 설치/미설치 두 환경(brain-build 적재 집계 줄과 대조)."""
    docs = led["documents"]
    intakes = [bf.expected_intake(d) for d in docs]
    ok = sum(1 for i in intakes if i["status"] == bf.INTAKE_OK)
    unreadable = sum(1 for i in intakes if i["status"] == bf.INTAKE_UNREADABLE)
    hangul = sum(1 for i in intakes if i["hangul"])
    hangul_ok = sum(1 for i in intakes if i["hangul"] and i["status"] == bf.INTAKE_OK)
    hangul_bad = hangul - hangul_ok
    return {
        "total": len(docs),
        "hangul": hangul,
        "installed": {"ok": ok, "unreadable": unreadable, "no_tool": 0},
        # 미설치면 리더를 못 돌려 형식 판정도 못 한다 — 한글 파일은 전부 '판독 도구 없음'.
        "not_installed": {"ok": ok - hangul_ok, "unreadable": unreadable - hangul_bad, "no_tool": hangul},
    }


def _problem_files(led: dict) -> list[str]:
    """brain-build 가 `문제파일.md` 에 무엇을 어떤 분류로 적어야 정답인가(#31)."""
    out = ["## 문제파일 기대 분류 (brain-build `문제파일.md` 대조)", ""]
    rows = []
    for d in led["documents"]:
        it = bf.expected_intake(d)
        if it["status"] == bf.INTAKE_OK and not it["hangul"]:
            continue
        rows.append((d["path"], it))
    if not rows:
        out.append("_(손상·잠금·한글 문서 없음 — 전건 정상 적재가 정답)_")
        out.append("")
        return out
    out.append("| 파일 | 기대 분류 | 사유(리더가 말하는 형식) | 조치 |")
    out.append("|------|-----------|--------------------------|------|")
    for path, it in rows:
        out.append(f"| {_md_escape(path)} | **{it['status']}** | {_md_escape(it['reason']) or '—'} | {_md_escape(it['action'])} |")
    out.append("")
    t = intake_tally(led)
    if t["hangul"]:
        ins, nin = t["installed"], t["not_installed"]
        out.append("적재 집계 기대값 (원본 총 N / 정상 적재 M / 읽기 불가 K / 판독 도구 없음 T):")
        out.append("")
        out.append(f"- itda-doc 설치: 원본 총 {t['total']} / 정상 적재 {ins['ok']} / 읽기 불가 {ins['unreadable']} / 판독 도구 없음 {ins['no_tool']}")
        out.append(
            f"- itda-doc 미설치: 원본 총 {t['total']} / 정상 적재 {nin['ok']} / 읽기 불가 {nin['unreadable']} / 판독 도구 없음 {nin['no_tool']}"
            " — 한글 문서는 형식과 무관하게 전부 **판독 도구 없음 — itda-doc 미설치** 가 정답"
        )
        out.append("")
        out.append(
            "> 오답 신호: 정상 적재여야 할 한글 문서(확장자가 틀린 것 포함)를 읽기 불가로 적음 · 미지원 형식을 사유 없이"
            " '손상' 으로 뭉뚱그림 · 한글 문서를 문제파일에 남기지 않고 조용히 건너뜀. HWP 3·배포용 파일의 본문 자리는"
            " 의사난수라 kordoc 같은 대체 도구로도 본문이 나오지 않는다(대체 경로 결과는 채점 대상 아님)."
        )
        out.append("")
    return out


def _bait_boundary(led: dict) -> list[str]:
    baits = led.get("baits", []) or []
    out = ["## 오탐 경계 (모순 아님 — 오인 시 감점)", ""]
    if not baits:
        out.append("_(선언된 오탐 미끼 없음)_")
        out.append("")
        return out
    out.append("| ID | 유형 | 제목 | 왜 모순이 아닌가 |")
    out.append("|----|------|------|------------------|")
    for b in baits:
        out.append(
            f"| {b['id']} | `{b['type']}` | {_md_escape(b['title'])} | {_md_escape(b['detection'])} |"
        )
    out.append("")
    return out


_RELATION_KO = {"lt": "<", "gt": ">", "lte": "≤", "gte": "≥", "eq": "=", "ne": "≠"}
_OP_SYM = {"sum": "+", "product": "×", "diff": "−"}


def _fmt_num(x):
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return f"{x:,}" if isinstance(x, int) else str(x)


def _deriv_formula(ins: dict) -> str:
    d = ins["derivation"]
    op = d["op"]
    result = ins["result"]
    parts = [f"{_fmt_num(o['value'])}({o['from']})" for o in d["operands"]]
    if op in ("sum", "product", "diff"):
        sym = f" {_OP_SYM[op]} "
        return f"{sym.join(parts)} = **{_fmt_num(result['value'])}**"
    if op == "ratio":
        scale = d.get("scale", 1)
        tail = f" × {scale}" if scale != 1 else ""
        return f"{parts[0]} ÷ {parts[1]}{tail} = **{_fmt_num(result['value'])}**"
    # compare / threshold
    rel = _RELATION_KO.get(d.get("relation", ""), d.get("relation", ""))
    return f"{parts[0]} {rel} {parts[1]}"


def _insights_section(led: dict) -> list[str]:
    insights = led.get("insights", []) or []
    out = ["## 인사이트 (합성해야만 보이는 것 — 3계단 질답 모범답안)", ""]
    if not insights:
        out.append("_(선언된 인사이트 없음)_")
        out.append("")
        return out
    out.append("여러 문서를 종합해야만 보이는 결론이다(단일 문서엔 정답이 없다 — verify 제5축 스포일러 금지로 보장).")
    out.append("")
    for tier in (1, 2, 3):
        group = [i for i in insights if i.get("tier") == tier]
        if not group:
            continue
        out.append(f"### Tier {tier}")
        out.append("")
        for ins in group:
            out.append(f"- **[{ins['id']}] {ins['title']}** `({ins['type']})`")
            out.append(f"  - 질문: {ins['surface_question']}")
            out.append(f"  - 기대 결론: {ins['conclusion']}")
            out.append(f"  - 도출식: {_deriv_formula(ins)}")
            out.append(f"  - 근거(≥2 문서): {', '.join(ins['evidence'])}")
        out.append("")
    return out


def build_answer_sheet(ledger_path: str) -> str:
    led = bf.load_ledger(ledger_path)
    company = led["profile"]["company"]
    lines = [f"# 강사용 정답지 — {company} 함정과 숫자", ""]
    lines.append("> **비공개.** 수강생에게 배포하지 않습니다. 데이터셋 수정 시 원장(ledger)과 함께 갱신하세요.")
    lines.append("> 이 정답지는 원장에서 자동 파생되었습니다(brain-fixture answer_sheet.py).")
    lines.append("")
    lines += _worldview(led)
    lines += _traps_table(led)
    lines += _canon_numbers(led)
    lines += _expected_audit(led)
    lines += _problem_files(led)
    lines += _bait_boundary(led)
    lines += _insights_section(led)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="brain-fixture 정답지 생성기")
    ap.add_argument("ledger", help="원장 JSON 경로")
    ap.add_argument("--out", required=True, help="정답지 md 출력 경로")
    args = ap.parse_args(argv)
    try:
        md = build_answer_sheet(args.ledger)
    except bf.BFError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 2
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"정답지 생성 완료 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
