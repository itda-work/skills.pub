"""comment_parser.py - 네이버 cbox JSONP 댓글 응답 파싱 및 트리 재구성.

REQ-BLOGREADER-004: 댓글/대댓글 트리 수집 및 구성.

- REQ-004.2: JSONP 콜백 래퍼 제거 후 JSON만 추출
- REQ-004.5: 댓글 노드 필드 정의
- REQ-004.6: children은 created_at 오름차순 정렬
- REQ-004.7: max_depth 적용 — 깊이 초과 노드 제외
- REQ-004.8: max_comments 적용 — BFS 순서로 절단
- REQ-004.10: 삭제된 댓글 body 마커 대체, 노드 유지

REQ-BLOGREADER-013: 댓글 작성자 이름 필터.

- REQ-013.1: nickname 정확 일치 (대소문자 구분)
- REQ-013.2: 매칭 노드 평탄 리스트 반환, children=[]
- REQ-013.3: created_at 오름차순 정렬
- REQ-013.4: 0건 시 빈 리스트, 예외 없음
- REQ-013.6: 삭제된 댓글도 매칭 대상
"""
from __future__ import annotations

import html as _html_module
import json
import re
from collections import deque
from typing import Any

# REQ-004.5 구현 노트 (v0.9.0): cbox contents에 <br>/<br/>/<br /> 포함 가능.
# 이를 개행 문자로 변환하고 HTML 엔티티(&amp; &lt; &gt; 등)를 디코딩한다.
# 순서: unescape 후 <br> 치환 — &lt;br&gt; 같은 이스케이프된 태그 텍스트를 보존하기 위함.
_RE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
# 잔여 HTML 태그 제거 (br 외 혹시 남은 태그) — 알려지지 않은 태그만 텍스트로 변환
_RE_HTML_TAG = re.compile(r"<[^>]+>")

# @MX:ANCHOR: [AUTO] build_comment_tree — 댓글 트리 구성 공개 API (fan_in >= 3)
# @MX:REASON: naver_adapter.get_comments, 테스트, 향후 CLI에서 호출 (REQ-004.5~004.10)

_DELETED_BODY_MARKER = "[삭제된 댓글입니다]"
# REQ-004.11: 비밀 댓글(secret=True) 마커 — deleted와 동일 정책(노드 유지, body 대체)
_SECRET_BODY_MARKER = "[비밀 댓글입니다]"
# C 결론 (v0.9.0): commentType=stk 스티커 댓글은 contents가 원래 빈 문자열.
# 추가 페치로 본문 보강 불가 (sticker 필드에 메타데이터만 존재, 텍스트 본문 없음).
# 한계: 스티커 댓글은 텍스트 body가 없는 설계이므로 [스티커] 마커를 표시한다.
_STICKER_BODY_MARKER = "[스티커]"


def _s(v: object) -> str:
    """None-safe 문자열 변환 헬퍼.

    JSON null → Python None인 필드를 str()로 변환하면 'None' 문자열이 생성된다.
    이 함수는 None을 빈 문자열로 대체하여 'None' 리터럴 노출을 방지한다.

    버그 A 수정: cbox null 필드(maskedUserName 등)가 None으로 파싱될 때
    str(None)='None' 이 되는 현상을 차단.
    """
    return "" if v is None else str(v)


def _normalize_comment_body(raw: str | None) -> str:
    """cbox contents 문자열을 정규화한다.

    REQ-004.5 구현 노트 (v0.9.0):
    1. None 안전 처리 (→ 빈 문자열)
    2. html.unescape로 HTML 엔티티 디코딩 (&amp; → &, &lt; → <, &#xNN; 등)
       순서: unescape 먼저 → <br> 치환. 이렇게 해야 &lt;br&gt; 같은
       텍스트 표현이 <br> 태그로 잘못 처리되지 않는다.
    3. <br>, <br/>, <br /> (대소문자/공백 변형 모두) → 개행 문자 \\n 치환
    4. 잔여 HTML 태그(br 외) → 텍스트만 추출(태그 제거)

    Args:
        raw: cbox contents 원시 값 (None 또는 문자열).

    Returns:
        정규화된 본문 문자열.
    """
    if raw is None:
        return ""
    text = str(raw)
    # 1단계: HTML 엔티티 디코딩 (unescape 먼저)
    text = _html_module.unescape(text)
    # 2단계: <br> 변형 → 개행
    text = _RE_BR.sub("\n", text)
    # 3단계: 잔여 HTML 태그 제거 (br 외에 다른 태그가 있으면 텍스트만 보존)
    text = _RE_HTML_TAG.sub("", text)
    return text

