# 표준 DESIGN.md (Google Stitch 포맷) — 차용·직해석·저작 가이드

**DESIGN.md** 는 Google Stitch 가 도입한 표준 개념이다: AI 에이전트가 읽고 일관된 UI 를 생성하는 **평문 디자인 시스템 문서**(파싱·설정 불필요 — "마크다운은 LLM 이 가장 잘 읽는 포맷"). getdesign.md(VoltAgent/awesome-design-md, **MIT**)가 이 포맷으로 실사이트를 역공학한 **75종 브랜드 카탈로그**를 배포한다. design-core 는 이 표준을 차용(getdesign)·저작(`../catalog/`) 양방향으로 쓴다(#1021).

> ⚠️ **design-core 토큰(v2)과 별개다.** v2(`design-md-v2.md`)는 코드 렌더러(dockit·sheetkit)용 **결정론 dialect** — 이름만 비슷할 뿐 소비자·용도가 다르다(아래 비교표). 표준 파일을 `design_core.load()` 에 넣지 말 것.

## 표준 vs v2 — 소비 모드 비교

| | **표준 DESIGN.md** (본 문서) | **design-core 토큰 v2** |
|---|---|---|
| 소비자 | LLM 에이전트(Claude·Stitch·Cursor …)가 **원문 직해석** | 코드(`load()` → dockit·sheetkit) |
| 용도 | **1회성 산출물**(이 웹페이지·이 발표자료) — 풍부함 우선 | **반복 파이프라인**(정기 보고서·템플릿) — drift 0·검증 우선 |
| 구조 | 9섹션 산문 + 확장 frontmatter(다단 색 역할·타이포 스케일·컴포넌트) | 4계층 평면 토큰(색 7~9·폰트 2·constraints) |
| 단위 | px(웹 네이티브) | 인치·비율(PPTX 기준) |
| 검증 | 9섹션 체크리스트 + 직해석 프리뷰 눈검증 | `validate.py`(A1 무결성 ERROR 게이트) |

**[HARD] 직해석 원칙**: 표준 파일은 원문 그대로 읽어 쓴다 — 자동 매퍼로 좁은 스키마에 욱여넣지 않는다. 실측(#1021): `load()` 통과 시 minimax `accent #ff5530`→None·font→None, bmw-m 원본 신호 76개→유효 5색으로 **원문의 90%+ 가 소실**됐다. 매체별 표현 필터(예: pptx 3열 필터)는 소비하는 어댑터 스킬의 책임이다.

## 9섹션 구조 (Stitch 정본 + getdesign 확장)

| # | 섹션 | 담는 것 |
|---|---|---|
| 1 | Visual Theme & Atmosphere | 무드·밀도·디자인 철학 |
| 2 | Color Palette & Roles | 의미적 이름 + hex + 기능 역할 |
| 3 | Typography Rules | 폰트 패밀리·전체 위계표(size/weight/lineHeight/letterSpacing) |
| 4 | Component Stylings | 버튼·카드·입력·네비 + 상태 |
| 5 | Layout Principles | 간격 스케일·그리드·여백 철학 |
| 6 | Depth & Elevation | 그림자 시스템·표면 위계 |
| 7 | Do's and Don'ts | 디자인 가드레일·안티패턴 |
| 8 | Responsive Behavior | 브레이크포인트·터치 타깃·collapsing |
| 9 | Agent Prompt Guide | 색 즉시 참조 + ready-to-use 프롬프트 |

**Frontmatter 관례**(getdesign 실물 기준 — bmw-m·minimax): `version`/`name`/`description` + `colors:`(다단 역할별 hex — canvas·surface 계열·ink/body/muted·brand 계열·semantic) + `typography:`(스케일별 fontFamily·fontSize·fontWeight·lineHeight·letterSpacing) + `rounded:`/`spacing:`(px) + `components:`(토큰참조 `"{colors.canvas}"` 형식). frontmatter 없는 순수 산문형(spotify)도 유효하다. 본문 끝에 **Known Gaps**(추출·저작의 한계 정직 서술)를 두는 것이 getdesign 관례.

## 획득 (getdesign 카탈로그)

```bash
npx -y getdesign@latest list                        # 75종 카탈로그(slug - 한줄설명)
npx -y getdesign@latest add <slug> [--out <경로>]    # 정본 — 기본 ./DESIGN.md, --force 덮어쓰기
# 폴백(네트워크/Node 부재 시 — 마스터 승인 2026-07-11):
curl -fsSL https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/<slug>/DESIGN.md -o DESIGN.md
```

- 상세·프리뷰 페이지: `https://getdesign.md/<slug>/design-md` (Light/Dark 프리뷰 탭). 브랜드별 preview.html 은 저장소에 없다(404 실측) — 프리뷰가 필요하면 아래 미니 프리뷰 관습으로 직접 렌더한다.
- 카테고리 축(9종: AI/개발도구/백엔드/생산성/디자인툴/핀테크/커머스/미디어/자동차)은 awesome-design-md README 가 기계가독(`- [**이름**](URL) - 설명` 73링크).
- 라이선스 **MIT** — 수정(CJK Addendum 증보)·캐시·동봉 자유. 단 카탈로그는 "공개 웹사이트의 시각 언어 추출물"이며 각 사이트의 브랜드 정체성 소유권과 무관 — 대외 상업물에는 조직 브랜드 가이드 확인을 권한다.

## 미니 프리뷰 관습 (직해석 렌더)

후보 비교(차용 ②단계)·저작 관문C 에서, 에이전트가 DESIGN.md 원문을 읽고 **단일 자립 HTML**(외부 의존 0)을 직접 작성해 보여준다. 필수 구성: ① 색 스와치(역할명+hex, frontmatter 의 주요 역할 전부) ② 타이포 위계(display→body→caption 실제 폰트 스택·weight 로) ③ 버튼(primary·outline)·카드 1~2개 ④ 해당 브랜드 시그니처 모티프 1개(예: 스트라이프 그라디언트, M 트라이컬러 스트라이프). 팔레트 나열이 아니라 "**각 색·타이포가 제 역할로 쓰인 화면**"이어야 한다(v2 `preview.py` 와 같은 철학 — 렌더러만 에이전트).

## Korean Typography Addendum (한글 증보 템플릿)

getdesign 원문은 라틴 전제다(음수 자간·Light(300) 본문·독점 서체). 한글 산출물이 목적이면 획득한 DESIGN.md **끝에** 아래 섹션을 추가한다 — 원문을 깎지 않는 **증보**이며, bmw-m 의 "Note on Font Substitutes" 섹션과 동형의 관례다.

```markdown
## Korean Typography Addendum

이 디자인을 한글 산출물에 적용할 때 다음 규칙이 원 타이포 규칙에 우선한다
(원 디자인의 display 폰트·자간은 라틴/숫자 run 에만 유지 — 브랜드 정체성 보존):

- **한글 폰트**: 모든 한글 run 은 한글 안전 고딕으로 — Pretendard, Noto Sans KR
  (fallback: Malgun Gothic, Apple SD Gothic Neo). 세리프·독점 서체를 한글에 쓰지 않는다.
- **자간**: 음수 letterSpacing 은 한글 run 에서 0 으로 클램프. 양수 트래킹도 2px 이하로 캡.
- **weight**: 300(Light) 본문은 한글에서 400(Regular)로 승격 — thin 한글은 렌더러에 따라
  명조/흐림 폴백 위험. 700 display 는 한글 700 그대로.
- **의미색 관행**: 기본 international(상승=그린/하락=레드). 국내 금융 청중이면
  krx(상승=레드/하락=블루)로 전환하고 문서 전체에 일관 적용.
```

PPTX 로 갈 때는 이 증보와 별개로 `pptx-design` 의 deckkit 한글 가드(`kr_font_name()`·자간 클램프)가 런타임에서 한 번 더 방어한다(이중 안전).

## 저작 규율 (갭 필러 — `../catalog/`)

getdesign 에 없는 브랜드(한국·자사·사이트 없는 신규)를 저작할 때(SKILL.md 관문 A~E):

- **9섹션 전부** 채운다(빈 섹션 금지 — 얇더라도 방향을 서술).
- **frontmatter 완결**을 하우스 스타일로 강제한다 — getdesign 실물은 frontmatter 가 선택이지만, 우리 저작물은 코드 소비 여지(추후 결정론 전환)를 위해 핵심 색 역할·타이포 스케일을 반드시 담는다.
- **Korean Typography Addendum 포함**(한국 브랜드는 본문이 이미 한글-safe 라도 krx 토글 등 관행 명시).
- **Known Gaps 정직 서술** — 공개 자료 참조 스타일인지, 원본 브랜드 가이드 재현인지, 무엇이 미정의인지.
- 재사용 항목은 `../catalog/<slug>/DESIGN.md`(+ `preview.html`), 1회성은 사용자 작업 폴더.

## History

- 2026-07-11: 초안 (#1021). getdesign-first 재편 — 표준(Stitch) 포맷 정의·v2 dialect 구분·획득 명령(npx 정본/raw 폴백)·직해석 원칙([HARD] load() 금지, minimax/bmw-m 소실 실측)·미니 프리뷰 관습·CJK Addendum 템플릿·저작 규율 명문화.
