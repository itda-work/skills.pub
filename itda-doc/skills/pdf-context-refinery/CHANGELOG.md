# Changelog — itda-work/pdf-context-refinery


## [1.4.0] — 2026-09-28 (#28)

### Added

- `page_quality.py` 에 `garbled_hangul` 판정 — ToUnicode 가 잘못 매핑돼 한글 음절 영역의 엉뚱한 글자("뽩 쪀싪텖")가 나오는 쪽은
  대체문자·PUA 비율에 안 걸려 텍스트 경로로 가고 LLM 이 깨진 글을 정리하려 들었다. 받침 분포로 가른다: 한글 음절 30자 이상에서
  받침 없는 음절 비율 < 0.15 **그리고** 희귀 받침(겹받침·ㅋㅌㅍ) 비율 ≥ 0.15. 설계는 kordoc(`src/pdf/quality.ts`, MIT) 대조에서
  가져오고 임계는 우리 실측으로 정했다.
- 쪽별 지표 `hangul_chars`·`no_batchim_ratio`·`rare_batchim_ratio` 와 문서 단위 권고 `doc_needs_ocr`(판정 쪽의 30% 이상이
  `needs_vision`) — 기존 키는 그대로다. SKILL Step 1 에 "깨진 한글 쪽은 정리하지 말고 비전으로" 를 적었다.

### 실측 근거 (임계)

- 정상: 기업마당 공고 첨부 PDF 51건(339쪽, 한글 30음절 이상 319쪽) + 저장소 PDF 4건(300쪽) — 받침 없음 최소 0.286, 희귀 받침 최대 0.042.
  같은 공고들의 연속 30음절 창 20,792개 — 받침 없음 최소 0.133, 희귀 최대 0.100. 받침 없음만 보면 짧은 구간이 걸리므로 두 조건을 AND 로 둔다.
- 깨짐: 공고 12건을 다시 짜서 ToUnicode 를 고친 표본 — 무작위 음절(21쪽) 받침 없음 ≤ 0.099·희귀 ≥ 0.387,
  코드포인트 +1 어긋남(21쪽) 받침 없음 0·희귀 ≥ 0.224. kordoc 의 희귀 ≥ 0.25 는 +1 어긋남 2쪽을 놓쳐 0.15 로 낮췄다.
- 결과: 공고 51건 `garbled_hangul` 거짓 양성 0, 깨진 표본 42쪽 전건 검출. `doc_needs_ocr` 는 공고 중 1쪽짜리 스캔 포스터 8건에만 섰다.
- 한계: 문서 안에 실제로 쓰인 음절끼리 뒤바뀐 매핑(21쪽 표본)은 받침 분포가 그대로라 못 잡는다.

### Tests

- 경계값(받침 없음 = 0.15·희귀 = 0.15)·30음절 미만 비판정·low_text 우선·혼합 문서·`doc_needs_ocr` 비율 테스트. 뮤테이션 10종 전건 RED.

## [1.3.0] — 2026-09-27 (#5)

### Added

- `scripts/page_quality.py` — 전 페이지 텍스트층 판정(`empty`·`low_text`·`garbled`·`ok`)과 비전으로 읽을 쪽 목록 `needs_vision` 을 JSON 으로 낸다.
  Step 1 이 첫 3쪽 샘플이 아니라 이 목록으로 스캔 쪽을 가른다 — 앞은 텍스트, 뒤 신청자격 표만 스캔인 공고의 뒤쪽을 조용히 빠뜨리던 것을 막는다
  (kordoc 대조 #1·gpt-6-astra 리뷰). 기업마당 공고 첨부 PDF 16건 실측에서 스캔 3건·저텍스트 쪽 3개를 골라냈다.
- 비전으로도 못 읽은 쪽은 결과 머리에 "미검증 쪽" 으로 남기는 계약 — funding 한계 고지가 이 목록을 옮긴다.
- 뮤테이션 2종(판정 목록을 garbled 로 좁힘·끝쪽 빈 조각 전부 제거) RED 실측.

## [1.2.3] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [1.2.2] — 2026-07-26 (이슈 #1280)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280) — Cowork 전용 오해 제거.

## [1.2.1] — 2026-07-26 (이슈 #1274)

### Fixed

- Step 6 검증 명령의 미정의 변수 `${CLAUDE_SKILL_DIR}` 제거 — Prerequisites 에 `SKILL_DIR` 확정 스니펫(Code=`$CLAUDE_PLUGIN_ROOT` / Cowork=세션 마운트 find) 신설. `python` 호출을 `python3` 로 교정(python-runtime 규칙).

## [1.2.0] — 2026-05-22 (SPEC-PDF-REFINERY-REFS-001)

### New Features

- `references/` 도메인 아키텍처 신설 (Progressive Disclosure 패턴).
  `references/README.md` 매핑표 + `domain-tax-accounting.md` / `domain-electronics.md` / `domain-legal.md` / `domain-engineering.md` 4개 도메인 파일 (§1~7 구조, 각 ≤130줄).
- `verify_quality.py --domain {tax-accounting|electronics|legal|engineering}` 옵션 추가.
  도메인별 페이지 헤더 정규식 + 검증 항목(수식 패턴, 조문 패턴, 단위 패턴 등) 활성화.
- Step 1 Analyze에 도메인 감지 단계 추가: `references/README.md` 매핑표 기준 키워드 grep, 임계값 3, 결정론적 동률 처리.
- `check_domain_items()` 신규 함수: 도메인별 검증 항목 반환 (`domain=None` → 빈 리스트, backward compat 보장).

### Improvements

- SKILL.md 도메인 어휘 외부화: 세무·회계 특화 키워드(`조특법`, `법인령`, OCR 아티팩트 예시 등) → `domain-tax-accounting.md §6`으로 이전.
- SKILL.md 283줄 → 180줄 (NFR-1 ≤180 달성). 항상-로드 토큰 절감 ~4K.
- `verify_quality.py` 페이지 헤더 정규식 한국어 세무 가정 → `--domain` 옵션으로 도메인별 분리. 미지정 시 기존 동작 100% 유지(backward compat).
- `references/README.md` 도메인 감지 키워드에 영문 보강 (electronics: `inverter·grid·voltage·current·frequency·AC·DC·capacitor·resistor`, legal: `plaintiff·defendant·court·statute·case·judgment`, engineering: `stress·strain·load·thermodynamics·fluid·material·Chapter`) + grep `-iE` 대소문자 무시. NREL 영문 PDF (152p inverter 매뉴얼) 라이브 재검증 통과 — electronics 1569 매칭으로 임계값 3 압도 1위.

### Tests

- `tests/test_verify_quality_domain.py` 신설: 22 tests (도메인별 4종 × 패턴 테스트 + backward compat 4 + 단위 테스트 5).
- 52 passed / 0 failed / 0 skipped (기존 30 + 신규 22).

## [1.1.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [1.1.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.
