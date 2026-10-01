---
name: data-ask
description: >
  CSV 를 한국어로 물으면 실제로 계산해 답하는 질문 스킬입니다. "지역별 환불율", "월별 매출 추이", "재구매 비중"처럼 말하면 됩니다.
  SQL 을 직접 쓰지 않고 typed QueryPlan 으로 옮겨 검증된 SQL 을 duckdb 로 실행하며(눈대중 금지), 표본이 작은 결과는 신뢰가 낮다고 경고합니다. cp949 한국 엑셀도 그대로 읽습니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[CSV 경로 또는 질문]"
metadata:
  author: "Chinseok"
  version: "0.2.4"
  category: "data-analysis"
  status: "experimental"
  recommended: false
  created_at: "2026-06-24"
  updated_at: "2026-09-30"
  tags: "csv, duckdb, queryplan, sql, data-analysis, read-only, incubating"
---

# data-ask

비전공 실무자가 한국어로 물으면 CSV 를 **실제로 계산해** 답하는 "질문 양심" 스킬.
itda-data 데이터 양심 vertical(정리 `data-prep` · 질문 `data-ask`)의 질문 담당.
(SPEC-DATA-VERTICAL-001, itda-data. 구 `data-query-runner`·`data-analysis-advisor` 흡수)

핵심: **LLM 이 SQL 을 직접 쓰지 않는다.** 한국어 요청 → typed `QueryPlan` → 결정론·파라미터화 SQL → 잠금된 duckdb 실행 → 정직 보고(소셀 N 자동 경고).

