"""국세법령정보시스템(taxlaw.nts.go.kr) action.do API 클라이언트.

브라우저 없이 순수 HTTP 로 통합검색·전문 조회를 수행한다.

계약 근거: 2026-09-01 라이브 실측 (references/taxlaw-api.md 박제).
사이트가 실제로 보내는 XHR 요청 원형을 그대로 재현한다 — 파라미터를
임의로 더하거나 빼지 않는다 (request-profile-first).
"""
from __future__ import annotations

import html as _html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

_BASE = "https://taxlaw.nts.go.kr"
_ACTION_ENDPOINT = _BASE + "/action.do"
_REQUEST_TIMEOUT = 25

# 사이트 XHR 이 보내는 헤더 원형 (실측 캡처와 동일 — 신원 토큰 없음)
_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Referer": _BASE + "/is/USEISA001M.do",
}

# 스킬 도메인 별칭 → 사이트 컬렉션명 (실측: USEISA001M.do 인라인 JS)
DOMAINS = {
    "law": "statute",  # 법령
    "interpretation": "question",  # 세법해석례
    "precedent": "precedent",  # 판례·결정례
    "counsel": "hometaxCnslThan",  # 상담사례
    "form": "appendForm",  # 별표·서식
    "library": "formerLibrary",  # 전자도서관
}
_COLLECTION_TO_DOMAIN = {v: k for k, v in DOMAINS.items()}

DOMAIN_LABELS = {
    "law": "법령",
    "interpretation": "세법해석례",
    "precedent": "판례·결정례",
    "counsel": "상담사례",
    "form": "별표·서식",
    "library": "전자도서관",
}

# 정렬 별칭 → sortField 값 (실측: data-sortField 속성)
SORTS = {
    "accuracy": "SCORE/DESC",
    "registered": "FRS_RGT_DTM/DESC",
    "produced": "DCM_RGT_DTM/DESC",
}

# 통합검색 actionId (실측: Biz.actionId.getListSch)
_ACTION_SEARCH = "ASEISA001MR01"
# 세법해석례·판례 상세 (실측: USEQTA002P/USEPDA002P 공통)
_ACTION_DCM_DETAIL = "ASIQTB002PR01"
# 상담사례 상세 (실측: USEISA004P Biz.actionId.getQnA)
_ACTION_COUNSEL_DETAIL = "ASEISA004MR01"
# 법령 조문 전문 (실측: USESTA002M Biz.doSearchCntn)
_ACTION_LAW_DETAIL = "ASISTA002MR03"
# 법령 목록 — 법령명·구분코드 역해석용 (실측: USESTA002M Biz.doSearch)
_ACTION_LAW_LIST = "ASISTA002MR01"


class TaxlawAPIError(Exception):
    """국세법령정보시스템 API 호출·계약 오류."""


# ── 저수준 호출 ────────────────────────────────────────────────────────────


