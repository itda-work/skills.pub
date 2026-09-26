# 원장(ledger.json) 스키마 — 에이전트 저작 가이드

원장은 데이터셋의 **단일 진실 소스(SSoT)**다. 모든 문서 값·함정·정답지가 원장에서 파생된다.
에이전트(당신)는 **원장만 저작**하고, 문서 렌더·검증·정답지는 Python 이 결정론으로 수행한다.
문서 값을 원장 밖에서 창작하지 않는다 — 원장에 없는 값은 데이터셋에 존재할 수 없다.

`scripts/generate.py` 가 이 원장을 렌더하고, `scripts/verify.py` 가 원장 ↔ 생성물을 재대조한다.
`bf_common.validate_ledger()` 가 아래 계약을 강제한다(위반 시 exit 2 + "어느 필드가 왜").

---

## 최상위 구조

```jsonc
{
  "schema_version": "1",
  "profile":  { … },        // 필수 — 업체/주체 (가상 명칭만)
  "entities": { … },        // 선택 — 거래처·제품 등
  "series":   { … },        // 선택 — 수치 시계열·대장
  "canon":    { … },        // 선택 — 함정이 대조하는 정본 값(이름→숫자)
  "documents": [ … ],       // 필수 — 렌더할 문서 전건(최소 1개)
  "consistency": [ … ],     // 선택 — 파생 계산 재검증(합계·곱·차)
  "traps":    [ … ],        // 선택 — 함정(의도된 편차/구조)
  "baits":    [ … ]         // 선택 — 오탐 미끼(모순 아님 선언)
}
```

> [HARD] `profile.company`·`entities`·인물명·상표는 **전부 가상**이어야 한다. 실존 상호·인명·브랜드 금지.

### profile

```json
{ "company": "가상 업체명(주)", "description": "무엇을 하는 회사인가",
  "ceo": "가상 대표명", "founded": "2014", "headcount": 22, "annual_revenue": "48억" }
```

`company` 만 필수. 나머지는 정답지 세계관 요약에 쓰인다.

### entities (선택)

```json
{ "customers": [{"name": "가상 매출처"}],
  "suppliers": [{"name": "가상 매입처"}],
  "products":  [{"code": "WM-100", "name": "온열매트", "unit_price": 128000}] }
```

`products[].unit_price` 는 정답지에 "제품(단가)" 로 표기된다.

### series / canon (선택)

- `series` — 시계열 대장. `{"monthly_sales_2026": {"2026-01": 218, …}}`. 정답지 "정본 숫자" 에 나열.
- `canon` — 함정이 대조하는 **정본 값(이름→숫자)**. `{"a4_contract_price": 19800}`. trap 의 `canon` 서술과 함께 쓴다.

---

## documents[] — 렌더할 문서 전건

공통 필수 필드: `path`(폴더 포함 **상대경로**, posix), `type`, `internal_date`(`"YYYY-MM-DD HH:MM"`).
`internal_date` 는 **파일 mtime 으로 박힌다**(verify ③축). 버전 함정의 최신성 단서다.

> [HARD] `path` 는 출력 폴더 기준 **상대경로**만 허용한다. **절대경로**(`/`·`C:`)와 **경로 탈출**(`..` 로 폴더 밖)은 스키마 검증이 명시 거부한다(출력 폴더 밖 파일 덮어쓰기 차단). 또한 정규화 시 같은 물리 파일이 되는 **중복 경로**(`a/../same.txt` ↔ `same.txt`)도 거부한다. `~$` 잠금 파일명 등 정상 상대경로는 통과한다.

| type | 본문 필드 | 렌더 |
|------|-----------|------|
| `docx` | `title`(str), `blocks`[] | 제목 + 문단/제목/표 |
| `xlsx` | `sheets`{시트명: rows[][]} | 시트별 행(첫 행 헤더 관례) |
| `pptx` | `slides`[{title, bullets[]}] | 첫 장=표지, 이후 본문 |
| `pdf`  | `title`(str), `lines`[str] | 한글 텍스트 레이어 PDF |
| `txt`  | `content`(str) | 평문 |
| `csv`  | `rows`[][] | CSV |
| `broken` | (선택 `note`) | 손상 zip(열기 실패 — 문제파일 함정) |
| `lock` | (선택 `note`) | `~$` 오피스 잠금 임시파일(문서 아님) |

