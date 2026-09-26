"""scout_common.py — web-scout 공용: 경로 해석·형제 스킬(web-reader) 모듈 로더·데이터 디렉토리.

길 X(automation-responsibility-split): 이 스킬의 Python 은 MCP 를 직접 부르지 않는다. HTTP 는
web-reader 의 fetch_html/url_validator 를 **재사용**한다(중복 구현 금지 — R2 리뷰 결정).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
SEED_DIR = SKILL_DIR / "playbooks"
WEB_READER_SCRIPTS = SKILL_DIR.parent / "web-reader" / "scripts"
SCHEMA_VERSION = 1


def load_module(name: str, directory: Path | None = None) -> Any:
    d = directory or SCRIPTS_DIR
    path = d / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"모듈 없음: {path}")
    spec = importlib.util.spec_from_file_location(f"webscout_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def web_reader(name: str) -> Any:
    """형제 스킬 web-reader 의 스크립트 모듈(fetch_html·url_validator·extract_records·provenance)."""
    return load_module(name, WEB_READER_SCRIPTS)


def local_data_dir(subdir: str = "playbooks") -> Path:
    """로컬 누적 플레이북 위치 — shared/itda_path.resolve_data_dir("web-scout") (AGENTS.md 관례).
    itda_path 를 못 찾으면(배포본 밖) $ITDA_DATA_ROOT 또는 ./.itda-skills 로 폴백하되 그 사실을 stderr 에 남긴다.
    """
    for cand in (SKILL_DIR.parent.parent.parent / "shared", Path(os.environ.get("ITDA_SHARED_DIR", ""))):
        if cand and (cand / "itda_path.py").exists():
            sys.path.insert(0, str(cand))
            try:
                from itda_path import resolve_data_dir  # type: ignore[import]
                return Path(resolve_data_dir("web-scout", subdir))
            except Exception as e:  # pragma: no cover
                print(f"[web-scout] itda_path 실패({e}) — 폴백 경로 사용", file=sys.stderr)
            break
    root = Path(os.environ.get("ITDA_DATA_ROOT") or ".itda-skills")
    p = root / "web-scout" / subdir
    p.mkdir(parents=True, exist_ok=True)
    print(f"[web-scout] itda_path 미발견 — 로컬 플레이북 경로 폴백: {p}", file=sys.stderr)
    return p
