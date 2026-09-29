---
name: brain-fixture
description: >
  함정(모순·버전지옥·규정이중화·손상파일 등)을 의도적으로 심은 가상 회사의 연습용
  데이터셋 폴더(워드·엑셀·PPT·PDF·txt·csv)를 만드는 스킬입니다. 한글 문서 함정(확장자
  틀림·HWP 3·배포용)도 심습니다. brain-build 검증·데모·강의
  실습용으로 쓰며, 원장(ledger) SSoT 에서 문서를 결정론 렌더하고 생성 직후 수치·연계성을
  자기 검증한 뒤 강사용 정답지까지 자동 생성합니다. "연습용 가상 폴더 만들어줘",
  "함정 심은 모의 데이터셋 생성해줘", "헬스케어 회사 연습 데이터 만들어줘",
  "brain-build 테스트용 샘플 폴더 만들어줘", "가상 회사 공유폴더 만들어줘"처럼 말하면 됩니다.
  실존 상호·인명 금지 — 전부 가상 명칭으로 만듭니다.
license: MIT
compatibility: "Python 3.10+ (python-docx·openpyxl·python-pptx·reportlab·pypdf)"
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, mcp__workspace__bash
argument-hint: "[업체명·설명 | 개인 프리셋(freelancer|household|club)] [출력 폴더]"
metadata:
  author: "Chinseok"
  version: "0.4.0"
  category: "knowledge-base"
  status: "experimental"
  recommended: false
  created_at: "2026-07-18"
  updated_at: "2026-09-28"
  tags: "test-data, fixture, synthetic-dataset, traps, insights, synthesis, ledger, deterministic, self-verify, answer-key, docx, xlsx, pptx, pdf, hwp, hwpx, incubating"
---

# brain-fixture

brain-build 를 검증·시연·교육하려면 **함정을 심은 가상 회사 폴더**가 매번 필요하다. 손으로 만들면
며칠 걸리고, 만들어도 문서 간 수치가 안 맞아(합계≠월별, 날짜 역전) 정답지가 틀어진다. brain-fixture 는
이 폴더를 **원장(ledger)에서 결정론으로 렌더**하고, **생성 직후 원장 ↔ 생성물을 재대조**해 정합을
구조로 보장한 뒤, 강사용 **정답지**까지 자동으로 만든다. 업종만 바꾼 세트도 원장 하나로 재생성된다.

itda-research 비정형 문서 vertical 의 **함정 데이터셋 포지(forge)**. (SPEC-BRAIN-FIXTURE-001, #1201 — 한빛오피스 37파일 fixture 수작업 경험의 일반화.)

---

## Claude 오케스트레이션 지시서

> [HARD] **가상 명칭만.** 실존 상호·인명·상표를 쓰지 않는다. 업체·대표·거래처·제품·담당자는 전부 가상으로 창작한다(세라젬 등 실존명 금지 — 인접 도메인이라도 새 가상명).
> [HARD] **출력 폴더 비파괴.** 출력 폴더가 이미 존재하고 비어있지 않으면 **명시 거부**한다(generate.py 가 exit 2). 기존 데이터를 덮어쓰지 않는다 — 빈 폴더나 새 경로를 쓴다.
> [HARD] **게이트 실패를 성공으로 위장 금지.** verify.py 가 FAIL(exit 2)이면 결과를 "완료"로 제시하지 않는다. findings 를 읽고 **원장을 보정한 뒤 재생성**한다(관문4 루프). 원장 수정 없이 생성물만 손대지 않는다.
> [HARD] **원장이 SSoT.** 모든 문서 값은 원장에서 파생된다. 문서에 들어갈 숫자·날짜를 원장 밖에서 임의로 창작하지 않는다 — 원장에 없는 값은 데이터셋에 존재할 수 없다. 함정도 원장에 "의도된 편차"로 선언한다.

### 산출물

- **데이터셋 폴더** — 함정을 심은 가상 회사 문서 무더기(docx·xlsx·pptx·pdf·hwpx·hwp·txt·csv + 손상/잠금/한글 미지원 파일, mtime=내부 날짜).
- **원장 `ledger.json`** — SSoT. 재생성·업종 변형의 근거로 보존한다.
- **정답지 `.md`** — 강사용(비공개). 함정 표·정본 숫자·기대 검수 결과·**문제파일 기대 분류**(brain-build `문제파일.md` 대조)·오탐 경계·**인사이트(3계단 질답 모범답안)**.

### 관문0 — 스킬 디렉토리(SKILL_DIR) 확정

스킬 스크립트·참조 자산은 cwd 에 의존하지 않도록 **절대경로**로 쓴다. 실행 절 첫머리에서 `SKILL_DIR` 을 한 번 확정한다:

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/brain-fixture}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/brain-fixture' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\brain-fixture"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

