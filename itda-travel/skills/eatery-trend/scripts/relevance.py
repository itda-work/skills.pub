"""relevance.py — geo 게이트 + 음식 사전 + LLM 판정 훅 (REQ-005/013/015).

후보 키워드를 음식/트렌드 여부로 선별한다. 3단 파이프라인:
  1. geo 게이트(REQ-013) — 싼 선별. geo 토큰 미보유 후보 차단(SearchAd 연관은 전국 확산).
  2. 음식 사전(보조)     — 싼 전처리. 명확 음식=True, 명확 비음식(관광)=False, 모호=None.
  3. LLM 판정(REQ-015)  — 최종 권위. 사전 재현율 ~56%(§8.10 PoC#4)라 모호 후보는 LLM이 판정.

★ 게이트 실재성(feedback-gate-enforcement-code-not-docs): judge 미주입 시 사전 모호
  후보를 자동으로 food로 승격하지 않는다. needs_llm으로 분리해 LLM(Claude)에게
  명시적으로 위임한다. SKILL.md "Claude 라우팅 가이드"가 이 판정 단계를 강제한다.

사전은 *보조*다. 열거할 수 없는 다양한 요리명(텐동·조개구이)·지역 명물
(제주마음샌드)·먹거리 시장(동문시장)은 사전이 못 잡고 None을 돌려 LLM에 위임한다.
"""
from __future__ import annotations

from typing import Callable

# ---------------------------------------------------------------------------
# geo 토큰 (REQ-013) — 여행지별 본/하위 지명. 튜닝·확장 가능.
# ---------------------------------------------------------------------------
_GEO_SUBREGIONS: dict[str, tuple[str, ...]] = {
    "제주": ("제주", "제주시", "서귀포", "애월", "한림", "조천", "구좌", "성산",
            "표선", "남원", "안덕", "대정", "한경", "우도", "함덕", "월정", "협재", "중문"),
    "부산": ("부산", "해운대", "광안리", "서면", "남포동", "광복동", "전포", "기장",
            "송정", "다대포", "영도", "동래", "센텀", "수영", "초량"),
    "강릉": ("강릉", "경포", "안목", "주문진", "정동진", "사천", "교동", "초당"),
    "여수": ("여수", "돌산", "교동", "여서동", "웅천", "소호", "국동"),
    "서울": ("서울", "성수", "연남", "이태원", "을지로", "한남", "압구정", "홍대",
            "강남", "삼청", "익선동", "망원", "서촌", "북촌"),
    "경주": ("경주", "황리단길", "보문", "불국사", "감포"),
    "전주": ("전주", "한옥마을", "객사", "효자동", "신시가지"),
}


def geo_tokens(seed: str) -> list[str]:
    """seed 지역의 geo 토큰 목록(본 지명 + 하위 지명). 미등록 지역은 [seed]."""
    seed = seed.strip()
    if seed in _GEO_SUBREGIONS:
        return list(_GEO_SUBREGIONS[seed])
    return [seed]


def geo_gate(keyword: str, tokens: list[str]) -> bool:
    """키워드가 geo 토큰을 하나라도 포함하는가(REQ-013 타지역 누출 차단)."""
    return any(t and t in keyword for t in tokens)


def build_geo_food_grid(seed: str, food_seeds: list[str]) -> list[str]:
    """geo×음식 그리드 후보(REQ-013). 'seed food' 형태로 geo 강제. 순서 보존·중복 제거."""
    out: list[str] = []
    seen: set[str] = set()
    for f in food_seeds:
        cand = f"{seed} {f}".strip()
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


# ---------------------------------------------------------------------------
# 음식 사전 (보조, 고정밀·저재현 — §8.10 PoC#4)
# ---------------------------------------------------------------------------
# 명확한 음식 신호. 부분 문자열 매칭이므로 합성어도 포착(흑돼지구이 ← 흑돼지).
_FOOD_WORDS: tuple[str, ...] = (
    "맛집", "음식점", "식당", "카페", "디저트", "베이커리", "빵집", "제과",
    "국밥", "국수", "칼국수", "라멘", "우동", "돈가스", "흑돼지", "삼겹살",
    "갈비", "고깃집", "물회", "회덮밥", "횟집", "해물", "해산물", "갈치",
    "고등어", "전복", "성게", "몸국", "오메기떡", "한치", "분식", "떡볶이",
    "김밥", "치킨", "피자", "버거", "햄버거", "포차", "이자카야", "와인바",
    "맥주", "호프", "브런치", "파스타", "스테이크", "초밥", "스시", "곱창",
    "막창", "보쌈", "족발", "백반", "한정식", "비빔밥", "짜장", "짬뽕",
    "마라탕", "탕후루", "아이스크림", "젤라또", "와플", "케이크", "도넛",
    "샌드위치", "순대", "곰탕", "설렁탕", "해장국", "추어탕", "매운탕",
    "샤브샤브", "약과", "마카롱", "크로플", "두루치기", "수육", "전골",
    "뚝배기", "쌀국수", "분짜", "타코", "부리또", "감바스", "리조또",
    "먹거리", "다이닝", "오마카세", "베이글", "크루아상", "소금빵",
)

