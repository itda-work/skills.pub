# 매체 매핑 — design-core v2 → 웹/HTML CSS

design-core 토큰을 web(HTML/CSS)으로 적용하는 경로다. **pptx 와 결정적으로 다르다**: pptx 는 Claude 가 `.pptx` 이진을 직접 못 만들어 deckkit/LibreOffice 라는 무거운 렌더 어댑터(`pptx-design`)가 필수지만, web 은 **Claude 가 HTML/CSS 를 직접 생성**하므로 무거운 어댑터가 필요 없다. 토큰 + 본 매핑이면 **지금 동작**한다 — web 은 design-core 의 가장 쉬운 매체다.

## 두 경로 (둘 다 1급)

### ① 결정론 — `to_css_vars()` 로 tokens.css 생성
`design_core.to_css_vars(tokens)` 가 v2 토큰을 CSS custom properties(`:root { --bg … }`)로 변환한다. 한글 본문 폰트는 `fallback_fonts.korean` 스택으로 펼쳐 web 에서도 CJK 안전성을 유지한다. 산출 `tokens.css` 를 `<link>` 로 물리면 **그 한 줄만 교체해 브랜드 전환**이 된다(samsung-sds ↔ kari).

### ② 에이전트 직접 — 본 매핑 보고 생성
Claude 가 토큰을 읽고 아래 표대로 HTML/CSS·React·Tailwind config 를 직접 작성한다. 무거운 코드가 불필요 — Claude 자신이 렌더 엔진이다.

## 토큰 → CSS 변수 매핑

| v2 토큰 | CSS custom property |
|---|---|
| `color.bg`/`surface`/`fg`/`muted`/`primary`/`accent`/`border` | `--bg`/`--surface`/`--fg`/`--muted`/`--primary`/`--accent`/`--border` |
| `color.surface_2`(B-slot) | `--surface-2` (생략 시 `--surface` alias) |
| `semantic.up`/`down` | `--success`/`--danger` |
| `font.display`/`body` | `--font-display`/`--font-body` (한글 fallback 스택 동반) |
| `radius.base`(비율) | `--radius` (rem 근사) |
| `type-scale.*`(후속) | `--text-xs … --text-4xl` |
| `layout.grid`/`breakpoints`(후속) | `--container-max`, 미디어쿼리 |
| `constraints.web` | 제약 없음(기본) |

## 실증

`examples/web/` — `to_css_vars()` 가 생성한 `samsung-sds.tokens.css`·`kari.tokens.css` + 이를 소비하는 `demo.html`. demo 의 `var()` 참조 11개가 두 토큰셋 모두에 정의돼(미정의 0), **`<link>` 한 줄 교체로 브랜드가 전환**됨이 검증됐다(파일을 브라우저로 열어 확인).

## 후속(선택 고도화 — 지금도 동작하나 더 풍부하게)

- `type-scale` → `clamp()` 반응형 타입 스케일
- WCAG 대비 게이트를 web 에선 ERROR 로 승격 검토(`validate.py` advisory 재사용)
- Tailwind config / shadcn 산출(참고: opendesign 등 외부 토큰 표준)
