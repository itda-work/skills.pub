#!/usr/bin/env python3
"""PDF-to-Markdown 변환 품질 검증 스크립트.

출력 파일이 기대 품질 임계값을 충족하는지 검사한다.

Usage:
    python verify_quality.py <path> --pages <total_source_pages>
    python verify_quality.py output_dir/ --pages 470
    python verify_quality.py single_file.md --pages 50
    python verify_quality.py output/ --pages 50 --domain electronics
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# 도메인별 페이지 헤더 정규식 (REQ-010)
_DOMAIN_HEADER_REGEX: dict[str, str] = {
    "tax-accounting": r"^\d{1,3}\s{2,}\d{4}\s",
    "electronics": r"^\d+\s+[A-Za-z][A-Za-z\s]+\d+$",
    "legal": r"^제\d+조|^\d+\s+판례\s+\d+",
    "engineering": r"^\d+\s+Chapter\s+\d+|^\d+\s+[가-힣]+\s+\d+$",
}

# 기본 페이지 헤더 정규식 (backward compat, AC-8)
_DEFAULT_HEADER_REGEX = r"^\d{1,3}\s{2,}\d{4}\s"


def count_pattern(text: str, pattern: str) -> int:
    """텍스트에서 정규식 패턴의 매칭 횟수를 반환한다."""
    return len(re.findall(pattern, text, re.MULTILINE))


def check_domain_items(content: str, domain: str | None) -> list[tuple[str, str]]:
    """도메인별 추가 검증 항목을 검사한다 (REQ-010, AC-11).

    Args:
        content: 검사할 마크다운 텍스트 전체.
        domain: 도메인 이름 (None이면 빈 리스트 반환, AC-8 backward compat).

    Returns:
        (status, message) 튜플 리스트. status는 'PASS' 또는 'FAIL'.
    """
    if domain is None:
        return []

    verdicts: list[tuple[str, str]] = []

    if domain == "tax-accounting":
        # 법령 약칭 패턴: (조특법|법인령|소득령) 제?N조 카운트 ≥1
        pattern = r"(조특법|법인령|소득령)\s+제?\d+조"
        cnt = count_pattern(content, pattern)
        if cnt >= 1:
            verdicts.append(("PASS", f"Domain check [tax-accounting]: 법령 약칭 패턴 {cnt}건 발견"))
        else:
            verdicts.append(("FAIL", "Domain check [tax-accounting]: 법령 약칭 패턴 (조특법|법인령|소득령) 제?N조 0건 — 세무 PDF인지 확인"))

    elif domain == "electronics":
        # 수식 패턴: $...$  또는 \\[a-zA-Z]+ 카운트 ≥1
        pattern = r"\$[^$]+\$|\\[a-zA-Z]+"
        cnt = count_pattern(content, pattern)
        if cnt >= 1:
            verdicts.append(("PASS", f"Domain check [electronics]: 수식 패턴 {cnt}건 발견"))
        else:
            verdicts.append(("FAIL", "Domain check [electronics]: 수식 패턴 ($...$|\\cmd) 0건 — 이공계 PDF 수식 추출 확인"))

    elif domain == "legal":
        # 조문 패턴: 제N조 카운트 ≥3
        pattern = r"제\d+조"
        cnt = count_pattern(content, pattern)
        if cnt >= 3:
            verdicts.append(("PASS", f"Domain check [legal]: 조문 패턴 {cnt}건 발견"))
        else:
            verdicts.append(("FAIL", f"Domain check [legal]: 조문 패턴 제N조 {cnt}건 — 법률 PDF는 3건 이상 필요"))

    elif domain == "engineering":
        # 단위 패턴: N MPa|kN|Pa|N  또는  KS [A-Z] N 카운트 ≥1
        pattern = r"\d+\s*(MPa|kN|Pa|N)\b|KS\s+[A-Z]\s+\d+"
        cnt = count_pattern(content, pattern)
        if cnt >= 1:
            verdicts.append(("PASS", f"Domain check [engineering]: 단위/규격 패턴 {cnt}건 발견"))
        else:
            verdicts.append(("FAIL", "Domain check [engineering]: 단위(MPa|kN|Pa|N) 또는 KS 규격 0건 — 공학 PDF인지 확인"))

    # 알 수 없는 도메인은 빈 리스트 반환 (AC-8 guard)
    return verdicts


def analyze_file(filepath: str) -> dict:
    """단일 마크다운 파일의 구조 메트릭을 분석한다."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    return {
        "file": os.path.basename(filepath),
        "lines": len(lines),
        "h2_headers": count_pattern(content, r"^## "),
        "h3_headers": count_pattern(content, r"^### "),
        "h4_headers": count_pattern(content, r"^#### "),
        "table_rows": count_pattern(content, r"^\|"),
        "images": count_pattern(content, r"!\["),
        "page_markers": count_pattern(content, r"<!-- p\.\d+"),
        "blockquotes": count_pattern(content, r"^>"),
        "list_items": count_pattern(content, r"^- "),
        "empty_lines_ratio": sum(1 for line in lines if line.strip() == "") / max(len(lines), 1),
    }


