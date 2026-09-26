"""CSV 인코딩 결정 + 열-이름 위생 + 금액 정규화 보조 (stdlib only).

SPEC-DATA-VERTICAL-001 REQ-010.
엔진 교체(2026-06-25, #567): 타입·구분자·앞자리0(`06234`) 추론은 duckdb `read_csv`
네이티브 스니퍼로 이관(`safe_exec`). stdlib `infer_schema` 가 앞자리 0 을 정수로 잃던
버그가 교체 동기. 이 모듈에 남는 책임은 셋:
  1) `resolve_encoding` — duckdb 에 넘길 인코딩 결정(BOM → utf-8 시도 → cp949).
  2) `raw_header` + `column_issues` — duckdb 가 자동 rename 하기 전 원본 헤더 위생 검사
     (빈·None·중복 열 → data-prep 라우팅, F2·F3 크래시 방지).
  3) `clean_number` / `is_nullish` — 금액 정규화의 **파이썬 참조 구현**(단위 회귀).
     실제 집계 정규화의 정본은 SQL(`queryplan._num_expr`) 이다.
"""
from __future__ import annotations
import csv
import re
import unicodedata

_NUM_CLEAN = re.compile(r"[,\s₩%\\$¥€£]|원")  # \\ : cp949 는 ₩ 를 0x5C(역슬래시)로 저장
_NULLISH = {"", "미정", "해당없음", "n/a", "na", "null", "none", "-"}
_DELIMS = (",", ";", "\t", "|")


def _detect_bom(path: str) -> str | None:
    """BOM 기반 확정 인코딩. utf-16 / utf-8(BOM). 없으면 None → 시도 폴백."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8"  # duckdb 가 utf-8 BOM 을 자동 제거하므로 utf-8 로 넘긴다
    return None


def resolve_encoding(path: str) -> tuple[str, bool]:
    """duckdb `read_csv` 에 넘길 인코딩 결정 → (encoding, needs_encodings_ext).

    BOM 우선(utf-16 / utf-8). BOM 이 없으면 앞부분을 utf-8 로 디코드 시도해 성공하면
    utf-8, 실패하면 cp949(⊇ euc-kr) 로 본다. needs_encodings 는 cp949 일 때만 True —
    cp949 디코딩에는 duckdb 코어 `encodings` 확장 LOAD 가 필요하다.
    """
    bom = _detect_bom(path)
    if bom:
        return bom, False
    with open(path, "rb") as f:
        chunk = f.read(65536)
    try:
        chunk.decode("utf-8")
        return "utf-8", False
    except UnicodeDecodeError:
        return "cp949", True


def _sniff_delimiter(line: str) -> str:
    """헤더 라인에서 , ; \\t | 중 최빈 구분자(원본 헤더 위생 검사용).

    실제 로드 시 구분자는 duckdb 가 자동 감지한다 — 이건 raw 헤더를 열 단위로
    쪼개 빈/중복 이름만 보려는 용도라 근사로 충분하다.
    """
    counts = {d: line.count(d) for d in _DELIMS}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def raw_header(path: str, encoding: str) -> list[str]:
    """duckdb 자동 rename 전 **원본** 헤더 행. 빈/중복 열 이름 감지에 사용.

    duckdb 는 빈 헤더를 `column1`, 중복을 `지역_1` 로 바꿔 원본 결함을 가리므로,
    위생 검사는 read_csv 이전 stdlib 로 해야 한다.
    """
    enc = "utf-8-sig" if encoding == "utf-8" else encoding  # 파이썬 측 BOM 제거
    with open(path, newline="", encoding=enc, errors="replace") as f:
        line = f.readline()
    if not line:
        return []
    delim = _sniff_delimiter(line)
    return next(csv.reader([line], delimiter=delim), [])


def is_nullish(v) -> bool:
    return v is None or str(v).strip().lower() in _NULLISH


def clean_number(v) -> str:
    """금액 표기 정규화(파이썬 참조 구현). 전각→반각(NFKC), 회계 괄호 음수,
    통화기호·콤마·후행마이너스 제거.

    '₩-12,900원'→'-12900', '$1,200.50'→'1200.50', '(1,200,000)'→'-1200000',
    '１２３'→'123', '1500-'→'-1500'. (한글 단위 억/만 은 미지원 — follow-up)

    NOTE: 실제 집계 정규화의 정본은 SQL(`queryplan._num_expr`) 이며, 그쪽은 전각·
    후행마이너스를 다루지 않는다(duckdb 빌트인 한계 — backlog). 이 함수는 단위 회귀와
    오프라인 참조용으로 유지한다.
    """
    s = unicodedata.normalize("NFKC", str(v)).strip()
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = _NUM_CLEAN.sub("", s)
    if s.endswith("-") and s[:-1]:      # 후행 마이너스
        s = "-" + s[:-1]
    if neg and s and not s.startswith("-"):
        s = "-" + s
    return s


def column_issues(names: list) -> list[str]:
    """빈·None·중복 열 이름 진단(원본 헤더 기준). 비어있지 않으면 data-prep
    정돈이 선행돼야 한다(F2·F3 크래시 방지)."""
    if not names:
        return []
    issues = []
    if any(n is None for n in names):
        issues.append("이름 없는 열(헤더 어긋남/다중 표 가능)")
    if any(n is not None and str(n).strip() == "" for n in names):
        issues.append("빈 열 이름")
    seen, dups = set(), set()
    for n in names:
        if n in seen:
            dups.add(str(n))
        seen.add(n)
    if dups:
        issues.append("중복 열 이름: " + ", ".join(sorted(dups)))
    return issues
