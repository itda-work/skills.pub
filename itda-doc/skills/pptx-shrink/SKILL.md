---
name: pptx-shrink
description: >
  기존 PPTX 파일의 용량을 줄이는 스킬입니다. 슬라이드에 붙인 스크린샷·사진 PNG 를 해상도 그대로 JPEG 로 재인코딩하고
  텍스트·발표자 노트·그림 수가 그대로인지 자동 검증합니다(실측 62.7MB→12.2MB). 원본 덮어쓰기 전 백업 여부를 반드시 확인합니다.
  "이 ppt 용량 줄여줘", "발표자료가 커서 메일로 못 보내", "pptx 압축해줘", "이 덱 왜 이렇게 커?"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 기존 pptx 용량 축소 전담 — itda-doc:imagekit 은 낱개 이미지.
license: Apache-2.0
compatibility: "Claude Code & Cowork. Python 3.10+ · Pillow. Office 불필요(macOS/Linux/Windows)."
user-invocable: true
allowed-tools: Read, Bash, Glob, AskUserQuestion, mcp__workspace__bash
argument-hint: "<덱.pptx> [출력.pptx] [--quality 90|80|70] [--downsample-ppi 220|150]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "document"
  status: "beta"
  recommended: true
  version: "0.2.2"
  created_at: "2026-09-05"
  updated_at: "2026-09-27"
  tags: "pptx, powerpoint, shrink, compress, reduce, size, image, jpeg, png, screenshot, deck, slides, presentation, attachment"
---

# pptx-shrink

pptx 가 큰 이유는 거의 언제나 **슬라이드에 붙여 넣은 스크린샷 PNG** 다(hyve-training 12덱 실측:
파일 크기의 99% 가 미디어, 1MB 넘는 PNG 27장이 56MB). 이 스킬은 그 PNG 를 **해상도는 그대로** JPEG 로
바꾸고 나머지(텍스트·노트·마스터·애니메이션)는 바이트 단위로 보존한다. zip 을 직접 열어 이미지만
갈아 끼우므로 python-pptx 라운드트립 손실이 없다.

| 실측 (2026-09-05) | 전 | 후 |
|---|---|---|
| A 소개 및 왜 클로드인가 (58장) | 62.7 MB | 12.2 MB |
| L 클로징 (38장) | 43.4 MB | 7.7 MB |
| 12덱 합계 | 212 MB | 57 MB (73% 감소) |

## 사전 준비

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/pptx-shrink}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/pptx-shrink' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용

python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문 (Pillow)
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

```powershell
# Windows
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\pptx-shrink"  # 미설정이면 SKILL.md 위치 절대경로 사용
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를
> 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--dry-run` 은 명령만.

## 관문 ([HARD] — 순서대로)

### 관문 1 — 진단·실측 (파일을 쓰지 않는다)

```bash
python3 "$SKILL_DIR/scripts/pptx_shrink.py" report "<덱.pptx>" --json
```

report 는 **추정이 아니라 실측**이다 — 변환 대상 PNG 마다 품질 90/80/70 × 해상도 원본/220ppi/150ppi 를
실제로 인코딩해 조합별 결과 파일 크기를 잰다(`tiers_after_mb`). 사용자에게 **한 문단 + 표 하나**로 말한다:
"62.7MB 중 미디어가 99%, 1672×941 스크린샷 PNG 27장이 56MB. 투명 PNG 3장은 유지." 그리고

| | 해상도 원본 | 220ppi 축소 | 150ppi 축소 |
|---|---|---|---|
| 품질 90 | 14.1 MB | … | … |
| 품질 80 | 12.2 MB | … | … |
| 품질 70 | 10.6 MB | … | … |

- `convertible` 이 0 이면 여기서 멈춘다 — 이 스킬로는 줄지 않는다. 원인 후보를 말한다(`by_ext` 에 mp4·wav
  등 영상·음원 / 투명 PNG 다수 `kept_alpha` / 미디어 비중이 낮으면 임베드 폰트·슬라이드 수).
- `kept_alpha` 가 크면 "투명 배경 이미지는 화질 안전을 위해 건드리지 않는다" 고 미리 말한다.
- `downsample_recommended` 가 false(추가 절감 5% 미만)면 해상도 축소 열은 보여 주되 **권하지 않는다고 말한다**
  — 스크린샷이 표시 크기보다 작게 놓인 덱(슬라이드 폭 26.67in 강의 덱 실측: A 7.8→7.6MB)에서는 줄일 픽셀이 없다.
  true 면(레티나 캡처를 작게 배치한 덱) `downsample_gain_pct` 를 근거로 선택지에 올린다.

### 관문 2 — 선택 확인 (사용자 결정 · 건너뛰기 금지)

변환 전에 **반드시** 사용자에게 아래 셋을 한 번에 고르게 한다(AskUserQuestion — Cowork 에서는 말로 묻는다).

**① 품질** — 표의 세 행 중 하나. 기본 제안은 80(화면·프로젝터·PDF 에서 차이를 느끼기 어렵다). 인쇄용·도면이면
90, 첨부 상한이 급하면 70. 60 아래는 제안하지 않는다.

**② 해상도 축소** — `downsample_recommended` 가 true 일 때만 "220ppi(고화질 인쇄 상당) / 150ppi(화면 상당) /
안 함" 을 묻는다. false 면 묻지 않고 "안 함" 으로 진행하며 그 이유(추가 절감 N%)를 한 줄 말한다.
축소는 표시 크기보다 픽셀이 큰 이미지에만 적용되고 슬라이드 XML 은 건드리지 않는다.

