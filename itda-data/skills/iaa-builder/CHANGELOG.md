# Changelog — iaa-builder

## [0.1.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.2] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.1.1] — 2026-06-01 (itda-refine 게이트 반영, #30)

### Bug Fixes
- **M1 — 합격선↔등급 자기모순 해소**: 기본 졸업 합격선 `0.60 → 0.61`(= Landis-Koch substantial 하한, `DEFAULT_THRESHOLD` 상수화). 기존엔 κ=0.60이 `graduation.passed=true`인데 `interpret(0.60)='moderate'`(재측정 권고 등급)로 표기돼 자기모순. SKILL.md·interpretation.md 문구 "0.60=substantial"을 "0.61=substantial 하한"으로 정합. (spec-auditor + gate-enforcement 독립 2회 적발)
- **M2 — cs-intent→iaa 핸드오프 무음 단절 방지**: `sample.py`에 본문 컬럼 전량 공란 시 fail-loud 경고 추가(`all_text_empty()`). cs-intent 출력 스키마는 `text`를 금지(`additionalProperties:false`)하므로 `--text text`로 넣으면 빈 시트가 무음 생성되던 함정. SKILL.md 라우팅 가이드에 "원본 로그 join 또는 `--text evidence`" 명시. (cross-skill-integrator 종단 실측 적발)

### Docs
- **L1**: `per_category_kappa`·`ambiguous_categories`가 2인(Cohen) 한정이며 Fleiss(3인+)는 빈 배열임을 SKILL.md·interpretation.md 명시.
- **L2**: aspect-sentiment→iaa 핸드오프의 측정 단위(중첩 `aspects[]` 평탄화 필요)를 aspect-sentiment SKILL.md에 명시.

### Tests
- 24 → **26 passed**: M1 회귀(`test_default_threshold_is_substantial_floor`) + M2 회귀(`test_all_text_empty_detects_cs_intent_handoff_gap`).

> 정식 SPEC은 운영 졸업 시점에 `docs/specs/SPEC-IAA-BUILDER-001.md`로 생성 예정. 현재 명세 기준은 GitHub 이슈 #30.

## [0.1.0] — 2026-05-31 (이슈 #30 명세 기준, SPEC-IAA-BUILDER-001 명목)

### New Skill (PoC)
- **iaa-builder v0.1.0**: CS 분류 라벨의 어노테이터 간 일치도(IAA)를 Cohen·Fleiss κ로 측정하는 인프라 스킬. `itda-cs`의 첫 동반 인프라.
  - **결정론 코어**(`scripts/iaa.py`): Cohen's κ(2인)·Fleiss' κ(N인)·카테고리별 one-vs-rest κ·Landis-Koch 등급·졸업 게이트. stdlib(`math`)만, 손계산 검증값 대조.
  - **골드셋 샘플링**(`scripts/sample.py`): CS 로그(JSONL/CSV) → 층화 비례 샘플링(결정론, seed 고정) → 어노테이션 시트(라벨 빈칸 CSV) 생성.
  - **출력 검증**(`scripts/validate_output.py`): 리포트 JSON 스키마 + κ↔등급↔졸업 정합성.
  - `references/`(output-schema.json·interpretation.md) + SKILL.md + GUIDE.md.

### 설계 의도
- `aspect-sentiment`·`cs-intent` SKILL.md의 "운영 졸업 IAA 측정" 게이트가 **측정 수단 없이 문서로만 존재**(벽장 안전망) → 이 스킬이 게이트를 실행 가능하게 만든다.
- 모든 신규 CS 분류축(원인·긴급도 등) 추가의 **선행 관문**: 골드셋 + 2인 + κ 통과 전엔 거부.
- "thin wrapper 아님": κ는 LLM 추정이 아니라 `iaa.py`의 결정론 통계 연산. `data-analysis-advisor` 양심 게이트 철학의 CS판.

### 검증
- 단위 테스트 **24 passed** (κ 코어 17 + 샘플링 7).
  - 손계산 검증: Wikipedia Cohen κ=0.40, Fleiss 3-item 손계산 κ=0.5497.
  - 핸드오프 종단: sample.py 시트 생성 → 라벨 채움 → iaa.run_csv κ 산출.
- 라이브: 실제 cs-intent 출력 2회 라벨 → κ 산출(스킬 출시 검증).
