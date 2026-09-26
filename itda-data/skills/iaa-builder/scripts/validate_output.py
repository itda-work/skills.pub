#!/usr/bin/env python3
"""iaa-builder 리포트 JSON 검증 — 스키마 핵심 규칙 + κ/등급 정합성.

stdlib only (json, sys, os). 외부에서 받았거나 손편집된 IAA 리포트의
구조·정합성을 점검한다(iaa.py 자체 출력은 항상 유효).

사용법:
  # macOS/Linux
  python3 scripts/validate_output.py <report.json>
  # Windows
  py -3 scripts/validate_output.py <report.json>
"""
import json
import os
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

_BANDS = [
    (0.0, "poor"), (0.20, "slight"), (0.40, "fair"),
    (0.60, "moderate"), (0.80, "substantial"), (1.01, "almost perfect"),
]


def _expected_band(k):
    if k < 0:
        return "poor"
    for upper, label in _BANDS:
        if k <= upper:
            return label
    return "almost perfect"


def validate(report) -> list:
    errs = []
    for f in ("schema_version", "method", "n_items", "n_annotators",
              "overall_kappa", "interpretation", "graduation"):
        if f not in report:
            errs.append(f"필수 필드 누락: {f}")

    if report.get("method") not in ("cohen_kappa", "fleiss_kappa"):
        errs.append(f"method 비정상: {report.get('method')}")

    na = report.get("n_annotators")
    if isinstance(na, int):
        if na < 2:
            errs.append(f"n_annotators={na} (2 이상이어야 함)")
        if na == 2 and report.get("method") != "cohen_kappa":
            errs.append("2인인데 method가 cohen_kappa 아님")
        if na > 2 and report.get("method") != "fleiss_kappa":
            errs.append("3인+인데 method가 fleiss_kappa 아님")

    k = report.get("overall_kappa")
    if k is not None:
        if not (-1.0 <= k <= 1.0):
            errs.append(f"overall_kappa 범위 밖: {k}")
        else:
            exp = _expected_band(k)
            if report.get("interpretation") != exp:
                errs.append(
                    f"interpretation 불일치: κ={k:.3f} → '{exp}' 기대, "
                    f"실제 '{report.get('interpretation')}'")

    grad = report.get("graduation") or {}
    if "passed" in grad and k is not None and "threshold" in grad:
        expect_pass = k >= grad["threshold"]
        if bool(grad["passed"]) != expect_pass:
            errs.append(
                f"graduation.passed 모순: κ={k:.3f}, threshold={grad['threshold']}, "
                f"passed={grad['passed']}")

    amb = report.get("ambiguous_categories", [])
    if amb and not isinstance(amb, list):
        errs.append("ambiguous_categories 는 배열이어야 함")
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

    k = report.get("overall_kappa")
    grad = report.get("graduation", {})
    print(f"[VALID] method={report.get('method')} · "
          f"κ={k if k is None else f'{k:.3f}'} ({report.get('interpretation')}) · "
          f"졸업={'통과' if grad.get('passed') else '미통과'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
