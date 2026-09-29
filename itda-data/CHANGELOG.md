# Changelog — itda-data

## [1.2.0] - 2026-09-28

### Added

- `biz-redact` 0.3.0 — 한글(HWPX) 입력. `mask`·`verify`·`restore` 가 내용으로 HWPX 를 알아보고 서식을 보존한 채 가리며, 치환 뒤 컨테이너 전체를 다시 훑어 기밀이 남으면 exit 1·무산출(#17). 실 한컴 저장본 50건 일괄 통과.

### Changed

- `pii-redact` 0.2.0 — 주민번호 신뢰도에서 mod11 체크섬을 뺐다(2020-10 이후 발급 번호가 체계적으로 `candidate` 로 표기되던 결함). 성별 자리로 세기를 정해 달력에 없는 생년월일·미래 생년은 비검출(주민번호 라벨이 붙으면 `candidate` 로 가림), 주문·접수 같은 부정 문맥이면 신뢰도를 낮춘다. 부분 가림형(`900101-1******`) 검출 추가(#21).

### Fixed

- `synthetic-data` 0.1.2 — hwpx 채우기의 연쇄 치환·`{{항목}}` 집계 누락·서식이 갈린 run 에 걸친 placeholder 무음(#4).
- `biz-redact` 0.3.1 — description 448자 → 382자(배포 정책 상한 400자). 동작 불변(#25).
- `biz-redact` 0.3.2 · `synthetic-data` 0.1.3 — HWPX 입력의 압축 폭탄·XXE·경로 탐색 가드(hwpx 와 같은 가드·같은 환경변수, #27).
- `biz-redact` 0.3.3 — 본문 XML 이 UTF-8 이 아니거나 XML 이 깨진 HWPX 는 가리지 않고 exit 2 로 멈춘다(깨진 입력이 깨진 산출로 나가지 않게, #29).
- `data-audit` 0.4.0 · `data-verify` 0.4.0 — 먼 칸 서식 하나로 멈추던 희소 시트, 거꾸로 된·거대한 병합에서 파일을 못 열던 결함, 병합에 가려진 값의 무음 소실을 고쳤다(가려진 값·겹친 병합은 `입력` 발견으로). `data-prep` 0.2.3 — 엑셀 원본을 "CSV UTF-8 로 저장" 안내로 거부하고 설명을 CSV 전용으로 정정(#30).

## [1.1.1] - 2026-09-27

### Changed

- 제거된 xlsx 생성 스킬 지목 정리(2026-09-27) — `xlsx-recalc` 0.1.1(`[책임 경계]`·"쓰지 않을 때"·권장 체인·GUIDE), `data-audit` 0.3.1("쓰지 않을 때" 행 삭제).

## [1.1.0] - 2026-09-25

### Removed

- **hyve 선택 백엔드 절 정리 (itda-work/itda-hyve#6)** — hyve 앱이 폐기돼 열어둔 엑셀 실시간 지적 경로(`office_audit` MCP)를 뺐다. 파일 기반(openpyxl) 경로는 그대로.
  - `data-audit` 0.3.0 · `data-verify` 0.3.0 — SKILL.md·GUIDE.md 의 실시간 지적 절·Prerequisites·tags(`com`·`live-annotation`) 정리. 팩 README 의 `office_audit` 실시간 경로 광고도 지웠다. data-verify 의 수식 재계산 안내를 `xlsx-recalc` 로.

### Fixed

- `data-ask` 0.2.3 — cp949 첫 로딩 때 duckdb 확장 다운로드 진행 막대가 stdout 에 섞여 JSON 출력이 깨지던 결함(진행 막대 끔).
- `data-audit` golden 테스트 — fixture 를 hyve 저장소 `docs/specs/SPEC-XLSX-DATASKILL-BACKEND-001/golden` 에서 스킬 `tests/fixtures/golden/` 으로 옮겨 이 저장소 안에서 돈다(기존 10건 실패 해소).

## [1.0.0] - 2026-09-20

### Changed

- 팩 개명 `itda-data-analysis` → **`itda-data`** (#1703).
- `itda-cs-analysis` 흡수 — aspect-sentiment·cs-intent·iaa-builder.
- `itda-privacy-gate` 흡수 — biz-redact·pii-redact·synthetic-data.

## [0.21.0] - 2026-09-13

### Added

- **xlsx-recalc v0.1.0** (신규 스킬, #1690): openpyxl 등이 만든 캐시값 없는 xlsx 를 LibreOffice(24.8 이상) 단독으로 재계산.
  대체 엔진 7종이 모두 에러 없이 틀린 값을 내 1차 엔진은 두지 않았다. 계산 전 외부 링크 값 캐시·AF_UNIX·LibreOffice 버전을 확인하고,
  계산 후 타입별 캐시·수식 보존·외부 링크 파트 보존을 검증하며 LibreOffice 재직렬화 셀을 보고한다(stdlib, 바이너리 동봉 없음).

### Changed

- **data-audit v0.2.3**: `[책임 경계]` 추가 · 캐시값이 빈 파일의 재계산 안내를 xlsx-recalc 로 교체.

## [0.20.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-data` 개명(#1648 2단계). 스킬 구성 불변. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## 2026-09-01 (이슈 #1621) — v0.19.0

### Added

- **`agents/data-auditor.md` 신설** — data-verify·data-ask·data-prep 산출물의 수치를 원장·원 셀에서 독립 재계산하는 읽기 전용 감사자. tools `Read, Grep, Glob, Write, Bash, mcp__workspace__bash`(산출은 `outputs/data-audit-report.md` 1개), 최종 텍스트는 공통 AUDIT_SCHEMA JSON(`verdict`·`findings`·`recomputed`·`unverifiable`, critical 1건 = FAIL). `data-verify` v0.2.3 에 권장 체인 절 추가. 계약: `cowork-agent-orchestration.md` §감사자.

## 2026-07-26 (이슈 #1280·#1281·#1282·#1283)

### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.

## 2026-07-26 (이슈 #1279)

### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: data-ask 0.2.1 · data-audit 0.2.1 · data-compass 0.1.1 · data-prep 0.2.1 · data-verify 0.2.1.

## [0.18.0] — 2026-07-26 (data-compass 신설, #1271)

### New Features
- **data-compass v0.1.0** (신규 스킬): 데이터 분석 **내비게이터(순수 코치)** — 유저가 Claude 를 가이드하는 대신 Claude 가 유저를 가이드한다. 초기 2문항(데이터 위치·관심사, "몰라요" 유효)만 묻고, 데이터를 프로파일해 **분석 지도**(`<이름>-분석지도.md`: 지형·갈 수 있는 길·현재 위치·여정 로그)를 생성, 매 단계 "이렇게 말해보세요" 복붙 지시문으로 안내한다. 강의(교육) 용도 — 지시하는 법(프롬프트 리터러시)을 익히는 게 목적이라 **분석을 대신 실행하지 않는다**(자동 진행 금지 [HARD]).
  기존 4스킬의 관제탑: 품질 신호→data-prep, 집계/추이→data-ask, 합계성 컬럼→data-verify, 엑셀→data-audit 라우팅. stdlib only·cp949 대응·결정론 초기 지도(같은 데이터·관심사 → 같은 지도, 강의 재현성). id/pii 컬럼은 분석 축 추천에서 제외(data-ask 양심 계승). 라이브 실측 회귀 반영: 관심사 부스트가 있어도 정돈 경로는 맨 앞 고정, 여정 시작 추천에서 [보고] 제외. 19 tests GREEN(unit + deployed-style 재현성 바이트 대조).
- **data-profiler 에이전트** (플러그인 첫 에이전트): data-compass 가 명시 디스패치하는 프로파일링 전용 서브에이전트 — 격리 컨텍스트에서 지도 파일 산출, 대화에는 포인터+요약만(파일 릴레이, cowork-agent-orchestration 준수: tools 생략·입출력 계약·에러 핸들링 명시).

## [0.17.0] — 2026-07-07 (data-verify 신설, #967)

### New Features
- **data-verify v0.1.0** (신규 스킬): 데이터 **수치 검수** — data-audit(수식 구조·오류)와 구분되는 "값이 실제로 맞나" 검수 4종: 내부정합(소계/총계↔구성요소 합)·규칙위반(음수/범위/중복키/sum_to)·외부대조(원장 정답셋)·교차참조(시트 간 짝).
  정확성(data-accuracy): 허용오차 비교(눈대중·정확 `==` 금지)·통화/천단위/% 파싱·합계행을 규칙 검수에서 제외(sum_to 이중계산 방지). loader 가 Grid 만 공급하고 verifiers 는 순수함수인 백엔드 독립 설계(#968 COM/OpenXML 백엔드 재사용 대비). 9 tests GREEN(4종 unit + deployed-style + 오탐/이중계산 가드).

## [0.16.0] — 2026-07-07 (data-prep clean-data-xls 흡수, #951)

### New Features
- **data-prep**: Claude for Excel 의 clean-data-xls 고유 정제 흡수 — mojibake 복구(Ã©→é)·casing 통일(usa/USA→최빈 원형)·통화/천단위 숫자화($1,200→1200, 선행 0·% 보존으로 보수적). diagnose 에 mixed-type 열 경고 추가([가설], 변환 아님) — 통화표기는 number_as_text 정제로 해소되므로 숫자로 인정해 "정제하면 사라질 것" 오판을 차단.

### Improvements
- **data-prep emit**: cleanse 파이프라인 미배선 발견·배선 — trim·mojibake·숫자화·casing·날짜·중복 정제가 정돈본에 실제 반영. transform_log 에 정제 통계(`cleanse_stats`) 반환. 기존 4관문·cp949·원본 불변·결정론 모델 불변(기능 추가만). 29 tests GREEN.

## [0.15.0] — 2026-07-07 (data-audit 신설 — audit-xls 이식, #952)

### New Features
- **data-audit v0.1.0** (신규 스킬): Claude for Excel 의 audit-xls 를 itda-data 로 이식한 엑셀 **수식·데이터 감사**. openpyxl 양면 로드(수식면 `data_only=False` · 값면 `data_only=True`)로 수식오류(#REF! 등)·수식 내 하드코드(=A1*1.05)·이웃과 다른 수식·off-by-one 범위·복붙된 값·순환참조·깨진 시트 링크·단위/스케일 급변·숨긴 행/시트를 감사.
  수식 문자열 기반 감지라 openpyxl 재계산 한계와 무관. 보수적 판정(오탐 회귀 가드: #REF!→시트링크 오인 차단·사소한 상수 제외·다수 패턴 60%↑일 때만 불일치 판정). 재무모델 무결성(BS balance·cash tie-out·DCF/LBO 등)은 범위 외(#952 스코프). 19 tests GREEN(unit + deployed-style subprocess 격리).

## [0.14.0] — 2026-06-25 (데이터 vertical 졸업, #567)

### Breaking Changes
- **advisor/tidy 폐기 → data-ask/data-prep 승격**: itda-egg 인큐베이션의 `data-ask`(질문)·`data-prep`(정리)를 itda-data 로 졸업시키고, 기존 `data-analysis-advisor`·`data-tidy-advisor` 는 폐기(SPEC-DATA-VERTICAL-001 이 구 thesis SPEC ADVISOR-001·TIDY-001 을 대체). itda-data 를 데이터 양심 vertical 로 재정의.
  - 영향: 구 advisor/tidy 스킬 사용자는 data-ask/data-prep 으로 전환해야 함. README·lessons·market-scan 크로스레퍼런스 data-ask 로 정정, release-skills.yml OS_NEUTRAL_DIRS·requirements·marketplace 갱신. 새 위치 테스트 55 GREEN(38+17).

## [0.13.0] — 2026-05-31 (CS 스킬 분리 → itda-cs 신설, #28·#29)

### Breaking Changes
- **CS 도메인 스킬 2종 분리**: `aspect-sentiment`·`cs-intent`를 신규 플러그인 **`itda-cs`**로 이동(`git mv`, 코드 무변경). itda-data는 **일반 데이터 분석 전용**(`data-analysis-advisor`·`data-tidy-advisor`)으로 정리.
  - 분리 근거: 응집도(통계 양심 게이트 vs CS 텍스트 분류)·반복 주기·PII 민감도·`ml-absa`(PRIVATE) 백엔드 핸드오프가 일반 분석과 상이.
  - `plugin.json`: description에서 ABSA·인텐트 문구 제거, CS keywords(`감정분석`·`측면감정`·`absa`·`aspect-sentiment`·`상담분석`·`인텐트분류`·`문의유형`·`intent`·`cs-intent`) 제거.
  - 영향: itda-data를 통해 두 CS 스킬을 사용하던 사용자는 `itda-cs` 플러그인을 설치해야 함.

## [0.12.0] — 2026-05-30 (SPEC-CS-INTENT-001)

### New Features
- **cs-intent v0.1.0** (신규 스킬, PoC): CS 문의 **인텐트(문의유형) 분류**. `aspect-sentiment`의 자매 — 직교("왜 연락했나" vs "무엇에 대해 어떻게 느끼나"). 같은 doc 병행 가능.
  인텐트 10군+기타 · `primary_intent`+`secondary_intents`+`multi_intent` · stdlib 검증기 · `other_rate` 자기진단 · 운영 졸업 IAA 측정 게이트 명시.
  원천: aspect-sentiment 목적-적합성 검토(#26 → 자매 분리 #27). 스킬 CHANGELOG 참조.

## [0.11.1] — 2026-05-30 (SPEC-ABSA-SKILL-001 — 목적-적합성 검토 반영)

### Improvements
- **aspect-sentiment v0.1.1**: "통계+대처 목적-적합성" 11-에이전트 검토 결과 **계약 정합성** 수정(축 추가 없음).
  `reopen_count` 단건 출력 제거(→집계 레이어, SSOT 내적 모순 해소) · `taxonomy_version` 출력 전파(시계열 단절 보정) ·
  `other_rate` 비차단 자기진단 경고(기타>15% stderr) · `sub_aspect` 의미 고정(근본원인 흡수 금지) · `resolution=unknown` 가드.
  신규 분류축(인텐트·근본원인·긴급도)은 IAA 측정 인프라 부재로 전면 거부, 인텐트는 별도 자매 스킬로 분리. 스킬 CHANGELOG 참조.

## [0.11.0] — 2026-05-30 (SPEC-ABSA-SKILL-001)

### New Features
- **aspect-sentiment v0.1.0** (신규 스킬): 한국어 측면 기반 감정분석(ABSA) 라벨링 코어.
  Claude 직접 추론(`backend=claude`), 무상태 단건 처리·closed-set taxonomy(평면 단일계층 +
  `sub_aspect` 슬롯)·화자분리(CS, 고객 발화만)·상태 축(`process_signals`)·고정 출력 계약.
  `references/`(taxonomy.ko.yaml·output-schema.json·few-shot.md) + `scripts/validate_output.py`(stdlib).
  원천: `itda-skills/ml-absa` 기획서. 향후 ml-absa ML 백엔드 교체 가능. 자세한 내용은 스킬 CHANGELOG 참조.

## [0.10.0] — 2026-05-28 (SPEC-DATA-ADVISOR-CLI-001)

### New Features
- **data-analysis-advisor v1.3.0**: `dispatch.read_table(path)` 사용자 CSV/TSV/XLSX
  reader 신설. SKILL.md를 tidy 패턴(Python API form)으로 재작성하여 `python3 scripts/X.py`
  silent no-op 광고 6건 제거. 광고-코드 정합 lint 게이트(`test_skill_md_advertised_surface`)
  + deployed-style 종단 테스트(`test_deployed_style_handoff`) 신설. 자세한 내용은
  data-analysis-advisor CHANGELOG 참조.

## [0.9.1] — 2026-05-20 (SPEC-DATA-HARDEN-001 v0.3.1)

### Breaking Changes

- **Gate4·Gate5 코드 강제력 격상 (OQ-1=Path A)**: 광고된 "5관문 양심 게이트" 중 Gate4(dispatch)·Gate5(verify)가 이전까지 SKILL.md prompt 디스플린에만 의존(코드 강제력 0). `gate_orchestrator.py`에 `run_gate4`/`run_gate5` 함수 신설 + `from . import dispatch`/`from . import verify` 추가 + production 호출 체인 fail-loud(예외 또는 blocked status). thesis 50% 미구현 → 100% 코드 강제. 결과: 사용자가 LLM 우회 시도해도 Python 레이어에서 차단됨.
- **HARD 게이트 우회 차단**: `gate_orchestrator.py:49` `interview.get("answered", True)` → `False`. `causal_needed`/`error_cost` 키도 기본 False. 빈 dict 또는 키 누락 dict가 이전엔 Gate3 통과 가능했으나 이제 모두 blocked. 영향: `interview` payload 불완전 시 호출 즉시 차단(이전 행동에 의존하던 외부 코드 없음).

### New Features

- **`coerce_table_rows` 수집 경계 함수 (advisor)**: CSV 문자열 숫자 → int/float 자동 변환. column-wise 타입 추론(numeric/datetime/categorical) + 값 강제(whitespace→None). OQ-2 다신호 휴리스틱(컬럼명 패턴 `id`/`_id`/`code`/`zip`/`account`/`phone` OR 선행0 표본 1행+ OR 자릿수≥5)으로 ID/우편번호 자동 보호 + `protect_columns: list[str] | None` 명시 오버라이드 인자. stdlib only.
- **tidy→advisor 핸드오프 통합 테스트**: `test_handoff_integration.py` (data-analysis-advisor). raw messy CSV → tidy `emit_tidy()` → tidy_*.csv → `coerce_table_rows` → `build_profile_card` → status="분석 가능" 종단 실집행. mock 없음. 6/6 PASS.
- **GUIDE.md ×2**: data-analysis-advisor(134줄, "거부 결과를 받았다면" 섹션 포함) + data-tidy-advisor(120줄, "어떤 엑셀이 들어오면 무슨 일이 일어나는가"). itda-work email/blog-reader 표본 참고.
- **`honest_report` "다음 단계" 섹션**: advisor 거부 응답 시 tidy 권유, tidy 완료 시 advisor 권유. 사용자 이탈 방어.

### Improvements

- **CELL_N_* SSOT 일원화**: `verify.py:29-30` 독립 선언 제거, `from .profile_card import CELL_N_CRITICAL, CELL_N_CAUTION`. identity 회귀 테스트(`verify.CELL_N_CRITICAL is profile_card.CELL_N_CRITICAL`). 한쪽만 변경 시 무음 발산 위험 제거.
- **고cardinality ID 컬럼 status 판정 로직**: `profile_card.py`에 `has_sufficient_numeric` 검사 추가. 수치 컬럼이 N≥CELL_N_CAUTION + missing<0.5인 경우 단일 ID/범주 컬럼이 전역 "분석 불가" 강제 못 함. per-column status에서 "분석 보조 정보 없음" 표기, 전역 status에 전파 금지.
- **약단언 → 강단언 교체 (NFR-5)**: `test_profile_card.py:87` `assertIn(col_type, {"numeric", "categorical", ...})` → x1/x2/y per-column `assertEqual("numeric")`. 약단언이 "categorical도 valid label"로 허용해 #1 회귀를 가렸던 인과 제거.
- **`plugin.json` keywords 도달성**: `엑셀정리`·`데이터정돈`·`소계`·`헤더`·`tidy`·`구조진단` 6개 tidy 키워드 추가. 이전 keywords 10/10이 advisor계열(`5관문`·`거부게이트`·`파레토`·`conscience-gate`) 편향으로 data-tidy-advisor가 플러그인 단위 검색에서 사실상 비가시였음. advisor/tidy 균형 확보.
- **두 SKILL.md description 재작성**: 첫 1문장 사용자 자연어 트리거("데이터 분석 방법을 물어보거나 CSV·시트를 보여주면 적합한 분석 기법을 추천", "지저분한 엑셀·CSV 파일을 보여주면 구조 문제를 진단하고 정돈본을 새 파일로 만들어 드립니다"). 첫 2문장 내 금지어(`5관문`·`양심 게이트`·`[가설]`·`3단계 게이트`·`conscience-gate`·`EDA`·`tidy_*.csv`·`오케스트레이터`·`정직 보고`) 0건. 내부 메타포는 description 뒤쪽 또는 metadata.tags로 이동.

### Bug Fixes

- **CSV 문자열→categorical 오거부 (S0, 결함 #1)**: `_classify_value`가 `'15'`(str)→categorical, `15`(int)→numeric으로 분류해 CSV 6행 숫자 데이터 전 categorical로 잡혀 status="분석 불가" 강제. 광고된 2스킬 파이프라인(tidy→advisor) 확정 단절. `coerce_table_rows` 수집 경계로 해소(3회 독립 재현 완료).
- **종단 핸드오프 영구 false-skip (자기보고 falsify 적중)**: `test_handoff_integration.py:29` `_ADVISOR_SCRIPTS.parent.parent.parent`(3 levels up)이 존재하지 않는 `itda-data/data-tidy-advisor/scripts`를 가리킴 → `_TIDY_SCRIPTS.is_dir()` 영구 False → `test_full_pipeline_tidy_then_analyze`(REQ-012 단일 최고 레버리지) 영구 skip. evaluator-active 적대 재검증으로 적발, `.parent.parent`로 1줄 외과 수정 → 종단 파이프라인 실집행 성공.
- **vacuous mock 제거**: `test_integration.py:532` `mock_agent.assert_not_called()` 호출 경로 부재로 vacuous하게 항상 참. real-path test로 교체.
- **인코딩 잔재**: `분析`(한국어 분 + 중국어 析 혼용) → `분석`(순한국어) 18개소 일괄 교체.

### 도달성

- **GUIDE.md 신설**: 두 스킬 모두 GUIDE.md 없었음(itda-work 10+ 스킬은 전부 보유). 추가로 사용자가 "거부 결과를 받았다면" 다음 행동(EDA로 축소, 정본기법 채택, 데이터 보강) 안내 부재 → advisor GUIDE에 무조건 포함.
- **`marketplace.json`·루트 README**: 이전엔 "5관문 통계 양심 게이트"만 언급 → 두 스킬(통계 양심 + 구조 양심) 명시.

### 측정 가능한 효과

- 테스트: 484 → **557** passed (신규 73). 0 failed / 0 skipped (이전 1 skip이 thesis core 가렸음).
- AC: 0/13 → **13/13 PASS** (라이브 재현 + grep 강제력 + evaluator-active 적대 재검증 3중 게이트).
- 결함: 8 High 전부 해소. 잔재(부속): AC-3 조건부·AC-11 부속(후속 마이너 후보).
- 토큰: description 내부 메타포 30~40% → 첫 2문장 금지어 0건.

### Traceability

- SSOT: `docs/reviews/itda-data-evaluation-2026-05-20.md` (6경로 교차검증)
- SPEC: `.specs/SPEC-DATA-HARDEN-001/spec.md` v0.3.1
- commits: `3c7af93` (TDD 본체, 20 파일 +1698/-47) + `11a87c7` (AC-12·AC-6 외과 수정)
- 연계 SPEC: SPEC-DATA-ADVISOR-001 v0.7.0·SPEC-DATA-TIDY-001 v0.2.0 status 재오픈 없음 (EXC-4)

---

## 흡수 이력 — itda-cs-analysis

> #1703 재편으로 이 팩이 흡수되었다. 아래는 흡수 시점까지의 itda-cs-analysis 변경 이력이다.

## Changelog — itda-cs

## [0.3.0] - 2026-09-06

### Changed

- **플러그인 재정비 2·3단계 (#1648)** — 구 `itda-cs` 개명(#1648 2단계). pii-redact 는 `itda-privacy-gate` 로 이관 — 이 팩 스킬은 `itda-privacy-gate:pii-redact` 를 별도 팩 계약으로 지목한다. 폐기 이름은 별칭 없이 제거(마스터 결정 2026-09-05). 게이트: check_plugin_registry · check_plugin_refs(신설) · 카탈로그 · publish dry-run.

## 2026-07-26 (이슈 #1280·#1281·#1282·#1283)

### Changed

- **플랫폼 문서 정비 4축 일괄 (#1280·#1281·#1282·#1283)** — ① compatibility 라벨을 실태 정합(`Claude Code & Cowork` 표준, 역방향 라벨 교정) ② 설치 지시에서 `uv pip install --system`·`curl|sh` 제거(`python3 -m pip` 정본, 스크립트 안내 문자열·README 포함) ③ `.env` 안내를 양 플랫폼 병기(SKILL.md+GUIDE.md, 셸 env·`~/.claude/settings.json` env 명시) ④ `allowed-tools` 의 표준명 `Bash`/`WebFetch` 에 Cowork 실명(`mcp__workspace__bash`/`mcp__workspace__web_fetch`) 병기(73스킬) + brain `Task`→`Agent`, MCP 소비 4스킬은 필드 삭제(전체 상속). 세부 버전은 각 스킬 CHANGELOG 참조.

## 2026-07-26 (이슈 #1279)

### Changed

- **실행 경로 SKILL_DIR 규약 표준화 (#1279)** — SKILL.md 실행 명령을 SKILL_DIR 확정 블록(Code=`$CLAUDE_PLUGIN_ROOT/skills/<skill>` / Cowork=세션 마운트 find) 기준으로 통일. cwd 상대경로·저장소 경로·플레이스홀더 표기 제거. 대상: aspect-sentiment 0.1.4 · cs-intent 0.1.3 · iaa-builder 0.1.2 · pii-redact 0.1.2.

## [Unreleased] (cs-batch-extractor 서브에이전트 신설 — ABSA·인텐트 대량 병렬 추출, #1140)

### New Agent — 대량 배치 팬아웃/팬인 부품
- **cs-batch-extractor** (`agents/cs-batch-extractor.md`): `aspect-sentiment`·`cs-intent` 의 대량 배치에서 Lead 가 청크 단위로 명시 디스패치하는 무상태 워커. 격리 컨텍스트에서 청크의 각 항목을 독립 라벨링해 두 스킬의 고정 JSON 스키마 호환 JSONL 을 `outputs/` 에 쓰고, 텍스트로는 경로·건수만 반환(본 대화 원문 오염 0).
  - 목적은 **처리량(청크 병렬)+격리**뿐 — 통계 주장 없음(κ·IAA·독립 어노테이터 무관). 기각된 labeler(이중 라벨 κ 측정)와 다르다.
  - 두 스킬의 화자분리(고객 발화만)·closed-set·무상태 단건·고정 출력 계약을 그대로 승계. closed-set 이탈 라벨은 taxonomy catch-all `기타` 로(literal `미분류` 금지 — 집계 스크립트 out-of-taxonomy 회피). 스키마 불일치 항목은 skips 사이드카에 기록 후 스킵.
  - frontmatter 는 name·description 만(tools 생략 = 전체 상속, Cowork tools 이름 함정 회피). 근거 독트린: `.claude/rules/itda/skills/cowork-agent-orchestration.md`.

### Changed
- **aspect-sentiment SKILL.md**: '대량 배치 (팬아웃/팬인)' 절 추가 — 30건+ 는 Lead 가 청크(JSONL) 분할 → `cs-batch-extractor` 병렬 디스패치 → `validate_output.py` 로 검증·병합(팬인=Lead+스크립트 소유). 부재 환경 순차 단건 폴백. 단건 절차·스키마·taxonomy 불변.
- **cs-intent SKILL.md**: 동일 '대량 배치 (팬아웃/팬인)' 절 추가(task=cs-intent).

### Hardened (Codex R2 적대 리뷰 보완 — #1140)
- **aspect-sentiment 0.1.2→0.1.3 · cs-intent 0.1.1→0.1.2**: 두 `validate_output.py` 가 output-schema 의 top-level(및 aspect-sentiment `aspects[]`) `additionalProperties:false` 를 **실제 강제** — 기존 파서가 extra 필드를 조용히 통과시켜 스키마 계약이 실효 없던 것을 교정(Codex 실증). 허용 필드 집합 + `flags`/`confidence`/`domain` 타입·enum 검사 + 회귀 테스트(`tests/`) 신설. 스킬 CHANGELOG 참조.
- **cs-batch-extractor.md**: (7) 화자 제한을 `task=aspect-sentiment` 측면·극성 전용으로 정정(cs-intent 는 전체 멀티턴 문맥 허용, evidence 만 문의 목적 근거로 제한). (8) 커스텀 taxonomy 관철 — 입력 계약에 커스텀 경로(선택) + 자기 게이트·Lead 팬인을 `validate_output.py <jsonl> [taxonomy]` 로. (10) 참조 파일 폴백 탐색을 task 별 경로(`*itda-cs/skills/{aspect-sentiment,cs-intent}/*`)로 분리 + 필요 파일 3종 존재 확인.

## [0.2.0] — 2026-06-01 (PII 비식별화 게이트 신설, epic #28 로드맵 1순위, #33)

### New Skill — 두 번째 동반 인프라 (#33)
- **pii-redact v0.1.0**: 한국 CS 텍스트의 개인정보(PII)를 LLM에 넣기 전 결정론 룰로 검출·마스킹. epic #28 로드맵 1순위 인프라.
  - raw CS 로그를 Claude/외부에 붙여넣는 순간 PII가 유출된다 → "익명화한다"는 사람 디스플린을 코드 강제력으로 전환. 근거: ml-absa 기획서 §6.5.
  - **결정론 로컬 우선**: raw를 LLM에 먼저 넣지 않는다. 전화·이메일·주민번호·사업자번호·카드·계좌·운전면허·여권·주소 검출. 체크섬(주민 mod11·카드 Luhn)은 필터 아닌 confidence 태그. 플레이스홀더(`[전화_1]`) + 문서 내 일관 가명화. stdlib only.
  - **재현율 우선**: 누락 < 과제거. 카드 bare·계좌는 강한 구조·문맥 없으면 마스킹 보류(투명 기록) — 주문번호 과탐 방지.
  - 모든 CS 분석(aspect-sentiment·cs-intent)의 안전 입구 전처리. 단위 27 passed + 합성 로그 종단. 스킬 CHANGELOG 참조.

### Changed
- plugin.json description에 PII 비식별화 게이트 추가, keywords에 PII·비식별화·개인정보·마스킹·redact·privacy 추가. 플러그인 버전 0.1.0 → 0.2.0.

## [0.1.0] — 2026-05-31 (itda-cs 신설 — itda-data에서 CS 스킬 분리, #28·#29)

### New Plugin
- **itda-cs 신설**: CS 상담·문의 텍스트 분석 전용 스킬팩. `itda-data`(일반 데이터 분석)에서 CS 도메인 스킬 2종을 분리.
  - 분리 근거: 응집도(통계 양심 게이트 vs CS 텍스트 분류)·반복 주기·PII 민감도·`ml-absa`(PRIVATE) ML 백엔드 핸드오프가 일반 분석과 다름.
  - codex consult + 자체 비판 검토 수렴: "두 분류기만 옮기는 분리는 cosmetic split" → IAA 빌더(인프라 스킬) 동반으로 "CS 워크플로우 홈" 정의(#30 후속).

### Migrated Skills (코드 무변경, `git mv` 이동)
- **aspect-sentiment v0.1.1**: 한국어 측면 기반 감정분석(ABSA). `itda-data/skills/` → `itda-cs/skills/`.
- **cs-intent v0.1.0**: CS 문의 인텐트 분류. `itda-data/skills/` → `itda-cs/skills/`.

두 스킬의 references·scripts는 무변경. 상대경로(`../references/`)·stdlib only로 플러그인 이동에 자동 대응. SKILL.md는 IAA 게이트를 `iaa-builder`로 구체 링크하도록만 보강.

### New Skill — 첫 동반 인프라 (#30)
- **iaa-builder v0.1.0**: CS 분류 라벨의 어노테이터 간 일치도(IAA)를 Cohen·Fleiss κ로 측정. cosmetic split을 피하고 itda-cs를 "CS 워크플로우 홈"으로 정의하는 첫 인프라.
  - 기존 두 스킬의 "운영 졸업 IAA 측정" 게이트가 측정 수단 없이 문서로만 존재(벽장 안전망) → 이 스킬이 실행 가능하게 만든다.
  - 결정론 κ 코어(`iaa.py`) + 골드셋 층화 샘플링(`sample.py`) + 리포트 검증(`validate_output.py`). stdlib only.
  - 단위 24 passed(Wikipedia Cohen κ=0.40·Fleiss 손계산 κ=0.5497 대조 + 핸드오프 종단). 스킬 CHANGELOG 참조.

---

## 흡수 이력 — itda-privacy-gate

> #1703 재편으로 이 팩이 흡수되었다. 아래는 흡수 시점까지의 itda-privacy-gate 변경 이력이다.

## Changelog — itda-privacy-gate

## [0.1.1] - 2026-09-06

- **synthetic-data 0.1.1 (#1647)** — Windows cp949 stdout 크래시 수정(파이프 리다이렉트 시 `show`·`validate`·`generate` rc=1) + 사람 실측 픽스처.

## [0.1.0] - 2026-09-05

- **팩 신설 (#1648 1단계)** — 플러그인 재정비 지도 v0.5 의 `itda-privacy-gate`. 목적 축은 "외부 AI 에 넣기 전 보호 게이트"(마스킹·복원·가상 데이터). pii-redact(itda-cs) 이관은 2단계.
- **biz-redact 이관** — `itda-work/skills/biz-redact` → `itda-privacy-gate/skills/biz-redact` (v0.2.1, 내용 불변 · 경계 표기만 갱신). 구 참조 `itda-work:biz-redact` 는 즉시 제거(마이그레이션 없음 — 마스터 결정 2026-09-05).
- **synthetic-data 신설 (#1647)** — 사용자 문서 구조만 인터뷰로 받아 같은 구조의 가상 데이터를 생성. 프리셋(`presets/<도메인>/<문서>.json`) 요양병원 4종 + 노인장기요양 4종, 프리셋 검증기·공통 식별자 생성기·규칙 검증 리포트·항목 정의표·xlsx/hwpx 서식 채우기·한계 고지 2종.
