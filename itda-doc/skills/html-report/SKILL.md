---
name: html-report
description: >
  마크다운 보고서·분석 결과·회의 정리를 연차보고서 수준의 단일 파일 HTML 문서로 렌더링하는 스킬입니다. 외부 라이브러리 0개로 인라인 SVG 차트·스티키 목차·다크 모드·A4 인쇄를 내장하고 원본 데이터를 손실 없이 담습니다.
  스타일은 골격 가족 5종(코퍼레이트·컨설팅·에디토리얼·미니멀·공공기관 보고서형) × design-core 팔레트 조합으로 고릅니다.
  "이 보고서 HTML 파일로 만들어줘", "컨설팅 보고서 스타일로 전략 검토 문서 만들어줘", "공공기관 제출용 개조식 보고서 HTML로"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 보고서형 HTML 렌더 전담 — 아침 브리핑 페이지는 itda-work:morning-brief.
license: Apache-2.0
compatibility: "플랫폼 무관 (순수 프롬프트 스킬 — 스크립트·외부 의존 없음)"
user-invocable: true
allowed-tools: Read, Write, Glob, Grep, AskUserQuestion
argument-hint: "<보고서.md> [스타일: corporate|consulting|editorial|minimal|public-kr] [팔레트: design-core 프리셋명|DESIGN.md] [출력.html]"
metadata:
  author: "스킬.잇다"
  version: "0.3.1"
  category: "document"
  status: "beta"
  recommended: true
  created_at: "2026-07-27"
  updated_at: "2026-09-03"
  tags: "html, report, document, single-file, chart, dashboard, print, dark-mode, style-preset, design-core, consulting, editorial, public-sector"
---

# html-report — 극한 품질 단일 파일 HTML 문서 렌더러

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| "아침 브리핑 보여줘", 캘린더·메일에서 수집해 하루 한 장 페이지로 | itda-work:morning-brief |
| 워드·PPT 산출이 필요할 때 | itda-doc:docx-design · itda-doc:pptx-design |

## 목적

마크다운(또는 대화로 주어진 데이터)을 **연차보고서·브랜드 매거진 수준의 단일 파일 HTML**로 변환한다.
목표 수준: "브라우저에서 열었을 때, 디자인 에이전시가 2주 작업한 결과물로 보일 것."

이 스킬은 고정 템플릿을 쓰지 않는다. 아래 **품질 계약**(컴포넌트 규격 + 자기검증)이 템플릿을 대체한다.
레이아웃 창의성은 계약 위에서 발휘하라 — 계약은 하한이지 상한이 아니다.

스타일은 **두 축의 조합**이다(`references/styles/README.md` 가 정본):

- **골격 가족(축 A)** 5종 — `corporate`(코퍼레이트 리포트) · `consulting`(컨설팅 문서형) · `editorial`(에디토리얼) · `minimal`(미니멀 문서) · `public-kr`(공공기관 보고서형). 가족은 §2 컴포넌트 규격의 **변형**을 정한다(히어로·카드 정책·KPI 형태·표·차트 색·번호 체계). 가족 스펙 `references/styles/<가족>.md` 의 표가 §2 와 충돌하면 **가족 스펙이 우선**한다.
- **팔레트 프리셋(축 B)** — 형제 스킬(`docx-design`·`pptx-design`·`xlsx-design`)과 공유하는 `../design-core/library/` 8종 + 공공기관용 `gov-mono`. 색·의미색 관행·radius·display 폰트만 정하고 §5 토큰 값으로 인라인된다. 사용자 DESIGN.md 가 오면 같은 자리에 그 hex 를 넣는다.

## 워크플로우

