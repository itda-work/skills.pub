---
name: hwpx
description: >
  한글 HWP·HWPX 문서 스킬입니다. 읽기(HWP/HWPX → Markdown·HTML), 양식 채우기(기존 .hwpx
  양식의 서식을 유지한 채 자리표시·빈 칸·체크박스를 값으로 채움 — 사전검증·잔재 대조 포함),
  서식 생성(마크다운 → .hwpx: 행안부 AI 친화적 보고서·기안문(공문)·gov-report·보도자료·표지목차형),
  참고 서식 프로파일(사용자가 준 .hwpx 의 서식을 추출해 그 서식으로 생성)을 한 스킬에서 처리합니다.
  "이 HWP 파일 읽어줘", "이 한글 양식 채워줘", "빈칸 채워줘", "한글 보고서 만들어줘",
  "공문/기안문 hwpx로", "이 양식으로 보고서 작성해줘", "이 서식처럼 써줘(참고 hwpx 첨부)"처럼 말하면 됩니다.
license: Apache-2.0
compatibility:
  claude_desktop: false
  claude_code: true
user-invocable: true
allowed-tools: Bash, Read, Write, mcp__workspace__bash
argument-hint: "<hwp/hwpx 파일 경로 또는 보고서 마크다운 경로>"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  tags: "hwp, hwpx, document, convert, markdown, html, template, fill, report, government, profile"
  version: "1.4.2"
  category: "document"
  created_at: "2026-07-28"
  updated_at: "2026-09-28"
  status: "experimental"
  recommended: true
---

# HWP/HWPX 문서 처리 (통합)

한글 문서에 대한 세 가지 작업을 하나의 스킬로 라우팅합니다. **hyve MCP 등 외부
서버 없이 스킬 단독으로 동작**합니다 (Python 3.10+).

| 사용자 요청 | 작업 | 경로 |
|---|---|---|
| "이 HWP/HWPX 읽어줘", "마크다운으로 변환해줘" | **읽기** | `reader/` (hwpx_native) — [상세](reader/USAGE.md) |
| "이 한글 양식 채워줘", "빈칸에 값 넣어줘", **"이 양식으로 보고서 만들어줘"(빈칸·안내문 양식 첨부)** | **양식 채우기** | `scripts/fill_hwpx.py` — 아래 §채우기 |
| **"이 서식처럼 써줘", "우리 기관 보고서 서식으로"(참고 .hwpx 첨부 + 새 내용)** | **참고 서식 프로파일 생성** | `report/scripts/derive_profile.py` + `--template-dir` — 아래 §참고 서식 |
| "한글 보고서 만들어줘", "공문/기안문 hwpx로", "보도자료 서식으로" (파일 없음) | **서식 생성** | `report/` (hwpx_report) — 아래 §서식 생성 |

**양식 우선 원칙 — 세 갈래.** 사용자가 `.hwpx` 를 함께 줬으면 그 기관의 서식이 정답이며 내장 생성 템플릿으로
대체하지 않는다. 다만 그 파일이 무엇이냐에 따라 경로가 갈린다:

1. **빈칸·안내문 양식**(신청서·정산서·"입력하세요" 문구) → **채우기**. `--dump` 에서 `EMPTY` 셀·안내문 비율이 높으면 이쪽.
2. **참고 문서 + 새 내용**("이 보고서 서식처럼 새 안건을 써줘") → **프로파일 생성**. 본문 문단이 많고 사용자가 "이 서식처럼" 이라 말하면 이쪽.
3. **파일 없음** → 내장 조판 생성.

애매하면 사용자에게 **한 번** 묻는다("이 파일의 빈칸을 채울까요, 이 서식으로 새로 쓸까요?"). 읽기는 산출이 내용(마크다운)일 때다.

**입력 형태별 계약** — "요청 서식" 이 어떤 형태로 오든 아래대로 답한다(약속하지 않을 것을 약속하지 않는다):

