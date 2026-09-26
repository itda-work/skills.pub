"""안전 실행기 (SPEC-DATA-VERTICAL-001 REQ-020). 2단계 read_csv 봉인.

엔진(2026-06-25, #567): "신뢰 단계(우리 SQL)로 read_csv 로딩 → 봉인 → 에이전트 SQL".
  1) duckdb.connect() (기본, 외부접근 ON) — 신뢰 단계.
  2) (cp949 면) LOAD encodings.
  3) CREATE TABLE t AS SELECT * FROM read_csv('<원본>', encoding=<enc>)  ← 우리 SQL=신뢰.
     duckdb 네이티브 스니퍼가 타입·구분자·앞자리 0(`06234`→VARCHAR 보존)·날짜를 감지.
  4) SET enable_external_access=false; SET lock_configuration=true  ← 봉인.
  5) 검증된 plan SQL / 가드된 raw SQL 실행 — 이후 원격·로컬파일·잠금해제·COPY 전부 차단.

보안 경계(코드 강제): 봉인 후 enable_external_access=false → read_csv·httpfs·COPY·INSTALL
차단, lock_configuration=true → SET 재변경 차단. plan 생성 SQL 과 raw fallback 모두 봉인 뒤 실행.
"""
from __future__ import annotations
import re

import duckdb

import loader
import queryplan as qp

_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
# loader 의 nullish 집합과 동기화한 SQL 리터럴(전수 numeric 판정용).
_NULLISH_SQL = "(" + ", ".join("'" + s + "'" for s in sorted(loader._NULLISH)) + ")"


def _connect_load(path: str, enc: str, needs_encodings: bool):
    """2단계의 1~4단계: read_csv 로딩 후 봉인된 연결 반환."""
    con = duckdb.connect()
    # 첫 INSTALL 의 다운로드 진행 막대가 stdout 에 찍혀 JSON 출력을 깨뜨린다(깨끗한 홈 실측) — 끈다.
    con.execute("SET enable_progress_bar=false")
    if needs_encodings:
        # encodings 확장은 봉인(enable_external_access=false) 전에 1회 확보한다.
        # 미설치 환경(예: 깨끗한 CI runner)에서는 온라인 INSTALL 로 내려받고,
        # 오프라인이라도 이미 설치돼 있으면 LOAD 가 성공한다 — INSTALL 실패는
        # 무시하고 LOAD 결과로 최종 판정(SKILL "최초 1회 온라인 INSTALL" 자동화).
        try:
            con.execute("INSTALL encodings")
        except duckdb.Error:
            pass
        con.execute("LOAD encodings")
    safe = path.replace("'", "''")  # 경로 작은따옴표 escape
    con.execute(f"CREATE TABLE t AS SELECT * FROM read_csv('{safe}', encoding='{enc}', header=true)")
    con.execute("SET enable_external_access=false")
    con.execute("SET lock_configuration=true")
    return con


def _varchar_numeric(con, name: str) -> bool:
    """VARCHAR 컬럼이 정규화 가능한 통화/형식 금액인지 **전수** 판정.

    비-nullish 값이 모두 숫자로 정규화되고(num_ok>=nonnull) 통화/형식 마커가
    하나라도 있으면(marker>0) measure 후보. 순수 숫자코드(`06234` 등 앞자리 0)는
    마커가 없어 제외 → 코드값을 measure 로 오인하지 않는다.
    """
    q = qp._q(name)
    norm = qp.norm_sql(q)
    sql = (
        f"SELECT "
        f"count(*) FILTER (WHERE {q} IS NOT NULL AND lower(trim({q})) NOT IN {_NULLISH_SQL}), "
        f"count(*) FILTER (WHERE {norm} IS NOT NULL), "
        f"count(*) FILTER (WHERE {q} IS NOT NULL AND regexp_matches({q}, '{qp.MARKER_REGEX}')) "
        f"FROM t"
    )
    nonnull, num_ok, marker = con.execute(sql).fetchone()
    return nonnull > 0 and num_ok >= nonnull and marker > 0


