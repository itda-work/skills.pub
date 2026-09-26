#!/usr/bin/env python3
"""제품(Orca·Claude Code·Codex CLI) 릴리즈 노트를 수집·정제해 요약용 JSON 으로 만든다.

판단은 하지 않는다 — 결정론적 수집·파싱·분류만 담당하고,
"무엇이 중요한가" 는 SKILL.md 의 지시에 따라 에이전트가 정한다.

  python3 collect.py --product orca                # 기본: 프로파일의 최근 N일
  python3 collect.py --product claude --since 7d   # 기간 (d/w)
  python3 collect.py --product codex --since rust-v0.146.0   # 그 태그 '이후'
  python3 collect.py --product orca --new          # state/<product>.json 이후
  python3 collect.py --product orca --all          # 받아온 전 구간
  python3 collect.py --product orca --full         # 제외 표면도 items 에 포함

제품별 파싱 스타일은 profiles/<product>.json 의 parser.style 이 정한다:
  conventional — `* feat(scope)!: 제목` (Orca)
  prose        — `- Added/Fixed/Improved …` 산문형 (Claude Code)
  sections     — 섹션명(New Features/…)이 kind, 말미 PR 덤프 분리 (Codex)
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(SKILL_DIR, "profiles")
# state 는 머신 로컬 가변 데이터라 스킬 디렉토리(저장소·플러그인 배포 자산) 밖에 둔다.
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

# `* fix(terminal)!: 제목 by @user in https://github.com/o/r/pull/123`
CONVENTIONAL_RE = re.compile(
    r"^(?:(?P<kind>feat|fix|perf|refactor|chore|docs|test|build|ci|style|revert)"
    r"(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*)?(?P<title>.+)$"
)
PR_RE = re.compile(r"https://github\.com/[^/]+/[^/]+/pull/(\d+)")
# 오래된 릴리즈는 URL 대신 제목 끝에 `(#12280)` 로 PR 을 단다(orca v1.4.164·167 실측).
# codex 큐레이션 불릿은 `(#36544, #36409)` 처럼 복수를 단다.
PR_GROUP_RE = re.compile(r"\((#\d{3,6}(?:\s*,\s*#\d{3,6})*)\)\s*$")
PR_INLINE_RE = re.compile(r"\(#(\d{3,6})\)")
AUTHOR_RE = re.compile(r"\s+by\s+@[\w-]+(?=\s|$)")
# ` in https://github.com/o/r/pull/123` — 뒤에 릴리즈 노트가 덧붙인 사유가
# 오는 경우가 있어 문자열 끝에 고정하지 않는다(Revert 항목의 "— … not shipped").
TRAIL_RE = re.compile(r"\s+in\s+https://github\.com/\S*?/pull/\d+")
SHA_RE = re.compile(r"\s*\(`[0-9a-f]{7,}`\)")
BRACKET_SCOPE_RE = re.compile(r"^\[([^\]]{1,24})\]\s*")
# codex '## Changelog' 덤프: `- #35590 제목 @author`
DUMP_ITEM_RE = re.compile(r"^#(\d{3,7})\s+(?P<title>.+?)(?:\s+@[\w-]+)?$")
SKIP_LINE = ("made their first contribution", "**Full Changelog**", "Full Changelog:")
SKIP_SECTION = ("new contributors", "contributors")


def die(msg: str) -> None:
    print(f"[changelog] {msg}", file=sys.stderr)
    sys.exit(1)


def load_profile(product: str) -> dict:
    path = os.path.join(PROFILES_DIR, f"{product}.json")
    if not os.path.exists(path):
        die(f"프로파일이 없습니다: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def installed_version(profile: dict) -> str | None:
    plist_path = profile.get("app_plist")
    if plist_path:
        try:
            with open(plist_path, "rb") as fh:
                return plistlib.load(fh).get("CFBundleShortVersionString")
        except Exception:
            return None
    cmd = profile.get("version_cmd")
    if cmd:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except Exception:
            return None
        if out.returncode != 0:
            return None
        m = re.search(r"\d+(?:\.\d+)+", out.stdout or "")
        return m.group(0) if m else None
    return None


def version_tuple(tag: str) -> tuple:
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def fetch_releases(repo: str) -> list[dict]:
    cmd = ["gh", "api", f"repos/{repo}/releases?per_page=100"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        die("gh CLI 를 찾을 수 없습니다. `brew install gh` 후 `gh auth login`.")
    except subprocess.TimeoutExpired:
        die("gh api 호출이 90초를 넘겼습니다.")
    if out.returncode != 0:
        die(f"gh api 실패 (exit {out.returncode}): {out.stderr.strip()[:400]}")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        die(f"gh api 응답을 JSON 으로 읽지 못했습니다: {exc}")


def extract_prs(line: str) -> list[int]:
    """PR 참조 전부 (URL 형·괄호 인라인형·복수형)."""
    prs = [int(n) for n in PR_RE.findall(line)]
    group = PR_GROUP_RE.search(line)
    if group:
        prs += [int(n) for n in re.findall(r"\d+", group.group(1))]
    elif not prs:
        prs = [int(n) for n in PR_INLINE_RE.findall(line)][-1:]
    # 순서 보존 dedup
    seen: set[int] = set()
    return [p for p in prs if not (p in seen or seen.add(p))]


def clean_title(title: str) -> str:
    title = TRAIL_RE.sub("", title)
    title = AUTHOR_RE.sub("", title)
    title = SHA_RE.sub("", title)
    title = PR_GROUP_RE.sub("", title)
    return title.strip()


def parse_body(body: str, parser: dict) -> tuple[list[dict], list[dict]]:
    """릴리즈 본문 → (항목, 덤프 항목). 기여자 절·Full Changelog 는 버린다."""
    style = parser.get("style", "conventional")
    verb_kinds = {k.lower(): v for k, v in parser.get("verb_kinds", {}).items()}
    section_kinds = {k.lower(): v for k, v in parser.get("section_kinds", {}).items()}
    dump_sections = {s.lower() for s in parser.get("dump_sections", [])}

    items: list[dict] = []
    dump: list[dict] = []
    section = None
    for raw in (body or "").splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        stripped = line.lstrip()
        if not (stripped.startswith("* ") or stripped.startswith("- ")):
            continue
        line = stripped[2:].strip()
        if not line or any(tok in line for tok in SKIP_LINE):
            continue
        low_sec = (section or "").lower()
        if low_sec in SKIP_SECTION:
            continue

        if low_sec in dump_sections:
            m = DUMP_ITEM_RE.match(line)
            if m:
                dump.append({"pr": int(m.group(1)), "title": clean_title(m.group("title"))})
            continue

        prs = extract_prs(line)
        kind = scope = ""
        breaking = False
        title = line

        if style == "conventional":
            match = CONVENTIONAL_RE.match(line)
            if match:
                title = match.group("title")
                kind = match.group("kind") or ""
                scope = (match.group("scope") or "").lower()
                breaking = bool(match.group("bang"))
        elif style == "prose":
            bracket = BRACKET_SCOPE_RE.match(title)
            if bracket:
                scope = bracket.group(1).lower()
                title = BRACKET_SCOPE_RE.sub("", title)
            first_word = re.match(r"[A-Za-z]+", title)
            if first_word:
                kind = verb_kinds.get(first_word.group(0).lower(), "")
        elif style == "sections":
            kind = section_kinds.get(low_sec, "")

        title = clean_title(title)
        is_revert = (
            kind == "revert"
            or title.lower().startswith("revert")
            or "revert" in low_sec
        )
        # 관례 표기만 인정한다 — 소문자 "breaking" 은 제목에 흔히 쓰인다
        # ("without breaking TUIs" 를 breaking change 로 오판한 실측).
        if "BREAKING CHANGE" in line or "BREAKING:" in line or kind == "breaking":
            breaking = True

        items.append(
            {
                "section": section,
                "kind": kind or ("revert" if is_revert else ""),
                "scope": scope,
                "title": title,
                "pr": prs[0] if prs else None,
                "prs": prs,
                "breaking": breaking,
                "revert": is_revert,
            }
        )
    return items, dump


def resolve_window(args, profile: dict, state_path: str) -> tuple[str, dict]:
    """(설명, 판정함수 재료) 반환. 판정은 아래 select() 가 한다."""
    if args.all:
        return "전체(수집 범위)", {"mode": "all"}
    if args.new:
        tag = None
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as fh:
                tag = json.load(fh).get("tag")
        if not tag:
            days = profile.get("default_window_days", 3)
            return f"최근 {days}일(이전 확인 기록 없음)", {"mode": "days", "days": days}
        return f"{tag} 이후", {"mode": "after_tag", "tag": tag}
    if args.since:
        s = args.since.strip()
        m = re.fullmatch(r"(\d+)\s*([dwDW])", s)
        if m:
            days = int(m.group(1)) * (7 if m.group(2).lower() == "w" else 1)
            return f"최근 {days}일", {"mode": "days", "days": days}
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return f"{s} 이후", {"mode": "date", "date": s}
        return f"{s} 이후", {"mode": "after_tag", "tag": s}
    days = profile.get("default_window_days", 3)
    return f"최근 {days}일", {"mode": "days", "days": days}


def select(stable: list[dict], spec: dict) -> list[dict]:
    mode = spec["mode"]
    if mode == "all":
        return list(stable)
    if mode == "days":
        cut = datetime.now(timezone.utc) - timedelta(days=spec["days"])
        return [r for r in stable if r["_dt"] >= cut]
    if mode == "date":
        cut = datetime.fromisoformat(spec["date"]).replace(tzinfo=timezone.utc)
        return [r for r in stable if r["_dt"] >= cut]
    if mode == "after_tag":
        floor = version_tuple(spec["tag"])
        return [r for r in stable if version_tuple(r["tag_name"]) > floor]
    return list(stable)


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--product", required=True,
                    help="profiles/ 에 있는 제품 (orca | claude(-code) | codex | herdr)")
    ap.add_argument("--since", help="3d | 2w | 2026-08-01 | v1.4.170")
    ap.add_argument("--new", action="store_true", help="마지막으로 본 태그 이후")
    ap.add_argument("--all", action="store_true", help="수집 범위 전체")
    ap.add_argument("--full", action="store_true", help="제외 표면도 본문에 포함")
    ap.add_argument("--out", help="JSON 출력 경로 (기본 stdout)")
    args = ap.parse_args()

    product = resolve_product(args.product)
    if not product:
        die(f"알 수 없는 제품: {args.product} ({' | '.join(known_products())})")

    profile = load_profile(product)
    repo = profile["repo"]
    parser_cfg = profile.get("parser", {})
    conventional = parser_cfg.get("style", "conventional") == "conventional"
    excluded = set(profile.get("excluded_scopes", []))
    state_path = os.path.join(STATE_DIR, f"{product}.json")

    raw = fetch_releases(repo)
    stable = []
    for r in raw:
        if r.get("prerelease") or r.get("draft"):
            continue
        r["_dt"] = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
        stable.append(r)
    stable.sort(key=lambda r: r["_dt"], reverse=True)
    if not stable:
        die(f"{repo} 에서 정식 릴리즈를 찾지 못했습니다.")

    label, spec = resolve_window(args, profile, state_path)
    picked = select(stable, spec)

    # 기간 창이 비면(주말 등) 가장 최근 1개까지 넓힌다. 그러나 "태그 이후" 는
    # 비어 있는 것 자체가 답("새 릴리즈 없음")이라 넓히지 않는다.
    widened = no_new = False
    if not picked:
        if spec["mode"] == "after_tag":
            no_new = True
        else:
            picked = stable[:1]
            widened = True

    # 요청 구간이 수집 범위(최근 100건)보다 과거까지 뻗는지
    truncated = spec["mode"] in ("days", "date") and picked and picked[-1] is stable[-1]

    installed = installed_version(profile)
    inst_t = version_tuple(installed) if installed else None

    # Orca 는 오래된 릴리즈 항목을 이후 릴리즈에 다시 싣는다("Also included from …").
    # 원본은 **먼저 나온 쪽**이므로 과거 → 최신 순으로 훑어 첫 등장에 원본 자격을 주고,
    # 나중 릴리즈의 재등장을 재수록으로 표시한다. (타 제품에도 무해 — PR 재등장이 없으면 no-op)
    parsed = [(r, *parse_body(r.get("body"), parser_cfg)) for r in picked]
    seen_prs: dict[int, str] = {}
    for r, items, _dump in reversed(parsed):  # 과거 → 최신
        for it in items:
            pr = it.get("pr")
            if not pr:
                continue
            if pr in seen_prs:
                it["dup_of"] = seen_prs[pr]
            else:
                seen_prs[pr] = r["tag_name"]

    releases = []
    for r, items, dump_items in parsed:  # 최신 → 과거 (출력 순서)
        kept, dropped = [], []
        for it in items:
            (dropped if (it["scope"] in excluded and it["scope"] and not args.full) else kept).append(it)

        # 표면별 집계: conventional 은 scope, 산문·섹션형은 kind 로 센다
        counts: dict[str, int] = {}
        for it in kept:
            if it.get("dup_of"):
                continue  # 그 릴리즈의 '새로운' 것만 센다
            key = (it["scope"] if conventional else it["kind"]) or "(분류 없음)"
            counts[key] = counts.get(key, 0) + 1

        releases.append(
            {
                "tag": r["tag_name"],
                "published": r["published_at"],
                "date": r["published_at"][:10],
                "url": r["html_url"],
                "total": len(items),
                "dup": sum(1 for it in kept if it.get("dup_of")),
                "excluded": len(dropped),
                "excluded_scopes": sorted({d["scope"] for d in dropped if d["scope"]}),
                "empty": len(items) == 0 and len(dump_items) == 0,
                "installed": bool(inst_t and version_tuple(r["tag_name"]) <= inst_t),
                "scope_counts": dict(
                    sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
                "items": kept,
                "dump_items": dump_items,
            }
        )

    payload = {
        "product": product,
        "product_label": profile.get("display_name", product),
        "repo": repo,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_label": label,
        "window_widened": widened,
        "no_new": no_new,
        "range_truncated": bool(truncated),
        "installed_version": installed,
        "release_count": len(releases),
        "item_total": sum(x["total"] for x in releases),
        "item_kept": sum(len(x["items"]) for x in releases),
        "item_dup": sum(x["dup"] for x in releases),
        "item_excluded": sum(x["excluded"] for x in releases),
        "dump_total": sum(len(x["dump_items"]) for x in releases),
        "scope_labels": profile.get("scope_labels", {}),
        "releases": releases,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        name = payload["product_label"]
        if no_new:
            print(f"[changelog] {name} · {label} — 새 릴리즈 없음 (요약·렌더 불필요) → {args.out}")
        else:
            note = " · 창 확장됨" if widened else ""
            dup = f"·중복 {payload['item_dup']}" if payload["item_dup"] else ""
            dumps = f" · PR 덤프 {payload['dump_total']}건" if payload["dump_total"] else ""
            print(
                f"[changelog] {name} · {label}{note} · 릴리즈 {payload['release_count']}개 · "
                f"{payload['item_kept']}건(제외 {payload['item_excluded']}{dup}){dumps} → {args.out}"
            )
    else:
        print(text)


if __name__ == "__main__":
    main()