def check_ocr_artifacts(filepath: str, header_regex: str = _DEFAULT_HEADER_REGEX) -> list[str]:
    """마크다운 파일에서 OCR 아티팩트를 탐지한다."""
    issues: list[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.rstrip()
            # 글머리 아티팩트
            if re.match(r"^- \.\s", line):
                issues.append(f"  Line {i}: Bullet artifact '- .' -> should be '- '")
            # 페이지 번호 본문 혼입 (도메인별 헤더 정규식 사용)
            if re.match(header_regex, line):
                issues.append(f"  Line {i}: Possible page header in content: '{line[:50]}'")
            # 고아 짧은 조각 (테이블 셀 잔해 가능성)
            stripped = line.strip()
            if (
                0 < len(stripped) < 4
                and not stripped.startswith("#")
                and not stripped.startswith("|")
                and not stripped.startswith("-")
                and not stripped.startswith(">")
                and not stripped.startswith("`")
                and stripped != "---"
            ):
                issues.append(f"  Line {i}: Orphaned fragment: '{stripped}'")
    return issues[:20]  # 최대 20개로 제한


def verify(
    path: str,
    total_pages: int,
    doc_type: str = "textbook",
    domain: str | None = None,
) -> bool:
    """변환 결과의 품질을 검증한다.

    Args:
        path: .md 파일 또는 .md 파일이 있는 디렉토리 경로
        total_pages: 원본 PDF의 총 페이지 수
        doc_type: 문서 유형 (textbook, manual, form_heavy)
        domain: 도메인 옵션 (tax-accounting|electronics|legal|engineering|None).
                None이면 기존 동작 100% 유지 (AC-8 backward compat).

    Returns:
        모든 검사를 통과하면 True, 아니면 False
    """
    thresholds = {
        "textbook": {"min_lines_per_page": 8, "healthy_min": 15},
        "manual": {"min_lines_per_page": 7, "healthy_min": 10},
        "form_heavy": {"min_lines_per_page": 2, "healthy_min": 3},
    }
    t = thresholds.get(doc_type, thresholds["textbook"])

    # 도메인별 페이지 헤더 정규식 선택 (AC-8: None이면 기본값)
    header_regex = _DOMAIN_HEADER_REGEX.get(domain, _DEFAULT_HEADER_REGEX) if domain else _DEFAULT_HEADER_REGEX

    md_files: list[str] = []
    p = Path(path)
    if p.is_file() and p.suffix == ".md":
        md_files = [str(p)]
    elif p.is_dir():
        md_files = sorted(str(f) for f in p.glob("*.md") if f.name != "INDEX.md")

    if not md_files:
        print(f"ERROR: No .md files found at {path}")
        return False

    total_lines = 0
    all_passed = True
    results: list[dict] = []
    all_content = ""

    print(f"{'=' * 60}")
    print("PDF-to-Markdown Quality Report")
    print(f"{'=' * 60}")
    print(f"Source pages: {total_pages}")
    print(f"Document type: {doc_type}")
    if domain:
        print(f"Domain: {domain}")
    print(f"Files found: {len(md_files)}")
    print()

    for filepath in md_files:
        stats = analyze_file(filepath)
        total_lines += stats["lines"]
        results.append(stats)

        # 도메인 검증용 콘텐츠 누적
        with open(filepath, "r", encoding="utf-8") as f:
            all_content += f.read()

        print(f"--- {stats['file']} ---")
        print(f"  Lines: {stats['lines']}")
        print(f"  Structure: {stats['h2_headers']} ##, {stats['h3_headers']} ###, {stats['h4_headers']} ####")
        print(f"  Tables: {stats['table_rows']} rows")
        print(f"  Images: {stats['images']}, Page markers: {stats['page_markers']}")
        print(f"  Lists: {stats['list_items']}, Blockquotes: {stats['blockquotes']}")

        # OCR 아티팩트 검사 (도메인별 헤더 정규식 사용)
        artifacts = check_ocr_artifacts(filepath, header_regex=header_regex)
        if artifacts:
            print(f"  OCR Artifacts ({len(artifacts)} found):")
            for a in artifacts[:5]:
                print(f"    {a}")
            if len(artifacts) > 5:
                print(f"    ... and {len(artifacts) - 5} more")
        print()

    # 종합 평가
    lines_per_page = total_lines / max(total_pages, 1)

    print(f"{'=' * 60}")
    print("OVERALL ASSESSMENT")
    print(f"{'=' * 60}")
    print(f"Total lines: {total_lines}")
    print(f"Lines per page: {lines_per_page:.1f}")
    print(f"Threshold (content loss): < {t['min_lines_per_page']} lines/page")
    print(f"Healthy range: >= {t['healthy_min']} lines/page")
    print()

    # 판정
    verdicts: list[tuple[str, str]] = []

    if lines_per_page < t["min_lines_per_page"]:
        verdicts.append(("FAIL", f"Content likely LOST: {lines_per_page:.1f} lines/page (below {t['min_lines_per_page']})"))
        all_passed = False
    elif lines_per_page < t["healthy_min"]:
        verdicts.append(("WARN", f"Content may be thin: {lines_per_page:.1f} lines/page (below healthy {t['healthy_min']})"))
    else:
        verdicts.append(("PASS", f"Content density OK: {lines_per_page:.1f} lines/page"))

    total_tables = sum(r["table_rows"] for r in results)
    total_headers = sum(r["h2_headers"] + r["h3_headers"] for r in results)

    if total_headers == 0:
        verdicts.append(("FAIL", "No markdown headers found -- structure missing"))
        all_passed = False
    else:
        verdicts.append(("PASS", f"Structure present: {total_headers} headers"))

    if total_tables > 0:
        verdicts.append(("PASS", f"Tables present: {total_tables} rows"))
    else:
        verdicts.append(("WARN", "No tables found -- verify source has no tabular data"))

    # 도메인별 추가 검증 항목 (REQ-010, AC-11)
    domain_verdicts = check_domain_items(all_content, domain=domain)
    for dv in domain_verdicts:
        if dv[0] == "FAIL":
            all_passed = False
    verdicts.extend(domain_verdicts)

    for v in verdicts:
        status, msg = v
        icon = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}[status]
        print(f"  {icon} {msg}")

    print()
    if all_passed:
        print("Result: PASSED")
    else:
        print("Result: NEEDS ATTENTION -- re-process flagged sections with smaller chunks")

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify PDF-to-Markdown conversion quality.\n"
            "Use --domain to apply domain-specific header regex and verification items.\n"
            "Domains: tax-accounting, electronics, legal, engineering"
        )
    )
    parser.add_argument("path", help="Path to .md file or directory of .md files")
    parser.add_argument("--pages", type=int, required=True, help="Total source PDF pages")
    parser.add_argument(
        "--type",
        choices=["textbook", "manual", "form_heavy"],
        default="textbook",
        help="Document type for threshold selection",
    )
    parser.add_argument(
        "--domain",
        choices=["tax-accounting", "electronics", "legal", "engineering"],
        default=None,
        help=(
            "Domain-specific verification mode (REQ-010). "
            "tax-accounting: 법령 약칭 패턴 검증. "
            "electronics: 수식 패턴 검증. "
            "legal: 조문 패턴 ≥3 검증. "
            "engineering: 단위/KS규격 패턴 검증. "
            "기본값 None은 기존 동작 유지 (backward compat)."
        ),
    )
    args = parser.parse_args()

    passed = verify(args.path, args.pages, args.type, domain=args.domain)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
