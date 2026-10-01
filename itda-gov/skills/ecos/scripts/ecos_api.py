"""한국은행 ECOS OpenAPI 응답 파서 (파일 입력 전용).

네트워크는 itda-hyve 의 ``http_request`` 가 한다(itda-work/skills#45). 이 모듈은 그렇게 저장한
**응답 JSON 파일을 읽어** 오류 판정·전량 대조·정리만 한다 — 직접 API 를 부르지 않는다.

서비스(URL 경로 첫 세그먼트)와 응답 최상위 키가 같다:
    - KeyStatisticList (100대 통계지표)
    - StatisticSearch (통계 조회)
    - StatisticTableList (서비스 통계 목록)
    - StatisticItemList (통계 세부항목 목록)
    - StatisticWord (통계용어사전)

응답 형태 (2026-09-30 itda-hyve 실측):
    성공  {"<서비스>": {"list_total_count": N, "row": [...]}}
    오류  {"RESULT": {"CODE": "ERROR-101", "MESSAGE": "..."}}   ← HTTP 200 으로 온다
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hyve_input import HyveInputError, read_input

# 활용신청 페이지 — 인증키 관련 오류 시 사용자에게 자동 부착
_ECOS_APPLY_URL = "https://ecos.bok.or.kr/api/"

_ECOS_SETUP_GUIDE = (
    "\n[설정 안내] ECOS 인증키를 확인하세요:\n"
    f"  1. {_ECOS_APPLY_URL} 접속 → 회원가입 → 인증키 신청 (가입 시 즉시 발급)\n"
    "  2. itda-hyve GUI 시크릿 탭에 ECOS_API_KEY 로 등록 (앞뒤 공백 없이)\n"
    "  3. 발급 직후에는 수 분간 미반영일 수 있다 — 잠시 뒤 다시 조회\n"
)

# 정본 에러 코드 매핑 (출처: 한국은행 ECOS API개발명세서 6종 공통)
# references/ecos-매뉴얼/README.md 참조
# 키 형식: "{TYPE}-{CODE}" (TYPE = INFO | ERROR)
_ERROR_CODE_HINTS: dict[str, dict[str, Any]] = {
    "INFO-100": {"desc": "인증키가 유효하지 않습니다", "category": "setup", "needs_apply_url": True},
    "INFO-200": {"desc": "해당하는 데이터가 없습니다", "category": "data", "needs_apply_url": False},
    "ERROR-100": {"desc": "필수 값이 누락되어 있습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-101": {"desc": "주기와 다른 형식의 날짜 형식입니다", "category": "setup", "needs_apply_url": False},
    "ERROR-200": {"desc": "파일타입 값이 누락 혹은 유효하지 않습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-300": {"desc": "조회건수 값이 누락되어 있습니다", "category": "setup", "needs_apply_url": False},
    "ERROR-301": {"desc": "조회건수 값의 타입이 유효하지 않습니다 (정수 입력)", "category": "setup", "needs_apply_url": False},
    "ERROR-400": {"desc": "검색범위 초과 (60초 TIMEOUT)", "category": "transient", "needs_apply_url": False},
    "ERROR-500": {"desc": "서버 오류 (해당 서비스를 찾을 수 없음)", "category": "transient", "needs_apply_url": False},
    "ERROR-600": {"desc": "DB Connection 오류", "category": "transient", "needs_apply_url": False},
    "ERROR-601": {"desc": "SQL 오류", "category": "transient", "needs_apply_url": False},
    "ERROR-602": {"desc": "과도한 OpenAPI 호출로 이용 제한", "category": "transient", "needs_apply_url": False},
}

# 명령 → 서비스(응답 최상위 키)
SERVICES = {
    "key": "KeyStatisticList",
    "search": "StatisticSearch",
    "items": "StatisticItemList",
    "tables": "StatisticTableList",
    "word": "StatisticWord",
}

# 한 요청의 행 범위(시작~끝 건수). SKILL.md 의 쪽 이어받기 규칙과 같은 값이다.
PAGE_ROWS = 1000
# 남은 호출이 이보다 많으면(= list_total_count 5,000행 초과) 받기 전에 사용자에게 확인받는다(SKILL.md 호출 예산).
CONFIRM_CALLS = 5

# 저장 이름 규칙 — 끝의 ``-r<시작행>.json`` 이 그 파일의 행 범위 시작이다. 응답 본문에는 행 범위가 없다.
_START_RE = re.compile(r"-r(\d+)\.json$")


def _classify_ecos_error(error_code: str) -> tuple[str, str]:
    """ECOS API 오류 코드를 사용자 메시지와 카테고리로 분류.

    정본 매핑(_ERROR_CODE_HINTS)에서 한글 설명을 가져오고, 인증키 관련
    오류(INFO-100)는 활용신청 URL을 자동 부착한다.

    Returns:
        (사용자 메시지, 카테고리) 튜플.
        카테고리: "setup" | "transient" | "data" | "general"
    """
    hint = _ERROR_CODE_HINTS.get(error_code)
    if hint is None:
        return (
            f"ECOS API 오류 (코드: {error_code}) — 요청 URL 의 경로 세그먼트 또는 서버 상태를 확인하세요.",
            "general",
        )

    if error_code == "INFO-100":
        return (
            f"인증키 무효 ({error_code}, {hint['desc']}){_ECOS_SETUP_GUIDE}",
            "setup",
        )
    if error_code == "ERROR-602":
        return (
            f"{hint['desc']} ({error_code}) — 잠시 후 다시 받으세요(연달아 다시 부르지 않는다).",
            hint["category"],
        )
    if error_code == "ERROR-400":
        return (
            f"{hint['desc']} ({error_code}) — 검색 범위를 줄여서 다시 받으세요.",
            hint["category"],
        )
    if error_code == "ERROR-101":
        return (
            f"{hint['desc']} ({error_code}) — 주기/날짜 형식 확인 (A:2024, Q:2024Q1, M:202401, D:20240101)",
            hint["category"],
        )

    suffix = f" — 활용신청 URL: {_ECOS_APPLY_URL}" if hint["needs_apply_url"] else ""
    return (
        f"ECOS API 오류 ({error_code}, {hint['desc']}){suffix}",
        hint["category"],
    )


class ECOSAPIError(Exception):
    """저장된 응답이 성공 응답이 아니다 (본문의 RESULT.CODE)."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class InputFileError(Exception):
    """입력 파일을 가공할 수 없다 — 없음·절단·HTTP 오류·itda-hyve 실패·형식 불일치.

    ``kind`` 는 출력 JSON 의 ``error`` 값이다(``input``·``truncated``·``http``·``hyve``).
    """

    def __init__(self, message: str, kind: str = "input"):
        super().__init__(message)
        self.kind = kind


