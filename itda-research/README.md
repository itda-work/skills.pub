# itda-research

검증·업무DB 스킬팩 — 회의 기록을 믿기 전에 근거로 검수하고(meeting-reliability), 사내 비정형 문서 무더기를 업무DB(뇌)로 쌓고 검수한다(brain-*).

> **제거(2026-10-14, 사용자 결정 — 스킬 최소화)**: `ground-check`(1차 출처 강제 검증)·`investigate`(원인 조사)·`market-scan`(시장조사)과
> 에이전트 `ground-verifier`·`deep-researcher` 는 저장소에서 지웠습니다(git 이력에는 남아 있음). 출처 검증·조사·시장조사는 Claude 에게 바로 요청하세요.

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`brain-build`](skills/brain-build/SKILL.md) | 사내 비정형 문서 무더기로 업무DB(뇌)를 구축한다. |
| [`brain-ingest`](skills/brain-ingest/SKILL.md) | 업무DB 에 새 문서를 증분 적재한다. |
| [`brain-audit`](skills/brain-audit/SKILL.md) | 업무DB 를 원본과 대조해 다시 검수한다. |
| [`brain-scribe`](skills/brain-scribe/SKILL.md) | 업무DB 를 근거로 문서를 쓴다. |
| [`brain-fixture`](skills/brain-fixture/SKILL.md) | 업무DB 시험용 결정론 가상 문서 묶음을 만든다. |
| [`meeting-reliability`](skills/meeting-reliability/SKILL.md) | 회의 녹취·기록에서 "확인 / 확인 필요 / 예외"를 근거와 함께 정확히 가르는 신뢰성 검수 스킬입니다. |

에이전트: `brain-auditor`(업무DB 검수) · `meeting-reliability-worker`.

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-research@itda-skills-pub
```

스킬별 사전 준비는 각 `SKILL.md` Prerequisites 절과 `GUIDE.md` 에 있습니다.

## 개발

```bash
just test itda-research          # 저장소 루트
just -f itda-research/justfile test
```

회의·문서·데이터에서 **"확인 / 확인 필요 / 예외"를 근거와 함께 정확히 가르는** 신뢰성 검수 스킬군.
공개 스킬이 "정리"는 넘치게 제공하나 비워 둔 **"신뢰성 검수"**가 차별점이다.

> ⚠️ 이 그룹의 "audit"은 **감사 조직(경영진단·감사)** 도메인이다 — 저장소 루트의
> `STATUS-AUDIT.md`(하드코딩 audit 인프라, 횡단형)와는 **동음이의**다. 본 그룹의 상태는
> `STATUS-AUDIT-RELIABILITY.md`를 본다.

## meeting-reliability 설계 (구 itda-audit 본문)

| 스킬 | 설명 | 상태 |
|---|---|---|
| `meeting-reliability` | 회의 raw 녹취 → 신뢰성 검수 표(근거 tooltip HTML). 코어 5규칙 코드 강제. | v0.1.0 (alpha) |

## 설계

단일 **신뢰성 검수 엔진**(코어 5규칙: 근거 강제·over-hedge 균형·결정/실무 분리·잡담/과정값 제거·선택적 심층검토)을
타깃 비종속으로 두고, 타깃별 어댑터만 바꿔 확장한다. 회의록이 첫 레퍼런스 구현이며,
후속으로 전표·계약 검수 → 통제 테스트 → 감사 컨설팅으로 *대상 치환* 확장한다.

- **표현/검증 분리**: 구조화 JSON 코어(SSoT) → 결정론 verifier(코드 강제) + HTML 렌더러.
- **환각 차단**: 모든 행이 실재 원문 발화를 가리켜야 통과(근거 없는 단정 = FAIL).
- stdlib only · 무키 · Python 3.10+.

근거: SPEC-AUDIT-RELIABILITY-001 · PROPOSAL-AUDIT-RELIABILITY-SKILLS (보관된 `itda-skills/hyve` 저장소 기록 — 이 저장소와 배포본에는 없다)
