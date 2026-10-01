# Changelog — itda-work/human-tone

## [2.1.3] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다.

## [2.1.2] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 배포본에 실리는 `HANDOFF.md` 의 개인 절대 경로(`/Users/…`) 7곳을 `<저장소 루트>` 등 자리표시자로.

## [2.1.0] — 2026-09-01 (이슈 #1619)

### Changed

- `references/ai-tell-taxonomy.md` 정정 3건 — 상류 `im-not-ai` 의 대조 코퍼스(AI 60편 vs 2022년 이전 사람 60편, G²) 반증 반영. **A-2** `~를 통해` S1→S2, 남발(3회+)만 억제·한두 번 보존(원어민이 2배 더 씀) · **I-1** `것이다` 무조건 평서화 기각 → 연속 3회+ 남발일 때만(사람이 2배) · **A-16** 영어 대명사 직역은 번역 맥락 전용(자생 산문 미발동). 각 항목에 `근거:`·`정정 이력:` 을 남겼고 quick-rules·playbook 을 정합. 요약 근거 문서 `references/empirical-validation.md` 신설.
- SKILL.md 4대 철칙 4 "과윤문 금지" 를 스크립트 판정으로 교체하고 **6단계 사후 판정 게이트**를 절차 마지막에 편입. "정상 한국어를 지우는 것도 과윤문" 을 명문화.

### Added

- `scripts/verify_gates.py` — 윤문 사후 결정적 판정 게이트(표준 라이브러리만). 사전 정규화(공백·따옴표·대시·NFC) 후 4축: P0 문자 변경률(>30% WARN·≥50% ABORT, 카피 씬 면제) · P1 목표 달성/과교정(쉼표 4지표 z + A-2·I-1·A-16 조건부 과교정) · P2 수사 전멸(대구·부정 대조·문두 반복 ≥3→0 FAIL) · P3 보존 불변식(`lock_preserved` 재사용). exit 0 PASS / 1 FAIL / 2 INCONCLUSIVE(측정 불능은 PASS 로 접지 않는다) / 3 입력 오류.
- `tests/test_verify_gates.py`(4축 RED 표본·INCONCLUSIVE·카피 면제·정정 3건 보존 골든·taxonomy 문서 단언) + `tests/test_deployed_gates.py`(subprocess exit 계약). 뮤테이션 8종(S1 복원·preserve_min 0·abuse_run 1·A-16 전 씬·P2 무효·P3 항상 통과·INCONCLUSIVE→PASS·ABORT 해제) 전건 RED 실측.

## [2.0.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [2.0.4] — 2026-07-26 (이슈 #1280)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280) — Cowork 전용 오해 제거.

## [2.0.3] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [2.0.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [2.0.1] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.
