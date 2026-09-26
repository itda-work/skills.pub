"""추론 양심 게이트 (SPEC-DATA-VERTICAL-001 REQ-040).

Codex 강조: 추론 보고는 `decision_interview_id + gate_verdict + verification_result`
없이는 **생성 불가**해야 한다(advisor 5관문 양심을 ask 안에서 희석하지 않게 코드로 강제).
서술 경로(QueryPlan)와 분리된 상태기계의 종착 가드.
"""
from __future__ import annotations


def sample_sufficiency(n_rows: int, n_variables: int) -> dict:
    """변수당 표본으로 방법 타당성 판정 (advisor method_gate 계승).

    변수당 N<10 → rejected, 10~20 → gray_zone, >=20 → clean.
    """
    if n_variables <= 0:
        return {"passed": True, "status": "clean", "reason": "예측 변수 없음"}
    per = n_rows / n_variables
    if per < 10:
        return {"passed": False, "status": "rejected", "reason": f"변수당 표본 {per:.1f} (<10) — 회귀 신뢰 불가"}
    if per < 20:
        return {"passed": False, "status": "gray_zone", "reason": f"변수당 표본 {per:.1f} (10~20) — EDA 우선 권고"}
    return {"passed": True, "status": "clean", "reason": f"변수당 표본 {per:.1f} (>=20)"}


def method_gate(n_rows: int, predictors: list, multicollinearity_result: dict | None = None) -> dict:
    """방법 게이트 = 표본 충분성 + 다중공선성 (advisor 5관문 조건 합성).

    추론 보고의 gate_verdict 로 사용한다. 하나라도 걸리면 passed=False.
    """
    suff = sample_sufficiency(n_rows, len(predictors) + 1)  # +1: 결과 변수
    if not suff["passed"]:
        return suff
    mc = multicollinearity_result or {}
    if mc.get("detected"):
        return {"passed": False, "status": "rejected",
                "reason": f"다중공선성 검출({mc.get('reason', '')}) — 변수 정리 후 재시도"}
    return {"passed": True, "status": "clean",
            "reason": f"{suff['reason']}, 다중공선성 미검출"}


def build_inferential_report(evidence: dict, finding: str) -> str:
    """양심 증거가 갖춰진 경우에만 추론 보고를 생성한다.

    - decision_interview_id 없음 → 생성 불가(ValueError)
    - gate_verdict 없음 → 생성 불가(ValueError)
    - gate_verdict.passed == False → [거부] 보고(서술/EDA 대안) 반환
    - passed 인데 verification_result 없음 → 생성 불가(ValueError)
    """
    if not evidence.get("decision_interview_id"):
        raise ValueError("추론 보고 생성 불가 — 결정 인터뷰 미완(decision_interview_id 없음)")
    verdict = evidence.get("gate_verdict")
    if not verdict:
        raise ValueError("추론 보고 생성 불가 — 방법 게이트 판정 없음(gate_verdict 없음)")
    if not verdict.get("passed"):
        return f"[거부] {verdict.get('reason', '기법 부적합')} — 추론 대신 서술/EDA 를 권합니다."
    ver = evidence.get("verification_result")
    if not ver:
        raise ValueError("추론 보고 생성 불가 — 독립 재현 검증 없음(verification_result 없음)")
    note = "" if ver.get("reproduced") else "  ⚠️ 독립 재현 불일치 — 수치 신뢰에 주의"
    return f"[채택] {finding}{note}\n이 분석으로 내리는 결정: {evidence['decision_interview_id']}"
