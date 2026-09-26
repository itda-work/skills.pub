#!/usr/bin/env python3
"""정부 지원사업 공고 전수 수집 CLI — funding 스킬의 단일 진입점.

5종 소스(K-Startup·기업마당·NIPA·KOCCA·SMTECH)의 **모집중 공고를 전수 수집**해
jsonl + run_manifest.json 으로 남긴다. 회차 비교는 survey_diff.py 가 맡는다.

    # 5종 전부 (전수 수집)
    python3 survey_crawl.py list all -o 20260728-1400/survey.jsonl

    # 한 소스만 / 저부하 스모크(1페이지 계약 확인)
    python3 survey_crawl.py list kstartup -o survey.jsonl
    python3 survey_crawl.py list bizinfo -o survey.jsonl --smoke --max-pages 1

    # 상세 본문 + 첨부 (jsonl 의 url·공고번호를 그대로 넘긴다)
    python3 survey_crawl.py detail kstartup 178481 -o details/ \
        --download-dir attachments/ --merge-into survey.jsonl

계약 정본은 ../references/cli-contract.md 다 — 인자·종료코드·jsonl/매니페스트
스키마가 이 docstring 과 어긋나면 그 문서가 맞다.

종료코드 (fail-closed):
  0  전수 성공
  2  partial — 커버리지 불완전(네트워크·페이지 캡·파싱 실패·소스 일부 실패·
     첨부 불완전·api-window). 수집된 데이터는 그대로 저장된다.
  3  차단 — 401/403 또는 200 위장 CAPTCHA/접근거부. **우회하지 않고** 수동
     확인으로 전환하라는 신호다.

호출자는 exit 2 를 성공으로 취급해서는 안 된다. 커버리지 판정은 stderr 요약이
아니라 산출 폴더의 run_manifest.json 을 읽어서 한다.

의존: curl_cffi>=0.15 권장(requirements.txt). 미설치 시 urllib 경로로 동작하되
stderr 에 1회 명시 고지한다.
"""
import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import attach_download  # noqa: E402
import kstartup_crawl  # noqa: E402 — K-Startup(API 우선 + 크롤 폴백)
import sources_crawl  # noqa: E402 — bizinfo·nipa·kocca·smtech
from run_manifest import update_manifest  # noqa: E402

KSTARTUP = "kstartup"
OTHER_SOURCES = list(sources_crawl.SOURCES)  # bizinfo, nipa, kocca, smtech
ALL_SOURCES = [KSTARTUP, *OTHER_SOURCES]


