"""itda-hyve 가 저장한 입력 파일 판독 — 네트워크 없음.

요청은 itda-hyve 의 ``http_request`` 가 보내고 ``save_as`` 로 파일에 저장한다(itda-work/skills#45,
규칙 ``cowork-network-via-hyve``). 스킬 스크립트는 그 파일을 ``--input`` 으로 받는다. 이 모듈은
**hyve 층만** 판독한다 — 본문을 꺼내고 hyve 가 알려 준 실패를 타입 있는 예외로 올린다. API 별
본문 오류 코드(data.go.kr ``resultCode``·ECOS ``RESULT.CODE`` …)는 각 스킬이 판정한다.

입력 세 형태:
    (a) ``save_as`` 로 저장한 **본문 그대로**(정본 경로 — HTTP 오류여도 본문이 저장된다)
    (b) ``http_request`` 응답 JSON 전체(``status``·``body``|``body_base64``·``body_truncated`` …)를 옮겨 적은 파일
    (c) 실패한 호출 자리에 모델이 쓴 ``{"error": {"code", "message"}}``

예외 (전부 :class:`HyveInputError` — ``kind`` 가 스킬 출력 JSON 의 ``error`` 값과 맞는다):
    HyveFailure        kind="hyve"       (c) 실패 자리
    HyveHTTPError      kind="http"       (b) 의 status 가 400 이상(또는 200 미만)
    HyveTruncatedError kind="truncated"  (b) 의 ``body_truncated`` 가 참
    HyveEmptyError     kind="input"      빈 파일·빈 본문
    HyveReadError      kind="input"      파일 없음·읽기 실패
    HyveInputError     kind="input"      (b) 인데 본문이 없다(응답 요약만 있음)·base64 가 깨짐

예외 메시지에는 키 이름 뒤 값(``serviceKey=``·``crtfc_key=``·``apiKey=``·``key=`` …)을 가려 싣는다
(:func:`mask_secrets`). hyve 가 이미 가린 ``••••`` 는 그대로 둔다.

사용 예::

    from hyve_input import HyveInputError, read_input

    try:
        body = read_input(path)            # HyveBody(data, form, status, truncated, source …)
    except HyveInputError as exc:
        fail(exc.kind, str(exc))
    data = json.loads(body.data)           # 여기서부터 API 별 판정
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

__all__ = [
    "HyveBody",
    "HyveInputError",
    "HyveFailure",
    "HyveHTTPError",
    "HyveTruncatedError",
    "HyveEmptyError",
    "HyveReadError",
    "read_input",
    "unwrap",
    "mask_secrets",
    "snippet",
]

# 키 이름 뒤 값을 가린다. 이름 앞은 영숫자·밑줄이 아니어야 한다(``monkey=`` 의 ``key=`` 는 잡지 않는다).
_KEY_NAMES = (
    r"service_?key|crtfc_key|api_?key|auth_?key|access_?key|secret_?key|client_?secret"
    r"|access_?token|token|apikey|key"
)
_KEY_IN_TEXT = re.compile(
    rf"(?<![A-Za-z0-9_])((?:{_KEY_NAMES})=)[^&\s\"'<>]*", re.IGNORECASE
)
# 퍼센트 인코딩된 쿼리 안의 ``serviceKey%3D값`` — 이름 앞은 ``%3F``(?)·``%26``(&)일 수 있고,
# 값은 ``%26`` 앞에서 끝난다.
_KEY_IN_ENCODED = re.compile(
    rf"(?:(?<![A-Za-z0-9_])|(?<=%3F)|(?<=%3f)|(?<=%26))((?:{_KEY_NAMES})%3D)(?:(?!%26)[^&\s\"'<>])*", re.IGNORECASE
)
# JSON·파이썬 사전 꼴 ``"serviceKey": "값"`` — 따옴표 안의 값을 가린다.
_KEY_IN_JSON = re.compile(
    rf"(?<![A-Za-z0-9_])([\"']?(?:{_KEY_NAMES})[\"']?\s*:\s*([\"']))(?:(?!\2).)*", re.IGNORECASE
)
_MASK = "••••"


def mask_secrets(text: str) -> str:
    """키 이름 뒤 값을 ``••••`` 로 바꾼다. 이미 ``••••`` 이면 그대로다.

    세 꼴을 본다: ``serviceKey=값`` · 퍼센트 인코딩 ``serviceKey%3D값`` · JSON ``"serviceKey": "값"``.
    """
    text = _KEY_IN_TEXT.sub(lambda m: m.group(1) + _MASK, text)
    text = _KEY_IN_ENCODED.sub(lambda m: m.group(1) + _MASK, text)
    return _KEY_IN_JSON.sub(lambda m: m.group(1) + _MASK, text)


def snippet(data: bytes, limit: int = 80) -> str:
    """오류 메시지에 실을 본문 앞부분 — 공백을 정리하고 키 값을 가린다."""
    text = data[: limit * 4].decode("utf-8", errors="replace")
    text = " ".join(text.split())
    return mask_secrets(text)[:limit]


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class HyveInputError(Exception):
    """입력 파일을 본문으로 쓸 수 없다. ``kind`` 는 스킬 출력 JSON 의 ``error`` 값이다."""

    kind = "input"

    def __init__(self, message: str, source: Optional[Path] = None):
        super().__init__(mask_secrets(message))
        self.source = source


class HyveFailure(HyveInputError):
    """(c) itda-hyve 호출이 실패한 자리 — ``code`` 는 hyve 실패 코드(``secret_missing`` 등)."""

    kind = "hyve"

    def __init__(self, message: str, code: str, hyve_message: str = "", source: Optional[Path] = None):
        super().__init__(message, source)
        self.code = code
        self.hyve_message = mask_secrets(hyve_message)


class HyveHTTPError(HyveInputError):
    """(b) 응답 status 가 오류다. ``body`` 는 스킬이 API 오류 코드를 먼저 읽어 볼 수 있게 싣는다."""

    kind = "http"

    def __init__(self, message: str, status: Any, status_text: str, body: bytes,
                 truncated: bool = False, source: Optional[Path] = None):
        super().__init__(message, source)
        self.status = status
        self.status_text = status_text
        self.body = body
        self.truncated = truncated


class HyveTruncatedError(HyveInputError):
    """(b) ``body_truncated`` — 잘린 본문으로 결론 내지 않는다(``save_as`` 로 다시 받는다)."""

    kind = "truncated"


class HyveEmptyError(HyveInputError):
    """빈 파일 또는 빈 본문."""


class HyveReadError(HyveInputError):
    """파일이 없거나 읽을 수 없다."""


# ---------------------------------------------------------------------------
# 판독
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HyveBody:
    """판독 결과. ``form`` 은 ``"raw"``(a) 또는 ``"envelope"``(b)."""

    data: bytes
    form: str
    status: Optional[int] = None
    status_text: str = ""
    content_type: str = ""
    truncated: bool = False
    source: Optional[Path] = None

    def text(self) -> str:
        """본문을 UTF-8 문자열로(BOM 제거). 디코딩 실패는 ``UnicodeDecodeError`` 그대로 올린다."""
        return self.data.decode("utf-8-sig")


def _where(source: Optional[Path]) -> str:
    return f" — {source.name}" if source is not None else ""


def _is_failure_placeholder(obj: dict) -> bool:
    """(c) ``{"error": {"code": "<문자열>", …}}`` 한 키뿐인 객체.

    ``code`` 가 문자열이어야 한다 — hyve 실패 코드는 ``secret_missing`` 처럼 문자열이고, 같은 모양의
    API 오류 본문(Google 류 ``{"error": {"code": 400}}``)은 숫자라 본문으로 넘겨 스킬이 판정한다.
    """
    err = obj.get("error")
    return len(obj) == 1 and isinstance(err, dict) and isinstance(err.get("code"), str)


def _is_envelope(obj: dict) -> bool:
    """(b) hyve ``http_request`` 응답 — 정수 ``status`` 와 본문 필드(또는 ``saved_path``)."""
    status = obj.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        return False
    return any(k in obj for k in ("body", "body_base64", "saved_path"))


def unwrap(raw: bytes, source: Optional[Path] = None) -> HyveBody:
    """파일 바이트를 세 형태로 가려 본문을 돌려준다(판정은 모듈 docstring).

    JSON 이 아니거나, JSON 이어도 (b)·(c) 모양이 아니면 (a) 본문 그대로다 — 그 본문이 맞는지는 스킬이 판정한다.
    """
    if not raw.strip():
        raise HyveEmptyError(f"입력 파일이 비었습니다{_where(source)}", source)
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return HyveBody(data=raw, form="raw", source=source)
    if not isinstance(obj, dict):
        return HyveBody(data=raw, form="raw", source=source)

    if _is_failure_placeholder(obj):
        err = obj["error"]
        code = err["code"]
        msg = str(err.get("message") or "")
        raise HyveFailure(
            f"itda-hyve 호출이 실패한 자리다({code}): {msg}{_where(source)}",
            code=code, hyve_message=msg, source=source,
        )

    if not _is_envelope(obj):
        return HyveBody(data=raw, form="raw", source=source)

    status = obj["status"]
    status_text = str(obj.get("status_text") or "")
    truncated = bool(obj.get("body_truncated"))
    body = obj.get("body")
    if isinstance(body, str):
        data = body.encode("utf-8")
    elif isinstance(obj.get("body_base64"), str):
        try:
            data = base64.b64decode(obj["body_base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HyveInputError(f"body_base64 를 풀 수 없습니다({exc}){_where(source)}", source) from exc
    else:
        data = None

    if status >= 400 or status < 200:
        shown = snippet(data, 200) if data else ""
        raise HyveHTTPError(
            f"HTTP {status} {status_text}".rstrip() + f"{_where(source)}" + (f": {shown}" if shown else ""),
            status=status, status_text=status_text, body=data or b"", truncated=truncated, source=source,
        )
    if truncated:
        raise HyveTruncatedError(
            f"본문이 잘렸습니다(body_truncated) — save_as 로 다시 받으세요{_where(source)}", source
        )
    if data is None:
        raise HyveInputError(
            "itda-hyve 응답 요약에 본문이 없습니다 — saved_path 가 가리키는 파일을 --input 으로 넘기세요"
            f"{_where(source)}",
            source,
        )
    if not data.strip():
        raise HyveEmptyError(f"응답 본문이 비었습니다(HTTP {status}){_where(source)}", source)
    return HyveBody(
        data=data, form="envelope", status=status, status_text=status_text,
        content_type=str(obj.get("content_type") or ""), truncated=False, source=source,
    )


def read_input(path: Union[str, Path]) -> HyveBody:
    """``--input`` 파일 하나를 읽어 :func:`unwrap` 한다."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise HyveReadError(f"입력 파일이 없습니다: {p}", p)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise HyveReadError(f"입력 파일을 읽을 수 없습니다: {p} ({exc})", p) from exc
    return unwrap(raw, source=p)
