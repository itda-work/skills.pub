"""주택 공급·청약 — 호출 계획과 응답 가공 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request``·``batch`` 가 한다(itda-work/skills#45). 이 모듈은
  1. KOSIS 공급 지표·청약홈 분양정보를 받을 **호출 계획**(``http_request`` 인자 그대로)을 만들고
  2. 그렇게 저장한 **응답 파일을 읽어** 오류 판정·전량 대조·정리만 한다.
직접 API 를 부르지 않고 키 값을 보지 않는다(``{{secret:…}}`` 자리표시자만 싣는다).

요청 계약 근거(2026-09-30 판독·실측)는 ``references/api-contract.md`` 에 있다.

- KOSIS 통계자료: ``https://kosis.kr/openapi/Param/statisticsParameterData.do`` (kosis 스킬과 같은 URL).
  옛 ``statisticsParamData.do`` 는 HTTP 404 HTML 이었다(itda-hyve 실측).
- 청약홈 분양정보: data.go.kr 15098547 → ``https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail``.
  옛 ``apis.data.go.kr/B552555/APTInfoSearchService2`` 는 ``returnReasonCode 12``(서비스 없음·폐기)였다.
"""
from __future__ import annotations

import calendar
import json
import math
import re
from pathlib import Path
from typing import Any

from hyve_input import HyveHTTPError, HyveInputError, read_input


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 청약 데이터 시작점 (R18, AC-4 — 이전 구간 보간 금지)
SUBSCRIPTION_DATA_START_YM = "202002"

KOSIS_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
SUBSCRIPTION_URL = (
    "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"
)
KOSIS_SECRET = "{{secret:KOSIS_API_KEY}}"
KO_DATA_SECRET = "{{secret:KO_DATA_API_KEY}}"

# 단건 호출 timeout — Cowork 전송 상한(60초)보다 짧게.
CALL_TIMEOUT = 50
# itda-hyve batch 는 호출이 40개를 넘으면 하나도 실행하지 않는다.
BATCH_MAX = 40
# 청약 한 쪽의 행 수와 쪽 상한(호출 예산).
PER_PAGE = 500
MAX_PAGES = 20

# 지원하는 KOSIS 지표 — 표 ID 는 KOSIS 통합검색·통계표 화면 판독(2026-09-30).
# axes 는 통계표 화면의 분류 수. 모든 분류를 ALL 로 받는다(objL1~objL<axes>).
# region_axes 는 지역이 들어 있는 축 — 분류 ``C<n>`` 이거나 항목 ``ITM``. 착공·준공은 시도가 **항목** 축이다
# (화면 머리 `구 분(1) 부문명(1)`, 열이 시점 × 전국·서울… — W2 리뷰 M3). 나머지 분류는 ``category`` 로 싣는다.
# itmId·objL 슬롯·지역 축은 KOSIS 키가 없어 API 로는 확인하지 못했다(화면 근거 추정 — Cowork 실측 대기).
KOSIS_INDICATORS: dict[str, dict[str, Any]] = {
    "unsold": {"orgId": "116", "tblId": "DT_MLTM_2082", "label": "미분양",
               "table": "시·군·구별 미분양현황", "axes": 2, "cumulative": False,
               "region_axes": ("C1", "C2"), "region_label": "분류 구분(시도)·시군구"},
    "permitted": {"orgId": "116", "tblId": "DT_MLTM_1946", "label": "인허가",
                  "table": "부문별 주택건설 인허가실적(월별 누계)", "axes": 3, "cumulative": True,
                  "region_axes": ("C3",), "region_label": "분류 시도별"},
    "started": {"orgId": "116", "tblId": "DT_MLTM_5386", "label": "착공",
                "table": "주택건설 착공실적(월계)", "axes": 2, "cumulative": False,
                "region_axes": ("ITM",), "region_label": "항목(시도 단위 — 시군구 없음)"},
    "completed": {"orgId": "116", "tblId": "DT_MLTM_5372", "label": "준공",
                  "table": "주택건설 준공실적(월계)", "axes": 2, "cumulative": False,
                  "region_axes": ("ITM",), "region_label": "항목(시도 단위 — 시군구 없음)"},
}

