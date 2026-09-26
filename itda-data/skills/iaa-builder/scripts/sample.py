#!/usr/bin/env python3
"""iaa-builder 골드셋 샘플링 — CS 로그에서 어노테이션 시트(빈 라벨 CSV) 생성.

stdlib only (csv, json, os, random, sys). 외부 의존 없음.

입력: CS 텍스트 소스
  - JSONL: 줄당 객체. text_field(기본 'text')에서 본문 추출, id_field(기본 'doc_id') 식별자.
  - CSV: text_field/id_field 컬럼.
출력: 어노테이션 시트 CSV (item_id, text, annotator_1, annotator_2 — 라벨 빈칸).

층화(stratify): stratify_field 지정 시 그 값별 비례 배분으로 대표성 확보.
재현성: seed 고정(기본 42). Math.random 미사용(결정론).

사용법:
  python3 scripts/sample.py <소스.jsonl|csv> <n> [--text TEXT] [--id ID]
                            [--stratify FIELD] [--annotators K] [--seed S]
                            [--out sheet.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")


def load_rows(path: str, text_field: str, id_field: str) -> list:
    """소스(JSONL/CSV) → [{id, text, stratum_src(원본 dict)}]."""
    rows = []
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jsonl", ".ndjson", ".json"):
        with open(path, encoding="utf-8") as fh:
            for ln, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rows.append(obj)
    else:  # csv/tsv
        delim = "\t" if ext == ".tsv" else ","
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for obj in csv.DictReader(fh, delimiter=delim):
                rows.append(obj)
    return rows


def stratified_sample(rows: list, n: int, stratify_field: str | None, seed: int) -> list:
    """층화(또는 단순) 무작위 샘플. 결정론(seed 고정)."""
    rng = random.Random(seed)
    if n >= len(rows):
        out = list(rows)
        rng.shuffle(out)
        return out

    if not stratify_field:
        return rng.sample(rows, n)

    # 층별 그룹화 → 비례 배분(최소 1개 보장은 하지 않음; 비례 우선)
    strata: dict = {}
    for r in rows:
        key = str(r.get(stratify_field, "__none__"))
        strata.setdefault(key, []).append(r)

    picked = []
    total = len(rows)
    # 라운딩 손실 보정을 위해 floor 후 잔여를 큰 층부터 채움
    alloc = {}
    for key, group in strata.items():
        alloc[key] = int(n * len(group) / total)
    remainder = n - sum(alloc.values())
    for key in sorted(strata, key=lambda k: -len(strata[k])):
        if remainder <= 0:
            break
        alloc[key] += 1
        remainder -= 1

    for key, group in strata.items():
        k = min(alloc[key], len(group))
        picked.extend(rng.sample(group, k))
    rng.shuffle(picked)
    return picked


def all_text_empty(rows: list, text_field: str) -> bool:
    """본문 컬럼이 전량 공란인지 — IAA 라벨링 불가(무음 핸드오프 단절) 신호.

    cs-intent 출력 스키마는 `additionalProperties:false`로 text를 금지하므로,
    그 출력을 기본 `--text text`로 넣으면 이 함수가 True가 되어 경고를 띄운다.
    """
    return bool(rows) and not any((r.get(text_field) or "").strip() for r in rows)


def write_sheet(picked: list, text_field: str, id_field: str,
                annotators: int, out_path: str) -> int:
    """어노테이션 시트 CSV 작성(라벨 컬럼 빈칸). 작성 행 수 반환."""
    annot_cols = [f"annotator_{i}" for i in range(1, annotators + 1)]
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "text"] + annot_cols)
        for idx, r in enumerate(picked, 1):
            iid = r.get(id_field) or f"item_{idx:04d}"
            text = r.get(text_field, "")
            w.writerow([iid, text] + [""] * annotators)
    return len(picked)


def main():
    ap = argparse.ArgumentParser(description="골드셋 어노테이션 시트 생성")
    ap.add_argument("source")
    ap.add_argument("n", type=int)
    ap.add_argument("--text", default="text", dest="text_field")
    ap.add_argument("--id", default="doc_id", dest="id_field")
    ap.add_argument("--stratify", default=None, dest="stratify_field")
    ap.add_argument("--annotators", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="annotation_sheet.csv")
    args = ap.parse_args()

    if args.annotators < 2:
        sys.exit("어노테이터 2명 이상 필요(IAA 측정 전제).")

    rows = load_rows(args.source, args.text_field, args.id_field)
    if not rows:
        sys.exit("소스에서 행을 찾지 못함.")
    picked = stratified_sample(rows, args.n, args.stratify_field, args.seed)

    # fail-loud: 본문 컬럼이 전량 공란이면 IAA 라벨링이 불가하다(무음 단절 방지).
    if all_text_empty(picked, args.text_field):
        print(f"⚠️  [경고] '{args.text_field}' 본문이 전량 비어 있습니다 — 어노테이터가 읽을 텍스트가 없어 "
              f"IAA 라벨링이 불가합니다. cs-intent 출력엔 본문(text)이 없으니 "
              f"`--text evidence`(원문 인용)를 쓰거나 원본 CS 로그에 분류 결과를 join한 파일을 입력하세요.",
              file=sys.stderr)

    written = write_sheet(picked, args.text_field, args.id_field,
                          args.annotators, args.out)

    note = f" (층화: {args.stratify_field})" if args.stratify_field else ""
    print(f"[sample] {written}건 샘플 → {args.out}{note}, seed={args.seed}")
    print(f"[다음] {args.annotators}인이 라벨 컬럼을 독립 작성 후: "
          f"python3 scripts/iaa.py {args.out}")


if __name__ == "__main__":
    main()
