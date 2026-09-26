"""DART OpenAPI (전자공시시스템) 클라이언트.

경쟁사 분석에 필요한 핵심 API만 래핑:
    - 고유번호 조회 (corpCode.xml → ZIP → XML 파싱)
    - 기업개황 (/api/company.json)
    - 주요계정 재무제표 (/api/fnlttSinglAcnt.json)
    - 직원현황 (/api/empSttus.json)
    - 공시 목록 조회 (/api/list.json)
    - 사업보고서 텍스트 추출 (/api/document.xml)

엔드포인트: https://opendart.fss.or.kr/api/
인증: crtfc_key 쿼리 파라미터 (40자리)
"""
from __future__ import annotations

import datetime
import html
import io
import time
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import defusedxml.ElementTree as ET
import zipfile
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_BASE_URL = "https://opendart.fss.or.kr/api"
_TIMEOUT = 15

# ZIP 폭탄 방어: 압축 해제 후 단일 엔트리 최대 크기 (50MB)
MAX_ZIP_ENTRY_SIZE = 50 * 1024 * 1024
# ZIP 청크 단위 읽기 크기 (1MB)
_ZIP_CHUNK_SIZE = 1 * 1024 * 1024

# 보고서 코드 (SPEC-DART-FEEDBACK-001 REQ-006: half → q2 일관성)
REPRT_CODES = {
    "annual": "11011",      # 사업보고서
    "q1": "11013",          # 1분기보고서
    "q2": "11012",          # 2분기보고서 (구 'half' 반기보고서)
    "q3": "11014",          # 3분기보고서
}

# 재시도 설정: 지수 백오프(1s, 2s), 최대 2회
_RETRY_BACKOFFS = (1, 2)  # 재시도 횟수 = len(_RETRY_BACKOFFS)

# 제안서에서 자주 참조하는 핵심 계정명
KEY_ACCOUNTS = {
    "매출액", "수익(매출액)", "영업이익(손실)", "영업이익",
    "당기순이익(손실)", "당기순이익", "자산총계", "부채총계", "자본총계",
}

# compare 기본 4계정 (SPEC-DART-FEEDBACK-001 REQ-007: --accounts 기본값 명시화)
# 순서 보존 — table·csv 헤더 일관성을 위해 set 아닌 tuple
DEFAULT_ACCOUNTS: tuple[str, ...] = ("매출액", "영업이익", "당기순이익", "자산총계")


