"""국토교통부·공공데이터포털 XML API 공통 HTTP 클라이언트.

dart_api.py(153-222 재시도·225+ 바이너리·262-314 캐시)와
realestate_api.py(420-478 XML 파싱·_SUCCESS_CODES·_ERROR_CODE_HINTS·_APPLY_URL)
패턴을 통합한 소스 중립 HTTP 클라이언트.

설계 원칙:
    - source-provider 인터페이스: URL·파라미터를 인자로 받아 소스 종속성 없음
      (향후 미국 데이터 소스 교체 가능 — §6 US 확장 훅).
    - stdlib only: urllib, xml.etree.ElementTree, json, zipfile (외부 의존 없음).
    - 지수 백오프 재시도: 5xx·한도초과(resultCode 22)·HTTP 403 처리.
    - 파일 캐시: 요청 결과를 선택적으로 디스크 캐시에 저장/로드.

공개 API:
    RealEstateAPIError   -- 이 모듈의 예외 기반 클래스
    _parse_xml           -- XML bytes → dict (total_count/items/page)
    fetch_xml            -- URL + params → 단일 페이지 dict (재시도 포함)
    fetch_all_pages      -- URL + params → 전 페이지 items 리스트
    parse_amount         -- 금액 문자열 → int(만원)
    compute_summary      -- items → 통계(avg/median/max/min/count)
"""
from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

_TIMEOUT = 15  # HTTP 요청 타임아웃(초)
_RETRY_BACKOFFS = (1, 2)  # 지수 백오프: 1s, 2s (최대 2회 재시도)

# data.go.kr 공공데이터포털 공통 성공 응답 코드
_SUCCESS_CODES = {"000", "00", "0000"}

# PDF II장 OPEN API 에러 코드 매핑 (코드 → (의미, 조치))
_ERROR_CODE_HINTS: dict[str, tuple[str, str]] = {
    "01": ("Application Error", "서비스 제공기관 관리자 문의"),
    "02": ("DB Error", "서비스 제공기관 관리자 문의"),
    "03": ("No Data", "데이터 없음 -- 다른 년월/지역으로 재시도"),
    "04": ("HTTP Error", "서비스 제공기관 관리자 문의"),
    "05": ("Service Time Out", "잠시 후 재시도"),
    "10": ("잘못된 요청 파라미터", "ServiceKey 파라미터 누락 -- URL 확인"),
    "11": ("필수 요청 파라미터 누락", "기술문서 확인"),
    "12": ("해당 OpenAPI 서비스 없음/폐기", "활용신청한 API URL 재확인"),
    "20": (
        "서비스 접근 거부 (활용 미승인)",
        "마이페이지 활용신청 승인 상태 확인 -- 자동승인이라도 게이트웨이 동기화에 5~30분 소요",
    ),
    "22": ("일일 트래픽 초과", "활용신청 상세에서 일일 트래픽 한도 확인 또는 변경신청"),
    "30": (
        "등록되지 않은 서비스키",
        "마이페이지에서 발급받은 일반 인증키(Decoding) 재확인 -- URL 인코딩 누락 가능성",
    ),
    "31": ("기간 만료된 서비스키", "활용연장신청 후 재시도"),
    "32": ("등록되지 않은 도메인/IP", "활용신청정보의 도메인·IP 변경신청"),
}