def _describe(con) -> tuple[list[dict], list[dict]]:
    """봉인된 t 의 스키마([{name,type,samples,numeric}]) + 샘플행(profiler/structure 입력)."""
    desc = con.execute("DESCRIBE t").fetchall()  # (name, type, null, key, default, extra)
    cur = con.execute("SELECT * FROM t LIMIT 50")
    names = [d[0] for d in cur.description]
    sample_rows = [dict(zip(names, r)) for r in cur.fetchall()]
    schema: list[dict] = []
    for row in desc:
        name, typ = row[0], row[1]
        samples = [r[name] for r in sample_rows if not loader.is_nullish(r.get(name))][:3]
        numeric = qp.is_numeric_type(typ) or (typ == "VARCHAR" and _varchar_numeric(con, name))
        schema.append({"name": name, "type": typ, "samples": samples, "numeric": numeric})
    return schema, sample_rows


def _require_clean_columns(path: str, enc: str) -> None:
    """원본 헤더(duckdb rename 전)의 빈·None·중복 열을 막고 data-prep 로 라우팅(F2·F3)."""
    issues = loader.column_issues(loader.raw_header(path, enc))
    if issues:
        raise ValueError(
            "열 이름 문제로 직접 질의할 수 없습니다(" + "; ".join(issues)
            + "). data-prep 로 먼저 정돈한 뒤 질문하세요."
        )


def _execute(con, inner_sql: str, params: list, limit: int) -> dict:
    wrapped = f"SELECT * FROM ({inner_sql}) AS _q LIMIT {limit + 1}"
    cur = con.execute(wrapped, params)
    out = cur.fetchall()
    names = [d[0] for d in cur.description]
    truncated = len(out) > limit
    return {
        "columns": names,
        "rows": [list(r) for r in out[:limit]],
        "row_count": min(len(out), limit),
        "truncated": truncated,
        "sql": inner_sql,
        "params": params,
    }


def inspect(path: str) -> dict:
    """로드+프로파일 입력 일괄 제공: schema(type·samples·numeric)·sample_rows·encoding·column_issues.

    SKILL 1·2단계(프로파일·구조 점검)와 profiler/structure 의 단일 진입점.
    """
    enc, needs = loader.resolve_encoding(path)
    issues = loader.column_issues(loader.raw_header(path, enc))
    con = _connect_load(path, enc, needs)
    try:
        schema, sample_rows = _describe(con)
        total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    finally:
        con.close()
    return {"schema": schema, "sample_rows": sample_rows, "encoding": enc,
            "column_issues": issues, "row_count": total}


def run_plan(path: str, plan: qp.QueryPlan, limit: int | None = None) -> dict:
    """QueryPlan 을 결정론 SQL 로 변환해 봉인 연결에서 실행."""
    enc, needs = loader.resolve_encoding(path)
    _require_clean_columns(path, enc)
    con = _connect_load(path, enc, needs)
    try:
        schema, _ = _describe(con)
        if not schema:
            raise ValueError("빈 CSV 입니다.")
        sql, params = qp.plan_to_sql(plan, schema)
        res = _execute(con, sql, params, limit if limit is not None else plan.limit)
    finally:
        con.close()
    res["encoding"] = enc
    return res


def validate_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise ValueError("빈 쿼리입니다.")
    if ";" in s:
        raise ValueError("복수 문장 금지 — 한 번에 하나의 SELECT.")
    if not _READ_ONLY.match(s):
        raise ValueError("읽기 전용 SELECT/WITH 만 허용됩니다.")
    return s


def run_sql(path: str, sql: str, limit: int = 100) -> dict:
    """가드된 raw-SQL fallback (EXC-1: plan 표현 불가 질의에 한해, 명시 경고와 함께).

    소셀 N 자동 주입이 없으므로 호출부가 정직 보고 책임을 진다. 봉인 후 실행이라
    원격·로컬파일·COPY 는 차단된다(SELECT-only 검증 + enable_external_access=false).
    """
    enc, needs = loader.resolve_encoding(path)
    _require_clean_columns(path, enc)
    con = _connect_load(path, enc, needs)
    try:
        s = validate_sql(sql)
        res = _execute(con, s, [], limit)
    finally:
        con.close()
    res["encoding"] = enc
    res["fallback"] = True
    return res
