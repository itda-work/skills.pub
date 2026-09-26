"""한국은행 ECOS OpenAPI 클라이언트.

제안서/사업계획서에 필요한 거시경제 지표 수집:
    - 100대 주요 경제지표 (KeyStatisticList)
    - 통계 데이터 조회 (StatisticSearch)
    - 통계표 목록 (StatisticTableList)
    - 세부항목 목록 (StatisticItemList)

엔드포인트: https://ecos.bok.or.kr/api/
인증: PATH 기반 (URL 경로에 인증키 포함)
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_BASE_URL = "https://ecos.bok.or.kr/api"
_TIMEOUT = 15

# 활용신청 페이지 — 인증키 관련 오류 시 사용자에게 자동 부착
_ECOS_APPLY_URL = "https://ecos.bok.or.kr/api/"

_ECOS_SETUP_GUIDE = (
    "\n[설정 안내] ECOS_API_KEY를 확인하세요:\n"
    f"  1. {_ECOS_APPLY_URL} 접속 → 회원가입 → 인증키 신청\n"
    "  2. 인증키 즉시 발급 (가입 시 자동 부여)\n"
    "  3. 작업 폴더 루트(예: outputs/)에 .env 파일로 설정:\n"
    "       ECOS_API_KEY=발급받은_키\n"
    "  4. 첫 호출 실패 시 점검 절차:\n"
    "     - 키 문자열 정확성 확인 (앞뒤 공백 제거)\n"
    "     - URL 인코딩 이슈는 본 스크립트에서 자동 처리됨\n"
    "     - 잠시(수 분) 후 재시도 — 발급 직후 일시적 미반영 가능\n"
)

# 정본 에러 코드 매핑 (출처: 한국은행 ECOS API개발명세서 6종 공통)
# references/ecos-매뉴얼/README.md 참조
# 키 형식: "{TYPE}-{CODE}" (TYPE = INFO | ERROR)
_ERROR_CODE_HINTS: dict[str, dict[str, Any]] = {
    "INFO-100": {"desc": "인증키가 유효하지 않습니다", "category": "setup", "needs_apply_url": True},
    "INFO-200": {"desc": "해당하는 데이터가 없습니다", "category": "data", "needs_apply_url": False},
    "ERROR-100": {"desc": "필수 값이 누락되어 있습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-101": {"desc": "주기와 다른 형식의 날짜 형식입니다", "category": "setup", "needs_apply_url": False},
    "ERROR-200": {"desc": "파일타입 값이 누락 혹은 유효하지 않습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-300": {"desc": "조회건수 값이 누락되어 있습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-301": {"desc": "조회건수 값의 타입이 유효하지 않습니다 (정수 입력)", "category": "setup", "needs_apply_url": False},
    "ERROR-400": {"desc": "검색범위 초과 (60초 TIMEOUT)", "category": "transient", "needs_apply_url": False},
    "ERROR-500": {"desc": "서버 오류 (해당 서비스를 찾을 수 없음)", "category": "transient", "needs_apply_url": False},
    "ERROR-600": {"desc": "DB Connection 오류", "category": "transient", "needs_apply_url": False},
    "ERROR-601": {"desc": "SQL 오류", "category": "transient", "needs_apply_url": False},
    "ERROR-602": {"desc": "과도한 OpenAPI 호출로 이용 제한", "category": "transient", "needs_apply_url": False},
}

# 주기 코드
PERIOD_CODES = {
    "year": "A",
    "semi": "S",
    "quarter": "Q",
    "month": "M",
    "day": "D",
}


def _classify_ecos_error(error_code: str) -> tuple[str, str]:
    """ECOS API 오류 코드를 사용자 메시지와 카테고리로 분류.

    정본 매핑(_ERROR_CODE_HINTS)에서 한글 설명을 가져오고, 인증키 관련
    오류(INFO-100)는 활용신청 URL을 자동 부착한다.

    Args:
        error_code: ECOS API CODE 값 (예: "INFO-100", "ERROR-602").

    Returns:
        (사용자 메시지, 카테고리) 튜플.
        카테고리: "setup" | "transient" | "data" | "general"
    """
    hint = _ERROR_CODE_HINTS.get(error_code)
    if hint is None:
        return (
            f"ECOS API 오류 (코드: {error_code}) — 요청 파라미터 또는 서버 상태를 확인하세요.",
            "general",
        )

    if error_code == "INFO-100":
        return (
            f"인증키 무효 ({error_code}, {hint['desc']}){_ECOS_SETUP_GUIDE}",
            "setup",
        )
    if error_code == "ERROR-602":
        return (
            f"{hint['desc']} ({error_code}) — 잠시 후 재시도하세요.",
            hint["category"],
        )
    if error_code == "ERROR-400":
        return (
            f"{hint['desc']} ({error_code}) — 검색 범위를 줄여서 다시 시도하세요.",
            hint["category"],
        )
    if error_code == "ERROR-101":
        return (
            f"{hint['desc']} ({error_code}) — 주기/날짜 형식 확인 (A:2024, Q:2024Q1, M:202401, D:20240101)",
            hint["category"],
        )

    suffix = f" — 활용신청 URL: {_ECOS_APPLY_URL}" if hint["needs_apply_url"] else ""
    return (
        f"ECOS API 오류 ({error_code}, {hint['desc']}){suffix}",
        hint["category"],
    )

class ECOSAPIError(Exception):
    """ECOS API 호출 오류."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


