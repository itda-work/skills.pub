# design-core 토큰(v2) 스키마

매체 독립 디자인 토큰의 frontmatter 명세. v1 평면 형식(`colors`/`typography`/...)도 `design_core.normalize()` 가 v2 로 자동 승격하므로(legacy 무중단), 신규 작성은 v2 를 권장하되 v1 도 유효하다. 계층 의미는 `token-layers.md` 참조.

> ⚠️ **본 v2 는 코드 소비용 dialect 다** — `design_core.load()` 를 거쳐 dockit(docx)·sheetkit(xlsx) 등 코드 렌더러가 결정론 토큰을 요구하는 **반복 파이프라인** 전용. **Google Stitch 표준 DESIGN.md**(9섹션 산문 + 확장 frontmatter — getdesign.md 카탈로그)와는 이름만 비슷한 **별개 포맷**이며, 표준 파일은 `load()` 대상이 아니다(자동 매핑이 원문을 깎는다 — 직해석이 정본, `design-md-standard.md` §비교표·#1021).

## 토큰 그룹

### `color` (A1-identity)

| 키 | 의미 | 형식 |
|---|---|---|
| `bg` | 페이지 배경(브랜드 캔버스) | hex |
| `surface` | 카드/패널 배경 | hex |
| `fg` | 본문 텍스트 | hex |
| `muted` | 보조 텍스트·캡션 | hex |
| `primary` | 브랜드 지배색(시각 비중 60~70%) | hex |
| `accent` | 강조색(화면당 ≤2 가시 사용 권장) | hex |
| `border` | 기본 테두리·헤어라인 | hex |
| `surface_2`·`fg_2`·`border_soft` | (B-slot) 풍부 tier. 생략 시 상위 alias | hex |

### `semantic` (A2)

| 키 | 의미 |
|---|---|
| `up` / `down` | 상승/하락 의미색 (hex) |
| `convention` | `international`(상승=그린/하락=레드) 또는 `krx`(상승=레드/하락=블루) |

### `font` (A1-identity)

| 키 | 의미 |
|---|---|
| `display` | 디스플레이/제목용 라틴·숫자 stack |
| `body` | 본문 stack. 한글은 `kr-safe-gothic` 센티널 권장(어댑터 CJK 가드가 안전 고딕 강제) |

### `type-scale` (A1-structure, 선택)

`display`/`title`/`body`/`caption` 각각에 `size_pt`(PPTX)·`size_px`(웹)·`weight`·`lineHeight`·`letterSpacing` 와 라틴/CJK 분리 표기. 1차(PPTX) 는 size·weight 만 소비.

### `space` (A1-structure)

`margin`·`gap`(인치, PPTX 기준). 웹 환산용 `base_unit`(px, 예 `"8px"`) 선택.

### `radius` (A2)

`base`(비율 0~0.5, pill=0.5). PPTX adjustments 제약상 px 위계는 비율 근사.

### `layout` (A1-structure, 선택)

`grid`(columns·gutter), `breakpoints`(mobile/tablet/desktop — 웹 어댑터용, PPTX 무시), `three_zone`(header/content/footer 비율 — PPTX·웹 공통).

### `component` (B-slot, 선택 — 1차 스키마만)

`button`·`card` 등을 토큰 참조(`{color.primary}` 등)로 정의. 1차 PPTX 어댑터는 미사용(후속 웹 어댑터 대비).

### `motif` (C-extension)

반복 시각 요소를 한 문장으로(예: "소형 네이비 킥커 칩 + 푸터 헤어라인").

### `editorial` (C-extension)

`do`/`dont` 리스트. 매체 무관 에디토리얼 규칙.

### `constraints` (매체 프로필)

매체별 표현 제약. **렌더는 어댑터가 책임지고, 여기선 선언만** 한다.

```yaml
constraints:
  pptx:
    cjk_guard: true                 # 음수 자간→0 클램프, 세리프/thin 한글 필터, kr_font_name 강제
    gradient: pillow-bake           # python-pptx 네이티브 그라디언트 없음 → Pillow PNG
    motion: unsupported             # 정적 포맷
    opentype: unsupported           # tnum/ss01 미적용
    fallback_fonts:
      korean: ["Noto Sans KR", "Pretendard"]
  web: {}                           # 기본 제약 없음
```

> `constraints.pptx` 는 명시하지 않으면 `design_core` 가 위 기본 프로필을 자동 주입한다.

## v1 → v2 매핑 (값 보존)

| v1 평면 | v2 | 계층 |
|---|---|---|
| `colors.canvas` | `color.bg` | A1-identity |
| `colors.surface/ink/muted/primary/accent` | `color.surface/fg/muted/primary/accent` | A1-identity |
| `colors.hairline` | `color.border` | A1-identity |
| `colors.up`/`colors.down` | `semantic.up`/`semantic.down` | A2 |
| `typography.display`/`body` | `font.display`/`body` | A1-identity |
| `rounded` | `radius.base` | A2 |
| `spacing.{margin,gap}` | `space.{margin,gap}` | A1-structure |
| `semantic_convention` | `semantic.convention` | A1-structure |
| `motif`·`do`·`dont` | `motif`·`editorial.{do,dont}` | C-extension |

## 최소 v2 예시

```yaml
---
schema_version: 2
brand: acme
description: ACME 코퍼레이트 블루
color:
  bg: "#FFFFFF"
  surface: "#F4F7FC"
  fg: "#10203A"
  muted: "#5C6470"
  primary: "#0B57D0"
  accent: "#7CA8F0"
  border: "#D9DEE8"
semantic:
  convention: international
  up: "#0E7C4A"
  down: "#C0392B"
font:
  display: "Helvetica Neue"
  body: "kr-safe-gothic"
space: { margin: 0.8, gap: 0.35 }
radius: { base: 0.1 }
motif: "primary 1px 헤어라인 + 좌상단 로고 락업 반복"
editorial:
  do: ["제목은 주장형 문장", "수치엔 출처"]
  dont: ["팔레트 외 색", "그림자 남용"]
---
```
