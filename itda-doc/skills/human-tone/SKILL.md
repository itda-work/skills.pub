---
name: human-tone
description: >
  이미 작성된 한국어 사무 글(보고서·메일·기획서·공지)에서 AI 흔적을 걷어내는 후처리 스킬입니다.
  "이 보고서 AI 같아", "메일 너무 딱딱해", "사람이 쓴 것처럼 고쳐줘"처럼 말하면 됩니다.
  숫자·고유명사·서명은 잠금 가드로 보존합니다.
  [책임 경계] 본 스킬은 완성된 글의 후처리 검수 전담(AI 흔적 사전 가드 정본) — itda-doc:draft-post 는 처음부터 초안을 쓰는 생성 단계이며, 같은 글에 두 스킬을 겹쳐 적용하지 않습니다.
license: Apache-2.0
compatibility: "Claude Code & Cowork"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, mcp__workspace__bash
argument-hint: "<text-or-file> [--scene report|email|proposal|notice] [--register formal|semi|casual] [--strict] [--diff]"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  version: "2.1.2"
  category: "writing"
  created_at: "2026-05-11"
  updated_at: "2026-09-25"
  tags: "ai slop, humanize, human tone, post-processing, deslop, naturalize, korean writing, translationese, post-editese"
---

# human-tone

이미 작성된 텍스트에서 AI가 남긴 흔적을 걷어내고 사람의 호흡으로 다시 흐르게 합니다. **결정적 메트릭 + 사전 + 보존 잠금 가드를 갖춘 풀패키지 후처리 검수 스킬**입니다.

> 직장인의 마지막 한 줄 — 송부 직전, 보고 직전, 발송 직전에 한 번 돌리는 후처리 게이트.

## v2.0 주요 변경 (v1.0 → v2.0)

