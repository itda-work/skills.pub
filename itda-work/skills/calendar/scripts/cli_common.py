#!/usr/bin/env python3
"""itda-calendar: cli_common — shared CLI helpers (env resolve, connect, errors)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows locale(cp949) stdio 고정 해제 — JSON detail 의 한국어 안내가 cp949 로
# 인코딩되면 utf-8 부모 프로세스의 파이프 디코드가 깨진다 (#1036).
for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover - Python < 3.7
            pass

sys.path.insert(0, str(Path(__file__).parent))
from caldav_providers import (detect_providers, get_provider,  # noqa: E402
                              is_supported_provider, supported_provider_names)
from env_loader import merged_env  # noqa: E402
import caldav_client  # noqa: E402


def emit(obj, code: int = 0) -> None:
    """Print JSON to stdout and exit with code."""
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def emit_error(error: str, detail=None, code: int = 1) -> None:
    out = {"status": "error", "error": error}
    if detail is not None:
        out["detail"] = str(detail)[:300]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(code)


def resolve_provider_or_exit(provider: str, account: str | None = None) -> dict:
    """Resolve credentials, or exit with a classified error.

    Exit 1: ``unsupported_provider`` (provider this skill cannot serve, e.g.
    google/outlook/kakao — OAuth/iCal track) or ``credentials_missing``
    (supported provider, env vars absent). Exit 2: ``account_required``
    (supported provider, multiple ready accounts, no ``--account``).
    """
    # Unsupported provider — intentionally NOT served (non-goal). Google Calendar
    # is covered by Claude's official Google Calendar connector, so this skill does
    # not reimplement it; Outlook/Kakao are also unsupported (OAuth/iCal model).
    # Distinct from a supported provider that merely lacks credentials (no env vars
    # exist to "configure" an unsupported provider).
    if not is_supported_provider(provider):
        emit_error("unsupported_provider",
                   f"provider '{provider}' is not supported. "
                   f"supported: {', '.join(supported_provider_names())}. "
                   f"구글 캘린더는 Claude 공식 Google Calendar 커넥터를 쓰세요(이 스킬은 미지원). "
                   f"아웃룩·카카오도 미지원.",
                   code=1)

    env = merged_env()
    prov = get_provider(provider, env, account)
    if prov is not None:
        return prov

    detected = detect_providers(env)
    match = next((p for p in detected
                  if p["provider"] == provider or provider in p.get("aliases", [])),
                 None)
    if match and account is None:
        ready = [a["account_id"] for a in match["accounts"] if a["status"] == "ready"]
        if len(ready) > 1:
            emit_error("account_required",
                       f"multiple accounts for {provider}: {ready}; pass --account",
                       code=2)
    emit_error("credentials_missing",
               f"provider '{provider}' not configured (set its env vars; "
               f"see GUIDE.md)", code=1)


def classify_error(exc) -> str:
    """Map an exception to a stable error code."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "authorization" in name or "401" in msg or "unauthorized" in msg:
        return "auth_failed"
    if "notfound" in name or "404" in msg:
        return "not_found"
    if "timed out" in msg or "timeout" in msg:
        return "timeout"
    if any(s in msg for s in ("getaddrinfo", "name or service", "connection",
                              "ssl", "certificate")):
        return "network_error"
    return "caldav_error"


def connect_or_exit(prov: dict, timeout: int = 30):
    """Connect + discover principal, or exit 1 with a classified error."""
    client = caldav_client.connect(prov, timeout=timeout)
    try:
        principal = caldav_client.get_principal(client)
    except Exception as e:  # noqa: BLE001
        emit_error(classify_error(e), e, code=1)
    return client, principal
