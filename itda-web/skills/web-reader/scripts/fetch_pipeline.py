"""fetch_pipeline.py - 정적 fetch orchestrator (web-reader v3.0.0).

# @MX:NOTE: [AUTO] SPEC-WEBREADER-LIGHTEN-001 v3.0.0 — 동적 fetch / SPA 어댑터 일체 제거.
# 동적 use case 는 브라우저 경로(itda-web:aside-browser-mcp, Aside 브라우저)로 위임.
# 하위 호환을 위해 fetch_with_fallback() 시그니처는 유지하되, dynamic_only=True 또는
# site_pattern.dynamic=True 호출 시 ValueError 로 fail-fast 한다 (REQ-LIGHTEN-003).

본 모듈은 정적 fetch 단일 경로만 운영한다:
- _do_static_fetch: fetch_html.py 로 정적 fetch 수행
- assess_static_quality: 본문 품질 휴리스틱 (진단/로깅 용도)
- fetch_with_fallback: 정적 fetch + 품질 진단 로깅 (동적 폴백 없음)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# scripts/ 디렉토리 절대 경로 (importlib 기반 로딩에 사용)
_scripts_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

MIN_TEXT_LENGTH_DEFAULT = 500
MIN_MEANINGFUL_TAGS_DEFAULT = 3

# v3.0.0 마이그레이션 안내 메시지 (REQ-LIGHTEN-003.4)
# AC-3 검증 키워드 모두 포함: "동적 fetch 는 web-reader v3.0.0 에서 제거",
# "aside-browser-mcp"
DYNAMIC_MIGRATION_MSG = (
    "[web-reader v3.0.0] 동적 fetch 는 web-reader v3.0.0 에서 제거되었습니다.\n"
    "JavaScript 렌더링이 필요한 페이지는 브라우저 경로(itda-web:aside-browser-mcp, Aside 브라우저)를 사용하세요.\n"
    "마이그레이션 안내: itda-web/skills/web-reader/GUIDE.md 참조.\n"
)


# ---------------------------------------------------------------------------
# 데이터 클래스 (v2 와 동일 — 외부 호출자 호환 보존)
# ---------------------------------------------------------------------------

@dataclass
class QualityVerdict:
    """콘텐츠 품질 사전 판정 결과."""

    passed: bool
    text_length: int
    meaningful_tag_count: int
    quality_score: float
    reason: str


@dataclass
class FetchResult:
    """fetch_with_fallback() 반환 결과.

    v3.0.0 부터 fetch_method 는 항상 "static" 또는 "degraded_static" 만 반환.
    "dynamic" 값은 더 이상 발생하지 않는다.
    """

    html: str
    final_url: str
    # fetch_method: "static" | "degraded_static"  (v2 의 "dynamic" 제거됨)
    fetch_method: str
    quality_score: float
    meaningful_tag_count: int
    fallback_reason: str
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 콘텐츠 품질 휴리스틱 (진단/로깅 용도)
# ---------------------------------------------------------------------------

def assess_static_quality(
    html: str,
    *,
    min_text_length: int = MIN_TEXT_LENGTH_DEFAULT,
    min_meaningful_tags: int = MIN_MEANINGFUL_TAGS_DEFAULT,
) -> QualityVerdict:
    """정적 fetch 결과의 본문 품질을 사전 판정한다.

    # @MX:NOTE: [AUTO] v3.0.0 기준 — 진단/로깅 용도. 더 이상 동적 폴백 트리거가 아님.
    # passed=False 인 경우에도 호출자는 정적 결과를 그대로 사용한다.

    Args:
        html: 정적 fetch 로 받은 HTML 문자열.
        min_text_length: 텍스트 길이 임계값 (기본 500).
        min_meaningful_tags: 의미 있는 태그 최소 수 (기본 3).

    Returns:
        QualityVerdict (passed, text_length, meaningful_tag_count, quality_score, reason).
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return QualityVerdict(
            passed=True,
            text_length=0,
            meaningful_tag_count=0,
            quality_score=1.0,
            reason="bs4 unavailable, skipping quality check",
        )

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()

    body = soup.find("body")
    body_text = (body or soup).get_text(separator=" ", strip=True) if soup else ""
    text_length = len(body_text)

    meaningful_tag_count = (
        len(soup.find_all("p"))
        + len(soup.find_all("article"))
        + len(soup.find_all("section"))
        + sum(len(soup.find_all(f"h{i}")) for i in range(1, 7))
    )

    quality_score = min(
        text_length / max(min_text_length, 1),
        meaningful_tag_count / max(min_meaningful_tags, 1),
        1.0,
    )

    passed = quality_score >= 1.0

    if passed:
        reason = ""
    else:
        parts = []
        if text_length < min_text_length:
            parts.append(f"text_length={text_length} < {min_text_length}")
        if meaningful_tag_count < min_meaningful_tags:
            parts.append(f"meaningful_tags={meaningful_tag_count} < {min_meaningful_tags}")
        reason = "; ".join(parts) or "quality below threshold"

    return QualityVerdict(
        passed=passed,
        text_length=text_length,
        meaningful_tag_count=meaningful_tag_count,
        quality_score=quality_score,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 정적 fetch (단일 경로)
# ---------------------------------------------------------------------------

def _maybe_escalation(fetch_result: dict, url: str):
    """fetch_html 결과 dict가 must_escalate 를 신호하면 StaticFetchEscalate 를 반환.

    이게 P0 전파의 핵심 seam이다 — 정적 give-up 을 None(→ ContentExtractionError →
    exit 1)으로 뭉개지 않고, extract_content 가 broad fallback 보다 먼저 catch 해
    exit 4 (브라우저 경로 에스컬레이트)로 라우팅하게 한다. 순수 함수라 단위테스트 가능."""
    if not fetch_result.get("must_escalate"):
        return None
    from exceptions import StaticFetchEscalate  # type: ignore[import]

    return StaticFetchEscalate(
        url=url,
        stop_reason=str(fetch_result.get("stop_reason", "")),
        untried_routes=list(fetch_result.get("untried_routes") or []),
    )


def _do_static_fetch(
    url: str,
    min_text_length: int,
    min_meaningful_tags: int,
) -> FetchResult | None:
    """fetch_html 모듈로 정적 fetch 를 수행하고 FetchResult 를 반환한다.

    Raises:
        StaticFetchEscalate: 정적 격자가 WAF/차단으로 소진됐을 때 (P0 — exit 4 경로).
    """
    import importlib.util as _ilu

    filepath = os.path.join(_scripts_dir, "fetch_html.py")
    spec = _ilu.spec_from_file_location("fetch_html", filepath)
    if spec is None or spec.loader is None:
        return None
    fh = _ilu.module_from_spec(spec)
    spec.loader.exec_module(fh)  # type: ignore[union-attr]

    fetch_result = fh.fetch_url(url)
    _esc = _maybe_escalation(fetch_result, url)
    if _esc is not None:
        raise _esc
    if not fetch_result.get("content") or fetch_result.get("error"):
        return None

    html = str(fetch_result["content"])
    final_url = str(fetch_result.get("url") or url)
    verdict = assess_static_quality(
        html,
        min_text_length=min_text_length,
        min_meaningful_tags=min_meaningful_tags,
    )

    return FetchResult(
        html=html,
        final_url=final_url,
        fetch_method="static",
        quality_score=verdict.quality_score,
        meaningful_tag_count=verdict.meaningful_tag_count,
        fallback_reason="",
        extra={
            "headers": fetch_result.get("headers", {}),
            # 봉투(provenance) 재료 — extract_content 가 JSON `provenance` 로 싣는다 (v7.1.0, #1600 T0).
            # fetch_html 결과에 이미 있던 값을 버리지 않고 전달하는 것이 골자.
            "status_code": fetch_result.get("status_code"),
            "content_sha256": fetch_result.get("content_sha256"),
            "encoding": fetch_result.get("encoding"),
            "waf_profile": fetch_result.get("waf_profile"),
            "fetch_phase": _last_trace_phase(fetch_result) or "static",
            "fetched_at": _utc_now_iso(),
        },
    )


def _last_trace_phase(fetch_result: dict) -> str | None:
    trace = fetch_result.get("trace")
    if isinstance(trace, list) and trace:
        last = trace[-1]
        if isinstance(last, dict) and last.get("phase"):
            return str(last["phase"])
    return None


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# fetch_with_fallback orchestrator (v3.0.0 — 정적 단일 경로)
# ---------------------------------------------------------------------------

# @MX:ANCHOR: [AUTO] fetch_with_fallback — 정적 fetch 단일 진입점 (v3.0.0).
# @MX:REASON: extract_content.py + 외부 호출자가 본 함수 시그니처에 의존.
# v3.0.0 변경: dynamic_only / site_pattern.dynamic → ValueError fail-fast.
# 정적 폴백 로직 단순화: site_pattern → 정적 fetch → 품질 진단 → 반환.
def fetch_with_fallback(
    url: str,
    *,
    static_only: bool = False,
    dynamic_only: bool = False,
    min_text_length: int = MIN_TEXT_LENGTH_DEFAULT,
    min_meaningful_tags: int = MIN_MEANINGFUL_TAGS_DEFAULT,
    site_pattern: dict | None = None,
    stderr_out=None,
) -> FetchResult:
    """정적 fetch orchestrator (web-reader v3.0.0).

    REQ-LIGHTEN-003: 동적 fetch 요청 시 ValueError 로 fail-fast.

    Args:
        url: fetch 할 URL.
        static_only: True 이면 정적 fetch 만 (기본 동작과 동일 — v3.0.0 부터 의미 없음).
        dynamic_only: True 이면 ValueError 발생 (v3.0.0 부터 동적 미지원).
        min_text_length: 품질 진단 텍스트 길이 임계값 (로깅 용도).
        min_meaningful_tags: 품질 진단 의미 태그 수 임계값 (로깅 용도).
        site_pattern: match_site_pattern() 결과 dict. dynamic=True 면 ValueError 발생.
        stderr_out: 메시지 출력 대상 (기본: sys.stderr).

    Returns:
        FetchResult (html, final_url, fetch_method, quality_score, ...).

    Raises:
        ValueError: dynamic_only=True 또는 site_pattern.dynamic=True 인 경우 (v3.0.0).
        ContentExtractionError: 정적 fetch 가 빈 본문일 때.
    """
    import sys as _sys
    from exceptions import ContentExtractionError  # type: ignore[import]

    _out = stderr_out or _sys.stderr

    def _log(msg: str) -> None:
        print(msg, file=_out)

    # REQ-LIGHTEN-003.5: 동적 fetch 요청 fail-fast (Python API 경로)
    if dynamic_only:
        raise ValueError(DYNAMIC_MIGRATION_MSG)

    # REQ-LIGHTEN-003.5: site_pattern.dynamic=True 도 동적 요청으로 간주
    if site_pattern and site_pattern.get("dynamic"):
        raise ValueError(DYNAMIC_MIGRATION_MSG)

    # ── 정적 fetch (단일 경로) ─────────────────────────────────────────────
    static_result = _do_static_fetch(url, min_text_length, min_meaningful_tags)

    if static_result is None:
        raise ContentExtractionError(
            url=url,
            html_size=0,
            failed_field="body",
            attempted_selectors=[],
            original_exc=None,
        )

    # 품질 미달은 더 이상 동적 폴백 트리거가 아니다 — 진단 로깅만 수행.
    if static_result.quality_score < 1.0:
        _log(
            f"[web-reader] 정적 fetch 품질 진단: score={static_result.quality_score:.2f} "
            f"(text_length={int(static_result.quality_score * min_text_length)}, "
            f"meaningful_tags={static_result.meaningful_tag_count}). "
            "JavaScript 렌더링이 필요한 페이지라면 브라우저 경로(itda-web:aside-browser-mcp) 사용."
        )

    return static_result
