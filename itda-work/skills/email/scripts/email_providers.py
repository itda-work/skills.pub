#!/usr/bin/env python3
"""itda-email: email_providers module — SPEC-EMAIL-008 multi-account + Google rename."""
from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Provider registry (canonical names only)
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    "naver": {
        "name": "naver",
        "aliases": [],
        "smtp_host": "smtp.naver.com",
        "smtp_port": 465,
        "imap_host": "imap.naver.com",
        "imap_port": 993,
        "use_ssl": True,
        "capabilities": ["send", "read"],
        "email_prefix": "NAVER_EMAIL",
        "password_prefix": "NAVER_APP_PASSWORD",
        "legacy_email_prefix": None,
        "legacy_password_prefix": None,
        # keep for old callers that read email_env / password_env
        "email_env": "NAVER_EMAIL",
        "password_env": "NAVER_APP_PASSWORD",
    },
    "google": {
        "name": "google",
        "aliases": ["gmail"],
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "use_ssl": True,
        "capabilities": ["send", "read"],
        "email_prefix": "GOOGLE_EMAIL",
        "password_prefix": "GOOGLE_APP_PASSWORD",
        "legacy_email_prefix": "GMAIL_ADDRESS",
        "legacy_password_prefix": "GMAIL_APP_PASSWORD",
        # email_env / password_env preserved for old callers
        "email_env": "GOOGLE_EMAIL",
        "password_env": "GOOGLE_APP_PASSWORD",
    },
    "daum": {
        "name": "daum",
        "aliases": [],
        "smtp_host": "smtp.daum.net",
        "smtp_port": 465,
        "imap_host": "imap.daum.net",
        "imap_port": 993,
        "use_ssl": True,
        "capabilities": ["send", "read"],
        "email_prefix": "DAUM_EMAIL",
        "password_prefix": "DAUM_APP_PASSWORD",
        "legacy_email_prefix": None,
        "legacy_password_prefix": None,
        "email_env": "DAUM_EMAIL",
        "password_env": "DAUM_APP_PASSWORD",
    },
    "icloud": {
        "name": "icloud",
        "aliases": [],
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
        "use_ssl": True,
        "capabilities": ["send", "read"],
        "email_prefix": "ICLOUD_EMAIL",
        "password_prefix": "ICLOUD_APP_PASSWORD",
        "legacy_email_prefix": None,
        "legacy_password_prefix": None,
        "email_env": "ICLOUD_EMAIL",
        "password_env": "ICLOUD_APP_PASSWORD",
    },
}

# Alias -> canonical mapping (e.g. "gmail" -> "google")
PROVIDER_ALIASES: dict[str, str] = {
    alias: canonical
    for canonical, cfg in PROVIDERS.items()
    for alias in cfg["aliases"]
}

# Module-level flag: emit GMAIL_* deprecation warning at most once per process.
_warned_legacy_gmail: bool = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resolve_provider_name(name: str) -> str:
    """Convert alias (e.g. 'gmail') to canonical provider name (e.g. 'google')."""
    name = name.lower().strip()
    return PROVIDER_ALIASES.get(name, name)


def validate_email(addr: str) -> bool:
    """Return True if addr contains @ and a domain."""
    addr = addr.strip()
    if "@" not in addr:
        return False
    local, _, domain = addr.partition("@")
    return bool(local) and "." in domain


def validate_port(port: str | int) -> bool:
    """Return True if port is in range 1-65535."""
    try:
        p = int(str(port).strip())
        return 1 <= p <= 65535
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Internal scan helpers
# ---------------------------------------------------------------------------


def _scan_accounts(
    env: dict,
    email_prefix: str,
    password_prefix: str,
) -> dict[str, dict]:
    """Scan env for ``{email_prefix}{_SUFFIX}?`` + ``{password_prefix}{_SUFFIX}?`` pairs.

    Returns {account_id: {"email": ..., "password": ...}}.
    account_id is "default" for the unsuffixed pair, else the lowercased suffix.
    """
    accounts: dict[str, dict] = {}

    for key, value in env.items():
        if not value:
            continue
        if key == email_prefix:
            suffix = "default"
        elif key.startswith(email_prefix + "_"):
            suffix = key[len(email_prefix) + 1:].lower()
        else:
            continue
        accounts.setdefault(suffix, {})["email"] = value.strip()

    for key, value in env.items():
        if not value:
            continue
        if key == password_prefix:
            suffix = "default"
        elif key.startswith(password_prefix + "_"):
            suffix = key[len(password_prefix) + 1:].lower()
        else:
            continue
        accounts.setdefault(suffix, {})["password"] = value.strip()

    return accounts


