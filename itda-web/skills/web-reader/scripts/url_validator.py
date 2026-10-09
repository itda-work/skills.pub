#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""url_validator.py — 요청 전 URL 문자열 검사(사설·로컬 목적지 거부). 네트워크 없음.

web-reader 8.0.0(itda-work/skills#46): 요청은 itda-hyve 의 ``http_request`` 가 사용자 PC 에서 보낸다.
그 PC 에서는 공유기 관리 화면·로컬 서비스가 닿는다. 그래서 ``plan.py`` 는 호출을 만들기 전에,
그리고 리다이렉트 홉마다(``follow_redirects: false`` 로 한 홉씩 계획한다) 이 검사를 한다.

이 모듈이 **못 하는 것**: DNS 해석 뒤 IP 검사(스크립트는 소켓을 열지 않는다 — 규칙
``cowork-network-via-hyve``). 공개 이름이 사설 IP 로 풀리는 경우(DNS 리바인딩 포함)는 itda-hyve 가
목적지 IP 를 보고 막아야 한다 — 그 기능이 나오기 전에는 이 스킬을 배포하지 않는다(CHANGELOG 8.0.0).
"""
from __future__ import annotations

import ipaddress
import re
import urllib.parse


class SSRFError(ValueError):
    """사설·로컬 목적지이거나 검사할 수 없는 URL."""


# 거부하는 대역 — ``ipaddress`` 의 is_private 등에 더해 명시한다(판정이 파이썬 판에 따라 흔들리지 않게).
_BLOCKED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",        # this network
        "10.0.0.0/8",       # RFC 1918
        "100.64.0.0/10",    # CGNAT
        "127.0.0.0/8",      # loopback
        "169.254.0.0/16",   # link-local
        "172.16.0.0/12",    # RFC 1918
        "192.0.0.0/24",     # IETF protocol assignments
        "192.168.0.0/16",   # RFC 1918
        "198.18.0.0/15",    # benchmarking
        "224.0.0.0/4",      # multicast
        "240.0.0.0/4",      # reserved·broadcast
        "::/128",           # unspecified
        "::1/128",          # loopback
        "fc00::/7",         # ULA
        "fe80::/10",        # link-local
        "ff00::/8",         # multicast
        "64:ff9b::/96",     # NAT64 — 뒤 32비트가 IPv4 다(사설로 향할 수 있다)
        "64:ff9b:1::/48",   # 지역 NAT64(RFC 8215)
        "::/96",            # IPv4-compatible(폐기 표기 `[::127.0.0.1]`) — W14 리뷰 M1
        "100::/64",         # discard-only
        "::ffff:0:0:0/96",  # IPv4-translated(`[::ffff:0:127.0.0.1]`) — 재확인 ①
        "fec0::/10",        # 폐기된 site-local — 재확인 ①
    )
]

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# 로컬 이름 — 공개 DNS 에서 풀리지 않고 사용자 망 안을 가리킨다.
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".home.arpa", ".intranet", ".corp")

# 점·숫자·16진 표기만으로 된 호스트(``2130706433``·``0x7f.1``·``017700000001``) — 해석기에 따라
# 루프백으로 풀린다. 표준 점 네 개 십진 표기가 아니면 판정하지 않고 거부한다.
_NUMERIC_HOST = re.compile(r"^(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]*|[0-9]*))*\.?$", re.IGNORECASE)


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _blocked_ip(ip.ipv4_mapped)
        if ip.sixtofour is not None and _blocked_ip(ip.sixtofour):
            return True
    return any(ip in net for net in _BLOCKED_NETWORKS if ip.version == net.version)


_HOST_CHARS = re.compile(r"^[a-z0-9._-]+$")


# IDNA2003(파이썬 `idna` 코덱)과 UTS#46 비전이 처리(Go·브라우저)가 다르게 바꾸는 문자 — 바꾸면 **다른 도메인**이 된다(W14 재확인 N1).
# `ß`→`ss`(Go 는 그대로 퓨니코드), 어말 `ς`→`σ`, ZWJ·ZWNJ 는 지움(Go 는 남김). 바꾸지 않고 거부한다.
_DEVIATION_CHARS = {"\u00df": "ß", "\u1e9e": "ẞ", "\u03c2": "ς", "\u200d": "ZWJ", "\u200c": "ZWNJ"}


def _ascii_host(host: str) -> str:
    """호스트를 itda-hyve(Go)가 접속할 때 쓰는 ASCII 꼴로 바꾼다 — W14 리뷰 M1·재확인 N1.

    Go 의 HTTP 클라이언트는 접속 전에 비ASCII 호스트를 IDNA 매핑한다(전각 `１２７`→`127`, 원문자 `①`→`1`, `。`→`.`,
    전각 `ｌｏｃａｌｈｏｓｔ`→`localhost`). 원형 문자열에 검사를 대면 표기만 바꿔 넘어간다. 그래서 IDNA(NFKC 포함)로 바꾼 ASCII 에
    검사를 걸고, 그 ASCII 를 호출 URL 에 싣는다.

    - **ASCII 호스트(`xn--` 포함)는 바꾸지 않는다** — Go 는 ASCII 호스트를 풀지 않고 그대로 보낸다(재확인 N1: `xn--8g7ccp.0.0.1` 의
      dial 대상이 그 이름 그대로). 왕복 검사를 걸면 Go 가 받는 `xn--strae-oqa.de`(straße)를 거부하게 된다. 라벨 길이만 본다.
    - 비ASCII 호스트에 `ß`·`ς`·ZWJ·ZWNJ 가 있으면 거부한다 — 파이썬 IDNA2003 과 Go UTS#46 의 결과가 달라 검사한 것과 보내는 것이 갈린다.
    """
    if host.isascii():
        ascii_host = host.lower().rstrip(".")
        labels = ascii_host.split(".")
        if not ascii_host or len(ascii_host) > 253 or any(not lab or len(lab) > 63 for lab in labels):
            raise SSRFError(f"호스트 이름을 해석할 수 없습니다(빈 라벨·긴 라벨): {host}")
        return ascii_host
    found = [name for ch, name in _DEVIATION_CHARS.items() if ch in host]
    if found:
        raise SSRFError(
            f"호스트에 IDNA 처리 방식에 따라 다른 도메인이 되는 문자({'·'.join(found)})가 있습니다: {host} — 퓨니코드(xn--…) 표기로 다시 주세요"
        )
    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise SSRFError(f"호스트 이름을 해석할 수 없습니다: {host}") from exc
    return ascii_host.rstrip(".")


def _check_host(host: str) -> None:
    """정규화한 ASCII 호스트(대괄호 없는 IPv6 포함)를 검사한다."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if _blocked_ip(ip):
            raise SSRFError(f"사설·로컬 주소입니다: {host}")
        return
    if not _HOST_CHARS.match(host):
        raise SSRFError(f"호스트에 쓸 수 없는 문자가 있습니다: {host}")
    if _NUMERIC_HOST.match(host):
        raise SSRFError(f"표준이 아닌 숫자 표기 호스트입니다: {host}")
    if host == "localhost" or host.endswith(_LOCAL_SUFFIXES):
        raise SSRFError(f"로컬 이름입니다: {host}")
    if "." not in host:
        raise SSRFError(f"점이 없는 한 단어 호스트입니다(사내·로컬 이름): {host}")


def check_url(url: str) -> tuple[str, str]:
    """URL 을 검사해 ``(호출에 쓸 URL, ASCII 호스트)`` 를 돌려준다. 거부면 :class:`SSRFError`.

    - 스킴 http/https, 호스트 필수, 사용자 정보(``user:pass@``) 거부, 호스트의 ``%``(퍼센트 인코딩·IPv6 zone) 거부
    - 비ASCII 호스트를 IDNA(NFKC) ASCII 로 정규화한 뒤 검사한다(전각·원문자·``。``·IDN — W14 리뷰 M1). 돌려주는 URL 은 그 ASCII 호스트로 다시 쓴 것이다.
      ASCII 호스트는 그대로, ``ß``·``ς``·ZWJ·ZWNJ 가 든 비ASCII 호스트는 거부(재확인 N1)
    - 리터럴 IP(v4·v6·v4-mapped·v4-compatible·6to4·NAT64)가 사설·루프백·링크로컬·CGNAT·멀티캐스트 등이면 거부
    - 표준이 아닌 숫자 표기 호스트, ``localhost``·``.local``·``.internal`` 류, 점 없는 한 단어 호스트 거부
    """
    if not url or not url.strip():
        raise SSRFError("URL 이 비었습니다")
    url = url.strip()
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise SSRFError(f"URL 을 해석할 수 없습니다: {exc}") from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(f"http·https 만 받습니다(받은 스킴: {parts.scheme or '없음'!r})")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise SSRFError("URL 에 사용자 정보(user@ 또는 user:pass@)가 있습니다 — 이 스킬은 로그인 페이지를 받지 않습니다")
    try:
        raw_host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise SSRFError(f"호스트·포트를 해석할 수 없습니다: {exc}") from exc
    if not raw_host:
        raise SSRFError("URL 에 호스트가 없습니다")
    if "%" in raw_host:
        raise SSRFError(f"호스트에 퍼센트 인코딩(또는 IPv6 zone)이 있습니다: {raw_host}")
    if port is not None and not (0 < port < 65536):
        raise SSRFError(f"포트가 범위 밖입니다: {port}")

    is_v6 = ":" in raw_host
    host = raw_host.lower() if is_v6 else _ascii_host(raw_host)
    if not host:
        raise SSRFError("URL 에 호스트가 없습니다")
    _check_host(host)

    netloc = f"[{host}]" if is_v6 else host
    if port is not None:
        netloc += f":{port}"
    return urllib.parse.urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, parts.fragment)), host


def validate_url(url: str) -> str:
    """:func:`check_url` 의 URL 만 돌려준다(옛 호출 모양 — 거부면 :class:`SSRFError`)."""
    return check_url(url)[0]
