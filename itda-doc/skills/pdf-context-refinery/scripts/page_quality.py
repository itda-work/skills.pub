#!/usr/bin/env python3
"""PDF 페이지별 텍스트층 품질 판정 — 어느 쪽을 비전(이미지)으로 읽어야 하는지 가른다.

첫 몇 쪽만 샘플링하면 "앞은 텍스트, 뒤의 신청자격 표는 스캔" 인 공고를 통째로 텍스트 경로로
처리해 뒤쪽을 조용히 빠뜨린다(#5). 이 스크립트는 **전 페이지**를 pdftotext 한 번으로 읽어
쪽마다 글자 수와 깨진 글자 비율을 재고, 텍스트로 믿을 수 없는 쪽 목록(`needs_vision`)을 낸다.

판정(쪽마다):
  empty     글자 0 — 스캔·이미지 전용
  low_text  글자가 --min-chars 미만 — 표지·그림 쪽이거나 스캔 위 일부 텍스트
  garbled   대체문자(U+FFFD)·사용자 정의 영역(PUA)·제어문자 비율이 --max-bad-ratio 초과 — 글꼴 매핑 손상
  garbled_hangul
            한글 음절은 정상 영역인데 엉뚱한 글자 — ToUnicode 오매핑(#28). 받침 분포로 가른다:
            한글 음절 30자 이상에서 받침 없는 음절 비율 < 0.15 **그리고** 희귀 받침 비율 >= 0.15
  ok        그 외

문서 단위: 판정 쪽 중 needs_vision 비율이 0.3 이상이면 doc_needs_ocr=true — 쪽을 골라 읽기보다
문서 전체를 비전으로 읽는 편이 낫다는 권고다.

받침 임계 실측 근거(2026-09-28, #28):
  정상 — 기업마당 공고 첨부 PDF 51건 319쪽 + 저장소 PDF 4건 300쪽: 받침 없음 최소 0.286, 희귀 받침 최대 0.042.
         같은 문서들의 연속 30음절 창 20,792개: 받침 없음 최소 0.133(단독 판정이면 오탐), 희귀 받침 최대 0.100.
  깨짐 — 공고 12건을 AppleGothic 으로 다시 짜고 ToUnicode 를 고친 42쪽:
         무작위 음절(CID 뒤섞임) 받침 없음 <= 0.099·희귀 >= 0.387, 코드포인트 +1 어긋남 받침 없음 0·희귀 >= 0.224.
  kordoc 의 희귀 >= 0.25 는 +1 어긋남 2쪽을 놓쳐 0.15 로 낮췄다(정상 최대 0.100 과 여유가 있다).
  못 잡는 것: 문서 안에 실제로 쓰인 음절끼리 뒤바뀐 매핑 — 받침 분포가 그대로라 통계로는 안 갈린다.

사용:
  python3 page_quality.py 문서.pdf            # JSON(stdout)
  python3 page_quality.py 문서.pdf --pages 3-9

종료 코드: 0 판정 완료(나쁜 쪽이 있어도 0 — 판정은 JSON 으로 한다) / 2 입력·pdftotext 실패.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

if sys.version_info < (3, 8):
    sys.exit("Python 3.8+ 가 필요합니다")

DEFAULT_MIN_CHARS = 40
DEFAULT_MAX_BAD_RATIO = 0.05
HANGUL_MIN_SYLLABLES = 30
HANGUL_MAX_NO_BATCHIM = 0.15
HANGUL_MIN_RARE_BATCHIM = 0.15
DOC_NEEDS_OCR_PAGE_RATIO = 0.3
# 종성 인덱스 (code - 0xAC00) % 28 중 겹받침(ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ)과 드문 홑받침(ㅋㅌㅍ)
RARE_BATCHIM = frozenset({3, 5, 6, 9, 10, 11, 12, 13, 14, 15, 18, 24, 25, 26})


def _is_bad(ch: str) -> bool:
    code = ord(ch)
    if ch == "�":
        return True
    if 0xE000 <= code <= 0xF8FF or 0xF0000 <= code <= 0x10FFFD:
        return True
    return code < 0x20 and ch not in "\n\t\r\f"


def hangul_batchim_stats(visible: list[str]) -> tuple[int, float, float]:
    """한글 음절 수, 받침 없는 음절 비율, 희귀 받침 음절 비율."""
    jongs = [(ord(ch) - 0xAC00) % 28 for ch in visible if 0xAC00 <= ord(ch) <= 0xD7A3]
    n = len(jongs)
    if not n:
        return 0, 0.0, 0.0
    no_batchim = sum(1 for j in jongs if j == 0)
    rare = sum(1 for j in jongs if j in RARE_BATCHIM)
    return n, round(no_batchim / n, 4), round(rare / n, 4)


def is_garbled_hangul(hangul: int, no_batchim_ratio: float, rare_ratio: float) -> bool:
    # 둘 다(AND) 만족해야 한다 — 받침 없음만 보면 정상 글의 짧은 구간(30음절 창 최소 0.133)이 걸린다
    return (hangul >= HANGUL_MIN_SYLLABLES and no_batchim_ratio < HANGUL_MAX_NO_BATCHIM
            and rare_ratio >= HANGUL_MIN_RARE_BATCHIM)


def classify_page(text: str, min_chars: int = DEFAULT_MIN_CHARS, max_bad_ratio: float = DEFAULT_MAX_BAD_RATIO) -> dict:
    visible = [ch for ch in text if not ch.isspace()]
    chars = len(visible)
    bad = sum(1 for ch in visible if _is_bad(ch))
    ratio = round(bad / chars, 4) if chars else 0.0
    hangul, no_batchim_ratio, rare_ratio = hangul_batchim_stats(visible)
    if chars == 0:
        status = "empty"
    elif ratio > max_bad_ratio:
        status = "garbled"
    elif chars < min_chars:
        status = "low_text"
    elif is_garbled_hangul(hangul, no_batchim_ratio, rare_ratio):
        status = "garbled_hangul"
    else:
        status = "ok"
    return {"chars": chars, "bad_chars": bad, "bad_ratio": ratio,
            "hangul_chars": hangul, "no_batchim_ratio": no_batchim_ratio, "rare_batchim_ratio": rare_ratio,
            "status": status}


def split_pages(text: str) -> list[str]:
    """pdftotext 는 쪽마다 끝에 폼피드(\\f)를 붙인다 — 마지막 폼피드 뒤 빈 조각만 버린다.
    (빈 쪽도 자기 폼피드를 가지므로 스캔 쪽이 끝에 있어도 사라지지 않는다.)"""
    pages = text.split("\f")
    if text.endswith("\f"):
        pages = pages[:-1]
    return pages


def _parse_range(value: str) -> tuple[int, int]:
    if "-" in value:
        a, b = value.split("-", 1)
        return int(a), int(b)
    return int(value), int(value)


def doc_needs_ocr(needs: int, pages: int) -> bool:
    return pages > 0 and needs / pages >= DOC_NEEDS_OCR_PAGE_RATIO


def analyze(pdf: str, first: int | None = None, last: int | None = None,
            min_chars: int = DEFAULT_MIN_CHARS, max_bad_ratio: float = DEFAULT_MAX_BAD_RATIO) -> dict:
    cmd = ["pdftotext", "-layout"]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [pdf, "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or f"pdftotext rc={proc.returncode}")
    text = proc.stdout.decode("utf-8", "replace")
    start = first or 1
    pages = []
    for offset, page_text in enumerate(split_pages(text)):
        page = {"page": start + offset}
        page.update(classify_page(page_text, min_chars, max_bad_ratio))
        pages.append(page)
    needs = [p["page"] for p in pages if p["status"] != "ok"]
    counts: dict[str, int] = {}
    for p in pages:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    return {
        "pdf": pdf,
        "pages_checked": len(pages),
        "summary": counts,
        "needs_vision": needs,
        "doc_needs_ocr": doc_needs_ocr(len(needs), len(pages)),
        "thresholds": {"min_chars": min_chars, "max_bad_ratio": max_bad_ratio,
                       "hangul_min_syllables": HANGUL_MIN_SYLLABLES,
                       "hangul_max_no_batchim": HANGUL_MAX_NO_BATCHIM,
                       "hangul_min_rare_batchim": HANGUL_MIN_RARE_BATCHIM,
                       "doc_needs_ocr_page_ratio": DOC_NEEDS_OCR_PAGE_RATIO},
        "pages": pages,
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    ap = argparse.ArgumentParser(description="PDF 페이지별 텍스트층 품질 판정")
    ap.add_argument("pdf")
    ap.add_argument("--pages", help="검사할 쪽 범위 (예: 3-9, 기본 전체)")
    ap.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)
    ap.add_argument("--max-bad-ratio", type=float, default=DEFAULT_MAX_BAD_RATIO)
    args = ap.parse_args(argv)
    if shutil.which("pdftotext") is None:
        print("오류: pdftotext 가 없습니다 — poppler-utils 를 설치하세요 "
              "(macOS: brew install poppler / Ubuntu: apt-get install -y poppler-utils)", file=sys.stderr)
        return 2
    first = last = None
    if args.pages:
        first, last = _parse_range(args.pages)
    try:
        result = analyze(args.pdf, first, last, args.min_chars, args.max_bad_ratio)
    except (RuntimeError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
