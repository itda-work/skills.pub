# Changelog — aspect-sentiment

## [0.1.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.1.4] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.1.3 (2026-07-14) — validator 실효성 강화 + 대량 배치 연동 (#1140 Codex R2)
- **`validate_output.py` 가 output-schema 의 `additionalProperties:false` 를 실제 강제** — 기존 파서는 top-level·`aspects[]` 항목의 허용 밖 필드를 조용히 통과시켜(Codex 실증) extra 필드 누출(예: 원문 유출)을 못 잡았다. top-level·`aspects[]`·`process_signals` 허용 필드 집합 검사 + `flags`/`process_signals`/`escalated` 타입 검사 + `domain`·`customer_final_sentiment` enum + `confidence` 타입·범위(과거 문자열 confidence 는 TypeError 크래시) + 비-dict doc 가드 추가.
- **대량 배치(팬아웃/팬인) 연동 절 추가** — 30건+ 는 Lead 가 청크(JSONL) 분할 → `itda-cs:cs-batch-extractor` 병렬 디스패치 → `validate_output.py <jsonl> [taxonomy.yaml]` 로 검증·병합. **커스텀 taxonomy 를 워커에 주면 검증에도 같은 경로 전달**(안 하면 커스텀 라벨 거짓 거부). 단건 절차·스키마·taxonomy 불변.
- 회귀 테스트 신설(`tests/test_validate_output.py`): extra field FAIL·nested 타입·커스텀 taxonomy 관철·파일-레벨 exit code.

## 0.1.2 (2026-06-01) — itda-cs 분리 후속 (IAA 게이트 링크)
- 운영 졸업 "IAA 측정" 게이트를 같은 플러그인의 `iaa-builder` 스킬로 구체 링크(벽장 안전망 → 실행 가능 게이트).
- IAA 측정 단위 명시: doc당 `aspects[]`(중첩)는 iaa-builder 평면 라벨 컬럼에 직접 못 넣으므로 doc 단위(`overall_sentiment`) 또는 (doc, aspect) 쌍 평탄화 후 측정(itda-refine cross-skill-integrator 권고).

## 0.1.1 (2026-05-30) — 목적-적합성 검토 반영 (계약 정합성)

11-에이전트 "통계+대처 목적-적합성" 검토(6 페르소나 + 3 적대 검증) 결과, **축 추가 없이 계약 정합성만** 수정:
- **`reopen_count` 단건 출력에서 제거** → 집계 레이어(ml-absa). cross-doc 집계량이라 무상태 단건 라벨러가 채울 수 없는 내적 모순(SSOT 자인) 해소. output-schema·validate·taxonomy·few-shot·SKILL 동기화.
- **`taxonomy_version` 출력 스키마 전파**(optional, default `absa-cs-1.0`) — v1→v1.5 시계열 단절 보정.
- **`other_rate` 비차단 자기진단 경고**(validate_output.py) — 기타>15%·unknown·version 혼재 시 stderr 경고(차단 아님). "기타=인텐트 신호" 데이터 기반 트리거.
- **`sub_aspect` 의미 고정** — 측면 세분 한정, 근본원인(root_cause)은 별도 직교축(흡수 금지) 명문화.
- **`resolution=unknown` 도피 가드**(few-shot 1줄).
- 신규 분류축(인텐트·근본원인·긴급도·오너십)은 **전면 거부** — IAA 측정 인프라 0 상태에서 축 추가는 검증 불가. 인텐트는 별도 자매 스킬로 분리(thesis 보존).

## 0.1.0 (2026-05-30)

- 신규(**개념 증명/PoC**): 한국어 ABSA(측면 기반 감정분석) **라벨링 코어** 스킬. Claude 직접 추론(v1, `backend=claude`). 정확도 보장·평가·대량처리·ML 백엔드는 미비(후속).
- `GUIDE.md`: 자료 없이 지침만으로 돌려보는 **샘플 지침 9종**(다측면·배치·화자분리·완곡부정·사르카즘·미언급≠중립·커스텀 taxonomy·상태축·검증) + PoC 한계 명시.
- taxonomy 정본 v1.0(`references/taxonomy.ko.yaml`) — 평면 단일계층 + `sub_aspect` 비파괴 슬롯, CS/리뷰 `domain` 게이트.
- 고정 출력 계약(`references/output-schema.json`) — aspects·process_signals(상태 축)·flags. 향후 `ml-absa` ML 백엔드 교체 가능.
- few-shot(`references/few-shot.md`) — 한국어 난점(화자귀속·존댓말 완곡부정·체념 단답·턴간 지시대명사).
- 검증기(`scripts/validate_output.py`) — stdlib only, 스키마 핵심 규칙 + taxonomy 멤버십 + 필드 모순.
- 원천: `itda-skills/ml-absa` 기획서(§5.5 taxonomy 정본, §6 스키마, §7 난점).
- 범위 밖(후속): 집계·KPI 리포트, 골드셋 평가(F1·IAA), ml-absa 백엔드 연결.
