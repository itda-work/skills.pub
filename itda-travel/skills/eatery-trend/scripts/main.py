"""main.py — eatery-trend 모드 A/B 라우팅 + 종단 오케스트레이션 (REQ-006/008/010/020).

유행 맛집 = 관심의 미분(surge). 키워드가 트렌드 운반체, 식당은 목적지.

모드 B(주 파이프라인): 지역 seed → 발굴(자동완성+geo×음식 그리드+SearchAd 연관)
  → relevance(geo 게이트+사전+LLM 훅) → velocity(데이터랩 3레인) → trust(거품)
  → 장소(지역검색+카테고리 필터) → 뜨는 키워드 Top-N + 근거 + 가게.
모드 A(검색 보강): 동네+주제 → 가게목록 + 주제 surge 맥락(REQ-020 희박 신호:
  모든 가게 오버레이 금지, 떠오르는 키워드 맥락 + 이름 바이럴된 소수만 표기).

fail-loud(REQ-008): 소스별 도달 실패를 source_status/errors로 표면화하고
빈 결과를 성공으로 위장하지 않는다. 레벨(월검색량)과 속도(surge)를 분리 표기(REQ-006).

네트워크 없음(itda-work/skills#46 W17): 요청은 itda-hyve 가 보내고, CLI(plan·collect)는 hyve_store 로 저장 파일을 읽어
같은 파이프라인을 돌린다. 지금 쓰는 소스는 데이터랩·지역검색뿐이다 — 자동완성은 robots 전면 불허라 부르지 않고,
검색광고(월검색량·연관 키워드)는 itda-hyve 서명 기능(itda-work/itda-hyve#34)을 기다리며, 블로그 total 은 거품 비율의 분모(월검색량)가
없어 부르지 않는다. 그 소스들은 파이프라인 인자로 None 을 받아 사유를 source_status 에 싣는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import adapters
import hyve_store
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

# 쓰지 않는 소스의 사유 — source_status 에 실려 `🚨 소스 상태` 로 보인다(조용히 빼지 않는다).
AUTOCOMPLETE_UNUSED = "사용 안 함 — ac.search.naver.com robots 가 전면 불허(2026-10-06)"
TRUST_PENDING = "거품 판정 보류 — 월검색량(네이버 검색광고)이 없어 블로그/검색 비율을 낼 수 없다(itda-work/itda-hyve#34 대기)"


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
    autocomplete_fn: Callable | None,
    keywordstool_fn: Callable | None,
    judge: Callable[[str], bool | None] | None = None,
) -> dict:
    """발굴(자동완성+grid+SearchAd) → relevance 필터. validation 전 단계.

    ``autocomplete_fn``·``keywordstool_fn`` 이 None 이면 그 소스는 쓰지 않는다(사유를 source_status 에 싣는다):
    자동완성은 ac.search.naver.com robots 가 `User-agent: *` 전면 불허라 부르지 않고(2026-10-06), 검색광고는
    itda-hyve 서명 기능(itda-work/itda-hyve#34)을 기다린다. 그때 후보는 geo×음식 그리드뿐이다.

    Returns dict {tokens, food, needs_llm, rejected, vol_map, source_status, errors,
                  candidate_count}.
    """
    tokens = relevance.geo_tokens(seed)
    source_status: dict = {}
    errors: list[str] = []
    raw: list[str] = []

    # 1a. 자동완성 힌트(geo-scoped, REQ-011)
    if autocomplete_fn is None:
        source_status["autocomplete"] = AUTOCOMPLETE_UNUSED
    else:
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
    rel_kw: list[str] = []
    if keywordstool_fn is None:
        source_status["searchad"] = adapters.SEARCHAD_UNAVAILABLE
    else:
        ok, rows, reason = keywordstool_fn([f"{seed}맛집", f"{seed}디저트"])
        source_status["searchad"] = True if ok else reason
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
        "level_known": keywordstool_fn is not None,
    }


# ---------------------------------------------------------------------------
# 모드 B 종단
# ---------------------------------------------------------------------------
def run_mode_b(
    seed: str,
    *,
    autocomplete_fn: Callable | None,
    keywordstool_fn: Callable | None,
    datalab_fn: Callable,
    local_search_fn: Callable,
    blog_total_fn: Callable | None,
    judge: Callable[[str], bool | None] | None = None,
    top_n: int = 10,
    date_range: tuple[str, str] | None = None,
) -> dict:
    """모드 B 핫키워드 탐지 종단(AC-1).

    None 인 소스(자동완성·검색광고·블로그)는 쓰지 않는다 — 월검색량이 없으면(검색광고 None) floor 는 baseline 만 보고,
    거품 판정(블로그/검색 비율)은 분모가 없어 하지 않는다(블로그도 부르지 않는다). 결과의 ``level_known`` 이 그 사실을 싣는다.
    """
    start, end = date_range or _date_range()
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
        if keywordstool_fn is not None:
            vok, vrows, vreason = keywordstool_fn(batch)
            if vok:
                for row in vrows:
                    vol_map[_norm(row.get("relKeyword", ""))] = adapters.monthly_volume(row)
        for kw in batch:
            series = surge.parse_series(payload, kw)
            vol = vol_map.get(_norm(kw), 0) if keywordstool_fn is not None else None
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
        if r["monthly_vol"] is None or blog_total_fn is None:
            r["trust"] = {"is_bubble": False, "ratio": None, "penalty": 0.0, "reason": TRUST_PENDING}
        elif r["lane"] is not None or r["monthly_vol"] > 0:
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
        "level_known": keywordstool_fn is not None,
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
    autocomplete_fn: Callable | None,
    keywordstool_fn: Callable | None,
    datalab_fn: Callable,
    local_search_fn: Callable,
    blog_total_fn: Callable | None = None,
    judge: Callable[[str], bool | None] | None = None,
    date_range: tuple[str, str] | None = None,
) -> dict:
    """모드 A 검색 보강 — 동네×주제. 가게목록 + 주제 surge 맥락. None 인 소스는 쓰지 않는다(모드 B 와 같다)."""
    start, end = date_range or _date_range()
    tokens = relevance.geo_tokens(region)
    topic_kw = f"{region} {topic}".strip()
    source_status: dict = {}
    errors: list[str] = []

    # 카테고리 macro
    basket = relevance.build_geo_food_grid(region, list(BASKET_SEEDS))[:_DATALAB_BATCH]
    cat_ok, cat_payload, cat_reason = datalab_fn(basket, start, end)
    source_status["datalab_basket"] = True if cat_ok else cat_reason
    category_yoy = None
    if cat_ok and cat_payload:
        byoys = [surge.compute_yoy(surge.parse_series(cat_payload, b)) for b in basket]
        category_yoy = surge.category_yoy_from_basket(byoys)
    else:
        errors.append(f"카테고리 바스켓 데이터랩: {cat_reason}")

    # 주제 키워드 surge (REQ-020 a: 떠오르는 키워드 맥락)
    vol: int | None = None
    if keywordstool_fn is None:
        source_status["searchad"] = adapters.SEARCHAD_UNAVAILABLE
    else:
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
    if autocomplete_fn is None:
        source_status["autocomplete"] = AUTOCOMPLETE_UNUSED
    else:
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
        "level_known": keywordstool_fn is not None,
        "source_status": source_status,
        "errors": errors,
    }


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
    if vol is None:
        level_s = "월검색 미확인 · 거품 판정 보류"
    else:
        level_s = f"월검색 {vol:,} · {'⚠️거품' if tr.get('is_bubble') else '실수요'}"
    lines = [
        f"{icon} {r['keyword']}  [{lane}]",
        f"    속도: surge {surge_v:.2f}배 · {rel_s} · z {r.get('z')}  |  레벨: {level_s}",
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

    if result.get("level_known") is False:
        out.append("ℹ️ 월검색량(레벨)·협찬 거품 판정은 빠졌습니다 — 네이버 검색광고 API 가 itda-hyve 서명 기능을 기다립니다. "
                   "floor 는 데이터랩 baseline 만 봤습니다.")
    # fail-loud
    bad = [f"{k}={v}" for k, v in result["source_status"].items() if v is not True]
    if bad:
        out.append(f"🚨 소스 상태(fail-loud): {' / '.join(bad)}")
    return "\n".join(out)


def format_mode_a(result: dict) -> str:
    ts = result.get("topic_surge")
    out = [f"🍜 '{result['region']} {result['topic']}' — 동네×주제 트렌디 판별", ""]
    if ts:
        mv = ts.get("monthly_vol")
        mv_s = "월검색 미확인" if mv is None else f"월검색 {mv:,}"
        out.append(f"주제 키워드 맥락: [{ts.get('lane') or '안정/평탄'}] surge {ts.get('surge')}배 · {mv_s}")
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
# CLI — 요청은 itda-hyve, 이 스크립트는 계획과 가공만 (네트워크 없음)
# ---------------------------------------------------------------------------
def _reconfigure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="eatery-trend — 유행 맛집 탐지(관심의 미분). 요청은 itda-hyve 가 보내고 이 스크립트는 계획·가공만 한다."
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan", help="회차 폴더를 만들고 첫 호출 계획을 낸다")
    pl.add_argument("--mode", choices=["A", "B"], required=True, help="A=동네×주제, B=핫키워드 탐지")
    pl.add_argument("--seed", help="모드 B 지역/테마 시드 (예: 제주)")
    pl.add_argument("--region", help="모드 A 동네 (예: 성수)")
    pl.add_argument("--topic", help="모드 A 주제 (예: 국밥)")
    pl.add_argument("--top-n", type=int, default=10, help="모드 B Top-N (기본 10)")
    pl.add_argument("--run-dir", required=True, help="회차 폴더(스크립트가 보는 경로)")
    pl.add_argument("--save-dir", required=True, help="같은 폴더의 itda-hyve 호스트 절대 경로(save_dir)")
    co = sub.add_parser("collect", help="받은 파일로 판정 — 모자라면 다음 호출 계획")
    co.add_argument("--run-dir", required=True)
    for sp in (pl, co):
        sp.add_argument("--json", action="store_true", help="결과 JSON 만(report 문자열 없이)")
    return p


def _emit(obj: dict) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return {"ok": 0, "incomplete": 1, "partial": 2}.get(obj.get("status"), 1)


def _run(run_dir: Path, state: dict, as_json: bool) -> dict:
    store = hyve_store.Store(run_dir, state)
    rng = (state["start"], state["end"])
    deps = {"autocomplete_fn": None, "keywordstool_fn": None, "blog_total_fn": None,
            "datalab_fn": store.datalab_fn, "local_search_fn": store.local_search_fn}
    if state["mode"] == "B":
        result = run_mode_b(state["seed"], top_n=state["top_n"], date_range=rng, **deps)
        report = format_mode_b
    else:
        result = run_mode_a(state["region"], state["topic"], date_range=rng, **deps)
        report = format_mode_a
    if store.stop is not None:
        kind, msg = store.stop
        hyve_store.save_state(run_dir, state)
        return {"status": "error", "error": kind, "detail": msg}
    if store.pending:
        nxt = store.write_next()
        hyve_store.save_state(run_dir, state)
        return {"status": "incomplete", "received": store.received, **nxt,
                "detail": "아래 single_calls 를 하나씩, batch_args 를 batch 로 전부 부른 뒤 collect 를 다시 부른다"}
    hyve_store.save_state(run_dir, state)
    out: dict = {"status": "partial" if store.exhausted else "ok", "result": result}
    if store.exhausted:
        out["errors"] = store.exhausted
    if not as_json:
        out["report"] = report(result)
    return out


def main(argv: list[str] | None = None) -> int:
    _reconfigure_utf8()
    if sys.version_info < (3, 10):
        sys.stderr.write("Python 3.10+ 필요\n")
        return 2
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    run_dir = Path(args.run_dir)
    try:
        if args.cmd == "plan":
            if args.mode == "B" and not args.seed:
                raise hyve_store.StoreError("args", "모드 B는 --seed 가 필요하다")
            if args.mode == "A" and (not args.region or not args.topic):
                raise hyve_store.StoreError("args", "모드 A는 --region 과 --topic 이 필요하다")
            if not 1 <= args.top_n <= 25:
                raise hyve_store.StoreError("args", "--top-n 은 1~25 다")
            if not hyve_store.host_abs_path(args.save_dir):
                raise hyve_store.StoreError("args", "--save-dir 는 itda-hyve 가 쓸 호스트 절대 경로다(/Users/…, C:\\Users\\…)")
            run_dir.mkdir(parents=True, exist_ok=True)
            if (run_dir / hyve_store.STATE_NAME).exists():
                raise hyve_store.StoreError("input", "이 회차 폴더에는 이미 계획이 있다 — 다시 하려면 새 회차 폴더를 쓴다")
            start, end = hyve_store.date_window()
            state = {"skill": "eatery-trend", "mode": args.mode, "seed": args.seed, "region": args.region,
                     "topic": args.topic, "top_n": args.top_n, "save_dir": args.save_dir,
                     "start": start, "end": end, "round": 0}
        else:
            state = hyve_store.load_state(run_dir)
        return _emit(_run(run_dir, state, args.json))
    except hyve_store.StoreError as exc:
        return _emit({"status": "error", "error": exc.kind, "detail": str(exc)})


if __name__ == "__main__":
    raise SystemExit(main())
