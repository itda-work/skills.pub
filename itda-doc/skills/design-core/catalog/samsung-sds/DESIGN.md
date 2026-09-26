---
version: alpha
name: samsung-sds-corporate
description: 삼성SDS 류 기업 IT·B2B·IR 표면의 코퍼레이트 디자인 — Samsung Blue(#1428A0)가 시각 비중 60~70%를 지배하는 화이트 캔버스 위 절제된 그리드. 대문자 영문 킥커, 주장형(액션 타이틀) 헤드라인, 1px 헤어라인 규율, 모든 수치에 출처 라인을 다는 IR 신뢰 문법이 정체성이다. 장식·그림자·그라데이션 없이 반복되는 구조(같은 위치의 킥커·푸터·헤어라인)가 신뢰를 만든다. 한글 우선 브랜드 — Pretendard 단일 스택으로 한글·라틴을 함께 처리하고, 영문 킥커·숫자만 Helvetica Neue 를 병용한다.

colors:
  primary: "#1428A0"
  primary-light: "#5B8DEF"
  on-primary: "#FFFFFF"
  canvas: "#FFFFFF"
  surface: "#EEF2FB"
  ink: "#14181F"
  muted: "#5C6470"
  hairline: "#D5DBE8"
  chart-compare-blue: "#6E84CF"
  chart-compare-gray: "#A9B2C3"
  success: "#0E7C4A"
  danger: "#C0392B"

typography:
  display-xl:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.5px
  display-lg:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 36px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.3px
  title-lg:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0
  title-md:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  kicker:
    fontFamily: "Helvetica Neue, Pretendard, sans-serif"
    fontSize: 13px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 1.5px
  body-md:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: 0
  body-sm:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  caption:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0.2px
  stat-number:
    fontFamily: "Helvetica Neue, Pretendard, sans-serif"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: -0.5px
  button:
    fontFamily: "Pretendard, Noto Sans KR, sans-serif"
    fontSize: 14px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: 0.3px

rounded:
  none: 0px
  xs: 2px
  sm: 4px

spacing:
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 40px
  xxl: 64px
  section: 96px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.xs}"
    padding: 12px 24px
    height: 44px
  button-outline:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.button}"
    rounded: "{rounded.xs}"
    border: 1px solid {colors.primary}
    padding: 12px 24px
    height: 44px
  kicker-label:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.kicker}"
  hero-band:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.display-xl}"
    padding: 64px
  section-header:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.display-lg}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
    rounded: "{rounded.sm}"
    border: 1px solid {colors.hairline}
    padding: 24px
  stat-cell:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    typography: "{typography.stat-number}"
    border-top: 1px solid {colors.hairline}
    padding: 16px 0
  data-table-header:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-sm}"
    padding: 10px 12px
  data-table-zebra:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
  source-footer:
    backgroundColor: transparent
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
    border-top: 1px solid {colors.hairline}
    padding: 12px 0
---

## Visual Theme & Atmosphere

