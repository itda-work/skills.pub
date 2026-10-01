"""web-search 엔진 표 — 호출 계획(``http_request`` 인자)과 응답 파서. 네트워크 없음.

요청은 itda-hyve 의 ``http_request`` 가 보낸다(itda-work/skills#45, 규칙 ``cowork-network-via-hyve``).
이 모듈은 ① 엔진마다 그대로 보낼 ``http_request`` 인자를 만들고(:func:`build_call`)
② itda-hyve 가 ``save_as`` 로 저장한 응답 본문을 정규화 결과로 바꾼다(:func:`parse_response`).

키는 값이 아니라 ``{{secret:NAME}}`` 자리표시자로만 싣는다 — 전부 **헤더**다(URL·쿼리·본문에 키 없음).
이름은 itda-hyve 프리셋 이름 그대로다(``NAVER_CLIENT_ID``·``NAVER_CLIENT_SECRET`` 하나로 통일, 0.3.0).
Perplexity 는 0.3.0 에서 뺐다 — Sonar Chat Completions 지원이 2026-09-27 에 끝났다(필요해지면 Agent API 로 다시 넣는다).

응답 오류 본문 모양(2026-09-30 itda-hyve 로 인증 없이 보낸 실측 — ``tests/fixtures/noauth-*.json``):
    tavily      401 ``{"detail": {"error": "Unauthorized: …"}}``
    naver       401 ``{"errorMessage": "…", "errorCode": "024"}``
    serper      403 ``{"message": "Unauthorized. …", "statusCode": 403}``
    exa         402 ``{"error": "Payment required …", "tag": "X402_PAYMENT_REQUIRED", …}`` — 키 없는 요청에만 오는 x402.
                키가 있는 요청의 402 는 크레딧·예산 소진이다(exa.ai/docs/reference/search, 2026-09-30 판독).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from search_results import EngineResponse, SearchResult, source_from_url, strip_html

TIMEOUT_SEC = 50  # Cowork 전송 상한(60초)보다 짧게
MAX_RESULTS = 20  # Tavily max_results 0–20(문서), Serper·Exa 도 같은 상한으로 묶는다
NAVER_MAX_DISPLAY = 100  # Naver display 최대 100(넘으면 SE02)
EXA_HIGHLIGHT_CHARS = 300  # 발췌 상한(search_results.SNIPPET_MAX)과 같게
NAVER_TYPES = {"web": "webkr", "news": "news", "blog": "blog"}
SAVE_DIR_NAME = "web-search"

# 엔진 → 시크릿 이름·유료 여부·발급 안내. ``paid: False`` 는 "무료 한도 안에서 자동 과금이 없다" 는 뜻이다
# (Serper 는 가입 시 일회성 크레딧 뒤 선불 충전 — 충전하지 않으면 과금되지 않는다). ``auto`` 는 이 엔진들만 고른다.
# 유료(exa)는 사용자가 지목했을 때만 부른다(비용 가드). 키가 있는지는 호출해 봐야 안다(itda-hyve ``secret_missing``).
ENGINE_SPECS: dict[str, dict[str, Any]] = {
    "tavily": {
        "label": "Tavily",
        "secrets": ["TAVILY_API_KEY"],
        "paid": False,
        "issue_url": "https://app.tavily.com",
    },
    "naver": {
        "label": "Naver",
        "secrets": ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"],
        "paid": False,
        "issue_url": "https://developers.naver.com",
    },
    "serper": {
        "label": "Serper",
        "secrets": ["SERPER_API_KEY"],
        "paid": False,
        "issue_url": "https://serper.dev",
    },
    "exa": {
        "label": "Exa",
        "secrets": ["EXA_API_KEY"],
        "paid": True,
        "issue_url": "https://dashboard.exa.ai",
    },
}

ENGINE_NAMES: list[str] = list(ENGINE_SPECS)
AUTO_ENGINES: list[str] = [name for name, spec in ENGINE_SPECS.items() if not spec["paid"]]
PAID_ENGINES: list[str] = [name for name, spec in ENGINE_SPECS.items() if spec["paid"]]


def secret_guide(engine: str) -> str:
    """키 미등록 안내 — itda-hyve 시크릿 탭 하나."""
    spec = ENGINE_SPECS[engine]
    names = " · ".join(f"`{name}`" for name in spec["secrets"])
    return (
        f"{spec['label']} 키가 등록되어 있지 않습니다 — itda-hyve GUI 시크릿 탭에 {names} 로 등록하세요"
        f"(발급: {spec['issue_url']})."
    )


# ---------------------------------------------------------------------------
# 호출 계획
# ---------------------------------------------------------------------------

def _clamp(count: int, upper: int) -> int:
    return max(1, min(count, upper))


def _naver_type(naver_type: str) -> str:
    return naver_type if naver_type in NAVER_TYPES else "web"


def fingerprint(engine: str, query: str, count: int, naver_type: str = "web") -> str:
    """질의 인자 전부(엔진·질의·건수·엔진 고유 인자)의 8자 지문 — 저장 이름이 곧 식별 계약이다."""
    key: dict[str, Any] = {"engine": engine, "query": query.strip(), "count": count}
    if engine == "naver":
        key["naver_type"] = _naver_type(naver_type)
    raw = json.dumps(key, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:8]


def save_name(engine: str, query: str, count: int, naver_type: str = "web") -> str:
    """``web-search/<엔진>-<지문>.json`` — 한글을 넣지 않는다."""
    return f"{SAVE_DIR_NAME}/{engine}-{fingerprint(engine, query, count, naver_type)}.json"


SAVE_NAME_RE = re.compile(r"^(?P<engine>[a-z]+)-(?P<fp>[0-9a-f]{8})\.json$")


def _json_post(url: str, key_headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", **key_headers}
    return {
        "url": url,
        "method": "POST",
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
    }


def build_call(engine: str, query: str, count: int, naver_type: str = "web") -> dict[str, Any]:
    """엔진 하나의 ``http_request`` 인자(``save_dir`` 만 빠짐). 키는 헤더 자리표시자뿐이다."""
    query = query.strip()
    if engine == "tavily":
        args = _json_post(
            "https://api.tavily.com/search",
            {"Authorization": "Bearer {{secret:TAVILY_API_KEY}}"},
            {"query": query, "max_results": _clamp(count, MAX_RESULTS), "search_depth": "basic",
             "include_answer": False},
        )
    elif engine == "serper":
        args = _json_post(
            "https://google.serper.dev/search",
            {"X-API-KEY": "{{secret:SERPER_API_KEY}}"},
            {"q": query, "num": _clamp(count, MAX_RESULTS), "gl": "kr", "hl": "ko"},
        )
    elif engine == "exa":
        args = _json_post(
            "https://api.exa.ai/search",
            {"x-api-key": "{{secret:EXA_API_KEY}}"},
            {"query": query, "numResults": _clamp(count, MAX_RESULTS), "type": "auto",
             "contents": {"highlights": {"maxCharacters": EXA_HIGHLIGHT_CHARS},
                          "text": {"maxCharacters": 500}}},
        )
    elif engine == "naver":
        kind = _naver_type(naver_type)
        params = {"query": query, "display": str(_clamp(count, NAVER_MAX_DISPLAY)), "start": "1"}
        if kind != "web":
            # sort 는 news·blog 문서에만 있다(웹문서 webkr 은 query·display·start 셋 — 문서에 없는 인자는 싣지 않는다).
            params["sort"] = "sim"
        args = {
            "url": f"https://openapi.naver.com/v1/search/{NAVER_TYPES[kind]}.json",
            "params": params,
            "headers": {"X-Naver-Client-Id": "{{secret:NAVER_CLIENT_ID}}",
                        "X-Naver-Client-Secret": "{{secret:NAVER_CLIENT_SECRET}}"},
        }
    else:
        raise ValueError(f"알 수 없는 엔진: {engine}")
    args["timeout_sec"] = TIMEOUT_SEC
    args["save_as"] = save_name(engine, query, count, naver_type)
    return args


# ---------------------------------------------------------------------------
# 응답 판정
# ---------------------------------------------------------------------------

class EngineError(Exception):
    """엔진 하나의 실패 — ``code`` 가 출력 ``errors[].code`` 다."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


