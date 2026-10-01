"""국토교통부·공공데이터포털(data.go.kr) XML 응답 파서 — 네트워크 없음.

요청은 itda-hyve 의 ``http_request`` 가 보내고 ``save_as`` 로 파일에 저장한다
(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``). 이 모듈은 그 파일의 바이트를
읽어 판정·파싱만 한다 — 소켓을 여는 코드(구 ``fetch_xml``·``fetch_all_pages``)는 지웠다.
재시도는 itda-hyve 가 하고, 페이지 순회는 SKILL.md 가 모델에게 지시한다.

판정 (조용히 0건으로 접지 않는다):
    - ``<response>`` + ``header/resultCode`` 가 성공 코드(000·00·0000)일 때만 성공.
    - 그 밖의 resultCode, 게이트웨이 오류(``<OpenAPI_ServiceResponse>``), 루트가 다른 XML,
      XML 이 아닌 본문(HTTP 오류 페이지가 저장된 경우), 닫히지 않은 XML(절단)은 전부
      ``RealEstateAPIError``.
    - 성공 코드인데 ``<body>`` 가 없거나 ``totalCount``·``pageNo``·``numOfRows`` 가 숫자가 아니면
      ``NOT_RESPONSE``·``BAD_XML`` — 0건 성공으로 접지 않는다.
    - 입력이 itda-hyve 응답 JSON(모델이 http_request 결과나 batch 실패를 파일로 쓴 경우)이면
      ``error`` · HTTP 4xx/5xx · ``body_truncated`` 를 각각 명시 오류로 낸다. 이 hyve 층 판독은
      공용 ``hyve_input``(루트 ``shared/``)이 하고, 여기서는 그 예외를 error_code 계약
      (``HYVE_<code>``·``HTTP_<n>``·``TRUNCATED``·``NOT_XML``)으로 옮긴다. hyve 실패 자리는
      ``kind="hyve"`` 라 CLI 가 ``error: hyve`` 로 낸다(ecos·g2b 와 같은 분류).

공개 API:
    RealEstateAPIError   -- 이 모듈의 예외 기반 클래스(error_code 보유)
    parse_response_xml   -- 저장된 응답 파일 바이트 → {"total_count", "items", "page", "num_of_rows"}
    error_fields         -- RealEstateAPIError → CLI 오류 JSON 의 ``error``·``code``
    parse_amount         -- 금액 문자열 → int(만원)
    compute_summary      -- items → 통계(avg/median/max/min/count)
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from hyve_input import (
    HyveFailure,
    HyveHTTPError,
    HyveInputError,
    HyveTruncatedError,
    snippet,
    unwrap,
)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

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
    "22": (
        "일일 트래픽 초과",
        "활용신청 상세에서 일일 트래픽 한도 확인 또는 변경신청 -- 이어서 부르지 말고 멈춘다",
    ),
    "30": (
        "등록되지 않은 서비스키",
        "itda-hyve GUI 시크릿 탭에 KO_DATA_API_KEY 를 Decoding 키로 등록했는지 확인"
        " -- Encoding 키는 이중 인코딩돼 30 이 난다",
    ),
    "31": ("기간 만료된 서비스키", "활용연장신청 후 재시도"),
    "32": ("등록되지 않은 도메인/IP", "활용신청정보의 도메인·IP 변경신청"),
}

# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class RealEstateAPIError(Exception):
    """공공데이터 API 응답 오류(저장된 응답 파일이 성공 응답이 아님).

    ``kind`` 는 CLI 오류 JSON 의 ``error`` 값이다 — itda-hyve 실패 자리는 ``"hyve"``, 나머지는 ``"api"``.
    ``hyve_code`` 는 hyve 실패 코드(``secret_missing`` 등)다.
    """

    def __init__(self, message: str, error_code: str | None = None, *,
                 kind: str = "api", hyve_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.kind = kind
        self.hyve_code = hyve_code


def error_fields(exc: RealEstateAPIError) -> dict[str, Any]:
    """CLI 오류 JSON 의 ``error``·``code`` — hyve 실패 자리는 ``error: hyve`` + hyve 코드."""
    if exc.kind == "hyve":
        return {"error": "hyve", "code": exc.hyve_code}
    return {"error": "api", "code": exc.error_code}


# ---------------------------------------------------------------------------
# 판정 보조
# ---------------------------------------------------------------------------

def _snippet(data: bytes, limit: int = 80) -> str:
    """오류 메시지용 본문 앞부분(공백 정리·키 가림 — ``hyve_input.snippet``)."""
    return snippet(data, limit)


def _code_detail(code: str, message: str, apply_url: str | None) -> str:
    hint = _ERROR_CODE_HINTS.get(code)
    if hint:
        meaning, action = hint
        detail = f"API 오류 (resultCode={code}): {message} -- {meaning}. 조치: {action}"
    else:
        detail = f"API 오류 (resultCode={code}): {message}"
    if code in {"20", "30"} and apply_url:
        detail += f" 활용신청: {apply_url}"
    return detail


def _gateway_error(root: ET.Element, apply_url: str | None) -> RealEstateAPIError:
    """``<OpenAPI_ServiceResponse>`` — 키·활용신청 단계에서 게이트웨이가 돌려준 오류."""
    code = (root.findtext(".//returnReasonCode") or "").strip()
    auth = (root.findtext(".//returnAuthMsg") or "").strip()
    err = (root.findtext(".//errMsg") or "").strip()
    message = " / ".join(x for x in (err, auth) if x) or "게이트웨이 오류"
    if code:
        detail = "게이트웨이 " + _code_detail(code, message, apply_url)
    else:
        detail = f"게이트웨이 오류: {message}"
    return RealEstateAPIError(detail, error_code=code or "GATEWAY")


def _unwrap_hyve_json(data: bytes) -> bytes:
    """입력이 itda-hyve 응답 JSON 이면 판정하고 XML 본문을 꺼낸다.

    ``save_as`` 로 저장한 파일은 응답 본문 그대로라 이 경로를 타지 않는다. 모델이
    http_request 결과(``status``·``body``·``body_truncated``)나 batch 실패
    (``{"error": {"code", "message"}}``)를 파일로 쓴 경우를 명시 오류로 가른다.
    판독은 ``hyve_input.unwrap`` 이 하고, 여기서는 예외를 error_code 계약으로 옮긴다.
    """
    try:
        body = unwrap(data)
    except HyveFailure as exc:
        raise RealEstateAPIError(
            f"itda-hyve 호출 실패 ({exc.code}): {exc.hyve_message}".rstrip()
            + " -- 이 자리는 파일이 없다. 코드·메시지를 사용자에게 전하고 멈춘다",
            error_code=f"HYVE_{exc.code}", kind="hyve", hyve_code=exc.code,
        ) from exc
    except HyveHTTPError as exc:
        raise RealEstateAPIError(
            f"HTTP 오류 응답 (status={exc.status} {exc.status_text}).".rstrip()
            + " itda-hyve 가 재시도한 뒤의 결과다 -- 같은 요청을 반복하지 말고 사용자에게 알린다",
            error_code=f"HTTP_{exc.status}",
        ) from exc
    except HyveTruncatedError as exc:
        raise RealEstateAPIError(
            "응답 본문이 잘렸다(body_truncated=true) -- 잘린 본문으로 결론 내지 말고 save_as 로 다시 받는다",
            error_code="TRUNCATED",
        ) from exc
    except HyveInputError as exc:  # 빈 본문·본문 없는 응답 요약·깨진 base64
        raise RealEstateAPIError(f"{exc} -- save_as 로 받은 XML 파일을 넘긴다", error_code="NOT_XML") from exc
    if body.form == "raw":
        raise RealEstateAPIError("data.go.kr XML 응답도 itda-hyve 응답 JSON 도 아니다", error_code="NOT_XML")
    return body.data


def _parse_error(data: bytes, exc: ET.ParseError) -> RealEstateAPIError:
    """XML 파싱 실패를 절단·비 XML 로 갈라 설명한다."""
    stripped = data.strip()
    if stripped.startswith((b"<?xml", b"<response", b"<OpenAPI_ServiceResponse")):
        if b"</response>" not in stripped and b"</OpenAPI_ServiceResponse>" not in stripped:
            return RealEstateAPIError(
                f"XML 파싱 실패: 응답이 잘렸다(닫는 태그 없음, {len(data)}바이트) -- 그 쪽을 다시 받는다 ({exc})",
                error_code="TRUNCATED",
            )
        return RealEstateAPIError(f"XML 파싱 실패: {exc}", error_code="BAD_XML")
    return RealEstateAPIError(
        "XML 파싱 실패: XML 응답이 아니다 -- HTTP 오류 페이지가 저장됐을 수 있다"
        f"(http_request 응답의 status 확인). 본문 앞부분: {_snippet(data)!r}",
        error_code="NOT_XML",
    )


# ---------------------------------------------------------------------------
# XML 파싱
# ---------------------------------------------------------------------------

def _parse_xml(
    xml_bytes: bytes,
    service_key: str | None = None,
    apply_url: str | None = None,
) -> dict[str, Any]:
    """공공데이터 API 응답 바이트를 판정·파싱한다.

    Args:
        xml_bytes: 저장된 응답 파일 바이트(XML, 또는 itda-hyve 응답 JSON).
        service_key: 서비스 식별자 (선택, 호환용 — 쓰지 않는다).
        apply_url: 권한 오류(resultCode 20/30) 시 안내할 활용신청 URL.

    Returns:
        {"total_count": N, "items": [...], "page": N} 딕셔너리.

    Raises:
        RealEstateAPIError: 성공 응답이 아닌 모든 경우(모듈 docstring 의 판정).
    """
    head = xml_bytes.lstrip()
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:].lstrip()
    if head.startswith(b"{"):
        xml_bytes = _unwrap_hyve_json(xml_bytes)

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise _parse_error(xml_bytes, exc) from exc

    if root.tag == "OpenAPI_ServiceResponse":
        raise _gateway_error(root, apply_url)
    if root.tag != "response":
        raise RealEstateAPIError(
            f"data.go.kr 응답 형식이 아니다(루트 <{root.tag}>)", error_code="NOT_RESPONSE"
        )

    header = root.find("header")
    if header is None:
        raise RealEstateAPIError("data.go.kr 응답에 <header> 가 없다", error_code="NOT_RESPONSE")
    result_code = (header.findtext("resultCode") or "").strip()
    if result_code not in _SUCCESS_CODES:
        result_msg = (header.findtext("resultMsg") or "오류").strip()
        raise RealEstateAPIError(
            _code_detail(result_code or "(없음)", result_msg, apply_url),
            error_code=result_code or None,
        )

    body = root.find("body")
    if body is None:
        # 성공 코드인데 본문이 없다 — 0건 응답도 <body><items/><totalCount>0 을 싣는다(실측).
        raise RealEstateAPIError(
            f"성공 코드(resultCode={result_code})인데 <body> 가 없다 -- 0건으로 접지 않는다",
            error_code="NOT_RESPONSE",
        )

    total_count = _int_field(body, "totalCount", 0)
    page_no = _int_field(body, "pageNo", 1)
    num_of_rows = _int_field(body, "numOfRows", 0)

    items_el = body.find("items")
    items: list[dict[str, str]] = []
    if items_el is not None:
        for item_el in items_el.findall("item"):
            item: dict[str, str] = {}
            for child in item_el:
                item[child.tag] = (child.text or "").strip()
            items.append(item)

    return {"total_count": total_count, "items": items, "page": page_no, "num_of_rows": num_of_rows}


def _int_field(body: ET.Element, tag: str, default: int) -> int:
    """``<body>`` 의 숫자 필드. 없으면 기본값, 숫자가 아니면 ``BAD_XML``."""
    el = body.find(tag)
    if el is None:
        return default
    text = (el.text or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        raise RealEstateAPIError(
            f"<{tag}> 가 숫자가 아니다({text[:20]!r})", error_code="BAD_XML"
        ) from None


def parse_response_xml(
    xml_bytes: bytes,
    service_key: str | None = None,
    apply_url: str | None = None,
) -> dict[str, Any]:
    """저장된 응답 파일 바이트를 파싱하는 공개 진입점 (#1707).

    itda-hyve 의 ``http_request`` 가 ``save_as`` 로 저장한 응답 파일을 스킬 스크립트가
    ``--input`` 으로 읽을 때 쓴다. 판정·구조는 _parse_xml 과 같다(같은 함수를 노출).
    """
    return _parse_xml(xml_bytes, service_key=service_key, apply_url=apply_url)


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
