"""국토교통부 실거래가 12개 유형 — 저장된 응답 파일의 읽기·전량 대조·정규화 (네트워크 없음).

요청은 itda-hyve 가 달·페이지마다 보내고 ``save_as`` 로 저장한다(itda-work/skills#45). 구
``collect_deals_for_month``·``collect_deals_range``(직접 호출 페이지 순회)는 지웠다.

호출 계획은 스크립트가 만든다(W1 리뷰 M3) — ``plan_calls`` 가 달마다 1쪽, ``next_calls`` 가
모자란 쪽을 batch ``plan_file`` 로 쓸 호출 목록으로 만든다. 모델은 ``pageNo``·``DEAL_YMD``·
``save_as`` 를 손으로 옮겨 적지 않는다. 저장 이름 ``<유형>-<코드>-<YYYYMM>-p<쪽>.xml`` 이 식별
계약이고, ``read_sources`` 가 이름을 본문(``pageNo``·거래월·``sggCd``)과 대조한다(W1 리뷰 M1).

전량 판정(``completeness``)은 건수 합만 보지 않는다 — 같은 (달, 쪽) 중복은 인자 오류, 같은 달
쪽마다 ``totalCount``·``numOfRows`` 가 다르거나 쪽 경계에서 행이 겹치거나 건수가 넘치면 그 달을
처음부터 다시 받을 ``refetch`` 로 둔다(``max`` 로 조용히 합치지 않는다).

공개 API:
    ENDPOINT_MAP            -- 12개 엔드포인트 유형 매핑 테이블
    PAGE_ROWS·BATCH_LIMIT   -- 계획의 쪽당 행 수(100)·batch 한 번의 호출 상한(40)
    month_range             -- 시작월~종료월 YYYYMM 리스트 생성기
    check_month_range       -- YYYYMM 형식·순서 검증
    expand_inputs           -- 입력 인자의 글로브(``*``)를 스크립트가 펼친다(PowerShell 대비)
    save_name·parse_save_name -- 저장 이름 규칙
    source_month            -- 한 응답 파일의 거래월(YYYYMM) 추정
    read_sources            -- 응답 파일들 → (원본 항목, 파일별 메타) + 이름·본문 대조
    completeness            -- 달별 전량 판정(누락 쪽·다시 받을 달·빠진 달)
    month_completeness      -- 달별 totalCount ↔ 수집 건수 대조 (completeness 요약)
    missing_pages           -- 달별로 더 받아야 할 쪽 번호
    missing_months          -- 요청 기간 중 파일이 하나도 없는 달
    run_dir_name·run_dir_of -- 한 회차의 저장 폴더(save_dir 기준 상대 경로)
    build_call·plan_calls·next_calls -- batch 호출 목록
    write_plan_files        -- 40개 단위로 나눠 batch plan_file 로 쓴다
    check_endpoint_fields   -- 항목이 그 엔드포인트 응답인지(단지명 필드)
    is_cancelled            -- 해제 거래(cdealType) 판정
    normalize_trade_item    -- 매매 항목 snake_case 정규화
    normalize_rent_item     -- 전월세 항목 snake_case 정규화
    build_envelope          -- JSON envelope 생성
    items_to_csv            -- items → CSV 문자열
    save_results            -- .json + .csv 저장
"""
from __future__ import annotations

import csv
import glob
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# RealEstateAPIError·compute_summary는 deals_cli.py가 import하는 의도된 재노출 (ruff F401 제외)
from data_go_client import (  # noqa: F401
    RealEstateAPIError,
    compute_summary,
    parse_amount,
    parse_response_xml,
)

# ---------------------------------------------------------------------------
# 12개 엔드포인트 유형 매핑 테이블 (R10)
# ---------------------------------------------------------------------------
# 형식: { endpoint_key: {"url": ..., "service_name": ..., "deal_type": "trade"|"rent"} }
#
# 국토부 data.go.kr 실거래가 서비스 12종:
#   8 부동산 유형 × (매매 + 전월세) = 16 조합이지만
#   토지·상업업무용·공장창고·분양입주권은 전월세(rent) API 미제공 → 12개
#
#   매매(trade) 8종: 아파트, 오피스텔, 연립다세대, 단독다가구,
#                    토지, 상업업무용, 공장창고, 분양입주권
#   전월세(rent) 4종: 아파트, 오피스텔, 연립다세대, 단독다가구

_BASE_URL = "https://apis.data.go.kr/1613000"

