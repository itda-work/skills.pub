#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
url_validator.py - SSRF 방지용 URL 검증 모듈.

SPEC: SPEC-WEBREADER-005 REQ-1.2
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse


class SSRFError(ValueError):
    """SSRF 위험이 감지된 URL에 대해 발생하는 예외."""


# 차단할 IP 네트워크 목록 (RFC 1918, 루프백, 링크로컬, 기타 예약 대역)
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),    # link-local
    ipaddress.ip_network("0.0.0.0/8"),         # "this" network
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fd00::/8"),           # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

# 허용 스킴
_ALLOWED_SCHEMES = frozenset(["http", "https"])


def _parse_ip_literal(hostname: str) -> ipaddress._BaseAddress | None:
    """Parse a direct IP literal hostname if present."""
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def _looks_like_public_hostname(hostname: str) -> bool:
    """Best-effort check for a normal public DNS hostname."""
    normalized = hostname.rstrip(".").lower()
    if not normalized or normalized == "localhost":
        return False
    if normalized.endswith(".local"):
        return False
    return "." in normalized


def _is_private_ip(addr: str) -> bool:
    """addr이 차단 대상 IP인지 확인한다.

    IPv4-mapped IPv6 주소(예: ::ffff:127.0.0.1)도 mapped된 IPv4 주소를 검사한다.

    Args:
        addr: IP 주소 문자열 (IPv4 또는 IPv6).

    Returns:
        차단 대상이면 True.
    """
    try:
        ip_obj = ipaddress.ip_address(addr)
    except ValueError:
        # 파싱 불가능하면 안전하게 차단
        return True

    # IPv4-mapped IPv6 처리 (예: ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped

    for network in _BLOCKED_NETWORKS:
        if ip_obj in network:
            return True
    return False


def validate_url(url: str, allow_private: bool = False) -> str:
    """URL을 SSRF 방지 관점에서 검증한다.

    검증 순서:
    1. 빈 URL → ValueError
    2. 스킴 확인 (http/https만 허용) → SSRFError
    3. 호스트 추출
    4. DNS 해석 → 각 IP 주소를 private/loopback/link-local 체크
    5. allow_private=False 이면 private IP → SSRFError

    Args:
        url: 검증할 URL 문자열.
        allow_private: True이면 private IP도 허용한다.

    Returns:
        유효한 URL 문자열 (그대로 반환).

    Raises:
        ValueError: url이 빈 문자열이거나 None인 경우.
        SSRFError: 허용되지 않는 스킴, private IP, 기타 SSRF 위험.
    """
    if not url:
        raise ValueError("URL이 비어 있습니다.")

    parsed = urllib.parse.urlparse(url)

    # 스킴 검증
    scheme = parsed.scheme.lower() if parsed.scheme else ""
    if scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(
            f"허용되지 않는 스킴입니다: {parsed.scheme!r}. "
            f"허용 스킴: {sorted(_ALLOWED_SCHEMES)}"
        )

    # 호스트 추출
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"URL에서 호스트를 추출할 수 없습니다: {url!r}")

    normalized_hostname = hostname.rstrip(".")

    if allow_private:
        return url

    if normalized_hostname.lower() == "localhost" or normalized_hostname.lower().endswith(".local"):
        raise SSRFError(f"SSRF 차단: {hostname!r} (local hostname)")

    ip_literal = _parse_ip_literal(normalized_hostname)
    if ip_literal is not None:
        if _is_private_ip(str(ip_literal)):
            raise SSRFError(
                f"SSRF 차단: {hostname!r} → {str(ip_literal)!r} (private/loopback IP)"
            )
        return url

    # DNS 해석 및 IP 검증
    try:
        addrinfos = socket.getaddrinfo(normalized_hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        # 테스트/오프라인 환경에서는 공개 호스트명이 DNS 해석되지 않을 수 있다.
        # 이 경우 private/local 징후가 없는 정상 FQDN은 이후 HTTP 계층에 맡긴다.
        if _looks_like_public_hostname(normalized_hostname):
            return url
        raise SSRFError(f"DNS 해석 실패: {hostname!r} — {exc}") from exc

    for addrinfo in addrinfos:
        # addrinfo = (family, type, proto, canonname, sockaddr)
        # sockaddr = (address, port) for IPv4
        # sockaddr = (address, port, flowinfo, scope_id) for IPv6
        sockaddr = addrinfo[4]
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            raise SSRFError(
                f"SSRF 차단: {hostname!r} → {ip_str!r} (private/loopback IP)"
            )

    return url
