#!/usr/bin/env python3
"""run_playbook.py — S8 반복 조회 runner: 플레이북 hit → 재생 → 추출 레코드 → 결과 분류 → 회차 diff → 제안.

계약(이슈 #1600 §목표 4·5, 구현 리뷰 P1 "종단 경로"):
- 플레이북 위치의 `repeat_access` 단만 실행한다. L1/L2/L3 은 web-reader `fetch_html` 로 GET 1회(+플레이북 next 링크
  페이지네이션은 v0.3), C(L4) 는 **에이전트 몫** — runner 는 `needs_browser` 에 `l4_sequence` 를 실어 반환하고,
  에이전트가 저장한 raw HTML 을 `--l4-raw <dir>/<location_id>.html` 로 넘기면 같은 후처리(레코드·분류·diff)를 탄다(길 X).
- 산출 = 추출 레코드(web-reader `extract_records`, 봉투 포함) → `<data>/runs/<domain>/<host>/<location_id>/<UTC>.json`.
- 결과는 `grade.classify_result` 5분류. `incomplete|schema_drift` 는 재탐색 대상 → 플레이북을 **덮어쓰지 않고**
  `<data>/proposals/<domain>/<host>.proposal.yaml` 에 제안(evidence 갱신 + note). `auth_expired` 는 typed 종결.
- 회차 diff: 키 = source_url(없으면 link_raw). 신규·소실·변경(title/published/excerpt). 페이지 수준은 봉투 content_hash.
- 예산: 호스트당 물리 요청 ≤ --budget(기본 40, fetch_html trace 로 집계). 초과 시 남은 위치는 `budget_exceeded`.
- exit 0: 전 위치 성공(fresh_nonempty/empty_valid) · 2: stale/typed 실패/브라우저 필요 있음 · 1: 사용 오류.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_common import SEED_DIR, load_module, local_data_dir, web_reader  # noqa: E402

grade = load_module("grade")
pbm = load_module("playbook")
SUCCESS = {"fresh_nonempty", "empty_valid"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _vis(html: str) -> int:
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html or "", flags=re.S | re.I)
    return len(re.sub(r"\s+", " ", t).strip())


def expected_from(loc: dict[str, Any]) -> Any:
    e = loc.get("expected") or {}
    return grade.ExpectedShape(
        content_type_prefix=e.get("content_type_prefix", "text/html"),
        required_record_keys=tuple(e.get("required_record_keys", ("source_url", "title", "published"))),
        min_records=int(e.get("min_records", 1)),
        freshness_days=e.get("freshness_days"),
        denominator=e.get("denominator"),
    )


class Budget:
    def __init__(self, n: int) -> None:
        self.limit, self.used = n, 0

    def can(self) -> bool:
        return self.used < self.limit

    def account(self, r: dict | None) -> None:
        tr = (r or {}).get("trace")
        self.used += max(1, len(tr)) if isinstance(tr, list) else 1


def replay_static(fh: Any, loc: dict[str, Any], budget: Budget) -> dict[str, Any]:
    """L1~L3: GET 1회. 반환: raw·봉투 재료·진단."""
    if not budget.can():
        return {"diag": "budget_exceeded", "html": "", "status": None, "ct": "", "final_url": loc["url"], "encoding": None, "sha": None, "waf": None, "phase": "static"}
    try:
        r = fh.fetch_url(loc["url"])
    except Exception as e:
        budget.account(None)
        return {"diag": "fetch_error", "error": str(e), "html": "", "status": None, "ct": "", "final_url": loc["url"], "encoding": None, "sha": None, "waf": None, "phase": "static"}
    budget.account(r)
    html = str(r.get("content") or "")
    ct = str((r.get("headers") or {}).get("content-type") or ("application/xml" if html.lstrip().startswith("<?xml") else "text/html"))
    sig = grade.Signal(status=r.get("status_code"), content_type=ct, html=html, visible_len=_vis(html), min_text_length=200)
    diag = "ok" if (html.lstrip().startswith("<?xml") and r.get("status_code") == 200) else grade.diagnose(sig)
    tr = r.get("trace") or []
    return {"diag": diag, "html": html, "status": r.get("status_code"), "ct": ct, "final_url": str(r.get("url") or loc["url"]), "encoding": r.get("encoding"),
            "sha": r.get("content_sha256"), "waf": r.get("waf_profile"), "phase": (tr[-1].get("phase") if tr and isinstance(tr[-1], dict) else "static") or "static"}


def postprocess(loc: dict[str, Any], fetched: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """raw → 레코드(봉투 포함) → 분류. L4 raw 도 같은 함수를 탄다."""
    er, prov = web_reader("extract_records"), web_reader("provenance")
    page = prov.build_provenance(fetched["html"], raw_sha256=fetched.get("sha"), requested_url=loc["url"], final_url=fetched.get("final_url"),
                                 status=fetched.get("status"), fetched_at=_now(), encoding=fetched.get("encoding"), fetch_phase=fetched.get("phase", "static"), waf_profile=fetched.get("waf"))
    records: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    if fetched["html"] and fetched["diag"] in ("ok", "thin"):
        recs, page_text, stats = er.extract_records(fetched["html"], base_url=fetched.get("final_url") or loc["url"], js_link=loc.get("js_link"), js_link_template=loc.get("js_link_template"))
        records, rejected = er.finalize_records(recs, page_text)
        stats["rejected_excerpt"] = rejected
        for r in records:
            r["page_final_url"], r["page_fetched_at"] = page["final_url"], page["fetched_at"]
        if not records and stats.get("reason") == "no_dated_list" and expected_from(loc).min_records >= 1:
            fetched = {**fetched, "diag": "no_dated_list"}  # HTML 에서 목록 구조를 못 찾은 0건은 무소식이 아니다 — 재탐색 신호(거짓 성공 차단, CEO Brief 실측)
    obs = grade.Observation(status=fetched.get("status"), content_type=fetched.get("ct", ""), records=records, today=today, diag=fetched["diag"] if fetched["diag"] != "ok" else None)
    result = grade.classify_result(obs, expected_from(loc)) if fetched["diag"] not in ("budget_exceeded", "fetch_error", "browser_unavailable") else fetched["diag"]
    return {"location_id": loc["location_id"], "item": loc["item"], "url": loc["url"], "repeat_access": loc["repeat_access"], "diag": fetched["diag"], "result": result,
            "page": page, "records": records, "stats": stats, "error": fetched.get("error")}


def diff_records(prev: dict[str, Any] | None, cur: dict[str, Any]) -> dict[str, Any]:
    key = lambda r: r.get("source_url") or r.get("link_raw") or r.get("title")  # noqa: E731
    p = {key(r): r for r in (prev or {}).get("records", [])}
    c = {key(r): r for r in cur.get("records", [])}
    changed = [k for k in c.keys() & p.keys() if any(c[k].get(f) != p[k].get(f) for f in ("title", "published", "excerpt"))]
    return {"new": sorted(c.keys() - p.keys(), key=str), "gone": sorted(p.keys() - c.keys(), key=str), "changed": sorted(changed, key=str),
            "page_changed": bool(prev) and prev.get("page", {}).get("content_hash") != cur["page"]["content_hash"], "prev_run": (prev or {}).get("_run_file")}


def latest_run(run_dir: Path) -> dict[str, Any] | None:
    files = sorted(run_dir.glob("*.json"))
    if not files:
        return None
    d = json.loads(files[-1].read_text(encoding="utf-8"))
    d["_run_file"] = files[-1].name
    return d


def save_run(run_dir: Path, out: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / (out["page"]["fetched_at"].replace(":", "") + ".json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def run(host: str, domain: str, *, seed_dir: Path, local_dir: Path, data_dir: Path, budget_n: int = 40, l4_raw: Path | None = None, today: date | None = None, fh: Any = None) -> dict[str, Any]:
    pb = pbm.resolve(host, domain, seed_dir, local_dir)
    if pb is None:
        raise SystemExit(f"플레이북 없음: {domain}/{host} — S3 발견 프로브부터 시작하라")
    fh = fh or web_reader("fetch_html")
    budget = Budget(budget_n)
    t0 = time.time()
    report: dict[str, Any] = {"host": host, "domain": domain, "started_at": _now(), "locations": [], "needs_browser": [], "proposal": None}
    stale_notes: list[str] = []
    for loc in pb.get("locations", []):
        run_dir = data_dir / "runs" / domain / host / loc["location_id"]
        if loc["repeat_access"] == "L4":
            raw = (l4_raw / f"{loc['location_id']}.html") if l4_raw else None
            if raw and raw.exists():
                fetched = {"diag": "ok", "html": raw.read_text(encoding="utf-8", errors="replace"), "status": 200, "ct": "text/html", "final_url": loc["url"], "encoding": "utf-8", "sha": None, "waf": None, "phase": "l4_raw"}
            else:
                report["needs_browser"].append({"location_id": loc["location_id"], "url": loc["url"], "l4_sequence": loc.get("l4_sequence"), "save_as": f"<l4-raw>/{loc['location_id']}.html"})
                report["locations"].append({"location_id": loc["location_id"], "item": loc["item"], "repeat_access": "L4", "diag": "browser_unavailable", "result": "browser_unavailable", "records": [], "diff": None})
                continue
        elif loc["auth_state"] != "none":
            report["locations"].append({"location_id": loc["location_id"], "item": loc["item"], "repeat_access": loc["repeat_access"], "diag": "auth_state", "result": "auth_expired", "records": [], "diff": None})
            continue
        else:
            fetched = replay_static(fh, loc, budget)
        out = postprocess(loc, fetched, today)
        prev = latest_run(run_dir)
        out["diff"] = diff_records(prev, out)
        out["_run_file"] = save_run(run_dir, out).name
        report["locations"].append({k: out[k] for k in ("location_id", "item", "url", "repeat_access", "diag", "result", "records", "stats", "diff", "error", "_run_file")} | {"page": out["page"]})
        if out["result"] in grade.IS_STALE:
            stale_notes.append(f"{loc['location_id']}: {out['result']} (diag={out['diag']}, records={len(out['records'])})")
    report["requests"], report["elapsed_s"] = budget.used, round(time.time() - t0, 1)
    if stale_notes:
        prop = dict(pb)
        prop.pop("origin", None)
        for l in prop["locations"]:
            l.pop("origin", None)
            note = next((n for n in stale_notes if n.startswith(l["location_id"] + ":")), None)
            if note:
                l["evidence"] = {**l.get("evidence", {}), "stale_observed_at": report["started_at"], "stale_note": note}
        prop_path = data_dir / "proposals" / domain / f"{host}.yaml"
        report["proposal"] = str(pbm.propose(prop_path, prop))
        report["stale"] = stale_notes
    results = [l["result"] for l in report["locations"]]
    report["ok"] = bool(results) and all(r in SUCCESS for r in results)
    return report


def render_md(rep: dict[str, Any]) -> str:
    lines = [f"# web-scout 재생 — {rep['domain']}/{rep['host']} ({rep['started_at']}) · 요청 {rep.get('requests', 0)} · {rep.get('elapsed_s', 0)}s", "",
             "| 위치 | 단 | 진단 | 결과 | 레코드 | 신규/변경/소실 |", "|---|---|---|---|---|---|"]
    for l in rep["locations"]:
        d = l.get("diff") or {}
        lines.append(f"| {l['item']} | {l['repeat_access']} | {l['diag']} | **{l['result']}** | {len(l.get('records', []))} | {len(d.get('new', []))}/{len(d.get('changed', []))}/{len(d.get('gone', []))} |")
    if rep["needs_browser"]:
        lines += ["", "## 브라우저 필요(에이전트가 l4_sequence 실행 후 `--l4-raw` 로 raw 전달)"] + [f"- {n['location_id']}: {n['url']} → `{n['save_as']}`" for n in rep["needs_browser"]]
    if rep.get("proposal"):
        lines += ["", f"## 재탐색 제안(플레이북은 덮어쓰지 않았다): `{rep['proposal']}`"] + [f"- {s}" for s in rep.get("stale", [])]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="S8 플레이북 재생 runner")
    p.add_argument("--host", required=True); p.add_argument("--domain", required=True)
    p.add_argument("--seed-dir", default=str(SEED_DIR)); p.add_argument("--local-dir"); p.add_argument("--data-dir")
    p.add_argument("--budget", type=int, default=40); p.add_argument("--l4-raw"); p.add_argument("--json", action="store_true"); p.add_argument("--output")
    a = p.parse_args(argv)
    local_dir = Path(a.local_dir) if a.local_dir else local_data_dir("playbooks")
    data_dir = Path(a.data_dir) if a.data_dir else local_data_dir("").parent if False else (Path(a.data_dir) if a.data_dir else local_data_dir("runs").parent)
    rep = run(a.host, a.domain, seed_dir=Path(a.seed_dir), local_dir=local_dir, data_dir=data_dir, budget_n=a.budget, l4_raw=Path(a.l4_raw) if a.l4_raw else None)
    text = json.dumps(rep, ensure_ascii=False, indent=1) if a.json else render_md(rep)
    (Path(a.output).write_text(text, encoding="utf-8") if a.output else sys.stdout.write(text))
    return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
