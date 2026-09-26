---
name: design-core
description: >
  브랜드 디자인을 고르고(getdesign 표준 DESIGN.md 카탈로그 차용), 만들고(한국·자사 브랜드 저작), 검증·조회해
  웹·PPTX·DOCX·XLSX 여러 매체에 일관 적용하는 디자인 시스템 허브 스킬입니다.
  "스포티파이 톤으로 디자인 골라줘", "우리 브랜드 디자인 시스템 정의해줘", "이 DESIGN.md 검증해줘"처럼 말하면 됩니다.
license: Apache-2.0
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, WebFetch, AskUserQuestion, mcp__workspace__bash, mcp__workspace__web_fetch
argument-hint: "<브랜드/톤 키워드 또는 DESIGN.md 경로>"
metadata:
  author: "스킬.잇다"
  version: "0.6.3"
  category: "design"
  status: "beta"
  recommended: true
  created_at: "2026-06-21"
  updated_at: "2026-09-25"
  tags: "design-system, design-tokens, design-md, getdesign, palette, typography, branding"
---

# 디자인 시스템 코어 (design-core)

브랜드 디자인의 **허브**입니다. 성격이 다른 두 레이어를 관리합니다(#1021):

- **직해석 레이어 — 표준 DESIGN.md** (Google Stitch 포맷: 9섹션 산문 + 확장 frontmatter, `schema/design-md-standard.md`). getdesign.md 카탈로그(75종 브랜드, MIT)에서 **차용**하거나, 카탈로그에 없는 브랜드(한국·자사·사이트 없는 신규)를 같은 포맷으로 **저작**합니다(`catalog/`). 에이전트가 **원문을 직접 읽어** 웹·PPTX 등에 적용 — 1회성 산출물의 정본 경로.
- **결정론 레이어 — design-core 토큰(v2)** (`library/` 프리셋 8종 + `scripts/design_core.py`). docx-design(dockit)·xlsx-design(sheetkit) 등 **코드 렌더러**가 소비하는 opendesign 4계층 토큰 계약(`schema/design-md-v2.md`) — 반복 파이프라인의 톤 drift 0·`validate.py` 검증 가능성이 목적.

> [HARD] **표준 DESIGN.md 를 `design_core.load()` 에 넣지 않는다.** 자동 매핑이 풍부한 원문을 깎는다(실측 #1021: minimax `accent #ff5530`→None·font→None, bmw-m 원본 신호 76개→유효 5색). 표준 파일은 **직해석이 정본**이고, `load()` 는 v2/v1 프리셋 전용이다.

## getdesign-first 워크플로우 (표준 DESIGN.md 차용)

톤·브랜드 요청("스포티파이 느낌", "핀테크 다크 톤", "스트라이프처럼")이 오면 아래 순서로 진행합니다. 브랜드가 이미 명확하면 ①②를 건너뛰고 ③부터.

1. **선택** — `npx -y getdesign@latest list` 로 카탈로그(75종, `slug - 한줄설명`)를 받아 톤·주제 키워드에 맞는 **후보 2~3종**을 고릅니다. 카테고리 축(AI/개발도구/핀테크/자동차 등 9종)이 필요하면 awesome-design-md README 를 참조. 한국·문서 톤은 `catalog/`(한국 확장)과 `library/`(v2 프리셋)가 먼저입니다.
2. **프리뷰** — 후보별 raw DESIGN.md 를 fetch 해(아래 ③의 raw URL) 각각 **직해석 미니 프리뷰**(단일 HTML: 스와치·타이포 위계·버튼·카드 — 관습은 `schema/design-md-standard.md`)를 렌더해 나란히 제시하고, getdesign 상세 URL(`https://getdesign.md/<slug>/design-md`)을 병기합니다. `AskUserQuestion` 으로 확정받습니다.
3. **획득** — 정본은 CLI, 실패(네트워크/Node 부재) 시 raw 폴백(마스터 승인 2026-07-11):

   ```bash
   npx -y getdesign@latest add <slug> [--out <경로>]   # 정본 — 기본 ./DESIGN.md
   # 폴백:
   curl -fsSL https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/<slug>/DESIGN.md -o DESIGN.md
   ```

4. **매체 라우팅** — 획득한 원문을 매체별 정본 경로로 보냅니다:

   | 매체·용도 | 경로 |
   |---|---|
   | 웹/HTML·React | **원문 그대로** 프로젝트 루트 `DESIGN.md` 로 두고 UI 작성 전 참조(getdesign 본래 용도) |
   | PPTX 발표자료 | 원문을 `pptx-design` 관문2 "DESIGN.md 제공 시" 경로로 전달(3열 필터·한글 가드는 그쪽 책임) |
   | DOCX/XLSX **1회성** | 원문 직해석 — 핵심 hex(primary·ink·surface·hairline·의미색)를 `gen.py` 에 직접 인용 |
   | DOCX/XLSX **반복 파이프라인** | 결정론 토큰 필요 — v2 프리셋(`library/`)을 쓰거나, 원문 핵심 토큰을 v2 로 옮겨 적고(사람 확인) `load()` 경로 사용 |

5. **CJK Addendum** — 한글 산출물이 목적이면 획득한 DESIGN.md **끝에** "Korean Typography Addendum" 섹션을 추가합니다(템플릿: `schema/design-md-standard.md`). 원문을 깎는 게 아니라 **증보**입니다(MIT — 수정 자유). getdesign 원문은 라틴 전제(음수 자간·Light 본문·독점 서체)라 이 증보 없이는 한글 산출물이 깨질 수 있습니다.
6. **갭 필러(저작)** — 카탈로그·`catalog/`·`library/` 모두에 없으면 아래 저작 워크플로우(관문 A~E)로 **같은 표준 포맷**의 DESIGN.md 를 생성합니다.

## 위치 (SSOT)

- **표준 스키마·차용 가이드**: `schema/design-md-standard.md` — 9섹션 스펙·획득 명령·직해석 원칙·CJK Addendum 템플릿·미니 프리뷰 관습.
- **한국 확장 카탈로그**: `catalog/` — getdesign 에 없는 브랜드를 표준 포맷으로 저작한 항목(`catalog/README.md`).
- **v2 토큰 라이브러리(결정론)**: `library/` — 프리셋 8종(consulting-mbb·equity-research-dark·warm-editorial·print-broadsheet·tech-vivid-dark·minimal-mono·samsung-sds·kari). 선택 표는 `library/README.md`.
- **v2 스키마**: `schema/design-md-v2.md`(토큰 그룹·constraints — 코드 소비용 dialect), `schema/token-layers.md`(4계층·allowlist).
- **매체 매핑(v2)**: `mapping/pptx.md`·`mapping/docx.md`·`mapping/xlsx.md`·`mapping/web-css.md`, `mapping/cardnews.md`(후속 스텁).
- **코드(결정론 레이어)**: `scripts/design_core.py`(로더·정규화·조회), `scripts/validate.py`(v2 검증기), `scripts/preview.py`(v2 프리뷰).

## 어떤 매체로 갈 것인가

| 매체 | 경로 | 상태 |
|---|---|---|
| **웹/HTML·CSS** | 표준 DESIGN.md 원문 참조(위 워크플로우) — Claude 가 직접 렌더, 어댑터 불필요 | ✅ 정본. v2 `to_css_vars()` 는 결정론 브랜드 전환용 보조 |
| **PPTX 발표자료** | `pptx-design` 스킬(형제) — 표준 DESIGN.md 원문 또는 v2 프리셋을 소비하는 무거운 렌더 어댑터 | ✅ 가동. Claude 가 `.pptx` 를 직접 못 만들어 deckkit 이 **필수** |
| **DOCX 보고서** | `docx-design` 스킬(형제) — 1회성=원문 직해석, 반복=`docx_styles()`(v2) | ✅ 가동 |
| **XLSX 스프레드시트** | `xlsx-design` 스킬(형제) — 1회성=원문 직해석, 반복=`xlsx_styles()`(v2) | ✅ 가동 |
| 카드뉴스 이미지 | `mapping/cardnews.md` | 🔜 구조 스텁(후속) |

> **매체별 비대칭(핵심)**: pptx 는 Claude 능력 밖(이진 OOXML·한글 렌더·차트 객체)이라 `pptx-design` 코드 파이프라인이 반드시 필요합니다(원문/토큰 공급원 ↔ 렌더 엔진). 반면 web 은 Claude 자신이 렌더 엔진이라 표준 DESIGN.md 원문이면 충분합니다.

## 사용법 — 결정론 레이어 (v2 프리셋·토큰)

### 0) 실행 전 — 스킬 디렉토리 확정

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/design-core}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/design-core' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\design-core"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

### 0-b) 의존성 설치 (처음 한 번)

```bash
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# Windows: py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

### 1) 토큰 조회 (프로그래밍 — v2/v1 프리셋 전용)

```bash
# macOS/Linux
python3 -c "import sys; sys.path.insert(0,'$SKILL_DIR/scripts'); import design_core as dc; \
  t=dc.load('consulting-mbb'); print(t.color); print(t.pptx_palette())"
# Windows
py -3 -c "import sys; sys.path.insert(0,'$env:SKILL_DIR/scripts'); import design_core as dc; t=dc.load('consulting-mbb'); print(t.color)"
```

`design_core.load(<이름|경로|frontmatter dict|v2 DESIGN.md 텍스트>)` → 정규화된 `DesignTokens`. v1 평면 형식도 자동 승격(legacy 무중단). `.docx_styles()`/`.xlsx_styles()`/`.pptx_palette()` 는 코드 렌더러 호환 평면 스타일. **표준 DESIGN.md(9섹션+다단 역할 frontmatter)는 비대상**(위 [HARD]).

### 2) 검증 (v2 전용)

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/validate.py" --all            # library 전체
python3 "$SKILL_DIR/scripts/validate.py" consulting-mbb    # 단건
```

ERROR(A1 계층 무결성·hex 유효성) 1건이라도 있으면 종료코드 1. **표준 포맷 저작물의 검증**은 validate.py 가 아니라 `schema/design-md-standard.md` 의 9섹션 체크리스트 + 직해석 미니 프리뷰 눈검증입니다.

## 디자인 저작 워크플로우 (새 디자인 생성 — 관문 A~E)

새 디자인을 만들 때는 추측하지 말고 **물어보고 → 보여주고 → 확인받고 → 생성**합니다.

- **관문A 입력 인터뷰** — 먼저 **경로 분기**를 확인합니다: ⓐ **getdesign 차용**(유명 브랜드·서구 톤이면 기본값 — 위 워크플로우로 이동) ⓑ **기존 프리셋/카탈로그**(`library/` 8종·`catalog/` — 한국·문서 톤·반복 파이프라인) ⓒ **신규 저작**. ⓒ일 때 `AskUserQuestion` 으로 수집: ① 매체(발표자료/웹/문서 + 반복 파이프라인 여부) ② 브랜드 색(hex 있으면 그대로, 없으면 톤·업종에서 파생) ③ 분위기·톤 ④ 의미색 관행(international/krx) ⑤ 베이스(카탈로그 항목·프리셋) 변형 여부.
- **관문B 정보 충분성 게이트** — 산출 포맷별 최소 정보를 검토합니다. **표준 포맷(기본)**: frontmatter 핵심 색 역할(canvas/surface/ink/muted/primary/hairline 급) + 타이포 방향 + 9섹션을 채울 톤 서사. **v2 병행(반복 파이프라인 목적일 때)**: A1-identity(색 7 + 폰트 2)를 결정해 `validate.py` ERROR 0 확인. 부족하면 관문A 로 되돌아가 더 묻습니다.
- **관문C 프리뷰** — **표준 포맷**: 직해석 미니 프리뷰 HTML 을 렌더해 제시. **v2 병행**: `python3 "$SKILL_DIR/scripts/preview.py"` 로 web 한 장 + pptx 표지 한 장. 가능하면 `open` 으로 엽니다.
- **관문D 컨펌** — 프리뷰(+ v2 면 validate 결과)를 제시하고 OK/수정을 받습니다. 수정이면 토큰을 조정해 **관문C 로 루프**. 컨펌 없이 관문E 로 가지 않습니다.
- **관문E 생성** — **표준 포맷(기본)**: 9섹션 + frontmatter 완결 + **Korean Typography Addendum** + Known Gaps 정직 서술로 저장 — 재사용 카탈로그면 `catalog/<slug>/DESIGN.md`(+ 프리뷰 html), 1회성이면 사용자 작업 폴더 `DESIGN.md`. **v2 병행**: `library/<name>.md` 또는 `<name>.design.md` 를 함께 산출. 이후 발표자료는 `pptx-design`, 웹은 원문 참조로 바로 적용됨을 안내합니다.

> **기존 디자인 커스텀**: 관문A 에서 베이스(카탈로그 항목·프리셋)를 고르면 복사해 색·모티프만 바꾸는 빠른 경로로 들어갑니다(관문 B~E 동일). 처음부터 새로 만드는 것보다 안전합니다.
> **한글 본문 폰트**(v2)는 `kr-safe-gothic` 센티널을 유지하세요(어댑터 CJK 가드가 안전 고딕 강제·음수 자간 클램프).

## 토큰 계층 (요약 — 결정론 레이어)

- **A1-identity** — 토큰이 곧 브랜드(fallback 불가): `color.{bg,surface,fg,muted,primary,accent,border}`, `font.{display,body}`.
- **A1-structure** — 구조 결정(브랜드별 정의, 크로스브랜드 기본값 없음): `space`, `type-scale`, `layout`.
- **A2** — 필수+fallback 존재: `semantic.{up,down}`, `radius`.
- **B-slot** — 선택(상위 sibling alias): `surface_2→surface`, `fg_2→fg`, `border_soft→border`.
- **C-extension** — 브랜드 전용 allowlist: `motif`, `editorial`(do/dont). ≥2 브랜드가 같은 이름을 쓰면 B-slot→A2 로 승격.

자세히는 `schema/token-layers.md`.

## 매체 중립 원칙

design-core 는 어떤 매체 API(python-pptx 등)도 import 하지 않습니다. 매체별 표현 제약은 v2 토큰의 `constraints.<media>` 프로필로 선언하고(예: `constraints.pptx.cjk_guard`), 실제 렌더는 각 어댑터가 책임집니다. 표준 DESIGN.md 경로에서도 같은 원칙 — 매체 필터(예: pptx 3열 필터)는 **소비하는 어댑터 스킬**이 책임지고, design-core 는 원문 획득·증보(CJK Addendum)까지만 책임집니다.
