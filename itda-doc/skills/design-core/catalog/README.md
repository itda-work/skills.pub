# catalog/ — 표준 DESIGN.md 한국 확장 카탈로그

getdesign.md 카탈로그(75종 — 전부 서구 브랜드)에 **없는** 브랜드를 같은 **표준 DESIGN.md 포맷**(Google Stitch 9섹션 + 확장 frontmatter — `../schema/design-md-standard.md`)으로 저작해 채우는 곳이다(#1021). 소비 방식은 getdesign 산출물과 동일: **에이전트가 원문을 직접 읽어**(직해석) 웹·PPTX 등에 적용한다 — `design_core.load()` 대상이 아니다.

각 항목 구성:

| 파일 | 역할 |
|---|---|
| `<slug>/DESIGN.md` | 표준 포맷 디자인 문서(9섹션 + frontmatter + Korean Typography Addendum + Known Gaps) |
| `<slug>/preview.html` | 직해석 미니 프리뷰(자립 HTML — 스와치·타이포·버튼·카드) |

`../library/`(v2 프리셋 — 코드 소비·반복 파이프라인용 결정론 레이어)와는 **별개 레이어**다. 같은 브랜드가 양쪽에 있을 수 있다(예: samsung-sds — 시각적으로 동등, 포맷·소비자만 다름). 관계는 `../schema/design-md-standard.md` 비교표 참조.

## 항목

| slug | 톤 | 잘 맞는 주제 | v2 대응 |
|---|---|---|---|
| `samsung-sds` | Samsung Blue 코퍼레이트 — 절제된 그리드·킥커·출처 규율 | 기업 IT·B2B·IR·기술 발표·웹 | `../library/samsung-sds.md` |

## 저작 규율

`../schema/design-md-standard.md` §저작 규율을 따른다 — 9섹션 전부·frontmatter 완결·Korean Typography Addendum·Known Gaps 정직 서술. 신규 항목은 design-core SKILL.md 저작 워크플로우(관문 A~E)로 만들고 본 표에 행을 추가한다.
