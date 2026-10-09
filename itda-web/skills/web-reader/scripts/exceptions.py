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
