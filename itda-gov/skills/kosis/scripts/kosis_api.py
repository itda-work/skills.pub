"""KOSIS 국가통계포털 OpenAPI 클라이언트.

제안서/사업계획서에 필요한 통계 데이터 수집:
    - 통합검색 (키워드 → 통계표 목록)
    - 통계자료 조회 (orgId + tblId → 실제 데이터)

엔드포인트: https://kosis.kr/openapi/
인증: apiKey 쿼리 파라미터
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT = 15

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

# 활용신청 페이지 — 인증키 관련 오류 시 사용자에게 자동 부착
_KOSIS_APPLY_URL = "https://kosis.kr/openapi/"

_KOSIS_SETUP_GUIDE = (
    "\n[설정 안내] KOSIS_API_KEY를 확인하세요:\n"
    f"  1. {_KOSIS_APPLY_URL} 접속 → 회원가입 → Open API → 활용신청\n"
    "  2. 활용신청 즉시 자동 승인 (대기 없음). 마이페이지에서 인증키 확인\n"
    "  3. 작업 폴더 루트(예: outputs/)에 .env 파일로 설정:\n"
    "       KOSIS_API_KEY=발급받은_키\n"
    "  4. 첫 호출 실패 시 점검 절차:\n"
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


def _classify_kosis_error(error_code: str) -> tuple[str, str]:
    """KOSIS API 오류 코드를 사용자 메시지와 카테고리로 분류.

    정본 에러 코드 표(_ERROR_CODE_HINTS)에서 한글 설명을 가져오고,
    인증키 관련(10/11/42)은 활용신청 URL을 자동 부착한다.

    Args:
        error_code: KOSIS API err 코드.

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
            f"{hint['desc']} (오류 코드: {error_code}) — 잠시 후 재시도하세요.",
            hint["category"],
        )
    if error_code in ("30", "31"):
        return (
            f"조회 결과 이슈 (오류 코드: {error_code}, {hint['desc']})",
            hint["category"],
        )
    # 20, 21, 기타: setup
    return (
        f"KOSIS API 오류 (오류 코드: {error_code}, {hint['desc']}) — 요청 파라미터를 확인하세요.",
        hint["category"],
    )


