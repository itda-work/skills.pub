#!/usr/bin/env python3
"""iaa-builder 코어 — 어노테이터 간 일치도(IAA) 결정론 계산.

stdlib only (csv, json, math, random, sys, os). 외부 의존 없음.

제공 함수:
  cohen_kappa(a, b)            — 2인 명목 라벨 Cohen's κ
  fleiss_kappa(rows)           — N인(고정) 명목 라벨 Fleiss' κ
  per_category_kappa(a, b)     — 카테고리별 one-vs-rest Cohen's κ (2인 한정)
  interpret(kappa)             — Landis-Koch 등급 문자열
  analyze_labels(...)          — 전체 리포트 dict (졸업 게이트 포함)
  run_csv(path, threshold)     — 어노테이션 시트 CSV → 리포트 dict

κ 정의:
  Cohen  κ = (po - pe) / (1 - pe),  pe = Σ_k p_a(k)·p_b(k)
  Fleiss κ = (P̄ - Pe) / (1 - Pe),  P_i = (Σ_j n_ij² - n)/(n(n-1)), Pe = Σ_j p_j²
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

# 졸업 게이트 기본 합격선 = substantial 하한(Landis-Koch). κ≥0.61이면 'substantial' 등급이며,
# interpret(0.60)='moderate'(재측정 권고 등급)와의 자기모순을 피하기 위해 0.61로 둔다.
DEFAULT_THRESHOLD = 0.61

# Landis-Koch (1977) 등급 경계
_LANDIS_KOCH = [
    (0.0, "poor"),          # κ < 0
    (0.20, "slight"),       # 0.00–0.20
    (0.40, "fair"),         # 0.21–0.40
    (0.60, "moderate"),     # 0.41–0.60
    (0.80, "substantial"),  # 0.61–0.80
    (1.01, "almost perfect"),  # 0.81–1.00
]


def interpret(kappa: float) -> str:
    """κ 값을 Landis-Koch 등급 문자열로 변환."""
    if kappa < 0:
        return "poor"
    for upper, label in _LANDIS_KOCH:
        if kappa <= upper:
            return label
    return "almost perfect"


def cohen_kappa(a: list, b: list) -> dict:
    """2인 어노테이터 명목 라벨의 Cohen's κ.

    a, b: 동일 길이의 라벨 시퀀스(item 순서 정렬됨).
    반환: {kappa, po, pe, n}.  n==0 또는 pe==1 가드.
    """
    if len(a) != len(b):
        raise ValueError(f"라벨 길이 불일치: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        return {"kappa": None, "po": None, "pe": None, "n": 0}

    agree = sum(1 for x, y in zip(a, b) if x == y)
    po = agree / n

    ca, cb = Counter(a), Counter(b)
    labels = set(ca) | set(cb)
    pe = sum((ca.get(k, 0) / n) * (cb.get(k, 0) / n) for k in labels)

    if math.isclose(pe, 1.0):
        # 모든 항목이 단일 라벨 → 우연 일치가 1, κ 정의 불가. 완전일치면 1.0로 처리.
        kappa = 1.0 if math.isclose(po, 1.0) else 0.0
    else:
        kappa = (po - pe) / (1 - pe)
    return {"kappa": kappa, "po": po, "pe": pe, "n": n}


def fleiss_kappa(rows: list) -> dict:
    """N인(고정) 어노테이터 명목 라벨의 Fleiss' κ.

    rows: item별 라벨 리스트. 모든 item의 rater 수(n)가 동일해야 함.
    반환: {kappa, p_bar, pe, n_items, n_raters}.
    """
    rows = [r for r in rows if r]
    n_items = len(rows)
    if n_items == 0:
        return {"kappa": None, "p_bar": None, "pe": None, "n_items": 0, "n_raters": 0}

    rater_counts = {len(r) for r in rows}
    if len(rater_counts) != 1:
        raise ValueError(f"Fleiss κ는 고정 rater 수 가정 — item별 rater 수 불일치: {sorted(rater_counts)}")
    n = rater_counts.pop()
    if n < 2:
        raise ValueError("Fleiss κ는 item당 rater 2명 이상 필요")

    categories = sorted({lbl for r in rows for lbl in r})
    # n_ij: item i에 category j를 준 rater 수
    p_i_list = []
    cat_totals = Counter()
    for r in rows:
        c = Counter(r)
        cat_totals.update(c)
        sq = sum(v * v for v in c.values())
        p_i = (sq - n) / (n * (n - 1))
        p_i_list.append(p_i)

    p_bar = sum(p_i_list) / n_items
    total = n_items * n
    pe = sum((cat_totals.get(j, 0) / total) ** 2 for j in categories)

    if math.isclose(pe, 1.0):
        kappa = 1.0 if math.isclose(p_bar, 1.0) else 0.0
    else:
        kappa = (p_bar - pe) / (1 - pe)
    return {"kappa": kappa, "p_bar": p_bar, "pe": pe, "n_items": n_items, "n_raters": n}


def per_category_kappa(a: list, b: list) -> dict:
    """카테고리별 one-vs-rest Cohen's κ (2인 한정). {category: kappa}."""
    labels = sorted(set(a) | set(b))
    out = {}
    for c in labels:
        ba = [1 if x == c else 0 for x in a]
        bb = [1 if x == c else 0 for x in b]
        out[c] = cohen_kappa(ba, bb)["kappa"]
    return out


