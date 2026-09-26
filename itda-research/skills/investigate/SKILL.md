---
name: investigate
description: >
  경쟁 가설과 반증 실험으로 근본 원인을 체계적으로 조사하는 스킬입니다.
  "왜 이렇게 느리지?", "이 에러 원인이 뭐야?", "원인 분석해줘"처럼 말하면 됩니다.
  추측 대신 증거 기반 결론을 제공합니다.
license: Apache-2.0
compatibility: Claude Code & Cowork
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, mcp__workspace__bash
user-invocable: true
argument-hint: '<topic> [--depth simple|full] [--save <path>] [--type bug|perf|arch|verify|interpret]'
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "0.11.2"
  category: "investigation"
  created_at: "2026-04-03"
  updated_at: "2026-07-26"
  aliases: "debug, 분석, check, verify, 조사, 원인"
  tags: "investigate, debugging, hypothesis, falsification, scientific method, root cause analysis"
---

# investigate

반증주의 과학적 방법론으로 불확실한 상황을 체계적으로 조사합니다.

**핵심 원칙**: 모든 것은 가설이다 — 사용자의 주장, 에러 메시지, 문서, 에이전트의 분석, 실험 결과의 해석까지.

---

## Arguments

```
investigate <topic> [--depth simple|full] [--save <path>] [--type bug|perf|arch|verify|interpret]
```

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `<topic>` | 조사할 내용 (필수) | — |
| `--depth simple` | 경량 모드 강제 (1-3 도구 호출) | 자동 감지 |
| `--depth full` | 완전 모드 강제 (5-15 도구 호출) | 자동 감지 |
| `--save <path>` | 조사 보고서를 파일로 저장 | 채팅 출력 |
| `--type bug` | 버그/에러 조사로 강제 분류 | 자동 감지 |
| `--type perf` | 성능 조사로 강제 분류 | 자동 감지 |
| `--type arch` | 아키텍처 검증으로 강제 분류 | 자동 감지 |
| `--type verify` | 주장 검증으로 강제 분류 | 자동 감지 |
| `--type interpret` | 해석/설명 요청으로 강제 분류 | 자동 감지 |

> **`--save` vs 채팅 출력**: `--save <path>` 지정 시 동일 형식을 파일로 저장한다. 미지정 시 채팅에 인라인 출력한다. 경량 모드에서도 `--save` 지정 시 전체 구조 보고서 형식을 사용한다.

---

## 조사 유형 분류 (자동 감지)

| 유형 | 트리거 키워드 | 접근 방식 |
|------|-------------|----------|
| **bug** | error, bug, crash, exception, fail, 오류, 버그, 에러, 크래시 | 반증 기반 근본 원인 분석 |
| **perf** | slow, latency, bottleneck, memory, 느린, 지연, 병목, 메모리 | 측정 기반 가설 검증 |
| **arch** | design, pattern, approach, decision, 설계, 패턴, 아키텍처 | 트레이드오프 반증 분석 |
| **verify** | check, verify, confirm, validate, 확인, 검증, 맞는지 | 주장 반증 실험 |
| **interpret** | explain, why, how, interpret, 왜, 어떻게, 설명해줘 | 다중 해석 생성 |

> **보고서 Type 필드 전체 명칭**: 보고서 출력의 `**Type**` 필드에는 아래 전체 명칭을 사용한다.
> `bug` → `bug` | `perf` → `performance` | `arch` → `architecture` | `verify` → `verification` | `interpret` → `interpretation`

---

## 비례 엄격성 — 자동 깊이 결정

조사 전, 아래 신호로 경량/완전 모드를 자동 결정합니다:

**경량 모드 (simple)** — 다음 조건 모두 해당 시:
- 단일 파일, 명확한 스택 트레이스
- 재현 단계가 사용자 제공되고 결정론적
- 명백한 후보가 1-2개
- 사용자가 "간단히", "빠르게" 언급

**완전 모드 (full)** — 다음 조건 하나라도 해당 시:
- 교차 모듈, 불명확한 원인
- 재현 없음, 간헐적, 환경 의존적
- 복잡한 도메인, 미문서화
- 사용자가 "깊게", "철저히" 언급

