---
name: xlsx-recalc
description: >
  openpyxl 등으로 만든 xlsx 는 수식만 있고 계산값이 비어 미리보기·pandas·다른 스킬에서 빈칸으로 보입니다. LibreOffice 로 재계산해 값을 채운 새 파일을 만들고, 틀린 값을 성공으로 쓸 위험(외부 링크 값 없음·구버전 LibreOffice)은 계산 전에 막습니다. "엑셀 수식 값 채워줘", "xlsx 재계산해줘", "openpyxl 로 만든 파일 합계가 빈칸이야"처럼 말하면 됩니다.
  [책임 경계] 본 스킬은 수식 캐시값 재계산 전담 — itda-data:data-audit 는 수식 오류 감사, itda-doc:xlsx-design 은 xlsx 신규 생성.
license: MIT
compatibility: "Claude Code & Cowork. Python 3.10+ (stdlib). LibreOffice 24.8 이상(soffice) 필요."
user-invocable: true
allowed-tools: Read, Bash, Glob, mcp__workspace__bash
argument-hint: "<수식이 든.xlsx> [출력.xlsx]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.1.0"
  category: "data-analysis"
  status: "experimental"
  recommended: false
  created_at: "2026-09-13"
  updated_at: "2026-09-14"
  tags: "xlsx, excel, recalc, recalculate, formula, cache, openpyxl, libreoffice, spreadsheet"
---

# xlsx-recalc

openpyxl 로 만든 xlsx 는 **수식 문자열만 있고 캐시값(`<v>`)이 비어 있다.** 엑셀은 열 때 다시 계산하지만,
openpyxl `data_only=True`·pandas·미리보기·다른 스킬은 빈칸이나 0 을 본다. 이 스킬은 LibreOffice 로 재계산해
값을 채운 **새 파일**을 만든다.

계산은 **LibreOffice 만** 한다. 대체 엔진 7종(excelize·Formualizer·IronCalc·HyperFormula·formulas·pycel·xlcalculator)을
LibreOffice 결과와 셀 단위로 대조했더니 모두 에러 없이 틀린 값을 냈다(#1690). SUM·SUMIFS·VLOOKUP·ROUND·TEXT 같은
핵심 함수도 예외가 아니었다. 스크립트는 계산 **전후의 검사**를 맡는다.

| 시점 | 검사 | 실패 시 |
|---|---|---|
| 계산 전 | 외부 통합문서를 참조하는 수식마다 **링크 값 캐시**가 있는가(정의된 이름·이름 체인 포함) | exit 8 — 없으면 LibreOffice 가 0 을 성공으로 쓴다 |
| 계산 전 | Strict Open XML·데이터 테이블(가상 분석 표)이 아닌가 | exit 9 — 데이터 테이블은 LibreOffice 가 Excel 에 없는 `TABLE()` 수식으로 바꾼다 |
| 계산 전 | 이 환경이 `AF_UNIX` 소켓을 허용하는가(POSIX) | exit 7 — 막혀 있으면 LibreOffice 가 기동하지 못한다 |
| 계산 전 | LibreOffice 가 **24.8 이상**인가 | exit 6 — 7.4 는 XLOOKUP 을 몰라 에러 없이 틀린다 |
| 계산 | 격리 프로필(재계산 "항상") · timeout · 프로세스 그룹·프로필 기준 잔존 정리 | exit 4 — 재시도하지 않는다 |
| 계산 후 | 수식 셀·배열 수식 결과 셀마다 타입에 맞는 캐시가 있는가 · 입력 수식과 배열 범위가 그대로인가 · 외부 링크의 종류·대상 경로·시트 이름이 그대로인가 | exit 5 |
| 계산 후 | LibreOffice 가 수식 표기를 바꾼 셀(`formula_rewritten`) | 막지 않고 보고 — 값이 바뀔 수 있는 모양은 위험 표시 |

> [HARD] **"변환이 성공했다"로 끝내지 않는다.** 판정은 스크립트의 종료 코드와 JSON 이다. exit 0 이 아니면 결과 파일은
> 만들어지지 않으며, 에이전트가 다른 방법(다른 엔진·openpyxl 로 값 직접 쓰기·매크로)으로 대신 채우지 않는다.

## 사전 준비

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
# Cowork 는 플러그인 설치면 .remote-plugins, 단일 .skill 업로드면 .claude/skills 아래에 둔다(2026-09-14 실측)
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/xlsx-recalc}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins /sessions/*/mnt/.claude/skills -type d -path '*/skills/xlsx-recalc' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\xlsx-recalc"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

- Python 의존성 없음(stdlib).
- **LibreOffice 24.8 이상**(`soffice`). Cowork VM 에는 26.2 가 있다(2026-09-14 실측). 없으면 exit 3 — 설치하거나 `--soffice` 로 경로를 준다.

## 실행

```bash
python3 "$SKILL_DIR/scripts/recalc.py" 입력.xlsx 출력.xlsx --json
```

```powershell
py -3 "$env:SKILL_DIR\scripts\recalc.py" 입력.xlsx 출력.xlsx --json
```

- 출력 경로를 생략하면 `<입력 이름>-recalc.xlsx` 로 쓴다. 사용자에게 경로를 알린다. **입력과 같은 경로는 거부한다**(원본을 덮어쓰지 않는다).
- `--timeout 초`(기본 180): 넘기면 LibreOffice 를 정리하고 exit 4 로 끝낸다. 재시도하지 않는다.
- 수식이 하나도 없으면 LibreOffice 를 부르지 않고 그대로 복사한다(`engine: "none"`).

## 결과 해석 (JSON)

