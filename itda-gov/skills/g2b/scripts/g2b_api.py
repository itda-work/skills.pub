"""나라장터 공공데이터개방표준서비스 API 클라이언트.

공공데이터포털(https://www.data.go.kr) G2B 입찰공고 조회 API 래퍼.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

# API 엔드포인트
_API_ENDPOINT = (
    "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService"
    "/getDataSetOpnStdBidPblancInfo"
)

# 요청 타임아웃(초)
_REQUEST_TIMEOUT = 15


class G2BAPIError(Exception):
    """나라장터 API 호출 중 발생하는 오류."""


def format_date(date_str: str) -> str:
    """YYYY-MM-DD 형식 날짜를 YYYYMMDD로 변환.

    API에 전달하기 전 날짜 형식을 변환. begin_dt에는 0000, end_dt에는 2359를
    호출자가 직접 붙여서 사용.

    Args:
        date_str: YYYY-MM-DD 형식의 날짜 문자열.

    Returns:
        YYYYMMDD 형식의 날짜 문자열.

    Raises:
        ValueError: 날짜 형식이 올바르지 않거나 존재하지 않는 날짜인 경우.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"날짜 형식이 올바르지 않습니다: '{date_str}'. YYYY-MM-DD 형식으로 입력하세요."
        ) from exc
    return dt.strftime("%Y%m%d")


def validate_date_range(begin_dt: str, end_dt: str) -> None:
    """날짜 범위가 1개월을 초과하지 않는지 검증.

    Args:
        begin_dt: 시작일 (YYYYMMDD 형식).
        end_dt: 종료일 (YYYYMMDD 형식).

    Raises:
        G2BAPIError: 날짜 범위가 1개월을 초과하는 경우.
    """
    begin = datetime.strptime(begin_dt, "%Y%m%d")
    end = datetime.strptime(end_dt, "%Y%m%d")

    # 1개월 이내 여부 확인 (31일 기준으로 판단)
    delta = end - begin
    if delta.days > 31:
        raise G2BAPIError(
            f"날짜 범위가 1개월을 초과합니다 ({delta.days}일). "
            "최대 1개월 이내로 지정하세요."
        )


def build_url(api_key: str, params: dict) -> str:
    """API 요청 URL을 구성.

    serviceKey는 별도로 인코딩하여 이중 인코딩을 방지.
    다른 파라미터는 urllib.parse.urlencode로 인코딩.

    Args:
        api_key: 공공데이터포털 serviceKey (URL 디코딩 상태).
        params: serviceKey를 제외한 나머지 파라미터 딕셔너리.

    Returns:
        완성된 API 요청 URL 문자열.
    """
    # serviceKey는 별도로 인코딩 (safe='' 으로 모든 특수문자 인코딩)
    encoded_key = urllib.parse.quote(api_key, safe="")

    # 나머지 파라미터 인코딩
    other_params = urllib.parse.urlencode(params)

    if other_params:
        return f"{_API_ENDPOINT}?serviceKey={encoded_key}&{other_params}"
    return f"{_API_ENDPOINT}?serviceKey={encoded_key}"


# @MX:ANCHOR: [AUTO] G2B 입찰공고 조회의 핵심 API 호출 함수.
# @MX:REASON: fan_in >= 3 (collect_g2b 및 향후 확장); API 계약의 진입점.
def search_bids(
    api_key: str,
    begin_dt: str,
    end_dt: str,
    page: int = 1,
    rows: int = 10,
) -> dict:
    """나라장터 입찰공고를 조회.

    Args:
        api_key: 공공데이터포털 serviceKey.
        begin_dt: 조회 시작일 (YYYY-MM-DD 형식).
        end_dt: 조회 종료일 (YYYY-MM-DD 형식).
        page: 페이지 번호 (기본값 1).
        rows: 페이지당 결과 수 (기본값 10).

    Returns:
        다음 키를 포함하는 딕셔너리:
        - items: 입찰공고 목록
        - totalCount: 전체 결과 수
        - pageNo: 현재 페이지 번호
        - numOfRows: 페이지당 결과 수

    Raises:
        G2BAPIError: 날짜 범위 초과, 네트워크 오류, API 오류, JSON 파싱 실패 등.
        ValueError: 날짜 형식이 올바르지 않은 경우.
    """
    # rows 상한 적용 (API가 1000 이상이면 기본값 10으로 리셋)
    rows = max(1, min(999, rows))

    # 날짜 형식 변환 (YYYY-MM-DD → YYYYMMDD)
    begin_yyyymmdd = format_date(begin_dt)
    end_yyyymmdd = format_date(end_dt)

    # 날짜 범위 검증 (1개월 이내)
    validate_date_range(begin_yyyymmdd, end_yyyymmdd)

    # API 파라미터 구성 (시간 붙이기: begin=0000, end=2359)
    params = {
        "type": "json",
        "pageNo": str(page),
        "numOfRows": str(rows),
        "bidNtceBgnDt": begin_yyyymmdd + "0000",
        "bidNtceEndDt": end_yyyymmdd + "2359",
    }

    url = build_url(api_key, params)

    try:
        with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.URLError as exc:
        raise G2BAPIError(f"네트워크 오류: {exc}") from exc

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise G2BAPIError(f"JSON 파싱 실패: {exc}") from exc

    # 응답 구조 검증
    try:
        header = data["response"]["header"]
        body = data["response"]["body"]
    except (KeyError, TypeError) as exc:
        raise G2BAPIError(f"예상치 못한 응답 구조: {exc}") from exc

    result_code = header.get("resultCode", "")
    if result_code != "00":
        result_msg = header.get("resultMsg", "")
        raise G2BAPIError(
            f"API 오류 (resultCode={result_code}): {result_msg}"
        )

    items = body.get("items") or []
    return {
        "items": items,
        "totalCount": body.get("totalCount", 0),
        "pageNo": body.get("pageNo", page),
        "numOfRows": body.get("numOfRows", rows),
    }


