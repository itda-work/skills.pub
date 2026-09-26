#!/usr/bin/env python3
"""codex-usage — 이 머신의 Codex CLI 자격증명으로 사용량을 조회해 JSON 으로 낸다.

    python3 usage.py             # JSON 출력, exit 0
    python3 usage.py --max 20    # 5시간 창 사용률이 20% 이하면 exit 0, 초과 exit 1
    python3 usage.py --window weekly --max 80
    python3 usage.py --home ~/.codex-alt    # 두 번째 계정 프로필

조회 실패(자격증명 없음·토큰 만료·응답 형식 변경·네트워크)는 에러 JSON + **exit 2** 다 —
게이트로 쓸 때 모를 때는 통과시키지 않는다(fail-closed).

계약은 sheriff(Core/UsageStatus.swift·UsageFetcher.swift) 실측을 옮긴 것이다:
- 자격증명: `<설정홈>/auth.json` 의 `tokens.access_token` + `tokens.account_id`.
  설정 홈은 `--home` > `CODEX_HOME` > `~/.codex` — CODEX_HOME 은 codex 가 실제로 보는
  변수라, cod-alt 세션에서는 인자 없이도 그 프로필을 읽는다.
- 요청: GET https://chatgpt.com/backend-api/wham/usage, `ChatGPT-Account-Id` 헤더.
  codex 바이너리·app-server 가 필요 없다(구 `skills/scripts/codex_usage.py` 는 app-server
  `account/rateLimits/read` 를 썼다 — 이 스크립트로 통합, #1683).
- 응답: `rate_limit.primary_window`·`secondary_window`. 창 길이는 `limit_window_seconds`(초)로
  오며 어느 자리가 5시간인지는 계약이 아니다 — 길이로 고른다.

토큰 값은 어떤 출력에도 싣지 않는다. Python 3.9 호환(stdlib 전용).
"""
import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def _norm(path):
    """경로를 절대경로 + NFC 로 (맥 파일명 자모 분해 방지)."""
    return unicodedata.normalize("NFC", os.path.abspath(os.path.expanduser(path)))


DEFAULT_CONFIG_DIR = _norm("~/.codex")


class UsageError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ── 자격증명 ──────────────────────────────────────────────────────────────

def parse_credential(text):
    """auth.json → {access_token, account_id}. 형식이 틀리면 None."""
    try:
        root = json.loads(text)
    except Exception:
        return None
    tokens = root.get("tokens") if isinstance(root, dict) else None
    if not isinstance(tokens, dict):
        return None
    token = tokens.get("access_token")
    if not isinstance(token, str) or not token:
        return None
    return {"access_token": token, "account_id": tokens.get("account_id") or ""}


def resolve_config_dir(home=None, env=None):
    """설정 홈 해석 — `--home` > `CODEX_HOME` > `~/.codex`."""
    env = os.environ if env is None else env
    return _norm(home or env.get("CODEX_HOME") or DEFAULT_CONFIG_DIR)


def load_credential(config_dir=None):
    path = os.path.join(config_dir or DEFAULT_CONFIG_DIR, "auth.json")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        raise UsageError("no_credential",
                         "Codex 자격증명이 없다 — `codex login` 하면 생긴다 (%s)" % path)
    cred = parse_credential(text)
    if not cred:
        raise UsageError("bad_credential", "%s 에 tokens.access_token 이 없다" % path)
    return cred


# ── 요청 ──────────────────────────────────────────────────────────────────

def fetch_usage(cred, timeout=15):
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": "Bearer " + cred["access_token"],
        "ChatGPT-Account-Id": cred["account_id"],
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except Exception as e:
        raise UsageError("network", "네트워크 오류: " + str(e))
    if status in (401, 403):
        raise UsageError("token_expired", "토큰 만료 — `codex` 를 한 번 실행하면 갱신된다 (HTTP %d)" % status)
    if status != 200:
        raise UsageError("http_%d" % status, "HTTP %d" % status)
    return body


