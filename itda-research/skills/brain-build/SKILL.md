---
name: brain-build
description: >
  회사 공유폴더의 비정형 문서 무더기(워드·엑셀·PPT·PDF·한글 HWP·txt 수십~수백 개)를 근거 추적 가능한 업무DB(뇌)로 만드는 빌드 스킬입니다. 원본을 전수 열람해(원본 불가침) 주제별 위키 페이지 + INDEX.md + CLAUDE.md(질답·운영 규율) + 문제파일.md 를 생성하고, 문서 규약을 역공학하며, 끝에 독립 검수(brain-auditor)를 1회 자동 실행합니다. "이 폴더를 업무DB로 만들어줘", "공유폴더 정리해서 뇌로 만들어줘", "이 문서들 근거 추적 가능하게 정리", "회사 두뇌 구축", "업무DB 빌드"처럼 말하면 됩니다.
  원본 불가침 — 원본 파일은 절대 수정·이동·삭제하지 않고 읽기만 합니다. 산출물은 새 업무DB 폴더입니다.
license: MIT
compatibility: "Python 3.10+ (오케스트레이션 스킬 — 문서 판독은 에이전트 경유)"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, Skill, mcp__workspace__bash
argument-hint: "[소스 폴더 경로] (예: ~/회사공유폴더)"
metadata:
  author: "Chinseok"
  version: "0.4.1"
  category: "knowledge-base"
  status: "experimental"
  recommended: false
  created_at: "2026-07-14"
  updated_at: "2026-09-30"
  tags: "knowledge-base, second-brain, provenance, unstructured, docx, xlsx, pptx, pdf, hwp, hwpx, wiki, reverse-engineering, convention, incubating"
---

# brain-build

회사 공유폴더에는 워드·엑셀·PPT·PDF·한글(HWP·HWPX)·txt 가 폴더마다 흩어져 있다. "최종"·"진짜최종"·"개정안"
같은 파일명은 어느 게 진짜 최신인지 알 수 없고, 계약 단가와 실제 발주 단가가 달라도 아무도 못
잡는다. brain-build 는 이 무더기를 **근거 추적 가능한 업무DB(뇌)**로 만든다 — 원본을 전수
읽어 주제별 위키로 정리하고, 문서 규약을 역공학하고, 끝에 독립 검수로 문서 사이 모순까지 잡는다.