# 재시도 대상 에러코드 (일시적 오류)
_RETRYABLE_RESULT_CODES = {"22"}


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class RealEstateAPIError(Exception):
    """공공데이터 API 호출 오류."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


# ---------------------------------------------------------------------------
# XML 파싱
# ---------------------------------------------------------------------------

def _parse_xml(
    xml_bytes: bytes,
    service_key: str | None = None,
    apply_url: str | None = None,
) -> dict[str, Any]:
    """공공데이터 API XML 응답을 파싱한다.

    realestate_api.py 420-478 패턴 포팅.
    _SUCCESS_CODES / _ERROR_CODE_HINTS / apply_url 권한 오류 안내 포함.

    Args:
        xml_bytes: API 응답 XML 바이트.
        service_key: 서비스 식별자 (선택, 로깅용).
        apply_url: 권한 오류(resultCode 20/30) 시 안내할 활용신청 URL.

    Returns:
        {"total_count": N, "items": [...], "page": N} 딕셔너리.

    Raises:
        RealEstateAPIError: resultCode가 성공 코드가 아닌 경우, XML 파싱 실패.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise RealEstateAPIError(f"XML 파싱 실패: {exc}") from exc

    # 에러 코드 확인
    header = root.find("header")
    if header is not None:
        result_code = (header.findtext("resultCode") or "").strip()
        if result_code and result_code not in _SUCCESS_CODES:
            result_msg = header.findtext("resultMsg") or "오류"
            hint = _ERROR_CODE_HINTS.get(result_code)
            if hint:
                meaning, action = hint
                detail = (
                    f"API 오류 (resultCode={result_code}): {result_msg}"
                    f" -- {meaning}. 조치: {action}"
                )
            else:
                detail = f"API 오류 (resultCode={result_code}): {result_msg}"
            # 권한 관련 코드에는 활용신청 URL 부착
            if result_code in {"20", "30"} and apply_url:
                detail += f" 활용신청: {apply_url}"
            raise RealEstateAPIError(detail, error_code=result_code)

    body = root.find("body")
    if body is None:
        return {"total_count": 0, "items": [], "page": 1}

    total_count_el = body.find("totalCount")
    total_count = int(total_count_el.text or "0") if total_count_el is not None else 0

    page_no_el = body.find("pageNo")
    page_no = int(page_no_el.text or "1") if page_no_el is not None else 1

    items_el = body.find("items")
    items: list[dict[str, str]] = []
    if items_el is not None:
        for item_el in items_el.findall("item"):
            item: dict[str, str] = {}
            for child in item_el:
                item[child.tag] = (child.text or "").strip()
            items.append(item)

    return {"total_count": total_count, "items": items, "page": page_no}


def parse_response_xml(
    xml_bytes: bytes,
    service_key: str | None = None,
    apply_url: str | None = None,
) -> dict[str, Any]:
    """저장된 응답 XML 바이트를 파싱하는 공개 진입점 (#1707).

    itda-hyve 의 ``http_request`` 가 ``save_as`` 로 저장한 응답 파일을 스킬 스크립트가
    ``--input`` 으로 읽을 때 쓴다. 판정·구조는 _parse_xml 과 같다(같은 함수를 노출).
    """
    return _parse_xml(xml_bytes, service_key=service_key, apply_url=apply_url)


# ---------------------------------------------------------------------------
# HTTP 클라이언트 (지수 백오프 재시도)
# ---------------------------------------------------------------------------

def _is_retryable_http(exc: urllib.error.HTTPError) -> bool:
    """재시도 대상 HTTP 오류 여부 판정 (5xx만 재시도, 4xx 즉시 실패)."""
    return exc.code >= 500


