"""surge.py — 3레인 trend 분류기 (REQ-001/014/017/018/019).

thesis: 유행 = 평점(레벨)이 아니라 *관심의 미분(velocity)*. 데이터랩 검색트렌드
시계열을 입력으로 baseline 대비 recent 윈도의 상승을 측정한다.

단일 임계는 전부 오판한다(§8.6). 3 직교 신호를 분리한 3레인 분류기:
  (a) 신규출현    — 시리즈 < ~26주(전년 데이터 無) + 막주 상승
  (b) 검증상승    — 카테고리 상대 YoY ≥ ~2 + z ≥ 1.0 + 막주 비붕괴
  (c) 미디어스파이크 — 인물/방송 토큰 + 급등(지속성 약하면 별도 표기)

★ 모든 레인은 magnitude floor(절대 검색량·baseline 평균)를 선통과해야 한다
  (REQ-014/§8.11 PoC#5). floor가 없으면 [0,0,0,0] 노이즈가 "신규출현"으로
  1위를 차지하는 버그가 재발한다.

임계 상수(~26주/~2/~1.0/~1000/~5/~56주)는 PoC 잠정값이며 튜닝 여지가 있다(OQ-1 잔여).
"""
from __future__ import annotations

import statistics

# ---------------------------------------------------------------------------
# 튜닝 가능 임계 상수 (PoC 잠정값 — OQ-1 잔여)
# ---------------------------------------------------------------------------
RECENT_WINDOW = 4          # recent 윈도(주)
NEW_SERIES_MAX_WEEKS = 26  # 이 미만 = 전년 데이터 無 = 신상 출현 신호
RELATIVE_YOY_MIN = 2.0     # 검증상승 카테고리 상대 YoY 하한
Z_MIN = 1.0                # 검증상승 z-score 하한
VOL_FLOOR = 1000           # 전레인 절대 월검색량 floor (SearchAd)
BASELINE_FLOOR = 5.0       # 전레인 데이터랩 baseline 평균 floor
YOY_MIN_WEEKS = 56         # YoY 계산 최소 시리즈 길이(≥17개월, 52+4)
MOMENTUM_COLLAPSE_RATIO = 0.5  # 막주 < 직전평균 × 이 비율 → 붕괴

_WEEKS_PER_YEAR = 52
_EPS = 1e-9
_Z_FLAT_JUMP = 10.0  # 평탄 baseline에서 급등 시 z 강신호 sentinel

# 미디어 레인 토큰(REQ-016) — 인물/방송. 튜닝 가능.
_MEDIA_TOKENS = (
    "성시경", "흑백요리사", "백종원", "수요미식회", "성시경의", "또간집",
    "줄서는식당", "최자로드", "풍자", "이영자", "toradeo", "미쉐린", "미슐랭",
)


# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------
def parse_series(payload: dict, keyword: str) -> list[dict]:
    """데이터랩 payload에서 keyword 그룹의 data([{period, ratio}])를 추출한다.

    groupName(응답 title) 우선 매칭, 실패 시 keywords 리스트 포함 여부로 매칭.
    없으면 빈 리스트.
    """
    if not isinstance(payload, dict):
        return []
    for r in payload.get("results", []) or []:
        if r.get("title") == keyword or keyword in (r.get("keywords") or []):
            return r.get("data", []) or []
    return []


def ratios(series: list[dict]) -> list[float]:
    """[{period, ratio}] → [ratio]. 비수치는 0.0."""
    out: list[float] = []
    for pt in series or []:
        v = pt.get("ratio") if isinstance(pt, dict) else None
        try:
            out.append(float(v))
        except (ValueError, TypeError):
            out.append(0.0)
    return out


def _to_values(series_or_values) -> list[float]:
    """series([{period,ratio}]) 또는 이미 [float]인 입력을 [float]로 정규화."""
    if series_or_values and isinstance(series_or_values[0], dict):
        return ratios(series_or_values)
    return [float(v) for v in (series_or_values or [])]


# ---------------------------------------------------------------------------
# 기본 통계
# ---------------------------------------------------------------------------
def recent_mean(values, n: int = RECENT_WINDOW) -> float:
    vals = _to_values(values)
    if not vals:
        return 0.0
    window = vals[-n:] if len(vals) >= n else vals
    return statistics.fmean(window)


def baseline_mean(values, n: int = RECENT_WINDOW) -> float:
    """recent 윈도를 제외한 나머지 평균. 시리즈가 짧으면 전체 평균."""
    vals = _to_values(values)
    if not vals:
        return 0.0
    base = vals[:-n] if len(vals) > n else vals
    return statistics.fmean(base) if base else 0.0