def disagreements(item_ids: list, a: list, b: list) -> list:
    """불일치 item 목록 [{item_id, labels: [a, b]}]."""
    out = []
    for iid, x, y in zip(item_ids, a, b):
        if x != y:
            out.append({"item_id": iid, "labels": [x, y]})
    return out


def analyze_labels(item_ids: list, annotator_cols: list, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """전체 IAA 리포트 생성.

    item_ids: item 식별자 리스트
    annotator_cols: [[어노테이터1 라벨...], [어노테이터2 라벨...], ...]  (각 길이 == len(item_ids))
    threshold: 졸업 게이트 κ 합격선(기본 0.6 = substantial 하한)
    """
    n_annot = len(annotator_cols)
    if n_annot < 2:
        raise ValueError("어노테이터 2명 이상 필요")
    n_items = len(item_ids)

    report = {
        "schema_version": "1.0",
        "n_items": n_items,
        "n_annotators": n_annot,
        "threshold": threshold,
    }

    if n_annot == 2:
        a, b = annotator_cols
        ck = cohen_kappa(a, b)
        per_cat = per_category_kappa(a, b)
        report.update({
            "method": "cohen_kappa",
            "overall_kappa": ck["kappa"],
            "po": ck["po"],
            "pe": ck["pe"],
            "per_category_kappa": per_cat,
            "disagreements": disagreements(item_ids, a, b),
        })
        ambiguous = sorted(c for c, k in per_cat.items()
                           if k is not None and k < threshold)
    else:
        rows = [[col[i] for col in annotator_cols] for i in range(n_items)]
        fk = fleiss_kappa(rows)
        report.update({
            "method": "fleiss_kappa",
            "overall_kappa": fk["kappa"],
            "p_bar": fk["p_bar"],
            "pe": fk["pe"],
        })
        # Fleiss 다인에서 불일치 = 만장일치 아닌 item
        dis = [{"item_id": iid, "labels": [col[i] for col in annotator_cols]}
               for i, iid in enumerate(item_ids)
               if len({col[i] for col in annotator_cols}) > 1]
        report["disagreements"] = dis
        ambiguous = []

    k = report["overall_kappa"]
    report["interpretation"] = interpret(k) if k is not None else None
    report["ambiguous_categories"] = ambiguous
    report["graduation"] = {
        "threshold": threshold,
        "passed": bool(k is not None and k >= threshold),
        "note": (
            f"overall κ={k:.3f} ≥ {threshold} → 운영 졸업 가능 후보(샘플 대표성 별도 확인)"
            if k is not None and k >= threshold
            else f"overall κ={'N/A' if k is None else f'{k:.3f}'} < {threshold} → "
                 f"분류 정의 보강 후 재라벨 권장(합격선이 아니라 정의를 고친다)"
        ),
    }
    return report


def run_csv(path: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """어노테이션 시트 CSV → IAA 리포트.

    CSV 형식: 헤더에 item_id(필수) + annotator_* 라벨 컬럼 2개 이상.
    text 등 기타 컬럼은 무시. 빈 라벨이 있는 행은 제외(미완성 라벨).
    """
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        annot_cols = [f for f in fields if f.lower().startswith("annotator")
                      or f.lower().startswith("rater") or f.lower().startswith("라벨")]
        if len(annot_cols) < 2:
            raise ValueError(
                f"라벨 컬럼 2개 이상 필요(annotator_*/rater_*/라벨_*). 발견: {annot_cols}")
        id_col = "item_id" if "item_id" in fields else fields[0]

        item_ids, cols = [], [[] for _ in annot_cols]
        skipped = 0
        for row in reader:
            vals = [(row.get(c) or "").strip() for c in annot_cols]
            if any(v == "" for v in vals):
                skipped += 1
                continue
            item_ids.append((row.get(id_col) or "").strip())
            for i, v in enumerate(vals):
                cols[i].append(v)

    report = analyze_labels(item_ids, cols, threshold)
    report["source"] = os.path.basename(path)
    report["annotator_columns"] = annot_cols
    report["skipped_incomplete_rows"] = skipped
    return report


def main():
    if len(sys.argv) < 2:
        sys.exit(f"사용법: iaa.py <어노테이션시트.csv> [threshold={DEFAULT_THRESHOLD}]")
    if sys.argv[1] in ("-h", "--help"):
        # --help 를 파일 경로로 받으면 FileNotFoundError 로 죽는다(#1630 실측)
        print(f"사용법: iaa.py <어노테이션시트.csv> [threshold={DEFAULT_THRESHOLD}]")
        return
    path = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_THRESHOLD
    report = run_csv(path, threshold)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["graduation"]["passed"]:
        print(f"\n⚠️  {report['graduation']['note']}", file=sys.stderr)


if __name__ == "__main__":
    main()
