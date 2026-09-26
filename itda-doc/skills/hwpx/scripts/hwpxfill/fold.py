"""비교용 정규화(접기) — 눈으로 구별되지 않는 표기 차이를 한 형태로 접는다 (--check 분류·--fix 교정안 전용).

접기 규칙: 결합 시퀀스 단위 NFC → 혼동문자 접기(중점·따옴표·물결·대시·전각/특수 공백) → 공백 제거 → PUA(한컴 글머리 글리프) 제거.
치환 자체는 접기를 쓰지 않는다(정확 부분문자열) — 접기는 "왜 안 맞는지" 를 말하고 교정안을 내는 데만 쓴다.

출처: 혼동문자 접기 표(`_FOLD_GROUPS`)는 jkf87/hwpx-skill (MIT, 96a2633) scripts/map_preflight.py:FOLD 의
데이터성 상수를 차용해 확장했다(물결 ‾·전각 콜론 등 추가). 코드 구조·알고리즘은 본 저장소 독자 구현이다.
"""
from __future__ import annotations

import unicodedata

_FOLD_GROUPS = (
    ("·‧・•∙⋅ㆍ", "·"),
    ("‘’‛`´′", "'"),
    ('“”„″', '"'),
    ("~∼〜～", "~"),
    ("-–—―‐‑−", "-"),
    ("：", ":"),
    ("（", "("),
    ("）", ")"),
)
FOLD: dict[str, str] = {}
for _src, _dst in _FOLD_GROUPS:
    for _ch in _src:
        FOLD[_ch] = _dst


def is_pua(c: str) -> bool:
    o = ord(c)
    return 0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFD


def _groups(text: str) -> list[tuple[int, int]]:
    """결합 시퀀스 단위 그룹 [(start, end)…] — 결합 문자·한글 중성/종성 자모는 앞 글자에 붙인다.

    NFC 를 글자 하나씩 적용하면 분해형(NFD) 한글 '성명'(ㅅ+ㅓ+ㅇ…)이 합성되지 않아 표기 차이를 못 접는다
    (Codex R2 F8). 그렇다고 문자열 전체를 NFC 하면 원문 인덱스 대응이 깨져 --fix 교정안이 원문 부분문자열이
    아니게 된다 — 그래서 **그룹 단위**로 NFC 하고 그룹 전체를 원문 span 하나에 대응시킨다."""
    groups: list[tuple[int, int]] = []
    for i, c in enumerate(text):
        o = ord(c)
        joins = unicodedata.combining(c) > 0 or 0x1160 <= o <= 0x11FF
        if joins and groups:
            groups[-1] = (groups[-1][0], i + 1)
        else:
            groups.append((i, i + 1))
    return groups


def fold_map(text: str) -> tuple[str, list[tuple[int, int]]]:
    """접은 문자열과, 접은 문자열의 각 글자가 원문의 어느 span [start, end) 에서 왔는지의 표.

    --fix 교정안이 **원문의 대응 부분문자열**이어야 하므로(Codex R1 F15) 대응은 span 으로 준다 —
    NFD 한 글자는 원문에서 2~3 코드포인트다.
    """
    out: list[str] = []
    src: list[tuple[int, int]] = []
    for gs, ge in _groups(text):
        for n in unicodedata.normalize("NFC", text[gs:ge]):
            n = FOLD.get(n, n)
            if n.isspace() or is_pua(n) or n == "\ufffc":
                continue
            out.append(n)
            src.append((gs, ge))
    return "".join(out), src


def fold(text: str) -> str:
    return fold_map(text)[0]


def unfold_span(text: str, src: list[tuple[int, int]], start: int, end: int) -> str:
    """접은 문자열의 [start, end) 에 대응하는 원문 부분문자열."""
    if end <= start:
        return ""
    return text[src[start][0] : src[end - 1][1]]
