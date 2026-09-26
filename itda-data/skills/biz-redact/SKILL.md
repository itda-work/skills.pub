---
name: biz-redact
description: >
  업무 문서의 영업기밀(거래처명·프로젝트코드·담당자·단가 등)을 외부 AI에 넣기 전 로컬에서
  결정론적으로 마스킹하고, AI 산출물의 토큰을 원값으로 되돌리는 왕복 게이트입니다.
  "이 견적서 마스킹해서 검토해줘", "거래처명 가리고 원가절감안 분석해줘",
  "AI가 돌려준 검토서 원래 이름으로 복원해줘"처럼 말하면 됩니다.
  사용자 용어집으로 무엇을 가릴지 통제하고, 잔존 0을 검증하며, 무엇을 치환했는지 감사 기록을 남깁니다.
  [책임 경계] 본 스킬은 용어집 기반 영업기밀 마스킹·왕복 복원 전담 — itda-data:pii-redact 는 정형 PII 무상태 마스킹, itda-data:synthetic-data 는 실제 데이터 없이 같은 구조의 가상 데이터 생성.
license: MIT
compatibility: "Python 3.10+"
user-invocable: true
allowed-tools: Read, Bash, Write, Glob, mcp__workspace__bash
argument-hint: "<마스킹할 문서 파일 경로> [--glossary <용어집.json>]"
metadata:
  author: "Chinseok"
  version: "0.2.1"
  category: "data-analysis"
  status: "experimental"
  created_at: "2026-07-16"
  updated_at: "2026-09-05"
  tags: "redaction, masking, roundtrip, glossary, trade-secret, deterministic, stdlib, korean, audit"
---

# biz-redact

> 견적서·원가절감안·검토자료를 외부 AI에 붙여넣는 순간 거래처명·단가·프로젝트코드가 유출됩니다. 이 스킬은 "가려서 넣는다"는 **사람 디스플린**을 **AI 밖 결정론 코드**의 강제력으로 바꾸고, AI가 돌려준 산출물을 원값으로 **왕복 복원**합니다.

용어집 기반 **결정론 마스킹 게이트**입니다. 마스킹·검증·복원은 전부 `scripts/biz_redact.py`가 로컬에서 수행합니다(Claude의 판단이 아니라 실제 룰 연산). 에이전트는 스크립트를 실행하고 **기밀값이 없는 리포트만** 읽습니다.

---

## 핵심 원칙

1. **AI 밖 게이트 (P3 자기모순 차단)** — 마스킹은 정의상 AI 접촉 **전에** 로컬 코드가 해야 경계가 성립한다. 에이전트에게 "가려줘"라고 원문을 주는 순간 원문이 이미 클라우드 모델에 들어간다. 그래서 에이전트는 원문을 읽지 않고 `mask` 스크립트만 실행한다.
2. **결정론 = 재현·감사 가능** — 같은 입력·같은 용어집이면 마스킹본은 항상 byte-identical. LLM 개입 0.
3. **왕복 복원** — PII와 달리 단가·금액은 **AI가 검토할 대상 그 자체**일 수 있다. map.json(복원키) 기반으로 AI 산출물의 토큰을 원값으로 되돌리고, 토큰 변형을 감지한다.
4. **잔존 0 검증** — "마스킹했다"가 아니라 "용어집 전 항목 잔존 0 검증됨" 리포트로 증명한다.
5. **stdlib only** (`re`·`json`·`argparse`·`hashlib`·`datetime`·`pathlib`) — 외부 의존 없음. 고정 출력 계약.

> 무엇을 가릴지는 **사용자 용어집**(`glossary.json`)이 정한다. 도구는 정책 판단을 하지 않고 등재된 항목만 집행한다. 용어집 작성 형식·제약은 [`references/glossary-format.md`](./references/glossary-format.md) 참조.

---

## [HARD] 철칙 (반드시 지킨다)

