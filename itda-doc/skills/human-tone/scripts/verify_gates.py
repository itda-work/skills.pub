"""verify_gates.py — 윤문 사후 결정적 판정 게이트 (4축, LLM 호출 0, 표준 라이브러리만).

human-tone 의 "변경률 30% 경고 / 50% 강제 중단" 은 v2.0 까지 SKILL.md 의 문서 규율이었다.
문서 규율은 지켜졌는지 아무도 재지 않는다 — 이 스크립트가 그 판정을 코드로 옮기고,
문자 변경률만으로는 보이지 않는 세 축(목표 달성/과교정 · 수사 전멸 · 보존 불변식)을 더한다.

축:
    P0 문자 변경률 — 정규화한 before/after 의 문자 단위 변경률. >30% WARN, ≥50% ABORT(롤백).
                    카피 씬은 면제(보고만). <5% 는 저윤문 **참고**만 — 억지로 더 고치라는
                    신호가 아니다(상류 반증: 정상 한국어를 지우는 것이 더 큰 결함).
    P1 목표 달성/과교정 — ① baseline z 지표: 윤문 전 z>2.0 이던 지표가 윤문 후 z≤1.0 으로
                    들어왔는가(미달 WARN), -1.5 아래로 넘어갔는가(과교정 WARN).
                    ② 조건부 규칙(A-2·I-1·A-16, 2026-09 #1619 상류 반증 반영): 남발이 아니던
                    정상 사용을 0 으로 지웠으면 과교정 WARN.
    P2 수사 전멸 — 대구·부정 대조·문두 반복(anaphora) 합계가 before ≥ N 인데 after == 0 이면 FAIL.
                    줄인 것이 아니라 수사 구조를 몰살한 것이다(C-8 처방은 "일부만 비대칭으로").
    P3 보존 불변식 — lock_preserved.mask/audit 재사용: 보존 토큰 전부 잔존 + 원문에 없던 숫자 0.

종료 코드:
    0 PASS          전 축 통과
    1 FAIL          WARN/FAIL/ABORT 1건 이상 — 축별 status 로 롤백(ABORT)/보완(WARN·FAIL) 구분
    2 INCONCLUSIVE  판정 불능 — 표본이 짧아 z 를 못 재거나 baseline 이 없다. **PASS 가 아니다.**
    3 입력 오류      파일 없음·빈 텍스트·미지 씬·인자 오류. 게이트를 건너뛰지 않는다.

사용:
    python3 verify_gates.py --before input.txt --after final.txt --scene report
    python3 verify_gates.py --before a.txt --after b.txt --scene email --json

설계 출처: `epoko77-ai/im-not-ai`(MIT) `verify_gates.py` 의 축 구성(P0~P3)과 exit 의미론을 참고했다.
로직은 이 스킬의 지표(metrics.py v1.6 · lock_preserved.py) 위에 다시 썼다. README 차용 출처 참조.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import lock_preserved as lp  # noqa: E402
import metrics as mt  # noqa: E402

VERSION = "v1.0"

EXIT_PASS, EXIT_FAIL, EXIT_INCONCLUSIVE, EXIT_INPUT = 0, 1, 2, 3

# ── P0 임계 ────────────────────────────────────────────────────────────────
CHANGE_WARN = 0.30
CHANGE_ABORT = 0.50
CHANGE_LOW = 0.05

# ── P1 z 임계(baseline 지표) ───────────────────────────────────────────────
Z_FLAGGED = 2.0        # 윤문 전 이 값을 넘긴 지표만 목표 대상
Z_TARGET = 1.0         # 윤문 후 여기 안으로 들어와야 달성
Z_OVERCORRECT = -1.5   # 여기 아래로 넘어가면 과교정
MIN_SENTENCES_FOR_Z = 10  # 이 미만이면 비율 지표가 quantization 노이즈 — z 판정 SKIP → INCONCLUSIVE
# P1 z 대상은 KatFish 실측 셀(baseline.json genres.*)이 있는 쉼표 4지표뿐이다. metrics.py 의
# hanja_nominalizer_density·lexical_diversity 는 스스로 "placeholder/rough proxy" 라 선언한 추정
# baseline 이고 lexical_diversity 는 z 부호까지 반대(높을수록 사람)라 목표 판정에 쓰지 않는다.
P1_Z_KEYS = ("comma_inclusion_rate", "comma_usage_rate", "ending_comma_rate", "comma_segment_length")

# ── P1 조건부 규칙(상류 empirical-validation 반영, #1619) ──────────────────
# abuse_min: before 가 이 값 이상이면 "남발" — 억제 대상. 미만이면 정상 사용이라 보존 대상.
# abuse_run: 연속 종결 횟수 기준(I-1). scenes: 이 씬에서만 발동(A-16 번역 맥락 전용).
# preserve_min: 윤문 후 남아 있어야 하는 최소 개수(before 가 그보다 적으면 before 만큼).
# 뮤테이션(구 S1 무조건 제거 semantics 복원): A-2 preserve_min→0 · I-1 abuse_run→1 ·
# A-16 scenes→전 씬. 각각 tests/test_verify_gates.py 의 보존 골든이 RED 가 되어야 한다.
CONDITIONAL_RULES: dict[str, dict[str, Any]] = {
    "A-2": {"label": "~를 통해", "abuse_min": 3, "preserve_min": 1},
    "I-1": {"label": "것이다 종결", "abuse_run": 3},
    "A-16": {"label": "영어 대명사 직역(그/그녀/그들/그것)", "scenes": {"translation"}},
}

# ── P2 임계 ────────────────────────────────────────────────────────────────
ANNIHILATION_BEFORE_MIN = 3  # 사무 글은 짧다 — 상류(5)보다 낮춰 잡는다. 정상 수사의 절대 개수는 판정하지 않는다.

SCENES = {"report", "email", "proposal", "notice", "translation", "copy"}
COPY_SCENES = {"copy"}
SCENE_ALIASES = {
    "보고서": "report", "리포트": "report", "메일": "email", "이메일": "email",
    "기획서": "proposal", "제안서": "proposal", "공지": "notice", "안내문": "notice",
    "번역": "translation", "카피": "copy", "광고": "copy", "슬로건": "copy",
}
# metrics.py baseline 장르 매핑 — 사무 산문 4종은 에세이 셀을 쓴다(KatFish 에 사무 장르 셀 없음).
_METRICS_GENRE = {s: "essay" for s in SCENES}


def canonical_scene(scene: str) -> str:
    s = (scene or "").strip()
    return SCENE_ALIASES.get(s, s.lower())


# ── 사전 정규화 — 게이트 앞에서 한 번만 ──────────────────────────────────────
_ZERO_WIDTH_RE = re.compile("[\u200b\ufeff\u2060]")  # ZWJ/ZWNJ 는 이모지 결합에 쓰여 보존
_SPECIAL_SPACE_RE = re.compile("[\u00a0\u2000-\u200a\u202f\u205f\u3000]")
_DASH_RE = re.compile("[–—―‒]")
_QUOTE_MAP = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def normalize(text: str) -> str:
    """공백·따옴표·대시·NFC 통일. before/after 양쪽에 같은 정규화를 적용해야 변경률이 같은 기준을 쓴다.

    AI 워터마크 제거 기능이 아니다 — 측정 기준을 하나로 맞추는 것이 목적이다.
    """
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _ZERO_WIDTH_RE.sub("", t)
    t = _SPECIAL_SPACE_RE.sub(" ", t)
    t = t.translate(_QUOTE_MAP)
    t = _DASH_RE.sub("-", t)
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return t.strip()


# ── 계수 함수 ──────────────────────────────────────────────────────────────
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+|\n+")
_PUNCT_TAIL_RE = re.compile(r"[\s\.\!\?。\"'\)\]」』]+$")
_TONGHAE_RE = re.compile(r"통하여|통해")
_GEOSIDA_RE = re.compile(r"것(?:이다|입니다|이었다|이었습니다)$")
_PRONOUN_RE = re.compile(r"^(?:그는|그가|그의|그를|그에게|그녀|그들|그것)")
_NEG_CONTRAST_RE = re.compile(r"(?:이|가|은|는) 아니라")
_QUESTION_PAIR_RE = re.compile(r"(?:인가|일까)[,?]\s*[^.!?\n]{1,40}?(?:인가|일까)")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def count_tonghae(text: str) -> int:
    """A-2 — '통해/통하여' 출현 수."""
    return len(_TONGHAE_RE.findall(text))


def count_geosida(text: str) -> tuple[int, int]:
    """I-1 — '것이다' 류 종결 (총 개수, 최장 연속 횟수)."""
    total = run = longest = 0
    for s in sentences(text):
        tail = _PUNCT_TAIL_RE.sub("", s)
        if _GEOSIDA_RE.search(tail):
            total += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return total, longest


def count_pronouns(text: str) -> int:
    """A-16 — 어절 선두의 3인칭 대명사(그는/그의/그녀/그들/그것…) 수."""
    return sum(1 for tok in text.split() if _PRONOUN_RE.match(tok))


def rhetoric_counts(text: str) -> dict[str, int]:
    """P2 — 수사 구조 계수. 대구(A인가, B인가) · 부정 대조(A가 아니라 B) · 문두 반복(anaphora)."""
    sents = sentences(text)
    anaphora = 0
    prev_head = None
    for s in sents:
        head = s.split()[0] if s.split() else ""
        head = _PUNCT_TAIL_RE.sub("", head)
        if len(head) >= 2 and head == prev_head:
            anaphora += 1
        prev_head = head
    return {
        "question_pair": len(_QUESTION_PAIR_RE.findall(text)),
        "neg_contrast": len(_NEG_CONTRAST_RE.findall(text)),
        "anaphora": anaphora,
    }


def change_rate(before: str, after: str) -> float:
    """문자 단위 변경률 (0~1). 두 텍스트가 모두 비면 0."""
    if not before and not after:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, before, after, autojunk=False).ratio()


# ── 축 판정 ────────────────────────────────────────────────────────────────

def judge_p0(rate: float, scene: str) -> dict[str, Any]:
    if scene in COPY_SCENES:
        return {"status": "REPORT", "value": round(rate, 4),
                "note": f"문자 변경률 {rate:.1%} — 카피 씬은 변경률 게이트 면제(판정은 P3 사실 앵커가 맡는다)"}
    if rate >= CHANGE_ABORT:
        return {"status": "ABORT", "value": round(rate, 4),
                "note": f"문자 변경률 {rate:.1%} ≥ {CHANGE_ABORT:.0%} — 강제 중단, 마지막 안정 버전으로 롤백"}
    if rate > CHANGE_WARN:
        return {"status": "WARN", "value": round(rate, 4),
                "note": f"문자 변경률 {rate:.1%} > {CHANGE_WARN:.0%} — 과윤문 경고, 변경 하나하나를 탐지 근거와 대조"}
    note = f"문자 변경률 {rate:.1%} — 정상 범위(5~30%)"
    if rate < CHANGE_LOW:
        note = f"문자 변경률 {rate:.1%} < {CHANGE_LOW:.0%} — 저윤문 참고(S1 누락 재확인). 억지로 더 고치지 않는다"
    return {"status": "PASS", "value": round(rate, 4), "note": note}


def judge_p1_z(before: str, after: str, scene: str, baseline: str | None) -> dict[str, Any]:
    n_sent = len(sentences(before))
    if n_sent < MIN_SENTENCES_FOR_Z:
        return {"status": "SKIP", "notes": [
            f"문장 {n_sent}개 < {MIN_SENTENCES_FOR_Z}개 — 비율 지표가 노이즈라 z 판정을 건너뛴다(INCONCLUSIVE)"]}
    genre = _METRICS_GENRE.get(scene, "essay")
    try:
        b = mt.compute_all(before, genre=genre, baseline_path=baseline)
        a = mt.compute_all(after, genre=genre, baseline_path=baseline)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "NO_BASELINE", "notes": [f"baseline 을 읽지 못했다({exc}) — P1 은 판정 불능(INCONCLUSIVE)"]}
    notes: list[str] = []
    status = "PASS"
    for key in P1_Z_KEYS:
        bz = (b.get("z_scores") or {}).get(key)
        az = (a.get("z_scores") or {}).get(key)
        if bz is None or az is None or bz <= Z_FLAGGED:
            continue
        if az > Z_TARGET:
            status = "WARN"
            notes.append(f"{key}: z {bz:+.2f} → {az:+.2f} — 목표(≤{Z_TARGET:+.1f}) 미달")
        elif az < Z_OVERCORRECT:
            status = "WARN"
            notes.append(f"{key}: z {bz:+.2f} → {az:+.2f} — {Z_OVERCORRECT:+.1f} 아래로 과교정")
        else:
            notes.append(f"{key}: z {bz:+.2f} → {az:+.2f} — 목표 달성")
    if not notes:
        notes.append("윤문 전에 z>2.0 으로 걸린 baseline 지표가 없다")
    return {"status": status, "notes": notes}


def judge_p1_conditional(before: str, after: str, scene: str) -> dict[str, Any]:
    """조건부 규칙 과교정 — 남발이 아니던 정상 한국어를 0 으로 지웠는가."""
    notes: list[str] = []
    status = "PASS"
    detail: dict[str, Any] = {}

    r = CONDITIONAL_RULES["A-2"]
    b_t, a_t = count_tonghae(before), count_tonghae(after)
    detail["A-2"] = [b_t, a_t]
    if a_t < min(b_t, r["preserve_min"]):
        status = "WARN"
        why = "남발이 아니라 보존 대상" if b_t < r["abuse_min"] else "남발이어도 한두 번은 보존"
        notes.append(f"A-2 '{r['label']}' {b_t} → {a_t} — {why}(상류 반증: 원어민이 2배 더 씀). 과교정")

    r = CONDITIONAL_RULES["I-1"]
    (b_g, b_run), (a_g, _) = count_geosida(before), count_geosida(after)
    detail["I-1"] = [b_g, a_g, {"before_max_run": b_run}]
    if b_g > 0 and b_run < r["abuse_run"] and a_g == 0:
        status = "WARN"
        notes.append(f"I-1 '{r['label']}' {b_g} → 0 (최장 연속 {b_run} < {r['abuse_run']}) — 남발이 아니라 보존 대상"
                     "(상류 반증: 사람이 2배 더 씀). 과교정")

    r = CONDITIONAL_RULES["A-16"]
    b_p, a_p = count_pronouns(before), count_pronouns(after)
    detail["A-16"] = [b_p, a_p]
    if scene not in r["scenes"] and b_p > 0 and a_p == 0:
        status = "WARN"
        notes.append(f"A-16 '{r['label']}' {b_p} → 0 — 씬 '{scene}' 은 자생 한국어 산문이라 이 규칙이 발동하지 않는다"
                     "(번역 맥락 전용). 과교정")

    if not notes:
        notes.append("조건부 규칙(A-2·I-1·A-16) 과교정 없음")
    return {"status": status, "notes": notes, "detail": detail}


def judge_p2(before: str, after: str) -> dict[str, Any]:
    b, a = rhetoric_counts(before), rhetoric_counts(after)
    tb, ta = sum(b.values()), sum(a.values())
    detail = {"before": b, "after": a, "total": [tb, ta]}
    if tb >= ANNIHILATION_BEFORE_MIN and ta == 0:
        return {"status": "FAIL", "detail": detail,
                "note": f"수사 구조 {tb} → 0 — 줄인 게 아니라 전멸시켰다. C-8 처방은 '일부만 비대칭으로'이지 전량 삭제가 아니다"}
    return {"status": "PASS", "detail": detail, "note": f"수사 구조 {tb} → {ta}"}


def judge_p3(before: str, after: str) -> dict[str, Any]:
    _, pmap = lp.mask(before)
    report = lp.audit(before, after, pmap)
    detail = {"preserved_count": report["preserved_count"],
              "mismatches": report["mismatches"], "extra_numeric": report["extra_numeric"]}
    if not report["pass"]:
        parts = []
        if report["mismatches"]:
            parts.append(f"보존 토큰 {len(report['mismatches'])}건 소실/변형")
        if report["extra_numeric"]:
            parts.append(f"원문에 없던 숫자 {report['extra_numeric']}")
        return {"status": "FAIL", "detail": detail, "note": "보존 불변식 위반: " + ", ".join(parts)}
    return {"status": "PASS", "detail": detail,
            "note": f"보존 토큰 {report['preserved_count']}개 잔존, 환각 숫자 0"}


# ── 종합 ───────────────────────────────────────────────────────────────────

def run(before_raw: str, after_raw: str, scene: str = "report",
        baseline: str | None = None) -> dict[str, Any]:
    scene_in = scene
    scene = canonical_scene(scene)
    if scene not in SCENES:
        raise ValueError(f"미지 씬 '{scene_in}' — 허용: {sorted(SCENES)}")
    before, after = normalize(before_raw), normalize(after_raw)
    if not before or not after:
        raise ValueError("before/after 가 비어 있다")

    rate = change_rate(before, after)
    p0 = judge_p0(rate, scene)
    p1z = judge_p1_z(before, after, scene, baseline)
    p1c = judge_p1_conditional(before, after, scene)
    p2 = judge_p2(before, after)
    p3 = judge_p3(before, after)

    statuses = [p0["status"], p1z["status"], p1c["status"], p2["status"], p3["status"]]
    if any(s in ("ABORT", "FAIL", "WARN") for s in statuses):
        verdict, code = "FAIL", EXIT_FAIL
    elif p1z["status"] in ("SKIP", "NO_BASELINE"):
        # 검사하지 못한 것을 통과로 읽지 않는다.
        verdict, code = "INCONCLUSIVE", EXIT_INCONCLUSIVE
    else:
        verdict, code = "PASS", EXIT_PASS

    return {
        "version": VERSION,
        "verdict": verdict,
        "exit_code": code,
        "rollback": p0["status"] == "ABORT",
        "scene": scene,
        "scene_input": scene_in,
        "char_count": [len(before), len(after)],
        "axes": {
            "P0_문자변경률": p0,
            "P1_목표달성_z": p1z,
            "P1_과교정_조건부규칙": p1c,
            "P2_수사전멸": p2,
            "P3_보존불변식": p3,
        },
        "caveat": ("P0·P2·P3 는 정확한 셈이고 P1 z 는 stdev 추정치에 기댄 지시적 수치다. "
                   "이 게이트는 구조를 볼 뿐 의미를 보지 않는다 — 13항 의미 동등성 audit 은 따로 한다."),
    }


class _Parser(argparse.ArgumentParser):
    """인자 오류를 exit 3 으로 낸다(argparse 기본 2 는 이 스크립트에서 INCONCLUSIVE 다)."""

    def error(self, message: str):  # noqa: D102
        self.print_usage(sys.stderr)
        print(f"{self.prog}: 인자 오류: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = _Parser(description="human-tone 윤문 사후 판정 게이트 (P0~P3)")
    ap.add_argument("--before", required=True, help="윤문 전 원문 파일")
    ap.add_argument("--after", required=True, help="윤문본 파일")
    ap.add_argument("--scene", default="report", help="report|email|proposal|notice|translation|copy (한국어 별칭 허용)")
    ap.add_argument("--baseline", default=None, help="metrics baseline.json 경로(기본: scripts/baseline.json)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args(argv)

    try:
        before, after = _read(args.before), _read(args.after)
    except OSError as exc:
        print(f"게이트 실행 불가: {exc}", file=sys.stderr)
        return EXIT_INPUT
    try:
        result = run(before, after, args.scene, args.baseline)
    except ValueError as exc:
        print(f"게이트 입력 오류: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # noqa: BLE001 — 게이트가 조용히 죽으면 안 된다
        print(f"게이트 실행 오류: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INPUT

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result["exit_code"]

    print(f"판정: {result['verdict']}  (씬={result['scene']}, exit={result['exit_code']}"
          f"{', 롤백' if result['rollback'] else ''})")
    for axis, data in result["axes"].items():
        print(f"  [{data['status']:<7}] {axis}")
        if "note" in data:
            print(f"            {data['note']}")
        for n in data.get("notes", []):
            print(f"            {n}")
    print(f"\n{result['caveat']}")
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
