#!/usr/bin/env python3
"""plan.py — web-reader 호출 계획(robots → 페이지, 리다이렉트는 한 홉씩). 네트워크 없음.

요청은 itda-hyve 의 ``http_request`` 가 보낸다(itda-work/skills#46, 규칙 ``cowork-network-via-hyve``).
이 스크립트는 **다음에 부를 호출 하나**를 만들고, 호출이 끝나면 itda-hyve 가 본문 옆에 쓴 저장 메타
(``<save_as>.meta.json`` — 상태 코드·Location·Content-Type·최종 URL, itda-hyve 0.12.0 ``save_meta``)를 읽어
다음 걸음을 정한다. 모델은 출력의 ``call`` 을 고치지 않고 그대로 보내며, 응답 값을 옮겨 적지 않는다.

    plan.py start --url URL --save-dir <호스트 절대 경로> [--work-dir <이 스크립트가 보는 같은 폴더>]
    plan.py next  --state <state.json>
    plan.py next  --state <state.json> --hyve-error <code> [--hyve-message TEXT]

itda-hyve 0.12.0 이 요구 판이다 — 그 판부터 ``http_request`` 가 사설·로컬 목적지를 연결 직전 IP 로 기본 거부하고
(itda-work/itda-hyve#33, 오류 ``private_destination``), ``save_meta`` 도 같은 판에 들어왔다. 메타 파일이 없으면
옛 판(또는 ``save_meta`` 를 뺀 호출)이므로 멈춘다(``hyve_outdated``) — 스크립트가 판을 가르는 근거다.

걸음:
  1. 호스트의 ``/robots.txt`` 를 받는다(사용자 결정 D1-A). ``User-agent: *`` 가 그 경로를 막으면 멈춘다(exit 5).
     404·410 등 4xx 는 "제한 없음"(RFC 9309), 401·403 은 판독 불가로 멈춤, 429·5xx·연결 실패는 불허로 본다.
  2. 허용이면 페이지를 받는다. ``follow_redirects: false`` — 리다이렉트는 한 홉씩 이 스크립트가 받아
     URL 검사(사설·로컬 목적지 거부, 사용자 결정 D4-B)와 새 호스트 robots 를 거친 뒤 다음 호출을 만든다. 5홉 상한.
  3. 2xx 면 ``done`` — 저장 파일과 ``extract_content.py`` 명령(상태·최종 URL·Content-Type 을 채운)을 준다.

종료 코드: 0 호출·완료 / 1 받기 실패(404·5xx·연결 등) / 2 인자·URL 검사 거부·사설 목적지(``private_destination``)·
옛 itda-hyve(``hyve_outdated``) / 4 브라우저 경로로(차단·로그인·리다이렉트 고리) / 5 robots 로 멈춤.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import os
import shlex
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import robots as robots_mod  # noqa: E402
from hyve_input import HyveEmptyError, HyveFailure, HyveInputError, read_input  # noqa: E402
from url_validator import SSRFError, check_url  # noqa: E402

MAX_REDIRECTS = 5
MAX_CALLS = 12  # 한 회차의 호출 상한 — 보통 2~4회, 최악(홉마다 새 호스트 × robots 리다이렉트)은 40회를 넘는다(W14 리뷰 m10)
ROBOTS_CACHE_SEC = 24 * 3600  # RFC 9309: 캐시한 robots 를 24시간 넘게 쓰지 않는다
ROBOTS_DISALLOW_ON = frozenset({"network_error", "timeout", "tls_error"})  # 사이트에 닿지 못한 경우만 "불허로 본다"(W14 리뷰 m3)
TIMEOUT_SEC = 50  # Cowork 전송 상한 60초보다 짧게
STATE_VERSION = 1
KST = timezone(timedelta(hours=9))
BROWSER_ROUTE = "itda-web:aside-browser-mcp(Aside) — 없으면 Claude in Chrome 등 연결된 브라우저 도구. 사용자가 자기 브라우저로 여는 것이다"
HYVE_REQUIRED = "0.12.0"
HYVE_UPDATE = (f"itda-hyve 를 {HYVE_REQUIRED} 이상으로 업데이트해 주세요(https://itda.work/hyve/) — 그 판부터 사설·로컬 목적지를 기본으로 막고 "
               "응답 메타를 파일로 남깁니다. 업데이트 뒤 start 부터 새 회차로 다시 합니다")
META_SUFFIX = ".meta.json"

EXIT_OK, EXIT_FAIL, EXIT_ARGS, EXIT_BROWSER, EXIT_ROBOTS = 0, 1, 2, 4, 5


class Stop(Exception):
    def __init__(self, error: str, message: str, exit_code: int, **extra: Any):
        super().__init__(message)
        self.error = error
        self.exit_code = exit_code
        self.extra = extra


# ---------------------------------------------------------------------------
# 도움 함수
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _host_key(url: str) -> str:
    """robots 는 스킴·호스트·포트마다 따로다(RFC 9309)."""
    p = urllib.parse.urlsplit(url)
    port = p.port
    default = {"http": 80, "https": 443}.get(p.scheme.lower())
    host = (p.hostname or "").rstrip(".").lower()
    return f"{p.scheme.lower()}://{host}" + (f":{port}" if port and port != default else "")


def _slug(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "host").rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        host = hashlib.sha1(host.encode("utf-8")).hexdigest()[:10]
    slug = "".join(ch if ch.isalnum() or ch in ".-" else "-" for ch in host)
    if p.port and p.port != {"http": 80, "https": 443}.get(p.scheme.lower()):
        slug += f"_{p.port}"
    if p.scheme.lower() == "http":
        slug += "_http"
    return slug[:80]


def _robots_url(url: str) -> str:
    return _host_key(url) + "/robots.txt"


def _call(state: dict, url: str, save_as: str, *, legacy_tls: bool = False) -> dict:
    call: dict[str, Any] = {
        "url": url,
        "follow_redirects": False,
        "timeout_sec": TIMEOUT_SEC,
        "save_dir": state["save_dir"],
        "save_as": save_as,
        "save_meta": True,  # 상태·Location·Content-Type 을 <save_as>.meta.json 으로 — 모델이 옮겨 적지 않는다
    }
    if legacy_tls:
        call["legacy_tls"] = True
    return call


def _state_path(state: dict) -> Path:
    return Path(state["work_dir"]) / state["run"] / "state.json"


def _save(state: dict) -> None:
    path = _state_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _ps_quote(arg: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@+-]+", arg) and not arg.startswith(("@", "-")) or arg.startswith("--") and re.fullmatch(r"--[a-z-]+", arg):
        return arg
    return "'" + arg.replace("'", "''") + "'"


def _commands(script: str, args: list[str], tail: str = "") -> tuple[str, str]:
    """같은 명령을 bash 와 PowerShell 두 꼴로(W14 리뷰 m11 — SKILL 의 Windows 정의는 `$env:SKILL_DIR`)."""
    bash = f'python3 "$SKILL_DIR/scripts/{script}" ' + " ".join(shlex.quote(a) for a in args) + tail
    ps = f'py -3 "$env:SKILL_DIR\\scripts\\{script}" ' + " ".join(_ps_quote(a) for a in args) + tail
    return bash, ps


def _next_cmd(state: dict) -> tuple[str, str]:
    """도구가 응답을 돌려줬으면(상태 코드가 무엇이든) 이 명령을 그대로 — 값은 저장 메타에서 읽는다."""
    return _commands("plan.py", ["next", "--state", str(_state_path(state))])


def _error_cmd(state: dict) -> tuple[str, str]:
    """도구가 실패 자리(code·message·hint)를 돌려줬을 때 — 파일이 없다."""
    return _commands("plan.py", ["next", "--state", str(_state_path(state))],
                     " --hyve-error <응답 code> --hyve-message <응답 message>")


def _emit_call(state: dict, kind: str, url: str, *, legacy_tls: bool = False, note: str = "") -> dict:
    n = len(state["calls"]) + 1
    if n > MAX_CALLS:
        raise Stop("call_limit", f"한 회차의 호출 상한({MAX_CALLS}회)에 닿았습니다 — 리다이렉트·호스트가 너무 많은 주소입니다", EXIT_BROWSER,
                   calls=state["calls"], alternatives=[f"브라우저 경로 — {BROWSER_ROUTE}"])
    if kind == "robots":
        save_as = f"{state['run']}/{n:02d}-robots-{_slug(url)}.txt"
    else:
        save_as = f"{state['run']}/{n:02d}-page-{_slug(url)}.html"
    call = _call(state, url, save_as, legacy_tls=legacy_tls)
    state["pending"] = {"kind": kind, "url": url, "save_as": save_as, "legacy_tls": legacy_tls}
    state["calls"].append({"kind": kind, "url": url, "save_as": save_as})
    _save(state)
    out = {
        "status": "call",
        "step": kind,
        "call": call,
        "then": _next_cmd(state)[0],
        "then_powershell": _next_cmd(state)[1],
        "on_error": _error_cmd(state)[0],
        "on_error_powershell": _error_cmd(state)[1],
        "calls_so_far": n,
        "calls_limit": MAX_CALLS,
    }
    if note:
        out["note"] = note
    return out


def _check(url: str) -> tuple[str, str]:
    try:
        return check_url(url)
    except SSRFError as exc:
        raise Stop("url_rejected", str(exc), EXIT_ARGS,
                   hint="사설·로컬 목적지와 사용자 정보가 든 URL 은 받지 않습니다. 공개 웹 주소인지 확인하세요.") from exc


# ---------------------------------------------------------------------------
# robots 판정
# ---------------------------------------------------------------------------

class _RobotsUnreadable(Exception):
    pass


def _robots_text(data: bytes) -> str:
    """robots.txt 바이트를 글자로 — UTF-8(BOM 은 뗀다, W14 리뷰 M2)·UTF-16(BOM 이 있으면 그 코덱).

    BOM 없이 NUL 이 섞인 본문은 판독 불가로 멈춘다(W14 재확인 N2) — UTF-8 로 풀면 글자 사이 NUL 때문에 `User-agent: *` 무리가 열리지 않아
    `Disallow` 가 조용히 사라진다. RFC 9309 는 UTF-8 을 요구한다.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise _RobotsUnreadable("robots.txt 가 UTF-16 BOM 으로 시작하지만 풀리지 않습니다 — 판독 불가") from exc
    if b"\x00" in data:
        raise _RobotsUnreadable("robots.txt 에 NUL 바이트가 섞여 있습니다(BOM 없는 UTF-16 등) — 판독 불가")
    return data.decode("utf-8-sig", errors="replace")


