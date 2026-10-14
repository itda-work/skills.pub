# itda-doc

문서 스킬팩 — 한글 문서 읽기·채우기·생성(hwpx), AI 흔적 제거(human-tone), 이미지 생성(imagegen), PPTX 용량 축소(pptx-shrink). 품질 하한·자기검증 게이트.

> 2026-09-05 플러그인 재정비(#1648)로 구 `itda-work` 가 목적별 팩으로 나뉘었습니다. 콘텐츠 산출 스킬은 여기, 웹 수집은 `itda-web`, 하루 조직(캘린더·메일·날씨·환율)은 `itda-work`, 검증(2026-10-14 제거)은 `itda-research`, 업무 코칭(2026-10-14 제거)은 `itda-work`, PDF 정제는 `itda-research` 로 갔습니다. 구 이름 `itda-work` 는 마켓플레이스에서 제거됐습니다(별칭 없음).

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`human-tone`](skills/human-tone/SKILL.md) | 이미 작성된 한국어 사무 글(보고서·메일·기획서·공지)에서 AI 흔적을 걷어내는 후처리 스킬입니다. |
| [`hwpx`](skills/hwpx/SKILL.md) | 한글 HWP·HWPX 문서 스킬입니다. |
| [`imagegen`](skills/imagegen/SKILL.md) | 발표자료·블로그·문서용 이미지와 삽화를 품질 하한과 함께 만드는 스킬입니다. |
| [`pptx-shrink`](skills/pptx-shrink/SKILL.md) | 기존 PPTX 파일의 용량을 줄이는 스킬입니다. |

> 브랜드 디자인 토큰과 Word·PPTX·Excel 신규 생성을 맡던 디자인 스킬 4종은 2026-09-27 제거했습니다(git 이력에는 남아 있음). 한글 문서는 `hwpx` 가 만듭니다.

> 초안 작성(`draft-post`)·HTML 보고서(`html-report`)·네이버 블로그 키워드(`blog-seo`)·PDF 정제(`pdf-context-refinery`)·이미지 가공(`imagekit`)은 2026-10-14 제거했습니다(사용자 결정 — 스킬 최소화, git 이력에는 남아 있음). 같은 일은 Claude 기본 기능으로 합니다 — 초안·HTML 문서는 Claude 에게 바로 요청하고, PDF 는 Claude 의 기본 PDF 읽기(Read 도구·공식 `pdf` 스킬)로 읽고, 이미지 크기·포맷 조정도 Claude 에게 바로 요청합니다.

> `imagegen`(이미지 생성)은 2026-09-25 저장소 이관 때 빠졌다가 2026-09-28 itda-hyve 의 에이전트 작업(`agent_run`) 경로로 되살렸습니다. itda-hyve 0.10.1 이상이 필요하고, codex 는 itda-hyve 창의 에이전트 탭에서 설치·로그인합니다(ChatGPT 구독, 따로 설치한 codex 는 쓰지 않음). `pptx-diff`(PPTX 버전 비교)는 빠진 그대로입니다(git 이력에는 남아 있음).

> hwpx 읽기는 동봉 Python native 변환기(`skills/hwpx/reader/hwpx_native`)로 동작합니다 — 외부 바이너리 동봉 계약은 없습니다(2026-09 R2 정리).

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-doc@itda-skills-pub
```

스킬별 사전 준비(API 키·Python 패키지)는 각 `SKILL.md` 의 Prerequisites 절에 있습니다.

## 개발

```bash
just test itda-doc          # 저장소 루트
just -f itda-doc/justfile test
```