def zscore(values, n: int = RECENT_WINDOW) -> float | None:
    """(recent_mean - baseline_mean) / baseline_std.

    baseline 표본 부족(<2) → None. baseline 표준편차 0(완전 평탄)인데
    급등 → 강신호 sentinel, 하락 → 0.0 (z 미정의로 라이저를 놓치지 않기 위함).
    """
    vals = _to_values(values)
    base = vals[:-n] if len(vals) > n else vals
    if len(base) < 2:
        return None
    b_mean = statistics.fmean(base)
    b_std = statistics.pstdev(base)
    r_mean = recent_mean(vals, n)
    if b_std < _EPS:
        if r_mean > b_mean + _EPS:
            return _Z_FLAT_JUMP
        return 0.0
    return (r_mean - b_mean) / b_std


def last_week_rising(values, n: int = RECENT_WINDOW) -> bool:
    """막주가 직전 구간 대비 상승했는가(가속 포함)."""
    vals = _to_values(values)
    if not vals:
        return False
    if len(vals) == 1:
        return vals[0] > 0
    prior = vals[-n:-1] if len(vals) > n else vals[:-1]
    prior_mean = statistics.fmean(prior) if prior else 0.0
    return vals[-1] > prior_mean or vals[-1] > vals[-2]


def momentum_collapse(values, n: int = RECENT_WINDOW) -> bool:
    """막주가 직전평균 × MOMENTUM_COLLAPSE_RATIO 미만 → 붕괴(REQ-019)."""
    vals = _to_values(values)
    if len(vals) < 2:
        return False
    prior = vals[-n:-1] if len(vals) > n else vals[:-1]
    if not prior:
        return False
    prior_mean = statistics.fmean(prior)
    if prior_mean < _EPS:
        return False
    return vals[-1] < prior_mean * MOMENTUM_COLLAPSE_RATIO


# ---------------------------------------------------------------------------
# YoY (REQ-018, §8.6) — 카테고리 상대값
# ---------------------------------------------------------------------------
def compute_yoy(values, n: int = RECENT_WINDOW) -> float | None:
    """절대 YoY = recent 윈도 평균 ÷ 약 52주 전 동일 윈도 평균.

    시리즈가 YOY_MIN_WEEKS 미만이면 None(전년 데이터 부족 = 신규 신호).
    1년 전 구간이 거의 0이면 None(의미 있는 비율 불가).
    """
    vals = _to_values(values)
    if len(vals) < YOY_MIN_WEEKS:
        return None
    r_mean = recent_mean(vals, n)
    year_ago = vals[-(_WEEKS_PER_YEAR + n):-_WEEKS_PER_YEAR]
    if not year_ago:
        return None
    ya_mean = statistics.fmean(year_ago)
    if ya_mean < _EPS:
        return None
    return r_mean / ya_mean


def relative_yoy(keyword_yoy: float | None, category_yoy: float | None) -> float | None:
    """키워드YoY ÷ 카테고리YoY(REQ-018). macro 지역 하락 보정.

    어느 한쪽이 None이거나 카테고리YoY가 0 이하면 None.
    """
    if keyword_yoy is None or category_yoy is None or category_yoy <= _EPS:
        return None
    return keyword_yoy / category_yoy


def category_yoy_from_basket(basket_yoys) -> float | None:
    """지역 상시 키워드 바스켓 YoY들의 중앙값 = 카테고리 macro(REQ-018)."""
    vals = [y for y in (basket_yoys or []) if y is not None]
    if not vals:
        return None
    return statistics.median(vals)


# ---------------------------------------------------------------------------
# floor / 미디어 (REQ-014 / REQ-016)
# ---------------------------------------------------------------------------
def magnitude_floor_pass(monthly_vol: float, base_mean: float) -> bool:
    """절대 검색량 ≥ VOL_FLOOR AND baseline 평균 ≥ BASELINE_FLOOR.

    전레인 필수(REQ-014). 신규 레인도 이 floor를 먼저 통과해야 한다(§8.11 PoC#5).
    """
    return monthly_vol >= VOL_FLOOR and base_mean >= BASELINE_FLOOR


def is_media_token(keyword: str, tokens=None) -> bool:
    """인물/방송 토큰 포함 여부(REQ-016). 성시경·흑백요리사 등."""
    toks = tokens if tokens is not None else _MEDIA_TOKENS
    return any(t in keyword for t in toks)