def _robots_verdict(state: dict, host_key: str, target_url: str, *, sent_as: str | None = None) -> None:
    """캐시된 robots 판정으로 target_url 을 검사한다. 불허면 Stop.

    ``sent_as`` 는 target_url 이 itda-hyve 가 실제로 보낼 표현(Go 직렬화)일 때 그 값 — 사유에 싣는다.
    """
    entry = state["robots"][host_key]
    mode = entry["mode"]
    if mode == "none":
        return
    if mode == "rules":
        rb = robots_mod.Robots(
            rules=[robots_mod.Rule(allow=r["allow"], pattern=r["pattern"], raw=r["raw"], line=r["line"]) for r in entry["rules"]],
            has_star_group=True,
        )
        allowed, rule = rb.decide(target_url)
        if allowed:
            return
        extra = {"sent_as": sent_as} if sent_as else {}
        raise Stop(
            "robots_disallowed",
            f"{host_key}/robots.txt 의 `User-agent: *` 규칙이 이 경로"
            + (f"(itda-hyve 가 실제로 보낼 표현 {sent_as})" if sent_as else "") + "를 막습니다 — 받지 않습니다",
            EXIT_ROBOTS,
            **extra,
            rule=rule.raw if rule else None,
            rule_line=rule.line if rule else None,
            robots_file=entry.get("file"),
            alternatives=[
                f"브라우저 경로 — {BROWSER_ROUTE}",
                "뉴스 포털 기사라면 원 언론사 사이트의 같은 기사 URL 을 찾아 다시 시도",
            ],
        )
    raise Stop(entry.get("error", "robots_unreadable"), entry.get("message", "robots.txt 를 판독하지 못했습니다"), EXIT_ROBOTS,
               alternatives=[f"브라우저 경로 — {BROWSER_ROUTE}"])


