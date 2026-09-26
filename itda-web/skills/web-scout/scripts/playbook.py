"""playbook.py — 플레이북(memory) 스키마·조회·병합·제안·원자 갱신.

3층 분리(#1600 §목표 4): 코드(도메인 무관) / 시드 `playbooks/<도메인>/<host>.yaml`(읽기 전용) /
로컬 누적 `resolve_data_dir("web-scout")/playbooks/<도메인>/<host>.yaml`.
- 병합 단위는 **위치(location_id)** — 로컬 부분 파일이 시드의 다른 위치를 가리지 않는다.
- 비밀은 `secret_ref`(이름)만. 값처럼 보이는 것은 거부(fail-closed).
- 갱신은 제안 파일(`*.proposal.yaml`) → 사용자 확인 → commit(임시 파일 + os.replace 원자).
- `schema_version` 불일치는 typed 거부(migration 은 MVP 비목표).
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
LOCATION_REQUIRED = ("location_id", "item", "url", "discovery_path", "repeat_access", "auth_state", "grade", "evidence")
EVIDENCE_REQUIRED = ("observed_at", "samples", "browser")
SECRET_REF_SYNTAX = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")  # 식별자만 — 값이 들어올 자리가 아니다
SECRET_QUERY_KEY = re.compile(r"(?i)(token|key|auth|session|sess|password|passwd|secret|sig|signature|jsessionid|phpsessid)")
SECRET_KEY_LIKE = re.compile(r"(?i)^(cookie|set-cookie|token|access[_-]?token|authorization|password|passwd|secret|api[_-]?key|session[_-]?id)$")
SECRET_VALUE_LIKE = re.compile(r"(?i)(cookie|token|authorization|password|secret|api[_-]?key)\s*[:=]\s*\S{6,}|^[A-Za-z0-9+/=_-]{32,}$")


class PlaybookError(ValueError):
    pass


def validate(pb: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if pb.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version 불일치: {pb.get('schema_version')!r} != {SCHEMA_VERSION}")
        return errs
    for k in ("host", "domain", "locations"):
        if k not in pb:
            errs.append(f"필수 키 없음: {k}")
    seen: set[str] = set()
    for i, loc in enumerate(pb.get("locations") or []):
        for k in LOCATION_REQUIRED:
            if k not in loc:
                errs.append(f"locations[{i}] 필수 키 없음: {k}")
        lid = loc.get("location_id")
        if lid in seen:
            errs.append(f"location_id 중복: {lid}")
        seen.add(lid)
        ev = loc.get("evidence") or {}
        for k in EVIDENCE_REQUIRED:
            if k not in ev:
                errs.append(f"locations[{i}].evidence 필수 키 없음: {k}")
        if loc.get("grade") not in ("A", "B", "C", "D"):
            errs.append(f"locations[{i}] grade 값 이상: {loc.get('grade')!r}")
        # 비밀 값 거부 — secret_ref 만 허용
        sr = loc.get("secret_ref")
        if sr is not None and not (isinstance(sr, str) and SECRET_REF_SYNTAX.match(sr)):
            errs.append(f"locations[{i}].secret_ref: 식별자 문법(^[A-Z][A-Z0-9_]+$)만 허용 — 값이 아니다")
        # headers 는 이름과 무관하게 값 박제 금지(값은 secret_ref 로만)
        for hk, hv in (loc.get("headers") or {}).items():
            if isinstance(hv, str) and hv.strip() and not (hv.startswith("secret_ref:") and SECRET_REF_SYNTAX.match(hv[11:])):
                errs.append(f"locations[{i}].headers.{hk}: 헤더 값 박제 금지 — 'secret_ref:NAME' 형식만")
        # URL 쿼리에 비밀류 키가 있으면 거부
        from urllib.parse import parse_qsl, urlsplit
        for qk, qv in parse_qsl(urlsplit(str(loc.get("url") or "")).query, keep_blank_values=True):
            if SECRET_QUERY_KEY.search(qk) and qv:
                errs.append(f"locations[{i}].url: 쿼리 키 '{qk}' 가 비밀류 — 값 박제 금지")
        for k, v in _walk(loc):
            if k == "secret_ref":
                continue
            if isinstance(v, str) and k not in ("url", "excerpt", "note") and not v.startswith("secret_ref:"):
                # 키 이름이 비밀류이거나(Authorization·Cookie·token…) 값이 비밀처럼 보이면 거부 — 이름(secret_ref)만 허용
                if SECRET_KEY_LIKE.search(k) or SECRET_VALUE_LIKE.search(v):
                    errs.append(f"locations[{i}].{k}: 비밀 값처럼 보이는 문자열 — secret_ref(이름)만 허용")
        if "query_values" in loc or "cookies" in loc:
            errs.append(f"locations[{i}]: 쿼리 값·쿠키는 박제하지 않는다 (request-profile-first)")
    return errs


def _walk(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, prefix)
    else:
        yield prefix, obj


def load(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        pb = yaml.safe_load(f) or {}
    errs = validate(pb)
    if errs:
        raise PlaybookError(f"{path}: " + "; ".join(errs))
    return pb


def merge(seed: dict[str, Any] | None, local: dict[str, Any] | None) -> dict[str, Any]:
    """위치 단위 병합: 로컬 > 시드. 로컬에 없는 시드 위치는 유지된다."""
    if seed is None and local is None:
        raise PlaybookError("병합 대상 없음")
    base = dict(seed or local or {})
    locs: dict[str, dict[str, Any]] = {l["location_id"]: dict(l) for l in (seed or {}).get("locations", [])}
    for l in (local or {}).get("locations", []):
        locs[l["location_id"]] = {**locs.get(l["location_id"], {}), **l, "origin": "local"}
    for lid, l in locs.items():
        l.setdefault("origin", "seed")
    base["locations"] = list(locs.values())
    base["schema_version"] = SCHEMA_VERSION
    return base


def resolve(host: str, domain: str, seed_dir: Path, local_dir: Path) -> dict[str, Any] | None:
    seed_p, local_p = seed_dir / domain / f"{host}.yaml", local_dir / domain / f"{host}.yaml"
    seed = load(seed_p) if seed_p.exists() else None
    local = load(local_p) if local_p.exists() else None
    if seed is None and local is None:
        return None
    return merge(seed, local)


def write_atomic(path: Path, pb: dict[str, Any]) -> None:
    errs = validate(pb)
    if errs:
        raise PlaybookError("; ".join(errs))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(pb, f, allow_unicode=True, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # 쓰기 중단 시 원본 무손상
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def propose(path: Path, pb: dict[str, Any]) -> Path:
    """확인 전 산출은 제안 파일로만 — 기존 플레이북을 덮어쓰지 않는다."""
    p = path.with_suffix(".proposal.yaml")
    write_atomic(p, pb)
    return p


def commit_proposal(proposal: Path) -> Path:
    target = proposal.with_name(proposal.name.replace(".proposal.yaml", ".yaml"))
    pb = load(proposal)
    write_atomic(target, pb)
    proposal.unlink()
    return target


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    p = argparse.ArgumentParser(description="플레이북 검증·조회·제안 커밋")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("path")
    r = sub.add_parser("resolve"); r.add_argument("--host", required=True); r.add_argument("--domain", required=True); r.add_argument("--seed-dir", required=True); r.add_argument("--local-dir", required=True)
    c = sub.add_parser("commit"); c.add_argument("proposal")
    a = p.parse_args(argv)
    try:
        if a.cmd == "validate":
            errs = validate(yaml.safe_load(open(a.path, encoding="utf-8")) or {})
            print("\n".join(errs) if errs else "ok"); return 1 if errs else 0
        if a.cmd == "resolve":
            pb = resolve(a.host, a.domain, Path(a.seed_dir), Path(a.local_dir))
            print(json.dumps(pb, ensure_ascii=False, indent=1) if pb else "null"); return 0
        if a.cmd == "commit":
            print(commit_proposal(Path(a.proposal))); return 0
    except PlaybookError as e:
        print(f"Error: {e}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
