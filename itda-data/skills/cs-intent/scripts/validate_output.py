#!/usr/bin/env python3
"""cs-intent 출력 JSONL 검증 — 스키마 핵심 규칙 + 인텐트 멤버십.

stdlib only (json, re, os, sys). PyYAML 의존 없이 intent-taxonomy.ko.yaml 의
intents 블록을 정규식으로 간이 파싱한다.

사용법:
  # macOS/Linux
  python3 scripts/validate_output.py <출력.jsonl> [intent-taxonomy.yaml]
  # Windows
  py -3 scripts/validate_output.py <출력.jsonl> [intent-taxonomy.yaml]
"""
import sys
import json
import re
import os

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

DOMAIN = {"cs"}

# output-schema.json 의 additionalProperties:false 를 실제로 강제하는 허용 필드 집합.
# (스키마는 계약이지만 파서가 검사하지 않으면 extra 필드가 조용히 통과한다 — #1140 Codex.)
ALLOWED_TOP = {
    "doc_id", "language", "taxonomy_version", "domain", "primary_intent",
    "secondary_intents", "evidence", "confidence", "flags",
}


def load_intent_labels(yaml_path):
    """intent-taxonomy.ko.yaml 의 intents: 블록에서 라벨 키만 추출(정규식, stdlib)."""
    if not os.path.exists(yaml_path):
        return None
    with open(yaml_path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^intents:\s*\n(.*?)(?=^\S)", text, re.M | re.S)
    block = m.group(1) if m else ""
    return set(re.findall(r"^  ([^\s#:][^:]*):", block, re.M))


def validate_doc(doc, allowed):
    errs = []
    if not isinstance(doc, dict):
        return ["doc 는 JSON 객체여야 함"]

    for f in ("doc_id", "language", "primary_intent", "evidence", "flags"):
        if f not in doc:
            errs.append(f"필수 필드 누락: {f}")

    # top-level additionalProperties:false — 허용 밖 필드 차단
    extra = set(doc) - ALLOWED_TOP
    if extra:
        errs.append(f"허용되지 않은 top-level 필드: {sorted(extra)} (output-schema additionalProperties:false)")

    if "language" in doc and not isinstance(doc["language"], str):
        errs.append("language 는 문자열이어야 함")
    if "domain" in doc and doc["domain"] not in DOMAIN:
        errs.append(f"domain 잘못: {doc.get('domain')} (허용: cs)")

    pi = doc.get("primary_intent")
    if pi and allowed is not None and pi not in allowed:
        errs.append(f"primary_intent '{pi}' 인텐트 체계 외 (→ '기타' 강등 필요)")
    if not doc.get("evidence"):
        errs.append("evidence 누락(원문 인용 필요)")

    sec = doc.get("secondary_intents", [])
    if sec is not None and not isinstance(sec, list):
        errs.append("secondary_intents 는 배열이어야 함")
        sec = []
    for s in (sec or []):
        if allowed is not None and s not in allowed:
            errs.append(f"secondary_intents '{s}' 인텐트 체계 외")

    c = doc.get("confidence")
    if c is not None and not (isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1):
        errs.append(f"confidence 범위 밖/타입 오류: {c!r}")

    fl = doc.get("flags")
    if fl is not None and not isinstance(fl, dict):
        errs.append("flags 는 JSON 객체여야 함")
        fl = {}
    elif fl is None:
        fl = {}

    # multi_intent 정합성
    if fl.get("multi_intent") and not (sec or []):
        errs.append("모순: flags.multi_intent=true 인데 secondary_intents 가 비어있음")
    return errs


def main():
    if len(sys.argv) < 2:
        sys.exit("사용법: validate_output.py <출력.jsonl> [intent-taxonomy.yaml]")
    if sys.argv[1] in ("-h", "--help"):
        # --help 를 파일 경로로 받으면 FileNotFoundError 로 죽는다(#1630 실측)
        print("사용법: validate_output.py <출력.jsonl> [intent-taxonomy.yaml]")
        return
    path = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    tax = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "references", "intent-taxonomy.ko.yaml")

    allowed = load_intent_labels(tax)
    if allowed:
        print(f"[intents] {len(allowed)}개 인텐트군 로드: {', '.join(sorted(allowed))}")
    else:
        print("[intents] 로드 실패 — 멤버십 검증 생략")

    total = ok = other_cnt = 0
    versions = set()
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  [{ln}] JSON 파싱 실패: {e}")
                continue
            if doc.get("primary_intent") == "기타":
                other_cnt += 1
            if doc.get("taxonomy_version"):
                versions.add(doc["taxonomy_version"])
            errs = validate_doc(doc, allowed)
            if errs:
                print(f"  [{ln}] {doc.get('doc_id', '?')} — {len(errs)}건:")
                for e in errs:
                    print(f"        - {e}")
            else:
                ok += 1

    print(f"\n결과: {ok}/{total} valid")

    # 비차단 자기진단 경고 (stderr) — 인텐트 체계 미스매치 신호
    if total:
        rate = other_cnt / total
        if rate > 0.15:
            print(f"⚠️  [자기진단] '기타' primary 비율 {rate:.0%} (>15%) — 인텐트 체계 미스매치 가능. "
                  f"어떤 문의가 기타로 몰리는지 점검 권장(인텐트군 신설/legacy_map 보강 신호).", file=sys.stderr)
    if len(versions) > 1:
        print(f"⚠️  taxonomy_version 혼재 {sorted(versions)} — 시계열 비교 시 버전 단절 주의.", file=sys.stderr)

    sys.exit(0 if total and ok == total else 1)


if __name__ == "__main__":
    main()