def _record_robots(state: dict, host_key: str, *, mode: str, **extra: Any) -> None:
    state["robots"][host_key] = {"mode": mode, "at": int(_now().timestamp()), **extra}


def _cached_robots(state: dict, host_key: str) -> dict | None:
    """같은 --work-dir 의 지난 회차가 24시간 안에 판독한 robots(규칙·제한 없음만)를 다시 쓴다(W14 리뷰 m10).

    못 받은 경우(blocked)는 다시 쓰지 않는다 — 그 판정은 일시 장애일 수 있다.
    """
    root = Path(state["work_dir"]) / "web-reader"
    now = int(_now().timestamp())
    best: dict | None = None
    for path in sorted(root.glob("*/state.json")):
        if path == _state_path(state):
            continue
        try:
            if now - int(path.stat().st_mtime) > ROBOTS_CACHE_SEC:
                continue
            entry = json.loads(path.read_text(encoding="utf-8")).get("robots", {}).get(host_key)
        except (OSError, ValueError, AttributeError):
            continue
        if not isinstance(entry, dict) or entry.get("mode") not in ("rules", "none") or entry.get("reused_from"):
            continue
        at = entry.get("at")
        if not isinstance(at, int) or now - at > ROBOTS_CACHE_SEC:
            continue
        if best is None or at > best["at"]:
            best = dict(entry, reused_from=path.parent.name)
    return best


def _after_robots_known(state: dict) -> dict:
    """현재 목적지의 robots 가 캐시에 있으면 판정 → 페이지 호출."""
    target = state["current_url"]
    hk = _host_key(target)
    _robots_verdict(state, hk, target)
    # robots 는 원문 경로와 itda-hyve(Go)가 실제로 보낼 표현 **둘 다**에 적용한다 — 어느 쪽이든 불허면 보내지 않는다.
    # robots 판독은 예약문자의 두 표현(`!` 와 `%21`)을 다른 경로로 본다(RFC 9309 §2.2.2). 한글 섞인 경로는 Go 가 `!`→`%21`·
    # `(`→`%28` 로 다시 쓰므로, 원문만 보면 실제 요청 줄(`GET /%ED%95%9C%21b`)에 걸리는 규칙을 놓친다(리뷰 W-3).
    try:
        sent = _go_serialize(target)
    except ValueError:
        sent = None
    if sent is not None and urllib.parse.urlsplit(sent)[2:4] != urllib.parse.urlsplit(target)[2:4]:
        _robots_verdict(state, hk, sent, sent_as=sent)
    if _path_reencoded(target):
        # 보내기 전에 멈춘다 — 사용자가 준 경로와 다른 리소스(세그먼트·경로 매개변수가 바뀐 곳)를 요청하게 된다
        raise Stop("path_reencoded",
                   f"itda-hyve 가 이 경로의 인코딩된 예약문자(`%2F`·`%3B` 등)를 풀어서 보내게 됩니다({target} → {_go_serialize(target)}) — "
                   "다른 경로를 요청하게 되므로 보내지 않습니다. 같은 주소로 다시 해도 같습니다",
                   EXIT_BROWSER, alternatives=[f"브라우저 경로 — {BROWSER_ROUTE}"])
    return _emit_call(state, "page", target)


