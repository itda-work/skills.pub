"""design-core 토큰 검증기 (SPEC-DESIGN-CORE-001 REQ-003).

검증 항목:
  (a) 계층 무결성 — A1-identity 색·폰트 필수(누락 ERROR), A2 의미색 권장(advisory).
  (b) 색 hex 유효성 — A1 은 ERROR, B-slot/확장은 advisory.
  (c) 대비 — bg/fg·surface/fg WCAG AA(4.5:1) 미달 advisory.
  (d) CJK constraints — cjk_guard↔fallback_fonts 정합, body 세리프/명조 휴리스틱 advisory.
  (e) C-extension allowlist — 미등록 최상위 frontmatter 키 advisory.

CLI:
  python validate.py <name|path ...>   # 지정 토큰 검증
  python validate.py --all             # library/ 전체
종료코드: ERROR 1건 이상이면 1, 아니면 0.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design_core as dc  # noqa: E402

# allowlist: 알려진 표준 최상위 키 ∪ C-extension allowlist
KNOWN_TOP_KEYS = {
    # 메타
    "preset", "brand", "version", "description", "schema_version", "license",
    # v1 평면
    "colors", "typography", "semantic_convention", "rounded", "spacing", "do", "dont",
    # v2 계층
    "color", "semantic", "font", "type_scale", "space", "radius", "layout",
    "component", "editorial", "constraints",
    # C-extension allowlist
    "motif", "kicker_style", "chart_hint",
}

_SERIF_HINTS = ("serif", "myungjo", "명조", "batang", "바탕", "gungsuh", "궁서", "song", "송")


@dataclass
class Issue:
    level: str  # "ERROR" | "WARN"
    code: str
    message: str


@dataclass
class ValidationResult:
    name: str
    issues: list = field(default_factory=list)

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.level == "WARN"]

    @property
    def ok(self) -> bool:
        return not self.errors


# ── WCAG 대비 ────────────────────────────────────────────────────────────
def _luminance(hexv: str) -> float:
    h = hexv.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(h1: str, h2: str) -> float:
    l1, l2 = _luminance(h1), _luminance(h2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ── 검증 ─────────────────────────────────────────────────────────────────
def validate(source) -> ValidationResult:
    issues: list[Issue] = []
    name = str(source)
    raw_fm = None
    try:
        tokens = dc.load(source)
        if isinstance(source, dict):
            raw_fm = source
        else:
            path = source if os.path.isfile(str(source)) else None
            if path is None:
                cand = os.path.join(
                    dc.LIBRARY_DIR,
                    source if str(source).endswith(".md") else f"{source}.md",
                )
                path = cand if os.path.isfile(cand) else None
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    raw_fm, _ = dc.parse_design_md(f.read())
                name = os.path.splitext(os.path.basename(path))[0]
        if tokens.name:
            name = tokens.name
    except Exception as e:  # noqa: BLE001
        return ValidationResult(name=name, issues=[Issue("ERROR", "load", f"로드 실패: {e}")])

    color = tokens.color
    sem = tokens.semantic
    font = tokens.font

    # (a)+(b) A1-identity 색
    for k in dc.A1_IDENTITY_COLORS:
        v = color.get(k)
        if v is None:
            issues.append(Issue("ERROR", "missing-a1-color", f"A1-identity 색 누락: color.{k}"))
        elif not dc.is_hex(v):
            issues.append(Issue("ERROR", "bad-hex", f"유효하지 않은 hex: color.{k}={v!r}"))
    for k, v in color.items():
        if k in dc.A1_IDENTITY_COLORS:
            continue
        if v is not None and not dc.is_hex(v):
            issues.append(Issue("WARN", "bad-hex", f"hex 아님(B-slot/확장): color.{k}={v!r}"))

    # (a) A1-identity 폰트
    for k in dc.A1_IDENTITY_FONTS:
        if not font.get(k):
            issues.append(Issue("ERROR", "missing-font", f"A1-identity 폰트 누락: font.{k}"))

    # (a)+(b) A2 의미색
    for k in dc.A2_SEMANTIC:
        v = sem.get(k)
        if v is None:
            issues.append(Issue("WARN", "missing-semantic", f"의미색 권장: semantic.{k}"))
        elif not dc.is_hex(v):
            issues.append(Issue("ERROR", "bad-hex", f"유효하지 않은 hex: semantic.{k}={v!r}"))
    conv = sem.get("convention")
    if conv not in ("international", "krx"):
        issues.append(Issue("WARN", "convention", f"semantic.convention 은 international|krx 권장: {conv!r}"))

    # (c) 대비
    bg, fg, surface = color.get("bg"), color.get("fg"), color.get("surface")
    if dc.is_hex(bg) and dc.is_hex(fg):
        cr = contrast_ratio(bg, fg)
        if cr < 4.5:
            issues.append(Issue("WARN", "contrast", f"본문 대비 부족(bg/fg {cr:.1f}:1 < 4.5 WCAG AA)"))
    if dc.is_hex(surface) and dc.is_hex(fg):
        cr = contrast_ratio(surface, fg)
        if cr < 4.5:
            issues.append(Issue("WARN", "contrast", f"surface 대비 부족(surface/fg {cr:.1f}:1 < 4.5)"))

    # (d) CJK constraints
    pptx = tokens.constraints.get("pptx", {}) or {}
    if pptx.get("cjk_guard"):
        fb = (pptx.get("fallback_fonts") or {}).get("korean")
        if not fb:
            issues.append(Issue("WARN", "cjk", "constraints.pptx.cjk_guard=true 인데 fallback_fonts.korean 미정의"))
    body = (font.get("body") or "").lower()
    if any(h in body for h in _SERIF_HINTS):
        issues.append(Issue("WARN", "cjk-body-font",
                            f"body 폰트가 세리프/명조 계열로 보임: {font.get('body')!r} (한글 가독성 위험)"))

    # (e) C-extension allowlist
    if isinstance(raw_fm, dict):
        for k in raw_fm:
            if k not in KNOWN_TOP_KEYS:
                issues.append(Issue("WARN", "unknown-key", f"미등록 최상위 키(C-extension allowlist 외): {k}"))

    return ValidationResult(name=name, issues=issues)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="design-core 토큰 검증기")
    ap.add_argument("targets", nargs="*", help="프리셋 이름 또는 DESIGN.md 경로")
    ap.add_argument("--all", action="store_true", help="library/ 전체 검증")
    args = ap.parse_args(argv)

    targets = args.targets
    if args.all or not targets:
        targets = dc.list_presets()
    if not targets:
        print("검증 대상이 없습니다. (library/ 비어있음)")
        return 0

    total_err = 0
    total_warn = 0
    for t in targets:
        r = validate(t)
        status = "✅ GREEN" if r.ok else "❌ ERROR"
        print(f"\n[{status}] {r.name}")
        for i in r.issues:
            mark = "  ✗" if i.level == "ERROR" else "  ·"
            print(f"{mark} {i.level} {i.code}: {i.message}")
        total_err += len(r.errors)
        total_warn += len(r.warnings)

    print(f"\n— 합계: ERROR {total_err} · advisory {total_warn} · 대상 {len(targets)}종")
    return 1 if total_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