_AUTH_WORDS = re.compile(r"unauthori|invalid[ _]api[ _]key|authenticat|forbidden|api key", re.I)
_RATE_WORDS = re.compile(
    r"rate[ _]?limit|too many|excessive requests|quota|exceed|limit reached|usage limit|credits?|budget|balance",
    re.I,
)
_EXPECTED_KEY = {"tavily": "results", "serper": "organic", "exa": "results", "naver": "items"}
_X402 = "X402_PAYMENT_REQUIRED"


def _error_text(engine: str, obj: dict[str, Any]) -> tuple[str, Any] | None:
    """본문이 엔진의 오류 모양이면 (메시지, 코드) — 아니면 None."""
    if engine == "tavily":
        detail = obj.get("detail")
        if isinstance(detail, dict) and detail.get("error"):
            return str(detail["error"]), None
        if isinstance(detail, str) and detail:
            return detail, None
        if isinstance(detail, list) and detail:
            # 422 검증 오류(문서 모양 ``{"detail": [{"loc", "msg", "type"}]}``) — 다른 엔진의 응답이 아니라 요청 오류다
            first = detail[0] if isinstance(detail[0], dict) else {}
            return f"요청 검증 오류: {first.get('msg') or detail[0]}", 422
        if isinstance(obj.get("error"), str):
            return obj["error"], None
    elif engine == "naver":
        if obj.get("errorCode") or obj.get("errorMessage"):
            return f"{obj.get('errorMessage', '')} (errorCode {obj.get('errorCode', '?')})", obj.get("errorCode")
    elif engine == "serper":
        if "statusCode" in obj or ("message" in obj and "organic" not in obj):
            return str(obj.get("message") or ""), obj.get("statusCode")
    elif engine == "exa":
        if obj.get("error"):
            tag = obj.get("tag")
            return str(obj["error"]) + (f" ({tag})" if tag else ""), tag
    return None


