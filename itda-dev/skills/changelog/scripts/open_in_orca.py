#!/usr/bin/env python3
"""HTML 을 Orca 내장 브라우저 탭으로 연다 (제품별 이전 탭이 살아 있으면 재사용).

  python3 open_in_orca.py --product orca --file out.html --tag v1.4.177

탭을 실제로 연 뒤에만 state/<product>.json 을 갱신한다 — 중간에 실패하면
다음 실행에서 같은 구간이 다시 잡히도록.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# state 는 머신 로컬 가변 데이터라 스킬 디렉토리(저장소·플러그인 배포 자산) 밖에 둔다.
PROFILES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles"
)

STATE_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "itda-changelog",
)

# 별칭만 여기 적는다. 제품 자체는 profiles/<product>.json 이 있으면 자동으로 인식되므로
# 새 제품을 추가할 때 이 스크립트를 고칠 필요가 없다 (herdr 추가 때 이 구조로 바꿨다).
PRODUCT_ALIASES = {
    "claude": "claude-code",
    "claudecode": "claude-code",
    "cc": "claude-code",
    "codex-cli": "codex",
}


def known_products() -> list[str]:
    try:
        return sorted(
            f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith(".json")
        )
    except OSError:
        return []


def resolve_product(name: str) -> str | None:
    low = (name or "").lower()
    resolved = PRODUCT_ALIASES.get(low, low)
    return resolved if resolved in known_products() else None


def orca(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["orca", *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        print("[changelog] orca CLI 를 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        return 1, ""
    return p.returncode, p.stdout


def page_id_from(stdout: str) -> str | None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    result = data.get("result") or {}
    return result.get("browserPageId") or result.get("pageId") or data.get("browserPageId")


def load_state(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            pass
    return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True, help="profiles/ 에 있는 제품 (orca | claude(-code) | codex | herdr)")
    ap.add_argument("--file", required=True, help="열 HTML 경로")
    ap.add_argument("--tag", help="이번에 확인한 최신 태그 (last_seen 기록용)")
    ap.add_argument("--no-state", action="store_true", help="last_seen 갱신 안 함")
    args = ap.parse_args()

    product = resolve_product(args.product)
    if not product:
        print(f"[changelog] 알 수 없는 제품: {args.product} "
              f"({' | '.join(known_products())})", file=sys.stderr)
        sys.exit(1)
    state_path = os.path.join(STATE_DIR, f"{product}.json")

    path = os.path.abspath(args.file)
    if not os.path.exists(path):
        print(f"[changelog] 파일이 없습니다: {path}", file=sys.stderr)
        sys.exit(1)
    url = "file://" + path

    state = load_state(state_path)
    page_id = state.get("page_id")
    reused = False

    if page_id:
        code, _ = orca("tab", "show", "--page", page_id, "--json")
        if code == 0:
            code, _ = orca("goto", "--page", page_id, "--url", url)
            reused = code == 0
        if not reused:
            page_id = None

    if not page_id:
        code, out = orca("tab", "create", "--url", url, "--json")
        if code != 0:
            print("[changelog] Orca 탭을 열지 못했습니다. Orca 가 실행 중인지 확인하세요.",
                  file=sys.stderr)
            sys.exit(1)
        page_id = page_id_from(out)

    if not args.no_state:
        os.makedirs(STATE_DIR, exist_ok=True)
        state.update(
            {
                "tag": args.tag or state.get("tag"),
                "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "page_id": page_id,
            }
        )
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)

    print(
        f"[changelog] {product} · Orca 탭 {'재사용' if reused else '신규'} "
        f"(page {page_id}) · last_seen={args.tag or state.get('tag')}"
    )


if __name__ == "__main__":
    main()
