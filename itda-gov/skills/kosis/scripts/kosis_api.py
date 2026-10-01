"""KOSIS 국가통계포털 OpenAPI — 호출 계획과 응답 파서 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 모듈은
  1. 명령마다 부를 **호출 계획**(``http_request`` 인자 그대로)을 만들고
  2. 그렇게 저장한 **응답 파일을 읽어** 오류 판정·분류축 해석·정리만 한다.
직접 API 를 부르지 않고 키 값을 보지 않는다(``{{secret:KOSIS_API_KEY}}`` 자리표시자만 싣는다).

엔드포인트: https://kosis.kr/openapi/ (인증은 쿼리 ``apiKey``)
통계자료 URL 은 ``Param/statisticsParameterData.do`` 다 — 2026-09-30 itda-hyve 실측에서 이 URL 은
KOSIS 오류 JSON(err 10, 키 없이 보냄)을 줬고, 오타 ``Param/statisticsParamData.do`` 는 HTTP 404 HTML 이었다.

응답 형태:
    성공      행 배열 ``[{...}, ...]`` (getMeta TBL 은 단일 객체)
    오류      ``{"err":"10","errMsg":"…"}`` — 옛 서버는 키에 따옴표가 없는 ``{err:"10",…}`` 도 준다
    SDMX      Generic XML, 오류는 ``<error><err>21</err>…``
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from hyve_input import HyveHTTPError, HyveInputError, read_input

logger = logging.getLogger(__name__)

# 엔드포인트
_SEARCH_URL = "https://kosis.kr/openapi/statisticsSearch.do"
_DATA_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
# SDMX Generic 네임스페이스 — objL1 부재 통계표의 정본 전송 형식(아래 주석 참조)
_SDMX_NS = {
    "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
    "message": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
}
_LIST_URL = "https://kosis.kr/openapi/statisticsList.do"
# 메타자료(통계표 구조) — 통계자료와 동일 endpoint, method=getMeta (매뉴얼 §2.5)
_META_URL = "https://kosis.kr/openapi/statisticsData.do"
# 통계설명(작성목적·법적근거 등) — statisticsExplData.do, method=getList (매뉴얼 §2.4)
_EXPL_URL = "https://kosis.kr/openapi/statisticsExplData.do"
# 통계주요지표 설명자료 — pkNumberService.do, service=1 (매뉴얼 §2.7.2.1)
_INDICATOR_URL = "https://kosis.kr/openapi/pkNumberService.do"

SECRET = "{{secret:KOSIS_API_KEY}}"
# Cowork 는 호출 하나를 60초에 끊는다 — 그보다 짧게.
TIMEOUT_SEC = 50

# 활용신청 페이지 — 인증키 관련 오류 시 사용자에게 자동 부착
_KOSIS_APPLY_URL = "https://kosis.kr/openapi/"

_KOSIS_SETUP_GUIDE = (
    "\n[설정 안내] KOSIS_API_KEY 를 확인하세요:\n"
    f"  1. {_KOSIS_APPLY_URL} 접속 → 회원가입 → Open API → 활용신청(자동 승인, 마이페이지에서 인증키 확인)\n"
    "  2. itda-hyve GUI 시크릿 탭에 KOSIS_API_KEY 이름으로 등록(키 값을 대화에 붙여 넣지 않는다)\n"
    "  3. 첫 호출 실패 시 점검:\n"
    "     - Base64 키 끝 '=' 패딩 누락 여부 확인 (전체 복사 필수)\n"
    "     - 만료된 인증키는 마이페이지에서 기간 연장 가능\n"
    "     - 잠시(수 분) 후 재시도 — 신규 발급 직후 일시적 미반영 가능\n"
)

# 정본 에러 코드 매핑 (출처: KOSIS OpenAPI 매뉴얼 v1.0 §1.4.2)
# references/kosis-매뉴얼/01-인증키-에러메시지.md 참조
_ERROR_CODE_HINTS: dict[str, dict[str, Any]] = {
    "10": {"desc": "인증키 누락", "category": "setup", "needs_apply_url": True},
    "11": {"desc": "인증키 기간만료", "category": "setup", "needs_apply_url": True},
    "20": {"desc": "필수요청변수 누락", "category": "setup", "needs_apply_url": False},
    "21": {"desc": "잘못된 요청변수", "category": "setup", "needs_apply_url": False},
    "30": {"desc": "조회결과 없음", "category": "data", "needs_apply_url": False},
    "31": {"desc": "조회결과 초과", "category": "data", "needs_apply_url": False},
    "40": {"desc": "호출가능건수 제한", "category": "transient", "needs_apply_url": False},
    "41": {"desc": "호출가능 ROW수 제한", "category": "transient", "needs_apply_url": False},
    "42": {"desc": "사용자별 이용 제한", "category": "setup", "needs_apply_url": True},
    "50": {"desc": "서버오류", "category": "transient", "needs_apply_url": False},
}

# 수록주기 코드
PERIOD_CODES = {
    "year": "Y",
    "half": "H",
    "quarter": "Q",
    "month": "M",
    "day": "D",
}

# 메타자료 조회유형 — 코드 발견(ITM)이 핵심 진입점
META_TYPES = ("TBL", "ORG", "PRD", "ITM", "CMMT", "UNIT", "SOURCE", "WGT", "NCD")


def _classify_kosis_error(error_code: str) -> tuple[str, str]:
    """KOSIS API 오류 코드를 사용자 메시지와 카테고리로 분류.

    정본 에러 코드 표(_ERROR_CODE_HINTS)에서 한글 설명을 가져오고,
    인증키 관련(10/11/42)은 활용신청 URL 과 시크릿 등록 안내를 붙인다.

    Returns:
        (사용자 메시지, 카테고리) 튜플.
        카테고리: "setup" | "transient" | "data" | "general"
    """
    hint = _ERROR_CODE_HINTS.get(error_code)
    if hint is None:
        return (
            f"KOSIS API 오류 (오류 코드: {error_code}) — 요청 파라미터 또는 서버 상태를 확인하세요.",
            "general",
        )

    if error_code in ("10", "11", "42"):
        return (
            f"KOSIS_API_KEY 확인 필요 (오류 코드: {error_code}, {hint['desc']}){_KOSIS_SETUP_GUIDE}",
            hint["category"],
        )
    if error_code in ("40", "41"):
        return (
            f"{hint['desc']} (오류 코드: {error_code}) — 호출 빈도를 줄이거나 KOSIS 관리자에게 문의하세요.",
            hint["category"],
        )
    if error_code == "50":
        return (
            f"{hint['desc']} (오류 코드: {error_code}) — 잠시 후 다시 받으세요.",
            hint["category"],
        )
    if error_code == "31":
        return (
            f"조회 결과 이슈 (오류 코드: 31, {hint['desc']}) — 한 번에 4만 셀을 넘는다. 기간·항목·분류를 나눠 받으세요.",
            hint["category"],
        )
    if error_code == "30":
        return (
            f"조회 결과 이슈 (오류 코드: 30, {hint['desc']})",
            hint["category"],
        )
    # 20, 21, 기타: setup
    return (
        f"KOSIS API 오류 (오류 코드: {error_code}, {hint['desc']}) — 요청 파라미터를 확인하세요.",
        hint["category"],
    )


class KOSISAPIError(Exception):
    """저장된 응답이 KOSIS 오류 응답이다 (본문의 err 코드)."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class InputFileError(Exception):
    """입력 파일을 가공할 수 없다 — 없음·이름 규칙 위반·절단·HTTP 오류·itda-hyve 실패·KOSIS 응답 아님.

    ``kind`` 는 출력 JSON 의 ``error`` 값이다(``input``·``truncated``·``http``·``hyve``).
    """

    def __init__(self, message: str, kind: str = "input"):
        super().__init__(message)
        self.kind = kind