def classify(engine: str, message: str, code: Any = None, status: int | None = None) -> str:
    """오류 메시지·코드·HTTP 상태로 ``AUTH_FAILED``·``RATE_LIMITED``·``API_ERROR`` 를 가른다.

    Exa 402 는 둘로 갈린다 — ``X402_PAYMENT_REQUIRED`` 는 키 없는 요청(= 키 문제), 나머지 402 는 크레딧·예산 소진.
    """
    if engine == "exa" and code == _X402:
        return "AUTH_FAILED"
    if engine == "exa" and re.search(r"payment required", message, re.I):
        # 키가 있는 요청의 402 — 본문 그대로에는 상태가 없어 낱말로 본다(태그 목록은 문서가 열어 두었다, 재리뷰 n4)
        return "RATE_LIMITED"
    numeric = None
    for value in (code, status):
        try:
            numeric = int(value)
            break
        except (TypeError, ValueError):
            continue
    if engine == "naver":
        if str(code) in {"024", "028"}:
            return "AUTH_FAILED"
        if str(code) == "010":
            return "RATE_LIMITED"
    if numeric in (401, 403):
        return "AUTH_FAILED"
    if numeric in (402, 429, 432, 433):
        return "RATE_LIMITED"
    if _AUTH_WORDS.search(message):
        return "AUTH_FAILED"
    if _RATE_WORDS.search(message):
        return "RATE_LIMITED"
    return "API_ERROR"


def check_body(engine: str, data: bytes, status: int | None = None) -> dict[str, Any]:
    """본문을 JSON 으로 읽고 엔진 오류 모양이면 :class:`EngineError` — 정상이면 그 객체.

    결과 목록 키는 **있는지가 아니라 배열인지**로 본다 — 배열이 아니면 "성공 0건" 이 아니라 ``PARSE_ERROR``.
    """
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        head = " ".join(data[:200].decode("utf-8", errors="replace").split())[:80]
        raise EngineError(
            "PARSE_ERROR",
            f"{engine} 응답이 JSON 이 아닙니다(저장이 끊겼거나 HTML 오류 페이지): {head}",
        ) from None
    if not isinstance(obj, dict):
        raise EngineError("PARSE_ERROR", f"{engine} 응답이 JSON 객체가 아닙니다")
    found = _error_text(engine, obj)
    if found is not None:
        message, code = found
        raise EngineError(classify(engine, message, code, status), f"{engine}: {message}".strip())
    key = _EXPECTED_KEY[engine]
    if key not in obj:
        raise EngineError(
            "PARSE_ERROR",
            f"{engine} 응답에 `{key}` 가 없습니다 — 다른 엔진·다른 요청의 응답일 수 있습니다",
        )
    if not isinstance(obj[key], list):
        raise EngineError(
            "PARSE_ERROR",
            f"{engine} 응답의 `{key}` 가 배열이 아닙니다({type(obj[key]).__name__}) — 결과 0건으로 읽지 않습니다",
        )
    return obj


