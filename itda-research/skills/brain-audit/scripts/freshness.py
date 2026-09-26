#!/usr/bin/env python3
"""신선도 점검 — 소스 폴더 재스캔 후 빌드 시점 기준선(manifest)과 대조 (SPEC-BRAIN-VERTICAL-001 REQ-003).

brain-audit 제5각(신선도)의 결정론 엔진. 오케스트레이션(에이전트)이 아니라 순수 계산이므로
Python 이 담당한다(stdlib only — os.stat mtime). 문서 판독은 하지 않는다.

기준선(baseline)은 **빌드 시점에 고정된 정수 mtime manifest** 가 authoritative 다:
  - brain-build 가 빌드 끝에 `scan` 산출을 `<업무DB>/.brain-manifest.json` 으로 저장(정수 epoch mtime — 타임존 무관·정밀).
  - brain-audit 는 그 manifest 를 baseline 으로 `diff` 한다. **현재 스캔값으로 기준선을 덮지 않는다**(자기비교로 항상 최신이 되는 거짓 안심 차단). 기준선 갱신은 brain-ingest 가 적재 성공 시에만 한다.
  - manifest 가 없으면(구 빌드) 신선도는 `unknown` 으로 실패 처리하고 재빌드를 권고한다 — 커버리지 표를 현재값으로 backfill 해 diff 하지 않는다.

모드:
  scan  <source>                     → {상대경로: {mtime, mtime_iso, size}} JSON. manifest 저장·표 실측값 공급.
  diff  <source> --baseline <json>   → manifest(정수 mtime) 대비 신규/변경/삭제/불변. (정본 경로)
  diff  <source> --report <md>       → 검수리포트.md 커버리지 표(수정시각 열)를 baseline 으로 파싱(fallback).
  update-baseline <source> --manifest <json> --paths ...
                                     → manifest 에 **지정 경로만** 병합(brain-ingest 부분 적재 — 미적재 변경 흡수 방지).

결정론: 동일 입력 → 동일 출력(정렬·고정 포맷). 비교 키는 정수 epoch mtime(타임존 무관). 난수·현재시각 의존 없음.
표시 문자열(mtime_iso)만 로컬 오프셋 포함 ISO 로 렌더(사람 가독) — 비교에는 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

if sys.version_info < (3, 10):
    sys.exit("Error: Python 3.10+ required.")

# 스캔에서 제외하는 순수 잡음(OS 메타데이터). 원본 문서·임시 잠금(~$)·손상 파일은 제외하지 않는다.
_IGNORE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
_IGNORE_DIR_PARTS = frozenset({"__pycache__", ".git"})

# manifest 는 정수 mtime 이 정본이라 정확 비교(0). --report fallback(초 단위 ISO)도 초 정밀이라 0 로 충분.
# 분 단위로 반올림된 수기 표를 baseline 으로 쓸 때만 호출자가 --tolerance 를 올린다.
DEFAULT_TOLERANCE_SEC = 0

# 타임스탬프 토큰(오프셋/‘Z’ 허용). 파일명 속 날짜 오인을 막기 위해 _is_pure_ts 는 fullmatch 로 검사.
_TS_RE = r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?)?"
# 셀 끝 상태 접미사(예: "(읽기 불가)")만 제거하기 위한 패턴.
_ANNOT_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _iso(epoch: float) -> str:
    """epoch(초) → 로컬 오프셋 포함 ISO(예: 2026-06-05T14:30:00+09:00). 표시 전용, 초 단위."""
    return datetime.fromtimestamp(int(epoch)).astimezone().isoformat(timespec="seconds")


def _parse_ts(text: str) -> float | None:
    """느슨한 ISO 타임스탬프 → epoch(초). 오프셋/‘Z’ 처리. naive 는 UTC 로 간주(문서화). 실패 시 None."""
    s = text.strip().strip("`").strip()
    if not s:
        return None
    m = re.search(_TS_RE, s)
    if not m:
        return None
    token = m.group(0).replace(" ", "T")
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(token)  # 오프셋 포함/초 포함 처리(3.10)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):  # 초 없는/날짜만 fallback
            try:
                dt = datetime.strptime(token, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # 오프셋 없는 값 = UTC 로 명시 해석
    return dt.timestamp()


def _norm_rel(path: str) -> str:
    """경로를 정규화(슬래시 통일, 앞쪽 ./ 제거). 비교 키."""
    p = path.strip().strip("`").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def _is_pure_ts(cell: str) -> bool:
    """셀 전체가 타임스탬프(파일명 속 날짜가 아님)인지."""
    s = cell.strip().strip("`").strip()
    return bool(re.fullmatch(_TS_RE, s))


def _extract_path(cell: str) -> str | None:
    """표 셀에서 원본 경로만 추출. 끝의 상태 접미사("(읽기 불가)" 등)만 떼고 나머지 전체를 경로로 본다.

    공백 포함 경로(발주/사본 - 사본 - 발주서.xlsx)도 온전히 보존한다 — 토큰 분해로 자르지 않는다.
    """
    cc = cell.strip().strip("`").strip()
    if not cc:
        return None
    cc = _ANNOT_SUFFIX_RE.sub("", cc).strip()  # 끝의 (…) 주석 제거
    if _is_pure_ts(cc):  # 순수 타임스탬프 셀은 경로가 아님
        return None
    # 경로 판정: 슬래시를 포함하거나 파일 확장자로 끝난다.
    if "/" in cc or re.search(r"\.\w{1,5}$", cc):
        return _norm_rel(cc)
    return None


def scan(source: str) -> dict[str, dict]:
    """소스 폴더를 재귀 스캔 → {상대경로: {mtime, mtime_iso, size}}. 정렬 키(결정론)."""
    root = os.path.abspath(source)
    if not os.path.isdir(root):
        raise NotADirectoryError(f"소스 폴더가 아님: {source}")
    out: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIR_PARTS]
        for name in filenames:
            if name in _IGNORE_NAMES:
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = _norm_rel(os.path.relpath(full, root))
            out[rel] = {
                "mtime": int(st.st_mtime),  # 정수 epoch — 비교의 정본(타임존 무관)
                "mtime_iso": _iso(st.st_mtime),  # 표시 전용
                "size": st.st_size,
            }
    return dict(sorted(out.items()))


# 정식 마크다운 구분선 셀: 선택 콜론 + 대시 3개 이상 + 선택 콜론(---, :---, ---:, :---:).
# 단일 '-' 데이터 셀(| - | - |)을 구분선으로 오인하지 않도록 대시 3개 이상만 인정.
_SEP_CELL_RE = re.compile(r"^:?-{3,}:?$")


def _is_separator_row(cells: list[str]) -> bool:
    """마크다운 표 구분선(| --- | :--: |) 행인지(대시 3개 이상만)."""
    return bool(cells) and all(_SEP_CELL_RE.match(c.strip()) for c in cells)


def parse_report_baseline(report_text: str) -> dict[str, float]:
    """검수리포트.md 의 **커버리지 표**(수정시각 열이 있는 표)에서만 (경로 → baseline mtime epoch) 파싱.

    커버리지 표 판정은 **구분선(|---|) 바로 앞 헤더 행**에 '수정시각'/'mtime' 이 있는지로만 한다.
    데이터 행에 우연히 'mtime' 이 있어도(예: `자료/mtime 분석.docx`) 헤더로 오인하지 않는다. (fallback — 정본은 manifest.)
    """
    lines = report_text.splitlines()
    baseline: dict[str, float] = {}
    in_coverage = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "|" not in stripped:
            in_coverage = False  # 표 종료
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if _is_separator_row(cells):
            # 헤더 = 바로 앞 표 행. 그 헤더에 수정시각/mtime 이 있으면 이 표가 커버리지 표.
            hdr = []
            if i > 0 and "|" in lines[i - 1]:
                hdr = [c.strip() for c in lines[i - 1].strip().strip("|").split("|")]
            in_coverage = any(("수정시각" in c) or ("mtime" in c.lower()) for c in hdr)
            continue
        if not in_coverage:
            continue  # 헤더 행 자체 + 비커버리지 표 데이터 행은 건너뜀
        ts_epoch: float | None = None
        path_cell: str | None = None
        for c in cells:
            if ts_epoch is None and _is_pure_ts(c):
                ts_epoch = _parse_ts(c)
                continue
            if path_cell is None:
                p = _extract_path(c)
                if p:
                    path_cell = p
        if path_cell and ts_epoch is not None:
            baseline[path_cell] = ts_epoch
    return baseline


def _read_manifest_json(path: str):
    """manifest JSON 파일을 읽는다. 손상(비JSON·빈 파일)은 **명시 에러**로 표면화한다.

    부재(unknown 처리)와 달리 손상은 "기준선이 있었는데 못 믿게 된" 상태다 — 빈 값으로
    대체하면 미적재 변경이 전부 신규로 위장되거나 기준선이 조용히 소실된다(조용한 폴백 금지).
    """
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"manifest 손상(JSON 파싱 실패): {path} — {e}. "
                "brain-build 재빌드(또는 백업 복원)로 기준선을 재생성하세요. "
                "손상 기준선을 빈 값으로 대체하지 않습니다."
            ) from e


def update_baseline(
    manifest_path: str, source: str, paths: list[str]
) -> dict[str, dict]:
    """기존 manifest 에 **지정 경로만** 현재 mtime 으로 병합(부분 적재 반영, brain-ingest 전용).

    나머지 경로는 손대지 않으므로, 함께 존재하던 **미적재 변경은 기준선에 흡수되지 않고 계속 stale** 로 남는다.
    적재한 경로가 삭제됐으면 manifest 에서도 제거한다. 반환 = 갱신된 manifest(정렬).

    manifest 부재는 **명시 에러**다 — 경로 오타 시 빈 기준선을 조용히 새로 만들면 정본
    manifest 가 1~2 엔트리 기준선으로 대체돼 신선도가 통째로 무너진다(조용한 폴백 금지).
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"manifest 없음: {manifest_path} — update-baseline 은 기존 기준선에만 병합합니다. "
            "경로 오타면 정정하고, 기준선이 정말 없으면 brain-build 재빌드로 생성하세요"
            "(빈 기준선을 자동 생성하지 않습니다)."
        )
    current = scan(source)
    base = _read_manifest_json(manifest_path)
    for p in paths:
        rel = _norm_rel(p)
        if rel in current:
            base[rel] = current[rel]
        else:
            base.pop(rel, None)  # 적재한 삭제 반영
    return dict(sorted(base.items()))