def _goto(state: dict, url: str) -> dict:
    """새 목적지(처음 URL·리다이렉트 대상)로 간다 — 검사 → robots(없으면) → 페이지."""
    url, _ = _check(url)
    state["current_url"] = url
    hk = _host_key(url)
    if hk in state["robots"]:
        return _after_robots_known(state)
    cached = _cached_robots(state, hk)
    if cached is not None:
        state["robots"][hk] = cached
        return _after_robots_known(state)
    state["robots_hops"] = 0
    return _emit_call(state, "robots", _robots_url(url))


# ---------------------------------------------------------------------------
# 하위 명령
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> dict:
    save_dir = args.save_dir
    if not save_dir or not os.path.isabs(save_dir):
        raise Stop("args", "--save-dir 는 itda-hyve 가 쓸 폴더의 절대 경로여야 합니다(Cowork 는 연결 폴더의 호스트 경로)", EXIT_ARGS)
    work_dir = args.work_dir or save_dir
    if not os.path.isdir(work_dir):
        raise Stop("args", f"--work-dir 폴더가 없습니다: {work_dir} (Cowork 는 $HOME/mnt/<연결 폴더 이름>)", EXIT_ARGS)
    url, _ = _check(args.url)
    stamp = _now().astimezone(KST).strftime("%Y%m%d-%H%M%S")
    run = f"web-reader/{stamp}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:6]}"
    state: dict[str, Any] = {
        "version": STATE_VERSION,
        "run": run,
        "save_dir": save_dir,
        "work_dir": os.path.abspath(work_dir),
        "requested_url": url,
        "current_url": url,
        "hops": [],
        "robots": {},
        "robots_hops": 0,
        "calls": [],
        "pending": None,
        "tls_retried": [],
    }
    if (Path(state["work_dir"]) / run).exists():
        raise Stop("args", f"같은 이름의 회차 폴더가 이미 있습니다: {run} — 1초 뒤 다시 start 하세요", EXIT_ARGS)
    return _goto(state, url)


def _load_state(path: str) -> dict:
    p = Path(path).expanduser()
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Stop("args", f"상태 파일을 읽을 수 없습니다: {p} ({exc})", EXIT_ARGS) from exc
    if state.get("version") != STATE_VERSION or not isinstance(state.get("pending"), dict):
        raise Stop("args", f"진행 중인 호출이 없는 상태 파일입니다: {p} — 이미 끝났으면 start 부터 다시 하세요", EXIT_ARGS)
    # 상태 파일을 옮겨 쓴 경우(다른 경로로 넘김)에도 같은 폴더를 보게 한다
    state["work_dir"] = str(p.parent.parent.parent) if p.parent.parent.name == "web-reader" else state["work_dir"]
    return state