**서브에이전트 팬아웃 (선택)** — 완전 모드에서 독립 가설·증거 축이 여러 개면, 환경에 `itda-research:deep-researcher` 서브에이전트가 있을 때 축별로 병렬 위임할 수 있다(가설 + 검증할 증거 + 반증 요구를 프롬프트로). 격리 컨텍스트가 로그·페이지 원문을 흡수하고 구조화 요약만 반환하므로 본 조사 컨텍스트가 오염되지 않는다. 반환된 증거도 아래 방법론의 반증·신뢰도 보정을 동일하게 거친다. 서브에이전트가 없으면 본 컨텍스트에서 순차 진행한다.

---

## 방법론: 6단계 과학적 조사

> **경량 모드**: 6단계 모두 적용하되 출력 간결화. 최소 2개 경쟁 가설, 1회 반증 시도.
> **완전 모드**: 완전한 6단계. 최소 3개 경쟁 가설, 주요 가설당 2회 반증 시도.

---

### Step 1: Observe — 관찰

**목적**: 해석과 분리된 사실만 수집한다.

수행할 작업:
- 관련 소스 파일, 로그, 에러 출력을 읽는다
- 정확한 에러 메시지, 스택 트레이스, 측정값을 기록한다
- 환경 조건(OS, 버전, 설정)을 확인한다
- 사용자의 보고를 **주장**으로 기록한다 (사실이 아님)

**안티패턴**: "인증 모듈이 고장났다" (해석)
**올바른 관찰**: "로그인 엔드포인트가 auth.py:42 NullPointerException과 함께 500 반환" (관찰)

출력: 검증 가능한 데이터만 담긴 "원시 관찰" 섹션

---

### Step 2: Hypothesize — 가설 수립

**목적**: 관찰에 대한 경쟁 설명을 여러 개 생성한다.

수행할 작업:
- 최소 2개의 경쟁 가설 생성 (완전 모드: 3개 이상)
- 각 가설은 **반증 가능**해야 한다 (논리적으로 반증할 수 있는 관찰이 존재해야 함)
- "가능성 낮지만 배제 불가" 가설을 최소 1개 포함 (앵커링 편향 방지)
- 초기 그럴듯함으로 순위를 매기되, **그럴듯함만으로 제거하지 않는다**

**품질 검사**: 어떤 관찰로도 반증할 수 없는 가설은 유효하지 않다. 재구성한다.

---

### Step 3: Predict — 예측

**목적**: 가설을 구분할 예측을 정의한다.

각 가설에 대해 명시한다:
- **참일 때**: "X를 관찰해야 한다"
- **거짓일 때**: "Y를 관찰해야 한다" ← **반증 예측** (핵심)

반증 예측이 실행할 실험을 결정한다.

---

### Step 4: Experiment — 실험

**목적**: 가설을 구분하는 최소한의 테스트를 실행한다.

원칙:
- **증명이 아닌 반증**을 위해 실험을 설계한다
- 가능하면 한 번에 하나의 변수만
- 가설을 구분하는 가장 단순한 실험 사용
- 실행한 정확한 명령어와 출력을 기록한다

조사 유형별 실험:
- **bug**: 타겟 로깅 추가, 제어된 입력으로 재현, 경계 조건 테스트
- **perf**: 특정 코드 경로 프로파일링, 전후 측정, 변수 격리
- **arch**: 최소 프로토타입 구축, 의존성 체인 추적, 실패 모드 테스트
- **verify**: 주장 재현, 주장의 엣지 케이스 테스트, 반례 탐색

---

### Step 5: Analyze — 분석

**목적**: 편향 없이 예측과 결과를 비교한다.

수행할 작업:
- 각 가설에 대해 예측을 실제 결과와 비교한다
- 가설 상태를 표시한다: **supported** (예측 일치) | **eliminated** (반증 예측 일치) | **inconclusive** (결과 모호)
- 모든 가설이 제거되면 → 새 데이터로 Step 2로 복귀
- 결과가 모호하면 → 더 판별력 있는 실험 설계

**안티패턴**: "결과가 H1을 지지하기에 충분히 가깝다." 예측에 명확히 일치하지 않으면 inconclusive다.

---

### Step 6: Conclude — 결론

**목적**: 보정된 신뢰도로 결론을 명시한다.

수행할 작업:
- 가장 많은 반증 시도를 통과한 살아남은 가설을 식별한다
- 아래 신뢰도 보정 표에 따라 신뢰도를 할당한다
- 신뢰도에 비례한 조치를 권장한다
- 남아있는 불확실성을 명시적으로 문서화한다

