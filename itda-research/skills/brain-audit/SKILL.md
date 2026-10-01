---
name: brain-audit
description: >
  업무DB(뇌)를 독립 재검수하는 스킬입니다. 정기잡·수시 점검 진입점으로, 검수 에이전트(brain-auditor)를 격리 디스패치해 4각도(전수성·수치 재대조·근거 추적·교차 모순)를 다시 돌리고, 제5각 신선도 점검을 더합니다 — 소스 폴더를 재스캔해 빌드 시점과 대조, 신규/변경/삭제 파일로 "뇌가 낡았는지" 감지합니다. 검증대기 미결 주장·내용 검색 불가(스캔 PDF 등) 건수도 표면화합니다. "이 업무DB 검수해줘", "뇌 아직 최신이야?", "공유폴더 바뀐 거 반영됐나 확인", "업무DB 재검수", "신선도 점검"처럼 말하면 됩니다.
  원본 불가침 — 원본은 읽기만 하며 산출은 검수리포트.md 갱신입니다.
license: MIT
compatibility: "Python 3.10+ (신선도 스캔 stdlib only)"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, mcp__workspace__bash
argument-hint: "[업무DB 폴더 경로] (소스 폴더는 CLAUDE.md 머리말에서 읽음)"
metadata:
  author: "Chinseok"
  version: "0.3.5"
  category: "knowledge-base"
  status: "experimental"
  recommended: false
  created_at: "2026-07-14"
  updated_at: "2026-09-30"
  tags: "knowledge-base, audit, freshness, reconciliation, provenance, staleness, claim, incubating"
---

# brain-audit

`brain-build`가 만든 업무DB(뇌)를 **독립적으로 재검수**하는 진입점이다. 빌드 때 한 번 검수했더라도,
원본이 바뀌면 뇌가 낡는다. brain-audit 는 ① 검수 4각도를 격리 컨텍스트에서 **다시** 돌리고,
② **신선도 점검**(제5각)으로 소스 폴더가 빌드 이후 얼마나 달라졌는지를 온디맨드로 감지한다.

