---
name: draft-post
description: >
  블로그·보고서·기획서·보도자료·뉴스레터를 도메인 맞춤 인터뷰로 초안 작성하는 스킬입니다.
  "블로그 글 써줘", "보고서 초안 작성해줘", "기획서 만들어줘"처럼 말하면 됩니다.
  컨텍스트를 모은 뒤 도메인별로 톤·구조를 조정한 마크다운 초안을 출력합니다.
  [책임 경계] 본 스킬은 초안 생성 전담(AI 흔적 사전의 정본: itda-doc:human-tone) — 이미 작성된 글의 AI 흔적 제거·문체 후처리는 itda-doc:human-tone 이 맡고, 본 스킬은 발행·송부를 하지 않습니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork"
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, mcp__workspace__bash
argument-hint: "<topic> [--style <style>] [--save <path>] [--analyze <file>] [--list-styles]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "1.2.8"
  category: "writing"
  created_at: "2026-03-28"
  updated_at: "2026-09-27"
  tags: "blog, report, draft, writing, official, government, press-release, proposal, briefing, newsletter, meeting-minutes"
---

# draft-post

주제와 글쓰기 스타일을 받아 인터뷰 기반으로 마크다운 초안을 생성합니다.

> 스크립트 없이 프롬프트만으로 동작 — 추가 의존성 없음

## Arguments

- `<topic>` (필수): 글의 주제. 예: "Claude Cowork MCP 연동 가이드"
- `--style <style>` (선택): 글쓰기 스타일. `references/` 내 빌트인 스타일 또는 사용자 정의 스타일명. 기본값: `blog`
- `--save <path>` (선택): 초안을 저장할 파일 경로. 생략 시 대화창에 출력만 함
- `--analyze <file>` (선택): 기존 자료를 분석하여 새 reference 스타일을 생성. "스타일 확장 가이드" 참조
- `--list-styles` (선택): 초안 생성 없이 사용 가능한 스타일 목록만 출력하고 종료

### 사용 가능한 스타일

| 스타일 | 파일 | 설명 |
|--------|------|------|
| **공공 도메인** | | |
| `blog` | `references/blog.md` | 블로그 포스팅 (기본값) |
| `official-report` | `references/official-report.md` | 공무원 업무보고/현황보고/기획보고 |
| `press-release` | `references/press-release.md` | 정부/공공기관 보도자료 |
| `proposal` | `references/proposal.md` | 기획서/제안서 (정책 기획, 사업 제안) |
| `briefing` | `references/briefing.md` | 간부 보고용 브리핑 자료 (A4 1매) |
| `official-letter` | `references/official-letter.md` | 공문/시행문/업무연락 (대외+대내) |
| `policy-brief` | `references/policy-brief.md` | 정책 브리프 (정책 이슈 분석/제언) |
| **민간 도메인** | | |
| `business-plan` | `references/business-plan.md` | 사업계획서 (IR 덱, 정부지원사업) |
| `announcement` | `references/announcement.md` | 사내 공지/안내문 |
| `newsletter` | `references/newsletter.md` | 이메일 뉴스레터 |
| `meeting-minutes` | `references/meeting-minutes.md` | 회의록/간담회 기록 |
| `product-brief` | `references/product-brief.md` | 제품/서비스 소개서 |

새 스타일을 추가하려면 "스타일 확장 가이드"를 참조하세요.

## Workflow

### Step 0: 환경 감지

실행 시작 시 환경을 자동 감지하고 `USER_STYLES_DIR`를 결정한다.

1. `CLAUDE_CODE_IS_COWORK` 환경변수 확인:
   - Bash 도구로 `echo $CLAUDE_CODE_IS_COWORK` 실행
   - 값이 `1`이면 → **Claude Cowork** 환경
   - 값이 없거나 그 외 → **Claude Code**(또는 일반 로컬) 환경