1. **평문 기밀 파일 4종 — 원문·`glossary.json`·`map.json`·`restored.txt` — 을 에이전트가 Read 하지 않는다.** `mask`/`verify`/`restore`는 **Bash로 스크립트만 실행**한다. 에이전트가 읽어도 되는 **신뢰 산출물**은 `masked.txt`·`report.json`·`verify`/`restore` 리포트·`audit.jsonl` 넷뿐이다(전부 기밀값 미포함). 사용자가 원문을 대화에 붙여넣으려 하면 **파일 경로로 달라고 안내한다** — 붙여넣는 순간 이미 유출이며, 그 자기모순을 막는 것이 이 스킬의 존재 이유다. 복원 결과 확인도 `restore` 리포트(변형 0·복원 건수)로 하고, `restored.txt`는 사용자가 로컬에서 연다.
   > ⚠️ 이 경계는 **지시-강제(instruction-enforced)** 다 — 도구 권한으로 완전히 차단되지 않는다. `Read`는 신뢰 산출물(`masked.txt`·`report.json`) 열람에 필요해 허용되므로, 같은 `Read`로 원문·`map.json`을 여는 것을 기술적으로 막지는 못한다. 이 [HARD] 철칙을 지키는 것이 유일한 방어선이며, 지키지 않으면 경계가 무효가 된다. (스크립트가 만드는 `map.json`·`restored.txt`는 파일 권한도 `0600`으로 좁혀 타 사용자 열람을 막는다.)
2. **`verify` 잔존 > 0 인 마스킹본은 AI 과제에 절대 쓰지 않는다.** 잔존이 발견되면 **중단하고 보고**한다(용어집 보강 안내). 잔존한 채로 AI에 넘기면 게이트가 무효다.
3. **평문 기밀 4종과 `_workspace/` 산출물은 커밋하지 않는다.** 저장소 커밋 금지선이다(합성 `references/glossary-template.json`만 예외).
4. **트레이드오프 안내 의무** — 단가·금액을 용어집에 넣으면 **AI가 그 수치를 검토할 수 없다**. 마스킹 범위를 정할 때 아래 "마스킹 범위 ↔ AI 수행력" 절을 사용자에게 반드시 알린다.

---

## 워크플로우

> 명령은 macOS/Linux 기준 `python3`, Windows는 `py -3`로 바꿔 실행한다(그 외 인자 동일).

### 실행 전 — 스킬 디렉토리 확정

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/biz-redact}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/biz-redact' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\biz-redact"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

### 0단계 — 용어집 확인

무엇을 가릴지 담은 `glossary.json`이 있어야 한다. 없으면 `"$SKILL_DIR/references/glossary-template.json"`(합성 예시)을 복사해 사용자가 채우도록 안내하고, 형식은 `references/glossary-format.md`를 따른다. **용어집은 평문 기밀 파일이므로 에이전트가 Read 하지 않는다** — 사용자가 로컬에서 작성한다.

### 1단계 — 마스킹 (mask)

`masked.txt`·`map.json`·`report.json`을 생성하고, `report` JSON을 stdout으로도 출력한다.

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/biz_redact.py" mask <input.txt> --glossary <glossary.json> \
    [--out-dir _workspace/biz-redact/<doc-id>] [--doc-id <id>] [--now <ISO8601>]
