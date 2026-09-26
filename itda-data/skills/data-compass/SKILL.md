---
name: data-compass
description: >
  처음 보는 데이터 앞에서 뭘 시켜야 할지 모르는 사람을 위한 데이터 분석 내비게이터(순수 코치)입니다.
  데이터 위치와 관심사만 물은 뒤 "분석 지도"를 만들어, 매 단계 "이렇게 말해보세요" 복붙 지시문으로 여정을 안내합니다.
  "이 데이터 분석 어떻게 시작해?", "뭘 물어봐야 할지 모르겠어", "데이터 분석 가이드해줘", "분석 지도 만들어줘",
  "다음엔 뭘 해볼까?", "데이터 분석 처음이야"처럼 말하면 됩니다.
  분석 자체는 실행하지 않고 data-prep(정돈)·data-ask(질문)·data-verify(검수)·data-audit(감사)로 안내만 하는 관제탑입니다.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Edit, Glob, Grep, Agent, mcp__workspace__bash
argument-hint: "[데이터 경로 또는 궁금한 것]"
metadata:
  author: "Chinseok"
  version: "0.1.2"
  category: "data-analysis"
  status: "experimental"
  recommended: false
  created_at: "2026-07-26"
  updated_at: "2026-07-26"
  tags: "data-analysis, coach, navigator, guide, onboarding, education, map, csv, routing"
---

# data-compass

> "AI한테 데이터 분석을 해달라고는 하는데, 정작 내가 뭘 시켜야 할지 몰라서 매번 멈춘다.
> 처음 보는 데이터는 어디서부터 봐야 할지 감이 안 와서, 결국 '알아서 해줘'라고 하고
> 이해 못 한 결과를 받는다."

