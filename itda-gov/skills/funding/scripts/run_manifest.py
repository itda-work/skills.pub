#!/usr/bin/env python3
# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: 로그 태그를 [funding] 으로 교체. schema v1 계약은 원본 그대로.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""Shared writer for run_manifest.json (schema v1) — funding 수집 크롤러 공용.

Both crawlers (kstartup_crawl.py, sources_crawl.py) call update_manifest()
at the end of every `list` run (success AND partial) so that coverage can be
read from a machine-readable file instead of scraping stderr.

Schema v1 (one file per output folder, next to the jsonl):

  {
    "manifest_schema_version": 1,
    "generated_at": "2026-07-23T22:00:00+09:00",   # ISO8601, KST
    "runs": [
      {
        "source": "kstartup",
        "status": "ok" | "partial" | "manual" | "inactive",
        "exit_code": 0 | 2,
        "pages_fetched": 12,
        "reported_total": 260,        # optional — only if the site reports one
        "collected": 178,
        "duplicates": 30,             # optional — carousel/pagination repeats
        "stop_reason": "no-new-2pages",
        "cutoff": null,               # --since value when the run used one
        "errors": ["page 3: HTTP 500"]
      }
    ]
  }

Merge semantics: if a run_manifest.json already exists in the folder
(e.g. `list all`, or kstartup then bizinfo into the same survey folder),
new runs are appended and an existing entry for the SAME source is replaced
by the newest one. The file is always rewritten atomically (tmp → os.replace)
so a crash can never leave a half-written manifest.

Privacy: only counts/status/reasons go in — never search terms, profile
fields, or announcement bodies.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_NAME = "run_manifest.json"


def _reject_dup_keys(pairs):
    """object_pairs_hook — 중복 키 거부(Codex #12). 중복 manifest_schema_version/
    status가 #10 검증을 우회하지 못하게 매니페스트 로드에도 적용한다."""
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"duplicate JSON key: {k!r}")
        d[k] = v
    return d
KST = timezone(timedelta(hours=9))
VALID_STATUS = ("ok", "partial", "manual", "inactive")


def make_run(source, status, exit_code, pages_fetched, collected, stop_reason,
             errors=None, reported_total=None, duplicates=None, cutoff=None):
    """Build one schema-v1 run entry. Counts/status only — no content."""
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r} (expected one of {VALID_STATUS})")
    # 정합성 계약(Codex #10): 상태와 종료코드는 모순될 수 없다. ok는 성공(0),
    # 그 외(partial/manual/inactive)는 반드시 비-0이어야 한다. 음수 카운트도 거부.
    exit_code = int(exit_code)
    if status == "ok" and exit_code != 0:
        raise ValueError(f"status=ok인데 exit_code={exit_code} (0이어야 함)")
    if status != "ok" and exit_code == 0:
        raise ValueError(f"status={status!r}인데 exit_code=0 (비-0이어야 함)")
    for label, val in (("pages_fetched", pages_fetched), ("collected", collected)):
        if int(val) < 0:
            raise ValueError(f"{label}가 음수({val}) — 불가")
    if reported_total is not None and int(reported_total) < 0:
        raise ValueError(f"reported_total 음수({reported_total}) — 불가")
    if duplicates is not None and int(duplicates) < 0:
        raise ValueError(f"duplicates 음수({duplicates}) — 불가")
    run = {
        "source": source,
        "status": status,
        "exit_code": int(exit_code),
        "pages_fetched": int(pages_fetched),
        "collected": int(collected),
        "stop_reason": stop_reason,
        "cutoff": cutoff,
        "errors": [str(e) for e in (errors or [])],
    }
    if reported_total is not None:
        run["reported_total"] = int(reported_total)
    if duplicates is not None:
        run["duplicates"] = int(duplicates)
    return run