def cmd_list(args):
    """요청한 소스를 순차 수집해 하나의 jsonl + 하나의 run_manifest.json 으로 남긴다."""
    names = ALL_SOURCES if args.source == "all" else [args.source]
    records = []
    runs = []
    codes = []

    if KSTARTUP in names:
        recs, run, code = kstartup_crawl.collect_list(
            max_pages=args.max_pages,
            min_expected=args.min_expected,
            smoke=args.smoke,
        )
        records.extend(recs)
        runs.append(run)
        codes.append(code)

    others = [n for n in names if n != KSTARTUP]
    if others:
        recs, src_runs, code = sources_crawl.collect_sources(
            others, max_pages=args.max_pages, smoke=args.smoke
        )
        records.extend(recs)
        runs.extend(src_runs)
        codes.append(code)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    present_sources = None
    if records:
        with open(args.output, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[funding] saved: {args.output} ({len(records)} items)", file=sys.stderr)
        # jsonl 은 전체 덮어쓰기다 — 이번에 쓰지 않은 소스의 옛 run 이
        # 매니페스트에 남으면 커버리지가 거짓이 된다(계약 §5).
        present_sources = {rec.get("source") for rec in records}
    else:
        # 0건을 파일로 덮어쓰면 직전 회차의 정상 데이터가 사라지고, 이후 diff 가
        # 전 공고를 GONE 으로 오판한다. 쓰지 않고 사유만 표면화한다.
        print(
            f"[funding] {args.output} 미기록 — 수집 0건(파싱 실패·차단 의심). "
            "기존 파일을 덮어쓰지 않았다",
            file=sys.stderr,
        )

    manifest_path = update_manifest(args.output, runs,
                                    present_sources=present_sources)
    print(f"[funding] manifest: {manifest_path}", file=sys.stderr)

    # 3(차단) > 2(partial) > 0 — 가장 무거운 신호가 프로세스 종료코드가 된다.
    code = 3 if 3 in codes else (2 if 2 in codes else 0)
    for run in runs:
        print(
            f"[funding]   {run['source']}: {run['status']} "
            f"({run['collected']}건, stop={run['stop_reason']})",
            file=sys.stderr,
        )
    if code:
        print(
            f"[funding] 종료코드 {code} — "
            + ("차단 신호: 우회하지 말고 수동 확인으로 전환하라"
               if code == 3 else
               "커버리지 불완전(partial): 보고서에 한계를 고지하라"),
            file=sys.stderr,
        )
    return code


def cmd_detail(args):
    """상세 본문(+선택적 첨부)을 저장하고 목록 jsonl 에 병합한다."""
    if args.source == KSTARTUP:
        return kstartup_crawl.collect_detail(
            args.targets, args.output,
            download_dir=args.download_dir, merge_into=args.merge_into,
        )
    urls = [t for t in args.targets if t.startswith("http")]
    bad = [t for t in args.targets if not t.startswith("http")]
    if bad:
        # id 만으로는 상세 URL 을 복원할 수 없다(bizinfo·smtech 는 목록의 전체
        # 쿼리가 없으면 intro 로 302된다) — 추측 대신 명시적으로 거부한다.
        print(
            f"[funding] {args.source} detail 은 jsonl 의 url 을 그대로 넘겨야 한다"
            f"(공고 id 만으로는 상세 URL 복원 불가): {', '.join(bad[:3])}",
            file=sys.stderr,
        )
        return 2
    fetch = sources_crawl.make_detail_fetcher()
    return sources_crawl.cmd_detail(
        fetch, urls, args.output,
        download_dir=args.download_dir, merge_into=args.merge_into,
    )


def build_parser():
    ap = argparse.ArgumentParser(
        prog="survey_crawl.py",
        description="정부 지원사업 공고 전수 수집 (5종 소스) — funding 스킬",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="모집중 공고 목록을 전수 수집")
    p_list.add_argument("source", choices=[*ALL_SOURCES, "all"],
                        help="수집 소스 (all = 5종 전부)")
    p_list.add_argument("-o", "--output", default="survey.jsonl",
                        help="jsonl 산출 경로 (run_manifest.json 은 같은 폴더)")
    p_list.add_argument("--max-pages", type=int, default=40,
                        help="소스당 페이지 상한 (기본 40)")
    p_list.add_argument("--min-expected", type=int, default=kstartup_crawl.MIN_EXPECTED,
                        help="K-Startup 최소 기대 건수 — 미만이면 partial(0 이면 해제)")
    p_list.add_argument("--smoke", action="store_true",
                        help="저부하 스모크: coverage 검증(page-cap·min-expected)만 "
                             "완화. 1페이지 파싱 0건·네트워크 오류·차단은 그대로 실패")
    p_list.set_defaults(func=cmd_list)

    p_det = sub.add_parser("detail", help="상세 본문·첨부 수집 + jsonl 병합")
    p_det.add_argument("source", choices=ALL_SOURCES, help="대상 소스")
    p_det.add_argument("targets", nargs="+",
                       help="K-Startup 은 공고번호 또는 상세 URL, 그 외 소스는 "
                            "jsonl 의 url 을 그대로 (쿼리 파라미터 필수)")
    p_det.add_argument("-o", "--output", default="details", help="상세 텍스트 폴더")
    p_det.add_argument("--download-dir",
                       help="첨부 다운로드 폴더(공고별 하위 폴더). robots 불허·계약 "
                            "미확정 경로는 다운로드하지 않고 링크만 기록한다")
    p_det.add_argument("--merge-into",
                       help="목록 jsonl 에 content_hash/hash_version/attachments 병합")
    p_det.set_defaults(func=cmd_detail)
    return ap


def main():
    args = build_parser().parse_args()
    try:
        sys.exit(args.func(args) or 0)
    except attach_download.ManualEscalation as e:
        print(f"MANUAL [funding] {e} — 우회하지 않고 수동 확인으로 전환",
              file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
