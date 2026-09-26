"""selfcheck.py — 산출 표 ↔ 원문 대조 게이트.

SKILL.md가 산출 직후 호출하는 강제 게이트. must-pass(★) 위반이 하나라도
있으면 ok=False → 에이전트는 재작성(상한 MAX_REWRITES회, /investigate Iron Law 차용).
초과 시 자동 보정 대신 사람 검토 플래그로 멈춘다(추정 채움 금지).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from meeting_adapter import Turn, load_transcript
from reliability_rules import (
    MUST_PASS_CODES,
    Row,
    Violation,
    rows_from_dicts,
    run_all_verifiers,
)

MAX_REWRITES = 3  # 게이트 FAIL 시 재작성 루프 상한 (초과 → 사람 검토 플래그)


@dataclass
class SelfCheckResult:
    ok: bool
    violations: list[Violation]
    must_pass_failed: list[Violation]

    def summary(self) -> str:
        if self.ok:
            warns = [v for v in self.violations if v not in self.must_pass_failed]
            tail = f" (warn {len(warns)}건)" if warns else ""
            return f"PASS — must-pass 위반 0건{tail}"
        lines = [f"FAIL — must-pass 위반 {len(self.must_pass_failed)}건:"]
        for v in self.must_pass_failed:
            lines.append(f"  [{v.code}] {v.row_item} — {v.detail}")
        for v in self.violations:
            if v not in self.must_pass_failed:
                lines.append(f"  (warn)[{v.code}] {v.row_item} — {v.detail}")
        return "\n".join(lines)


def selfcheck(rows: list[Row], turns: list[Turn]) -> SelfCheckResult:
    violations = run_all_verifiers(rows, turns)
    must = [v for v in violations if v.code in MUST_PASS_CODES]
    return SelfCheckResult(ok=not must, violations=violations, must_pass_failed=must)


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python selfcheck.py <result.json> <transcript.md>", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    rows = rows_from_dicts(data["rows"] if isinstance(data, dict) else data)
    turns = load_transcript(argv[1])
    res = selfcheck(rows, turns)
    print(res.summary())
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