**안티패턴**: 단일 실험 후 "높은 신뢰도" 주장. 높은 신뢰도는 3회 이상 통과 + 모든 경쟁 가설 제거가 필요하다.

---

## 신뢰도 보정 시스템

신뢰도는 **통과한 반증 시도 수**로만 결정된다 — 권위나 직관으로 선언하지 않는다.

| 수준 | 정의 | 결정 지침 |
|------|------|----------|
| **speculation** | 반증 시도 없음; 초기 추측 | 행동하지 말 것; 더 조사 필요 |
| **low** | 1회 반증 통과; 경쟁 가설 미검증 | 임시 회피책 허용; 조사 계속 |
| **medium** | 2회 이상 반증 통과; 최소 1개 경쟁 가설 제거 | 제한적 배포 허용; 면밀히 모니터링 |
| **high** | 3회 이상 반증 통과; 모든 경쟁 가설 제거 | 구조적 수정 적합; 자신 있게 커밋 |

신뢰도 **하락** 조건:
- 새 증거가 지지 가설을 반박할 때
- 제거된 경쟁 가설이 새 데이터로 부활할 때
- 결론의 범위가 증거를 초과할 때

---

## 중간 피벗 — 모든 가설 제거 시

활성 가설이 모두 실험 결과에 의해 제거되면:

1. 놀라움을 **명시적으로 인정**한다
2. 새 데이터로 **Step 1(Observe)로 복귀**한다
3. 놀라움을 반영한 **새로운 가설을 생성**한다
4. 제거된 가설에 결과를 **억지로 끼워 맞추지 않는다**

---

## 모든 것은 가설이다

다음을 사실이 아닌 **가설로 취급**한다:

| 항목 | 올바른 취급 |
|------|-----------|
| 사용자 주장 ("배포 후 문제 시작됨") | 가설: "배포가 문제를 일으켰다" |
| 에러 메시지 | 에러는 증상; 원인은 가설 |
| 외부 문서 | 문서는 의도된 동작; 실제 동작은 다를 수 있음 |
| 에이전트 분석 | 이 스킬의 분석도 반증 대상 가설 |
| 실험 결과 해석 | 관찰은 사실; 그 의미는 가설 |

---

## 관찰 vs 해석 분리

항상 명확히 구분한다:

- **관찰**: 원시 데이터, 정확한 출력, 문자 그대로의 로그 메시지, 측정값
- **해석**: 관찰의 의미, 가능한 원인, 추론된 관계

이 둘을 섞지 말고 별도 레이블 섹션으로 표시한다.

---

## 출력 형식

```
## Investigation: {제목}
**Type**: {bug | performance | architecture | verification | interpretation}
**Confidence**: {speculation | low | medium | high}
**Date**: {날짜}

### 1. Observations
{원시 관찰, 해석과 분리}

### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | {설명} | {active | eliminated | supported} | {횟수} |
| H2 | {설명} | {active | eliminated | supported} | {횟수} |

### 3. Experiments
#### Experiment {N}: {설명}
- **Target Hypothesis**: H{n}
- **Falsification Prediction**: H{n}이 틀렸다면 {X}를 관찰해야 한다
- **Actual Result**: {실제 발생한 것}
- **Verdict**: {supports | eliminates | inconclusive} H{n}

### 4. Conclusion
**Supported Hypothesis**: H{n} — {설명}
**Confidence**: {수준} ({이유})
**Recommended Action**: {신뢰도에 따른 행동}

### 5. Remaining Uncertainty
{아직 모르는 것; 결론을 바꿀 수 있는 것}
```

`--save <path>` 지정 시 이 형식으로 파일에 저장한다.

---

## 안티패턴 목록

### Step 1 (Observe)
- [X] "시스템이 느려졌다" → [O] "API p95 지연시간이 배포 전 200ms → 배포 후 3200ms"
- [X] 사용자 주장을 관찰로 기록 → [O] 주장을 인용하고 검증 대상으로 표시

### Step 2 (Hypothesize)
- [X] 가능성이 낮다고 즉시 제거 → [O] 반증 증거 없이는 유지
- [X] 단일 가설만 추구 → [O] 항상 최소 2개 유지

### Step 3 (Predict)
- [X] 확증 예측만 ("H1이 맞다면 X") → [O] 반증 예측 필수 ("H1이 틀렸다면 Y")

