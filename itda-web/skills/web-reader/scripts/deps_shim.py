"""스킬별 설치 정문의 런타임 — `scripts/install_skill_deps.py` 가 import 한다 (#1630 S2~S5).

정본은 스킬 루트의 `deps.json`(manifest 에서 `deps_manifest.py gen-specs` 가 생성 — 손으로
고치면 validate ⑧ 이 RED). 이 모듈은 그 행들을 **그룹으로 골라** `deps_strategy` 가 정한
전략으로 pip 을 부른다. requirements 파일을 통째로 넘기지 않는다 — 그러면 optional·dev 까지
설치된다(4차 리뷰 P0-1).

## 설치 계약 (계획 §18 확정 — 2026-09-02)

    무인자      default = necessity ∈ {startup_required, feature_required} ∧ scope == runtime
                ∧ (provisioning ≠ transitive ∨ keep_in_install_target)     ← 마커 행은 포함(pip 이 평가)
    --all       + optional_enhancement (runtime)
    --dev       + scope ∈ {tests, evals, examples}
    --check     설치하지 않고 각 행의 import 가시성만 보고(exit 0 — 보고이지 판정이 아니다)
    --dry-run   고른 명령만 출력
    --json      기계 판독 출력

    exit  0 성공 (설치 대상이 비었으면 declares_no_deps 가 참일 때만)
          2 안전한 설치 경로 없음 — venv 제안
          3 pip 실패 — 실행한 명령과 대안을 stderr 에
          4 deps.json 부재·손상, 또는 빈 대상인데 declares_no_deps 가 아님
    PEP 723 스킬: pip 경로가 아니다 — uv 안내만 하고 0 (설치 명령을 만들지 않는다)
    pip 밖 의존(tesseract 등): 설치 뒤 안내만 (우리가 못 지키는 약속은 하지 않는다)

stdlib only. `deps_strategy` 는 배포본에서 같은 `scripts/` 에 평면 복사돼 있고, 소스 체크아웃에서는
shim 이 `skills/shared` 를 찾아 sys.path 에 넣는다(2차 리뷰 P0-2 — 소스·배포 양쪽에서 같은 명령).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from deps_strategy import (UNSUPPORTED, Environment, decide_strategy, render_command,
                           suggest_venv)

SCHEMA = 1
DEFAULT_NECESSITY = {"startup_required", "feature_required"}
DEV_SCOPES = {"tests", "evals", "examples"}


class SpecError(Exception):
    pass


def load_spec(skill_dir: Path) -> dict:
    p = skill_dir / "deps.json"
    if not p.is_file():
        raise SpecError(f"deps.json 이 없습니다: {p} — 이 스킬은 설치 정문이 없거나 배포본이 손상됐습니다")
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SpecError(f"deps.json 을 읽을 수 없습니다: {e}") from e
    if spec.get("schema") != SCHEMA or "rows" not in spec:
        raise SpecError(f"deps.json schema 불일치(기대 {SCHEMA})")
    return spec


def select_rows(spec: dict, *, all_: bool = False, dev: bool = False) -> list[dict]:
    out = []
    for r in spec["rows"]:
        nec, scope = r["necessity"], r["scope"]
        if nec == "unused":
            continue
        transitive_skip = r["provisioning"].startswith("transitive") and not r.get("keep_in_install_target")
        if scope == "runtime":
            if nec in DEFAULT_NECESSITY and not transitive_skip:
                out.append(r)
            elif all_ and nec == "optional_enhancement" and not transitive_skip:
                out.append(r)
        elif dev and scope in DEV_SCOPES and nec != "unused":
            out.append(r)
    return out


def requirement_of(r: dict) -> str:
    s = f"{r['dist']}{r.get('specifier') or ''}"
    if r.get("marker"):
        s += f"; {r['marker']}"
    return s


def visible(import_names: list[str]) -> bool | None:
    if not import_names:
        return None
    return all(importlib.util.find_spec(n) is not None for n in import_names)


def check(spec: dict, rows: list[dict]) -> dict:
    return {"skill": spec["skill"],
            "rows": [{"dist": r["dist"], "necessity": r["necessity"], "visible": visible(r.get("import_names", []))}
                     for r in rows]}


def main(skill_dir: Path, argv: list[str] | None = None, *, runner=subprocess.run) -> int:
    ap = argparse.ArgumentParser(prog="install_skill_deps",
                                 description="이 스킬의 의존성을 이 환경에 맞는 방식으로 설치한다(정본: deps.json)")
    ap.add_argument("--all", action="store_true", help="선택 의존(optional)까지 설치")
    ap.add_argument("--dev", action="store_true", help="tests·evals·examples 의존까지 설치")
    ap.add_argument("--check", action="store_true", help="설치하지 않고 현재 상태만 보고")
    ap.add_argument("--dry-run", action="store_true", help="고른 명령만 출력")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        spec = load_spec(skill_dir)
    except SpecError as e:
        print(f"[deps] {e}", file=sys.stderr)
        return 4

    if spec.get("pep723"):
        ep = spec["pep723"].get("entrypoint", "")
        msg = (f"[deps] {spec['skill']}: pip 설치 경로가 아닙니다 — 정문 `{ep}` 이 `uv run --script` 로 "
               f"의존({', '.join(r['dist'] for r in spec['rows'])})을 자동 관리합니다. uv 가 없으면 설치하세요: https://docs.astral.sh/uv/")
        print(json.dumps({"skill": spec["skill"], "pep723": True, "entrypoint": ep}, ensure_ascii=False) if a.json else msg)
        return 0

    rows = select_rows(spec, all_=a.all, dev=a.dev)
    if a.check:
        rep = check(spec, rows)
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=1))
        else:
            for r in rep["rows"]:
                print(f"  {'✓' if r['visible'] else '✗' if r['visible'] is False else '?'} {r['dist']} ({r['necessity']})")
        return 0

    targets = [requirement_of(r) for r in rows]
    if not targets:
        if spec.get("declares_no_deps"):
            print(f"[deps] {spec['skill']}: 설치할 의존이 없습니다 — {spec.get('no_deps_rationale', '')}")
            return 0
        print(f"[deps] {spec['skill']}: 고른 그룹에 설치 대상이 없는데 declares_no_deps 도 아닙니다 — deps.json 을 확인하세요",
              file=sys.stderr)
        return 4

    env = Environment.detect()
    strategy = decide_strategy(env)
    if strategy.kind == UNSUPPORTED:
        print(f"[deps] {strategy.reason}\n\n{suggest_venv(env)}", file=sys.stderr)
        return 2
    cmd = strategy.command(env.python, targets)
    shown = render_command(cmd)
    if a.json:
        print(json.dumps({"skill": spec["skill"], "strategy": strategy.kind, "targets": targets,
                          "command": cmd, "command_display": shown, "dry_run": a.dry_run}, ensure_ascii=False, indent=1))
    else:
        print(f"[deps] {strategy.reason}")
        for w in strategy.warnings:
            print(f"[deps] ⚠ {w}")
        print(f"[deps] 실행: {shown}")
    if a.dry_run:
        return 0
    proc = runner(cmd)
    rc = getattr(proc, "returncode", 1)
    if rc != 0:
        print(f"\n[deps] 설치에 실패했습니다(rc={rc}). 아래를 직접 실행해 보세요:\n  {shown}\n\n{suggest_venv(env)}",
              file=sys.stderr)
        return 3
    for np_ in spec.get("non_pip", []):
        print(f"[deps] ⚠ {np_['dist']} 는 pip 밖 의존이 더 필요합니다: {np_['requirement']} — 직접 설치하세요")
    return 0
