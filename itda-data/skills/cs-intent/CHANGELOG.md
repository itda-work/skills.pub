# Changelog — cs-intent

## [0.1.5] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.1.4] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.3] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.1.2 (2026-07-14) — validator 실효성 강화 + 대량 배치 연동 (#1140 Codex R2)
- **`validate_output.py` 가 output-schema 의 `additionalProperties:false` 를 실제 강제** — 기존 파서는 top-level 허용 밖 필드를 조용히 통과시켰다(Codex 실증). top-level 허용 필드 집합 검사 + `flags` 타입 검사(과거 비-dict `flags` 를 `or {}` 로 삼켜 정합성 검사 무력화) + `domain` enum + `confidence` 타입·범위(문자열 confidence TypeError 크래시) + 비-dict doc 가드 추가.
- **대량 배치(팬아웃/팬인) 연동 절 추가** — 30건+ 는 Lead 가 청크(JSONL) 분할 → `itda-cs:cs-batch-extractor` 병렬 디스패치 → `validate_output.py <jsonl> [intent-taxonomy.yaml]` 로 검증·병합. **커스텀 인텐트 체계를 워커에 주면 검증에도 같은 경로 전달**. 단건 절차·스키마·인텐트 체계 불변.
- 회귀 테스트 신설(`tests/test_validate_output.py`): extra field FAIL·`flags` 타입·multi_intent 정합성·커스텀 체계 관철·파일-레벨 exit code.

## 0.1.1 (2026-06-01) — itda-cs 분리 후속 (IAA 게이트 링크)
- 운영 졸업 "IAA 측정" 게이트를 같은 플러그인의 `iaa-builder` 스킬로 구체 링크(`sample.py` 골드셋 → 2인 라벨 → `iaa.py` Cohen κ → 졸업 게이트). 벽장 안전망 → 실행 가능 게이트.
- `primary_intent`는 평면 단일값이라 iaa-builder `--stratify`/라벨 컬럼에 바로 흐름(단, 본문은 원본 로그 또는 `evidence` 사용 — cs-intent 출력 스키마는 `text` 미포함).

## 0.1.0 (2026-05-30)

- 신규(**개념 증명/PoC**): CS 문의 **인텐트(문의유형) 분류** 스킬. `aspect-sentiment`의 자매(직교 — "왜 연락했나" vs "무엇에 대해 어떻게 느끼나").
- 인텐트 체계 10군 + 기타(`references/intent-taxonomy.ko.yaml`), 고정 출력 계약(`output-schema.json`), few-shot(단일·복수·감정동반·미분류), stdlib 검증기.
- `primary_intent` + `secondary_intents` + `flags.multi_intent`. `taxonomy_version` 전파 · `other_rate` 비차단 자기진단 경고.
- **운영 졸업엔 IAA 측정(골드셋·2인·Cohen κ) 필수** 명시(벽장 안전망 회피).
- 원천: `aspect-sentiment` 목적-적합성 검토(itda-skills #26 → 자매 분리 #27). 운영 소분류 ~50종이 인텐트축이라는 진단.
- 범위 밖(후속): legacy_map(소분류→인텐트) P1 확정 · 라우팅/SLA · 집계 KPI · 골드셋 평가.
