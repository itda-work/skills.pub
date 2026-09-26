"""tag_parser.py - 네이버 블로그 태그 API(BlogTagListInfo.naver) 응답 파서.

REQ-BLOGREADER-003.x: 포스트 태그 추출.

실측 2026-05-18 (v0.9.3): 태그는 포스트 본문 HTML(모바일/PC)에 존재하지
않고, 별도 API로만 제공된다 (댓글 cbox API와 동형 구조).

- 엔드포인트: https://blog.naver.com/BlogTagListInfo.naver?blogId={id}&logNo={logNo}
- 응답: {"taglist":[{"msg":"","logno":"<logNo>",
          "tagName":"<UTF-8 percent-encoded, %2C(,) 구분>",
          "encTagName":"<EUC-KR legacy 인코딩 — 미사용>"}]}
- tagName 디코딩: urllib.parse.unquote → ',' split

이전(~v0.9.2) post_parser.py의 `class="post_tag"` 본문 스크래핑은
실제 마크업에 해당 클래스가 없어 항상 빈 리스트를 반환하던 죽은 경로였다.
"""
from __future__ import annotations

import json
import re
from urllib.parse import unquote

# 방어적 JSON 본문 추출: 응답 앞뒤 공백/노이즈 또는 JSONP 래핑 대비.
# 댓글 strip_jsonp_callback과 동형 — 첫 '{' 부터 마지막 '}' 까지.
_RE_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_tag_list_json(raw: str, log_no: str) -> list[str]:
    """BlogTagListInfo.naver 응답에서 해당 logNo의 태그 리스트를 추출한다.

    Args:
        raw: API 응답 원문 (JSON 문자열, 앞뒤 노이즈 허용).
        log_no: 대상 포스트 번호. taglist 항목의 logno와 매칭한다.

    Returns:
        태그 문자열 리스트 (입력 순서 보존, 중복·빈값 제거).
        파싱 실패·빈 응답·매칭 항목 없음 → 빈 리스트 (graceful, 예외 없음).
    """
    if not raw:
        return []

    match = _RE_JSON_OBJECT.search(raw)
    if not match:
        return []

    try:
        payload = json.loads(match.group(0))
    except (ValueError, TypeError):
        return []

    tag_list = payload.get("taglist")
    if not isinstance(tag_list, list):
        return []

    target = str(log_no)
    enc_tag_name: str | None = None
    for item in tag_list:
        if not isinstance(item, dict):
            continue
        if str(item.get("logno", "")) == target:
            enc_tag_name = item.get("tagName")
            break

    if enc_tag_name is None:
        return []

    decoded = unquote(enc_tag_name)
    result: list[str] = []
    seen: set[str] = set()
    for token in decoded.split(","):
        tag = token.strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result