2. Cowork 환경이면, `./mnt/` 디렉토리 존재 여부 확인:
   - Bash 도구로 `[ -d "./mnt" ] && echo "MOUNTED" || echo "NOT_MOUNTED"` 실행

3. 결과에 따른 `USER_STYLES_DIR` 결정:

   | 환경 | USER_STYLES_DIR | 영속성 |
   |------|-----------------|--------|
   | Claude Code (로컬) | `.itda-skills/draft-post/styles/` | 프로젝트 단위 영구 |
   | Cowork + 마운트 (`./mnt/` 존재) | `./mnt/.itda-skills/draft-post/styles/` | 호스트 영구 |
   | Cowork + 마운트 없음 | `.itda-skills/draft-post/styles/` | 세션 한정 |

이후 모든 단계에서 `USER_STYLES_DIR`를 사용자 스타일의 저장·탐색 기준 경로로 사용한다.

### Step 1: 스타일 레퍼런스 로드

#### 1-a. Anti-AI 문체 가이드 로드 (항상)

스타일과 무관하게 `references/_anti-ai-korean.md`를 항상 먼저 로드한다.
이 파일의 규칙(AI 습관어 금지, 번역투 금지, 어미 변화, 자가 점검)은 이후 모든 단계에서 글쓰기 제약 조건으로 적용한다.

#### 1-b. `--list-styles` 플래그 처리

`--list-styles`가 지정된 경우, 초안 생성 없이 스타일 목록만 출력하고 종료한다:

```
📂 사용 가능한 스타일

빌트인 스타일:
  blog            블로그 포스팅 (기본값)
  official-report 공무원 업무보고/현황보고/기획보고
  ...

사용자 정의 스타일:
  stock-blog      주식 블로그 스타일
  ...
```

- `references/` 디렉토리를 Glob으로 스캔, `_` prefix 파일(`_template.md`, `_anti-ai-korean.md`)을 제외한 `.md` 파일을 **빌트인 스타일**로 표시
- `USER_STYLES_DIR`를 Glob으로 스캔하여 `.md` 파일을 **사용자 정의 스타일**로 표시
- 각 스타일의 한 줄 설명은 해당 레퍼런스 파일의 `개요` 섹션 또는 첫 번째 헤딩 직후 첫 문장에서 추출
- 사용자 정의 스타일이 없으면 해당 섹션을 생략하고 스타일 생성 방법 안내
- `--list-styles`와 `<topic>`이 함께 지정되면 목록만 출력하고 종료 (topic 무시)

#### 1-c. 일반 스타일 로드

1. `--style` 인자에서 스타일명을 확인한다 (기본값: `blog`)
2. 다음 순서로 스타일 파일을 탐색한다:
   - `{USER_STYLES_DIR}/{style}.md` — 사용자 정의 스타일 우선
   - `{스킬 디렉토리}/references/{style}.md` — 빌트인 스타일
3. 파일이 없으면 사용 가능한 스타일 목록을 출력하고 선택을 요청한다:
   - 빌트인: `references/` Glob 스캔 (`_template.md` 제외), `(빌트인)` 라벨 표시
   - 사용자 정의: `USER_STYLES_DIR` Glob 스캔, `(사용자 정의)` 라벨 표시
   - 동명 스타일이 양쪽에 존재하면 사용자 정의만 표시 (사용자 정의 우선)
   - 사용자가 스타일을 선택하면 해당 레퍼런스를 로드

로드된 레퍼런스의 내용은 이후 모든 단계에서 글쓰기 규칙으로 적용한다.

### Step 2: 주제 분석 & 질문 준비

주제와 로드된 스타일 레퍼런스를 분석하고, 좋은 글을 쓰기 위해 필요한 질문을 준비한다.

**공통 질문 영역** (주제에 맞게 3-6개 선별):

- **대상 독자**: 누구를 위한 글인가?
- **핵심 메시지**: 독자가 글을 읽고 얻어갈 한 가지는?
- **다룰 범위**: 어디까지 다루고, 어디서 끊을지

