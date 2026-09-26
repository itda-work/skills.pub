#!/usr/bin/env python3
"""stakeholder-map 구조 게이트 — 이해관계자 문서가 선행 전달 규율을 갖췄는지 기계 검사한다.

이해관계자 문서(stakeholders/<이름>.md)는 "이 사람이 일을 시작하려면 뭘 먼저 알아야
하나"를 담는 계약이다. 선행 전달물(제약 조건)이 비거나 모호하면("잘 부탁", "센스있게")
받은 쪽이 짐작으로 만들고, 다 만든 걸 다시 만드는 낭비가 생긴다 — 테이블 사이즈를
안 알려주고 진열 시안을 받는 격이다.

'이 제약이 충분한가·요청 순서가 맞는가' 같은 **의미** 판정은 이 스크립트가 아니라
SKILL.md 지시에 따라 에이전트가 채점한다 — 스크립트 PASS ≠ 좋은 문서.

입력 형식(이해관계자 문서 — 최상위 섹션은 `##`):

    # 이해관계자 — 김디자 (디자이너)

    ## 역할
    - 온보딩 화면 시안 담당

    ## 요청할 것
    - 온보딩 개선안 시안 2종 — 기한: 7/30

    ## 받을 것
    - 컴포넌트 가이드 최신본

    ## 선행 전달물
    - 톤: 밝고 실용적 (참고: 기존 배너 2종)
    - 형식: 1080x1920 세로, 슬라이드 4장
    - 필수 문구: "7월 한정"

    ## 소통
    - 채널: 슬랙 #onboarding
    - 주기: 주간 목요일 싱크

사용:
    python3 check_stakeholder.py <파일.md> [<파일2.md> ...]   # 파일 여러 개 가능
    py -3 check_stakeholder.py stakeholders/*.md              # Windows
    python3 check_stakeholder.py <파일.md> --json             # 기계 판독

exit code: 0 = 전 파일 hard 통과, 1 = 위반 파일 존재, 2 = 사용법 오류
"""
from __future__ import annotations

import json
import re
import sys

if sys.version_info[0] < 3:  # pragma: no cover - python2 방어
    sys.exit("python3 필요")

# Windows 콘솔(cp949)이 em-dash·이모지를 인코딩 못 해 깨지는 것을 막는다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):  # pragma: no cover - 구버전/파이프 방어
        pass

SECTION_KEYWORDS = {
    "ROLE": ["역할", "role"],
    "ASK": ["요청할", "요청", "ask", "request"],
    "RECEIVE": ["받을", "receive"],
    "HANDOFF": ["선행 전달물", "선행전달물", "선행 전달", "제약", "handoff", "constraints"],
    "COMM": ["소통", "커뮤니케이션", "communication", "채널"],
}
REQUIRED_SECTIONS = ["ROLE", "ASK", "HANDOFF", "COMM"]
SECTION_LABELS = {
    "ROLE": "역할", "ASK": "요청할 것", "RECEIVE": "받을 것",
    "HANDOFF": "선행 전달물", "COMM": "소통",
}

# 모호어 — 받은 쪽이 짐작으로 채우게 만드는 어휘(hard 섹션에서 반려)
VAGUE_TERMS = [
    "알아서", "적당히", "적절히", "적절하게", "잘 부탁", "센스", "느낌있게", "이쁘게",
    "예쁘게", "깔끔하게", "빠르게", "최대한", "가능한 한", "가능한한", "괜찮게",
    "nicely", "properly", "asap", "whenever",
]
VAGUE_REGEX = [re.compile(r"(^|\s)잘(\s|$)")]

# 미확정 마커 — 모르는 칸을 플레이스홀더로 채워 게이트를 통과시키는 것을 막는다(#1246 D3).
# 계약은 "모르면 그 줄을 지워서 게이트 FAIL 로 표면화" — '확인 필요: …' 류 값은 제약이 아니다.
PENDING_TERMS = [
    "확인 필요", "확인필요", "미확정", "미정", "추후 확정", "tbd", "todo", "❗",
]

