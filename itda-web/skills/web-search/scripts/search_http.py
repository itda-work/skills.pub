"""web-search 공용 HTTP — urllib 기반 GET/POST JSON + 오류 분류 예외.

표준 라이브러리만 사용한다(itda-web 관행 + 배포 환경 안전 — 추가 의존성 0).
API 키는 호출자가 헤더·바디로만 전달하며, 본 모듈은 키를 URL 쿼리에 싣지 않고
예외 메시지에 키 평문을 담지 않는다(SPEC-WEB-SEARCH-001 §3.4 · REQ-006).

오류는 종료코드(SPEC §4 REQ-007)에 매핑되는 예외로 변환한다:
    인증(401/403) → AuthError(exit 4)
    쿼터(429)     → QuotaError(exit 5)
    네트워크/타임아웃 → NetworkError(exit 6)
    기타 HTTP/파싱  → EngineHTTPError/ParseError(exit 6)
    키 없음        → MissingKeyError(exit 3)
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 12
DEFAULT_RETRIES = 2
# 외부로 나가는 UA 에 우리 신원(제품·조직·저장소 URL)을 싣지 않는다 — 범용 토큰만(outbound-identity-leak).
USER_AGENT = "Mozilla/5.0"


def _env_int(name: str, default: int) -> int:
    """테스트·운영에서 타임아웃/재시도를 env 로 조정(미설정·오입력 시 default)."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


class SearchError(Exception):
    """검색 호출 실패 기반 예외. ``code``·``exit_code`` 로 종료코드 매핑."""

    code = "INTERNAL_ERROR"
    exit_code = 6


class MissingKeyError(SearchError):
    code = "MISSING_API_KEY"
    exit_code = 3


class AuthError(SearchError):
    code = "AUTH_FAILED"
    exit_code = 4


class QuotaError(SearchError):
    code = "RATE_LIMITED"
    exit_code = 5


class NetworkError(SearchError):
    code = "NETWORK_ERROR"
    exit_code = 6


class EngineHTTPError(SearchError):
    code = "ENGINE_HTTP_ERROR"
    exit_code = 6


class ParseError(SearchError):
    code = "PARSE_ERROR"
    exit_code = 6


def _backoff(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 4))


# 일부 엔진은 인증 실패를 401/403 이 아니라 422/400 + 본문 메시지로 신호한다.
# (라이브에서 확인된 패턴 — 422 + "subscription token is invalid"/"api key" 등)
_AUTH_MARKERS = (
    "subscription token",
    "invalid api key",
    "invalid token",
    "unauthorized",
    "not authorized",
    "authentication",
    "api key",
)


def _looks_like_auth(status: int, body: str) -> bool:
    if status not in (400, 422):
        return False
    low = body.lower()
    return any(marker in low for marker in _AUTH_MARKERS)


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int | None = None,
    retries: int | None = None,
    engine: str = "",
) -> Any:
    """JSON 엔드포인트를 호출하고 파싱된 객체를 반환한다.

    429·5xx·네트워크 오류는 지수 백오프로 ``retries`` 회 재시도한다. 키는
    ``headers``/``json_body`` 로만 전달한다(URL 쿼리에 싣지 않음). ``timeout``·
    ``retries`` 미지정 시 env(``WEB_SEARCH_TIMEOUT``/``WEB_SEARCH_RETRIES``) → 기본값.
    """
    if timeout is None:
        timeout = _env_int("WEB_SEARCH_TIMEOUT", DEFAULT_TIMEOUT)
    if retries is None:
        retries = _env_int("WEB_SEARCH_RETRIES", DEFAULT_RETRIES)
    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)
    headers.setdefault("Accept", "application/json")

    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params)}"

    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    label = engine or "검색 엔진"

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                body = exc.read().decode("utf-8", errors="replace")[:1000]
            except Exception:  # noqa: BLE001 - 본문 없거나 읽기 실패 시 무시
                body = ""
            if status in (401, 403) or _looks_like_auth(status, body):
                raise AuthError(
                    f"{label} 인증 실패 — API 키가 거부되었습니다(HTTP {status})."
                ) from None
            if status == 429:
                if attempt < retries:
                    _backoff(attempt)
                    continue
                raise QuotaError(f"{label} 요청 한도 초과(HTTP 429).") from None
            if 500 <= status < 600 and attempt < retries:
                _backoff(attempt)
                continue
            raise EngineHTTPError(f"{label} 오류 응답(HTTP {status}).") from None
        except (urllib.error.URLError, socket.timeout, TimeoutError):
            if attempt < retries:
                _backoff(attempt)
                continue
            raise NetworkError(f"{label} 연결 실패 — 네트워크 또는 타임아웃.") from None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ParseError(f"{label} 응답을 해석하지 못했습니다.") from None

    raise NetworkError(f"{label} 연결 실패.")
