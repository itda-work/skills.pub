# Changelog — work-plan

## [0.13.1] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- 스킬 카탈로그(`references/skill-catalog.md`) 재생성 — 저장소 이관 때 빠진 hyve 앱 전제 스킬 8종이 목록에서 빠지고, calendar·email 설명이 itda-hyve 이름으로. ground-check 가 빠진 스킬을 실재로 인정하지 않는다.
- `ground_check.py` 동명 스킬 설명 문구 일반화(동작 불변). 동명 스킬이 사라져 복수 경로 분기를 더는 검증하지 않던 테스트를 임시 카탈로그 fixture 로 고정했다.

## [move] — 2026-07-28 (이슈 #1319)

### Changed

- itda-work → itda-coach 팩 이동 (여정 코칭 팩 재편 — 계획 단계 편입). 스킬 이름·계약 불변, skill-catalog 소속 표기 갱신.

## [rename] — 2026-07-27 (이슈 #1310)

### Changed

- 스킬명 `plan-work` → `work-plan` — itda-work 업무 파이프라인 `work-*` 접두 패밀리 통일. 참조 전수 갱신(CI 매트릭스·skill-catalog·형제 스킬 상호참조).

## [0.12.1] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.12.0] — 2026-07-22

### New Features / Improvements (#1225 — ax-proposal 설계 역수입·파이프라인 마찰 축소)

- **3중 컨펌 해소 — 축약 mirror-back**: find-work 메모 첨부(또는 같은 세션 이어받기) 입력은
  이미 인터뷰로 합의된 산출물이므로 전체 4항목 재확인 대신 "요지 2~3줄 + 달라진 점 1문"으로
  축약(생략 아님 — [HARD] 생략 금지 불변, 변경점은 일반 mirror-back으로). find-work 컨펌 →
  mirror-back 컨펌 → Stage 4 컨펌의 3중 게이트 이중 노동 제거. mirror-back-patterns.md 패턴 추가.
- **Stage 1 첫 턴 4지선다 조건화**: 호출 인자·첫 메시지에 요구사항이 이미 오면 입력 방식을 묻지
  않고 유형 판별 후 바로 진행. 빈손일 때만 4지선다. 같은 세션 find-work 이어받기는 첨부 불요.
- **가치·검증 이월 손실 수리**: `extract_from_findwork_memo`가 find-work 메모 §6 가치 추정·
  §5 AI 출력 검증을 추가 추출(value/verification 키), `merge_inputs` 요약에 포함. 산출 메모
  "요구사항"(기대 가치 한 줄)·"실패 시 대처"(검증 방법·주기)로 이월 — 계획의 준비 비용을
  정당화할 ROI 근거가 파이프라인에서 유실되던 문제 수리. 회귀 테스트 4건 추가.
- **저장 전 셀프 리뷰** (Stage 4, 컨펌 게이트 직전): ground-check(기계 검증)와 별개의 정성
  1패스 — 실행 가능성·발화 동작성("다음 세션에서 시작하기" 발화가 실제 트리거되는가)·준비물
  완결성 3축에서 약점을 찾아 반영 (ax-proposal 관문4 방식).

### Why

