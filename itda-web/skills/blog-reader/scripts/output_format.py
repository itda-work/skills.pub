"""output_format.py - JSON / Markdown 출력 포맷터.

REQ-BLOGREADER-008: 출력 포맷 (json|markdown)
  - REQ-008.2: JSON — pretty-print 2칸, ensure_ascii=False, UTF-8
  - REQ-008.3: Markdown — list/post/comments/search/read 형식
  - REQ-008.4: --output 경로 지정 시 파일 기록 (itda_path 기준)

Stage 4: output_format.py 신규 작성
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# JSON 포맷터
# ---------------------------------------------------------------------------

def format_json(
    data: "dict[str, Any] | list[Any]",
    output_path: "str | None" = None,
) -> str:
    """데이터를 pretty-print JSON 문자열로 변환한다.

    REQ-008.2: 들여쓰기 2칸, ensure_ascii=False, UTF-8 인코딩.
    REQ-008.4: output_path 지정 시 itda_path.resolve_data_dir 기준으로 파일 기록.

    Args:
        data: 직렬화할 dict 또는 list.
        output_path: 저장할 파일 경로 (선택). itda_path.resolve_data_dir("blog-reader") 기준 상대 경로.

    Returns:
        pretty-print JSON 문자열.
    """
    result = json.dumps(data, ensure_ascii=False, indent=2)

    if output_path is not None:
        _write_output(result, output_path)

    return result


# ---------------------------------------------------------------------------
# Markdown 포맷터 — list / search 공통 테이블
# ---------------------------------------------------------------------------

def format_markdown_list(posts: "list[dict[str, Any]]") -> str:
    """포스트 목록을 마크다운 테이블로 변환한다.

    REQ-008.3: list 결과 — 포스트 제목·URL·작성일·요약 테이블.
    AC-12: | logNo | title | published_at | category | 헤더.

    Args:
        posts: 포스트 딕셔너리 리스트 (logNo, title, url, published_at, category, summary 포함).

    Returns:
        마크다운 테이블 문자열.
    """
    lines: list[str] = [
        "| logNo | title | published_at | category |",
        "| --- | --- | --- | --- |",
    ]
    for post in posts:
        log_no = _escape_md(str(post.get("logNo", "")))
        title = _escape_md(str(post.get("title", "")))
        url = str(post.get("url", ""))
        pub = _escape_md(str(post.get("published_at", "")))
        category = _escape_md(str(post.get("category", "")))
        # 제목에 URL 링크 삽입
        title_cell = f"[{title}]({url})" if url else title
        lines.append(f"| {log_no} | {title_cell} | {pub} | {category} |")
    return "\n".join(lines)


def format_markdown_search(posts: "list[dict[str, Any]]") -> str:
    """검색 결과를 마크다운 테이블로 변환한다.

    REQ-008.3: search 결과는 list와 동일한 테이블 형식.

    Args:
        posts: 검색 결과 포스트 딕셔너리 리스트.

    Returns:
        마크다운 테이블 문자열.
    """
    return format_markdown_list(posts)


def format_markdown_discover(result: "dict[str, Any]") -> str:
    """전역 검색(discover) 결과를 마크다운 테이블로 변환한다 (REQ-015, #1334).

    Args:
        result: {"posts": [...], "total_count": N} 딕셔너리.
                posts 항목은 blog_id, log_no, title, url, published_at,
                blog_name, summary 포함.

    Returns:
        마크다운 테이블 문자열 (전체 건수 헤더 포함).
    """
    posts = result.get("posts", [])
    total = result.get("total_count", 0)
    lines: list[str] = [
        f"전체 {total}건 중 {len(posts)}건",
        "",
        "| blogId | title | published_at | blogName |",
        "| --- | --- | --- | --- |",
    ]
    for post in posts:
        blog_id = _escape_md(str(post.get("blog_id", "")))
        title = _escape_md(str(post.get("title", "")))
        url = str(post.get("url", ""))
        pub = _escape_md(str(post.get("published_at", "")))
        blog_name = _escape_md(str(post.get("blog_name", "")))
        title_cell = f"[{title}]({url})" if url else title
        lines.append(f"| {blog_id} | {title_cell} | {pub} | {blog_name} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown 포맷터 — post 본문
# ---------------------------------------------------------------------------

def format_markdown_post(article: "dict[str, Any]") -> str:
    """포스트 본문을 마크다운 문서로 변환한다.

    REQ-008.3: H1(제목) + 메타(작성자/카테고리/태그) + 본문.
    REQ-003.1/.2: body 단일 키 사용 (v0.7.0 BREAKING).
    설계 결정 (v0.7.0): body 키는 body_format에 따라 마크다운 또는 HTML.
    설계 결정 (v0.5.3): published_at은 post detail 메타에서 제거.
    발행시각은 list/search 결과에서만 표시된다.

    Args:
        article: get_post 반환 딕셔너리.
                 body 키에 본문 (markdown 기본, html 가능).
                 images 키에 이미지 목록 (body가 HTML일 때만 별도 섹션 표시).

    Returns:
        마크다운 문서 문자열.
    """
    title = article.get("title", "")
    author = article.get("author", "")
    category = article.get("category", "")
    tags: "list[str]" = article.get("tags", [])
    body: str = article.get("body", "")
    images: "list[dict[str, Any]]" = article.get("images", [])

    lines: list[str] = []

    # H1 제목
    lines.append(f"# {title}")
    lines.append("")

    # 메타 라인 (작성자·카테고리만 — 발행시각은 list/search 경로 전용)
    meta_parts = []
    if author:
        meta_parts.append(f"작성자: {author}")
    if category:
        meta_parts.append(category)
    if meta_parts:
        lines.append(f"*{' | '.join(meta_parts)}*")
        lines.append("")

    # 태그
    if tags:
        tag_str = " ".join(f"`{t}`" for t in tags)
        lines.append(f"태그: {tag_str}")
        lines.append("")

    # REQ-003.1/.2: body 단일 키 — markdown(기본) 또는 html 그대로 출력
    if body:
        lines.append(body)
        lines.append("")

    # 이미지 리스트 — body가 HTML(마크다운 이미지 미포함)일 때 별도 섹션
    # body_format이 html이면 images 리스트를 별도 표시; markdown이면 본문 inline 포함
    # HTML 여부는 body 내용의 "<" 태그 포함 여부로 간이 판별
    body_is_html = body.lstrip().startswith("<")
    if images and body_is_html:
        lines.append("## 이미지")
        lines.append("")
        for img in images:
            img_url = img.get("url", "")
            alt = img.get("alt", "")
            lines.append(f"- ![{alt}]({img_url})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown 포맷터 — comments 트리
# ---------------------------------------------------------------------------

def format_markdown_comments(comments_result: "dict[str, Any]") -> str:
    """댓글 트리를 들여쓰기 기반 중첩 리스트로 변환한다.

    REQ-008.3: 들여쓰기 기반 중첩 리스트.
    filter_author 결과(children=[] 평탄 리스트)도 처리한다.

    Args:
        comments_result: get_comments 반환 딕셔너리.
            {"comments": [...], "total_count": N, ...}

    Returns:
        마크다운 중첩 리스트 문자열.
    """
    root_comments: "list[dict[str, Any]]" = comments_result.get("comments", [])
    lines: list[str] = []
    _render_comment_nodes(root_comments, depth=0, lines=lines)
    return "\n".join(lines) if lines else "*(댓글 없음)*"


def _render_comment_nodes(
    nodes: "list[dict[str, Any]]",
    depth: int,
    lines: "list[str]",
) -> None:
    """댓글 노드를 마크다운 리스트로 렌더링한다.

    ISS-3ae5e8ad 근본 수정: 재귀 → 명시적 스택 기반 반복으로 전환.
    깊이 2000 이상의 합성 트리에서 RecursionError 없이 처리된다.
    들여쓰기 순서는 DFS(전위) 방식으로 기존과 동일하게 유지된다.
    """
    # 스택 항목: (node, depth) 쌍. 역순 push로 원래 순서 보존.
    stack: list[tuple[dict[str, Any], int]] = [
        (node, depth) for node in reversed(nodes)
    ]
    while stack:
        node, cur_depth = stack.pop()
        indent = "  " * cur_depth
        # REQ-004.11 표시 폴백: author/nickname 모두 빈 값(비밀 댓글)이면 익명 라벨 표시.
        # 가짜 실명 생성 금지 — "(작성자 비공개)"는 명시적 익명 라벨이다.
        _display_name = node.get("author") or node.get("nickname") or "(작성자 비공개)"
        body = node.get("body", "")
        created_at = node.get("created_at", "")
        meta = f"{_display_name}"
        if created_at:
            meta += f" ({created_at})"
        lines.append(f"{indent}- **{meta}**: {body}")
        children = node.get("children", [])
        for child in reversed(children):
            stack.append((child, cur_depth + 1))


# ---------------------------------------------------------------------------
# Markdown 포맷터 — read (article + comments 통합)
# ---------------------------------------------------------------------------

def format_markdown_read(read_result: "dict[str, Any]") -> str:
    """통합 조회 결과를 단일 마크다운 문서로 변환한다.

    REQ-014.8: (a) H1 제목 + 메타 + 본문 + 이미지 (post와 동일) 다음에
               (b) ## 댓글 헤더 + 들여쓰기 트리 순서.

    Args:
        read_result: read_post 반환 딕셔너리 {"article": {...}, "comments": {...}}.

    Returns:
        통합 마크다운 문서 문자열.
    """
    article = read_result.get("article", {})
    comments_result = read_result.get("comments", {})

    article_md = format_markdown_post(article)
    comments_md = format_markdown_comments(comments_result)

    return f"{article_md}\n\n## 댓글\n\n{comments_md}"


# ---------------------------------------------------------------------------
# 파일 출력 헬퍼
# ---------------------------------------------------------------------------

def _write_output(content: str, output_path: str) -> None:
    """content를 output_path에 기록한다.

    REQ-008.4: itda_path.resolve_data_dir("blog-reader") 기준 상대 경로.
    ISS-efc8e91c: 절대 경로도 항상 resolve_data_dir 기준으로 재결합.
    '..' 경로 탈출 시도는 ValueError 발생.

    Args:
        content: 기록할 문자열.
        output_path: 파일 경로 (data_dir 기준 상대 또는 파일명).
                     절대 경로는 basename만 추출하여 data_dir 안에 기록.

    Raises:
        ValueError: output_path가 data_dir 경계를 탈출하려 할 때.
    """
    try:
        from itda_path import resolve_data_dir
        base = Path(resolve_data_dir("blog-reader"))
    except ImportError:
        # itda_path가 없는 테스트 환경 등: CWD 기준
        base = Path.cwd()

    input_path = Path(output_path)

    # ISS-efc8e91c: 절대 경로인 경우 basename만 취해 data_dir 안에 기록
    if input_path.is_absolute():
        safe_name = input_path.name
    else:
        safe_name = output_path

    # resolve_data_dir 기준으로 경로 결합
    resolved = (base / safe_name).resolve()

    # '..' 탈출 방지: resolved 경로가 base 하위인지 확인
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        raise ValueError(
            f"output_path가 데이터 디렉토리 경계를 벗어납니다: {output_path!r}"
        )

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def _escape_md(text: str) -> str:
    """마크다운 테이블 셀 안에서 파이프 문자를 이스케이프한다."""
    return text.replace("|", "\\|").replace("\n", " ")
