#!/usr/bin/env python3
"""itda-calendar: caldav_providers — CalDAV provider registry.

Track 1 (app-password Basic Auth) providers + custom CalDAV. Mirrors the
itda-email provider/multi-account pattern (env var suffixes).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Provider registry (track 1: CalDAV + app-specific password, Basic Auth)
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    "icloud": {
        "name": "icloud",
        "aliases": ["apple"],
        "caldav_url": "https://caldav.icloud.com/",
        "login_prefix": "ICLOUD_EMAIL",
        "password_prefix": "ICLOUD_APP_PASSWORD",
        "note": "Apple ID app-specific password (2FA required). Shares the "
                "credential with the itda-email iCloud account.",
        "experimental": False,
    },
    "naver": {
        "name": "naver",
        "aliases": [],
        "caldav_url": "https://caldav.calendar.naver.com/",
        "login_prefix": "NAVER_EMAIL",
        "password_prefix": "NAVER_APP_PASSWORD",
        "note": "네이버 애플리케이션 비밀번호 (2FA 시 필수). itda-email과 동일 "
                "변수(NAVER_EMAIL/NAVER_APP_PASSWORD)를 공유한다. 로그인은 전체 이메일.",
        "experimental": False,
        # 네이버는 comp-filter/time-range REPORT가 비어서 objects 열거 경로를 쓴다.
        # iCloud/custom은 표준 REPORT가 정상이므로 빈 결과를 신뢰한다(불필요한 스캔 방지).
        "list_via_objects": True,
    },
}

PROVIDER_ALIASES: dict[str, str] = {
    alias: canonical
    for canonical, cfg in PROVIDERS.items()
    for alias in cfg["aliases"]
}


def resolve_provider_name(name: str) -> str:
    """Map alias (e.g. 'apple') to canonical name (e.g. 'icloud')."""
    name = name.lower().strip()
    return PROVIDER_ALIASES.get(name, name)


def supported_provider_names() -> list[str]:
    """Canonical names of providers this skill can serve (track 1 + custom).

    For user-facing messages. Excludes OAuth/iCal-track providers
    (google/outlook/kakao) which are not implemented.
    """
    return list(PROVIDERS.keys()) + ["custom"]


def is_supported_provider(name: str) -> bool:
    """True if ``name`` is a known provider, an alias, or 'custom'.

    Distinguishes an unsupported provider (e.g. 'google' — OAuth track,
    no env vars exist) from a supported-but-unconfigured one (e.g. 'icloud'
    with missing credentials).
    """
    canonical = resolve_provider_name(name)
    return canonical in PROVIDERS or canonical == "custom"


# ---------------------------------------------------------------------------
# env scanning (suffix-based multi-account, identical rules to itda-email)
# ---------------------------------------------------------------------------


def _scan_pair(env: dict, login_prefix: str, password_prefix: str) -> dict[str, dict]:
    """Scan ``{login_prefix}{_SUFFIX}?`` + ``{password_prefix}{_SUFFIX}?`` pairs."""
    accounts: dict[str, dict] = {}
    for prefix, field in ((login_prefix, "login"), (password_prefix, "password")):
        for key, value in env.items():
            if not value:
                continue
            if key == prefix:
                suffix = "default"
            elif key.startswith(prefix + "_"):
                suffix = key[len(prefix) + 1:].lower()
            else:
                continue
            accounts.setdefault(suffix, {})[field] = value.strip()
    return accounts


def _scan_custom(env: dict) -> dict[str, dict]:
    """Scan custom CalDAV: CALDAV_URL / CALDAV_USER / CALDAV_PASSWORD (+ _SUFFIX)."""
    accounts: dict[str, dict] = {}
    fields = (("CALDAV_URL", "url"), ("CALDAV_USER", "login"),
              ("CALDAV_PASSWORD", "password"))
    for prefix, field in fields:
        for key, value in env.items():
            if not value:
                continue
            if key == prefix:
                suffix = "default"
            elif key.startswith(prefix + "_"):
                suffix = key[len(prefix) + 1:].lower()
            else:
                continue
            accounts.setdefault(suffix, {})[field] = value.strip()
    return accounts


def _account_entry(account_id: str, acc: dict, required: list[tuple[str, str]]) -> dict:
    """Build a status entry; ``required`` is [(field, ENV_PREFIX), ...]."""
    suffix = "" if account_id == "default" else f"_{account_id.upper()}"
    missing = [prefix + suffix for field, prefix in required if not acc.get(field)]
    entry = {
        "account_id": account_id,
        "login": acc.get("login"),
        "status": "ready" if not missing else "incomplete",
    }
    if "url" in acc or any(f == "url" for f, _ in required):
        entry["url"] = acc.get("url")
    if missing:
        entry["missing"] = missing
    return entry


def detect_providers(env: dict) -> list[dict]:
    """Return provider status list (ready / incomplete / not_configured)."""
    results = []
    for name, cfg in PROVIDERS.items():
        accounts = _scan_pair(env, cfg["login_prefix"], cfg["password_prefix"])
        required = [("login", cfg["login_prefix"]), ("password", cfg["password_prefix"])]
        account_list = [_account_entry(aid, acc, required)
                        for aid, acc in sorted(accounts.items())]
        status = _provider_status(account_list)
        results.append({
            "provider": name,
            "aliases": list(cfg["aliases"]),
            "experimental": cfg.get("experimental", False),
            "status": status,
            "accounts": account_list,
        })

    custom = _scan_custom(env)
    required = [("url", "CALDAV_URL"), ("login", "CALDAV_USER"),
                ("password", "CALDAV_PASSWORD")]
    custom_list = [_account_entry(aid, acc, required)
                   for aid, acc in sorted(custom.items())]
    results.append({
        "provider": "custom",
        "aliases": [],
        "experimental": False,
        "status": _provider_status(custom_list),
        "accounts": custom_list,
    })
    return results


def _provider_status(account_list: list[dict]) -> str:
    if not account_list:
        return "not_configured"
    if any(a["status"] == "ready" for a in account_list):
        return "ready"
    return "incomplete"


def get_provider(name: str, env: dict, account: str | None = None) -> dict | None:
    """Resolve provider config + credentials for the given account.

    Returns dict with caldav_url/login/password, or None if missing/ambiguous.
    """
    canonical = resolve_provider_name(name)

    if canonical == "custom":
        accounts = _scan_custom(env)
        required_fields = ("url", "login", "password")
    elif canonical in PROVIDERS:
        cfg = PROVIDERS[canonical]
        accounts = _scan_pair(env, cfg["login_prefix"], cfg["password_prefix"])
        required_fields = ("login", "password")
    else:
        return None

    if not accounts:
        return None

    if account is None:
        if len(accounts) == 1:
            selected = next(iter(accounts))
        elif "default" in accounts:
            selected = "default"
        else:
            return None  # ambiguous
    else:
        selected = account.lower().strip()
        if selected not in accounts:
            return None

    acc = accounts[selected]
    if not all(acc.get(f) for f in required_fields):
        return None

    if canonical == "custom":
        caldav_url = acc["url"]
    else:
        caldav_url = PROVIDERS[canonical]["caldav_url"]

    return {
        "name": canonical,
        "account_id": selected,
        "caldav_url": caldav_url,
        "login": acc["login"],
        "password": acc["password"],
        "list_via_objects": PROVIDERS.get(canonical, {}).get("list_via_objects", False),
    }