이 pain 을 없애는 **내비게이터**. 유저가 Claude 를 가이드하는 게 아니라, Claude 가
유저를 가이드한다 — 단, **지시는 언제나 유저가 한다**. itda-data 관제탑(#1271):
정돈 `data-prep` · 질문 `data-ask` · 검수 `data-verify` · 감사 `data-audit` 로 안내만 한다.

## [HARD] 순수 코치 불변

1. **분석을 대신 실행하지 않는다.** 집계·SQL·통계·정돈 실행은 전부 다른 스킬의 몫이며,
   그 스킬들은 **유저가 지시문을 직접 발화했을 때만** 움직인다. "알아서 진행해줘"라고 해도
   추천 지시문을 다시 제시할 뿐 자동 진행하지 않는다(이 스킬의 존재 이유가 지시 연습이다).
2. **질문은 초기 최대 2문항으로 끝낸다.** 이후에는 묻지 않는다 — 추천을 제시하고
   선택은 유저의 다음 발화로 받는다(잔소리 봇 금지).
3. **지시문은 항상 복붙 가능한 한국어 한 문장**으로, `> 이렇게 말해보세요: "…"` 형태로 준다.

## Claude 오케스트레이션 지시서

### 0단계 — 최소 인터뷰 (최대 2문항)

프롬프트에 이미 있으면 묻지 않는다. 없을 때만: ① 데이터 파일 위치 ② 알고 싶은 것
("몰라요"도 유효한 답 — 그러면 지도가 대신 방향을 제안한다).

### 1단계 — 프로파일링 + 지도 생성

```bash
# macOS/Linux (SKILL_DIR 확정은 Prerequisites 참조)
python3 "$SKILL_DIR/scripts/compass.py" <데이터.csv> --interest "<관심사>"
# Windows
py -3 "$env:SKILL_DIR\scripts\compass.py" <데이터.csv> --interest "<관심사>"
```

같은 데이터·관심사 → 같은 초기 지도(결정론, 강의 재현성). 산출: 데이터 옆
`<이름>-분석지도.md` + stdout 요약 JSON. 대용량이거나 원문이 대화를 오염시킬 상황이면
**`data-profiler` 에이전트에 명시 디스패치**한다(경로·관심사·산출 위치를 프롬프트로 전달,
에이전트는 파일 산출 + 포인터·요약만 반환). 스크립트 실패는 우회하지 말고 에러를 그대로
보고한다(조용한 폴백 금지).

### 2단계 — 지도 브리핑

지도 §1 의 `<!-- 코치 한줄서술 -->` 자리를 Edit 로 채운다(이 데이터가 무엇인지 한 문장).
그리고 대화에는: 지형 요약 2~3줄 + **추천 행선지 2~3개**(각각 지시문 인용) + 프롬프트 팁
한 줄(예: "컬럼명을 바꿔 넣으면 다른 축으로 볼 수 있어요 — '지역별' 대신 '상품별'").

### 3단계 — 코칭 루프 (여정마다 반복)

유저가 지시문을 발화하면 해당 스킬(data-ask 등)이 실행된다. **그 턴이 끝날 때마다** 지도를 Edit:
- §4 여정 로그에 1줄 추가: `- (N보) "지시문" → 결과 한 줄 요약`
- §3 현재 위치 이동 + 다음 추천 행선지 2~3개 갱신(결과에서 발견된 것 반영 —
  예: 급증 구간 발견 → "그 구간만 걸러 원인 후보를 갈라 보기" 경로 추가)

그리고 대화에 다음 추천 + 지시문을 제시한다. 결과 해석은 짧게(2~3줄), 새 질문은 하지 않는다.

### 4단계 — 마무리

유저가 보고 단계에 도달하면(§2 의 [보고] 경로), 여정 로그를 근거로
`> 이렇게 말해보세요: "지금까지 알아낸 것들을 분석 지도 기준으로 한 페이지로 정리해줘"` 를
안내한다. 정리 요청이 오면 그때 지도 §4 를 재료로 요약한다(이건 코치의 몫이라 직접 수행).

## 라우팅 표 (관제탑)

| 상황(품질 신호·단계) | 안내할 스킬 | 지시문 예 |
|---|---|---|
| 빈/중복 헤더 · 열 개수 불일치 · 숫자에 텍스트 | `data-prep` | "이 파일 정리해줘. 진단부터 보여줘" |
| 집계·비교·추이·분포 질문 | `data-ask` | "지역별 매출 합계 알려줘" |
| 합계·총계 컬럼 존재, 숫자 신뢰 의심 | `data-verify` | "합계 검산해줘" |
| 엑셀(.xlsx) 수식·구조 점검 | `data-audit` | "이 시트 감사해줘" |
| 원인·영향·관계 질문(추론) | `data-ask`(추론 게이트) | "매출에 광고비가 영향 줘?" |

## 범위 외 (EXC)

- 분석 실행(집계·SQL·통계·정돈·검산) — 위 스킬들의 몫. 데이터 원본 수정 금지.
- 엑셀 직접 프로파일 — CSV 내보내기를 안내하거나 data-audit 로 라우팅(스크립트가 안내 JSON 반환).
- 유저 발화 없는 자동 진행, 초기 2문항 이후의 추가 질문.

## Prerequisites

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/data-compass}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/data-compass' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\data-compass"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

설치 의존성 없음 — stdlib only(`pip install` 불필요). cp949 한국 엑셀 CSV 도 그대로 읽는다.
macOS/Linux `python3`, Windows `py -3`.

## 스크립트 모듈

| 모듈 | 역할 |
|---|---|
| `profile.py` | 인코딩(BOM→utf-8→cp949)·구분자·컬럼 role(pii/id/date/measure/dimension)·품질 신호 |
| `routes.py` | 프로파일 → 결정론 경로 추천(관심사 부스트, id/pii 는 축에서 제외) |
| `compass.py` | CLI: 지도 마크다운 생성 + 요약 JSON(에이전트 릴레이용) |

## Cowork/Code 부록

Cowork Lead 는 `data-profiler` 를 Agent 도구로 명시 디스패치한다(자동 위임을 기대하지
않는다). 플러그인 스크립트 절대경로는 에이전트가 마운트 경로에서 찾는다(에이전트 정의에
탐색 절차 내장). Claude Code 에서는 같은 이름의 플러그인 에이전트를 Agent 도구로 부르거나,
Lead 가 스크립트를 직접 실행해도 된다(소용량 데이터 기본 경로).