# 지역 축 선언을 응답으로 대조하는 재료(재리뷰 minor 4). 실 KOSIS 행은 분류마다 C<n>_OBJ_NM(분류 이름)을 싣는다.
_REGION_OBJ_WORDS = ("시도", "시군구", "시·군·구", "지역", "행정구역")
_SIDO_NAMES = frozenset({
    "전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
    "전북", "전남", "경북", "경남", "제주", "전남광주", "수도권", "지방",
})

# KOSIS 오류 코드 (매뉴얼 §1.4.2)
_KOSIS_HINTS = {
    "10": "인증키 누락 — itda-hyve GUI 시크릿 탭에 KOSIS_API_KEY 를 등록",
    "11": "인증키 기간만료 — KOSIS 마이페이지에서 연장",
    "20": "필수요청변수 누락 — kosis-plan 이 준 params 를 그대로 보냈는지 확인",
    "21": "잘못된 요청변수 — 표의 분류 수(objL)나 항목이 맞지 않는다",
    "30": "조회결과 없음 — 기간을 확인(수록기간 밖일 수 있다)",
    "31": "조회결과 초과 — 기간을 나눠 여러 번 받는다",
    "40": "호출가능건수 제한 — 잠시 뒤 다시",
    "41": "호출가능 ROW수 제한 — 기간을 나눠 받는다",
    "42": "사용자별 이용 제한 — KOSIS 관리자 문의",
    "50": "KOSIS 서버오류 — 잠시 뒤 다시",
}

# odcloud(청약홈) 오류 코드 — 본문 {"code": 음수, "msg": …}
_ODCLOUD_HINTS = {
    "-401": "인증키 오류 — itda-hyve GUI 시크릿 탭의 KO_DATA_API_KEY(Decoding 키)와 "
            "데이터셋 15098547 활용신청을 확인",
    "-4": "등록되지 않은 인증키이거나 활용신청 전 — 데이터셋 15098547 활용신청을 확인",
}