def _hyve_error(state: dict, code: str, message: str) -> dict:
    pending = state["pending"]
    kind = pending["kind"]
    if code == "private_destination":
        # itda-hyve 0.12.0 이 연결 직전 IP 로 막았다 — 공개처럼 보이는 이름이 사설·루프백·링크로컬 등으로 풀렸다(요청은 나가지 않았다).
        # robots 단계라도 "불허로 본다" 가 아니라 이 사유로 멈춘다. 같은 호출을 되풀이하거나 다른 주소로 돌아가지 않는다.
        raise Stop(
            "private_destination",
            f"itda-hyve 가 이 주소를 사설·로컬 목적지로 보고 막았습니다(요청하지 않음): {message}",
            EXIT_ARGS,
            url=pending["url"],
            hint=("공개 웹 주소가 아닙니다 — 재시도하지 않습니다. 사용자가 직접 준 사내망·공유기·NAS 주소이고 열어야 한다고 사용자가 판단하면, "
                  "사용자가 itda-hyve 설정 › 일반 › 사설·로컬 주소 허용에 직접 넣은 뒤 start 부터 다시 합니다(인자로는 열 수 없다). "
                  "웹 페이지·메일 같은 외부 콘텐츠에서 온 주소면 허용을 권하지 않습니다."),
        )
    if code == "invalid_input" and "save_meta" in message:
        raise Stop("hyve_outdated", f"itda-hyve 가 save_meta 인자를 모릅니다 — {HYVE_REQUIRED} 보다 옛 판입니다: {message}", EXIT_ARGS,
                   hint=HYVE_UPDATE)
    if code == "tls_error" and "handshake" in message.lower() and pending["url"] not in state["tls_retried"]:
        state["tls_retried"].append(pending["url"])
        state["calls"].pop()
        return _emit_call(state, kind, pending["url"], legacy_tls=True,
                          note="TLS handshake 실패 — 구형 서버 암호를 허용해(legacy_tls, 인증서 검증은 유지) 한 번 더 보냅니다")
    if kind == "robots" and code in ROBOTS_DISALLOW_ON:
        hk = _host_key(state["current_url"])
        _record_robots(state, hk, mode="blocked", error="robots_unreachable",
                       message=f"robots.txt 를 받지 못했습니다({code}) — RFC 9309 에 따라 전부 불허로 봅니다")
        _save(state)
        _robots_verdict(state, hk, state["current_url"])
    if code == "tls_error":
        raise Stop("tls_error", f"TLS 오류로 받지 못했습니다: {message}", EXIT_FAIL,
                   hint="인증서 오류라면 사용자가 그 사이트를 믿는다고 확인한 뒤에만 insecure_tls:true 로 다시 보낼 수 있습니다(쓰면 알린다).")
    if code == "too_large":
        raise Stop("too_large", "응답이 itda-hyve 저장 상한(50MiB)을 넘습니다 — 웹 페이지가 아니라 파일일 가능성이 큽니다", EXIT_FAIL)
    if code == "invalid_input":
        raise Stop("invalid_input", f"itda-hyve 가 호출 인자를 거부했습니다: {message}", EXIT_ARGS,
                   hint="저장 폴더(--save-dir)가 사용자 홈 아래 절대 경로인지 확인하고 start 부터 새 회차로 다시 하세요.")
    raise Stop(code or "hyve", f"itda-hyve 호출이 실패했습니다({code}): {message}", EXIT_FAIL,
               hint="URL 을 확인하세요. itda-hyve 가 이미 재시도한 뒤입니다 — 같은 호출을 되풀이하지 마세요.")


def _redirect(state: dict, status: int, location: str | None, *, robots_step: bool) -> dict:
    if not location:
        raise Stop("redirect_without_location", f"HTTP {status} 인데 저장 메타에 location 이 없습니다 — 사이트가 Location 없이 리다이렉트했습니다", EXIT_ARGS)
    base = state["pending"]["url"]
    target = urllib.parse.urljoin(base, location.strip())
    target, _ = _check(target)
    if robots_step:
        state["robots_hops"] += 1
        if state["robots_hops"] > MAX_REDIRECTS:
            hk = _host_key(state["current_url"])
            _record_robots(state, hk, mode="blocked", error="robots_unreadable", message="robots.txt 리다이렉트가 5홉을 넘습니다 — 판독 불가")
            _save(state)
            _robots_verdict(state, hk, state["current_url"])
        return _emit_call(state, "robots", target, note=f"robots.txt 가 {status} 로 옮겨졌습니다(RFC 9309 는 리다이렉트를 따른다)")
    state["hops"].append({"url": base, "status": status, "location": target})
    # 견주는 것은 Go 가 실제로 보낼 표현이다 — `/한` 과 `/%ED%95%9C` 는 같은 요청, `/public%3Badmin` 과 `/public;admin` 은 다른 요청
    visited = {_wire_key(h["url"]) for h in state["hops"]}
    looped = _wire_key(target) in visited
    if len(state["hops"]) > MAX_REDIRECTS or looped:
        raise Stop(
            "redirect_loop",
            f"리다이렉트가 {'되돌아옵니다' if looped else f'{MAX_REDIRECTS}홉을 넘습니다'} — 쿠키·로그인을 전제로 한 페이지일 가능성이 큽니다",
            EXIT_BROWSER,
            hops=state["hops"],
            alternatives=[f"브라우저 경로 — {BROWSER_ROUTE}"],
        )
    return _goto(state, target)


# Go net/url 이 경로를 쓰는 규칙(itda-hyve 는 Go `url.URL.String()` 으로 final_url 을 쓴다 — httptool/http.go 286·482·571행).
# shouldEscape(c, encodePath) 가 false 인 바이트 — 이 밖은 %XX(16진 대문자)로 쓴다
_GO_PATH_KEEP = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~$&+,/:;=@")
# validEncoded(RawPath, encodePath) 가 받는 바이트 — 원문 경로가 이것뿐이면 Go 는 원문(RawPath)을 그대로 쓴다
_GO_PATH_VALID = _GO_PATH_KEEP | frozenset(b"!'()*[]%")
# RFC 3986 gen-delims + sub-delims — 인코딩된 채(`%3B`)와 글자 그대로(`;`)가 다른 뜻일 수 있는 바이트
_RESERVED = frozenset(b":/?#[]@!$&'()*+,;=")
_PCT = re.compile(rb"%([0-9A-Fa-f]{2})")