1. **입력 분석** — 원본의 데이터 포인트를 전수 파악한다: 지표(KPI 후보), 시계열, 구성비, 비교, 시간축(일정·타임라인), 등급(리스크·우선순위), 서술.
2. **스타일 확정(가족 × 팔레트)** — `references/styles/README.md` 의 판정 트리거로 **신호**(가족명·톤 키워드·프리셋명·DESIGN.md·문서 성격이 자명한 경우: 장애 회고 → `minimal`, 개조식 제출 보고 → `public-kr`, 이사회 분기 보고 → `corporate`)가 하나라도 있으면 **되묻지 않고** 그 가족 + 기본 팔레트로 간다. 무신호 + 대화형이면 **AskUserQuestion 으로 콘텐츠 적합 가족 2~3종 + "알아서"** 를 제시한다(각 보기 = 가족 이름 + 골격 한 줄 + 기본 팔레트, 가장 맞는 것을 첫 옵션 추천). 무신호 + 비대화형(Cowork·MCP·AskUserQuestion 부재)이면 README 선택표 "잘 맞는 문서" 열로 자동 선택하고 완료 보고에 "가족 5종 중 X 로 렌더했으며 다른 스타일 요청 가능" 을 한 줄 남긴다. 구 문구("매거진 톤으로"·"다크 테마로"·"네이비")는 README 하위 호환 표로 해석한다. 확정 후 **해당 가족 스펙 파일을 반드시 읽는다.**
3. **컴포넌트 매핑** — §2 해부학 12종 중 콘텐츠가 뒷받침하는 컴포넌트를 전부 선택하고, 각 수치 덩어리에 §3 차트 문법으로 차트 유형을 배정한다.
4. **생성** — 단일 HTML 작성. 기본 출력 경로 `<cwd>/reports/<slug>-<YYYYMMDD>.html` (사용자 지정 시 그 경로).
5. **자기검증** — §10 체크리스트 18항 + 가족 스펙 말미의 **가족 자기검증 항목**을 전수 검사하고, 실패 항목을 고친 뒤에만 완료를 보고한다.

## §1 절대 원칙 (위반 시 실패)

1. **단일 파일 완결** — 모든 CSS·JS·SVG 인라인. 외부 JS 라이브러리(Chart.js·D3·Tailwind CDN·htmx) 0개.
2. **유일한 외부 의존 = 한국어 폰트 CDN** — Pretendard CDN `<link>` 1건 + preconnect. `font-family` 폴백에 system-ui 계열 필수(오프라인에서도 깨지지 않게).
3. **정보 무손실** — 원본의 **모든 데이터 포인트**(숫자·표 행·항목·각주)를 수용한다. "공간이 없어 생략"은 실패다. 넘치는 상세는 부록(`<details>`)으로 보낸다. 원본에 없는 수치 창작도 실패다.
4. **파일 크기 예산 ≤ 350KB** — 크기는 CSS 중복 제거로 아끼는 것이지 데이터를 버려서 아끼는 게 아니다.
5. **AI 티 금지** — 보라색 그라데이션 히어로, 이모지 헤딩(🚀 📊 ✨), "혁신적인/놀라운" 류 과장 형용사, 의미 없는 아이콘 나열 금지. 진지한 기업 문서의 절제된 언어와 시각만.

## §2 문서 해부학 — 컴포넌트 12종

콘텐츠가 해당 요소를 뒷받침하는 한 **전부** 포함한다. 아래 규격은 **가족 공통 기본값**이며, 확정한 가족 스펙(`references/styles/<가족>.md`)의 골격 토큰 표가 같은 항목을 다르게 정하면 그쪽을 따른다(예: `consulting` 은 KPI 스트립 대신 숫자 행, `public-kr` 은 히어로 대신 표지·격자 표, `minimal` 은 카드 0):

| # | 컴포넌트 | 규격 |
|---|----------|------|
| 1 | **커버 히어로** | 문서 유형 eyebrow(sans 12px 600·자간 0.04em) + 제목(clamp(30px,5vw,48px)) + 부제 + 메타 행(작성일·기간·작성 주체·문서번호). **밝은 배경 + 룰 하나**가 기본(가족별 표지 형태는 스펙 참조). 다색 그라데이션·짙은 밴드 금지 |
| 2 | **핵심 요약** | 히어로 직후. 30초 독해용 3~5문장 + 핵심 결론 1줄 강조(좌측 4px 액센트 보더 콜아웃) |
| 3 | **KPI 스트립** | 지표 4~6개 = 레이블(12px) + 값(24~40px, tabular-nums) + 전기 대비 델타(▲▼ 부호+색). 열 수를 **명시**(auto-fit 고아 금지). 카드/숫자 행/인라인 스탯/격자 표 중 가족 스펙이 정한 형태. 델타 색은 방향이 아니라 **의미**를 따른다 — 비용 상승은 부정색 |
| 4 | **스티키 목차** | 데스크톱(≥1100px) 좌측 고정 내비 + scroll-spy(IntersectionObserver ≤30줄). 모바일에선 숨김 |
| 5 | **섹션 시스템** | 각 `<section>` = 섹션 번호(가족별: `01`·논점 N·없음·`Ⅰ.`) + 제목 + 리드 문장. 섹션 간 여백 ≥64px |
| 6 | **데이터 테이블** | §4 표 규격 준수 |
| 7 | **SVG 차트 ≥ 3종** | §3 차트 문법 준수. 같은 유형 반복보다 데이터 성격별 상이한 유형 |
| 8 | **콜아웃** | 주의·통찰·결정 사항은 본문에 섞지 말고 콜아웃(배경 tint + 의미색 룰 + 레이블 — 가족별 형태)으로 분리, ≥2개 |
| 9 | **타임라인/로드맵** | 시간축 데이터가 있으면 수직 타임라인(점+선+카드) 또는 수평 바 |
| 10 | **리스크 매트릭스** | 심각도·확률 데이터는 색 점(dot)+등급 뱃지, 가능하면 심각도×확률 2D 그리드. 텍스트 나열 금지 |
| 11 | **부록** | 본문 흐름을 깨는 상세 표·주석·방법론은 `<details>` 접이식 부록으로 — 데이터를 버리지 않는 안전판 |
| 12 | **푸터 크레딧** | 생성일시·데이터 출처·면책 문구·문서 버전. 12px 보조색 |

