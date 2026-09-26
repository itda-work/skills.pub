# brain-fixture

함정(모순·버전지옥·규정이중화·손상파일 등)을 의도적으로 심은 **가상 회사 연습용 데이터셋**을
만드는 스킬. brain-build 검증·데모·강의 실습용이다. 원장(ledger) SSoT 에서 문서를 결정론
렌더하고, 생성 직후 원장 ↔ 생성물을 재대조해 정합을 구조로 보장한 뒤, 강사용 정답지까지
자동 생성한다. (SPEC-BRAIN-FIXTURE-001, #1201)

## 무엇을 만드나

- **데이터셋 폴더** — docx·xlsx·pptx·pdf·txt·csv + 손상/잠금 파일. mtime = 문서 내부 날짜.
- **원장 `ledger.json`** — 단일 진실 소스. 재생성·업종 변형의 근거.
- **정답지 `.md`** — 강사용(비공개): 함정 표·정본 숫자·기대 검수 결과·오탐 경계·인사이트(3계단 질답 모범답안).

원장 3축: **함정**(잘못된 것) · **미끼**(잘못 아닌 것) · **인사이트**(여러 문서를 종합해야만 보이는 것 — verify 제5축 "합성 강제"가 스포일러 금지로 "단일 문서엔 정답 없음"을 보장).

## 구조 (원장 SSoT · 창의/결정론 분리)

```
사용자 입력(업체명·설명 | 개인 프리셋)
   ▼  에이전트: 세계관·수치 대장·함정을 ledger.json 으로 저작   ← 창의 구간
   ▼  scripts/generate.py  (결정론 렌더)                     ← 기계 구간
데이터셋 폴더
   ▼  scripts/verify.py    (자기 검증 게이트 — 4축 재대조)     ← 기계 구간
PASS → scripts/answer_sheet.py (정답지)  |  FAIL → 원장 보정 후 재생성
```

verify 게이트는 5축이다: ①수치 정합 ②연계성 ③mtime ④함정 실재 ⑤합성 강제(insights 선언 시). ⑤는 evidence 문서 상이성·피연산자 실재·derivation 재계산 + 스포일러 금지(파생 결과값이 어느 단일 문서에 직접 렌더되면 FAIL)를 본다.

## 사용법

```bash
# macOS/Linux (Windows 는 py -3)
python3 scripts/generate.py <ledger.json> --out <출력폴더>     # 렌더 (비어있지 않은 폴더는 exit 2 거부)
python3 scripts/verify.py   <ledger.json> <출력폴더>           # 게이트 (exit 0 PASS / 2 FAIL, 한국어 findings)
python3 scripts/answer_sheet.py <ledger.json> --out <정답지.md>  # 정답지
python3 scripts/qa_sheet.py <ledger.json> --out-dir <폴더>     # 질답 실사격 — qa-questions.md(응답자)·qa-key.json(채점자)
```

원장 저작 가이드는 `references/ledger-schema.md`, 질답 채점 절차는 `references/qa-protocol.md`, 참조 모범은 `examples/healthcare-ledger.json`(헬스케어 기기 업체 38문서·함정 8종·인사이트 5개), 개인형 씨앗은 `presets/{freelancer,household,club}.json`.

질답 실사격(REQ-060): `qa_sheet.py` 가 인사이트에서 응답자용 질문지와 채점자용 키를 분리 산출하고, **질문지에 정답 수치·근거 경로가 누출되면 exit 2**로 막는다(스포일러 금지의 질답판). 응답자는 업무DB 폴더만 연 zero-context 에이전트.

## 검증 지도

```bash
# 스킬 테스트 (스킬 루트에서)
python3 -m pytest tests/ -q
# 헬스케어판 라이브 왕복
python3 scripts/generate.py examples/healthcare-ledger.json --out /tmp/hc
python3 scripts/verify.py   examples/healthcare-ledger.json /tmp/hc   # exit 0
```

## 의존성

`python-docx`·`openpyxl`·`python-pptx`·`reportlab`(한글 텍스트 레이어 PDF)·`pypdf`(PDF 재파싱). `requirements.txt` 참조. 환경 변수·외부 API 없음. hyve 무의존(길 X thin skill).