# JSONP 콜백 패턴: _callback_xxx(...); 또는 jQuery_xxx(...) 등
# 콜백 이름은 영문자/숫자/밑줄/달러 기호로 구성됨
# ISS-jsonpml: re.MULTILINE 제거, DOTALL 유지 — JSON 본문의 ')\n'에서 조기 절단 방지
# ISS-jsonppfx: /**/jQuery_xxx(...) 형식 허용 — Naver cbox 실측 응답은 /**/ 접두사 포함
_JSONP_CALLBACK_RE = re.compile(
    r"^\s*(?:/\*\*/\s*)?[\w$.]+\s*\(([\s\S]*)\)\s*;?\s*$",
    re.DOTALL,
)


def strip_jsonp_callback(raw: str) -> dict[str, Any]:
    """JSONP 콜백 래퍼에서 내부 JSON 페이로드를 추출한다.

    JSONP 형식: `_callback_xxx({...});` 또는 `jQuery_xxx({...})`
    공백·세미콜론·줄바꿈을 처리하고 내부 JSON만 추출 후 파싱한다.

    ISS-99e744bc 근본 수정:
    - regex 매치 성공 시 match.group(1)을 사용하여 콜백명 패턴 검증을 실효화한다.
      _JSONP_CALLBACK_RE의 콜백명 그룹(r'[\\w$.]+')이 비표준 이름을 거부하는 역할을 한다.
    - 매치 실패 시 ValueError를 raise하여 비표준 콜백명을 보수적으로 거부한다.
      이전 폴백(슬라이싱)은 `evilcb({...})` 같은 비허용 패턴도 수용했으므로 제거.

    ISS-jsonpml 호환: _JSONP_CALLBACK_RE는 re.DOTALL 플래그를 사용하므로
    멀티라인 JSON 본문도 group(1)으로 안전하게 추출된다.

    Args:
        raw: JSONP 원시 응답 문자열.

    Returns:
        파싱된 JSON 딕셔너리.

    Raises:
        ValueError: JSONP 콜백 패턴과 일치하지 않거나 JSON 파싱 실패 시.
    """
    stripped = raw.strip()
    # ISS-99e744bc: 콜백 이름 패턴 확인 — 매치 실패 시 즉시 거부 (폴백 없음)
    match = _JSONP_CALLBACK_RE.match(stripped)
    if not match:
        raise ValueError(
            f"JSONP 콜백 패턴을 찾을 수 없습니다. "
            f"입력 앞부분: {raw[:100]!r}"
        )
    # ISS-99e744bc: match.group(1)으로 추출 — regex가 콜백명 패턴을 검증한 결과만 수용.
    # _JSONP_CALLBACK_RE의 콜백명 그룹(r'[\w$.]+')이 비표준 이름을 거부하는 역할을 한다.
    # ISS-jsonpml 호환: re.DOTALL 플래그로 멀티라인 JSON도 올바르게 캡처됨.
    json_str = match.group(1)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSONP 내부 JSON 파싱 실패: {exc}"
        ) from exc


