---
name: pdf-context-refinery
description: >
  PDF를 LLM 컨텍스트·지식베이스용 구조화 마크다운으로 정제하는 스킬입니다.
  "PDF를 마크다운으로 변환해줘", "이 교재를 지식베이스로 만들어줘", "PDF OCR 정리해줘"처럼 말하면 됩니다.
  OCR 정리·표 재구성·섹션 분할·한국어 정규화를 포함합니다.
license: Apache-2.0
compatibility: Claude Code & Cowork
user-invocable: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, mcp__workspace__bash
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "1.4.1"
  category: "domain"
  created_at: "2026-03-21"
  updated_at: "2026-09-30"
  tags: "pdf, markdown, ocr, knowledge-base, rag, conversion"
  triggers-keywords: "pdf to markdown, pdf to md, knowledge base, 마크다운 변환, 지식베이스, OCR cleanup, PDF 변환, PDF 정제"
  triggers-agents: "expert-backend, expert-refactoring"
  triggers-phases: "run"
---

# PDF Context Refinery

## 이 스킬이 하는 일

PDF 원문 추출은 깨진 결과물을 만든다: 띄어쓰기 누락, 테이블 파편화, 문장 단절, 구조 부재. 이 스킬은 그것을 사람이 읽고 LLM이 참조할 수 있는 깨끗한 구조화된 마크다운으로 재구성한다.

## Prerequisites

poppler-utils (`pdftotext`, `pdfinfo`, `pdftoppm`) 필요. Claude Cowork: 기본 설치됨. Ubuntu: `apt-get install -y poppler-utils`. macOS: `brew install poppler`.

Step 1 페이지 판정·Step 6 검증 스크립트가 쓸 스킬 디렉토리 경로를 `SKILL_DIR` 로 확정합니다:

**먼저** 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 `SKILL_DIR` 에 넣고 아래 블록을 실행한다 — 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다(후보가 여럿이면 멈춘다).

