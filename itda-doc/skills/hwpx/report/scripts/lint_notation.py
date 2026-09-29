#!/usr/bin/env python3
"""공문서 표기법 검사 (#14) — 원고 마크다운에서 날짜·시각·금액·문장부호 표기를 찾아 **경고만** 한다.

근거(1차 출처, 판독일 2026-09-28 — 법제처 현행):
  - 「행정업무의 운영 및 혁신에 관한 규정」 제7조제5항: 날짜는 숫자로, 연·월·일 글자 대신 온점. 시·분은 24시각제 숫자, 글자 대신 쌍점.
    (단서: 특별한 사유가 있으면 다른 방법 가능 — 그래서 오류가 아니라 경고다)
  - 같은 규정 시행규칙 제2조제2항: 금액은 아라비아 숫자 뒤 괄호에 한글 — 예) 금113,560원(금일십일만삼천오백육십원)
  - 띄어쓰기(온점 뒤·쌍점·물결표·「붙임」)는 `references/document-style-rules.md` 의 문장부호 절(편람·한글 맞춤법 문장부호)을 따른다.

자동 교정은 하지 않는다 — 원고는 사용자의 것이고, 단서 조항("특별한 사유") 판단도 사람의 몫이다.

사용:
  python3 lint_notation.py 원고.md [--json]
종료 코드: 0 발견 없음 / 1 발견 있음 / 2 입력 오류.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass

if sys.version_info < (3, 8):
    sys.exit("Python 3.8+ 가 필요합니다")


@dataclass
class Finding:
    line: int
    code: str
    text: str
    message: str


# (코드, 패턴, 안내). 패턴은 한 줄 안에서만 본다.
RULES: list[tuple[str, re.Pattern, str]] = [
    ("DATE_KOREAN", re.compile(r"(?:(?:19|20)\d{2}\s*년\s*)?\d{1,2}\s*월\s*\d{1,2}\s*일"),
     "날짜는 숫자와 온점으로 — 예) 2026. 9. 6. (규정 제7조제5항)"),
    ("TIME_KOREAN", re.compile(r"(?:오전|오후)\s*\d{1,2}\s*시|\d{1,2}\s*시\s*\d{1,2}\s*분"),
     "시각은 24시각제 숫자와 쌍점으로 — 예) 15:20 (규정 제7조제5항)"),
    ("MONEY_NO_HANGUL", re.compile(r"금\s?\d{1,3}(?:,\d{3})+원(?!\s*\()"),
     "금액은 숫자 뒤 괄호에 한글을 함께 — 예) 금113,560원(금일십일만삼천오백육십원) (시행규칙 제2조제2항)"),
    ("COLON_SPACE", re.compile(r"(?<=[^\s\d:|])\s+:(?=\s)"),
     "쌍점은 앞말에 붙이고 뒤는 한 칸 — 예) 기간: 2026. 9. 6."),
    # 한 개짜리 물결표만 — `~~` 는 마크다운 취소선 기호다
    ("TILDE_SPACE", re.compile(r"[^\s~]\s+(?<!~)[~∼](?![~∼])\s*[^\s~]|[^\s~](?<!~)[~∼](?![~∼])\s+[^\s~]"),
     "물결표는 앞뒤를 붙여 쓴다 — 예) 9. 6.∼9. 20."),
    ("ATTACH_COLON", re.compile(r"^\s*붙임\s*:"),
     "「붙임」 뒤에는 쌍점을 쓰지 않는다 — 예) 붙임  운영 계획 1부.  끝."),
]

# 온점 날짜 후보 — 표준형(`2026. 9. 6.`)이 아니면 경고. 후보를 넓게 잡고 표준형만 통과시킨다.
_DOT_DATE_RE = re.compile(r"(?<![\d.])(?:19|20)\d{2}\.\s*\d{1,2}\.\s*\d{1,2}(?:\.(?!\d))?")
_DOT_DATE_OK = re.compile(r"(?:19|20)\d{2}\. [1-9]\d?\. [1-9]\d?\.")
_DOT_DATE_MSG = "날짜 온점 뒤는 한 칸 띄우고 월·일 앞에 0 을 붙이지 않으며 끝에 온점 — 예) 2026. 9. 6."

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_URL_RE = re.compile(r"https?://\S+")


def lint_text(text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    in_fence = False
    start = 0
    # front-matter(--- … ---)는 메타데이터라 검사하지 않는다
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for number, raw in enumerate(lines, start=1):
        if number <= start:
            continue
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _URL_RE.sub(" ", raw)
        for m in _DOT_DATE_RE.finditer(line):
            if not _DOT_DATE_OK.fullmatch(m.group(0)):
                findings.append(Finding(number, "DATE_DOT_FORMAT", m.group(0).strip(), _DOT_DATE_MSG))
        for code, pattern, message in RULES:
            for m in pattern.finditer(line):
                findings.append(Finding(number, code, m.group(0).strip(), message))
    return findings


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    ap = argparse.ArgumentParser(description="공문서 표기법 검사(경고만, 자동 교정 없음)")
    ap.add_argument("input", help="원고 마크다운(- 는 stdin)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        text = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    except OSError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    findings = lint_text(text)
    if args.json:
        print(json.dumps({"ok": not findings, "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=1))
    else:
        for f in findings:
            print(f"L{f.line}\t{f.code}\t{f.text}\t{f.message}")
        print(f"표기 경고 {len(findings)}건" if findings else "표기 경고 없음", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