class DARTAPIError(Exception):
    """DART API 호출 오류."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


_DART_APPLY_URL = "https://opendart.fss.or.kr"

_DART_SETUP_GUIDE = (
    "\n[설정 안내] DART_API_KEY를 확인하세요:\n"
    f"  1. {_DART_APPLY_URL} 접속 → 오픈API → 인증키 신청/관리\n"
    "  2. 40자리 인증키 발급 후, 작업 폴더 루트(예: outputs/)에 .env 파일로 설정:\n"
    "       DART_API_KEY=발급받은_키\n"
    "  3. 첫 호출 실패 시 점검 절차:\n"
    "     - 키 문자열 40자리 정확성 확인 (앞뒤 공백 제거)\n"
    "     - URL 인코딩 이슈는 본 스크립트에서 자동 처리됨\n"
    "     - 잠시(수 분) 후 재시도 — 발급 직후 일시적 미반영 가능\n"
)

# 정본 에러 코드 매핑 (출처: opendart.fss.or.kr/guide/detail.do 6개 분류 가이드)
# references/ 디렉토리의 정본 가이드 표를 인코딩한 단일 슈퍼셋.
_ERROR_CODE_HINTS: dict[str, dict[str, Any]] = {
    "000": {"desc": "정상", "category": "ok", "needs_apply_url": False},
    "010": {"desc": "등록되지 않은 키", "category": "setup", "needs_apply_url": True},
    "011": {"desc": "사용할 수 없는 키 (일시 중지)", "category": "setup", "needs_apply_url": True},
    "012": {"desc": "접근할 수 없는 IP", "category": "setup", "needs_apply_url": False},
    "013": {"desc": "조회된 데이터가 없습니다", "category": "data", "needs_apply_url": False},
    "014": {"desc": "파일이 존재하지 않습니다", "category": "data", "needs_apply_url": False},
    "020": {"desc": "요청 제한 초과 (일 20,000건)", "category": "transient", "needs_apply_url": False},
    "021": {"desc": "조회 가능한 회사 개수 초과 (최대 100건)", "category": "general", "needs_apply_url": False},
    "100": {"desc": "필드의 부적절한 값", "category": "setup", "needs_apply_url": False},
    "101": {"desc": "부적절한 접근", "category": "setup", "needs_apply_url": False},
    "800": {"desc": "시스템 점검으로 인한 서비스 중지", "category": "transient", "needs_apply_url": False},
    "900": {"desc": "정의되지 않은 오류", "category": "general", "needs_apply_url": False},
    "901": {"desc": "사용자 계정 개인정보 보유기간 만료", "category": "setup", "needs_apply_url": True},
}


def _classify_dart_error(error_code: str) -> tuple[str, str]:
    """DART API 오류 코드를 사용자 메시지와 카테고리로 분류.

    정본 에러 코드 표(_ERROR_CODE_HINTS)에서 한글 설명을 가져오고,
    필요 시 활용신청 URL을 자동 부착한다. 카테고리 분류는 기존 UX 분기와
    호환되도록 setup/transient/data/general 4종으로 통일.

    Args:
        error_code: DART API status 코드.

    Returns:
        (사용자 메시지, 카테고리) 튜플.
        카테고리: "setup" | "transient" | "data" | "general"
    """
    hint = _ERROR_CODE_HINTS.get(error_code)
    if hint is None:
        return (
            f"DART API 오류 (오류 코드: {error_code}) — 요청 파라미터 또는 서버 상태를 확인하세요.",
            "general",
        )

    # 011/100은 기존 테스트 호환을 위해 setup 카테고리 + DART_API_KEY 안내 유지
    if error_code in ("011", "100"):
        return (
            f"DART_API_KEY 확인 필요 (오류 코드: {error_code}, {hint['desc']}){_DART_SETUP_GUIDE}",
            "setup",
        )
    if error_code == "020":
        return (
            f"{hint['desc']} (오류 코드: {error_code}) — 잠시 후 자동 재시도합니다.",
            "transient",
        )
    if error_code == "013":
        return (
            f"조회 결과 없음 (오류 코드: {error_code}, {hint['desc']})",
            "data",
        )

    # 010, 090, 기타: 기존 동작 유지 (general). 정본 한글 설명 부착.
    suffix = f" — 활용신청 URL: {_DART_APPLY_URL}" if hint["needs_apply_url"] else ""
    return (
        f"DART API 오류 (오류 코드: {error_code}, {hint['desc']}){suffix}",
        "general",
    )


def _is_retryable_http_error(exc: Exception) -> bool:
    """재시도 대상 HTTP 오류인지 판정 (5xx만 재시도, 4xx는 즉시 실패)."""
    import urllib.error as _ue
    if isinstance(exc, _ue.HTTPError):
        return exc.code >= 500
    return False


def _request_json(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    """DART API JSON 엔드포인트 호출.

    HTTP 5xx 또는 DART status=020(요청 한도 초과) 발생 시 지수 백오프(1s, 2s)로
    최대 2회 재시도한다. 4xx 및 기타 오류는 즉시 실패한다.

    Args:
        endpoint: 엔드포인트 이름 (예: "company").
        params: 쿼리 파라미터 (crtfc_key 포함).

    Returns:
        파싱된 JSON 응답 딕셔너리.

    Raises:
        DARTAPIError: 네트워크 오류, 파싱 실패, API 오류 등.
    """
    query = urllib.parse.urlencode(params)
    url = f"{_BASE_URL}/{endpoint}.json?{query}"

    last_exc: Exception | None = None
    for attempt, backoff in enumerate([(0,)] + list((b,) for b in _RETRY_BACKOFFS)):
        # attempt 0은 최초 시도, 이후는 재시도
        if attempt > 0:
            wait = _RETRY_BACKOFFS[attempt - 1]
            print(f"[재시도 {attempt}/{len(_RETRY_BACKOFFS)}] {last_exc}", file=__import__("sys").stderr)
            time.sleep(wait)

        try:
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            # @MX:NOTE: HTTP 403은 게이트웨이 단계 권한 거부 — 활용신청 안내 부착.
            if exc.code == 403:
                raise DARTAPIError(
                    f"권한 거부 (HTTP 403) — 활용신청이 필요할 수 있습니다."
                    f"{_DART_SETUP_GUIDE}",
                    error_code="HTTP_403",
                ) from exc
            if _is_retryable_http_error(exc):
                last_exc = DARTAPIError(f"네트워크 오류: {exc}")
                continue
            raise DARTAPIError(f"네트워크 오류: {exc}") from exc
        except urllib.error.URLError as exc:
            if _is_retryable_http_error(exc):
                last_exc = DARTAPIError(f"네트워크 오류: {exc}")
                continue
            raise DARTAPIError(f"네트워크 오류: {exc}") from exc

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DARTAPIError(f"JSON 파싱 실패: {exc}") from exc

        # 에러 코드 확인
        status = data.get("status", "")
        if status == "020":
            # 요청 한도 초과 — 재시도 대상
            msg = data.get("message", "요청 한도 초과")
            last_exc = DARTAPIError(f"DART API 오류 ({status}): {msg}", error_code=status)
            continue
        if status and status != "000":
            msg = data.get("message", "알 수 없는 오류")
            raise DARTAPIError(f"DART API 오류 ({status}): {msg}", error_code=status)

        return data

    # 모든 시도 실패
    if last_exc:
        raise last_exc
    raise DARTAPIError("알 수 없는 오류로 요청 실패")


def parse_saved_json(raw: bytes | str) -> dict[str, Any]:
    """itda-hyve 가 ``save_as`` 로 저장한 DART JSON 응답을 읽는다 (#1707).

    네트워크는 itda-hyve 가 하고 이 함수는 파일 내용만 판정한다 — ``_request_json`` 과 **같은
    status 판정**(``000`` 만 성공, ``020`` 은 한도 초과)을 쓴다. HTTP 200 이어도 성공이 아니며
    재시도는 itda-hyve 몫이라 여기서는 하지 않는다.

    Raises:
        DARTAPIError: JSON 파싱 실패 또는 status != "000".
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DARTAPIError(f"JSON 파싱 실패: {exc}") from exc
    if not isinstance(data, dict):
        raise DARTAPIError("DART 응답 형식이 아닙니다(JSON 객체가 아님)")
    status = data.get("status", "")
    if status and status != "000":
        msg = data.get("message", "알 수 없는 오류")
        raise DARTAPIError(f"DART API 오류 ({status}): {msg}", error_code=status)
    return data


# raw escape-hatch: endpoint 이름은 영문자로 시작하는 영숫자만 허용.
# DART OpenAPI 엔드포인트는 전부 camelCase 영숫자(company, fnlttSinglAcntAll,
# pifricDecsn 등)이며, 이 경계가 경로 traversal('..','/')·호스트/쿼리 주입(':','?','&')을
# 차단한다(SSRF 방지). DART는 전부 read-only GET이라 쓰기 부작용도 구조적으로 없음.
_RAW_ENDPOINT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def request_raw(
    api_key: str, endpoint: str, params: dict[str, str],
) -> dict[str, Any]:
    """임의의 DART OpenAPI GET 엔드포인트를 직접 호출한다 (escape-hatch).

    references/에 정본 명세는 있으나 전용 서브커맨드가 없는 엔드포인트
    (배당 alotMatter, 소송 lwstLg, 전환사채 cvbdIsDecsn, 증자 irdsSttus 등)를
    모델이 직접 호출할 수 있게 하는 범용 통로다. ``_request_json``에 위임하므로
    재시도(1s,2s)·HTTP403 안내·status≠000 분류를 그대로 상속한다.

    보안: ``endpoint``는 ``_RAW_ENDPOINT_RE``(영문 시작 영숫자)만 허용 — 경로
    traversal·호스트/쿼리 주입을 차단한다. ``crtfc_key``는 ``api_key``로 자동
    주입되며, ``params``에 담긴 ``crtfc_key``는 무시(덮어쓰기)된다.

    한계(설계상, SPEC-DART-KDART-001 EXC-6): JSON 원문만 반환한다. 임의
    엔드포인트라 필드 스키마를 모르므로 단위변환·CSV·source.url 등 가공은
    제공하지 않는다(가공이 필요하면 전용 finance/compare 사용). status
    ``013``/``014``(데이터 없음)는 에러가 아니라 빈 결과 dict로 반환한다.

    Args:
        api_key: DART 인증키(40자리). crtfc_key로 주입된다.
        endpoint: 엔드포인트 이름 (영숫자, 예: "alotMatter").
        params: 추가 쿼리 파라미터 (corp_code, bsns_year 등). crtfc_key 제외.

    Returns:
        DART JSON 응답 dict (status/message/list 등 원형 그대로).

    Raises:
        ValueError: endpoint가 영숫자 형식이 아닐 때.
        DARTAPIError: 인증/설정/서버 오류 등 (013·014 제외).
    """
    if not _RAW_ENDPOINT_RE.match(endpoint or ""):
        raise ValueError(
            f"잘못된 엔드포인트 이름: {endpoint!r} — 영문자로 시작하는 영숫자만 "
            "허용됩니다 (예: alotMatter, lwstLg, cvbdIsDecsn). "
            "경로(/)·URL·쿼리(?, &)는 넣을 수 없습니다."
        )
    # crtfc_key는 우리가 주입한다 — 사용자 params의 crtfc_key는 덮어쓴다.
    merged = {k: v for k, v in params.items() if k != "crtfc_key"}
    merged["crtfc_key"] = api_key

    try:
        return _request_json(endpoint, merged)
    except DARTAPIError as exc:
        # 데이터 없음(013)·파일 없음(014)은 정상적인 빈 결과로 처리.
        if exc.error_code in ("013", "014"):
            return {"status": exc.error_code, "message": str(exc), "list": []}
        raise


def _request_binary(url: str) -> bytes:
    """바이너리 데이터 다운로드.

    HTTP 5xx 발생 시 지수 백오프(1s, 2s)로 최대 2회 재시도한다.

    Args:
        url: 전체 URL.

    Returns:
        바이너리 데이터.

    Raises:
        DARTAPIError: 다운로드 실패.
    """
    last_exc: Exception | None = None
    for attempt, _ in enumerate([(0,)] + list((b,) for b in _RETRY_BACKOFFS)):
        if attempt > 0:
            wait = _RETRY_BACKOFFS[attempt - 1]
            print(f"[재시도 {attempt}/{len(_RETRY_BACKOFFS)}] {last_exc}", file=__import__("sys").stderr)
            time.sleep(wait)

        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except urllib.error.URLError as exc:
            if _is_retryable_http_error(exc):
                last_exc = DARTAPIError(f"다운로드 실패: {exc}")
                continue
            raise DARTAPIError(f"다운로드 실패: {exc}") from exc

    if last_exc:
        raise last_exc
    raise DARTAPIError("알 수 없는 오류로 다운로드 실패")


# @MX:ANCHOR: [AUTO] corp_code 조회의 핵심 함수.
# @MX:REASON: fan_in >= 3 (collect_company의 모든 서브커맨드); 회사명→고유번호 변환 계약.
def find_corp_code(
    api_key: str,
    corp_name: str,
    cache_path: str | None = None,
) -> list[dict[str, str]]:
    """회사명으로 DART 고유번호(corp_code)를 검색.

    corpCode.xml ZIP 파일을 다운로드하여 파싱. cache_path가 지정되면
    다운로드한 XML을 캐싱하여 재사용.

    Args:
        api_key: DART API 인증키.
        corp_name: 검색할 회사명 (부분 일치).
        cache_path: 캐시 파일 경로 (None이면 캐시 안 함).

    Returns:
        매칭된 기업 목록:
        [{"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930"}, ...]

    Raises:
        DARTAPIError: ZIP 다운로드/파싱 실패.
    """
    from pathlib import Path

    xml_content = None

    # 캐시 확인
    if cache_path:
        cache_file = Path(cache_path)
        if cache_file.exists():
            logger.info("캐시에서 corpCode.xml 로드: %s", cache_path)
            xml_content = cache_file.read_bytes()

    # 캐시 없으면 다운로드
    if xml_content is None:
        url = f"{_BASE_URL}/corpCode.xml?crtfc_key={api_key}"
        zip_data = _request_binary(url)

        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                names = zf.namelist()
                if not names:
                    raise DARTAPIError("ZIP 파일이 비어있습니다.")
                xml_content = _safe_zip_read(zf, names[0])
        except zipfile.BadZipFile as exc:
            raise DARTAPIError(f"ZIP 파싱 실패: {exc}") from exc

        # 캐시 저장
        if cache_path:
            cache_file = Path(cache_path)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(xml_content)
            logger.info("corpCode.xml 캐시 저장: %s", cache_path)

    # XML 파싱 및 검색
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise DARTAPIError(f"XML 파싱 실패: {exc}") from exc

    results: list[dict[str, str]] = []
    search_lower = corp_name.lower()
    search_parts = _split_mixed_query(corp_name)

    for item in root.iter("list"):
        name = item.findtext("corp_name", "")
        name_eng = item.findtext("corp_eng_name", "")
        if _match_corp(search_lower, search_parts, name, name_eng):
            results.append({
                "corp_code": item.findtext("corp_code", ""),
                "corp_name": name,
                "corp_name_eng": name_eng,
                "stock_code": item.findtext("stock_code", "").strip(),
                "modify_date": item.findtext("modify_date", ""),
            })

    return results


import re

# 한글 유니코드 범위
_RE_HANGUL = re.compile(r"[가-힣]+")
_RE_NON_HANGUL = re.compile(r"[a-zA-Z0-9]+")


def _split_mixed_query(query: str) -> list[str]:
    """한글+영문 혼합 검색어를 부분으로 분리.

    예: "삼성SDS" → ["삼성", "sds"]
        "LG CNS" → ["lg", "cns"]
        "삼성전자" → ["삼성전자"]

    Args:
        query: 검색어.

    Returns:
        분리된 소문자 토큰 목록. 단일 언어면 빈 리스트.
    """
    hangul_parts = _RE_HANGUL.findall(query)
    alpha_parts = _RE_NON_HANGUL.findall(query)

    # 한글과 영문이 모두 있을 때만 분리 (혼합 검색어)
    if hangul_parts and alpha_parts:
        return [p.lower() for p in hangul_parts + alpha_parts]
    return []


def _match_corp(
    search_lower: str,
    search_parts: list[str],
    name: str,
    name_eng: str,
) -> bool:
    """기업명 매칭 판정.

    매칭 전략:
    1. 단순 부분 매칭: 검색어가 한글명 또는 영문명에 포함
    2. 혼합 매칭: 한글 부분이 한글명에, 영문 부분이 영문명에 모두 포함

    Args:
        search_lower: 소문자 변환된 원본 검색어.
        search_parts: _split_mixed_query()의 결과.
        name: DART 한글 회사명.
        name_eng: DART 영문 회사명.

    Returns:
        매칭 여부.
    """
    name_lower = name.lower()
    eng_lower = name_eng.lower()

    # 전략 1: 단순 부분 매칭
    if search_lower in name_lower or search_lower in eng_lower:
        return True

    # 전략 2: 혼합 매칭 (한글+영문 분리)
    if search_parts:
        hangul_ok = all(
            p in name_lower for p in search_parts if _RE_HANGUL.fullmatch(p)
        )
        alpha_ok = all(
            p in eng_lower for p in search_parts if _RE_NON_HANGUL.fullmatch(p)
        )
        if hangul_ok and alpha_ok:
            return True

    return False


def get_company_info(api_key: str, corp_code: str) -> dict[str, Any]:
    """기업개황 조회.

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.

    Returns:
        기업개황 딕셔너리 (corp_name, ceo_nm, induty_code, adres 등).
    """
    return _request_json("company", {
        "crtfc_key": api_key,
        "corp_code": corp_code,
    })


def get_financial_statements(
    api_key: str,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = "11011",
) -> list[dict[str, Any]]:
    """단일회사 주요계정 재무제표 조회.

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.
        bsns_year: 사업연도 (예: "2024").
        reprt_code: 보고서 코드 (기본: "11011" 사업보고서).

    Returns:
        재무제표 계정 목록.
        각 항목: {account_nm, fs_div, sj_div, thstrm_amount, frmtrm_amount, ...}
    """
    data = _request_json("fnlttSinglAcnt", {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    })
    return data.get("list", [])


def get_financial_statements_all(
    api_key: str,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = "11011",
    fs_div: str = "CFS",
) -> list[dict[str, Any]]:
    """단일회사 전체 재무제표 조회 (fnlttSinglAcntAll).

    주요계정(fnlttSinglAcnt, 약 30항목)이 아닌 전체 계정(약 176항목)을 반환한다.
    sj_div: BS(재무상태표)/IS(손익계산서)/CIS(포괄손익)/CF(현금흐름)/SCE(자본변동)

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.
        bsns_year: 사업연도 (예: "2024").
        reprt_code: 보고서 코드 (기본: "11011" 사업보고서).
        fs_div: "CFS"(연결) 또는 "OFS"(개별). 기본 연결.

    Returns:
        전체 재무제표 계정 목록 (176항목 내외).
        각 항목: {sj_div, account_nm, thstrm_amount, frmtrm_amount, rcept_no, ...}
    """
    data = _request_json("fnlttSinglAcntAll", {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
    })
    return data.get("list", [])


def get_employee_status(
    api_key: str,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = "11011",
) -> list[dict[str, Any]]:
    """직원현황 조회.

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.
        bsns_year: 사업연도.
        reprt_code: 보고서 코드.

    Returns:
        직원현황 목록.
        각 항목: {fo_bbm, sexdstn, rgllbr_co, cnttk_co, sm, avrg_cnwk_sdytrn, ...}
    """
    data = _request_json("empSttus", {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    })
    return data.get("list", [])


# 사업보고서 법정 제출 기한 90일 + 버퍼 5일 (REQ-DART-002-003)
REPORT_SUBMISSION_LAG_DAYS = 95


def filter_key_financials(
    statements: list[dict[str, Any]],
    fs_div: str = "CFS",
) -> tuple[list[dict[str, str]], bool]:
    """재무제표에서 제안서용 핵심 계정만 추출.

    CFS 결과가 비면 OFS로 자동 폴백한다.
    동일 (fs_div, account_nm) 중복은 첫 건 유지(결정성 보장).

    Args:
        statements: get_financial_statements()의 반환값.
        fs_div: "CFS"(연결) 또는 "OFS"(개별). 기본 연결.

    Returns:
        (핵심 계정 목록, 폴백_발생_여부) 튜플.
        핵심 계정 목록: [{account_nm, thstrm_amount, frmtrm_amount, rcept_no, ...}, ...]
        폴백 발생 여부: True이면 요청 fs_div에 결과가 없어 반대 fs_div로 대체됨.
    """
    def _extract(div: str) -> list[dict[str, str]]:
        seen_accounts: set[str] = set()
        results: list[dict[str, str]] = []
        for item in statements:
            if item.get("fs_div") != div:
                continue
            account = item.get("account_nm", "")
            if account not in KEY_ACCOUNTS:
                continue
            # 동일 (fs_div, account_nm) 중복 제거 — 첫 건 유지
            dedup_key = f"{div}:{account}"
            if dedup_key in seen_accounts:
                continue
            seen_accounts.add(dedup_key)
            results.append({
                "account_nm": account,
                "thstrm_amount": item.get("thstrm_amount", ""),
                "frmtrm_amount": item.get("frmtrm_amount", ""),
                "bfefrmtrm_amount": item.get("bfefrmtrm_amount", ""),
                "bsns_year": item.get("bsns_year", ""),
                "currency": item.get("currency", "KRW"),
                "rcept_no": item.get("rcept_no", ""),
            })
        return results

    primary = _extract(fs_div)
    if primary:
        return primary, False

    # 폴백: CFS↔OFS 전환
    fallback_div = "OFS" if fs_div == "CFS" else "CFS"
    fallback = _extract(fallback_div)
    return fallback, bool(fallback)


# @MX:ANCHOR: [AUTO] 공시 목록 조회의 진입 함수.
# @MX:REASON: fan_in >= 3 (cmd_disclosure, find_latest_business_report, 폴백 분기); status=013 처리 계약.
def list_disclosures(
    api_key: str,
    corp_code: str,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str | None = None,
    page_no: int = 1,
    page_count: int = 10,
) -> dict[str, Any]:
    """공시 목록 조회 (list.json).

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.
        bgn_de: 시작일 (YYYYMMDD).
        end_de: 종료일 (YYYYMMDD).
        pblntf_ty: 공시 유형 (A=정기공시, B=주요사항보고, None=전체).
        page_no: 페이지 번호 (기본 1).
        page_count: 페이지당 건수 (기본 10, 최대 100).

    Returns:
        list.json 응답 딕셔너리. status=013 시 {"list": [], "total_count": "0"} 반환.

    Raises:
        DARTAPIError: 013 이외의 API 오류.
    """
    params: dict[str, str] = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": str(page_no),
        "page_count": str(page_count),
    }
    if pblntf_ty is not None:
        params["pblntf_ty"] = pblntf_ty

    try:
        return _request_json("list", params)
    except DARTAPIError as exc:
        # status=013: 조회 결과 없음 → 정상 케이스
        if exc.error_code == "013":
            return {"list": [], "total_count": "0", "status": "013"}
        raise