# 선행 전달물 구체성: "키: 값" 구조 — 톤/형식/사이즈/문구처럼 이름 붙은 제약이어야
# 받은 쪽이 체크리스트로 쓸 수 있다.
KEYED_ITEM = re.compile(r"^[^:：]{1,20}[:：]\s*\S")

# 기한/시점 신호(요청 항목 권장 — W2)
DUE_SIGNAL = re.compile(r"기한|까지|마감|\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2}|due", re.I)
# 소통 채널·주기 신호(W3)
CHANNEL_SIGNAL = re.compile(r"채널|슬랙|slack|메일|mail|카톡|teams|전화", re.I)
CADENCE_SIGNAL = re.compile(r"주기|주간|매주|매일|격주|월간|요일|daily|weekly", re.I)

_MD_HEADING = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
_TITLE_ROLE = re.compile(r"[(（][^)）]{1,30}[)）]")


def _match_section(text: str):
    low = text.strip().lower()
    best, best_len = None, -1
    for sid, kws in SECTION_KEYWORDS.items():
        for kw in kws:
            if kw in low and len(kw) > best_len:
                best, best_len = sid, len(kw)
    return best


def parse(raw: str):
    """{title, sections{sid: [line...]}} — 최상위 `##` 만 섹션, `#` 은 문서 제목."""
    sections: dict[str, list[str]] = {}
    title = ""
    current = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        mh = _MD_HEADING.match(stripped)
        if mh:
            level = len(mh.group(1))
            if level == 1:
                title = mh.group(2)
                current = None
                continue
            if level == 2:
                current = _match_section(mh.group(2))
                if current:
                    sections.setdefault(current, [])
                continue
            if current:
                sections[current].append(mh.group(2))
            continue
        if current:
            sections[current].append(re.sub(r"^[-*•]\s*", "", stripped))
    return {"title": title, "sections": sections}


def _vague_hits(text: str):
    hits = []
    low = text.lower()
    for term in VAGUE_TERMS:
        if term.lower() in low:
            hits.append(term)
    for rx in VAGUE_REGEX:
        m = rx.search(text)
        if m:
            hits.append(m.group().strip())
    return hits


