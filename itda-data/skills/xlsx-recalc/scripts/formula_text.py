"""xlsx 수식 문자열을 계산 없이 해석한다(stdlib) — 공유 수식 전개 · 외부 링크 참조 추출 · 재직렬화 비교.

LibreOffice 가 계산은 하지만, 계산 **전후로** 스크립트가 확인할 것이 셋 있다(#1690).

1. 공유 수식(`<f t="shared">`) 자식 셀은 수식 문자열이 비어 있다 — 비교·외부 참조 검사를 하려면 부모 수식을
   행·열 차이만큼 옮겨 전개해야 한다.
2. 외부 통합문서 참조(`[1]Sheet1!$A$1`)는 LibreOffice 가 링크 파트의 값 캐시로 계산한다. 그 캐시가 없으면 0 을
   성공으로 쓴다(조용한 오답) — 참조한 셀마다 캐시가 있는지 먼저 확인해야 한다.
3. LibreOffice 는 저장할 때 수식을 다시 직렬화한다(`TRUE`→`TRUE()`, `ROUND(0.49999999999999994,0)`→`ROUND(0.5,0)`).
   값이 바뀔 수 있는 변화(숫자·문자열 리터럴, 함수, 참조)와 표기만 바뀐 변화를 가른다.

완전한 수식 파서가 아니다. 모르는 모양은 **보수적으로** 다룬다 — 외부 참조는 해석 불가로 거부하고, 재직렬화 비교는
위험으로 분류한다.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass

MAX_COL = 16384  # XFD
MAX_ROW = 1048576


def mask_strings(text: str) -> str:
    """문자열 리터럴 "..." 의 내용을 같은 길이의 \\x00 으로 가린다(따옴표는 남긴다). 인덱스가 원문과 일치한다."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append('"')
            i += 1
            while i < n:
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        out.append("\x00\x00")
                        i += 2
                        continue
                    out.append('"')
                    i += 1
                    break
                out.append("\x00")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def mask_names(text: str) -> str:
    """문자열 리터럴 + 따옴표 시트 이름('...') + 대괄호 구간([1]·Table1[Col]·[[#This Row],[A1]]) 을 같은 길이로 가린다.

    공유 수식을 옮길 때 `'[1]A1'!A1` 의 시트 이름 A1 이나 `Table1[A1]` 의 열 이름을 셀 주소로 착각하지 않게 한다(Codex R2 #3).
    """
    masked = list(mask_strings(text))
    i, n = 0, len(masked)
    while i < n:
        ch = masked[i]
        if ch == "'":
            j = i + 1
            while j < n:
                if masked[j] == "'":
                    if j + 1 < n and masked[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            for k in range(i + 1, min(j, n)):
                masked[k] = "\x01"
            i = j + 1
        elif ch == "[":
            depth, j = 0, i
            while j < n:
                if masked[j] == "[":
                    depth += 1
                elif masked[j] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            for k in range(i + 1, min(j, n)):
                masked[k] = "\x01"
            i = j + 1
        else:
            i += 1
    # 따옴표 없는 시트 접두(`A1!B1` 의 A1)는 셀 정규식의 `!` 선행 금지(_CELL)가 막는다.
    return "".join(masked)


def string_literals(text: str) -> list[str]:
    masked = mask_strings(text)
    return [text[m.start() + 1:m.end() - 1].replace('""', '"') for m in re.finditer(r'"\x00*"', masked)]


def col_to_num(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def split_cell(ref: str) -> tuple[int, int]:
    """'$B$12' → (col 2, row 12)."""
    m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?(\d+)", ref)
    if not m:
        raise ValueError(ref)
    return col_to_num(m.group(1)), int(m.group(2))


# 참조 앞에 올 수 없는 글자(이름·함수·시트 접두의 일부가 아닌 경계)
_BOUND = r"(?<![\w.$\\])"  # \w 는 유니코드 — `세율A1` 같은 이름 안의 A1 을 셀로 보지 않는다
_CELL = r"(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![\w(.!])"
_CELL_RE = re.compile(_BOUND + _CELL)
_COLRANGE_RE = re.compile(_BOUND + r"(\$?)([A-Za-z]{1,3}):(\$?)([A-Za-z]{1,3})(?![\w(!])")
_ROWRANGE_RE = re.compile(r"(?<![\w.$\\:])(\$?)(\d+):(\$?)(\d+)(?![\w.(:!])")


def _valid_cell(col: str, row: str) -> bool:
    c, r = col_to_num(col), int(row)
    return 1 <= c <= MAX_COL and 1 <= r <= MAX_ROW


def shift_formula(text: str, drow: int, dcol: int) -> str:
    """공유 수식 부모 문자열을 자식 위치로 옮긴다. `$` 가 붙은 축은 고정, 문자열 리터럴은 그대로."""
    if not drow and not dcol:
        return text
    masked = mask_names(text)
    edits: list[tuple[int, int, str]] = []

    def taken(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e, _ in edits)

    for m in _COLRANGE_RE.finditer(masked):
        if taken(m.start(), m.end()):
            continue
        d1, c1, d2, c2 = m.groups()
        if col_to_num(c1) > MAX_COL or col_to_num(c2) > MAX_COL:
            continue
        n1 = col_to_num(c1) + (0 if d1 else dcol)
        n2 = col_to_num(c2) + (0 if d2 else dcol)
        edits.append((m.start(), m.end(), f"{d1}{num_to_col(max(n1, 1))}:{d2}{num_to_col(max(n2, 1))}"))
    for m in _ROWRANGE_RE.finditer(masked):
        if taken(m.start(), m.end()):
            continue
        d1, r1, d2, r2 = m.groups()
        n1 = int(r1) + (0 if d1 else drow)
        n2 = int(r2) + (0 if d2 else drow)
        edits.append((m.start(), m.end(), f"{d1}{max(n1, 1)}:{d2}{max(n2, 1)}"))
    for m in _CELL_RE.finditer(masked):
        if taken(m.start(), m.end()):
            continue
        dc, col, dr, row = m.groups()
        if not _valid_cell(col, row):
            continue
        nc = col_to_num(col) + (0 if dc else dcol)
        nr = int(row) + (0 if dr else drow)
        edits.append((m.start(), m.end(), f"{dc}{num_to_col(max(nc, 1))}{dr}{max(nr, 1)}"))
    out = text
    for s, e, rep in sorted(edits, reverse=True):
        out = out[:s] + rep + out[e:]
    return out


# ── 외부 링크 참조 ─────────────────────────────────────────────────────────

@dataclass
class ExternalRef:
    link: int  # [n] — 1-based
    sheet: str | None  # None 이면 외부 정의된 이름([1]!Name)
    target: str  # 셀·범위·이름 원문
    raw: str


# '[1]Sheet 1'!A1 · '[1]Sheet1:Sheet3'!A1 · [1]Sheet1!A1 · [1]!Name
_EXT_QUOTED = re.compile(r"'\[(\d+)\]((?:[^']|'')*)'!")
_EXT_PLAIN = re.compile(r"(?<![A-Za-z0-9_.'\]])\[(\d+)\]([^\s!'\[\](),;+\-*/^&=<>{}\"]*)!")
_TARGET = re.compile(
    r"\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?(?![A-Za-z0-9_(])"
    r"|\$?[A-Za-z]{1,3}:\$?[A-Za-z]{1,3}(?![A-Za-z0-9_(])"
    r"|\$?\d+:\$?\d+(?![A-Za-z0-9_(])"
    r"|[A-Za-z_\\][A-Za-z0-9_.\\]*"
)


def external_refs(text: str) -> list[ExternalRef]:
    """수식 문자열의 외부 링크 참조를 뽑는다. 대상 모양을 못 읽으면 target 을 빈 문자열로 둔다(호출자가 거부)."""
    masked = mask_strings(text)
    found: list[ExternalRef] = []
    spans: list[tuple[int, int]] = []
    for rx, quoted in ((_EXT_QUOTED, True), (_EXT_PLAIN, False)):
        for m in rx.finditer(masked):
            if any(not (m.end() <= s or m.start() >= e) for s, e in spans):
                continue
            sheet = text[m.start(2):m.end(2)]
            if quoted:
                sheet = sheet.replace("''", "'")
            t = _TARGET.match(masked, m.end())
            target = text[t.start():t.end()] if t else ""
            end = t.end() if t else m.end()
            # `[1]S!A1 : A2` 처럼 대상 뒤에 범위 연산자가 이어지면 실제 범위를 셀 수 없다 — 대상을 비워 거부시킨다.
            rest = masked[end:].lstrip(" ")
            if target and rest.startswith(":"):
                target = ""
            spans.append((m.start(), end))
            found.append(ExternalRef(link=int(m.group(1)), sheet=sheet or None, target=target, raw=text[m.start():end]))
    return found


_DYNAMIC_REF_FUNCS = re.compile(r"(?<![A-Za-z0-9_.])(OFFSET|INDIRECT)\s*\(", re.IGNORECASE)


def has_dynamic_reference(text: str) -> bool:
    """참조를 옮기거나 문자열로 만드는 함수(OFFSET·INDIRECT) — 외부 참조와 함께 쓰이면 필요한 캐시 셀을 정적으로 알 수 없다."""
    return _DYNAMIC_REF_FUNCS.search(mask_strings(text)) is not None


# 파일 이름으로 쓴 외부 참조 — `'[other.xlsx]Sheet1'!A1` · `[other.xlsx]Sheet1!A1` · `'C:\\d\\[a b.xlsx]S'!A1` · `[a.xlsx]!Name`.
# openpyxl 은 이 표기를 링크 파트 없이 수식 문자열로만 저장한다(Excel 은 [숫자] + 링크 파트로 저장). 뒤에 `!` 가 붙어야 하므로
# 표 구조 참조(`Tbl[Col]`·`[@Col]`·`Tbl[[#This Row],[a]]`)와 겹치지 않는다.
_EXT_FILENAME_QUOTED = re.compile(r"'(?:[^'\[]|'')*\[(?!\d+\])[^\[\]']+\](?:[^']|'')*'!")
_EXT_FILENAME_PLAIN = re.compile(r"\[(?!\d+\])[^\[\]\s']+\][^\s!'\[\](),;+\-*/^&=<>{}\"]*!")


def has_filename_external_reference(text: str) -> bool:
    """문자열 밖에 파일 이름 표기의 외부 참조가 있는가. 값 캐시를 담을 링크 파트가 없는 모양이라 계산할 수 없다."""
    masked = mask_strings(text)
    return bool(_EXT_FILENAME_QUOTED.search(masked) or _EXT_FILENAME_PLAIN.search(masked))


def has_external_marker(text: str) -> bool:
    """외부 참조 표기([숫자] 또는 파일 이름)가 문자열 밖에 하나라도 있는가 — 해석 누락을 잡는 보수적 신호."""
    return re.search(r"\[\d+\]", mask_strings(text)) is not None or has_filename_external_reference(text)


_NAME_CHARS = r"[^\W]|[.\\?]"  # 유니코드 글자·숫자·_ 와 . \\ ?


def name_used(text: str, name: str) -> bool:
    """정의된 이름이 수식에서 토큰으로 쓰였는가(대소문자 무시·유니코드). 문자열 리터럴은 제외한다.

    `S!Rate` 처럼 시트로 한정한 이름도 잡는다(Codex R2 #2). 보수적이다 — 같은 철자의 다른 토큰도 사용으로 본다.
    """
    if name.upper() not in text.upper():  # 대부분의 수식은 여기서 끝난다
        return False
    return _name_pattern(name).search(mask_strings(text)) is not None


@functools.lru_cache(maxsize=4096)
def _name_pattern(name: str) -> re.Pattern:
    # 뒤에 괄호가 와도 사용으로 본다 — `Rate (A1:A2)` 교차·`Rate(…)` 오기 모두 이름을 거칠 수 있다(Codex R3 #2, 보수).
    return re.compile(r"(?<![\w.\\?])" + re.escape(name) + r"(?![\w.\\?])", re.IGNORECASE)


# ── 재직렬화 비교 ──────────────────────────────────────────────────────────

_NUM_RE = re.compile(r"(?<![A-Za-z0-9_.$:\\])(\d+\.?\d*|\.\d+)(?:[eE]([+-]?\d+))?(?![A-Za-z0-9_.(:!])")
_FUNC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(")


def _numbers(masked: str, original: str) -> list[float]:
    vals = []
    for m in _NUM_RE.finditer(masked):
        try:
            vals.append(float(original[m.start():m.end()]))
        except ValueError:
            vals.append(float("nan"))
    return vals


def _functions(masked: str) -> list[str]:
    return [f.upper() for f in _FUNC_RE.findall(masked) if f.upper() not in ("TRUE", "FALSE")]


def _references(masked: str) -> list[str]:
    s = masked.replace("'", "").replace("$", "").upper()
    refs = []
    for m in re.finditer(
        r"(?<![A-Z0-9_.])(?:(?:[^\s!(),;+\-*/^&=<>{}\"\x00]+!)?[A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?(?![A-Z0-9_(])"
        r"|(?:[^\s!(),;+\-*/^&=<>{}\"\x00]+!)?[A-Z]{1,3}:[A-Z]{1,3}(?![A-Z0-9_(]))",
        s,
    ):
        tok = m.group(0)
        if ":" in tok:
            head, _, tail = tok.rpartition(":")
            prefix, bang, first = head.rpartition("!")
            if first == tail:
                tok = f"{prefix}{bang}{first}"
        refs.append(tok)
    return refs


def _protected_chunks(body: str) -> list[tuple[str, str]]:
    """("str"|"sheet"|"bracket"|"code", 원문) 조각. 문자열·따옴표 시트 이름·대괄호 구간은 정규화하지 않는다."""
    out, i, n, start = [], 0, len(body), 0
    while i < n:
        ch = body[i]
        if ch in "\"'[":
            if start < i:
                out.append(("code", body[start:i]))
            if ch == "[":
                depth, j = 0, i
                while j < n:
                    depth += body[j] == "["
                    depth -= body[j] == "]"
                    if depth == 0:
                        break
                    j += 1
                kind = "bracket"
            else:
                j = i + 1
                while j < n:
                    if body[j] == ch:
                        if j + 1 < n and body[j + 1] == ch:
                            j += 2
                            continue
                        break
                    j += 1
                kind = "str" if ch == '"' else "sheet"
            out.append((kind, body[i:j + 1]))
            i = start = j + 1
        else:
            i += 1
    if start < n:
        out.append(("code", body[start:]))
    return out


def canonical(text: str) -> str:
    """LibreOffice 재직렬화에서 **값에 영향이 없다고 확인한** 표기 차이만 지운 정규형.

    - 코드 부분의 대소문자·연산자 옆 공백 · `TRUE()`/`FALSE()` → `TRUE`/`FALSE` · 같은 셀 범위(`F18:F18`→`F18`)
    - 숫자 리터럴 표기(`1E308`→`1E+308`, 값이 같을 때만)
    - 필요 없는 시트 이름 따옴표(`'설정'!`→`설정!`) — 시트 이름 자체는 대소문자만 접고 그 밖은 그대로 둔다
    문자열 리터럴·대괄호(구조적 참조·외부 링크 번호) 안은 건드리지 않는다(Codex R3 신규 #2: `'Data - 1'`→`'Data-1'`,
    `Table1[1E3]`→`Table1[1000]` 을 무해로 접던 결함).
    """
    body = text.strip().lstrip("=")
    # 공백 삭제는 조각을 나누기 **전에** 전체 문자열에서 판정한다. 조각 끝에서 판정하면 `A1 'S'!A1`(교차)의 공백이
    # 보호 조각 경계에서 사라져 `A1S!A1` 과 같아진다(Codex R4). 문자열·시트명·대괄호 안은 마스킹해 건드리지 않는다.
    masked = mask_names(body)
    keep = [True] * len(body)
    for m in re.finditer(r"(?<=[^\w$')\]\x00\x01])\s+|\s+(?=[^\w$'(\[\x00\x01\"])|^\s+|\s+$", masked):
        for k in range(m.start(), m.end()):
            keep[k] = False
    body = "".join(ch for ch, k in zip(body, keep) if k)
    chunks = _protected_chunks(body)
    parts = []
    for idx, (kind, chunk) in enumerate(chunks):
        if kind in ("str", "bracket"):
            parts.append(chunk)
            continue
        if kind == "sheet":
            inner = chunk[1:-1].replace("''", "'")
            nxt = chunks[idx + 1][1] if idx + 1 < len(chunks) else ""
            simple = re.fullmatch(r"[^\W\d][\w.]*", inner) and nxt.startswith("!")
            parts.append(inner.upper() if simple else "'" + inner.upper() + "'")
            continue
        c = chunk.upper()
        c = re.sub(r"\b(TRUE|FALSE)\(\)", r"\1", c)
        c = re.sub(r"(\$?[A-Z]{1,3}\$?\d+):(\$?[A-Z]{1,3}\$?\d+)(?![A-Z0-9_(])",
                   lambda m: m.group(1) if m.group(1) == m.group(2) else m.group(0), c)

        def num(m):
            try:
                return repr(float(m.group(0)))
            except ValueError:
                return m.group(0)
        parts.append(_NUM_RE.sub(num, c))
    return "".join(parts)


def rewrite_risks(before: str, after: str) -> list[str]:
    """두 수식 문자열의 차이 중 값이 바뀔 수 있는 종류를 돌려준다. 빈 목록이면 **확인된 표기 변환만** 있는 것이다.

    기본은 위험이다 — 정규형이 같을 때만 무해로 보고, 다르면 원인 분류(숫자·문자열·함수·참조)를 붙이고 분류가
    안 되면 `other_changed` 로 표시한다(Codex R2 #7: `A1+A2`→`A1-A2`·`TRUE`→`FALSE` 를 무해로 숨기던 결함).
    """
    b, a = before.strip().lstrip("="), after.strip().lstrip("=")
    if b == a or canonical(b) == canonical(a):
        return []
    mb, ma = mask_strings(b), mask_strings(a)
    risks = []
    nb, na = _numbers(mb, b), _numbers(ma, a)
    if len(nb) != len(na) or any(x != y for x, y in zip(nb, na)):
        risks.append("numeric_literal_changed")
    if string_literals(b) != string_literals(a):
        risks.append("string_literal_changed")
    if _functions(mb) != _functions(ma):
        risks.append("function_changed")
    if _references(mb) != _references(ma):
        risks.append("reference_changed")
    return risks or ["other_changed"]