`blocks[]` 각 원소: `{"kind": "p"|"h", "text": "…"}` 또는 `{"kind": "table", "rows": [[셀…], …]}`.
셀·라인의 **숫자는 verify ①축이 재파싱해 전수 대조**한다. 콤마 표기(`"19,800"`)와 순수 숫자(`19800`) 모두 19800 으로 인식된다.

> **v1 한계 — 값은 양수 정수 권장.** verify ①축은 **정수 존재(membership)**로 대조하므로, **부호(음수) 검증은 v1 비대상**이다(`11500` → `-11500` 부호 반전 변조는 게이트가 잡지 못한다). 게이트의 목적은 렌더러 결함·원장↔문서 drift 검출이지 임의 변조 방어가 아니다(하이픈은 날짜 범위 표기라 부호 휴리스틱은 거짓 FAIL 위험이 커 채택하지 않음). 금액·수량은 **양수 정수**로 저작한다.

> [HARD] `broken`/`lock` 경로는 반드시 손상/잠금 의도를 반영한다. `lock` 은 basename 이 `~$` 로 시작해야 한다(예: `임시/~$월간보고.docx`).

---

## consistency[] — 파생 계산 재검증 (연계성)

원장 저작 시 흔한 사고가 "합계 ≠ 월별", "공급가액 ≠ 단가×수량" 이다. 이를 게이트가 잡는다.

```json
{ "id": "C1", "desc": "2026 월별매출 합계",
  "op": "sum", "operands": [218,195,242,231,256,249], "expected": 1391,
  "expected_in": "데이터/2026_월별매출.xlsx" }
```

- `op`: `sum`(합) | `product`(곱) | `diff`(operands[0] − 나머지 합).
- verify 는 `op(operands) == expected` 를 재계산한다(원장 산술 오류 차단).
- `expected_in`(선택): 그 기대값이 **실제 렌더된 문서에 존재**해야 한다(원장 계산 ↔ 문서 drift 차단). 정본 총액이 렌더되는 문서를 가리킨다.

> 총액·차액을 문서에 넣었다면 반드시 consistency 로 묶어라. 그래야 정답지 숫자가 구조적으로 정확하다.

---

## traps[] / baits[] — 함정과 오탐 미끼

공통 필드: `id`(str), `type`, `title`, `detection`(기대 검출 서술), `targets`[](대상 문서 경로), `markers`[](실재 확인용), 선택 `canon`(정본 vs 편차 서술).

> [HARD] `markers` 가 없으면 함정이 조용히 누락돼도 게이트가 못 잡는다(유령 함정). **traps·baits 각각 검증 가능한 marker 를 최소 1개** 선언하라 — 스키마 검증이 markerless 함정/미끼를 명시 거부하고, verify ④축도 방어 심층으로 FAIL 처리한다. marker 는 verify ④축이 대상 문서를 재파싱해 실재를 확인한다.

marker 1건 = `{"path": …}` + 아래 중 **정확히 1개**:

| 키 | 의미 | 예 |
|----|------|----|
| `value`(int) | 그 정수가 대상 문서에 렌더돼야 함 | `{"path": "견적서/…xlsx", "value": 21500}` |
| `text`(str)  | 그 문구가 대상 문서에 있어야 함 | `{"path": "규정/…docx", "text": "500,000원"}` |
| `unreadable`(true) | 대상이 손상 파일이어야 함(정상 zip 이면 FAIL) | `{"path": "백업/…xlsx", "unreadable": true}` |
| `name_prefix`(str) | basename 이 접두로 시작 | `{"path": "임시/~$…docx", "name_prefix": "~$"}` |

### 함정 유형 카탈로그 (traps[].type, v1)

| type | 무엇 | 실현 방법 |
|------|------|-----------|
| `contradiction` | 문서 간 값 모순 | 계약가 vs 견적/발주가를 각 문서에 서로 다른 `value` 로. canon 에 정본. |
| `version-hell` | 버전 N부작(pptx/docx) | 같은 제목의 문서 여러 개(`_v2`,`_최종`,`_진짜최종`), 단가·조건을 조금씩 다르게. markers 로 각 버전의 차이값. |
| `stale-rule` | 규정 이중화(구버전 공존) | 최신 규정(`규정/`)과 옛 개정안(`옛날자료/`)을 문구 90% 동일하게, 한도만 다르게. |
| `time-warp` | 시점 역행 메모 | 머리글 날짜가 본문이 참조하는 사건보다 이르게(4/12 메모가 5월 사건 언급). |
| `decision-drift` | 결정 미반영 | 회의록의 인하 결정 vs 이후 보고서가 옛 단가 계상. |
| `broken-file` | 손상 파일 | `type:"broken"` 문서 + `unreadable:true` marker. |
| `lock-file` | 오피스 잠금 임시 | `type:"lock"` 문서 + `name_prefix:"~$"` marker. |
| `untitled` | 무제/제목없음 파일명이나 내용 중요 | `path` 를 `무제1.docx`·`임시/제목없음.txt` 로, 내용 marker(`text`)로 중요성 확인. |