**스타일별 추가 질문**은 레퍼런스 파일의 "인터뷰 질문" 섹션에서 가져온다.

질문은 한 번에 모두 하지 말고, 2-3개씩 나눠서 대화형으로 진행한다.

### Step 3: 인터뷰 진행 (최소 2라운드)

사용자와 최소 2회 이상 Q&A를 진행한다:

- Round 1: 핵심 질문 2-3개 (대상, 메시지, 범위)
- Round 2: 구체화 질문 2-3개 (구조, 세부 내용, 톤)
- Round 3 (선택): 보충 질문 (빠진 것, 최종 확인)

사용자의 답변이 충분하면 더 질문하지 않고 진행한다.
답변이 부족하면 추가 질문을 한다.

### Step 4: 초안 작성

인터뷰 결과를 바탕으로, 레퍼런스에 정의된 규칙에 따라 마크다운 초안을 생성한다.

레퍼런스 파일에 정의된 항목을 적용한다:
- **frontmatter 템플릿**: 레퍼런스의 "Frontmatter 템플릿" 섹션
- **필수 구성 요소**: 레퍼런스의 "필수 구성 요소" 섹션
- **문체 규칙**: 레퍼런스의 "문체 규칙" 섹션
- **Anti-AI 문체 규칙**: `_anti-ai-korean.md`의 규칙을 함께 적용한다:
  - Section 1(AI 습관어)에 해당하는 표현을 사용하지 않는다
  - Section 2(번역투 패턴)에 해당하는 구조를 피한다
  - Section 3(사람처럼 쓰는 기법)의 어미 변화, 문장 길이 변화를 적용한다
  - Section 3.4(스타일별 허용 범위)에서 현재 스타일의 예외 사항을 확인한다

### Step 5: 수정 제안

초안 출력 후 `_anti-ai-korean.md` Section 4(자가 점검 체크리스트)를 기준으로 AI 문체 점검 결과를 먼저 표시한다:

```
🔍 AI 문체 자가 점검 결과
  ✅ AI 습관어 미포함
  ✅ 번역투 패턴 미포함
  ⚠️ 3문단에서 "~합니다" 3회 연속 → 어미 변화 권장
  ✅ 문장 길이 변화 충분
```

점검 결과 표시 후 사용자에게 옵션을 제시한다:

- AI 문체 점검에서 발견된 항목 자동 수정
- 특정 섹션 다시 쓰기
- 톤 조절
- 내용 추가/삭제
- 완료 (현재 상태로 확정)

사용자가 "완료"를 선택할 때까지 반복한다.

### Step 6: 최종 출력

완료 후 처리:

- `--save <path>` 인자가 있으면: 해당 경로에 파일 저장 후 경로 안내
- 인자가 없으면: 사용자에게 저장 여부를 질문
  - 저장 원함 → 경로를 입력받아 Write 도구로 저장
  - 저장 안 함 → 대화창 출력으로 완료

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 이미 작성된 글의 AI 흔적 제거·문체 다듬기 | itda-doc:human-tone |
| 네이버 블로그 키워드 선정(초안 앞 단계) | itda-doc:blog-seo |
| 주장·수치의 출처 검증 | itda-research:ground-check |
| 완성 문서를 한글(hwpx)·HTML 보고서로 조판 | itda-doc:hwpx · itda-doc:html-report |
| 메일 발송 | itda-work:email |

## 권장 체인

```
blog-seo → draft-post → human-tone    (키워드 → 초안 → 송부 직전 검수)
```

`human-tone` 과 같은 글에 겹쳐 적용하지 않는다 — 본 스킬은 생성 단계 사전 가드, `human-tone` 은 후처리 검수(가드 정본).

## 스타일 확장 가이드

### 방법 1: 템플릿에서 직접 작성

1. `references/_template.md`를 참고하여 내용을 작성
2. `{USER_STYLES_DIR}/{새스타일명}.md`에 저장 (Step 0에서 결정된 경로)
   - 디렉토리가 없으면 Write 도구로 저장 시 자동 생성