def _make_node(
    comment: dict[str, Any],
    depth: int,
    children: list[dict[str, Any]],
    *,
    effective_parent_id: str | None,
) -> dict[str, Any]:
    """cbox 응답 댓글 딕셔너리를 표준 노드 형식으로 변환한다.

    REQ-004.5: comment_id, parent_id, author, nickname, body,
               created_at, is_reply, depth, children 포함.
    REQ-004.10: deleted=true이면 body를 마커로 대체.
    REQ-004.11: secret=true이면 body를 비밀 댓글 마커로 대체 (노드 유지, deleted 우선).

    ISS-bfscycle: effective_parent_id는 build_comment_tree가 정규화한 값.
    자기참조(cid == parentCommentNo)가 None으로 변환된 결과가 전달됨.

    버그 A 수정: cbox null 필드(maskedUserName 등)를 _s()로 변환하여
    str(None)='None' 리터럴이 노드 필드에 노출되지 않도록 한다.

    Args:
        comment: cbox 댓글 딕셔너리.
        depth: 트리 깊이 (루트=0).
        children: 자식 노드 리스트.
        effective_parent_id: 정규화된 parent_id (None = 루트).

    Returns:
        표준 노드 딕셔너리.
    """
    comment_id = str(comment.get("commentNo", ""))
    parent_id: str | None = effective_parent_id

    is_deleted = bool(comment.get("deleted", False))
    # REQ-004.11: secret은 deleted보다 후순위 — deleted 우선 적용
    is_secret = bool(comment.get("secret", False))
    if is_deleted:
        body = _DELETED_BODY_MARKER
    elif is_secret:
        body = _SECRET_BODY_MARKER
    else:
        raw_contents = comment.get("contents", "")
        comment_type = _s(comment.get("commentType", ""))
        # C 결론 (v0.9.0): commentType=stk 스티커 댓글은 contents가 원래 빈 문자열.
        # 추가 HTTP 페치로 본문 보강 불가 — sticker 필드에 이미지 메타데이터만 있음.
        if comment_type == "stk" and not raw_contents:
            body = _STICKER_BODY_MARKER
        else:
            # B 수정 (v0.9.0): html.unescape 후 <br>→\n, 잔여 HTML 태그 제거
            body = _normalize_comment_body(raw_contents)

    # created_at: regTime을 ISO 8601로 그대로 사용
    created_at = _s(comment.get("regTime", ""))

    return {
        "comment_id": _s(comment.get("commentNo", "")),
        "parent_id": parent_id,
        # 버그 A 수정: _s()로 None 안전 변환 — str(None)='None' 방지
        "author": _s(comment.get("userName")),
        "nickname": _s(comment.get("maskedUserName")),
        "body": body,
        "created_at": created_at,
        "is_reply": depth > 0,
        "depth": depth,
        "children": children,
    }