def _do_action(action_id: str, param_data: dict, *, opener=None) -> dict:
    """action.do 호출 후 data[action_id] 를 반환.

    응답 계약을 명시 검증한다 — 200 이어도 JSON/SUCCESS/키가 아니면
    typed 에러로 표면화한다 (no-silent-fallback).
    """
    body = urllib.parse.urlencode(
        {
            "actionId": action_id,
            "paramData": json.dumps(param_data, ensure_ascii=False),
        }
    ).encode("utf-8")
    req = urllib.request.Request(_ACTION_ENDPOINT, data=body, headers=_HEADERS)
    open_fn = opener or urllib.request.urlopen
    resp = None
    try:
        resp = open_fn(req, timeout=_REQUEST_TIMEOUT)
        content_type = (resp.headers.get("content-type") or "").lower()
        raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise TaxlawAPIError(
            f"HTTP {exc.code} 오류 (actionId={action_id})"
        ) from exc
    except urllib.error.URLError as exc:
        raise TaxlawAPIError(
            f"네트워크 오류 (actionId={action_id}): {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        # read() 단계의 타임아웃은 URLError 로 감싸이지 않고 그대로 샌다
        raise TaxlawAPIError(
            f"응답 시간 초과 (actionId={action_id})"
        ) from exc
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
    if "json" not in content_type:
        # SPA catch-all 등이 200 + HTML 을 돌려주는 위조 성공 차단
        raise TaxlawAPIError(
            f"기대와 다른 응답 형식(Content-Type={content_type!r}, "
            f"actionId={action_id}) — 사이트 계약이 변경됐을 수 있습니다."
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TaxlawAPIError(
            f"JSON 파싱 실패 (actionId={action_id}): {raw[:200]!r}"
        ) from exc
    if parsed.get("status") != "SUCCESS":
        raise TaxlawAPIError(
            f"API status={parsed.get('status')!r} "
            f"message={parsed.get('message')!r} (actionId={action_id})"
        )
    payload = parsed.get("data")
    if not isinstance(payload, dict):
        raise TaxlawAPIError(
            f"응답 data 가 객체가 아닙니다 (actionId={action_id}) — 계약 변경 의심."
        )
    data = payload.get(action_id)
    if data is None:
        raise TaxlawAPIError(
            f"응답에 data[{action_id!r}] 가 없습니다 — 계약 변경 의심."
        )
    return data


# ── 텍스트 정리 ────────────────────────────────────────────────────────────

_HS_RE = re.compile(r"<!HS>|<!HE>")
# 태그는 ASCII 문자로 시작하는 것만 제거한다 (리뷰 R1 P1-2 실측):
# 법령 조문·서식 본문에는 `<개정 2016.12.20>`·`<2018.12.31>` 같은
# 개정·시행일 표기가 **리터럴 꺾쇠**로 실려 오며, 이를 지우면 적용 연도를
# 가를 유일한 담체가 무음 소실된다(ntstTextEnlrDscCntn 은 극히 일부 행만 채워짐).
_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>|<!--.*?-->|<![A-Za-z\[][^>]*>", re.S)
# ↑ 세 번째 갈래: <!DOCTYPE …>·Word 조건부 주석(<![if …]>) 선언 — 본문이 아니다.
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_BREAK_RE = re.compile(r"(?i)<br\s*/?>|</p>|</tr>|</div>|</li>|</h[1-6]>")


def strip_highlight(text: str, *, bold: bool = False) -> str:
    """검색 하이라이트 마커(<!HS>…<!HE>)를 제거하거나 마크다운 굵게로 변환."""
    if not text:
        return ""
    if bold:
        return text.replace("<!HS>", "**").replace("<!HE>", "**")
    return _HS_RE.sub("", text)


def clean_text(text: str) -> str:
    """검색 결과 필드용: 마커·실제 태그 제거 + 엔티티 해제 + 공백 정돈.

    개정·시행일 표기는 두 형태로 온다 — 검색 필드는 엔티티
    (`&lt;개정 2010.1.1&gt;`), 법령 상세·서식 본문은 리터럴(`<개정 2016.12.20>`).
    전자는 태그 제거를 unescape 이전에 해서, 후자는 _TAG_RE 가 ASCII 문자
    시작 태그만 지우게 좁혀서 각각 보존한다 (리뷰 R1 P1-2).
    """
    if not text:
        return ""
    out = strip_highlight(text)
    out = _TAG_RE.sub(" ", out)  # 실측: 요지에 <BR/> 등이 섞여 온다
    out = _html.unescape(out)
    # 통칙 요약처럼 마크업이 `&lt;p&gt;` 로 이중 인코딩돼 오는 행이 있다(R2 최종 P2).
    # unescape 후 한 번 더 — _TAG_RE 는 ASCII 시작 태그만 잡으므로 `<개정 …>` 은 남는다.
    out = _TAG_RE.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip()


def html_to_text(fragment: str) -> str:
    """상세 응답의 본문 HTML 을 읽기용 텍스트로 변환."""
    if not fragment:
        return ""
    out = _SCRIPT_RE.sub("", fragment)
    out = _BREAK_RE.sub("\n", out)
    out = _TAG_RE.sub("", out)
    out = _html.unescape(out)
    out = out.replace("\r\n", "\n").replace("\xa0", " ")
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n\s*\n+", "\n", out)
    return out.strip()


def _fmt_date(raw: str) -> str:
    """YYYYMMDD… → YYYY.MM.DD (형식이 다르면 원문 유지)."""
    if raw and len(raw) >= 8 and raw[:8].isdigit():
        return f"{raw[:4]}.{raw[4:6]}.{raw[6:8]}"
    return raw or ""


# ── 검색 결과 정규화 ───────────────────────────────────────────────────────


def _statute_title(name: str, article: str, article_title: str) -> str:
    """사이트 표기와 동일하게 조립: `법령명【조표시 조제목】`.

    브라우저 10검색어 대조(2026-09-01)에서 확정한 규칙 — 항·호·목 행은
    TEXT_KRN_NM 이 이미 조 경로를 담고 있어(`제72조의2 제1항 제2호`) 그것만
    쓰고, 조·장·절 행은 TEXT_UQNM + TEXT_KRN_NM 을 잇는다. 통칙·집행기준처럼
    UQNM 이 비는 행은 KRN_NM 만 감싼다.
    """
    if article and article_title.startswith(article):
        inner = article_title  # 조제목이 자기 조표시로 시작 (예: 제3조 + "제3조의 특례") — 중복 방지
    elif article_title.startswith("제") and article:
        inner = article_title  # 항·호·목 — KRN_NM 이 전체 경로
    else:
        inner = " ".join(x for x in (article, article_title) if x)
    return f"{name}【{inner}】" if inner else name


def _norm_statute(it: dict) -> dict:
    article = clean_text(it.get("TEXT_UQNM") or "")
    article_title = clean_text(it.get("TEXT_KRN_NM") or "")
    name = clean_text(it.get("NM") or "")
    title = _statute_title(name, article, article_title)
    kind = clean_text(it.get("LBL1_NM") or "")  # 법령/훈령/통칙/집행 — 사이트 배지
    enfr = _fmt_date(it.get("ENFR_DT") or "")
    is_statute = (it.get("SUB_ID") or "").startswith("LBM001") and bool(it.get("BRKD_ID"))
    return {
        "domain": "law",
        "title": title,
        "doc_no": "",
        "date": _fmt_date(it.get("PMG_DT") or ""),
        "extra": " / ".join(x for x in (kind, f"시행 {enfr}" if enfr else "") if x),
        "summary": clean_text(it.get("TEXT_KRN_CNTN") or ""),
        "tax_type": clean_text(it.get("STTT_SHRG_NM") or ""),
        "verdict": "",
        # 전문 조회(detail_law = ASISTA002MR03)는 국세법령(LBM001) 행만 성립한다.
        # 통칙·집행기준·훈령·조약은 별도 팝업 화면이라 id 를 비우고 원문 URL 만 준다.
        "id": ":".join(
            [it.get("BSC_ID") or "", it.get("BRKD_ID") or "", it.get("PMG_NO") or ""]
        ) if is_statute else "",
        "detail_url": _statute_detail_url(it),
    }


def _statute_detail_url(it: dict) -> str:
    """사이트 `LinkBroker.totalSearch.stttDetail`(common_link.js) 라우팅 이식.

    SUB_ID 접두로 5갈래 — 실측 2026-09-01. 국세법령 상세(USESTA002M)는
    `ntstTlawClCd` 가 없으면 **빈 화면**을 렌더한다(브라우저 3조합 실측).
    """
    sub = it.get("SUB_ID") or ""
    bsc = it.get("BSC_ID") or ""
    if sub.startswith("LBM001"):  # 국세법령 테이블
        q = {
            "ntstTlawClCd": it.get("TLAW_CL_CD") or "",
            "ntstSysClCd": it.get("SYS_CL_CD") or "",
            "ntstBscId": bsc,
            "ntstTextUqno": it.get("RFRN_NTST_TEXT_UQNO") or it.get("TEXT_UQNO") or "",
            "ntstEnfrDt": it.get("ENFR_DT") or "",
        }
        return f"{_BASE}/st/USESTA002M.do?{urllib.parse.urlencode(q)}"
    if sub in ("BM001_04", "BM001_05"):  # 기본통칙 / 세법집행기준
        page = "USESTD002P" if sub == "BM001_04" else "USESTE001P"
        q = {
            "ntstBscId": bsc,
            "rgtYr": it.get("RGT_YR") or "",
            "ntstExrBaseSn": it.get("TEXT_SN") or "",
        }
        return f"{_BASE}/st/{page}.do?{urllib.parse.urlencode(q)}"
    if sub == "BL027":  # 조세조약
        q = {
            "txaAgrmBscId": bsc,
            "textUqnm": it.get("TEXT_UQNM") or "",
            "textSn": it.get("TEXT_SN") or "",
        }
        return f"{_BASE}/st/USESTC002P.do?{urllib.parse.urlencode(q)}"
    # 그 외 = 행정규칙(훈령·고시)
    q = {
        "ntarBscId": bsc,
        "ntarClCd": it.get("NTAR_CL_CD") or "",
        "ntstTextUqno": it.get("TEXT_UQNO") or "",
    }
    return f"{_BASE}/st/USESTA011P.do?{urllib.parse.urlencode(q)}"


def _norm_dcm(it: dict, domain: str) -> dict:
    """세법해석례(question)·판례(precedent) 공통 정규화."""
    path = "/qt/USEQTA002P.do" if domain == "interpretation" else "/pd/USEPDA002P.do"
    doc_id = it.get("DOC_ID") or ""
    return {
        "domain": domain,
        "title": clean_text(it.get("TTL") or ""),
        "doc_no": clean_text(it.get("NTST_DCM_DSCM_CNTN") or ""),
        "date": _fmt_date(it.get("DCM_RGT_DTM_S") or it.get("DCM_RGT_DTM") or ""),
        "extra": clean_text(it.get("NTST_DCM_CL_NM") or ""),
        "summary": clean_text(it.get("GIST_CNTN") or it.get("CNTN") or ""),
        "tax_type": clean_text(it.get("NTST_TLAW_CL_NM") or ""),
        "verdict": clean_text(it.get("NTST_DCM_DCS_CL_NM") or ""),
        "id": doc_id,
        "detail_url": f"{_BASE}{path}?ntstDcmId={doc_id}" if doc_id else "",
    }


def _norm_counsel(it: dict) -> dict:
    req_id = it.get("REQ_STD_ID") or ""
    return {
        "domain": "counsel",
        "title": clean_text(it.get("STD_TITLE") or ""),
        "doc_no": "",
        "date": _fmt_date(it.get("REGST_DT") or ""),
        "extra": f"조회수 {it.get('VIEW_CNT') or '0'}",
        "summary": clean_text(it.get("ANSWER_STD_CONTENT") or ""),
        "tax_type": clean_text(it.get("REQ_TP_NM") or ""),
        "verdict": "",
        "id": req_id,
        "detail_url": f"{_BASE}/is/USEISA004P.do?reqStdId={req_id}" if req_id else "",
    }


def _norm_form(it: dict) -> dict:
    detail_q = urllib.parse.urlencode(
        {
            "ntstBscId": it.get("BSC_ID") or "",
            "ntstBrkdId": it.get("BRKD_ID") or "",
            "ntstAtFrmlSn": it.get("FRML_SN") or "",
        }
    )
    return {
        "domain": "form",
        "title": clean_text(it.get("FRML_NM") or ""),
        "doc_no": "",
        "date": _fmt_date(it.get("PMG_DT") or ""),
        "extra": f"시행 {_fmt_date(it.get('ENFR_DT') or '')}",
        "summary": clean_text(it.get("FILE_CN") or "")[:300],
        "tax_type": clean_text(it.get("LBL2_TTL") or ""),
        "verdict": "",
        "id": ":".join(
            [
                it.get("BSC_ID") or "",
                it.get("BRKD_ID") or "",
                it.get("FRML_SN") or "",
            ]
        ),
        "detail_url": f"{_BASE}/st/USESTA007P.do?{detail_q}",
    }


def _norm_library(it: dict) -> dict:
    detail_q = urllib.parse.urlencode(
        {
            "ntstPlcnBkId": it.get("NTST_PLCN_BK_ID") or "",
            "ntstPlcnBkTtl": clean_text(it.get("NTST_PLCN_BK_TTL") or ""),
            "ntstFleId": it.get("NTST_FLE_ID") or "",
            "pageNum": it.get("PAGE_NUM") or "1",
        }
    )
    return {
        "domain": "library",
        "title": clean_text(it.get("NM") or it.get("NTST_PLCN_BK_TTL") or ""),
        "doc_no": "",
        "date": _fmt_date(it.get("PLCN_DT") or ""),
        "extra": clean_text(it.get("NTST_JRSD_DNO_NM") or ""),
        "summary": clean_text(it.get("FILE_CN") or "")[:300],
        "tax_type": clean_text(it.get("LBL2_TTL") or ""),
        "verdict": "",
        "id": it.get("DOC_ID") or "",
        "detail_url": f"{_BASE}/el/USEELA002P.do?{detail_q}",
    }


_NORMALIZERS = {
    "law": _norm_statute,
    "interpretation": lambda it: _norm_dcm(it, "interpretation"),
    "precedent": lambda it: _norm_dcm(it, "precedent"),
    "counsel": _norm_counsel,
    "form": _norm_form,
    "library": _norm_library,
}


# ── 공개 API ───────────────────────────────────────────────────────────────


def build_search_param(
    query: str,
    collections: list[str],
    *,
    start_count: int = 1,
    view_count: int = 10,
    sort_field: str = "SCORE/DESC",
    doc_no: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    use_synonym: bool = False,
) -> dict:
    """통합검색 paramData 조립 — 실측 요청 원형과 동일 키 집합만 사용."""
    return {
        "schVcb": query,
        "startCount": start_count,
        "collection": ",".join(collections),
        "wnKey": "",
        "searchType": "document" if doc_no else "",
        "sortField": sort_field,
        "ntstTlawClCdList": [],
        "icldVcbCtl": list(include or []),
        "exclVcbCtl": list(exclude or []),
        "rltnStttCtl": [],
        "schDtBase": "DCM_RGT_DTM",
        "viewCount": str(view_count),
        "prtsSprcChiefJdgmYn": "",
        "prtsAttrYrCtl": [],
        "prtsPrgrStatCtl": [],
        "mainIdCtl": [],
        "useSynonymYn": "Y" if use_synonym else "N",
    }


def parse_search_response(data: dict) -> dict:
    """ASEISA001MR01 응답 → {domain: {"total": n, "items": [...]}}."""
    vo = data.get("searchResultVO")
    if not isinstance(vo, dict):
        raise TaxlawAPIError("searchResultVO 가 없습니다 — 응답 계약 변경 의심.")
    err = vo.get("errorMsg")
    if err and err != "no error":
        raise TaxlawAPIError(f"검색엔진 오류: {err}")
    out: dict = {}
    for coll in vo.get("collectionList") or []:
        name_en = coll.get("nameEn") or ""
        domain = _COLLECTION_TO_DOMAIN.get(name_en)
        if domain is None:
            continue  # intEpn 등 스킬 비대상 컬렉션
        normalizer = _NORMALIZERS[domain]
        items = [normalizer(it) for it in coll.get("resultList") or []]
        out[domain] = {"total": coll.get("totalCount") or 0, "items": items}
    return out


def search(
    query: str,
    domains: list[str],
    *,
    limit: int = 10,
    page: int = 1,
    sort: str = "accuracy",
    doc_no: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    use_synonym: bool = False,
    opener=None,
) -> dict:
    """통합검색. domains 는 DOMAINS 의 별칭 목록."""
    bad = [d for d in domains if d not in DOMAINS]
    if bad:
        raise TaxlawAPIError(
            f"알 수 없는 도메인: {', '.join(bad)} "
            f"(가능: {', '.join(DOMAINS)})"
        )
    if sort not in SORTS:
        raise TaxlawAPIError(
            f"알 수 없는 정렬: {sort} (가능: {', '.join(SORTS)})"
        )
    if page < 1 or limit < 1:
        raise TaxlawAPIError("page·limit 은 1 이상이어야 합니다.")
    param = build_search_param(
        query,
        [DOMAINS[d] for d in domains],
        start_count=(page - 1) * limit + 1,
        view_count=limit,
        sort_field=SORTS[sort],
        doc_no=doc_no,
        include=include,
        exclude=exclude,
        use_synonym=use_synonym,
    )
    data = _do_action(_ACTION_SEARCH, param, opener=opener)
    blocks = parse_search_response(data)
    # 요청 집합 ↔ 응답 집합 대조 (리뷰 R1 P2-2): 요청한 도메인이 응답에
    # 없으면 "0건"과 구별되는 missing 블록으로 명시한다 — 무음 드롭 금지.
    ordered: dict = {}
    for d in domains:
        ordered[d] = blocks.get(d) or {"total": None, "items": [], "missing": True}
    return {
        "query": query,
        "page": page,
        "limit": limit,
        "domains": ordered,
    }


def _document_body(data: dict) -> str:
    """상세 응답의 dcmHwpEditorDVOList 에서 html 전문을 추출."""
    parts = []
    for entry in data.get("dcmHwpEditorDVOList") or []:
        if entry.get("dcmFleTy") == "html" and entry.get("dcmFleByte"):
            parts.append(html_to_text(entry["dcmFleByte"]))
    return "\n\n".join(p for p in parts if p)


def detail_document(ntst_dcm_id: str, domain: str = "interpretation", *, opener=None) -> dict:
    """세법해석례·판례 상세(전문) 조회."""
    data = _do_action(
        _ACTION_DCM_DETAIL,
        {"dcmDVO": {"ntstDcmId": ntst_dcm_id, "wnKey": ""}},
        opener=opener,
    )
    dvo = data.get("dcmDVO")
    if not isinstance(dvo, dict):
        raise TaxlawAPIError(
            f"문서를 찾을 수 없습니다 (ntstDcmId={ntst_dcm_id})."
        )
    related = [
        clean_text(r.get("ntstTextNm") or "")
        for r in data.get("dcmRltnStttList") or []
        if r.get("ntstTextNm")
    ]
    path = "/qt/USEQTA002P.do" if domain == "interpretation" else "/pd/USEPDA002P.do"
    return {
        "domain": domain,
        "id": ntst_dcm_id,
        "title": clean_text(dvo.get("ntstDcmTtl") or ""),
        "doc_no": clean_text(dvo.get("ntstDcmDscmCntn") or ""),
        "date": _fmt_date(dvo.get("ntstDcmRgtDt") or ""),
        "gist": clean_text(dvo.get("ntstDcmGistCntn") or ""),
        "reply": clean_text(dvo.get("ntstDcmCntn") or ""),
        "body": _document_body(data),
        "related_laws": related,
        "detail_url": f"{_BASE}{path}?ntstDcmId={ntst_dcm_id}",
    }


def detail_counsel(req_std_id: str, *, opener=None) -> dict:
    """상담사례 상세 조회."""
    data = _do_action(
        _ACTION_COUNSEL_DETAIL, {"reqStdId": req_std_id}, opener=opener
    )
    if not data.get("stdTitle"):
        raise TaxlawAPIError(f"상담사례를 찾을 수 없습니다 (reqStdId={req_std_id}).")
    return {
        "domain": "counsel",
        "id": req_std_id,
        "title": clean_text(data.get("stdTitle") or ""),
        "tax_type": clean_text(data.get("reqTpNm") or ""),
        "date": _fmt_date(data.get("regstDt") or ""),
        "answer": html_to_text(data.get("answerStdContent") or ""),
        "detail_url": f"{_BASE}/is/USEISA004P.do?reqStdId={req_std_id}",
    }


def detail_law(law_id: str, *, article: str | None = None, opener=None) -> dict:
    """법령 조문 전문 조회.

    law_id: 검색 결과 id 형식 "<ntstBscId>:<ntstBrkdId>:<ntstPmgNo>".
    article: "제18조" 처럼 조 표시를 주면 해당 조문만 추린다.
    """
    parts = law_id.split(":")
    if len(parts) != 3 or not all(parts[:2]):
        raise TaxlawAPIError(
            "law 상세 id 는 '<ntstBscId>:<ntstBrkdId>:<공포번호>' 형식입니다 "
            "(검색 결과의 id 를 그대로 사용하세요)."
        )
    bsc_id, brkd_id, pmg_no = parts
    data = _do_action(
        _ACTION_LAW_DETAIL,
        {"ntstBscId": bsc_id, "ntstBrkdId": brkd_id, "ntstPmgNo": pmg_no},
        opener=opener,
    )
    rows = data.get("txaStttHsryDVOList")
    if not rows:
        raise TaxlawAPIError(f"조문을 찾을 수 없습니다 (id={law_id}).")
    # 실측: MR03 행에는 ntstNm(법령명)·ntstEnfrDt·ntstTlawClCd 가 전부 null 이다.
    # 법령명과 구분코드는 법령 목록 액션(MR01)에서 같은 ntstBscId 행을 찾아 해석한다.
    sys_cd = next((r.get("ntstSysClCd") for r in rows if r.get("ntstSysClCd")), "")
    law_name, tlaw_cd = _resolve_law_identity(bsc_id, sys_cd, opener=opener)
    articles = []
    for row in rows:
        art_no = clean_text(row.get("ntstTextUqnm") or "")
        name = clean_text(row.get("ntstTextNm") or "")
        if article:
            # 실측 구조: 조 본문은 헤더 행이 아니라 후속 항·호·목 행에 있고,
            # 그 행들의 ntstTextNm 이 "제2조 제1호"처럼 조 표시로 시작한다.
            is_header = art_no == article
            is_child = name.startswith(article + " ")
            if not (is_header or is_child):
                continue
        articles.append(
            {
                "article": art_no,
                "title": name,
                "text": html_to_text(row.get("ntstTextCntn") or ""),
                "note": html_to_text(row.get("ntstTextEnlrDscCntn") or ""),
            }
        )
    if article and not articles:
        raise TaxlawAPIError(
            f"{law_name}에서 {article!r} 조문을 찾지 못했습니다."
        )
    # 브라우저 실측(2026-09-01): USESTA002M 은 ntstTlawClCd 가 없으면 빈 화면이고,
    # ntstBrkdId 가 조회 버전(시행일)을 고정한다. 구분코드를 못 얻으면 URL 을
    # 지어내지 않고 None 으로 둔다(검색 결과의 URL 을 쓰라고 안내).
    detail_url = None
    if tlaw_cd:
        detail_url = f"{_BASE}/st/USESTA002M.do?" + urllib.parse.urlencode(
            {
                "ntstTlawClCd": tlaw_cd,
                "ntstSysClCd": sys_cd,
                "ntstBscId": bsc_id,
                "ntstBrkdId": brkd_id,
            }
        )
    return {
        "domain": "law",
        "id": law_id,
        "law_name": law_name,
        "article_count": len(rows),
        "articles": articles,
        "detail_url": detail_url,
    }


def _resolve_law_identity(bsc_id: str, sys_cd: str, *, opener=None) -> tuple[str, str]:
    """MR01(법령 목록)에서 ntstBscId 가 같은 행을 찾아 (법령명, 국세법령구분코드)를 돌려준다.

    실패·미발견은 ("", "") — 호출자가 사실대로 비워 둔다(no-silent-fallback:
    조용히 다른 값을 쓰지 않고, 빈 값을 표면화한다).
    """
    param = {"ntstBscId": bsc_id}
    if sys_cd:
        param["ntstSysClCd"] = sys_cd
    try:
        data = _do_action(_ACTION_LAW_LIST, param, opener=opener)
    except TaxlawAPIError:
        return "", ""
    for row in data.get("txaStttDVOList") or []:
        if row.get("ntstBscId") == bsc_id:
            return clean_text(row.get("ntstNm") or ""), (row.get("ntstTlawClCd") or "")
    return "", ""
