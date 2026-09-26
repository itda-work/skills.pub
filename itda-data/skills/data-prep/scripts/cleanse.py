"""값 정제 (SPEC-DATA-VERTICAL-001 — tidy parity). stdlib only, 결정론.

공백 정리 · 날짜 정규화(한국 흔한 포맷 → ISO) · 중복 행 제거
· mojibake/인코딩 복구 · casing 정규화 · number-as-text 변환 (#951 clean-data-xls 흡수).

[정확성 원칙] 애매하면 손대지 않는다 — number-as-text 는 통화·천단위 콤마가 명시된 값만
숫자화하고 선행 0(우편번호·사번 등)은 보존한다. casing 은 같은 값의 대소문자 변형이 실제로
있을 때만 최빈 원형으로 통일한다.
"""
from __future__ import annotations
import re
import unicodedata
from collections import Counter

_DATE_PATS = [
    (re.compile(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$"),
     lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
    (re.compile(r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일?$"),
     lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
    (re.compile(r"^(\d{4})[.\-/](\d{1,2})$"),
     lambda m: f"{m.group(1)}-{int(m.group(2)):02d}"),
]


def normalize_date(value) -> str:
    s = str(value).strip()
    for pat, fn in _DATE_PATS:
        m = pat.match(s)
        if m:
            return fn(m)
    return s


def _looks_date(s) -> bool:
    return any(p.match(str(s).strip()) for p, _ in _DATE_PATS)


def detect_date_columns(rows: list[list[str]]) -> list[int]:
    if not rows:
        return []
    width = max(len(r) for r in rows)
    out = []
    for c in range(width):
        vals = [r[c] for r in rows if c < len(r) and str(r[c]).strip() != ""]
        if vals and sum(1 for v in vals if _looks_date(v)) / len(vals) >= 0.8:
            out.append(c)
    return out


def trim(rows: list[list[str]]) -> list[list[str]]:
    return [[str(c).strip() for c in r] for r in rows]


def dedupe(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    seen: set = set()
    out = []
    for r in rows:
        key = tuple(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out, len(rows) - len(out)


def normalize_date_columns(rows: list[list[str]], date_cols: list[int]) -> list[list[str]]:
    s = set(date_cols)
    return [[(normalize_date(c) if i in s else c) for i, c in enumerate(r)] for r in rows]


# ── #951 흡수: mojibake 복구 ────────────────────────────────────────────────
_MOJIBAKE_MARKERS = ("Ã", "â\x80", "Â", "�", "ï¿½")


def fix_mojibake(value) -> str:
    """UTF-8 이 latin-1 로 오해독된 mojibake(Ã©, â€™)를 복구하고 제어문자를 제거한다.

    마커가 있을 때만 latin-1→utf-8 재해독을 시도하고, 실패하면 원본을 보존한다(보수적).
    """
    t = str(value)
    if any(mk in t for mk in _MOJIBAKE_MARKERS):
        try:
            t = t.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    # 비인쇄 제어문자 제거(탭은 보존)
    t = "".join(ch for ch in t if ch == "\t" or unicodedata.category(ch)[0] != "C")
    return t


def fix_mojibake_rows(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    n = 0
    out = []
    for r in rows:
        nr = []
        for c in r:
            f = fix_mojibake(c)
            if f != str(c):
                n += 1
            nr.append(f)
        out.append(nr)
    return out, n


# ── #951 흡수: number-as-text 변환 ─────────────────────────────────────────
_MONEY = re.compile(r"^[$₩€£¥]?\s*(-?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)$")


def number_as_text(value) -> str:
    """통화기호·천단위 콤마가 붙은 숫자를 순수 숫자 문자열로. 선행 0 은 보존한다.

    "$1,234"→"1234", "1,234.5"→"1234.5". "007"·"45%"·"abc" 는 손대지 않는다(보수적).
    """
    t = str(value).strip()
    if "," not in t and not any(sym in t for sym in "$₩€£¥"):
        return t  # 통화·천단위 신호가 없으면 그대로(선행 0 보존)
    m = _MONEY.match(t)
    if m:
        return m.group(1) + m.group(2).replace(",", "")
    return t


def number_as_text_rows(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    n = 0
    out = []
    for r in rows:
        nr = []
        for c in r:
            f = number_as_text(c)
            if f != str(c):
                n += 1
            nr.append(f)
        out.append(nr)
    return out, n


# ── #951 흡수: casing 정규화 ───────────────────────────────────────────────
def _is_number_like(v) -> bool:
    try:
        float(str(v).replace(",", "").lstrip("$₩€£¥ ").strip())
        return True
    except (TypeError, ValueError):
        return False


def detect_casing_columns(rows: list[list[str]]) -> list[int]:
    """같은 값의 대소문자 변형(usa/USA/Usa)이 실제로 있는 텍스트 열만."""
    if not rows:
        return []
    width = max((len(r) for r in rows), default=0)
    out = []
    for c in range(width):
        vals = [str(r[c]).strip() for r in rows if c < len(r) and str(r[c]).strip()]
        if len(vals) < 2:
            continue
        if sum(1 for v in vals if _is_number_like(v)) > len(vals) * 0.4:
            continue  # 숫자 열은 casing 무의미
        seen: dict[str, str] = {}
        has_variant = False
        for v in vals:
            k = v.casefold()
            if k in seen and seen[k] != v:
                has_variant = True
                break
            seen.setdefault(k, v)
        if has_variant:
            out.append(c)
    return out


def normalize_casing_columns(rows: list[list[str]], cols: list[int]) -> list[list[str]]:
    """각 열에서 casefold 그룹별 최빈 원형으로 통일(결정론: 동점은 등장순)."""
    maps: dict[int, dict[str, str]] = {}
    for c in cols:
        groups: dict[str, Counter] = {}
        for r in rows:
            if c < len(r):
                v = str(r[c]).strip()
                if v:
                    groups.setdefault(v.casefold(), Counter())[v] += 1
        maps[c] = {k: cnt.most_common(1)[0][0] for k, cnt in groups.items()}
    out = []
    for r in rows:
        nr = list(r)
        for c in cols:
            if c < len(nr):
                v = str(nr[c]).strip()
                if v and v.casefold() in maps[c]:
                    nr[c] = maps[c][v.casefold()]
        out.append(nr)
    return out