# @MX:ANCHOR: [AUTO] data.go.kr XML API 공통 핵심 호출 함수 -- 모든 부동산 스킬이 의존.
# @MX:REASON: fan_in >= 3 (realty-deals, realty-supply, realty-price-stats 등);
#             재시도/캐시/에러코드 처리가 이 함수의 계약임.
def fetch_xml(
    url: str,
    params: dict[str, str],
    *,
    apply_url: str | None = None,
    cache_path: str | Path | None = None,
) -> dict[str, Any]:
    """data.go.kr XML 엔드포인트를 호출하고 결과를 반환한다.

    dart_api.py 153-222 재시도 패턴 + realestate_api.py 420-478 XML 파싱 통합.

    재시도 정책:
        - HTTP 5xx: 지수 백오프(1s, 2s)로 최대 2회 재시도.
        - HTTP 403: 활용신청 안내 포함 즉시 RealEstateAPIError 발생.
        - resultCode 22(트래픽 초과): 재시도 대상.

    캐시 정책:
        - cache_path가 지정되면 결과 XML bytes를 파일에 저장/로드.
        - 기존 캐시가 있으면 네트워크 호출 없이 캐시에서 반환.

    Args:
        url: 호출 대상 URL (쿼리스트링 없이).
        params: 쿼리 파라미터 딕셔너리 (serviceKey, LAWD_CD, DEAL_YMD 등).
        apply_url: 권한 오류(HTTP 403, resultCode 20/30) 시 안내할 활용신청 URL.
        cache_path: 응답 XML을 캐시할 파일 경로 (None이면 캐시 없음).

    Returns:
        {"total_count": N, "items": [...], "page": N}

    Raises:
        RealEstateAPIError: 네트워크 오류, API 에러 응답, XML 파싱 실패.
    """
    # 캐시 우선 로드 (dart_api.py 262-314 패턴)
    if cache_path:
        cache_file = Path(cache_path)
        if cache_file.exists():
            return _parse_xml(cache_file.read_bytes(), apply_url=apply_url)

    # URL 구성
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"

    last_exc: RealEstateAPIError | None = None
    attempts = [(0,)] + [(b,) for b in _RETRY_BACKOFFS]

    for attempt_idx, _ in enumerate(attempts):
        if attempt_idx > 0:
            wait = _RETRY_BACKOFFS[attempt_idx - 1]
            time.sleep(wait)

        try:
            with urllib.request.urlopen(full_url, timeout=_TIMEOUT) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                detail = "권한 거부 (HTTP 403) -- 활용신청이 필요합니다."
                if apply_url:
                    detail += f" 활용신청: {apply_url} (자동승인이라도 동기화에 5~30분 소요)"
                raise RealEstateAPIError(detail, error_code="HTTP_403") from exc
            if _is_retryable_http(exc):
                last_exc = RealEstateAPIError(f"네트워크 오류 (HTTP {exc.code}): {exc.reason}")
                continue
            raise RealEstateAPIError(f"네트워크 오류: HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            last_exc = RealEstateAPIError(f"네트워크 오류: {exc}")
            continue

        # XML 파싱 (resultCode 22 재시도)
        try:
            result = _parse_xml(raw, apply_url=apply_url)
        except RealEstateAPIError as exc:
            if exc.error_code in _RETRYABLE_RESULT_CODES:
                last_exc = exc
                continue
            raise

        # 성공 -- 캐시 저장
        if cache_path:
            cache_file = Path(cache_path)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(raw)

        return result

    # 모든 시도 소진
    if last_exc:
        raise last_exc
    raise RealEstateAPIError("알 수 없는 오류로 요청 실패")


# ---------------------------------------------------------------------------
# 전 페이지네이션 수집
# ---------------------------------------------------------------------------

def fetch_all_pages(
    url: str,
    params: dict[str, str],
    *,
    rows_per_page: int = 100,
    apply_url: str | None = None,
) -> list[dict[str, str]]:
    """totalCount 전량이 수집될 때까지 페이지를 반복 요청한다.

    기존 collect_realestate.py cmd_trade(103-107)의 page=1 단일 호출 버그를
    교정한 함수. totalCount > numOfRows인 경우에도 절단 없이 전량 수집한다.

    Args:
        url: 호출 대상 URL.
        params: 쿼리 파라미터 (serviceKey, LAWD_CD, DEAL_YMD 등).
                pageNo / numOfRows는 이 함수가 자동 관리한다.
        rows_per_page: 페이지당 행 수 (기본 100).
        apply_url: 권한 오류 안내 URL.

    Returns:
        전 페이지에서 수집된 items 리스트.

    Raises:
        RealEstateAPIError: 첫 페이지 호출 실패 시.
    """
    all_items: list[dict[str, str]] = []
    page = 1

    while True:
        page_params = dict(params)
        page_params["pageNo"] = str(page)
        page_params["numOfRows"] = str(rows_per_page)

        result = fetch_xml(url, page_params, apply_url=apply_url)
        all_items.extend(result["items"])

        total_count = result["total_count"]
        fetched_so_far = len(all_items)

        # 전량 수집 완료 조건
        if fetched_so_far >= total_count or not result["items"]:
            break

        page += 1

    return all_items


# ---------------------------------------------------------------------------
# 통계 유틸리티 (realestate_api.py 481-529 포팅)
# ---------------------------------------------------------------------------

def parse_amount(val: str) -> int:
    """금액 문자열을 정수(만원 단위)로 변환.

    Args:
        val: 금액 문자열 (예: "115,000", "85500", "-", "").

    Returns:
        정수 금액. 빈 문자열이나 '-'는 0 반환.
    """
    if not val or val.strip() == "-":
        return 0
    try:
        return int(val.replace(",", "").strip())
    except ValueError:
        return 0


def compute_summary(
    items: list[dict[str, Any]],
    amount_field: str = "dealAmount",
) -> dict[str, Any]:
    """거래 목록에서 요약 통계를 계산한다.

    realestate_api.py compute_summary(498-529) 포팅.

    Args:
        items: 거래 항목 목록.
        amount_field: 금액 필드명 (매매: "dealAmount", 전세: "deposit").

    Returns:
        {"avg": N, "median": N, "max": N, "min": N, "count": N}
    """
    if not items:
        return {"avg": 0, "median": 0, "max": 0, "min": 0, "count": 0}

    amounts = sorted(parse_amount(item.get(amount_field, "0")) for item in items)
    n = len(amounts)
    total = sum(amounts)
    avg = total // n

    mid = n // 2
    if n % 2 == 1:
        median = amounts[mid]
    else:
        median = (amounts[mid - 1] + amounts[mid]) // 2

    return {
        "avg": avg,
        "median": median,
        "max": amounts[-1],
        "min": amounts[0],
        "count": n,
    }