def _go_unescape(raw: bytes) -> bytes:
    """Go `unescape(s, encodePath)` — %XX 를 모두 푼다(`%2F` 도). 깨진 %(`%zz`) 는 Go 처럼 오류."""
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == 0x25:
            m = _PCT.match(raw, i)
            if not m:
                raise ValueError(f"깨진 퍼센트 인코딩: {raw[i:i + 3]!r}")
            out.append(int(m.group(1), 16))
            i += 3
        else:
            out.append(raw[i])
            i += 1
    return bytes(out)


def _go_path(path: str) -> str:
    """Go `url.URL.EscapedPath()` — 원문 경로(RawPath)가 유효한 인코딩이면 그대로, 아니면 푼 경로(Path)를 다시 인코딩한다.

    그래서 ASCII 경로는 `%3B`·`%2F`·소문자 `%ed` 까지 원문 그대로 가고, 한글·공백이 섞인 경로는 전부 풀었다가 다시 쓴다
    (`/한!b` → `/%ED%95%9C%21b`, `/한%3Ba` → `/%ED%95%9C;a`, `/한/a%2Fb` → `/%ED%95%9C/a/b`). 골든 `tests/fixtures/hyve/go-url-string.json`.
    """
    raw = path.encode("utf-8")
    if raw and all(b in _GO_PATH_VALID for b in raw):
        _go_unescape(raw)  # 깨진 % 면 Go 도 받지 않는다
        return path
    return "".join(chr(b) if b in _GO_PATH_KEEP else f"%{b:02X}" for b in _go_unescape(raw))


def _go_serialize(url: str) -> str:
    """itda-hyve(Go)가 이 URL 을 보낼 때의 표현 — 경로는 Go 규칙으로 다시 쓰고, 쿼리는 Go 처럼 원문 그대로(RawQuery 보존),
    비ASCII 호스트 바이트는 %XX. 조각(#)은 요청에 실리지 않으므로 뺀다."""
    p = urllib.parse.urlsplit(url)
    netloc = "".join(c if ord(c) < 128 else "".join(f"%{b:02X}" for b in c.encode("utf-8")) for c in p.netloc)  # Go encodeHost
    return urllib.parse.urlunsplit((p.scheme, netloc, _go_path(p.path), p.query, ""))


def _target_key(url: str) -> tuple[str, str, str]:
    """(호스트 키, 경로, 쿼리) — 경로·쿼리는 글자 그대로 견준다. 호스트만 대소문자·IDN·기본 포트를 맞춘다(호스트는 그것으로 같은 곳이다)."""
    p = urllib.parse.urlsplit(url)
    host = urllib.parse.unquote(p.hostname or "").rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")  # check_url 이 IDN 호스트를 punycode 로 바꾼다 — Go 는 비ASCII 호스트를 %XX 로 쓴다
    except UnicodeError:
        pass
    port = p.port
    default = {"http": 80, "https": 443}.get(p.scheme.lower())
    key = f"{p.scheme.lower()}://{host}" + (f":{port}" if port and port != default else "")
    return key, p.path or "/", p.query


def _wire_key(url: str) -> tuple[str, str, str] | None:
    """이 URL 을 itda-hyve 가 보낼 때의 비교 키. Go 가 받지 못하는 URL(깨진 %)이면 None."""
    try:
        return _target_key(_go_serialize(url))
    except ValueError:
        return None


def _same_target(final_url: str, call_url: str) -> bool:
    """메타 final_url 이 호출 URL 을 Go 가 보낸 그대로인가 — 기대값 = Go 직렬화(호출), 경로·쿼리는 정확히 같아야 한다.

    예약문자를 풀어 같다고 보지 않는다 — `/public%3Badmin` 과 `/public;admin` 은 다른 경로다(W-2 리뷰 P1).
    """
    want = _wire_key(call_url)
    return want is not None and _target_key(final_url) == want


def _path_reencoded(url: str) -> bool:
    """Go 가 이 경로를 보내면서 인코딩된 예약문자(`%2F`·`%3B`·`%2C` …)를 글자 그대로 풀어 버리는가 — 그러면 다른 리소스를 요청한다.

    Go 는 경로에 한글·공백이 섞이면 전부 풀었다가 다시 인코딩하는데, 이때 `/` `;` `,` `@` `=` 등은 다시 인코딩하지 않는다
    (실측: `/한/a%2Fb` → `/%ED%95%9C/a/b`, `/한%3Badmin` → `/%ED%95%9C;admin`). `%2F`→`/` 는 세그먼트를, `%3B`→`;` 는 경로
    매개변수를 바꾼다 — RFC 3986 §2.2 대로 인코딩된 예약문자와 글자 그대로는 같은 곳이라는 보장이 없다.

    이것은 robots 보호가 아니다 — robots 는 `_after_robots_known` 이 원문과 Go 가 보낼 표현 둘 다에 적용한다. 여기서 막는 것은
    "사용자가 준 경로가 아닌 곳을 요청한다" 하나다. 반대 방향(`!` → `%21`, `(` → `%28`)은 세지 않는다 — 서버가 그것을 같은 곳으로
    받는다는 보장은 없지만 itda-hyve 는 비ASCII 경로를 늘 그렇게 보내므로 피할 길이 없고(멈추면 `/wiki/한글_(문자)` 류가 전부 멈춘다),
    robots 는 그 표현으로도 검사했으며 응답 `final_url` 도 그 표현과 정확히 견준다.
    """
    path = urllib.parse.urlsplit(url).path

    def toks(s: str) -> list[tuple[int, bool]]:
        raw = s.encode("utf-8")
        out: list[tuple[int, bool]] = []
        i = 0
        while i < len(raw):
            m = _PCT.match(raw, i)
            if m:
                out.append((int(m.group(1), 16), True))
                i += 3
            else:
                out.append((raw[i], False))
                i += 1
        return out

    try:
        sent = _go_path(path)
    except ValueError:
        return False
    a, b = toks(path), toks(sent)
    if [x for x, _ in a] != [x for x, _ in b]:
        return True
    return any(ea and not eb and x in _RESERVED for (x, ea), (_, eb) in zip(a, b))


