---
name: pii-redact
description: >
  한국 CS 상담·문의 텍스트의 개인정보(PII)를 LLM에 넣기 전 결정론 룰로 검출·마스킹하는 스킬입니다.
  "이 상담 로그 비식별화해줘", "개인정보 가려줘", "PII 마스킹", "이거 안전하게 익명화해줘"처럼 말하면 됩니다.
  전화·주민번호·카드·계좌·이메일·주소 등을 플레이스홀더로 치환하고 마스킹 리포트를 남깁니다. 모든 CS 스킬의 안전 입구 전처리.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, Grep, mcp__workspace__bash
argument-hint: "[비식별화할 텍스트 파일 또는 붙여넣은 CS 로그]"
metadata:
  author: "Chinseok"
  version: "0.1.3"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-06-01"
  updated_at: "2026-07-26"
  tags: "pii, redaction, masking, privacy, korean, cs, stdlib"
---

# pii-redact

> raw CS 로그를 Claude나 외부에 붙여넣는 순간 개인정보가 유출됩니다. 이 스킬은 "익명화한다"는 **사람 디스플린**을 **코드 강제력**으로 바꿉니다.
> `aspect-sentiment`·`cs-intent` 등 모든 CS 분석의 **안전 입구 전처리**입니다 — 분석 전에 PII를 먼저 가립니다.

한국 CS 텍스트의 PII를 **결정론적으로 검출·마스킹**합니다. 마스킹은 `scripts/redact.py`가 정규식/룰로 수행합니다(Claude의 판단이 아니라 실제 룰 연산).

---

## 핵심 원칙

1. **결정론 로컬 우선** — raw 텍스트를 **LLM에 먼저 넣지 않는다**. 정규식/룰로 먼저 가린다. (LLM 2차 리뷰는 *이미 마스킹된* 텍스트에만, 옵션·기본 off.)
2. **재현율 우선** — 누락(PII 유출)이 과제거(본문 훼손)보다 위험. 단 마스킹 리포트로 무엇을 몇 건 가렸는지 투명 보고.
3. **체크섬은 필터가 아니라 confidence 태그** — 주민번호 mod11·카드 Luhn 실패해도 마스킹은 하되 confidence를 낮춘다.
4. **플레이스홀더 + 문서 내 일관 가명화** — `[전화_1]` 형식. 같은 문서에서 같은 값은 같은 토큰(무상태).
5. **stdlib only** (`re`/`json`/`sys`/`os`/`argparse`) — 외부 의존 없음. 고정 출력 계약(`references/output-schema.json`).

> 검출 유형: 전화 · 이메일 · 주민등록번호 · 사업자등록번호 · 카드 · 계좌 · 운전면허 · 여권 · 한국 주소.
> 패턴·confidence·과탐 균형의 상세 근거는 `references/patterns.md`.

## Claude 라우팅 가이드

아래 모든 스크립트 실행에 앞서 `SKILL_DIR` 을 한 번 확정한다:
```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/pii-redact}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/pii-redact' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```
```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\pii-redact"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

### A. CS 로그를 비식별화한다 → redact.py
파일 또는 stdin으로 텍스트를 넣으면 비식별 텍스트 + 마스킹 리포트(JSON)가 나온다.
```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/redact.py" <로그.txt>
# Windows
py -3 "$env:SKILL_DIR\scripts\redact.py" <로그.txt>
```
- `--text-only`: 리포트 없이 비식별 텍스트만 출력(다음 분석 스킬에 바로 넘길 때).
- `--mask-low`: 보류된 low confidence 항목(bare 카드번호 등)까지 마스킹(최대 재현율).
- 사용자에게 `by_type`(유형별 건수)·`low_confidence_skipped`(보류 항목)를 해석해 전달한다.

### B. 다른 CS 스킬의 입구 전처리로 쓴다
`aspect-sentiment`·`cs-intent`에 raw 로그를 넣기 전 이 스킬을 **먼저** 통과시킨다.
```bash
python3 "$SKILL_DIR/scripts/redact.py" raw_log.txt --text-only > redacted.txt
# 이후 redacted.txt 를 분석 스킬 입력으로 사용
```

### C. (옵션) LLM 2차 리뷰 — 기본 off
결정론 룰은 **자유텍스트 이름**(예: "홍길동")이나 구어체 주소를 못 잡는다. 더 강한 비식별이 필요하면,
**redact.py가 이미 마스킹한 텍스트에 한해** Claude가 잔여 PII를 추가로 가린다. ⚠️ raw 텍스트에는 절대 LLM을 먼저 쓰지 않는다(원칙 1).

### D. 결과 검증
```bash
python3 "$SKILL_DIR/scripts/redact.py" <로그.txt> > report.json
python3 "$SKILL_DIR/scripts/validate_output.py" report.json   # Windows: py -3 "$env:SKILL_DIR\scripts\validate_output.py" ...
```
`validate_output.py`는 리포트에 **원문 PII가 새지 않았는지**(키 화이트리스트)·by_type 합·토큰 치환 반영을 점검한다.

## 출력 예시

```json
{
  "schema_version": "1.0",
  "redacted_text": "연락처는 [전화_1] 이고 주문번호 2024-0312-8841 건입니다",
  "n_redactions": 1,
  "by_type": {"phone": 1},
  "redactions": [{"type": "phone", "token": "[전화_1]", "confidence": "high", "span": [4, 17]}],
  "low_confidence_skipped": [],
  "policy": {"mask_format": "placeholder", "consistent_pseudonym": true, "recall_first": true, "mask_low_confidence": false, "llm_second_pass": false},
  "residual_risk_note": "결정론 룰 기반 — 자유텍스트 이름은 남을 수 있다(옵션 LLM 2차 리뷰 권장)"
}
```
> 주문번호(`2024-0312-8841`)는 PII가 아니므로 마스킹되지 않는다(과탐 방지).

## 한계 (정직)

- **자유텍스트 이름·구어체 주소**는 못 잡는다 → 옵션 LLM 2차 리뷰(C)로 보완.
- **계좌**는 은행별 자리수가 달라 문맥 키워드 게이트에 의존한다 — 문맥 없는 계좌는 놓칠 수 있다.
- **계좌 vs 사업자번호 라벨**: `123-45-67890`처럼 `3-2-5` 형태는 사업자등록번호 패턴과 일치해, 계좌 문맥이 있어도 `사업자번호`로 라벨될 수 있다. **마스킹은 정상(유출 0)**, `by_type` 라벨만 어긋난다(둘 다 PII라 결과는 안전). 상세는 `references/patterns.md`.
- **카드/계좌 bare 숫자열**은 주문번호 오인을 막기 위해 강한 구조·문맥 없으면 보류(`low_confidence_skipped`).
- 룰 기반이라 신조어·변형 표기(예: "공일공")에는 약하다.

## ⚠️ 데이터 안전

CS 실데이터를 저장소에 저장하지 않는다. 검증·테스트는 합성 데이터만 사용한다. 원본 로그는 읽기 전용으로만 다룬다.
