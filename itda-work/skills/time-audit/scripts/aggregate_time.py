#!/usr/bin/env python3
"""time-audit 결정론 집계 — timelog.json 을 받아 업무 시간 리포트 수치를 계산한다.

리포트의 모든 수치(카테고리·난이도별 합계, 주별 추이, 미배정 비율)는 이 스크립트의
출력에서만 인용한다 — 에이전트가 시간을 암산·어림하지 않는다(환각 차단).

입력 계약(timelog.json) — 소스(캘린더 MCP 커넥터·itda-work:calendar·파일)와 무관하게
에이전트가 이 스키마로 정규화한다:

    {
      "period": {"from": "2026-06-29", "to": "2026-07-12"},
      "source": "calendar-mcp | itda-calendar | file",
      "categories": {
        "보고서 작성": {"difficulty": "상"},
        "회의":       {"difficulty": "중"}
      },
      "events": [
        {"summary": "월간 보고서 초안", "start": "2026-07-01T09:00:00+09:00",
         "end": "2026-07-01T12:00:00+09:00", "category": "보고서 작성"},
        {"summary": "워크숍", "start": "2026-07-02", "all_day": true, "category": "회의"},
        {"summary": "점심 약속", "start": "2026-07-01T12:00:00+09:00",
         "end": "2026-07-01T13:00:00+09:00", "exclude": true}
      ]
    }

규칙:
- exclude=true 이벤트는 업무가 아니다(건수·시간만 별도 보고).
- all_day=true 이벤트는 건수만 집계하고 시간 합산에서 뺀다(종일 일정의 시간은 알 수 없다).
- category 없는(비제외) 이벤트는 '미배정'으로 집계하고, 업무 시간 대비 20% 초과면 WARN.
- difficulty 는 카테고리 단위 상|중|하. 미지정 카테고리는 '미지정'으로 묶는다.
- 스키마 위반(필드 누락·end<=start·잘못된 difficulty)은 조용히 건너뛰지 않고
  전부 나열해 exit 2 로 실패한다.

#1246 D1·D2 기계 게이트 (#1257 — 프롬프트 규율의 코드화, O2 관측 근거):
- period.from/to 는 필수이며 **사용자가 요청한 기간 그대로**여야 한다. 기간 밖 이벤트가
  섞이면 전수 나열 후 exit 2 — 요청 기간과 다른 데이터로 리포트를 강행하는 경로 차단(D1).
- 제외(timed) 시간 비율이 30% 초과면 WARN — 애매한 이벤트를 exclude 로 빼서 미배정
  WARN 을 우회하는 경로 표면화(D2). exclude 는 확실한 비업무만, 애매하면 미배정.
- "provisional": true 면 사람용·JSON 출력 모두에 잠정(사용자 확인 전) 마커를 강제 각인 —
  배정·제외·난이도를 사용자가 확인하기 전의 결과를 확정처럼 인용하는 경로 차단(D2).

사용:
    python3 aggregate_time.py timelog.json          # 사람용 마크다운 리포트
    py -3 aggregate_time.py timelog.json            # Windows
    python3 aggregate_time.py timelog.json --json   # 기계 판독

exit code: 0 = 집계 성공(WARN 포함 가능), 2 = 스키마/사용법 오류
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

if sys.version_info[0] < 3:  # pragma: no cover - python2 방어
    sys.exit("python3 필요")

# Windows 콘솔(cp949)이 em-dash·이모지를 인코딩 못 해 깨지는 것을 막는다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):  # pragma: no cover - 구버전/파이프 방어
        pass

DIFFICULTIES = ("상", "중", "하")
UNASSIGNED = "미배정"
NO_DIFFICULTY = "미지정"
UNASSIGNED_WARN_RATIO = 0.20
EXCLUDE_WARN_RATIO = 0.30
PROVISIONAL_MARK = "⚠️ 잠정 — 배정·제외·난이도가 사용자 확인 전입니다. 확정 인용 금지"


def _parse_dt(value: str, field: str, idx: int, errors: list) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"events[{idx}].{field}: ISO8601 아님 — {value!r}")
        return None


def validate(data) -> tuple[dict, list[str]]:
    """스키마 검증 — 위반은 전부 모아 반환한다(첫 오류에서 멈추지 않는다)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return {}, ["최상위가 객체가 아님"]

    # 기간 필수 (D1 게이트) — 사용자가 요청한 기간 그대로. 무단 대체 금지.
    period = data.get("period") or {}
    p_from = p_to = None
    if not isinstance(period, dict) or not period.get("from") or not period.get("to"):
        errors.append("period.from/to: 누락 — 사용자가 요청한 기간을 그대로 적는다(무단 대체 금지)")
    else:
        try:
            p_from = date.fromisoformat(str(period["from"])[:10])
            p_to = date.fromisoformat(str(period["to"])[:10])
        except ValueError:
            errors.append(f"period: 날짜 아님 — from={period.get('from')!r}, to={period.get('to')!r}")
            p_from = p_to = None
        if p_from and p_to and p_to < p_from:
            errors.append(f"period: to({p_to}) < from({p_from})")
            p_from = p_to = None

    categories = data.get("categories", {})
    if not isinstance(categories, dict):
        errors.append("categories: 객체가 아님")
        categories = {}
    for name, meta in categories.items():
        diff = (meta or {}).get("difficulty")
        if diff is not None and diff not in DIFFICULTIES:
            errors.append(f"categories[{name!r}].difficulty: {diff!r} (허용: 상|중|하)")

    events = data.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events: 비어 있거나 배열이 아님")
        events = []

    norm_events = []
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            errors.append(f"events[{i}]: 객체가 아님")
            continue
        summary = ev.get("summary")
        if not summary:
            errors.append(f"events[{i}].summary: 누락")
        all_day = bool(ev.get("all_day", False))
        exclude = bool(ev.get("exclude", False))
        category = ev.get("category")
        if category is not None and category not in categories:
            errors.append(f"events[{i}].category: {category!r} 가 categories 에 없음")
        start_raw = ev.get("start")
        if not start_raw:
            errors.append(f"events[{i}].start: 누락")
            continue
        if all_day:
            # 종일 일정은 날짜만 필요
            try:
                start_day = date.fromisoformat(str(start_raw)[:10])
            except ValueError:
                errors.append(f"events[{i}].start: 날짜 아님 — {start_raw!r}")
                continue
            norm_events.append({
                "summary": summary, "all_day": True, "exclude": exclude,
                "category": category, "day": start_day, "hours": 0.0,
            })
            continue
        end_raw = ev.get("end")
        if not end_raw:
            errors.append(f"events[{i}].end: 누락 (종일 일정이면 all_day=true 로)")
            continue
        start = _parse_dt(start_raw, "start", i, errors)
        end = _parse_dt(end_raw, "end", i, errors)
        if start is None or end is None:
            continue
        if end <= start:
            errors.append(f"events[{i}]: end<=start — {summary!r}")
            continue
        norm_events.append({
            "summary": summary, "all_day": False, "exclude": exclude,
            "category": category, "day": start.date(),
            "start": start, "end": end,
            "hours": round((end - start).total_seconds() / 3600, 2),
        })

    # 기간 밖 이벤트 = 요청 기간과 다른 데이터의 혼입 (D1 게이트, #1246 실측: 2015 요청 →
    # 2025 데이터로 무단 대체). 조용히 잘라내지 않고 전수 나열해 실패시킨다.
    if p_from and p_to:
        out_of_range = [
            f"{e['summary']!r} ({e['day'].isoformat()})"
            for e in norm_events if not (p_from <= e["day"] <= p_to)
        ]
        if out_of_range:
            errors.append(
                f"기간 밖 이벤트 {len(out_of_range)}건 — 요청 기간({p_from}~{p_to})과 다른 데이터 혼입 금지, "
                "기간이 틀렸으면 사용자에게 확인: " + ", ".join(out_of_range[:10]))

    return {"categories": categories, "events": norm_events,
            "period": data.get("period", {}), "source": data.get("source", ""),
            "provisional": bool(data.get("provisional", False))}, errors


