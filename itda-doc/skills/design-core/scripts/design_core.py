"""design-core: 매체 중립 디자인 토큰 로더·정규화·조회 (SPEC-DESIGN-CORE-001).

DESIGN.md(frontmatter YAML + 본문)를 v1(평면) 또는 v2(계층) 형식으로 받아
정규화된 토큰 모델(DesignTokens)로 반환한다. PPTX·웹·카드뉴스 어댑터가
공통으로 소비하는 SSOT 진입점이다.

설계 원칙:
- 매체 중립: 본 모듈은 어떤 매체 API(python-pptx 등)도 import 하지 않는다.
- 역호환: v1 평면 frontmatter(colors/typography/...)를 v2 계층으로 승격한다.
- 어댑터 경계: PPTX 등 매체별 변환은 to_pptx_palette() 같은 얇은 역매핑으로만.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - 의존성 누락 시 명확한 안내
    yaml = None

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_SCRIPTS_DIR)
LIBRARY_DIR = os.path.join(_SKILL_ROOT, "library")

# ── v1(현행 평면) → v2(계층) 매핑 (SPEC §5.2) ────────────────────────────
_V1_COLOR_TO_V2 = {
    "canvas": "bg",
    "surface": "surface",
    "ink": "fg",
    "muted": "muted",
    "primary": "primary",
    "accent": "accent",
    "hairline": "border",
}
_V1_SEMANTIC_KEYS = ("up", "down")

# 계층별 필수 토큰 (SPEC §5.1)
A1_IDENTITY_COLORS = ("bg", "surface", "fg", "muted", "primary", "accent", "border")
A1_IDENTITY_FONTS = ("display", "body")
A2_SEMANTIC = ("up", "down")

# B-slot: 상위 sibling 에 alias (브랜드가 풍부한 tier 없으면 var 대체)
_BSLOT_ALIAS = {
    "surface_2": "surface",
    "fg_2": "fg",
    "border_soft": "border",
}

# C-extension allowlist (브랜드 전용, 미등록 키는 advisory)
C_EXTENSION_ALLOWLIST = ("motif", "editorial", "kicker_style", "chart_hint")

# constraints.pptx 기본 프로필 — CJK 가드 승격 (REQ-007)
DEFAULT_PPTX_CONSTRAINTS = {
    "cjk_guard": True,            # 음수 자간→0 클램프, 세리프/thin 한글 필터, kr_font_name 강제
    "gradient": "pillow-bake",    # python-pptx 네이티브 그라디언트 없음 → Pillow PNG 베이크
    "motion": "unsupported",      # 정적 포맷
    "opentype": "unsupported",    # tnum/ss01 등 미적용
    "fallback_fonts": {"korean": ["Noto Sans KR", "Pretendard"]},
}

# constraints.docx 기본 프로필 — East Asian 폰트 바인딩 계약 (SPEC-OFFICE-DOC-GEN-DEEPEN-001)
#
# pptx 의 cjk_guard 와 의도가 다르다. pptx 가드는 LibreOffice 의 한글 세리프/붓글씨
# 폴백을 막으려는 것이지만, Word 는 한글을 네이티브로 정상 렌더한다. 따라서 docx 의
# 핵심은 "음수 자간 클램프"가 아니라 run 의 w:rFonts 를 ascii/hAnsi(라틴) ↔ eastAsia
# (한글)로 분리 바인딩하는 정확성이다(라틴 디스플레이 폰트가 한글 글리프를 먹지 않게).
DEFAULT_DOCX_CONSTRAINTS = {
    "eastasia_guard": True,       # 한글 run → eastAsia 안전 고딕, 라틴은 ascii/hAnsi 분리 바인딩
    "page_size": "A4",            # 문서 매체 기본(인쇄 A4). 어댑터가 letter 로 덮어쓸 수 있음
    "opentype": "supported",      # Word 는 tnum/커닝 등 OpenType 지원(pptx/LibreOffice 와 차이)
    # eastAsia 후보 — 어댑터(dockit.kr_font_name)가 첫 존재 폰트를 선택. Windows Word 기본은
    # Malgun Gothic(항상 존재·한글 또렷), 크로스플랫폼/LibreOffice 프리뷰는 Noto Sans KR·Pretendard.
    "fallback_fonts": {"korean": ["Malgun Gothic", "맑은 고딕", "Noto Sans KR", "Pretendard"]},
}

# constraints.xlsx 기본 프로필 — 셀 한글 폰트 가드 (SPEC-OFFICE-DOC-GEN-DEEPEN-001 P5)
#
# Excel 은 run/cell 레벨 ascii↔eastAsia 분리 바인딩이 없다(셀 폰트는 단일 이름). 따라서
# xlsx 의 한글 정책은 "한글이 담긴 셀의 폰트를 Korean-capable 폰트로 보장"하는 것이다
# (라틴 디스플레이 폰트가 셀에 박혀 한글이 의도와 다른 폴백으로 렌더되는 것 차단).
DEFAULT_XLSX_CONSTRAINTS = {
    "kr_font_guard": True,        # 한글 셀 → Korean-capable 폰트 보장
    "thousands": True,            # 천단위 콤마 숫자서식 기본
    "fallback_fonts": {"korean": ["Malgun Gothic", "맑은 고딕", "Noto Sans KR", "Pretendard"]},
}

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def is_hex(value: Any) -> bool:
    """문자열이 유효한 #RGB/#RRGGBB hex 인지."""
    return isinstance(value, str) and bool(_HEX_RE.match(value.strip()))


