"""
키워드 스코어링 엔진

FR-003: 포화지수, 문서비율, KEI 계산
FR-004: S/A/B/C/D 등급 분류
"""
from __future__ import annotations

# 등급 순서 (낮을수록 나쁨)
GRADE_ORDER = ["S", "A", "B", "C", "D"]

# 등급 한국어 레이블
GRADE_LABELS: dict[str, str] = {
    "S": "블루키워드",
    "A": "유망 키워드",
    "B": "기회 있음",
    "C": "경쟁 치열",
    "D": "레드키워드",
}


def calculate_saturation_index(doc_count: int, monthly_volume: int) -> float:
    """포화지수 계산: (문서수 / 월간총검색량) × 100"""
    if monthly_volume == 0:
        return 0.0
    return (doc_count / monthly_volume) * 100


def calculate_doc_ratio(doc_count: int, monthly_volume: int) -> float:
    """문서비율 계산: 문서수 / 월간총검색량"""
    if monthly_volume == 0:
        return 0.0
    return doc_count / monthly_volume


def calculate_kei(monthly_volume: int, doc_count: int) -> float:
    """KEI 계산: (월간총검색량)² / 문서수"""
    if doc_count == 0:
        return 0.0
    return (monthly_volume ** 2) / doc_count


def calculate_total_monthly_volume(pc_volume: int, mobile_volume: int) -> int:
    """총 월간검색량 계산: PC + 모바일"""
    return pc_volume + mobile_volume


def _grade_from_saturation(saturation_index: float) -> str:
    """포화지수 기반 등급 결정"""
    if saturation_index < 10.0:
        return "S"
    elif saturation_index < 20.0:
        return "A"
    elif saturation_index < 40.0:
        return "B"
    elif saturation_index < 60.0:
        return "C"
    else:
        return "D"


def _grade_from_doc_ratio(doc_ratio: float) -> str:
    """문서비율 기반 등급 결정"""
    if doc_ratio < 0.5:
        return "S"
    elif doc_ratio < 1.0:
        return "A"
    elif doc_ratio < 1.5:
        return "B"
    elif doc_ratio < 3.0:
        return "C"
    else:
        return "D"


def classify_grade(saturation_index: float, doc_ratio: float) -> str:
    """등급 분류: 포화지수와 문서비율 불일치 시 낮은(보수적) 등급 사용"""
    grade_sat = _grade_from_saturation(saturation_index)
    grade_doc = _grade_from_doc_ratio(doc_ratio)

    # GRADE_ORDER에서 인덱스가 높을수록 낮은 등급
    idx_sat = GRADE_ORDER.index(grade_sat)
    idx_doc = GRADE_ORDER.index(grade_doc)

    # 더 낮은 등급(보수적) 선택
    return GRADE_ORDER[max(idx_sat, idx_doc)]


def get_grade_label(grade: str) -> str:
    """등급 한국어 레이블 반환"""
    return GRADE_LABELS.get(grade, "알 수 없음")


def score_keyword(
    keyword: str,
    monthly_pc: int,
    monthly_mobile: int,
    doc_count: int,
) -> dict:
    """키워드 종합 스코어링

    Args:
        keyword: 키워드 텍스트
        monthly_pc: 월간 PC 검색량 (< 10 경우 5로 대체 완료된 값)
        monthly_mobile: 월간 모바일 검색량 (< 10 경우 5로 대체 완료된 값)
        doc_count: 블로그 문서수

    Returns:
        스코어링 결과 딕셔너리
    """
    monthly_volume = calculate_total_monthly_volume(monthly_pc, monthly_mobile)
    saturation_index = calculate_saturation_index(doc_count, monthly_volume)
    doc_ratio = calculate_doc_ratio(doc_count, monthly_volume)
    kei = calculate_kei(monthly_volume, doc_count)
    grade = classify_grade(saturation_index, doc_ratio)
    grade_label = get_grade_label(grade)

    return {
        "keyword": keyword,
        "monthly_volume": monthly_volume,
        "monthly_pc": monthly_pc,
        "monthly_mobile": monthly_mobile,
        "doc_count": doc_count,
        "saturation_index": round(saturation_index, 2),
        "doc_ratio": round(doc_ratio, 4),
        "kei": round(kei, 2),
        "grade": grade,
        "grade_label": grade_label,
    }


def filter_keywords(
    keywords: list[dict],
    min_volume: int = 500,
    min_grade: str = "B",
) -> list[dict]:
    """키워드 필터링: 최소 검색량 및 최소 등급 기준

    Args:
        keywords: 스코어링된 키워드 목록
        min_volume: 최소 월간 검색량 (기본값 500)
        min_grade: 최소 등급 (기본값 B)

    Returns:
        필터링된 키워드 목록 (KEI 내림차순 정렬)
    """
    min_grade_idx = GRADE_ORDER.index(min_grade) if min_grade in GRADE_ORDER else len(GRADE_ORDER) - 1

    filtered = [
        kw for kw in keywords
        if kw.get("monthly_volume", 0) >= min_volume
        and GRADE_ORDER.index(kw.get("grade", "D")) <= min_grade_idx
    ]

    # KEI 내림차순 정렬
    filtered.sort(key=lambda x: x.get("kei", 0), reverse=True)
    return filtered