### 오탐 미끼 유형 (baits[].type)

| type | 무엇 | 왜 모순 아님 |
|------|------|-------------|
| `direction` | 매입가 vs 판매가 | 거래 방향이 달라 값이 달라도 정상(마진). |
| `scope` | 기간·범위 상이 | 상반기 vs 연간처럼 집계 범위가 달라 값이 다름. |
| `duplicate` | 값 동일 사본 | 같은 값의 사본(`사본 - …`)은 모순이 아니라 중복. |

미끼는 검수관이 "모순"으로 **오인하면 감점**인 지점이다. `detection` 에 "왜 모순이 아닌가" 를 쓴다.

---

## insights[] — 합성해야만 보이는 것 (v0.2, REQ-050)

원장 3축의 셋째: **함정**(잘못된 것) · **미끼**(잘못 아닌 것) · **인사이트**(여러 문서를 종합해야만 보이는 것). 인사이트는 "데이터를 파악해야만 알 수 있는" 결론을 기계로 보장한다 — 단일 문서엔 정답이 없어야 한다.

필드: `id`(str) · `type`(str, 카탈로그 아래) · `title`(str) · `conclusion`(str, **자연어** 기대 결론) · `surface_question`(str, 3계단 질문 예시) · `tier`(1|2|3 정수, bool 불가) · `evidence`(**서로 다른 documents[].path ≥2**) · `derivation`(도출식) · `result`(**기계 검증축**).

> **conclusion 은 자연어 설명, `result` 는 기계 검증축이다(분리).** 수치 결론을 relation op(compare) 뒤에 숨겨 스포일러 검사를 우회하는 것을 막기 위해, 검증은 `conclusion` 문구가 아니라 `result` 가 담당한다.

### 유형 카탈로그 (insights[].type)

| type | 무엇 | 도출 op |
|------|------|--------|
| `negotiation-leverage` | 협상 카드(요청가 < 청구가 등) | compare |
| `threshold` | 기준 미달/초과(재고 < 안전재고) | threshold |
| `trend` | 증감·성장률(전년 대비) | ratio |
| `concentration` | 편중·비중(단일 채널 의존) | ratio |
| `margin` | 마진·회수기간(판매가 ÷ 월렌탈) | ratio |
| `deadline` | 기한·잔여일 | diff |

### derivation + result — 도출식과 기계 검증축

```jsonc
"derivation": {
  "op": "diff|sum|product|ratio|compare|threshold",
  "operands": [ {"value": <유한 숫자>, "from": "<evidence 문서 경로>"}, … ],
  // ratio: "scale": <배수, 기본 1 · % 는 100>, "round": <소수 자리, 기본 0>  (피연산자 2개=분자/분모)
  // compare|threshold: "relation": "lt|gt|lte|gte|eq|ne"  (피연산자 2개)
},
"result": {
  "kind": "numeric",   // 수치 결론 → op 은 sum|diff|product|ratio 여야 함
  "value": <유한 숫자>  // derivation 재계산과 일치·스포일러 검사 대상
}
// 또는  "result": { "kind": "relation" }   // 부등호 결론 → op 은 compare|threshold
```

- **피연산자는 서로 다른 evidence 문서 ≥2 에서** 와야 한다(선언). 각 `value` 는 `from` 문서의 재파싱 값에 실재해야 한다(verify 제5축).
- **result.kind = numeric**: op 이 수치 산출(sum·diff·product·ratio)이어야 하고, `result.value` 를 둔다. verify 가 derivation 을 재계산해 `result.value` 와 일치를 확인하고, `result.value` 를 스포일러 검사한다.
- **result.kind = relation**: op 이 compare·threshold 여야 하고, verify 가 부등호 성립을 확인한다(스포일러 비대상).
- 숫자(operand·result.value·tier)는 **유한**해야 한다 — NaN·Infinity·bool 은 로드·검증 단계에서 거부된다.
- `insights` 키를 두면 반드시 **배열**이다(`{}`·`false`·`0` 은 거부). 배열이 비면 "0건 PASS"(SKIP 아님). 키 자체를 생략해야 SKIP(하위호환).

