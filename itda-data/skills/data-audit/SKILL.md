---
name: data-audit
description: >
  엑셀·스프레드시트의 수식 오류와 흔한 실수를 훑어 위험한 셀을 짚어주는 감사 스킬입니다. #REF!·하드코드(=A1*1.05)·범위 누락(off-by-one)·복붙으로 뭉개진 수식·순환참조·깨진 시트 링크를 찾습니다. "이 시트 감사해줘", "수식 검토해줘", "수식 오류 찾아줘", "QA해줘", "복붙하다 뭐 깨졌는지 봐줘", "모델에 뭔가 이상해"처럼 말하면 됩니다.
  보고 우선(확인 없이 셀 미변경). 파일은 openpyxl 크로스플랫폼(Office 불필요).
  [책임 경계] 본 스킬은 수식 오류·실수 감사 전담 — 캐시값이 빈 파일의 재계산은 itda-data:xlsx-recalc.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, mcp__workspace__bash
argument-hint: "[xlsx 경로 또는 감사 요청]"
metadata:
  author: "Chinseok"
  version: "0.4.1"
  category: "data-tidy"
  status: "experimental"
  recommended: false
  created_at: "2026-07-07"
  updated_at: "2026-09-30"
  tags: "xlsx, audit, formula, spreadsheet, openpyxl, qa, hardcode, incubating"
---

# data-audit

엑셀 모델을 며칠 손대다 보면 `=A1*1.05`처럼 숫자를 셀에 박아둔 곳, `SUM`이 마지막 행을 빠뜨린 곳,
복붙하다 수식이 값으로 뭉개진 곳을 눈으로는 못 찾는다. 보내기 직전 합계가 미묘하게 안 맞는데
어디서 틀어졌는지 몰라 처음부터 다시 훑는 — 그 반복을 없애는 "수식 양심" 스킬.

itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask` · 감사 `data-audit`)의 감사 담당.
(#952, Claude for Excel `audit-xls` 이식 — 수식·데이터 레벨. 재무모델 무결성은 범위 외.)

---

## Claude 오케스트레이션 지시서

> [HARD] 보고 우선 — 발견을 먼저 보고하고, 셀 수정은 사용자가 명시적으로 요청할 때만 그 셀만 고친다.
> [HARD] "동작함"이 아니라 "실제로 그 셀이 틀렸나"로 판정한다(데이터 정확성 원칙). 확신이 낮은 발견은 severity를 낮추고 근거를 함께 낸다.
> 아래 모듈을 임포트해 쓸 때는 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다(CLI 로 쓰면 `python3 "$SKILL_DIR/scripts/audit.py"`).

### 관문1 — 감사 실행
```python
import audit
result = audit.audit_workbook(path, sheet=None)   # sheet=None 이면 전체 워크북(숨은 시트 포함)
```

### 관문2 — 발견 보고
```python
import report
print(report.render(result))     # Sheet·Cell·Severity·Category·Issue·Fix 테이블 + 요약 한 줄
```

### 관문3 — 수정 (사용자 확인 후에만)
- [HARD] 확인 없이 셀 변경 금지. 사용자가 특정 발견의 수정을 요청하면 **그 셀만** 고치고, 원본 백업을 남긴다.

---

## 무엇을 잡나 (수식·데이터 레벨)
| Severity | 항목 |
|---|---|
| Critical | 수식 오류(`#REF!` `#VALUE!` `#N/A` `#DIV/0!` `#NAME?`) · 깨진 시트 링크 · 순환참조 |
| Warning | 수식 내 하드코드(`=A1*1.05`) · 이웃과 다른 수식 · off-by-one 범위 · 복붙으로 값이 된 수식 · 단위/스케일 급변 |
| Info | 숨긴 행·시트(override·stale 계산 은닉 가능) |

## 이 스킬을 쓰지 않을 때
| 상황 | 대신 쓸 스킬 |
|---|---|
| openpyxl 로 만든 파일이라 수식 캐시값이 비어 있다(값 기반 검사 전 재계산) | `itda-data:xlsx-recalc` |
| 수식 구조가 아니라 합계·원장 대조로 값이 맞는지 검산 | `itda-data:data-verify` |

## 범위 외
- 재무모델 무결성: BS balance·cash tie-out·재무제표 3표 정합, DCF/LBO/3-statement/Merger/Comps 모델별 버그 (#952 스코프 아웃)
- Excel 애드인(Office JS)·열어둔 엑셀에 실시간 하이라이트/코멘트 — 본 스킬은 파일 기반 openpyxl.

## 정확성 한계 (openpyxl 재계산)
openpyxl은 수식을 **재계산하지 않는다**. `#REF!`·`#DIV/0!` 같은 **동적 에러 값**은 파일에 마지막 저장된 캐시값 기준으로만 읽힌다.
한 번도 Excel/LibreOffice로 열어 계산·저장된 적 없는 파일은 이 캐시가 비어 놓칠 수 있다 —
필요하면 `itda-data:xlsx-recalc` 로 재계산한 새 파일을 감사한다(LibreOffice 단독, 격리 프로필·timeout).
수식 **문자열** 기반 검사(하드코드·off-by-one·순환참조·깨진 링크·복붙)는 이 한계와 무관하게 동작한다.

## 입력 방어 (엑셀 파일)
열기 전에 시트의 병합 목록을 먼저 읽는다(`scripts/xlsx_guard.py`, 원본 불변).
- **거꾸로 적힌 병합**(`B1:A1`)은 openpyxl 이 파일 전체를 못 여는 원인이라 빼고 읽는다.
- **거대한 병합**(병합 하나 1만 칸 초과, 시트 합계 20만 칸 초과)은 빼고 읽는다 — 열 전체 병합 하나로 수십 초·수백 MB 가 들었다.
- **겹친 병합**·**병합에 가려진 값**(왼쪽 위가 아닌 칸의 값 — openpyxl 은 조용히 버린다)은 알린다.
- 위 네 가지는 모두 category `입력` · Warning 발견으로 보고에 실린다. 조용히 넘기지 않는다.
- 칸은 파일에 실제로 있는 것만 읽는다 — 먼 칸에 서식만 남은 시트(행 20만)도 즉시 끝난다.
- date1904(맥 엑셀) 워크북의 날짜는 openpyxl 이 보정해 읽는다(테스트 고정).
- 값이 꽉 찬 큰 시트는 여전히 무겁다: 10만 행×20열(200만 칸)에 약 14초·2.2GB(파일을 수식·값 두 번 연다).

## Prerequisites
**파일 감사(크로스플랫폼)**: Python 3.10+ · openpyxl (`scripts/requirements.txt`).

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
printf "%s\n" "$c"' _ data-audit itda-data "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```
```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'data-audit'; $P = 'itda-data'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
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
python3 "$SKILL_DIR/scripts/audit.py" <파일.xlsx>            # 사람용 테이블
python3 "$SKILL_DIR/scripts/audit.py" <파일.xlsx> --json      # 기계용 JSON

# Windows — 정문
py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
py -3 "$env:SKILL_DIR\scripts\audit.py" <파일.xlsx>
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | openpyxl 수식면·값면 양면 로드(`SheetView`) |
| `checks.py` | 수식·데이터 감사 체크(오류·하드코드·불일치·off-by-one·복붙·순환·링크·단위·숨김) |
| `report.py` | 발견 테이블 + 요약 렌더(사람용/기계용) |
| `audit.py` | 감사 오케스트레이션 엔트리(보고 우선) |
