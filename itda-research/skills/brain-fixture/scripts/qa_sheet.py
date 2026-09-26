#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brain-fixture qa_sheet — insights[] 에서 질답 E2E 질문지·채점지 분리 산출(REQ-060).

사용:
  python3 scripts/qa_sheet.py <ledger.json> --out-dir <폴더>   # macOS/Linux
  py -3 scripts/qa_sheet.py <ledger.json> --out-dir <폴더>      # Windows

산출:
  - qa-questions.md : 응답자용. tier 오름차순, 각 항목은 번호·tier·surface_question **만**.
                      결론·수치·evidence·derivation 일절 미포함.
  - qa-key.json     : 채점자용. insight 별 {id, tier, question, expected{conclusion, result, evidence, derivation}}.

정답 미누출 자체검증(스포일러 금지의 질답판): 질문 문구에 ① result 수치(정수 인코딩+소수 표기)
② evidence 경로 문자열이 있으면 exit 2 명시 에러(해당 insight id·누출 토큰 명시 — surface_question 을 고치라는 지시).
insights 미선언/빈 배열이면 exit 2 "질답 대상 없음".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bf_common as bf  # noqa: E402

_OP_SYM = {"sum": "+", "product": "×", "diff": "−"}
_REL_KO = {"lt": "<", "gt": ">", "lte": "≤", "gte": "≥", "eq": "=", "ne": "≠"}


def _ordered(insights: list) -> list:
    # tier 오름차순, 동일 tier 는 원장 선언 순서 보존.
    return sorted(enumerate(insights), key=lambda p: (p[1]["tier"], p[0]))


def _deriv_summary(ins: dict) -> str:
    d = ins["derivation"]
    op = d["op"]
    parts = [f"{o['value']}({o['from']})" for o in d["operands"]]
    if op in ("sum", "product", "diff"):
        return f"{f' {_OP_SYM[op]} '.join(parts)} = {ins['result']['value']}"
    if op == "ratio":
        scale = d.get("scale", 1)
        tail = f" × {scale}" if scale != 1 else ""
        return f"{parts[0]} ÷ {parts[1]}{tail} = {ins['result']['value']}"
    rel = _REL_KO.get(d.get("relation", ""), d.get("relation", ""))
    return f"{parts[0]} {rel} {parts[1]}"


def _forbidden_tokens(ins: dict) -> set[str]:
    """질문지에 있으면 정답 누출인 토큰 — result 수치(정수+소수) + evidence 경로·파일명(basename)."""
    toks: set[str] = set(ins["evidence"])
    # 파일명만 심어도 출처를 직격 지목한다(예: "…_렌탈견적서.xlsx 기준으로") — basename 도 금지.
    toks |= {p.rsplit("/", 1)[-1] for p in ins["evidence"]}
    if ins["result"]["kind"] == "numeric":
        sp_ints, sp_strs = bf.spoiler_signatures(ins["derivation"], ins["result"]["value"])
        toks |= {str(i) for i in sp_ints} | set(sp_strs)
    return toks


def build_qa(ledger_path: str) -> tuple[str, dict]:
    led = bf.load_ledger(ledger_path)
    insights = led.get("insights")
    if not insights:  # None(키 부재) 또는 빈 배열
        raise bf.BFError("질답 대상 없음 — insights 가 선언되지 않았거나 비어 있습니다.")

    company = led["profile"]["company"]
    ordered = _ordered(insights)

    # 질문지(md) — 번호·tier·surface_question 만.
    q_lines = [f"# 질답 질문지 — {company}", ""]
    q_lines.append("> 응답자 안내: **업무DB 폴더만** 열람해 답하세요(원장·정답지·검수리포트·채점지 접근 금지).")
    q_lines.append("> 답마다 **근거 파일 경로**를 명시하고, 폴더에 없는 값은 지어내지 마세요. 프로토콜: `references/qa-protocol.md`.")
    q_lines.append("")
    last_tier = None
    for n, (_, ins) in enumerate(ordered, start=1):
        if ins["tier"] != last_tier:
            if last_tier is not None:
                q_lines.append("")
            q_lines.append(f"## Tier {ins['tier']}")
            q_lines.append("")
            last_tier = ins["tier"]
        q_lines.append(f"{n}. (tier {ins['tier']}) {ins['surface_question']}")
    q_lines.append("")
    questions_md = "\n".join(q_lines)

    # 정답 미누출 자체검증 — surface_question 텍스트만 대상(구조 스캐폴딩 오탐 회피).
    question_texts = "\n".join(ins["surface_question"] for ins in insights)
    leaks: list[str] = []
    for ins in insights:
        for tok in sorted(_forbidden_tokens(ins)):
            if tok in question_texts:
                leaks.append(f"{ins['id']}:'{tok}'")
    if leaks:
        raise bf.BFError(
            "질문지에 정답 누출 — " + ", ".join(leaks) +
            ". 해당 insight 의 surface_question 에서 result 수치·evidence 경로를 제거하세요."
        )

    # 채점지(json).
    key = {
        "company": company,
        "questions": [
            {
                "id": ins["id"],
                "tier": ins["tier"],
                "question": ins["surface_question"],
                "expected": {
                    "conclusion": ins["conclusion"],
                    "result": ins["result"],
                    "evidence": ins["evidence"],
                    "derivation": _deriv_summary(ins),
                },
            }
            for _, ins in ordered
        ],
    }
    return questions_md, key


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="brain-fixture 질답 E2E 질문지·채점지 생성기")
    ap.add_argument("ledger", help="원장 JSON 경로")
    ap.add_argument("--out-dir", required=True, help="qa-questions.md·qa-key.json 출력 폴더")
    args = ap.parse_args(argv)
    try:
        questions_md, key = build_qa(args.ledger)
    except bf.BFError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 2
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "qa-questions.md").write_text(questions_md, encoding="utf-8")
    (out / "qa-key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"질답 산출 완료 → {out}/qa-questions.md ({len(key['questions'])}문항), {out}/qa-key.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
