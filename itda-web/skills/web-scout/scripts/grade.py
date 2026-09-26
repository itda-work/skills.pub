"""grade.py — 판정 축(순수 함수): 사다리 전이 · 등급 파생 · 반복 조회 결과 분류 · 재현성 의미 비교.

전부 순수 함수다(HTTP·파일 없음). SKILL.md 의 전이표·등급표와 1:1 — 표를 바꾸면 여기와 테스트를 같이 바꾼다.
이슈 #1600 §목표 1·3·5 · L4 preflight 교훈(루트 JS 리다이렉트·install_gate·정적 껍데기의 오래된 샘플).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# 전이표 (S4) — 신호 → 진단코드 → 전이
# ---------------------------------------------------------------------------

INSTALL_GATE_MARKERS = re.compile(
    r"veraport|nprotect|anysign|magicline|inisafe|touchen|astx|ipinside|"
    r"보안\s*프로그램\s*설치|보안모듈\s*설치|공동인증서|공인인증서\s*(설치|등록)|"
    r"href=[\"'][^\"']+\.(exe|dmg|pkg|msi)[\"']",
    re.I,
)
CHALLENGE_MARKERS = re.compile(r"cf-challenge|__cf_chl|just a moment|captcha|access denied|attention required|imperva|incapsula|akamai", re.I)
AUTH_MARKERS = re.compile(r"type=[\"']password[\"']|로그인이\s*필요|로그인\s*후\s*이용|sign in to continue|please log ?in", re.I)
POLICY_MARKERS = re.compile(r"접근이\s*차단|차단된\s*요청|forbidden by policy|not allowed from your (country|region)|robots?\s*정책", re.I)
JS_REDIRECT = re.compile(
    r"(?:window\.|document\.|top\.|self\.)?location(?:\.href|\.replace|\.assign)?\s*(?:=|\()\s*[\"']([^\"']+)[\"']"
    r"|<meta[^>]+http-equiv=[\"']refresh[\"'][^>]+url=([^\"'>\s]+)",
    re.I,
)

TRANSITIONS = {
    "ok": "stop",
    "thin": "escalate",
    "spa_shell": "escalate",
    "js_redirect": "retry_final_url",
    "install_gate": "stop",
    "challenge": "escalate",
    "auth_evidence": "stop",
    "policy_block": "stop",
    "ambiguous_403": "require_confirmation",
    "auth_required": "stop",
    "not_found": "rediscover_once",
    "rate_limited": "retry_after",
    "server_error": "retry_after",
    "budget_exceeded": "stop",
    "browser_unavailable": "stop",
}


@dataclass
class Signal:
    status: int | None
    content_type: str = ""
    html: str = ""
    visible_len: int = 0
    min_text_length: int = 500


def js_redirect_target(html: str) -> str | None:
    m = JS_REDIRECT.search(html or "")
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip() or None


def diagnose(sig: Signal) -> str:
    """신호 → 진단코드. 순서가 계약이다(install_gate 는 본문 판정보다 먼저 — 200 + 텍스트가 있어도 게이트)."""
    html = sig.html or ""
    if sig.status is None:
        return "browser_unavailable"
    if sig.status == 429:
        return "rate_limited"
    if sig.status >= 500:
        return "server_error"
    if sig.status in (404, 410):
        return "not_found"
    if sig.status == 401:
        return "auth_required"
    if sig.status == 403:
        if CHALLENGE_MARKERS.search(html):
            return "challenge"
        if AUTH_MARKERS.search(html):
            return "auth_evidence"
        if POLICY_MARKERS.search(html):
            return "policy_block"
        return "ambiguous_403"
    if INSTALL_GATE_MARKERS.search(html) and sig.visible_len < 3 * sig.min_text_length:
        return "install_gate"
    if CHALLENGE_MARKERS.search(html) and sig.visible_len < sig.min_text_length:
        return "challenge"
    if sig.visible_len < 200 and js_redirect_target(html):
        return "js_redirect"
    if sig.visible_len < sig.min_text_length:
        return "spa_shell" if re.search(r"<script", html, re.I) else "thin"
    return "ok"


def transition(diag: str) -> str:
    return TRANSITIONS[diag]


# ---------------------------------------------------------------------------
# 축 → 파생 등급 (S5)
# ---------------------------------------------------------------------------

@dataclass
class Axes:
    discovery_path: str          # feed | static_list | site_search | api | none
    repeat_access: str           # L1 | L2 | L3 | L4
    auth_state: str = "none"     # none | required | blocked | blocked:security_module
    env_availability: str = "n/a"  # browser kind 또는 n/a


def derive_grade(a: Axes) -> str:
    if a.auth_state != "none":
        return "D"
    if a.repeat_access == "L4":
        return "C"
    if a.discovery_path == "feed" and a.repeat_access == "L1":
        return "A"
    if a.repeat_access == "L1" and a.discovery_path in ("static_list",):
        return "A" if a.discovery_path == "feed" else "B"
    return "B"


# ---------------------------------------------------------------------------
# 반복 조회 결과 분류 (S8)
# ---------------------------------------------------------------------------

@dataclass
class ExpectedShape:
    """플레이북이 위치별로 갖는 기대 shape. 최소 건수 단독 판정 금지 — 축을 여럿 본다."""
    content_type_prefix: str = "text/html"
    required_record_keys: tuple[str, ...] = ("source_url", "title", "published")
    min_records: int = 1
    freshness_days: int | None = None   # 최신 항목이 N일 내여야 정상 (정적 껍데기의 오래된 샘플 차단)
    denominator: int | None = None      # 사이트 총계가 있을 때


@dataclass
class Observation:
    status: int | None
    content_type: str
    records: list[dict[str, Any]] = field(default_factory=list)
    today: date | None = None
    diag: str | None = None


def _latest(records: list[dict[str, Any]]) -> date | None:
    best = None
    for r in records:
        p = (r.get("published") or "")[:10]
        try:
            d = datetime.strptime(p, "%Y-%m-%d").date() if len(p) == 10 else datetime.strptime(p[:7] + "-01", "%Y-%m-%d").date()
        except ValueError:
            continue
        best = d if best is None or d > best else best
    return best


def classify_result(obs: Observation, exp: ExpectedShape) -> str:
    """성공 종결: fresh_nonempty · empty_valid / 재탐색: incomplete · schema_drift / typed 종결: auth_expired."""
    if obs.diag in ("auth_evidence", "auth_required", "install_gate"):
        return "auth_expired"
    if obs.status is None or not obs.content_type.lower().startswith(exp.content_type_prefix):
        return "schema_drift"
    if obs.status != 200 or (obs.diag not in (None, "ok")):
        return "schema_drift"  # 403/5xx·thin·spa_shell·no_dated_list(목록 구조 미인식) 의 0건은 무소식이 아니라 깨진 수집 (R-impl P1)
    if not obs.records:
        return "empty_valid"  # 0건 자체는 정상 — 200·정상 진단·Content-Type 이 맞을 때만 무소식
    for r in obs.records:
        if any(k not in r for k in exp.required_record_keys):
            return "schema_drift"
    if exp.denominator is not None and len(obs.records) < exp.denominator:
        return "incomplete"
    if len(obs.records) < exp.min_records:
        return "incomplete"
    if exp.freshness_days is not None:
        latest = _latest(obs.records)
        today = obs.today or date.today()
        if latest is None or (today - latest).days > exp.freshness_days:
            return "schema_drift"  # 정적 껍데기의 오래된 샘플(현대해상 2021년 3건) — 살아 있는 목록이 아니다
    return "fresh_nonempty"


IS_STALE = {"incomplete", "schema_drift"}
IS_SUCCESS = {"fresh_nonempty", "empty_valid"}


# ---------------------------------------------------------------------------
# 재현성 판정 (S4b) — 브라우저 밖 재생 응답 vs 관측 응답 의미 비교
# ---------------------------------------------------------------------------

@dataclass
class ReplayCompare:
    observed_final_url: str
    replayed_final_url: str
    observed_ct: str
    replayed_ct: str
    observed_ids: set[str]
    replayed_ids: set[str]
    observed_key_types: dict[str, str]
    replayed_key_types: dict[str, str]
    method: str = "GET"


def replayability(c: ReplayCompare, *, min_overlap: float = 0.6) -> str:
    """anonymous_replayable | session_bound | browser_only. 바이트 비교 금지(거짓 실패) · shape 단독 금지(거짓 성공)."""
    if c.method.upper() != "GET":
        return "browser_only"  # 비-GET 재생은 하지 않는다 (collect-only)
    if urlsplit(c.observed_final_url)[:2] != urlsplit(c.replayed_final_url)[:2]:
        return "session_bound"  # 로그인 리다이렉트 등 origin 이탈
    if c.observed_ct.split(";")[0].strip().lower() != c.replayed_ct.split(";")[0].strip().lower():
        return "session_bound"  # 로그인 HTML 200 위조 (#1431)
    if c.observed_key_types != c.replayed_key_types:
        return "session_bound"
    if not c.observed_ids:
        return "session_bound"  # 항목 ID 집합이 없으면 형제 응답과 구분 불가 — 안전 쪽
    overlap = len(c.observed_ids & c.replayed_ids) / len(c.observed_ids)
    return "anonymous_replayable" if overlap >= min_overlap else "session_bound"


def key_types(obj: Any, depth: int = 1) -> dict[str, str]:
    """핵심 키 타입 지문 — 같은 키가 배열/문자열로 갈리는 요약 갈음(collection-completeness ⑫)을 잡는다."""
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out[k] = type(v).__name__
            if depth > 0 and isinstance(v, dict):
                for k2, t2 in key_types(v, depth - 1).items():
                    out[f"{k}.{k2}"] = t2
    elif isinstance(obj, list):
        out["[]"] = "list"
        if obj and isinstance(obj[0], dict):
            for k, t in key_types(obj[0], depth).items():
                out[f"[].{k}"] = t
    return out