# ── frontmatter 파싱 ─────────────────────────────────────────────────────
def parse_design_md(text: str) -> tuple[dict, str]:
    """DESIGN.md 텍스트에서 (frontmatter dict, 본문 str) 분리.

    `---` 로 감싼 선두 YAML 블록을 frontmatter 로 본다. 없으면 ({}, 전체).
    """
    if yaml is None:
        raise RuntimeError(
            "design-core 는 PyYAML 이 필요합니다. `pip install -r requirements.txt`"
        )
    stripped = text.lstrip("﻿")  # BOM 방어
    if not stripped.startswith("---"):
        return {}, text
    parts = stripped.split("\n", 1)
    if len(parts) < 2:
        return {}, text
    rest = parts[1]
    end = rest.find("\n---")
    if end == -1:
        return {}, text
    fm_text = rest[:end]
    body = rest[end + 4:]  # '\n---' 다음
    # 본문 선두의 잔여 개행/구분 정리
    body = body.lstrip("\n")
    data = yaml.safe_load(fm_text) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter 가 매핑(dict)이 아닙니다.")
    return data, body


def _is_v2(fm: dict) -> bool:
    """frontmatter 가 v2(계층) 형식인지 판별."""
    if fm.get("schema_version") == 2:
        return True
    # v2 시그니처: color/font/space 계층 키 존재 & v1 평면 키 부재
    has_v2 = any(k in fm for k in ("color", "font", "space", "constraints"))
    has_v1 = any(k in fm for k in ("colors", "typography"))
    return has_v2 and not has_v1


# ── 정규화 (v1/v2 → v2 표준 dict) ────────────────────────────────────────
def normalize(fm: dict) -> dict:
    """frontmatter(v1 평면 또는 v2 계층)를 v2 표준 토큰 dict 로 정규화.

    반환 구조:
      meta, color{}, semantic{}, font{}, type_scale{}, space{}, radius{},
      layout{}, component{}, motif, editorial{do,dont}, constraints{pptx,web}
    """
    if _is_v2(fm):
        norm = _normalize_v2(fm)
    else:
        norm = _normalize_v1(fm)
    _inject_defaults(norm)
    return norm


