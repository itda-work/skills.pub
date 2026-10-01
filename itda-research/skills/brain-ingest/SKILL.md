---
name: brain-ingest
description: >
  업무DB(뇌)에 새 문서를 증분 적재하는 스킬입니다(v1.1). 신규 사내 문서를 주제별 위키에 반영하고, 외부 산출물(웹 검색·DART 등)은 외부/에 출처·수집일을 강제해 격리 적재하며, 적재이력을 갱신합니다. 검증대기 구두 주장의 근거 실물이 도착하면 주장 값과 대조해 적재하고 졸업시킵니다. "뇌에 새 문서 반영해줘", "이 견적서들 업무DB에 넣어줘", "업무DB 업데이트"처럼 말하면 되고, 뇌 폴더 밖 대화에서도 "이 얘기 뇌에 반영해줘"라고 명시 요청하면 대상 뇌를 확인해 주장→근거 파이프라인으로 접수합니다.
  원본 불가침 — 위키만 갱신하며, 검증 안 된 채팅 내용은 위키에 쓰지 않습니다.
license: MIT
compatibility: "Python 3.10+ (오케스트레이션 스킬)"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, Skill, mcp__workspace__bash
argument-hint: "[업무DB 폴더 경로] [새 문서 경로 또는 외부 산출물]"
metadata:
  author: "Chinseok"
  version: "0.2.6"
  category: "knowledge-base"
  status: "experimental"
  recommended: false
  created_at: "2026-07-14"
  updated_at: "2026-09-30"
  tags: "knowledge-base, incremental, ingest, adapter, external-source, provenance, claim, verification, incubating, scaffold"
---

# brain-ingest (v1.1 — 스캐폴드)

