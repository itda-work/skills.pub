> 이 문서는 통합 hwpx 스킬의 report 경로 상세 사용법이다 (구 hwpx-report SKILL.md).
> 아래 `SKILL_DIR` 블록은 통합 스킬의 `report/` 서브트리를 가리키도록 갱신되어 있다.
> `requirements.txt` 는 스킬 루트로 병합: `"${SKILL_DIR}/../requirements.txt"`.

# 마크다운 → 정부 보고서 HWPX (hwpx 서식 생성)

Claude(또는 사용자)가 **마크다운으로 쓴 보고서**를 대한민국 정부 범용 한글 서식
`.hwpx`(gov-report 템플릿)로 변환합니다. LLM 의 강점(콘텐츠 작성)과 엔진의 강점
(서식 보존 생성)을 분업합니다.

이 스킬은 **생성(쓰기) 전용**입니다. 반대 방향(HWP/HWPX → 마크다운 읽기)은 reader 경로를 쓰세요(../reader/USAGE.md).

## 설계 원칙

- **Python 네이티브 생성**: `hwpx_report` 패키지가 gov-report/press-release 템플릿 기반 HWPX 생성을 전담합니다.
- **결정론 매퍼**: `scripts/md_to_docspec.py`(표준 라이브러리 전용)가 마크다운을 엔진 입력(DocSpec JSON)으로 변환합니다.
- **무성 success 금지**: 변환 경고(평탄화·clamp·문단 변환)와 산출 경로를 항상 사용자에게 보고합니다.

---

## 사전 준비: Python 실행 환경

`hwpx` CLI 바이너리는 필요 없습니다. 이 스킬은 포함된 Python 패키지(`hwpx_report`)로 HWPX ZIP을 직접 생성합니다.

- Python 3.10+가 필요합니다.
- 먼저 스킬 디렉토리 경로를 `SKILL_DIR` 로 확정합니다 (이하 모든 명령이 이 변수를 사용):

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/hwpx}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/hwpx' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 스킬 루트(SKILL.md 위치) 절대경로를 그대로 사용
SKILL_DIR="$SKILL_DIR/report"
```

```powershell
$env:SKILL_DIR = "$env:CLAUDE_PLUGIN_ROOT\skills\hwpx\report"  # 미설정이면 SKILL.md 위치 절대경로 사용
```

- 이미지를 넣는 보고서는 크기 산정을 위해 `Pillow`가 필요합니다. 누락 시 다음처럼 설치합니다.

```bash
python3 -m pip install -r "${SKILL_DIR}/../requirements.txt"
```

```powershell
py -3 -m pip install -r "$env:SKILL_DIR\..\requirements.txt"
```

---

## 워크플로 (2단계)

### 준비 — 마크다운 파일 확정

입력 마크다운을 쓰기 가능한 작업 경로에 둡니다.

```bash
mkdir -p .itda-skills
cp <입력보고서.md> .itda-skills/report.md
```

보고서 구조 규약은 아래 [마크다운 작성 규약](#마크다운-작성-규약)을 따릅니다.
사용자가 자유 형식 텍스트만 줬다면, 먼저 그 규약에 맞춰 개조식 마크다운으로 정리합니다.

### 1단계 — DocSpec 변환

```bash
# macOS/Linux
python3 "${SKILL_DIR}/scripts/md_to_docspec.py" .itda-skills/report.md -o .itda-skills/spec.json

# Windows
py -3 "$env:SKILL_DIR\scripts\md_to_docspec.py" .itda-skills\report.md -o .itda-skills\spec.json
```

- 제목/보고일/부서는 마크다운 front-matter 또는 인자로 지정합니다.
  - front-matter 미지정 시: `--title "제목" --date "26. 6. 8." --dept "전략기획팀"`
  - 인자가 front-matter 보다 우선합니다.
- 매퍼는 **경고를 stderr 로** 출력합니다(평탄화·clamp·문단 변환·제목 누락). 경고가 있으면 사용자에게 그대로 전달합니다.

### 2단계 — HWPX 생성 + 제시

```bash
# macOS/Linux
PYTHONPATH="${SKILL_DIR}${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m hwpx_report convert .itda-skills/spec.json -o .itda-skills/report.hwpx --template gov-report