class KOSISAPIError(Exception):
    """KOSIS API 호출 오류."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


def _request(url: str, params: dict[str, str]) -> list[dict[str, Any]] | dict[str, Any]:
    """KOSIS API 호출.

    Args:
        url: 엔드포인트 URL.
        params: 쿼리 파라미터.

    Returns:
        파싱된 JSON 응답 (리스트 또는 딕셔너리).

    Raises:
        KOSISAPIError: 네트워크 오류, 파싱 실패, API 오류.
    """
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    full_url = f"{url}?{query}"

    try:
        with urllib.request.urlopen(full_url, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        # @MX:NOTE: HTTP 403은 게이트웨이 단계 권한 거부 — 활용신청 안내 부착.
        if exc.code == 403:
            raise KOSISAPIError(
                f"권한 거부 (HTTP 403) — 활용신청이 필요할 수 있습니다."
                f"{_KOSIS_SETUP_GUIDE}",
                error_code="HTTP_403",
            ) from exc
        raise KOSISAPIError(f"네트워크 오류: {exc}") from exc
    except urllib.error.URLError as exc:
        raise KOSISAPIError(f"네트워크 오류: {exc}") from exc

    text = raw.decode("utf-8")

    # KOSIS 에러 응답은 비표준 JSON (키에 따옴표 없음):
    #   {err:"10",errMsg:"인증KEY값이 누락되었습니다."}
    # 표준 JSON으로 변환 후 파싱
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _fix_unquoted_json(text)

    # 에러 응답 확인 — 정본 한글 hint + 활용신청 URL 자동 부착
    if isinstance(data, dict) and "err" in data:
        err_code = str(data.get("err", ""))
        err_msg = data.get("errMsg", "알 수 없는 오류")
        hint_msg, _category = _classify_kosis_error(err_code)
        raise KOSISAPIError(
            f"KOSIS API 오류 ({err_code}): {err_msg} | {hint_msg}",
            error_code=err_code,
        )

    return data


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


# @MX:ANCHOR: [AUTO] KOSIS 통합검색의 핵심 함수.
# @MX:REASON: fan_in >= 3 (collect_stats의 search/data 서브커맨드); 통계표 탐색 진입점.
def search_statistics(
    api_key: str,
    keyword: str,
    start_count: int = 1,
    result_count: int = 10,
) -> list[dict[str, Any]]:
    """키워드로 통계표를 검색.

    Args:
        api_key: KOSIS 인증키.
        keyword: 검색 키워드 (예: "인구", "GDP", "시장 규모").
        start_count: 페이지 번호 (기본 1).
        result_count: 페이지당 결과 수 (기본 10).

    Returns:
        통계표 목록. 각 항목:
        {ORG_ID, ORG_NM, TBL_ID, TBL_NM, STAT_ID, STAT_NM, ...}
    """
    params = {
        "method": "getList",
        "apiKey": api_key,
        "searchNm": keyword,
        "sort": "RANK",
        "startCount": str(start_count),
        "resultCount": str(result_count),
        "format": "json",
    }

    data = _request(_SEARCH_URL, params)
    if isinstance(data, list):
        return data
    return []


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


def get_table_axes(
    api_key: str,
    org_id: str,
    tbl_id: str,
) -> dict[str, Any]:
    """통계표의 분류축 구조(objL 슬롯)와 항목 코드를 해석.

    getMeta type=ITM 응답의 OBJ_ID_SN 을 그대로 objL 슬롯으로 쓴다 — 추측하지 않는다.

    Args:
        api_key: KOSIS 인증키.
        org_id: 기관 코드.
        tbl_id: 통계표 ID.

    Returns:
        {
          "table_name": str,
          "items": [{"id", "name", "unit_id", "unit_name"}],
          "axes": [{"slot": int, "obj_id", "obj_name",
                    "values": [{"code", "name", "parent"}]}],  # slot 오름차순
        }
    """
    rows = get_table_meta(api_key, org_id, tbl_id, meta_type="ITM")

    items: list[dict[str, str]] = []
    axis_map: dict[str, dict[str, Any]] = {}

    for row in rows:
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
    try:
        tbl_meta = get_table_meta(api_key, org_id, tbl_id, meta_type="TBL")
        if tbl_meta:
            table_name = tbl_meta[0].get("TBL_NM", "") or ""
    except KOSISAPIError:
        table_name = ""

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


def _request_sdmx(url: str, params: dict[str, str]) -> str:
    """SDMX(XML) 응답을 원문 문자열로 받는다 — 오류 응답은 KOSISAPIError 로 승격."""
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    try:
        with urllib.request.urlopen(f"{url}?{query}", timeout=_TIMEOUT) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise KOSISAPIError(f"네트워크 오류: {exc}") from exc

    if "<err>" in text:
        try:
            root = ET.fromstring(text)
            err_code = (root.findtext("err") or "").strip()
            err_msg = (root.findtext("errMsg") or "").strip()
        except ET.ParseError:
            err_code, err_msg = "", text[:200]
        hint_msg, _cat = _classify_kosis_error(err_code)
        raise KOSISAPIError(
            f"KOSIS API 오류 ({err_code}): {err_msg} | {hint_msg}",
            error_code=err_code or None,
        )
    return text


def get_statistics_data_ex(
    api_key: str,
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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """통계자료 조회 + 진단 정보.

    obj_l1~obj_l4 는 **통계표의 1~4번째 분류축**(논리 순서)이다. 실제 objL 슬롯은
    getMeta 의 OBJ_ID_SN 이 정하며, 필요할 때만 해석한다(정상 표는 추가 호출 0).

    Returns:
        (행 목록, 진단 dict). 진단:
        {"transport": "json"|"sdmx", "axis_slots": [int], "resolved": bool,
         "axes": [{"slot","obj_id","obj_name"}], "notes": [str]}
    """
    logical = [obj_l1 or "ALL", obj_l2, obj_l3, obj_l4]
    while len(logical) > 1 and not logical[-1]:
        logical.pop()

    notes: list[str] = []

    def _json_call(slot_values: dict[int, str]) -> list[dict[str, Any]]:
        params = _build_data_params(
            org_id, tbl_id, itm_id, slot_values,
            prd_se, start_prd_de, end_prd_de, new_est_prd_cnt,
        )
        params["apiKey"] = api_key
        data = _request(_DATA_URL, params)
        return data if isinstance(data, list) else []

    naive_slots = {i: v for i, v in enumerate(logical, start=1)}
    # 1차 시도는 논리 순서 = objL 슬롯(대다수 통계표의 사실). 정상 표는 여기서 끝나
    # 추가 호출이 0 이다. 슬롯이 어긋난 표는 KOSIS 가 오류 20/21 로 거부하므로,
    # 그때만 getMeta 로 실제 슬롯을 실측해 재시도한다(추측 금지).
    try:
        rows = _json_call(naive_slots)
        return rows, {
            "transport": "json",
            "axis_slots": sorted(s for s, v in naive_slots.items() if v),
            "resolved": False,
            "axes": [],
            "notes": notes,
        }
    except KOSISAPIError as exc:
        if exc.error_code not in ("20", "21"):
            raise
        naive_error: KOSISAPIError = exc
        notes.append(
            f"기본 슬롯(objL1~) 호출이 오류 {exc.error_code} 로 거부돼 "
            "통계표 분류축 구조(getMeta OBJ_ID_SN)를 실측해 재시도했습니다."
        )

    # --- 구조 재확인 (objL 슬롯 실측) ---
    try:
        structure = get_table_axes(api_key, org_id, tbl_id)
    except KOSISAPIError as exc:
        raise KOSISAPIError(
            f"{naive_error} | 분류축 구조 조회도 실패했습니다({exc}). "
            f"`info --org-id {org_id} --tbl-id {tbl_id}` 로 축을 직접 확인하세요.",
            error_code=naive_error.error_code,
        ) from exc

    axes = structure["axes"]
    if not axes:
        raise KOSISAPIError(
            f"{naive_error} | 이 통계표({org_id}/{tbl_id})의 분류축 메타(getMeta type=ITM)가 "
            "비어 있습니다 — KOSIS 사이트에서 통계표 제공 상태를 확인하세요.",
            error_code=naive_error.error_code,
        )

    # 논리 순서 값 → 실제 슬롯 (부족분은 ALL)
    slot_values: dict[int, str] = {}
    for idx, axis in enumerate(axes):
        value = logical[idx] if idx < len(logical) else ""
        slot_values[int(axis["slot"])] = value or "ALL"

    slots = sorted(slot_values)
    axis_summary = [
        {"slot": int(a["slot"]), "obj_id": a["obj_id"], "obj_name": a["obj_name"]}
        for a in axes
    ]

    if slots and slots[0] == 1:
        # 슬롯 1 이 있는 표 — JSON 이 정상 동작한다.
        try:
            rows = _json_call(slot_values)
        except KOSISAPIError as exc:
            if exc.error_code == "21":
                raise KOSISAPIError(
                    f"{exc} | 이 통계표의 분류축은 {_describe_axes(structure)} 입니다. "
                    f"`info --org-id {org_id} --tbl-id {tbl_id}` 로 코드를 확인하세요.",
                    error_code=exc.error_code,
                ) from exc
            raise
        if not rows:
            notes.append("KOSIS 가 빈 응답을 돌려줬습니다 — 조회 조건(시점·분류값)을 확인하세요.")
        return rows, {
            "transport": "json", "axis_slots": slots, "resolved": True,
            "axes": axis_summary, "notes": notes,
        }

    # 슬롯 1 이 없는 표 — KOSIS JSON 직렬화가 빈 배열을 내므로 SDMX 가 정본이다.
    notes.append(
        f"이 통계표의 첫 분류축이 objL{slots[0]} 입니다(objL1 없음). "
        "KOSIS JSON 은 이런 표에 빈 응답을 돌려주므로 SDMX(Generic) 경로로 조회했습니다."
    )
    params = _build_data_params(
        org_id, tbl_id, itm_id, slot_values,
        prd_se, start_prd_de, end_prd_de, new_est_prd_cnt,
    )
    params["format"] = "sdmx"
    params["type"] = "Generic"
    params.pop("jsonVD", None)
    params["apiKey"] = api_key
    try:
        xml_text = _request_sdmx(_DATA_URL, params)
    except KOSISAPIError as exc:
        if exc.error_code in ("20", "21"):
            raise KOSISAPIError(
                f"{exc} | 이 통계표의 분류축은 {_describe_axes(structure)} 입니다. "
                f"`info --org-id {org_id} --tbl-id {tbl_id}` 로 코드를 확인하세요.",
                error_code=exc.error_code,
            ) from exc
        raise
    rows = _parse_sdmx_generic(xml_text, structure, org_id, tbl_id)
    if not rows:
        notes.append("SDMX 응답에도 관측값이 없습니다 — 조회 조건(시점·분류값)을 확인하세요.")
    return rows, {
        "transport": "sdmx", "axis_slots": slots, "resolved": True,
        "axes": axis_summary, "notes": notes,
    }


def get_statistics_data(
    api_key: str,
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
) -> list[dict[str, Any]]:
    """통계자료 조회 (파라미터 방식).

    Args:
        api_key: KOSIS 인증키.
        org_id: 기관 코드 (예: "101" = 통계청).
        tbl_id: 통계표 ID (예: "DT_1B04005N").
        itm_id: 항목 ID ("ALL" 또는 "T2+T3" 등).
        obj_l1: 1번째 분류축 값 ("ALL" 또는 특정 코드).
        obj_l2: 2번째 분류축 값.
        obj_l3: 3번째 분류축 값.
        obj_l4: 4번째 분류축 값.
        prd_se: 수록주기 ("Y"=연, "M"=월, "Q"=분기).
        start_prd_de: 시작 시점 (예: "2020").
        end_prd_de: 종료 시점 (예: "2024").
        new_est_prd_cnt: 최근 N개 시점 (start/end 대신 사용).

    Returns:
        통계 데이터 목록. 각 항목:
        {TBL_NM, C1, C1_NM, ITM_ID, ITM_NM, UNIT_NM, PRD_DE, DT, ...}
    """
    rows, _diag = get_statistics_data_ex(
        api_key, org_id, tbl_id, itm_id=itm_id,
        obj_l1=obj_l1, obj_l2=obj_l2, obj_l3=obj_l3, obj_l4=obj_l4,
        prd_se=prd_se, start_prd_de=start_prd_de, end_prd_de=end_prd_de,
        new_est_prd_cnt=new_est_prd_cnt,
    )
    return rows


def parse_value(dt_str: str) -> float | None:
    """KOSIS DT 필드 값을 숫자로 변환.

    KOSIS는 모든 값을 문자열로 반환하므로 변환이 필요.

    Args:
        dt_str: DT 필드 값 (예: "51740000", "-", "").

    Returns:
        숫자 값, 또는 None (데이터 없음).
    """
    if not dt_str or dt_str.strip() in ("-", "…", "x", "X", ""):
        return None
    try:
        return float(dt_str.replace(",", ""))
    except ValueError:
        return None


def summarize_data(
    data: list[dict[str, Any]],
    value_field: str = "DT",
) -> list[dict[str, Any]]:
    """통계 데이터를 제안서용 요약 형태로 정리.

    Args:
        data: get_statistics_data()의 반환값.
        value_field: 값 필드명 (기본: "DT").

    Returns:
        정리된 데이터:
        [{period, item_name, category, value, unit}, ...]
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