itda-research 비정형 문서 vertical 의 재검수·신선도 담당. (SPEC-BRAIN-VERTICAL-001, #1122)

---

## Claude 오케스트레이션 지시서

> [HARD] **원본 불가침.** 소스 폴더 원본을 읽기 전용으로만 접근한다. 산출은 `검수리포트.md` 갱신뿐이다. (SPEC INV-1)
> [HARD] **격리 검수.** 재검수도 빌드/이전 검수 기억에 의존하지 않는다 — `brain-auditor`를 새 컨텍스트로 디스패치해 원본을 다시 열게 한다.

### 입력

- **업무DB 폴더 경로** (필수). 소스 폴더 경로는 업무DB `CLAUDE.md` 머리말 `sources:` 에서 읽는다(자기서술 메타 — REQ-030, **절대경로 1개** — v1 단일 소스). 값이 상대경로거나 폴더가 실재하지 않으면 추측으로 보정하지 말고 사용자에게 소스 폴더 절대경로를 확인한다.

### 관문0 — 스킬 디렉토리(SKILL_DIR) 확정

스킬 스크립트는 cwd 에 의존하지 않도록 **절대경로**로 실행한다. 실행 절 첫머리에서 `SKILL_DIR` 을 한 번 확정하고, 이후 모든 스크립트 경로를 `"$SKILL_DIR"` 기준으로 쓴다:

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
printf "%s\n" "$c"' _ brain-audit itda-research "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'brain-audit'; $P = 'itda-research'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

### 관문1 — 신선도 점검 (제5각, 결정론)

소스 폴더를 재스캔해 **빌드 시점 기준선(manifest)**과 대조한다. 이 단계는 **결정론 Python 헬퍼**가 담당한다(에이전트 눈대중 금지):

```bash
# macOS/Linux — baseline = 빌드 시점 manifest (정본)
python3 "$SKILL_DIR/scripts/freshness.py" diff "<소스폴더>" --baseline "<업무DB>/.brain-manifest.json"
# Windows
py -3 "$env:SKILL_DIR\scripts\freshness.py" diff "<소스폴더>" --baseline "<업무DB>\.brain-manifest.json"
```

출력(JSON)의 `new`·`changed`·`deleted`·`unchanged`·`stale` 를 읽어 **신규/변경/삭제 파일**을 파악한다.

- **기준선의 정본은 빌드 시점 manifest**(`.brain-manifest.json` — 정수 mtime, 타임존 무관). brain-build 가 빌드 끝에 저장하고, brain-ingest 가 적재 성공 시에만 갱신한다. **brain-audit 은 기준선을 갱신하지 않는다**(현재 스캔값으로 덮으면 미적재 변경이 다음 검사에서 사라져 항상 "최신"으로 위장된다 — 거짓 안심).
- **기준선 부재**(`stale: null`, `baseline: "absent"` — 구 빌드): 신선도를 **판정 불가(unknown)**로 보고하고 **재빌드를 권고**한다. 현재 스캔값으로 커버리지 표를 backfill 해 diff 하지 않는다(자기비교 금지).
- **기준선 손상**(비JSON·빈 파일): freshness.py 가 `Error: manifest 손상 …` 으로 명시 중단한다(exit 2 — 빈 값 대체 없음). 재빌드(또는 백업 복원)로 기준선을 재생성하도록 안내한다.
- manifest 가 없고 검수리포트 커버리지 표에 수정시각 열만 있을 때는 fallback 으로 `--report "<업무DB>/검수리포트.md"` 를 쓸 수 있으나, 이는 정밀도가 낮다(정본은 manifest).
- `stale: false` 면 "뇌 최신"으로 보고하고, 4각도 전면 재검수는 사용자 요청 시에만 수행한다.

### 관문1.5 — 미결 주장 · 검색 사각 집계 (#1222·#1223, 결정론)

판단이 아니라 세는 것이다 — 두 가지를 집계해 관문3 리포트로 잇는다:

- **검증대기 미결**: `<업무DB>/검증대기.md`가 있으면 미결 주장 건수와 최장 경과일을 센다(예: "검증대기 3건, 최장 12일"). 오래된 미결은 근거 확보 재촉을 조치 권고에 포함한다. 파일이 없으면 "미결 주장 0건"으로 보고한다(에러 아님 — 주장이 아직 없었던 뇌).
- **내용 검색 불가**: `문제파일.md`의 "내용 검색 불가" 분류(스캔 PDF·이미지 등 텍스트 추출 불가) 건수를 센다 — 질답의 텍스트 검색이 보지 못하는 사각의 크기다.

### 관문2 — 4각도 재검수 디스패치 (변경이 있거나 사용자가 전면 재검수를 요청할 때)

`Agent` 도구로 **`brain-auditor`를 디스패치**한다. 프롬프트에 업무DB·소스 폴더 경로 + 관문1 신선도 결과(신규/변경 파일 목록)를 넘기고, 변경분에 초점을 둔 검수를 요청한다. 신규 파일이 위키에 반영되지 않았으면 그 자체가 전수성(각도 1) 결함이다. 에이전트 타입이 없는 환경이면 brain-build 관문7의 **2차 경로**(general-purpose 서브에이전트에 `"$SKILL_DIR/../../agents/brain-auditor.md"` 지시서 주입 — 격리 동등 성립)와 동일하게 디스패치한다.

### 관문3 — 검수리포트 신선도 절 갱신

`검수리포트.md`의 **신선도 절**을 관문1 결과로 갱신한다:

- 재검수일 · `stale` 여부 · 신규/변경/삭제 파일 목록(경로 + 빌드 시점 vs 현재 수정시각).
- 미결 주장(검증대기 건수·최장 경과)·내용 검색 불가 건수(검색 사각) — 관문1.5 집계.
- 변경분에 대한 brain-auditor 재검수 요약(신규 모순·해소된 모순).
- 조치 권고: 신규/변경 파일이 있으면 `brain-ingest`(증분 적재, v1.1)로 위키에 반영할 것을 안내(원본 불가침 — 위키만 갱신). 오래된 미결 주장은 근거 확보(실물 제공·구두확인서 승인)를 재촉한다.

### 완료 보고

사용자에게 요약한다: 뇌 이름 · 신선도(최신/낡음 + 신규 N·변경 M·삭제 K) · 미결 주장·검색 사각 집계 · 재검수 모순 변화 · 조치 권고.

---

## 원칙

- **신선도는 결정론**(`freshness.py`) — 파일 존재·수정시각은 계산이지 판단이 아니다. 모순 판정만 에이전트(brain-auditor)가 한다.
- **최신성은 파일명이 아니라 내부 날짜** — 신선도 점검은 파일 mtime 으로 "무엇이 바뀌었나"를 감지하고, 문서 최신성 판단(어느 버전이 진짜 최신인가)은 여전히 문서 내부 날짜로 한다.
- **길 X thin skill** — hyve 무의존. freshness 는 stdlib only.