def diff(
    baseline: dict[str, float],
    current: dict[str, dict],
    tolerance_sec: int = DEFAULT_TOLERANCE_SEC,
) -> dict:
    """baseline(경로→mtime epoch) vs 현재 스캔 → 신규/변경/삭제/불변. 비교는 정수 epoch."""
    cur_keys = set(current)
    base_keys = set(baseline)
    new = sorted(cur_keys - base_keys)
    deleted = sorted(base_keys - cur_keys)
    changed: list[dict] = []
    unchanged: list[str] = []
    for rel in sorted(cur_keys & base_keys):
        cur_mtime = current[rel]["mtime"]
        base_mtime = baseline[rel]
        if abs(cur_mtime - base_mtime) > tolerance_sec:
            changed.append(
                {
                    "path": rel,
                    "baseline_mtime": _iso(base_mtime),
                    "current_mtime": current[rel]["mtime_iso"],
                }
            )
        else:
            unchanged.append(rel)
    stale = bool(new or deleted or changed)
    return {
        "stale": stale,
        "new": [{"path": p, "mtime": current[p]["mtime_iso"]} for p in new],
        "changed": changed,
        "deleted": deleted,
        "unchanged": unchanged,
        "counts": {
            "new": len(new),
            "changed": len(changed),
            "deleted": len(deleted),
            "unchanged": len(unchanged),
        },
    }


