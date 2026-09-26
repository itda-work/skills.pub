#!/usr/bin/env python3
"""work-redesign 구조 게이트 — 업무 지도(work-map.md)가 위임 규율을 갖췄는지 기계 검사한다.

업무 지도는 내 업무를 태스크→행동 단위로 쪼개고 가치×AI개입 4분면으로 매핑한 문서다.
쪼개지 않은 뭉텅이(태스크 1개·행동 없음)는 통째 위임 = 의존이고, 전부 자동화 칸에
넣은 답안은 "인간이 지킬 것"을 비운 의존 선언이다. 이 게이트는 그 두 실패와
"사용자 맥락 없는 일반론"(워크슬롭)을 형식 수준에서 반려한다.

'이 행동이 정말 자동화 대상인가·지킬 것의 이유가 타당한가' 같은 **의미** 판정은
이 스크립트가 아니라 SKILL.md 지시에 따라 에이전트가 채점한다 — 스크립트 PASS ≠ 좋은 지도.

입력 형식(업무 지도 — 최상위 섹션은 `##`, 태스크는 `###`):

    ## 맥락
    - 프로젝트: 2분기 파트너 온보딩 개편
    - 도구: Jira, Confluence
    - 이해관계자: 김OO(디자이너)

    ## 태스크 인벤토리
    ### 1. 온보딩 현황 조사
    - Jira 티켓 90일치 내보내기
    - 이탈 구간별 집계

    ## 인간이 지킬 것
    - 개선안 우선순위 결정 — 이유: 파트너 정책 판단

    ## AI로 증강할 것
    - 이탈 구간별 집계 — 검증: 원본 티켓 수와 합계 일치

    ## 일부러 유지할 것
    - 레거시 매뉴얼 정리 — 재검토: 3개월 뒤

    ## 자동화할 것
    - Jira 티켓 내보내기 — 다음: miniskill-forge로 굳히기

    ## 다음 행동
    - 자동화 1순위를 work-find로 구체화

사용:
    python3 check_work_map.py <work-map.md>          # 파일
    py -3 check_work_map.py <work-map.md>            # Windows
    cat work-map.md | python3 check_work_map.py      # stdin
    python3 check_work_map.py <work-map.md> --json   # 기계 판독
    python3 check_work_map.py <work-map.md> --single # 단일 업무 경량 모드(C3 태스크 하한 2→1)

--single 은 "업무 하나만 들고 온" 경량 모드용 완화다: 태스크는 1개면 되지만,
행동 ≥2/태스크(뭉텅이 반려)·좌측 계약·고유 맥락 교차·증강 검증 서술은 그대로 강제한다 —
의존 방지 철학은 축소판에서도 동일하다.

exit code: 0 = 모든 hard 검사 통과, 1 = 위반, 2 = 사용법 오류
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

# 최상위(##) 섹션 키워드 → 정규 섹션 id. 태스크명(###)은 키워드 매칭하지 않으므로
# "자동화 스크립트 관리" 같은 태스크명이 섹션으로 오인되지 않는다.
SECTION_KEYWORDS = {
    "CONTEXT": ["맥락", "배경", "context"],
    "TASKS": ["태스크", "인벤토리", "업무 목록", "task"],
    "KEEP": ["지킬", "인간이", "human", "keep"],
    "AUGMENT": ["증강", "augment"],
    "HOLD": ["유지", "보류", "hold", "defer"],
    "AUTOMATE": ["자동화", "automate"],
    "NEXT": ["다음", "next"],
}
REQUIRED_SECTIONS = ["CONTEXT", "TASKS", "KEEP", "AUGMENT", "HOLD", "AUTOMATE", "NEXT"]
SECTION_LABELS = {
    "CONTEXT": "맥락",
    "TASKS": "태스크 인벤토리",
    "KEEP": "인간이 지킬 것",
    "AUGMENT": "AI로 증강할 것",
    "HOLD": "일부러 유지할 것",
    "AUTOMATE": "자동화할 것",
    "NEXT": "다음 행동",
}
QUADRANTS = ["KEEP", "AUGMENT", "HOLD", "AUTOMATE"]

# 증강 항목의 검증 서술 신호 — 위임은 검증을 동반해야 한다(없으면 의존).
VERIFY_SIGNAL = re.compile(r"검증|대조|판정|일치|기준|정답|정석|체크리스트|verify|check against", re.I)
# HOLD 항목의 재검토 시점 신호(경고)
REVISIT_SIGNAL = re.compile(r"재검토|뒤|후에|시점|revisit|later", re.I)
# 자동화 항목의 다음 행동(핸드오프) 신호(경고)
HANDOFF_SIGNAL = re.compile(r"다음|→|굳히|스킬|next|handoff", re.I)
# 협업(사람 인터페이스) 신호 — 명시 태그 [협업] 또는 대인 행동 어휘.
# "보고서"·"회의록"(산출물)은 제외하고 "보고"·"회의"(행위)만 잡는다.
COLLAB_SIGNAL = re.compile(
    r"\[협업\]|전화|회의(?!록)|미팅|면담|대면|설득|협의|소통|발표|보고(?!서)|meeting|negotiat|present", re.I
)

# 맥락 값 토큰에서 제외할 일반어 — 재등장 카운트가 공허해지는 것을 막는다.
GENERIC_TOKENS = {
    "프로젝트", "역할", "도구", "이해관계자", "동료", "팀", "업무", "회사",
    "관련", "담당", "기타", "등", "있음", "없음",
}

_MD_HEADING = re.compile(r"^(#{1,6})\s*(.+?)\s*$")


def _match_section(text: str):
    """헤딩 텍스트가 최상위 섹션 키워드를 포함하면 섹션 id 반환(긴 키워드 우선)."""
    low = text.strip().lower()
    best, best_len = None, -1
    for sid, kws in SECTION_KEYWORDS.items():
        for kw in kws:
            if kw in low and len(kw) > best_len:
                best, best_len = sid, len(kw)
    return best


def parse(raw: str):
    """업무 지도를 {sections: {sid: [line...]}, tasks: [{name, actions}]} 로 파싱.

    최상위 섹션은 `##` 헤딩만 인식하고, TASKS 섹션 안의 더 깊은 헤딩(`###`+)은
    태스크명으로 취급한다. `#`(문서 제목)·매칭 안 되는 `##` 는 섹션을 닫는다.
    """
    sections: dict[str, list[str]] = {}
    tasks: list[dict] = []
    current = None
    current_task = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        mh = _MD_HEADING.match(stripped)
        if mh:
            level = len(mh.group(1))
            title = mh.group(2)
            if level <= 2:
                sid = _match_section(title) if level == 2 else None
                current = sid
                current_task = None
                if sid:
                    sections.setdefault(sid, [])
                continue
            if current == "TASKS":
                current_task = {"name": title, "actions": []}
                tasks.append(current_task)
                continue
            # 다른 섹션 안의 깊은 헤딩은 내용으로 취급
            if current:
                sections[current].append(title)
            continue
        content = re.sub(r"^[-*•]\s*", "", stripped)
        if current == "TASKS" and current_task is not None:
            current_task["actions"].append(content)
        elif current:
            sections[current].append(content)
    return {"sections": sections, "tasks": tasks}


def _context_tokens(context_lines):
    """맥락 섹션에서 고유 맥락 토큰 추출 — `키: 값` 의 값 부분을 구분자로 쪼갠다."""
    tokens = []
    for ln in context_lines:
        m = re.match(r"^([^:：]{1,20})[:：]\s*(.*)$", ln)
        value = m.group(2) if m else ln
        for tok in re.split(r"[,·/()（）\s]+", value):
            tok = tok.strip()
            if len(tok) >= 2 and tok not in GENERIC_TOKENS:
                tokens.append(tok)
    return tokens


def evaluate(raw: str, single: bool = False):
    parsed = parse(raw)
    sections = parsed["sections"]
    tasks = parsed["tasks"]
    checks = []

    def add(cid, name, ok, detail, severity="hard"):
        checks.append({"id": cid, "name": name, "ok": ok, "detail": detail, "severity": severity})

    # C1 필수 섹션 존재(맥락·태스크·4분면 4개·다음 행동) — TASKS 는 태스크 유무로 판정
    missing = []
    for s in REQUIRED_SECTIONS:
        if s == "TASKS":
            if "TASKS" not in sections or not tasks:
                missing.append(s)
        elif s not in sections or not sections[s]:
            missing.append(s)
    add("C1", "필수 섹션 존재(맥락·태스크·4분면·다음 행동)", not missing,
        "누락/빈 섹션: " + ", ".join(SECTION_LABELS[s] for s in missing) if missing else "OK")

    # C2 좌측 계약: 인간이 지킬 것 ≥1 + 일부러 유지할 것 ≥1 (전부 자동화 = 의존 선언 → 반려)
    keep_n = len(sections.get("KEEP", []))
    hold_n = len(sections.get("HOLD", []))
    add("C2", "좌측 계약 — 인간이 지킬 것 ≥1, 일부러 유지할 것 ≥1", keep_n >= 1 and hold_n >= 1,
        f"지킬 것={keep_n}건, 유지할 것={hold_n}건 (0건이면 전부-자동화 답안 — 지킬 것과 안 할 것부터 정한다)")

    # C3 분해 계약: 태스크 ≥2(단일 업무 모드는 ≥1), 각 태스크 행동 ≥2 (뭉텅이 반려)
    min_tasks = 1 if single else 2
    thin = [t["name"] for t in tasks if len(t["actions"]) < 2]
    c3_ok = len(tasks) >= min_tasks and not thin
    detail = []
    if len(tasks) < min_tasks:
        if single:
            detail.append(f"태스크 {len(tasks)}개 (<1 — 분해할 업무가 없다)")
        else:
            detail.append(f"태스크 {len(tasks)}개 (<2 — 프로젝트가 태스크 1개면 아직 뭉텅이)")
    if thin:
        detail.append("행동 <2 태스크: " + ", ".join(thin))
    add("C3", f"분해 계약 — 태스크 ≥{min_tasks}, 태스크마다 행동 ≥2", c3_ok,
        "; ".join(detail) if detail else "OK")

    # C4 고유 맥락 교차: 맥락 토큰 ≥3 선언 + 그중 ≥2 가 본문(태스크·4분면)에 재등장
    # 재등장 0 이면 맥락 따로 일반론 따로 — 워크슬롭 신호.
    tokens = _context_tokens(sections.get("CONTEXT", []))
    body_text = "\n".join(
        [a for t in tasks for a in ([t["name"]] + t["actions"])]
        + [ln for q in QUADRANTS for ln in sections.get(q, [])]
    )
    reused = sorted({tok for tok in tokens if tok in body_text})
    c4_ok = len(tokens) >= 3 and len(reused) >= 2
    add("C4", "고유 맥락 교차 — 맥락 토큰 ≥3, 본문 재등장 ≥2 (일반론 반려)", c4_ok,
        f"선언 {len(tokens)}개, 재등장 {len(reused)}개"
        + (f" ({', '.join(reused[:5])})" if reused else " — 맥락과 무관한 일반론 의심"))

    # C5 증강 항목마다 검증 서술 — 검증 없는 위임은 의존이다.
    augment = sections.get("AUGMENT", [])
    if not augment:
        add("C5", "증강 항목마다 검증 서술 (검증 없는 위임 = 의존)", False,
            "판정 불가 — 증강 섹션 부재/공백")
    else:
        noverify = [ln for ln in augment if not VERIFY_SIGNAL.search(ln)]
        add("C5", "증강 항목마다 검증 서술 (검증 없는 위임 = 의존)", not noverify,
            "검증 서술 없는 항목:\n    " + "\n    ".join(noverify) if noverify else "OK")

    # W1 과잉 자동화 비율 — 자동화+증강이 4분면 항목의 80% 초과면 재검토 신호
    quad_counts = {q: len(sections.get(q, [])) for q in QUADRANTS}
    total = sum(quad_counts.values())
    if total:
        right = quad_counts["AUGMENT"] + quad_counts["AUTOMATE"]
        if right / total > 0.8:
            add("W1", "자동화+증강 비율 80% 초과 — 과잉 자동화 신호", False,
                f"{right}/{total}건. 지킬 것·유지할 것이 형식적이지 않은지 재검토", severity="warn")

    # W2 유지 항목에 재검토 시점 권장
    hold_norev = [ln for ln in sections.get("HOLD", []) if not REVISIT_SIGNAL.search(ln)]
    if hold_norev:
        add("W2", "유지 항목에 재검토 시점 권장(예: 3개월 뒤)", False,
            "시점 없는 항목: " + "; ".join(hold_norev), severity="warn")

    # W3 자동화 항목에 다음 행동(핸드오프) 권장
    auto_nonext = [ln for ln in sections.get("AUTOMATE", []) if not HANDOFF_SIGNAL.search(ln)]
    if auto_nonext:
        add("W3", "자동화 항목에 다음 행동 권장(예: 다음: miniskill-forge)", False,
            "다음 행동 없는 항목: " + "; ".join(auto_nonext), severity="warn")

    # W4 자동화 항목의 협업 신호 — 사람 인터페이스가 걸린 행동을 통째로 자동화하려는 신호.
    # 기술 부분(집계·초안)만 분리해 위임하고 전달·설득은 사람 몫으로 남기는지 재검토.
    auto_collab = [ln for ln in sections.get("AUTOMATE", []) if COLLAB_SIGNAL.search(ln)]
    if auto_collab:
        add("W4", "자동화 항목에 협업(사람 인터페이스) 신호 — 기술만 분리 위임 검토", False,
            "협업 신호 항목: " + "; ".join(auto_collab), severity="warn")

    hard = [c for c in checks if c["severity"] == "hard"]
    passed = sum(1 for c in hard if c["ok"])
    return {
        "ok": all(c["ok"] for c in hard),
        "score": f"{passed}/{len(hard)}",
        "mode": "single" if single else "full",
        "checks": checks,
        "sections_found": sorted(sections.keys()),
        "task_count": len(tasks),
        "quadrant_counts": {SECTION_LABELS[q]: len(sections.get(q, [])) for q in QUADRANTS},
    }


def render_human(result) -> str:
    mode_tag = " · 단일 업무 모드" if result.get("mode") == "single" else ""
    lines = [f"work-redesign 구조 게이트 — {'PASS ✅' if result['ok'] else 'FAIL ❌'}  ({result['score']} hard{mode_tag})", ""]
    for c in result["checks"]:
        mark = "⚠️ " if c["severity"] == "warn" else ("✅" if c["ok"] else "❌")
        lines.append(f"{mark} {c['id']} {c['name']}")
        if not c["ok"] or c["severity"] == "warn":
            for d in str(c["detail"]).splitlines():
                lines.append(f"      {d}")
    if not result["ok"]:
        lines.append("")
        lines.append("→ 실패 축마다 인터뷰로 되돌아가 사용자 맥락으로 채운다. 짐작으로 채우지 않는다.")
    return "\n".join(lines)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
    single = "--single" in argv
    if args:
        try:
            raw = open(args[0], encoding="utf-8").read()
        except OSError as e:
            sys.stderr.write(f"파일 읽기 실패: {e}\n")
            return 2
    else:
        if sys.stdin.isatty():
            sys.stderr.write(__doc__)
            return 2
        raw = sys.stdin.read()

    result = evaluate(raw, single=single)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
