"""추론 실행부 (SPEC-DATA-VERTICAL-001 — advisor parity).

상관·단순회귀를 **두 독립 경로로 계산해 교차검증**(`_verify`)한다 — advisor 관문5
독립 재현의 코드화. 결과의 `_verify` 가 gates.build_inferential_report 의
verification_result 로 들어가 양심 루프를 닫는다.

stdlib only(numpy/statsmodels 불요). p-value·다중회귀·VIF 는 후속(statsmodels lazy).
"""
from __future__ import annotations
import math

_TOL = 1e-6


def _nums(rows: list[dict], *cols: str) -> list[list[float]]:
    out = []
    for r in rows:
        try:
            out.append([float(str(r[c]).replace(",", "")) for c in cols])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _pearson_cov(xs, ys):  # 경로 A: 편차곱/표준편차
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        raise ValueError("분산이 0인 변수가 있어 상관을 계산할 수 없습니다")
    return cov / (sx * sy)


def _pearson_sum(xs, ys):  # 경로 B: 합 공식(수치적으로 독립)
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    syy = sum(y * y for y in ys)
    denom = math.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy))
    if denom == 0:
        raise ValueError("분산이 0인 변수가 있어 상관을 계산할 수 없습니다")
    return (n * sxy - sx * sy) / denom


def pearson(rows: list[dict], x: str, y: str) -> dict:
    data = _nums(rows, x, y)
    n = len(data)
    if n < 3:
        raise ValueError(f"상관 계산 표본 부족(N={n}<3)")
    xs = [d[0] for d in data]
    ys = [d[1] for d in data]
    a, b = _pearson_cov(xs, ys), _pearson_sum(xs, ys)
    return {
        "method": "pearson",
        "r": round(a, 4),
        "n": n,
        "_verify": {"reproduced": abs(a - b) < _TOL, "diff": abs(a - b)},
    }


def _slope_cov(xs, ys):  # 경로 A
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        raise ValueError("설명변수 분산이 0이라 회귀할 수 없습니다")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r2


def _slope_normal(xs, ys):  # 경로 B: 정규방정식
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    if denom == 0:
        raise ValueError("설명변수 분산이 0이라 회귀할 수 없습니다")
    return (n * sxy - sx * sy) / denom


def simple_regression(rows: list[dict], y: str, x: str) -> dict:
    data = _nums(rows, x, y)
    n = len(data)
    if n < 3:
        raise ValueError(f"회귀 표본 부족(N={n}<3)")
    xs = [d[0] for d in data]
    ys = [d[1] for d in data]
    slope_a, intercept, r2 = _slope_cov(xs, ys)
    slope_b = _slope_normal(xs, ys)
    return {
        "method": "simple_regression",
        "slope": round(slope_a, 6),
        "intercept": round(intercept, 6),
        "r2": round(r2, 4),
        "n": n,
        "_verify": {"reproduced": abs(slope_a - slope_b) < _TOL, "diff": abs(slope_a - slope_b)},
    }


# ── 다중공선성 (advisor VIF 양심 보존) ──────────────────────────────────────────
# 진짜 VIF 는 statsmodels(+numpy) lazy 로 시도하고, 없으면 stdlib pairwise 상관으로
# 폴백한다 → 양심이 의존성 부재로 조용히 사라지지 않는다(NFR-3: descriptive 경로 미로드).
def _try_vif(rows: list[dict], predictors: list[str], threshold: float):
    try:
        import numpy as np  # noqa: lazy
        from statsmodels.stats.outliers_influence import variance_inflation_factor  # noqa: lazy
    except ImportError:
        return None
    data = _nums(rows, *predictors)
    if len(data) <= len(predictors) + 1:
        return None  # 자유도 부족 → 폴백
    X = np.column_stack([np.ones(len(data)), np.array(data, dtype=float)])
    try:
        with np.errstate(divide="ignore", invalid="ignore"):  # 완전 공선성 → VIF=inf(정상 검출)
            vifs = {p: float(variance_inflation_factor(X, i + 1)) for i, p in enumerate(predictors)}
    except Exception:
        return None
    detected = any(v > threshold for v in vifs.values())
    return {
        "detected": detected,
        "method": "vif",
        "vifs": {k: round(v, 2) for k, v in vifs.items()},
        "reason": (f"VIF>{threshold} 변수 존재" if detected else f"모든 VIF<={threshold}"),
    }


def _pairwise_multicollinearity(rows, predictors, r_threshold):
    worst, pair = 0.0, None
    for i in range(len(predictors)):
        for j in range(i + 1, len(predictors)):
            try:
                r = abs(pearson(rows, predictors[i], predictors[j])["r"])
            except ValueError:
                continue
            if r > worst:
                worst, pair = r, (predictors[i], predictors[j])
    detected = worst > r_threshold
    return {
        "detected": detected,
        "method": "pairwise",
        "max_r": round(worst, 4),
        "pair": pair,
        "reason": (f"|r|={worst:.2f}>{r_threshold} {pair}" if detected else f"최대 |r|={worst:.2f}"),
    }


def multicollinearity(rows: list[dict], predictors: list[str],
                      vif_threshold: float = 10.0, r_threshold: float = 0.9) -> dict:
    """예측 변수 간 다중공선성 진단. VIF(statsmodels lazy) → pairwise 상관 폴백."""
    if len(predictors) < 2:
        return {"detected": False, "method": "n/a", "reason": "예측 변수 1개 이하 — 해당 없음"}
    vif = _try_vif(rows, predictors, vif_threshold)
    return vif if vif is not None else _pairwise_multicollinearity(rows, predictors, r_threshold)