### Step 4 (Experiment)
- [X] 여러 변수를 동시에 변경 → [O] 한 번에 하나씩
- [X] 가설을 확인하려는 실험 → [O] 가설을 반증하려는 실험

### Step 5 (Analyze)
- [X] "충분히 가깝다"로 지지 선언 → [O] 명확히 일치해야 supported
- [X] 제거된 가설에 결과 끼워맞춤 → [O] 중간 피벗 절차 수행

### Step 6 (Conclude)
- [X] 1회 실험 후 "high confidence" 주장 → [O] 3회 이상 통과 + 모든 경쟁 가설 제거 필요
- [X] 남아있는 불확실성 생략 → [O] Remaining Uncertainty 섹션 필수

---

## 약식 예시: verify — 법률 조항 적용 여부 (비코딩 도메인)

> bug는 경량/완전/패턴C, perf는 패턴A, arch는 패턴B 참조

**요청**: "개인정보보호법 제15조가 우리 서비스의 쿠키 수집에 적용되는지 확인해줘"

```
## Investigation: 개인정보보호법 제15조 적용 여부
**Type**: verification | **Confidence**: medium | **Date**: 2026-04-04
### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | 제15조 동의 의무가 쿠키에 직접 적용 | eliminated | 1 |
| H2 | 쿠키는 "수집 수단"으로 정보통신망법 우선 적용 | supported | 2 |
| H3 | 쿠키에 식별정보 포함 시 제15조 적용 (조건부) | supported | 1 |
### 3. Experiments
- **Experiment 1**: 제15조 "개인정보" 정의와 쿠키 대조
- **Falsification Prediction**: H1이 틀렸다면 쿠키 자체는 "개인정보"에 해당하지 않아야 함
- **Actual Result**: 제2조 — 세션 쿠키는 비해당, 이메일 포함 쿠키는 해당
- **Verdict**: eliminates H1, supports H3
### 4. Conclusion
**Confidence**: medium — 쿠키 종류에 따라 적용 법률이 다름. 법률 자문 권장
```

## 약식 예시: interpret — 메트릭 급등 해석

**요청**: "대시보드에서 API 요청 수가 갑자기 10배 늘었는데 뭘 의미하지?"

```
## Investigation: API 요청 수 10배 급증 원인
**Type**: interpretation | **Confidence**: high | **Date**: 2026-04-04
### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | 실제 사용자 트래픽 급증 | eliminated | 1 |
| H2 | 외부 크롤러/봇 대량 요청 | supported | 3 |
| H3 | 모니터링 집계 오류 | eliminated | 1 |
### 3. Experiments
- **Experiment 1**: 급증 시간대 User-Agent 분포 확인
- **Falsification Prediction**: H2가 틀렸다면 상위 UA가 모두 일반 브라우저여야 함
- **Actual Result**: 요청 87%가 `Googlebot/2.1`
- **Verdict**: supports H2, eliminates H1
### 4. Conclusion
**Confidence**: high (3회 반증 통과, H1·H3 제거)
**Recommended Action**: robots.txt 크롤링 제한, 봇 트래픽 대시보드 분리
```

---

## 예시 (경량 모드)

**요청**: "이 ImportError 원인 찾아줘" (명확한 스택 트레이스 제공)

```
## Investigation: ImportError in data_processor.py
**Type**: bug | **Confidence**: medium | **Date**: 2026-04-03

### 1. Observations
- data_processor.py:15에서 `ImportError: cannot import name 'parse_json' from 'utils'`
- utils.py가 존재함 (Glob으로 확인)
- 최근 git 커밋 2개: "refactor utils.py" (2시간 전)

### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | refactor에서 parse_json이 삭제/리네임됨 | supported | 2 |
| H2 | import 경로가 변경됨 | eliminated | 1 |

### 3. Experiments
#### Experiment 1: utils.py에서 parse_json 함수 검색
- **Falsification Prediction**: H1이 틀렸다면 utils.py에 parse_json이 있어야 함
- **Actual Result**: Grep 결과 — utils.py에 parse_json 없음. parse_json → parse_json_v2로 리네임됨
- **Verdict**: supports H1, eliminates H2

#### Experiment 2: git log로 리네임 확인
- **Falsification Prediction**: H1이 틀렸다면 git log에 parse_json 변경 없어야 함
- **Actual Result**: "refactor: rename parse_json to parse_json_v2" 커밋 확인
- **Verdict**: supports H1

### 4. Conclusion
**Supported Hypothesis**: H1 — refactor에서 parse_json이 parse_json_v2로 리네임됨
**Confidence**: medium (2회 반증 통과, H2 제거)
**Recommended Action**: data_processor.py의 import를 parse_json_v2로 업데이트

### 5. Remaining Uncertainty
- parse_json_v2의 시그니처가 변경됐는지 확인 필요
- 다른 파일에서도 parse_json을 사용하는지 Grep으로 확인 권장
```