def _build_account_list(accounts: dict[str, dict], cfg: dict) -> list[dict]:
    """Convert raw account dicts into structured account_list entries."""
    account_list = []
    for account_id, acc in sorted(accounts.items()):
        email = acc.get("email", "")
        password = acc.get("password", "")
        if email and password and validate_email(email):
            account_entry: dict = {
                "account_id": account_id,
                "email": email,
                "status": "ready",
                "capabilities": list(cfg["capabilities"]),
            }
        else:
            missing = []
            suffix_upper = "" if account_id == "default" else f"_{account_id.upper()}"
            if not email:
                missing.append(cfg["email_prefix"] + suffix_upper)
            if not password:
                missing.append(cfg["password_prefix"] + suffix_upper)
            account_entry = {
                "account_id": account_id,
                "email": email or None,
                "status": "incomplete",
                "capabilities": [],
                "missing": missing,
            }
        account_list.append(account_entry)
    return account_list


def _detect_custom_accounts(env: dict) -> dict:
    """Build the custom provider entry with multi-account suffix support."""
    # Scan SMTP_HOST{_SUFFIX} keys to discover account suffixes
    smtp_host_prefix = "SMTP_HOST"
    suffixes: dict[str, str] = {}  # suffix -> SMTP_HOST value

    for key, value in env.items():
        if not value:
            continue
        if key == smtp_host_prefix:
            suffixes["default"] = value.strip()
        elif key.startswith(smtp_host_prefix + "_"):
            suffix = key[len(smtp_host_prefix) + 1:].lower()
            suffixes[suffix] = value.strip()

    account_list = []
    for suffix, host_val in sorted(suffixes.items()):
        sfx_upper = "" if suffix == "default" else f"_{suffix.upper()}"
        port_str = (env.get(f"SMTP_PORT{sfx_upper}") or "").strip()
        user = (env.get(f"SMTP_USER{sfx_upper}") or "").strip()
        password = (env.get(f"SMTP_PASSWORD{sfx_upper}") or "").strip()
        imap_host = (env.get(f"IMAP_HOST{sfx_upper}") or "").strip()
        imap_port_str = (env.get(f"IMAP_PORT{sfx_upper}") or "").strip()

        required_present = all([host_val, port_str, user, password])
        if not required_present:
            missing = []
            if not host_val:
                missing.append(f"SMTP_HOST{sfx_upper}")
            if not port_str:
                missing.append(f"SMTP_PORT{sfx_upper}")
            if not user:
                missing.append(f"SMTP_USER{sfx_upper}")
            if not password:
                missing.append(f"SMTP_PASSWORD{sfx_upper}")
            account_list.append({
                "account_id": suffix,
                "email": user or None,
                "status": "incomplete",
                "capabilities": [],
                "missing": missing,
            })
            continue

        port_valid = validate_port(port_str)
        caps = ["send"]
        if imap_host and imap_port_str:
            caps.append("read")

        account_list.append({
            "account_id": suffix,
            "email": user,
            "status": "ready" if port_valid else "incomplete",
            "capabilities": caps,
            "smtp_host": host_val,
            "smtp_port": int(port_str) if port_valid else port_str,
            "imap_host": imap_host or None,
            "imap_port": int(imap_port_str) if imap_port_str and imap_host else None,
        })

    if not account_list:
        provider_status = "not_configured"
    elif any(a["status"] == "ready" for a in account_list):
        provider_status = "ready"
    else:
        provider_status = "incomplete"

    return {
        "provider": "custom",
        "aliases": [],
        "status": provider_status,
        "accounts": account_list,
    }