class IncompleteError(Exception):
    """다음 단계 응답이 더 필요하다. ``next_calls`` 에 받을 호출이 담긴다(data 의 적응형 흐름)."""

    def __init__(self, message: str, next_calls: list[dict[str, Any]], stage: str):
        super().__init__(message)
        self.next_calls = next_calls
        self.stage = stage


# --- 호출 계획 ---

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe(token: str) -> str:
    """저장 이름 조각 — 영숫자·``_``·``.``·``-`` 만 남긴다(한글·공백은 ``_``)."""
    return _NAME_SAFE.sub("_", str(token)) or "_"


def query_hash(query: dict[str, Any]) -> str:
    """질의 인자 전부의 짧은 지문(8자). 저장 이름에 실어 다른 질의의 파일이 섞이지 않게 한다."""
    blob = json.dumps(query, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


def build_call(call_id: str, url: str, params: dict[str, str], save_as: str) -> dict[str, Any]:
    """``http_request`` 한 번 — batch ``calls`` 한 칸 형태. 단독 호출은 ``args`` 만 쓴다."""
    full = {"apiKey": SECRET, **{k: str(v) for k, v in params.items()}}
    return {
        "id": call_id,
        "tool": "http_request",
        "args": {"url": url, "params": full, "timeout_sec": TIMEOUT_SEC, "save_as": save_as},
    }


def plan_search(keyword: str, count: int = 10) -> dict[str, Any]:
    name = f"kosis/search-{query_hash({'keyword': keyword, 'count': count})}.json"
    return build_call("search", _SEARCH_URL, {
        "method": "getList", "searchNm": keyword, "sort": "RANK",
        "startCount": "1", "resultCount": str(count), "format": "json",
    }, name)


def info_save_name(org_id: str, tbl_id: str, meta_type: str, obj_id: str = "", itm_id: str = "") -> str:
    base = f"kosis/info-{_safe(org_id)}-{_safe(tbl_id)}-{_safe(meta_type)}"
    if obj_id or itm_id:
        base += "-" + query_hash({"objId": obj_id, "itmId": itm_id})
    return base + ".json"


def plan_info(org_id: str, tbl_id: str, meta_type: str = "ITM", obj_id: str = "", itm_id: str = "") -> dict[str, Any]:
    params = {"method": "getMeta", "orgId": org_id, "tblId": tbl_id, "type": meta_type, "format": "json"}
    if obj_id:
        params["objId"] = obj_id
    if itm_id:
        params["itmId"] = itm_id
    return build_call(f"info-{meta_type}", _META_URL, params,
                      info_save_name(org_id, tbl_id, meta_type, obj_id, itm_id))


def plan_list(vw_cd: str = "MT_ZTITLE", parent_list_id: str = "") -> dict[str, Any]:
    params = {"method": "getList", "vwCd": vw_cd, "format": "json", "jsonVD": "Y"}
    if parent_list_id:
        params["parentListId"] = parent_list_id
    name = f"kosis/list-{_safe(vw_cd)}-{_safe(parent_list_id) if parent_list_id else 'root'}.json"
    return build_call("list", _LIST_URL, params, name)


def plan_meta(stat_id: str = "", org_id: str = "", tbl_id: str = "", meta_itm: str = "ALL") -> dict[str, Any]:
    params = {"method": "getList", "metaItm": meta_itm, "format": "json", "jsonVD": "Y"}
    if stat_id:
        params["statId"] = stat_id
        target = _safe(stat_id)
    else:
        if not (org_id and tbl_id):
            raise ValueError("meta 는 --stat-id 또는 --org-id·--tbl-id 가 필요합니다")
        params["orgId"] = org_id
        params["tblId"] = tbl_id
        target = f"{_safe(org_id)}-{_safe(tbl_id)}"
    return build_call("meta", _EXPL_URL, params, f"kosis/meta-{target}-{_safe(meta_itm)}.json")


def plan_indicator(jipyo_id: str, page_no: int = 1, num_of_rows: int = 10) -> dict[str, Any]:
    params = {"method": "getList", "service": "1", "serviceDetail": "pkAll", "jipyoId": jipyo_id,
              "pageNo": str(page_no), "numOfRows": str(num_of_rows), "format": "json"}
    return build_call("indicator", _INDICATOR_URL, params,
                      f"kosis/indicator-{_safe(jipyo_id)}-p{page_no}-n{num_of_rows}.json")


# --- 응답 파일 판독 ---

def _read_bytes(path: str | Path) -> bytes:
    """입력 파일에서 응답 본문을 꺼낸다 — hyve 층 판독은 공용 ``hyve_input`` 이 한다.

    HTTP 오류면 본문의 KOSIS err 를 먼저 본다(그쪽이 더 구체적이다). 403 은 게이트웨이 권한 거부다.
    """
    p = Path(path).expanduser()
    try:
        return read_input(p).data
    except HyveHTTPError as exc:
        _raise_kosis_error(exc.body)
        if exc.status == 403:
            raise InputFileError(
                f"권한 거부 (HTTP 403) — 활용신청이 필요할 수 있습니다({p.name}).{_KOSIS_SETUP_GUIDE}",
                kind="http",
            ) from exc
        raise InputFileError(str(exc), kind=exc.kind) from exc
    except HyveInputError as exc:
        raise InputFileError(str(exc), kind=exc.kind) from exc


def _raise_kosis_error(body: bytes) -> None:
    """본문이 KOSIS 오류 형태(JSON·따옴표 없는 JSON·XML)면 KOSISAPIError. 아니면 조용히 돌아온다."""
    text = body.decode("utf-8", "replace").strip()
    code = msg = None
    if text.startswith("<"):
        if "<err>" in text:
            try:
                root = ET.fromstring(text)
                code = (root.findtext("err") or "").strip()
                msg = (root.findtext("errMsg") or "").strip()
            except ET.ParseError:
                m = re.search(r"<err>\s*(\w+)\s*</err>", text)
                code, msg = (m.group(1) if m else ""), ""
    elif text.startswith("{") and "err" in text[:200]:
        data: Any = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                data = _fix_unquoted_json(text)
            except KOSISAPIError:
                m = re.search(r'"?err"?\s*:\s*"?(\w+)"?', text)
                code, msg = (m.group(1), "") if m else (None, None)
        if isinstance(data, dict) and "err" in data:
            code, msg = str(data.get("err", "")), str(data.get("errMsg", ""))
    if code is None:
        return
    hint_msg, _cat = _classify_kosis_error(code)
    raise KOSISAPIError(f"KOSIS API 오류 ({code}): {msg or '알 수 없는 오류'} | {hint_msg}", error_code=code or None)


def load_json(path: str | Path) -> list[dict[str, Any]] | dict[str, Any]:
    """저장된 KOSIS JSON 응답 파일 하나를 읽는다 — 오류 응답이면 예외.

    Raises:
        InputFileError: 파일 없음·절단·HTTP 오류·itda-hyve 실패·KOSIS 응답 아님(HTML 오류 페이지 등).
        KOSISAPIError: 본문이 KOSIS 오류(err 코드).
    """
    p = Path(path).expanduser()
    body = _read_bytes(p)
    _raise_kosis_error(body)
    text = body.decode("utf-8", "replace").lstrip("﻿")
    stripped = text.lstrip()
    if stripped.startswith("<"):
        raise InputFileError(
            f"KOSIS JSON 응답이 아닙니다({p.name}) — HTML·XML 이 왔다. 호출 URL 이 plan 이 준 것과 같은지 확인하세요"
            " (오타 URL 은 HTTP 404 HTML 을 준다)."
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = _fix_unquoted_json(text)
        except KOSISAPIError as exc:
            raise InputFileError(
                f"KOSIS 응답을 JSON 으로 읽지 못했습니다({p.name}) — 본문이 잘렸을 수 있다: {exc}",
                kind="truncated",
            ) from exc
    if not isinstance(data, (list, dict)):
        raise InputFileError(f"KOSIS 응답 형태가 아닙니다({p.name}): {type(data).__name__}")
    return data


def load_sdmx(path: str | Path) -> str:
    """저장된 SDMX(Generic) 응답 파일을 읽는다 — 오류 응답이면 예외."""
    p = Path(path).expanduser()
    body = _read_bytes(p)
    _raise_kosis_error(body)
    text = body.decode("utf-8", "replace").lstrip("﻿")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise InputFileError(
            f"SDMX XML 을 읽지 못했습니다({p.name}) — 본문이 잘렸거나 XML 이 아니다: {exc}", kind="truncated",
        ) from exc
    if not root.tag.endswith("GenericData"):
        raise InputFileError(f"SDMX Generic 응답이 아닙니다({p.name}): 루트 {root.tag}")
    return text


def _fix_unquoted_json(text: str) -> dict[str, Any] | list[dict[str, Any]]:
    """KOSIS 비표준 JSON을 파싱.

    KOSIS 응답은 키에 따옴표가 없는 JavaScript 객체 표기법:
        [{ORG_ID:"101",TBL_NM:"인구(시도)"}]
    값 내부에 콜론이 포함될 수 있어 단순 regex 치환은 불안전.
    문자열 밖의 키만 정확히 따옴표로 감싸는 상태 머신 방식으로 변환.

    Args:
        text: 비표준 JSON 문자열.

    Returns:
        파싱된 딕셔너리 또는 리스트.

    Raises:
        KOSISAPIError: 변환 후에도 파싱 실패.
    """
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # 문자열 리터럴: 그대로 복사
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            result.append(text[i:j])
            i = j
            continue

        # { 또는 , 뒤의 키 (따옴표 없는 식별자):  key: → "key":
        if ch in '{,' :
            result.append(ch)
            i += 1
            # 공백 건너뛰기
            while i < n and text[i] in ' \t\n\r':
                result.append(text[i])
                i += 1
            # 따옴표 없는 키 탐지: [A-Za-z_][A-Za-z0-9_]* 뒤에 : 이 오는 패턴
            if i < n and text[i] != '"' and text[i] != '{' and text[i] != '[':
                key_start = i
                while i < n and (text[i].isalnum() or text[i] == '_'):
                    i += 1
                if i < n and text[i] == ':':
                    # 키에 따옴표 추가
                    result.append('"')
                    result.append(text[key_start:i])
                    result.append('"')
                else:
                    result.append(text[key_start:i])
            continue

        result.append(ch)
        i += 1

    fixed = "".join(result)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as exc:
        raise KOSISAPIError(f"JSON 파싱 실패: {exc}") from exc



# --- 분류축 슬롯(objL 번호) 해석 ---
#
# KOSIS 통계표의 분류축은 getMeta type=ITM 의 OBJ_ID_SN(분류 일련번호)이 지목하는
# objL 슬롯으로만 호출된다. 대부분의 표는 OBJ_ID_SN=1 부터 시작하지만 **항상 그렇지
# 않다** — 한국보건산업진흥원(orgId 358) 표들은 첫 축이 OBJ_ID_SN=2 라 objL1 을 보내면
# KOSIS 가 오류 21(잘못된 요청 변수)로 거부한다(#1684 실측 2026-09-11).
#
# 더 고약한 것은 그 표들의 **JSON 직렬화**다. objL2 로 정확히 호출하면 오류는 사라지지만
# JSON 은 빈 배열 `[]` 을 돌려준다(C1 이 없는 표를 JSON 빌더가 비워 버린다). 같은 요청의
# SDMX(Generic)에는 데이터가 전부 들어 있다 — 그래서 슬롯 1 이 없는 표는 SDMX 가 정본
# 전송 형식이다. 실측 대조(#1684):
#   358/DT_358004_008 slots=[2]    json=0건  sdmx=54건
#   358/DT_358004_007 slots=[2,3]  json=0건  sdmx=70건
#   358/DT_358004_001 slots=[1,2]  json=190건 sdmx=190건   ← 기관이 아니라 표 단위 성질
#   101/DT_1K41014    slots=[1]    json=84건  sdmx=84건
_ITEM_AXIS_IDS = ("ITEM",)


def _axis_sort_key(axis: dict[str, Any]) -> int:
    return int(axis.get("slot") or 0)


def _as_list(data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """KOSIS 응답을 항상 리스트로 정규화 (getMeta type=TBL/ORG 등은 단일 dict)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def table_axes(itm_rows: list[dict[str, Any]], tbl_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """getMeta type=ITM(과 선택적으로 TBL) 응답에서 분류축 구조(objL 슬롯)와 항목 코드를 푼다.

    getMeta type=ITM 응답의 OBJ_ID_SN 을 그대로 objL 슬롯으로 쓴다 — 추측하지 않는다.

    Returns:
        {"table_name": str, "items": [{"id","name","unit_id","unit_name"}],
         "axes": [{"slot": int, "obj_id", "obj_name", "values": [{"code","name","parent"}]}]}  # slot 오름차순
    """
    items: list[dict[str, str]] = []
    axis_map: dict[str, dict[str, Any]] = {}

    for row in itm_rows:
        obj_id = row.get("OBJ_ID", "") or ""
        if obj_id in _ITEM_AXIS_IDS or row.get("OBJ_NM") == "항목":
            items.append({
                "id": row.get("ITM_ID", "") or "",
                "name": row.get("ITM_NM", "") or "",
                "unit_id": row.get("UNIT_ID", "") or "",
                "unit_name": row.get("UNIT_NM", "") or "",
            })
            continue
        axis = axis_map.setdefault(obj_id, {
            "slot": int(row.get("OBJ_ID_SN") or 0) or None,
            "obj_id": obj_id,
            "obj_name": row.get("OBJ_NM", "") or "",
            "values": [],
        })
        axis["values"].append({
            "code": row.get("ITM_ID", "") or "",
            "name": row.get("ITM_NM", "") or "",
            "parent": row.get("UP_ITM_ID", "") or "",
        })

    axes = list(axis_map.values())
    # OBJ_ID_SN 이 비어 오는 표는 등장 순서를 슬롯으로 본다(관측 불가 → 보수적 기본값).
    for idx, axis in enumerate(axes, start=1):
        if not axis["slot"]:
            axis["slot"] = idx
    axes.sort(key=_axis_sort_key)

    table_name = ""
    if tbl_rows:
        table_name = tbl_rows[0].get("TBL_NM", "") or ""
    return {"table_name": table_name, "items": items, "axes": axes}


def _describe_axes(structure: dict[str, Any]) -> str:
    """분류축 구조를 사용자 안내 문장으로."""
    axes = structure.get("axes") or []
    if not axes:
        return "이 통계표에는 분류축이 없습니다."
    parts = []
    for axis in axes:
        sample = ", ".join(v["code"] for v in axis["values"][:4])
        more = " …" if len(axis["values"]) > 4 else ""
        parts.append(
            f"objL{axis['slot']}={axis['obj_name']}({axis['obj_id']}) 예: {sample}{more}"
        )
    return " / ".join(parts)


def _build_data_params(
    org_id: str,
    tbl_id: str,
    itm_id: str,
    slot_values: dict[int, str],
    prd_se: str,
    start_prd_de: str,
    end_prd_de: str,
    new_est_prd_cnt: int | None,
) -> dict[str, str]:
    """통계자료 요청 파라미터 조립 (objL 슬롯은 호출자가 확정해 넘긴다)."""
    params: dict[str, str] = {
        "method": "getList",
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": itm_id,
        "prdSe": prd_se,
        "format": "json",
        "jsonVD": "Y",
    }
    # objL 은 값이 있는 슬롯만 — 빈 문자열 전송 시 KOSIS 가 오류 21 로 거부한다.
    for slot in sorted(slot_values):
        value = slot_values[slot]
        if value:
            params[f"objL{slot}"] = value

    if new_est_prd_cnt is not None:
        params["newEstPrdCnt"] = str(new_est_prd_cnt)
    else:
        if start_prd_de:
            params["startPrdDe"] = start_prd_de
        if end_prd_de:
            params["endPrdDe"] = end_prd_de
    return params


def _parse_sdmx_generic(
    xml_text: str,
    structure: dict[str, Any],
    org_id: str,
    tbl_id: str,
) -> list[dict[str, Any]]:
    """SDMX Generic 응답을 KOSIS JSON 행 스키마로 환원.

    SeriesKey 는 코드만 싣는다(FREQ/ITEM/C_<OBJ_ID>) — 이름·단위는 getMeta 원본
    (structure)에서만 채운다. 추측하지 않는다(data-accuracy).
    """
    root = ET.fromstring(xml_text)

    axes = sorted(structure.get("axes") or [], key=_axis_sort_key)
    # C_<OBJ_ID> → (출력 열 번호 C1..Cn, 축 메타)
    axis_by_key = {f"C_{a['obj_id']}": (i, a) for i, a in enumerate(axes, start=1)}
    name_by_axis = {
        a["obj_id"]: {v["code"]: v["name"] for v in a["values"]} for a in axes
    }
    item_by_id = {i["id"]: i for i in (structure.get("items") or [])}
    # 단위명은 getMeta 가 준 UNIT_ID→UNIT_NM 대응에서만 채운다 — SDMX 는 단위 코드만 싣고,
    # 대응이 없으면 이름을 지어내지 않고 코드만 남긴다(data-accuracy).
    unit_name_by_id = {
        i["unit_id"]: i["unit_name"]
        for i in (structure.get("items") or [])
        if i.get("unit_id") and i.get("unit_name")
    }
    table_name = structure.get("table_name", "")

    rows: list[dict[str, Any]] = []
    for series in root.iter(f"{{{_SDMX_NS['generic']}}}Series"):
        key_el = series.find(f"{{{_SDMX_NS['generic']}}}SeriesKey")
        keys: dict[str, str] = {}
        if key_el is not None:
            for val in key_el.findall(f"{{{_SDMX_NS['generic']}}}Value"):
                keys[val.get("id", "")] = val.get("value", "")

        itm_id = keys.get("ITEM", "")
        item = item_by_id.get(itm_id, {})
        base: dict[str, Any] = {
            "ORG_ID": org_id,
            "TBL_ID": tbl_id,
            "TBL_NM": table_name,
            "ITM_ID": itm_id,
            "ITM_NM": item.get("name", ""),
            "UNIT_ID": item.get("unit_id", ""),
            "UNIT_NM": item.get("unit_name", ""),
            "PRD_SE": keys.get("FREQ", ""),
        }
        for key_id, code in keys.items():
            mapped = axis_by_key.get(key_id)
            if mapped is None:
                continue
            col, axis = mapped
            base[f"C{col}"] = code
            base[f"C{col}_NM"] = name_by_axis[axis["obj_id"]].get(code, "")
            base[f"C{col}_OBJ_NM"] = axis["obj_name"]

        for obs in series.findall(f"{{{_SDMX_NS['generic']}}}Obs"):
            dim = obs.find(f"{{{_SDMX_NS['generic']}}}ObsDimension")
            val = obs.find(f"{{{_SDMX_NS['generic']}}}ObsValue")
            chn = obs.find(f"{{{_SDMX_NS['generic']}}}LstChnDe")
            row = dict(base)
            row["PRD_DE"] = dim.get("value", "") if dim is not None else ""
            row["DT"] = val.get("value", "") if val is not None else ""
            row["LST_CHN_DE"] = chn.get("value", "") if chn is not None else ""
            # 단위는 관측치 단위(Attributes UNIT)가 항목 단위보다 정확하다
            # (예: 358/DT_358004_007 은 매출현황별 축에 따라 단위가 갈린다).
            attrs = obs.find(f"{{{_SDMX_NS['generic']}}}Attributes")
            if attrs is not None:
                for aval in attrs.findall(f"{{{_SDMX_NS['generic']}}}Value"):
                    if aval.get("id") == "UNIT":
                        unit_id = aval.get("value", "")
                        if unit_id:
                            row["UNIT_ID"] = unit_id
                            row["UNIT_NM"] = unit_name_by_id.get(
                                unit_id, row.get("UNIT_NM", "") or "",
                            )
            rows.append(row)

    return rows



# --- data: 적응형 3단 흐름 (1차 JSON → getMeta 로 축 재매핑 → JSON 재호출 또는 SDMX) ---
#
# 옛 스크립트는 한 실행 안에서 1~3번 불렀다. 지금은 스크립트가 다음에 받을 호출을 ``next_calls``
# 로 내고, 모델이 itda-hyve 로 받아 **지금까지의 파일 전부**를 다시 넘기는 루프다. 단계는 파일
# 이름이 가른다 — ``data-<org>-<tbl>-<질의지문>-{json1|json2|sdmx}`` · ``info-<org>-<tbl>-{ITM|TBL}``.

_DATA_NAME_RE = re.compile(r"^data-(?P<org>[^-]+)-(?P<tbl>.+)-(?P<qh>[0-9a-f]{8})-(?P<stage>json1|json2|sdmx)\.(?:json|xml)$")
_INFO_NAME_RE = re.compile(r"^info-(?P<org>[^-]+)-(?P<tbl>.+)-(?P<type>ITM|TBL)\.json$")


class DataQuery:
    """data 명령의 질의 — plan 과 가공이 같은 인자로 같은 지문·호출을 만든다."""

    def __init__(
        self,
        org_id: str,
        tbl_id: str,
        itm_id: str = "ALL",
        obj_l1: str = "ALL",
        obj_l2: str = "",
        obj_l3: str = "",
        obj_l4: str = "",
        prd_se: str = "Y",
        start_prd_de: str = "",
        end_prd_de: str = "",
        new_est_prd_cnt: int | None = None,
    ):
        self.org_id = org_id
        self.tbl_id = tbl_id
        self.itm_id = itm_id or "ALL"
        logical = [obj_l1 or "ALL", obj_l2 or "", obj_l3 or "", obj_l4 or ""]
        while len(logical) > 1 and not logical[-1]:
            logical.pop()
        self.logical = logical
        self.prd_se = prd_se
        self.start_prd_de = "" if new_est_prd_cnt is not None else (start_prd_de or "")
        self.end_prd_de = "" if new_est_prd_cnt is not None else (end_prd_de or "")
        self.new_est_prd_cnt = new_est_prd_cnt

    def fingerprint(self) -> str:
        return query_hash({
            "org": self.org_id, "tbl": self.tbl_id, "itm": self.itm_id, "obj": self.logical,
            "prd": self.prd_se, "start": self.start_prd_de, "end": self.end_prd_de,
            "recent": self.new_est_prd_cnt,
        })

    def save_name(self, stage: str) -> str:
        ext = "xml" if stage == "sdmx" else "json"
        return f"kosis/data-{_safe(self.org_id)}-{_safe(self.tbl_id)}-{self.fingerprint()}-{stage}.{ext}"

    def params(self, slot_values: dict[int, str]) -> dict[str, str]:
        return _build_data_params(
            self.org_id, self.tbl_id, self.itm_id, slot_values,
            self.prd_se, self.start_prd_de, self.end_prd_de, self.new_est_prd_cnt,
        )

    def naive_slots(self) -> dict[int, str]:
        return {i: v for i, v in enumerate(self.logical, start=1)}

    def first_call(self) -> dict[str, Any]:
        return build_call("data-json1", _DATA_URL, self.params(self.naive_slots()), self.save_name("json1"))

    def meta_calls(self) -> list[dict[str, Any]]:
        return [plan_info(self.org_id, self.tbl_id, "ITM"), plan_info(self.org_id, self.tbl_id, "TBL")]

    def remapped_slots(self, structure: dict[str, Any]) -> dict[int, str]:
        """논리 순서 값 → 실제 슬롯 (부족분은 ALL)."""
        slot_values: dict[int, str] = {}
        for idx, axis in enumerate(structure["axes"]):
            value = self.logical[idx] if idx < len(self.logical) else ""
            slot_values[int(axis["slot"])] = value or "ALL"
        return slot_values

    def json2_call(self, slot_values: dict[int, str]) -> dict[str, Any]:
        return build_call("data-json2", _DATA_URL, self.params(slot_values), self.save_name("json2"))

    def sdmx_call(self, slot_values: dict[int, str]) -> dict[str, Any]:
        params = self.params(slot_values)
        params["format"] = "sdmx"
        params["type"] = "Generic"
        params.pop("jsonVD", None)
        return build_call("data-sdmx", _DATA_URL, params, self.save_name("sdmx"))


def _classify_data_files(query: DataQuery, paths: list[str]) -> dict[str, Path]:
    """입력 파일을 단계별로 가른다. 다른 질의·다른 표의 파일이나 이름 규칙 위반은 오류."""
    found: dict[str, Path] = {}
    qh = query.fingerprint()
    org, tbl = _safe(query.org_id), _safe(query.tbl_id)
    for raw in paths:
        p = Path(raw).expanduser()
        m = _DATA_NAME_RE.match(p.name)
        if m:
            if (m["org"], m["tbl"]) != (org, tbl):
                raise InputFileError(f"다른 통계표의 파일입니다: {p.name} (지금 질의 {query.org_id}/{query.tbl_id})")
            if m["qh"] != qh:
                raise InputFileError(
                    f"다른 조회 조건으로 받은 파일입니다: {p.name} (지금 질의 지문 {qh}) — "
                    "plan 과 같은 인자(--item·--obj1~4·--period·--start/--end/--recent)로 가공하세요"
                )
            key = m["stage"]
        else:
            m = _INFO_NAME_RE.match(p.name)
            if not m:
                raise InputFileError(
                    f"파일 이름이 규칙과 다릅니다: {p.name} — plan·next_calls 가 준 save_as 를 그대로 쓰세요"
                )
            if (m["org"], m["tbl"]) != (org, tbl):
                raise InputFileError(f"다른 통계표의 메타 파일입니다: {p.name}")
            key = f"meta-{m['type']}"
        if key in found:
            raise InputFileError(f"같은 단계 파일이 두 번 들어왔습니다: {found[key].name}, {p.name}")
        found[key] = p
    return found


def _need(message: str, calls: list[dict[str, Any]], stage: str) -> IncompleteError:
    return IncompleteError(message, calls, stage)


def resolve_data(query: DataQuery, paths: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """저장된 파일들로 data 를 끝까지 푼다. 다음 응답이 필요하면 :class:`IncompleteError`.

    Returns:
        (행 목록, 진단 dict). 진단:
        {"transport": "json"|"sdmx", "axis_slots": [int], "resolved": bool,
         "axes": [{"slot","obj_id","obj_name"}], "notes": [str], "stage": str}
    """
    files = _classify_data_files(query, paths)
    notes: list[str] = []

    if "json1" not in files:
        raise _need("1차 응답 파일이 없습니다 — next_calls 의 호출을 받아 함께 넘기세요", [query.first_call()], "json1")

    naive = query.naive_slots()
    try:
        rows = _as_list(load_json(files["json1"]))
        return rows, {
            "transport": "json",
            "axis_slots": sorted(s for s, v in naive.items() if v),
            "resolved": False, "axes": [], "notes": notes, "stage": "json1",
        }
    except KOSISAPIError as exc:
        # 슬롯이 어긋난 표는 KOSIS 가 오류 20/21 로 거부한다 — 그때만 getMeta 로 실제 슬롯을 실측한다(추측 금지).
        if exc.error_code not in ("20", "21"):
            raise
        naive_error = exc
    notes.append(
        f"기본 슬롯(objL1~) 호출이 오류 {naive_error.error_code} 로 거부돼 "
        "통계표 분류축 구조(getMeta OBJ_ID_SN)를 받아 다시 불렀습니다."
    )

    if "meta-ITM" not in files:
        raise _need(
            f"1차 호출이 오류 {naive_error.error_code} 로 거부됐습니다 — 분류축 구조(getMeta ITM·TBL)를 받아 "
            "지금까지의 파일과 함께 넘기세요",
            query.meta_calls(), "meta",
        )
    try:
        itm_rows = _as_list(load_json(files["meta-ITM"]))
    except KOSISAPIError as exc:
        raise KOSISAPIError(
            f"{naive_error} | 분류축 구조 조회도 실패했습니다({exc}). "
            f"`info --org-id {query.org_id} --tbl-id {query.tbl_id}` 로 축을 직접 확인하세요.",
            error_code=naive_error.error_code,
        ) from exc
    tbl_rows: list[dict[str, Any]] = []
    if "meta-TBL" in files:
        try:
            tbl_rows = _as_list(load_json(files["meta-TBL"]))
        except KOSISAPIError as exc:
            notes.append(f"통계표 이름(getMeta TBL)을 받지 못했습니다: {exc.error_code}")

    structure = table_axes(itm_rows, tbl_rows)
    if not structure["axes"]:
        raise KOSISAPIError(
            f"{naive_error} | 이 통계표({query.org_id}/{query.tbl_id})의 분류축 메타(getMeta type=ITM)가 "
            "비어 있습니다 — KOSIS 사이트에서 통계표 제공 상태를 확인하세요.",
            error_code=naive_error.error_code,
        )

    slot_values = query.remapped_slots(structure)
    slots = sorted(slot_values)
    axis_summary = [
        {"slot": int(a["slot"]), "obj_id": a["obj_id"], "obj_name": a["obj_name"]}
        for a in structure["axes"]
    ]

    if slots and slots[0] == 1:
        # 슬롯 1 이 있는 표 — JSON 이 정상 동작한다.
        if "json2" not in files:
            raise _need("분류축 슬롯을 다시 맞춘 호출을 받아 지금까지의 파일과 함께 넘기세요",
                        [query.json2_call(slot_values)], "json2")
        try:
            rows = _as_list(load_json(files["json2"]))
        except KOSISAPIError as exc:
            if exc.error_code == "21":
                raise KOSISAPIError(
                    f"{exc} | 이 통계표의 분류축은 {_describe_axes(structure)} 입니다. "
                    f"`info --org-id {query.org_id} --tbl-id {query.tbl_id}` 로 코드를 확인하세요.",
                    error_code=exc.error_code,
                ) from exc
            raise
        if not rows:
            notes.append("KOSIS 가 빈 응답을 돌려줬습니다 — 조회 조건(시점·분류값)을 확인하세요.")
        return rows, {"transport": "json", "axis_slots": slots, "resolved": True,
                      "axes": axis_summary, "notes": notes, "stage": "json2"}

    # 슬롯 1 이 없는 표 — KOSIS JSON 직렬화가 빈 배열을 내므로 SDMX 가 정본이다.
    notes.append(
        f"이 통계표의 첫 분류축이 objL{slots[0]} 입니다(objL1 없음). "
        "KOSIS JSON 은 이런 표에 빈 응답을 돌려주므로 SDMX(Generic) 경로로 조회했습니다."
    )
    if "sdmx" not in files:
        raise _need("첫 분류축이 objL1 이 아닌 표입니다 — SDMX 호출을 받아 지금까지의 파일과 함께 넘기세요",
                    [query.sdmx_call(slot_values)], "sdmx")
    try:
        xml_text = load_sdmx(files["sdmx"])
    except KOSISAPIError as exc:
        if exc.error_code in ("20", "21"):
            raise KOSISAPIError(
                f"{exc} | 이 통계표의 분류축은 {_describe_axes(structure)} 입니다. "
                f"`info --org-id {query.org_id} --tbl-id {query.tbl_id}` 로 코드를 확인하세요.",
                error_code=exc.error_code,
            ) from exc
        raise
    rows = _parse_sdmx_generic(xml_text, structure, query.org_id, query.tbl_id)
    if not rows:
        notes.append("SDMX 응답에도 관측값이 없습니다 — 조회 조건(시점·분류값)을 확인하세요.")
    return rows, {"transport": "sdmx", "axis_slots": slots, "resolved": True,
                  "axes": axis_summary, "notes": notes, "stage": "sdmx"}


def parse_value(dt_str: str) -> float | None:
    """KOSIS DT 필드 값을 숫자로 변환 (``-``·``…``·``x`` 등은 None)."""
    if not dt_str or str(dt_str).strip() in ("-", "…", "x", "X", ""):
        return None
    try:
        return float(str(dt_str).replace(",", ""))
    except ValueError:
        return None


def summarize_data(
    data: list[dict[str, Any]],
    value_field: str = "DT",
) -> list[dict[str, Any]]:
    """통계 데이터를 제안서용 요약 형태로 정리.

    Returns:
        [{period, item_name, category, value, unit, ...}, ...] — 값이 숫자가 아닌 행은 뺀다.
    """
    results: list[dict[str, Any]] = []

    for row in data:
        value = parse_value(row.get(value_field, ""))
        if value is None:
            continue

        entry = {
            "period": row.get("PRD_DE", ""),
            "item_name": row.get("ITM_NM", ""),
            "item_name_eng": row.get("ITM_NM_ENG", ""),
            "category": row.get("C1_NM", ""),
            "category_eng": row.get("C1_NM_ENG", ""),
            "value": value,
            "unit": row.get("UNIT_NM", ""),
            "table_name": row.get("TBL_NM", ""),
            "org_id": row.get("ORG_ID", ""),
            "tbl_id": row.get("TBL_ID", ""),
        }
        # 2중 분류표(예: 358/DT_358004_007)는 C2 가 있어야 행이 식별된다.
        if row.get("C2_NM") or row.get("C2"):
            entry["category2"] = row.get("C2_NM", "")
            entry["category2_code"] = row.get("C2", "")
        results.append(entry)

    return results


def find_region_code(itm_rows: list[dict[str, Any]], region: str) -> list[dict[str, Any]]:
    """자연어 지역명을 통계표별 분류(objL) 코드로 매핑 — getMeta type=ITM 응답에서만 찾는다.

    코드↔이름 대조는 KOSIS 응답 원본에서만 하고 추측하지 않는다(data-accuracy).
    getMeta type=ITM 실측 구조(#1145): 각 행은 분류값 1건. OBJ_ID/OBJ_NM=분류축,
    ITM_ID/ITM_NM=값 코드/이름(항목축 OBJ_ID="ITEM"은 제외).

    Returns:
        매칭 후보 목록 (일치도 높은 순): [{code, name, axis_id, axis_name}, ...]
    """
    tokens = [t for t in region.replace(",", " ").split() if t]
    scored: list[tuple[int, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    for row in itm_rows:
        axis_id = row.get("OBJ_ID", "")
        axis_name = row.get("OBJ_NM", "")
        if axis_id == "ITEM" or axis_name == "항목":
            continue
        name = row.get("ITM_NM", "")
        code = row.get("ITM_ID", "")
        key = (code, name)
        if not name or key in seen:
            continue
        seen.add(key)
        score = sum(1 for t in tokens if t in name)
        if score:
            scored.append((score, {
                "code": code,
                "name": name,
                "axis_id": axis_id,
                "axis_name": axis_name,
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _score, item in scored]