class IncompleteError(Exception):
    """받은 행이 list_total_count 에 모자라다 (전량 대조 실패). ``missing`` 은 더 받을 ``"시작~끝"`` 목록."""

    def __init__(self, message: str, missing: list[str]):
        super().__init__(message)
        self.missing = missing


def _read_body(path: Path) -> bytes:
    """입력 파일에서 응답 본문을 꺼낸다 — hyve 층 판독은 공용 ``hyve_input`` 이 한다.

    세 형태(본문 그대로·``http_request`` 응답 JSON 전체·실패 자리 ``{"error": …}``)를 받고, 절단·HTTP 오류·
    itda-hyve 실패·없는 파일을 :class:`InputFileError` 로 올린다(``kind`` = 출력 JSON 의 ``error``).
    """
    try:
        return read_input(path).data
    except HyveInputError as exc:
        raise InputFileError(str(exc), kind=exc.kind) from exc


def parse_response(path: str | Path, service: str) -> dict[str, Any]:
    """저장된 응답 파일 하나를 읽어 ``{"total": N, "rows": [...], "empty": bool}`` 로 돌려준다.

    Raises:
        InputFileError: 파일 없음·JSON 아님·절단·HTTP 오류·다른 서비스의 응답.
        ECOSAPIError: 본문의 RESULT.CODE 가 오류다(INFO-200 데이터 없음은 제외).
    """
    p = Path(path).expanduser()
    body = _read_body(p)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputFileError(
            f"JSON 이 아닙니다 — 본문이 잘렸거나 HTTP 오류 페이지일 수 있다({p.name}): {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise InputFileError(f"ECOS 응답 형태가 아닙니다: {p.name}")

    result = data.get("RESULT")
    if isinstance(result, dict):
        code = str(result.get("CODE", ""))
        msg = result.get("MESSAGE", "알 수 없는 오류")
        if code == "INFO-200":
            return {"total": 0, "rows": [], "empty": True, "message": msg}
        hint_msg, _category = _classify_ecos_error(code)
        raise ECOSAPIError(f"{hint_msg} | 원본 메시지: {msg} ({p.name})", error_code=code)

    block = data.get(service)
    if not isinstance(block, dict):
        found = ", ".join(sorted(data)) or "(빈 객체)"
        raise InputFileError(f"{service} 응답이 아닙니다({found}): {p.name}")
    rows = block.get("row") or []
    try:
        total: int | None = int(block["list_total_count"])
    except (KeyError, TypeError, ValueError):
        total = None  # 기준선 없음 — collect_rows 가 경고로 남긴다
    return {"total": total, "rows": rows, "empty": False}


def _chunks(first: int, last: int) -> list[str]:
    """``first``~``last`` 를 ``PAGE_ROWS`` 씩 끊어 ``"시작~끝"`` 목록으로."""
    out = []
    start = first
    while start <= last:
        end = min(start + PAGE_ROWS - 1, last)
        out.append(f"{start}~{end}")
        start = end + 1
    return out


def missing_ranges(received: int, total: int) -> list[str]:
    """1행부터 ``received`` 행을 이어 받았을 때 남은 범위(``PAGE_ROWS`` 씩)."""
    return _chunks(received + 1, total)


def start_row(path: str | Path) -> int:
    """저장 이름 끝의 ``-r<시작행>.json`` 을 읽는다. 없으면 :class:`InputFileError`."""
    name = Path(path).name
    m = _START_RE.search(name)
    if not m or int(m.group(1)) < 1:
        raise InputFileError(
            f"파일 이름이 규칙(…-r<시작행>.json)과 다릅니다: {name} — 응답 본문에는 행 범위가 없어 이름으로 안다. "
            "SKILL.md 의 저장 이름을 그대로 쓰세요(예: ecos/items-901Y009-r1.json · …-r1001.json)"
        )
    return int(m.group(1))


def _row_key(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def collect_rows(paths: list[str], service: str) -> dict[str, Any]:
    """여러 쪽 파일의 행을 모으고 ``list_total_count`` 와 전량 대조한다.

    합치기 전에 네 가지를 본다 — 행 수 합만 맞으면 같은 쪽 두 번·다른 질의 혼입이 ``ok`` 로 지나간다(W4 리뷰 M2).

    1. **질의가 같은가** — 모든 파일의 ``list_total_count`` 가 같아야 한다. 다르면 다른 질의(통계표·기간·항목)의
       응답이 섞였다는 ``input`` 오류다. ECOS 통계는 공표 주기(일·월·분기) 단위로 갱신돼 쪽을 받는 몇 초~몇 분 사이에
       건수가 바뀌는 일이 드물고, 바뀌었더라도 쪽 경계가 어긋나 어차피 처음부터 다시 받아야 한다 — 그래서 경고로
       두지 않고 오류로 둔다(나라장터 g2b 는 받는 사이 공고가 계속 늘어 경고 + 최댓값이다).
    2. **행 범위가 겹치지 않는가** — 파일 이름의 ``-r<시작행>`` 과 받은 행 수로 범위를 세운다. 같은 시작행이 두 번
       (다른 폴더 사본)이거나 범위가 겹치면 ``input`` 오류다.
    3. **행이 겹치지 않는가** — 행 전체가 같은 행이 둘 이상이면 ``input`` 오류다(ECOS 행은 TIME·ITEM_CODE 로 유일).
    4. **1행부터 빈틈없이 이어지는가** — 빈 범위·꼬리를 정확히 계산해 :class:`IncompleteError` 로 알린다.

    ``list_total_count`` 가 없는 응답은 받은 행 수를 분모로 쓰되 ``warnings`` 에 기준선이 없다고 남긴다.

    Returns:
        ``{"rows": [...], "total_count": N, "sources": [{path, start_row, total_count, rows}], "warnings": [...]}``
    """
    parsed_files = []
    for p in paths:
        parsed = parse_response(p, service)
        parsed_files.append((str(Path(p).expanduser()), start_row(p), parsed))

    warnings: list[str] = []
    sources = [{"path": path, "start_row": start, "total_count": pr["total"], "rows": len(pr["rows"])}
               for path, start, pr in parsed_files]

    # INFO-200(데이터 없음)은 행이 없는 성공이다 — 다른 쪽과 섞이지 않았을 때만.
    if all(pr["empty"] for _, _, pr in parsed_files):
        return {"rows": [], "total_count": 0, "sources": sources, "warnings": warnings}

    # 1. 질의 동일성 — 모든 파일의 list_total_count 가 같아야 한다.
    totals = {pr["total"] for _, _, pr in parsed_files if not pr["empty"]}
    empties = [Path(path).name for path, _, pr in parsed_files if pr["empty"]]
    if empties:
        raise InputFileError(
            f"데이터 없음(INFO-200) 응답과 행이 있는 응답이 섞였습니다({', '.join(empties)}) — "
            "다른 질의의 파일이 들어왔는지 확인하세요"
        )
    known = {t for t in totals if t is not None}
    if len(known) > 1:
        detail = ", ".join(f"{Path(s['path']).name}={s['total_count']}" for s in sources)
        raise InputFileError(
            f"파일마다 list_total_count 가 다릅니다({detail}) — 다른 질의(통계표·주기·기간·항목)의 응답이 섞였다. "
            "한 명령에는 같은 URL 의 쪽들만 넘기세요"
        )
    if None in totals:
        no_total = [Path(s["path"]).name for s in sources if s["total_count"] is None]
        warnings.append(
            f"list_total_count 가 없는 응답이 있습니다({', '.join(no_total)}) — 전량 기준선이 없어 받은 행 수로만 셉니다"
        )

    # 2. 행 범위 — 시작행 순으로 겹침·빈틈을 본다.
    spans = sorted(((start, path, pr) for path, start, pr in parsed_files), key=lambda t: t[0])
    starts = [start for start, _, _ in spans]
    dup_starts = sorted({s for s in starts if starts.count(s) > 1})
    if dup_starts:
        names = [Path(path).name for start, path, _ in spans if start in dup_starts]
        raise InputFileError(
            f"같은 행 범위(시작행 {dup_starts})가 두 번 들어왔습니다({', '.join(names)}) — 다른 폴더에 다시 받은 사본이면 하나만 넘기세요"
        )
    gaps: list[tuple[int, int]] = []
    cursor = 1
    for start, path, pr in spans:
        if start < cursor:
            raise InputFileError(
                f"행 범위가 겹칩니다 — {Path(path).name} 은 {start}행부터인데 앞 파일이 {cursor - 1}행까지 받았다. "
                "같은 URL 의 <시작행>/<끝행> 을 1000행씩 겹치지 않게 받으세요"
            )
        if start > cursor:
            gaps.append((cursor, start - 1))
        cursor = start + len(pr["rows"])

    # 3. 행 중복.
    rows: list[dict[str, Any]] = []
    for _, _, pr in spans:
        rows.extend(pr["rows"])
    keys = [_row_key(r) for r in rows]
    dup_rows = len(keys) - len(set(keys))
    if dup_rows:
        raise InputFileError(
            f"같은 행이 {dup_rows}개 겹칩니다 — 같은 범위를 두 번 받았거나 받는 사이 자료가 바뀌었다. 1행부터 다시 받으세요"
        )

    total = known.pop() if known else len(rows)
    if cursor - 1 > total:
        raise InputFileError(
            f"list_total_count={total} 인데 {cursor - 1}행까지 받았습니다 — 다른 질의의 파일이 섞였는지 확인하세요"
        )
    if cursor - 1 < total:
        gaps.append((cursor, total))

    # 4. 빈틈 — 정확한 범위를 알린다.
    if gaps:
        missing = [r for a, b in gaps for r in _chunks(a, b)]
        more = len(missing)
        ask = (f" 남은 호출이 {more}회로 {CONFIRM_CALLS}회를 넘는다 — 받기 전에 사용자에게 호출 수를 알리고 "
               "기간·항목코드를 좁힐지 확인받으세요." if more > CONFIRM_CALLS else "")
        raise IncompleteError(
            f"list_total_count={total} 인데 받은 행={len(rows)} — 다음 행 범위를 더 받아 "
            f"지금 파일과 함께 넘기세요: {', '.join(missing)}.{ask}",
            missing,
        )
    return {"rows": rows, "total_count": total, "sources": sources, "warnings": warnings}


def infer_period(rows: list[dict[str, Any]]) -> str:
    """TIME 형식으로 주기를 추정한다 (A:2024 · Q:2024Q1 · M:202401 · D:20240101)."""
    t = str(rows[0].get("TIME", "")) if rows else ""
    if "Q" in t:
        return "quarter"
    if "S" in t:
        return "semi"
    return {4: "year", 6: "month", 8: "day"}.get(len(t), "")


def parse_value(val_str: str) -> float | None:
    """DATA_VALUE 문자열을 숫자로 변환. 숫자가 아니면 None."""
    if not val_str or val_str.strip() in ("-", "", "…", "x", "X", "*"):
        return None
    try:
        return float(val_str.replace(",", ""))
    except ValueError:
        return None


def summarize_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """StatisticSearch 행을 제안서용 요약 형태로 정리.

    Returns:
        [{time, stat_code, stat_name, item_name, item_name2, value, unit}, ...]
    """
    results: list[dict[str, Any]] = []

    for row in rows:
        value = parse_value(row.get("DATA_VALUE", "") or "")
        if value is None:
            continue

        results.append({
            "time": row.get("TIME", ""),
            "stat_code": row.get("STAT_CODE", ""),
            "stat_name": row.get("STAT_NAME", ""),
            "item_name": row.get("ITEM_NAME1", ""),
            "item_name2": row.get("ITEM_NAME2", ""),
            "value": value,
            "unit": row.get("UNIT_NAME", ""),
        })

    return results
