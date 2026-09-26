#!/usr/bin/env python3
"""itda-email: diagnose_smtp.py — layered SMTP diagnostic for connection errors.

Identifies WHERE in the connection stack a failure occurs:
  DNS resolution → TCP connect → SSL handshake → SMTP banner →
  EHLO → AUTH

Used when ``check_connection.py`` reports a generic "Connection unexpectedly
closed" error, which can stem from many root causes (sandbox egress block,
SSL intercept proxy, server-side rate limiting, invalid credentials, ...).

Output: structured JSON with per-layer status and an aggregated ``diagnosis``
hint pointing at the most likely root cause.
"""
from __future__ import annotations

import argparse
import json
import smtplib
import socket
import ssl
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from email_providers import get_provider  # noqa: E402
from env_loader import merged_env  # noqa: E402

DEFAULT_TIMEOUT = 10
COMPARE_HOSTS = (
    ("google.com", 443),  # baseline: TLS to a globally reachable host
)


def _ms_since(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def probe_dns(host: str) -> dict:
    """Resolve host to IPs."""
    t0 = time.time()
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        ips = sorted({info[4][0] for info in infos})
        return {"status": "ok", "ips": ips, "elapsed_ms": _ms_since(t0)}
    except socket.gaierror as e:
        return {"status": "fail", "error": "dns_failure", "detail": str(e)}


def probe_tcp(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Open raw TCP socket — confirms egress reachability."""
    t0 = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {"status": "ok", "elapsed_ms": _ms_since(t0)}
    except TimeoutError:
        return {"status": "fail", "error": "tcp_timeout",
                "detail": f"TCP connect to {host}:{port} timed out after {timeout}s"}
    except ConnectionRefusedError as e:
        return {"status": "fail", "error": "tcp_refused", "detail": str(e)}
    except OSError as e:
        return {"status": "fail", "error": "tcp_error", "detail": str(e)}


def probe_ssl(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """TCP + SSL handshake. Captures TLS version + peer cert subject."""
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert() or {}
                subject = cert.get("subject", ())
                # subject is tuple of tuples — flatten common name
                cn = None
                for entry in subject:
                    for k, v in entry:
                        if k == "commonName":
                            cn = v
                            break
                return {
                    "status": "ok",
                    "tls_version": ssock.version(),
                    "peer_cn": cn,
                    "elapsed_ms": _ms_since(t0),
                }
    except ssl.SSLError as e:
        return {"status": "fail", "error": "ssl_error", "detail": str(e)}
    except TimeoutError:
        return {"status": "fail", "error": "ssl_timeout",
                "detail": f"SSL handshake to {host}:{port} timed out"}
    except Exception as e:  # noqa: BLE001 — diagnostic catch-all
        return {"status": "fail", "error": "ssl_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_smtp_465(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """SMTP_SSL connect + banner + EHLO (no auth)."""
    t0 = time.time()
    try:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            banner = getattr(smtp, "_helo_resp", None) or ""
            code, msg = smtp.ehlo()
            features = sorted(smtp.esmtp_features.keys())
            return {
                "status": "ok",
                "ehlo_code": code,
                "features": features,
                "elapsed_ms": _ms_since(t0),
            }
    except smtplib.SMTPServerDisconnected as e:
        return {"status": "fail", "error": "server_disconnected", "detail": str(e)}
    except smtplib.SMTPConnectError as e:
        return {"status": "fail", "error": "smtp_connect_error", "detail": str(e)}
    except (TimeoutError, socket.timeout) as e:
        return {"status": "fail", "error": "smtp_timeout", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "smtp_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_smtp_587_starttls(host: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """SMTP plaintext connect on 587 + STARTTLS upgrade with verified cert."""
    t0 = time.time()
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, 587, timeout=timeout) as smtp:
            smtp.ehlo()
            if not smtp.has_extn("starttls"):
                return {"status": "fail", "error": "no_starttls",
                        "detail": "Server did not advertise STARTTLS"}
            smtp.starttls(context=ctx)
            smtp.ehlo()
            return {"status": "ok", "elapsed_ms": _ms_since(t0)}
    except (TimeoutError, socket.timeout) as e:
        return {"status": "fail", "error": "starttls_timeout", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "starttls_failed",
                "detail": f"{type(e).__name__}: {e}"}


def probe_smtp_587_auth(host: str, email: str, password: str,
                         timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Full STARTTLS(587) + AUTH — iCloud 등 SSL 미지원 provider 전용."""
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, 587, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(email, password)
            return {"status": "ok", "elapsed_ms": _ms_since(t0)}
    except smtplib.SMTPAuthenticationError as e:
        return {"status": "fail", "error": "auth_failed",
                "detail": f"code={e.smtp_code} {e.smtp_error!r}"}
    except smtplib.SMTPServerDisconnected as e:
        return {"status": "fail", "error": "server_disconnected_during_auth",
                "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "auth_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_smtp_auth(host: str, port: int, email: str, password: str,
                    timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Full SMTP_SSL + AUTH — confirms credentials work end-to-end."""
    t0 = time.time()
    try:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            smtp.login(email, password)
            return {"status": "ok", "elapsed_ms": _ms_since(t0)}
    except smtplib.SMTPAuthenticationError as e:
        return {"status": "fail", "error": "auth_failed",
                "detail": f"code={e.smtp_code} {e.smtp_error!r}"}
    except smtplib.SMTPServerDisconnected as e:
        return {"status": "fail", "error": "server_disconnected_during_auth",
                "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "auth_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_baseline(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Baseline TCP+SSL to a generic host — distinguishes 'no internet' from
    'NAVER-specific block'."""
    return {
        "tcp": probe_tcp(host, port, timeout),
        "ssl": probe_ssl(host, port, timeout),
    }


def diagnose(report: dict) -> tuple[str, str]:
    """Classify the failure into a known pattern.

    Returns (diagnosis_code, human_readable_message).
    """
    d = report["diagnostics"]

    # 1. DNS layer
    if d["dns"]["status"] == "fail":
        return ("dns_failure",
                "DNS 해석 실패. 인터넷 연결 자체가 끊겼거나 DNS 서버 설정 문제.")

    # 2. Baseline check — is internet itself working?
    baseline = d.get("baseline", {})
    baseline_tcp_ok = baseline.get("google.com:443", {}).get("tcp", {}).get("status") == "ok"
    if not baseline_tcp_ok:
        return ("no_internet",
                "google.com:443 도 안 되는 상황. 일반 인터넷 egress가 차단됨.")

    # iCloud 등 STARTTLS 전용 provider 경로 (ssl_465 키 부재)
    if "ssl_465" not in d:
        if d.get("tcp_587", {}).get("status") == "fail":
            return ("egress_block_587",
                    "포트 587 차단됨. STARTTLS 전용 provider(iCloud 등)이므로 발송 불가.")
        if d.get("starttls_587", {}).get("status") == "fail":
            return ("starttls_failure",
                    "STARTTLS 핸드셰이크 실패. 회사 프록시의 TLS intercept 또는 서버 측 차단.")
        auth = d.get("smtp_auth_587")
        if auth and auth.get("status") == "fail":
            if auth.get("error") == "auth_failed":
                return ("credentials_invalid",
                        "STARTTLS+AUTH 실패. 앱 전용 비밀번호 만료/오타, 2FA 미활성 가능.")
            return ("auth_layer_error",
                    f"STARTTLS+AUTH 단계 비정상 오류 ({auth.get('error')}).")
        return ("all_ok", "모든 레이어 정상 (STARTTLS 경로).")

    # 3. TCP 465 layer
    if d["tcp_465"]["status"] == "fail":
        if d.get("tcp_587", {}).get("status") == "ok":
            return ("egress_block_465",
                    "포트 465만 차단됨. 587(STARTTLS)로 전환 필요. "
                    "샌드박스/회사망의 outbound firewall이 SMTPS만 막은 상태.")
        return ("egress_block_smtp",
                "SMTP 모든 포트(465/587) 차단. 컨테이너/Cowork 샌드박스의 SMTP 전체 차단 가능.")

    # 4. SSL 465 layer
    if d["ssl_465"]["status"] == "fail":
        return ("ssl_intercept_or_break",
                "TCP는 되지만 SSL 핸드셰이크 실패. 회사 프록시의 TLS intercept, "
                "오래된 OpenSSL, 인증서 신뢰 체인 누락 등이 원인일 수 있음.")

    # 5. SMTP banner/EHLO layer
    if d["smtp_465"]["status"] == "fail":
        err = d["smtp_465"].get("error", "")
        if err == "server_disconnected":
            return ("server_disconnect",
                    "SSL는 OK인데 SMTP 핸드셰이크 직후 서버가 연결 끊음. "
                    "NAVER 측 IP 평판/rate limit, 또는 사용자 계정의 SMTP 차단 가능.")
        return ("smtp_protocol_error",
                f"SMTP 프로토콜 레벨 오류 ({err}). 서버 응답 형식이 비표준이거나, "
                "MITM proxy가 SMTP를 변조 중일 수 있음.")

    # 6. AUTH layer
    auth_result = d.get("smtp_auth_465")
    if auth_result and auth_result.get("status") == "fail":
        if auth_result.get("error") == "auth_failed":
            return ("credentials_invalid",
                    "연결은 모두 OK인데 로그인 실패. 앱 비밀번호 만료/오타, "
                    "2FA 미활성, IMAP/SMTP 사용 미허용 가능.")
        return ("auth_layer_error",
                f"AUTH 단계에서 비정상 오류 ({auth_result.get('error')}).")

    return ("all_ok", "모든 레이어 정상.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Layered SMTP diagnostic to identify connection failure root cause.",
    )
    parser.add_argument("--provider", required=True,
                        choices=["naver", "google", "gmail", "daum", "icloud", "custom"])
    parser.add_argument("--account", default=None)
    parser.add_argument("--no-auth", action="store_true",
                        help="Skip the AUTH probe (DNS+TCP+SSL+EHLO only).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"Per-probe timeout in seconds (default: {DEFAULT_TIMEOUT}).")
    args = parser.parse_args()

    env = merged_env()
    provider = get_provider(args.provider, env, account=args.account)
    if not provider:
        print(json.dumps({"status": "error", "error": "provider_not_found"}))
        sys.exit(1)

    smtp_host = provider["smtp_host"]
    smtp_port = provider["smtp_port"]
    is_starttls_only = (smtp_port == 587)

    if is_starttls_only:
        # iCloud 등 587/STARTTLS 전용 provider: SSL 465 probe skip (의미 없는 거짓 fail 방지)
        diagnostics = {
            "dns": probe_dns(smtp_host),
            "tcp_587": probe_tcp(smtp_host, 587, args.timeout),
            "starttls_587": probe_smtp_587_starttls(smtp_host, args.timeout),
            "baseline": {
                f"{h}:{p}": probe_baseline(h, p, args.timeout) for h, p in COMPARE_HOSTS
            },
        }
        if not args.no_auth and provider.get("email") and provider.get("password"):
            diagnostics["smtp_auth_587"] = probe_smtp_587_auth(
                smtp_host, provider["email"], provider["password"], args.timeout
            )
    else:
        diagnostics = {
            "dns": probe_dns(smtp_host),
            "tcp_465": probe_tcp(smtp_host, smtp_port, args.timeout),
            "ssl_465": probe_ssl(smtp_host, smtp_port, args.timeout),
            "smtp_465": probe_smtp_465(smtp_host, smtp_port, args.timeout),
            "tcp_587": probe_tcp(smtp_host, 587, args.timeout),
            "starttls_587": probe_smtp_587_starttls(smtp_host, args.timeout),
            "baseline": {
                f"{h}:{p}": probe_baseline(h, p, args.timeout) for h, p in COMPARE_HOSTS
            },
        }
        if not args.no_auth and provider.get("email") and provider.get("password"):
            diagnostics["smtp_auth_465"] = probe_smtp_auth(
                smtp_host, smtp_port, provider["email"], provider["password"], args.timeout
            )

    report: dict = {
        "provider": args.provider,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "diagnostics": diagnostics,
    }
    code, message = diagnose(report)
    report["diagnosis"] = {"code": code, "message": message}

    overall_ok = code == "all_ok"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