## §3 차트 문법 (인라인 SVG)

차트는 장식이 아니라 **주장**이다. 각 차트에 "이 차트가 증명하는 한 문장" 캡션(`<figcaption>`)을 반드시 단다.

**공통 규격**
- `viewBox` 기반 반응형(`width="100%"`), `<figure>` + `<figcaption>` 구조.
- **축·눈금 라벨 필수**: Y축 눈금 3~5개(천 단위 콤마), X축 카테고리 라벨. 라벨 없는 차트는 그리지 마라.
- 그리드라인: 수평 minor `#F0EEE6` 1px. 4면 프레임 박스 금지.
- **값 라벨 필수**: 막대 끝/포인트 위에 실제 값(11px mono). 독자가 눈금을 역산하게 하지 마라.
- 단위(억원·%·건)는 축 제목 또는 캡션에 1회.
- SVG 내부 텍스트는 `font-family="Pretendard, system-ui, sans-serif"` 직접 지정(CSS 변수 상속 불가 가정).

**유형 선택**

| 데이터 성격 | 차트 | 금지 |
|-------------|------|------|
| 시계열 추이 | 라인(마커+마지막 값 강조) 또는 수직 막대 | 3D, 그라데이션 영역 남용 |
| 항목 비교 | 수평 막대(내림차순, 최대값 액센트) | 무지개색 막대 |
| 구성비(합=100%) | 도넛(중앙 합계 숫자) 또는 100% 스택 수평바 | 파이 5조각 초과 |
| 목표 대비 달성 | 불릿 차트(목표 tick + 실적 바) | 게이지 미터 |
| 2계열 대비 | 그룹 막대 + 범례(12px 색 견본) | 이중 Y축 |

**색 규칙** — 기본 데이터 색 1개(팔레트 `--accent`) + 강조 1개(`--accent-2` 또는 `--ink`) + 나머지 뉴트럴(`--g300` 농담). **2계열 비교는 액센트 + 뉴트럴**(같은 색상의 두 톤 금지). 시맨틱: 긍정 `--pos`, 부정 `--neg`, 중립 그레이. 한 차트에 유채색 3개 초과 금지. `public-kr` 은 흑백 판독(패턴 fill·명도 차)이 우선.

## §4 표 규격

- 숫자 컬럼: **우측 정렬 + `font-variant-numeric: tabular-nums`** + 천 단위 콤마. 소수 자릿수 컬럼 내 통일.
- 증감 컬럼: 부호(▲▼)와 색을 **함께** 사용 — 색맹 대비 부호 병기 필수.
- 헤더: 12px 600, 배경·룰은 가족 스펙(기본: 배경 없음 + 하단 2px `--ink` 룰). 긴 표는 `position: sticky; top: 0`.
- 소계 행 `border-top: 2px solid`, 합계 행 배경 tint + 볼드 — 선택자는 `tr.tot > *`(행 머리 `th` 포함, `td` 만 잡아 첫 셀이 비는 결함 금지). zebra는 12행 이상만.
- 셀 내 미니 시각화 허용: 값 비례 스파크바, 등급 dot, 진척 프로그레스바.
- 8컬럼 초과 표는 `overflow-x: auto` 래퍼. 페이지 전체 가로 스크롤 절대 금지.

## §5 타이포그래피·색·간격

