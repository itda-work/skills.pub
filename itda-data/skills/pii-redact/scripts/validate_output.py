#!/usr/bin/env python3
"""pii-redact 리포트 JSON 검증 — 스키마 핵심 규칙 + 안전 불변식.

stdlib only (json, sys, os, re). 외부에서 받았거나 손편집된 마스킹 리포트의
구조·정합·안전(원문 PII 미유출)을 점검한다(redact.py 자체 출력은 항상 유효).

사용법:
  # macOS/Linux
  python3 scripts/validate_output.py <report.json>
  # Windows
  py -3 scripts/validate_output.py <report.json>
"""
import json
import os
import re
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

_CONF = {"high", "candidate", "low"}
_REDACTION_KEYS = {"type", "token", "confidence", "span"}
_SKIPPED_KEYS = {"type", "span", "reason"}


def validate(report) -> list:
    errs = []
    for f in ("schema_version", "redacted_text", "n_redactions", "by_type",
              "redactions", "low_confidence_skipped", "policy"):
        if f not in report:
            errs.append(f"필수 필드 누락: {f}")
    if errs:
        return errs

    if report["schema_version"] != "1.0":
        errs.append(f"schema_version 비정상: {report['schema_version']}")

    redactions = report.get("redactions") or []
    n = report.get("n_redactions")
    if isinstance(n, int) and n != len(redactions):
        errs.append(f"n_redactions({n}) != redactions 길이({len(redactions)})")

    # by_type 합 == n_redactions
    by_type = report.get("by_type") or {}
    if sum(by_type.values()) != len(redactions):
        errs.append(f"by_type 합({sum(by_type.values())}) != redactions 길이({len(redactions)})")

    # redactions 항목: 키 화이트리스트(원문 PII 필드 유입 차단) + 값 정합
    for i, r in enumerate(redactions):
        extra = set(r) - _REDACTION_KEYS
        if extra:
            errs.append(f"redactions[{i}] 허용 외 키(원문 유출 위험): {sorted(extra)}")
        if r.get("confidence") not in _CONF:
            errs.append(f"redactions[{i}] confidence 비정상: {r.get('confidence')}")
        tok = r.get("token", "")
        if not (isinstance(tok, str) and tok.startswith("[") and tok.endswith("]")):
            errs.append(f"redactions[{i}] token 형식 비정상: {tok!r}")
        span = r.get("span")
        if (not isinstance(span, list) or len(span) != 2
                or not all(isinstance(x, int) for x in span) or span[0] > span[1]):
            errs.append(f"redactions[{i}] span 비정상: {span}")
        by_type_has = r.get("type") in by_type
        if not by_type_has:
            errs.append(f"redactions[{i}] type '{r.get('type')}'가 by_type에 없음")

    # low_confidence_skipped 구조 + 키 화이트리스트(보류 항목으로도 원문 PII 유입 차단)
    for i, s in enumerate(report.get("low_confidence_skipped") or []):
        if "type" not in s or "span" not in s:
            errs.append(f"low_confidence_skipped[{i}] type/span 누락")
        extra = set(s) - _SKIPPED_KEYS
        if extra:
            errs.append(f"low_confidence_skipped[{i}] 허용 외 키(원문 유출 위험): {sorted(extra)}")

    # redacted_text에 토큰이 실제로 반영됐는지(토큰 누락 = 미치환 의심)
    rtext = report.get("redacted_text", "")
    for tok in {r.get("token") for r in redactions}:
        if tok and tok not in rtext:
            errs.append(f"redacted_text에 토큰 '{tok}' 미반영(치환 누락 의심)")

    return errs


def main():
    if len(sys.argv) < 2:
        sys.exit("사용법: validate_output.py <report.json>")
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit(f"파일 없음: {path}")
    with open(path, encoding="utf-8") as fh:
        report = json.load(fh)

    errs = validate(report)
    if errs:
        print(f"[INVALID] {len(errs)}건:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)

    print(f"[VALID] 마스킹 {report.get('n_redactions')}건 · "
          f"유형 {sorted(report.get('by_type', {}))} · "
          f"보류 {len(report.get('low_confidence_skipped', []))}건")
    sys.exit(0)


if __name__ == "__main__":
    main()