def _normalize_v1(fm: dict) -> dict:
    colors = fm.get("colors", {}) or {}
    typo = fm.get("typography", {}) or {}
    color: dict[str, Any] = {}
    for v1k, v2k in _V1_COLOR_TO_V2.items():
        if v1k in colors:
            color[v2k] = colors[v1k]
    semantic: dict[str, Any] = {
        "convention": fm.get("semantic_convention", "international"),
    }
    for k in _V1_SEMANTIC_KEYS:
        if k in colors:
            semantic[k] = colors[k]
    spacing = fm.get("spacing", {}) or {}
    norm = {
        "meta": {
            "preset": fm.get("preset"),
            "version": fm.get("version"),
            "description": fm.get("description"),
            "schema_version": 1,  # 원본은 v1
        },
        "color": color,
        "semantic": semantic,
        "font": {
            "display": typo.get("display"),
            "body": typo.get("body"),
        },
        "type_scale": fm.get("type_scale", {}) or {},
        "space": {
            "margin": spacing.get("margin"),
            "gap": spacing.get("gap"),
        },
        "radius": {"base": fm.get("rounded")},
        "layout": fm.get("layout", {}) or {},
        "component": fm.get("component", {}) or {},
        "motif": fm.get("motif"),
        "editorial": {
            "do": list(fm.get("do", []) or []),
            "dont": list(fm.get("dont", []) or []),
        },
        "constraints": fm.get("constraints", {}) or {},
    }
    return norm


def _normalize_v2(fm: dict) -> dict:
    editorial = fm.get("editorial", {}) or {}
    norm = {
        "meta": {
            "preset": fm.get("preset") or fm.get("brand"),
            "version": fm.get("version"),
            "description": fm.get("description"),
            "schema_version": 2,
        },
        "color": dict(fm.get("color", {}) or {}),
        "semantic": dict(fm.get("semantic", {}) or {}),
        "font": dict(fm.get("font", {}) or {}),
        "type_scale": dict(fm.get("type_scale", {}) or {}),
        "space": dict(fm.get("space", {}) or {}),
        "radius": dict(fm.get("radius", {}) or {}),
        "layout": dict(fm.get("layout", {}) or {}),
        "component": dict(fm.get("component", {}) or {}),
        "motif": fm.get("motif"),
        "editorial": {
            "do": list(editorial.get("do", []) or []),
            "dont": list(editorial.get("dont", []) or []),
        },
        "constraints": dict(fm.get("constraints", {}) or {}),
    }
    norm["semantic"].setdefault("convention", "international")
    return norm


def _inject_defaults(norm: dict) -> None:
    """누락된 A2/constraints 기본값 주입 (derive 단계 대용)."""
    # B-slot alias 해소: 누락 시 상위 sibling 값으로 채움
    color = norm["color"]
    for slot, parent in _BSLOT_ALIAS.items():
        if slot not in color and parent in color:
            color[slot] = color[parent]  # 동일 값으로 alias(자기완결 토큰)
    # constraints.pptx 기본 프로필 병합 (명시값 우선)
    constraints = norm["constraints"]
    pptx = dict(DEFAULT_PPTX_CONSTRAINTS)
    pptx.update(constraints.get("pptx", {}) or {})
    constraints["pptx"] = pptx
    # constraints.docx 기본 프로필 병합 (명시값 우선)
    docx = dict(DEFAULT_DOCX_CONSTRAINTS)
    docx.update(constraints.get("docx", {}) or {})
    constraints["docx"] = docx
    # constraints.xlsx 기본 프로필 병합 (명시값 우선)
    xlsx = dict(DEFAULT_XLSX_CONSTRAINTS)
    xlsx.update(constraints.get("xlsx", {}) or {})
    constraints["xlsx"] = xlsx
    constraints.setdefault("web", {})


