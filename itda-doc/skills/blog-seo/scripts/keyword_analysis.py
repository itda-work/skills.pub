"""
블루키워드 분석 파이프라인 - 메인 진입점

CLI: python3 scripts/keyword_analysis.py --keywords "파이썬 독학,파이썬 강의" [options]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from typing import Any

from naver_blog_search import NaverBlogSearchClient
from naver_datalab import NaverDatalabClient, detect_trend_type, calculate_trend_score
from naver_searchad import NaverSearchAdClient, MissingApiKeyError
from scoring import score_keyword, filter_keywords


class CliValidationError(Exception):
    """CLI 입력 유효성 검사 오류"""
    pass


def run_analysis(
    seed_keywords: list[str],
    searchad_api_key: str,
    searchad_secret_key: str,
    searchad_customer_id: str,
    naver_client_id: str,
    naver_client_secret: str,
    min_volume: int = 500,
    min_grade: str = "B",
    top_n: int = 50,
    include_trend: bool = False,
    cache_path: str | None = None,
) -> list[dict]:
    """키워드 분석 파이프라인 실행

    1. SearchAd API로 관련 키워드 확장
    2. 블로그 검색 API로 문서수 조회
    3. 스코어링 (포화지수, KEI, 등급)
    4. 필터링
    5. (선택) 트렌드 분석

    Returns:
        스코어링된 키워드 목록 (KEI 내림차순 정렬, 필터 적용)
    """
    # 1. API 클라이언트 초기화 (키 유효성 검사 포함)
    searchad_client = NaverSearchAdClient(
        api_key=searchad_api_key,
        customer_id=searchad_customer_id,
        secret_key=searchad_secret_key,
    )
    blog_client = NaverBlogSearchClient(
        client_id=naver_client_id,
        client_secret=naver_client_secret,
        cache_path=cache_path,
    )

    # 2. 관련 키워드 확장
    raw_keywords = searchad_client.get_keyword_suggestions(seed_keywords)

    if not raw_keywords:
        return []

    # 3. 블로그 문서수 조회
    keyword_texts = [kw["relKeyword"] for kw in raw_keywords]
    doc_counts = blog_client.batch_get_doc_counts(keyword_texts, top_n=top_n)

    # 4. 스코어링 — 블로그 문서수가 조회된 키워드만 처리 (top_n 범위 밖은 제외)
    scored_keywords = []
    for kw in raw_keywords:
        keyword = kw["relKeyword"]
        if keyword not in doc_counts:
            continue
        scored = score_keyword(
            keyword=keyword,
            monthly_pc=kw["monthly_pc"],
            monthly_mobile=kw["monthly_mobile"],
            doc_count=doc_counts[keyword],
        )
        scored["comp_idx"] = kw.get("comp_idx", "")
        scored_keywords.append(scored)

    # 5. 필터링
    filtered = filter_keywords(scored_keywords, min_volume=min_volume, min_grade=min_grade)

    # 6. (선택) 트렌드 분석
    if include_trend:
        datalab_client = NaverDatalabClient(
            client_id=naver_client_id,
            client_secret=naver_client_secret,
        )
        for item in filtered:
            trend_data = datalab_client.get_trend(item["keyword"])
            trend_type = detect_trend_type(trend_data)
            trend_score = calculate_trend_score(trend_type)
            item["trend_type"] = trend_type
            item["trend_score"] = trend_score

    return filtered


def format_results(results: list[dict], fmt: str = "json") -> str:
    """분석 결과를 지정된 포맷으로 변환

    Args:
        results: 스코어링된 키워드 목록
        fmt: "json" | "md" | "csv"

    Returns:
        포맷된 문자열
    """
    # KEI 내림차순 정렬
    sorted_results = sorted(results, key=lambda x: x.get("kei", 0), reverse=True)

    if fmt == "json":
        return json.dumps(sorted_results, ensure_ascii=False, indent=2)

    elif fmt == "md":
        return _format_markdown(sorted_results)

    elif fmt == "csv":
        return _format_csv(sorted_results)

    else:
        raise ValueError(f"지원하지 않는 출력 포맷: {fmt}. json|md|csv 중 하나를 사용하세요.")


def _format_markdown(results: list[dict]) -> str:
    """Markdown 테이블 형식 출력"""
    has_trend = any("trend_type" in r for r in results)

    lines = ["## 블루키워드 분석 결과", ""]

    if has_trend:
        lines.append("| 키워드 | 월간검색량 | 문서수 | 포화지수 | KEI | 등급 | 트렌드 |")
        lines.append("|--------|-----------|-------|---------|-----|------|--------|")
    else:
        lines.append("| 키워드 | 월간검색량 | 문서수 | 포화지수 | KEI | 등급 |")
        lines.append("|--------|-----------|-------|---------|-----|------|")

    for r in results:
        cells = [
            r.get('keyword', ''),
            f"{r.get('monthly_volume', 0):,}",
            f"{r.get('doc_count', 0):,}",
            f"{r.get('saturation_index', 0):.1f}%",
            f"{r.get('kei', 0):,.0f}",
            f"{r.get('grade', '')} ({r.get('grade_label', '')})",
        ]
        if has_trend:
            cells.append(r.get('trend_type', 'N/A'))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _format_csv(results: list[dict]) -> str:
    """CSV 형식 출력"""
    if not results:
        return ""

    output = io.StringIO()
    # 모든 필드 수집
    fieldnames = list(results[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)
    return output.getvalue()


def write_output(content: str, output_path: str | None = None) -> None:
    """결과 출력 (파일 또는 stdout)"""
    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        print(content)


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI 인수 파싱"""
    parser = argparse.ArgumentParser(
        description="네이버 API 기반 블루키워드 발굴 도구"
    )
    parser.add_argument(
        "--keywords",
        required=True,
        help="시드 키워드 (쉼표 구분, 최대 5개). 예: '파이썬 독학,파이썬 강의'",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=500,
        help="최소 월간 검색량 (기본값: 500)",
    )
    parser.add_argument(
        "--min-grade",
        default="B",
        choices=["S", "A", "B", "C", "D"],
        help="최소 등급 (기본값: B)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="블로그 문서수 조회 최대 키워드 수 (기본값: 20)",
    )
    parser.add_argument(
        "--trend",
        action="store_true",
        help="트렌드 분석 포함 (Naver Datalab API 호출)",
    )
    parser.add_argument(
        "--format",
        default="md",
        choices=["json", "md", "csv"],
        help="출력 포맷 (기본값: md)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="출력 파일 경로 (기본값: stdout)",
    )

    args = parser.parse_args(argv)

    # 키워드 파싱
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if len(keywords) > 5:
        raise CliValidationError(
            f"키워드는 최대 5개까지만 입력 가능합니다. 현재 {len(keywords)}개."
        )
    args.keywords = keywords

    return args