> **상태: v1.1 스캐폴드.** 아래는 확정된 orchestration outline 이며, 구현·라이브 검증은 v1 안정화 후 진행한다(SPEC-BRAIN-VERTICAL-001 REQ-040, #1122 비범위). "뇌에게 데이터 업데이트를 요청한다"의 v1 실체가 이 스킬 호출이다.

`brain-build`가 만든 업무DB에 새 문서가 생길 때마다 전체 재빌드하지 않고 **증분 적재**한다.

---

## Claude 오케스트레이션 지시서 (outline)

> [HARD] **원본 불가침.** 새 사내 문서도 읽기 전용. 위키(Layer 2)와 `INDEX.md`만 갱신한다. (SPEC INV-1)
> [HARD] **근거·모순 규율 계승.** 증분 페이지도 인라인 근거 강제, 기존 값과 상충하면 모순 보존(brain-build 관문3 동일).

### 관문0 — 스킬 디렉토리(SKILL_DIR) 확정

헬퍼 스크립트는 cwd 에 의존하지 않도록 **절대경로**로 실행한다. 실행 절 첫머리에서 `SKILL_DIR` 을 한 번 확정한다:

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
printf "%s\n" "$c"' _ brain-ingest itda-research "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'brain-ingest'; $P = 'itda-research'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

### 관문1 — 적재원 분류

- **사내 신규 문서** — 소스 폴더에 새로 생긴 원본. brain-build 관문2 판독 → 해당 주제 위키에 반영. 형식별 경로는 brain-build 관문2 가 정본이다 — 한글 문서(`.hwp`·`.hwpx`·`.hml`)는 `itda-doc:hwpx` 읽기 경로로 판독하고, 리더가 거부한 파일(HWP 3.x·HWPML·배포용 보호·암호)과 **itda-doc 미설치로 못 읽은 한글 문서**는 조용히 건너뛰지 않고 `문제파일.md` 에 사유와 함께 추가한다(brain-build 의 크로스플러그인 미설치 계약 그대로). 못 읽은 파일은 적재한 것이 아니므로 관문3 기준선 전진(`--paths`)에 넣지 않는다 — 계속 stale 로 남아 다음 점검이 다시 잡는다.
- **외부 스킬 산출물** — `itda-web:web-search`·`itda-gov:dart`·`itda-gov:kosis`·`itda-work:exchange-rate` 등이 수집한 자료. **`외부/` 폴더에 격리 적재**하고 `출처:`(어느 스킬·URL·API)·`수집일:`을 강제한다(사내 원본과 분리 — CLAUDE.md 적재 규칙 9).
- **주장 해소 근거** (#1222, SPEC-BRAIN-CLAIM-001) — `검증대기.md`의 미결 주장에 대응해 도착한 실물(사내 문서·외부 수집물·승인된 구두확인서). 관문1.5 대조 게이트를 거친다.

### 관문1.5 — 주장 대조 게이트 (검증대기 해소, #1222)

> [HARD] **검증 안 된 채팅 내용을 위키에 직접 쓰지 않는다.** 적재되는 것은 대조를 통과한 실물뿐이다(SPEC-BRAIN-CLAIM-001 INV-C1).

적재원이 주장 해소 근거이거나, 신규 문서가 `검증대기.md`의 미결 주장과 같은 대상을 다루면 적재 전에 대조한다:

- **일치** — 정상 적재(관문2~) 후 `검증대기.md`에서 졸업: 해소일·근거 경로를 기록한다. 위키 근거는 도착한 원본을 가리킨다(주장 발화가 아니라).
- **불일치** — 임의 판정하지 않는다. 양쪽 값(주장 vs 실물)을 모순으로 보존하고(CLAUDE.md 적재 규칙 8) `검증대기.md` 항목에 불일치 사실을 기록, 사용자 확인을 권고한다.
- **뇌 밖 접수** — 업무DB 폴더를 열지 않은 대화에서 명시 요청("이 얘기 뇌에 반영해줘")으로 호출되면, 먼저 대상 업무DB 경로를 확인하고(`CLAUDE.md` 머리말 자기서술로 식별) 주장을 그 뇌의 `검증대기.md`에 등록 + 근거 요구부터 시작한다. 자동 감지는 뇌 폴더를 연 세션의 `CLAUDE.md` 규율만 담당한다(전역 감시 없음 — INV-C2).

### 관문2 — 신규 유형 학습 루프

처음 보는 문서 유형을 만나면 기존 `규약/양식/`에 없으므로, 양식을 역공학해 `규약/양식/{유형}.md`(상태: 추정)로 등록한다(brain-build 관문4 규약 역공학 계승).

### 관문3 — 적재이력 + 신선도 기준선 갱신 (REQ-031)

`INDEX.md`의 적재이력 절에 "언제(적재일) 무엇(파일·주제)이 들어왔나"를 추가한다.

> [HARD] **신선도 기준선 갱신은 brain-ingest 만, 그리고 적재한 경로만.** 신규 문서를 실제로 위키에 적재(반영)한 뒤, **전체 재스캔으로 manifest 를 통째로 교체하지 않는다** — 그러면 함께 존재하던 **미적재 변경까지 기준선에 흡수돼 stale 이 사라진다**(거짓 안심). 반드시 `update-baseline` 으로 **적재 완료한 경로만** 병합한다(절대경로 실행):
>
> ```bash
> # macOS/Linux — 적재 완료한 경로만 기준선 전진(나머지 미적재 변경은 계속 stale 유지)
> python3 "$SKILL_DIR/../brain-audit/scripts/freshness.py" update-baseline "<소스폴더>" \
>   --manifest "<업무DB>/.brain-manifest.json" --paths "견적서/신규.xlsx" "계약/신규.docx" \
>   > "<업무DB>/.brain-manifest.json.tmp" && mv "<업무DB>/.brain-manifest.json.tmp" "<업무DB>/.brain-manifest.json"
> # Windows: py -3 "$env:SKILL_DIR\..\brain-audit\scripts\freshness.py" update-baseline ... (동일)
> ```
>
> brain-audit 은 기준선을 갱신하지 않으므로(자기비교 방지), "적재하지 않은 채 기준선만 최신화"되는 일이 없다. manifest 경로가 틀리거나 파일이 손상돼 있으면 freshness.py 가 **명시 에러로 중단**한다(exit 2 — 빈 기준선 자동 생성·대체 없음). 에러 메시지대로 경로를 정정하거나 재빌드로 기준선을 재생성한다.

### 관문4 — 신선도·검수 연계

증분 적재 후 `brain-audit`로 신선도 절을 갱신하고, 신규 문서가 기존 값과 모순되면 `brain-auditor` 재검수로 검수리포트에 반영한다.

---

## 원칙

- **증분 ≠ 재빌드** — 전수성은 brain-audit 신선도 점검이 보증한다(적재 누락 = stale 검출).
- **외부 자료 오염 방지** — 외부 수집물은 반드시 `외부/` + `출처:`·`수집일:`. 사내 근거와 섞지 않는다.
- **주장은 실물로만 해소** — 채팅 발언은 적재 요구 신호일 뿐 지식이 아니다. 뇌는 어떤 경우에도 1차 기록이 되지 않는다(순수 암묵지도 승인된 구두확인서 원본 경유 — SPEC-BRAIN-CLAIM-001).
- **길 X thin skill** — hyve 무의존.