화이트 캔버스(`{colors.canvas}`) 위에서 Samsung Blue(`{colors.primary}` — #1428A0, PMS 286C)가 시각 비중 60~70%를 지배하는 **절제된 코퍼레이트 시스템**이다. 브랜드 에너지는 장식이 아니라 **규율**에서 나온다: 모든 표면에서 같은 위치에 반복되는 대문자 영문 킥커, 주장형(액션 타이틀) 헤드라인, 1px 헤어라인(`{colors.hairline}`), 그리고 수치가 등장하는 모든 자리에 붙는 출처 라인. 그림자·그라데이션·입체 효과는 쓰지 않는다 — 플랫 헤어라인 시스템이 곧 신뢰의 시각 언어다.

표면 리듬은 **블루 샌드위치**: 도입(히어로/표지)과 마무리(클로징/CTA)는 Samsung Blue 풀블리드, 본문은 화이트 + 아이스 블루(`{colors.surface}`) 패널 교차. 본문 한가운데 넓은 블루 면을 깔지 않는다.

**Key Characteristics:**
- Samsung Blue 지배(60~70%) + 라이트 블루(`{colors.primary-light}`) 보조 — 팔레트 밖 색 없음
- 대문자 영문 킥커(`{typography.kicker}`, 1.5px 트래킹) + 주장형 한글 헤드라인의 짝
- 1px 헤어라인 규율 — 구획·표·푸터 전부 헤어라인, 그림자 0
- 모든 수치 표면에 출처 라인(`자료: …`) — IR 신뢰 문법
- 한글 우선: Pretendard 단일 스택(한글·라틴 통합), Helvetica Neue 는 영문 킥커·큰 숫자 전용

## Color Palette & Roles

### Brand
- **Samsung Blue** (`{colors.primary}` — #1428A0): 지배색. 히어로/클로징 배경, 헤드라인 강조, 버튼, 표 헤더, 차트 주 시리즈. 공개 CI Blue(PMS 286C / RGB 20,40,160) 참조.
- **Light Blue** (`{colors.primary-light}` — #5B8DEF): 보조 전용 — 보조 막대·패널 강조 칩·링크 호버. 지배색을 침범하지 않는다.
- **On Primary** (`{colors.on-primary}` — #FFFFFF): 블루 면 위 텍스트.

### Surface
- **Canvas** (`{colors.canvas}` — #FFFFFF): 본문 기본 배경.
- **Surface** (`{colors.surface}` — #EEF2FB): 카드·패널·표 zebra 행의 아이스 블루 틴트.

### Text
- **Ink** (`{colors.ink}` — #14181F): 본문·헤드라인 기본.
- **Muted** (`{colors.muted}` — #5C6470): 보조 텍스트·캡션·출처 라인.

### Lines
- **Hairline** (`{colors.hairline}` — #D5DBE8): 유일한 구획 장치. 1px 고정.

### Chart & Semantic
- **비교군 시리즈**: 주인공은 Samsung Blue, 비교군은 `{colors.chart-compare-blue}`(#6E84CF)·`{colors.chart-compare-gray}`(#A9B2C3) — 위계는 채도로 만든다. 기본 파랑/주황 조합 금지.
- **Success / Danger** (`{colors.success}` #0E7C4A / `{colors.danger}` #C0392B): 상승·하락, 긍정·경고. 기본 international 관행(krx 전환은 Addendum 참조).

## Typography Rules

### Font Families
정본은 **Pretendard**(fallback: Noto Sans KR) — 한글·라틴을 한 스택으로 처리하는 한글 우선 브랜드다. **Helvetica Neue** 는 대문자 영문 킥커와 큰 숫자(`{typography.stat-number}`)에만 병용해 "글로벌 IT" 결을 만든다.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `{typography.display-xl}` | 48px | 700 | 1.15 | -0.5px | 히어로 헤드라인(주장형 문장) |
| `{typography.display-lg}` | 36px | 700 | 1.2 | -0.3px | 섹션 헤드 |
| `{typography.title-lg}` | 24px | 700 | 1.3 | 0 | 카드 타이틀·소섹션 |
| `{typography.title-md}` | 20px | 600 | 1.4 | 0 | 카드 부제·리드 문단 |
| `{typography.kicker}` | 13px | 700 | 1.3 | 1.5px | 대문자 영문 킥커("EXECUTIVE SUMMARY") |
| `{typography.stat-number}` | 32px | 700 | 1.1 | -0.5px | KPI 빅넘버 |
| `{typography.body-md}` | 16px | 400 | 1.65 | 0 | 본문 |
| `{typography.body-sm}` | 14px | 400 | 1.6 | 0 | 표 본문·보조 문단 |
| `{typography.caption}` | 12px | 400 | 1.4 | 0.2px | 출처 라인·캡션 |
| `{typography.button}` | 14px | 700 | 1.0 | 0.3px | 버튼 라벨 |

### Principles
- 헤드라인은 **주장형 문장**(액션 타이틀)으로 쓴다 — "클라우드 전환 현황"이 아니라 "클라우드 전환이 비용 구조를 바꿨다".
- 큰 한글 디스플레이의 음수 자간은 -0.5px 까지만(과도한 음수 금지 — Addendum).
- 본문은 400 유지 — Light(300) 본문을 쓰지 않는다(한글 가독).

## Component Stylings

- **`{component.hero-band}`** — Samsung Blue 풀블리드 밴드. 상단에 킥커(화이트, 투명도 80%), 중앙에 `{typography.display-xl}` 주장형 헤드라인(화이트), 하단에 KPI 스트립 3~4종(라벨 작게·숫자 크게, 헤어라인 구분).
- **`{component.button-primary}`** — Samsung Blue 채움 + 화이트 라벨, `{rounded.xs}`(2px — 거의 직각). **`{component.button-outline}`** — 1px 블루 아웃라인 + 블루 라벨.
- **`{component.kicker-label}`** — 대문자 영문, 블루, 1.5px 트래킹. 모든 섹션 헤드 위에 반복.
- **`{component.card}`** — `{colors.surface}` 배경 + 헤어라인 테두리, `{rounded.sm}`(4px), 24px 패딩. 번호 칩(01/02/03) + 볼드 소제목 + 1~2줄 본문 구성의 2×3 그리드가 정석.
- **`{component.stat-cell}`** — 헤어라인 상단 경계 + Samsung Blue 빅넘버(`{typography.stat-number}`) + muted 라벨. 3~4개 나열한 KPI 레일.
- **`{component.data-table-header}`** — Samsung Blue 채움 + 화이트 헤더. 본문 행은 화이트/`{colors.surface}` zebra 교차 + 헤어라인. 숫자 열은 우측 정렬 + 천단위 콤마.
- **`{component.source-footer}`** — 헤어라인 위 좌측 `자료: …`(muted caption), 우측 페이지/구획 표시. **수치가 있는 모든 표면에 필수.**

## Layout Principles

- **Spacing scale**: 8px 기수 — `{spacing.xs}` 8 · `{spacing.sm}` 12 · `{spacing.md}` 16 · `{spacing.lg}` 24 · `{spacing.xl}` 40 · `{spacing.xxl}` 64 · `{spacing.section}` 96.
- **그리드**: 본문 최대 폭 ~1200px, 12컬럼. 카드 그리드는 데스크톱 3-up(또는 2×3), 태블릿 2-up, 모바일 1-up.
- **여백 철학**: 절제된 균질 여백 — 섹션 간 `{spacing.section}`(96px) 고정. 본문을 가운데 정렬하지 않는다(좌측 정렬 규율).
- **반복 구조**: 킥커 → 헤드라인 → 본문/그리드 → 출처 푸터의 수직 리듬을 모든 섹션에서 유지.

## Depth & Elevation

| Level | Treatment | Use |
|---|---|---|
| Flat | 배경색만 | 본문·히어로·클로징 |
| Hairline | 1px `{colors.hairline}` | 구획·카드 테두리·표·푸터 |
| Tint | `{colors.surface}` 패널 | 카드·zebra — "높이"가 아니라 "영역" |

그림자·blur·입체 효과 없음. 깊이는 블루 샌드위치(진한 도입/마무리 ↔ 밝은 본문)의 명도 대비가 만든다.

## Do's and Don'ts

### Do
- 제목은 주장형 문장(액션 타이틀) — Samsung Blue 헤드라인 또는 잉크 헤드라인 + 블루 강조.
- primary(블루) 시각 비중 60~70%, `{colors.primary-light}` 는 보조 막대·패널에만.
- 모든 수치 표면에 출처 라인(`자료: …`) — IR 신뢰 규율.
- 도입·마무리는 블루, 본문은 화이트(샌드위치).
- 차트 주 시리즈는 Samsung Blue, 비교군은 채도 낮춘 블루·그레이.

### Don't
- 제목 밑 액센트 라인(AI 슬라이드 전형) 금지.
- 팔레트 외 색 추가·그라데이션 남용 금지.
- 그림자·입체 효과 금지(플랫 헤어라인 시스템 유지).
- 본문 가운데 정렬 금지.
- Light(300) 본문·과도한 음수 자간 금지(한글 가독 — Addendum).

## Responsive Behavior

| Name | Width | Key Changes |
|---|---|---|
| Mobile | < 768px | 카드 1-up, KPI 스트립 2×2, 히어로 헤드라인 48→32px |
| Tablet | 768–1024px | 카드 2-up, 표는 가로 스크롤 컨테이너 |
| Desktop | > 1024px | 12컬럼 풀 그리드, 카드 3-up, 본문 최대 1200px |

- 터치 타깃: 버튼 높이 44px(최소 준수).
- 표는 축소하지 않고 컨테이너 내 가로 스크롤로 보존(숫자 가독 우선).

## Agent Prompt Guide

### Quick Color Reference
- 배경: `#FFFFFF` / 패널: `#EEF2FB` / 텍스트: `#14181F` / 보조 텍스트: `#5C6470`
- 브랜드: `#1428A0`(지배) / `#5B8DEF`(보조) / 헤어라인: `#D5DBE8`
- 의미색: 상승 `#0E7C4A` / 하락 `#C0392B` (krx 전환 시 반전 — Addendum)

### Example Component Prompts
- "히어로 밴드: #1428A0 풀블리드, 상단 대문자 영문 킥커(13px/700/1.5px 트래킹, 화이트 80%), 중앙 주장형 한글 헤드라인 48px/700 화이트, 하단 KPI 3종(라벨 12px muted, 숫자 32px/700)."
- "카드 그리드 2×3: #EEF2FB 배경 + 1px #D5DBE8 테두리 + 4px 라운드, 번호 칩(01~06, #1428A0), 볼드 소제목 20px/600, 본문 2줄 14px #5C6470."
- "데이터 표: 헤더 #1428A0 채움 + 화이트 14px, 본문 화이트/#EEF2FB zebra, 숫자 우측 정렬 + 천단위 콤마, 표 아래 '자료: …' 캡션 12px #5C6470."

### Iteration Guide
1. 새 섹션은 킥커 → 헤드라인 → 본문 → 출처 푸터 리듬부터 깐다.
2. 색이 고민되면 블루를 더하지 말고 여백·헤어라인으로 해결한다.
3. 강조가 두 곳 이상이면 하나로 줄인다 — 이 시스템의 강조는 희소성이 생명.

## Korean Typography Addendum

이 디자인은 **한글 우선으로 저작**되어 본문 규칙이 이미 한글-safe 다(Pretendard 스택·400 본문·음수 자간 -0.5px 이내). 적용 시 다음만 추가 확인한다:

- **한글 폰트**: 모든 한글 run 은 Pretendard, Noto Sans KR (fallback: Malgun Gothic, Apple SD Gothic Neo). Helvetica Neue 는 영문 킥커·숫자 run 전용 — 한글 run 에 바인딩하지 않는다.
- **자간**: 한글 display 음수 자간은 -0.5px 까지. PPTX(LibreOffice 렌더) 경로에서는 deckkit 가드가 한글 음수 자간을 0 으로 클램프한다 — 정상 동작이다.
- **weight**: 본문 400 고정(300 금지). display 700 유지.
- **의미색 관행**: 기본 international(상승=`#0E7C4A` 그린/하락=`#C0392B` 레드). 국내 금융·증권 청중 대상이면 **krx**(상승=레드/하락=블루)로 전환하고 문서 전체에 일관 적용한다.

## Known Gaps

- 본 문서는 **공개 CI 참조 스타일 저작물**이다 — Samsung 공식 CI 의 공개 Blue(#1428A0, PMS 286C)를 참조했으며, 삼성SDS 사내 브랜드 가이드 원본(로고 운용·전용 서체·정확한 보조 팔레트)을 재현하지 않는다. 정밀 브랜드 적용이 필요하면 조직 브랜드 가이드의 hex 로 frontmatter `colors` 를 교체하라.
- 실사이트 역공학이 아니라 **저작물**이다(getdesign 항목들과 성립 방식이 다름) — 컴포넌트 목록은 IR·발표·웹 소개 표면 기준의 정수이며 실서비스 UI 전수가 아니다.
- 모션·트랜지션·폼 검증 상태는 미정의.
- 결정론 토큰(v2)이 필요한 반복 파이프라인은 `../../library/samsung-sds.md`(시각 동등)를 쓴다.