# Windows
py -3 "$env:SKILL_DIR\scripts\biz_redact.py" mask <input.txt> --glossary <glossary.json> ...
#   --doc-id 기본값: 원문 콘텐츠 SHA256 앞 12 hex (파일명 비의존 — 기밀 파일명 누출 차단)
#   --out-dir 기본값: _workspace/biz-redact/<위 doc-id>/
#   --now: 타임스탬프 고정 주입(테스트 결정론용; 미지정 시 현재 시각)
```

- `mask`는 치환 직후 **자체 잔존 검증을 자동 실행**한다. 잔존 > 0이면 exit 1(알고리즘 자기모순 = 에러 표면화)이고, 신뢰 산출물은 디스크에 승격되지 않는다.
- 에이전트는 stdout의 `report.json`(기밀값 미포함)을 읽어 `by_category`(카테고리별 건수)·`residual_count`·`result`를 사용자에게 해석해 전달한다. `masked.txt`·`map.json`은 **경로만** 안내한다.

### 2단계 — 잔존 검증 (verify, 독립 확인)

`mask`가 자동 검증하지만, 마스킹본을 AI에 넘기기 전 **독립 실행**으로 재확인한다.

```bash
python3 "$SKILL_DIR/scripts/biz_redact.py" verify <masked.txt> --glossary <glossary.json>
```

`verified=true`(exit 0)여야 다음 단계로 간다. `false`(exit 1)면 [HARD] 2에 따라 **중단·보고**한다. 리포트는 `entry_index`·위치만 담고 평문은 없으므로, 사용자는 용어집 `entry_index`로 로컬에서 대조한다.

### 3단계 — 마스킹본으로 AI 과제 수행

**`masked.txt`만** AI 검토 과제(요약·비교·검토서 작성 등)에 넘긴다. 토큰(`⟦거래처_1⟧` 형식)은 실체 종류를 드러내므로, AI는 "⟦거래처_1⟧의 단가가 ⟦단가_2⟧로 높다"처럼 토큰 그대로 검토한다. **AI에게 토큰을 바꾸거나 원값을 추측하지 말라고 지시한다**(토큰 변형은 복원을 깨뜨린다 — 4단계가 감지·차단한다).

### 4단계 — 왕복 복원 (restore)

AI 산출물의 토큰을 `map.json` 기준 원값으로 복원하고, 변형·환각 토큰을 감지한다.

```bash
python3 "$SKILL_DIR/scripts/biz_redact.py" restore <ai_output.txt> --map <map.json> \
    [--out <restored.txt>] [--now <ISO8601>]
