---
name: cs-intent
description: >
  한국어 CS 상담·문의 텍스트를 "왜 연락했나"(인텐트/문의유형)로 분류하는 스킬입니다.
  "이 문의 유형 분류해줘", "상담 인텐트 뽑아줘", "문의를 주문/배송/반품으로 나눠줘"처럼 말하면 됩니다.
  측면 감정분석(aspect-sentiment)과 직교합니다 — 무엇에 대해 어떻게 느끼나가 아니라 왜 연락했나. 무상태 단건·closed-set·고정 JSON.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[CS 텍스트/JSONL 또는 분류 요청]"
metadata:
  author: "Chinseok"
  version: "0.1.4"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-05-30"
  updated_at: "2026-07-26"
  tags: "intent, cs, classification, korean, stdlib"
---

# cs-intent

> ⚠️ **개념 증명(PoC) 스킬.** CS 문의를 인텐트(문의유형)로 분류하는 핵심 흐름을 Claude 단독으로 시연합니다.
> 정확도 보장·골드셋 평가는 아직 없습니다. **운영 분류기로 졸업하려면 IAA 측정(소규모 골드셋·2인 이상 라벨러·Cohen κ)이 필수**입니다(측정 없는 분류 = 벽장 안전망) — 같은 플러그인의 `iaa-builder` 스킬로 측정. 결과는 참고용.

한국어 CS 상담·문의 텍스트를 **"왜 연락했나"(인텐트/문의유형)**로 분류합니다.
`aspect-sentiment`(측면-감정)의 **자매 스킬**이며 직교합니다 — 같은 doc에 두 스킬을 병행할 수 있습니다.