```css
:root {
  /* 팔레트 축 — references/styles/README.md 프리셋 표의 값을 인라인한다 (예: samsung-sds) */
  --bg:#FFFFFF; --paper:#FFFFFF; --tint:#EEF2FB; --ink:#14181F;
  --accent:#1428A0; --accent-2:#5B8DEF; --line:#D5DBE8;
  --pos:#0E7C4A; --neg:#C0392B; --warn:#9A6206;
  --g100:var(--tint); --g300:var(--line); --g500:#5C6470;
  --g700:color-mix(in srgb, var(--ink) 80%, var(--bg));
  --accent-d:color-mix(in srgb, var(--accent) 85%, #000);
  --sans:"Pretendard",system-ui,-apple-system,"Segoe UI",sans-serif;
  --display:"Helvetica Neue",var(--sans);   /* 라틴·숫자 전용 — 한글은 Pretendard 로 떨어진다 */
  --mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,monospace;
}
```

팔레트 프리셋 9종(design-core 8 + `gov-mono`)의 값·다크 짝·파생 규칙·의미색 관행(international/krx)·가족×팔레트 금지 조합은 **`references/styles/README.md` 가 정본**이다. 사용자 DESIGN.md 는 같은 변수에 hex 만 치환한다. 다크 부팅 프리셋(`kari`·`equity-research-dark`·`tech-vivid-dark`)은 §6 의 "OS 라이트 감지 시 라이트 부팅·인쇄 라이트 강제" 를 따른다.

- 타입 스케일(1.25배): 12 / 15(본문) / 19 / 24 / 30 / 38px. 본문 line-height 1.7, 제목 1.25. **letter-spacing 음수는 라틴·숫자 전용**(한글 헤딩·본문에 음수 자간·thin weight 금지 — design-core 한글 가드와 동일).
- 라벨(eyebrow·표 헤더·캡션 라벨)은 **sans 12px 600 자간 .04em** 이 기본. mono 는 문서번호·Exhibit 번호·표 안 수치 식별자에만(가족 스펙이 달리 정하지 않는 한).
- 간격 스케일: 4/8/12/16/24/32/48/64/72/96px 외 임의값 금지.
- 본문 컨테이너 640~760px(가족별 고정값), 표·차트는 가족 브레이크아웃 폭까지.
- 국문 조판: `word-break: keep-all`, `text-wrap: pretty`(지원 시).
- 대비: 본문 ≥7:1, 보조 ≥4.5:1. 액센트색은 링크·강조·큰 숫자에 쓰되 14px 미만 본문 텍스트 색으로 금지.
- 세리프·명조가 필요한 가족(`editorial`·`public-kr`)은 **로컬 스택**(`Georgia`/`"Noto Serif KR","Apple Myungjo","Nanum Myeongjo","Batang",serif`)만 쓴다 — 웹폰트 CDN 은 Pretendard 1건뿐(§1-2).

## §6 다크 모드 (필수)

- `prefers-color-scheme: dark` 자동 대응 + 우상단 고정 토글(localStorage, `data-theme` 속성).
- 다크 팔레트: `references/styles/README.md` 의 "다크 짝" 파생 규칙을 따른다(라이트 프리셋 → 배경 `#0F1218`·카드 `#171B24`·본문 `#E7EAF0`·액센트는 라이트 accent 를 65% 밝힌 값; 다크 부팅 프리셋은 자기 값이 다크).
- **차트·표·뱃지 전부 다크 검수**: SVG 텍스트 fill·그리드라인·보더가 다크 배경에서 보여야 한다. `[data-theme="dark"] svg .grid { … }` 식 선택자로 오버라이드.
- 인쇄는 무조건 라이트 강제.

## §7 인쇄 = 제2의 일급 매체

"브라우저 인쇄 → PDF"가 배포 경로다. 인쇄 품질은 화면과 동급.

```css
@page { size: A4; margin: 18mm 16mm; }
@media print {
  :root { color-scheme: light; }
  body { background:#fff; font-size:10.5pt; }
  nav.toc, .theme-toggle, .no-print { display:none !important; }
  section, figure, table, .kpi-strip { break-inside: avoid; }
  h2 { break-after: avoid; }
  details { display:block; } details > * { display:block; }  /* 부록 자동 펼침 */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
```

`<details>` 인쇄 강제 펼침으로 접힌 정보의 인쇄 소실 0.

## §8 인터랙션 (vanilla JS 총 60줄 이내)

