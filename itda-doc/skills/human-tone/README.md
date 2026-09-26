# itda-work / human-tone

직장인 보고서·이메일·기획서·공지의 AI 슬롭을 결정적 메트릭과 보존 가드로 검수하는 후처리 스킬.

상세 사용법은 [SKILL.md](./SKILL.md) 참조.

---

## 차용 출처 (Attribution)

이 스킬의 핵심 자산은 [`epoko77-ai/im-not-ai`](https://github.com/epoko77-ai/im-not-ai) v1.6.1 (MIT License, ⭐937 stars on GitHub) 의 **Humanize KR — 한글 AI 티 제거기** 시스템에서 차용되었습니다.

저작자: epoko77-ai (Copyright (c) 2026)
원본 라이선스: MIT — 본 스킬 디렉토리에 [`LICENSE-im-not-ai`](./LICENSE-im-not-ai) 사본을 동봉합니다.

### 차용 자산 (그대로 또는 직장인 도메인 변형)

| 파일 | 출처 | 변경 |
|---|---|---|
| `references/ai-tell-taxonomy.md` | `humanize-korean/references/ai-tell-taxonomy.md` (587줄) | **그대로** + 직장인 사무 도메인 K 카테고리 5종 부록 추가 (총 666줄) |
| `references/quick-rules.md` | `humanize-korean/references/quick-rules.md` (133줄) | **그대로** + K 카테고리 압축 매칭 룰 부록 추가 (총 169줄) |
| `references/rewriting-playbook.md` | `humanize-korean/references/rewriting-playbook.md` (181줄) | **그대로** + 직장인 시나리오 4종(보고서/이메일/기획서/공지) Before/After 사례집 §6 추가 (총 322줄) |
| `scripts/metrics.py` | `humanize-korean/references/metrics.py` (404줄, v1.6) | **그대로** — 표준 라이브러리만 사용. 외부 의존 0 |
| `scripts/baseline.json` | `humanize-korean/references/baseline.json` (102줄, KatFish 베이스라인) | **그대로** — 인간 470편 / AI 1624편 기준 |
| `scripts/lock_preserved.py` | (자체 작성) | itda-work에서 신규. 보존 영역 placeholder 마스킹 가드 |
| `scripts/verify_gates.py` | `korean-humanize/references/verify_gates.py` (im-not-ai 계열, 2026-08 판) | **설계만 참고** — 축 구성(P0~P3)·exit 의미론·fail-closed(INCONCLUSIVE) 원칙. 로직은 우리 지표(metrics v1.6 + lock_preserved) 위에 재작성, 조건부 규칙(A-2·I-1·A-16) 과교정 축은 자체 추가 (#1619) |
| `references/empirical-validation.md` | `korean-humanize/references/empirical-validation.md` (im-not-ai 계열, 2026-08 판) | **요약** — 측정 설계·G² 수치·기각 판정·측정 오류 정정을 우리 구조로 정리. 독립 재현 아님. 본진 3건 정정(A-2 S2·I-1 조건부·A-16 번역 한정)의 근거 앵커 (#1619) |
| `SKILL.md` | (자체 작성) | itda-work 컨벤션(Apache-2.0 / metadata 블록 / 4 scene)으로 직장인 도메인 재구성 |

### 미차용 (차기 검토)

- `humanize-korean/references/metrics_v2.py` (746줄) — post-editese 3축, baseline_v2.json이 placeholder 상태라 v2.x에서 도입
- `humanize-korean/references/scholarship.md` (289줄) — 학술 출처. 사용자 가치 대비 본문 비대 우려로 본 라운드 제외
- `humanize-korean/references/web-service-spec.md` — 웹 서비스 확장 스펙. itda-work 범위 밖
- `.claude/agents/*.md` (12개) — Claude Cowork는 sub-agent 미지원. monolith fast path 단일 스킬로 흡수
- `.claude/commands/humanize.md`, `humanize-redo.md` — Claude Cowork는 슬래시 커맨드 미지원. SKILL.md `user-invocable: true`로 대체

### 주요 설계 변경

1. **단일 스킬 monolith path** — 원본의 12 에이전트 풀 스택은 출판·저널리즘 대상이라 직장인 후처리 검수에는 과함. monolith fast path 1개 스킬로 통합 (원본의 humanize-monolith 패턴)
2. **K 카테고리 자체 신설** — 원본 A~J 분류는 한국어 출판물 대상. 사무 한국어 특유의 보고서식 군더더기·이메일 과공손·기획서 차용어·공지 ChatGPT 흔적·결론 회피 5종을 K로 별도 신설
3. **lock_preserved.py 자체 작성** — 원본은 변경률 30/50 가드만 있고 보존 영역 결정적 마스킹은 없음. 직장인 도메인은 숫자·고유명사·서명·법조항 환각 위험이 더 크므로 placeholder 가드 추가

### 라이선스 호환성

- 원본 (im-not-ai): MIT
- 본 스킬 (SKILL.md frontmatter): Apache-2.0
- itda-work plugin.json: MIT

MIT 라이선스는 fork·재배포·상용 활용을 모두 허용하며 저작권 표기 + 라이선스 사본 동봉을 조건으로 합니다. 본 스킬은 [`LICENSE-im-not-ai`](./LICENSE-im-not-ai)에 원본 사본을 보존하고, 본 README의 "차용 출처" 섹션에 출처를 명시합니다.

Apache-2.0(SKILL.md)은 MIT(차용 자산)와 호환됩니다 — MIT 자산을 Apache-2.0 환경에서 재배포할 수 있으며, 차용된 references/scripts/ 파일은 원본 MIT 라이선스를 그대로 유지합니다.

### 변경 이력

- **v2.1.0** (2026-09-01, #1619) — 상류 경험적 반증 3건 반영(A-2·I-1·A-16, 정정 이력 보존) + `verify_gates.py` 결정적 판정 게이트 신설(30/50% 문서 규율 → 스크립트 판정)
- **v2.0.0** (2026-05-11) — im-not-ai v1.6.1 풀패키지 차용. v1.0의 휴리스틱 15개 본문 폐기, 결정적 메트릭·사전·보존 가드로 전환
- **v1.0.0** (2026-05-11) — 초기 휴리스틱 버전. MIT 라이선스 AI 글쓰기 탐지 패턴 영감