# 명확한 비음식(관광·교통·정보). 음식 단어가 함께 없을 때만 False로 본다.
_NONFOOD_WORDS: tuple[str, ...] = (
    "가볼만한곳", "관광지", "관광", "여행코스", "여행지", "렌트카", "렌터카",
    "항공권", "비행기", "숙소", "호텔", "펜션", "리조트", "게스트하우스",
    "입장료", "날씨", "지도", "일정", "패키지", "박물관", "미술관", "전시",
    "해수욕장", "오름", "폭포", "동굴", "전망대", "등대", "수목원",
    "충전소", "주차장", "버스", "사건", "부동산", "글램핑", "캠핑장",
    "스파", "카약", "서핑", "승마", "패러글라이딩", "스쿠버", "낚시배",
    "올레길", "둘레길", "케이블카", "테마파크", "아쿠아리움", "사진스팟",
)


def dict_food_hint(keyword: str) -> bool | None:
    """음식 사전 판정. True=명확 음식 / False=명확 비음식 / None=모호(LLM 위임).

    고정밀(false-positive 0 지향)·저재현(~56%). 음식 단어가 있으면 True가
    비음식 단어보다 우선(예: '제주 항공권 맛집' → 음식 의도 가능 → True).
    """
    has_food = any(w in keyword for w in _FOOD_WORDS)
    if has_food:
        return True
    has_nonfood = any(w in keyword for w in _NONFOOD_WORDS)
    if has_nonfood:
        return False
    return None


# ---------------------------------------------------------------------------
# 후보 필터 (geo → 사전 → LLM 훅)
# ---------------------------------------------------------------------------
def classify_candidate(keyword: str, tokens: list[str]) -> dict:
    """단일 후보의 geo·사전 상태. {keyword, geo_ok, food_hint, needs_llm}."""
    geo_ok = geo_gate(keyword, tokens)
    hint = dict_food_hint(keyword)
    return {
        "keyword": keyword,
        "geo_ok": geo_ok,
        "food_hint": hint,
        "needs_llm": geo_ok and hint is None,
    }


def filter_candidates(
    candidates: list[str],
    tokens: list[str],
    judge: Callable[[str], bool | None] | None = None,
) -> dict:
    """후보 목록을 food / rejected / needs_llm으로 분류한다(REQ-005/013/015).

    Args:
        candidates: 후보 키워드 목록.
        tokens: geo 토큰(geo_tokens()).
        judge: LLM 음식 판정 훅 callable(keyword)->bool|None.
               True=음식·False=비음식·None=여전히 모호. 사전 모호 후보에만 호출(효율).
               None(미주입)이면 모호 후보는 needs_llm으로 분리(게이트 실재).

    Returns:
        dict {food: [cand,...], rejected: [cand,...], needs_llm: [cand,...]}.
        각 cand는 classify_candidate() dict + (judge 시) 'judged' 표기.
    """
    food: list[dict] = []
    rejected: list[dict] = []
    needs_llm: list[dict] = []

    seen: set[str] = set()
    for kw in candidates:
        if kw in seen:
            continue
        seen.add(kw)
        c = classify_candidate(kw, tokens)

        if not c["geo_ok"]:
            c["reason"] = "geo 토큰 부재 — 타지역 누출 차단(REQ-013)"
            rejected.append(c)
            continue

        hint = c["food_hint"]
        if hint is True:
            c["reason"] = "사전 음식 확정"
            food.append(c)
        elif hint is False:
            c["reason"] = "사전 비음식 확정(관광/교통) — 배제"
            rejected.append(c)
        else:
            # 모호 → LLM 판정(REQ-015)
            if judge is not None:
                verdict = judge(kw)
                c["judged"] = verdict
                if verdict is True:
                    c["reason"] = "LLM 음식 판정"
                    food.append(c)
                elif verdict is False:
                    c["reason"] = "LLM 비음식 판정 — 배제"
                    rejected.append(c)
                else:
                    c["reason"] = "LLM 판정 유보 — 추가 확인 필요"
                    needs_llm.append(c)
            else:
                c["reason"] = "사전 모호 — LLM 판정 필요(REQ-015)"
                needs_llm.append(c)

    return {"food": food, "rejected": rejected, "needs_llm": needs_llm}