### 관문0-b — 의존성 설치 (처음 한 번)

```bash
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# Windows: py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

### 관문1 — 입력 수집

두 경로 중 하나로 시작한다.

- **업체형(자유 저작)** — 사용자에게 받는다: ① **업체명**(가상) ② **업종·설명**(무엇을 하는 회사인가) ③ **규모**(직원 수·파일 수 대략) ④ **함정 구성**(어떤 함정을 넣을지 — 미지정 시 기본 세트: 계약단가 모순·버전지옥·규정이중화·결정미반영·손상/잠금/무제 파일·시점역행). 실존명을 요청받으면 가상명으로 치환하겠다고 알린다.
- **개인형(프리셋)** — `"$SKILL_DIR/presets/"` 3종 중 선택: `freelancer`(프리랜서 정산)·`household`(가계 아카이브)·`club`(동호회 운영). 각 프리셋은 **동작하는 씨앗 원장**이다 — `_preset` 블록의 `recommended_traps`·`expand` 안내대로 documents/traps 를 늘려 완성한다.

출력 폴더 경로도 확인한다(미지정 시 작업 폴더 아래 `<업체명>_연습폴더/` 제안).

### 관문2 — 원장 저작 (창의 구간)

`"$SKILL_DIR/references/ledger-schema.md"` 를 **정독**하고 그 계약대로 `ledger.json` 을 저작한다. 핵심:

- `profile`·`entities`·`series`·`canon` 에 세계관과 정본 수치를 세운다.
- `documents[]` 에 렌더할 문서 전건을 유형별로 선언한다(`internal_date` 는 파일 mtime 으로 박힌다 — 버전 함정의 최신성 단서).
- **함정은 `traps[]` 에, 오탐 미끼는 `baits[]` 에** "의도된 편차/구조"로 선언한다. 함정마다 `markers` 를 최소 1개 붙여야 verify 가 실재를 확인한다(조용한 누락 차단).
- **파생 계산은 `consistency[]` 로 묶는다**(합계·곱·차). 총액을 문서에 넣었으면 반드시 consistency 로 재검증되게 한다 — 그래야 정답지 숫자가 구조적으로 정확하다.
- 함정 유형 카탈로그: `contradiction`·`version-hell`·`stale-rule`·`time-warp`·`decision-drift`·`broken-file`·`lock-file`·`untitled`, 한글 문서 3종 `hangul-document`(정상 HWPX·HWP 5 — 읽혀야 정답)·`ext-mismatch`(`.hwpx` 인데 내용은 HWP 5 — 내용으로 읽혀야 정답)·`hangul-unsupported`(HWP 3.x·배포용 보호 — "한글 리더 미지원 형식" 기록이 정답). 한글 함정은 `format` marker(파일 **내용 서명**)로 무엇인지 선언한다. 오탐 미끼: `direction`(매입 vs 판매)·`scope`(기간·형태 상이)·`duplicate`(값 동일 사본).
- **인사이트를 `insights[]` 에 4~5개 넣는다**(원장 3축의 세 번째 — 함정=잘못된 것, 미끼=잘못 아닌 것, **인사이트=여러 문서를 종합해야만 보이는 것**). 각 인사이트: `conclusion`(**자연어** 설명)·`derivation`(op+operands)·`result`(**기계 검증축** — `kind: numeric`+`value`, 또는 `kind: relation`)·`evidence`(**서로 다른 문서 ≥2**)·`surface_question`(3계단 질문)·`tier`(1~3). 유형 카탈로그: `negotiation-leverage`·`threshold`·`trend`·`concentration`·`margin`·`deadline`. 수치 결론은 반드시 `result.kind=numeric`(+수치 산출 op)로 선언한다 — relation op(compare) 뒤에 숨기면 스키마가 거부한다.
  - **[HARD] 스포일러 금지** — 수치 결론(result.kind=numeric)의 **파생 결과값이 어느 단일 문서에도 직접 렌더되면 안 된다**(verify 제5축이 FAIL). 정수 인코딩(예 13.7→137)과 **소수 표기("13.7")** 를 모두 검사하고, **어느 한 문서에 피연산자가 전부 공존해도 FAIL**(그 문서만으로 도출 가능 = 합성 아님). 충돌하면(우연 포함) **원장 수치를 조정**해 파생값·피연산자를 서로 다른 문서로 분산한다. compare/threshold(부등호)는 스포일러 대상이 아니다.
  - **가상 명칭 재확인** — 회사·거래처·인물은 실존 상호와 겹치지 않는 **독특한 코인 명칭**을 쓴다(흔한 "웰"·"케어"+업종어 조합은 실존 충돌 위험 — 음절을 비튼 비실재풍 조합).

동봉 예시 `"$SKILL_DIR/examples/healthcare-ledger.json"`(가상 헬스케어 기기 업체 42문서·함정 12종(한글 4종 포함)·미끼 3종·인사이트 6개)를 참조 모범으로 삼는다.

### 관문3 — 데이터셋 렌더 (기계 구간)

원장을 결정론으로 렌더한다.

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/generate.py" <ledger.json> --out <출력폴더>
# Windows
py -3 "$env:SKILL_DIR\scripts\generate.py" <ledger.json> --out <출력폴더>
```