| 필드 | 뜻 |
|---|---|
| `libreoffice_version` · `formula_cells` · `elapsed_ms` | 계산한 LibreOffice 버전 · 수식 셀 수 · 걸린 시간 |
| `input_missing_cache` | 입력에서 캐시가 없던 수식 셀 수(openpyxl 저장본이면 보통 전부) |
| `error_cells` · `error_cell_count` | 계산 결과가 에러 값(`#DIV/0!`·`#N/A` 등)인 셀(최대 50) — **사용자에게 보고한다** |
| `external_link_refs` | 외부 통합문서 참조 수. 링크 파트에 저장된 값으로 계산했다(원본 파일을 다시 읽지 않았다) |
| `external_link_targets_restored` | LibreOffice 가 표기만 바꾼 외부 링크 대상 경로(`/data/x.xlsx` → `../../../data/x.xlsx` 등)를 입력 원문으로 되돌린 목록. 같은 위치를 가리킬 때만 되돌린다 |
| `workbook` | `date1904`(1904 날짜 체계) · `full_precision`(false 면 "표시 형식대로 계산") — LibreOffice 가 그 설정대로 계산했다 |
| `formula_rewritten_count` · `formula_rewritten_risky_count` · `formula_rewritten` | LibreOffice 가 저장하며 표기를 바꾼 수식. 항목마다 `before`·`after`·`risks` |

사용자에게는 엔진·에러 셀·(있으면) 외부 링크 값을 썼다는 사실을 한국어로 요약한다.

### 수식 표기 변경(`formula_rewritten`)

LibreOffice 는 저장할 때 수식을 다시 쓴다. 대부분은 표기만 바뀐다(`TRUE`→`TRUE()`, `'설정'!A1`→`설정!A1`, `F18:F18`→`F18`).
`risks` 가 비어 있지 않으면 **다음 재계산에서 값이 달라질 수 있는 변화**다 — 사용자에게 셀과 전후 수식을 그대로 보여 준다.

| risk | 예 |
|---|---|
| `numeric_literal_changed` | `ROUND(0.49999999999999994,0)` → `ROUND(0.5,0)` — 지금 캐시는 0, 다음 계산은 1 |
| `string_literal_changed` · `function_changed` · `reference_changed` | 문자열 상수·함수 이름(`_xlfn.` 접두 포함)·참조가 달라짐 |
| `other_changed` | 위 분류에 들지 않지만 확인된 표기 변환도 아닌 차이(연산자·논리 상수·시트 이름 등) — 무해로 보지 않는다 |

## 실패 대응 (종료 코드)

| exit | 상황 | 할 일 |
|---|---|---|
| 2 | 입력이 없음·xlsx 가 아님·출력 폴더 없음·입력=출력 | 메시지대로 경로를 확인한다 |
| 3 | soffice 없음·실행 불가 | LibreOffice 설치 여부를 사용자에게 알린다 |
| 4 | timeout | 파일 크기·수식 수를 보고하고, 사용자가 원하면 `--timeout` 을 늘려 **한 번** 재실행 |
| 5 | 변환 실패·산출 검증 실패(캐시 없음·수식 소실·배열 범위 변경·외부 링크 변경·LibreOffice 저장 실패) | 메시지 원문을 보고한다. 결과 파일은 없다 |
| 6 | LibreOffice 24.8 미만·버전 판독 불가 | 버전을 알리고 LibreOffice 업그레이드를 안내한다. 낮은 버전으로 억지로 돌리지 않는다 |
| 7 | AF_UNIX 소켓 차단(샌드박스) | 이 환경에서는 LibreOffice 를 실행할 수 없다고 알린다 |
| 8 | 외부 링크 값 캐시 없음·필요한 셀을 증명할 수 없는 외부 참조(전체 열·OFFSET/INDIRECT 와 함께)·링크 파트 없이 파일 이름으로 쓴 외부 참조(openpyxl 의 `'[other.xlsx]Sheet1'!A1`) | `external_link_problems` 의 셀과 참조를 보여 주고, **원본을 Excel 에서 열어 링크를 업데이트·저장**한 뒤 다시 실행하도록 안내한다 |
| 9 | Strict Open XML · 데이터 테이블 | Strict 는 Excel 에서 "Excel 통합 문서(*.xlsx)" 로 다시 저장하도록, 데이터 테이블은 이 스킬로 계산할 수 없다고 알린다 |

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 수식이 틀렸는지·하드코드·범위 누락을 찾고 싶다 | `itda-data:data-audit` |
| 합계·원장 대조처럼 값이 맞는지 검산하고 싶다 | `itda-data:data-verify` |
| 데이터로 디자인된 엑셀을 새로 만들고 싶다 | `itda-doc:xlsx-design` |
| 엑셀 파일을 열어 둔 채 실시간으로 계산값을 보고 싶다(Windows·Office) | `itda-data:data-audit` 의 실시간 경로 |

## 권장 체인

```
xlsx-design(또는 openpyxl 생성) → xlsx-recalc → data-audit / data-verify
```

감사·검수 스킬은 캐시값을 읽으므로, 방금 만든 xlsx 는 재계산을 먼저 거친다.

## 한계

- **결과는 LibreOffice 의 계산값이다.** LibreOffice 와 Excel 이 다른 드문 경우(논리값 산술, `SUM("123")` 같은 텍스트 숫자 처리 등)는
  Excel 로 열어 다시 계산하면 값이 달라질 수 있다. Excel 기준 대조는 아직 하지 않았다(#1690).
- 외부 링크는 파일에 저장된 값으로 계산한다. 원본 통합문서를 다시 읽지 않으므로, 링크 값이 오래됐으면 결과도 오래된 값이다.
- 수식은 도구에 맞게 고치지 않는다. LibreOffice 가 표기를 바꾼 경우는 `formula_rewritten` 으로 알린다.