# ---------------------------------------------------------------------------
# 3레인 분류기 (REQ-017)
# ---------------------------------------------------------------------------
def classify(
    keyword: str,
    series,
    *,
    monthly_vol: float,
    category_yoy: float | None,
    media_tokens=None,
) -> dict:
    """단일 키워드를 3레인 중 하나(또는 None)로 분류한다.

    Args:
        keyword: 후보 키워드(미디어 토큰 판정에 사용).
        series: 데이터랩 data([{period, ratio}]) 또는 [ratio].
        monthly_vol: SearchAd 절대 월검색량(레벨).
        category_yoy: 지역 카테고리 macro YoY(바스켓 중앙값). 상대YoY 분모.

    Returns:
        dict {lane, surge, z, yoy, relative_yoy, weeks, floor_passed,
              momentum_ok, is_media, reason}
        lane ∈ {"신규출현","검증상승","미디어스파이크", None}.
        floor 미통과 시 lane=None(격리).
    """
    vals = _to_values(series)
    weeks = len(vals)
    b_mean = baseline_mean(vals)
    r_mean = recent_mean(vals)
    surge = (r_mean / b_mean) if b_mean > _EPS else (r_mean if r_mean > _EPS else 0.0)
    z = zscore(vals)
    kw_yoy = compute_yoy(vals)
    rel_yoy = relative_yoy(kw_yoy, category_yoy)
    media = is_media_token(keyword, media_tokens)
    rising = last_week_rising(vals)
    momentum_ok = not momentum_collapse(vals)
    floor_passed = magnitude_floor_pass(monthly_vol, b_mean)

    result = {
        "lane": None,
        "surge": round(surge, 3),
        "z": (round(z, 3) if z is not None else None),
        "yoy": (round(kw_yoy, 3) if kw_yoy is not None else None),
        "relative_yoy": (round(rel_yoy, 3) if rel_yoy is not None else None),
        "weeks": weeks,
        "floor_passed": floor_passed,
        "momentum_ok": momentum_ok,
        "is_media": media,
        "reason": "",
    }

    # 0) magnitude floor 전레인 선통과 (REQ-014 / §8.11 PoC#5)
    if not floor_passed:
        result["reason"] = (
            f"magnitude floor 미달(월검색량 {int(monthly_vol)}<{VOL_FLOOR} "
            f"또는 baseline {b_mean:.1f}<{BASELINE_FLOOR}) → 계절성/노이즈 의심, 격리"
        )
        return result

    elevated = (
        (z is not None and z >= Z_MIN)
        or (rel_yoy is not None and rel_yoy >= RELATIVE_YOY_MIN)
        or surge >= 1.5
    )

    # 1) 미디어스파이크 (REQ-016) — 인물/방송 토큰 + 급등이면 별도 레인(precedence)
    if media and elevated:
        result["lane"] = "미디어스파이크"
        result["reason"] = (
            "미디어 토큰 + 급등 — 1급 신호이나 지속성 약할 수 있음"
            + ("(막주 붕괴)" if not momentum_ok else "")
        )
        return result

    # 2) 신규출현 — 전년 데이터 無(짧은 시리즈) + 막주 상승
    if weeks < NEW_SERIES_MAX_WEEKS and rising:
        result["lane"] = "신규출현"
        result["reason"] = f"시리즈 {weeks}주(<{NEW_SERIES_MAX_WEEKS}, 전년 데이터 無) + 막주 상승"
        return result

    # 3) 검증상승 — 카테고리 상대 YoY ≥ 2 + z ≥ 1 + 막주 비붕괴
    if (
        rel_yoy is not None
        and rel_yoy >= RELATIVE_YOY_MIN
        and z is not None
        and z >= Z_MIN
        and momentum_ok
    ):
        result["lane"] = "검증상승"
        result["reason"] = f"카테고리 상대 YoY {rel_yoy:.2f}≥{RELATIVE_YOY_MIN} + z {z:.2f}≥{Z_MIN} + 막주 비붕괴"
        return result

    # floor는 통과했으나 어느 라이저 레인도 아님 = 안정/식는 중 (유행 아님, REQ-020)
    if not momentum_ok:
        result["reason"] = "급등 후 막주 붕괴 — 스파이크 소진(라이저 아님)"
    else:
        result["reason"] = "floor 통과하나 상승 신호 부족 — 안정/클래식(유행 아님)"
    return result