# ── 토큰 모델 ────────────────────────────────────────────────────────────
@dataclass
class DesignTokens:
    """정규화된 v2 토큰 접근 래퍼."""
    raw: dict
    body: str = ""

    @property
    def meta(self) -> dict:
        return self.raw.get("meta", {})

    @property
    def color(self) -> dict:
        return self.raw.get("color", {})

    @property
    def semantic(self) -> dict:
        return self.raw.get("semantic", {})

    @property
    def font(self) -> dict:
        return self.raw.get("font", {})

    @property
    def space(self) -> dict:
        return self.raw.get("space", {})

    @property
    def layout(self) -> dict:
        return self.raw.get("layout", {})

    @property
    def constraints(self) -> dict:
        return self.raw.get("constraints", {})

    @property
    def name(self) -> str | None:
        return self.meta.get("preset")

    def pptx_palette(self) -> dict:
        return to_pptx_palette(self)

    def pptx_layout(self) -> dict:
        return to_pptx_layout(self)

    def docx_styles(self) -> dict:
        return to_docx_styles(self)

    def xlsx_styles(self) -> dict:
        return to_xlsx_styles(self)


# ── 로더 ─────────────────────────────────────────────────────────────────
def load(source: str | dict) -> DesignTokens:
    """프리셋 이름 | 파일 경로 | frontmatter dict | DESIGN.md 텍스트를 로드.

    - dict          → frontmatter 로 간주, 정규화.
    - 존재 파일 경로 → 읽어서 파싱·정규화.
    - 'consulting-mbb' 같은 이름 → library/<name>.md 로드.
    - '---' 로 시작하는 긴 문자열 → DESIGN.md 텍스트로 파싱.
    """
    if isinstance(source, dict):
        return DesignTokens(raw=normalize(source), body="")
    if isinstance(source, str) and source.lstrip().startswith("---") and "\n" in source:
        fm, body = parse_design_md(source)
        return DesignTokens(raw=normalize(fm), body=body)
    path = source
    if not os.path.isfile(path):
        cand = os.path.join(LIBRARY_DIR, source if source.endswith(".md") else f"{source}.md")
        if os.path.isfile(cand):
            path = cand
        else:
            raise FileNotFoundError(f"디자인 토큰을 찾을 수 없습니다: {source}")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    fm, body = parse_design_md(text)
    return DesignTokens(raw=normalize(fm), body=body)


def list_presets() -> list[str]:
    """library/ 의 프리셋 이름 목록(README 제외)."""
    if not os.path.isdir(LIBRARY_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(LIBRARY_DIR)):
        if fn.endswith(".md") and fn.upper() != "README.MD":
            out.append(fn[:-3])
    return out


# ── PPTX 어댑터 역매핑 (deckkit 호환 평면 팔레트) ─────────────────────────
def to_pptx_palette(tokens: DesignTokens) -> dict:
    """v2 토큰 → 기존 deckkit/build.py 가 기대하는 평면 hex 팔레트.

    이주 전 프리셋 frontmatter(colors.*)와 1:1 동치를 보장한다(AC-02).
    """
    c = tokens.color
    s = tokens.semantic
    return {
        "canvas": c.get("bg"),
        "surface": c.get("surface"),
        "ink": c.get("fg"),
        "muted": c.get("muted"),
        "primary": c.get("primary"),
        "accent": c.get("accent"),
        "hairline": c.get("border"),
        "up": s.get("up"),
        "down": s.get("down"),
    }


# ── PPTX 레이아웃 어댑터 (three_zone·grid·space → deckkit 좌표 헬퍼 입력, #701/#702 P0) ──
DEFAULT_PPTX_LAYOUT = {
    "three_zone": {"header": 0.14, "content": 0.76, "footer": 0.10},
    "grid": {"columns": 12, "gutter": 0.2},
}