| 사용자가 주는 것 | 동작 | 실패 모드·한계 |
|---|---|---|
| `.hwpx` 빈칸/안내문 양식 | 채우기(`--dump → --check → 채움 --strict → --residue`) | 안내문 잔존은 `--residue` 가 exit 2 로 차단 |
| `.hwpx` 참고 문서 + 새 내용 | 프로파일 추출 → `--template-dir` 생성 → `compare --ref` 확인 | 다중 섹션·표지·결재란·머리말/꼬리말은 경고 후 **본문 서식만** 근사 |
| `.hwp` | 스킬 단독으로는 **읽기만**. 채우기·서식 추출은 한글에서 `.hwpx` 로 저장한 뒤 | `.hwp` 를 직접 채우려 하지 않는다 |
| HWP 3.x·`.hml`(HWPML) | 리더 미지원 — 한글에서 HWPX 저장 또는 kordoc 대체 경로(아래 §읽기 — 못 읽는 형식) | 사용자 동의 없이 외부 패키지를 실행하지 않는다 |
| PDF·스캔·스크린샷 서식 | **미지원을 말한다** — 구조(제목·절·표 유무)를 물어 내장 조판으로 폴백 | "비슷하게" 를 약속하지 않는다(OCR·치수 추정 비목표) |
| 말로만("우리 기관 스타일로") | 확인 질문 1회(참고 파일 유무·용지·번호 체계) → 내장 조판 | — |

## 준비 — SKILL_DIR 확정 (모든 경로의 기준)

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/hwpx}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/hwpx' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 이 SKILL.md 가 있는 디렉토리 절대경로를 그대로 사용
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\hwpx"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

의존성 (읽기: Pillow·olefile / 생성 이미지: Pillow / 채우기·사전검증·프로파일 추출: 표준 라이브러리만):

```bash
python3 "$SKILL_DIR/scripts/install_skill_deps.py"          # 정문
# Windows: py -3 "$env:SKILL_DIR\scripts\install_skill_deps.py"
# 수동 폴백: python3 -m pip install --user -r "$SKILL_DIR/requirements.txt"
```