v1.0은 LLM 사전 지식에 기댄 휴리스틱 15개로 구성됐던 반면, v2.0은 [`epoko77-ai/im-not-ai`](https://github.com/epoko77-ai/im-not-ai) v1.6.1 (MIT, ⭐937 stars) 의 풀 시스템을 차용해 결정적 자산을 갖췄습니다. 차용 자산과 변경 사항은 [README.md](./README.md) 의 "차용 출처" 섹션 참조.

- `references/ai-tell-taxonomy.md` — 10대 분류 × 40+ 패턴 SSOT (한국 번역학계 8유형 + 국제 이론 3대축 학술 근거)
- `references/quick-rules.md` — Monolith Fast Path용 압축 매칭 룰
- `references/rewriting-playbook.md` — 카테고리별 치환 레시피 + 4장르 처리
- `scripts/metrics.py` + `scripts/baseline.json` — 22지표 결정적 측정 (KatFish 베이스라인, 표준 라이브러리만)
- `scripts/lock_preserved.py` — 보존 영역 placeholder 마스킹 가드 (자체 작성)
- `scripts/verify_gates.py` — 윤문 사후 결정적 판정 게이트 4축 (v2.1, #1619 — P0 변경률·P1 목표 달성/과교정·P2 수사 전멸·P3 보존 불변식, exit 0/1/2/3)
- `references/empirical-validation.md` — 상류 대조 코퍼스(G²) 반증 요약 (v2.1 — A-2 S2 강등·I-1 조건부·A-16 번역 맥락 한정의 근거)
- 직장인 사무 도메인 **K 카테고리 5종** 자체 신설 (taxonomy/quick-rules/playbook 모두 K 부록 포함)

## 4대 철칙 (Prime Directives)

ref-im-not-ai에서 차용. 직장인 도메인은 오히려 더 엄격하게 적용합니다.

1. **의미 불변 (Fidelity First)** — 사실·주장·수치·고유명사·인용·서명은 100% 원문 보존. `lock_preserved.py`로 사전 잠금.
2. **근거 기반 (Span-Grounded)** — 모든 변경은 탐지된 패턴에 연결. 탐지 없는 구간은 건드리지 않음.
3. **장르 유지 (Tone Match)** — 보고서를 에세이로, 이메일을 광고 카피로 옮기지 않음. `--scene` 자동·수동 지정.
4. **과윤문 금지 (No Over-Polish)** — 변경률 30% 초과 시 경고, 50% 이상 시 강제 중단. `verify_gates.py` 가 결정적으로 판정한다(v2.1 부터 문서 규율이 아니라 스크립트 판정). **정상 한국어를 지우는 것도 과윤문이다** — `~를 통해` 1~2회·`것이다` 단발·자생 산문의 `그는` 은 보존 대상(상류 반증, `references/empirical-validation.md`).

## 이 스킬을 쓰지 않을 때

| 상황 | 대신 쓸 스킬 |
|---|---|
| 처음부터 글을 써야 할 때 | itda-doc:draft-post |
| 제품 카피·브랜드 슬로건(의도된 기교) | itda-doc:draft-post `--style copy` |
| 코드·JSON/CSV·로그·표·통계 | 적용 제외 — 아래 Do-NOT List |
| 주장·수치의 출처가 맞는지 검증 | itda-research:ground-check |
| 영업기밀·개인정보 마스킹 | itda-data:biz-redact |

**가드 정본**: AI 흔적 사전은 본 스킬 `references/ai-tell-taxonomy.md` 가 정본이다(상류 G² 반증 반영, #1619). `draft-post` 의 `references/_anti-ai-korean.md` 는 이를 따르는 생성 단계 사전 가드 — 정본이 바뀌면 그쪽을 맞춘다(#1620).

## Arguments

- `<text-or-file>` (필수): 다듬을 텍스트 또는 파일 경로 (`.md`, `.txt`, 표준 입력)
- `--scene` (선택): `report` / `email` / `proposal` / `notice`. 미지정 시 도메인 자동 분류 보조 신호로 추정 (quick-rules.md 하단 표 참조)
- `--register` (선택): `formal` / `semi` / `casual`. 미지정 시 다수 어미로 자동 감지
- `--strict` (선택): Fast Path를 건너뛰고 Strict 5단계 (탐지 → 윤문 → 보존 감사 → 자연도 재측정 → 종합 판정) 실행. 8,000자 초과 시 자동 활성화
- `--diff` (선택): 변경 라인만 GitHub diff 스타일로 출력. 보고 라인 공유용

## 워크플로우 (Monolith Fast Path)

기본은 단일 호출 fast path입니다. ≤5,000자 텍스트는 다음 6단계를 한 번의 검수로 처리합니다(마지막 6단계가 결정적 판정 게이트).

### 0단계 — 스킬 디렉토리 확정

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/human-tone}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/human-tone' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

### 1단계 — 보존 영역 잠금 (결정적)

```bash
python3 "$SKILL_DIR/scripts/lock_preserved.py" mask <input.txt> > _workspace/01_masked.txt
```

`lock_preserved.py`가 다음을 placeholder(`⟦KEEP0001⟧` 형식)로 치환합니다:
- URL · 이메일 · 전화 · 날짜 · 시간
- 큰따옴표 인용 · 법조항 (`제17조 제2항`)
- 통화/금액 · 퍼센트 · 일반 숫자
- (수동 보존이 필요한 고유명사는 `--mask-extra` 옵션으로 추가 — 차기 확장)

이 단계는 LLM 의존 없이 정규식으로 100% 결정적. 환각 방지 1차 가드.

### 2단계 — 도메인 자동 분류 + 패턴 진단

`references/quick-rules.md` 하단 표의 보조 신호로 `--scene` 자동 추정 (제목·헤더·수치 비율·글머리 기호 비율). 이후 해당 scene의 카테고리 우선순위로 진단:

- **report (보고서)**: K-1 → I → A-7 → E → D
- **email (이메일)**: K-2 → B → G → 호칭/서명 보존
- **proposal (기획서)**: K-3 → C → F → J
- **notice (공지)**: K-4 → C-2 → I-4 → E-7

전체 분류 체계는 `references/ai-tell-taxonomy.md` 참조 (A 번역투 19개 + B 영어 인용 4 + C 구조 12 + D 관용구 7 + E 리듬 7 + F 수식 5 + G Hedging 3 + H 접속사 4 + I 형식명사 6 + J 시각 장식 4 + **K 직장인 5**).

### 3단계 — 인간화 재작성 (수술적)

`references/rewriting-playbook.md`의 카테고리별 치환 레시피를 따릅니다. 직장인 시나리오 4종의 Before/After 사례는 §6 참조. 우선순위:

1. **숫자 회복** — 추상 표현을 입력 텍스트의 숫자·사실로 되돌림 (없으면 `[?]`로 표시)
2. **주어 복원** — 수동·피동 제거, 주체(팀·부서·시스템) 명시
3. **결론 선두 배치** — 첫 두 문장이 배경 설명이면 결론·요청을 맨 앞으로
4. **어미 단조 해소** — 같은 어미 4회+ 시 1회만 변형
5. **잉여 전환어 컷** — `또한`/`더불어`/`한편` 단락 첫머리 반복분 1~2개 제거

### 4단계 — 결정적 측정 (metrics 진단)

```bash
# 빠른 위험도 한 줄 (stdout: low/medium/high)
python3 "$SKILL_DIR/scripts/metrics.py" --input _workspace/03_rewrite.md --baseline "$SKILL_DIR/scripts/baseline.json" --genre <scene>

# 진단 JSON 상세 (5단계 audit·report 블록 생성용)
python3 "$SKILL_DIR/scripts/metrics.py" --input _workspace/03_rewrite.md --baseline "$SKILL_DIR/scripts/baseline.json" --genre <scene> --output _workspace/04_metrics.json
```

`metrics.py`가 22개 지표(쉼표 분포, 종결어미 다양성, 한자어 명사화 밀도, 어휘 다양성 등)를 z-score로 측정해 risk_band(low/medium/high) + 등급(A/B/C/D)을 산출합니다. 베이스라인은 KatFish (인간 470편 / AI 1624편).

`--output`을 지정하면 risk_band·risk_score·z_scores·lexicon_hits·evidence_spans 등 상세 진단을 JSON으로 기록합니다. 5단계의 의미 동등성 audit 블록은 이 JSON을 읽어 생성합니다.

변경률 가드는 6단계의 `verify_gates.py` 가 판정한다(문서 규율 아님). 여기서는 metrics 진단만 기록한다.

### 5단계 — 보존 영역 복원 + 13항 의미 동등성 audit

```bash
python3 "$SKILL_DIR/scripts/lock_preserved.py" restore <rewritten.txt> _workspace/preserve_map.json > _workspace/05_final.txt
python3 "$SKILL_DIR/scripts/lock_preserved.py" audit <input.txt> _workspace/05_final.txt _workspace/preserve_map.json
```

복원 단계에서 placeholder 1:1 복원 + 환각 감사(원본에 없는 숫자가 복원본에 새로 등장하면 fail). 그 후 다음 13항을 통과해야 최종 승인:

1. 고유명사 (인명·지명·제품명·모델명)
2. 수치·단위
3. 날짜·시간
4. 직접 인용 (큰따옴표 내부)
5. 법률·규정 조문
6. 수식·공식
7. 주장·결론 방향 (긍정↔부정 전환 금지)
8. 인과관계 (A→B가 B→A로 역전 금지)
9. 주어 변경 시 의미 유지
10. 양화·한정 (모든/대부분 층위 보존)
11. 극성 (이중부정 단순화 시 극성 유지)
12. 순서 (시간순·중요도순 의미 보존)
13. 누락·첨가 금지

13항 중 1건이라도 fail이면 자동 롤백. 보고서·기획서는 모든 항목 100% 유효, 이메일은 9·10·11항 특히 중요.

### 6단계 — 사후 판정 게이트 (결정적, 마지막 단계)

```bash
python3 "$SKILL_DIR/scripts/verify_gates.py" --before <input.txt> --after _workspace/05_final.txt --scene <scene>
# JSON 이 필요하면 --json. exit: 0 PASS / 1 FAIL / 2 INCONCLUSIVE / 3 입력 오류
```

`verify_gates.py` 는 before/after 를 같은 기준으로 정규화(공백·따옴표·대시·NFC)한 뒤 4축을 판정한다:

| 축 | 판정 | 실패 시 |
|---|---|---|
| P0 문자 변경률 | >30% WARN, ≥50% ABORT(`rollback: true`). 카피 씬은 면제 | ABORT 면 마지막 안정 버전으로 롤백, WARN 이면 변경을 탐지 근거와 대조 |
| P1 목표 달성/과교정 | 윤문 전 z>2.0 이던 쉼표 지표가 z≤1.0 으로 들어왔는가 · **A-2·I-1·A-16 의 정상 사용을 0 으로 지웠는가** | 미달이면 남은 S1 을 처리, 과교정이면 지운 것을 되살린다 |
| P2 수사 전멸 | 대구·부정 대조·문두 반복이 before ≥3 인데 after 0 | 하나는 살리고 나머지를 비대칭으로 |
| P3 보존 불변식 | `lock_preserved` 토큰 전부 잔존 + 원문에 없던 숫자 0 | 롤백 후 재윤문 |

**exit 2(INCONCLUSIVE)는 PASS 가 아니다** — 문장 10개 미만이거나 baseline 을 못 읽어 P1 z 를 재지 못한 것이다. 그 경우 P0·P2·P3 결과와 13항 audit 으로 판정하고, 출력의 진단 블록에 "게이트: INCONCLUSIVE(표본 짧음)" 을 명시한다. exit 1 은 축별 `status` 를 읽어 롤백(ABORT)과 보완(WARN·FAIL)을 가른다. exit 3 은 게이트를 건너뛴 것이므로 입력을 고쳐 다시 돌린다.

## 출력 형식

`--diff` 미지정 시 다음 3블록:

```markdown
### 진단
씬: report (자동 감지)  /  등급: B → A
주요 패턴 (카테고리 / severity / 횟수):
  - K-1 보고서식 군더더기 / S2 / 4건
  - I-3 형식명사 과다 / S2 / 3건
  - A-8 이중 피동 / S1 / 1건
  - E-2 어미 단조(됩니다 ×7) / S2 / 1건
보존 잠금: 숫자 12개 · 고유명사 5개 · 결재선 1블록
변경률: 22% (정상)
의미 동등성: 13/13 통과
게이트: PASS (P0 22% · P1 달성/과교정 0 · P2 수사 3→2 · P3 이상 없음)

### 다듬은 텍스트
(전체 본문)

### 변경 노트
- [본론 서두] "전반적으로 양상을 띠고 있습니다" → "주간 거래량이 18% 줄었습니다" (K-1)
- [3페이지 1단락] 수동태 6건 → 기획팀 주어로 능동 전환 (A-7)
- [확인 요청 단락] "확인 부탁드립니다" 4회 → 1회 + 항목 번호 3개 (K-2b)
```

`--diff` 지정 시: 변경 라인만 GitHub diff 스타일.

## 적용 제외 (Do-NOT List)

- 코드 (프로그래밍 언어 소스)
- JSON/YAML/CSV 데이터, 로그
- 차트·표·통계 (시각화 자료)
- 제품 카피·브랜드 슬로건 (의도된 기교를 AI 패턴으로 오인할 위험 — `itda-draft-post --style copy` 사용)
- 시·소설·창작물

## 권장 체인

```
draft-post → human-tone               (사내 초안 → 송부 직전 검수)
[외부 AI 초안] → human-tone           (Cowork·ChatGPT 결과물 후처리)
blog-seo → draft-post → human-tone    (네이버 블로그 발행 풀체인)
```

`draft-post`와 같은 글에 겹쳐 적용하지 않습니다 — 생성 단계 가드(draft-post)와 후처리 검수(본 스킬, 가드 정본)의 역할 분담이며, 두 번 돌리면 의도된 직장인 화법(예: 결재 표현)이 과도하게 평준화됩니다.

## 관련 스킬

- `itda-doc:draft-post` — 초안 생성 단계 가드(사전 정본은 본 스킬)
- `itda-doc:blog-seo` — 키워드 → 초안 → 검수 풀체인의 맨 앞
- `itda-work:email` — 검수된 메일을 SMTP로 송부

## 차기 확장

- `--profile <path>` 옵션 — itda-org-tone (별도 신규 스킬) 출력 마크다운 프로필 적용
- `metrics_v2.py` 통합 — post-editese 3축 (simplification/normalisation/interference) 측정 (현재는 v1.6 안정 자산만)
- `scripts/lock_preserved.py --mask-extra` — 사용자 정의 고유명사 사전 추가 잠금

---

**구분점**: 이 스킬은 *생성*이 아닌 *검수*다. 한국 사무환경의 보고·결재·송부 맥락을 알고 있는 후처리 게이트로, 결정적 측정과 보존 가드를 갖춘 풀패키지로 동작한다.
