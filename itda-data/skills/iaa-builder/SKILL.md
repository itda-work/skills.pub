---
name: iaa-builder
description: >
  CS 분류 라벨의 어노테이터 간 일치도(IAA)를 Cohen·Fleiss κ로 측정하는 스킬입니다.
  "이 라벨링 일치도 재줘", "Cohen 카파 계산", "골드셋 만들어줘", "이 분류 운영에 써도 돼?"처럼 말하면 됩니다.
  골드셋 샘플링 → 2인 독립 라벨 → κ 산출 → 졸업 게이트 판정. aspect-sentiment·cs-intent의 운영 졸업 선행 관문.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[어노테이션 시트 CSV 또는 CS 로그 + n]"
metadata:
  author: "Chinseok"
  version: "0.1.3"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-05-31"
  updated_at: "2026-07-26"
  tags: "iaa, kappa, cohen, fleiss, agreement, korean, stdlib"
---

# iaa-builder

> CS 분류축(`aspect-sentiment` 측면, `cs-intent` 인텐트)을 **운영에 쓸 수 있는지 측정**하는 인프라 스킬입니다.
> "이 카테고리가 사람마다 일관되게 라벨되는가"를 **Cohen/Fleiss κ로 수치화**합니다. 측정 없는 분류축은 검증 불가능한 라벨만 쌓는 *벽장 안전망*입니다.

CS 라벨링의 **어노테이터 간 일치도(Inter-Annotator Agreement)**를 측정합니다. κ 계산은 `scripts/iaa.py`가 **결정론적으로 수행**합니다(Claude의 추정값이 아니라 실제 통계 연산).

> 설계 원천: `aspect-sentiment`·`cs-intent` SKILL.md의 "운영 졸업 IAA 측정" 게이트가 측정 수단 없이 문서로만 존재 → 이 스킬이 게이트를 실행 가능하게 만든다(itda-skills #28·#30).

---

## 핵심 원칙

1. **결정론 코어** — κ는 `scripts/iaa.py`가 계산. 손계산 검증된 공식(Cohen·Fleiss). LLM 추정 금지.
2. **측정이 게이트** — κ가 합격선(**기본 0.61 = Landis-Koch substantial 하한**) 미만이면 운영 졸업 보류. κ=0.60은 'moderate'(재측정 권고 등급)이라 졸업 미달.
3. **합격선이 아니라 정의를 고친다** — κ가 낮은 카테고리는 *정의*를 보강하고 재라벨(라벨러 탓 금지).
4. **2인 이상 독립 라벨** — 같은 골드셋을 2명+가 서로 모르게 라벨해야 일치도가 의미를 가짐.
5. **stdlib only** — 외부 의존 없음. 고정 출력 계약(`references/output-schema.json`).

> `per_category_kappa`·`ambiguous_categories`는 **2인(Cohen) 경로 한정**이다. 3인+(Fleiss)에서는 카테고리별 분해를 산출하지 않아 `ambiguous_categories`가 빈 배열이다.

## Claude 라우팅 가이드

아래 모든 스크립트 실행에 앞서 `SKILL_DIR` 을 한 번 확정한다:
```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/iaa-builder}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/iaa-builder' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\iaa-builder"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

### A. 골드셋이 아직 없다 → 샘플링부터
**본문(text)을 가진 원본 CS 로그**(JSONL/CSV)에서 어노테이션 시트(라벨 빈칸 CSV)를 만든다:
```bash
python3 "$SKILL_DIR/scripts/sample.py" <원본로그.jsonl> 200 --text text --id doc_id --stratify primary_intent
```
- `--stratify`로 분류값(예: cs-intent의 `primary_intent`)별 비례 배분 → 대표성 확보.
- 출력 `annotation_sheet.csv`를 **2명+가 독립적으로** 라벨 컬럼(`annotator_1`, `annotator_2`)에 채운다.
- ⚠️ **cs-intent 출력을 직접 넣지 말 것**: cs-intent 출력 스키마는 본문(`text`)을 포함하지 않는다(`additionalProperties:false`). 그대로 넣으면 시트의 text 컬럼이 비어 라벨링이 불가하다(sample.py가 경고). → 원본 로그에 cs-intent의 `primary_intent`를 join하거나, `--text evidence`(원문 인용 발췌)로 측정한다.

### B. 라벨이 채워진 시트가 있다 → κ 측정
```bash
python3 "$SKILL_DIR/scripts/iaa.py" annotation_sheet.csv 0.61
```
- 2인 → Cohen's κ + 카테고리별 κ + 불일치 목록. 3인+ → Fleiss' κ.
- 출력 JSON의 `graduation.passed`·`ambiguous_categories`·`disagreements`를 사용자에게 해석해 전달.
- 등급 기준: `references/interpretation.md` (Landis-Koch).

### C. 결과 해석
- `passed=false`면 `ambiguous_categories`(κ 낮은 카테고리)의 정의 보강을 권한다.
- `disagreements`의 실제 불일치 사례로 경계 규칙을 다듬는다.

> 측면/인텐트 분류 자체는 `aspect-sentiment`·`cs-intent`의 일. 이 스킬은 그 출력의 **신뢰성을 측정**한다.

## 출력 예시

```json
{
  "schema_version": "1.0",
  "method": "cohen_kappa",
  "n_items": 200,
  "n_annotators": 2,
  "overall_kappa": 0.713,
  "interpretation": "substantial",
  "po": 0.85, "pe": 0.48,
  "per_category_kappa": {"배송": 0.82, "환불보상": 0.55, "반품교환": 0.58},
  "ambiguous_categories": ["환불보상", "반품교환"],
  "disagreements": [{"item_id": "tk_0007", "labels": ["환불보상", "반품교환"]}],
  "graduation": {"threshold": 0.61, "passed": true, "note": "..."}
}
```

## 검증

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/validate_output.py" <report.json>
# Windows
py -3 "$env:SKILL_DIR\scripts\validate_output.py" <report.json>
```

## 한계 (정직)

- κ는 **명목 단일 라벨** 기준. 다중 라벨(secondary_intents)은 primary만 또는 라벨별 이진 κ로 분해.
- prevalence/bias paradox: 한 카테고리가 압도적이면 κ가 낮게 나올 수 있음(`po`·`pe` 병기).
- κ가 높아도 골드셋 대표성이 무너지면 운영 일반화는 별도 확인 필요.