> 설계 원천: `aspect-sentiment` 목적-적합성 검토(itda-skills #26 → 자매 분리 #27). 운영 소분류 ~50종이 사실 인텐트축이라는 진단에서 출발.

---

## 핵심 원칙

1. **무상태 단건 처리** — doc(상담 1건/문의 1건)을 독립으로 분류. 판정 간 오염 0.
2. **closed-set 인텐트** — `references/intent-taxonomy.ko.yaml`의 확정 인텐트군만. 매핑 불가 시 `기타`. 사용자 커스텀 YAML 우선.
3. **primary + secondary** — 주 인텐트 1개 + (있으면) 부 인텐트 배열. 한 문의에 의도가 복수면 `flags.multi_intent=true`.
4. **인텐트 ≠ 감정** — "왜 연락했나"만. 측면별 긍·부정은 `aspect-sentiment`의 일. 여기서 감정 라벨 금지.
5. **고정 출력 계약** — `references/output-schema.json`. `evidence`는 원문 인용. 저신뢰는 `flags.low_confidence=true`.

## Claude 라우팅 가이드

사용자가 CS 텍스트를 주면:

1. **인텐트 체계 로드** — `references/intent-taxonomy.ko.yaml`(내장 기본 10군). 사용자 커스텀 우선.
2. **doc별 무상태 분류** — 각 doc을 독립으로, `output-schema.json` 형식 JSON **1개** 출력. 배치면 doc별 반복(섞지 않기).
3. **primary 결정** — 가장 핵심 문의 의도 1개. 부수 의도가 뚜렷하면 `secondary_intents`에 추가 + `flags.multi_intent`.
4. **검증** — `"$SKILL_DIR/scripts/validate_output.py"`(아래 §검증 참조)로 스키마·인텐트 멤버십 검증.

> 측면별 감정이 필요하면 **`aspect-sentiment`를 함께** 쓰세요(직교·병행). 라우팅·SLA·팀 배정은 본 스킬 범위 밖(티켓 라우터 영역).

## 출력 예시

```json
{
  "doc_id": "tk_0001",
  "language": "ko",
  "taxonomy_version": "cs-intent-1.0",
  "domain": "cs",
  "primary_intent": "주문취소변경",
  "secondary_intents": ["배송"],
  "evidence": "바지 2개는 취소해주시고 후드는 언제 오나요",
  "confidence": 0.86,
  "flags": {"multi_intent": true, "low_confidence": false}
}
```

## 검증

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/cs-intent}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/cs-intent' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\cs-intent"  # 미설정이면 SKILL.md 위치 절대경로 사용
```
```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/validate_output.py" <출력.jsonl>
# Windows
py -3 "$env:SKILL_DIR\scripts\validate_output.py" <출력.jsonl>
```

## 대량 배치 (팬아웃/팬인)

입력이 대량(예: 30건 이상)이면 본 대화가 원문으로 오염되고 처리도 느리다. 서브에이전트를 쓸 수 있는 환경(Cowork 등)에서는 **청크 팬아웃**으로 처리한다:

1. **분할** — Lead 가 입력 doc 을 청크 파일(예: 10~20건/청크, **JSONL** — 한 줄 = 단건 입력 shape)로 나눠 세션 폴더에 저장한다. raw 로그는 `itda-data:pii-redact`(다른 팩 — 미설치면 `itda-data` 설치를 안내하고 마스킹 없이 진행하지 않는다) 로 **선행 비식별화**한다.
2. **팬아웃** — `itda-data:cs-batch-extractor` 를 청크별로 **병렬 명시 디스패치**한다(디스패치 프롬프트에 `task=cs-intent` + 이 파일의 closed-set 인텐트 체계·무상태 단건·고정 JSON 원칙 + 청크 파일 경로 + `outputs/` 출력 경로). 워커는 각 항목을 무상태로 분류해 스키마 호환 JSONL 을 `outputs/` 에 쓰고 경로·건수만 반환한다.
3. **팬인(집계는 Lead 소유)** — Lead 가 반환된 JSONL 들을 `python3 "$SKILL_DIR/scripts/validate_output.py" <출력.jsonl> [intent-taxonomy.yaml]` 로 검증하고 병합한다. **커스텀 인텐트 체계를 워커에 줬으면 검증에도 같은 경로를 두 번째 인자로 넘긴다** — 안 넘기면 커스텀 인텐트가 내장 체계 기준으로 거짓 거부·`기타` 오강등된다. 집계는 스킬 스크립트가, 분류는 무상태 워커가 맡는다(워커는 집계하지 않는다).

서브에이전트 부재 환경은 위 절차 대신 **기존 본 컨텍스트 순차 단건 처리로 폴백**한다(핵심 원칙의 doc별 무상태 반복). **단건 절차·출력 스키마·인텐트 체계는 불변** — 배치는 같은 계약을 병렬화·격리할 뿐이다. 오케스트레이션 세부는 `.claude/rules/itda/skills/cowork-agent-orchestration.md`.

## 운영 졸업 게이트 (PoC 탈출 전제)

이 스킬을 시연을 넘어 운영 분류기로 쓰려면 **IAA 측정 절차 선행** — 같은 플러그인의 **`iaa-builder` 스킬**로 실행한다:
- `iaa-builder/scripts/sample.py`로 골드셋(예: 100~200건) 샘플링(`--stratify primary_intent`) → 2인 이상 독립 라벨링.
- `iaa-builder/scripts/iaa.py`로 **Cohen κ** 측정. κ가 낮은 인텐트는 `ambiguous_categories`로 잡히며, 인텐트군 정의를 먼저 보강 후 재라벨(합격선이 아니라 정의를 고친다).
- 측정 절차 없이 인텐트군을 늘리면 검증 불가능한 라벨만 누적된다(벽장 안전망).

## 한계 (정직)

- 정확도 미보장(골드셋·κ 평가 전). 복합·모호 의도는 약함.
- 인텐트군↔운영 소분류 매핑(`legacy_map`)은 P1에서 결정론적으로 확정(여기선 상위 10군만).
- 라우팅·SLA·팀 배정·집계 KPI는 범위 밖(다운스트림).
