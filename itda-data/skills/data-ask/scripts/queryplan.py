"""QueryPlan 계약 + 결정론 SQL 생성 (SPEC-DATA-VERTICAL-001 REQ-001·002·003).

Codex 1순위: LLM이 SQL을 직접 쓰지 않는다. typed QueryPlan 을 만들면 여기서
**결정론적·파라미터화 SQL**을 생성한다. 컬럼은 스키마 실재 검증, aggregation·op는
화이트리스트, 리터럴은 ? 바인딩(인젝션 차단). group-by 는 count(*) AS n 자동 주입(소셀 강제).

엔진 교체(2026-06-25, #567): 데이터는 duckdb `read_csv` 가 로드한다 → 통화/쉼표 금액은
VARCHAR 로 남는다(앞자리 0 코드 보존을 위해 자동 정수화하지 않으므로). 따라서 measure·
숫자필터는 SQL 정규화식(`_num_expr`)으로 감싼다 — 금액 정규화의 **정본**이 여기다.
"""
from __future__ import annotations
from dataclasses import dataclass, field

_AGG = {"count", "sum", "avg", "min", "max", "ratio"}
_OPS = {"=", "!=", ">", ">=", "<", "<="}
_GRAIN = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}

# duckdb 숫자 storage 타입(DESCRIBE 표기). DECIMAL(p,s)·UBIGINT 등 prefix 매칭.
_NUMERIC_TYPES = {
    "BIGINT", "INTEGER", "SMALLINT", "TINYINT", "HUGEINT",
    "UBIGINT", "UINTEGER", "USMALLINT", "UTINYINT", "UHUGEINT",
    "DOUBLE", "FLOAT", "REAL", "DECIMAL",
}


@dataclass
class QueryPlan:
    aggregation: str                       # count|sum|avg|min|max|ratio
    measure: str | None = None             # sum/avg/min/max 대상 컬럼
    dimensions: list = field(default_factory=list)   # group-by 컬럼
    filters: list = field(default_factory=list)      # [{"column","op","value"}]
    ratio_condition: dict | None = None    # ratio: {"column","op","value"} → 조건 충족 비율
    time_grain: str | None = None          # day|month|year (dimensions[0] 에 적용)
    null_policy: str = "exclude"
    requires_n: bool = True                # 소셀 강제: group-by 에 count(*) n 주입
    order_desc: bool = True
    limit: int = 100


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def is_numeric_type(duck_type: str) -> bool:
    """duckdb DESCRIBE 타입이 숫자형인지. 'DECIMAL(18,3)' 등 prefix 매칭."""
    return str(duck_type).split("(")[0].strip().upper() in _NUMERIC_TYPES


# 금액에서 measure 를 인식하는 통화/형식 마커(회계괄호·통화기호·쉼표·퍼센트).
# safe_exec 의 numeric_like 전수 판정과 공유한다.
MARKER_REGEX = r"[,₩%()$¥€£]|원"


def norm_sql(qcol: str) -> str:
    """이미 _q() 처리된 컬럼식 → 금액 정규화 후 DOUBLE 캐스트(TRY_CAST).

    회계괄호 음수 `(500)`→-500, 통화기호·쉼표·원·% 제거. 숫자 아니면 NULL.
    전각숫자·후행마이너스·한글 수단위(억/만)는 미지원(backlog) — clean_number 참조.
    """
    paren = f"regexp_replace({qcol}, '^\\(([0-9,.]+)\\)$', '-\\1')"
    stripped = f"regexp_replace({paren}, '[,₩%\\s원$¥€£]', '', 'g')"
    return f"TRY_CAST({stripped} AS DOUBLE)"


def _num_expr(name: str, type_map: dict) -> str:
    """숫자 집계용 컬럼식. 숫자 storage 면 그대로, VARCHAR(통화/쉼표)면 정규화."""
    if is_numeric_type(type_map.get(name, "VARCHAR")):
        return _q(name)
    return norm_sql(_q(name))


def _cmp_expr(name: str, value, type_map: dict) -> str:
    """비교(filter·ratio) 좌변. value 가 숫자면 숫자 비교(정규화), 문자열이면 원본 컬럼.

    bool 은 숫자 취급하지 않는다(Y/N·True/False 문자열 매칭 보존)."""
    if isinstance(value, bool):
        return _q(name)
    if isinstance(value, (int, float)):
        return _num_expr(name, type_map)
    return _q(name)


def plan_to_sql(plan: QueryPlan, schema: list[dict]) -> tuple[str, list]:
    """검증된 QueryPlan → (inner_sql, params). 위반 시 ValueError(한국어)."""
    names = {c["name"] for c in schema}
    type_map = {c["name"]: c.get("type", "VARCHAR") for c in schema}

    def need(col, what):
        if col not in names:
            raise ValueError(f"{what} 컬럼이 데이터에 없습니다: {col}")

    if plan.aggregation not in _AGG:
        raise ValueError(f"허용되지 않은 집계: {plan.aggregation}")
    if plan.time_grain and plan.time_grain not in _GRAIN:
        raise ValueError(f"허용되지 않은 시간 단위: {plan.time_grain}")
    for d in plan.dimensions:
        need(d, "차원")
    for f in plan.filters:
        need(f.get("column"), "필터")
        if f.get("op") not in _OPS:
            raise ValueError(f"허용되지 않은 필터 연산자: {f.get('op')}")

    params: list = []
    select: list[str] = []

    grain_dim = plan.dimensions[0] if (plan.time_grain and plan.dimensions) else None
    for d in plan.dimensions:
        if d == grain_dim:
            select.append(f"strftime(CAST({_q(d)} AS DATE), '{_GRAIN[plan.time_grain]}') AS {_q(d)}")
        else:
            select.append(_q(d))

    value_label = None
    if plan.aggregation == "count":
        pass  # n 이 값 역할
    elif plan.aggregation == "ratio":
        rc = plan.ratio_condition
        if not rc:
            raise ValueError("ratio 집계에는 ratio_condition 이 필요합니다")
        need(rc.get("column"), "비율 조건")
        if rc.get("op") not in _OPS:
            raise ValueError(f"허용되지 않은 비율 조건 연산자: {rc.get('op')}")
        cmp = _cmp_expr(rc["column"], rc.get("value"), type_map)
        select.append(f'round(avg(case when {cmp} {rc["op"]} ? then 1.0 else 0 end), 4) AS "비율"')
        params.append(rc["value"])
        value_label = "비율"
    else:  # sum/avg/min/max
        if not plan.measure:
            raise ValueError(f"{plan.aggregation} 집계에는 measure 가 필요합니다")
        need(plan.measure, "측정")
        select.append(f'{plan.aggregation}({_num_expr(plan.measure, type_map)}) AS "값"')
        value_label = "값"

    include_n = plan.requires_n or plan.aggregation == "count" or bool(plan.dimensions)
    if include_n:
        select.append("count(*) AS n")

    where: list[str] = []
    for f in plan.filters:
        where.append(f"{_cmp_expr(f['column'], f.get('value'), type_map)} {f['op']} ?")
        params.append(f["value"])
    if plan.null_policy == "exclude" and plan.measure and plan.aggregation in ("sum", "avg", "min", "max"):
        where.append(f"{_num_expr(plan.measure, type_map)} IS NOT NULL")

    sql = "SELECT " + ", ".join(select) + " FROM t"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if plan.dimensions:
        sql += " GROUP BY ALL"
        order_col = value_label or ("n" if include_n else None)
        if order_col:
            sql += f' ORDER BY {_q(order_col)} ' + ("DESC" if plan.order_desc else "ASC")
    return sql, params
