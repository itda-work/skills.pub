#!/usr/bin/env python3
"""data-compass CLI — 프로파일 + 경로 추천 → 분석 지도 파일 생성.

  python3 scripts/compass.py <데이터.csv> [--interest "관심사"] [--out 지도.md]

산출:
  1) 분석 지도 마크다운(기본: 데이터 파일 옆 `<이름>-분석지도.md`)
  2) stdout 에 요약 JSON(에이전트가 포인터+요약만 대화로 릴레이)

초기 지도는 완전 결정론(같은 데이터·관심사 → 같은 지도, 타임스탬프 없음).
이후 §3(현재 위치)·§4(여정 로그) 갱신은 코치(Claude)가 Edit 로 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile as prof  # noqa: E402
import routes as rt     # noqa: E402

ROLE_KO = {"measure": "측정값", "dimension": "차원", "date": "날짜", "id": "식별자", "pii": "개인정보"}
NARRATIVE_MARK = "<!-- 코치 한줄서술: 이 자리에 '이 데이터는 무엇인가'를 한 문장으로 채우세요 -->"


def render_map(p: dict, routes: list[dict], interest: str = "") -> str:
    lines: list[str] = []
    add = lines.append
    add(f"# 분석 지도 — {p['file']}")
    add("")
    add("> data-compass 가 만든 분석 여정 지도입니다. 한 걸음 나아갈 때마다")
    add("> §3(현재 위치)과 §4(지나온 길)가 갱신됩니다. 지시는 언제나 당신이 합니다.")
    add("")
    add("## 1. 지형 — 이 데이터는 무엇인가")
    add("")
    add(NARRATIVE_MARK)
    add("")
    trunc = " (프로파일은 앞부분만 읽음)" if p["truncated"] else ""
    add(f"- 규모: {p['n_rows']:,}행 × {p['n_cols']}열 · 인코딩 {p['encoding']}{trunc}")
    if interest:
        add(f"- 관심사: {interest}")
    add("")
    add("| 컬럼 | 역할 | 예시 | 고유값 | 결측% |")
    add("|---|---|---|---|---|")
    for c in p["columns"]:
        ex = ", ".join(c["samples"][:2]) if c["samples"] else "—"
        add(f"| {c['name']} | {ROLE_KO.get(c['role'], c['role'])} | {ex} | {c['distinct']} | {c['missing_pct']} |")
    add("")
    q = p["quality"]
    signals = list(q["header_issues"])
    if q["ragged_rows"]:
        signals.append(f"열 개수가 안 맞는 행 {q['ragged_rows']}건")
    if q["high_missing"]:
        signals.append("결측 많은 열: " + ", ".join(q["high_missing"]))
    if q["mixed_numeric"]:
        signals.append("숫자에 텍스트 섞인 열: " + ", ".join(q["mixed_numeric"]))
    add("- 품질 신호: " + (" · ".join(signals) if signals else "특이 없음"))
    add("")
    add("## 2. 갈 수 있는 길 — 이 데이터로 가능한 분석")
    add("")
    for i, r in enumerate(routes, 1):
        add(f"{i}. **[{r['stage']}]** {r['title']} — {r['why']} (담당: `{r['skill']}`)")
    add("")
    add("## 3. 현재 위치와 다음 행선지")
    add("")
    add("- 현재 위치: **출발점** (지형 파악 완료, 아직 첫 분석 전)")
    for i, r in enumerate(rt.recommend(routes), 1):
        tag = " ← 추천" if i == 1 else ""
        add(f"- 행선지 {i}{tag}: [{r['stage']}] {r['title']}")
        add(f"  > 이렇게 말해보세요: “{r['say']}”")
    add("")
    add("## 4. 지나온 길 — 여정 로그")
    add("")
    add("- (출발) 지도 생성 — 아직 첫 걸음 전입니다.")
    add("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="데이터 분석 지도 생성")
    ap.add_argument("data_path")
    ap.add_argument("--interest", default="", help="사용자 관심사(모르면 생략)")
    ap.add_argument("--out", default="", help="지도 파일 경로(기본: 데이터 옆 <이름>-분석지도.md)")
    args = ap.parse_args()

    src = Path(args.data_path)
    if not src.is_file():
        print(json.dumps({"error": f"파일이 없습니다: {src}"}, ensure_ascii=False))
        return 2
    if src.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        print(json.dumps({
            "error": "엑셀 파일은 직접 프로파일하지 않습니다",
            "guidance": "시트를 CSV 로 내보내거나, 수식·구조가 궁금하면 data-audit 에 감사를 요청하세요",
        }, ensure_ascii=False))
        return 2

    p = prof.profile_table(str(src))
    routes = rt.build_routes(p, args.interest)
    out = Path(args.out) if args.out else src.with_name(f"{src.stem}-분석지도.md")
    out.write_text(render_map(p, routes, args.interest), encoding="utf-8")

    print(json.dumps({
        "map_path": str(out),
        "file": p["file"],
        "n_rows": p["n_rows"],
        "n_cols": p["n_cols"],
        "encoding": p["encoding"],
        "needs_prep": p["needs_prep"],
        "quality": p["quality"],
        "recommendations": [{"stage": r["stage"], "skill": r["skill"], "say": r["say"]} for r in rt.recommend(routes)],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
