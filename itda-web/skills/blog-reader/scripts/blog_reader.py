"""blog_reader.py - blog-reader CLI 엔트리포인트.

REQ-BLOGREADER-010: 5개 서브커맨드 (list/post/comments/search/read)
REQ-BLOGREADER-008: --format json|markdown 출력 포맷
REQ-BLOGREADER-009: exit code 매핑
REQ-BLOGREADER-014: read 서브커맨드 (본문 + 댓글 통합)

# @MX:NOTE: [AUTO] main() — CLI 단일 진입점 (REQ-010.1)
# SPEC-COLLECTOR-CLI-001 패턴: argparse parents=[common_parser]로 인자 위치 자유화.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, NoReturn

from errors import (
    AntiBotBlockError,
    BlogNotFoundError,
    BlogReaderError,
    EmptyResultError,
    UnsupportedPlatformError,
)
from naver_adapter import NaverBlogAdapter
from output_format import (
    format_json,
    format_markdown_comments,
    format_markdown_discover,
    format_markdown_list,
    format_markdown_post,
    format_markdown_read,
    format_markdown_search,
)
from url_normalize import normalize_naver_blog_url

# ---------------------------------------------------------------------------
# exit code 상수 (REQ-009.1)
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_GENERAL_ERROR = 1
EXIT_ARG_ERROR = 2
EXIT_EMPTY = 3
EXIT_ANTIBOT = 4
EXIT_UNSUPPORTED = 5
EXIT_NOT_FOUND = 6

_ANTIBOT_STDERR_MSG = "anti-bot 차단 감지 — 우회 시도하지 않음"

# ISS-deadcode: _EXIT_CODE_MAP 제거 — exit code 매핑은 exc.exit_code 경로로 처리


# ---------------------------------------------------------------------------
# 공통 parent parser 생성 (REQ-010.2, REQ-010.3)
# ---------------------------------------------------------------------------

def _make_common_parser(use_suppress: bool = False) -> argparse.ArgumentParser:
    """공통 옵션 parent parser를 반환한다.

    SPEC-COLLECTOR-CLI-001 패턴: add_help=False로 생성해야
    서브커맨드의 parents=[common] 에서 --help 충돌이 없다.

    ISS-e3551b8f / AC-16 근본 수정:
    subparser에서 parents=[common]을 사용할 때, subparser의 default=None이
    root에서 파싱된 값을 덮어쓰는 문제가 있다.
    use_suppress=True이면 모든 공통 옵션의 default를 argparse.SUPPRESS로 설정해
    미지정 시 root 파서에서 설정된 값이 보존된다.
    """
    _SUPPRESS = argparse.SUPPRESS
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "--format",
        choices=["json", "markdown"],
        default=_SUPPRESS if use_suppress else "json",
        help="출력 포맷 (json|markdown). 기본값: json",
    )
    p.add_argument(
        "--output",
        default=_SUPPRESS if use_suppress else None,
        metavar="경로",
        help="결과를 파일로 저장할 경로 (itda_path 기준 상대 경로)",
    )
    p.add_argument(
        "--user-agent",
        default=_SUPPRESS if use_suppress else None,
        metavar="UA",
        help="HTTP 요청에 사용할 User-Agent 문자열",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=_SUPPRESS if use_suppress else None,
        metavar="초",
        help="HTTP 요청 타임아웃 (초 단위)",
    )
    p.add_argument(
        "--throttle",
        type=float,
        default=_SUPPRESS if use_suppress else 0.5,
        metavar="초",
        help="연속 요청 사이 최소 지연 (초, 기본 0.5, 하한 0.3). 0 이하 지정 시 오류.",
    )
    return p


# ---------------------------------------------------------------------------
# 메인 parser + 서브커맨드 구성
# ---------------------------------------------------------------------------

def _build_parser(common: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """argparse 루트 parser를 구성한다.

    REQ-010.3: parents=[common]으로 공통 옵션이 서브커맨드 앞·뒤 어디에 와도 동작.
    REQ-010.4: --help 출력 한국어.

    ISS-e3551b8f / AC-16 근본 수정:
    subparser도 parents=[common]을 사용하지만 use_suppress=True인 별도 parent를 사용.
    SUPPRESS된 옵션은 subparser에서 미지정 시 Namespace에 추가되지 않아
    root에서 파싱된 값이 보존된다.
    """
    # subparser 전용 parent — SUPPRESS로 root 파싱 결과를 보호
    common_sup = _make_common_parser(use_suppress=True)

    root = argparse.ArgumentParser(
        prog="blog_reader",
        description="네이버 블로그 조회 CLI (읽기 전용)",
        parents=[common],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = root.add_subparsers(dest="subcommand", metavar="서브커맨드")

    # ---- list ----
    p_list = sub.add_parser(
        "list",
        parents=[common_sup],
        help="포스트 목록 조회",
        description="블로그 포스트 목록을 날짜 내림차순으로 조회합니다.",
    )
    p_list.add_argument("--blog-id", required=True, metavar="ID", help="네이버 블로그 ID")
    p_list.add_argument("--days", type=int, default=None, metavar="N", help="최근 N일 이내 포스트만 반환")
    p_list.add_argument("--limit", type=int, default=20, metavar="N", help="최대 반환 수 (기본: 20)")
    p_list.add_argument("--category", default=None, metavar="이름", help="카테고리명 필터")

    # ---- post ----
    p_post = sub.add_parser(
        "post",
        parents=[common_sup],
        help="포스트 본문 조회",
        description="포스트 본문을 구조화된 형태로 조회합니다.",
    )
    _add_url_or_blogid_logno(p_post)
    p_post.add_argument(
        "--body-format",
        choices=["markdown", "html"],
        default="markdown",
        dest="body_format",
        help="본문 형식 (markdown|html). 기본값: markdown",
    )
    _add_no_image_urls_option(p_post)

    # ---- comments ----
    p_comments = sub.add_parser(
        "comments",
        parents=[common_sup],
        help="댓글/대댓글 트리 조회",
        description="포스트의 댓글과 대댓글을 트리 구조로 조회합니다.",
    )
    _add_url_or_blogid_logno(p_comments)
    _add_comment_options(p_comments)

    # ---- search ----
    p_search = sub.add_parser(
        "search",
        parents=[common_sup],
        help="블로그 내 검색",
        description="블로그 안에서 키워드 검색을 수행합니다.",
    )
    p_search.add_argument("--blog-id", required=True, metavar="ID", help="검색 대상 블로그 ID")
    p_search.add_argument("--query", required=True, metavar="키워드", help="검색 키워드")
    p_search.add_argument("--limit", type=int, default=20, metavar="N", help="최대 반환 수 (기본: 20)")

    # ---- discover ----
    p_discover = sub.add_parser(
        "discover",
        parents=[common_sup],
        help="네이버 블로그 전역 키워드 검색 (메타데이터만, #1334)",
        description=(
            "네이버 블로그 전체에서 키워드로 포스트를 검색해 "
            "제목·요약·URL 메타데이터만 반환합니다. 본문은 read로 이어읽습니다."
        ),
    )
    p_discover.add_argument("--query", required=True, metavar="키워드", help="검색 키워드")
    p_discover.add_argument("--limit", type=int, default=20, metavar="N", help="최대 반환 수 (기본: 20)")
    p_discover.add_argument(
        "--order",
        choices=["sim", "date"],
        default="sim",
        help="정렬 (sim=관련도순, date=최신순). 기본값: sim",
    )

    # ---- read ----
    p_read = sub.add_parser(
        "read",
        parents=[common_sup],
        help="포스트 본문 + 댓글 통합 조회 (REQ-014)",
        description="포스트 본문과 댓글 트리를 한 번에 조회합니다.",
    )
    _add_url_or_blogid_logno(p_read)
    _add_comment_options(p_read)
    p_read.add_argument(
        "--body-format",
        choices=["markdown", "html"],
        default="markdown",
        dest="body_format",
        help="본문 형식 (markdown|html). 기본값: markdown",
    )
    _add_no_image_urls_option(p_read)

    return root


def _add_no_image_urls_option(parser: argparse.ArgumentParser) -> None:
    """--no-image-urls 옵션을 추가한다 (REQ-003.9, v0.11.0).

    토큰 절감용. 기본 OFF (이미지 URL 포함, 하위 호환). 켜지면 본문
    이미지는 [이미지: alt] 플레이스홀더로 치환되고 images 배열은 빈다.
    """
    parser.add_argument(
        "--no-image-urls",
        action="store_true",
        dest="no_image_urls",
        help="본문 이미지 URL을 [이미지: alt] 플레이스홀더로 치환하고 "
        "images 배열을 비웁니다 (토큰 절감, 기본 OFF)",
    )


def _add_url_or_blogid_logno(parser: argparse.ArgumentParser) -> None:
    """--url 또는 --blog-id + --log-no 옵션 그룹을 추가한다."""
    grp = parser.add_mutually_exclusive_group(required=False)
    grp.add_argument("--url", default=None, metavar="URL", help="포스트 URL (PC/모바일 모두 허용)")
    # --blog-id + --log-no 는 개별 옵션으로 추가 (상호 배타 그룹 밖)
    parser.add_argument("--blog-id", default=None, metavar="ID", help="블로그 ID")
    parser.add_argument("--log-no", default=None, metavar="번호", help="포스트 번호 (logNo)")


def _add_comment_options(parser: argparse.ArgumentParser) -> None:
    """댓글 관련 공통 옵션을 추가한다."""
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="댓글 최대 깊이 (기본: 무제한)",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=None,
        metavar="N",
        help="최대 댓글 수 (기본: 무제한)",
    )
    parser.add_argument(
        "--filter-author",
        default=None,
        metavar="닉네임",
        help="댓글 작성자 닉네임 필터 (정확 일치)",
    )


# ---------------------------------------------------------------------------
# URL 또는 blog_id + log_no → URL 변환
# ---------------------------------------------------------------------------

def _resolve_url(args: argparse.Namespace) -> str:
    """args에서 모바일 URL을 결정한다.

    --url 또는 (--blog-id + --log-no) 중 하나가 반드시 있어야 한다.
    둘 다 없으면 _exit_arg_error()를 호출(NoReturn)한다.

    ISS-resolveurl: 모든 경로가 str 반환 또는 NoReturn임을 명확히.

    Args:
        args: 파싱된 argparse.Namespace.

    Returns:
        정규화된 모바일 URL.

    Raises:
        SystemExit(EXIT_ARG_ERROR): URL/blog_id 모두 없을 때.
    """
    url = getattr(args, "url", None)
    blog_id = getattr(args, "blog_id", None)
    log_no = getattr(args, "log_no", None)

    # ISS-7b965c91 근본 수정: --url과 --blog-id + --log-no 동시 지정 시 명시적 exit 2.
    # argparse의 mutually_exclusive_group은 단일 인자 단위라 이 조합을 자동으로 막지 못한다.
    if url and (blog_id or log_no):
        _exit_arg_error(
            "--url과 --blog-id / --log-no는 함께 사용할 수 없습니다. "
            "둘 중 하나만 지정하세요."
        )

    if url:
        return normalize_naver_blog_url(url)
    if blog_id and log_no:
        return normalize_naver_blog_url(
            f"https://m.blog.naver.com/{blog_id}/{log_no}"
        )
    # ISS-resolveurl: _exit_arg_error는 NoReturn — 이 경로는 반환하지 않음
    _exit_arg_error("--url 또는 --blog-id + --log-no 중 하나를 지정해야 합니다.")


def _exit_arg_error(msg: str) -> NoReturn:
    """인자 오류를 stderr에 출력하고 exit 2로 종료한다."""
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(EXIT_ARG_ERROR)


# ---------------------------------------------------------------------------
# 출력 처리
# ---------------------------------------------------------------------------

def _output(
    data: "dict[str, Any] | list[Any]",
    fmt: str,
    formatter_fn: "Any",
    output_path: "str | None",
) -> None:
    """데이터를 지정한 포맷으로 stdout 또는 파일에 출력한다."""
    if fmt == "json":
        text = format_json(data, output_path)
    else:
        text = formatter_fn(data)
        if output_path is not None:
            _write_output_file(text, output_path)

    if output_path is None:
        print(text)


def _write_output_file(content: str, output_path: str) -> None:
    """content를 output_path에 기록한다 (output_format._write_output 래퍼)."""
    from output_format import _write_output
    _write_output(content, output_path)


# ---------------------------------------------------------------------------
# 서브커맨드 핸들러
# ---------------------------------------------------------------------------

def _handle_list(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    blog_id = getattr(args, "blog_id", None)
    if not blog_id:
        _exit_arg_error("list 서브커맨드에 --blog-id가 필요합니다.")

    # P3: --limit / --days 양수 검증 (REQ-010)
    if args.limit is not None and args.limit <= 0:
        _exit_arg_error(f"--limit은 1 이상이어야 합니다 (입력값: {args.limit}).")
    if args.days is not None and args.days <= 0:
        _exit_arg_error(f"--days는 1 이상이어야 합니다 (입력값: {args.days}).")

    filters: "dict[str, Any]" = {
        "blog_id": blog_id,
        "limit": args.limit,
    }
    if args.days is not None:
        filters["days"] = args.days
    if args.category:
        filters["category"] = args.category

    posts = adapter.list_posts(filters)
    _output(
        posts,
        args.format,
        format_markdown_list,
        args.output,
    )
    return EXIT_OK


def _handle_post(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    url = _resolve_url(args)
    # REQ-003.1/.2: --body-format로 본문 형식 결정 (기본: markdown)
    body_format: str = getattr(args, "body_format", "markdown")
    # REQ-003.9 (v0.11.0): --no-image-urls 토큰 절감 옵션
    strip_image_urls: bool = getattr(args, "no_image_urls", False)
    article = adapter.get_post(
        url, body_format=body_format, strip_image_urls=strip_image_urls
    )
    _output(
        article,
        args.format,
        format_markdown_post,
        args.output,
    )
    return EXIT_OK


def _handle_comments(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    url = _resolve_url(args)
    options: "dict[str, Any]" = {}
    if args.max_depth is not None:
        options["max_depth"] = args.max_depth
    if args.max_comments is not None:
        options["max_comments"] = args.max_comments
    if args.filter_author:
        options["filter_author"] = args.filter_author

    result = adapter.get_comments(url, options)

    # P1: comments 단독 명령에서 오류가 있으면 exit != 0 (REQ-009 정합).
    # get_comments는 dict+error 키로 graceful 반환함(read 서브커맨드가 의존).
    # 단독 comments 명령에서는 error 키가 있으면 stderr 출력 + EXIT_GENERAL_ERROR.
    # 정상 0건(error 키 없음)은 exit 0 유지.
    error_msg = result.get("error") if isinstance(result, dict) else None
    if error_msg:
        print(f"오류: {error_msg}", file=sys.stderr)
        return EXIT_GENERAL_ERROR

    _output(
        result,
        args.format,
        format_markdown_comments,
        args.output,
    )
    return EXIT_OK


def _handle_search(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    blog_id = getattr(args, "blog_id", None)
    if not blog_id:
        _exit_arg_error("search 서브커맨드에 --blog-id가 필요합니다.")
    query = getattr(args, "query", None)
    if not query:
        _exit_arg_error("search 서브커맨드에 --query가 필요합니다.")

    # P3: --limit 양수 검증 (REQ-010)
    if args.limit is not None and args.limit <= 0:
        _exit_arg_error(f"--limit은 1 이상이어야 합니다 (입력값: {args.limit}).")

    options: "dict[str, Any]" = {
        "blog_id": blog_id,
        "limit": args.limit,
    }
    posts = adapter.search(query, options)
    _output(
        posts,
        args.format,
        format_markdown_search,
        args.output,
    )
    return EXIT_OK


def _handle_discover(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    query = getattr(args, "query", None)
    if not query:
        _exit_arg_error("discover 서브커맨드에 --query가 필요합니다.")

    if args.limit is not None and args.limit <= 0:
        _exit_arg_error(f"--limit은 1 이상이어야 합니다 (입력값: {args.limit}).")

    options: "dict[str, Any]" = {
        "limit": args.limit,
        "order_by": getattr(args, "order", "sim"),
    }
    result = adapter.discover(query, options)
    _output(
        result,
        args.format,
        format_markdown_discover,
        args.output,
    )
    return EXIT_OK


def _handle_read(args: argparse.Namespace, adapter: NaverBlogAdapter) -> int:
    url = _resolve_url(args)
    options: "dict[str, Any]" = {}
    if getattr(args, "max_depth", None) is not None:
        options["max_depth"] = args.max_depth
    if getattr(args, "max_comments", None) is not None:
        options["max_comments"] = args.max_comments
    if getattr(args, "filter_author", None):
        options["filter_author"] = args.filter_author
    # REQ-003.1/.2: --body-format로 본문 형식 결정 (기본: markdown)
    options["body_format"] = getattr(args, "body_format", "markdown")
    # REQ-003.9 (v0.11.0): --no-image-urls 토큰 절감 옵션
    options["strip_image_urls"] = getattr(args, "no_image_urls", False)

    result = adapter.read_post(url, options)
    _output(
        result,
        args.format,
        format_markdown_read,
        args.output,
    )
    return EXIT_OK


_SUBCOMMAND_HANDLERS = {
    "list": _handle_list,
    "post": _handle_post,
    "comments": _handle_comments,
    "search": _handle_search,
    "discover": _handle_discover,
    "read": _handle_read,
}


# ---------------------------------------------------------------------------
# 메인 함수
# ---------------------------------------------------------------------------

# @MX:ANCHOR: [AUTO] main — CLI 단일 진입점
# @MX:REASON: blog_reader.py의 공개 진입점, 모든 서브커맨드가 여기를 통해 실행됨 (fan_in >= 3)
def main(argv: "list[str] | None" = None) -> int:
    """CLI 진입점.

    REQ-010.1: python3 scripts/blog_reader.py {subcommand} [options] 형태로 호출.
    REQ-009.1: 예외 타입 → exit code 매핑.
    REQ-009.2: AntiBotBlockError → stderr에 차단 메시지 출력 후 exit 4.

    Args:
        argv: CLI 인자 리스트. None이면 sys.argv[1:] 사용.

    Returns:
        exit code (int).
    """
    if argv is None:
        argv = sys.argv[1:]

    common = _make_common_parser()
    parser = _build_parser(common)

    # 인자 없이 호출 시 도움말 출력
    if not argv:
        parser.print_help()
        return EXIT_ARG_ERROR

    # REQ-010.3: argparse parents 패턴으로 위치 자유화
    # 파싱 실패는 exit 2
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_ARG_ERROR
        return code

    subcommand = getattr(args, "subcommand", None)
    if subcommand is None:
        parser.print_help()
        return EXIT_ARG_ERROR

    handler = _SUBCOMMAND_HANDLERS.get(subcommand)
    if handler is None:
        parser.print_help()
        return EXIT_ARG_ERROR

    # ISS-e3551b8f: --user-agent / --timeout 공통 옵션 배선
    # SPEC R-3: --throttle 검증 및 배선
    adapter_options: "dict[str, Any]" = {}
    if getattr(args, "user_agent", None):
        adapter_options["user_agent"] = args.user_agent
    if getattr(args, "timeout", None) is not None:
        adapter_options["timeout"] = args.timeout

    # --throttle 검증: 0 이하 → 인자 오류(exit 2), 하한 클램프는 어댑터에서 수행
    throttle_val: float = getattr(args, "throttle", 0.5)
    if throttle_val <= 0:
        _exit_arg_error(
            f"--throttle은 0보다 커야 합니다 (interval 없이 요청 금지). "
            f"입력값: {throttle_val}"
        )
    # 하한(0.3) 미만이면 경고 후 어댑터에서 클램프 (stderr 경고)
    from naver_adapter import _THROTTLE_FLOOR as _FLOOR
    if 0 < throttle_val < _FLOOR:
        import sys as _sys
        print(
            f"경고: --throttle {throttle_val}s는 하한 {_FLOOR}s로 조정됩니다.",
            file=_sys.stderr,
        )
    adapter_options["throttle"] = throttle_val
    adapter = NaverBlogAdapter(options=adapter_options if adapter_options else None)

    try:
        return handler(args, adapter)

    except AntiBotBlockError as exc:
        # REQ-009.2: anti-bot 차단 감지 — stderr에 메시지 출력
        print(_ANTIBOT_STDERR_MSG, file=sys.stderr)
        if str(exc):
            print(str(exc), file=sys.stderr)
        return EXIT_ANTIBOT

    except UnsupportedPlatformError as exc:
        print(f"UnsupportedPlatformError: {exc}", file=sys.stderr)
        return EXIT_UNSUPPORTED

    except BlogNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NOT_FOUND

    except EmptyResultError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_EMPTY

    except BlogReaderError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return exc.exit_code

    except Exception as exc:  # noqa: BLE001
        print(f"예상치 못한 오류: {exc}", file=sys.stderr)
        return EXIT_GENERAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
