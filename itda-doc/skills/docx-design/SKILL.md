---
name: docx-design
description: >
  콘텐츠 마크다운과 수치 데이터로 디자인된 Word 문서(.docx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는 스킬입니다.
  design-core 디자인 토큰(팔레트·타이포·표 스타일·간격)을 해석해 표지·헤딩·표·콜아웃·페이지번호에 반영하고, 한글은 eastAsia 안전 폰트로 분리 바인딩합니다.
  "NovaTech 연차보고서 docx로 만들어줘", "이 프리셋으로 워드 보고서 디자인해줘", "md 내용으로 디자인된 워드 문서 생성"처럼 말하면 됩니다.
license: Apache-2.0
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, WebFetch, AskUserQuestion, mcp__workspace__bash, mcp__workspace__web_fetch
argument-hint: "<콘텐츠.md> [데이터.json] [프리셋 또는 DESIGN.md 경로] [출력.docx]"
metadata:
  author: "스킬.잇다"
  version: "0.4.0"
  category: "document"
  status: "beta"
  recommended: true
  created_at: "2026-06-29"
  updated_at: "2026-09-25"
  tags: "docx, word, report, design-md, document"
---

# DOCX 디자인 생성 (docx-design)

콘텐츠 명세(Markdown 아웃라인)와 수치 데이터(JSON/표)를 입력받아, 디자인된 Word 문서(.docx)를 **신규 생성**합니다. `pptx-design` 의 docx 형제로, **design-core** 매체중립 토큰을 공유합니다(SSoT). 생성은 순수 Python(`python-docx`)으로 수행되어 **macOS/Linux/Windows 에서 Microsoft Office 없이** 동작하며, 검증·미리보기 렌더는 Windows=Word COM / 그 외=LibreOffice 로 처리합니다.

> **왜 이 스킬인가(#655 근거)**: 손-오케스트레이션으로 만든 Word 문서는 평이한 출력에 머뭅니다. 본 스킬은 `pptx-design` 패턴을 docx 에 복제해 — 동일 콘텐츠를 프리셋만 바꿔 **시각적으로 구별되는 디자인 문서**로 산출합니다.

## 백엔드

- **python-docx(`gen.py` + `scripts/dockit.py`)**: 크로스플랫폼·성숙·Office 불필요. **항상 이 경로로 생성한다.**

**비목표**: 기존 회사 .docx 편집·병합·브랜드 마스터 적용, 코멘트·변경추적·TOC 필드 같은 Word 네이티브 의미 요소는 본 스킬(신규 디자인 생성기)의 범위가 아니다.

---

## 사전 준비: 의존성 + 도구 탐색

세션 내 1회만 확인합니다.

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/docx-design}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/docx-design' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

# macOS/Linux — 정문(기본: python-docx·PyYAML · `--all` 로 PyMuPDF·Pillow 까지)
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\docx-design"  # 미설정이면 SKILL.md 위치 절대경로 사용

# Windows — 정문(pywin32 는 마커로 Windows 에서만 설치된다)
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백: py -3 -m pip install --user -r "$env:SKILL_DIR\requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

- **생성**(관문3)은 `python-docx` 만으로 충분합니다(Office·LibreOffice 불필요).
- **검증·미리보기**(관문4)의 렌더는 Windows 에서 Word COM(설치 시), 그 외에서 LibreOffice(`soffice`)를 씁니다. **없어도 HARD GATE(빈문서·토큰·한글 바인딩)는 정상 판정**되고, 렌더 의존 검사(빈 페이지)만 생략되며 `render_unavailable` advisory 로 표면화됩니다.

레퍼런스:
- **★디자인 프리셋(ready-to-use 8종)**: `../design-core/library/` — 선택 표는 그 안의 `README.md`. 톤 키워드("컨설팅"·"에디토리얼"·"신문"·"미니멀"…)가 오면 여기서 1종을 골라 적용.
- **★표준 DESIGN.md 차용(getdesign 75종 + 한국 확장 `../design-core/catalog/`)**: 유명 브랜드 톤이 오면 design-core getdesign-first 워크플로우(`../design-core/SKILL.md`)로 원문을 획득해 관문2 "표준 DESIGN.md 제공 시" 경로로 소비(`../design-core/schema/design-md-standard.md`).
- **토큰 → Word 스타일 매핑**: `../design-core/mapping/docx.md`
- **DESIGN.md → docx 3열 필터 + 재현 카탈로그**: `references/design-md-mapping.md`
- **공개 헬퍼 API**: `scripts/dockit.py` (생성 스크립트가 import) · **검증기**: `scripts/verify.py` · **렌더기**: `scripts/render.py`
- **동작 예제**: `examples/sample/` (NovaTech FY2025 — content.md · data.json · design.md · gen.py)

---

## Claude 오케스트레이션 지시서 ([HARD] 관문)

아래 5개 관문을 **순서대로** 통과합니다. 특히 **관문4(검증 게이트)는 절대 건너뛰지 마세요.**

### 관문1 — 입력 수집

1. **콘텐츠 명세(필수)** — 문서 아웃라인 Markdown(섹션·표지·각 섹션의 제목/본문/표/KPI). 콘텐츠는 SSoT 로 고정하고 디자인만 변수입니다.
2. **수치 데이터(표·KPI 가 있으면 필수)** — JSON 또는 표. 모든 수치는 여기서 인용(손입력 금지, 데이터 정확성 우선).
3. **프리셋/DESIGN.md(선택)** — 프리셋 이름·로컬 경로·URL. 미제공이고 톤 키워드도 없으면 관문2의 대화형 톤 선택 게이트로 갑니다.

발화가 모호하면(섹션 수·데이터 출처 불명) 진행 전 1회 확인합니다.

### 관문2 — 디자인 시스템 해석

- **프리셋/DESIGN.md 미제공 + 톤 신호 있음 → 바로 진행**: `../design-core/library/README.md` 선택 표에서 주제 적합 프리셋 1종을 골라 적용합니다(연차보고서·IR·전략 → consulting-mbb, 데이터 리포트·에디토리얼 → warm-editorial, 저널·인쇄 → print-broadsheet, 프리미엄·제품 → minimal-mono 등).
- **무신호 + 대화형 → [HARD] 톤 선택 게이트**: 주제 적합 후보 2~3종 + "주제에 맞게 알아서" 를 `AskUserQuestion` 으로 제시합니다.
- **무신호 + 비대화형 → 자동 선택 폴백**: 주제·톤에 맞는 프리셋 1종을 스스로 골라 적용하고, 선택 근거를 한 줄 남깁니다.
- **프리셋/v2 DESIGN.md 제공 시**: `design_core.load(<경로>)` → `docx_styles()` 로 토큰을 받습니다. 핵심 팔레트 hex 를 헤딩·표 헤더·콜아웃·규칙선에 실제로 반영합니다.
- **★표준 DESIGN.md(Stitch/getdesign — 9섹션 + 다단 역할 frontmatter) 제공 시**: `load()` **비대상**입니다(자동 매핑이 원문을 깎음 — `../design-core/schema/design-md-standard.md` [HARD]). **원문을 직해석**해 핵심 hex(primary·ink·surface·hairline·의미색)를 `gen.py` 에 직접 인용하고, 한글 eastAsia 분리 바인딩(dockit)은 그대로 방어합니다. **반복 파이프라인**(정기 산출)이면 v2 프리셋을 쓰거나 핵심 토큰을 v2 로 옮겨 적어(사람 확인) `load()` 경로로 태웁니다.
- **★한글 정책(docx 재설계 — pptx 가드 verbatim 이식 ❌)**: Word 는 한글을 네이티브로 정상 렌더합니다. 핵심은 run 의 `w:rFonts` 를 **ascii/hAnsi(라틴 디스플레이) ↔ eastAsia(안전 한글 고딕)로 분리 바인딩**하는 것입니다 — dockit 의 `set_run_font` / `apply_design` 이 자동 집행합니다. 라틴 디스플레이가 세리프여도 한글은 고딕으로 분리되어 "세리프 헤드 + 한글 고딕" 이 깔끔히 공존합니다(pptx LibreOffice 경로가 못 하던 것). 음수 자간 클램프는 불필요(Word 정상 처리).
- **재현 천장 인지**: Word 단락/표에는 모서리 반경(`radius`)이 없고(무시), 네이티브 그라디언트는 비1급(필요 시 Pillow PNG 임베드·표지 한정). 색·헤딩 위계·표 스타일·헤더/푸터·간격은 높은 재현입니다(`references/design-md-mapping.md`).

### 관문3 — 생성 (`gen.py` 작성)

per-invocation 생성 스크립트 `gen.py` 를 작업 디렉토리에 작성·실행합니다. **반드시 `scripts/dockit.py` 의 공개 API 를 import** 합니다(직접 python-docx 보일러플레이트 금지):

```python
import sys, os
SKILL_DIR = "<위 블록에서 확정한 이 스킬 디렉토리 절대경로>"
DESIGN_CORE = os.path.join(SKILL_DIR, os.pardir, "design-core")
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))                        # dockit
sys.path.insert(0, os.path.join(DESIGN_CORE, "scripts"))                      # design_core
import dockit as dk
import design_core as dc

st = dc.load("consulting-mbb").docx_styles()       # 또는 경로/DESIGN.md
doc = dk.new_doc(margin_in=st["margin_in"], page=st["page_size"])
th = dk.apply_design(doc, st)                       # Normal/Heading 스타일·여백·eastAsia 설정
dk.kicker(doc, "EXECUTIVE SUMMARY")
dk.heading(doc, "핵심 요약", level=1)
dk.kpi_strip(doc, [("$4.82B", "연간 매출"), ...])
dk.add_table(doc, headers=[...], rows=[...], col_align=["left","right",...])
dk.callout(doc, [("요약  ", dict(bold=True)), ("...", {})])
dk.set_footer(doc, left="...")                      # 페이지번호 N / M
dk.save_doc(doc, OUT)
```

준수 사항:
- **한글 폰트(자동 분리 바인딩)**: dockit 빌더는 theme 의 라틴/한글 폰트를 자동 적용합니다. 직접 run 을 만들면 `dk.set_run_font(r, latin=..., kr=...)` 로 — 한글이 있으면 `kr` 미지정 시 안전 고딕을 자동 바인딩합니다.
- **색은 토큰에서만**: `st["primary"]`·`st["accent"]`·`st["up"]`/`st["down"]`(의미색) 등 design-core 토큰을 씁니다(기본 파랑/회색 손지정 금지).
- **표는 dockit `add_table`**: 헤더 fill + zebra + 헤어라인 테두리가 자동 적용됩니다(기본 Word 표 스타일 금지).
- **레이아웃 다양화**: 표지(색 밴드)·요약(KPI+콜아웃)·표·불릿·클로징을 서로 다르게 구성합니다.
- **결정론**: 난수 미사용(동일 입력 → 동일 산출).
- 생성 산출물은 **스킬/작업 디렉토리 안에서만** 씁니다.

### 관문4 — ★검증 게이트 [HARD — 건너뛰기 금지]

생성된 docx 에 `scripts/verify.py` 를 실행해 **HARD GATE PASS** 를 확보합니다.

```bash
# 필수 토큰 파일(콘텐츠/데이터 핵심 명칭·수치를 1줄 1토큰) 작성 후:
py -3 "$env:SKILL_DIR\scripts\verify.py" <생성.docx> --tokens tokens.txt    # Windows
python3 "$SKILL_DIR/scripts/verify.py" <생성.docx> --tokens tokens.txt        # macOS/Linux
```

- **HARD GATE = (빈문서 + 토큰누락 + 한글_eastAsia_미바인딩 + 저대비) == 0**. PASS 시 exit 0.
- **한글 eastAsia 미바인딩은 HARD**입니다 — 라틴 폰트가 한글 글리프를 먹어 깨지는 재앙을 차단합니다(이 SPEC 의 핵심 불변량).
- **저대비(가독성)도 HARD**입니다(#668) — run 글자색 ↔ 효과적 배경(셀/단락 음영 → 페이지 흰색) WCAG 대비가 **3.0:1 미만이면 FAIL**. 다크 프리셋 토큰을 라이트 본문에 보정 없이 쓰면 여기서 잡힙니다. **다크 프리셋(equity-research-dark·tech-vivid-dark·kari)은 샌드위치**(표지/클로징 다크 밴드 + 라이트 본문)로 렌더됩니다 — docx 는 인쇄 가능한 페이지 배경이 없어 전면 다크 본문이 불가하기 때문(`../design-core/mapping/docx.md` 정책). design-core 어댑터가 토큰을 자동 보정하므로 `gen.py` 는 강조 텍스트에 `primary_text`, 밴드 fill 에 `primary`/`ink` 를 쓰면 됩니다.
- **advisory**(비차단): 약대비(`weak_contrast` 3.0~4.5)·eastAsia 가 라틴 폰트로 바인딩된 의심(`kr_eastasia_latinish`)·헤딩 0개(`no_headings`)·빈 표 셀·빈 페이지·렌더 불가. 검토해 가독성·위계를 교정합니다.
- **FAIL 시**: `_verify/<stem>.json` 을 Read 로 확인 → 원인을 `gen.py` 에서 수정 → 재생성·재검증. PASS 까지 반복합니다.
- **시각 QA 보강**: 게이트 PASS 후에도 렌더 PNG(`_verify/<stem>_render/*.png`)를 Read 로 직접 보고(저대비·오정렬·표 넘침·불필요한 래핑) 최소 1회 수정-재검 사이클을 돕니다.

검증 게이트를 생략하거나 FAIL 인데 산출로 진행하는 것은 **[HARD] 위반**입니다.

### 관문5 — 산출

1. **DOCX** — 최종 .docx 경로.
2. **렌더 미리보기** — `python3 "$SKILL_DIR/scripts/render.py" <docx>` 가 생성한 페이지 PNG 경로.
3. **검증 요약** — HARD GATE 결과(빈문서/토큰/한글바인딩 = 0 PASS), advisory 신호, 적용 프리셋·핵심 팔레트 hex 와 반영 위치, 재현 한계에 걸린 토큰과 대체 처리.

---

## 검증 도구 빠른 참조

| 도구 | 역할 | 호출 |
|---|---|---|
| `scripts/dockit.py` | 공개 헬퍼 API(생성 스크립트가 import) | `import dockit as dk` |
| `scripts/verify.py` | 빈문서/토큰/한글바인딩/구조/렌더 검증 + HARD GATE | `python3 "$SKILL_DIR/scripts/verify.py" <docx> [--tokens t.txt] [--out DIR] [--no-render]` |
| `scripts/render.py` | Word COM(Win) / LibreOffice 렌더 → PDF → PNG | `python3 "$SKILL_DIR/scripts/render.py" <docx> [out_dir] [--dpi N]` |

`verify.py` 는 PASS 시 exit 0, FAIL 시 exit 1 을 반환하므로 자동화에서 분기 가능합니다.

---

## 에러 처리

| 상황 | 대응 |
|---|---|
| `python-docx` 미설치 | `"$SKILL_DIR/requirements.txt"` 로 설치(macOS/Linux `python3 -m pip`, Windows `py -3 -m pip`) |
| 렌더 도구 부재(Word COM/soffice 모두 불가) | 생성은 가능함을 알리고, 검증/미리보기 렌더만 생략(advisory). 실행 가능한 검증과 공백을 분리 보고 |
| 한글 eastAsia 미바인딩(HARD FAIL) | `gen.py` 에서 dockit 빌더 사용 확인 또는 `set_run_font(r, kr=dk.kr_font_name())` 명시 → 재생성·재검증 |
| 코멘트/변경추적/TOC 보강 요청 | 본 스킬 비목표 — 생성한 .docx 를 Word 에서 열어 직접 추가하도록 안내 |
| 기존 회사 docx 편집/병합/브랜드 마스터 | 본 스킬(신규 생성기) 비목표 |