# @MX:ANCHOR: [AUTO] 사업보고서 문서 텍스트 추출 함수.
# @MX:REASON: fan_in >= 3 (cmd_business, 폴백 분기, 외부 스크립트); ZIP/인코딩 복잡성 캡슐화.
def get_document_text(
    api_key: str,
    rcept_no: str,
    section_pattern: str | None = None,
    max_chars: int = 5000,
) -> str:
    """사업보고서 원문 텍스트 추출 (document.xml ZIP).

    ZIP 다운로드 → 가장 큰 파일 선택 → UTF-8/EUC-KR 폴백 디코딩 →
    HTML 태그 제거 → 섹션 필터링 → 길이 제한 적용.

    Args:
        api_key: DART API 인증키.
        rcept_no: 접수번호 (14자리).
        section_pattern: 추출할 섹션의 정규식 패턴. None이면 전체 본문.
        max_chars: 최대 반환 문자 수 (0이면 무제한).

    Returns:
        정제된 텍스트.

    Raises:
        DARTAPIError: 다운로드 실패, ZIP 파싱 실패, 인코딩 실패.
    """
    url = f"{_BASE_URL}/document.xml?crtfc_key={api_key}&rcept_no={rcept_no}"
    zip_data = _request_binary(url)

    # ZIP 압축 해제 — 가장 큰 파일 선택 (ZIP 폭탄 방어 적용)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            names = zf.namelist()
            if not names:
                raise DARTAPIError("document.xml ZIP이 비어있습니다.")

            # 각 파일 크기 기준으로 가장 큰 파일 선택
            largest_name = max(names, key=lambda n: zf.getinfo(n).file_size)
            raw_bytes = _safe_zip_read(zf, largest_name)
    except zipfile.BadZipFile as exc:
        raise DARTAPIError(f"document.xml ZIP 파싱 실패: {exc}") from exc

    # 인코딩 감지: UTF-8 우선, EUC-KR 폴백
    text = _decode_with_fallback(raw_bytes)

    # HTML/XML 태그 제거 및 공백 정리
    text = _strip_html(text)

    # 섹션 필터링
    if section_pattern:
        text = _extract_section(text, section_pattern)

    # 길이 제한
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]

    return text


