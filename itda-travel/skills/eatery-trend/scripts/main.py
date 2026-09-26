"""main.py — eatery-trend 모드 A/B 라우팅 + 종단 오케스트레이션 (REQ-006/008/010/020).

유행 맛집 = 관심의 미분(surge). 키워드가 트렌드 운반체, 식당은 목적지.

모드 B(주 파이프라인): 지역 seed → 발굴(자동완성+geo×음식 그리드+SearchAd 연관)
  → relevance(geo 게이트+사전+LLM 훅) → velocity(데이터랩 3레인) → trust(거품)
  → 장소(지역검색+카테고리 필터) → 뜨는 키워드 Top-N + 근거 + 가게.
모드 A(검색 보강): 동네+주제 → 가게목록 + 주제 surge 맥락(REQ-020 희박 신호:
  모든 가게 오버레이 금지, 떠오르는 키워드 맥락 + 이름 바이럴된 소수만 표기).

fail-loud(REQ-008): 소스별 도달 실패를 source_status/errors로 표면화하고
빈 결과를 성공으로 위장하지 않는다. 레벨(월검색량)과 속도(surge)를 분리 표기(REQ-006).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from typing import Callable

import adapters
import cache
import places
import relevance
import surge
import trust

# ---------------------------------------------------------------------------
# 발굴 시드 (튜닝 가능) — 지역 비의존 일반 음식 컨셉. 지역 명물은 자동완성·SearchAd가 채움.
# ---------------------------------------------------------------------------
FOOD_SEEDS: tuple[str, ...] = (
    "맛집", "카페", "디저트", "빵집", "국밥", "국수", "고기", "회", "해산물", "브런치",
)
# 카테고리 macro YoY 바스켓(REQ-018) — 지역 상시 attention 키워드(food+여행 혼합).
BASKET_SEEDS: tuple[str, ...] = ("맛집", "카페", "여행", "가볼만한곳", "호텔")

_DATALAB_WEEKS = 78          # ≥56주(YoY) 보장하는 조회 범위(약 18개월)
_DATALAB_BATCH = 5           # 데이터랩 그룹 최대 5
_FOOD_CAP = 25               # 데이터랩 검증 후보 상한(grid + 발굴음식, REQ-009)
_NEEDS_LLM_CAP = 25          # LLM 판정 위임 후보 상한(vol 상위) — Claude가 처리 가능한 규모
_DEFAULT_THROTTLE = 0.3      # 호출 간 간격(초, REQ-009 rate-limit)


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def _date_range(weeks: int = _DATALAB_WEEKS) -> tuple[str, str]:
    """데이터랩 조회 [start, end]. end=오늘, start=weeks주 전(YoY용 ≥56주)."""
    end = date.today()
    start = end - timedelta(weeks=weeks)
    return start.isoformat(), end.isoformat()


def _norm(kw: str) -> str:
    return kw.replace(" ", "")


def _dedup_candidates(raw: list[str]) -> list[str]:
    """공백 제거 키로 중복 제거. 공백이 더 많은(가독·관용) 표시형을 선호.

    SearchAd 연관키워드는 공백 없음('제주몸국'), 자동완성/데이터랩은 공백 있음
    ('제주 몸국'). 같은 개념이 두 후보로 갈리지 않도록 정규화한다.
    """
    by_key: dict[str, str] = {}
    for c in raw:
        c = (c or "").strip()
        key = _norm(c)
        if not key:
            continue
        if key not in by_key or c.count(" ") > by_key[key].count(" "):
            by_key[key] = c
    return list(by_key.values())


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _score(r: dict) -> float:
    """랭킹 점수 = 상대YoY(없으면 surge) − 거품 penalty."""
    base = r.get("relative_yoy")
    if base is None:
        base = r.get("surge") or 0.0
    penalty = r.get("trust", {}).get("penalty", 0.0) if isinstance(r.get("trust"), dict) else 0.0
    return float(base) - float(penalty)


# ---------------------------------------------------------------------------
# 발굴 + relevance (모드 B 1~2단계, --emit-candidates와 공유)
# ---------------------------------------------------------------------------
def discover(
    seed: str,
    *,
    autocomplete_fn: Callable,
    keywordstool_fn: Callable,
    judge: Callable[[str], bool | None] | None = None,
) -> dict:
    """발굴(자동완성+grid+SearchAd) → relevance 필터. validation 전 단계.

    Returns dict {tokens, food, needs_llm, rejected, vol_map, source_status, errors,
                  candidate_count}.
    """
    tokens = relevance.geo_tokens(seed)
    source_status: dict = {}
    errors: list[str] = []
    raw: list[str] = []

    # 1a. 자동완성 힌트(geo-scoped, REQ-011)
    ac_ok_any = False
    for q in (f"{seed} ", f"{seed} 맛집", f"{seed} 디저트"):
        ok, items, reason = autocomplete_fn(q)
        ac_ok_any = ac_ok_any or ok
        if ok:
            raw.extend(items)
        else:
            errors.append(f"자동완성('{q}'): {reason}")
    source_status["autocomplete"] = True if ac_ok_any else "전 호출 실패"

    # 1b. geo×음식 그리드(geo 강제, REQ-013) — geo 토큰 + 음식 시드로 *구성상 음식*.
    #     사전/LLM 판정을 우회한다(bare "회"·"고기"를 사전에 넣으면 박람회·전시회를
    #     음식으로 오판해 정밀도가 붕괴하므로, 모호어는 grid 구성으로만 음식 확정).
    grid = relevance.build_geo_food_grid(seed, list(FOOD_SEEDS))

    # 1c. SearchAd 연관 breadth + 월검색량(REQ-002)
    vol_map: dict[str, int] = {}
    ok, rows, reason = keywordstool_fn([f"{seed}맛집", f"{seed}디저트"])
    source_status["searchad"] = True if ok else reason
    rel_kw: list[str] = []
    if ok:
        for row in rows:
            rk = row.get("relKeyword", "")
            if rk:
                rel_kw.append(rk)
                vol_map[_norm(rk)] = adapters.monthly_volume(row)
    else:
        errors.append(f"SearchAd 발굴: {reason}")

    # 2. relevance — 발굴(자동완성+SearchAd)만 geo→사전→LLM 훅에 태운다.
    discovered = _dedup_candidates(raw + rel_kw)
    filt = relevance.filter_candidates(discovered, tokens, judge=judge)

    def _by_vol(k: str) -> int:
        return vol_map.get(_norm(k), 0)

    # 발굴 음식은 월검색량 상위로 랭킹 — PoC 실신호(오메기떡·몸국)가 cap에 밀리지 않게.
    disc_food = sorted((c["keyword"] for c in filt["food"]), key=_by_vol, reverse=True)
    # food = grid(구성상 음식, 항상 포함) + 발굴 음식 상위. 공백 변형 중복 제거 후 상한.
    food = _dedup_candidates(grid + disc_food)[:_FOOD_CAP]
    # needs_llm도 vol 상위로 bound — LLM(Claude)이 판정할 수 있는 규모로.
    needs_llm = sorted((c["keyword"] for c in filt["needs_llm"]), key=_by_vol, reverse=True)[:_NEEDS_LLM_CAP]
    rejected = [c["keyword"] for c in filt["rejected"]]
    candidates = _dedup_candidates(grid + discovered)

    return {
        "tokens": tokens,
        "food": food,
        "needs_llm": needs_llm,
        "rejected": rejected,
        "vol_map": vol_map,
        "source_status": source_status,
        "errors": errors,
        "candidate_count": len(candidates),
    }


# ---------------------------------------------------------------------------
# 모드 B 종단
# ---------------------------------------------------------------------------
def run_mode_b(
    seed: str,
    *,
    autocomplete_fn: Callable,
    keywordstool_fn: Callable,
    datalab_fn: Callable,
    local_search_fn: Callable,
    blog_total_fn: Callable,
    judge: Callable[[str], bool | None] | None = None,
    top_n: int = 10,
) -> dict:
    """모드 B 핫키워드 탐지 종단(AC-1)."""
    start, end = _date_range()
    disc = discover(seed, autocomplete_fn=autocomplete_fn,
                    keywordstool_fn=keywordstool_fn, judge=judge)
    tokens = disc["tokens"]
    vol_map = disc["vol_map"]
    source_status = disc["source_status"]
    errors = disc["errors"]

    # 3. 카테고리 macro YoY 바스켓(REQ-018)
    basket = relevance.build_geo_food_grid(seed, list(BASKET_SEEDS))[:_DATALAB_BATCH]
    cat_ok, cat_payload, cat_reason = datalab_fn(basket, start, end)
    source_status["datalab_basket"] = True if cat_ok else cat_reason
    category_yoy = None
    if cat_ok and cat_payload:
        byoys = [surge.compute_yoy(surge.parse_series(cat_payload, b)) for b in basket]
        category_yoy = surge.category_yoy_from_basket(byoys)
    else:
        errors.append(f"카테고리 바스켓 데이터랩: {cat_reason}")

    # 4. validation: 데이터랩 배치 + SearchAd 월검색량
    classified: list[dict] = []
    datalab_ok_any = False
    for batch in _chunks(disc["food"], _DATALAB_BATCH):
        ok, payload, reason = datalab_fn(batch, start, end)
        datalab_ok_any = datalab_ok_any or ok
        if not ok:
            errors.append(f"데이터랩({'/'.join(batch)}): {reason}")
            continue
        vok, vrows, vreason = keywordstool_fn(batch)
        if vok:
            for row in vrows:
                vol_map[_norm(row.get("relKeyword", ""))] = adapters.monthly_volume(row)
        for kw in batch:
            series = surge.parse_series(payload, kw)
            vol = vol_map.get(_norm(kw), 0)
            r = surge.classify(kw, series, monthly_vol=vol, category_yoy=category_yoy)
            r["keyword"] = kw
            r["monthly_vol"] = vol
            classified.append(r)
    source_status["datalab"] = True if datalab_ok_any else "전 배치 실패"

    # 5. trust(거품) + 6. 장소(지역검색)
    # 블로그 호출은 라이저 + 검색량 있는 강등 후보로 제한(REQ-009). vol 0 죽은
    # 노이즈는 거품 진단이 무의미하므로 blog 호출을 생략한다.
    risers: list[dict] = []
    demoted: list[dict] = []
    for r in classified:
        kw = r["keyword"]
        if r["lane"] is not None or r["monthly_vol"] > 0:
            bok, btotal, breason = blog_total_fn(kw)
            if bok:
                r["trust"] = trust.assess(btotal or 0, r["monthly_vol"])
            else:
                r["trust"] = {"is_bubble": False, "ratio": None, "penalty": 0.0,
                              "reason": f"블로그 도달 실패: {breason}"}
        else:
            r["trust"] = {"is_bubble": False, "ratio": None, "penalty": 0.0,
                          "reason": "검색량 0 — 노이즈(블로그 비율 평가 생략)"}
        if r["lane"] is not None:
            r["places"] = places.resolve_places(kw, tokens, local_search_fn)
            r["score"] = _score(r)
            risers.append(r)
        else:
            r["demote_reason"] = (
                r["trust"]["reason"] if r["trust"].get("is_bubble") else r["reason"]
            )
            demoted.append(r)

    risers.sort(key=lambda x: x["score"], reverse=True)

    return {
        "mode": "B",
        "seed": seed,
        "category_yoy": category_yoy,
        "risers": risers[:top_n],
        "demoted": demoted,
        "needs_llm": disc["needs_llm"],
        "rejected_count": len(disc["rejected"]),
        "candidate_count": disc["candidate_count"],
        "source_status": source_status,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 모드 A 종단 (REQ-020)
# ---------------------------------------------------------------------------
def run_mode_a(
    region: str,
    topic: str,
    *,
    autocomplete_fn: Callable,
    keywordstool_fn: Callable,
    datalab_fn: Callable,
    local_search_fn: Callable,
    blog_total_fn: Callable,
    judge: Callable[[str], bool | None] | None = None,
) -> dict:
    """모드 A 검색 보강 — 동네×주제. 가게목록 + 주제 surge 맥락."""
    start, end = _date_range()
    tokens = relevance.geo_tokens(region)
    topic_kw = f"{region} {topic}".strip()
    source_status: dict = {}
    errors: list[str] = []

    # 카테고리 macro
    basket = relevance.build_geo_food_grid(region, list(BASKET_SEEDS))[:_DATALAB_BATCH]
    cat_ok, cat_payload, cat_reason = datalab_fn(basket, start, end)
    category_yoy = None
    if cat_ok and cat_payload:
        byoys = [surge.compute_yoy(surge.parse_series(cat_payload, b)) for b in basket]
        category_yoy = surge.category_yoy_from_basket(byoys)

    # 주제 키워드 surge (REQ-020 a: 떠오르는 키워드 맥락)
    vol = 0
    vok, vrows, _vr = keywordstool_fn([topic_kw])
    if vok:
        for row in vrows:
            if _norm(row.get("relKeyword", "")) == _norm(topic_kw):
                vol = adapters.monthly_volume(row)
        if vol == 0 and vrows:
            vol = adapters.monthly_volume(vrows[0])
    tok, tpayload, treason = datalab_fn([topic_kw], start, end)
    source_status["datalab"] = True if tok else treason
    topic_surge = None
    if tok and tpayload:
        series = surge.parse_series(tpayload, topic_kw)
        topic_surge = surge.classify(topic_kw, series, monthly_vol=vol, category_yoy=category_yoy)
        topic_surge["keyword"] = topic_kw
        topic_surge["monthly_vol"] = vol
    else:
        errors.append(f"데이터랩({topic_kw}): {treason}")

    # 가게목록 (지역검색 + 음식 카테고리 + geo assert)
    pr = places.resolve_places(topic_kw, tokens, local_search_fn)

    # 이름 바이럴된 소수만 surge 표기 (REQ-020 b) — 모든 가게 오버레이 금지.
    # 싼 신호: 가게명이 자동완성 힌트에 등장(사람들이 그 이름으로 검색).
    viral: list[str] = []
    aok, hints, _ar = autocomplete_fn(f"{region} ")
    if aok and pr.get("status") == "ok":
        for pl in pr.get("places", []):
            t = pl.get("title", "")
            if t and any(t in h for h in hints):
                viral.append(t)

    return {
        "mode": "A",
        "region": region,
        "topic": topic,
        "topic_kw": topic_kw,
        "topic_surge": topic_surge,
        "category_yoy": category_yoy,
        "places": pr,
        "viral_stores": viral,
        "source_status": source_status,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 기본 어댑터 래퍼 (cache + throttle) — CLI 경로
# ---------------------------------------------------------------------------
def _make_cached_adapters(use_cache: bool = True, throttle: float = _DEFAULT_THROTTLE) -> dict:
    """adapters를 cache TTL + throttle로 감싼 callable 묶음(REQ-009)."""

    def _throttle():
        if throttle:
            time.sleep(throttle)

    def autocomplete_fn(q):
        return adapters.autocomplete(q)  # 비공식·휘발성, 캐시 안 함

    def keywordstool_fn(hints):
        key = ["kt"] + sorted(hints)
        if use_cache:
            c = cache.get_value("searchad", key)
            if c is not None:
                return (True, c, "")
        _throttle()
        ok, data, reason = adapters.keywordstool(hints)
        if ok and use_cache:
            cache.set_value("searchad", key, data)
        return ok, data, reason

    def datalab_fn(keywords, start=None, end=None, unit="week"):
        key = ["dl", start, end, unit] + sorted(keywords)
        if use_cache:
            c = cache.get_value("datalab", key)
            if c is not None:
                return (True, c, "")
        _throttle()
        ok, data, reason = adapters.datalab(keywords, start, end, unit)
        if ok and use_cache:
            cache.set_value("datalab", key, data)
        return ok, data, reason

    def local_search_fn(q):
        key = ["ls", q]
        if use_cache:
            c = cache.get_value("local", key)
            if c is not None:
                return (True, c, "")
        _throttle()
        ok, data, reason = adapters.local_search(q)
        if ok and use_cache:
            cache.set_value("local", key, data)
        return ok, data, reason

    def blog_total_fn(q):
        key = ["bt", q]
        if use_cache:
            c = cache.get_value("blog", key)
            if c is not None:
                return (True, c, "")
        _throttle()
        ok, data, reason = adapters.blog_total(q)
        if ok and use_cache:
            cache.set_value("blog", key, data)
        return ok, data, reason

    return {
        "autocomplete_fn": autocomplete_fn,
        "keywordstool_fn": keywordstool_fn,
        "datalab_fn": datalab_fn,
        "local_search_fn": local_search_fn,
        "blog_total_fn": blog_total_fn,
    }


def _load_judge(judge_file: str | None) -> Callable[[str], bool | None] | None:
    """--judge-file JSON({keyword: true/false})에서 LLM 판정 훅 구성(REQ-015)."""
    if not judge_file:
        return None
    try:
        with open(judge_file, encoding="utf-8") as f:
            verdicts = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(verdicts, dict):
        return None
    return lambda kw: verdicts.get(kw)


# ---------------------------------------------------------------------------
# 출력 포맷 (한국어, REQ-006 레벨/속도 분리)
# ---------------------------------------------------------------------------
_LANE_ICON = {"신규출현": "🆕", "검증상승": "🔥", "미디어스파이크": "📺"}


def _fmt_riser(r: dict) -> str:
    lane = r.get("lane") or "-"
    icon = _LANE_ICON.get(lane, "·")
    rel = r.get("relative_yoy")
    rel_s = f"상대YoY {rel:.2f}" if rel is not None else "신규(YoY 없음)"
    vol = r.get("monthly_vol", 0)
    surge_v = r.get("surge", 0)
    tr = r.get("trust", {})
    trust_s = "⚠️거품" if tr.get("is_bubble") else "실수요"
    lines = [
        f"{icon} {r['keyword']}  [{lane}]",
        f"    속도: surge {surge_v:.2f}배 · {rel_s} · z {r.get('z')}  |  레벨: 월검색 {vol:,} · {trust_s}",
    ]
    if not r.get("momentum_ok", True):
        lines.append("    ⚠️ 막주 모멘텀 붕괴 — 식는 중(지속성 약함)")
    pr = r.get("places", {})
    st = pr.get("status")
    if st == "ok":
        for pl in pr.get("places", [])[:3]:
            lines.append(f"      🏠 {pl['title']} ({pl['category']}) — {pl['roadAddress']}")
        if pr.get("homonym"):
            lines.append(f"      ↳ {pr.get('note')}")
    elif st in ("no_match", "no_food_match"):
        lines.append(f"      🏠 {pr.get('note')}")
    elif st == "source_error":
        lines.append(f"      ⚠️ 지역검색 실패: {pr.get('reason')}")
    return "\n".join(lines)


def format_mode_b(result: dict) -> str:
    cat = result.get("category_yoy")
    cat_s = f"{cat:.2f}" if cat is not None else "산출 실패"
    out = [
        f"🍜 '{result['seed']}' 뜨는 맛집 키워드 (유행 = 관심의 미분)",
        f"   카테고리 macro YoY {cat_s} · 후보 {result['candidate_count']}개 · "
        f"라이저 {len(result['risers'])} / 강등 {len(result['demoted'])} / LLM판정필요 {len(result['needs_llm'])}",
        "",
    ]
    if result["risers"]:
        for lane in ("신규출현", "검증상승", "미디어스파이크"):
            group = [r for r in result["risers"] if r.get("lane") == lane]
            if group:
                out.append(f"── {_LANE_ICON[lane]} {lane} ──")
                out.extend(_fmt_riser(r) for r in group)
                out.append("")
    else:
        out.append("(뜨는 키워드 없음 — 소스 상태를 확인하세요)")
        out.append("")

    if result["needs_llm"]:
        out.append(f"🤔 LLM 음식 판정 필요(가게명/신조어, REQ-015): {', '.join(result['needs_llm'][:15])}")
    bubbles = [d for d in result["demoted"] if d.get("trust", {}).get("is_bubble")]
    if bubbles:
        out.append(f"⚠️ 협찬 거품 강등: {', '.join(d['keyword'] for d in bubbles[:10])}")

    # fail-loud
    bad = [f"{k}={v}" for k, v in result["source_status"].items() if v is not True]
    if bad:
        out.append(f"🚨 소스 상태(fail-loud): {' / '.join(bad)}")
    return "\n".join(out)


def format_mode_a(result: dict) -> str:
    ts = result.get("topic_surge")
    out = [f"🍜 '{result['region']} {result['topic']}' — 동네×주제 트렌디 판별", ""]
    if ts:
        out.append(f"주제 키워드 맥락: [{ts.get('lane') or '안정/평탄'}] surge {ts.get('surge')}배 · "
                   f"월검색 {ts.get('monthly_vol', 0):,}")
        if ts.get("lane"):
            out.append(f"   → '{result['topic']}'은(는) 지금 떠오르는 맥락 ({ts.get('reason')})")
        else:
            out.append(f"   → '{result['topic']}'은(는) 안정적(유행 급등 아님)")
    out.append("")
    pr = result.get("places", {})
    if pr.get("status") == "ok":
        out.append(f"가게 ({len(pr['places'])}곳, 음식 카테고리+{result['region']} 주소 확인):")
        for pl in pr["places"]:
            viral = " 🔥이름바이럴" if pl["title"] in result.get("viral_stores", []) else ""
            out.append(f"  🏠 {pl['title']} ({pl['category']}){viral} — {pl['roadAddress']}")
        out.append("")
        out.append("ℹ️ 평범한 가게는 이름 surge 신호가 없는 게 정상입니다(유행≠노포). "
                   "트렌디 = 떠오르는 키워드 맥락 + 이름이 바이럴된 소수만 표기(REQ-020).")
    else:
        out.append(f"가게: {pr.get('note') or pr.get('reason') or '없음'}")
    bad = [f"{k}={v}" for k, v in result["source_status"].items() if v is not True]
    if bad:
        out.append(f"🚨 소스 상태(fail-loud): {' / '.join(bad)}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="eatery-trend — 유행 맛집 탐지(관심의 미분). 모드 B(핫키워드)/A(동네×주제)."
    )
    p.add_argument("--mode", choices=["A", "B"], required=True, help="A=동네×주제, B=핫키워드 탐지")
    p.add_argument("--seed", help="모드 B 지역/테마 시드 (예: 제주)")
    p.add_argument("--region", help="모드 A 동네 (예: 성수)")
    p.add_argument("--topic", help="모드 A 주제 (예: 국밥)")
    p.add_argument("--top-n", type=int, default=10, help="모드 B Top-N (기본 10)")
    p.add_argument("--judge-file", help="LLM 음식 판정 결과 JSON({키워드: true/false}) (REQ-015)")
    p.add_argument("--emit-candidates", action="store_true",
                   help="모드 B 발굴+relevance만 JSON 출력(LLM 판정 전 단계, 호출 절약)")
    p.add_argument("--json", action="store_true", help="JSON 출력")
    p.add_argument("--no-cache", action="store_true", help="캐시 비활성")
    p.add_argument("--throttle", type=float, default=_DEFAULT_THROTTLE, help="호출 간 간격(초)")
    return p


def main(argv: list[str] | None = None) -> int:
    if sys.version_info[0] < 3:
        sys.stderr.write("Python 3.10+ 필요\n")
        return 2
    args = build_parser().parse_args(argv)
    deps = _make_cached_adapters(use_cache=not args.no_cache, throttle=args.throttle)
    judge = _load_judge(args.judge_file)

    if args.mode == "B":
        if not args.seed:
            sys.stderr.write("모드 B는 --seed가 필요합니다.\n")
            return 2
        if args.emit_candidates:
            disc = discover(args.seed, autocomplete_fn=deps["autocomplete_fn"],
                            keywordstool_fn=deps["keywordstool_fn"], judge=judge)
            print(json.dumps({"food": disc["food"], "needs_llm": disc["needs_llm"],
                              "rejected": disc["rejected"], "source_status": disc["source_status"]},
                             ensure_ascii=False, indent=2))
            return 0
        result = run_mode_b(args.seed, judge=judge, top_n=args.top_n, **deps)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_mode_b(result))
        return 0

    # mode A
    if not args.region or not args.topic:
        sys.stderr.write("모드 A는 --region과 --topic이 필요합니다.\n")
        return 2
    result = run_mode_a(args.region, args.topic, judge=judge, **deps)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_mode_a(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