---

## 예시 (완전 모드)

**요청**: "간헐적으로 500 에러 발생, 재현 방법 모름"

→ 완전 모드 활성화: 재현 없음, 간헐적, 환경 의존적

```
## Investigation: 간헐적 500 에러 원인 분석
**Type**: bug | **Confidence**: medium | **Date**: 2026-04-03

### 1. Observations
- 프로덕션 로그에서 500 에러 발생 빈도: 분당 0~5회 (불규칙)
- 에러 발생 시 스택 트레이스: `ConnectionPoolTimeoutError` (DB 연결 풀)
- 에러 미발생 시에도 DB 응답시간 p99 800ms (정상 p99: 50ms)
- 최근 배포 없음 (5일 전이 마지막)
- 트래픽 패턴: 피크 시간대(오전 10-11시)와 에러 빈도 상관 있음

### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | DB 연결 풀 고갈 (동시 요청 급증 시) | supported | 3 |
| H2 | 외부 결제 API 타임아웃 전파 | eliminated | 2 |
| H3 | 특정 쿼리의 락 경쟁 (Lock Contention) | inconclusive | 1 |

### 3. Experiments

#### Experiment 1: 에러 발생 시점 DB 연결 수 확인
- **Falsification Prediction**: H1이 틀렸다면 에러 발생 시 DB 연결 수가 풀 상한(20)보다 낮아야 함
- **Actual Result**: 에러 발생 시점 DB 연결 수 20/20 (풀 포화)
- **Verdict**: supports H1

#### Experiment 2: 결제 API 응답시간과 에러 상관관계 확인
- **Falsification Prediction**: H2가 틀렸다면 결제 API 타임아웃 로그와 500 에러 발생 시각이 불일치해야 함
- **Actual Result**: 결제 API 로그에 타임아웃 없음. 에러 발생과 무관
- **Verdict**: eliminates H2

#### Experiment 3: 피크 시간대 slow query 로그 확인
- **Falsification Prediction**: H3이 틀렸다면 slow query 로그가 에러 발생 시점과 무관해야 함
- **Actual Result**: slow query 로그 있으나 에러와 일부만 겹침 (인과관계 불명확)
- **Verdict**: inconclusive H3

... (H1 추가 반증 2회: 연결 풀 크기 임시 확대 후 에러율 70% 감소 확인)

### 4. Conclusion
**Supported Hypothesis**: H1 — 피크 트래픽 시 DB 연결 풀 고갈로 500 에러 발생
**Confidence**: medium (3회 반증 통과, H2 제거, H3 미결)
**Recommended Action**: DB 연결 풀 크기 20 → 50 상향, 피크 시간대 연결 수 모니터링 알럿 추가

### 5. Remaining Uncertainty
- H3(락 경쟁)가 H1과 복합 원인인지 미확인 — slow query 원인 별도 조사 권장
- 연결 풀 확대 후 DB 서버 자체 부하가 새 병목이 될 가능성
- 근본 원인이 특정 엔드포인트의 DB 연결 누수일 가능성 배제 안 됨
```

---

## 핵심 패턴 예시

> 아래 3가지는 이 스킬이 기존 추론 습관과 **다르게 동작해야 하는 핵심 상황**이다.

### 패턴 A: 반증 우선 — 첫 가설 탈락

**요청**: "CI 빌드가 2배 느려졌어, 어제 의존성 추가한 게 원인인 것 같아"