def build_comment_tree(
    payload: dict[str, Any],
    *,
    max_depth: int | None = None,
    max_comments: int | None = None,
) -> dict[str, Any]:
    """cbox JSONP 응답 페이로드에서 댓글 트리를 구성한다.

    REQ-004.5: 노드 필드 정의
    REQ-004.6: children은 created_at 오름차순 정렬
    REQ-004.7: max_depth 초과 노드 제외
    REQ-004.8: max_comments 초과 시 BFS 순서로 절단
    REQ-004.10: 삭제된 댓글 본문 마커 대체, 노드 유지

    Args:
        payload: strip_jsonp_callback()이 반환한 딕셔너리.
                 {"result": {"commentList": [...], "morePage": bool}} 구조.
        max_depth: 최대 허용 깊이. None이면 무제한.
        max_comments: 최대 허용 노드 수. None이면 무제한.

    Returns:
        {"comments": [루트 노드들], "total_count": N, "truncated": bool}
    """
    result = payload.get("result", {})
    comment_list: list[dict[str, Any]] = result.get("commentList", [])

    # P2a: 페이지 상한 도달 여부 판정 (REQ-004.8, #1 회귀 수정 v0.7.2)
    # 실 cbox 응답의 morePage는 dict 커서 객체 {'prev':..., 'next':..., 'start':None, 'end':None}
    # → truthy이지만 "추가 페이지 존재"를 의미하지 않음. 완전한 1페이지에도 항상 존재함.
    # 판정 우선순위:
    #   1) pageModel이 있으면 pageModel.nextPage > 0 또는 totalPages > 1 로 판정 (실 cbox 기준)
    #   2) pageModel 없이 morePage가 literal bool True (어댑터 합성 신호) 일 때만 truncated
    #   3) morePage가 dict/truthy 객체인 경우 무시 (라이브 cbox 커서 — 페이지 완결 여부 불명)
    page_has_more: bool
    page_model = result.get("pageModel")
    if page_model is not None and isinstance(page_model, dict):
        # pageModel 기준: nextPage > 0이면 미수집 페이지 존재
        next_page = page_model.get("nextPage", 0)
        total_pages = page_model.get("totalPages", 1)
        page_has_more = bool(next_page and next_page > 0) or total_pages > 1
    else:
        # pageModel 없음: 어댑터 합성 신호만 신뢰 (literal bool True만 허용)
        raw_more = result.get("morePage", False)
        page_has_more = raw_more is True  # dict/other truthy는 무시

    # --- 1단계: 노드 ID → raw comment 매핑 ---
    raw_map: dict[str, dict[str, Any]] = {}
    for c in comment_list:
        cid = str(c.get("commentNo", ""))
        if cid:
            raw_map[cid] = c

    # --- 2단계: depth 계산 (BFS 방식으로 트리 순서 결정) ---
    # parent_id → children_ids 매핑 (순서 보존)
    # ISS-bfscycle: 자기참조(cid == parent_id) 제외로 순환의 첫 단계를 차단
    children_map: dict[str | None, list[str]] = {}
    # ISS-bfscycle: 정규화된 parent_id 기록 — _make_node에 전달하여 노드 필드도 일치시킴
    effective_parent_map: dict[str, str | None] = {}
    for c in comment_list:
        cid = str(c.get("commentNo", ""))
        parent_no = c.get("parentCommentNo")
        parent_id: str | None = str(parent_no) if parent_no is not None else None
        if cid == parent_id:
            # 자기참조 댓글 — 루트 노드로 격하
            parent_id = None
        effective_parent_map[cid] = parent_id
        children_map.setdefault(parent_id, []).append(cid)

    # 루트 노드 목록 (parent_id가 None인 것)
    root_ids = children_map.get(None, [])

    # --- 3단계: BFS로 트리 구성, max_depth 및 max_comments 적용 ---
    # (comment_id, depth) 쌍을 BFS 큐에 넣어 순회
    truncated = False
    total_count = 0

    # 완성된 노드를 저장 (comment_id → node dict)
    built_nodes: dict[str, dict[str, Any]] = {}

    # BFS: (comment_id, depth) 순서로 처리
    # 루트부터 너비 우선으로 방문하여 max_comments 적용
    queue: deque[tuple[str, int]] = deque()

    # 루트 노드를 created_at 오름차순으로 정렬하여 큐에 삽입
    sorted_root_ids = sorted(
        root_ids,
        key=lambda cid: raw_map.get(cid, {}).get("regTime", ""),
    )
    for rid in sorted_root_ids:
        queue.append((rid, 0))

    # 허용 집합: max_comments/max_depth를 통과한 노드 ID들
    allowed: set[str] = set()
    # ISS-bfscycle: visited 가드 — A→B, B→A 순환 방지
    visited: set[str] = set()

    while queue:
        cid, depth = queue.popleft()

        # ISS-bfscycle: 이미 방문한 노드 재큐잉 금지
        if cid in visited:
            continue
        visited.add(cid)

        # max_depth 초과 시 제외
        if max_depth is not None and depth > max_depth:
            truncated = True
            continue

        # max_comments 초과 시 절단
        if max_comments is not None and total_count >= max_comments:
            truncated = True
            continue

        if cid not in raw_map:
            continue

        allowed.add(cid)
        total_count += 1

        # 자식 노드를 created_at 오름차순으로 큐에 추가
        child_ids = children_map.get(cid, [])
        sorted_child_ids = sorted(
            child_ids,
            key=lambda c: raw_map.get(c, {}).get("regTime", ""),
        )
        for child_id in sorted_child_ids:
            if child_id not in visited:
                queue.append((child_id, depth + 1))

    # --- 4단계: allowed 집합 기준으로 노드 빌드 (후위 순서로) ---
    # 리프부터 빌드해야 children 리스트가 완성됨
    # → 역방향 위상 정렬: 자식을 먼저 처리
    # 간단하게: depth 내림차순으로 allowed 정렬 후 빌드

    # allowed 노드의 depth 계산
    node_depth: dict[str, int] = {}
    q2: deque[tuple[str, int]] = deque()
    for rid in sorted_root_ids:
        if rid in allowed:
            q2.append((rid, 0))
    visited2: set[str] = set()
    while q2:
        cid, depth = q2.popleft()
        if cid in visited2:
            continue
        visited2.add(cid)
        node_depth[cid] = depth
        for child_id in children_map.get(cid, []):
            if child_id in allowed and child_id not in visited2:
                q2.append((child_id, depth + 1))

    # depth 내림차순으로 정렬 → 리프 먼저 빌드
    build_order = sorted(allowed, key=lambda cid: node_depth.get(cid, 0), reverse=True)

    for cid in build_order:
        raw = raw_map[cid]
        depth = node_depth.get(cid, 0)

        # 자식 노드 중 allowed인 것만 포함, created_at 오름차순
        child_ids = children_map.get(cid, [])
        valid_children = [
            built_nodes[c]
            for c in sorted(
                child_ids,
                key=lambda c: raw_map.get(c, {}).get("regTime", ""),
            )
            if c in allowed and c in built_nodes
        ]

        built_nodes[cid] = _make_node(
            raw,
            depth,
            valid_children,
            effective_parent_id=effective_parent_map.get(cid, None),
        )

    # --- 5단계: 루트 노드 리스트 구성 ---
    root_nodes = [
        built_nodes[rid]
        for rid in sorted_root_ids
        if rid in built_nodes
    ]

    # P2a: morePage=True이면 미수집 댓글이 있음 → truncated OR 처리 (REQ-004.8)
    return {
        "comments": root_nodes,
        "total_count": total_count,
        "truncated": truncated or page_has_more,
    }