def _week_monday(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def aggregate(data: dict) -> dict:
    categories = data["categories"]
    events = data["events"]

    excluded = [e for e in events if e["exclude"]]
    work = [e for e in events if not e["exclude"]]
    timed = [e for e in work if not e["all_day"]]
    all_days = [e for e in work if e["all_day"]]

    per_cat: dict[str, dict] = {}
    for e in work:
        cat = e["category"] or UNASSIGNED
        row = per_cat.setdefault(cat, {"hours": 0.0, "count": 0, "all_day_count": 0})
        row["count"] += 1
        if e["all_day"]:
            row["all_day_count"] += 1
        else:
            row["hours"] = round(row["hours"] + e["hours"], 2)
    for cat, row in per_cat.items():
        timed_n = row["count"] - row["all_day_count"]
        row["avg_hours"] = round(row["hours"] / timed_n, 2) if timed_n else 0.0
        row["difficulty"] = (
            (categories.get(cat) or {}).get("difficulty") or NO_DIFFICULTY
            if cat != UNASSIGNED else UNASSIGNED
        )

    per_diff: dict[str, float] = {}
    for cat, row in per_cat.items():
        if cat == UNASSIGNED:
            continue
        per_diff[row["difficulty"]] = round(per_diff.get(row["difficulty"], 0.0) + row["hours"], 2)

    weekly: dict[str, float] = {}
    for e in timed:
        wk = _week_monday(e["day"])
        weekly[wk] = round(weekly.get(wk, 0.0) + e["hours"], 2)

    total_timed = round(sum(e["hours"] for e in timed), 2)
    unassigned_hours = per_cat.get(UNASSIGNED, {}).get("hours", 0.0)
    unassigned_ratio = round(unassigned_hours / total_timed, 3) if total_timed else 0.0

    warnings = []
    if unassigned_ratio > UNASSIGNED_WARN_RATIO:
        warnings.append(
            f"미배정 {unassigned_hours}h / 업무 {total_timed}h = {unassigned_ratio:.0%} (>20%) — 매핑 인터뷰로 되돌아가 배정을 채울 것")

    # 제외 비율 (D2 게이트) — 애매한 이벤트를 exclude 로 빼면 미배정 WARN 이 못 본다.
    excluded_hours = round(sum(e["hours"] for e in excluded if not e["all_day"]), 2)
    excl_denom = excluded_hours + total_timed
    if excl_denom and excluded_hours / excl_denom > EXCLUDE_WARN_RATIO:
        warnings.append(
            f"제외 {excluded_hours}h / 전체 {excl_denom}h = {excluded_hours / excl_denom:.0%} (>30%) — "
            "exclude 는 확실한 비업무만, 애매하면 미배정으로 두고 사용자에게 확인")

    # 겹침(동시간대 이중 기록) 탐지 — 기록 신뢰도 신호
    overlaps = []
    seq = sorted(timed, key=lambda e: e["start"])
    for a, b in zip(seq, seq[1:]):
        if b["start"] < a["end"]:
            overlaps.append(f"{a['summary']!r} ↔ {b['summary']!r} ({a['day'].isoformat()})")
    if overlaps:
        warnings.append("겹치는 이벤트 " + str(len(overlaps)) + "쌍: " + "; ".join(overlaps[:5]))

    top_hours = sorted(
        ((c, r) for c, r in per_cat.items() if c != UNASSIGNED),
        key=lambda x: x[1]["hours"], reverse=True)
    top_avg = sorted(
        ((c, r) for c, r in per_cat.items() if c != UNASSIGNED and r["avg_hours"] > 0),
        key=lambda x: x[1]["avg_hours"], reverse=True)

    return {
        "period": data["period"], "source": data["source"],
        "provisional": data.get("provisional", False),
        "totals": {
            "work_hours": total_timed,
            "work_events": len(work),
            "all_day_events": len(all_days),
            "excluded_events": len(excluded),
            "excluded_hours": excluded_hours,
            "unassigned_hours": unassigned_hours,
            "unassigned_ratio": unassigned_ratio,
        },
        "by_category": {c: per_cat[c] for c in sorted(per_cat, key=lambda c: -per_cat[c]["hours"])},
        "by_difficulty": per_diff,
        "weekly": dict(sorted(weekly.items())),
        "top_by_hours": [c for c, _ in top_hours[:3]],
        "top_by_avg": [c for c, _ in top_avg[:3]],
        "warnings": warnings,
    }


def render_human(r: dict) -> str:
    t = r["totals"]
    period = r.get("period") or {}
    lines = [
        f"# time-audit 집계 — {period.get('from', '?')} ~ {period.get('to', '?')} (source: {r.get('source') or '?'})",
        "",
    ]
    if r.get("provisional"):
        lines += [f"> {PROVISIONAL_MARK}", ""]
    lines += [
        f"- 업무 시간 합계: **{t['work_hours']}h** (이벤트 {t['work_events']}건, 종일 {t['all_day_events']}건은 건수만)",
        f"- 제외(업무 아님): {t['excluded_events']}건 / {t['excluded_hours']}h",
        f"- 미배정: {t['unassigned_hours']}h ({t['unassigned_ratio']:.0%})",
        "",
        "## 카테고리별",
        "| 카테고리 | 난이도 | 시간(h) | 건수 | 평균(h) |",
        "|---|---|---|---|---|",
    ]
    for cat, row in r["by_category"].items():
        lines.append(f"| {cat} | {row['difficulty']} | {row['hours']} | {row['count']} | {row['avg_hours']} |")
    lines += ["", "## 난이도별", "| 난이도 | 시간(h) |", "|---|---|"]
    for diff in ("상", "중", "하", NO_DIFFICULTY):
        if diff in r["by_difficulty"]:
            lines.append(f"| {diff} | {r['by_difficulty'][diff]} |")
    lines += ["", "## 주별 추이", "| 주(월요일) | 시간(h) |", "|---|---|"]
    for wk, h in r["weekly"].items():
        lines.append(f"| {wk} | {h} |")
    lines += ["", f"- 시간 최다: {', '.join(r['top_by_hours']) or '-'}",
              f"- 건당 최장(병목 후보): {', '.join(r['top_by_avg']) or '-'}"]
    if r["warnings"]:
        lines += ["", "## ⚠️ WARN"]
        lines += [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
    if not args:
        sys.stderr.write(__doc__)
        return 2
    try:
        data = json.load(open(args[0], encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"timelog.json 읽기 실패: {e}\n")
        return 2

    normalized, errors = validate(data)
    if errors:
        sys.stderr.write("스키마 오류 — 집계 중단(부분 결과 없음):\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        return 2

    result = aggregate(normalized)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
