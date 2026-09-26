#!/usr/bin/env python3
"""task-brief 구조 게이트 — 작업 브리프가 3요소 규율을 갖췄는지 기계 검사한다.

작업 브리프는 일상 요청 1건을 에이전트에 던지기 직전, 30초~2분 안에 채우는 1장짜리
계약이다. 3요소가 빠지면 에이전트가 sandbox 없이 헤매거나(범위 결손), '동작함'을
자기보고로 흘려보내거나(검증 결손), 언제 멈출지 몰라 토큰을 태운다(완료정의 결손).

이 스크립트는 그 3요소의 **형식**을 강제하는 구조 게이트다. 특히 검증 방법이
'자기보고'(확인했다·잘 된다·문제없음)가 아니라 **재현 가능한 명령·파일·수치**로
서술됐는지 본다 — 브리프를 받는 쪽이 스스로 돌려 참·거짓을 판정할 수 있어야 한다.

'사실 명제인가·경계가 본질적인가·완료가 완결인가' 같은 **의미** 판정은 이 스크립트가
아니라 SKILL.md 지시에 따라 에이전트(강한 모델)가 채점한다 — 스크립트 PASS ≠ 좋은 브리프.

입력 형식(작업 브리프, 아래 섹션 — 최상단 '## 의도 (선택)' 는 맥락 산문으로 검사 제외):

    ## 작업
    <한 줄 사실 목표>

    ## 범위
    - 포함: internal/foo/ 의 파서 로직, handler_foo.go
    - 제외: MCP 등록·CLI parity·다른 도메인 파일

    ## 검증 방법
    - `go test -race ./internal/foo/...` exit==0
    - STATUS-FOO.md 에 신규 항목 1줄 추가됨

    ## 완료 정의
    - git status clean
    - 위 테스트 GREEN + STATUS 갱신 커밋됨

    ## 예산 (선택)
    - 질문 허용: 2회
    - 토큰 상한: 200k

사용:
    python3 check_task_brief.py <brief.md>        # 파일
    py -3 check_task_brief.py <brief.md>          # Windows
    cat brief.md | python3 check_task_brief.py    # stdin
    python3 check_task_brief.py <brief.md> --json  # 기계 판독

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

# 브리프는 1장 — 길면 SPEC 후보(feedback-triage 로 핸드오프). soft 경고만.
BRIEF_SOFT_LIMIT = 2000

# 섹션 키워드 → 정규 섹션 id
# INTENT(의도)는 선택 섹션 — hard 검사(C1~C5) 대상이 아니지만, 파서가 인식해야
# 그 내용이 인접 hard 섹션으로 새어(bleed) 들어가 오탐을 만들지 않는다(#1080).
SECTION_KEYWORDS = {
    "INTENT": ["의도", "배경", "intent", "background", "context", "why"],
    "TASK": ["작업", "목표", "task", "goal"],
    "SCOPE": ["범위", "스코프", "scope", "sandbox", "샌드박스"],
    "VERIFY": ["검증방법", "검증 방법", "검증", "verify", "verification", "검사"],
    "DONE": ["완료정의", "완료 정의", "완료", "완료조건", "done", "definition of done", "dod"],
    "BUDGET": ["예산", "budget", "한도", "제약"],
}
REQUIRED_SECTIONS = ["TASK", "SCOPE", "VERIFY", "DONE"]

# 검증가능 토큰: 비교 연산자 · exit code · 파일존재 · 개수 · 상태 · 인라인 코드(명령/경로)
_OP = r"(>=|<=|==|!=|>|<|≥|≤)"
VERIFIABLE_PATTERNS = [
    re.compile(_OP),
    re.compile(r"\bexit\b|종료코드|return\s*code|returncode|exit\s*code", re.I),
    re.compile(r"존재|exists?|파일|경로|\.json\b|\.md\b|\.txt\b|\.csv\b|\.go\b|\.py\b|\.ts\b|/", re.I),
    re.compile(r"\b\d+\s*(건|개|줄|라인|회|%|초|ms|s|턴|turns?|tokens?|k)\b", re.I),
    re.compile(r"\bpass(ed)?\b|\bgreen\b|clean\b|merged\b|push|추가됨|갱신됨|생성됨", re.I),
    re.compile(r"`[^`]+`"),  # 인라인 코드 = 재현 가능한 명령·경로
]

# 자기보고 어휘 — 검증 방법이 '재현 명령'이 아니라 '작성자의 주장'인 신호.
# 검증 섹션에서만 hard 로 잡는다("확인했다" 자체가 금지, 명령·파일·수치로 치환).
SELF_REPORT_TERMS = [
    "확인했", "확인함", "확인 완료", "확인완료", "체크했", "체크함",
    "테스트해봤", "테스트했", "테스트함", "돌려봤", "돌려보았", "돌려봄",
    "동작 확인", "동작확인", "정상 동작", "정상동작", "정상 작동", "정상작동",
    "잘 됨", "잘됨", "잘 된다", "잘된다", "잘 돌아", "잘 동작", "잘 나온다", "잘 나옴",
    "문제 없", "문제없", "이상 없", "이상없", "이상무",
    "육안", "눈으로", "보면 됨", "보면 된다", "확인하면 됨", "확인하면 된다",
    "looks good", "works fine", "seems to work", "should work",
    "verified manually", "checked manually", "i tested", "i checked", "i verified",
    "manually verified", "manually tested",
]

# 형용사·부사(모호어) 블랙리스트 — 판정 불가능한 주관 서술.
# 주의: "clean"(git status clean·상태 토큰)은 제외.
VAGUE_TERMS = [
    "깔끔", "적절", "충분", "제대로", "빠르게", "빠른", "신속",
    "좋게", "좋은", "완벽", "원활", "안정적", "효율", "최적", "간결",
    "대략", "어느 정도", "어느정도", "최대한", "가능한 한", "가능한한",
    "매끄럽", "튼튼", "견고", "유연", "훌륭", "우수", "양호", "깨끗하게",
    "properly", "cleanly", "nicely", "robust", "efficient",
    "appropriately", "sufficiently", "smoothly", "better",
]
# "잘"·"well"·"good" 은 단어 경계로만(오탐 방지)
VAGUE_REGEX = [re.compile(r"(^|\s)잘(\s|$)"), re.compile(r"\bwell\b", re.I), re.compile(r"\bgood\b", re.I)]

# 범위 sandbox 경계: '포함'(건드릴 것) + '제외'(건드리지 말 것)
SCOPE_IN = re.compile(r"포함|허용|건드[릴린]|touch|include|in[- ]?scope|대상", re.I)
SCOPE_OUT = re.compile(r"제외|비범위|건드리지|금지|except|exclude|out[- ]?of[- ]?scope|미대상|안\s*건드", re.I)

# 완료 정의의 "상태" 토큰(동사형 종료 배제용)
STATE_TOKENS = re.compile(
    r"됨|완료|clean|exists?|존재|==|\bpass|\b0\s*건|merged|push|green|갱신|커밋됨|생성됨|추가됨|no\b", re.I
)

_MD_HEADING = re.compile(r"^#{1,6}\s*(.+?)\s*$")


def _match_keyword(text: str):
    """text 앞부분이 섹션 키워드와 일치하면 섹션 id 반환."""
    low = text.strip().lower()
    # 긴 키워드 우선(예: "검증방법"이 "검증"보다 먼저 매칭되게)
    best = None
    best_len = -1
    for sid, kws in SECTION_KEYWORDS.items():
        for kw in kws:
            if low.startswith(kw) and len(kw) > best_len:
                best = sid
                best_len = len(kw)
    return best


def parse_sections(raw: str):
    """텍스트를 {section_id: [content_line, ...]} 로 파싱."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        header_sid = None
        inline = None
        # 1) markdown heading 형태: `## 검증 방법`
        mh = _MD_HEADING.match(stripped)
        if mh and line.lstrip().startswith("#"):
            header_sid = _match_keyword(mh.group(1))
        # 2) label 형태: `범위: ...`
        if header_sid is None:
            ml = re.match(r"^([^:：]{1,20})[:：]\s*(.*)$", stripped)
            if ml:
                sid = _match_keyword(ml.group(1))
                if sid:
                    header_sid = sid
                    inline = ml.group(2).strip()
        if header_sid:
            current = header_sid
            sections.setdefault(current, [])
            if inline:
                sections[current].append(inline)
            continue
        if current:
            # 불릿 마커 제거
            sections[current].append(re.sub(r"^[-*•]\s*", "", stripped))
    return sections


