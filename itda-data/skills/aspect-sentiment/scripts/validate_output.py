#!/usr/bin/env python3
"""aspect-sentiment 출력 JSONL 검증 — 스키마 핵심 규칙 + taxonomy 멤버십.

stdlib only (json, re, os, sys). PyYAML 의존 없이 taxonomy.ko.yaml 의 aspect 라벨을
정규식으로 간이 추출한다.

사용법:
  # macOS/Linux
  python3 scripts/validate_output.py <출력.jsonl> [taxonomy.yaml]
  # Windows
  py -3 scripts/validate_output.py <출력.jsonl> [taxonomy.yaml]
"""
import sys
import json
import re
import os

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

POLARITY = {"positive", "neutral", "negative"}
OVERALL = {"positive", "neutral", "negative", "mixed"}
RESOLUTION = {"resolved", "unresolved", "partial", "unknown"}
SPEAKER = {"customer", "agent", "system", None}
DOMAIN = {"cs", "review"}

# output-schema.json 의 additionalProperties:false 를 실제로 강제하는 허용 필드 집합.
# (스키마는 계약이지만 파서가 검사하지 않으면 extra 필드가 조용히 통과한다 — #1140 Codex.)
ALLOWED_TOP = {
    "doc_id", "language", "taxonomy_version", "domain", "overall_sentiment",
    "customer_final_sentiment", "aspects", "process_signals",
    "mentioned_aspects", "flags",
}
ALLOWED_ASPECT = {
    "aspect", "polarity", "sub_aspect", "evidence", "turn_id", "speaker", "confidence",
}
ALLOWED_PS = {"resolution", "escalated"}


