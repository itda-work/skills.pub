"""http_util.py - urllib.request 공용 래퍼.

모든 외부 HTTP를 표준 라이브러리로 수행한다(REQ-009).
타임아웃·에러 분류·JSON 파싱 결과를 (성공여부, 데이터, 사유) 튜플로 반환한다.
예외를 호출부로 전파하지 않는 graceful 설계(REQ-010/013).
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


_USER_AGENT = (
    "Mozilla/5.0 (compatible; weather-here-skill; +itda-skills)"
)


def fetch_json(
    url: str,
    timeout: int = 5,
) -> tuple[bool, Any | None, str]:
    """URL에서 JSON을 가져와 파싱한다.

    Args:
        url: 요청할 HTTPS URL.
        timeout: 타임아웃(초), 기본 5초 (REQ-010).

    Returns:
        (ok, data, reason):
            ok=True  → data: 파싱된 dict/list, reason: ""
            ok=False → data: None, reason: 한국어 오류 설명 문자열
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw)
        return True, data, ""
    except urllib.error.HTTPError as exc:
        return False, None, f"HTTP 오류 {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return False, None, f"네트워크 연결 오류: {exc.reason}"
    except socket.timeout:
        return False, None, "요청 시간 초과(timeout)"
    except json.JSONDecodeError as exc:
        return False, None, f"JSON 파싱 오류: {exc.msg}"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"알 수 없는 오류: {exc}"