**③ 저장 방식** — 스크립트도 같은 것을 강제한다: `--in-place` 는 `--backup` 또는 `--no-backup` 없이는 거부된다(exit 2).

| 선택 | 명령 | 결과 |
|---|---|---|
| **새 파일로 저장** (기본·권장) | `shrink "<덱.pptx>"` 또는 `-o "<출력.pptx>"` | 원본 무접촉, `<이름>-shrunk.pptx` 생성 |
| 원본 교체 + 백업 보관 | `shrink "<덱.pptx>" --in-place --backup` | `<이름>.bak.pptx` 를 남기고 원본 교체(`--backup <경로>` 로 위치 지정) |
| 원본 교체, 백업 없음 | `shrink "<덱.pptx>" --in-place --no-backup` | 되돌릴 수 없다 — 사용자가 "백업 없이" 를 **명시**했을 때만 |

사용자가 "그냥 줄여줘" 라고만 했으면 품질 80 · 축소 안 함 · 새 파일이다. 원본 교체를 원해도 백업 여부를 묻지 않고
③ 세 번째로 가지 않는다. git 으로 추적되는 파일이라 해도 묻는다 — 되돌릴 수 있는지는 사용자가 판단한다.

### 관문 3 — 실행

```bash
python3 "$SKILL_DIR/scripts/pptx_shrink.py" shrink "<덱.pptx>" [-o "<출력.pptx>"] [--quality 80] [--downsample-ppi 220] [--json]
# 원본 교체: --in-place --backup [경로]   또는   --in-place --no-backup
# 기존 출력/백업 덮어쓰기: --force · 실측만: --dry-run
```

- 관문 2 의 선택을 그대로 옮긴다: `--quality` = ①, `--downsample-ppi` = ②(안 함이면 생략), 저장 방식 = ③.
- 기본값: JPEG 품질 80 · 300KB 미만 PNG 유지 · 투명 PNG 유지 · JPEG 가 더 커지면 유지 · 해상도 불변(축소 미선택 시).
- **PowerPoint 에 그 파일이 열려 있으면 먼저 닫게 한다.** 열린 채 원본을 교체하면 PowerPoint 가 저장하는
  순간 원본으로 되돌아간다(실측 사고). 새 파일 저장(①)이면 무관하다.

### 관문 4 — 검증 (자동, 실패 시 산출 폐기)

`shrink` 는 끝나기 전에 `scripts/verify.py` 를 자동으로 돌린다 — 슬라이드 수 · 슬라이드별 텍스트 ·
발표자 노트 · 슬라이드별 그림 수 · rels 참조 실재 · [Content_Types] 확장자 선언. 하나라도 어긋나면
산출물을 지우고 exit 3(`status: verify_failed`)으로 끝난다. 이때는 결과를 사용자에게 주지 말고 실패
사유(`verify.problems`)를 그대로 보고한다. 별도로 다시 돌리려면:

```bash
python3 "$SKILL_DIR/scripts/verify.py" "<원본.pptx>" "<변환본.pptx>"
```

### 관문 5 — 보고

JSON 의 `before_mb`·`after_mb`·`reduction_pct`·`converted`·`downsampled`·`kept`·`params`(품질·ppi)·`output`·`backup`·`verify.ok` 로
**표 한 줄 + 문장 두 개**를 만든다. 백업이 있으면 경로를, ③이었으면 "백업 없이 교체됨" 을 반드시 적는다.
`skipped` 가 있으면(열리지 않는 PNG) 목록을 붙인다. 감소폭이 30% 미만이면 GUIDE 의 "덜 줄어드는 경우" 를
근거로 이유를 말한다 — 결함이 아니라 투명 PNG·영상·이미 JPEG 인 경우가 대부분이다.

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 낱개 이미지 파일(png·jpg) 용량·크기 조정 | itda-doc:imagekit |
| 발표자료를 새로 만들기 | 비지원 — 이 저장소에 해당 스킬이 없다 |
| 두 버전의 차이를 보기 | 비지원 — 이 저장소에 해당 스킬이 없다 |
| 슬라이드 내용·서식 편집, 애니메이션·노트 조작 | 비지원 — PowerPoint 에서 직접 편집 |
| 잘라낸 부분을 실제로 버리고 싶다(srcRect 적용) | 비지원 — 실측 이득 0.2MB 수준(#1646). PowerPoint "그림 압축" 을 안내 |
| 영상·음원이 커서 큰 pptx | 비지원 — 미디어를 링크로 바꾸거나 별도 압축 |

## 하지 않는 것

- 잘라내기 적용·중복 제거·알파 평탄화. 해상도 축소는 **사용자가 표를 보고 고른 경우에만**(기본 꺼짐).
- 원본 교체를 묻지 않고 하는 것. `--no-backup` 을 사용자 동의 없이 붙이는 것.
- 하나의 PNG 라도 화질 판단을 대신하는 것 — 투명 PNG 는 무조건 유지한다.

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 규율의 하네스 강제 (선택 설정)

덱을 git 으로 관리하는 저장소라면 pre-commit 훅으로 같은 처리를 자동화할 수 있다 — hyve-training 저장소의
`scripts/hooks/pre-commit` 이 선례다(staged pptx 를 `--in-place` 로 변환 후 재-add, 열린 파일은 `lsof` 로
감지해 커밋 중단, `PPTX_SHRINK_SKIP=1` 우회). 훅은 이 스킬의 배포 범위 밖이며, 그 저장소가 백업 정책
(git 이력이 곧 백업)을 스스로 정한 뒤에만 `--no-backup` 을 쓴다.
