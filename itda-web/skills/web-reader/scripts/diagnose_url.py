#!/usr/bin/env python3
"""web-reader: diagnose_url.py — layered HTTP diagnostic for fetch failures.

Identifies WHERE in the request stack a fetch failure occurs:
  SSRF check → DNS → TCP → SSL → HTTP HEAD → HTTP GET → Content-Type → robots.txt

Used when ``fetch_html.py`` reports a generic error or returns an empty
result. Modeled on the email skill's ``diagnose_smtp.py``.

Output: structured JSON with per-layer status and an aggregated ``diagnosis``
hint pointing at the most likely root cause.
"""
from __future__ import annotations

import argparse
import http.client
import json
import socket
import ssl
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from url_validator import SSRFError, validate_url  # noqa: E402

DEFAULT_TIMEOUT = 10
BASELINE_URL = "https://www.google.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)


def _ms_since(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def probe_ssrf(url: str) -> dict:
    """SSRF 정책 검증 — private/loopback IP 등을 사전 차단."""
    try:
        validate_url(url)
        return {"status": "ok"}
    except SSRFError as e:
        return {"status": "fail", "error": "ssrf_blocked", "detail": str(e)}
    except ValueError as e:
        return {"status": "fail", "error": "invalid_url", "detail": str(e)}


def probe_dns(host: str) -> dict:
    t0 = time.time()
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        ips = sorted({info[4][0] for info in infos})
        return {"status": "ok", "ips": ips, "elapsed_ms": _ms_since(t0)}
    except socket.gaierror as e:
        return {"status": "fail", "error": "dns_failure", "detail": str(e)}


def probe_tcp(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    t0 = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {"status": "ok", "elapsed_ms": _ms_since(t0)}
    except TimeoutError:
        return {"status": "fail", "error": "tcp_timeout",
                "detail": f"TCP {host}:{port} timed out after {timeout}s"}
    except ConnectionRefusedError as e:
        return {"status": "fail", "error": "tcp_refused", "detail": str(e)}
    except OSError as e:
        return {"status": "fail", "error": "tcp_error", "detail": str(e)}


def probe_ssl(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> dict:
    if port not in (443, 8443):
        # http URL — no SSL layer
        return {"status": "skipped", "reason": "non-tls scheme"}
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert() or {}
                cn = None
                for entry in cert.get("subject", ()):
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
    except ssl.SSLCertVerificationError as e:
        return {"status": "fail", "error": "ssl_cert_invalid", "detail": str(e)}
    except ssl.SSLError as e:
        return {"status": "fail", "error": "ssl_error", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "ssl_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_http(url: str, method: str = "HEAD", *, user_agent: str = DEFAULT_UA,
               timeout: float = DEFAULT_TIMEOUT,
               max_redirects: int = 5) -> dict:
    """Issue an HTTP request and capture status, headers, redirect chain."""
    t0 = time.time()
    redirect_chain: list[dict] = []
    current = url
    try:
        for hop in range(max_redirects + 1):
            req = urllib.request.Request(
                current, method=method, headers={"User-Agent": user_agent},
            )
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.HTTPError as e:
                return {
                    "status": "ok" if e.code < 500 else "fail",
                    "http_status": e.code,
                    "error": f"http_{e.code}",
                    "url": current,
                    "redirect_chain": redirect_chain,
                    "elapsed_ms": _ms_since(t0),
                }
            location = resp.headers.get("Location")
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            content_length = resp.headers.get("Content-Length")
            if 300 <= status < 400 and location:
                redirect_chain.append({"from": current, "to": location, "status": status})
                current = urllib.parse.urljoin(current, location)
                resp.close()
                continue
            return {
                "status": "ok",
                "http_status": status,
                "final_url": current,
                "content_type": content_type,
                "content_length": int(content_length) if content_length else None,
                "redirect_chain": redirect_chain,
                "server": resp.headers.get("Server"),
                "elapsed_ms": _ms_since(t0),
            }
        return {
            "status": "fail",
            "error": "redirect_loop",
            "redirect_chain": redirect_chain,
            "detail": f"Exceeded {max_redirects} redirects",
        }
    except (TimeoutError, socket.timeout) as e:
        return {"status": "fail", "error": "http_timeout", "detail": str(e)}
    except urllib.error.URLError as e:
        return {"status": "fail", "error": "url_error",
                "detail": f"{type(e.reason).__name__}: {e.reason}"}
    except http.client.BadStatusLine as e:
        return {"status": "fail", "error": "bad_status_line", "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "fail", "error": "http_unknown",
                "detail": f"{type(e).__name__}: {e}"}


def probe_robots(host: str, scheme: str, path: str = "/",
                 user_agent: str = DEFAULT_UA, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Check whether robots.txt allows fetching `path` for our UA."""
    robots_url = f"{scheme}://{host}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        allowed = rp.can_fetch(user_agent, f"{scheme}://{host}{path}")
        return {"status": "ok", "allowed": allowed, "robots_url": robots_url}
    except Exception as e:  # noqa: BLE001
        return {
            "status": "skipped",
            "reason": f"{type(e).__name__}: {e}",
            "robots_url": robots_url,
        }


def diagnose(report: dict) -> tuple[str, str]:
    d = report["diagnostics"]

    if d["ssrf"]["status"] == "fail":
        return ("ssrf_blocked",
                f"URL이 SSRF 정책에 의해 차단됨. {d['ssrf'].get('detail', '')}")

    if d["dns"]["status"] == "fail":
        return ("dns_failure",
                "DNS 해석 실패. 호스트 이름 오타이거나 인터넷/DNS 문제.")

    baseline_tcp_ok = d.get("baseline", {}).get("tcp", {}).get("status") == "ok"
    if not baseline_tcp_ok:
        return ("no_internet",
                "google.com:443 도 안 됨. 일반 인터넷 egress 차단.")

    if d["tcp"]["status"] == "fail":
        return ("tcp_blocked",
                f"호스트:포트 연결 차단. 방화벽/egress 정책 또는 서버 다운.")

    if d["ssl"]["status"] == "fail":
        if d["ssl"].get("error") == "ssl_cert_invalid":
            return ("ssl_cert_invalid",
                    "TLS 인증서 검증 실패. 만료/CN 불일치/체인 미신뢰. "
                    "정상 사이트라면 클라이언트의 root CA store 갱신 필요.")
        return ("ssl_handshake_fail",
                "TCP는 OK인데 SSL 핸드셰이크 실패. proxy intercept 의심.")

    http_layer = d["http_head"]
    if http_layer["status"] == "fail":
        err = http_layer.get("error", "")
        if err == "http_timeout":
            return ("http_timeout",
                    "HTTP 응답 timeout. 서버 처리 지연, 또는 응답 헤더가 안 옴.")
        if err == "redirect_loop":
            return ("redirect_loop",
                    "리다이렉트 무한 루프. 쿠키/세션 의존 페이지 가능성.")
        return ("http_layer_error", f"HTTP 레벨 오류: {err}")

    code = http_layer.get("http_status")
    if code == 403:
        return ("http_403_forbidden",
                "403 Forbidden. anti-bot/User-Agent 차단/지역 차단/유료 콘텐츠 가능. "
                "브라우저 경로(itda-web:aside-browser-mcp) 시도 권장.")
    if code == 404:
        return ("http_404_not_found", "404 Not Found. URL 자체가 잘못됨.")
    if code == 429:
        return ("http_429_rate_limit",
                "429 Too Many Requests. rate limit 초과. 잠시 후 재시도.")
    if code and 500 <= code < 600:
        return (f"http_{code}_server_error",
                f"{code} 서버 에러. 대상 서버 측 문제. 잠시 후 재시도.")

    ct = (http_layer.get("content_type") or "").lower()
    if not ct.startswith(("text/", "application/json", "application/xml",
                         "application/rss", "application/atom")):
        return ("non_html_content",
                f"Content-Type={ct} — HTML이 아님. PDF/이미지/binary는 별도 도구 필요.")

    robots = d.get("robots", {})
    if robots.get("status") == "ok" and robots.get("allowed") is False:
        return ("robots_denied",
                "robots.txt가 해당 경로 fetch 금지. crawl 정책 준수 시 fetch 불가.")

    cl = http_layer.get("content_length")
    if cl == 0:
        return ("empty_response", "서버가 0 byte 응답. 정상이지만 콘텐츠 없음.")

    return ("all_ok", f"모든 레이어 정상 (HTTP {code}, {ct}).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Layered HTTP diagnostic for web-reader fetch failures.",
    )
    parser.add_argument("url", help="대상 URL (https://...)")
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--skip-robots", action="store_true",
                        help="robots.txt 검사 생략 (네트워크 1회 절약).")
    args = parser.parse_args()

    parsed = urllib.parse.urlparse(args.url)
    host = parsed.hostname or ""
    scheme = parsed.scheme or "https"
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    diagnostics = {
        "ssrf": probe_ssrf(args.url),
        "dns": probe_dns(host) if host else {"status": "skipped"},
    }
    if diagnostics["ssrf"]["status"] == "ok" and diagnostics["dns"]["status"] == "ok":
        diagnostics["tcp"] = probe_tcp(host, port, args.timeout)
        diagnostics["ssl"] = probe_ssl(host, port, args.timeout)
        diagnostics["http_head"] = probe_http(
            args.url, "HEAD", user_agent=args.user_agent, timeout=args.timeout,
        )
        if not args.skip_robots:
            diagnostics["robots"] = probe_robots(
                host, scheme, path, args.user_agent, args.timeout,
            )
        # baseline
        baseline_parsed = urllib.parse.urlparse(BASELINE_URL)
        diagnostics["baseline"] = {
            "url": BASELINE_URL,
            "tcp": probe_tcp(baseline_parsed.hostname or "", 443, args.timeout),
        }

    report = {"url": args.url, "host": host, "diagnostics": diagnostics}
    code, message = diagnose(report)
    report["diagnosis"] = {"code": code, "message": message}

    overall_ok = code == "all_ok"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