def to_pptx_layout(tokens: "DesignTokens") -> dict:
    """v2 `layout`(three_zone·grid) + `space` → deckkit 좌표 헬퍼가 소비하는 평면 레이아웃.

    `layout` 토큰은 그간 스키마에만 있고 어떤 어댑터도 읽지 않던 dormant 상태였다(#701):
    `frontmatter-schema-vs-prose` 규칙상 "machine 이 안 읽는 값"이었다. 본 함수가
    deckkit `zone_bounds()`/`grid_cells()` 의 입력 계약이 되어 토큰을 살린다(machine 소비 승격).
    미지정 시 표준 보고서 기본(DEFAULT_PPTX_LAYOUT)으로 떨어져, 기존 자유 배치 gen.py 는 비파괴.

    반환 키:
      margin_in, gap_in        : 상하·요소 간 여백(인치, space 토큰; 미정의면 None)
      three_zone {header, content, footer} : 수직 분할 비율(합 1.0 정규화)
      grid {columns, gutter}   : 본문 균일 그리드(열 수·거터 인치)
    """
    lay = tokens.layout
    sp = tokens.space
    tz = dict(DEFAULT_PPTX_LAYOUT["three_zone"])
    for k, v in (lay.get("three_zone") or {}).items():
        if k in tz and isinstance(v, (int, float)) and v >= 0:
            tz[k] = float(v)
    total = sum(tz.values()) or 1.0
    tz = {k: v / total for k, v in tz.items()}  # 합 1.0 정규화(비율 안정)
    grid = dict(DEFAULT_PPTX_LAYOUT["grid"])
    for k, v in (lay.get("grid") or {}).items():
        if k in grid and v is not None:
            grid[k] = v
    return {
        "margin_in": sp.get("margin"),
        "gap_in": sp.get("gap"),
        "three_zone": tz,
        "grid": grid,
    }


# ── Web 어댑터 (CSS custom properties — pptx 와 대조되는 가벼운 텍스트 경로) ──
def _font_stack(name, kfonts):
    """폰트명 → CSS font-family 스택. 한글 안전 폰트를 fallback 으로 동반(CJK 가드의 web 판)."""
    ko = ", ".join(f'"{x}"' if " " in x else x for x in (kfonts or []))
    if name == "kr-safe-gothic":
        return (ko + ", sans-serif") if ko else "system-ui, sans-serif"
    base = f'"{name}"' if name and " " in name else (name or "system-ui")
    return f"{base}, {ko}, sans-serif" if ko else f"{base}, sans-serif"


def to_css_vars(tokens: DesignTokens, selector: str = ":root") -> str:
    """v2 토큰 → CSS custom properties (web 어댑터, 결정론적 출력).

    pptx 의 무거운 deckkit/LibreOffice 파이프라인과 달리 web 은 텍스트 CSS 라,
    이 가벼운 함수(또는 에이전트가 `mapping/web-css.md` 보고 직접 생성)로 충분하다.
    한글 본문 폰트는 fallback_fonts.korean 스택으로 펼쳐 web 에서도 CJK 안전성을 유지한다.
    """
    c, s, f = tokens.color, tokens.semantic, tokens.font
    kfonts = (tokens.constraints.get("pptx", {}).get("fallback_fonts", {}) or {}).get("korean", [])
    radius = tokens.raw.get("radius", {}).get("base")
    rows = [
        ("--bg", c.get("bg")), ("--surface", c.get("surface")),
        ("--surface-2", c.get("surface_2", c.get("surface"))),
        ("--fg", c.get("fg")), ("--muted", c.get("muted")),
        ("--primary", c.get("primary")), ("--accent", c.get("accent")),
        ("--border", c.get("border")),
        ("--success", s.get("up")), ("--danger", s.get("down")),
        ("--font-display", _font_stack(f.get("display"), kfonts)),
        ("--font-body", _font_stack(f.get("body"), kfonts)),
    ]
    if radius is not None:
        rows.append(("--radius", f"{round(float(radius) * 3, 3)}rem"))
    body = "\n".join(f"  {k}: {v};" for k, v in rows if v is not None)
    return f"{selector} {{\n{body}\n}}\n"


