"""reliability_rules.py — 신뢰성 검수 코어 5규칙 (타깃 비종속 엔진).

회의·전표·통제 어느 타깃이든 공유하는 결정론 verifier 모음.
각 verifier는 (rows, turns)를 받아 위반(Violation) 리스트를 반환한다(빈 리스트=통과).
SKILL.md prose 경고가 아니라 코드로 규칙을 강제한다(gate-enforcement).

정직성 주의 — 2층 방어:
  1) 본 모듈의 verifier = 일반 메커니즘(근거-주장 정합·날짜 실재·잡담 마커)을 결정론 검사.
  2) fixture 특화 골든 단언("출시 담당 미단정"·"패키지 결정권자=대표")은
     test_golden_meeting.py가 추가로 못박는다.
verifier는 "근거 없는 단정"은 잡지만, 같은 근거 발화 안의 의미 전이(품질점검↔출시)까지는
구분하지 못한다 — 그 경계는 골든 단언이 담당한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from meeting_adapter import Turn, full_text

# ── 마커 상수 ──────────────────────────────────────────────
CHITCHAT_MARKERS = [
    "점심", "구내식당", "김밥", "메뉴", "회의실 예약", "회의실",
    "수고하셨", "수고하세요", "수고하십",
]
# 안건 명사 — 잡담 마커가 있어도 이 중 하나가 있으면 '순수 잡담'이 아니다.
# (예: 마감 발화 "다음 회의는 … 수고하셨어요"는 안건 발화 — 잡담 아님)
AGENDA_NOUNS = [
    "출시", "예산", "광고", "교육", "패키지", "사은품", "발주", "품질",
    "배분", "증액", "미정", "확정", "결정", "안건", "마무리", "다음 회의",
    "경쟁사", "원가", "시안", "수량",
]
ASSIGN_MARKERS = [
    "걸로 합시다", "해주세요", "해 주세요", "만들어", "준비", "조율", "정해오",
    "파악", "가져와", "알아볼", "드릴", "공유", "완료하는", "증액으로 가고",
    "진행하겠", "하겠습니다", "할게요", "드리겠",
]
DECIDER_MARKERS = ["검토", "보고 후에 정", "보고 후", "정합시다", "결재", "승인"]

_ISO_DATE = re.compile(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}")
_KO_DATE = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일")
_TITLE_OWNER = re.compile(
    r".+(?:과장|차장|부장|팀장|대리|사원|주임|선임|책임|수석|이사|상무|전무|사장|본부장|실장)$"
)

# ── Violation 코드 ────────────────────────────────────────
EVIDENCE_MISSING = "EVIDENCE_MISSING"
CHITCHAT = "CHITCHAT"
INVENTED_DATE = "INVENTED_DATE"
OWNER_FABRICATED = "OWNER_FABRICATED"
DECISION_ACTION_MERGED = "DECISION_ACTION_MERGED"

# ★ must-pass (selfcheck FAIL 트리거)
MUST_PASS_CODES = frozenset(
    {EVIDENCE_MISSING, CHITCHAT, INVENTED_DATE, OWNER_FABRICATED, DECISION_ACTION_MERGED}
)


@dataclass
class Row:
    """신뢰성 검수 표의 한 행(구조화 결과 SSoT)."""

    item: str
    category: str  # 결정 | 실무 | 리스크
    status: str  # 확정 | 미정 | 확인필요
    owner: str | None = None
    due: str | None = None
    evidence: list[int] = field(default_factory=list)
    basis: str = ""
    risk_note: str | None = None


@dataclass
class Violation:
    code: str
    row_item: str
    detail: str


# ── 헬퍼 ──────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _is_unasserted_owner(owner: str | None) -> bool:
    if owner is None:
        return True
    return ("미지정" in owner) or ("확인" in owner) or (owner.strip() == "")


def _is_specific_owner(owner: str | None) -> bool:
    """특정 담당(사람/팀)으로 단정된 owner인지. 미지정·확인필요·None은 False."""
    if _is_unasserted_owner(owner):
        return False
    if owner == "대표":
        return True
    if owner.endswith("팀"):
        return True
    return bool(_TITLE_OWNER.match(owner))


def _owner_token(owner: str) -> str:
    return re.sub(r"\(.*?\)", "", owner).strip()


def _has(text: str, markers: list[str]) -> bool:
    return any(m in text for m in markers)


def _is_chitchat_turn(t: Turn) -> bool:
    return _has(t.text, CHITCHAT_MARKERS)


def _is_pure_chitchat_turn(t: Turn) -> bool:
    """순수 잡담 발화 — 잡담 마커가 있고 안건 명사는 없는 발화.

    혼합 발화(안건 + 끝인사)는 잡담으로 보지 않는다.
    """
    return _is_chitchat_turn(t) and not _has(t.text, AGENDA_NOUNS)


# ── verifier (코어 5규칙) ─────────────────────────────────
def verify_evidence_exists(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    """R1/AC-9 — 각 행은 실재하는 발화 인덱스를 1개 이상 가리켜야 한다."""
    out: list[Violation] = []
    n = len(turns)
    for r in rows:
        if not r.evidence:
            out.append(Violation(EVIDENCE_MISSING, r.item, "근거 발화 인덱스가 비어 있음"))
            continue
        bad = [i for i in r.evidence if i < 0 or i >= n]
        if bad:
            out.append(Violation(EVIDENCE_MISSING, r.item, f"존재하지 않는 발화 인덱스 {bad}"))
    return out


def verify_no_chitchat(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    """AC-3 — 잡담(점심·회의실 예약 등)을 항목으로 넣지 않는다."""
    out: list[Violation] = []
    n = len(turns)
    for r in rows:
        if _has(r.item, CHITCHAT_MARKERS):
            out.append(Violation(CHITCHAT, r.item, "항목명이 잡담 마커를 포함"))
            continue
        ev = [i for i in r.evidence if 0 <= i < n]
        if ev and all(_is_pure_chitchat_turn(turns[i]) for i in ev):
            out.append(Violation(CHITCHAT, r.item, "근거가 잡담 발화로만 구성"))
    return out


def verify_no_invented_date(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    """AC-4 — 원문에 없는 캘린더 날짜를 추정해 채우지 않는다.

    상대표현('다음 주까지' 등)은 날짜 정규식에 안 걸려 보존 허용.
    """
    out: list[Violation] = []
    src = _norm(full_text(turns))
    for r in rows:
        for val in (r.item, r.status, r.due):
            if not val:
                continue
            for m in _ISO_DATE.findall(val) + _KO_DATE.findall(val):
                if _norm(m) not in src:
                    out.append(Violation(INVENTED_DATE, r.item, f"원문에 없는 날짜 '{m}'"))
    return out


def verify_owner_not_fabricated(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    """AC-1/R1 — 특정 담당 단정 행은 근거 발화에 배정/자임 증거가 있어야 한다.

    배정 증거 = 근거 발화 중 (담당명이 본문 등장 OR 발화자==담당) AND 배정 마커 동반.
    증거 없는 단정 = 환각 → FAIL.
    """
    out: list[Violation] = []
    n = len(turns)
    for r in rows:
        if not _is_specific_owner(r.owner):
            continue
        owner = r.owner or ""
        token = _owner_token(owner)
        ev = [i for i in r.evidence if 0 <= i < n]
        ok = False
        for i in ev:
            t = turns[i]
            if owner == "대표":
                if ("대표" in t.text) and _has(t.text, DECIDER_MARKERS):
                    ok = True
                    break
                continue
            named = bool(token) and (token in t.text)
            same = (t.speaker == owner) or (bool(token) and t.speaker == token)
            if (named or same) and _has(t.text, ASSIGN_MARKERS):
                ok = True
                break
        if not ok:
            out.append(Violation(OWNER_FABRICATED, r.item, f"담당 '{owner}' 단정에 배정 근거 없음"))
    return out


def verify_decision_action_split(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    """AC-5 — 결정(보류/미정)과 후속 실무를 한 행에 뭉치지 않는다.

    탐지: category=결정 & status∈{미정,보류} & owner=특정 실무자(대표 제외) & due 존재
         → 결정-대기 행에 실행 담당+기한이 섞임 = 병합 스멜.
    """
    out: list[Violation] = []
    for r in rows:
        if r.category != "결정":
            continue
        if r.status not in ("미정", "보류"):
            continue
        if r.owner == "대표" or not _is_specific_owner(r.owner):
            continue
        if r.due:
            out.append(Violation(DECISION_ACTION_MERGED, r.item, "결정-보류 행에 실행 담당+기한이 병합됨"))
    return out


ALL_VERIFIERS = [
    verify_evidence_exists,
    verify_no_chitchat,
    verify_no_invented_date,
    verify_owner_not_fabricated,
    verify_decision_action_split,
]


def run_all_verifiers(rows: list[Row], turns: list[Turn]) -> list[Violation]:
    out: list[Violation] = []
    for v in ALL_VERIFIERS:
        out.extend(v(rows, turns))
    return out


def rows_from_dicts(data: list[dict]) -> list[Row]:
    """JSON dict 리스트 → Row 리스트."""
    return [Row(**d) for d in data]