def _is_verifiable(line: str) -> bool:
    return any(p.search(line) for p in VERIFIABLE_PATTERNS)


def _self_report_hits(text: str):
    hits = []
    low = text.lower()
    for term in SELF_REPORT_TERMS:
        if term.lower() in low:
            hits.append(term)
    return hits


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
    sections = parse_sections(raw)
    checks = []  # (id, name, ok, detail, severity)

    def add(cid, name, ok, detail, severity="hard"):
        checks.append({"id": cid, "name": name, "ok": ok, "detail": detail, "severity": severity})

    # C1 필수 섹션 존재(작업·범위·검증·완료)
    missing = [s for s in REQUIRED_SECTIONS if s not in sections or not sections[s]]
    label = {"TASK": "작업", "SCOPE": "범위", "VERIFY": "검증방법", "DONE": "완료정의"}
    add("C1", "필수 섹션 존재(작업·범위·검증방법·완료정의)", not missing,
        "누락/빈 섹션: " + ", ".join(label[s] for s in missing) if missing else "OK")

    # C2 범위 sandbox 경계: 포함 + 제외 둘 다
    scope_text = "\n".join(sections.get("SCOPE", []))
    has_in = bool(SCOPE_IN.search(scope_text))
    has_out = bool(SCOPE_OUT.search(scope_text))
    add("C2", "범위에 포함(sandbox) + 제외(비범위) 경계 명시", has_in and has_out,
        f"포함={has_in}, 제외={has_out} (제외 없으면 무한 sandbox — 에이전트가 인접 파일까지 헤맴)")

    # C3 검증 = 재현 명령·파일·수치 (자기보고 금지)
    # 섹션 부재/공백이면 "검사 대상 0"의 공허한 통과(vacuous pass)가 되므로
    # OK 가 아니라 판정 불가 FAIL 로 표시한다(#1083 — 축별 보강 질문의 근거 보존).
    verify_lines = sections.get("VERIFY", [])
    if not verify_lines:
        add("C3", "검증 방법이 재현 명령·파일·수치 (자기보고 금지)", False,
            "판정 불가 — 검증방법 섹션 부재/공백 (재현 명령·파일·수치로 채워야 함)")
    else:
        verify_text = "\n".join(verify_lines)
        unverifiable = [ln for ln in verify_lines if not _is_verifiable(ln)]
        self_report = _self_report_hits(verify_text)
        c3_ok = not unverifiable and not self_report
        detail_parts = []
        if unverifiable:
            detail_parts.append("검증불가 줄(명령·파일·수치 없음):\n    " + "\n    ".join(unverifiable))
        if self_report:
            detail_parts.append("자기보고 어휘(재현 명령으로 치환): " + ", ".join(sorted(set(self_report))))
        add("C3", "검증 방법이 재현 명령·파일·수치 (자기보고 금지)", c3_ok,
            "\n".join(detail_parts) if detail_parts else "OK")

    # C4 완료 정의 = 관측 가능 상태(동사형 종료 배제)
    done_text = "\n".join(sections.get("DONE", []))
    has_state = bool(STATE_TOKENS.search(done_text))
    add("C4", "완료 정의가 '작업'이 아닌 '관측 가능한 상태'", has_state,
        "상태 토큰(됨/clean/exists/pass/0건/커밋됨 등) 필요" if not has_state else "OK")

    # C5 형용사·부사 금지 (작업·범위·검증·완료)
    # 4개 hard 섹션이 전부 비면(헤딩 없는 생짜 초안) 섹션 스캔이 공허해지므로
    # 원문 전체를 스캔해 실제 모호어를 지목하고 판정 불가 FAIL 로 표시한다(#1083).
    # 섹션이 하나라도 있으면 기존 동작 유지 — 인사말 등 미배정 서두의 오탐을 막는다.
    hard_all_empty = all(not sections.get(s) for s in ("TASK", "SCOPE", "VERIFY", "DONE"))
    if hard_all_empty:
        vh = _vague_hits(raw)
        detail = "판정 불가 — 섹션 미구성(원문 전체 스캔)"
        if vh:
            detail += ", 모호어: " + ", ".join(sorted(set(vh)))
        add("C5", "형용사·부사(모호어) 0 (작업·범위·검증·완료)", False, detail)
    else:
        hard_text = "\n".join(
            "\n".join(sections.get(s, [])) for s in ("TASK", "SCOPE", "VERIFY", "DONE")
        )
        vh = _vague_hits(hard_text)
        add("C5", "형용사·부사(모호어) 0 (작업·범위·검증·완료)", not vh,
            "모호어: " + ", ".join(sorted(set(vh))) if vh else "OK")

    # W1 예산 섹션 권장(경고만)
    if "BUDGET" not in sections or not sections.get("BUDGET"):
        add("W1", "예산(질문 허용·토큰·시간) 섹션 권장", False,
            "선택 항목 — 에이전트 폭주 방지에 유용(예: 질문 허용 2회, 토큰 상한 200k)", severity="warn")

    # W2 브리프 길이 근접 — 길면 SPEC 후보
    n = len(raw)
    if n > BRIEF_SOFT_LIMIT:
        add("W2", "브리프 1장 초과 — SPEC 후보 신호", False,
            f"{n}자 (>{BRIEF_SOFT_LIMIT}). 요청이 크면 feedback-triage/신규 기획 워크플로우로 핸드오프 검토",
            severity="warn")

    hard = [c for c in checks if c["severity"] == "hard"]
    passed = sum(1 for c in hard if c["ok"])
    ok = all(c["ok"] for c in hard)
    return {
        "ok": ok,
        "score": f"{passed}/{len(hard)}",
        "checks": checks,
        "sections_found": sorted(sections.keys()),
        "length": n,
    }


def render_human(result) -> str:
    lines = []
    lines.append(f"task-brief 구조 게이트 — {'PASS ✅' if result['ok'] else 'FAIL ❌'}  ({result['score']} hard)")
    lines.append("")
    for c in result["checks"]:
        if c["severity"] == "warn":
            mark = "⚠️ "
        else:
            mark = "✅" if c["ok"] else "❌"
        lines.append(f"{mark} {c['id']} {c['name']}")
        if not c["ok"] or c["severity"] == "warn":
            for d in str(c["detail"]).splitlines():
                lines.append(f"      {d}")
    if not result["ok"]:
        lines.append("")
        lines.append("→ 실패 축마다 구체 보강 질문을 만들어 사용자에게 되묻는다. 검증은 명령·파일·수치로.")
    return "\n".join(lines)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
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

    result = evaluate(raw)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