def _as_list(data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """KOSIS 응답을 항상 리스트로 정규화.

    getMeta type=TBL/ORG 등은 단일 dict, type=ITM/PRD 등은 list 를 반환한다.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


# 메타자료 조회유형 — 코드 발견(ITM)이 핵심 진입점
META_TYPES = ("TBL", "ORG", "PRD", "ITM", "CMMT", "UNIT", "SOURCE", "WGT", "NCD")


def get_table_meta(
    api_key: str,
    org_id: str,
    tbl_id: str,
    meta_type: str = "ITM",
    obj_id: str = "",
    itm_id: str = "",
) -> list[dict[str, Any]]:
    """통계표 메타(구조) 조회 — objL·itmId 코드 발견의 정본.

    get_statistics_data 에 넘길 objL/itmId 값을 모를 때, type=ITM 으로
    분류(OBJ_ID/OBJ_NM)와 항목(ITM_ID/ITM_NM) 코드를 확보한다.
    통계자료와 동일 endpoint(statisticsData.do)에 method=getMeta 만 붙인다.

    Args:
        api_key: KOSIS 인증키.
        org_id: 기관 코드.
        tbl_id: 통계표 ID.
        meta_type: 조회유형 (META_TYPES 중 하나, 기본 ITM=분류항목).
        obj_id: 특정 분류 ID 로 필터 (ITM 유형, 선택).
        itm_id: 특정 자료코드 ID 로 필터 (ITM 유형, 선택).

    Returns:
        메타 레코드 목록. type=ITM 예:
        [{OBJ_ID, OBJ_NM, ITM_ID, ITM_NM, UNIT_NM, UP_ITM_ID, OBJ_ID_SN}, ...]
    """
    params: dict[str, str] = {
        "method": "getMeta",
        "apiKey": api_key,
        "orgId": org_id,
        "tblId": tbl_id,
        "type": meta_type,
        "format": "json",
    }
    if obj_id:
        params["objId"] = obj_id
    if itm_id:
        params["itmId"] = itm_id

    return _as_list(_request(_META_URL, params))


def list_statistics(
    api_key: str,
    vw_cd: str = "MT_ZTITLE",
    parent_list_id: str = "",
) -> list[dict[str, Any]]:
    """통계목록 트리 탐색 — 주제별/기관별/국제/지역 통계표를 드릴다운.

    통합검색으로 안 잡히는 국제·OECD 통계(vwCd=MT_RTITLE)나
    지자체 통계(MT_ATITLE01/MT_GTITLE01)의 진입로.

    Args:
        api_key: KOSIS 인증키.
        vw_cd: 서비스뷰 코드 (MT_ZTITLE=주제별, MT_OTITLE=기관별,
            MT_RTITLE=국제통계연감, MT_ATITLE01=지역통계 주제별,
            MT_GTITLE01=e-지방지표 주제별, MT_BUKHAN=북한통계 등).
        parent_list_id: 시작 목록 ID (생략 시 최상위 레벨).

    Returns:
        목록 노드 목록. 각 항목:
        {VW_CD, LIST_ID, LIST_NM, ORG_ID, TBL_ID, TBL_NM, STAT_ID, SEND_DE}
        TBL_ID 가 있으면 잎(통계표), 없으면 하위 드릴다운 대상.
    """
    params: dict[str, str] = {
        "method": "getList",
        "apiKey": api_key,
        "vwCd": vw_cd,
        "format": "json",
        "jsonVD": "Y",
    }
    if parent_list_id:
        params["parentListId"] = parent_list_id

    return _as_list(_request(_LIST_URL, params))


def get_stat_explanation(
    api_key: str,
    stat_id: str = "",
    org_id: str = "",
    tbl_id: str = "",
    meta_itm: str = "ALL",
) -> list[dict[str, Any]]:
    """통계설명자료 조회 — 작성목적·법적근거·조사주기 등.

    Args:
        api_key: KOSIS 인증키.
        stat_id: 통계조사 ID (orgId+tblId 대신 단독 사용 가능).
        org_id: 기관 코드 (stat_id 없을 때).
        tbl_id: 통계표 ID (stat_id 없을 때).
        meta_itm: 요청 항목 (ALL=전체, statsNm=조사명, writingPurps=조사목적,
            basisLaw=법적근거 등 28종, 매뉴얼 §2.4).

    Returns:
        설명 레코드 (통상 1건):
        [{statsNm, statsKind, basisLaw, writingPurps, statsPeriod, ...}]
    """
    params: dict[str, str] = {
        "method": "getList",
        "apiKey": api_key,
        "metaItm": meta_itm,
        "format": "json",
        "jsonVD": "Y",
    }
    if stat_id:
        params["statId"] = stat_id
    else:
        params["orgId"] = org_id
        params["tblId"] = tbl_id

    return _as_list(_request(_EXPL_URL, params))


def get_indicator(
    api_key: str,
    jipyo_id: str,
    page_no: int = 1,
    num_of_rows: int = 10,
) -> list[dict[str, Any]]:
    """통계주요지표 설명자료 조회 — 지표 개념·선정방법·출처.

    지표 고유번호별 설명자료조회(매뉴얼 §2.7.2.1, pkNumberService.do).

    Args:
        api_key: KOSIS 인증키.
        jipyo_id: 지표 ID.
        page_no: 페이지 번호.
        num_of_rows: 페이지당 건수.

    Returns:
        지표 설명 목록:
        [{statJipyoId, statJipyoNm, jipyoExplan, jipyoExplan1}, ...]
    """
    params: dict[str, str] = {
        "method": "getList",
        "service": "1",
        "serviceDetail": "pkAll",
        "apiKey": api_key,
        "jipyoId": jipyo_id,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "format": "json",
    }
    return _as_list(_request(_INDICATOR_URL, params))


def find_region_code(
    api_key: str,
    org_id: str,
    tbl_id: str,
    region: str,
) -> list[dict[str, Any]]:
    """자연어 지역명을 통계표별 분류(objL) 코드로 매핑.

    통계표의 지역 분류(getMeta type=ITM 의 OBJ 값들)를 받아
    지역명과 부분일치하는 후보를 반환한다. 코드↔이름 대조는
    KOSIS 응답 원본에서만 하고 추측하지 않는다(data-accuracy).

    Args:
        api_key: KOSIS 인증키.
        org_id: 기관 코드.
        tbl_id: 통계표 ID.
        region: 지역명 (예: "인천 서구", "강남구").

    Returns:
        매칭 후보 목록 (일치도 높은 순):
        [{code, name, axis_id, axis_name}, ...]
        code=분류값 코드(ITM_ID — objL 인자로 사용), name=지역 국문명(ITM_NM),
        axis_name=분류축 이름(OBJ_NM, 예: "시도별") — 어느 objL 축인지 식별용.

    Note:
        getMeta type=ITM 실측 구조(#1145): 각 행은 분류값 1건.
        OBJ_ID/OBJ_NM=분류축(항목/성별/시도별 등), ITM_ID/ITM_NM=값 코드/이름.
        지역명은 ITM_NM 에, 코드는 ITM_ID 에 있다(항목축 OBJ_ID="ITEM"은 제외).
    """
    meta = get_table_meta(api_key, org_id, tbl_id, meta_type="ITM")

    tokens = [t for t in region.replace(",", " ").split() if t]
    scored: list[tuple[int, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    for row in meta:
        axis_id = row.get("OBJ_ID", "")
        axis_name = row.get("OBJ_NM", "")
        # 항목축(측정 지표)은 지역 후보가 아니므로 제외
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
