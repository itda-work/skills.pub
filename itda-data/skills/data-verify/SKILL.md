---
name: data-verify
description: >
  엑셀·CSV의 숫자가 실제로 맞는지 검수하는 스킬입니다. 부분합↔총계 불일치·원장 대조·음수/범위/중복 규칙 위반·시트 간 값 어긋남을 찾아 "이 숫자 틀렸어요"를 근거(기대값 vs 실제값 vs 차이)와 함께 짚습니다. "이 수치 맞는지 검수해줘", "합계 검산해줘", "원장이랑 대조해줘", "이 값들 검산해줘", "숫자 이상 없는지 봐줘"처럼 말하면 됩니다.
  보고 전용 — 확인 없이 값을 바꾸지 않습니다. 파일 검수는 openpyxl 크로스플랫폼(Office 불필요).
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, mcp__workspace__bash
argument-hint: "[xlsx/csv 경로 또는 검수 요청]"
metadata:
  author: "Chinseok"
  version: "0.4.1"
  category: "data-tidy"
  status: "experimental"
  recommended: false
  created_at: "2026-07-07"
  updated_at: "2026-09-30"
  tags: "verify, reconcile, numbers, spreadsheet, openpyxl, integrity, incubating"
---

# data-verify

엑셀에 숫자를 정리해놨는데 — 부분합이 총계랑 미묘하게 안 맞고, 집계값이 원장이랑 다르고,
음수가 나오면 안 되는 칸에 음수가 있고, 두 시트에서 같아야 할 값이 어긋나 있다. 보고서 내기
직전 "이 숫자들 진짜 맞나?"가 불안한데 대조할 시간이 없어 그냥 믿고 내는 — 그 불안을 없애는
"수치 양심" 스킬.

itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask` · 수식감사 `data-audit` ·
수치검수 `data-verify`)의 값 검수 담당. (#967)

`data-audit` 이 "수식이 옳게 짜였나"라면, `data-verify` 는 "값이 실제로 맞나"를 본다.

---

## Claude 오케스트레이션 지시서

> [HARD] 보고 전용 — 검수 결과를 먼저 보고하고, 값 수정은 사용자가 명시적으로 요청할 때만.
> [HARD] plausible ≠ correct — 허용오차를 명시하고 눈대중 금지(data-accuracy). 차이는 항상 수치로 제시한다.
> 아래 모듈을 임포트해 쓸 때는 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다(CLI 로 쓰면 `python3 "$SKILL_DIR/scripts/verify.py"`).

### 관문1 — 검수 설정 구성
자동 가능한 **내부정합** 외에는 대조 기준(원장·규칙·짝)이 필요하다. 사용자와 함께 config 를 구성한다:
```python
config = {
  "sheet": "Sheet1",                                  # 대상 시트(기본: 첫 시트)
  "internal": {"tolerance": 0.01},                    # 소계/총계 ↔ 구성요소 합 (자동 감지)
  "rules": {"non_negative": ["금액"], "unique": ["ID"],
            "range": {"비율": [0, 100]}, "sum_to": {"비중": 100}},
  "external": {"key": "코드", "value": "금액",
               "reference": {"A001": 1000, "A002": 2000}},   # 원장 정답셋
  "cross": [{"a": ["요약", "B2"], "b": ["상세", "합계"]}],     # 시트 간 같아야 할 값
}
```

### 관문2 — 검수 실행
```python
import verify
result = verify.verify_workbook(path, config)   # 원본 불변, 순수 판정
```

### 관문3 — 보고
```python
import report
print(report.render(result))     # 항목·위치·기대값·실제값·차이·심각도 테이블 + 요약
```

### 관문4 — 수정 (사용자 확인 후에만)
- [HARD] 확인 없이 값 변경 금지. 사용자가 특정 발견의 수정을 요청하면 그 셀만 고친다.

---

## 무엇을 잡나 (값 정확성 4종)
| 종류 | 무엇을 대조 | 기준 |
|---|---|---|
| **내부 정합** | 소계/총계 ↔ 구성요소 합 | 자동 감지(합계 라벨) + 허용오차 |
| **규칙 위반** | 음수 불가·범위·중복 키·합계 목표 | `rules` config |
| **외부 대조** | 집계값 ↔ 원장/원천 정답셋 | `external.reference` |
| **교차 참조** | 시트 간/파일 간 같아야 할 값 | `cross` 짝 |

심각도: **Critical**(정합 깨짐·원장 불일치) · **Warning**(규칙 위반·범위) · **Info**(참고).

## 독립 검수 — 권장 체인 (data-auditor)

이 스킬이 낸 검수 결과를 **같은 세션이 다시 믿지 않게** 하려면 읽기 전용 감사자에게 넘긴다:

```
data-verify(검수 보고) → itda-data:data-auditor(원장·원 셀 독립 재계산, AUDIT_SCHEMA JSON)
```

`Agent` 도구로 `itda-data:data-auditor` 를 명시 디스패치한다(자동 위임은 발동하지 않는다). 프롬프트에
**검수 대상 산출물 경로 + 원장 경로**(없으면 원장 대조 축이 `unverifiable` 로 남는다)를 넘기고, 반환된
JSON 의 `verdict` 를 필드로 읽는다 — critical 1건이면 `FAIL` 이고 `unverifiable` 이 비어 있지 않으면
`PASS` 가 아니다. 감사자는 파일을 고치지 않으며 `outputs/data-audit-report.md` 1개만 쓴다
(계약: `cowork-agent-orchestration.md` §감사자). 에이전트 타입이 없는 환경이면 general-purpose
서브에이전트에 `agents/data-auditor.md` 지시서를 먼저 읽고 따르라고 명시한다.

## 범위 외
- 수식 구조·오류 감사(#REF!·하드코드 등) → `data-audit`
- 재무모델 무결성(BS balance·DCF/LBO) → 범위 밖
- 수식 감사 → `data-audit`. 캐시값이 빈 파일의 수식 재계산 → `itda-data:xlsx-recalc`.
- 열어둔 엑셀에 실시간 하이라이트/코멘트 — 본 스킬은 파일 기반 openpyxl.

## 정확성 원칙 (data-accuracy)
- 부동소수점 비교는 **허용오차**(`tolerance`, 기본 0.01)로 — 눈대중·정확한 `==` 금지.
- 통화/천단위/`%` 표기는 숫자로 파싱해 비교(`$1,200`→1200, `45%`→45 — 기호만 제거해 `45+55=100` 검산이 자연스럽게).
- "동작함"이 아니라 "값이 실제와 일치함"으로 판정. 표본·눈대중 금지.

## 입력 방어 (엑셀 파일)
열기 전에 시트의 병합 목록을 먼저 읽는다(`scripts/xlsx_guard.py`, 원본 불변).
- **거꾸로 적힌 병합**(`B1:A1`)은 openpyxl 이 파일 전체를 못 여는 원인이라 빼고 읽는다.
- **거대한 병합**(병합 하나 1만 칸 초과, 시트 합계 20만 칸 초과)은 빼고 읽는다 — 열 전체 병합 하나로 수십 초·수백 MB 가 들었다.
- **겹친 병합**·**병합에 가려진 값**(왼쪽 위가 아닌 칸의 값 — openpyxl 은 조용히 버린다)은 알린다.
- 위 네 가지는 모두 종류 `입력` · Warning 발견으로 보고에 실린다. 조용히 넘기지 않는다.
- 값 grid 는 값이 있는 범위까지만 만든다 — 먼 칸에 서식만 남은 시트(행 20만)도 즉시 끝난다.
- date1904(맥 엑셀) 워크북의 날짜는 openpyxl 이 보정해 읽는다(테스트 고정).
- 값이 꽉 찬 큰 시트는 여전히 무겁다: 10만 행×20열(200만 칸)에 약 6초·1.1GB.
- 부동소수 잔차(`0.1+0.2` = 0.30000000000000004)는 허용오차 비교라 불일치로 잡지 않는다(테스트 고정).

## Prerequisites
**파일 경로(크로스플랫폼)**: Python 3.10+ · openpyxl (`scripts/requirements.txt`).

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
printf "%s\n" "$c"' _ data-verify itda-data "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```
```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'data-verify'; $P = 'itda-data'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```
```bash
# macOS/Linux — 정문
python3 "$SKILL_DIR/scripts/install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/scripts/requirements.txt"
python3 "$SKILL_DIR/scripts/verify.py" <파일.xlsx> --config config.json
# Windows — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
py -3 "$env:SKILL_DIR\scripts\verify.py" <파일.xlsx> --config config.json
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | openpyxl 값 grid 로드(시트별). **백엔드 독립** 인터페이스 |
| `verifiers.py` | 내부정합·규칙위반·외부대조·교차참조 순수 판정 함수 |
| `report.py` | 발견 테이블 + 요약 렌더 |
| `verify.py` | 검수 오케스트레이션 엔트리(보고 전용) |