출력 폴더가 비어있지 않으면 exit 2 로 거부한다(비파괴). 원장 스키마 위반은 exit 2 + "어느 필드가 왜" 명시 에러.

### 관문4 — 자기 검증 게이트 (기계 구간, PASS 까지 루프)

> [HARD] 생성에 그치지 않는다 — **원장 ↔ 생성물을 재대조**한다. verify.py 가 게이트다.

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/verify.py" <ledger.json> <출력폴더>
# Windows
py -3 "$env:SKILL_DIR\scripts\verify.py" <ledger.json> <출력폴더>
```

5축(①수치 정합 ②연계성 ③mtime ④함정 실재 ⑤합성 강제)을 검사해 exit 0(PASS)/2(FAIL). ⑤는 insights 선언 시에만 돌고 없으면 SKIP(하위호환). **FAIL 이면 findings(한국어)를 읽고 원장을 보정한 뒤 관문3부터 재생성**한다. 보정 루프는 **최대 3회**까지 돌고, 3회 후에도 FAIL 이면 **fail-visible 보고**한다(잔여 findings 를 그대로 제시하고 "게이트 미통과"로 종결 — 성공으로 위장하지 않는다). 흔한 FAIL 원인: 합계≠월별(consistency 불일치)·함정 마커 미렌더·문서 간 값 오타·**인사이트 파생값이 문서에 직접 렌더됨(스포일러)**.

### 관문5 — 정답지 생성

게이트 PASS 후에만 강사용 정답지를 만든다.

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/answer_sheet.py" <ledger.json> --out <정답지.md>
# Windows
py -3 "$env:SKILL_DIR\scripts\answer_sheet.py" <ledger.json> --out <정답지.md>
```

