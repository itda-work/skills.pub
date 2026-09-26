"""trust.py — 협찬 거품 필터 (REQ-007/022).

신뢰 엔진의 validation 단계. 발굴(블로그·인스타)은 협찬·체험단으로 오염되지만,
*검색량은 협찬으로 부풀리기 어렵다*. 따라서 `블로그수 / 월검색량` 비율이
협찬 오염도의 정량 지표다(§8.9 PoC#3).

거품 판정(REQ-007): 비율 > ~200 AND 절대 검색량 < floor.
  - 비율 과대 + 검색 미달 = 체험단이 도배하나 아무도 그 문구로 검색 안 함(감성/인생샷/분위기좋은 카페).
  - 비율 낮음 = 검색이 블로그를 따라옴 = organic 실수요(카페루시아 0.4).
  - 비율 높아도 절대 검색량이 많으면 거품 아님(실수요가 협찬을 정당화).

블로그는 *거품 탐지기*일 뿐 발굴 소스가 아니다(REQ-022). 최신순 블로그는
협찬/스팸 오염으로 cold 신상 발굴에 부적합.
"""
from __future__ import annotations

import math

# 튜닝 가능 임계 (PoC 잠정값 — OQ 잔여)
BLOG_RATIO_BUBBLE = 200.0  # 블로그/검색 비율 거품 임계
SEARCH_FLOOR = 1000        # 거품 판정용 절대 월검색량 floor (surge.VOL_FLOOR와 정렬)

# 거품으로 판정된 후보의 랭킹 강등 penalty(REQ-007). main.py가 순위 점수에서 차감.
_BUBBLE_PENALTY = 100.0


def bubble_ratio(blog_total: float, monthly_vol: float) -> float:
    """블로그수 / 월검색량. 검색량 0이면 inf(검색 결측 = 극단 거품 신호)."""
    if monthly_vol <= 0:
        return math.inf if blog_total > 0 else 0.0
    return blog_total / monthly_vol


def assess(
    blog_total: float,
    monthly_vol: float,
    *,
    ratio_threshold: float = BLOG_RATIO_BUBBLE,
    search_floor: float = SEARCH_FLOOR,
) -> dict:
    """협찬 거품 여부를 판정한다.

    Args:
        blog_total: 네이버 블로그 검색 총건수(협찬 도배 지표).
        monthly_vol: SearchAd 절대 월검색량(실수요 지표).

    Returns:
        dict {is_bubble, ratio, penalty, reason}.
        is_bubble=True → 비율 과대 AND 절대검색 미달(REQ-007).
        penalty: 거품이면 강등 점수(>0), organic이면 0.
    """
    ratio = bubble_ratio(blog_total, monthly_vol)
    is_bubble = ratio > ratio_threshold and monthly_vol < search_floor

    ratio_disp = "inf" if ratio == math.inf else f"{ratio:.1f}"
    if is_bubble:
        reason = (
            f"협찬 거품 의심 — 블로그/검색 비율 {ratio_disp}>{ratio_threshold:.0f} "
            f"+ 월검색 {int(monthly_vol)}<{int(search_floor)}(체험단 도배·실검색 부재) → 강등"
        )
        penalty = _BUBBLE_PENALTY
    else:
        if monthly_vol >= search_floor:
            reason = f"실수요 — 월검색 {int(monthly_vol)}≥{int(search_floor)}(검색이 블로그를 따라옴, 비율 {ratio_disp})"
        else:
            reason = f"organic — 블로그/검색 비율 {ratio_disp}≤{ratio_threshold:.0f}(협찬 도배 신호 약함)"
        penalty = 0.0

    return {"is_bubble": is_bubble, "ratio": ratio, "penalty": penalty, "reason": reason}