3. 스킬 실행 시 `--style {새스타일명}`으로 사용

### 방법 2: 기존 자료 분석으로 자동 생성

사용자가 기존 문서(pptx, docx, 메일 HTML, PDF, txt 등)를 제공하면, 해당 자료를 분석하여 새 reference 파일을 자동 생성할 수 있다.

**사용법**: `--analyze <파일경로 또는 디렉토리>`

**지원 형식**:

| 형식 | 분석 방법 |
|------|----------|
| `.md`, `.txt` | Read 도구로 직접 읽기 |
| `.html` | Read 도구로 읽어 HTML 구조 분석 |
| `.docx` | Bash에서 `python3 -c "import zipfile; ..."` 로 document.xml 추출 |
| `.pptx` | Bash에서 `python3 -c "import zipfile; ..."` 로 slide XML 추출 |
| `.pdf` | Read 도구의 PDF 읽기 기능 사용 |
| 디렉토리 | 하위 파일을 모두 스캔하여 공통 패턴 도출 |

**분석 워크플로우**:

1. **파일 읽기**: 제공된 자료를 형식에 맞게 로드
2. **구조 분석**: 문서의 섹션 구조, 반복 패턴, 필수 요소를 파악
3. **문체 분석**: 어미 패턴, 문장 길이, 톤, 용어 사용 빈도를 분석
4. **메타데이터 추출**: frontmatter에 해당하는 메타 정보 식별
5. **레퍼런스 초안 생성**: `_template.md` 구조에 맞춰 분석 결과를 정리
6. **사용자 확인**: 생성된 레퍼런스 초안을 제시하고 수정 요청을 받음
7. **저장**: 확정된 레퍼런스를 `{USER_STYLES_DIR}/{스타일명}.md`에 저장
   - 스타일명이 빌트인 스타일과 동일하면 "빌트인 스타일을 사용자 정의로 오버라이드합니다" 안내 후 저장
   - 디렉토리가 없으면 자동 생성 (`mkdir -p` 상당)
   - **저장 실패 폴백**: Write 도구가 실패하면 (예: `./mnt/` 경로 권한 부족), `USER_STYLES_DIR`를 `.itda-skills/draft-post/styles/`로 재설정하여 재저장을 시도한다. 재저장도 실패하면 채팅에 마크다운 코드블록으로 내용을 출력한다
   - **Cowork + 마운트 없음인 경우**: 저장에 더해 확정된 레퍼런스 내용을 채팅에 마크다운 코드블록으로 출력하여, 사용자가 직접 복사·보관할 수 있도록 안내한다
8. **저장 완료 메시지**: 환경에 따라 다르게 출력:
   - Claude Code 또는 Cowork + 마운트: `"{스타일명}" 스타일이 저장되었습니다. --style {스타일명}으로 사용할 수 있습니다.`
   - Cowork + 마운트 없음: `현재 세션에서 --style {스타일명}으로 사용 가능합니다. 영구 저장하려면 Cowork 대화에 호스트 폴더를 마운트하세요.`

**여러 파일 제공 시**: 공통 패턴을 추출하여 하나의 레퍼런스로 통합한다. 파일 간 차이가 클 경우 사용자에게 어떤 패턴을 기준으로 할지 질문한다.

**분석 결과에 포함되는 항목**:

- 발견된 문서 구조 (섹션 제목, 순서, 계층)
- 감지된 문체 패턴 (어미, 경어 수준, 금지/권장 표현)
- 추출된 frontmatter 후보 필드
- 예시 패턴 (실제 문서에서 발췌, 익명화)
- 기존 스타일 중 가장 유사한 레퍼런스와의 비교

레퍼런스 파일은 자동으로 발견되므로 SKILL.md 수정 없이 스타일을 추가할 수 있다.
다만, "사용 가능한 스타일" 테이블에 추가하면 사용자가 쉽게 찾을 수 있다.