# ── 색 대비 유틸 (매체 중립 — 어떤 매체 API 도 import 안 함) ────────────────
def _h6(value) -> str:
    """'#1E2761' / '1e2761' / '#abc' → 'RRGGBB'(대문자 6자리)."""
    h = str(value or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return ((h or "000000") + "000000")[:6].upper()


def _rgb_tuple(value) -> tuple[int, int, int]:
    h = _h6(value)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rel_lum(value) -> float:
    """WCAG 상대 휘도(0..1)."""
    def _lin(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb_tuple(value)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(c1, c2) -> float:
    """WCAG 명도 대비비(1.0..21.0)."""
    l1, l2 = _rel_lum(c1), _rel_lum(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def is_dark_color(value, threshold: float = 0.18) -> bool:
    """배경 hex 가 다크인지(상대 휘도 < threshold)."""
    return _rel_lum(value) < threshold


def mix(c1, c2, t: float) -> str:
    """c1↔c2 선형 보간(t=0→c1, t=1→c2) → '#RRGGBB'. 채널은 0..255 로 클램프."""
    a, b = _rgb_tuple(c1), _rgb_tuple(c2)
    m = tuple(max(0, min(255, int(round(a[i] + (b[i] - a[i]) * t)))) for i in range(3))
    return "#%02X%02X%02X" % m


def readable_on(text_color, bg_color, ratio: float = 4.5) -> str:
    """text_color 를 bg_color 위에서 ratio 이상 대비가 되도록 (필요 시 어둡게) 보정.

    이미 대비를 만족하면 **원본을 그대로 반환**(대비 충족 토큰 무변경 — consulting 등
    회귀 가드 통과). 미달이면 RGB 를 비례 축소(hue 보존)하며 어둡게 해 ratio 를 만족하는
    첫 값을 찾는다. docx/xlsx 본문은 라이트 배경이므로 "어둡게 = 대비 증가".
    주의: 라이트 프리셋이라도 **sub-대비 토큰은 보정된다**(예: warm-editorial 의 저대비
    up·테라코타 브랜드텍스트는 가독을 위해 어두워짐 — fill 용 primary 원본은 불변).
    """
    if not text_color:
        return text_color
    if contrast_ratio(text_color, bg_color) >= ratio:
        return text_color
    r, g, b = _rgb_tuple(text_color)
    f = 1.0
    while f > 0:
        cand = "#%02X%02X%02X" % (int(r * f), int(g * f), int(b * f))
        if contrast_ratio(cand, bg_color) >= ratio:
            return cand
        f -= 0.03
    return "#000000"


# 본문 라이트(샌드위치) 정규화 — docx/xlsx 공용.
#   매체 한계상 docx 페이지 배경·xlsx 기본 시트는 항상 라이트(흰색)다(python-docx 는
#   페이지 배경 미지원, Word/Excel 인쇄 배경은 출력 안 됨). 따라서 다크 프리셋이라도
#   본문 영역은 라이트로 렌더된다. 본 헬퍼는 **본문 텍스트 토큰**(ink/muted/primary_text/
#   up/down)을 흰 배경 대비로 보정하고, **본문 채움면**(surface/surface_2/border = zebra·
#   패널·헤어라인)을 라이트 틴트로 낮춘다. 표지·클로징의 다크/브랜드 밴드는 호출측이
#   primary(브랜드)·ink(다크) 를 fill 로 써서 별도 유지하고, 밴드 글자색은 on_color 가
#   자동 선택한다(SPEC-OFFICE-DOC-GEN-DEEPEN-001 — 다크 프리셋 docx/xlsx 샌드위치 정책).
_SANDWICH_BODY_BG = "#FFFFFF"


def _sandwich_palette(c: dict, s: dict) -> dict:
    bg = c.get("bg") or "#FFFFFF"
    fg = c.get("fg") or "#222222"
    muted = c.get("muted") or "#5C6470"
    primary = c.get("primary") or fg
    surface = c.get("surface") or "#F2F2F2"
    surface_2 = c.get("surface_2", surface) or surface
    border = c.get("border") or "#D9DEE8"
    up, down = s.get("up"), s.get("down")
    dark = is_dark_color(bg)
    body = _SANDWICH_BODY_BG
    # 본문 채움면(zebra/패널/헤어라인) 먼저 — 다크 프리셋은 브랜드 틴트의 라이트 면으로,
    # 라이트 프리셋은 원본 유지.
    if dark:
        surf = mix(primary, body, 0.93)
        surf2 = mix(primary, body, 0.88)
        bord = mix(primary, body, 0.72)
    else:
        surf, surf2, bord = surface, surface_2, border
    # 대비 기준 = 가장 어두운 라이트 본문 배경(surf2). 텍스트는 흰 본문뿐 아니라
    # zebra/콜아웃 패널(surf/surf2) 위에도 올라가므로, 흰색이 아니라 surf2 를 기준으로
    # 보정해 라이트 패널에서도 마진을 확보한다(#668: 흰색 기준이면 zebra 위 의미색이
    # 3:1 미만으로 떨어지는 회귀를 차단).
    ref = surf2
    # 다크 프리셋 본문 잉크는 라이트 fg 를 깎은 회색이 아니라 프리셋의 다크 캔버스(bg)를
    # 그대로 — 또렷한 근-검정 + 브랜드 색조. 라이트 프리셋은 fg(어두움) 그대로.
    ink_src = bg if dark else fg
    return {
        "is_dark": dark,
        "ink": readable_on(ink_src, ref, 7.0),
        "muted": readable_on(muted, ref, 4.5),
        "primary_text": readable_on(primary, ref, 4.5),  # 4.5 → 본문 강조/헤딩이 verify advisory(4.5) 도 통과
        "up": readable_on(up, ref, 3.5) if up else up,
        "down": readable_on(down, ref, 3.5) if down else down,
        "surface": surf,
        "surface_2": surf2,
        "border": bord,
    }


# ── DOCX 어댑터 역매핑 (dockit 호환 평면 스타일) ──────────────────────────
def to_docx_styles(tokens: DesignTokens) -> dict:
    """v2 토큰 → docx-design(dockit) 어댑터가 소비하는 평면 스타일 dict.

    매체 중립 원칙 유지 — 본 함수는 어떤 Word API 도 import 하지 않는다. 색은 토큰
    원본(`#RRGGBB`)을 그대로 넘기고(dockit 이 RGBColor 로 변환), 한글은 실제 폰트명을
    여기서 고정하지 않고 `constraints.docx.fallback_fonts.korean` **후보 리스트**만 넘긴다
    (어댑터가 환경에서 첫 존재 폰트를 선택 — kr_font_name 책임 경계).

    반환 키:
      page_bg, ink, muted, primary, accent, surface, surface_2, border, up, down (hex)
      convention                : 의미색 관행(international|krx)
      latin_font                : 라틴/숫자 디스플레이 폰트(eastAsia 아님)
      body_font                 : 본문 폰트 센티널('kr-safe-gothic') 또는 라틴 본문
      korean_fallbacks          : eastAsia 바인딩 후보(어댑터가 첫 존재 폰트 선택)
      eastasia_guard            : 한글 run eastAsia 분리 바인딩 활성 여부
      margin_in, gap_in         : 페이지 여백·문단 간격(인치)
      type_scale                : 헤딩 스케일(있으면)
      page_size                 : 페이지 크기(A4|letter)
    """
    c, s, f = tokens.color, tokens.semantic, tokens.font
    docx_c = tokens.constraints.get("docx", {}) or {}
    kfonts = (docx_c.get("fallback_fonts", {}) or {}).get("korean", [])
    sw = _sandwich_palette(c, s)
    return {
        "page_bg": c.get("bg"),               # 식별용 캔버스(다크 프리셋 원본) — 본문 배경 아님
        "ink": sw["ink"],                     # 본문 텍스트(흰 배경 대비 보정)
        "muted": sw["muted"],                 # 보조 텍스트(보정)
        "primary": c.get("primary"),          # 브랜드 — 표지/헤더/밴드 fill 용(원본)
        "primary_text": sw["primary_text"],   # 브랜드 텍스트(헤딩/강조, 흰 배경 대비 보정)
        "accent": c.get("accent"),
        "surface": sw["surface"],             # 본문 zebra/패널 fill(다크 프리셋은 라이트 틴트)
        "surface_2": sw["surface_2"],
        "border": sw["border"],
        "up": sw["up"],
        "down": sw["down"],
        "is_dark": sw["is_dark"],             # 다크 프리셋 여부(샌드위치 정책·검증 가드용)
        "convention": s.get("convention", "international"),
        "latin_font": f.get("display"),
        "body_font": f.get("body"),
        "korean_fallbacks": list(kfonts),
        "eastasia_guard": bool(docx_c.get("eastasia_guard", True)),
        "margin_in": tokens.space.get("margin"),
        "gap_in": tokens.space.get("gap"),
        "type_scale": dict(tokens.raw.get("type_scale", {}) or {}),
        "page_size": docx_c.get("page_size", "A4"),
    }


# ── XLSX 어댑터 역매핑 (sheetkit 호환 평면 스타일) ────────────────────────
def to_xlsx_styles(tokens: DesignTokens) -> dict:
    """v2 토큰 → xlsx-design(sheetkit) 어댑터가 소비하는 평면 스타일 dict.

    매체 중립 유지 — openpyxl 등 어떤 Excel API 도 import 하지 않는다. 색은 토큰
    원본(`#RRGGBB`)을 그대로 넘기고(sheetkit 이 ARGB 로 변환), 한글 폰트는 후보 리스트만
    넘긴다(sheetkit 의 kr_font_name 이 환경에서 선택 — 매체 경계 유지).

    반환 키:
      page_bg, ink, muted, primary, accent, surface, surface_2, border, up, down (hex)
      convention                : 의미색 관행(international|krx)
      latin_font                : 라틴/숫자 디스플레이 폰트(제목/헤더 라틴)
      body_font                 : 본문 폰트 센티널('kr-safe-gothic') 또는 라틴 본문
      korean_fallbacks          : 한글 셀 폰트 후보(어댑터가 첫 존재 폰트 선택)
      kr_font_guard             : 한글 셀 Korean-capable 폰트 보장 여부
      chart_palette             : 차트 시리즈 색 시퀀스(primary→accent→up→down→muted)
      type_scale                : 타이포 스케일(있으면)
    """
    c, s, f = tokens.color, tokens.semantic, tokens.font
    xlsx_c = tokens.constraints.get("xlsx", {}) or {}
    kfonts = (xlsx_c.get("fallback_fonts", {}) or {}).get("korean", [])
    # 차트 시리즈는 원본(비비드) 색 — 흰 배경 위에서도 또렷, 본문 텍스트 보정과 무관
    chart = [x for x in (c.get("primary"), c.get("accent"), s.get("up"),
                         s.get("down"), c.get("muted")) if x]
    sw = _sandwich_palette(c, s)
    return {
        "page_bg": c.get("bg"),               # 식별용 캔버스(원본) — 기본 시트는 라이트
        "ink": sw["ink"],                     # 셀 텍스트(흰 배경 대비 보정)
        "muted": sw["muted"],
        "primary": c.get("primary"),          # 브랜드 — 타이틀/헤더 fill 용(원본)
        "primary_text": sw["primary_text"],   # 브랜드 텍스트(타이틀/강조, 보정)
        "accent": c.get("accent"),
        "surface": sw["surface"],             # zebra/패널 fill(다크 프리셋은 라이트 틴트)
        "surface_2": sw["surface_2"],
        "border": sw["border"],
        "up": sw["up"],
        "down": sw["down"],
        "is_dark": sw["is_dark"],
        "convention": s.get("convention", "international"),
        "latin_font": f.get("display"),
        "body_font": f.get("body"),
        "korean_fallbacks": list(kfonts),
        "kr_font_guard": bool(xlsx_c.get("kr_font_guard", True)),
        "chart_palette": chart,
        "type_scale": dict(tokens.raw.get("type_scale", {}) or {}),
    }