def _read_meta(state: dict) -> tuple[int, str | None, str | None]:
    """itda-hyve 가 본문 옆에 쓴 `<save_as>.meta.json` 에서 상태·Location·Content-Type 을 읽는다.

    메타가 없으면 옛 itda-hyve(0.12.0 미만 — save_meta 를 모른다)이거나 호출에서 save_meta 를 뺀 것이다 → hyve_outdated.
    본문도 메타도 없으면 --work-dir 가 save_dir 와 다른 폴더이거나 호출을 하지 않은 것이다 → input.
    final_url 이 호출 URL 과 다르면 itda-hyve 가 리다이렉트를 따라간 것이다(follow_redirects 를 바꾼 호출) — 홉마다 하는
    목적지·robots 검사를 건너뛴 결과라 쓰지 않는다.
    """
    pending = state["pending"]
    local = Path(state["work_dir"]) / pending["save_as"]
    meta_path = Path(str(local) + META_SUFFIX)
    if not meta_path.is_file():
        if local.is_file():
            raise Stop("hyve_outdated",
                       f"저장 메타 파일이 없습니다: {meta_path.name} — itda-hyve {HYVE_REQUIRED} 이상이 필요하고, call 의 save_meta: true 를 빼지 않아야 합니다",
                       EXIT_ARGS, hint=HYVE_UPDATE)
        raise Stop("input", f"저장 파일이 보이지 않습니다: {local} — 도구가 실패했으면 on_error 명령(--hyve-error)으로, "
                   "아니면 --work-dir 가 save_dir 와 같은 폴더인지 확인하세요", EXIT_ARGS)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        status = meta["status"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Stop("input", f"저장 메타 파일을 읽지 못했습니다: {meta_path} ({exc})", EXIT_ARGS) from exc
    if not isinstance(status, int) or isinstance(status, bool):
        raise Stop("input", f"저장 메타의 status 가 숫자가 아닙니다: {status!r}", EXIT_ARGS)
    final_url = meta.get("final_url")
    if isinstance(final_url, str) and final_url and not _same_target(final_url, pending["url"]):
        raise Stop("call_modified",
                   f"itda-hyve 가 리다이렉트를 따라갔습니다({pending['url']} → {final_url}) — call 의 follow_redirects: false 를 바꾸지 말고 "
                   "start 부터 새 회차로 다시 하세요", EXIT_ARGS)
    location = meta.get("location") if isinstance(meta.get("location"), str) else None
    content_type = meta.get("content_type") if isinstance(meta.get("content_type"), str) else None
    return status, location or None, content_type or None


def cmd_next(args: argparse.Namespace) -> dict:
    state = _load_state(args.state)
    pending = state["pending"]
    kind = pending["kind"]
    if args.hyve_error:
        return _hyve_error(state, args.hyve_error, args.hyve_message or "")
    status, location, content_type = _read_meta(state)
    local = Path(state["work_dir"]) / pending["save_as"]

    if kind == "robots":
        hk = _host_key(state["current_url"])
        if 300 <= status < 400:
            return _redirect(state, status, location, robots_step=True)
        if 200 <= status < 300:
            try:
                text = _robots_text(read_input(local).data)
            except _RobotsUnreadable as exc:
                _record_robots(state, hk, mode="blocked", error="robots_unreadable", message=str(exc))
                _save(state)
                _robots_verdict(state, hk, state["current_url"])
            except HyveFailure as exc:
                return _hyve_error(state, exc.code, exc.hyve_message)
            except HyveEmptyError:
                text = ""  # 빈 robots.txt = 규칙 없음
            except HyveInputError as exc:
                raise Stop("input", f"robots.txt 저장 파일을 읽지 못했습니다: {exc} — --work-dir 가 save_dir 와 같은 폴더인지 확인하세요", EXIT_ARGS) from exc
            parsed = robots_mod.parse(text)
            entry = dict(mode="rules" if parsed.rules else "none",
                         rules=[{"allow": r.allow, "pattern": r.pattern, "raw": r.raw, "line": r.line} for r in parsed.rules],
                         file=str(local))
            _record_robots(state, hk, **entry)
            # robots.txt 가 다른 스킴·호스트로 옮겨졌으면 그 파일은 그 호스트의 robots 이기도 하다(http→https 가 흔하다)
            # 단, 옮겨 간 곳이 정확히 `/robots.txt`(쿼리 없음)일 때만 — 홈·로그인 화면으로 옮겨진 응답을 robots 로 기록하지 않는다(W14 리뷰 M3)
            served = _host_key(pending["url"])
            served_parts = urllib.parse.urlsplit(pending["url"])
            if (served != hk and served not in state["robots"]
                    and served_parts.path == "/robots.txt" and not served_parts.query):
                _record_robots(state, served, **entry)
        elif status in (401, 403):
            _record_robots(state, hk, mode="blocked", error="robots_unreadable",
                           message=f"robots.txt 가 HTTP {status} 입니다 — 사이트가 첫 요청부터 막고 있어 판독할 수 없습니다")
        elif status == 429 or status >= 500:
            _record_robots(state, hk, mode="blocked", error="robots_unreachable",
                           message=f"robots.txt 가 HTTP {status} 입니다 — RFC 9309 에 따라 전부 불허로 봅니다")
        elif 400 <= status < 500:
            _record_robots(state, hk, mode="none", note=f"HTTP {status} — robots.txt 없음(제한 없음)")
        else:
            raise Stop("args", f"알 수 없는 상태 코드: {status}", EXIT_ARGS)
        _save(state)
        return _after_robots_known(state)

    # page
    if 300 <= status < 400:
        return _redirect(state, status, location, robots_step=False)
    if 200 <= status < 300:
        if not local.is_file():
            raise Stop("input", f"저장 파일이 보이지 않습니다: {local} — --work-dir 가 save_dir 와 같은 폴더인지 확인하세요", EXIT_ARGS)
        final_url = pending["url"]
        fetched_at = _now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        state["done"] = {"file": str(local), "final_url": final_url, "status": status,
                         "content_type": content_type or "", "fetched_at": fetched_at}
        state["pending"] = None
        _save(state)
        common = [str(local), "--url", state["requested_url"], "--final-url", final_url,
                  "--status", str(status), "--fetched-at", fetched_at]
        if content_type:
            common += ["--content-type", content_type]
        extract = _commands("extract_content.py", common + ["--format", "markdown"])
        records = _commands("extract_records.py", common + ["--format", "json"])
        return {
            "status": "done",
            "file": str(local),
            "requested_url": state["requested_url"],
            "final_url": final_url,
            "http_status": status,
            "content_type": content_type,
            "redirects": len(state["hops"]),
            "calls": len(state["calls"]),
            "extract": extract[0],
            "records": records[0],
            "extract_powershell": extract[1],
            "records_powershell": records[1],
        }
    if status in (401, 403, 407):
        raise Stop("blocked_or_auth", f"HTTP {status} — 로그인이 필요하거나 봇 차단으로 거부됐습니다", EXIT_BROWSER,
                   alternatives=[f"브라우저 경로 — {BROWSER_ROUTE}"])
    if status in (404, 410):
        raise Stop("not_found", f"HTTP {status} — 페이지가 없습니다. URL 을 확인하세요", EXIT_FAIL)
    if status == 429:
        raise Stop("rate_limited", "HTTP 429 — itda-hyve 가 이미 재시도했습니다. 잠시 뒤 다시 하세요", EXIT_FAIL)
    if status >= 500:
        raise Stop("server_error", f"HTTP {status} — 사이트 서버 오류입니다(itda-hyve 가 이미 재시도했습니다)", EXIT_FAIL)
    raise Stop("http", f"HTTP {status} — 페이지를 받지 못했습니다", EXIT_FAIL)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = argparse.ArgumentParser(description="web-reader 호출 계획 — robots → 페이지, 리다이렉트는 한 홉씩")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="처음 URL 로 계획을 시작한다(첫 호출 = robots.txt)")
    s.add_argument("--url", required=True)
    s.add_argument("--save-dir", required=True, help="itda-hyve save_dir — 호스트 절대 경로(Cowork 는 연결 폴더의 호스트 경로)")
    s.add_argument("--work-dir", help="이 스크립트가 같은 폴더를 보는 경로(Cowork 는 $HOME/mnt/<폴더 이름>, 같은 머신이면 생략)")
    n = sub.add_parser("next", help="방금 부른 호출의 결과를 넘겨 다음 걸음을 받는다")
    n.add_argument("--state", required=True)
    n.add_argument("--hyve-error", dest="hyve_error", help="도구가 실패했을 때 그 code(network_error·timeout·tls_error·too_large …)")
    n.add_argument("--hyve-message", dest="hyve_message")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ARGS
    try:
        out = cmd_start(args) if args.cmd == "start" else cmd_next(args)
        code = EXIT_OK
    except Stop as stop:
        out = {"status": "stopped", "error": stop.error, "message": str(stop), **stop.extra}
        code = stop.exit_code
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