허용 목록 외 JS 금지: ① TOC scroll-spy(IntersectionObserver) ② 다크 토글+localStorage ③ `<details>`(네이티브, JS 불요) ④ 표 정렬 또는 차트 hover 값 표시 중 택1(선택).
부드러운 이동은 `html { scroll-behavior: smooth; }`. 스크롤 애니메이션·패럴랙스 금지.

## §9 접근성·시맨틱

- 랜드마크 `<header> <nav> <main> <section> <footer>`, 섹션마다 `aria-labelledby`.
- 헤딩 위계 h1→h2→h3 건너뛰기 금지, h1은 1개.
- SVG 차트: `role="img"` + `<title>` + `aria-label`(핵심 수치 요약).
- 색만으로 의미 전달 금지(§4 부호 병기). 포커스 스타일 제거 금지, 토글에 `aria-pressed`.

## §10 자기 검증 체크리스트 — 출력 직전 전수 확인

하나라도 실패하면 고친 뒤 완료를 보고한다:

- [ ] 원본의 모든 표 행·수치가 문서 어딘가에 존재 (부록 포함)
- [ ] 창작된 수치 없음
- [ ] SVG 차트 3종 이상 + 전부 축 라벨·값 라벨·캡션
- [ ] KPI 카드에 델타 부호+색 병기
- [ ] 숫자 컬럼 우측 정렬 + tabular-nums + 천 단위 콤마
- [ ] 스티키 TOC + scroll-spy 코드 존재
- [ ] 다크 토글 + prefers-color-scheme + 차트 다크 검수
- [ ] `@page` + break-inside + details 인쇄 펼침
- [ ] 모바일(390px) 가로 스크롤 없음 (표는 래퍼 스크롤)
- [ ] 외부 의존 = 폰트 CDN 1건뿐
- [ ] 이모지 헤딩·보라 그라데이션·과장 형용사 없음
- [ ] 헤딩 위계 정상, h1 1개
- [ ] SVG에 title/aria-label
- [ ] 섹션 번호·리드 문장 존재
- [ ] 콜아웃 ≥2개
- [ ] 푸터 생성 메타·출처
- [ ] JS 60줄 이내, 허용 목록 외 없음
- [ ] 파일 ≤ 350KB
- [ ] 확정한 가족 스펙(`references/styles/<가족>.md`) 말미의 **가족 자기검증 항목 전건 통과**
- [ ] 팔레트 변수가 README 프리셋 표(또는 사용자 DESIGN.md) 값과 일치, 임의 색 0

## 사용 예시

- "2분기 경영 현황 정리한 이 마크다운, HTML 보고서로 만들어줘"
- "장애 회고 문서를 HTML로 렌더해줘. 타임라인 강조해줘"
- "이 재무 분석을 이사회 배포용으로 — 인쇄했을 때 깨끗해야 해"

## 하지 않는 것

- 외부 JS/CSS 라이브러리 도입, 빌드 단계 도입, 다중 파일 산출.
- 데이터 요약·생략을 크기 절감 수단으로 사용.
- 슬라이드(발표 자료)·독립 인포그래픽 — 별도 도구의 몫이다.

## 참고

- [`references/styles/README.md`](references/styles/README.md) — 스타일 시스템 정본: 가족 선택표·판정 트리거·팔레트 프리셋 9종 값·다크 짝·금지 조합·구 문구 하위 호환.
- 가족 스펙: [`corporate.md`](references/styles/corporate.md) · [`consulting.md`](references/styles/consulting.md) · [`editorial.md`](references/styles/editorial.md) · [`minimal.md`](references/styles/minimal.md) · [`public-kr.md`](references/styles/public-kr.md) — 골격 토큰 표 + 금지 + 가족 자기검증.
- 가족별 샘플(계약 전체 충족, **구조·밀도의 눈높이 참고용** — 마크업 복제 금지, 콘텐츠에 맞는 레이아웃을 새로 설계하라):
  [`sample-quarterly.html`](references/sample-quarterly.html)(corporate × samsung-sds, 분기 경영 현황) ·
  [`sample-consulting.html`](references/sample-consulting.html)(consulting × consulting-mbb, 신사업 진입 검토) ·
  [`sample-editorial.html`](references/sample-editorial.html)(editorial × warm-editorial, 연차보고서) ·
  [`sample-minimal.html`](references/sample-minimal.html)(minimal × tech-vivid-dark, 인시던트 회고) ·
  [`sample-public-kr.html`](references/sample-public-kr.html)(public-kr × gov-mono, 사업 추진 현황 보고).