# Windows PowerShell
$env:PYTHONPATH = "$env:SKILL_DIR;$env:PYTHONPATH"
py -3 -m hwpx_report convert .itda-skills\spec.json -o .itda-skills\report.hwpx --template gov-report
```

- `--template <내장 id>` 대신 `--template-dir <프로파일 디렉토리>` 를 주면 [참고 서식 프로파일](#참고-서식-프로파일-derive_profilepy)로
  생성한다(둘을 함께 주면 argparse 가 exit 2 로 거부). `--template` 은 **내장 id 전용** — 경로 구분자·디렉토리를 주면 거부한다.
  `--template-dir` 는 내장 id 우선 규칙을 타지 않고 그 디렉토리를 직접 로드하므로 프로파일 이름이 `ai-report` 여도 내장이 선택되지 않는다.
  디렉토리 로더는 실존·필수 4파일·manifest `id` = **사용자가 준 경로의 basename**·언어별 fontRef 실재를 검사하고, 심볼릭 링크 루트는 거부한다.
  DocSpec `table.template` 이름은 `[A-Za-z0-9_-]+` 만 허용하며(루트 밖 파일 접근 차단), 없는 표 템플릿은 `basic` 으로 대체하되 stderr 경고를 낸다.
- 생성 성공 메시지(`보고서 HWPX 생성 완료: ...`)와 출력 경로를 사용자에게 보고합니다.
- Cowork 환경(`CLAUDE_CODE_IS_COWORK=1`)에서는 `.hwpx` 를 `mnt/outputs/` 로 복사합니다.
- 실패(exit code != 0) 시 stderr 를 그대로 전달합니다.

---

## 조판(layout)과 템플릿 — 2026-09 (#1651)

템플릿 manifest 의 `layout` 이 본문 조립 방식을 정한다. 매퍼 `--layout` 과 엔진 `--template` 은 같은 이름을 쓴다.

| layout / template | 용도 | 항목 계층 | 절 제목 | 표 | 특이 사항 |
|---|---|---|---|---|---|
| `ai-report` (권장) | 행안부 AI 친화적 보고서 원칙(2026-08-24) | 3단 `○` `-` `·`(또는 `item_markers: outline` → `가.` `1)` `가)`) | `1.`(또는 `section_numbering: roman` → `Ⅰ.`) 굵은 평문 | 위에 `< 표 N. 제목 >`, 제목 없으면 경고 | 산문 문단 보존, 제목 박스·섹션바 없음, 메타 줄 `보고유형 / 날짜 / 부서 담당자` |
| `official-letter` | 기안문(공문) | 4단 `1.` `가.` `1)` `가)` 자동 번호(형제 1개면 기호 생략) | 절 제목이 있으면 1단계 항목으로 승격 | 표 뒤에 끝나면 `  끝.` 별도 줄 | 수신·(경유)·제목·붙임·`끝.`·발신명의·시행 정보, 날짜 `2026. 9. 6.` |
| `briefing` | 표지·목차·섹션바 내부보고서(장식형) | 4단 `□` `○` `―` `※` | 로마숫자 섹션바(1×3 표) | 종전 | 표지(기관명·제목·작성일)·목차 자동, 페이지 나눔 2회 |
| `press-release` | 보도자료 | 2단 `□` `❍` + **산문 문단 보존**(리드문·인용) | 종전 | 표 지원(v1.2.0) | `--layout press-release` = report 조판 + 산문 보존 |
| `report` → `gov-report` | 종전 계약(구 개조식) | 2단 `□` `❍`(산문은 □ 로 변환·경고) | 종전 | 종전 | 변경 없음(회귀 골든 불변) |

front-matter / `--field` 로 주는 값 (한글 키 별칭 포함):

| 키 | 별칭 | 쓰는 조판 |
|---|---|---|
| `org` | 기관명·기관 | official-letter(상단 기관명) · briefing(표지) |
| `receiver` / `via` / `sender` | 수신 / 경유 / 발신명의·발신 | official-letter |
| `drafter` / `reviewer` / `approver` | 기안자·담당자 / 검토자 / 결재자 | official-letter(하단) · ai-report(메타 줄 담당자) |
| `doc_no` / `address` / `phone` / `email` / `cooperator` / `disclosure` | 문서번호 / 주소 / 전화 / 전자우편·이메일 / 협조자 / 공개구분 | official-letter(시행 정보·하단). 기안자·검토자·결재권자는 **직위 성명**으로 주면 용어 없이 그대로 실린다 |
| `report_type` | 보고유형·보고 유형 | ai-report(메타 줄, 예: 서면보고) |
| `attachments` | 붙임 (`\|` 로 구분) | official-letter(붙임 목록 + 끝.) · briefing(목차 [붙 임]) |
| `item_markers` / `section_numbering` | — | ai-report(`symbol`\|`outline` / `digit`\|`roman`) |

`--max-level` 은 layout 기본값(report·press-release 2 · ai-report 3 · 그 외 4)을 덮어쓴다.

**ai-report 표·그림 제목 규칙(v1.2.0)** — 표·그림 **바로 위** 줄의 `< 제목 >`(또는 `표 1. 제목`)을 제목으로 붙인다. 번호는 등장 순서로
엔진이 매기며 사용자가 쓴 번호는 벗기고 어긋나면 경고한다(`표준 …`처럼 낱말이 "표"로 시작해도 번호 표기로 오인하지 않는다).
이미지는 `![제목](경로)` 의 대체텍스트를 제목으로 쓰고, 제목·대체텍스트가 둘 다 없으면 경고한다. 절 번호는 전부 사용자가 쓴 경우만
유지하고 일부만 쓰면 전부 자동으로 다시 매긴다. `item_markers: outline` 은 절 번호 축에 따라 시작점이 달라진다
(`digit` → `가. 1) 가)`, `roman` → `1. 가. 1)`). 사용자가 `□ ○ ― ※` 기호를 직접 쓴 줄은 그 기호의 계층으로 들어간다. 규격 근거: [references/document-style-rules.md](references/document-style-rules.md).

## 마크다운 작성 규약

엔진 입력은 **개조식(□/❍)** 정부 보고서입니다. 마크다운을 다음 규약으로 작성하면 의도대로 변환됩니다.

| 마크다운 | 결과 | 비고 |
|---|---|---|
| `# 제목` | 보고서 제목 | 최초 1개만. 머리글에 들어감 |
| `## 1. 개요` 또는 최상위 `1. 개요` | 섹션 제목 | 번호는 보존됨 |
| `- 항목` / `* 항목` | level 1 항목(□) | 들여쓰기 없음 |
| `  - 하위` (들여쓰기) | level 2 항목(❍) | 1단계 중첩 |
| `### 소제목` | 섹션으로 평탄화 | 깊은 계층은 비목표(경고) |
| 3단계 이상 중첩 | level 2 로 clamp | 경고 |
| 일반 문단 | level 1 항목(□) | 개조식 변환(경고) |
| 마크다운 표 `\| … \|` | 표(basic 템플릿) | 헤더+구분선+행 → 데이터를 컬럼에 배치 + 구분선 **열 정렬**(`:--`/`--:`/`:-:`) 본문 셀 반영. 그 외 서식은 아래 한계 참조 |
| 단독 줄 이미지 `![alt](src)` | 이미지(본문 임베드) | 로컬 파일을 BinData 로 임베드 + 가운데 정렬 배치(소스 순서 보존). 원격 URL 은 제외+경고 |