```bash
# SKILL_DIR 확정(skill-dir-resolution) — 스킬을 불러올 때 받은 base directory 를 먼저 SKILL_DIR="그 경로" 로 넣는다(항상)
# 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다 — SKILL.md 가 있는 후보가 하나일 때만 받고 아니면 멈춘다
SKILL_DIR=$(sh -c '
S=$1 P=$2 H=${5:-$HOME/.claude}
ok() { d=${1%/}; [ "${d##*/}" = "$S" ] && [ -f "$d/SKILL.md" ] && (cd "$d" && pwd -P); }
[ -n "$3" ] && { ok "$3" && exit; d=${3%/}; [ "${d##*/}" = "$S" ] && echo "SKILL_DIR 무시: $3 에 SKILL.md 가 없다" >&2; }
[ -n "$4" ] && { ok "$4/skills/$S" && exit; echo "CLAUDE_PLUGIN_ROOT 무시: $4/skills/$S 에 SKILL.md 가 없다" >&2; }
c=$(for d in "$H"/plugins/synced/*/"$P"/skills/"$S" "$H"/plugins/synced/*/"$P"~*/skills/"$S" "$H"/plugins/cache/*/"$P"/*/skills/"$S" \
    /root/.claude/plugins/synced/*/"$P"/skills/"$S" /root/.claude/plugins/synced/*/"$P"~*/skills/"$S" \
    /sessions/*/mnt/.remote-plugins/*/skills/"$S" /sessions/*/mnt/.claude/skills/"$S"; do ok "$d"; done | sort -u)
[ "$(printf "%s\n" "$c" | grep -c .)" -gt 1 ] && { printf "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다:\n%s\n" "$c" >&2; exit 1; }
printf "%s\n" "$c"' _ pdf-context-refinery itda-doc "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

> **스캔 PDF**: `pdftoppm`으로 PNG 변환 후 Claude 비전으로 직접 읽는다.

## Pipeline

```
PDF → Analyze → Plan → Extract → Transform → Assemble → Verify
```

## Step 1: Analyze

```bash
pdfinfo "<pdf_path>" | grep Pages
python3 "$SKILL_DIR/scripts/page_quality.py" "<pdf_path>" > .itda-skills/page_quality.json   # 전 페이지 텍스트층 판정
pdftotext -f 1 -l 3 "<pdf_path>" .itda-skills/sample.txt
wc -c .itda-skills/sample.txt
pdftotext -f 1 -l 10 -layout "<pdf_path>" .itda-skills/toc.txt
```

> 임시 파일은 CWD 기준 `.itda-skills/`에 저장한다 (Cowork 컨테이너 호환).

파악할 5가지:
- **언어** — 한국어, 영어, 일본어, 혼합?
- **문서 유형** — 교과서, 매뉴얼, 보고서, 서식 위주?
- **총 페이지 수** — 청킹 전략을 결정한다.
- **목차 유무** — 있으면 섹션 경계 정의에 활용한다.
- **도메인** — `references/README.md` 매핑표와 sample.txt를 대조. 도메인 감지 후 1개만 Read.

### 도메인 감지 (키워드 grep, 임계값 3)

각 도메인 키워드는 `references/README.md` 매핑표 참조. sample.txt에서 도메인별 키워드 카운트를 집계:

- 최고 카운트 도메인이 **임계값 ≥3** → 해당 `references/domain-{name}.md` Read
- 동률이면 README.md 매핑표 순서 기준 첫 번째 선택
- 임계값 미달 → `Domain: not detected (max match count < 3)` 로그, references 미로드

**어느 쪽을 비전으로 읽을지는 `page_quality.json` 의 `needs_vision` 이 정한다** — 첫 3쪽 샘플로 정하지 않는다.
앞은 텍스트인데 뒤의 표·신청자격 쪽만 스캔인 문서가 실재하고(공고 첨부), 샘플 판정은 그 뒤쪽을 조용히 빠뜨린다.
쪽마다 `empty`(글자 0 — 스캔)·`low_text`(글자 40 미만)·`garbled`(대체문자·PUA·제어문자 5% 초과 — 글꼴 매핑 손상)·
`garbled_hangul`(한글 음절은 정상 영역인데 엉뚱한 글자 — ToUnicode 오매핑)·`ok` 로 판정한다. `needs_vision` 의 쪽은
`pdftoppm`으로 PNG 로 바꿔 Claude 비전으로 읽고, 나머지는 텍스트 경로로 간다.
**`garbled_hangul` 쪽의 텍스트는 정리해서 살릴 수 없다** — "뽩 쪀싪텖" 같은 글자는 원문과 대응이 끊긴 것이라 문맥으로 고치면
지어낸 글이 된다. 반드시 비전으로 읽는다. 판정 근거는 쪽별 `hangul_chars`·`no_batchim_ratio`·`rare_batchim_ratio` 에 있다
(한글 30음절 이상에서 받침 없음 < 0.15 이고 겹받침·ㅋㅌㅍ 받침 ≥ 0.15). `doc_needs_ocr: true`(판정 쪽의 30% 이상이
`needs_vision`)면 쪽을 골라 읽지 말고 문서 전체를 비전으로 읽는다.
`sample.txt` 는 언어·도메인 감지용으로만 쓴다.

**비전으로도 읽지 못한 쪽은 결과 머리에 "미검증 쪽: p.N, …" 으로 남긴다** — 다른 스킬(`itda-gov:funding` 등)이
이 목록을 그대로 한계 고지에 옮긴다. `page_quality.py` 가 exit 2(pdftotext 없음·열기 실패)면 그 오류를 그대로 전달한다.

## Step 2: Plan

진행 전에 확인:
- **출력 모드**: 섹션별 파일 또는 단일 파일?
- **이미지 임베딩**: 서식 페이지를 PNG로 렌더링?

### 청킹 전략

| 총 페이지 | 청크 크기 | 이유 |
|-----------|----------|------|
| < 30 | 전체 | 한 번에 처리 가능 |
| 30–80 | 30–40 페이지 | 섹션당 한 패스 |
| 80–200 | 40–50 페이지 | 병렬 패스 |
| 200+ | 50 페이지 최대 | 반드시 병렬화 |

섹션이 50페이지를 초과하면 자연스러운 소절 경계에서 분할하되, 5페이지 오버랩을 둔다. 독립 섹션은 병렬 실행 가능.

## Step 3: Extract

```bash
mkdir -p .itda-skills
pdftotext -f <start> -l <end> -layout "<pdf_path>" .itda-skills/section_raw.txt
# 서식 페이지 이미지 필요 시:
pdftoppm -f <page> -l <page> -png -r 200 "<pdf_path>" .itda-skills/page
```

## Step 4: Transform

핵심 단계. 원시 텍스트를 읽고 구조화된 마크다운으로 재작성한다.

도메인이 감지된 경우 → Step 1에서 Read한 `references/domain-{name}.md`의 §1~6 가이드를 추가 적용한다.
도메인 미감지 또는 medical placeholder → SKILL.md 일반 규칙만 적용.

### 4a. 헤더

```markdown
# [섹션 제목]

