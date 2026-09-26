# 프리셋 / 스펙 JSON 스키마 (schema_version 1.0)

프리셋(`presets/<도메인>/<문서>.json`)과 사용자가 고친 스펙(`spec.json`)은 같은 스키마다. 정본은 `scripts/synth.py` 의 `validate_spec` — 이 문서는 형식과 근거를 설명한다.

## 최상위 키 (`seed_examples` 외 전부 필수)

| 키 | 내용 |
|---|---|
| `schema_version` | `"1.0"` |
| `domain` / `document` | 프리셋 경로와 일치(`nursing-hospital` / `admission-ledger`). 스펙의 fields·rules 가 같은 이름의 프리셋과 동일하면 "프리셋 그대로 생성" 고지가 붙는다 |
| `title` | 한글 문서명 — xlsx 시트명·리포트 제목 |
| `format` | 기본 서식 `xlsx` · `hwpx` · `docx` |
| `fields[]` | 항목 정의(아래) |
| `rules[]` | 항목 간 규칙(아래) — 검증 리포트가 이 목록을 그대로 센다 |
| `reid_keys[]` | 재식별 게임용 준식별자 조합(항목명, 실재해야 함) |
| `legal[]` | `{law, article, note, status}` — status 는 `확인`(hyve-training `legal-basis.md` 확인본) 또는 `확인 필요` |
| `seed_examples[]` | 사용자가 손으로 친 **가짜** 예시 행(선택 — 키 자체는 생략 가능). `choice` 후보에 값이 편입된다. 자유텍스트 항목의 예시는 거부(철칙 2), 검증식 통과 주민번호·부여 가능 휴대전화가 있으면 실제 데이터 의심으로 RED |
| `preset_notice` | 프리셋 한계 고지 — 코드의 `PRESET_NOTICE` 와 **바이트 동일**해야 한다(변조 = RED) |

## `fields[]`

| 키 | 내용 |
|---|---|
| `name` | 항목명(중복 금지). xlsx 헤더·hwpx placeholder `(항목명)` 의 키 |
| `type` | `string` · `int` · `float` · `date` · `text` |
| `grade` | **필수** — `식별자` · `민감정보` · `준식별자` · `비개인정보` |
| `generator` | 아래 생성기 중 하나 |
| `free_text` | `true` 면 자유텍스트 — generator 는 `free_text` 여야 하고 값은 placeholder 로 나온다(`fill-text` 로 AI 문장 치환) |
| `desc` | 항목 정의표에 실리는 설명 |

### 생성기 `generator.kind`

| kind | 옵션 | 뜻 |
|---|---|---|
| `sequence` | `prefix` `start` `width` | 일련번호 `P01001` |
| `person_name` | `dup_ratio`(기본 0.06) | 가상 성명 + 동명이인 의도 삽입 |
| `rrn` | `birth_from` `gender_from` | 검증자리 고의 불일치 주민번호(생년월일·성별 항목과 정합) |
| `phone` / `address` | — | 예약 대역 / 가상 지명 |
| `choice` | `values` `weights` `empty_when_empty` | 후보 중 택1. `empty_when_empty: "퇴원일"` 이면 그 항목이 빈칸일 때 빈칸 |
| `int` / `float` | `min` `max` (`digits`) | 범위 난수 |
| `date` | `start` `end` | ISO 날짜 |
| `date_after` | `from` `min_days` `max_days` `null_ratio` | 기준일 이후 날짜. `null_ratio` 만큼 빈칸(재원 중 등) |
| `derive` | `fn` `args` (+`length` `map`) | 파생값 — `days_between(a,b)` · `sum(...)` · `diff(a,b)` · `prefix_map(src)` · `age_from(birth[,ref])` |
| `code` | `pattern` | `#`=숫자 `A`=대문자 (`L##########`) |
| `time_slot` | `values` | 근무조 등 |
| `free_text` | — | placeholder |
| `const` | `value` | 고정값 |

참조(`from`·`args`·`birth_from`·`gender_from`·`empty_when_empty`)는 실재 항목이어야 하고 순환이면 에러다. 생성 순서는 참조를 따라 자동 정렬된다.

## `rules[]` (각 규칙에 `id`·`desc`)

| kind | 키 | 검증 |
|---|---|---|
| `compare` | `left` `op` `right` | `<` `<=` `==` `>=` `>` `!=` — 한쪽이 빈칸이면 비교하지 않는다 |
| `derived` | `field` `fn` `args` | 파생값 재계산과 일치 |
| `prefix_map` | `field` `from` `length` `map` | `from` 앞 N자 → `map` 값 |
| `unique` | `field` | 중복 없음 |
| `in_set` | `field` `values` | 허용값 |
| `not_empty` | `field` | 필수 |
| `empty_iff` | `field` `with` | 두 항목이 함께 비거나 함께 찬다 |

## 개인정보 등급 (1교시 판단 기준표)

| 등급 | 뜻 | 예 |
|---|---|---|
| 식별자 | 단독으로 개인을 특정 | 이름·주민번호·연락처·주소·환자번호 |
| 민감정보 | 개인정보 보호법 제23조 — 건강 등 | 진단·분류군·등급·상담 내용 |
| 준식별자 | 결합하면 특정 가능(법 제2조 제1호 나목) | 병실·입원일·생년월일·성별 |
| 비개인정보 | 개인과 무관 | 집계값·근무조 |