```
## Investigation: CI 빌드 시간 2배 증가
**Type**: performance | **Confidence**: medium | **Date**: 2026-04-04
### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | 새 의존성의 설치 시간이 빌드를 지연 | eliminated | 1 |
| H2 | 새 테스트에 sleep/느린 I/O 포함 | supported | 2 |
| H3 | CI 러너 자체의 성능 저하 | eliminated | 1 |
### 3. Experiments
- **Experiment 1**: 빌드 vs 테스트 단계 시간 분리
- **Falsification Prediction**: H1이 틀렸다면 빌드 단계 시간이 증가하지 않았어야 함
- **Actual Result**: 빌드 2분→2분(동일), 테스트 2분→6분 → **eliminates H1**
- **Experiment 2**: 새 테스트 실행 시간 측정
- **Falsification Prediction**: H2가 틀렸다면 새 테스트 총 시간이 1분 미만이어야 함
- **Actual Result**: test_export.py 3.5분 (time.sleep(180)) → **supports H2**
### 4. Conclusion
**Confidence**: medium (2회 반증 통과, H1·H3 제거) — sleep을 mock으로 교체 권장
### 5. Remaining Uncertainty
- sleep 외 추가 I/O 대기 여부 미확인
```

**교훈**: 사용자가 의존성을 지목했지만 첫 반증에서 즉시 탈락. 반증이 조사 방향을 바꿨다.

### 패턴 B: 결론 보류 — 불확실성 인정

**요청**: "이 모놀리스를 마이크로서비스로 분리하는 게 맞을까?"

```
## Investigation: 모놀리스 → 마이크로서비스 전환 적합성
**Type**: architecture | **Confidence**: low | **Date**: 2026-04-04
### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | MSA 분리가 배포 독립성과 장애 격리를 개선 | inconclusive | 1 |
| H2 | 3명 팀에서 MSA 운영 오버헤드가 이점 상쇄 | inconclusive | 1 |
### 3. Experiments
- **Experiment 1**: 모듈 간 결합도 측정
- **Falsification Prediction**: H1이 틀렸다면 공유 DB 테이블이 많아 분리 불가능해야 함
- **Actual Result**: 2개 모듈이 6개 테이블 공유. 분리 가능하나 동기화 복잡 → **inconclusive H1**
- **Experiment 2**: 팀 규모 대비 운영 부담 추정
- **Falsification Prediction**: H2가 틀렸다면 3명/4서비스 성공 사례가 있어야 함
- **Actual Result**: 사례 확인 불가, 판단 근거 부족 → **inconclusive H2**
### 4. Conclusion
**Confidence**: low — 결론 보류. 배포 빈도 요구, 팀 확장 계획 확인 후 재조사
### 5. Remaining Uncertainty
- 비즈니스 요구(배포 빈도 증가) 여부에 따라 결론 변동 가능
```

**교훈**: 불확실하면 억지로 결론을 내지 않는다. `low`는 실패가 아니라 정직한 판단이다.

### 패턴 C: 사용자 오진 교정

**요청**: "어제 배포 후에 결제 실패가 발생하기 시작했어"

```
## Investigation: 배포 후 결제 실패 발생
**Type**: bug | **Confidence**: high | **Date**: 2026-04-04
### 1. Observations
- 결제 실패율 0%→12% (어제 15시~). 배포: 14시. 에러: `PaymentGatewayTimeout`
- 배포 diff: admin UI만 수정 (결제 로직 변경 없음) ← 사용자 주장 "배포 때문"은 **가설**
### 2. Hypotheses
| # | Hypothesis | Status | Falsification Attempts |
|---|-----------|--------|----------------------|
| H1 | 배포가 결제 실패 유발 (사용자 주장) | eliminated | 2 |
| H2 | 외부 PG사 API 장애 | supported | 3 |
| H3 | 네트워크 인프라 변경 | eliminated | 1 |
### 3. Experiments
- **Experiment 1**: 배포 diff 결제 코드 확인
- H1 반증: 결제 파일 변경 0건 → **eliminates H1**
- **Experiment 2**: 에러 시작 시각 대조
- H1 반증: 에러 14:30 시작, 배포 14:00 — 30분 차이 → **eliminates H1, supports H2**
- **Experiment 3**: PG사 API 응답시간
- H2 반증: p95 200ms→8초, PG사 공지 "14:25 서버 점검" → **supports H2**
### 4. Conclusion
**Confidence**: high (3회 반증 통과, H1·H3 제거) — PG사 점검 종료 확인 후 모니터링
### 5. Remaining Uncertainty
- PG사 점검 완료 여부 실시간 확인 필요
```

**교훈**: "배포 후 발생" ≠ "배포가 원인". 시간적 상관관계를 인과관계로 단정하지 않는다.