> 출처: [문서 제목] ([저자]), p.[시작]~[끝]

---
```

### 4b. 제목 계층

| 문서 요소 | 마크다운 |
|----------|---------|
| 대단원 | `##` |
| 절/주제 | `###` |
| 소절 | `####` |
| 본문 내 번호 항목 | `**(1)**` 인라인 |

섹션 경계에 페이지 마커: `<!-- p.42 -->`

### 4c. OCR 아티팩트 제거

- **페이지 머리글/꼬리글** — 제거. 도메인별 패턴: `references/domain-*.md §6` 참조.
- **글머리 아티팩트** — `- .`이나 `. ` 접두사 → 표준 목록 문법으로 정규화.
- **괄호 간격** — `( 4 )` → `(4)`.
- **고아 조각** — 짧은 줄(< 10자): 문맥에 병합하거나 아티팩트면 제거.

### 4d. 한국어 텍스트 정리

OCR은 띄어쓰기를 제거하는 경우가 많다. 조사(은/는/이/가/을/를/에/의/로/와/과/도/만/까지)는 앞 단어에 붙이고, 뒤에 공백. 문장 중간에서 끝나는 줄은 병합. 영어: 하이픈 단어 재결합.

### 4e. 테이블 복원

표 형식 데이터가 감지되면 반드시 마크다운 테이블을 생성한다. 구조가 모호하면 인용문이나 들여쓴 목록 사용. 도메인별 예시는 `references/domain-*.md §2` 참조.

### 4f. 특수 콘텐츠

- **인용문** (`>`) — 참고사항, 예외, 법률 인용
- **계산 예시** — 명확한 들여쓰기로 단계별 표시
- **목록** — `-`로 글머리, 적절한 중첩
- **도메인별 참조 형식** — `references/domain-*.md §3` 참조

### 4g. 서식 페이지 (이미지 모드 활성화 시)

서식/템플릿 위주 페이지는 `![서식 이름](images/p0XXX.png)` 형태로 이미지 렌더링. **주요 필드**: 간단한 설명 추가.

## Step 5: Assemble

**단일 파일 모드** — 목차 포함 .md 1개. **다중 파일 모드** — `{NN}_{설명_이름}.md` 번호 정렬 + `INDEX.md`.

## Step 6: Verify

```bash
python3 ${SKILL_DIR}/scripts/verify_quality.py <output_dir_or_file> --pages <total_pages>
# 도메인 지정 시 추가 검증 항목 활성화
python3 ${SKILL_DIR}/scripts/verify_quality.py <output_dir_or_file> --pages <total_pages> --domain <domain>
```

도메인 옵션: `tax-accounting`, `electronics`, `legal`, `engineering`

| 문서 유형 | 건강 범위 | 내용 손실 임계값 |
|----------|---------|---------------|
| 밀집 교과서 | 15–45줄/페이지 | < 8줄/페이지 |
| 기술 매뉴얼 | 10–20 | < 7 |
| 서식 위주 | 3–8 | < 2 |

검증 실패 섹션은 더 작은 청크로 재처리한다 (페이지 범위를 반으로 줄인다).

## Failure Recovery

1. **내용이 너무 짧음** — 청크 크기를 반으로 줄여 재추출
2. **테이블 깨짐** — `-layout` 없이 시도하거나 `tabula-py` 사용
3. **인코딩 문제** — `iconv -f CP949 -t UTF-8`로 변환
4. **스캔 PDF** — `pdftoppm -png -r 300` 후 Claude 비전으로 직접 읽기

## Evaluation

도메인별 평가 케이스는 `references/domain-*.md §7` 참조.
