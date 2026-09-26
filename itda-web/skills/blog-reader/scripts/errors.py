"""errors.py - blog-reader 예외 타입 정의.

REQ-BLOGREADER-009: exit code 매핑
  0 - 성공 (정상)
  1 - 일반 실패 (BlogStructureChangedError)
  2 - 인자 오류 (ArgumentError)
  3 - 대상 없음 (EmptyResultError)
  4 - anti-bot 차단 (AntiBotBlockError)
  5 - 미지원 플랫폼 (UnsupportedPlatformError)
  6 - 비공개/삭제 (BlogNotFoundError)
"""
from __future__ import annotations


class BlogReaderError(Exception):
    """blog-reader 예외 기반 클래스.

    모든 blog-reader 예외는 이 클래스를 상속한다.
    exit_code 클래스 속성으로 프로세스 종료 코드를 정의한다.
    """

    # @MX:NOTE: [AUTO] exit_code는 클래스 속성 — 인스턴스에서도 접근 가능
    exit_code: int = 1


class BlogStructureChangedError(BlogReaderError):
    """파서가 인식하지 못하는 HTML 구조 변경 시 발생.

    네이버 블로그 HTML 구조가 변경되어 파싱에 실패할 때 사용한다.
    exit code: 1 (일반 실패)
    """

    exit_code: int = 1


class ArgumentError(BlogReaderError):
    """CLI 인자 오류 또는 필수 옵션 누락 시 발생.

    exit code: 2 (인자 오류)
    """

    exit_code: int = 2


class EmptyResultError(BlogReaderError):
    """조회 결과가 0건일 때 발생.

    블로그 ID·logNo·검색 결과가 모두 없을 때 사용한다.
    exit code: 3 (대상 없음)
    """

    exit_code: int = 3


class AntiBotBlockError(BlogReaderError):
    """anti-bot 차단 감지 시 발생.

    HTTP 403/429, 캡차 페이지 감지, 비정상 응답 본문 등을 포함한다.
    REQ-009.2: 우회 시도 없이 즉시 종료.
    exit code: 4 (anti-bot 차단)
    """

    exit_code: int = 4


class UnsupportedPlatformError(BlogReaderError):
    """지원하지 않는 플랫폼(도메인)에 접근 시 발생.

    REQ-007.4: *.naver.com이 아닌 도메인에 대해 발생.
    exit code: 5 (미지원 플랫폼)
    """

    exit_code: int = 5


class BlogNotFoundError(BlogReaderError):
    """비공개 블로그 또는 삭제된 포스트 접근 시 발생.

    HTTP 404 또는 네이버 표준 "비공개 블로그입니다" 페이지 감지 시 사용.
    REQ-009.4: 명확한 에러 메시지와 함께 종료.
    exit code: 6 (비공개/삭제)
    """

    exit_code: int = 6