def _get_custom_provider(env: dict, account: str | None = None) -> dict | None:
    """Return resolved custom provider config for the given account."""
    smtp_host_prefix = "SMTP_HOST"
    suffixes: list[str] = []

    for key, value in env.items():
        if not value:
            continue
        if key == smtp_host_prefix:
            suffixes.append("default")
        elif key.startswith(smtp_host_prefix + "_"):
            suffixes.append(key[len(smtp_host_prefix) + 1:].lower())

    if not suffixes:
        return None

    # Select account_id
    if account is None:
        if len(suffixes) == 1:
            selected_id = suffixes[0]
        elif "default" in suffixes:
            selected_id = "default"
        else:
            return None
    else:
        selected_id = account.lower().strip()
        if selected_id not in suffixes:
            return None

    sfx_upper = "" if selected_id == "default" else f"_{selected_id.upper()}"
    host = (env.get(f"SMTP_HOST{sfx_upper}") or "").strip()
    port_str = (env.get(f"SMTP_PORT{sfx_upper}") or "465").strip()
    user = (env.get(f"SMTP_USER{sfx_upper}") or "").strip()
    password = (env.get(f"SMTP_PASSWORD{sfx_upper}") or "").strip()
    imap_host = (env.get(f"IMAP_HOST{sfx_upper}") or "").strip() or None
    imap_port_str = (env.get(f"IMAP_PORT{sfx_upper}") or "").strip()

    if not host or not user or not password:
        return None

    return {
        "name": "custom",
        "account_id": selected_id,
        "smtp_host": host,
        "smtp_port": int(port_str) if validate_port(port_str) else 465,
        "imap_host": imap_host,
        "imap_port": int(imap_port_str) if imap_port_str and imap_host else None,
        "use_ssl": True,
        "capabilities": ["send", "read"] if imap_host else ["send"],
        "email": user,
        "password": password,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_providers(env: dict) -> list[dict]:
    """Scan env and return list of provider status dicts (new multi-account schema)."""
    global _warned_legacy_gmail
    results = []

    for canonical_name, cfg in PROVIDERS.items():
        accounts = _scan_accounts(env, cfg["email_prefix"], cfg["password_prefix"])

        if cfg["legacy_email_prefix"]:
            legacy = _scan_accounts(
                env,
                cfg["legacy_email_prefix"],
                cfg["legacy_password_prefix"],
            )
            for suffix, legacy_acc in legacy.items():
                if suffix in accounts:
                    # GOOGLE_* wins; log info once
                    print(
                        f"info: {cfg['legacy_email_prefix']} ignored"
                        f" because {cfg['email_prefix']} is set",
                        file=sys.stderr,
                    )
                else:
                    # Legacy account — register with deprecation warning
                    accounts[suffix] = legacy_acc
                    if not _warned_legacy_gmail:
                        print(
                            f"warning: {cfg['legacy_email_prefix']}/{cfg['legacy_password_prefix']}"
                            f" is deprecated; use {cfg['email_prefix']}/{cfg['password_prefix']}"
                            f" instead (will be removed in v0.18.0)",
                            file=sys.stderr,
                        )
                        _warned_legacy_gmail = True

        account_list = _build_account_list(accounts, cfg)

        if not account_list:
            provider_status = "not_configured"
        elif any(a["status"] == "ready" for a in account_list):
            provider_status = "ready"
        else:
            provider_status = "incomplete"

        results.append({
            "provider": canonical_name,
            "aliases": list(cfg["aliases"]),
            "status": provider_status,
            "accounts": account_list,
        })

    results.append(_detect_custom_accounts(env))
    return results


def get_provider(name: str, env: dict, account: str | None = None) -> dict | None:
    """Get provider config + credentials for the given account.

    account=None  -> auto-select (FR-05 rules)
    account="default" / "1" / "work" -> explicit suffix lookup
    Returns None if not found or ambiguous.
    """
    global _warned_legacy_gmail
    canonical = resolve_provider_name(name)

    if canonical == "custom":
        return _get_custom_provider(env, account)

    if canonical not in PROVIDERS:
        return None

    cfg = PROVIDERS[canonical]
    accounts = _scan_accounts(env, cfg["email_prefix"], cfg["password_prefix"])

    # Merge legacy accounts (without overwriting canonical ones)
    if cfg["legacy_email_prefix"]:
        legacy = _scan_accounts(env, cfg["legacy_email_prefix"], cfg["legacy_password_prefix"])
        for suffix, legacy_acc in legacy.items():
            if suffix not in accounts:
                accounts[suffix] = legacy_acc
                if not _warned_legacy_gmail:
                    print(
                        f"warning: {cfg['legacy_email_prefix']}/{cfg['legacy_password_prefix']}"
                        f" is deprecated; use {cfg['email_prefix']}/{cfg['password_prefix']}"
                        f" instead (will be removed in v0.18.0)",
                        file=sys.stderr,
                    )
                    _warned_legacy_gmail = True

    if not accounts:
        return None

    # Account selection (FR-05)
    if account is None:
        if len(accounts) == 1:
            selected_id = next(iter(accounts))
        elif "default" in accounts:
            selected_id = "default"
        else:
            return None
    else:
        selected_id = account.lower().strip()
        if selected_id not in accounts:
            return None

    acc = accounts[selected_id]
    if not acc.get("email") or not acc.get("password"):
        return None

    return {
        "name": canonical,
        "account_id": selected_id,
        "smtp_host": cfg["smtp_host"],
        "smtp_port": cfg["smtp_port"],
        "imap_host": cfg["imap_host"],
        "imap_port": cfg["imap_port"],
        "use_ssl": cfg["use_ssl"],
        "capabilities": list(cfg["capabilities"]),
        "email": acc["email"],
        "password": acc["password"],
    }