def echoed_query(engine: str, obj: dict[str, Any]) -> str | None:
    """응답이 되돌려 준 질의어(Tavily ``query``·Serper ``searchParameters.q``) — 없으면 None."""
    if engine == "tavily":
        value = obj.get("query")
    elif engine == "serper":
        params = obj.get("searchParameters")
        value = params.get("q") if isinstance(params, dict) else None
    else:
        return None
    return value if isinstance(value, str) else None


def same_query(a: str, b: str) -> bool:
    """유니코드 정규형(NFC)·공백·대소문자만 다른 질의는 같다고 본다(엔진이 되돌릴 때 정규화할 수 있다)."""
    def norm(text: str) -> str:
        return " ".join(unicodedata.normalize("NFC", text).split()).casefold()
    return norm(a) == norm(b)


def parse_response(engine: str, obj: dict[str, Any], count: int, naver_type: str = "web") -> EngineResponse:
    """정상 응답 객체를 정규화한다. url 이 없는 항목은 ``meta.skipped_no_url`` 로 센다."""
    results: list[SearchResult] = []
    skipped = 0
    meta: dict[str, Any] = {}
    answer: str | None = None

    def add(url: Any, fallback_source: str = "", **fields: Any) -> None:
        nonlocal skipped
        if not isinstance(url, str) or not url:
            skipped += 1
            return
        results.append(SearchResult(rank=len(results) + 1, url=url, engine=engine,
                                    source=source_from_url(url) or fallback_source, **fields))

    def items(key: str) -> list[dict[str, Any]]:
        return [item if isinstance(item, dict) else {} for item in obj[key]]

    if engine == "tavily":
        # published_date 는 include_published_date(또는 topic=news)를 줄 때만 온다 — 지금 요청으로는 늘 없다.
        for item in items("results"):
            url = item.get("url")
            add(url, title=strip_html(item.get("title")) or str(url or ""), snippet=strip_html(item.get("content")),
                score=item.get("score"), published_at=item.get("published_date"))
        # answer 는 싣지 않는다 — 요청이 include_answer: false 이고, 출력 계약은 "answer 는 늘 null" 이다(재리뷰 n8).
        meta = {"search_depth": "basic"}
    elif engine == "serper":
        for item in items("organic"):
            url = item.get("link")
            add(url, title=strip_html(item.get("title")) or str(url or ""), snippet=strip_html(item.get("snippet")),
                published_at=item.get("date"))
        meta = {"gl": "kr"}
    elif engine == "exa":
        for item in items("results"):
            url = item.get("url")
            highlights = item.get("highlights") or []
            snippet = strip_html(" ".join(h for h in highlights if isinstance(h, str))) or strip_html(
                (item.get("text") or "")[:500])
            add(url, title=strip_html(item.get("title")) or str(url or ""), snippet=snippet,
                published_at=item.get("publishedDate"))
        meta = {"type": "auto"}
    elif engine == "naver":
        for item in items("items"):
            url = item.get("link")
            add(url, title=strip_html(item.get("title")) or str(url or ""),
                snippet=strip_html(item.get("description")),
                published_at=item.get("pubDate") or item.get("postdate"),
                fallback_source=str(item.get("bloggername") or ""))
        meta = {"naver_type": _naver_type(naver_type)}
        if isinstance(obj.get("total"), int):
            meta["total"] = obj["total"]
    else:
        raise ValueError(f"알 수 없는 엔진: {engine}")

    if skipped:
        meta["skipped_no_url"] = skipped
    return EngineResponse(engine=engine, results=results, answer=answer, meta=meta)