def load_manifest(path: str) -> dict[str, float]:
    """manifest JSON({rel:{mtime,...}} 또는 {rel: epoch|iso}) → {rel: mtime epoch}. 손상은 ValueError."""
    data = _read_manifest_json(path)
    out: dict[str, float] = {}
    for rel, v in data.items():
        if isinstance(v, dict):
            mt = v.get("mtime")
            if mt is None and v.get("mtime_iso"):
                mt = _parse_ts(v["mtime_iso"])
            if mt is not None:
                out[_norm_rel(rel)] = float(mt)
        elif isinstance(v, (int, float)):
            out[_norm_rel(rel)] = float(v)
        else:
            t = _parse_ts(str(v))
            if t is not None:
                out[_norm_rel(rel)] = t
    return out


def _absent_result(source: str, reason: str) -> dict:
    """기준선 부재 → stale 을 unknown(null) 으로 실패 처리(자기비교로 최신 위장 금지)."""
    return {
        "stale": None,
        "baseline": "absent",
        "reason": reason,
        "advice": "빌드 시점 기준선(.brain-manifest.json)이 없어 신선도를 판정할 수 없습니다. brain-build 재빌드로 기준선을 생성하세요.",
        "current_files": len(scan(source)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="업무DB 신선도 점검 (REQ-003)")
    sub = ap.add_subparsers(dest="mode", required=True)

    sp_scan = sub.add_parser("scan", help="소스 폴더 → {경로:{mtime,...}} JSON (manifest·표 실측값)")
    sp_scan.add_argument("source")

    sp_diff = sub.add_parser("diff", help="baseline(manifest 정본 / report fallback) 대비 신규·변경·삭제")
    sp_diff.add_argument("source")
    sp_diff.add_argument("--baseline", help="빌드 시점 manifest JSON (.brain-manifest.json) — 정본")
    sp_diff.add_argument("--report", help="검수리포트.md 커버리지 표 (fallback baseline)")
    sp_diff.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE_SEC,
        help="mtime 허용오차(초, 기본 0). 분 단위 수기 표를 baseline 으로 쓸 때만 상향",
    )

    sp_upd = sub.add_parser(
        "update-baseline",
        help="manifest 에 지정 경로만 병합(brain-ingest 부분 적재 — 미적재 변경 흡수 방지)",
    )
    sp_upd.add_argument("source")
    sp_upd.add_argument("--manifest", required=True, help="갱신할 manifest JSON 경로")
    sp_upd.add_argument(
        "--paths", nargs="+", required=True, help="적재 완료한 경로만(소스 폴더 기준 상대경로)"
    )

    args = ap.parse_args(argv)

    try:
        return _run(args)
    except (NotADirectoryError, FileNotFoundError, ValueError) as e:
        # 예상외 실패는 traceback 이 아니라 명시 에러로 표면화한다(조용한 폴백·원시 스택 금지).
        print(f"Error: {e}", file=sys.stderr)
        return 2


def _run(args) -> int:
    if args.mode == "scan":
        print(json.dumps(scan(args.source), ensure_ascii=False, indent=2))
        return 0

    if args.mode == "diff":
        if args.baseline:
            if not os.path.exists(args.baseline):
                print(
                    json.dumps(
                        _absent_result(args.source, f"manifest 없음: {args.baseline}"),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            baseline = load_manifest(args.baseline)
        elif args.report:
            with open(args.report, encoding="utf-8") as f:
                baseline = parse_report_baseline(f.read())
            if not baseline:
                print(
                    json.dumps(
                        _absent_result(
                            args.source, f"커버리지 표에서 baseline 을 찾지 못함: {args.report}"
                        ),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
        else:
            sys.exit("diff 모드는 --baseline(정본) 또는 --report(fallback) 가 필요합니다.")
        result = diff(baseline, scan(args.source), tolerance_sec=args.tolerance)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.mode == "update-baseline":
        updated = update_baseline(args.manifest, args.source, args.paths)
        print(json.dumps(updated, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