원장 traps/baits/consistency 에서 세계관 요약·함정 표·정본 숫자·기대 검수 결과·문제파일 기대 분류·오탐 경계·인사이트를 파생한다. 문제파일 기대 분류는 brain-build `문제파일.md` 와 같은 낱말(정상 적재 / 읽기 불가 / 판독 도구 없음)로 파일별 분류·사유·조치와 적재 집계 기대값을 **itda-doc 설치·미설치 두 경우**로 싣는다 — 미설치면 한글 문서는 형식과 무관하게 전부 "판독 도구 없음" 이 정답이다.

### 관문6 — 질답 실사격 (선택, REQ-060)

인사이트가 실제로 "종합해야만 답이 나오는지"를 실사격하려면 질문지·채점지를 만든다.

```bash
# macOS/Linux (Windows 는 py -3)
python3 "$SKILL_DIR/scripts/qa_sheet.py" <ledger.json> --out-dir <폴더>
```

`qa-questions.md`(응답자용 — 번호·tier·질문만)와 `qa-key.json`(채점자용 — 기대 결론·result·evidence·도출식 + `file_status` 문제파일 기대 분류)을 산출한다. **질문 문구에 정답 수치(정수 인코딩+소수 표기)·근거 경로가 있으면 exit 2 로 누출을 표면화**하니(스포일러 금지의 질답판), 그때는 해당 insight 의 `surface_question` 에서 수치·경로를 빼고 다시 만든다. 채점 절차·응답자 계약·tier 합격선은 `"$SKILL_DIR/references/qa-protocol.md"` 를 따른다 — 응답자는 **업무DB 폴더만** 연 zero-context 에이전트여야 하며(원장·정답지·qa-key 접근 금지), 답마다 근거 경로를 명시한다.

### 완료 보고

사용자에게 요약한다: 데이터셋 폴더 경로 · **파일 수**(정상 N / 문제파일 K — 한글 문서 H건 포함) · **함정 수·유형** · **인사이트 수** · **게이트 결과**(PASS/FAIL + 5축) · 정답지 경로 · 원장 경로. 정답지는 **비공개**(수강생 미배포)임을 덧붙인다. brain-build 로 이 폴더를 업무DB화해 검수관이 함정을 잡아내는지 교차 확인하려면 "이 폴더를 업무DB로 만들어줘"로 brain-build 를 수동 킥오프하라고 안내한다(EXC-4 — 자동 연동 아님).

---

## 원칙

- **원장 SSoT · 창의/결정론 분리** — 에이전트는 원장(세계관·함정)만 저작하고, 렌더·검증·정답지는 Python 이 결정론으로 수행한다. "생성 후 재검증"을 프로세스가 아니라 구조로 보장한다.
- **"동작함" ≠ "정확함"** — 폴더가 그럴듯해 보여도 수치가 원장과 일치하는지는 verify 게이트가 판정한다(no-silent-fallback — 실패는 exit 2 로 표면화).
- **길 X thin skill** — hyve 무의존. Cowork 에 스킬팩 + Python 의존만 있으면 동작한다.

## v1 한계

- **경로 안전** — `documents[].path` 는 출력 폴더 기준 상대경로만 허용한다. 절대경로·경로 탈출(`..`)·정규화 중복 경로는 스키마 검증이 명시 거부하고, generate/verify 도 파일 접근 직전 재확인한다(폴더 밖 파일 덮어쓰기 차단).
- **한글 문서는 판독기 계약 대상** — HWPX·HWP 5 는 스킬이 최소 구조를 직접 조립한다(다른 팩·외부 파일 무의존, 같은 원장이면 같은 바이트). 판정 기준은 한글 리더(`itda-doc:hwpx`)가 읽는가/무엇으로 거부하는가이고, 한컴오피스에서 열리는지는 보장하지 않는다. 표 블록은 셀을 ` | ` 로 이은 문단으로 렌더한다.
- **값은 양수 정수 권장** — verify ①축은 정수 존재(membership) 대조라 **부호(음수) 검증은 v1 비대상**이다(부호 반전 변조는 미검출). 게이트 목적은 렌더러 결함·원장↔문서 drift 검출이지 임의 변조 방어가 아니다. 금액·수량은 양수 정수로 저작한다.