_MONTH_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])$")
_KOSIS_NAME_RE = re.compile(r"kosis-([a-z]+)-(\d{6})-(\d{6})\.json$")
_SUB_NAME_RE = re.compile(r"subscription-(\d{6})-(\d{6})-p(\d+)\.json$")


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class SupplyAPIError(Exception):
    """저장된 응답이 성공 응답이 아니다(본문의 API 오류 코드)."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class InputFileError(Exception):
    """입력 파일을 가공할 수 없다. ``kind`` 는 출력 ``error`` 값(input·truncated·http·hyve)."""

    def __init__(self, message: str, kind: str = "input"):
        super().__init__(message)
        self.kind = kind


class IncompleteError(Exception):
    """쪽이 모자라다. ``next_calls`` 에 더 받을 호출이 담긴다."""

    def __init__(self, message: str, next_calls: list[dict[str, Any]], **extra: Any):
        super().__init__(message)
        self.next_calls = next_calls
        self.extra = extra


# ---------------------------------------------------------------------------
# 기간
# ---------------------------------------------------------------------------

def check_months(start_ym: str, end_ym: str) -> None:
    """YYYYMM 두 개를 검사한다. 틀리면 ValueError(인자 오류)."""
    for v in (start_ym, end_ym):
        if not _MONTH_RE.match(v or ""):
            raise ValueError(f"월 형식이 올바르지 않습니다: '{v}'. YYYYMM 으로 주세요(예: 202601).")
    if start_ym > end_ym:
        raise ValueError(f"시작월({start_ym})이 종료월({end_ym})보다 늦습니다.")


def _month_bounds(start_ym: str, end_ym: str) -> tuple[str, str]:
    y, m = int(end_ym[:4]), int(end_ym[4:])
    last = calendar.monthrange(y, m)[1]
    return f"{start_ym[:4]}-{start_ym[4:]}-01", f"{end_ym[:4]}-{end_ym[4:]}-{last:02d}"


# ---------------------------------------------------------------------------
# 호출 계획
# ---------------------------------------------------------------------------

def kosis_call(indicator: str, start_ym: str, end_ym: str) -> dict[str, Any]:
    """KOSIS 지표 한 개를 받는 호출 — batch ``calls`` 한 칸 형태(단독 호출은 ``args`` 만)."""
    if indicator not in KOSIS_INDICATORS:
        raise ValueError(f"지원하지 않는 지표: {indicator}. 지원: {list(KOSIS_INDICATORS)}")
    check_months(start_ym, end_ym)
    info = KOSIS_INDICATORS[indicator]
    params: dict[str, str] = {
        "method": "getList",
        "apiKey": KOSIS_SECRET,
        "orgId": info["orgId"],
        "tblId": info["tblId"],
        "itmId": "ALL",
    }
    for n in range(1, int(info["axes"]) + 1):
        params[f"objL{n}"] = "ALL"
    params.update({
        "prdSe": "M",
        "startPrdDe": start_ym,
        "endPrdDe": end_ym,
        "format": "json",
        "jsonVD": "Y",
    })
    return {
        "id": f"kosis-{indicator}-{start_ym}-{end_ym}",
        "tool": "http_request",
        "args": {
            "url": KOSIS_URL,
            "params": params,
            "timeout_sec": CALL_TIMEOUT,
            "save_as": f"supply/kosis-{indicator}-{start_ym}-{end_ym}.json",
        },
    }


def kosis_plan(indicator: str, start_ym: str, end_ym: str) -> dict[str, Any]:
    call = kosis_call(indicator, start_ym, end_ym)
    info = KOSIS_INDICATORS[indicator]
    return {"status": "ok", "indicator": indicator, "table": _table_meta(info),
            "start_month": start_ym, "end_month": end_ym, "calls": [call]}


def subscription_call(start_ym: str, end_ym: str, page: int, per_page: int = PER_PAGE) -> dict[str, Any]:
    """청약홈 분양정보 한 쪽을 받는 호출. 모집공고일(RCRIT_PBLANC_DE)로 기간을 건다."""
    check_months(start_ym, end_ym)
    gte, lte = _month_bounds(start_ym, end_ym)
    return {
        "id": f"subscription-{start_ym}-{end_ym}-p{page}",
        "tool": "http_request",
        "args": {
            "url": SUBSCRIPTION_URL,
            "params": {
                "serviceKey": KO_DATA_SECRET,
                "page": str(page),
                "perPage": str(per_page),
                "returnType": "JSON",
                "cond[RCRIT_PBLANC_DE::GTE]": gte,
                "cond[RCRIT_PBLANC_DE::LTE]": lte,
            },
            "timeout_sec": CALL_TIMEOUT,
            "save_as": f"supply/subscription-{start_ym}-{end_ym}-p{page}.json",
        },
    }


def subscription_plan(start_ym: str, end_ym: str, per_page: int = PER_PAGE) -> dict[str, Any]:
    """1쪽만 받는 계획. 2쪽 이후는 subscription 가공이 matchCount 를 보고 ``next_calls`` 로 알린다."""
    per_page = max(1, per_page)
    return {"status": "ok", "start_month": start_ym, "end_month": end_ym, "per_page": per_page,
            "calls": [subscription_call(start_ym, end_ym, 1, per_page)]}


def _suffix(i: int) -> str:
    if i >= 26:
        raise ValueError("호출이 1,040개를 넘는다 — 기간을 나눠 계획하세요")
    return chr(ord("a") + i)


def write_plans(path: str, calls: list[dict[str, Any]]) -> list[str]:
    """batch ``plan_file`` 형식으로 쓴다. 40개가 넘으면 ``<이름>a``·``<이름>b``… 로 나눈다.

    itda-hyve batch 는 호출이 40개를 넘으면 하나도 실행하지 않는다. ``save_dir`` 는 넣지 않는다 —
    batch 호출 인자로 준다(``plan_file`` 은 그 ``save_dir`` 기준 상대 경로로 풀린다).
    """
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    chunks = [calls[i:i + BATCH_MAX] for i in range(0, len(calls), BATCH_MAX)] or [[]]
    if len(chunks) == 1:
        targets = [out]
    else:
        targets = [out.with_name(f"{out.stem}{_suffix(i)}{out.suffix}") for i in range(len(chunks))]
    for target, chunk in zip(targets, chunks):
        target.write_text(
            json.dumps({"calls": chunk, "timeout_sec": CALL_TIMEOUT}, ensure_ascii=False,
                       separators=(",", ":")),
            encoding="utf-8",
        )
    return [str(t) for t in targets]


def _table_meta(info: dict[str, Any]) -> dict[str, Any]:
    return {"org_id": info["orgId"], "tbl_id": info["tblId"], "name": info["table"],
            "cumulative": bool(info["cumulative"]), "region_axis": info["region_label"]}


# ---------------------------------------------------------------------------
# 응답 파일 — 공통
# ---------------------------------------------------------------------------

def _read(path: Path, api_error) -> bytes:
    """hyve 층 판독(본문 그대로·응답 JSON 전체·실패 자리). HTTP 오류면 본문의 API 오류를 먼저 본다."""
    try:
        return read_input(path).data
    except HyveHTTPError as exc:
        api_error(exc.body, path)
        raise InputFileError(str(exc), kind=exc.kind) from exc
    except HyveInputError as exc:
        raise InputFileError(str(exc), kind=exc.kind) from exc


def _text(body: bytes, path: Path) -> str:
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputFileError(f"UTF-8 텍스트가 아닙니다({path.name}): {exc}") from exc


# ---------------------------------------------------------------------------
# KOSIS
# ---------------------------------------------------------------------------

_KOSIS_ERR_RE = re.compile(r"""["']?\berr["']?\s*:\s*["']?(\d+)""")
_KOSIS_MSG_RE = re.compile(r"""["']?errMsg["']?\s*:\s*["']([^"']*)""")


def _raise_kosis_error(body: bytes, path: Path) -> None:
    """본문이 KOSIS 오류(따옴표 있는 JSON·없는 JS 표기·XML)면 SupplyAPIError. 아니면 돌아온다."""
    text = body.decode("utf-8", "replace")
    code = None
    msg = ""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "err" in data:
            code, msg = str(data.get("err", "")), str(data.get("errMsg", ""))
    except json.JSONDecodeError:
        m = _KOSIS_ERR_RE.search(text) or re.search(r"<err>\s*(\d+)\s*</err>", text)
        if m and "<html" not in text.lower():
            code = m.group(1)
            mm = _KOSIS_MSG_RE.search(text) or re.search(r"<errMsg>(.*?)</errMsg>", text, re.S)
            msg = mm.group(1).strip() if mm else ""
    if code is not None:
        raise SupplyAPIError(
            f"KOSIS API 오류 ({code}, {msg}): {_KOSIS_HINTS.get(code, '요청 파라미터를 확인')} ({path.name})",
            error_code=code,
        )


def _parse_value(raw: Any) -> float | int | None:
    s = str(raw if raw is not None else "").replace(",", "").strip()
    if s in ("", "-", "…", "x", "X"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v.is_integer() else v


def parse_kosis(path: str | Path, region: str | None = None) -> dict[str, Any]:
    """저장된 KOSIS 응답 한 개를 읽어 지표 행으로 정리한다.

    이름 규칙 ``kosis-<지표>-<시작 YYYYMM>-<끝 YYYYMM>.json`` 에서 지표와 기간을 읽는다.
    KOSIS 통계자료 응답에는 총건수가 없다 — 전량 대조 기준선이 없다는 사실을 ``warnings`` 로 남긴다.
    """
    p = Path(path).expanduser()
    m = _KOSIS_NAME_RE.search(p.name)
    if not m or m.group(1) not in KOSIS_INDICATORS:
        raise InputFileError(
            f"파일 이름이 규칙(kosis-<지표>-<시작 YYYYMM>-<끝 YYYYMM>.json)과 다릅니다: {p.name} "
            "— kosis-plan 이 준 save_as 를 그대로 쓰세요"
        )
    indicator, start_ym, end_ym = m.group(1), m.group(2), m.group(3)
    info = KOSIS_INDICATORS[indicator]

    body = _read(p, _raise_kosis_error)
    _raise_kosis_error(body, p)
    text = _text(body, p)
    if "<html" in text[:500].lower():
        raise InputFileError(
            f"KOSIS 응답이 아니라 HTML 페이지입니다({p.name}) — 주소가 틀렸거나(404) 점검 중이다. "
            "kosis-plan 의 url 을 그대로 쓰세요"
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputFileError(f"KOSIS 응답이 JSON 이 아닙니다({p.name}): {exc}") from exc
    if not isinstance(data, list):
        raise InputFileError(f"KOSIS 통계자료 응답 형태(행 배열)가 아닙니다({p.name})")

    axes = info["region_axes"]
    results: list[dict[str, Any]] = []
    non_numeric = 0
    no_region = 0
    other_region_objs: set[str] = set()   # 지역 축으로 선언하지 않은 분류인데 이름이 지역을 말한다
    itm_names: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            raise InputFileError(f"KOSIS 행이 객체가 아닙니다({p.name})")
        tbl = str(row.get("TBL_ID") or "")
        if tbl and tbl != info["tblId"]:
            raise InputFileError(
                f"{p.name}: 행의 통계표({tbl})가 지표 {indicator} 의 표({info['tblId']})와 다릅니다 "
                "— 다른 요청의 응답이 이 이름으로 저장됐다"
            )
        reg_names, reg_codes, cat_names, cat_codes = [], [], [], []
        for n in range(1, 9):
            code = row.get(f"C{n}")
            if code in (None, ""):
                continue
            name = str(row.get(f"C{n}_NM") or "").strip()
            obj = str(row.get(f"C{n}_OBJ_NM") or "").strip()
            if f"C{n}" not in axes and any(w in obj for w in _REGION_OBJ_WORDS):
                other_region_objs.add(f"C{n}={obj}")
            if f"C{n}" in axes:
                reg_names.append(name)
                reg_codes.append(str(code))
            else:
                cat_names.append(name)
                cat_codes.append(str(code))
        item = str(row.get("ITM_NM") or "").strip()
        if item:
            itm_names.add(item)
        if "ITM" in axes:
            if item:
                reg_names.append(item)
                reg_codes.append(str(row.get("ITM_ID") or ""))
            item = ""
        if not any(reg_names):
            no_region += 1
        value = _parse_value(row.get("DT"))
        if value is None:
            non_numeric += 1
        results.append({
            "indicator": indicator,
            "period": str(row.get("PRD_DE", "")).strip(),
            "region": " ".join(x for x in reg_names if x),
            "region_code": "/".join(reg_codes),
            "category": " ".join(x for x in cat_names if x),
            "category_code": "/".join(cat_codes),
            "item": item,
            "value": value,
            "unit": str(row.get("UNIT_NM") or "").strip(),
        })

    warnings = [
        "KOSIS 통계자료 응답에는 총건수가 없어 전량 대조 기준선이 없다 — 오류 31(조회결과 초과)이 "
        "없으면 한 번에 다 온 것으로 본다"
    ]
    if no_region:
        warnings.append(
            f"지역 축({info['region_label']})이 비어 있는 행 {no_region}개 — 이 표의 지역 축 선언이 응답과 다를 수 있다"
            "(화면 근거 추정, Cowork 실측 대기). region 이 빈 행은 --region 으로 거를 수 없다"
        )
    mismatch = []
    if other_region_objs:
        mismatch.append(f"지역 축으로 선언하지 않은 분류가 지역 이름을 달고 왔다({', '.join(sorted(other_region_objs))})")
    if "ITM" in axes and itm_names and not itm_names & _SIDO_NAMES:
        mismatch.append(f"지역 축인 항목(ITM_NM)에 시도 이름이 없다(예: {', '.join(sorted(itm_names)[:3])})")
    if mismatch:
        warnings.append(
            f"지역 축 선언({info['region_label']})이 응답과 다르다 — {'; '.join(mismatch)}. region·--region 결과를 믿지 말고 "
            "이 경고를 사용자에게 전한다(선언은 화면 근거 추정, Cowork 실측 대기)"
        )
    if region:
        before = len(results)
        results = [r for r in results if region in r["region"]]
        if before and not results:
            msg = f"지역 '{region}' 이 이 표의 지역 축({info['region_label']})에 없어 0행이다"
            if tuple(axes) == ("ITM",):
                msg += " — 이 표는 시도 단위(서울·경기 …)만 있고, 이름은 KOSIS 표기(예: 전남광주)를 따른다"
            elif "C2" in axes and "C1" in axes:
                msg += " — 시도·시군구 이름(예: 서울, 강남구)의 표기를 확인한다"
            else:
                msg += " — 이 표는 시도 단위(서울·경기 …)다"
            warnings.append(msg)
    if non_numeric:
        warnings.append(f"값이 숫자가 아닌 행 {non_numeric}개는 value=null 이다(-·x 등, 0 으로 바꾸지 않았다)")
    if info["cumulative"]:
        warnings.append(f"{info['table']} — 값은 그 해 1월부터 그 달까지의 누계다(월 단독 값이 아니다)")
    if not data:
        warnings.append("행이 0개다 — 기간이 수록기간 밖인지 확인")
    return {
        "indicator": indicator,
        "table": _table_meta(info),
        "start_month": start_ym,
        "end_month": end_ym,
        "results": results,
        "warnings": warnings,
        "source": str(p),
    }


# ---------------------------------------------------------------------------
# 청약홈 분양정보 (odcloud)
# ---------------------------------------------------------------------------

def _raise_odcloud_error(body: bytes, path: Path) -> None:
    """본문이 odcloud 오류 ``{"code": 음수, "msg": …}`` 면 SupplyAPIError. data.go.kr 게이트웨이 XML 도 본다."""
    text = body.decode("utf-8", "replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"<returnReasonCode>\s*(\d+)\s*</returnReasonCode>", text)
        if m:
            auth = re.search(r"<returnAuthMsg>(.*?)</returnAuthMsg>", text, re.S)
            raise SupplyAPIError(
                f"공공데이터포털 게이트웨이 거부 (returnReasonCode={m.group(1)}, "
                f"{auth.group(1).strip() if auth else ''}) ({path.name})",
                error_code=f"gateway-{m.group(1)}",
            )
        return
    if isinstance(data, dict) and "code" in data and "data" not in data:
        code = str(data.get("code"))
        raise SupplyAPIError(
            f"청약홈 API 오류 (code={code}, {data.get('msg', '')}): "
            f"{_ODCLOUD_HINTS.get(code, '요청 파라미터와 활용신청 상태를 확인')} ({path.name})",
            error_code=code,
        )


def _sub_name(path: Path) -> tuple[str, str, int]:
    m = _SUB_NAME_RE.search(path.name)
    if not m:
        raise InputFileError(
            f"파일 이름이 규칙(subscription-<시작 YYYYMM>-<끝 YYYYMM>-p<쪽>.json)과 다릅니다: {path.name} "
            "— subscription-plan 이 준 save_as 를 그대로 쓰세요"
        )
    return m.group(1), m.group(2), int(m.group(3))


def _int(data: dict, key: str, path: Path) -> int:
    try:
        return int(data[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise InputFileError(f"청약홈 응답에 정수 {key} 가 없습니다({path.name})") from exc


def parse_subscription_page(path: str | Path) -> dict[str, Any]:
    """저장된 청약홈 분양정보 한 쪽을 읽는다.

    Returns:
        ``{"start", "end", "page", "per_page", "match_count", "current_count", "items"}``
    """
    p = Path(path).expanduser()
    start_ym, end_ym, name_page = _sub_name(p)
    body = _read(p, _raise_odcloud_error)
    _raise_odcloud_error(body, p)
    try:
        data = json.loads(_text(body, p))
    except json.JSONDecodeError as exc:
        raise InputFileError(f"청약홈 응답이 JSON 이 아닙니다({p.name}): {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise InputFileError(f"청약홈 분양정보 응답 형태({{page, perPage, matchCount, data}})가 아닙니다({p.name})")
    page = _int(data, "page", p)
    if page != name_page:
        raise InputFileError(
            f"{p.name}: 본문의 page({page})가 이름의 쪽(p{name_page})과 다릅니다 — 저장 이름을 바꾸지 마세요"
        )
    items = data["data"]
    current = _int(data, "currentCount", p)
    if current != len(items):
        raise InputFileError(f"{p.name}: currentCount({current})와 data 행 수({len(items)})가 다릅니다")
    return {
        "start": start_ym, "end": end_ym, "page": page,
        "per_page": _int(data, "perPage", p),
        # cond 로 기간을 걸었으므로 분모는 matchCount 다(totalCount 는 데이터셋 전체 행 수).
        "match_count": _int(data, "matchCount", p),
        "current_count": current,
        "items": items,
    }


def _sub_key(item: dict) -> tuple:
    parts = (str(item.get("HOUSE_MANAGE_NO", "")), str(item.get("PBLANC_NO", "")))
    if any(parts):
        return parts
    return tuple(sorted((str(k), str(v)) for k, v in item.items()))


def normalize_subscription(item: dict) -> dict[str, Any]:
    def s(key: str) -> str:
        v = item.get(key)
        return "" if v is None else str(v).strip()

    total = item.get("TOT_SUPLY_HSHLDCO")
    try:
        total_supply = int(total) if total not in (None, "") else None
    except (TypeError, ValueError):
        total_supply = None
    return {
        "house_manage_no": s("HOUSE_MANAGE_NO"),
        "pblanc_no": s("PBLANC_NO"),
        "house_nm": s("HOUSE_NM"),
        "house_type": s("HOUSE_SECD_NM"),
        "area": s("SUBSCRPT_AREA_CODE_NM"),
        "address": s("HSSPLY_ADRES"),
        "total_supply": total_supply,
        "rcrit_pblanc_de": s("RCRIT_PBLANC_DE"),
        "rcept_bgnde": s("RCEPT_BGNDE"),
        "rcept_endde": s("RCEPT_ENDDE"),
        "przwner_presnatn_de": s("PRZWNER_PRESNATN_DE"),
        "pblanc_url": s("PBLANC_URL"),
    }


def collect_subscription(paths: list[str], max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """저장된 쪽 파일들을 전량 대조해 합친다.

    - 한 번에 한 질의(같은 기간)만 받는다.
    - 분모는 쪽들의 ``matchCount`` 중 **최댓값**이다. 청약 공고는 받는 사이 새 공고가 붙을 수 있어
      쪽마다 matchCount 가 다를 수 있다 — 오류가 아니라 경고로 두고, 작은 값을 쓰면 모자란 쪽을 놓치므로 max 를 쓴다.
    - 쪽은 1부터 빈틈없이 이어져야 하고, 같은 쪽이 두 번 오거나 perPage 가 쪽마다 다르거나 필요한 쪽을 넘는 쪽이
      오면 ``input`` 오류. 합친 행이 분모를 넘어도 ``input`` 오류.
    - 오프셋 쪽 매김의 한계: 받는 사이 앞쪽에서 1건 빠지고 뒤에 1건 붙으면(matchCount 불변) 쪽 경계의 1건이 조용히 빠진다.
      건수로는 가를 수 없다 — 문서에 밝혀 둔다.
    - 분모가 0 이면(202002 이후 기간) 조회 조건 형식을 의심하라는 경고를 싣는다.
    - 마지막 쪽이 아닌 쪽은 perPage 만큼 차 있어야 한다(아니면 받는 사이 목록이 밀렸다).
    - 필요한 쪽이 ``max_pages`` 를 넘으면 상한까지만 요구하고 ``truncated`` 로 표시한다.
    """
    max_pages = max(1, max_pages)
    pages = [parse_subscription_page(x) for x in paths]
    if not pages:
        raise InputFileError("입력 파일이 없습니다")
    ranges = {(pp["start"], pp["end"]) for pp in pages}
    if len(ranges) > 1:
        raise InputFileError(f"한 번에 한 기간만 가공합니다 — 여러 기간이 섞였습니다: {sorted(ranges)}")
    start_ym, end_ym = ranges.pop()

    warnings: list[str] = []
    got = [pp["page"] for pp in pages]
    dup = sorted({g for g in got if got.count(g) > 1})
    if dup:
        raise InputFileError(f"같은 쪽이 두 번 들어왔습니다({dup})")
    sizes = {pp["per_page"] for pp in pages}
    if len(sizes) > 1:
        raise InputFileError(f"쪽마다 perPage 가 다릅니다({sorted(sizes)}) — 한 기간은 같은 perPage 로 받으세요")
    per_page = sizes.pop()
    matches = {pp["match_count"] for pp in pages}
    total = max(matches)
    if len(matches) > 1:
        warnings.append(
            f"쪽마다 matchCount 가 다릅니다({sorted(matches)}) — 받는 사이 공고가 바뀌었습니다. 큰 값({total})을 분모로 씁니다"
        )

    need = math.ceil(total / per_page) if total else 1
    upto = min(need, max_pages)
    will_truncate = need > max_pages
    extra = sorted(n for n in got if n > upto)
    if extra:
        raise InputFileError(
            f"필요한 쪽(1~{upto})을 넘는 쪽이 들어왔습니다({extra}) — matchCount={total}·perPage {per_page} 기준. "
            "다른 회차의 파일이 섞였는지 확인하고 이 회차 파일만 넘기세요"
        )
    missing = [n for n in range(1, upto + 1) if n not in got]
    if missing:
        next_calls = [subscription_call(start_ym, end_ym, n, per_page) for n in missing]
        raise IncompleteError(
            f"{start_ym}~{end_ym} matchCount={total}, 받은 쪽 {sorted(got)} → 더 받을 쪽 {missing}"
            + (f" (필요 {need}쪽 중 상한 {max_pages}쪽까지만 — 받기 전에 사용자에게 확인)" if will_truncate else ""),
            next_calls, need_pages=need, will_truncate=will_truncate, total_count=total,
        )

    for pp in pages:
        if pp["page"] < need and pp["current_count"] != per_page:
            raise InputFileError(
                f"{pp['page']}쪽이 {pp['current_count']}행입니다(perPage {per_page}) — 받는 사이 목록이 밀렸습니다. "
                "이 기간을 새 하위 폴더에 1쪽부터 다시 받으세요"
            )

    raw: list[dict] = []
    for pp in sorted(pages, key=lambda x: x["page"]):
        raw.extend(pp["items"])
    seen: set[tuple] = set()
    merged: list[dict] = []
    for item in raw:
        k = _sub_key(item)
        if k in seen:
            continue
        seen.add(k)
        merged.append(item)
    dups = len(raw) - len(merged)
    if dups:
        warnings.append(f"쪽 경계에서 겹친 공고 {dups}건을 하나로 합쳤습니다")

    if len(merged) > total:
        raise InputFileError(
            f"{start_ym}~{end_ym} 합친 공고 {len(merged)}건이 matchCount {total} 를 넘습니다 — 다른 질의·회차의 행이 섞였습니다. "
            "이 기간을 새 하위 폴더에 1쪽부터 다시 받으세요"
        )
    if total == 0 and end_ym >= SUBSCRIPTION_DATA_START_YM:
        warnings.append(
            f"{start_ym}~{end_ym} 모집공고가 0건입니다 — 청약 공고는 보통 한 달에도 수십 건이라 이상 신호다. "
            "조회 조건(RCRIT_PBLANC_DE 값 형식 YYYY-MM-DD, 명세에 없어 추정)이 맞는지 확인이 필요하다"
        )
    if will_truncate:
        warnings.append(
            f"전체 {total}건 중 {len(merged)}건만 받았습니다(상한 {max_pages}쪽). 기간을 좁히거나 --max-pages 를 늘리세요"
        )
    elif len(merged) < total:
        raise IncompleteError(
            f"{start_ym}~{end_ym} matchCount={total} 인데 {len(merged)}건 — 받는 사이 목록이 밀렸습니다. "
            "이 기간을 새 하위 폴더에 1쪽부터 다시 받으세요",
            [], need_pages=need, will_truncate=False, total_count=total,
        )

    return {
        "start_month": start_ym,
        "end_month": end_ym,
        "total_count": total,
        "need_pages": need,
        "truncated": will_truncate,
        "pages": sorted(got),
        "items": [normalize_subscription(x) for x in merged],
        "sources": [{"path": str(Path(x).expanduser()), "page": pp["page"], "match_count": pp["match_count"],
                     "item_count": len(pp["items"])} for x, pp in zip(paths, pages)],
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# JSON envelope
# ---------------------------------------------------------------------------

def subscription_note(start_month: str | None) -> str | None:
    """2020-02 이전 구간을 요청했으면 알린다(R18 — 보간하지 않는다)."""
    if start_month and start_month < SUBSCRIPTION_DATA_START_YM:
        return (
            f"청약 데이터는 {SUBSCRIPTION_DATA_START_YM}부터 제공됩니다. "
            f"요청 시작월({start_month})은 데이터 시작 이전으로, 해당 구간은 보간 없이 공백으로 처리됩니다."
        )
    return None