def _safe_zip_read(zf: zipfile.ZipFile, name: str) -> bytes:
    """ZIP 엔트리를 안전하게 읽기 (ZIP 폭탄 방어).

    ZipInfo.file_size를 사전 검사하여 MAX_ZIP_ENTRY_SIZE 초과 시 즉시 거부한다.
    실제 읽기도 청크 단위로 누적하여 한도 도달 시 중단한다.

    Args:
        zf: 열린 ZipFile 객체.
        name: 엔트리 이름.

    Returns:
        읽은 바이트.

    Raises:
        DARTAPIError: 엔트리 크기가 MAX_ZIP_ENTRY_SIZE를 초과할 때.
    """
    info = zf.getinfo(name)
    # 사전 검증: 압축 해제 후 크기 초과 시 즉시 거부
    if info.file_size > MAX_ZIP_ENTRY_SIZE:
        raise DARTAPIError(
            f"ZIP 엔트리 크기 초과: {info.file_size} bytes > {MAX_ZIP_ENTRY_SIZE} bytes (ZIP 폭탄 방어)"
        )

    # 청크 단위 읽기: 실제 압축 해제 크기 누적 확인
    chunks: list[bytes] = []
    total = 0
    with zf.open(name) as f:
        while True:
            chunk = f.read(_ZIP_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ZIP_ENTRY_SIZE:
                raise DARTAPIError(
                    f"ZIP 엔트리 실제 크기가 한도 초과: {total} bytes > {MAX_ZIP_ENTRY_SIZE} bytes"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _decode_with_fallback(raw: bytes) -> str:
    """UTF-8 디코딩 시도, 실패 시 EUC-KR 폴백.

    Args:
        raw: 원시 바이트.

    Returns:
        디코딩된 문자열.

    Raises:
        DARTAPIError: 두 인코딩 모두 실패.
    """
    try:
        return raw.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        pass

    try:
        return raw.decode("euc-kr")
    except (UnicodeDecodeError, ValueError) as exc:
        raise DARTAPIError(f"인코딩 감지 실패 (UTF-8, EUC-KR 모두 실패): {exc}") from exc


def _strip_html(text: str) -> str:
    """HTML/XML 태그 제거 및 공백 정리.

    블록 태그(<p>, <div>, <br>, <tr>, <li>, <h1>~<h6>)는 줄바꿈으로 변환하여
    표·문단 등 의미 단위 구조를 보존한다. 인라인 태그는 공백으로 대체한다.
    html.unescape()로 모든 named/numeric entity를 한 번에 디코딩한다.

    Args:
        text: 원시 HTML 텍스트.

    Returns:
        태그가 제거된 정제 텍스트.
    """
    # 블록 태그: 줄바꿈으로 변환 (닫힘 태그도 포함)
    _BLOCK_RE = re.compile(
        r"<\s*/?\s*(p|div|br|tr|li|h[1-6])(\s[^>]*)?>",
        re.IGNORECASE,
    )
    text = _BLOCK_RE.sub("\n", text)

    # 나머지 태그: 공백으로 대체
    text = re.sub(r"<[^>]+>", " ", text)

    # HTML entity 디코딩 (html.unescape = 모든 named·numeric 처리)
    text = html.unescape(text)

    # 연속 공백/탭 정리 (줄바꿈은 유지)
    text = re.sub(r"[ \t]+", " ", text)
    # 3개 이상 연속 개행 → 2개로 축소
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_section(text: str, pattern: str) -> str:
    """정규식 패턴으로 섹션을 추출.

    패턴이 등장하는 위치부터 다음 섹션 헤더 이전까지 추출한다.
    헤더 감지는 번호 접두(로마·아라비아) 또는 화이트리스트 방식을 사용하여
    짧은 한글 본문 줄의 오인식을 방지한다.

    end_idx가 None일 때: 다음 섹션 헤더를 발견하지 못한 경우이므로
    파일 끝까지(lines[start_idx:])를 반환한다.

    Args:
        text: 전체 텍스트.
        pattern: 섹션 시작 정규식 (예: "사업의 내용").

    Returns:
        추출된 섹션 텍스트. 매칭 없으면 전체 텍스트 반환.
    """
    compiled = re.compile(pattern, re.IGNORECASE)

    # DART 사업보고서 표준 섹션 라벨 화이트리스트 (14개)
    _KNOWN_SECTION_LABELS = {
        "회사의 개요",
        "사업의 내용",
        "재무에 관한 사항",
        "주식의 총수",
        "임원 및 직원 등의 현황",
        "회사의 기관에 관한 사항",
        "주주에 관한 사항",
        "계열회사 등의 현황",
        "이해관계자와의 거래내용",
        "그 밖에 투자자 보호를 위하여 필요한 사항",
        "이사회의 작성 심의 결의",
        "감사보고서",
        "연결재무제표",
        "재무제표",
    }

    # 번호 접두 패턴: I. / II. / 1. / 1-1. / 제1조. 등
    _NUMBERED_HEADER_RE = re.compile(
        r"^(?:[IVXLCDM]+\.|[0-9]+(?:-[0-9]+)*\.|제\d+조\.?)\s+\S",
        re.IGNORECASE,
    )

    def _is_section_header(line: str) -> bool:
        """줄이 섹션 헤더인지 판정."""
        stripped = line.strip()
        if not stripped:
            return False
        # 번호 접두 패턴 매칭
        if _NUMBERED_HEADER_RE.match(stripped):
            return True
        # 화이트리스트 매칭 (접두 제거 후 비교)
        # "I. 회사의 개요" → "회사의 개요" 추출
        label_part = re.sub(r"^[IVXLCDM0-9\-\.제조\s]+\s*", "", stripped, flags=re.IGNORECASE).strip()
        return stripped in _KNOWN_SECTION_LABELS or label_part in _KNOWN_SECTION_LABELS

    lines = text.split("\n")
    start_idx: int | None = None
    end_idx: int | None = None  # None = 다음 헤더 미발견, 파일 끝까지 반환

    for i, line in enumerate(lines):
        stripped = line.strip()
        if start_idx is None:
            if compiled.search(stripped):
                start_idx = i
        else:
            # 현재 섹션과 다른 헤더가 나타나면 경계로 인식
            if _is_section_header(line) and not compiled.search(stripped):
                end_idx = i
                break

    if start_idx is None:
        return text

    # end_idx=None이면 파일 끝까지 포함
    section_lines = lines[start_idx:end_idx]
    return "\n".join(section_lines).strip()


# 보고서명 키워드 → report_type 매핑
_REPORT_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("사업보고서", "annual"),
    ("반기보고서", "half"),
    ("1분기보고서", "q1"),
    ("3분기보고서", "q3"),
]


def _classify_report_type(report_nm: str) -> str | None:
    """보고서명에서 report_type 분류.

    Args:
        report_nm: DART 보고서명.

    Returns:
        "annual" | "half" | "q1" | "q3", 매칭 없으면 None.
    """
    for keyword, rtype in _REPORT_TYPE_KEYWORDS:
        if keyword in report_nm:
            return rtype
    return None


def _extract_bsns_year(report_nm: str, rcept_dt: str) -> str:
    """보고서명 또는 접수일로 사업연도 추출.

    report_nm "(YYYY.MM)" 패턴 우선, 없으면 rcept_dt 연도 - 1.

    Args:
        report_nm: DART 보고서명.
        rcept_dt: 접수일 (YYYYMMDD).

    Returns:
        사업연도 문자열.
    """
    bsns_year_match = re.search(r"\((\d{4})\.\d{2}\)", report_nm)
    if bsns_year_match:
        return bsns_year_match.group(1)
    if rcept_dt[:4].isdigit():
        return str(int(rcept_dt[:4]) - 1)
    return ""


# @MX:ANCHOR: [AUTO] 분기·반기 폴백을 포함한 최신 보고서 조회 핵심 함수.
# @MX:REASON: fan_in >= 3 (find_latest_business_report 위임, cmd_finance, cmd_business, 테스트); prefer 계약 포함.
def find_latest_report(
    api_key: str,
    corp_code: str,
    prefer: str = "annual",
) -> dict[str, str]:
    """최근 95일 내 보고서 조회 (분기·반기 폴백 지원).

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.
        prefer: "annual" → 사업보고서만 (기존 동작 유지),
                "latest" → 사업/반기/분기 중 가장 최신 1건.

    Returns:
        {"rcept_no": "...", "bsns_year": "...", "rcept_dt": "...", "report_type": "..."}.

    Raises:
        DARTAPIError: 최근 보고서 없음.
    """
    # KST(Asia/Seoul) 기준 오늘 날짜 — UTC 컨테이너 환경에서도 정확한 95일 윈도우 산출
    today = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    bgn_date = today - datetime.timedelta(days=REPORT_SUBMISSION_LAG_DAYS)
    bgn_de = bgn_date.strftime("%Y%m%d")
    end_de = today.strftime("%Y%m%d")

    data = list_disclosures(
        api_key, corp_code, bgn_de, end_de, pblntf_ty="A", page_count=100,
    )

    all_items = data.get("list", [])

    if prefer == "annual":
        # 기존 동작: 사업보고서만 필터
        candidates = [
            item for item in all_items
            if "사업보고서" in item.get("report_nm", "")
        ]
        if not candidates:
            raise DARTAPIError("최근 사업보고서 없음")
    else:
        # latest 모드: 사업/반기/분기 전부 대상
        candidates = [
            item for item in all_items
            if _classify_report_type(item.get("report_nm", "")) is not None
        ]
        if not candidates:
            raise DARTAPIError("최근 보고서 없음 (사업·반기·분기 모두 없음)")

    # rcept_dt + rcept_no 기준 최신 1건 (정정공시 tie-breaker)
    latest = max(
        candidates,
        key=lambda x: (x.get("rcept_dt", ""), x.get("rcept_no", "")),
    )

    report_nm = latest.get("report_nm", "")
    rcept_dt = latest.get("rcept_dt", "")
    bsns_year = _extract_bsns_year(report_nm, rcept_dt)
    report_type = _classify_report_type(report_nm) or "annual"

    return {
        "rcept_no": latest.get("rcept_no", ""),
        "bsns_year": bsns_year,
        "rcept_dt": rcept_dt,
        "report_type": report_type,
    }


# @MX:ANCHOR: [AUTO] 최신 사업보고서 자동 폴백의 핵심 함수.
# @MX:REASON: fan_in >= 3 (cmd_business 폴백, cmd_finance 폴백, 테스트); 95일 룰 계약.
def find_latest_business_report(
    api_key: str,
    corp_code: str,
) -> dict[str, str]:
    """최근 95일 내 가장 최신 사업보고서 조회 (하위 호환).

    find_latest_report(prefer="annual")로 위임한다.

    Args:
        api_key: DART API 인증키.
        corp_code: 8자리 고유번호.

    Returns:
        {"rcept_no": "...", "bsns_year": "...", "rcept_dt": "..."} 딕셔너리.

    Raises:
        DARTAPIError: 최근 사업보고서 없음.
    """
    result = find_latest_report(api_key, corp_code, prefer="annual")
    return {
        "rcept_no": result["rcept_no"],
        "bsns_year": result["bsns_year"],
        "rcept_dt": result["rcept_dt"],
    }


def _match_account(
    account_nm: str,
    search_accounts: list[str],
) -> str | None:
    """계정명 매칭: 정확 일치 우선, 없으면 부분 일치 fallback.

    Args:
        account_nm: DART 계정명.
        search_accounts: 검색할 계정명 목록.

    Returns:
        매칭된 검색 계정명, 없으면 None.
    """
    # 정확 일치 우선
    for acct in search_accounts:
        if account_nm == acct:
            return acct
    # 부분 일치 fallback
    for acct in search_accounts:
        if acct in account_nm or account_nm in acct:
            return acct
    return None


def compare_financials(
    api_key: str,
    corp_codes: list[str],
    year: str,
    accounts: list[str],
    reprt_code: str = "11011",
    fs_div: str = "CFS",
) -> dict[str, dict]:
    """다기업 재무 비교 조회.

    Args:
        api_key: DART API 인증키.
        corp_codes: 8자리 고유번호 목록.
        year: 사업연도 (예: "2024").
        accounts: 조회할 계정명 목록.
        reprt_code: 보고서 코드 (기본: "11011" 사업보고서).
        fs_div: 연결(CFS)/개별(OFS). CFS 없으면 OFS로 자동 폴백.

    Returns:
        {corp_code: {"data": {account_nm: {...}}, "fallback": bool, "rcept_no": str}}
        조회 실패 기업은 빈 dict.
    """
    result: dict[str, dict] = {}

    for corp_code in corp_codes:
        try:
            statements = get_financial_statements(api_key, corp_code, year, reprt_code)
            key_items, fallback = filter_key_financials(statements, fs_div)
            corp_result: dict[str, dict] = {}
            rcept_no_val = ""

            for item in key_items:
                matched = _match_account(item["account_nm"], accounts)
                if matched and matched not in corp_result:
                    # 정확 일치 우선 처리: 이미 등록된 경우 덮어쓰지 않음 (부분 일치 방지)
                    corp_result[matched] = {
                        "thstrm_amount": item.get("thstrm_amount", ""),
                        "frmtrm_amount": item.get("frmtrm_amount", ""),
                        "bfefrmtrm_amount": item.get("bfefrmtrm_amount", ""),
                        "currency": item.get("currency", "KRW"),
                        "rcept_no": item.get("rcept_no", ""),
                    }
                if not rcept_no_val:
                    rcept_no_val = item.get("rcept_no", "")

            result[corp_code] = {
                "data": corp_result,
                "fallback": fallback,
                "rcept_no": rcept_no_val,
            }
        except DARTAPIError:
            result[corp_code] = {"data": {}, "fallback": False, "rcept_no": ""}

    return result