# 페이지네이션 기본값
# 1페이지당 최대 행 수(API 상한 999). 페이지 호출 횟수를 줄이기 위해 큰 값을 쓴다.
_PAGE_SIZE = 999
# 무한루프/과도호출 방지 상한. 999 * 20 = 최대 약 2만 건까지 순회.
_MAX_PAGES = 20


def _item_key(item: dict) -> tuple:
    """페이지 경계 중복 제거용 안정 키.

    같은 데이터셋에서 한 입찰공고(bidNtceNo)가 차수(bidNtceOrd)별로 여러 행을
    가질 수 있고, 페이지 간 중복이 관측된다. (공고번호, 차수, 참조공고번호,
    참조차수) 조합으로 행을 식별한다. 식별 필드가 모두 비면 항목 전체를
    정렬된 튜플로 폴백한다.
    """
    parts = (
        str(item.get("bidNtceNo", "")),
        str(item.get("bidNtceOrd", "")),
        str(item.get("refNtceNo", "")),
        str(item.get("refNtceOrd", "")),
    )
    if any(parts):
        return parts
    return tuple(sorted((str(k), str(v)) for k, v in item.items()))


# @MX:ANCHOR: [AUTO] 거짓 0건 방지 — 날짜범위 전 페이지 순회 수집.
# @MX:REASON: 키워드 검색이 첫 페이지 밖 공고를 놓치는 silent under-collect 결함 수정 진입점.
def collect_all_bids(
    api_key: str,
    begin_dt: str,
    end_dt: str,
    page_size: int | None = None,
    max_pages: int | None = None,
) -> dict:
    """날짜 범위 내 입찰공고를 모든 페이지에 걸쳐 누적 수집.

    totalCount를 읽어 필요한 페이지를 순회하며 항목을 누적한다.
    페이지 경계에서 발생하는 중복(같은 bidNtceNo/bidNtceOrd 재출현)은
    안정 키로 제거한다. max_pages 상한에 도달하면 미조회분이 남아도
    중단하고 truncated=True로 표시한다.

    클라이언트 측 키워드 필터링은 호출자가 누적된 items에 대해 수행한다.
    이렇게 해야 키워드가 첫 페이지 밖(예: 11번째, 500번째)에 있어도
    수집되어 거짓 0건(false 0)을 방지한다.

    Args:
        api_key: 공공데이터포털 serviceKey.
        begin_dt: 조회 시작일 (YYYY-MM-DD 형식).
        end_dt: 조회 종료일 (YYYY-MM-DD 형식).
        page_size: 페이지당 결과 수 (기본 999, 호출 횟수 최소화).
        max_pages: 순회 상한 페이지 수 (기본 20, 무한루프/과호출 방지).

    Returns:
        다음 키를 포함하는 딕셔너리:
        - items: 중복 제거된 누적 입찰공고 목록.
        - totalCount: API가 보고한 필터 전 전체 결과 수.
        - pages_fetched: 실제 호출한 페이지 수.
        - truncated: max_pages 상한 때문에 미조회분이 남았으면 True.
        - scanned_count: 누적·중복제거 후 실제 스캔한 항목 수.

    Raises:
        G2BAPIError: 날짜 범위 초과, 네트워크 오류, API 오류 등.
        ValueError: 날짜 형식이 올바르지 않은 경우.
    """
    # 모듈 기본값을 호출 시점에 해석(테스트에서 _PAGE_SIZE 패치 가능).
    if page_size is None:
        page_size = _PAGE_SIZE
    if max_pages is None:
        max_pages = _MAX_PAGES
    page_size = max(1, min(999, page_size))
    max_pages = max(1, max_pages)

    accumulated: list[dict] = []
    seen: set[tuple] = set()
    total_count = 0
    pages_fetched = 0
    truncated = False

    page = 1
    while page <= max_pages:
        result = search_bids(
            api_key=api_key,
            begin_dt=begin_dt,
            end_dt=end_dt,
            page=page,
            rows=page_size,
        )
        pages_fetched += 1

        # totalCount는 첫 페이지(실제로는 모든 페이지) 응답에서 동일하게 보고됨.
        try:
            total_count = int(result.get("totalCount", 0) or 0)
        except (TypeError, ValueError):
            total_count = 0

        page_items = result.get("items") or []
        new_in_page = 0
        for item in page_items:
            key = _item_key(item)
            if key in seen:
                continue
            seen.add(key)
            accumulated.append(item)
            new_in_page += 1

        # 종료 조건:
        # 1) 이번 페이지가 비었으면(더 이상 데이터 없음) 중단.
        if not page_items:
            break
        # 2) totalCount를 모두 소진했으면 중단.
        #    (중복 때문에 누적 < totalCount 일 수 있으므로 page*page_size 기준으로 판단)
        if total_count and page * page_size >= total_count:
            break
        # 3) 페이지가 page_size 미만이면 마지막 페이지로 간주.
        if len(page_items) < page_size:
            break

        page += 1
    else:
        # while 루프가 break 없이 max_pages를 소진한 경우(else 절).
        # 아직 미조회분이 남았는지 확인.
        if total_count and pages_fetched * page_size < total_count:
            truncated = True

    return {
        "items": accumulated,
        "totalCount": total_count,
        "pages_fetched": pages_fetched,
        "truncated": truncated,
        "scanned_count": len(accumulated),
    }
