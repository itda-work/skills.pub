"""국세법령정보시스템(taxlaw.nts.go.kr) action.do — 요청 조립과 응답 판독(네트워크 없음).

요청은 itda-hyve ``http_request`` 가 보낸다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``).
이 모듈은 사이트 XHR 과 같은 요청(POST ``/action.do``)을 **만들기만** 하고, itda-hyve 가 ``save_as`` 로
저장한 응답을 판독한다.

요청 원형(브라우저 실측 — references/taxlaw-api.md):
- 본문은 jQuery ``$.ajax`` 가 만드는 그대로 ``actionId=<ID>&paramData=<JSON.stringify(...)>`` —
  JSON 은 공백 없는 직렬화, 인코딩은 ``encodeURIComponent`` 에 공백 ``+``(jQuery.param).
- 헤더는 사이트 JS(``Req.doAction`` 의 jQuery)가 싣는 셋(``Content-Type``·``Accept``·``X-Requested-With``)과
  Referer. Referer 는 캡처한 값이 아니라 **그 XHR 을 보내는 화면 주소로 고른 값**이다(XHR 훅은 Referer 를 못 본다).
  브라우저가 스스로 붙이는 ``Origin``·``Sec-Fetch-*``·쿠키는 싣지 않는다 — 없이 성립함은 실측(2026-10-01 10회 200).
  파라미터를 임의로 더하거나 빼지 않는다(request-profile-first).
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
import urllib.parse

_BASE = "https://taxlaw.nts.go.kr"
ACTION_URL = _BASE + "/action.do"

# 사이트 XHR 헤더(2026-10-01 aside 실측 — Req.doAction 이 보내는 그대로). User-Agent 는 싣지 않는다.
_XHR_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}
# 통합검색 XHR 을 보내는 화면. 그 화면 자체는 robots Disallow 라 부르지 않는다 — Referer 헤더로만 실린다.
SEARCH_REFERER = _BASE + "/is/USEISA001M.do"

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

ACTION_SEARCH = "ASEISA001MR01"  # 통합검색 (Biz.actionId.getListSch)
ACTION_DCM_DETAIL = "ASIQTB002PR01"  # 세법해석례·판례 상세 (USEQTA002P/USEPDA002P 공통)
ACTION_COUNSEL_DETAIL = "ASEISA004MR01"  # 상담사례 상세 (USEISA004P)
ACTION_LAW_DETAIL = "ASISTA002MR03"  # 법령 조문 전문 (USESTA002M Biz.doSearchCntn)
ACTION_LAW_LIST = "ASISTA002MR01"  # 법령 목록 — 법령명 역해석 (USESTA002M Biz.doSearch)

_DCM_PAGE = {"interpretation": "/qt/USEQTA002P.do", "precedent": "/pd/USEPDA002P.do"}


class TaxlawAPIError(Exception):
    """응답이 계약과 다르다. ``kind`` 는 CLI 출력 JSON 의 ``error`` 값이다."""

    kind = "site"

    def __init__(self, message: str, kind: str | None = None):
        super().__init__(message)
        if kind:
            self.kind = kind


# ── 요청 조립 ──────────────────────────────────────────────────────────────


def _js_uri_component(text: str) -> str:
    """``encodeURIComponent`` 와 같은 결과(안 바꾸는 글자: 영숫자 ``-_.!~*'()``)."""
    return urllib.parse.quote(text, safe="-_.!~*'()")


def encode_body(action_id: str, param_data: dict) -> str:
    """jQuery ``$.ajax({data: {actionId, paramData: JSON.stringify(p)}})`` 가 보내는 본문과 글자까지 같다."""
    payload = json.dumps(param_data, ensure_ascii=False, separators=(",", ":"))
    pairs = (("actionId", action_id), ("paramData", payload))
    return "&".join(
        f"{_js_uri_component(k)}={_js_uri_component(v)}".replace("%20", "+") for k, v in pairs
    )


def action_call(action_id: str, param_data: dict, referer: str) -> dict:
    """itda-hyve ``http_request`` 인자(저장 인자 제외). 조회 전용 POST 라 ``retry_unsafe``."""
    return {
        "url": ACTION_URL,
        "method": "POST",
        "headers": {**_XHR_HEADERS, "Referer": referer},
        "body": encode_body(action_id, param_data),
        "retry_unsafe": True,
        "timeout_sec": 50,
    }


def call_key(call: dict) -> str:
    """요청 본문의 짧은 지문 — 저장 이름에 넣어 응답과 질의를 잇는다.

    이름 지문은 "plan 이 이 이름을 지었다" 만 증명한다. 실제로 보낸 본문이 그 본문이었는지는 응답이 되비친
    요청 값(검색 ``schVcb``·``startCount``…, 법령 ``ntstBscId``…)으로 판독 함수가 따로 대조한다.
    """
    return hashlib.sha256(call["body"].encode("utf-8")).hexdigest()[:12]


def dcm_page_url(domain: str, doc_id: str) -> str:
    return f"{_BASE}{_DCM_PAGE[domain]}?ntstDcmId={doc_id}"


def dcm_referer(domain: str, doc_id: str) -> str:
    """검색 결과를 누르면 여는 팝업 주소 — ``Page.openPopup`` 의 ``$.param({ntstDcmId, wnKey})``(wnKey 가 없으면 빈 값)."""
    return f"{dcm_page_url(domain, doc_id)}&wnKey="


def counsel_page_url(req_std_id: str) -> str:
    return f"{_BASE}/is/USEISA004P.do?reqStdId={req_std_id}"


def law_page_url(tlaw_cd: str, sys_cd: str, bsc_id: str, brkd_id: str) -> str:
    """법령 상세 화면 — ``ntstTlawClCd`` 없으면 빈 화면, ``ntstBrkdId`` 가 버전(시행일)을 고정(2026-09-01 실측)."""
    return f"{_BASE}/st/USESTA002M.do?" + urllib.parse.urlencode(
        {"ntstTlawClCd": tlaw_cd, "ntstSysClCd": sys_cd, "ntstBscId": bsc_id, "ntstBrkdId": brkd_id}
    )


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
    """통합검색 paramData — 실측 요청 원형과 같은 키·순서."""
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


# 검색엔진이 주는 가장 깊은 결과 번호(추정 경계). 2026-10-01 itda-hyve 실측 — "세법" 해석례(전체 42,410건) limit 10:
# startCount 1,001·2,001·3,001·4,001 은 10건씩, 5,001 은 0건(리뷰 라이브: 9,901 도 0건). 4,011~5,000 은 재지 않았다.
# 이 경계 안에서도 결과가 모자라면 판독이 incomplete(깊은 쪽 문구)로 멈춘다.
MAX_RESULT_INDEX = 5000


def check_search_args(domains: list[str], *, limit: int, page: int, sort: str) -> None:
    bad = [d for d in domains if d not in DOMAINS]
    if bad:
        raise TaxlawAPIError(
            f"알 수 없는 도메인: {', '.join(bad)} (가능: {', '.join(DOMAINS)})", "args"
        )
    if not domains:
        raise TaxlawAPIError("도메인이 비었습니다.", "args")
    if len(set(domains)) != len(domains):
        raise TaxlawAPIError("같은 도메인을 두 번 적었습니다.", "args")
    if sort not in SORTS:
        raise TaxlawAPIError(f"알 수 없는 정렬: {sort} (가능: {', '.join(SORTS)})", "args")
    if page < 1 or limit < 1:
        raise TaxlawAPIError("page·limit 은 1 이상이어야 합니다.", "args")
    if limit > 100:
        raise TaxlawAPIError("limit 은 100 이하로 — 대량 수집 용도가 아니다.", "args")
    last = page * limit
    if last > MAX_RESULT_INDEX:
        raise TaxlawAPIError(
            f"검색엔진은 {MAX_RESULT_INDEX:,}번째 결과까지만 준다 — 이 쪽은 {(page - 1) * limit + 1:,}~{last:,}번째다. "
            "검색어를 좁히거나 포함어·제외어·문서번호 검색으로 분모를 줄여라.",
            "args",
        )


def search_param(
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
) -> dict:
    check_search_args(domains, limit=limit, page=page, sort=sort)
    if not query.strip():
        raise TaxlawAPIError("검색어가 비었습니다.", "args")
    return build_search_param(
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


def search_call(query: str, domains: list[str], **kw) -> dict:
    return action_call(ACTION_SEARCH, search_param(query, domains, **kw), SEARCH_REFERER)


def dcm_detail_call(doc_id: str, domain: str) -> dict:
    """세법해석례·판례 상세 — 팝업 화면이 보내는 ``{"dcmDVO": Page.getParameter()}``."""
    return action_call(
        ACTION_DCM_DETAIL, {"dcmDVO": {"ntstDcmId": doc_id, "wnKey": ""}}, dcm_referer(domain, doc_id)
    )


def counsel_detail_call(req_std_id: str) -> dict:
    return action_call(ACTION_COUNSEL_DETAIL, {"reqStdId": req_std_id}, counsel_page_url(req_std_id))


LAW_ID_HELP = (
    "law 상세 id 는 '<ntstBscId>:<ntstBrkdId>:<공포번호>:<체계구분>:<세법구분>' 다섯 칸입니다 "
    "(검색 결과의 id 를 그대로 사용하세요 — 0.1.x 의 세 칸 id 는 검색을 다시 하면 새 id 가 나옵니다)."
)


def parse_law_id(law_id: str) -> tuple[str, str, str, str, str]:
    parts = law_id.split(":")
    if len(parts) != 5 or not all(parts):  # 공포번호도 사이트는 늘 싣는다(연혁 버튼 값)
        raise TaxlawAPIError(LAW_ID_HELP, "args")
    if not all(re.fullmatch(r"[0-9A-Za-z]*", p) for p in parts):
        raise TaxlawAPIError(LAW_ID_HELP, "args")
    return tuple(parts)  # type: ignore[return-value]


def law_detail_calls(law_id: str) -> tuple[dict, dict]:
    """법령 전문 두 호출 — 조문 전문(MR03)과 법령 목록(MR01, 법령명 역해석).

    둘 다 법령 상세 화면(USESTA002M)이 보내는 모양이다: MR03 ``{ntstBscId, ntstBrkdId, ntstPmgNo}``,
    MR01 ``{ntstSysClCd, ntstTlawClCd}``(Biz.doSearch — 2026-10-01 aside 판독).
    """
    bsc, brkd, pmg, sys_cd, tlaw = parse_law_id(law_id)
    referer = law_page_url(tlaw, sys_cd, bsc, brkd)
    mr03 = action_call(
        ACTION_LAW_DETAIL, {"ntstBscId": bsc, "ntstBrkdId": brkd, "ntstPmgNo": pmg}, referer
    )
    mr01 = action_call(ACTION_LAW_LIST, {"ntstSysClCd": sys_cd, "ntstTlawClCd": tlaw}, referer)
    return mr03, mr01


# ── 응답 판독 ──────────────────────────────────────────────────────────────


def unwrap_action(raw: bytes, action_id: str) -> dict:
    """저장된 응답 본문 → ``data[action_id]``. 200 이어도 JSON·SUCCESS·키가 아니면 실패다(no-silent-fallback)."""
    text = raw.decode("utf-8-sig", errors="replace")
    head = text.lstrip()[:1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        if head == "{":
            raise TaxlawAPIError(
                f"응답 JSON 이 끝까지 오지 않았습니다(잘림 의심, actionId={action_id}) — 새로 받으세요.",
                "truncated",
            ) from exc
        raise TaxlawAPIError(
            f"JSON 이 아닌 응답입니다(actionId={action_id}, 앞부분 {text.strip()[:80]!r}) — "
            "오류·점검 화면이거나 사이트 계약이 바뀌었습니다."
        ) from exc
    if not isinstance(parsed, dict):
        raise TaxlawAPIError(f"응답이 객체가 아닙니다 (actionId={action_id}) — 계약 변경 의심.")
    if parsed.get("status") != "SUCCESS":
        raise TaxlawAPIError(
            f"API status={parsed.get('status')!r} message={parsed.get('message')!r} (actionId={action_id})"
        )
    payload = parsed.get("data")
    if not isinstance(payload, dict):
        raise TaxlawAPIError(f"응답 data 가 객체가 아닙니다 (actionId={action_id}) — 계약 변경 의심.")
    data = payload.get(action_id)
    if data is None:
        others = ", ".join(sorted(payload)) or "없음"
        raise TaxlawAPIError(
            f"응답에 data[{action_id!r}] 가 없습니다(있는 키: {others}) — 다른 호출의 응답이거나 계약 변경."
        )
    if not isinstance(data, dict):
        raise TaxlawAPIError(f"data[{action_id!r}] 가 객체가 아닙니다 — 계약 변경 의심.")
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


def _need_str(value) -> None:
    if not isinstance(value, str):
        raise TaxlawAPIError(f"문자열이어야 할 필드에 {type(value).__name__} 값이 왔습니다 — 응답 계약 변경 의심.")


def objects(value, where: str) -> list[dict]:
    """응답 목록 — ``None`` 은 빈 목록, 목록이 아니거나 원소가 객체가 아니면 ``site``(traceback 대신)."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise TaxlawAPIError(f"{where} 가 객체 목록이 아닙니다 — 응답 계약 변경 의심.")
    return value


def check_echo(data: dict, expected: dict, what: str) -> None:
    """응답이 되비친 요청 값이 계획과 같은지. 되비침이 없으면 대조 없이 통과하지 않는다(``site``)."""
    for key, want in expected.items():
        if key not in data or data[key] is None:
            raise TaxlawAPIError(f"{what} 응답에 되비친 {key} 가 없습니다 — 대조할 수 없어 멈춥니다(계약 변경 의심).")
        got = data[key]
        if got != want:
            raise TaxlawAPIError(
                f"{what} 응답이 되비친 {key}={got!r} 가 계획({want!r})과 다릅니다 — 보낸 본문이 plan 출력과 다릅니다. "
                "plan 이 준 호출을 그대로 보냈는지 확인하고 새 하위 폴더로 다시 받으세요.",
                "mismatch",
            )


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
    _need_str(text)
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
    _need_str(fragment)
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
    if raw:
        _need_str(raw)
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
        # id = 조문 전문(MR03) 키 3종 + 법령 목록(MR01) 키 2종 — 두 호출을 한 번에 계획한다.
        "id": ":".join(
            [it.get(k) or "" for k in ("BSC_ID", "BRKD_ID", "PMG_NO", "SYS_CL_CD", "TLAW_CL_CD")]
        ) if is_statute and it.get("SYS_CL_CD") and it.get("TLAW_CL_CD") else "",
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
        "detail_url": dcm_page_url(domain, doc_id) if doc_id else "",
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
        "detail_url": counsel_page_url(req_id) if req_id else "",
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


# ── 판독 결과 ──────────────────────────────────────────────────────────────


SEARCH_ECHO_KEYS = ("schVcb", "collection", "startCount", "viewCount", "sortField", "searchType", "icldVcbCtl", "exclVcbCtl")


def search_echo(param: dict) -> dict:
    """계획한 paramData 에서 응답이 되비쳐야 할 값 — 응답은 ``startCount``·``viewCount`` 를 문자열로 싣는다(실측)."""
    return {k: (str(param[k]) if k in ("startCount", "viewCount") else param[k]) for k in SEARCH_ECHO_KEYS}


def parse_search_response(data: dict, domains: list[str], *, limit: int, page: int, param: dict) -> dict:
    """ASEISA001MR01 응답 → ``{"domains": {domain: {"total", "items"[, "missing"]}}, "warnings": [...]}``.

    먼저 응답 상위가 되비친 요청(검색어·컬렉션·시작 번호·건수·정렬·검색 종류·포함/제외어)을 계획한 ``param`` 과
    대조한다 — 다르면 다른 질의의 응답이다(``mismatch``). 저장 이름 지문은 plan 이 이름을 지었다는 것만 증명한다.

    도메인마다 받은 건수를 분모로 대조한다: 기대 건수 = ``min(limit, total - start + 1)``(0 이하면 0).
    ``resultCount``·``resultList`` 길이가 그와 다르면 실패다(부분본을 전량처럼 말하지 않는다 — collection-completeness).
    요청한 도메인이 응답에 없으면 0건과 구별되는 ``missing`` 블록으로 둔다.
    """
    vo = data.get("searchResultVO")
    if not isinstance(vo, dict):
        raise TaxlawAPIError("searchResultVO 가 없습니다 — 응답 계약 변경 의심.")
    err = vo.get("errorMsg")
    if err and err != "no error":
        raise TaxlawAPIError(f"검색엔진 오류: {err}")
    check_echo(data, search_echo(param), "검색")
    colls = vo.get("collectionList")
    if not isinstance(colls, list):
        raise TaxlawAPIError("collectionList 가 목록이 아닙니다 — 응답 계약 변경 의심.")
    colls = objects(colls, "collectionList")
    start = (page - 1) * limit + 1
    got: dict = {}
    for coll in colls:
        domain = _COLLECTION_TO_DOMAIN.get(coll.get("nameEn") or "")
        if domain is None:
            continue  # intEpn 등 스킬 비대상 컬렉션
        if domain not in domains:
            raise TaxlawAPIError(
                f"요청하지 않은 컬렉션 {coll.get('nameEn')!r} 이 응답에 있습니다 — 다른 질의의 응답입니다.",
                "mismatch",
            )
        if domain in got:
            raise TaxlawAPIError(f"컬렉션 {coll.get('nameEn')!r} 이 응답에 두 번 있습니다.")
        total = coll.get("totalCount")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise TaxlawAPIError(f"{domain}: totalCount 형식이 계약과 다릅니다.")
        results = objects(coll.get("resultList"), f"{domain} resultList")
        expected = max(0, min(limit, total - start + 1))
        count = coll.get("resultCount")
        if not results and expected and start > 1:
            raise TaxlawAPIError(
                f"{DOMAIN_LABELS[domain]}: 전체 {total:,}건인데 검색엔진이 {start:,}번째부터는 결과를 주지 않았습니다 — "
                "다시 받아도 같습니다. 검색어를 좁히거나 포함어·제외어·문서번호 검색으로 분모를 줄이세요.",
                "incomplete",
            )
        if len(results) != expected or (count is not None and count != len(results)):
            raise TaxlawAPIError(
                f"{DOMAIN_LABELS[domain]}: 전체 {total}건 중 {start}번째부터 {expected}건이 와야 하는데 "
                f"{len(results)}건(resultCount={count!r})이 왔습니다 — 결과를 말하지 않습니다.",
                "incomplete",
            )
        got[domain] = {"total": total, "items": [_NORMALIZERS[domain](it) for it in results]}
    warnings = []
    ordered: dict = {}
    for d in domains:
        if d in got:
            ordered[d] = got[d]
            if got[d]["total"] and not got[d]["items"]:
                warnings.append(
                    f"{DOMAIN_LABELS[d]}: 전체 {got[d]['total']}건 — {page}쪽은 마지막 쪽 너머라 비었습니다."
                )
        else:
            ordered[d] = {"total": None, "items": [], "missing": True}
            warnings.append(f"{DOMAIN_LABELS[d]}: 응답에 이 도메인이 없습니다(0건이 아니라 미수신 — 사이트 계약 변경 의심).")
    return {"domains": ordered, "warnings": warnings}


def _document_body(data: dict) -> str:
    """상세 응답의 dcmHwpEditorDVOList 에서 html 전문을 추출."""
    parts = []
    for entry in objects(data.get("dcmHwpEditorDVOList"), "dcmHwpEditorDVOList"):
        if entry.get("dcmFleTy") == "html" and entry.get("dcmFleByte"):
            parts.append(html_to_text(entry["dcmFleByte"]))
    return "\n\n".join(p for p in parts if p)


def parse_dcm_detail(data: dict, doc_id: str, domain: str) -> dict:
    """세법해석례·판례 상세(전문). 문서가 없으면 사이트는 SUCCESS 인 채 ``dcmDVO=null`` 을 준다."""
    dvo = data.get("dcmDVO")
    if not isinstance(dvo, dict) or not (dvo.get("ntstDcmId") or dvo.get("ntstDcmTtl")):
        raise TaxlawAPIError(f"문서를 찾을 수 없습니다 (ntstDcmId={doc_id}).", "not_found")
    check_echo(dvo, {"ntstDcmId": doc_id}, "문서 상세")
    related = [
        clean_text(r.get("ntstTextNm") or "")
        for r in objects(data.get("dcmRltnStttList"), "dcmRltnStttList")
        if r.get("ntstTextNm")
    ]
    return {
        "domain": domain,
        "id": doc_id,
        "title": clean_text(dvo.get("ntstDcmTtl") or ""),
        "doc_no": clean_text(dvo.get("ntstDcmDscmCntn") or ""),
        "date": _fmt_date(dvo.get("ntstDcmRgtDt") or ""),
        "gist": clean_text(dvo.get("ntstDcmGistCntn") or ""),
        "reply": clean_text(dvo.get("ntstDcmCntn") or ""),
        "body": _document_body(data),
        "related_laws": related,
        "detail_url": dcm_page_url(domain, doc_id),
    }


def parse_counsel_detail(data: dict, req_std_id: str) -> dict:
    if not data.get("stdTitle"):
        raise TaxlawAPIError(f"상담사례를 찾을 수 없습니다 (reqStdId={req_std_id}).", "not_found")
    check_echo(data, {"reqStdId": req_std_id}, "상담사례")
    return {
        "domain": "counsel",
        "id": req_std_id,
        "title": clean_text(data.get("stdTitle") or ""),
        "tax_type": clean_text(data.get("reqTpNm") or ""),
        "date": _fmt_date(data.get("regstDt") or ""),
        "answer": html_to_text(data.get("answerStdContent") or ""),
        "detail_url": counsel_page_url(req_std_id),
    }


def parse_law_detail(mr03: dict, mr01: dict, law_id: str, *, article: str | None = None) -> dict:
    """법령 조문 전문. MR03 행에는 법령명·구분코드가 없어(항상 null — 실측) MR01 에서 같은 ntstBscId 행을 찾는다.

    MR01 에 그 행이 없으면 법령명을 비우고 ``warnings`` 로 알린다(지어내지 않는다).
    """
    bsc, brkd, pmg, sys_cd, tlaw = parse_law_id(law_id)
    check_echo(mr03, {"ntstBscId": bsc, "ntstBrkdId": brkd, "ntstPmgNo": pmg}, "조문 전문")
    check_echo(mr01, {"ntstSysClCd": sys_cd, "ntstTlawClCd": tlaw}, "법령 목록")
    rows = mr03.get("txaStttHsryDVOList")
    if not rows:
        raise TaxlawAPIError(f"조문을 찾을 수 없습니다 (id={law_id}).", "not_found")
    rows = objects(rows, "txaStttHsryDVOList")
    other = {r.get("ntstBrkdId") for r in rows if r.get("ntstBrkdId")} - {brkd}
    if other:
        raise TaxlawAPIError(
            f"다른 법령 버전의 응답입니다(ntstBrkdId {sorted(other)[0]}, 요청 {brkd}).", "mismatch"
        )
    law_rows = mr01.get("txaStttDVOList")
    if not isinstance(law_rows, list):
        raise TaxlawAPIError("txaStttDVOList 가 목록이 아닙니다 — 법령 목록 응답이 아니거나 계약 변경.")
    law_rows = objects(law_rows, "txaStttDVOList")
    # MR01 은 그 체계(법률·시행령 …)의 법령 목록 전체다(2026-10-01 실측: 01/101 → 세법 31행, 02/ZZZ → 4,775행).
    if any(r.get("ntstSysClCd") != sys_cd for r in law_rows):
        raise TaxlawAPIError(
            f"법령 목록에 체계구분 {sys_cd} 이 아닌 행이 있습니다 — 다른 id 의 파일을 넘겼습니다.", "mismatch"
        )
    law_name = ""
    for r in law_rows:
        if r.get("ntstBscId") == bsc:
            if r.get("ntstTlawClCd") != tlaw:
                raise TaxlawAPIError(
                    f"id 의 세법구분({tlaw})과 법령 목록의 값({r.get('ntstTlawClCd')})이 다릅니다.", "mismatch"
                )
            law_name = clean_text(r.get("ntstNm") or "")
            break
    warnings = [] if law_name else [f"법령 목록({sys_cd}/{tlaw})에 ntstBscId {bsc} 가 없어 법령명을 비웠습니다."]
    articles = []
    for row in rows:
        art_no = clean_text(row.get("ntstTextUqnm") or "")
        name = clean_text(row.get("ntstTextNm") or "")
        if article:
            # 실측 구조: 조 본문은 헤더 행이 아니라 후속 항·호·목 행에 있고,
            # 그 행들의 ntstTextNm 이 "제2조 제1호"처럼 조 표시로 시작한다.
            if not (art_no == article or name.startswith(article + " ")):
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
        raise TaxlawAPIError(f"{law_name or bsc}에서 {article!r} 조문을 찾지 못했습니다.", "not_found")
    return {
        "domain": "law",
        "id": law_id,
        "law_name": law_name,
        "article_count": len(rows),
        "articles": articles,
        "detail_url": law_page_url(tlaw, sys_cd, bsc, brkd),
        "warnings": warnings,
    }