ENDPOINT_MAP: dict[str, dict[str, str]] = {
    # ---- 매매 (trade) 8종 ----
    "apt_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
        "service_name": "RTMSDataSvcAptTrade",
        "deal_type": "trade",
        "prop_label": "아파트",
        "apply_url": "https://www.data.go.kr/data/15126469/openapi.do",
    },
    "offi_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
        "service_name": "RTMSDataSvcOffiTrade",
        "deal_type": "trade",
        "prop_label": "오피스텔",
        "apply_url": "https://www.data.go.kr/data/15126464/openapi.do",
    },
    "rh_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
        "service_name": "RTMSDataSvcRHTrade",
        "deal_type": "trade",
        "prop_label": "연립다세대",
        "apply_url": "https://www.data.go.kr/data/15058017/openapi.do",
    },
    "sh_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
        "service_name": "RTMSDataSvcSHTrade",
        "deal_type": "trade",
        "prop_label": "단독다가구",
        "apply_url": "https://www.data.go.kr/data/15058022/openapi.do",
    },
    "land_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
        "service_name": "RTMSDataSvcLandTrade",
        "deal_type": "trade",
        "prop_label": "토지",
        "apply_url": "https://www.data.go.kr/data/15126472/openapi.do",
    },
    "biz_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
        "service_name": "RTMSDataSvcNrgTrade",
        "deal_type": "trade",
        "prop_label": "상업업무용",
        "apply_url": "https://www.data.go.kr/data/15126471/openapi.do",
    },
    "factory_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcFctTrade/getRTMSDataSvcFctTrade",
        "service_name": "RTMSDataSvcFctTrade",
        "deal_type": "trade",
        "prop_label": "공장창고",
        "apply_url": "https://www.data.go.kr/data/15055660/openapi.do",
    },
    "presale_trade": {
        "url": f"{_BASE_URL}/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade",
        "service_name": "RTMSDataSvcSilvTrade",
        "deal_type": "trade",
        "prop_label": "분양입주권",
        "apply_url": "https://www.data.go.kr/data/15126467/openapi.do",
    },
    # ---- 전월세 (rent) 4종 ----
    "apt_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
        "service_name": "RTMSDataSvcAptRent",
        "deal_type": "rent",
        "prop_label": "아파트",
        "apply_url": "https://www.data.go.kr/data/15126474/openapi.do",
    },
    "offi_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
        "service_name": "RTMSDataSvcOffiRent",
        "deal_type": "rent",
        "prop_label": "오피스텔",
        "apply_url": "https://www.data.go.kr/data/15126475/openapi.do",
    },
    "rh_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
        "service_name": "RTMSDataSvcRHRent",
        "deal_type": "rent",
        "prop_label": "연립다세대",
        "apply_url": "https://www.data.go.kr/data/15058020/openapi.do",
    },
    "sh_rent": {
        "url": f"{_BASE_URL}/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
        "service_name": "RTMSDataSvcSHRent",
        "deal_type": "rent",
        "prop_label": "단독다가구",
        "apply_url": "https://www.data.go.kr/data/15058023/openapi.do",
    },
}


# 계획의 쪽당 행 수 — 쪽 수는 ceil(totalCount / PAGE_ROWS) 다.
PAGE_ROWS = 100
# itda-hyve batch 는 호출이 40개를 넘으면 하나도 실행하지 않는다(netbridge §batch).
BATCH_LIMIT = 40
# batch 전체 시간 상한 — Cowork 는 도구 호출 하나를 60초에 끊는다.
BATCH_TIMEOUT_SEC = 50
SECRET_KEY = "{{secret:KO_DATA_API_KEY}}"

# ---------------------------------------------------------------------------
# 월 범위 유틸리티
# ---------------------------------------------------------------------------

_YM = re.compile(r"^(\d{4})(\d{2})$")


def check_month_range(start_ymd: str, end_ymd: str) -> None:
    """``YYYYMM`` 형식과 순서를 검증한다. 틀리면 ValueError(인자 오류).

    ``2026-08`` 같은 꼴이나 역순 범위를 그대로 두면 없는 달(``202600``)을 안내하거나 빈 범위로
    빠진 달 검사가 꺼진다(W1 리뷰 m1).
    """
    for name, ym in (("--start-month", start_ymd), ("--end-month", end_ymd)):
        m = _YM.match(ym or "")
        if not m or not 1 <= int(m.group(2)) <= 12:
            raise ValueError(f"{name} 는 YYYYMM 이다(예: 202608) — 받은 값: {ym!r}")
    if start_ymd > end_ymd:
        raise ValueError(f"--start-month {start_ymd} 가 --end-month {end_ymd} 보다 늦다")

def month_range(start_ymd: str, end_ymd: str):
    """시작월~종료월(YYYYMM) 범위의 월 목록을 순서대로 생성한다.

    Args:
        start_ymd: 시작 연월 (YYYYMM, 예: "202601").
        end_ymd: 종료 연월 (YYYYMM, 예: "202606").

    Yields:
        YYYYMM 형식의 문자열.
    """
    start_y = int(start_ymd[:4])
    start_m = int(start_ymd[4:6])
    end_y = int(end_ymd[:4])
    end_m = int(end_ymd[4:6])

    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# 저장된 응답 파일 읽기 + 전량 대조
