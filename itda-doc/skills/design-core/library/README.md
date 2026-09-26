# design-core 토큰 라이브러리 — ready-to-use v2 프리셋

> **유명 서구 브랜드 톤**("스포티파이 느낌"·"스트라이프처럼")은 본 라이브러리가 아니라 **getdesign 표준 DESIGN.md 차용**이 우선이다(`../SKILL.md` getdesign-first 워크플로우·`../schema/design-md-standard.md`, #1021). 본 라이브러리는 **결정론 토큰(v2)** 프리셋 — 코드 소비(dockit·sheetkit)·반복 파이프라인용이자, getdesign 에 없는 한국·문서 톤 커버리지다. 표준 포맷의 한국 확장 카탈로그는 `../catalog/`.

DESIGN.md 미제공 시(또는 "컨설팅 느낌"·"다크 트레이딩 톤" 같은 톤 키워드만 있을 때) 이 디렉토리에서 주제 적합 프리셋 1종을 골라 **그대로 DESIGN.md 로 적용**한다. 각 프리셋은 **색·평면 기하·레이아웃·모티프** 등 매체 중립 토큰 서브셋(재현도 높은 축)을 담으며, 매체별 어댑터가 이를 소비한다(PPTX 재현 세부·한계: `../../pptx-design/references/design-md-mapping.md`).

조직 브랜드 적용은 프리셋을 복사해 `colors`(v2 `color`) hex 만 바꾸는 것이 가장 빠른 출발점이다. 작성 후 `scripts/validate.py` 로 검증한다(design-core `SKILL.md` 참조).

## 선택 표

| 프리셋 | 톤 | 핵심 축 | 잘 맞는 주제 | 의미색 기본 |
|---|---|---|---|---|
| `consulting-mbb.md` | 라이트(다크 샌드위치) | 네이비 `1E2761` + 아이스 `CADCFC`, 킥커 칩·푸터 규율 | 전략·IR·임원 보고·주가/시장 분석 | international |
| `equity-research-dark.md` | 다크 | 블랙 `0B0E11` + 옐로 `F0B90B` 희소 액센트, mono 숫자 | 트레이딩·시장 모니터링·온체인 | international (krx 토글) |
| `warm-editorial.md` | 라이트(크림↔다크 교차) | 크림 `FAF9F5` + 코랄 `CC785C` + 틸 `5DB8A6` | 데이터 리포트·에디토리얼·신뢰 서사 | international |
| `print-broadsheet.md` | 라이트(페이퍼) | 페이퍼 `F4F1EA` + 잉크 `111111` + 잉크블루 `0047AB` 단일 액센트 | 저널·심층 분석·인쇄 감각 | international |
| `tech-vivid-dark.md` | 다크 | 다크 `121212` + 비비드 그린 `1ED760` + glow 모티프 | 미디어·콘텐츠·테크 몰입형 | international |
| `minimal-mono.md` | 라이트(갤러리) | 모노크롬 `171A20` + 단일 액센트 `3E6AE1`, 거대 타이포·여백 | 프리미엄·제품 런칭·비전 | international |
| `samsung-sds.md` | 라이트(코퍼레이트) | 삼성 블루 `1428A0` + 라이트 블루 보조, 절제된 그리드 | 기업 IT·B2B·IR·기술 발표 | international |
| `kari.md` | 다크/딥블루(우주) | 딥스페이스 네이비 `0A1430` + 시안 액센트, 우주 모티프 | 정부출연연·항공우주·연구 성과 | international |

## 프리셋 frontmatter 계약 (v1 평면 키 — `design_core` 가 v2 로 자동 승격)

- `colors`: `canvas`·`surface`·`ink`·`muted`·`primary`·`accent`·`hairline`·`up`·`down` (hex) → v2 `color.{bg,surface,fg,muted,primary,accent,border}` + `semantic.{up,down}`
- `typography`: `display`(라틴/숫자 전용 — 한글은 어댑터 가드가 안전 고딕 강제) · `body` → v2 `font.{display,body}`
- `semantic_convention`: `international`(상승=그린/하락=레드) 또는 `krx`(상승=레드/하락=블루) → v2 `semantic.convention`
- `rounded`(비율 0~0.5) · `spacing`(인치) · `motif`(한 문장) · `do`/`dont` → v2 `radius.base` · `space` · `motif` · `editorial`
- 본문: Overview → 슬라이드 문법(표지·요약·차트·그리드·클로징 레시피) → Do/Don't

> 한글 주의: 모든 프리셋의 `typography.display` 는 **라틴/숫자 전용**이다. 한글 run 은 매체 어댑터의 **CJK 가드**가 안전 고딕을 강제한다(PPTX: `kr_font_name()` — `constraints.pptx.cjk_guard`). 음수 `letterSpacing`·thin weight 는 프리셋에 넣지 않는다(한글=필터). 계층·검증은 `../schema/token-layers.md`.
