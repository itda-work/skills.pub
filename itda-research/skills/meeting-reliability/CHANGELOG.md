# Changelog — meeting-reliability

## [0.1.4] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 음성→텍스트 상류로 지목하던 `itda-egg:stt`(hyve 앱 전제라 저장소 이관 때 빠짐)를 지우고, “텍스트로 받아써서 넣는다(받아쓰기 스킬 없음)” 로 바꿨다. GUIDE 의 없는 스킬 트리거 문장도 삭제.

## [0.1.3] — 2026-07-26 (이슈 #1284)

### Fixed

- 골든 회귀 경로 정정 — scripts/tests → tests/ (test-directory-convention 정본).

## [0.1.2] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.1] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.0] — 2026-06-21 (SPEC-AUDIT-RELIABILITY-001, #547)

### New Skill (alpha)
- 회의 raw 녹취 → **신뢰성 검수 표**. 감사 신뢰성 엔진의 레퍼런스 구현(코어 5규칙 = 타깃 비종속).
- **코어 5규칙**(근거 강제 · `확인 필요` over-hedge 균형 · 결정/실무·확정/미정 분리 · 잡담/과정값 제거 · 선택적 심층검토)을 결정론 verifier로 **코드 강제**(gate-enforcement; SKILL.md prose 경고가 아님).
- **표현/검증 분리**: 구조화 JSON 코어(SSoT) → `selfcheck` 게이트 → 단일 자족 HTML(`render_html`, 근거 tooltip = 원문 발화·앞뒤 맥락·판정 근거).
- **환각 차단**: 각 행이 실재 발화 span을 가리켜야 통과 — 날조 담당·추정 날짜는 근거 부재로 FAIL.
- **골든 회귀**: 부록 A(raw 녹취 fixture + ③ 기대출력 + ★ assertion 5종). pytest 32 케이스 GREEN.
- stdlib only · 무키 · Python 3.10+.

### 경계
- STT(음성→텍스트)는 `itda-egg:stt` 상류 위임 · 서술형 작성은 `itda-work:draft-post`. 본 스킬은 검수.
- 전표·통제·컨설팅 계층은 후속(엔진 재사용, 어댑터 교체).