itda-research 비정형 문서 vertical 의 빌드 담당. (SPEC-BRAIN-VERTICAL-001, #1122 — IGM 업무DB 실습키트 3차 리허설 실측 설계.)

---

## Claude 오케스트레이션 지시서

> [HARD] **원본 불가침.** 소스 폴더의 원본 파일을 절대 **수정·이동·삭제·이름변경 하지 않는다.** 읽기 전용으로만 접근한다. 산출물은 원본과 분리된 **새 업무DB 폴더**다. (SPEC INV-1)
> [HARD] **전수성.** 원본을 하나도 건너뛰지 않는다. 읽을 수 없거나 정상 문서가 아닌 파일(손상·잠금 임시파일 `~$*`·빈 문서)도 `문제파일.md`에 사유와 함께 기록해 커버한다. (REQ-022)
> [HARD] **근거 강제.** 위키 본문의 모든 수치·금액·날짜·결정 뒤에 근거 원본 경로를 괄호로 인라인 표기한다. 근거 없는 값을 지어내지 않는다. (REQ-020)
> [HARD] **모순 보존.** 서로 다른 문서가 같은 대상에 다른 값을 담으면 임의로 하나를 고르지 않고 양쪽 값·근거를 남긴다. 판정은 검수(brain-auditor)에 맡긴다. (REQ-021)
> [HARD] **빌드 끝에 brain-auditor 를 1회 자동 호출**해 검수 4각도를 실행한다(관문7). 검수는 빌드 기억과 격리된 컨텍스트에서 원본을 다시 열어 수행한다.

### 입력

- **소스 폴더 경로** (필수, **1개 한정 — v1 단일 소스**) — 원본 문서 무더기가 있는 폴더. 하위 폴더 재귀 포함. 폴더 2개 이상을 요청받으면 **명시 거부**하고 폴더별로 뇌를 분리 빌드할 것을 제안한다 — 신선도 기준선(manifest)·근거 상대경로가 단일 루트 전제라, 다중 소스를 그대로 받으면 기준선이 한쪽 폴더만 대표하거나 상대경로가 충돌해 신선도 레이어가 조용히 틀린 답을 낸다(SPEC-BRAIN-VERTICAL-001 v1 범위).
- **뇌 이름** (선택) — 미지정 시 소스 폴더명 또는 사용자 확인으로 정한다.
- **업무DB 출력 경로** (선택) — 미지정 시 소스 폴더 **옆에** `<뇌 이름>_업무DB/` 로 만든다(원본 트리 밖 — 원본 불가침).

### 관문0 — 스킬 디렉토리(SKILL_DIR) 확정

스킬 자산(템플릿·헬퍼 스크립트·에이전트 지시서)은 cwd 에 의존하지 않도록 **절대경로**로 읽는다. 실행 절 첫머리에서 `SKILL_DIR` 을 한 번 확정하고, 이후 모든 경로를 `"$SKILL_DIR"` 기준으로 쓴다:

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
printf "%s\n" "$c"' _ brain-build itda-research "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'brain-build'; $P = 'itda-research'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

### 관문1 — 전수 스캔 · 인벤토리

소스 폴더를 재귀 스캔해 전체 파일 인벤토리를 만든다(전수성 기준선).

```bash
# macOS/Linux
find "<소스폴더>" -type f | sort        # 숨김/임시 포함, .DS_Store 는 인벤토리에만
# Windows
# Get-ChildItem -Recurse -File "<소스폴더>" | Select FullName
```

- 각 파일: 상대경로 · 확장자 · 크기 · **수정시각(mtime)** 을 기록한다. **수정시각은 검수리포트 커버리지 표(관측 필드, REQ-032)와 신선도 점검(brain-audit)의 기준선**이므로 반드시 캡처한다.
- `~$*`(Office 잠금 임시파일)·0~수백 byte 손상 의심 파일은 표시해 둔다(관문3 `문제파일.md` 후보).
- 한글 문서(`.hwp`·`.hwpx`·`.hml`)는 따로 세어 둔다 — 관문2 에서 `itda-doc:hwpx` 경로로 읽을 대상이고, 그 플러그인이 없으면 전부 문제파일이 된다.

### 관문2 — 원본 판독 (읽기 전용, 유형별)

각 원본을 유형에 맞게 읽는다. **에이전트가 문서를 판독**한다(길 X — Python 이 문서를 직접 파싱하지 않는다). 관문1에서 표시한 문제 후보(`~$*` 잠금·0byte 등)는 유형별 판독을 시도하기 전에 실패(빈 파일·본체 아님)만 확정하고 관문3 `문제파일.md` 로 보낸다 — 문서 스킬 호출은 정상 후보에만 쓴다:

- `.docx` → `document-skills:docx` 스킬 또는 로컬 파서로 본문·표 추출.
- `.xlsx`/`.csv` → `document-skills:xlsx`. 정형 수치가 핵심이면 `itda-data:data-verify`(수치 검수)를 하위 활용 가능.
- `.pptx` → `document-skills:pptx` (슬라이드 텍스트 + **표지/슬라이드 내부 작성일** — 최신성 판별의 정본).
- `.pdf` → `document-skills:pdf` (텍스트 레이어 추출). **스캔 PDF(텍스트 레이어 부재)·이미지 위주 문서는 "내용 검색 불가"로 분류**해 관문3 `문제파일.md`에 기록한다(OCR 필요 여부 관찰 병기, #1223) — 판독·적재 여부와 별개로, 이후 텍스트 검색이 이 파일 내용을 보지 못한다는 표시다.
- `.hwp`·`.hwpx`·`.hml`(한글) → `itda-doc:hwpx` 스킬의 **읽기** 경로(§읽기 — HWP/HWPX → Markdown)로 마크다운 변환해 판독한다. 변환 명령·옵션은 그 스킬 SKILL.md 가 정본이다(여기서 다시 적지 않는다).
  - **원본 불가침** — 변환은 원본을 작업 폴더(`.itda-skills/`)로 **복사한 사본**에 대해 하고, 변환 결과(`.md`·이미지)를 소스 폴더 안에 쓰지 않는다. 판독 목적이면 `--no-extract-images` 로 본문만 뽑고, 결과가 한 칸짜리 표 덩어리면 `--unwrap-layout-tables` 로 다시 뽑는다.
  - 형식은 확장자가 아니라 **파일 내용**으로 갈린다 — 확장자가 틀린 한글 파일(`.hwpx` 인데 실제로는 HWP 5)도 그대로 읽힌다. 근거 경로는 변환 사본이 아니라 **원본 상대경로**로 적는다.
  - 리더가 **exit 0 이 아니면**(HWP 3.x·HWPML(`.hml`)·배포용 보호·암호·한글이 아닌 파일 → exit 2 와 무엇인지 한 줄 안내 — 판정은 종료 코드 값이 아니라 0 이 아닌지로 한다) 판독 실패로 확정하고 관문3 `문제파일.md` 에 **리더가 말한 형식·사유를 그대로** 적는다(조치: HWP 3.x·HWPML 은 한글에서 HWPX 로 저장, 배포용 보호·암호는 해제한 원본 요청). kordoc 대체 경로는 외부 패키지 실행이라 **자동으로 돌리지 않는다** — 완료 보고에서 한 번 묻는다.
  - 변환은 성공했는데 본문이 비어 있거나 이미지뿐이면 스캔 PDF 와 같이 **"내용 검색 불가"** 로 기록한다.

> **크로스플러그인 미설치 계약 (조용한 생략 금지)**: 한글 리더는 **itda-doc** 플러그인(`itda-doc:hwpx`) 소속이고
> brain-build 는 **itda-research** 소속이라 함께 설치돼 있지 않을 수 있다. 스킬이 없거나 호출이 실패하면
> 한글 문서를 **조용히 건너뛰지 않는다** — 그 파일마다 `문제파일.md` 에 **"판독 도구 없음 — itda-doc 미설치"** 로 기록하고,
> 완료 보고에 **"한글 문서(HWP/HWPX) N건 미판독 — itda-doc 플러그인을 설치하면 업무DB에 적재할 수 있습니다"** 를 명시한다.
> 다른 형식(`.docx` 등)의 경로로 한글 파일을 억지로 열거나, 바이너리를 텍스트로 읽어 "판독"으로 세지 않는다.

- `.txt` → Read.
- 손상/잠금/빈 파일 → 판독 실패를 기록(관문3 `문제파일.md`).

판독 시 각 문서에서 **주제·핵심 수치·날짜·결정·대상(거래처·품목 등)**을 뽑고, **근거 경로(소스폴더 기준 상대경로)**를 항상 함께 유지한다. 최신성은 파일명이 아니라 **문서 내부 날짜**로 판단한다.

### 관문3 — 주제별 위키 작성 (Layer 2)

주제별로 `.md` 페이지를 만든다(실제 도메인에 맞게 — 거래처·계약·규정·매출·재고·인사·회의·제안 등). 각 페이지:

- 상단 머리말: `출처:`(근거가 된 원본 경로 목록) · `최종갱신:`.
- 본문: 모든 수치·금액·날짜·결정 뒤 괄호 인라인 근거. 예: `19,800원 (계약/대영인쇄_연간공급계약_2026.docx)`.
- 관련 페이지 `[[페이지명]]` 링크.
- 모순은 봉합하지 않고 양쪽 값·근거 병존.

페이지 실물 예시(형식 기준 — 머리말 + 인라인 근거 + 모순 병존):

```markdown
출처: 계약/대영인쇄_연간공급계약_2026.docx, 발주/2026-03_발주서.xlsx
최종갱신: 2026-07-14

# 거래처 — 대영인쇄

- 품목: A4 복사용지, 박스당 2,500매 (계약/대영인쇄_연간공급계약_2026.docx)
- 매입 단가 — **모순 병존**: 계약 19,800원 (계약/대영인쇄_연간공급계약_2026.docx) vs
  발주 실적 21,000원 (발주/2026-03_발주서.xlsx) → 임의 판정하지 않음, 검수 대조 대상.

관련: [[사무용품-단가]]
```

이어서 카탈로그를 만든다:

- **`INDEX.md`** — 페이지 카탈로그(페이지·주제·주요 근거 원본) + **적재이력 절**(언제 무엇이 들어왔나 — REQ-031, brain-ingest 증분의 데이터 소스) + 원본→페이지 커버리지 요약 + 알려진 핵심 모순 요약.
- **`문제파일.md`** — 읽기 불가(손상·잠금·**한글 리더 미지원 형식**: HWP 3.x·HWPML·배포용 보호·암호)·**판독 도구 없음(itda-doc 미설치로 못 읽은 한글 문서 — 설치하면 적재 가능)**·**내용 검색 불가(스캔 PDF·이미지 등 텍스트 추출 불가 — 판독은 됐어도 텍스트 검색의 사각, #1223)**·주의(사본 접두·버전 파일명·무제 파일) 파일을 사유·조치와 함께 기록. 적재 집계(원본 총 N / 정상 적재 M / 읽기 불가 K / 판독 도구 없음 T / 내용 검색 불가 S).

### 관문4 — 규약 역공학 (규약 레이어)

원본의 폴더 배치·파일명·문서 양식을 관찰해 규약을 역공학한다(REQ-010):

- **`규약/폴더-지도.md`** — "어떤 문서가 어느 폴더에" 배치 체계. 명문 규정 존재 여부부터 확인.
- **`규약/명명-규칙.md`** — 파일명 패턴 + 관찰된 위반 사례(무제·사본 접두·버전 지옥·"개정안" 오도·연도 누락·임시/손상 파일).
- **`규약/양식/{유형}.md`** — 반복 유형(회의록·견적서·품의서 등)의 레이아웃(모범 원본 지정).

각 규약 항목에 **`근거`·`표본 수`·`상태(추정/확정)`**를 붙인다. 우선순위: **명문 규정 > 관찰된 다수 패턴 > 단일 사례 추정.**

> [HARD] 명문 규정과 실제 관찰이 **불일치**하면(예: 온보딩 가이드 "부서별" vs 실제 폴더 "유형별") 명문을 기계적으로 확정하지 말고 **불일치를 보존·명시하고 사용자 확인을 권고**한다. (REQ-011)

### 관문5 — Layer 3 스키마 (CLAUDE.md) + 뇌 메타 자기서술

`"$SKILL_DIR/../../references/CLAUDE-template.md"`(정본 — **플러그인 루트**의 `references/`, 스킬 디렉토리 내부가 아님)를 업무DB 폴더의 `CLAUDE.md`로 심는다. `{{...}}` 플레이스홀더를 실제 값으로 치환:

- **머리말(frontmatter) 뇌 메타** (REQ-030 자기서술): `brain`(뇌 이름) · `sources`(소스 폴더 — **절대경로**로 항목 1개, v1 단일 소스. brain-audit 가 이 값만으로 소스 폴더를 찾으므로 상대경로를 쓰면 실행 위치에 따라 해석이 갈린다) · `last_updated` · `source_files`(원본 파일 수). 파일시스템 스캔만으로 뇌를 발견·식별할 수 있게 하는 필드 — 임의로 비우지 않는다.
- 본문의 `{{소스 폴더}}`·`{{뇌 이름}}`도 치환. 주석 블록은 생성물에서 제거.

이 `CLAUDE.md`가 **질답 규율의 담당자**다(스킬이 아니라 DB 스키마가 질답을 담당 — Cowork 이 폴더를 열면 자동 적용, 스킬팩 없는 동료에게 폴더만 줘도 규율을 따름). 템플릿의 **「신규 열람자 온보딩(인수인계) 규칙」**도 함께 심긴다 — 이 뇌를 처음 받는 사람(신입·후임)이 폴더를 열면 근거 기반 브리핑·이해 확인을 받을 수 있다(사람↔뇌 이해 격차 해소, 상태는 뇌에 비저장).

### 관문6 — 신선도 기준선(manifest) 저장

> [HARD] 빌드 시점 **정수 mtime 기준선**을 저장해야 이후 brain-audit 신선도 점검이 "무엇이 바뀌었나"를 판정할 수 있다. 기준선이 없으면 신선도는 판정 불가(unknown)가 된다. **검수(관문7)보다 먼저 저장한다** — 검수관이 참조하는 기계 기준선이 검수 시점에 존재해야 하고, 커버리지 표와 manifest 의 스냅샷 시점도 일치한다.

위키·카탈로그가 확정되면 `freshness.py scan` 으로 소스 폴더 스냅샷을 떠 **`<업무DB>/.brain-manifest.json`** 에 저장한다(절대경로 실행). scan 이 실패해도 깨진/빈 manifest 가 남지 않도록 **임시 파일에 쓴 뒤 성공 시에만 이동**한다:

```bash
# macOS/Linux
python3 "$SKILL_DIR/../brain-audit/scripts/freshness.py" scan "<소스폴더>" \
  > "<업무DB>/.brain-manifest.json.tmp" && mv "<업무DB>/.brain-manifest.json.tmp" "<업무DB>/.brain-manifest.json"
# Windows (py -3 "$env:SKILL_DIR\..\brain-audit\scripts\freshness.py" scan ... — 동일하게 .tmp 후 move)
```

이 manifest 가 신선도 기준선의 정본이다(정수 epoch mtime — 타임존 무관). `검수리포트.md` 커버리지 표의 수정시각 열은 사람 가독용 관측 필드(REQ-032)이고, 기계 대조는 manifest 로 한다. **brain-audit 은 이 기준선을 갱신하지 않으며**(현재값으로 덮으면 미적재 변경이 사라짐), 갱신은 brain-ingest 가 적재 성공 시에만 한다.

### 관문7 — 독립 검수 자동 호출 (brain-auditor)

> [HARD] 빌드 산출을 **믿지 말고 검수한다.** 빌드 기억과 격리된 컨텍스트에서 원본을 다시 열어야 자기검증 편향이 차단된다.

`Agent` 도구로 **`brain-auditor` 서브에이전트를 1회 디스패치**한다. 프롬프트에 넘길 것:

- 업무DB 폴더 경로 + 소스 폴더 경로.
- 관문1 인벤토리(파일 목록 + **수정시각**) — 커버리지 표의 관측 필드(REQ-032) 기준선. 기계 기준선 manifest 는 관문6에서 이미 저장돼 있다.
- 검수 4각도 지시(전수성·수치 재대조·근거 추적·교차 모순)와 산출 파일(`검수리포트.md`).

brain-auditor 가 `검수리포트.md`를 쓰면, 발견된 핵심 모순 요약을 `INDEX.md`의 "알려진 핵심 모순"에 반영한다. brain-auditor 의 **최종 텍스트는 AUDIT_SCHEMA JSON**(`verdict`·`findings`·`recomputed`·`unverifiable`, #1621)이다 — 검수 통과 여부는 리포트 문장에서 추론하지 말고 `verdict` 필드로 읽는다(critical 1건 = `FAIL`, `unverifiable` 비어 있지 않으면 `PASS` 아님).

**2차 경로 (에이전트 타입 부재 시)** — 환경에 `itda-research:brain-auditor` 에이전트 타입이 없으면(스킬팩 미설치·소스 저장소 등), general-purpose 서브에이전트에 `"$SKILL_DIR/../../agents/brain-auditor.md"` 지시서를 먼저 읽고 그대로 따르라고 프롬프트로 명시해 디스패치한다. 새 컨텍스트의 서브에이전트가 지시서를 따르므로 **격리 검수가 동등하게 성립**한다(빌드 기억 미공유) — 이 경로는 배너 대상이 아니다.

> [HARD] **fail-visible fallback.** 서브에이전트 디스패치 자체가 불가한 환경(`Agent` 도구 부재 등)이면 격리 독립 검수는 **성립하지 않는다**(자기검증 편향 미차단 — SPEC REQ-002 위반). 이때는 검수를 "통과"로 제시하지 말고, `검수리포트.md` 최상단에 **`⚠️ 격리 검수 미수행 — 자기검증 편향 미차단, 독립 재검수 필요`** 배너를 달고 종합 요약을 `검증 불가`로 표기한다. 본 컨텍스트에서 임시로 각도를 훑더라도 그 결과는 "미검증"이다.

### 완료 보고

빌드 끝에 사용자에게 요약한다: 업무DB 경로 · 원본 N개(정상 M / 문제 K) · 위키 페이지 수 · (한글 문서를 못 읽었다면) 미판독 건수와 그 사유별 조치(itda-doc 설치 · 한글에서 HWPX 저장 · kordoc 대체 경로 사용 여부 질문) · 검수 결과(모순 건수·심각도) · 뇌 이름. **원본은 무수정**임을 확인한다. 후임·신입에게 넘길 때는 폴더를 열고 "인수인계 브리핑 해줘"라고 하면 `CLAUDE.md` 온보딩 규칙이 근거 기반 안내·이해 확인을 제공한다고 덧붙인다.

---

## 원칙

- **원본 불가침**이 최우선. 검수·정정 권고도 원본 수정을 포함하지 않는다(정정은 원본 소유 부서 확인 후 사람이).
- **"동작함" ≠ "정확함"** — 위키가 그럴듯해 보여도 원본과 일치하는지는 검수(관문6)가 판정한다.
- **길 X thin skill** — hyve 무의존. Cowork 에 스킬팩만 있으면 동작. 결정론 헬퍼(신선도)는 brain-audit 소관.