# ---------------------------------------------------------------------------

# 유형별로 응답 항목에 반드시 있는 금액 필드 — 매매·전월세 파일을 뒤바꿔 넘기면 잡는다.
_KIND_FIELD = {"trade": "dealAmount", "rent": "deposit"}
_KIND_LABEL = {"trade": "매매", "rent": "전월세"}

# 저장 이름 규칙 `<유형>-<코드>-<YYYYMM>-p<쪽>.xml` — 식별 계약이다. plan 이 이 이름을 만들고,
# read_sources 가 본문과 대조한다. 0건인 달은 항목으로 달을 알 수 없어 이름에서 읽는다.
_SAVE_NAME = re.compile(
    r"^(?P<kind>[a-z]+_(?:trade|rent))-(?P<code>\d{5})-(?P<month>\d{6})-p(?P<page>\d+)\.xml$"
)
_NAME_MONTH = re.compile(r"-(\d{6})-p\d+\.[A-Za-z]+$")


def save_name(endpoint_type: str, lawd_cd: str, month: str, page: int) -> str:
    """저장 이름 ``<유형>-<코드>-<YYYYMM>-p<쪽>.xml`` (한글 없음)."""
    return f"{endpoint_type}-{lawd_cd}-{month}-p{page}.xml"


def parse_save_name(name: str) -> dict[str, Any] | None:
    """저장 이름을 풀어 ``kind``·``code``·``month``·``page`` 를 돌려준다. 규칙 밖 이름이면 None."""
    m = _SAVE_NAME.match(name)
    if not m or m.group("kind") not in ENDPOINT_MAP:
        return None
    return {"kind": m.group("kind"), "code": m.group("code"),
            "month": m.group("month"), "page": int(m.group("page"))}


def expand_inputs(paths: list[str]) -> list[str]:
    """입력 인자에 글로브(``*``·``?``·``[``)가 있으면 스크립트가 펼친다.

    bash 는 셸이 펼치지만 PowerShell 은 네이티브 실행 파일에 와일드카드를 넘긴다(W1 리뷰 m6).
    따옴표로 감싼 패턴도 같은 결과가 나오게 여기서 펼친다. 맞는 파일이 없으면 ValueError.
    """
    out: list[str] = []
    for p in paths:
        if any(ch in p for ch in "*?["):
            matched = sorted(glob.glob(str(Path(p).expanduser())))
            if not matched:
                raise ValueError(f"입력 파일이 없습니다: {p} (패턴과 맞는 파일이 없다)")
            out.extend(matched)
        else:
            out.append(p)
    return out


def source_month(items: list[dict[str, str]]) -> str:
    """그 파일이 담은 거래월(YYYYMM). 항목이 없으면 빈 문자열.

    응답 XML 에는 조회 월(DEAL_YMD)이 없으므로 항목의 dealYear·dealMonth 최빈값으로 정한다.
    """
    months = [
        f"{(i.get('dealYear') or '').strip()}{(i.get('dealMonth') or '').strip().zfill(2)}"
        for i in items
        if (i.get("dealYear") or "").strip() and (i.get("dealMonth") or "").strip()
    ]
    if not months:
        return ""
    return Counter(months).most_common(1)[0][0]


def _row_key(item: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(item.items()))