def update_manifest(output_path, new_runs, present_sources=None):
    """Write/merge run_manifest.json next to *output_path* atomically.

    *output_path* is the jsonl the crawler writes (its folder receives the
    manifest). *new_runs* is a list of make_run() entries. Returns the
    manifest path.

    *present_sources*: 방금 쓴 jsonl 에 실재하는 소스 집합. jsonl 은 전체
    덮어쓰기인데 매니페스트는 소스별 병합이라, 부분 재수집(`list bizinfo`
    단독)을 하면 데이터가 사라진 타 소스의 옛 status=ok run 이 잔존해
    커버리지 계약(cli-contract §5)이 붕괴한다. 이 인자가 주어지면 jsonl 에
    없는 소스의 잔존 run 을 제거한다(None 이면 대조하지 않는다 — jsonl 을
    쓰지 않은 런 등).
    """
    out_dir = os.path.dirname(os.path.abspath(output_path))
    path = os.path.join(out_dir, MANIFEST_NAME)

    runs = []
    recovered_from = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f, object_pairs_hook=_reject_dup_keys)
            if not isinstance(old, dict):
                raise ValueError("manifest top level is not a JSON object")
            # 알 수 없는 스키마 버전을 조용히 v1로 덮어쓰지 않는다(Codex #10) —
            # 미래/손상 버전은 corrupt 경로로 보존한 뒤 새로 시작한다.
            old_ver = old.get("manifest_schema_version")
            if old_ver != MANIFEST_SCHEMA_VERSION:
                raise ValueError(
                    f"unsupported manifest_schema_version {old_ver!r} "
                    f"(this writer emits v{MANIFEST_SCHEMA_VERSION})")
            old_runs = old.get("runs", [])
            if not isinstance(old_runs, list):
                raise ValueError('"runs" is not a list')
            runs = [r for r in old_runs if isinstance(r, dict)]
        except (json.JSONDecodeError, OSError, ValueError, AttributeError) as e:
            # Corrupt/schema-mismatched manifest: NEVER silently discard the
            # old coverage data — preserve the file under a .corrupt-<ts>
            # name, record the recovery in the new manifest, and warn.
            ts = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
            corrupt_path = os.path.join(out_dir, f"{MANIFEST_NAME}.corrupt-{ts}")
            n = 1
            while os.path.exists(corrupt_path):
                corrupt_path = os.path.join(
                    out_dir, f"{MANIFEST_NAME}.corrupt-{ts}.{n}")
                n += 1
            try:
                os.replace(path, corrupt_path)
                recovered_from = os.path.basename(corrupt_path)
                print(
                    f"[funding] WARNING: corrupt {MANIFEST_NAME} ({e}) — "
                    f"preserved as {recovered_from}; starting a fresh manifest",
                    file=sys.stderr,
                )
            except OSError as move_err:
                print(
                    f"[funding] WARNING: corrupt {MANIFEST_NAME} ({e}) and "
                    f"could not preserve it ({move_err}); it will be overwritten",
                    file=sys.stderr,
                )
            runs = []

    new_sources = {r["source"] for r in new_runs}
    runs = [r for r in runs if r.get("source") not in new_sources]
    runs.extend(new_runs)

    if present_sources is not None:
        keep = set(present_sources) | new_sources
        stale = sorted({r.get("source") for r in runs if r.get("source") not in keep})
        if stale:
            runs = [r for r in runs if r.get("source") in keep]
            print(
                f"[funding] WARNING: {', '.join(map(str, stale))} run 제거 — "
                f"{os.path.basename(output_path)} 에 해당 소스 데이터가 없다"
                "(부분 재수집으로 덮어써짐). 커버리지 판정에서 제외한다",
                file=sys.stderr,
            )

    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "runs": runs,
    }
    if recovered_from is not None:
        manifest["recovered_from_corrupt"] = recovered_from

    fd, tmp = tempfile.mkstemp(prefix=".run_manifest.", suffix=".tmp", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)  # atomic on POSIX — readers never see a partial file
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
