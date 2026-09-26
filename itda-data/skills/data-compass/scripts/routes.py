"""분석 경로(행선지) 추천 — 프로파일 → 결정론 경로 목록.

data-compass 의 "갈 수 있는 길" 생성기. 각 경로는 담당 스킬과
복붙 가능한 한국어 지시문(say)을 함께 든다 — 유저는 지시문을 그대로
말하거나 변형해 여정을 진행한다(순수 코치: 여기서 실행하지 않는다).

관심사(interest)가 주어지면 토큰이 닿는 컬럼·경로를 앞으로 올린다.
같은 (프로파일, 관심사) → 같은 경로 목록(강의 재현성).
"""
from __future__ import annotations

import re

MAX_ROUTES = 6

_SPLIT = re.compile(r"[\s,·/]+")


def _tokens(interest: str) -> list[str]:
    return [t for t in _SPLIT.split(interest.strip()) if t] if interest else []


def _promote(names: list[str], tokens: list[str]) -> list[str]:
    """관심사 토큰이 닿는 컬럼을 앞으로(안정 정렬 — 원래 순서 보존)."""
    if not tokens:
        return names
    return sorted(names, key=lambda n: 0 if any(t in n for t in tokens) else 1)


def build_routes(profile: dict, interest: str = "") -> list[dict]:
    tokens = _tokens(interest)
    cols = profile["columns"]
    # id/pii 는 집계 축에서 제외(data-ask 와 동일 양심)
    measures = _promote([c["name"] for c in cols if c["role"] == "measure"], tokens)
    dims = _promote([c["name"] for c in cols if c["role"] == "dimension"], tokens)
    dates = [c["name"] for c in cols if c["role"] == "date"]
    totals = [c["name"] for c in cols if c.get("totalsish")]
    routes: list[dict] = []

    if profile.get("needs_prep"):
        q = profile.get("quality", {})
        why = " · ".join(q.get("header_issues", []) + (
            [f"열 개수가 안 맞는 행 {q['ragged_rows']}건"] if q.get("ragged_rows") else []
        ) + ([f"숫자에 텍스트 섞임: {', '.join(q['mixed_numeric'])}"] if q.get("mixed_numeric") else []))
        routes.append({
            "stage": "정돈", "skill": "data-prep",
            "title": "먼저 데이터를 정돈합니다",
            "why": why or "구조 결함이 감지되었습니다",
            "say": f"{profile['file']} 파일 정리해줘. 진단부터 보여줘",
        })

    if dims and measures:
        routes.append({
            "stage": "탐색", "skill": "data-ask",
            "title": f"{dims[0]} 기준으로 {measures[0]}을(를) 갈라 봅니다",
            "why": "어디에서 값이 큰지/작은지가 첫 지형 감각입니다",
            "say": f"{dims[0]}별 {measures[0]} 합계와 평균 알려줘",
        })
    if dates and measures:
        routes.append({
            "stage": "추이", "skill": "data-ask",
            "title": f"시간 흐름에서 {measures[0]} 변화를 봅니다",
            "why": "추이를 알면 이상 구간(급증·급감)이 눈에 띕니다",
            "say": f"월별 {measures[0]} 추이 보여줘",
        })
    if dims:
        routes.append({
            "stage": "탐색", "skill": "data-ask",
            "title": f"{dims[0]} 값이 어떻게 분포하는지 봅니다",
            "why": "값별 건수는 데이터의 몸통이 어디인지 알려줍니다",
            "say": f"{dims[0]} 값별 건수 분포 알려줘",
        })
    if measures:
        routes.append({
            "stage": "탐색", "skill": "data-ask",
            "title": f"{measures[0]} 상위 건을 봅니다",
            "why": "극단값 몇 건이 전체 그림을 왜곡할 수 있습니다",
            "say": f"{measures[0]} 상위 10건 보여줘",
        })
    if totals:
        routes.append({
            "stage": "검증", "skill": "data-verify",
            "title": "합계·총계가 실제로 맞는지 검산합니다",
            "why": f"합계성 컬럼({', '.join(totals)})은 어긋나 있기 일쑤입니다",
            "say": "합계 검산해줘. 부분합이랑 총계 맞는지 봐줘",
        })
    routes.append({
        "stage": "보고", "skill": "data-compass",
        "title": "여정을 한 페이지 보고로 정리합니다",
        "why": "분석은 남에게 설명할 수 있어야 끝난 것입니다",
        "say": "지금까지 알아낸 것들을 분석 지도 기준으로 한 페이지로 정리해줘",
    })

    if tokens:  # 관심사가 닿는 경로를 앞으로 — 단 정돈은 맨 앞, 보고는 맨 뒤 고정
        def score(r: dict) -> int:  # (지저분한 데이터는 언제나 정돈이 첫 걸음이다)
            text = r["title"] + r["say"]
            return 0 if any(t in text for t in tokens) else 1
        head = [r for r in routes if r["stage"] == "정돈"]
        tail = [r for r in routes if r["stage"] == "보고"]
        mid = sorted((r for r in routes if r["stage"] not in ("정돈", "보고")), key=score)
        routes = head + mid + tail

    return routes[:MAX_ROUTES]


def recommend(routes: list[dict], k: int = 3) -> list[dict]:
    """§3 행선지 추천 — 여정 시작 시 [보고] 는 추천하지 않는다(경로 목록에는 남는다)."""
    picks = [r for r in routes if r["stage"] != "보고"][:k]
    return picks or routes[:k]