def read_sources(
    paths: list[str],
    *,
    deal_type: str | None = None,
    endpoint_type: str | None = None,
    lawd_cd: str | None = None,
    month_span: tuple[str, str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """itda-hyve 가 저장한 응답 파일들을 읽어 (원본 항목 누적, 파일별 메타) 를 돌려준다.

    이름이 저장 규칙을 따르면 본문과 대조한다(식별 계약 — W1 리뷰 M1):
    ``-p<쪽>`` ↔ 본문 ``pageNo`` · ``-<YYYYMM>`` ↔ 항목 거래월 · ``-<코드>`` ↔ 항목 ``sggCd`` ·
    ``<유형>`` ↔ ``endpoint_type``. 규칙 밖 이름도 받되 본문끼리의 대조(``sggCd``·중복 쪽)는 한다.

    Args:
        paths: 응답 파일 경로들(달·페이지마다 1개). 글로브는 ``expand_inputs`` 가 펼친다.
        deal_type: "trade"·"rent" 를 주면 항목이 그 유형의 응답인지 확인한다.
        endpoint_type: ``apt_trade`` 등. 저장 이름의 유형과 대조한다.
        lawd_cd: 법정동코드. 항목 ``sggCd``·저장 이름의 코드와 대조한다.
        month_span: (시작월, 종료월). 범위 밖 달의 파일을 거부한다.

    Raises:
        ValueError: 파일 없음, 유형이 다른 응답, 이름↔본문 불일치, 다른 지역·범위 밖 달, 같은 (달, 쪽) 중복.
        RealEstateAPIError: 성공 응답이 아닌 파일(메시지 앞에 파일 이름을 붙인다).
    """
    raw_items: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    edges: list[tuple[dict[str, Any], tuple, tuple]] = []
    for p in expand_inputs(paths):
        path = Path(p).expanduser()
        if not path.is_file():
            raise ValueError(f"입력 파일이 없습니다: {p}")
        try:
            parsed = parse_response_xml(path.read_bytes())
        except RealEstateAPIError as exc:
            raise RealEstateAPIError(
                f"{path.name}: {exc}", error_code=exc.error_code, kind=exc.kind, hyve_code=exc.hyve_code
            ) from exc
        items = parsed["items"]
        if deal_type in _KIND_FIELD and items and _KIND_FIELD[deal_type] not in items[0]:
            raise ValueError(
                f"{path.name}: {_KIND_LABEL[deal_type]} 응답이 아닙니다"
                f"({_KIND_FIELD[deal_type]} 필드 없음) — 매매·전월세 파일이 뒤바뀌지 않았는지 확인"
            )
        body_month = source_month(items)
        codes = sorted({(i.get("sggCd") or "").strip() for i in items} - {""})
        name = parse_save_name(path.name)
        if name:
            if endpoint_type and name["kind"] != endpoint_type:
                raise ValueError(
                    f"{path.name}: 저장 이름의 유형 {name['kind']} 가 {endpoint_type} 와 다르다 — 받은 엔드포인트와 인자를 맞춘다"
                )
            if name["page"] != parsed["page"]:
                raise ValueError(
                    f"{path.name}: 저장 이름은 {name['page']}쪽인데 본문 pageNo={parsed['page']} — "
                    "호출의 pageNo 와 save_as 가 어긋났다. 계획(plan)이 만든 호출을 그대로 쓴다"
                )
            if body_month and body_month != name["month"]:
                raise ValueError(
                    f"{path.name}: 저장 이름은 {name['month']} 인데 항목의 거래월은 {body_month} — "
                    "호출의 DEAL_YMD 와 save_as 가 어긋났다"
                )
            if codes and codes != [name["code"]]:
                raise ValueError(
                    f"{path.name}: 저장 이름의 지역코드 {name['code']} 와 항목 sggCd {codes} 가 다르다"
                )
            if lawd_cd and name["code"] != lawd_cd:
                raise ValueError(f"{path.name}: 저장 이름의 지역코드 {name['code']} 가 --lawd-cd {lawd_cd} 와 다르다")
        if len(codes) > 1:
            raise ValueError(f"{path.name}: 한 응답에 지역코드가 여럿이다({codes})")
        if lawd_cd and codes and codes != [lawd_cd]:
            raise ValueError(f"{path.name}: 응답의 sggCd {codes[0]} 가 지역코드 {lawd_cd} 와 다르다 — 다른 지역 파일이 섞였다")
        month = body_month or (name["month"] if name else "")
        if not month:
            m = _NAME_MONTH.search(path.name)
            month = m.group(1) if m else ""
        if month_span and month and not (month_span[0] <= month <= month_span[1]):
            raise ValueError(
                f"{path.name}: {month} 는 요청 기간 {month_span[0]}~{month_span[1]} 밖이다 — 그 달 파일은 넘기지 않는다"
            )
        raw_items.extend(items)
        src = {
            "path": str(path),
            "month": month,
            "total_count": parsed["total_count"],
            "page": parsed["page"],
            "num_of_rows": parsed.get("num_of_rows", 0),
            "item_count": len(items),
            "sgg_cd": codes[0] if codes else (name["code"] if name else ""),
        }
        sources.append(src)
        if items:
            edges.append((src, _row_key(items[0]), _row_key(items[-1])))

    # 같은 (달, 쪽) 이 두 파일에 있으면 한쪽은 다른 질의이거나 사본이다 — 건수 합이 맞아도 통과시키지 않는다.
    seen: dict[tuple[str, int], str] = {}
    for src in sources:
        if not src["month"]:
            continue
        key = (src["month"], src["page"])
        if key in seen:
            raise ValueError(
                f"{src['month']} {src['page']}쪽이 두 파일에 있다: {Path(seen[key]).name} · {Path(src['path']).name} — "
                "하나만 넘긴다(다른 폴더의 사본·이름을 바꾼 파일이 섞였는지 확인)"
            )
        seen[key] = src["path"]

    # 쪽 경계에서 행이 겹치면(앞 쪽 마지막 행 == 다음 쪽 첫 행) 받는 사이 목록이 밀린 것이다.
    by_pos = {(src["month"], src["page"]): (first, last) for src, first, last in edges}
    for src, first, _ in edges:
        prev = by_pos.get((src["month"], src["page"] - 1))
        if prev and prev[1] == first:
            src["overlaps_prev_page"] = True
    return raw_items, sources


def completeness(
    sources: list[dict[str, Any]],
    *,
    month_span: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """달별 전량 판정. 건수 합만 보지 않는다(W1 리뷰 M1).

    Returns:
        ``months``: [{"month", "total_count", "collected"}] (``total_count`` 가 쪽마다 다르면
        ``total_counts`` 도 싣는다), ``warnings``, ``missing_pages``: {달: [쪽]} (그 달이 일관될 때만),
        ``refetch``: 처음부터 다시 받을 달(``totalCount``·``numOfRows`` 가 쪽마다 다름·쪽 경계 겹침·
        건수 초과), ``absent``: 요청 기간 중 파일이 하나도 없는 달, ``complete``: 모두 비었는가.
    """
    per: dict[str, dict[str, Any]] = {}
    for s in sources:
        month = s["month"]
        if not month:
            continue  # 규칙 밖 이름의 빈 쪽 — 어느 달인지 알 수 없다(대조에서 제외)
        e = per.setdefault(month, {"totals": [], "rows": set(), "pages": set(), "filled": set(),
                                   "collected": 0, "overlap": False})
        e["totals"].append(int(s["total_count"]))
        if s.get("num_of_rows"):
            e["rows"].add(int(s["num_of_rows"]))
        e["pages"].add(int(s["page"]))
        if s["item_count"]:
            e["filled"].add(int(s["page"]))
        e["collected"] += int(s["item_count"])
        e["overlap"] = e["overlap"] or bool(s.get("overlaps_prev_page"))

    months: list[dict[str, Any]] = []
    warnings: list[str] = []
    missing: dict[str, list[int]] = {}
    refetch: list[str] = []
    for month in sorted(per):
        e = per[month]
        distinct = sorted(set(e["totals"]))
        total = distinct[-1]
        rows = min(e["rows"]) if e["rows"] else PAGE_ROWS
        pages = -(-total // rows)  # ceil
        row: dict[str, Any] = {"month": month, "total_count": total, "collected": e["collected"]}
        reasons = []
        if len(distinct) > 1:
            row["total_counts"] = distinct
            reasons.append(f"쪽마다 totalCount 가 다르다({'·'.join(map(str, distinct))}) — 받는 사이 거래가 늘었다")
        if len(e["rows"]) > 1:
            reasons.append(f"쪽마다 numOfRows 가 다르다({'·'.join(map(str, sorted(e['rows'])))}) — 쪽 경계가 맞지 않는다")
        if e["overlap"]:
            reasons.append("앞 쪽 마지막 행과 다음 쪽 첫 행이 같다 — 받는 사이 목록이 밀렸다")
        if e["collected"] > total:
            reasons.append(f"totalCount={total} 보다 수집={e['collected']} 이 많다")
        beyond = sorted(p for p in e["filled"] if p > pages)
        if beyond and e["collected"] <= total:
            reasons.append(f"totalCount={total} 이면 {pages}쪽까지인데 {beyond} 쪽에 행이 있다")
        if reasons:
            refetch.append(month)
            warnings.append(f"{month}: " + "; ".join(reasons) + " — 그 달을 1쪽부터 다시 받는다")
        else:
            gap = sorted(set(range(1, pages + 1)) - e["pages"])
            if gap:
                missing[month] = gap
            if e["collected"] < total:
                warnings.append(
                    f"{month}: totalCount={total} 인데 수집={e['collected']} — 페이지를 더 받아야 합니다"
                )
            elif gap:
                warnings.append(f"{month}: 건수는 맞는데 {gap} 쪽이 없다 — 빠진 쪽을 받는다")
        months.append(row)

    absent: list[str] = []
    if month_span:
        have = set(per)
        absent = [m for m in month_range(*month_span) if m not in have]
        warnings += [f"{m}: 파일이 없다 — 그 달 1쪽부터 받는다" for m in absent]

    return {
        "months": months,
        "warnings": warnings,
        "missing_pages": missing,
        "refetch": refetch,
        "absent": absent,
        "complete": not (warnings or missing or refetch or absent),
    }


def month_completeness(
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """월별 totalCount 와 수집 건수를 대조한다 (``completeness`` 요약 — 달 목록과 경고)."""
    rep = completeness(sources)
    return rep["months"], rep["warnings"]


def missing_pages(
    sources: list[dict[str, Any]],
    rows_per_page: int = PAGE_ROWS,
) -> dict[str, list[int]]:
    """달별로 아직 받지 않은 쪽 번호. 모두 받았으면 빈 dict.

    쪽 수는 본문 ``numOfRows``(없으면 ``rows_per_page``)로 ceil(totalCount/numOfRows) 다.
    ``refetch`` 달(쪽마다 totalCount 가 다른 달 등)은 여기 싣지 않는다 — ``completeness`` 를 본다.
    """
    return completeness(sources)["missing_pages"]


def missing_months(sources: list[dict[str, Any]], start_ymd: str, end_ymd: str) -> list[str]:
    """요청 기간(start~end) 가운데 응답 파일이 하나도 없는 달."""
    have = {s["month"] for s in sources if s["month"]}
    return [m for m in month_range(start_ymd, end_ymd) if m not in have]


# ---------------------------------------------------------------------------
# 호출 계획 — itda-hyve batch plan_file (W1 리뷰 M3, 공통 지시 파일럿 기본값 2)
# ---------------------------------------------------------------------------

_TAG = re.compile(r"^[A-Za-z0-9]{1,12}$")


def run_dir_name(prefix: str, lawd_cd: str, start_ymd: str, end_ymd: str, tag: str | None = None) -> str:
    """한 회차의 저장 폴더(save_dir 기준 상대 경로) ``<prefix>/<코드>-<시작월>-<종료월>[-<tag>]``."""
    if tag is not None and not _TAG.match(tag):
        raise ValueError(f"--tag 는 영숫자 1~12자다(한글·기호 없음) — 받은 값: {tag!r}")
    base = f"{prefix}/{lawd_cd}-{start_ymd}-{end_ymd}"
    return f"{base}-{tag}" if tag else base


def run_dir_of(paths: list[str], prefix: str) -> str:
    """입력 파일들이 든 회차 폴더를 save_dir 기준 상대 경로로 돌려준다(``<prefix>/<폴더>``).

    다음 계획의 ``save_as`` 를 같은 폴더에 두기 위해 쓴다. 파일이 한 폴더에 있지 않거나 그 폴더가
    ``<prefix>/…`` 가 아니면 ValueError — plan 이 만든 폴더의 파일만 이어 받을 수 있다.
    """
    parents = {Path(p).expanduser().resolve().parent for p in expand_inputs(paths)}
    if len(parents) != 1:
        raise ValueError("다음 계획은 한 회차 폴더의 파일로만 만든다 — 입력이 여러 폴더에 있다")
    parent = parents.pop()
    if parent.parent.name != prefix:
        raise ValueError(f"다음 계획은 plan 이 만든 {prefix}/<코드>-<시작월>-<종료월> 폴더의 파일로만 만든다 — 받은 폴더: {parent}")
    return f"{prefix}/{parent.name}"


def build_call(endpoint_type: str, lawd_cd: str, month: str, page: int, run_dir: str) -> dict[str, Any]:
    """한 쪽을 받는 호출 — batch ``calls`` 한 칸. 단독 호출은 ``args`` 에 ``save_dir``·``timeout_sec`` 을 더한다."""
    ep = ENDPOINT_MAP[endpoint_type]
    return {
        "id": f"{endpoint_type}-{month}-p{page}",
        "tool": "http_request",
        "args": {
            "url": ep["url"],
            "params": {
                "serviceKey": SECRET_KEY,
                "LAWD_CD": lawd_cd,
                "DEAL_YMD": month,
                "pageNo": str(page),
                "numOfRows": str(PAGE_ROWS),
            },
            "save_as": f"{run_dir}/{save_name(endpoint_type, lawd_cd, month, page)}",
        },
    }


def plan_calls(
    endpoint_types: list[str], lawd_cd: str, start_ymd: str, end_ymd: str, run_dir: str,
) -> list[dict[str, Any]]:
    """1차 계획 — 달마다·유형마다 1쪽. 2쪽 이후는 ``next_calls`` 가 totalCount 를 보고 정한다."""
    return [
        build_call(et, lawd_cd, month, 1, run_dir)
        for month in month_range(start_ymd, end_ymd)
        for et in endpoint_types
    ]


def next_calls(
    report: dict[str, Any], endpoint_type: str, lawd_cd: str, run_dir: str, *, refetch: bool = False,
) -> list[dict[str, Any]]:
    """``completeness`` 결과로 더 받을 호출. 빠진 달은 1쪽, 모자란 달은 빠진 쪽.

    ``refetch=True`` 면 다시 받을 달의 쪽 전부(ceil(최대 totalCount/100))를 싣는다 — 같은 이름을
    덮어쓰므로 계획 파일에 ``overwrite`` 가 들어가고, 사용자 확인 뒤에만 쓴다.
    """
    calls = [build_call(endpoint_type, lawd_cd, m, 1, run_dir) for m in report["absent"]]
    for month, pages in sorted(report["missing_pages"].items()):
        calls += [build_call(endpoint_type, lawd_cd, month, p, run_dir) for p in pages]
    if refetch:
        totals = {r["month"]: r["total_count"] for r in report["months"]}
        for month in report["refetch"]:
            pages = max(1, -(-totals[month] // PAGE_ROWS))
            calls += [build_call(endpoint_type, lawd_cd, month, p, run_dir) for p in range(1, pages + 1)]
    return calls


def write_plan_files(
    path: str, calls: list[dict[str, Any]], run_dir: str, *, overwrite: bool = False,
) -> dict[str, Any]:
    """batch ``plan_file`` 형식(``{calls, timeout_sec[, overwrite]}``)으로 쓴다. 40개 단위로 나눈다.

    ``path`` 는 회차 폴더(``run_dir``) 안이어야 한다 — ``plan_file`` 의 상대 경로가 ``save_dir``
    기준으로 풀리기 때문이다. 40개를 넘으면 ``plan-1a.json``·``plan-1b.json`` 처럼 나눈다.

    Returns:
        ``plan_files``(batch 에 넘길 save_dir 기준 경로)·``written``(쓴 파일 경로)·``call_count``.
    """
    out = Path(path).expanduser()
    if out.suffix != ".json":
        raise ValueError(f"계획 파일은 .json 이다 — 받은 값: {path}")
    want = run_dir.split("/")
    if list(out.resolve().parent.parts[-len(want):]) != want:
        raise ValueError(
            f"계획 파일은 회차 폴더 {run_dir}/ 안에 쓴다(plan_file 은 save_dir 기준 상대 경로다) — 받은 값: {path}"
        )
    chunks = [calls[i:i + BATCH_LIMIT] for i in range(0, len(calls), BATCH_LIMIT)] or [[]]
    if len(chunks) > 26:
        raise ValueError(f"호출이 {len(calls)}개다 — 기간·유형을 줄여 나눠 받는다(계획 파일 26개 상한)")
    out.parent.mkdir(parents=True, exist_ok=True)
    written, rel = [], []
    for i, chunk in enumerate(chunks):
        target = out if len(chunks) == 1 else out.with_name(f"{out.stem}{chr(ord('a') + i)}{out.suffix}")
        payload: dict[str, Any] = {"calls": chunk, "timeout_sec": BATCH_TIMEOUT_SEC}
        if overwrite:
            payload["overwrite"] = True
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written.append(str(target))
        rel.append(f"{run_dir}/{target.name}")
    return {"plan_files": rel, "written": written, "call_count": len(calls)}


def calls_preview(calls: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """stdout 에 실을 앞 몇 개 — 계획 파일을 썼으면 전부를 다시 찍지 않는다."""
    return calls[:limit]


# ---------------------------------------------------------------------------
# 정규화 (collect_realestate.py 41-88 snake_case 패턴 포팅)
# ---------------------------------------------------------------------------

# 유형별 단지명 필드 — 받은 파일이 --type/--prop-type 과 같은 엔드포인트인지 확인한다.
# 단독다가구·토지·상업업무용·공장창고는 단지명 필드가 없고, 분양입주권은 아파트와 같은 aptNm 이라 이름 대조에 맡긴다.
_NAME_FIELD = {"apt": "aptNm", "offi": "offiNm", "rh": "mhouseNm"}


def check_endpoint_fields(endpoint_type: str, items: list[dict[str, str]], flag: str = "--type") -> None:
    """항목이 ``endpoint_type`` 의 응답인지 단지명 필드로 확인한다. 아니면 ValueError(W1 리뷰 m4)."""
    prop = endpoint_type.split("_")[0]
    field = _NAME_FIELD.get(prop)
    if field and items and field not in items[0]:
        raise ValueError(
            f"{flag} {endpoint_type.split('_')[0] if flag == '--prop-type' else endpoint_type} 인데 응답에 {field} 가 없다"
            " — 받은 엔드포인트 유형과 맞춘다"
        )


def is_cancelled(item: dict[str, Any]) -> bool:
    """해제 거래인가 — 매매 응답 ``cdealType``(정규화 ``cdeal_type``)이 비어 있지 않으면 해제다(실측 ``O``)."""
    return bool((item.get("cdeal_type") or item.get("cdealType") or "").strip())


def _normalize_common_fields(item: dict[str, str]) -> dict[str, Any]:
    """매매·전월세 공통 필드를 snake_case로 정규화.

    아파트는 aptNm, 오피스텔은 offiNm, 연립은 mhouseNm 등 유형별 상이.
    소비자에게 통일된 apt_nm 키로 노출.
    """
    return {
        "apt_nm": (
            item.get("aptNm") or item.get("offiNm") or
            item.get("mhouseNm") or item.get("sggNm") or ""
        ).strip(),
        "exclu_use_ar": item.get("excluUseAr", "").strip(),
        "deal_year": item.get("dealYear", "").strip(),
        "deal_month": item.get("dealMonth", "").strip(),
        "deal_day": item.get("dealDay", "").strip(),
        "floor": item.get("floor", "").strip(),
        "build_year": item.get("buildYear", "").strip(),
        "umd_nm": item.get("umdNm", "").strip(),
        "jibun": item.get("jibun", "").strip(),
    }


def normalize_trade_item(item: dict[str, str]) -> dict[str, Any]:
    """매매 API 응답 항목을 snake_case로 정규화.

    Args:
        item: API 원본 항목.

    Returns:
        정규화된 딕셔너리 (deal_amount 필드 포함).
    """
    return {
        **_normalize_common_fields(item),
        "deal_amount": parse_amount(item.get("dealAmount", "0")),
        # 해제 거래 — 통계·조인은 기본으로 뺀다(W1 리뷰 M6). 원본 행 수집은 그대로 싣는다.
        "cdeal_type": (item.get("cdealType") or "").strip(),
        "cdeal_day": (item.get("cdealDay") or "").strip(),
    }


def normalize_rent_item(item: dict[str, str]) -> dict[str, Any]:
    """전월세 API 응답 항목을 snake_case로 정규화.

    Args:
        item: API 원본 항목.

    Returns:
        정규화된 딕셔너리 (deposit, monthly_rent 필드 포함).
    """
    return {
        **_normalize_common_fields(item),
        "deposit": parse_amount(item.get("deposit", "0")),
        "monthly_rent": parse_amount(item.get("monthlyRent", "0")),
    }


# ---------------------------------------------------------------------------
# 출력 포맷 (collect_realestate.py 117-137 envelope 패턴 포팅)
# ---------------------------------------------------------------------------

def build_envelope(
    status: str,
    region: str,
    items: list[dict[str, Any]],
    lawd_cd: str,
    *,
    summary: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """JSON envelope을 생성한다.

    envelope 스키마: status / region / count / results / [summary]
    (spec.md R13)

    Args:
        status: "ok" 또는 에러 상태.
        region: 한글 지역명.
        items: 수집된 거래 항목 리스트.
        lawd_cd: 법정동코드.
        summary: 요약 통계 (선택).
        **extra: 추가 키-값.

    Returns:
        JSON envelope 딕셔너리.
    """
    env: dict[str, Any] = {
        "status": status,
        "region": region,
        "lawd_cd": lawd_cd,
        "count": len(items),
        "results": items,
    }
    if summary is not None:
        env["summary"] = summary
    env.update(extra)
    return env


# ---------------------------------------------------------------------------
# CSV 변환
# ---------------------------------------------------------------------------

# CSV 출력 시 사용할 기본 컬럼 순서
_TRADE_CSV_FIELDS = [
    "apt_nm", "deal_amount", "deal_year", "deal_month", "deal_day",
    "exclu_use_ar", "floor", "build_year", "umd_nm", "jibun", "cdeal_type", "cdeal_day",
]

_RENT_CSV_FIELDS = [
    "apt_nm", "deposit", "monthly_rent", "deal_year", "deal_month", "deal_day",
    "exclu_use_ar", "floor", "build_year", "umd_nm", "jibun",
]


def items_to_csv(
    items: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> str:
    """items 리스트를 CSV 문자열로 변환한다.

    Args:
        items: 거래 항목 리스트.
        fields: CSV 컬럼 순서. None이면 첫 항목의 키 또는 기본 필드 사용.

    Returns:
        CSV 형식 문자열 (헤더 포함).
    """
    if fields is None:
        if items:
            fields = list(items[0].keys())
        else:
            fields = _TRADE_CSV_FIELDS

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(item)
    return output.getvalue()


# ---------------------------------------------------------------------------
# 결과 저장 (.json + .csv)
# ---------------------------------------------------------------------------

def save_results(
    envelope: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    base_path: str,
) -> tuple[str, str]:
    """JSON envelope과 CSV를 파일로 저장한다.

    Args:
        envelope: JSON envelope 딕셔너리.
        items: 거래 항목 리스트 (CSV 저장용).
        base_path: 파일 기반 경로 (확장자 없이). .json / .csv가 자동 부여된다.

    Returns:
        (json_path, csv_path) 튜플.
    """
    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)

    json_path = str(base) + ".json"
    csv_path = str(base) + ".csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    csv_str = items_to_csv(items)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_str)

    return json_path, csv_path
