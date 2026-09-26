"""진단 카드 + 확인 요청 (SPEC-DATA-VERTICAL-001 REQ-050).

[HARD] 단정 금지 — "[가설]", "~로 보입니다", "맞나요?" 형태 유지.
"""
from __future__ import annotations


def render_card(diagnosis: dict) -> str:
    if diagnosis.get("status") != "diagnosed":
        return f"진단 불가: {diagnosis.get('reason', '')}"
    lines = ["[진단 결과 — 아래는 모두 가설입니다]"]
    lines.append(f"- 헤더는 {diagnosis['header_row']}행으로 보입니다 → {diagnosis['header_hypothesis']}")
    if diagnosis["subtotal_rows"]:
        lines.append(f"- 소계/빈 행으로 보이는 행(제거 후보): {diagnosis['subtotal_rows']}")
    if diagnosis["empty_columns"]:
        lines.append(f"- 빈 열로 보이는 열(제거 후보): {diagnosis['empty_columns']}")
    for mc in diagnosis.get("mixed_type_columns", []):
        lines.append(
            f"- {mc['col']}열은 대부분 숫자(약 {int(mc['num_ratio'] * 100)}%)인데 "
            f"텍스트가 섞여 보입니다(예: {mc['text_samples']}) — 확인이 필요합니다"
        )
    return "\n".join(lines)


def render_confirm(diagnosis: dict) -> str:
    return "위 [가설]대로 정돈본을 새 파일로 만들까요? 틀린 부분이 있으면 알려주세요. (원본은 그대로 둡니다)"