def load_aspect_labels(yaml_path):
    """taxonomy.ko.yaml 의 aspects: 블록에서 라벨 키만 추출(정규식, stdlib)."""
    if not os.path.exists(yaml_path):
        return None
    with open(yaml_path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^aspects:\s*\n(.*?)(?=^\S)", text, re.M | re.S)
    block = m.group(1) if m else ""
    # 들여쓰기 2칸 + 라벨 + ':' (주석/빈 줄 제외)
    return set(re.findall(r"^  ([^\s#:][^:]*):", block, re.M))


def _in_unit_range(c):
    return isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1


def validate_doc(doc, allowed):
    errs = []
    if not isinstance(doc, dict):
        return ["doc 는 JSON 객체여야 함"]

    for f in ("doc_id", "language", "aspects", "mentioned_aspects", "flags"):
        if f not in doc:
            errs.append(f"필수 필드 누락: {f}")

    # top-level additionalProperties:false — 허용 밖 필드 차단
    extra = set(doc) - ALLOWED_TOP
    if extra:
        errs.append(f"허용되지 않은 top-level 필드: {sorted(extra)} (output-schema additionalProperties:false)")

    if "language" in doc and not isinstance(doc["language"], str):
        errs.append("language 는 문자열이어야 함")
    if "domain" in doc and doc["domain"] not in DOMAIN:
        errs.append(f"domain 잘못: {doc.get('domain')} (허용: cs, review)")

    asp = doc.get("aspects", [])
    if not isinstance(asp, list):
        errs.append("aspects 는 배열이어야 함")
        asp = []

    for i, a in enumerate(asp):
        if not isinstance(a, dict):
            errs.append(f"aspects[{i}] 는 객체여야 함")
            continue
        ax = set(a) - ALLOWED_ASPECT
        if ax:
            errs.append(f"aspects[{i}] 허용되지 않은 필드: {sorted(ax)} (additionalProperties:false)")
        label = a.get("aspect")
        if label and allowed is not None and label not in allowed:
            errs.append(f"aspects[{i}].aspect '{label}' taxonomy 외 (→ '기타' 강등 필요)")
        if a.get("polarity") not in POLARITY:
            errs.append(f"aspects[{i}].polarity 잘못: {a.get('polarity')}")
        if not a.get("evidence"):
            errs.append(f"aspects[{i}].evidence 누락(원문 인용 필요)")
        if a.get("speaker") not in SPEAKER:
            errs.append(f"aspects[{i}].speaker 잘못: {a.get('speaker')}")
        c = a.get("confidence")
        if c is not None and not _in_unit_range(c):
            errs.append(f"aspects[{i}].confidence 범위 밖/타입 오류: {c!r}")

    ov = doc.get("overall_sentiment")
    if ov is not None and ov not in OVERALL:
        errs.append(f"overall_sentiment 잘못: {ov}")
    cfs = doc.get("customer_final_sentiment")
    if cfs is not None and cfs not in OVERALL:
        errs.append(f"customer_final_sentiment 잘못: {cfs}")

    ma = doc.get("mentioned_aspects")
    if ma is not None and not isinstance(ma, list):
        errs.append("mentioned_aspects 는 배열이어야 함")

    fl = doc.get("flags")
    if fl is not None and not isinstance(fl, dict):
        errs.append("flags 는 JSON 객체여야 함")

    # 미언급 ≠ 중립 / 필드 모순
    if not asp and doc.get("mentioned_aspects"):
        errs.append("모순: aspects 가 비었는데 mentioned_aspects 가 비어있지 않음")

    ps = doc.get("process_signals")
    if isinstance(ps, dict):
        # reopen_count 는 아래 전용 메시지로 안내하므로 일반 extra 검사에서 제외
        px = set(ps) - ALLOWED_PS - {"reopen_count"}
        if px:
            errs.append(f"process_signals 허용되지 않은 필드: {sorted(px)} (additionalProperties:false)")
        if ps.get("resolution") is not None and ps.get("resolution") not in RESOLUTION:
            errs.append(f"process_signals.resolution 잘못: {ps.get('resolution')}")
        if "escalated" in ps and not isinstance(ps["escalated"], bool):
            errs.append("process_signals.escalated 는 boolean 이어야 함")
        if "reopen_count" in ps:
            errs.append("reopen_count 는 단건 출력에서 제거됨 — cross-doc 집계량이라 무상태 단건 라벨러가 채울 수 없음(집계 레이어 ml-absa 책임). 단건 스키마에서 빼라")
    elif ps is not None:
        errs.append("process_signals 는 JSON 객체여야 함")

    return errs


def main():
    if len(sys.argv) < 2:
        sys.exit("사용법: validate_output.py <출력.jsonl> [taxonomy.yaml]")
    if sys.argv[1] in ("-h", "--help"):
        # --help 를 파일 경로로 받으면 FileNotFoundError 로 죽는다(#1630 실측)
        print("사용법: validate_output.py <출력.jsonl> [taxonomy.yaml]")
        return
    path = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    tax = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "references", "taxonomy.ko.yaml")

    allowed = load_aspect_labels(tax)
    if allowed:
        print(f"[taxonomy] {len(allowed)}개 라벨 로드: {', '.join(sorted(allowed))}")
    else:
        print("[taxonomy] 로드 실패 — aspect 멤버십 검증 생략")

    total = ok = 0
    other_cnt = total_asp = unknown_cnt = 0
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
            # 비차단 자기진단 신호 집계 (순수 규칙 산식 — 라벨러 판단·IAA 무관)
            for a in (doc.get("aspects") or []):
                total_asp += 1
                if a.get("aspect") == "기타":
                    other_cnt += 1
            ps0 = doc.get("process_signals") or {}
            if ps0.get("resolution") == "unknown":
                unknown_cnt += 1
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

    # 비차단 자기진단 경고 (stderr, exit code 비영향) — taxonomy 미스매치/품질 신호
    if total_asp:
        rate = other_cnt / total_asp
        if rate > 0.15:
            print(f"⚠️  [자기진단] '기타' 측면 비율 {rate:.0%} (>15%) — taxonomy 미스매치 가능. "
                  f"어떤 문의가 기타로 몰리는지 점검 권장(인텐트/문의유형 분류 신호일 수 있음).", file=sys.stderr)
    if unknown_cnt:
        print(f"⚠️  resolution=unknown {unknown_cnt}건 — 본문에 단서 있으면 partial/unresolved 권장(few-shot 참조).", file=sys.stderr)
    if len(versions) > 1:
        print(f"⚠️  taxonomy_version 혼재 {sorted(versions)} — 시계열 비교 시 버전 단절 주의.", file=sys.stderr)

    sys.exit(0 if total and ok == total else 1)


if __name__ == "__main__":
    main()