ax-proposal(itda-ceragem)과의 비교 검토(#1225)에서 도출. ground-check·컨펌 게이트 등 기존
자산은 불변, 마찰(중복 컨펌·불필요 첫 질문)과 이월 손실만 수리.

## [0.11.0] — 2026-07-18

### Bug Fixes / Improvements (#1216 — 카탈로그 stale 현행화 + 생성기 전환)

- **skill-catalog.md 를 수기 큐레이션에서 자동 생성물로 전환**: 2026-05-21 자 23종에서 멈춰
  실제 스킬(91종)과 드리프트 — Stage 3 [HARD] ground-check 가 이 파일에 바인딩되어 실재 스킬이
  "⚠️ 확인 필요"로 강등되던 동작 결함. `skills/scripts/gen_skill_catalog.py` 신설(SKILL.md
  frontmatter·본문에서 결정론 생성, `--check` drift 검사)로 91종/20팩 전수 현행화.
  표기 드리프트 교정 동반: `hwpx`→`hwpx-reader`(#368 rename 미반영), dart 의 키 오기
  (KO_DATA_API_KEY→DART_API_KEY).
- **ground_check 경로 매핑 단일 소스화**: 하드코딩 `_SKILL_DIR_MAP`(23종, 카탈로그와 이중
  소스) 폐기 → 카탈로그 md "경로 매핑" 블록 파싱으로 교체. 동명 스킬(web-automation ×2)
  복수 경로 허용.
- **env 허용목록 카탈로그 파생**: `check_env_var` 허용목록 = 기본 세트 ∪ 카탈로그 "필요한 키"
  열 파생(`_catalog_env_vars`). 스킬 추가 시 카탈로그 재생성만으로 키가 따라온다.
  ground-check-rules.md §2 를 파생 구조로 갱신(+stale 행 교정: GEMINI→emoticon,
  RONE→realty-price-stats, KO_DATA 사용 스킬에서 dart 제거).
- **drift 재발 가드**: `scripts/tests/test_gen_skill_catalog.py` 신설 — 카탈로그↔SKILL.md
  전수 정합·경로 실존·셀 비공백을 release-skills CI(`pytest scripts/tests/`)에서 강제.
  plan-work 인수 테스트에 회귀 2클래스 추가(신세대 스킬 인식·카탈로그 파생 키 통과).

## [0.10.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.10.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.10.1] — 2026-05-21 (라이브 검증으로 적발된 실 동작 결함 외과 수정)

### Bug Fixes

- **build_memo_content API contract 한-영 키 불일치** (Critical, 라이브 검증 발견): 이전 구현이 영문 키(`requirements`, `plan`, `prereqs`, `keys`, `next_session`, `failure`)만 받아 LLM이 SKILL.md 한국어 섹션 헤더("요구사항", "단계별 계획" 등)를 그대로 키로 쓰면 모든 섹션이 `미정`으로 채워지는 결함. 한국어 키 우선·영문 키 fallback의 호환층 추가로 외과 수정. 신규 테스트 `TestAC17_KoreanKeyContract` 2건 추가. 기존 45 → 49 tests PASS.
- **apply_human_tone 정책-코드 불일치** (Medium, 동일 라이브 검증 발견): SKILL.md §Stage 4가 흐릿한 마케팅 슬롭("효율적인 워크플로우를 위해...") 금지를 정책으로 박았으나 이전 apply_human_tone은 단순 단어 치환만 수행해 [[feedback-gate-enforcement-code-not-docs]] 패턴 재현. `detect_marketing_slop()` 신설로 7종 슬롭 패턴 정규식 detection 추가. 신규 테스트 `test_ac_09_marketing_slop_detected`, `test_ac_09_clean_text_no_slop` 2건 추가.

### Why

[[feedback-skip-counts-suspect-as-failures]] 정확 재현 — 45 tests PASS 자체는 진실이었으나 테스트가 영문 키만 사용해 contract mismatch를 falsify하지 못함. 라이브 데이터 레이어 적대 검증(catalog_loader/ground_check/memo_writer 실 호출)으로 두 결함 동시 적발. SPEC AC는 "스킬이 어떻게 동작해야 하는가"는 정의하지만 "LLM이 SKILL.md 한국어 헤더로 호출하면 어떻게 되는가" 같은 실 사용 시나리오는 다루지 않았던 갭. 향후 manager-tdd 위임에서 데이터 레이어 contract는 "SKILL.md 본문에 노출된 키 어휘로 직접 호출 통과" 테스트를 표준화 권장.

## [0.10.0] — 2026-05-21 (skill-creator 적대적 평가 반영)

### Improvements

- **description 트리거 어휘 개선** (H-1·H-2·M-1 일괄 해소):
  - "내가 말한 거 다시 정리해서 확인해줘" 신규 트리거 어휘 추가 (mirror-back 자체 발화로 plan-work 호출 가능)
  - "자동화하기 전에 뭘 준비해야 해?" 신규 트리거 어휘 추가 (선행 자료 안내 가치 노출)
  - "어떻게 진행할까" (광범위, false positive 위험) → "어떻게 시작하지" + "어떤 itda 스킬로 풀 수 있어" (구체)
  - "요구사항" (SI/IT 업계 용어) → "이거", "하고 싶은 게 정해진" (회사원 청중 어휘로 환원)
  - 영문 supporting 문장 1→2 문장 확장. mirror-back·ground-check·memo 키워드 노출.
- **allowed-tools 최소 권한 축소** (H-3 해소): `Read, Bash, Write, Edit, Glob, Grep` → `Read, Write, Bash`. Edit·Glob·Grep은 스킬 동작에 사용하지 않음 (scripts/는 stdlib만, references는 Read로 충분).
- **tags 정제** (M-3 부분 해소): 내부 메커니즘 용어(`mirror-back`, `ground-check`)와 청중 부적합어(`비개발자`) 제거, 사용자 검색 어휘(`다시정리`, `시작방법`, `선행자료`, `직장인`)로 교체.

### Why

skill-creator로 외부 적대적 평가 시 발견된 트리거 정확도 결함 5건 중 4건을 즉시 해소. 정성 평가 기준 트리거 정확도 약 60→80%+ 예상. 변경된 동작 없음 — description·tags·allowed-tools 메타데이터만 정제.

[[feedback-gate-enforcement-code-not-docs]] 정신 — description은 메타데이터지만 사용자가 스킬을 만나는 첫 게이트이므로 정확한 트리거 어휘로 enforcement.

## [0.9.0] — 2026-05-21 (SPEC-PLAN-WORK-001)

### New Features

- **Stage 1 입력 모드 4지선다**: 자유 텍스트 / find-work 메모 첨부 / 이전 plan-work 메모 첨부 / find-work 안내 후 종료.
- **Stage 2 Mirror-back**: 요구사항을 목표·자료·빈도·결과물 4항목으로 정리하고 사용자 확인을 받는다. 최대 3회 반복 후 항목 단위 확인 모드로 전환. 어떤 상황에서도 생략 불가.
- **Stage 3 계획 수립 + Ground-check (DP-1 Hybrid)**: `references/skill-catalog.md` 큐레이션 목록으로 스킬명·환경변수명 검증. 실패 시 abort 아닌 downgrade-with-warning (DP-3).
- **Stage 4 컨펌 게이트**: AskUserQuestion 4지선다로 명시적 확인 후 저장. 보류 선택 시 `미정` 마커로 부분 저장.
- **산출 메모 6섹션**: 요구사항 / 단계별 계획 / 선행 자료 안내 / 필요한 키·접근 권한 / 다음 세션에서 시작하기 / 실패 시 대처.
- **종료 키워드 처리**: "여기까지", "그만", "보류" 발화 시 즉시 Stage 4로 점프.
- **재진입 모드**: 이전 plan-work 메모 첨부 시 지정 섹션만 mirror-back, 나머지 보존.
- **Python 데이터 레이어** (scripts/): catalog_loader.py, ground_check.py, memo_writer.py — stdlib only, Python 3.10+.
- **45개 수용 기준 테스트**: 18개 AC 전량 커버 (0 skipped).

### Why

find-work가 "뭘 할지 모르는" 사용자를 위한 스킬이라면, plan-work는 "뭘 할지는 알지만 어떻게 진행할지 모르는" 사용자를 위한 실행 계획 생성 스킬이다. find-work의 자매 스킬로 SPEC-PLAN-WORK-001에 명세됨.

- SPEC: `.specs/SPEC-PLAN-WORK-001/spec.md`

### Limitations (초기 버전)

- 스킬 카탈로그는 수동 큐레이션 (`references/skill-catalog.md`) — 신규 스킬 추가 시 파일 갱신 필요.
- 한 세션에 하나의 메모만 생성.
- 다중 세션 자동 메모리 없음 — 이전 메모는 사용자가 직접 첨부.
