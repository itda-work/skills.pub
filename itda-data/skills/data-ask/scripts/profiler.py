"""컬럼 role 판정 + 질문 비계 (SPEC-DATA-VERTICAL-001 REQ-011).

role: pii · id · date · measure · dimension.
비계·집계에서 id/pii 를 측정값·차원 후보에서 제외 → 현 runner scaffold 의
'고객명별 주문번호'(PII·ID) 류 무의미 제안 결함을 코어에서 해결.
"""
from __future__ import annotations
import re

_PII = re.compile(r"(이름|성명|고객명|성함|전화|연락처|휴대폰|핸드폰|email|이메일|메일|주소|생년|생일|주민|계좌|카드번호)", re.I)
_ID = re.compile(r"(주문번호|주문no|번호|코드|식별|uuid|order_?id|_id\b|_no\b|\bid\b|\bno\b|code)", re.I)
# '월' 은 끝에 올 때만(주문월·가입월·정산월) date — '월성장률'·'월매출'(시작/중간)·'개월'(기간)은 제외.
_DATE = re.compile(r"(일자|날짜|일시|등록일|주문일|결제일|접수일|예약일|평가일|가입일|일$|date|datetime|month|(?<!개)월$|연도|년도)", re.I)
_DATE_VAL = re.compile(r"^\d{4}[-/.]\d{1,2}([-/.]\d{1,2})?")


def classify_role(col: dict, rows: list[dict] | None = None) -> str:
    # 이름 기반 우선(precedence: pii > date > id > measure > dimension).
    # 순수 cardinality 로 id 를 잡으면 고유한 측정값(금액 등)을 오분류하므로 쓰지 않는다.
    name, dtype = str(col.get("name") or ""), col.get("type", "VARCHAR")  # None-safe (F3)
    samples = col.get("samples", [])
    if _PII.search(name):
        return "pii"
    if dtype in ("DATE", "TIMESTAMP") or _DATE.search(name) or any(_DATE_VAL.match(str(s)) for s in samples):
        return "date"
    if _ID.search(name):
        return "id"
    # measure: duckdb 숫자 storage 이거나, 통화/형식 금액(VARCHAR) 으로 판정된 numeric 컬럼.
    # (엔진 교체 후 타입은 safe_exec.inspect 의 duckdb DESCRIBE + numeric 전수판정에서 옴.)
    if col.get("numeric") or dtype in ("BIGINT", "DOUBLE"):
        return "measure"
    return "dimension"


def profile(rows: list[dict], schema: list[dict]) -> list[dict]:
    return [{**c, "role": classify_role(c, rows)} for c in schema]


def suggest_questions(profiled: list[dict]) -> list[str]:
    measures = [c["name"] for c in profiled if c["role"] == "measure"]
    dims = [c["name"] for c in profiled if c["role"] == "dimension"]
    dates = [c["name"] for c in profiled if c["role"] == "date"]
    qs: list[str] = []
    if dims and measures:
        qs.append(f"{dims[0]}별 {measures[0]} 합계·평균은?")
    if dates and measures:
        qs.append(f"월별 {measures[0]} 추이는?")
    if dims:
        qs.append(f"{dims[0]} 값별 건수 분포는?")
    if measures:
        qs.append(f"{measures[0]} 상위 10건은?")
    if len(dims) >= 2:
        qs.append(f"{dims[0]}·{dims[1]} 조합별 건수는?")
    return qs[:5]
