# design-core — 브랜드 디자인 허브 (표준 DESIGN.md + 결정론 토큰)

브랜드 디자인을 **고르고(getdesign 표준 DESIGN.md 카탈로그 차용), 만들고(한국·자사 브랜드 저작), 여러 매체(웹·PPTX·DOCX·XLSX)에 일관 적용**하는 허브 스킬입니다(#1021). 두 레이어를 관리합니다: ① **표준 DESIGN.md**(Google Stitch 9섹션 — 직해석, 1회성 산출 정본) ② **v2 토큰**(opendesign 4계층 계약 — 코드 소비·반복 파이프라인, SPEC-DESIGN-CORE-001).

## 구성

| 경로 | 역할 |
|---|---|
| `schema/design-md-standard.md` | 표준 DESIGN.md(Stitch) 차용·직해석·저작 가이드 + CJK Addendum 템플릿 |
| `catalog/` | 한국 확장 카탈로그 — getdesign 에 없는 브랜드의 표준 포맷 저작물(samsung-sds 등) |
| `library/` | v2 토큰 프리셋 8종(코드 소비·반복 파이프라인). 선택 표: `library/README.md` |
| `schema/design-md-v2.md` | v2 토큰 그룹·constraints 명세(코드 소비용 dialect) |
| `schema/token-layers.md` | A1-identity/A1-structure/A2/B-slot + C-extension allowlist |
| `mapping/pptx.md`·`docx.md`·`xlsx.md`·`web-css.md` | v2 → 매체 어댑터 매핑 (가동) |
| `mapping/cardnews.md` | 후속 매체 어댑터 (구조 스텁) |
| `scripts/design_core.py` | v2 토큰 로더·정규화(v1→v2)·조회 |
| `scripts/validate.py` | v2 계층·hex·대비·CJK·allowlist 검증기 |

## 빠른 시작

```bash
# macOS/Linux (Windows: py -3)
python3 -m pip install -r requirements.txt          # PyYAML
python3 scripts/validate.py --all                   # library 전체 검증
python3 -c "import sys; sys.path.insert(0,'scripts'); import design_core as dc; print(dc.load('consulting-mbb').pptx_palette())"
```

## 매체 경로

- **웹/HTML**: 표준 DESIGN.md **원문 참조**가 정본(getdesign 본래 용도) — Claude 가 직접 렌더. v2 `to_css_vars()`(`mapping/web-css.md`, `examples/web/`)는 결정론 브랜드 전환용 보조.
- **PPTX**: 형제 스킬 `pptx-design` 이 표준 DESIGN.md 원문 또는 v2 프리셋을 deckkit 으로 렌더(무거운 어댑터 필수 — Claude 가 `.pptx` 를 직접 못 만듦).
- **DOCX/XLSX**: 형제 스킬 `docx-design`·`xlsx-design` — 1회성은 원문 직해석, 반복 파이프라인은 `docx_styles()`/`xlsx_styles()`(v2).
- **카드뉴스**: 후속 SPEC (현재 `mapping/cardnews.md` 스텁).

## 설계 원칙

매체 중립 — 본 스킬은 python-pptx 등 매체 API 를 import 하지 않습니다. 매체별 제약은 `constraints.<media>` 프로필로 선언하고 렌더는 각 어댑터가 책임집니다. 한글은 `constraints.pptx.cjk_guard` 로 안전 고딕·자간을 보호합니다.

## 라이선스

Apache-2.0