def _build_url(*segments: str) -> str:
    """PATH 기반 URL 생성.

    ECOS API는 쿼리 파라미터가 아닌 경로(path) 기반으로 파라미터를 전달.
    한글 검색어(StatisticWord의 단어 등) 비-ASCII 세그먼트는 percent-encoding
    해야 한다. encode 없이 전송하면 urllib이 'ascii' codec UnicodeEncodeError로
    실패한다 (라이브 검증: word --word "GDP디플레이터" 크래시, 2026-06-09).

    Args:
        segments: URL 경로 세그먼트.

    Returns:
        완성된 URL (trailing slash 포함, 각 세그먼트 percent-encoded).
    """
    encoded = [urllib.parse.quote(str(s), safe="") for s in segments]
    return _BASE_URL + "/" + "/".join(encoded) + "/"


def _request(url: str) -> dict[str, Any]:
    """ECOS API 호출.

    Args:
        url: 전체 URL.

    Returns:
        파싱된 JSON 응답.

    Raises:
        ECOSAPIError: 네트워크 오류, 파싱 실패, API 오류.
    """
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        # @MX:NOTE: HTTP 403은 게이트웨이 단계 권한 거부 — 활용신청 안내 부착.
        if exc.code == 403:
            raise ECOSAPIError(
                f"권한 거부 (HTTP 403) — 활용신청이 필요할 수 있습니다."
                f"{_ECOS_SETUP_GUIDE}",
                error_code="HTTP_403",
            ) from exc
        raise ECOSAPIError(f"네트워크 오류: {exc}") from exc
    except urllib.error.URLError as exc:
        raise ECOSAPIError(f"네트워크 오류: {exc}") from exc

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ECOSAPIError(f"JSON 파싱 실패: {exc}") from exc

    # 에러 응답 확인 — 정본 한글 hint + 활용신청 URL 자동 부착
    if "RESULT" in data:
        code = data["RESULT"].get("CODE", "")
        msg = data["RESULT"].get("MESSAGE", "알 수 없는 오류")

        # INFO-200: 데이터 없음 (에러가 아닌 정상 응답)
        if code == "INFO-200":
            return {"_empty": True, "_message": msg}

        # 그 외 모든 INFO/ERROR 코드는 _classify_ecos_error로 처리
        hint_msg, _category = _classify_ecos_error(code)
        raise ECOSAPIError(
            f"{hint_msg} | 원본 메시지: {msg}",
            error_code=code,
        )

    return data


# @MX:ANCHOR: [AUTO] ECOS 100대 주요 경제지표 조회 함수.
# @MX:REASON: fan_in >= 3 (collect_econ의 key/search 서브커맨드); 핵심 경제지표 진입점.
def get_key_statistics(
    api_key: str,
    start: int = 1,
    end: int = 200,
) -> list[dict[str, Any]]:
    """100대 주요 경제지표 조회.

    한국은행이 선정한 핵심 경제지표를 한번에 조회. 제안서에서 경제 환경 개요에 유용.

    Args:
        api_key: ECOS 인증키.
        start: 시작 건수 (기본 1).
        end: 종료 건수 (기본 200).

    Returns:
        주요 지표 목록. 각 항목:
        {CLASS_NAME, KEYSTAT_NAME, DATA_VALUE, CYCLE, UNIT_NAME}
    """
    url = _build_url("KeyStatisticList", api_key, "json", "kr", start, end)
    data = _request(url)

    if data.get("_empty"):
        return []

    return data.get("KeyStatisticList", {}).get("row", [])