# @MX:ANCHOR: [AUTO] filter_comments_by_author — 댓글 작성자 필터 공개 API (fan_in >= 3)
# @MX:REASON: naver_adapter.get_comments, 테스트, CLI(Stage 4)에서 호출 (REQ-013)

def filter_comments_by_author(
    tree_result: dict[str, Any],
    author: str,
) -> dict[str, Any]:
    """댓글 트리에서 nickname이 author와 정확 일치하는 노드를 평탄 리스트로 반환한다.

    REQ-013.1: nickname == author 정확 일치 (대소문자 구분)
    REQ-013.2: 매칭 노드를 평탄 리스트로 반환, 각 노드의 children=[]
    REQ-013.3: created_at 오름차순 정렬
    REQ-013.4: 0건 시 빈 리스트, 예외 없음
    REQ-013.6: 삭제된 댓글도 nickname 매칭 대상

    Args:
        tree_result: build_comment_tree()의 반환값.
                     {"comments": [...트리 노드들...], "total_count": N, "truncated": bool}
        author: 필터할 nickname (정확 일치, 대소문자 구분).

    Returns:
        {"comments": [평탄 리스트], "total_count": M, "truncated": False}
        - total_count: 필터 후 매칭 노드 수
        - truncated: 항상 False (필터링은 잘라내기가 아님)
    """
    matched: list[dict[str, Any]] = []

    # ISS-3ae5e8ad 근본 수정: 재귀 → 명시적 스택 기반 반복 순회.
    # 깊이 2000 이상의 합성 트리에서 RecursionError 없이 처리된다.
    # 평탄화 순서는 DFS(전위) 방식으로 기존과 동일하게 유지된다.
    # ISS-filterauthor: author(userName) 또는 nickname(maskedUserName) 중 하나와 일치 시 포함.
    # 실측 cbox: userName = 실명, maskedUserName = 부분 마스킹 — 합성 fixture는 반대 패턴 가능.
    stack: list[dict[str, Any]] = list(reversed(tree_result.get("comments", [])))
    while stack:
        node = stack.pop()
        if node.get("author") == author or node.get("nickname") == author:
            # REQ-013.2: 매칭 노드는 children=[]로 정규화
            matched.append({**node, "children": []})
        # 자식 노드도 순회 (부모 매칭 여부와 무관하게) — 역순으로 push하여 순서 보존
        children = node.get("children", [])
        for child in reversed(children):
            stack.append(child)

    # REQ-013.3: created_at 오름차순 정렬
    matched.sort(key=lambda n: n.get("created_at", ""))

    return {
        "comments": matched,
        "total_count": len(matched),
        "truncated": False,
    }