#   --out 기본값: <map.json 이 위치한 디렉토리>/restored.txt — 항상 _workspace 안(gitignore 가드 내)에
#   생성돼 평문 restored.txt 가 가드 밖으로 새지 않는다 (ai_output 위치와 무관)
```

- 변형 감지: map에 없는 `⟦…⟧` 패턴(환각·공백삽입 토큰), 복원 후 `⟦⟧` 잔존은 **exit 1**. 원값·alias가 복원 전부터 평문 등장하면 경고(마스킹 우회 의심)로 리포트에 기록한다.
- 에이전트는 `restore` 리포트(복원 건수·변형 0)만 읽고, **`restored.txt`는 경로만 안내**한다(사용자가 로컬에서 연다).

> 복원의 목적은 "산출물 토큰의 원값 복원"이지 원문 byte 재현이 아니다. alias로 매칭된 출현도 **대표값(value)으로 정규화**되므로, alias가 쓰인 문서는 복원본이 원문과 표기가 달라질 수 있다(아래 한계 참조).

### 공통 — 감사 로그

`mask`·`restore`는 `_workspace/biz-redact/audit.jsonl`(기본값, `--audit-log`로 변경)에 한 줄 JSON을 append한다: 시각·단계·결과·doc_id·카테고리별 건수·이상 건수만 기록하며 **기밀값은 담기지 않는다**.

**exit code**: `0` 성공(잔존 0·변형 0) / `1` 게이트 실패(잔존 > 0, 변형·환각 토큰) / `2` 사용 오류(입력 파일 없음·용어집·map 스키마 위반).

---

## 마스킹 범위 ↔ AI 수행력 (트레이드오프)

**용어집에 넣은 항목은 AI가 볼 수 없다.** 그래서 무엇을 가릴지는 AI에게 무엇을 시킬지와 직결된다.

| 용어집에 넣는 대상 | 효과 | AI 수행력 |
|---|---|---|
| 식별자만 (거래처·프로젝트코드·담당자) | 누가·어느 건인지 감춤 | 단가·원가율 **수치 검토 가능** ✅ |
| 식별자 + 수치 (단가·금액) | 수치까지 감춤 | 절대 단가 검토 **불가**, 토큰 간 **상대 비교만** 가능 |

- **기본 권장**: 식별자(거래처·프로젝트코드·담당자)는 가리고, **검토 대상 수치는 남긴다**. 그래야 AI가 "이 단가가 시세 대비 높다" 같은 실질 검토를 한다.
- 회사 정책상 수치도 외부 반출 금지면 단가를 용어집에 넣되, 그 경우 **AI는 `⟦단가_1⟧`과 `⟦단가_2⟧`의 상대 크기(어느 쪽이 큰지)만** 다룰 수 있음을 사용자에게 명시적으로 알린다.
- 이 판단은 사용자·보안팀 몫이다. 도구는 용어집대로 집행만 한다.

---

## 출력 예시 — report.json (mask stdout)

```json
{
  "schema_version": "1.0",
  "doc_id": "a1b2c3d4e5f6",
  "glossary_name": "설비팀-용어집",
  "glossary_sha256": "9f2c…(64 hex)",
  "created_at": "2026-07-16T09:00:00Z",
  "by_category": {"거래처": 3, "프로젝트": 1, "단가": 2},
  "tokens_total": 4,
  "tokens": ["⟦거래처_1⟧", "⟦프로젝트_1⟧", "⟦단가_1⟧", "⟦단가_2⟧"],
  "residual_count": 0,
  "normalized": false,
  "result": "pass"
}
```

> 값은 예시다. `by_category`는 카테고리별 치환 **건수**(occurrence), `tokens`는 사용된 **고유 토큰** 목록, `tokens_total`은 그 개수다. `normalized`는 원문이 NFD(분해형)라 NFC로 정규화됐는지 여부다(아래 "한계" 참조 — 기본 `false`). **원값 평문은 report.json에 없다**(원값은 `map.json`에만 존재). `verify`/`restore` 리포트도 같은 급으로 기밀값을 담지 않는다(`verify`/`restore` 리포트에도 `normalized` 플래그가 있다).

---

## 한계 (정직)

- **용어집 등재는 사람 몫** — NER(자유텍스트 신종 기밀 자동 검출)이 없다. 용어집에 없는 거래처·코드는 **가려지지 않는다**. 결정론을 지키는 대가이며, 등재 누락은 사용자 책임이다.
- **조사 정규화 불일치** — alias로 매칭된 출현은 복원 시 대표값으로 정규화된다. 대표값과 alias의 받침이 다르면 한국어 조사가 어긋날 수 있다(예: alias "삼성"이 대표값 "삼성전자"로 복원되면 "삼성은" → "삼성전자은"처럼 조사가 부정확). 복원의 목적은 원값 회복이지 문법 교정이 아니다.
- **토큰 변형 시 안전 실패** — 한국어 카테고리 라벨을 토큰에 넣는 것은 확대 적용이라 LLM이 라벨을 번역·변형할 여지가 있다. 이 경우 복원은 조용히 틀리지 않고 **변형 감지로 exit 1(안전 실패)** 한다. 변형이 관찰되면 AI에게 토큰 보존을 다시 지시하거나 재실행한다.
- **유니코드 정규화(NFC) — 안전 우선** — 입력 텍스트·표면형을 처리 전 **NFC로 정규화**한다. macOS 등에서 흔한 NFD(분해형) 한글 문서에서 등재 기밀이 매칭 실패로 조용히 안 가려지던(위음성) 것을 막기 위함이다(**기밀 마스킹 > 원문 바이트 보존**). 이 때문에 **바이트 수준 왕복 무손실(mask→restore가 원문과 byte-identical)은 NFC 문서에만 성립**한다 — 원문이 NFD였으면 복원본은 NFC라 원문 바이트와 다를 수 있다(NFC로는 동일). 원문이 NFD였던 경우 `mask`·`verify`·`restore` 리포트의 `normalized: true` 플래그로 그 사실을 정직하게 표기한다.
- **겹치는 등재 표면형의 파편 잔존** — 등재 표면형끼리 겹칠 때(예: "거래처지원"과 "지원"이 둘 다 등재), 길이 내림차순 치환으로 긴 쪽이 먼저 토큰화되면 짧은 쪽의 일부가 잘려나가 **의미상 남은 파편이 완결 표면형이 아니라 잔존 스캔에 0으로 보일 수 있다**. 잔존 스캔은 "완결 표면형의 미치환"을 잡지, 부분문자열 파편까지 재조립하지 않는다. 겹치는 표면형은 용어집에서 서로 포함 관계가 되지 않게 정리하고, 필요하면 마스킹본을 육안 확인한다(상세는 `references/glossary-format.md`).
- **텍스트 한정** — 이미지·스캔 속 기밀은 다루지 않는다.

---

## 적용 제외

- 용어집에 없는 **신종 기밀 검출**(NER 미도입).
- "무엇이 기밀인가"의 **정책 판단**(보안팀·사람 소관 — 도구는 집행만).
- **이미지·스캔** 속 기밀(텍스트 한정).
- **정형 PII**(전화·주민번호·카드 등) — 아래 pii-redact 소관이다.

---

## pii-redact와의 역할 차이

같은 "마스킹"이지만 대상·구조가 다르다.

| 축 | `pii-redact` (itda-data) | `biz-redact` (itda-data) |
|---|---|---|
| 가리는 대상 | 정형 PII(전화·주민번호·카드·계좌 등) | 자유텍스트 영업기밀(거래처·프로젝트코드·단가) |
| 검출 방식 | 내장 정규식·룰 패턴 | 사용자 용어집(NER 없음) |
| 상태 | **무상태** — 복원 없음(PII는 영구 마스킹으로 충분) | **왕복** — map.json 복원키(단가는 검토 대상이라 복원 필수) |
| 스코프 | 한국 CS 상담·문의 텍스트 | 업무 문서(견적서·원가절감안·검토자료) |

구조적 이유: CS 분석에서 전화번호는 판정에 무관해 영구 마스킹으로 족했지만, 검토 업무에서 단가는 AI가 검토할 대상 그 자체라 최종 리포트에 원값이 복원돼야 한다 — 왕복 복원이 이 스킬에만 필수인 이유다. (두 스킬은 스코프가 다르며, 여기서는 역할 경계만 설명한다.)

## 부록: Claude Code 확장 (선택)

이 절은 Claude Code 세션에만 적용된다. Cowork 는 본문 절차 그대로 진행한다(부록 미적용이 결함이 아니다).

### 규율의 하네스 강제 (P4, 선택 설정)

[HARD] 철칙 1(평문 기밀 4종 Read 금지)은 지시-강제다 — 본문 스스로 "도구 권한으로 완전히 차단되지
않는다"고 명시한다. Claude Code 사용자는 프로젝트 `.claude/settings.json` 의 PreToolUse hook 으로
이를 실제 차단으로 승격할 수 있다(예시 — 경로는 작업 레이아웃에 맞게 조정):

```json
{"hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command",
  "command": "jq -e '.tool_input.file_path | test(\"(glossary\\\\.json|map\\\\.json|restored\\\\.txt)$\") | not' >/dev/null || { echo '[biz-redact] 평문 기밀 파일 Read 차단([HARD] 철칙 1)' >&2; exit 2; }"}]}]}}
```

hook 이 없어도 본문 철칙은 그대로 유효하다 — hook 은 방어선을 문서에서 코드로 승격하는 선택지다.