def search_statistics(
    api_key: str,
    stat_code: str,
    period: str,
    start_date: str,
    end_date: str,
    item_code1: str = "",
    item_code2: str = "",
    item_code3: str = "",
    item_code4: str = "",
    start: int = 1,
    end: int = 1000,
) -> list[dict[str, Any]]:
    """통계 데이터 조회 (StatisticSearch).

    Args:
        api_key: ECOS 인증키.
        stat_code: 통계표코드 (예: "901Y009").
        period: 주기 ("A", "Q", "M", "D").
        start_date: 시작일 (주기에 맞는 형식).
        end_date: 종료일.
        item_code1~4: 항목코드 (선택).
        start: 시작 건수.
        end: 종료 건수 (최대 10000).

    Returns:
        통계 데이터 목록. 각 항목:
        {STAT_CODE, STAT_NAME, ITEM_CODE1, ITEM_NAME1, UNIT_NAME, TIME, DATA_VALUE}
    """
    # PATH 세그먼트 구성
    segments = [
        "StatisticSearch", api_key, "json", "kr",
        str(start), str(end),
        stat_code, period, start_date, end_date,
    ]

    # 항목코드 추가 (빈 문자열이면 생략하되, 중간 코드가 있으면 이전 것도 포함)
    codes = [item_code1, item_code2, item_code3, item_code4]
    # 마지막 비어있지 않은 코드까지만 포함
    last_idx = -1
    for i, code in enumerate(codes):
        if code:
            last_idx = i
    if last_idx >= 0:
        for i in range(last_idx + 1):
            segments.append(codes[i] or "")

    url = _build_url(*segments)
    data = _request(url)

    if data.get("_empty"):
        return []

    return data.get("StatisticSearch", {}).get("row", [])


def get_table_list(
    api_key: str,
    start: int = 1,
    end: int = 1000,
) -> list[dict[str, Any]]:
    """통계표 목록 조회.

    Args:
        api_key: ECOS 인증키.
        start: 시작 건수.
        end: 종료 건수.

    Returns:
        통계표 목록. 각 항목:
        {STAT_CODE, STAT_NAME, CYCLE, ORG_NAME}
    """
    url = _build_url("StatisticTableList", api_key, "json", "kr", start, end)
    data = _request(url)

    if data.get("_empty"):
        return []

    return data.get("StatisticTableList", {}).get("row", [])


def get_item_list(
    api_key: str,
    stat_code: str,
    start: int = 1,
    end: int = 500,
) -> list[dict[str, Any]]:
    """통계표 세부항목 목록 조회.

    Args:
        api_key: ECOS 인증키.
        stat_code: 통계표코드.
        start: 시작 건수.
        end: 종료 건수.

    Returns:
        항목 목록. 각 항목:
        {STAT_CODE, STAT_NAME, GRP_CODE, GRP_NAME, ITEM_CODE, ITEM_NAME, CYCLE}
    """
    url = _build_url("StatisticItemList", api_key, "json", "kr", start, end, stat_code)
    data = _request(url)

    if data.get("_empty"):
        return []

    return data.get("StatisticItemList", {}).get("row", [])


def search_word(
    api_key: str,
    word: str,
    start: int = 1,
    end: int = 20,
) -> list[dict[str, Any]]:
    """통계용어사전 검색.

    경제/통계 용어의 공식 정의를 조회. 제안서에서 용어 설명 인용에 유용.

    Args:
        api_key: ECOS 인증키.
        word: 검색할 용어 (예: "소비자동향지수", "GDP디플레이터").
        start: 시작 건수.
        end: 종료 건수.

    Returns:
        용어 목록. 각 항목: {WORD, CONTENT}
    """
    url = _build_url("StatisticWord", api_key, "json", "kr", start, end, word)
    data = _request(url)

    if data.get("_empty"):
        return []

    return data.get("StatisticWord", {}).get("row", [])


def parse_value(val_str: str) -> float | None:
    """DATA_VALUE 문자열을 숫자로 변환.

    Args:
        val_str: DATA_VALUE 필드 값.

    Returns:
        숫자 값, 또는 None.
    """
    if not val_str or val_str.strip() in ("-", "", "…", "x", "X", "*"):
        return None
    try:
        return float(val_str.replace(",", ""))
    except ValueError:
        return None


def summarize_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """통계 데이터를 제안서용 요약 형태로 정리.

    Args:
        rows: search_statistics()의 반환값.

    Returns:
        정리된 데이터: [{time, stat_name, item_name, value, unit}, ...]
    """
    results: list[dict[str, Any]] = []

    for row in rows:
        value = parse_value(row.get("DATA_VALUE", ""))
        if value is None:
            continue

        results.append({
            "time": row.get("TIME", ""),
            "stat_code": row.get("STAT_CODE", ""),
            "stat_name": row.get("STAT_NAME", ""),
            "item_name": row.get("ITEM_NAME1", ""),
            "item_name2": row.get("ITEM_NAME2", ""),
            "value": value,
            "unit": row.get("UNIT_NAME", ""),
        })

    return results
