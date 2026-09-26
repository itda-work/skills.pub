#!/usr/bin/env python3
"""cloudflare-tunnel desired-state 정책/계획 엔진 (순수 로직, 부수효과 없음).

이 모듈은 cloudflared / Cloudflare API 를 호출하지 않는다. 선언형 desired-state
(라우트 표)를 받아 검증하고, 보안 기본값을 강제하며, reconcile 단계가 실행할
계획(cloudflared ingress · DNS CNAME · Access 애플리케이션)을 순수 데이터로
산출한다. 실제 적용(cloudflared 실행·REST 호출)은 별도 모듈이 담당한다.

보안 기본값 (SPEC-OPS-TUNNEL-001):
- 라우트별 Access 는 **기본 required**. `public` 은 명시적 opt-in 만.
- 비-HTTP 서비스(rdp/ssh/tcp/...)에는 `public` 을 허용하지 않는다(거부).
- 모든 public 라우트는 노출 경고로 표면화한다.
- required 인데 라이브 Access 앱이 없으면 drift 경고로 표면화한다.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

if sys.version_info < (3, 10):  # 런타임 가드 (.claude/rules/itda/skills/python-runtime.md)
    sys.exit("Python 3.10+ required")

# Access 를 떼어도(평문 노출) 그나마 정당화되는 스킴 = HTTP 계열만.
HTTP_SCHEMES = frozenset({"http", "https"})
# 인식하는 서비스 스킴. 이 밖이면 경고로 표면화한다.
KNOWN_SCHEMES = frozenset({"http", "https", "rdp", "ssh", "tcp", "smb", "unix"})

AccessMode = Literal["required", "public"]


class PolicyError(ValueError):
    """desired-state 가 스키마 또는 보안 정책을 위반했을 때."""


@dataclass(frozen=True)
class Route:
    """단일 ingress 라우트."""

    hostname: str
    service: str  # 예: "rdp://localhost:3389", "http://localhost:8080"
    access: AccessMode = "required"
    policy: str | None = None  # Access 신원 정책 (예: "email:you@example.com")

    @property
    def scheme(self) -> str:
        return self.service.split("://", 1)[0].lower() if "://" in self.service else ""


@dataclass(frozen=True)
class DesiredState:
    tunnel: str
    routes: tuple[Route, ...]
    default_policy: str | None = None  # Access 라우트에 policy 미지정 시 기본 신원


def parse_state(data: object) -> DesiredState:
    """JSON 객체(dict)를 검증해 DesiredState 로 변환한다. 위반 시 PolicyError."""
    if not isinstance(data, dict):
        raise PolicyError("desired-state 는 JSON 객체여야 합니다.")
    tunnel = data.get("tunnel")
    if not isinstance(tunnel, str) or not tunnel.strip():
        raise PolicyError("`tunnel`(터널 이름)은 필수 문자열입니다.")
    raw_routes = data.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise PolicyError("`routes` 는 1개 이상의 배열이어야 합니다.")

    seen: set[str] = set()
    routes: list[Route] = []
    for i, r in enumerate(raw_routes):
        if not isinstance(r, dict):
            raise PolicyError(f"routes[{i}] 는 객체여야 합니다.")
        hostname = r.get("hostname")
        service = r.get("service")
        if not isinstance(hostname, str) or not hostname.strip():
            raise PolicyError(f"routes[{i}].hostname 이 누락되었습니다.")
        if not isinstance(service, str) or "://" not in service:
            raise PolicyError(
                f"routes[{i}].service 는 'scheme://host:port' 형식이어야 합니다 "
                f"(받음: {service!r})."
            )
        if hostname in seen:
            raise PolicyError(f"중복 hostname: {hostname}")
        seen.add(hostname)
        access = r.get("access", "required")
        if access not in ("required", "public"):
            raise PolicyError(
                f"routes[{i}].access 는 'required' 또는 'public' 이어야 합니다 "
                f"(받음: {access!r})."
            )
        policy = r.get("policy")
        if policy is not None and not isinstance(policy, str):
            raise PolicyError(f"routes[{i}].policy 는 문자열이어야 합니다.")
        routes.append(
            Route(hostname=hostname, service=service, access=access, policy=policy)
        )

    default_policy = data.get("default_policy")
    if default_policy is not None and not isinstance(default_policy, str):
        raise PolicyError("`default_policy` 는 문자열이어야 합니다.")
    return DesiredState(
        tunnel=tunnel, routes=tuple(routes), default_policy=default_policy
    )


def enforce_policy(state: DesiredState) -> None:
    """보안 기본값 위반 시 PolicyError 를 던진다.

    핵심 불변식: 비-HTTP 서비스(rdp/ssh/tcp/...)는 절대 public 일 수 없다.
    """
    for r in state.routes:
        if r.access == "public" and r.scheme not in HTTP_SCHEMES:
            raise PolicyError(
                f"라우트 '{r.hostname}': 비-HTTP 서비스('{r.scheme or '미지정'}')에는 "
                f"`access: public` 을 허용하지 않습니다. RDP/SSH/TCP 는 반드시 "
                f"Access 로 보호하세요(`access: required`)."
            )


def audit_exposure(state: DesiredState) -> list[str]:
    """desired-state 자체의 노출 위험을 경고 목록으로 표면화한다."""
    warnings: list[str] = []
    for r in state.routes:
        if r.access == "public":
            warnings.append(
                f"⚠️  {r.hostname} → {r.service} 는 PUBLIC 입니다(Access 없음). "
                f"원본 서비스 자체 인증·보안에만 의존합니다."
            )
        if r.scheme and r.scheme not in KNOWN_SCHEMES:
            warnings.append(
                f"⚠️  {r.hostname}: 알 수 없는 서비스 스킴 '{r.scheme}' — 확인하세요."
            )
    return warnings


def build_ingress(state: DesiredState) -> list[dict]:
    """cloudflared config.yml 의 ingress 목록(catch-all 404 가 마지막)."""
    rules: list[dict] = [
        {"hostname": r.hostname, "service": r.service} for r in state.routes
    ]
    rules.append({"service": "http_status:404"})
    return rules


def build_config_yaml(
    state: DesiredState, tunnel_id: str, credentials_file: str | None = None
) -> str:
    """desired-state → cloudflared config.yml (YAML 문자열).

    값에 YAML 특수문자가 없는 단순 구조라 stdlib 로 결정론적으로 직렬화한다.
    `cloudflared tunnel ingress validate` 로 교차검증할 수 있다.
    """
    lines = [f"tunnel: {tunnel_id}"]
    if credentials_file:
        lines.append(f"credentials-file: {credentials_file}")
    lines.append("ingress:")
    for rule in build_ingress(state):
        if "hostname" in rule:
            lines.append(f"  - hostname: {rule['hostname']}")
            lines.append(f"    service: {rule['service']}")
        else:
            lines.append(f"  - service: {rule['service']}")
    return "\n".join(lines) + "\n"


def build_dns_plan(state: DesiredState, tunnel_id: str) -> list[dict]:
    """각 라우트 hostname → 터널 CNAME(proxied) 계획.

    실제 적용은 reconcile 가 `cloudflared tunnel route dns` 또는 REST 로 수행한다.
    tunnel_id 는 터널 UUID 이며 호출자가 `cloudflared tunnel list` 에서 해석해 넘긴다.
    """
    target = f"{tunnel_id}.cfargotunnel.com"
    return [
        {"hostname": r.hostname, "type": "CNAME", "content": target, "proxied": True}
        for r in state.routes
    ]


def build_access_plan(state: DesiredState) -> list[dict]:
    """Access 애플리케이션이 필요한 라우트(= required)의 계획."""
    apps: list[dict] = []
    for r in state.routes:
        if r.access != "required":
            continue
        apps.append({"hostname": r.hostname, "policy": r.policy or state.default_policy})
    return apps


def detect_access_drift(
    state: DesiredState, live_access_hostnames: list[str]
) -> list[str]:
    """라이브 Access 앱 집합과 desired 보호 집합을 비교해 미보호 노출을 경고한다."""
    live = set(live_access_hostnames)
    warnings: list[str] = []
    for r in state.routes:
        if r.access == "required" and r.hostname not in live:
            warnings.append(
                f"⚠️  {r.hostname} 는 required 이지만 Access 애플리케이션이 없습니다 "
                f"— 보호되지 않은 채 노출 중입니다!"
            )
    return warnings


def _render_text(cmd: str, state: DesiredState, tunnel_id: str) -> str:
    lines = [f"# tunnel: {state.tunnel}", ""]
    if cmd == "plan":
        lines.append("## ingress (cloudflared config.yml)")
        for rule in build_ingress(state):
            if "hostname" in rule:
                lines.append(f"  - {rule['hostname']} -> {rule['service']}")
            else:
                lines.append(f"  - (catch-all) -> {rule['service']}")
        lines.append("")
        lines.append("## DNS (CNAME -> tunnel)")
        for d in build_dns_plan(state, tunnel_id):
            lines.append(f"  - {d['hostname']} CNAME {d['content']} (proxied)")
        lines.append("")
        lines.append("## Access 애플리케이션 (required 라우트)")
        access = build_access_plan(state)
        if not access:
            lines.append("  (없음 — 모든 라우트가 public)")
        for a in access:
            lines.append(f"  - {a['hostname']} : {a['policy'] or '<정책 미지정>'}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="cloudflare-tunnel desired-state 정책/계획 도구"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "audit", "config"):
        sp = sub.add_parser(name)
        sp.add_argument("state_file", help="desired-state JSON 파일 경로")
        sp.add_argument("--tunnel-id", default="<TUNNEL_ID>", help="터널 UUID")
        if name == "config":
            sp.add_argument(
                "--credentials-file", default=None, help="터널 자격증명 JSON 경로"
            )
        else:
            sp.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
        state = parse_state(data)
        enforce_policy(state)
    except PolicyError as exc:
        print(f"정책 위반: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1

    if args.cmd == "config":
        # config.yml 은 stdout 으로만 출력(cloudflared 가 그대로 소비/검증).
        print(
            build_config_yaml(state, args.tunnel_id, args.credentials_file), end=""
        )
        for w in audit_exposure(state):
            print(w, file=sys.stderr)
        return 0

    warnings = audit_exposure(state)
    if args.cmd == "audit":
        payload: dict = {"warnings": warnings}
    else:
        payload = {
            "tunnel": state.tunnel,
            "ingress": build_ingress(state),
            "dns": build_dns_plan(state, args.tunnel_id),
            "access": build_access_plan(state),
            "warnings": warnings,
        }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.cmd == "audit":
        print("\n".join(warnings) if warnings else "노출 경고 없음.")
    else:
        print(_render_text("plan", state, args.tunnel_id))
    for w in warnings:
        print(w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
