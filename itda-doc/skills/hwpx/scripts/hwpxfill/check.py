"""--check 사전검증(ok/fixable/ctrl/multi/missing)·--fix 교정·--residue 사후 대조.

판정은 채널로: 결과 dict(JSON) + exit code. 문장 grep 판정 금지(`verdict-channel-not-inference`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .fold import fold_map, unfold_span
from .scan import Para, SENTINEL, display_with_marks

Value = str | list[str]

MULTI_WINDOW = 20  # multi 판정에서 이어 붙일 최대 문단 수


@dataclass
class KeyVerdict:
    key: str
    cls: str  # ok | fixable | ctrl | multi | missing
    count: int = 0
    fix: str | None = None  # fixable: 원문의 대응 부분문자열
    paragraph: int | None = None
    paragraph_end: int | None = None
    display: str = ""
    parts: list[str] = field(default_factory=list)  # ctrl/multi: 나눔 제안

    def to_json(self) -> dict:
        d: dict = {"key": self.key, "class": self.cls}
        if self.cls == "ok":
            d["count"] = self.count
        if self.fix is not None:
            d["fix"] = self.fix
        if self.paragraph is not None:
            d["paragraph"] = self.paragraph
        if self.paragraph_end is not None:
            d["paragraph_end"] = self.paragraph_end
        if self.display:
            d["display"] = self.display
        if self.parts:
            d["parts"] = self.parts
        return d


def _ctrl_stripped(p: Para) -> str:
    return p.text.replace(SENTINEL, "")


def classify_key(key: str, paras: list[Para]) -> KeyVerdict:
    """키 하나를 문서 문단들과 대조해 분류한다. 우선순위: ok → fixable → ctrl → multi → missing."""
    if not key or SENTINEL in key:
        return KeyVerdict(key, "missing")
    # ok — 정확 부분문자열(치환기가 실제로 매칭하는 것과 같은 판정)
    n = sum(p.text.count(key) for p in paras if p.text)
    if n:
        return KeyVerdict(key, "ok", count=n)
    fk, _ = fold_map(key)
    if not fk:
        return KeyVerdict(key, "missing")
    # fixable — 접기 정규화로 잡히고 컨트롤을 가로지르지 않음. 교정안은 원문 부분문자열(Codex F15)
    for p in paras:
        if not p.text:
            continue
        ft, src = fold_map(p.text)
        pos = ft.find(fk)
        if pos < 0:
            continue
        fix = unfold_span(p.text, src, pos, pos + len(fk))
        if SENTINEL in fix:
            continue  # sentinel 은 접기에서 제거되지 않으므로 여기 올 수 없지만, 방어
        return KeyVerdict(key, "fixable", fix=fix, paragraph=p.number, display=display_with_marks(p))
    # ctrl — 컨트롤을 지우면 맞는다 → 키를 컨트롤 앞뒤로 나눠라
    for p in paras:
        if not p.has_ctrl:
            continue
        stripped = _ctrl_stripped(p)
        ft, src = fold_map(stripped)
        pos = ft.find(fk)
        if pos < 0:
            continue
        # stripped 오프셋 → 원문 오프셋: sentinel 을 건너뛴 만큼 보정
        start_s, end_s = src[pos][0], src[pos + len(fk) - 1][1]
        orig_start = _stripped_to_orig(p.text, start_s)
        orig_end = _stripped_to_orig(p.text, end_s - 1) + 1
        span = p.text[orig_start:orig_end]
        parts = [s.strip() for s in span.split(SENTINEL) if s.strip()]
        return KeyVerdict(key, "ctrl", paragraph=p.number, display=display_with_marks(p), parts=parts)
    # multi — 연속 문단을 합친 키 → 문단별로 나눠라
    mv = _find_multi(fk, paras)
    if mv is not None:
        return mv
    return KeyVerdict(key, "missing")


def _stripped_to_orig(text: str, k: int) -> int:
    """sentinel 을 제거한 문자열의 오프셋 k → 원문 오프셋."""
    seen = 0
    for i, c in enumerate(text):
        if c == SENTINEL:
            continue
        if seen == k:
            return i
        seen += 1
    return len(text)


def _find_multi(fk: str, paras: list[Para]) -> KeyVerdict | None:
    folded = [(p, *fold_map(p.text)) for p in paras]
    n = len(folded)
    for i in range(n):
        p_i, f_i, src_i = folded[i]
        if not f_i:
            continue
        max_l = min(len(f_i), len(fk) - 1)
        for L in range(max_l, 0, -1):
            if not fk.startswith(f_i[-L:]):
                continue
            remaining = fk[L:]
            parts = [unfold_span(p_i.text, src_i, len(f_i) - L, len(f_i))]
            j = i + 1
            ok = False
            while j < n and j <= i + MULTI_WINDOW:
                p_j, f_j, src_j = folded[j]
                if not f_j:
                    j += 1
                    continue
                if remaining.startswith(f_j):
                    parts.append(p_j.text.strip())
                    remaining = remaining[len(f_j) :]
                    if not remaining:
                        ok = True
                        break
                    j += 1
                    continue
                if f_j.startswith(remaining):
                    parts.append(unfold_span(p_j.text, src_j, 0, len(remaining)))
                    ok = True
                    break
                break
            if ok:
                return KeyVerdict(fk, "multi", paragraph=p_i.number, paragraph_end=folded[j][0].number, parts=parts)
    return None


@dataclass
class CheckResult:
    verdicts: list[KeyVerdict]

    @property
    def ok(self) -> bool:
        return all(v.cls == "ok" for v in self.verdicts)

    def to_json(self) -> dict:
        groups: dict[str, list] = {"ok": [], "fixable": [], "ctrl": [], "multi": [], "missing": []}
        for v in self.verdicts:
            groups[v.cls].append(v.to_json())
        return {"ok": self.ok, "summary": {k: len(v) for k, v in groups.items()}, "keys": groups}


def check_mapping(mapping: dict[str, Value], paras: list[Para]) -> CheckResult:
    verdicts = []
    for key in mapping:
        v = classify_key(key, paras)
        v.key = key  # multi 는 접은 키로 판정했으므로 원래 키를 되돌린다
        verdicts.append(v)
    return CheckResult(verdicts)


def fixed_mapping(mapping: dict[str, Value], result: CheckResult) -> dict[str, Value]:
    """fixable 만 교정안(원문 부분문자열)으로 바꾼 매핑. 값은 그대로."""
    fixes = {v.key: v.fix for v in result.verdicts if v.cls == "fixable" and v.fix}
    out: dict[str, Value] = {}
    for k, val in mapping.items():
        out[fixes.get(k, k)] = val
    return out


def fix_collisions(mapping: dict[str, Value], result: CheckResult) -> dict[str, list[str]]:
    """교정하면 같은 자리로 겹치는 키 그룹 {교정안: [원래 키…]}.

    두 키가 같은 원문 부분문자열로 접히면 `fixed_mapping` 의 dict 대입이 앞 항목을 조용히 덮어써 값이 소실된다
    (Codex R2 F9). 그래서 --fix 는 충돌이 있으면 쓰지 않고 collision 으로 보고한다 — 사람이 키를 나눠야 한다."""
    fixes = {v.key: v.fix for v in result.verdicts if v.cls == "fixable" and v.fix}
    targets: dict[str, list[str]] = {}
    for key in mapping:
        targets.setdefault(fixes.get(key, key), []).append(key)
    return {t: ks for t, ks in targets.items() if len(ks) > 1}


def format_verdict(v: KeyVerdict) -> str:
    if v.cls == "ok":
        return f"ok\t{v.key}\tx{v.count}"
    if v.cls == "fixable":
        return f"fixable\t{v.key}\t→ {v.fix}\t(문단 {v.paragraph}: {v.display})"
    if v.cls == "ctrl":
        return f"ctrl\t{v.key}\t문단 {v.paragraph} 이 컨트롤을 품고 있습니다 — 키를 컨트롤 앞뒤로 나누세요: {v.parts}\t({v.display})"
    if v.cls == "multi":
        return f"multi\t{v.key}\t문단 {v.paragraph}~{v.paragraph_end} 을 합친 키입니다 — 문단별로 나누세요: {v.parts}"
    return f"missing\t{v.key}"


# ---- residue ------------------------------------------------------------------

SIGNIFICANT_MIN = 8
_LETTER_RE = re.compile(r"[가-힣A-Za-z]")
_WS_RE = re.compile(r"\s+")


# 자리표시 마커(괄호/이중중괄호/겹화살괄호) — --list 후보와 같은 규약(cli 가 이 정의를 쓴다)
PLACEHOLDER_RE = re.compile(r"\([^()<>{}\n]{1,40}\)|\{\{[^{}<>\n]{1,40}\}\}|《[^《》<>\n]{1,40}》")
RESIDUE_MARKER_RE = re.compile(r"\{\{[^{}<>\n]{1,40}\}\}|《[^《》<>\n]{1,40}》")
PAREN_MARKER_RE = re.compile(r"\([^()<>{}\n]{1,40}\)")
# 안내문 신호 — **명령형 어미** 또는 **자리표시 기호**만 본다. 단독 어휘(작성·예시·입력…)는 쓰지 않는다:
# 실 한컴 저장본(multi_image_formats)에서 '자기성장기록서 작성 및 제출(매월)'·'통계 작성'·'자기성장기록서 매월
# 작성·제출' 같은 정상 본문 5문단이 전부 잔재로 위장됐다(Codex R2 F4 실측).
# '예시' 도 뺐다 — 같은 파일의 '* 매칭 성향(예시) : 인구·사회학적 특성…' 은 본문이 예를 드는 문장이지
# "여기에 예시처럼 쓰라"가 아니다. 실제 안내문의 예시 줄은 대개 자리표시 기호(○○·___)를 함께 쓴다.
_GUIDANCE_VERB = r"(?:입력|작성|기재|기입|첨부|제출|표시|기술)"
_GUIDANCE_END = r"(?:하세요|하십시오|해\s*주세요|해\s*주십시오|바랍니다|요망|할\s*것)"
GUIDANCE_WORD_RE = re.compile(
    _GUIDANCE_VERB + r"\s*(?:하시기\s*)?" + _GUIDANCE_END
    + r"|써\s*주세요|적으세요|적어\s*주세요|적어\s*주시기\s*바랍니다"
    + r"|여기에"
    + r"|○○|OO|XX|△△|□□|_{3,}|…|\.{3,}"
)


def is_significant(text: str) -> bool:
    t = _WS_RE.sub("", text)
    return len(t) >= SIGNIFICANT_MIN and bool(_LETTER_RE.search(t))


def is_guidance_like(text: str) -> bool:
    """원본 문단이 '안내문 후보'인가 — 자리표시 마커를 품거나 안내 어휘를 담은 문단만 잔재 규칙 ②의 대상이다.

    초판은 유의미 문단 전부를 대상으로 삼아 실 양식(multi_section_with_image)에서 잔재 174건·자기 자신 대조도
    exit 2 를 냈다(2026-09-06 selfcheck 실측) — 바뀌지 않은 라벨·본문·법정 문구가 전부 '잔재'로 위장됐다.
    안내문 후보로 좁히되, 키가 닿은 문단의 세그먼트 규칙 ③은 그대로 둔다(문단 안 안내문 둘 중 하나만 바뀐 경우)."""
    # 괄호 마커는 보통 산문의 괄호("(단위 : 명)")와 구별되지 않아 잔재 후보에서 뺀다(--list 후보에는 그대로 쓴다).
    return bool(RESIDUE_MARKER_RE.search(text) or GUIDANCE_WORD_RE.search(text))


@dataclass
class ResidueItem:
    kind: str  # key | paragraph | segment | value_missing
    text: str
    paragraph: int

    def to_json(self) -> dict:
        return {"kind": self.kind, "text": self.text, "paragraph": self.paragraph}


def marker_shapes(keys: list[str]) -> set[str]:
    """매핑 키가 실제로 쓰는 자리표시 **모양** — 세그먼트 잔재 판정의 게이트다.

    양식마다 규약이 다르므로(괄호 `(성명)` · 이중중괄호 · 겹화살괄호) 사용자가 무엇을 채웠는지가 그 문서의
    규약이다. 괄호는 산문에도 흔해서(`(결원보충 방법 및 신규임용)`) 무조건 신호로 쓰면 문장 안 부분문자열
    키를 정상적으로 쓴 실행이 exit 2 가 된다(Claude R2 C-F4 실측). 그래서 **키가 그 모양을 쓸 때만** 인정한다.
    """
    shapes: set[str] = set()
    for key in keys:
        if RESIDUE_MARKER_RE.search(key):
            shapes.add("marker")
        if PAREN_MARKER_RE.search(key):
            shapes.add("paren")
    return shapes


def is_segment_residue_candidate(text: str, shapes: set[str]) -> bool:
    """세그먼트가 잔재 후보인가 — 안내 어미를 갖거나, **매핑이 쓰는 모양의** 자리표시를 품었을 때."""
    if is_guidance_like(text):
        return True
    if "marker" in shapes and RESIDUE_MARKER_RE.search(text):
        return True
    return "paren" in shapes and bool(PAREN_MARKER_RE.search(text))


def _segments(text: str, keys: list[str]) -> list[str]:
    """원본 문단을 매핑 키로 잘라 만든 세그먼트(키 자리 제외). 키가 하나도 없으면 빈 목록."""
    claimed: list[tuple[int, int]] = []
    for key in keys:
        if not key:
            continue
        idx = 0
        while True:
            pos = text.find(key, idx)
            if pos < 0:
                break
            idx = pos + len(key)
            if any(pos < e and s < idx for s, e in claimed):
                continue
            claimed.append((pos, idx))
    if not claimed:
        return []
    claimed.sort()
    segs: list[str] = []
    cursor = 0
    for s, e in claimed:
        segs.append(text[cursor:s])
        cursor = e
    segs.append(text[cursor:])
    return [s for s in segs if s.strip()]


def find_residue(
    orig_paras: list[Para], result_paras: list[Para], mapping: dict[str, Value], keep: list[str]
) -> tuple[list[ResidueItem], dict[str, int]]:
    """잔재 = ① 매핑 키(placeholder 원문)가 결과에 남음 ② 원본의 안내문 후보 문단(유의미 8자+ 이고 마커·명령형 어미 보유)이 결과에 부분문자열로 남음
    ③ 원본 문단을 매핑 키로 잘라 만든 세그먼트(8자+ **이고 안내 어미·자리표시 마커 보유**)가 남음(문단 안 안내문 둘 중 하나만 바뀐 경우, Codex R1 F9)
    ④ **커버리지** — 원본에 있던 키의 치환값이 결과에 없음(kind=value_missing, Codex R2 F3).

    ④ 가 없으면 "키가 사라졌는가" 만 보므로 **전혀 무관하거나 빈 결과 파일도 통과**한다(fail-open).
    반환값: (잔재 목록, coverage{keys_in_original, values_found})."""
    keys = list(mapping)
    shapes = marker_shapes(keys)
    result_blob = "\n".join(p.text for p in result_paras if p.text)
    items: list[ResidueItem] = []
    seen: set[str] = set()

    def kept(s: str) -> bool:
        return any(k and k in s for k in keep)

    left_keys: set[str] = set()
    for key in keys:
        if key and SENTINEL not in key and key in result_blob and not kept(key) and key not in seen:
            seen.add(key)
            left_keys.add(key)
            where = next((p.number for p in orig_paras if key in p.text), 0)
            items.append(ResidueItem("key", key, where))
    coverage = {"keys_in_original": 0, "values_found": 0}
    for key, value in mapping.items():
        if not key or SENTINEL in key:
            continue
        where = next((p.number for p in orig_paras if key in p.text), None)
        if where is None:
            continue  # 원본에 없던 키 — 커버리지 대상이 아니다(--check 가 missing 으로 잡는다)
        coverage["keys_in_original"] += 1
        if key in left_keys:
            continue  # 키가 그대로 남아 있음 — 이미 ① 로 보고했다(중복 보고 금지)
        values = value if isinstance(value, list) else [value]
        missing = [v for v in values if v and v not in result_blob]
        if not missing:
            coverage["values_found"] += 1
            continue
        for v in missing:
            if v not in seen:
                seen.add(v)
                items.append(ResidueItem("value_missing", v, where))
    for p in orig_paras:
        text = p.text.strip()
        if not text:
            continue
        if is_significant(text) and is_guidance_like(text) and text in result_blob and not kept(text) and text not in seen:
            seen.add(text)
            items.append(ResidueItem("paragraph", text, p.number))
            continue
        for seg in _segments(p.text, keys):
            s = seg.strip()
            if not is_segment_residue_candidate(s, shapes):
                continue
            if is_significant(s) and s in result_blob and not kept(s) and s not in seen:
                seen.add(s)
                items.append(ResidueItem("segment", s, p.number))
    return items, coverage