> 설치 정문은 `install_skill_deps.py` 다(#1630) — 이 환경(venv·PEP 668 관리형·권한 부족)에 맞는 pip 인자를 스스로 고르고 실행한 명령을 보여 준다. `--check` 는 상태만, `--all` 은 선택 의존까지, `--dry-run` 은 명령만.

입력 파일은 항상 쓰기 가능한 작업 디렉토리(`.itda-skills/`)로 복사한 뒤 처리합니다.
Cowork 업로드 경로는 read-only 일 수 있고, 채우기는 원본 보존이 원칙입니다.

## 읽기 — HWP/HWPX → Markdown·HTML

```bash
mkdir -p .itda-skills && cp <입력파일> .itda-skills/
PYTHONPATH="${SKILL_DIR}/reader" \
python3 -m hwpx_native convert .itda-skills/<파일명> -o .itda-skills/<파일명>.md --format md
```

- 본문만(이미지 제외): `--no-extract-images` / HTML: `--format html`
- 공고·안내문처럼 본문 전체가 테두리 표 하나에 들어 있어 결과가 한 칸짜리 표 덩어리면 `--unwrap-layout-tables` 로 다시 변환한다(옵트인 — 표 틀만 풀고 글자는 그대로).
- 표 평탄화 지침·이미지 캡션 옵션 등 상세: [reader/USAGE.md](reader/USAGE.md)

### 읽기 — 이 리더가 못 읽는 형식 (HWP 3.x·HWPML)

형식은 확장자가 아니라 **파일 내용**으로 판정한다 — 확장자가 틀린 공고(`.hwpx` 인데 실제로는 HWP 5)도 그대로 읽는다.
리더가 읽는 것은 **HWP 5.x·HWPX** 이고, 그 밖이면 exit 2 와 함께 무엇인지 알린다(HWP 3.x·HWPML(.hml)·Word/Excel 등).
잘리거나 깨진 파일도 exit 2 「손상된 … 문서입니다」로 끝난다 — 한글에서 열어 다시 저장한 파일을 받는다.

HWP 3.x·HWPML 은 다음 순서로 안내한다.

1. **한글(한컴오피스)에서 열어 HWPX 로 저장**해 달라고 한다 — 가장 정확하고 외부 도구가 필요 없다.
2. 한글이 없으면 **kordoc**(npm, MIT, github.com/chrisryugj/kordoc)으로 읽는다. 외부 패키지를 내려받아 실행하므로 **사용자에게 먼저 묻고**,
   버전을 고정한다:

   ```bash
   npx -y kordoc@4.15.7 .itda-skills/<파일> -o .itda-skills/<파일>.md
   ```

   - 요건: Node.js 20+ · npm 레지스트리 접속. 첫 실행은 약 450MB·25초(Cowork 실측 2026-09-28), 이후 캐시로 1초대.
     Cowork 는 대화마다 캐시가 사라질 수 있어 매번 첫 실행 비용이 든다.
   - HWP 3.x(한글 97 등)·HWPML 읽기를 실측으로 확인했다. 결과 마크다운은 kordoc 형식이다(병합 표는 HTML) — 이 스킬의
     품질 게이트 밖이므로 그 사실을 사용자에게 말한다.
   - Cowork(x86_64)에서는 kordoc 의 선택 의존 설치가 NuGet 차단으로 실패해 **이미지 OCR·PNG 렌더가 안 된다** — 이 스킬의 대체 경로(HWP 3.x·HWPML 읽기)에는
     필요 없다. 그 기능까지 써야 하면 `ONNXRUNTIME_NODE_INSTALL=skip npx -y kordoc@4.15.7 …` 로 설치한다(원인·우회 실측: 능력 지도 §3.8).
   - npm 에 닿지 않으면 그 오류를 그대로 전하고 1번으로 돌아간다 — 다른 경로로 우회하지 않는다.

## 채우기 — 양식 서식 유지 + placeholder·빈 칸 채움

원리는 docx "사본 채우기"와 동일: 양식을 새로 그리는 게 아니라 **원본의 `Contents/section*.xml` 텍스트만
바꾸므로** 서식·표·번호가 그대로 유지됩니다. 매칭은 **문단 단위**(run 분절·글꼴 차이 무관)이고, 표준 라이브러리만 씁니다.
정본 동선은 **네 단계**입니다 — 사전검증과 잔재 대조를 건너뛰지 마세요(안내문이 남은 채 결재로 나가는 것이 제1 위험).

```bash
# 0) 양식 안 문단 전수 조사 — 한 줄에 `번호⇥위치⇥플래그⇥텍스트`. 위치 = 본문 | 표i rN cM, 플래그 = OK | CTRL(탭·줄바꿈 낀 문단) | EMPTY(빈 셀)
python3 "${SKILL_DIR}/scripts/fill_hwpx.py" .itda-skills/양식.hwpx --dump
#    (괄호·{{}}·《》 마커 규약이 있는 양식이면 --list 로 후보만 볼 수도 있다 — 규약이 없으면 0건이 정상)

# 1) 매핑을 짠 뒤 사전검증 — 키마다 ok / fixable(표기 차이: 교정안 제시) / ctrl(탭·줄바꿈을 가로지름: 키를 나눌 것) / multi(문단 여러 개를 합친 키) / missing
python3 "${SKILL_DIR}/scripts/fill_hwpx.py" .itda-skills/양식.hwpx --check --map 채움값.json --fix .itda-skills/채움값.fixed.json
#    ok 외 하나라도 있으면 exit 2. --fix 는 fixable 만 원문 표기로 고친 매핑을 써 준다(값·라벨은 그대로).
#    두 키의 교정안이 같은 자리로 겹치면 collision — 파일을 쓰지 않고 exit 2(키를 서로 다른 자리로 나눈다)

# 2) 채우기 (원본과 다른 출력 경로 필수, --strict 권장)
#    --cell = 빈 셀을 --dump 좌표로 / --label = 라벨 셀의 오른쪽(없으면 아래) 빈 셀 / --tick = □항목 → ☑항목
python3 "${SKILL_DIR}/scripts/fill_hwpx.py" .itda-skills/양식.hwpx -o .itda-skills/결과.hwpx --strict \
  --map .itda-skills/채움값.fixed.json \
  --cell "표0 r2 c1=정보통신과" \
  --label "성명=김서준" \
  --tick "개인정보 수집 동의"
#    매핑 JSON 예: {"(부서명)": "내부감사팀", "본문 안내 문구": ["첫째", "둘째"]} ← 같은 키가 여러 번이면 배열로 순차 치환

# 3) 잔재 대조 — 원본의 안내문 후보(마커·"…하세요/바랍니다" 명령형 문단)와 매핑 키가 결과에 남았는지 + 매핑 값이
#    원래 그 키가 있던 **같은 문단의 같은 순서 자리**에 들어갔는지(커버리지 — 자리가 뒤바뀌면 value_misplaced,
#    없으면 value_missing, 문단 수가 달라지면 structure). 어긋나면 exit 2
python3 "${SKILL_DIR}/scripts/fill_hwpx.py" .itda-skills/결과.hwpx --residue .itda-skills/양식.hwpx \
  --map .itda-skills/채움값.fixed.json --keep "작성 후 제출"     # 의도적으로 남기는 법정·고정 문구는 --keep
```

- **매칭 계약**: 키는 문단 텍스트(직접 속한 `<hp:t>` 조각 + 그 형제로 놓인 **텍스트를 나누는** 요소를 문서 순서로
  이어붙인 것)에서 부분문자열로 찾고, 값은 **첫 조각(첫 run 서식)** 에 전부 들어가며 나머지 조각은 겹친 부분만 지운다.
  전각 공백(`fwSpace`)은 공백 하나로 본다. **탭·줄바꿈은 물론 필드(누름틀)·각주·그림·표를 가로지르는 키도 절대 맞지
  않는다**(`--check` 가 `ctrl` 로 분류하고 나눌 위치를 알려 준다). 반대로 **무텍스트 레이아웃 컨트롤**(한컴이 셀 첫
  run 에 넣는 `colPr`·`secPr` 등)은 텍스트를 나누지 않으므로 키에 영향이 없고 `CTRL` 로 표시되지도 않는다.
  삽입한 값은 다시 치환되지 않는다.
- 순차 치환은 값이 자리보다 적거나 많으면 **경고**한다(남는 자리는 그대로 둔다 — 조용히 지우지 않는다). `--strict` 는 미발견 키·
  값 없이 남은 자리·못 찾은 체크박스를 exit 3 으로 실패시킨다.
- **빈 칸 채움**: `--cell "표i rN cM=값"`(좌표는 `--dump` 의 것 — 병합 셀은 왼쪽 위 좌표) / `--label "라벨=값"`(라벨과 **정확히**
  같은 텍스트의 셀을 찾아 같은 행 바로 오른쪽, 없으면 바로 아래의 빈 셀). 라벨 모드는 그 표에 병합 셀이 있거나, 중첩 표가 얽혀 있거나
  (표가 중첩 표를 품었거나 **자신이 다른 표 안의 내부 표**이거나), 라벨이 0건·2건 이상이면 **거부**(exit 2)하고 좌표 모드를 안내한다. 값의 줄바꿈은 셀 안 줄바꿈이 된다. 괄호 빈칸(`일반(  )통`)은 미지원.
- `--check` 는 교정 후 두 키가 같은 자리로 겹치면 `collision` 으로 보고하고 `--fix` 파일을 **쓰지 않는다**(매핑 항목 소실 방지).
- **종료 코드**: 0 정상 / 1 사용법·입력 오류 / 2 `--check`·`--residue` 문제 및 `--cell`·`--label` 오류 / 3 `--strict` 실패.
  `--json` 을 주면 `--check`·`--residue` 결과가 JSON 으로 stdout 에 나온다(사람용 줄은 stderr) — 판정은 exit code·JSON 으로 한다.
- **옵트인 위생**(기본 꺼짐 — 한컴 macOS 실측 2026-09-07: 실 한컴 저장본을 텍스트만 치환해도 복구 경고 없음, 변형 4종 동일 렌더):
  `--strip-lineseg`(변경 문단의 줄 배치 캐시 제거), `--refresh-preview`(미리보기 텍스트 재생성). 한글이 "손상 파일 복구" 를 띄우는 문서를 만나면 이 둘을 켜서 다시 만들어 본다.
- 검증: 치환 후 XML 정합성과 **구조 검사**(생성 경로와 같은 9검사 — mimetype·필수 파트·secCnt·manifest 등)를 스크립트가 자체 확인한다. 원본에서 통과하던 검사가 결과에서 실패하면 exit 1, 원본 양식부터 어긋난 항목은 경고만 낸다. 내용 확인은 결과 파일을 **읽기 경로로 다시 열어** 교차 검증한다.
- 한계: 텍스트·셀 값·체크박스 전용. 표 행 추가·이미지 삽입·서식 변경은 지원하지 않는다
  (누름틀/필드 기반 채움·반복행 발행·행 추가는 범위 밖 — 이 스킬은 무의존 단독 동작이 원칙).

## 서식 생성 — 마크다운 → HWPX (템플릿 선택이 먼저)

| 사용자 의도 | `--layout` / `--template` | 특징 |
|---|---|---|
| 보고서·현황보고·계획(기본, **권장**) | `ai-report` | 행안부 AI 친화 원칙(2026-08): 장식 표 없음, 평문 제목+메타 줄, `1.` 절 제목, ○/- 서술식, 표 위 `< 표 N. 제목 >` |
| 공문·기안문·협조 요청·안내문 | `official-letter` | 수신·(경유)·제목, 항목기호 `1. 가. 1) 가)` 자동, 붙임·`끝.`, 발신명의·시행 정보 |
| 구 정부 개조식(제목 박스·□/❍) 명시 요청 | `report` / `gov-report` | 종전 계약 그대로(2단) |
| 보도자료 | `press-release` | 제목 박스 + 절 제목 + **산문 리드문·인용 보존** + 표 |
| 표지·목차·섹션바가 있는 결재용 내부보고서(명시 요청 시만) | `briefing` | 장식형 — AI 친화 원칙과 상충하므로 사용자가 그 형태를 지목했을 때만 |

```bash
# 0) 표기법 검사 — 날짜(2026. 9. 6.)·시각(15:20)·금액 한글 병기·쌍점·물결표·「붙임」. 경고만 한다(exit 1 = 경고 있음)
python3 "${SKILL_DIR}/report/scripts/lint_notation.py" .itda-skills/report.md
# 1) 마크다운 → DocSpec (layout 이 항목 계층 상한·번호 처리·표 제목 규칙을 정한다)
python3 "${SKILL_DIR}/report/scripts/md_to_docspec.py" .itda-skills/report.md -o .itda-skills/spec.json --layout ai-report
# 2) DocSpec → HWPX (template 은 layout 과 같은 이름)
PYTHONPATH="${SKILL_DIR}/report${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m hwpx_report convert .itda-skills/spec.json -o .itda-skills/report.hwpx --template ai-report
```

- 기안문은 `--layout official-letter` + `--template official-letter`. 수신·발신명의·기안자·붙임 같은 값은
  front-matter 한글 키(`수신:`, `발신명의:`, `붙임: A 1부. | B 1부.`)나 `--field receiver=…` 로 준다.
- 표기법 경고(0단계)는 사용자에게 보여 주고 **고칠지 묻는다** — 스스로 원고를 고치지 않는다. 규정에 "특별한 사유가 있으면 다른 방법" 단서가 있어 판단은 사용자 몫이다.
- 매퍼 경고(stderr)는 사용자에게 그대로 전달합니다 — 특히 ai-report 의 "표 제목 없음" 경고는 사용자에게 제목을 받아 채우는 것이 정본.
- 원고 내용을 버리는 경고(표 칸 절단·표 건너뜀·제목 줄 버림)는 `--strict` 를 주면 DocSpec 을 쓰지 않고 exit 2 — 공고·신청서처럼 칸 하나가 빠지면 안 되는 문서는 `--strict` 로 돌린다. 절단 경고는 버린 칸 글자를 보여 준다.
- 작성 규약·front-matter 키·조판별 상세·규격 근거: [report/USAGE.md](report/USAGE.md) · [report/references/document-style-rules.md](report/references/document-style-rules.md)
- 현업 발화 예시·함정·점검표·경고 사전: [GUIDE.md](GUIDE.md) · 실제 케이스 소스 20종: [report/examples/cases/](report/examples/cases/README.md)

## 참고 서식 — 사용자 .hwpx 의 서식으로 생성 (프로파일 추출)

"이 서식처럼 써줘" + 참고 `.hwpx` 가 있으면 그 문서의 **서식을 프로파일(템플릿 디렉토리)로 뽑아** 기존 조판(ai-report·report)이
그 서식으로 돌게 합니다. 1차 범위는 **단일 섹션 본문 스타일 근사**입니다 — 용지·여백·글꼴·제목/항목/산문/캡션 서식·표 서식을 가져오고,
표지·결재란·머리말/꼬리말·다중 섹션은 경고 후 본문 서식만 씁니다.

```bash
# 1) 참고 문서 → 프로파일(디렉토리 이름이 곧 템플릿 id). 폴백·경고는 stderr 와 manifest.json 에 남는다
python3 "${SKILL_DIR}/report/scripts/derive_profile.py" analyze .itda-skills/참고.hwpx -o .itda-skills/우리서식 --layout ai-report
# 2) 마크다운 → DocSpec (layout 은 1 과 같은 이름)
python3 "${SKILL_DIR}/report/scripts/md_to_docspec.py" .itda-skills/report.md -o .itda-skills/spec.json --layout ai-report
# 3) 그 프로파일로 생성 (--template 과 함께 쓸 수 없다 — --template 은 내장 id 전용이라 경로를 주면 거부한다)
PYTHONPATH="${SKILL_DIR}/report${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m hwpx_report convert .itda-skills/spec.json -o .itda-skills/report.hwpx --template-dir .itda-skills/우리서식
# 4) 서식이 실제로 실렸는지 속성 대조 (글꼴·크기·굵기·정렬·들여쓰기·용지·여백·표) — 불일치면 exit 2
python3 "${SKILL_DIR}/report/scripts/derive_profile.py" compare .itda-skills/우리서식 .itda-skills/report.hwpx --ref .itda-skills/참고.hwpx
```

- 본문 문단이 가장 많은 섹션을 채택한다(표지 섹션이 앞에 와도 된다 — 어느 섹션을 썼는지 경고·manifest `source_section`).
  마커(□ ○ ― ※ · Ⅰ. 1. 가.)와 굵기·크기로 층위를 추정해 **최빈 서식**을 뽑는다. 문단마다 서식을 손조정한 문서는 대표 서식이 원본과
  다를 수 있다 — 그 사실을 사용자에게 말한다. 못 찾은 층위는 내장값을 참고 문서 글꼴로 합성하고 경고한다(`--strict` 면 exit 2).
- `--template` 은 내장 id 전용이고 경로를 주면 거부한다 — 프로파일은 반드시 `--template-dir`(프로파일 이름이 `ai-report` 여도 내장이 아니라 그 디렉토리를 쓴다).
  `compare` 결과의 `fallback_styles` 는 참고 문서가 아니라 합성 내장값과 일치한 스타일이다(`--strict` 면 비어 있지 않을 때 exit 2).
- 지원 조판은 `ai-report`(기본)·`report` 두 종(기안문·briefing 비지원). 상세: [report/USAGE.md §참고 서식 프로파일](report/USAGE.md)

## 입력 안전 한계 — 압축 폭탄·위조 ZIP·DOCTYPE

읽기·채우기·참고 서식은 사용자가 받은 파일을 그대로 열므로, 풀기 **전에** 선언 크기로, 푸는 **동안** 실제 바이트로 잰다.
다음이면 트레이스백 대신 무엇이 걸렸는지 말하고 멈춘다(읽기 exit 2 · 채우기 exit 1 · 참고 서식 exit 1, 쓰다 만 결과는 지운다).

- ZIP 엔트리 500개 초과(정상 문서는 수십 개) · 압축을 푼 크기 256MB 초과(HWPX 합계, HWP 5 는 스트림 해제 합계)
- 저장·deflate 가 아닌 압축 방식, 선언 크기 위조, 경로 탐색 이름(`..`·절대경로), XML 의 DOCTYPE(정상 한글 문서에 없다)

정상 문서가 걸리면 상한을 올린다: `ITDA_MAX_UNZIP_MB`(MB, 최대 8192) · `ITDA_MAX_ZIP_ENTRIES`(최대 65535). 실 공고 첨부 164건
(최대 78MB·33엔트리 — 77MB BMP 가 든 공고)에서 거짓 양성 0.

## 공통 마무리

- Cowork 환경(`CLAUDE_CODE_IS_COWORK=1`)에서는 산출물을 `mnt/outputs/` 로 복사합니다.
- 실패(exit code != 0) 시 stderr 를 그대로 전달합니다. 무성 success 금지.
- 이 스킬은 **생성물 검증까지가 한 사이클**입니다: 생성·채움 후 읽기 경로로 열어
  텍스트를 확인하는 것을 기본 동선으로 삼으세요.
