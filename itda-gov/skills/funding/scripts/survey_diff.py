#!/usr/bin/env python3
# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# — skills/ir-search/scripts/diff_surveys.py. 개작: stderr prefix [funding],
# 프로필 파일명 계약(survey-profile.md / profile-snapshot.md), 한국어 요약.
"""두 회차(run) 폴더를 비교해 무엇이 바뀌었는지 보고한다.

이전 회차 폴더와 이번 회차 폴더의 raw 크롤 *.jsonl 을 전부 읽어(new_items.jsonl /
gone_* / report* / screening* 같은 diff 산출물은 건너뛴다) 다음으로 분류한다:

  NEW           — 직전 회차에 없던 신규 공고
  CHANGED       — 같은 공고인데 title / apply_start / apply_end / status /
                  content_hash 가 달라짐 (changed_fields 로 나열)
  NEEDS_REHASH  — 직전엔 content_hash 가 있었는데 이번엔 없음(상세 재수집 필요)
  GONE          — 사라진 공고(마감·내림) — gone_<out> 에 별도 기록
  UNCHANGED     — 그대로 — 직전 A/B/C 판정을 승계

레코드 키는 (source, source_id) 라 소스 간 ID 충돌이 없다. 한쪽 회차에서만
크롤된 소스는 GONE/NEW 비교에서 제외하고 따로 보고한다(재크롤하지 않은 소스가
"전부 마감"으로 보이면 안 된다).

프로필 fingerprint (선택, 권장):
  --old-profile 은 이전 회차 폴더의 profile-snapshot.md, --new-profile 은
  프로젝트 루트의 survey-profile.md 를 가리킨다(마크다운 "- 키: 값" 불릿).
  판정 축(창업 단계 / 지역 연고 / 대표자 / 필요한 것)이 다르거나, 한쪽만
  지정됐거나, 파싱에 실패하면 UNCHANGED 승계가 무효화되고(fail-closed)
  이번 회차 전건이 --out 에 NEW 로 기록된다.

사용법:
  python3 survey_diff.py <old_dir> <new_dir> [--out new_items.jsonl] \
      [--old-profile <old_dir>/profile-snapshot.md --new-profile survey-profile.md] \
      [--assume-complete]

출력: 사람이 읽는 요약은 stdout. --out 지정 시 검토 대상(NEW + CHANGED +
NEEDS_REHASH + 신규 소스 항목; 승계 무효 시 전건 NEW)을 공통 diff 레코드
wrapper 형식 jsonl 로 쓴다 — references/diff_record_schema.json 계약:

  {"kind": ..., "diff_status": ..., "changed_fields": [...], "record": {...}}

GONE 은 검토 대상이 아니라 기회 소멸 알림 재료이므로 gone_<out> 에 분리한다.

content_hash 비교: detail --merge-into 로 상세가 병합된 레코드는 해시로
비교한다. hash_version 불일치(v2↔v3 산식 전환)는 1회 CHANGED 로 흡수하고,
해시가 사라지면 NEEDS_REHASH 가 된다 — classify() 참고.

Exit code: 0 성공(변경이 없어도 0), 1 잘못된 입력(현재 회차 레코드 0건,
깨진 JSON 라인, 중복 키, 폴더 없음).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

PREFIX = "[funding]"

COMPARE_FIELDS = ["title", "apply_start", "apply_end", "status", "content_hash"]


def _warn(msg):
    print(f"{PREFIX} {msg}", file=sys.stderr)


def _die(msg):
    sys.exit(f"{PREFIX} ERROR: {msg}")


def _reject_dup_keys(pairs):
    """object_pairs_hook — 한 레코드에 중복 키가 있으면 거부한다.
    기본 로더는 뒤값만 남겨 위조 필드가 검사를 우회한다."""
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"중복 JSON 키: {k!r}")
        d[k] = v
    return d


# survey-profile.md / profile-snapshot.md 의 판정 축 불릿. 하나라도 달라지면
# 직전 A/B/C 판정을 승계할 수 없다.
PROFILE_AXES = ["창업 단계", "지역 연고", "대표자", "필요한 것"]

# 회차 폴더에 있지만 raw 크롤이 아닌 diff/판정 산출물
SKIP_FILES = {"new_items.jsonl"}
SKIP_PREFIXES = ("new_items", "screening", "report", "gone_")


def load_dir(d: Path):
    """*d* 의 raw 크롤 *.jsonl 을 전부 {(source, id): record} 로 읽는다.

    Fail-closed: 깨진 JSON 라인·중복 키는 exit 1 로 중단한다.
    """
    records = {}
    files = [
        f for f in sorted(d.glob("*.jsonl"))
        if f.name not in SKIP_FILES and not f.name.startswith(SKIP_PREFIXES)
    ]
    if not files:
        _die(f"raw 크롤 .jsonl 파일이 없다: {d}")
    for f in files:
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line, object_pairs_hook=_reject_dup_keys)
            except (json.JSONDecodeError, ValueError) as e:
                _die(f"깨진 JSON — {f}:{ln} — {e}")
            if not isinstance(rec, dict):
                # 스칼라(null/숫자/불리언)·리스트·문자열 라인은 공고 레코드가
                # 아니다. 조용히 넘기거나 raw TypeError 로 터지지 않고 거부한다.
                _die(f"공고 레코드가 JSON 객체가 아니다 — {f}:{ln} — "
                     f"{type(rec).__name__}")
            if "kind" in rec and "record" in rec:
                continue  # diff 산출물 레코드가 섞인 것 — raw 크롤이 아니다
            # kstartup 레코드는 pbancSn/start/deadline 을 갖고 source 가 없다.
            # 그 외 소스 레코드는 source/id/apply_* 를 갖는다.
            if "pbancSn" in rec:
                key = ("kstartup", str(rec["pbancSn"]))
                rec.setdefault("source", "kstartup")
                rec.setdefault("apply_start", rec.get("start", ""))
                rec.setdefault("apply_end", rec.get("deadline", ""))
            elif "source" in rec and "id" in rec:
                key = (rec["source"], str(rec["id"]))
            else:
                continue  # 알 수 없는 레코드 형태
            # 공통 diff 레코드 스키마(references/diff_record_schema.json)가
            # record.source/source_id 를 요구한다 — 원본 키(pbancSn/id)는 유지.
            rec["source_id"] = key[1]
            if key in records:
                _die(
                    f"중복 키 {key} — {f}:{ln} — 같은 공고가 두 번 로드됐다"
                    " (jsonl 파일이 겹치는가?)"
                )
            records[key] = rec
    return records


def parse_profile_bullets(path):
    """survey-profile.md / profile-snapshot.md 의 '- 키: 값' 불릿을 파싱한다."""
    fields = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return fields
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("-"):
            continue
        s = s.lstrip("-").strip()
        if ":" in s:
            k, v = s.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def profile_fingerprint(fields):
    payload = json.dumps({k: fields.get(k) for k in PROFILE_AXES},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def gone_eligible_from_manifest(curr_dir):
    """GONE 판정이 허용되는 소스 집합 — 이번 회차가 전수 수집을 증명한 소스뿐.

    커버리지 정직성: 공고를 "사라졌다"고 선언하려면 이번 회차가 그 소스를
    빠짐없이 훑었음이 증명돼야 한다. *curr_dir* 의 run_manifest.json 을 읽어
    (eligible, note) 를 반환한다:

      - eligible: status=="ok" 이고 exit_code==0 인 소스 이름 집합.
        partial(api-window/page-cap/manual/inactive) 이거나 manifest 에 없는
        소스는 제외 — 그 레코드는 GONE 으로 보고하지 않는다.
      - manifest 가 없거나 읽을 수 없으면 None — 호출자는 --assume-complete
        가 없는 한 모든 GONE 을 억제한다(fail-closed).
    note 는 요약에 찍을 사람용 문자열(정상 manifest 면 "").
    """
    mpath = curr_dir / "run_manifest.json"
    if not mpath.exists():
        return None, ("run_manifest.json 없음 — 커버리지 미증명이라 GONE 을 억제한다 "
                      "(전수 크롤이 확실하면 --assume-complete)")
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_dup_keys)
        runs = data.get("runs", [])
        if not isinstance(runs, list):
            raise ValueError('"runs" 가 리스트가 아니다')
    except (OSError, json.JSONDecodeError, ValueError, AttributeError) as e:
        return None, f"run_manifest.json 을 읽을 수 없다 ({e}) — GONE 억제"
    eligible = set()
    for r in runs:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "ok" and r.get("exit_code") == 0:
            s = r.get("source")
            if s:
                eligible.add(s)
    return eligible, ""


def changed_fields(old, new):
    return [f for f in COMPARE_FIELDS if (old.get(f) or None) != (new.get(f) or None)]


def classify(old, new):
    """공통 분류 계약 (content_hash/hash_version 포함).

    - 목록 필드 변경 → CHANGED (changed_fields 나열)
    - 양쪽에 해시가 있고 hash_version 이 같고 값이 다름 → CHANGED("content_hash")
    - 양쪽에 해시가 있는데 hash_version 이 다름(v2↔v3 등 산식 전환 — 값 비교
      무의미) → **1회 CHANGED(상세 재검증)**. NEEDS_REHASH 로 두면 재수집해도
      old 가 구버전이라 영구 루프가 된다.
    - 직전엔 해시가 있었는데 이번엔 없음 → NEEDS_REHASH (상세 재수집 후 재분류)
    - 직전엔 없었는데 이번에 처음 생김 → 1회 CHANGED (직전 판정이 상세 없이
      내려졌을 수 있으므로 재검토)
    - 그 외 → UNCHANGED
    """
    fields = [f for f in COMPARE_FIELDS if f != "content_hash"]
    changed = [f for f in fields if (old.get(f) or None) != (new.get(f) or None)]
    old_h, new_h = old.get("content_hash"), new.get("content_hash")
    old_v, new_v = old.get("hash_version"), new.get("hash_version")
    hash_incomparable = bool(old_h and new_h and old_v != new_v)
    if old_h and new_h and not hash_incomparable and old_h != new_h:
        changed.append("content_hash")
    if changed:
        return {"kind": "CHANGED", "changed_fields": changed}
    if hash_incomparable:
        return {"kind": "CHANGED",
                "changed_fields": ["hash_version(산식 전환 — 1회 상세 재검증)"]}
    if old_h and not new_h:
        return {"kind": "NEEDS_REHASH", "changed_fields": []}
    if new_h and not old_h:
        return {"kind": "CHANGED",
                "changed_fields": ["content_hash(최초 상세수집 — 재검토)"]}
    return {"kind": "UNCHANGED", "changed_fields": []}


def emit(fh, kind, flds, rec):
    """공통 diff 레코드(wrapper) 한 줄 — references/diff_record_schema.json 계약."""
    fh.write(json.dumps({"kind": kind, "diff_status": kind,
                         "changed_fields": flds, "record": rec},
                        ensure_ascii=False) + "\n")


def fmt(rec):
    end = rec.get("apply_end") or "?"
    return (f"[{rec.get('source')}] {rec.get('title', '(제목 없음)')} — 마감 {end}"
            f"\n    {rec.get('url', '')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old_dir", type=Path, help="이전 회차 폴더")
    ap.add_argument("new_dir", type=Path, help="이번 회차 폴더")
    ap.add_argument("--out", type=Path, help="검토 대상을 jsonl 로 기록할 경로")
    ap.add_argument("--old-profile",
                    help="이전 회차의 profile-snapshot.md")
    ap.add_argument("--new-profile",
                    help="이번 회차 기준 survey-profile.md")
    ap.add_argument("--assume-complete", action="store_true",
                    help="run_manifest.json 이 없어도 이번 회차를 전 소스 전수 "
                         "크롤로 간주한다(수기·레거시 폴더용). 이 옵션도 없고 "
                         "증명된 manifest 도 없으면 GONE 은 억제된다 — 부분 "
                         "크롤이 '전부 마감'으로 읽히면 안 된다.")
    args = ap.parse_args()

    for d in (args.old_dir, args.new_dir):
        if not d.is_dir():
            _die(f"폴더가 아니다: {d}")

    prev = load_dir(args.old_dir)
    curr = load_dir(args.new_dir)
    if not curr:
        _die("이번 회차 레코드가 0건 — diff 를 거부한다 "
             "(실패한 크롤이 '전부 마감'으로 보이면 안 된다)")

    # ---- 프로필 fingerprint 검증 (fail-closed) ---------------------------
    invalidate = False
    if bool(args.old_profile) != bool(args.new_profile):
        invalidate = True
        _warn("WARNING: 프로필 인자가 한쪽만 지정됐다 — 승계 무효(fail-closed), "
              "전체 재검토")
    elif args.old_profile and args.new_profile:
        old_fields = parse_profile_bullets(args.old_profile)
        new_fields = parse_profile_bullets(args.new_profile)
        # 판정 축(PROFILE_AXES)이 하나도 없는 프로필은 파싱 실패와 같다 — 무관한
        # 불릿만 있는 파일 두 개가 "동일 fingerprint"로 승계를 통과하면 안 된다.
        # 판정 축은 하나라도 빠지면 승계 근거가 불완전하다 — any 가 아니라 ALL.
        old_axes = all(old_fields.get(k) for k in PROFILE_AXES)
        new_axes = all(new_fields.get(k) for k in PROFILE_AXES)
        if not old_fields or not new_fields or not old_axes or not new_axes:
            invalidate = True
            _warn("WARNING: 프로필 파일을 읽지 못했거나 판정 축(창업 단계·지역 연고·"
                  "대표자·필요한 것)이 하나라도 비어 있다 — 승계 무효(fail-closed), "
                  "전체 재검토")
        elif profile_fingerprint(old_fields) != profile_fingerprint(new_fields):
            invalidate = True
            _warn("WARNING: 프로필이 바뀌었다 — 전체 재판정 필요 "
                  "(판정 축이 달라져 UNCHANGED 승계를 무효화한다)")
    else:
        _warn("NOTE: 프로필 미지정 — 판정 승계 유효성(fingerprint)이 검증되지 "
              "않았다. --old-profile/--new-profile 지정 권장")

    prev_sources = {k[0] for k in prev}
    curr_sources = {k[0] for k in curr}
    common = prev_sources & curr_sources

    # 커버리지 가드(fail-closed): 이번 회차가 전수 수집을 증명한 소스에서만
    # GONE 을 선언한다. 부분 크롤(api-window/page-cap)이나 증명 없는 소스는
    # "마감"과 "수집 범위 밖"을 구분할 수 없으므로 삭제를 억제한다.
    eligible, manifest_note = gone_eligible_from_manifest(args.new_dir)
    if eligible is None:  # manifest 없음/불량 → 아무것도 증명되지 않음
        gone_eligible = set(common) if args.assume_complete else set()
    else:
        gone_eligible = {s for s in eligible if s in common}
    suppressed_sources = {s for s in common if s not in gone_eligible}

    new = [curr[k] for k in curr if k not in prev and k[0] in common]
    closed = [prev[k] for k in prev if k not in curr and k[0] in common
              and k[0] not in suppressed_sources]
    suppressed_closed = [prev[k] for k in prev if k not in curr and k[0] in common
                         and k[0] in suppressed_sources]
    results = {k: classify(prev[k], curr[k]) for k in curr if k in prev}
    changed = [
        (prev[k], curr[k], r["changed_fields"])
        for k, r in results.items() if r["kind"] == "CHANGED"
    ]
    needs_rehash = [curr[k] for k, r in results.items()
                    if r["kind"] == "NEEDS_REHASH"]
    unchanged = sum(1 for r in results.values() if r["kind"] == "UNCHANGED")
    added_sources = sorted(curr_sources - prev_sources)
    dropped_sources = sorted(prev_sources - curr_sources)
    first_time = [curr[k] for k in curr if k[0] in added_sources]

    print(f"# 회차 diff: {args.old_dir.name} → {args.new_dir.name}")
    print(f"이전 {len(prev)}건 / 이번 {len(curr)}건 "
          f"(비교 소스: {', '.join(sorted(common)) or '없음'})\n")

    if invalidate:
        print("## CARRY-OVER INVALIDATED — 프로필(판정 축)이 바뀌었거나 검증 불가.")
        print("   UNCHANGED 승계 금지: 아래 분류와 무관하게 전건을 재검토하라.\n")

    print(f"## NEW ({len(new)}) — 전건 검토 + 상세 검증 필요")
    for r in sorted(new, key=lambda r: r.get("apply_end") or "~"):
        print(f"  + {fmt(r)}")

    print(f"\n## CHANGED ({len(changed)}) — 같은 공고인데 필드가 달라짐")
    for old, cur, flds in changed:
        was = ", ".join(f"{f}: {old.get(f) or '?'} → {cur.get(f) or '?'}" for f in flds)
        print(f"  ~ {fmt(cur)}\n    changed_fields: {flds} ({was})")

    if needs_rehash:
        print(f"\n## NEEDS_REHASH ({len(needs_rehash)}) — 직전엔 content_hash 가 "
              "있었는데 이번 회차엔 없음: 상세 재수집(merge) 후 재분류")
        for r in needs_rehash:
            print(f"  ? {fmt(r)}")

    print(f"\n## GONE ({len(closed)}) — 직전 회차 이후 사라짐")
    for r in closed:
        print(f"  - [{r.get('source')}] {r.get('title', '(제목 없음)')}")

    if manifest_note:
        print(f"\n## COVERAGE NOTE — {manifest_note}")
    if suppressed_closed:
        srcs = ", ".join(sorted({r.get('source') for r in suppressed_closed}))
        print(f"\n## GONE SUPPRESSED ({len(suppressed_closed)}) — 이번 회차의 "
              f"[{srcs}] 수집이 부분(api-window/page-cap/manual)이라 부재를 "
              "'마감'으로 단정하지 않는다. 전수 재크롤로 확인하라.")
        for r in suppressed_closed:
            print(f"  · [{r.get('source')}] {r.get('title', '(제목 없음)')}")

    if invalidate:
        print(f"\n## UNCHANGED: {unchanged}건 — 승계 불가(프로필 변경), 전건 재검토")
    else:
        print(f"\n## UNCHANGED: {unchanged}건 (직전 판정 승계)")

    if added_sources:
        print(f"\n## 이번 회차 신규 소스 ({', '.join(added_sources)}): "
              f"{len(first_time)}건 — 기준선이 없으므로 전건 검토")
    if dropped_sources:
        print(f"\n## WARNING — 직전 회차엔 있었으나 이번에 재크롤되지 않은 소스: "
              f"{', '.join(dropped_sources)} (해당 항목은 diff 하지 않았다)")

    if args.out:
        # 공통 diff 레코드 wrapper(kind/diff_status/changed_fields/record) —
        # references/diff_record_schema.json 계약.
        out_path = Path(args.out)
        gone_path = out_path.with_name("gone_" + out_path.name)
        n_out = 0
        with open(args.out, "w", encoding="utf-8") as f:
            if invalidate:
                # 프로필(판정 축) 변경 — 승계 무효: 전건을 NEW 로 강등해 재검토
                for r in curr.values():
                    emit(f, "NEW", [], r)
                n_out = len(curr)
            else:
                for r in new + first_time:
                    emit(f, "NEW", [], r)
                for _, cur, flds in changed:
                    emit(f, "CHANGED", flds, cur)
                for r in needs_rehash:
                    emit(f, "NEEDS_REHASH", [], r)
                n_out = len(new) + len(first_time) + len(changed) + len(needs_rehash)
        # GONE 은 검토 대상과 소비 방식이 다르다(기회 소멸 알림 재료) —
        # --out 에 섞으면 상세검증 대상으로 오인되므로 별도 파일로 분리한다.
        with open(gone_path, "w", encoding="utf-8") as f:
            for r in closed:
                emit(f, "GONE", [], r)
        print(f"\n검토 대상 {n_out}건 → {args.out}"
              + (" (이번 회차 전건 — 승계 무효)" if invalidate else "")
              + f"\nGONE {len(closed)}건 → {gone_path}")


if __name__ == "__main__":
    main()