# ── 응답 파싱 ─────────────────────────────────────────────────────────────

def window_kind(seconds):
    hours = seconds / 3600.0
    if hours <= 0:
        return "other", "기타"
    if hours <= 24:
        return "session", "%d시간" % int(round(hours))
    return "weekly", "%d일" % int(round(hours / 24))


def parse_usage(body):
    """응답 JSON → (plan, email, windows). sheriff.parseCodex 와 같은 규칙."""
    try:
        root = json.loads(body)
    except Exception:
        raise UsageError("bad_response", "응답이 JSON 이 아니다")
    if not isinstance(root, dict):
        raise UsageError("bad_response", "응답이 객체가 아니다")
    rate_limit = root.get("rate_limit")
    if not isinstance(rate_limit, dict):
        raise UsageError("bad_response", "응답 형식이 바뀜 — rate_limit 이 없다")
    windows = []
    for key in ("primary_window", "secondary_window"):
        bucket = rate_limit.get(key)
        if not isinstance(bucket, dict) or not isinstance(bucket.get("used_percent"), (int, float)):
            continue
        seconds = bucket.get("limit_window_seconds") or 0
        kind, label = window_kind(float(seconds))
        reset = bucket.get("reset_at")
        windows.append({
            "key": key, "kind": kind, "label": label,
            "percent": float(bucket["used_percent"]),
            "window_seconds": int(seconds),
            "resets_at": float(reset) if isinstance(reset, (int, float)) else None,
        })
    if not windows:
        raise UsageError("bad_response", "응답 형식이 바뀜 — primary_window 가 없다")
    plan = root.get("plan_type")
    plan = (plan[:1].upper() + plan[1:]) if isinstance(plan, str) and plan else None
    email = root.get("email") or None
    return plan, email, windows


def pick_window(windows, kind):
    for w in windows:
        if w["kind"] == kind:
            return w
    return None


def with_reset_text(windows, now=None):
    now = time.time() if now is None else now
    for w in windows:
        r = w.get("resets_at")
        w["resets_in_seconds"] = int(r - now) if r else None
        w["resets_at_local"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(r)) if r else None
    return windows


# ── 진입 ──────────────────────────────────────────────────────────────────

def build_report(body, now=None, config_dir=None):
    plan, email, windows = parse_usage(body)
    return {
        "ok": True,
        "provider": "codex",
        "config_dir": config_dir,
        "plan": plan,
        "email": email,
        "windows": with_reset_text(windows, now),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
    }


def gate(report, kind, max_percent):
    w = pick_window(report["windows"], kind)
    if w is None:
        return 2, {"passed": False, "reason": "창 없음: " + kind}
    passed = w["percent"] <= max_percent
    return (0 if passed else 1), {
        "passed": passed, "window": w["label"], "percent": w["percent"], "max": max_percent,
    }


def main(argv=None):
    # Windows 콘솔은 기본 cp949 라 한국어·— 가 UnicodeEncodeError 로 죽는다(surface 실측) — 출력은 UTF-8 로
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max", type=float, default=None, help="이 %% 이하일 때만 exit 0 (게이트)")
    ap.add_argument("--window", choices=["session", "weekly"], default="session",
                    help="게이트 대상 창 (기본 session=5시간)")
    ap.add_argument("--home", default=None, metavar="설정홈",
                    help="읽을 설정 홈 (기본: $CODEX_HOME 또는 ~/.codex). "
                         "두 번째 계정은 --home ~/.codex-alt")
    a = ap.parse_args(argv)
    config_dir = resolve_config_dir(a.home)
    try:
        report = build_report(fetch_usage(load_credential(config_dir)), config_dir=config_dir)
    except UsageError as e:
        print(json.dumps({"ok": False, "provider": "codex", "config_dir": config_dir,
                          "error": e.code, "message": e.message}, ensure_ascii=False))
        return 2
    code = 0
    if a.max is not None:
        code, verdict = gate(report, a.window, a.max)
        report["gate"] = verdict
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
