# Changelog — pii-redact

## [0.1.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.2] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.1] — 2026-06-01 (dogfooding 한계 문서화)

### Docs
- **계좌 vs 사업자번호 라벨 모호성** 명시(SKILL.md 한계·references/patterns.md): `123-45-67890`처럼 `3-2-5` 형태는 사업자등록번호 패턴과 일치해, 계좌 문맥이 있어도 `사업자번호`로 라벨될 수 있음. **마스킹은 정상(유출 0)**, `by_type` 라벨만 어긋남(둘 다 PII라 비식별 결과는 안전). 문맥 우선 라벨 보정은 후속 과제. (머지 후 dogfooding에서 발견)

## [0.1.0] — 2026-06-01 (이슈 #33 명세 기준, SPEC-PII-REDACT-001 명목)

### New Skill (PoC)
- **pii-redact v0.1.0**: 한국 CS 텍스트의 개인정보(PII)를 LLM에 넣기 전 결정론 룰로 검출·마스킹하는 인프라 스킬. `itda-cs`의 두 번째 동반 인프라(epic #28 로드맵 1순위).
  - **결정론 코어**(`scripts/redact.py`): 전화·이메일·주민등록번호·사업자등록번호·카드·계좌·운전면허·여권·한국 주소 검출. 주민번호 mod11·카드 Luhn 체크섬은 **필터가 아닌 confidence 태그**. 겹침 해소(우선순위·길이) + 문서 내 일관 가명화(`[전화_1]`) + 뒤→앞 치환(span 무손상). stdlib(`re`)만.
  - **출력 검증**(`scripts/validate_output.py`): 리포트 스키마 + **원문 PII 미유출**(redactions 키 화이트리스트) + by_type 합 + 토큰 치환 반영 정합성.
  - `references/`(output-schema.json·patterns.md) + SKILL.md.

### 설계 의도
- raw CS 로그를 Claude/외부에 붙여넣는 순간 PII가 유출된다. 현재 안전장치는 "익명화한다"는 **사람 디스플린뿐 — 코드 강제력 0** → 이 스킬이 그 게이트를 코드로 만든다. 근거: ml-absa(PRIVATE) 기획서 §6.5.
- **결정론 로컬 우선**(원칙 1): raw를 LLM에 먼저 넣지 않는다. LLM 2차 리뷰는 이미 마스킹된 텍스트에만, 옵션·기본 off(코드 아닌 SKILL.md 절차).
- **재현율 우선**: 누락 < 과제거. 단 카드 bare·계좌처럼 충돌이 큰 유형은 강한 구조·문맥 없으면 마스킹 보류(`low_confidence_skipped`)로 투명 기록 — 주문번호 16자리 등의 과탐을 막는다.
- `aspect-sentiment`·`cs-intent` 등 모든 CS 분석의 **안전 입구 전처리**.

### 설계 결정 (사용자 확정)
- 스킬명 `pii-redact` · 마스킹=플레이스홀더(`[전화_1]`) · 문서 내 일관 가명화 · LLM 2차 리뷰 기본 off.

### 검증
- 단위 테스트 **40 passed** (체크섬·유형별 재현율·오탐 정밀도·일관 가명화·raw 미유출·span 무손상·주소 경계·종단). codex review 9라운드 적대 검증 반영(주소 정규식 겹침·트리밍·건물번호 경계).
  - 정밀도 회귀: 주문번호 `2024-001234`·날짜 `2024-01-15`·bare 카드(Luhn 실패+문맥 없음)를 PII로 오인하지 않음.
  - 안전 불변식: redactions 항목은 `{type, token, confidence, span}`만 — 원문 PII 미포함.
- 라이브: 합성 CS 로그 종단(8유형 혼재 → 비식별 텍스트 + 마스킹 리포트 → validate VALID).

> 정식 SPEC은 운영 졸업 시점에 `docs/specs/SPEC-PII-REDACT-001.md`로 생성 예정. 현재 명세 기준은 GitHub 이슈 #33.