**메타데이터 경고**: `report_date` 미지정 시 엔진이 생성 시점의 오늘 날짜로, `dept` 미지정 시 머리글에 템플릿 기본 `부서명` 자리표시자가 남습니다. 매퍼가 경고하니 가급적 front-matter 또는 `--date`/`--dept` 로 지정하세요.

**번호 목록의 모호성**: `## 으로 연 섹션 안의 최상위 `1.`/`2.` 는 **순서 목록 항목(□)** 으로 처리됩니다.
`#`/`##` 제목이 전혀 없는 순수 번호 문서에서만 `1.`/`2.` 가 섹션 제목이 됩니다.

**표 지원 범위 (현재) / 향후 발전**: 마크다운 표는 **헤더·행·열 구조와 셀 데이터를 그대로 표로 변환**합니다(정상 표 → 전 셀 데이터가 올바른 컬럼에 배치). **열 정렬**(`:--` 좌 / `--:` 우 / `:-:` 중)은 구분선에서 캡처해 **본문 셀**에 반영합니다(헤더 셀은 보고서 관례상 항상 중앙 정렬, 콜론 없는 `---`은 중앙 유지). **표 위치**는 마크다운 소스 순서를 보존합니다 — 한 섹션 안에서 항목과 표가 나타난 순서대로 렌더되며, 표 앞뒤 설명이 의도한 위치에 옵니다(항목 사이에 낀 표는 `blocks` 로 방출, 표가 항목들 뒤에 몰려 있으면 기존 `items`/`tables` 유지). **셀 내 서식**(굵게 `**x**`/`__x__`, 기울임 `*x*`/`_x_`)은 **본문 셀**에서 run 단위로 보존합니다(서식 있는 표만 `rich_rows` 오버레이 방출, 링크는 가시 텍스트로 평문화, 헤더 셀은 평문 유지). **열 너비**는 내용에 비례합니다 — 각 열의 최대 표시폭(한글 2배)에 비례한 `col_widths` 가중치로 분배해 긴 내용 열은 넓게, 짧은 열은 좁게 배치합니다(엔진이 `table-width` 로 정규화). 단, 아래는 **현재 미반영 — 비목표(향후 발전 사항)**입니다. 필요해지면 별도 기획으로 이슈를 등록합니다:

| 항목 | 현재 | 향후 |
|---|---|---|
| 셀 병합·중첩 표·셀 내 이미지 | 미지원 | (FILL/ANALYZE 권장) |

> 데이터 누락 주의: 한 행의 셀이 헤더보다 **많으면** 초과분이 절단(경고)됩니다 — 행별 열 수를 헤더와 맞추세요(부족분은 빈 셀로 패딩).

**보고일 형식**: `YY. M. D.`(예: `26. 6. 8.`)를 권장합니다. 연도 2자리가 머리글의 연도 자리(`'YY`)에 들어갑니다.

**front-matter 예시**:

```markdown
---
title: AI 기반 연구지원 현황 보고
report_date: 26. 6. 8.
dept: 전략기획팀
---

## 1. 추진 배경
- 핵심 현황 한 줄
  - 세부 근거
```

지원 키 별칭: `title`/`제목`, `report_date`/`date`/`보고일`/`일자`, `dept`/`department`/`부서`/`부서명`.

---

## 참고 서식 프로파일 (derive_profile.py) — 2026-09 (#1653)

사용자가 준 **참고 `.hwpx`** 의 서식을 프로파일(템플릿 디렉토리)로 추출해 기존 조판이 그 서식으로 돌게 한다.
1차 범위는 **단일 섹션 본문 스타일 근사** — 다중 section(첫 section 만)·머리말/꼬리말·마스터페이지·쪽번호·표지/결재란
(짧은 표 + 페이지 나눔)·내장 글꼴은 **경고 후 본문 서식만** 채택한다.

```bash
# 추출 — 출력 디렉토리 이름이 곧 템플릿 id(--id 를 주면 디렉토리명과 같아야 한다)
python3 "${SKILL_DIR}/scripts/derive_profile.py" analyze 참고.hwpx -o 우리서식 [--layout ai-report|report] [--strict]
# 생성 — 위 2단계의 --template 대신
python3 -m hwpx_report convert spec.json -o out.hwpx --template-dir 우리서식
# 게이트 — 산출이 참고 서식을 실제로 실었는가(속성 대조). --ref 가 정본, 없으면 manifest 기대값(자기 오라클)으로만 대조
python3 "${SKILL_DIR}/scripts/derive_profile.py" compare 우리서식 out.hwpx --ref 참고.hwpx
```

| 산출 | 내용 |
|---|---|
| `header.xml` | 참고 문서 것을 그대로(글꼴·charPr·paraPr·borderFill) + 합성 폴백 추가분. `secCnt=1` 로 정정 |
| `manifest.source_section` | 본문 서식을 뽑은 섹션 — **최상위 텍스트 문단이 가장 많은 섹션**(표지가 section0 인 정부 문서에서 본문 섹션을 고른다). secPr 도 그 섹션 첫 문단 것 |
| `style-map.json` | 층위별 **최빈 (paraPr, charPr)** — 최상위 문단을 마커(□ ○ ― ※ · ㅇ ◦ - ⇒ / Ⅰ. / 1. / 가. / 1) / 가))와 굵기·크기로 분류해 조판이 쓰는 스타일 이름 전부(ai-report 11종·report 6종 + 표 10종)에 대응 |
| `section0.skel.xml` | 참고 첫 문단의 `secPr`(용지·여백·colPr) 보존. 첫 문단에 붙은 표·그림 개체는 `objects/` 로 분리(조판 미사용) |
| `tables/basic.xml` | 데이터 표(행 ≥ 3·열 2~12·본문 안·글자 40자+) 하나에서 테두리·셀 서식 추출. 없으면 gov-report 표 구조 계량값을 참고 서식으로 합성 + 경고 |
| `manifest.json` | `id`·`layout`·`derived_from{file, sha256[:12]}`·`fallback`(못 채워 합성한 스타일)·`warnings`·`body_width`·`profile`(기대 속성) |