def main(argv: list[str] | None = None) -> int:
    """메인 진입점"""
    try:
        args = parse_cli_args(argv)
    except CliValidationError as e:
        print(f"입력 오류: {e}", file=sys.stderr)
        return 1

    # 환경변수에서 API 키 로드 (CLI > environ > .env, SPEC-ENV-ERROR-001)
    from _env_setup import (
        get_naver_client_id,
        get_naver_client_secret,
        get_searchad_access_key,
        get_searchad_customer_id,
        get_searchad_secret_key,
    )
    try:
        searchad_api_key = get_searchad_access_key()
        searchad_secret_key = get_searchad_secret_key()
        searchad_customer_id = get_searchad_customer_id()
        naver_client_id = get_naver_client_id()
        naver_client_secret = get_naver_client_secret()
    except MissingApiKeyError as e:
        print(f"API 키 오류: {e}", file=sys.stderr)
        return 1

    try:
        results = run_analysis(
            seed_keywords=args.keywords,
            searchad_api_key=searchad_api_key,
            searchad_secret_key=searchad_secret_key,
            searchad_customer_id=searchad_customer_id,
            naver_client_id=naver_client_id,
            naver_client_secret=naver_client_secret,
            min_volume=args.min_volume,
            min_grade=args.min_grade,
            top_n=args.top_n,
            include_trend=args.trend,
        )
    except MissingApiKeyError as e:
        print(f"API 키 오류: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"분석 중 오류 발생: {e}", file=sys.stderr)
        return 1

    output = format_results(results, fmt=args.format)
    write_output(output, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
