#!/usr/bin/env python3
"""오피넷 평균 유가 조회 — 전국·시도 × 일간/주간/월간, 전기 대비 등락.

사용법:
    python3 fuel_price.py                                   # 전국 · 휘발유 · 월간 3개월
    python3 fuel_price.py --region 인천 --product 경유
    python3 fuel_price.py --term week --periods 8 --detail
    python3 fuel_price.py --term month --end 2026-07        # 특정 시점(과거) 조회
    python3 fuel_price.py --format table                    # 사람용 요약+표 (기본은 compact JSON)
    python3 fuel_price.py --source api --term day           # OPINET_API_KEY 있을 때만

출력은 결정론적(같은 응답 → 같은 문자열)이며 stdout 만 쓴다. 에러는 한국어로 stderr, exit 1.

유류비 정산 단가·공지문 생성은 스킬 범위 밖이다(마스터 결정 2026-09-02 — 조회에만 집중).
km당 단가가 필요하면 회사 규정 산식(예: 기준가 ÷ 연비 × 보정계수)으로 소비자가 계산한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass

import opinet_web
from opinet_web import NATIONAL, OpinetWebError, WebQueryResult

SOURCE_NOTE = "출처: 오피넷(한국석유공사) https://www.opinet.co.kr — 평균판매가격(부가세 포함, 원/리터)"


def fmt_won(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{digits}f}"


def diff_text(cur: float | None, prev: float | None) -> str:
    if cur is None or prev is None:
        return "—"
    d = cur - prev
    if abs(d) < 0.005:
        return "보합"
    return ("▲" if d > 0 else "▼") + f"{abs(d):,.2f}원"


PREV_WORD = {"day": "전일", "week": "전주", "month": "전월"}


@dataclass
class Briefing:
    term: str
    region: str
    product: str
    latest_label: str
    latest_price: float | None
    prev_label: str | None
    prev_price: float | None
    series: list[tuple[str, float | None]]
    as_of: str
    source: str

    def summary_line(self) -> str:
        head = f"{self.latest_label} {self.region} 평균 {self.product} {fmt_won(self.latest_price)}원/L"
        if self.prev_label is not None:
            head += f" ({PREV_WORD.get(self.term, '전기')} {fmt_won(self.prev_price)} 대비 {diff_text(self.latest_price, self.prev_price)})"
        return head

    def detail_table(self) -> str:
        lines = [f"| 기간 | {self.region} {self.product} (원/L) | 증감 |", "|---|---:|---:|"]
        prev: float | None = None
        for label, price in self.series:
            lines.append(f"| {label} | {fmt_won(price)} | {diff_text(price, prev) if prev is not None else '—'} |")
            prev = price
        return "\n".join(lines)

    def to_json(self) -> str:
        d = asdict(self)
        d["series"] = [{"period": l, "price": p} for l, p in self.series]
        d["summary"] = self.summary_line()
        d["detail_table"] = self.detail_table()
        d["source_note"] = SOURCE_NOTE
        # itda-gov 규약: stdout JSON 은 compact — pretty-print 금지 (#438, dart test_response_compact_guard 가 팩 전체 스캔)
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def make_briefing(
    series: list[tuple[str, float | None]],
    *,
    term: str,
    region: str,
    product: str,
    as_of: str,
    source: str,
) -> Briefing:
    if not series:
        raise OpinetWebError("조회 결과가 비었습니다")
    latest_label, latest_price = series[-1]
    prev_label, prev_price = (series[-2] if len(series) >= 2 else (None, None))
    return Briefing(
        term=term, region=region, product=product,
        latest_label=latest_label, latest_price=latest_price,
        prev_label=prev_label, prev_price=prev_price,
        series=list(series), as_of=as_of, source=source,
    )


def briefing_from_web(result: WebQueryResult) -> Briefing:
    return make_briefing(
        result.series, term=result.term, region=result.region, product=result.product_name,
        as_of=result.as_of, source="web",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="오피넷 평균 유가 조회 (전국·시도 × 일/주/월)")
    p.add_argument("--region", default=NATIONAL, help="전국(기본) 또는 시도명(서울·경기·인천…)")
    p.add_argument("--product", default="휘발유", help="휘발유(기본)·고급휘발유·경유·등유")
    p.add_argument("--term", choices=["day", "week", "month"], default="month", help="기간 단위(기본 month)")
    p.add_argument("--periods", type=int, default=3, help="가져올 기간 수(기본 3 — 전기 대비 계산용)")
    p.add_argument("--end", default=None,
                   help="조회 종료 시점 — 일간 YYYY-MM-DD, 주간·월간 YYYY-MM (기본: 오피넷 최신. 예: 2026-07 → 7월 평균)")
    p.add_argument("--format", choices=["json", "table"], default="json",
                   help="json(기본, compact — LLM·후처리용, summary 문자열 포함) | table(사람용 요약+표)")
    p.add_argument("--detail", action="store_true", help="(table 형식) 기간별 표 포함 — --format table 을 함축")
    p.add_argument("--json", action="store_true", help="(구식 별칭) --format json 과 동일")
    p.add_argument("--source", choices=["web", "api"], default="web",
                   help="web(기본, 키 불요) | api(OPINET_API_KEY 필요 — day 만, 최근 7일)")
    p.add_argument("--api-key", default=None, help="오피넷 API 키(--source api). 미지정 시 OPINET_API_KEY")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.source == "api":
            import opinet_api

            if args.term != "day":
                raise OpinetWebError(
                    "오피넷 Open API 에는 주간·월간 평균이 없습니다 — --source web(기본) 을 쓰거나 --term day 로 조회하세요"
                )
            if args.end:
                raise OpinetWebError("--source api 는 최근 7일만 제공합니다 — 특정 시점(--end)은 --source web(기본) 으로 조회하세요")
            key = opinet_api.resolve_key(args.api_key)
            prod = opinet_web.resolve_product(args.product)
            sido = opinet_web.resolve_region(args.region)
            region_name, series = opinet_api.series_from_api(key, region_code=sido, prodcd=prod)
            series = series[-max(args.periods, 2):]
            as_of = "".join(ch for ch in series[-1][0] if ch.isdigit()) if series else ""
            b = make_briefing(
                series, term="day", region=region_name, product=opinet_web.PRODUCTS[prod],
                as_of=as_of if len(as_of) == 8 else "????????", source="api",
            )
        else:
            result = opinet_web.fetch_average(
                term=args.term, periods=max(args.periods, 2), region=args.region, product=args.product, end=args.end,
            )
            result.series = result.series[-args.periods:] if args.periods >= 2 else result.series[-2:]
            b = briefing_from_web(result)
    except OpinetWebError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    fmt = args.format
    if args.detail and not args.json:
        fmt = "table"
    if fmt == "json":
        print(b.to_json())
        return 0
    print(b.summary_line())
    print()
    print(b.detail_table())
    print(SOURCE_NOTE)
    return 0


if __name__ == "__main__":
    sys.exit(run())
