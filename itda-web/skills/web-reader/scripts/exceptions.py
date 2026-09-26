"""exceptions.py - web-reader 진단 가능한 추출 에러 클래스.

SPEC-WEBREADER-008 REQ-5: ContentExtractionError 예외 클래스.
SPEC-WEBREADER-010 REQ-001: SelectorError / SelectorNoMatchError / SelectorSyntaxError.
본문 추출 파이프라인 전체가 소진되었을 때만 raise (메타 누락은 절대 raise 안 함).
"""
from __future__ import annotations


# @MX:NOTE: [AUTO] 진단 가능한 추출 에러 — REQ-5.
# 4개 진단 필드(url, html_size, failed_field, attempted_selectors)는 acceptance.md AC-4의 단언 대상.
# original_exc != None이면 raise ... from으로 __cause__ chain 보존 (REQ-5.3).
# stringify 포맷 변경 시 회귀 테스트 영향 확인.
# raise 시점 정책 (REQ-5.2):
#   - fallback chain 내 한 후보 selector 실패 → silent skip
#   - metadata 추출 한 필드 누락 → silent skip (REQ-1.4)
#   - 본문 추출 fallback chain 전체 소진 → ContentExtractionError raise
#   - 정적+동적+degrade 모두 빈 본문 → ContentExtractionError raise
class ContentExtractionError(Exception):
    """본문 추출 파이프라인 전체 소진 시 발생하는 진단 가능한 예외.

    Args:
        url: 처리하던 URL. 없으면 "<input file>" 또는 "<stdin>".
        html_size: HTML payload 바이트 수.
        failed_field: 실패한 추출 필드 ("title" / "body" / "og:image" 등).
        attempted_selectors: 시도한 CSS selector 목록 (순서 보존).
        original_exc: 원인 예외. non-None이면 raise ... from으로 __cause__ chain 보존.
    """

    def __init__(
        self,
        *,
        url: str,
        html_size: int,
        failed_field: str,
        attempted_selectors: list[str],
        original_exc: Exception | None = None,
    ) -> None:
        self.url = url
        self.html_size = html_size
        self.failed_field = failed_field
        self.attempted_selectors = list(attempted_selectors)
        self.original_exc = original_exc
        super().__init__(str(self))

    def __str__(self) -> str:
        """REQ-5.4 사람-친화 포맷 출력."""
        selector_lines = "\n".join(
            f"    - {sel}" for sel in self.attempted_selectors
        )
        if self.original_exc is not None:
            cause_str = f"{type(self.original_exc).__name__}: {self.original_exc}"
        else:
            cause_str = "<none>"

        return (
            f"ContentExtractionError: {self.failed_field} 추출 실패\n"
            f"  URL: {self.url}\n"
            f"  HTML 크기: {self.html_size} bytes\n"
            f"  시도한 selector:\n{selector_lines}\n"
            f"  원인: {cause_str}"
        )


# ---------------------------------------------------------------------------
# 정적 fetch 실패 게이트 (P0) — WAF 차단 소진을 '도달 불가'와 구분해 에스컬레이션.
# fetch_html.fetch_url() 가 must_escalate 를 신호하면 fetch_pipeline 이 이 예외를
# raise 하고, extract_content 가 broad fallback 보다 먼저 catch → exit 4
# (bot-challenge exit 4 와 동일한 의미). 단순 네트워크/404 실패는
# 이 예외를 쓰지 않고 기존대로 None → ContentExtractionError → exit 1 로 흐른다.
# ---------------------------------------------------------------------------


class StaticFetchEscalate(Exception):
    """정적 curl 격자가 WAF/차단으로 소진됐고, 브라우저 경로로 에스컬레이트해야 함을 알린다.

    Args:
        url: 처리하던 URL.
        stop_reason: 실패 분류 (challenge / forbidden 등 — fetch_html._classify_giveup).
        untried_routes: 정적 경로가 못 하는 다음 단계(예: itda-web:aside-browser-mcp).
    """

    def __init__(
        self,
        *,
        url: str,
        stop_reason: str,
        untried_routes: list[str],
    ) -> None:
        self.url = url
        self.stop_reason = stop_reason
        self.untried_routes = list(untried_routes)
        super().__init__(str(self))

    def escalation_message(self) -> str:
        """에이전트가 다음 행동을 결정론적으로 고르도록 stderr 에 출력할 안내문."""
        lines = [
            f"[web-reader] 정적 curl 격자 소진(stop_reason={self.stop_reason}) — "
            f"사이트를 '도달 불가'로 선언하지 마세요. {self.url}",
            "정적 curl 로는 anti-bot 우회가 안 됩니다. 다음 경로로 에스컬레이트:",
        ]
        for route in self.untried_routes:
            lines.append(f"  • {route}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return (
            f"StaticFetchEscalate: {self.stop_reason} — {self.url} "
            f"(untried: {', '.join(self.untried_routes) or '<none>'})"
        )


# ---------------------------------------------------------------------------
# SPEC-WEBREADER-010 REQ-001: Selector 도메인 예외 계층
# ContentExtractionError와 형제 관계 (상속 X) — selector 입력 오류는
# 파이프라인 소진과 의미가 달라 별도 베이스로 분리.
# ---------------------------------------------------------------------------


class SelectorError(Exception):
    """CSS selector 처리 실패의 베이스 예외."""


# @MX:NOTE: [AUTO] SelectorNoMatchError — selector 매칭 0건 도메인 예외.
# @MX:SPEC: SPEC-WEBREADER-010 REQ-001 / AC-001 / AC-003
# main()에서 catch → exit 1 + SPEC-009 AC-3 메시지 (byte-level).
class SelectorNoMatchError(SelectorError):
    """selector가 문서에서 0개의 요소를 매칭한 경우 발생.

    Args:
        selector: 사용자 지정 CSS selector 문자열.
        target: 검색 대상 ("document" | "rendered_page").
    """

    def __init__(self, *, selector: str, target: str) -> None:
        self.selector = selector
        self.target = target
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"CSS selector '{self.selector}' matched 0 elements in the {self.target}."
        )


# @MX:NOTE: [AUTO] SelectorSyntaxError — CSS selector 문법 오류 도메인 예외.
# @MX:SPEC: SPEC-WEBREADER-010 REQ-001 / AC-002 / AC-004
# soupsieve.SelectorSyntaxError와 이름 동일 — import 시 alias 필수
# (from exceptions import SelectorSyntaxError as DomainSelectorSyntaxError).
class SelectorSyntaxError(SelectorError):
    """CSS selector 문법 오류 발생 시 raise.

    Args:
        selector: 오류가 발생한 CSS selector 문자열.
        cause: 원본 soupsieve 에러 메시지.
    """

    def __init__(self, *, selector: str, cause: str) -> None:
        self.selector = selector
        self.cause = cause
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"Invalid CSS selector syntax: {self.cause}"
