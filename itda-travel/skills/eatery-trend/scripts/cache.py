"""cache.py — TTL 파일 캐시 (REQ-009).

SearchAd/데이터랩/블로그/지역검색 호출을 절약한다. 검색량은 휘발성이므로
TTL을 짧게(기본 6시간) 둔다 — 오래된 surge는 의미 없다.

캐시 위치는 itda_path.resolve_cache_dir("eatery-trend")로 결정한다(환경 독립).
now 인자를 주입 가능하게 하여 결정론적 단위 테스트를 지원한다.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from itda_path import resolve_cache_dir

DEFAULT_TTL = 6 * 3600  # 6시간 — 검색량 휘발성 대응(REQ-009)


def _cache_dir() -> Path:
    return resolve_cache_dir("eatery-trend")


def _key(namespace: str, key_parts) -> str:
    raw = namespace + "|" + "|".join(str(p) for p in key_parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _path(namespace: str, key_parts) -> Path:
    return _cache_dir() / f"{namespace}_{_key(namespace, key_parts)}.json"


def set_value(namespace: str, key_parts, value: Any, *, now: float | None = None) -> None:
    """값을 캐시에 기록한다(타임스탬프 포함)."""
    ts = time.time() if now is None else now
    path = _path(namespace, key_parts)
    try:
        path.write_text(json.dumps({"ts": ts, "value": value}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 캐시 실패는 치명적이지 않음(graceful) — 호출부가 라이브로 진행


def get_value(namespace: str, key_parts, *, ttl: float = DEFAULT_TTL, now: float | None = None) -> Any | None:
    """TTL 이내의 캐시 값을 반환한다. miss/만료/손상 시 None."""
    ts_now = time.time() if now is None else now
    path = _path(namespace, key_parts)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "ts" not in data:
        return None
    if ts_now - float(data["ts"]) > ttl:
        return None
    return data.get("value")