### [HARD] 스포일러 금지 (verify 제5축)

수치 결론(result.kind=numeric)의 **파생 결과값이 어느 단일 문서에도 직접 렌더되면 FAIL**이다(우연 충돌 포함 — 저작자가 수치를 고르면 되므로 결정론 하드 게이트). 결론 숫자가 한 문서에 이미 인쇄돼 있으면 "합성"이 아니다. 충돌 시 **원장 수치를 조정**해 파생값이 어느 문서에도 없게 만든다.
- **정수 채널**: sum/diff/product 는 결과 정수. **ratio 는 결과 × 10^round**(예 13.7 → 137, 38.5 → 385).
- **소수 문자열 채널**: 소수 결론이 소수 표기("13.7"·"13.70")로 직접 렌더돼도 FAIL(정수 인코딩만으론 못 잡는 경로). 재파싱 텍스트에서 확인한다.
- **합성 강제 실검사**: 어느 **단일 정상 문서도 필요한 피연산자 전체를 공존 보유하면 안 된다**(선언 `from` 이 상이해도, 실제 렌더 값 기준). 한 문서에 다 있으면 그 문서만으로 도출 가능 → FAIL. 피연산자를 서로 다른 문서로 분산하라.
- **compare/threshold(부등호)는 스포일러 대상이 아니다**(결과가 참/거짓이라 인쇄될 수치가 없음).

예: margin 손익분기 = 판매가 480,000 ÷ 월렌탈 35,000 = **13.7** → 어느 문서에도 "137"·"13.7" 이 없어야 통과. 판매가는 계약서, 월렌탈은 견적서에 있어 두 문서를 합쳐야만 13.7 이 나온다(한 문서에 480,000·35,000 이 공존해도 FAIL).

> **질답 실사격(REQ-060)** — `surface_question` 은 `scripts/qa_sheet.py` 가 응답자용 질문지로 뽑는다. 이때 질문 문구에 result 수치·evidence 경로가 들어 있으면(정답 누출) qa_sheet 가 exit 2 로 막으므로, `surface_question` 은 **수치·경로 없이 순수 질문**으로 쓴다(예: "상반기 실적이 작년보다 얼마나 성장했나?"). 채점 절차는 `qa-protocol.md`.

---

## 미니 예시

```json
{
  "schema_version": "1",
  "profile": {"company": "가상제지(주)", "description": "인쇄용지 도매"},
  "canon": {"a4_price": 19800},
  "documents": [
    {"path": "계약/연간계약.docx", "type": "docx", "internal_date": "2026-01-02 15:00",
     "title": "연간공급계약", "blocks": [
        {"kind": "table", "rows": [["품목","단가"],["A4 용지","19,800"]]},
        {"kind": "p", "text": "제4조 단가는 계약 기간 중 고정한다."}]},
    {"path": "견적서/2026-03_견적.xlsx", "type": "xlsx", "internal_date": "2026-03-12 11:00",
     "sheets": {"견적": [["품목","수량","단가","공급가액"],["A4 용지",200,21500,4300000]]}},
    {"path": "백업/실적.xlsx", "type": "broken", "internal_date": "2026-04-02 03:00"}
  ],
  "consistency": [
    {"id":"C1","desc":"공급가액=단가×수량","op":"product","operands":[21500,200],
     "expected":4300000,"expected_in":"견적서/2026-03_견적.xlsx"}
  ],
  "traps": [
    {"id":"T1","type":"contradiction","title":"계약단가 위반",
     "targets":["계약/연간계약.docx","견적서/2026-03_견적.xlsx"],
     "canon":"계약 19,800 vs 견적 21,500","detection":"서면 합의 없는 인상",
     "markers":[{"path":"계약/연간계약.docx","value":19800},
                {"path":"견적서/2026-03_견적.xlsx","value":21500}]},
    {"id":"T5","type":"broken-file","title":"손상 백업",
     "targets":["백업/실적.xlsx"],"detection":"열기 실패 — 문제파일 기록",
     "markers":[{"path":"백업/실적.xlsx","unreadable":true}]}
  ],
  "baits": []
}
```

이 원장으로 `generate.py` → `verify.py`(PASS) → `answer_sheet.py` 가 성립한다. 값을 바꾸면 verify 가 불일치를 짚는다.