- **폴백은 조용하지 않다** — 못 찾은 스타일은 내장 ai-report/gov-report 계량값(크기·굵기·정렬·들여쓰기)을 **참고 문서 본문 글꼴로 합성**해
  header 끝에 덧붙이고 stderr `경고:` + manifest `fallback` 에 남긴다. `--strict` 면 폴백·경고가 하나라도 있으면 exit 2.
- **게이트는 속성 대조다** — `validate_report_template`·역변환 순서 일치는 추출이 no-op 이어도 통과하므로 게이트가 못 된다.
  `compare` 는 산출 header/section 에서 실제 쓰인 스타일을 역참조해 글꼴 이름·height·bold·italic·align·left/intent/prev/next·줄간격 +
  용지/여백 + 첫 표의 폭·머리글/본문 셀 테두리·채움·글꼴을 대조한다(JSON, exit 0 일치 / 2 불일치 / 1 오류; 쓰인 스타일이 0 이면 exit 2).
  산출에서 쓰이지 않은 스타일도 style-map 값 자체를 기대값과 대조한다(`unused` 는 보고 필드). `fallback_styles` 는 참고 문서가 아니라 합성
  내장값과 일치한 스타일 목록이며 `--strict` 면 비어 있지 않을 때 exit 2 — "무엇을 근사했는가" 를 게이트가 말한다.
- **한계**: paraPr 이 줄마다 손조정된 문서는 "대표 서식" 이 원본과 다를 수 있다. 본문 전체가 표 안에 있는 문서는 최상위 텍스트 문단이 0 이라
  전 스타일 폴백(경고로 표면화). 지원 layout 은 `ai-report`·`report` 두 종(`official-letter`·`briefing` 비지원). `compare` 는 첫 최상위 표만 대조.
  한컴 실렌더는 사용자(또는 Parallels 한글)에서 확인하는 것이 정본이다.

## 비목표 (1차)

- **복잡한 표** — 셀 병합·중첩 표·표 안 이미지는 비목표입니다. 정교한 표는 사용자 양식 + FILL/ANALYZE 경로를 쓰세요.
- **이미지** — 단독 줄 `![alt](src)`(로컬/상대 경로)는 본문에 임베드합니다. 상대 경로는 입력 마크다운 파일 위치 기준으로 해석합니다. 큰 이미지는 본문 폭에 맞춰 비율 유지 축소(fit-to-page). 원격 URL(http/https/data)·셀 내 이미지·캡션 자동생성·리사이즈는 비목표(제외+경고). 텍스트에 섞인 이미지는 평문화. **신뢰 경계**: `src` 는 경로 격리 없이 그대로 읽어 임베드하므로(상대 경로 traversal·절대 경로 허용), 마크다운은 신뢰 가능한 출처여야 합니다(임의 로컬 파일 노출 방지).
- **3단계 이상 중첩 / inline 서식** — 깊은 계층은 level 2 로 clamp, `**굵게**`·`[링크](url)`·`` `코드` `` 는 평문으로 strip.
- **조직별 맞춤 서식** — 사용자가 자기 양식을 가져오는 경우입니다. 빈칸·안내문 양식이면 통합 hwpx 스킬의 채우기 경로(`../scripts/fill_hwpx.py`),
  참고 문서 + 새 내용이면 [참고 서식 프로파일](#참고-서식-프로파일-derive_profilepy)(단일 섹션 본문 근사 — 표지·결재란·머리말은 비목표)을 쓰세요.

---

## 에러 처리

| 상황 | 대응 |
|---|---|
| `No module named PIL` | `python3 -m pip install -r "${SKILL_DIR}/../requirements.txt"` 실행 안내 |
| `No module named hwpx_report` | `PYTHONPATH="${SKILL_DIR}..."` 설정 누락 여부 확인 |
| 매퍼가 제목 경고 출력 | `--title` 인자 또는 `# 제목` 추가 안내 |
| 생성 실패(exit != 0) | stderr 전달. spec.json 의 `level` 이 1/2 인지 확인 |
| 이미지 파일 읽기 실패 | 이미지 경로가 로컬에서 접근 가능한지 확인 |
| 생성 archive 검증 실패 | stderr 전달. 입력 spec과 템플릿 자산을 보존하고 이슈로 추적 |

---

## 테스트

매퍼와 Python 네이티브 생성 테스트(한컴 불필요):

```bash
# macOS/Linux
python3 -m pytest tests

# Windows
py -3 -m pytest tests
```
