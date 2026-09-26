"""CSV 경량 프로파일링 — 분석 지도의 결정론 재료 (stdlib only).

data-compass(#1271)의 지형 파악 담당. 같은 입력 → 같은 프로파일(강의 재현성).
계산·집계는 하지 않는다 — 그건 data-ask 의 몫이고, 여기서는 지도를 그리는 데
필요한 최소 사실(인코딩·규모·컬럼 역할·품질 신호)만 수집한다.

role 분류(pii/id/date/measure/dimension)는 data-ask profiler 와 같은
이름-우선 접근을 쓰되, duckdb 없이 stdlib 로 판정한다(의존 0 유지).
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

MAX_ROWS = 50_000          # 프로파일 판정에 읽는 최대 행(초과분은 truncated 로 표기)
SAMPLE_LIMIT = 3           # 컬럼별 예시값 수
DISTINCT_CAP = 50          # 고유값 셀 때 상한(초과는 "50+")
HIGH_MISSING_PCT = 30.0    # 결측 경고 임계

_PII = re.compile(r"(이름|성명|고객명|성함|전화|연락처|휴대폰|핸드폰|email|이메일|메일|주소|생년|생일|주민|계좌|카드번호)", re.I)
_ID = re.compile(r"(주문번호|주문no|번호|코드|식별|uuid|order_?id|_id\b|_no\b|\bid\b|\bno\b|code)", re.I)
_DATE = re.compile(r"(일자|날짜|일시|등록일|주문일|결제일|접수일|예약일|평가일|가입일|일$|date|datetime|month|(?<!개)월$|연도|년도)", re.I)
_DATE_VAL = re.compile(r"^\d{4}[-/.]\d{1,2}([-/.]\d{1,2})?")
_TOTALS = re.compile(r"(합계|총계|소계|총액|누계|total|subtotal)", re.I)
_NUM_CLEAN = re.compile(r"[,\s₩%\\$¥€£]|원")  # \\ : cp949 는 ₩ 를 0x5C 로 저장
_NULLISH = {"", "미정", "해당없음", "n/a", "na", "null", "none", "-"}
_DELIMS = (",", ";", "\t", "|")


def resolve_encoding(path: str) -> str:
    """BOM → utf-8 시도 → cp949(⊇ euc-kr). 반환값은 open(encoding=) 에 그대로 쓴다."""
    head = Path(path).read_bytes()[:65536]
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    try:
        head.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp949"


def sniff_delimiter(header_line: str) -> str:
    counts = {d: header_line.count(d) for d in _DELIMS}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def is_nullish(v) -> bool:
    return v is None or str(v).strip().lower() in _NULLISH


def looks_numeric(v) -> bool:
    """통화·천단위·%·회계괄호 표기까지 숫자로 인정(전각은 NFKC 정규화)."""
    s = unicodedata.normalize("NFKC", str(v)).strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    s = _NUM_CLEAN.sub("", s)
    if s.endswith("-") and s[:-1]:
        s = s[:-1]
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def header_issues(names: list[str]) -> list[str]:
    """빈·중복 열 이름 진단 — 있으면 data-prep 정돈이 먼저다."""
    issues = []
    if any(str(n).strip() == "" for n in names):
        issues.append("빈 열 이름")
    seen, dups = set(), set()
    for n in names:
        if n in seen:
            dups.add(str(n))
        seen.add(n)
    if dups:
        issues.append("중복 열 이름: " + ", ".join(sorted(dups)))
    return issues


def classify_role(name: str, samples: list[str]) -> str:
    """이름 우선 판정(pii > date > id > measure > dimension) — data-ask 와 동일 정신."""
    if _PII.search(name):
        return "pii"
    if _DATE.search(name) or any(_DATE_VAL.match(str(s)) for s in samples):
        return "date"
    if _ID.search(name):
        return "id"
    if samples and all(looks_numeric(s) for s in samples):
        return "measure"
    return "dimension"


def load_table(path: str) -> dict:
    enc = resolve_encoding(path)
    with open(path, newline="", encoding=enc, errors="replace") as f:
        first = f.readline()
        if not first:
            return {"encoding": enc, "delimiter": ",", "header": [], "rows": [], "truncated": False, "ragged_rows": 0}
        delim = sniff_delimiter(first)
        header = next(csv.reader([first], delimiter=delim), [])
        reader = csv.reader(f, delimiter=delim)
        rows, ragged, truncated = [], 0, False
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                truncated = True
                break
            if not any(str(c).strip() for c in row):
                continue  # 완전 빈 행은 프로파일에서 제외
            if len(row) != len(header):
                ragged += 1
            rows.append(row)
    return {"encoding": enc, "delimiter": delim, "header": header,
            "rows": rows, "truncated": truncated, "ragged_rows": ragged}


def profile_table(path: str) -> dict:
    """파일 → 지도 재료. 결정론(같은 파일 → 같은 dict)."""
    t = load_table(path)
    header, rows = t["header"], t["rows"]
    columns = []
    for idx, name in enumerate(header):
        values = [row[idx] if idx < len(row) else "" for row in rows]
        nonnull = [v for v in values if not is_nullish(v)]
        samples, seen = [], set()
        for v in nonnull:
            if v not in seen:
                samples.append(str(v))
                seen.add(v)
            if len(samples) >= SAMPLE_LIMIT:
                break
        distinct = set()
        for v in nonnull:
            distinct.add(v)
            if len(distinct) > DISTINCT_CAP:
                break
        missing_pct = round(100.0 * (len(values) - len(nonnull)) / len(values), 1) if values else 0.0
        numeric_ratio = round(sum(looks_numeric(v) for v in nonnull) / len(nonnull), 2) if nonnull else 0.0
        columns.append({
            "name": str(name),
            "role": classify_role(str(name), samples),
            "samples": samples,
            "missing_pct": missing_pct,
            "distinct": f"{DISTINCT_CAP}+" if len(distinct) > DISTINCT_CAP else str(len(distinct)),
            "numeric_ratio": numeric_ratio,
            "totalsish": bool(_TOTALS.search(str(name))),
        })
    issues = header_issues([str(n) for n in header])
    high_missing = [c["name"] for c in columns if c["missing_pct"] >= HIGH_MISSING_PCT]
    # 숫자가 다수인데 텍스트가 섞인 열(0.5~0.95): 집계 전에 정돈이 필요하다는 신호
    mixed_numeric = [c["name"] for c in columns if 0.5 <= c["numeric_ratio"] < 0.95 and c["role"] != "date"]
    return {
        "file": Path(path).name,
        "path": str(path),
        "encoding": t["encoding"],
        "delimiter": t["delimiter"],
        "n_rows": len(rows),
        "n_cols": len(header),
        "truncated": t["truncated"],
        "columns": columns,
        "quality": {
            "header_issues": issues,
            "ragged_rows": t["ragged_rows"],
            "high_missing": high_missing,
            "mixed_numeric": mixed_numeric,
        },
        "needs_prep": bool(issues) or t["ragged_rows"] > 0 or bool(mixed_numeric),
    }