실행 엔진은 **2단계 read_csv 봉인**(#567): 신뢰 단계에서 우리 SQL `read_csv` 로 로드하면 duckdb 네이티브 스니퍼가 타입·구분자·날짜·cp949 와 **앞자리 0 코드(`06234`→VARCHAR 보존)** 를 정확히 처리하고, 곧바로 외부접근을 봉인해 이후 에이전트 SQL 은 원격·로컬파일·COPY 가 차단된다. 통화/형식 금액(`480,000원`·`₩`·`(1,200)`)은 measure 집계 시 SQL 정규화식으로 처리한다.

---

## Claude 오케스트레이션 지시서

> [HARD] "무조건"·"빠르게"·force_override 로 매핑 확인·소셀 경고·추론 게이트를 건너뛰지 않는다.
> 아래 모듈 임포트 전에 Prerequisites 의 `SKILL_DIR` 확정 블록을 실행하고 `cd "$SKILL_DIR/scripts"` 한다.

### 1단계 — 로드 + 프로파일(role) + 비계
```python
import safe_exec, profiler
info = safe_exec.inspect(source_path)             # read_csv 2단계 봉인 → 타입·앞자리0·cp949 자동
schema, rows = info["schema"], info["sample_rows"] # schema: {name,type,samples,numeric}
profiled = profiler.profile(rows, schema)         # 컬럼별 role: id/pii/measure/dimension/date
examples = profiler.suggest_questions(profiled)   # id/pii 제외한 질문 예시
# 사용자에게: 컬럼·role 요약 + examples 제시 (encoding=info["encoding"])
```

### 2단계 — 구조 점검 + 분류 + 라우팅

**(a) 구조 점검 → prep preflight (REQ-030·031)**
```python
import structure
s = structure.assess_structure(rows)
if s["needs_prep"] or info["column_issues"]:   # 빈·None·중복 열(원본 헤더)도 prep 선행
    # data-prep 을 blocking 호출 → {tidy_path, transform_log, confirmation_id} 수신 후
    # info = safe_exec.inspect(tidy_path) 로 정돈본 재로드 → 1단계부터 다시.
    # ask 가 primary, prep 은 blocking preflight. (data-prep 스킬은 #11)
    ...
```

**(b) 분류**
- **추론**(관계·영향·유의성·예측·원인) → 2-c inferential_flow.
- **서술**(집계·필터·정렬·비율·시간버킷) → 3단계(QueryPlan).

**(c) inferential_flow — 추론 양심 (REQ-040, 서술 경로와 분리된 상태기계)**
```python
import gates, inference
# 1) 결정 인터뷰(AskUserQuestion): 무슨 결정? 인과로 해석? 오차비용? → decision_interview_id
# 2) 실행 + 교차검증: res = inference.simple_regression(rows, y="매출", x="광고비")
#    (또는 inference.pearson(rows, x, y)). res["_verify"] 가 독립 재구현 대조 결과.
# 2b) 다중공선성(예측변수 2개 이상): mc = inference.multicollinearity(rows, predictors)
#     → VIF(statsmodels lazy) 또는 pairwise 상관 폴백.
# 3) 방법 게이트(표본 충분성 + 다중공선성): verdict = gates.method_gate(res["n"], predictors, mc)
report_text = gates.build_inferential_report(
    {"decision_interview_id": di_id, "gate_verdict": verdict, "verification_result": res["_verify"]},
    f"기울기 {res['slope']} (R²={res['r2']}, N={res['n']})",
)
# [HARD] 세 증거(인터뷰·게이트·재현)가 없으면 build_inferential_report 가 ValueError 로 거부.
# 추론 보고는 날조 불가, 재현 불일치는 자동 경고 — advisor 5관문 양심(표본·다중공선성)을 코드로 보존.
# (p-value·다중회귀는 후속: statsmodels lazy)
```

### 3단계 — QueryPlan 작성 (SQL 직접 작성 금지)
```python
import queryplan as qp
plan = qp.QueryPlan(
    aggregation="ratio",                                   # count|sum|avg|min|max|ratio
    ratio_condition={"column": "환불여부", "op": "=", "value": "Y"},
    dimensions=["지역"],                                    # group-by (role=measure/id/pii 는 차원 금지)
    # measure="금액", filters=[{"column":..,"op":..,"value":..}], time_grain="month",
)
```
- 컬럼은 schema 실재값만. 모호하면 단정 말고 AskUserQuestion 확인.

### 4단계 — 안전 실행
```python
import safe_exec
result = safe_exec.run_plan(source_path, plan)
# plan_to_sql 이 결정론·파라미터화 SQL 생성, 실행기가 외부접근차단·SELECT-only·LIMIT·N자동주입 강제.
# plan 으로 표현 불가한 질의만 safe_exec.run_sql(가드된 raw fallback) — 명시 경고 동반.
```

### 5단계 — 정직 보고
```python
import report
print(report.render(result, threshold=5))   # 실행 SQL 노출 + 소셀(N<5) 자동 경고
```

---

## 범위 외 (EXC)
- LLM 직접 SQL 생성으로 QueryPlan 우회(raw fallback 은 경고+잠금에서만).
- 원본 수정·외부 네트워크·디스크 쓰기·임의 파일 접근.
- 데이터 정돈 → `data-prep`. 추론 통계 실행은 게이트 통과 후에만.

## Prerequisites

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
printf "%s\n" "$c"' _ data-ask itda-data "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'data-ask'; $P = 'itda-data'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

설치 정문 `python3 "$SKILL_DIR/scripts/install_skill_deps.py"`(Windows `py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"`) — duckdb 를 이 환경에 맞는 pip 인자로 설치한다(`--all` 이면 statsmodels 까지). 수동 폴백 `python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"`. 위 모듈들은 CLI 엔트리 없이 임포트하므로 **모듈 실행 전 `cd "$SKILL_DIR/scripts"`** 한다(Windows: `cd "$env:SKILL_DIR\scripts"`). cp949(한국 엑셀) 파일을 읽으려면 duckdb 코어 `encodings` 확장이 필요하다 — 최초 1회 온라인에서 `INSTALL encodings;` 한 뒤로는 오프라인에서 `LOAD encodings` 만으로 동작한다(`safe_exec` 가 cp949 일 때 자동 LOAD). 그 외 stdlib. macOS/Linux `python3`, Windows `py -3`.

## 스크립트 모듈
| 모듈 | 역할 |
|---|---|
| `loader.py` | 인코딩 결정(BOM→utf-8→cp949) + 원본 헤더 위생 검사 + 금액 정규화 참조 |
| `profiler.py` | 컬럼 role 판정 + 질문 비계 |
| `queryplan.py` | QueryPlan → 결정론·파라미터화 SQL(통화 measure 정규화 정본) |
| `safe_exec.py` | read_csv 2단계 봉인 실행기(`inspect`·plan 실행·N 주입·raw fallback) |
| `structure.py` | 경량 messy 감지(→ data-prep preflight) |
| `gates.py` | 추론 양심(증거 없이 보고 생성 차단·표본 게이트) |
| `inference.py` | 상관·단순회귀 실행 + 독립 재구현 교차검증 |
| `report.py` | 정직 보고(소셀 강제 경고) |
