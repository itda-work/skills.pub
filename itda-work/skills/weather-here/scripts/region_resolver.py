"""region_resolver.py — 지역명 → (lat, lon, 표시명) 결정 (REQ-003/012/017).

v0.4.0 변경: 반환을 (nx, ny, 표시명) → **(lat, lon, 표시명)**으로 정정.
  Open-Meteo는 위경도 직접 사용 — nx/ny(KMA 격자) 불요.
  kma_points 행의 lat/lon 컬럼 사용.

§4.6.1 이름 정규화 알고리즘:
  1. 입력 전처리(NFC·소문자·공백 정규화)
  2. 17 시·도 약칭 → 정식명 별칭
  3. 한·영 큐레이션 별칭(전수 자동화 금지, YAGNI)
  4. 매칭 우선순위: l1 정확 일치 → l2 정확 일치 → prefix 집계
  5. 일반구 대표점: l2 사전순(코드포인트) 첫 행

네트워크 호출 0. kma_points.POINTS 직접 참조.
"""
from __future__ import annotations

import unicodedata

import kma_points

# --- §4.6.1.2 : 17 시·도 약칭 → 정식명 ---
_SIDO_ALIAS: dict[str, str] = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}

# --- §4.6.1.3 : 한·영 큐레이션 별칭 (확정 범위) ---
# 정식명 또는 prefix("수원") 매핑.
_EN_ALIAS: dict[str, str] = {
    "seoul": "서울특별시",
    "busan": "부산광역시",
    "pusan": "부산광역시",
    "incheon": "인천광역시",
    "daegu": "대구광역시",
    "daejeon": "대전광역시",
    "gwangju": "광주광역시",
    "ulsan": "울산광역시",
    "sejong": "세종특별자치시",
    "jeju": "제주특별자치도",
    # 일반구 보유 시 — prefix 집계로 이어지도록 약칭 형태 매핑
    "suwon": "수원",
    "seongnam": "성남",
    "goyang": "고양",
    "yongin": "용인",
    "changwon": "창원",
    "cheongju": "청주",
    "jeonju": "전주",
    "pohang": "포항",
    "cheonan": "천안",
}


def _normalize(name: str) -> str:
    """입력 전처리: NFC · 소문자 · 공백 정규화."""
    name = unicodedata.normalize("NFC", name)
    name = name.strip().lower()
    # 내부 연속 공백 → 단일 공백 (re 미사용: stdlib only 정책 REQ-009)
    name = " ".join(name.split())
    return name


def _label(row: dict) -> str:
    """표시용 지역 라벨(l1 + l2)."""
    if row["l2"]:
        return f"{row['l1']} {row['l2']}"
    return row["l1"]


def resolve(place: str) -> tuple[float, float, str] | None:
    """지역명을 정규화하여 위경도(lat, lon)와 표시 지역명을 반환한다.

    v0.4.0: (nx, ny, 표시명) → **(lat, lon, 표시명)** 으로 반환 정정.
    Open-Meteo는 위경도를 직접 사용하므로 KMA 격자(nx,ny) 불요.

    §4.6.1 매칭 우선순위:
      a. l1 정식명 정확 일치 → 시·도 대표행(l2='') 사용.
      b. l2 시군구명 정확 일치 → 그 행 사용.
      c. l2 prefix 집계(일반구 보유 시·군) → l2 사전순 첫 행 대표점.
      d. 위 모두 실패 → None(graceful, 예외 없음).

    Args:
        place: 사용자 입력 지역명(한국어 또는 영문 큐레이션 별칭).

    Returns:
        (lat, lon, 표시지역명) 또는 None.
    """
    if not place:
        return None

    raw = _normalize(place)
    if not raw:
        return None

    # --- 별칭 확장: 영문 → 한국어 ---
    if raw in _EN_ALIAS:
        raw = _normalize(_EN_ALIAS[raw])

    # --- 별칭 확장: 시·도 약칭 → 정식명 ---
    sido_alias_lower = {k.lower(): v for k, v in _SIDO_ALIAS.items()}
    if raw in sido_alias_lower:
        raw = _normalize(sido_alias_lower[raw])

    # --- 매칭 우선순위 a: l1 정식명 정확 일치 → 시·도 대표행(l2='') ---
    raw_nfc = unicodedata.normalize("NFC", raw)
    for row in kma_points.POINTS:
        l1_norm = unicodedata.normalize("NFC", row["l1"].lower())
        if l1_norm == raw_nfc and row["l2"] == "":
            return float(row["lat"]), float(row["lon"]), _label(row)

    # --- 매칭 우선순위 b: l2 시군구명 정확 일치 ---
    for row in kma_points.POINTS:
        l2_norm = unicodedata.normalize("NFC", row["l2"].lower())
        if l2_norm == raw_nfc and row["l2"]:
            return float(row["lat"]), float(row["lon"]), _label(row)

    # --- 매칭 우선순위 c: l2 prefix 집계 (일반구 보유 시·군) ---
    candidates = _prefix_match(raw_nfc)
    if candidates:
        # l2 사전순(코드포인트) 첫 행 — §4.6.1.5 대표점 선택 규칙
        rep = sorted(candidates, key=lambda r: r["l2"])[0]
        return float(rep["lat"]), float(rep["lon"]), _label(rep)

    # --- d: 실패 → None ---
    return None


def _prefix_match(raw: str) -> list[dict]:
    """l2가 raw 또는 raw+'시' 로 시작하는 행 집계."""
    result: list[dict] = []
    # 시도 이름을 제외하고 l2 prefix만 체크
    prefixes = [raw]
    if not raw.endswith("시"):
        prefixes.append(raw + "시")

    for row in kma_points.POINTS:
        if not row["l2"]:
            continue
        l2_norm = unicodedata.normalize("NFC", row["l2"].lower())
        for prefix in prefixes:
            if l2_norm.startswith(prefix):
                result.append(row)
                break

    return result
