"""역명 정규화 — 한글 입력을 코레일이 인식하는 역명으로 견고화한다(REQ-009).

순수 모듈(네트워크·라이브러리 의존 없음, NFR-005). 흔한 별칭("서울역"→"서울")과
"역" 접미사를 정리하고, 알 수 없는 역은 유사 후보를 제시한다(차단보다 안내).
2026-09-01 SRT→KTX 통합으로 옛 SRT 전용역(수서·동탄·평택지제)도 코레일이
판매하므로 정상 역으로 취급한다(#1624 라이브 실측 — 각 구간 10건 조회 확인).

화이트리스트는 *주요역 힌트*이며 코레일 전체 역명을 망라하지 않는다. 최종 유효성은
실제 검색에서 코레일이 판단한다.
"""
from __future__ import annotations

import difflib

# 주요 KTX·간선 정차역(코레일 표기 기준). 망라가 아니라 정규화·후보 제시용 힌트.
KNOWN_STATIONS: frozenset[str] = frozenset(
    {
        # 경부선 계열
        "서울", "용산", "영등포", "광명", "수원", "천안아산", "오송", "대전",
        # 2026-09-01 SRT→KTX 통합으로 편입된 옛 SRT 전용역(#1624)
        "수서", "동탄", "평택지제", "서대구",
        "김천구미", "동대구", "경주", "신경주", "울산", "부산", "구포", "밀양", "물금",
        "포항",
        # 호남·전라선 계열
        "공주", "서대전", "계룡", "논산", "익산", "정읍", "장성", "광주송정",
        "나주", "목포", "전주", "남원", "순천", "여천", "여수엑스포",
        # 강릉·중앙선 계열
        "청량리", "상봉", "양평", "만종", "횡성", "둔내", "평창", "진부", "강릉",
        "정동진", "안동", "영주", "제천",
        # 경전선 계열
        "마산", "창원", "창원중앙", "진주",
        # 기타 시·종착
        "행신",
    }
)

# 흔한 별칭/표기 → 코레일 표기. "역" 접미사는 별도 규칙으로 처리한다.
ALIASES: dict[str, str] = {
    "서울역": "서울",
    "서울station": "서울",
    "부산역": "부산",
    "동대구역": "동대구",
    "대전역": "대전",
    "광주": "광주송정",      # KTX는 광주송정 정차(광주역은 일반열차 위주)
    "여수": "여수엑스포",
    "여수엑스포역": "여수엑스포",
    "여수EXPO": "여수엑스포",
    "신경주": "경주",        # 2021 역명 개정(신경주→경주)
    "울산역": "울산",
    "통도사": "울산",        # 울산(통도사) 병기역
    "천안": "천안아산",      # KTX는 천안아산역(일반 천안역과 구분)
    "지제": "평택지제",      # 옛 SRT 표기(#1624 통합)
    "평택": "평택지제",
    "아산": "천안아산",
}

class StationNotFound(ValueError):
    """역명을 해석하지 못함. 가까운 후보를 함께 전달한다(REQ-009)."""

    def __init__(self, raw: str, candidates: list[str]):
        self.raw = raw
        self.candidates = candidates
        if candidates:
            hint = ", ".join(candidates)
            super().__init__(f"'{raw}' 역을 찾지 못했습니다. 혹시 이 역인가요? {hint}")
        else:
            super().__init__(
                f"'{raw}' 역을 찾지 못했습니다. 역명을 다시 확인해 주세요."
            )


def _strip_suffix(name: str) -> str:
    """끝의 '역' 접미사를 제거한다. 단 한 글자가 되면 원형 유지."""
    if len(name) > 2 and name.endswith("역"):
        return name[:-1]
    return name


def normalize_station(raw: str) -> str:
    """입력 역명을 코레일 표기로 정규화한다(REQ-009).

    Returns:
        정규화된 역명.

    Raises:
        StationNotFound: 해석 실패(가까운 후보 포함).
        ValueError: 빈 입력.
    """
    if raw is None or not str(raw).strip():
        raise ValueError("역명이 비어 있습니다.")

    # 공백 정리(내부 공백 제거)
    name = "".join(str(raw).split())

    # 1) 별칭 직접 매핑(원형 그대로 / '역' 포함형 모두 키로 둠)
    if name in ALIASES:
        return ALIASES[name]

    # 2) 이미 정식 표기
    if name in KNOWN_STATIONS:
        return name

    # 3) '역' 접미사 제거 후 재시도(별칭·정식 모두)
    stripped = _strip_suffix(name)
    if stripped in ALIASES:
        return ALIASES[stripped]
    if stripped in KNOWN_STATIONS:
        return stripped

    # 4) 유사 후보 제시(자동 교정하지 않고 사용자 확인 유도)
    pool = sorted(KNOWN_STATIONS | set(ALIASES.keys()))
    candidates = difflib.get_close_matches(stripped, pool, n=3, cutoff=0.6)
    # 별칭이 후보로 나오면 정식 표기로 환원
    resolved = []
    for c in candidates:
        target = ALIASES.get(c, c)
        if target not in resolved:
            resolved.append(target)
    raise StationNotFound(stripped, resolved)