def evaluate(raw: str):
    doc = parse(raw)
    sections = doc["sections"]
    checks = []

    def add(cid, name, ok, detail, severity="hard"):
        checks.append({"id": cid, "name": name, "ok": ok, "detail": detail, "severity": severity})

    # C1 필수 섹션(역할·요청할 것·선행 전달물·소통) 존재·비지 않음
    missing = [s for s in REQUIRED_SECTIONS if not sections.get(s)]
    add("C1", "필수 섹션 존재(역할·요청할 것·선행 전달물·소통)", not missing,
        "누락/빈 섹션: " + ", ".join(SECTION_LABELS[s] for s in missing) if missing else "OK")

    # C2 선행 전달물 구체성 — 항목 ≥2, 전 항목 '키: 값' 구조
    handoff = sections.get("HANDOFF", [])
    unkeyed = [ln for ln in handoff if not KEYED_ITEM.match(ln)]
    c2_ok = len(handoff) >= 2 and not unkeyed
    detail = []
    if len(handoff) < 2:
        detail.append(f"{len(handoff)}건 (<2 — 톤·형식·분량·필수 문구처럼 이름 붙은 제약을 2건 이상)")
    if unkeyed:
        detail.append("'키: 값' 구조 아님:\n    " + "\n    ".join(unkeyed))
    add("C2", "선행 전달물 ≥2건, 전 항목 '키: 값' 제약 구조", c2_ok,
        "\n".join(detail) if detail else "OK")

    # C3 모호어 0 (hard 섹션) — "알아서"·"잘 부탁"은 제약이 아니라 짐작 위임이다
    hard_text = "\n".join("\n".join(sections.get(s, [])) for s in REQUIRED_SECTIONS)
    vh = _vague_hits(hard_text)
    add("C3", "모호어 0 (역할·요청·선행 전달물·소통)", not vh,
        "모호어: " + ", ".join(sorted(set(vh))) if vh else "OK")

    # C4 미확정 마커 0 (hard 섹션) — 모르는 칸은 플레이스홀더로 채우지 말고 지워서
    # 게이트 FAIL(C1/C2)로 표면화한다 (#1246 D3: '❗확인 필요' 값이 게이트를 우회한 실측)
    low_hard = hard_text.lower()
    pending = sorted({t for t in PENDING_TERMS if t in low_hard})
    add("C4", "미확정 마커 0 — 모르는 칸은 지워서 FAIL 로 표면화", not pending,
        "미확정 마커: " + ", ".join(pending) if pending else "OK")

    # W1 받을 것 섹션 권장
    if not sections.get("RECEIVE"):
        add("W1", "받을 것 섹션 권장 — 병목은 양방향에서 생긴다", False,
            "이 사람에게서 내가 받아야 할 것(자료·결정·승인)도 적으면 대기 병목이 보인다", severity="warn")

    # W2 요청 항목 기한 권장
    ask_nodue = [ln for ln in sections.get("ASK", []) if not DUE_SIGNAL.search(ln)]
    if ask_nodue:
        add("W2", "요청 항목에 기한 권장(예: 기한: 7/30)", False,
            "기한 없는 항목: " + "; ".join(ask_nodue), severity="warn")

    # W3 소통에 채널+주기 권장
    comm_text = "\n".join(sections.get("COMM", []))
    if comm_text and not (CHANNEL_SIGNAL.search(comm_text) and CADENCE_SIGNAL.search(comm_text)):
        add("W3", "소통에 채널·주기 둘 다 권장(예: 슬랙 + 주간 목요일)", False,
            f"채널={bool(CHANNEL_SIGNAL.search(comm_text))}, 주기={bool(CADENCE_SIGNAL.search(comm_text))}",
            severity="warn")

    # W4 문서 제목에 역할 병기 권장 — `# 이해관계자 — 김디자 (디자이너)`
    if not _TITLE_ROLE.search(doc["title"]):
        add("W4", "제목에 이름과 (역할) 병기 권장", False,
            f"현재 제목: {doc['title'] or '(없음)'}", severity="warn")

    hard = [c for c in checks if c["severity"] == "hard"]
    passed = sum(1 for c in hard if c["ok"])
    return {
        "ok": all(c["ok"] for c in hard),
        "score": f"{passed}/{len(hard)}",
        "title": doc["title"],
        "checks": checks,
        "sections_found": sorted(sections.keys()),
    }


def render_human(path: str, result) -> str:
    lines = [f"{path}: {'PASS ✅' if result['ok'] else 'FAIL ❌'}  ({result['score']} hard)"]
    for c in result["checks"]:
        if c["ok"] and c["severity"] == "hard":
            continue
        mark = "⚠️ " if c["severity"] == "warn" else "❌"
        lines.append(f"  {mark} {c['id']} {c['name']}")
        for d in str(c["detail"]).splitlines():
            lines.append(f"        {d}")
    return "\n".join(lines)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
    if not args:
        sys.stderr.write(__doc__)
        return 2

    results = {}
    for path in args:
        try:
            raw = open(path, encoding="utf-8").read()
        except OSError as e:
            sys.stderr.write(f"파일 읽기 실패: {e}\n")
            return 2
        results[path] = evaluate(raw)

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for path, result in results.items():
            print(render_human(path, result))
        fails = [p for p, r in results.items() if not r["ok"]]
        if fails:
            print()
            print("→ 실패 축은 인터뷰로 되돌아가 그 사람에게 실제로 필요한 제약을 묻는다.")
    return 0 if all(r["ok"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
