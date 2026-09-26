# itda-doc

업무 콘텐츠 산출 스킬팩 — 초안(draft-post)·문체(human-tone)·SEO 키워드·디자인 토큰(design-core)·Word/PPTX/Excel/HTML/한글 문서 렌더·이미지 가공을 한 파이프라인으로. 디자인 토큰 일관성·품질 하한·자기검증 게이트.

> 2026-09-05 플러그인 재정비(#1648)로 구 `itda-work` 가 목적별 팩으로 나뉘었습니다. 콘텐츠 산출 스킬은 여기, 웹 수집은 `itda-web`, 하루 조직(캘린더·메일·날씨·환율)은 `itda-work`, 검증(ground-check·investigate·market-scan)은 `itda-research`, 업무 코칭(work-find·work-proposal·work-pilot·task-brief)은 `itda-work`, PDF 정제는 `itda-research` 로 갔습니다. 구 이름 `itda-work` 는 마켓플레이스에서 제거됐습니다(별칭 없음).

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`blog-seo`](skills/blog-seo/SKILL.md) | 네이버 SearchAd API로 블로그 SEO용 블루키워드를 발굴하는 스킬입니다. |
| [`design-core`](skills/design-core/SKILL.md) | 브랜드 디자인을 고르고(getdesign 표준 DESIGN.md 카탈로그 차용), 만들고(한국·자사 브랜드 저작), 검증·조회해 웹·PPTX·DOCX·XLSX 여러 매체에 일관 적용하는 디자인 시스템 허브 스킬입니다. |
| [`docx-design`](skills/docx-design/SKILL.md) | 콘텐츠 마크다운과 수치 데이터로 디자인된 Word 문서(.docx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는 스킬입니다. |
| [`draft-post`](skills/draft-post/SKILL.md) | 블로그·보고서·기획서·보도자료·뉴스레터를 도메인 맞춤 인터뷰로 초안 작성하는 스킬입니다. |
| [`html-report`](skills/html-report/SKILL.md) | 마크다운 보고서·분석 결과·회의 정리를 연차보고서 수준의 단일 파일 HTML 문서로 렌더링하는 스킬입니다. |
| [`human-tone`](skills/human-tone/SKILL.md) | 이미 작성된 한국어 사무 글(보고서·메일·기획서·공지)에서 AI 흔적을 걷어내는 후처리 스킬입니다. |
| [`hwpx`](skills/hwpx/SKILL.md) | 한글 HWP·HWPX 문서 스킬입니다. |
| [`imagekit`](skills/imagekit/SKILL.md) | 이미지 조회·리사이즈·여백 크롭·DPI 변경·포맷 변환·회전을 단일 CLI로 처리하는 스킬입니다. |
| [`pptx-design`](skills/pptx-design/SKILL.md) | 콘텐츠 마크다운과 수치 데이터로 16:9 PPTX 발표자료를 크로스플랫폼(macOS/Linux, Office 불필요)으로 신규 생성하는 스킬입니다. |
| [`pptx-shrink`](skills/pptx-shrink/SKILL.md) | 기존 PPTX 파일의 용량을 줄이는 스킬입니다. |
| [`xlsx-design`](skills/xlsx-design/SKILL.md) | 수치 데이터로 디자인된 Excel 통합문서(.xlsx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는 스킬입니다. |

> hyve 앱이 있어야만 동작하던 `imagegen`(이미지 생성)·`pptx-diff`(PPTX 버전 비교)는 2026-09-25 저장소 이관 때 빠졌습니다(git 이력에는 남아 있음).

> hwpx 읽기는 동봉 Python native 변환기(`skills/hwpx/reader/hwpx_native`)로 동작합니다 — 외부 바이너리 동봉 계약은 없습니다(2026-09 R2 정리).

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-doc@itda-skills-pub
```

스킬별 사전 준비(API 키·환경변수·Python 패키지)는 각 `SKILL.md` 의 Prerequisites 절에 있습니다.

## 개발

```bash
just test itda-doc          # 저장소 루트
just -f itda-doc/justfile test
```
