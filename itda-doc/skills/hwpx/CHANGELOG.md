# Changelog — itda-hwpx

## [1.3.1] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- `.hwp` 변환 대안과 누름틀 채움 안내에서 hyve MCP(`hwpx.from_hwp`·`hwp` 도메인) 언급을 뺐다. 동작 변화 없음.

## [1.3.0] — 2026-09-07 (#1653)

jkf87/hwpx-skill(MIT) 대조 검토·Codex 적대 리뷰(`docs/research/hwpx-skill-review-jkf87/`)에서 실측된 공백을 닫았다 — 채우기가 조용히 놓치던 세 클래스
(글꼴이 다른 run 분절·혼동문자·인라인 컨트롤), 빈 셀 채움 불가, 요청 서식이 내장 조판 밖이면 답이 없던 것. 채우기·프로파일 코어는 표준 라이브러리 단독을 유지한다.

### Added

- **채우기 문단 단위 매처**(`scripts/hwpxfill/` 패키지, `scripts/fill_hwpx.py` 는 진입점 유지) — run 경계·`charPrIDRef` 차이와 무관하게 문단 텍스트에서 키를 찾아
  첫 조각에 값 전체를 두고 나머지 조각의 겹침만 지운다. 전각 공백은 공백 하나로 정규화하고 탭·줄바꿈·필드를 가로지르는 키는 절대 맞지 않는다(fail-closed).
  치환 전후 컨트롤 태그 시퀀스 동일 자기검사.
- `--check [--fix OUT.json] [--json]` 사전검증 — 키마다 ok / fixable(혼동문자·공백 차이, 교정안은 원문의 **대응 부분문자열**) / ctrl(나눔안) / multi / missing. 문제가 있으면 exit 2.
  교정안이 겹치는 두 키는 collision(파일 미생성·exit 2). 접기는 결합 시퀀스 단위 NFC(NFD 한글도 잡는다).
- `--residue 원본.hwpx [--keep 문구] [--json]` 잔재 대조 — 매핑 키 잔존·원본 **안내문 후보 문단**(`{{}}`·《》 마커 또는 `입력/작성/기재하세요`·`써 주세요`·○○·___ 같은 명령형·자리표시 문맥)·
  키로 자른 세그먼트 잔존(마커·안내 어휘가 있는 것만)·**치환값 커버리지**(원본에 있던 키의 값이 결과에 없으면 value_missing)를 잡는다. 잔재가 있으면 exit 2.
- `--dump` 를 문단 단위(`번호⇥위치⇥플래그⇥텍스트`, 표 좌표·`EMPTY`·`CTRL`)로. 미발견 경고가 `--check` 안내로.
- **빈 칸 채움** — `--cell "표i rN cM=값"`(좌표, self-closing `<hp:t/>`·run 없는 셀도 채움), `--label "라벨=값"`(논리 그리드에서 오른쪽→아래 빈 셀, 병합·중첩 표·0/2+건 거부), `--tick 항목`(□→☑).
- 옵트인 위생 `--strip-lineseg`(변경 문단의 줄 배치 캐시 제거)·`--refresh-preview`(미리보기 텍스트 재생성) — 한컴 실측 후 기본값 결정.
- **참고 서식 프로파일** `report/scripts/derive_profile.py analyze 참고.hwpx -o 프로파일/ [--layout ai-report|report] [--strict]` — 본문 문단이 가장 많은 섹션 채택(`source_section`), header 재사용,
  층위별 최빈 서식을 style-map 으로, secPr 보존 골격, 데이터 표 서식 추출, 폴백은 언어별 fontRef 를 보존해 합성 + 경고 + manifest 기록.
  `compare 프로파일/ out.hwpx --ref 참고.hwpx` 속성 대조 게이트(글꼴·크기·굵기·정렬·들여쓰기·용지·여백·표, 미사용 스타일도 대조, `fallback_styles` 보고·`--strict` exit 2).
- `python -m hwpx_report convert --template-dir 프로파일/` — 커스텀 템플릿 디렉토리 로더(`--template` 은 내장 id 전용·경로 거부, 필수 파일·id = 준 경로 basename·언어별 fontRef 실재 검사,
  심볼릭 링크 루트 거부, `table.template` 이름 제한·루트 이탈 차단, 없는 표 템플릿은 경고 후 basic).
- SKILL.md 라우팅 3분기(빈칸 양식 → 채우기 / 참고 문서 + 새 내용 → 프로파일 생성 / 파일 없음 → 내장 조판)와 입력 형태별 계약표(`.hwp`·PDF·구두 요청).
- 기안문 매퍼: 소스에 직접 쓴 규정 항목기호(`가.`·`1)`·`가)`)를 그 계층으로 해석(종전 `3. 가. 일시` 이중 번호). 경고 문구를 조판별로("번호 항목으로 변환").
- 샘플 카탈로그 `report/examples/cases/v13-samples/`(13종 + `run.sh` 일괄 재생성). **GUIDE.md 전면 재집필** — 기능 지도·읽기 옵션 전부·서식 5종(front-matter 전항)·채우기 4단계 전 기능·참고 서식·조합 시나리오·경고 사전·입력 형태별 약속·샘플 카탈로그, 지침은 `/hwpx …` 형식.

### Changed

- 채우기 매칭 계약이 `<hp:t>` 부분문자열에서 문단 단위로 바뀌었다. `merge_adjacent_runs` 폐기(테스트를 새 계약으로 갱신). `--dump` 출력 형식 변경.
- sentinel 정책은 "텍스트를 나누는가" 로 정의한다 — 탭·줄바꿈·필드·책갈피·그림·표·미지 컨트롤은 나눈다(fail-closed), `colPr`·`secPr`·쪽 번호 같은 무텍스트 레이아웃 컨트롤은 나누지 않는다
  (한컴이 셀 첫 run 에 넣는 `colPr` 를 접으면 실 양식의 `--label` 이 깨진다 — 2차 검수 시소 실측).
- 혼동문자 접기 표(`scripts/hwpxfill/fold.py`)는 jkf87/hwpx-skill(MIT, 96a2633) `map_preflight.py:FOLD` 의 데이터성 상수를 차용해 확장했다(README 차용 출처). 알고리즘·코드는 독자 구현.

### 검증

- pytest 272 passed(신규 100). v1.3 샘플 13종 전건 생성·역변환·프로파일 대조 통과. 2차 적대 검수(Codex gpt-5.6-sol 10건 + Claude 렌즈 9건, 전건 수용) 반영 — 형제 컨트롤 fail-closed·내부 표 라벨 거부·값 커버리지·후보 규칙 축소·
  fontRef 실재·미사용 스타일 대조·경로 격리·결합 NFC·collision·레이아웃 컨트롤 비분절·`--template-dir` 직접 로드·본문 섹션 채택·세그먼트 게이트.
  뮤테이션 RED 실측 21종(문단 매처→`<hp:t>` 매처 / sentinel 제거 / `--fix` 문단 전체 / 라벨 span·내부 표 거부 제거 / 안내문 판정 무력화 / 값 커버리지 제거 /
  compare 무력화·미사용 건너뜀 / 로더 디렉토리 무시·경로 검증 제거 / analyze no-op·section0 고정 / 여백 변조 등). 실 한컴 저장 픽스처(`large_table`·`multi_section_with_image`·
  `mixed_content`·`multi_image_formats`) `--dump`·`--check`·채움·`--label`·`--residue`·analyze/compare 스모크.
- 한컴오피스 HWP(macOS) 실측 2026-09-07: 실 한컴 저장본 채움 변형 4종(텍스트만 / +줄배치 캐시 제거 / +미리보기 갱신 / 둘 다) 전부 복구 경고 없이 원본과 동일 렌더 → 위생 옵션 기본 꺼짐 확정.
  신청서 채움본·안내문 채움본·참고 서식 생성본·AI 친화 보고서·기안문 정상 렌더. 미수행: 한글 저장 → 재열기 축, Windows 한컴(구독 해지). 기록 `docs/research/hwpx-skill-review-jkf87/live/`.

## [1.2.0] — 2026-09-06 (#1652)

서브에이전트 3기가 현업 시나리오 20종(AI 친화 보고서 6·기안문 6·표지형/구 개조식/보도자료/채우기/읽기 8)을 실제로 생성해
보고한 결함을 교정하고, 그 실측을 근거로 **현업용 GUIDE.md** 를 전면 집필했다. 케이스 소스는 `report/examples/cases/`.

### Added

- **GUIDE.md 현업판** — 서식별 "이렇게 말하면 → 이렇게 나온다", 작성 규약 표, front-matter 쿡북, 자주 나오는 경고와 처방,
  품질 점검표(행안부 원칙·행정업무규정), 양식 채우기 동선·함정, 읽기 옵션표, 경고 메시지 사전.
- 케이스북 `report/examples/cases/`(재생성 가능한 소스 20종 + 인덱스). 실험 원문은 `docs/research/hwpx-format-comparison-1651/experiments/`.
- 기안문 `협조자`·`공개구분` 필드. 매퍼 `--layout press-release`(보도자료 = report 조판 + 산문 보존). press-release 표 템플릿.
- ai-report: 이미지 무제목 경고, 사용자 캡션 번호 무시·불일치 경고, 절 번호 혼재 시 전부 자동 재매김, `outline`+`roman` 표준 체계
  (`Ⅰ. 1. 가. 1)`), 직접 타이핑한 `□ ○ ― ※` 줄을 기호 계층으로 해석.
- 리더: header paraPr 정렬을 셀 문단에 반영(HTML `text-align` — 열 정렬 왕복 검증 가능), 이미지 배치 크기(`sz`) 우선.
- `fill_hwpx --strict` 가 순차 잔여 자리도 exit 3. `--dump` 에 부분문자열 치환·기호 제외 안내.

### Fixed

- 기안문 서명 줄이 "기안자/검토자/결재자" 용어를 노출했다(별지 제1호서식 비고 위반) → 값(직위 성명)만. 시행 줄 `번호 (날짜)` → `번호(날짜)`.
  발신명의 누락·해석 불가 날짜가 무음 통과 → 경고.
- 보도자료에 표를 넣으면 매퍼 무경고 후 엔진 exit 1 → 표 템플릿 추가(구 Go 골든의 "에러가 정답" 계약 반전, 테스트에 이력).
- 읽기 md 의 `<img width>` 가 HWPUNIT 원값(36000) → 픽셀(480). 셀 문단 정렬이 역변환에서 소실.
- ai-report 캡션 판정이 `표준…`을 번호 표기로 오인해 번호 누락. `표 7.` 손 번호 그대로 출력. 절 번호 일부만 쓰면 `Ⅰ. → 1. → Ⅲ.`.
- clamp 경고가 "형제 번호로 재배치된다"는 의미 왜곡을 말하지 않았다 → 문구 보강.

### 검증

- pytest 172 passed(신규 15). 골든은 정렬 속성·이미지 픽셀 순증만(단어 손실 0 대조).

## [1.1.0] — 2026-09-06 (#1651)

외부 공개 스킬(Canine89/gonggong_hwpxskills)을 대조해 **양식 지식만** 가져오고(코드·템플릿 복제 없음), 행정안전부
「AI 친화적 보고서」 원칙(2026-08-24 보도자료 첨부 hwpx 실측)을 생성 경로의 권장 기본으로 삼았다.

### Added

- **조판(layout) 축** — 템플릿 manifest `layout`/`max_level` 로 본문 조립을 가른다(`report/hwpx_report/layouts.py`).
  header.xml 은 gov-report 것을 `report/scripts/derive_template_headers.py` 로 파생(멱등, `--check`).
  - `ai-report`(**권장**): 장식 표 없이 평문 제목 + `보고유형 / 날짜 / 부서 담당자` 메타 줄, `1.`(또는 `Ⅰ.`) 굵은 절 제목,
    `○ - ·`(또는 `가. 1) 가)`) 서술식 항목 3단, 표·그림 **위** `< 표 N. 제목 >`, 산문 문단 보존(`kind=prose`).
    매퍼 `--layout ai-report` 가 표 바로 위 `< 제목 >`/`표 N.` 줄을 제목으로 붙이고, 제목 없는 표를 경고한다.
  - `official-letter`(기안문): 행정업무규정 서식 원칙 — 항목기호 `1. 가. 1) 가)` 자동 번호(형제 1개면 기호 생략),
    2타 내어쓰기, 날짜 `2026. 9. 6.`, 붙임 목록 + 같은 줄 `끝.`(표로 끝나면 별도 줄), 발신명의·기안/검토/결재·시행 정보.
    매퍼 `--layout official-letter` 는 최상위 번호를 섹션으로 승격하지 않는다.
  - `briefing`: 표지(기관명·제목·작성일)·목차(자동)·로마숫자 섹션바(1×3 표)·`□ ○ ― ※` 4단 — 장식형이라 명시 요청 시만.
  - DocSpec `fields`·`attachments`, 표/그림 `caption`, 항목 `kind`. front-matter 한글 키 별칭(기관명·수신·경유·발신명의·기안자·담당자·
    검토자·결재자·문서번호·주소·전화·전자우편·보고유형·붙임). `--field KEY=VALUE`, `--max-level`.
  - 규격 참조 `report/references/document-style-rules.md`(1차 출처·판독일 명시), 예제 04~06.
- **채우기 `--dump`** — 양식 안 텍스트 전수(등장 순서·횟수). 마커 규약 없는 양식은 `--list` 휴리스틱이 일반 괄호만 잡았다
  (실측: 공공기관 보고서 양식에서 `(문단 위 15)` 류만 4종). **순차 치환** — 같은 키 `--set` 반복 / `--map` 배열 값을 등장
  순서대로 소비, 부족·잉여 모두 경고(남는 자리는 그대로 — 조용히 지우지 않는다).
- SKILL.md **양식 우선 원칙** — 사용자가 `.hwpx` 양식을 줬으면 생성이 아니라 채우기(그 기관 서식이 정답).

### Fixed

- **리더가 글상자(도형) 텍스트를 버렸다(R2)** — `rect/container` 등 `drawText` 안 문단을 수집하지 않아 정부 서식의 제목 박스가
  통째로 사라졌다. 우리 생성 엔진 산출을 우리 리더로 역변환하면 제목이 0건이라 "생성 후 읽기 교차검증" 동선이 제목 축에서
  공허했다. 도형 재귀 수집으로 복원(`_drawing_text_blocks`).
- **md 작성기가 셀 안 문단을 구분자 없이 이어 붙였다(R1)** — `브라더 공기관기본 보고서 양식`, `Ⅰ. 개요 1Ⅱ. 추진배경 2…`.
  문단 경계를 `<br>` 로 보존(`_render_cell`). 골든 갱신 전 단어 단위 전수 대조로 손실 0 확인(차이는 전부 `<br>` 분리·도형
  텍스트 순증). metrics 기대값 재계산(문단 273→279·461→485, 비어있지 않은 셀 199→208, 굵은 인라인 270→299).

### 검증

- 회귀 157 passed(신규 25: 도형·셀 경계 픽스처 단언, 순차 치환, 조판 3종 생성→리더 역변환 순서 단언, 번호 규칙, 매퍼 옵션).
  뮤테이션 3종(도형 미수집·구분자 제거·순차→일괄) RED 실측. gov-report/press-release 골든 불변.
- 6양식 비교 실험(`docs/research/hwpx-format-comparison-1651/`): 같은 주제로 gov-report 2종·보도자료·기안문·briefing·ai-report 생성 +
  외부 템플릿을 우리 채우기 도구로 채운 대조군. 대조군에서 템플릿 치환 방식의 한계(슬롯 수 고정 → 항목이 엉뚱한 절로 밀림,
  남는 안내문 수동 삭제)가 실측됐다.

## [1.0.3] — 2026-08-21

### Fixed

- **run 안의 여러 `<t>` 중 마지막만 남던 내용 손실 (#1536 ①)** — `_run_text` 가 `text = ...` 로 덮어써 run 의 **마지막 텍스트 조각만** 남겼다. 삭제된 Go 구현의 `encoding/xml` 이 반복 필드를 마지막 값으로 덮어쓰던 동작을 그대로 옮긴 것인데, **이식할 계약이 아니라 버그였다.**

  하이퍼링크·필드·각주 같은 제어 요소는 run 안에서 `<t>` 를 조각낸다. 그래서 그런 요소가 든 문단은 **앞부분 텍스트를 통째로 잃었다**:

  ```
  원문 <t> 3개 : '※ 건설산업지식정보 시스템('  'www.kiscon.net)'  ' 건설업체 정보조회 결과'
  구 산출      :                                                  ' 건설업체 정보조회 결과'
  ```

  기존 골든·metrics 기대값이 이 손실을 **박제**하고 있었다. 갱신 전 전수 대조로 **토큰 손실 0종·순증만** 확인했다(실제로 복원된 것: `□ 추진근거`, `청년 실업률 5.5%·확장실업률` 등). `paragraphs` 가 늘어난 것은 빈 문단이 실제 문단으로 살아난 결과다.

  회귀는 두 겹으로 고정한다 — `_run_text` 단위 테스트(제어 요소가 낀 실측 형태 포함)와, **골든을 잘못 갱신하면 함께 통과해 버리는** 바이트 비교를 보완하는 **문장 직접 단언**. 뮤테이션(구 동작 복원)에서 4건 RED 확인.

## [1.0.2] — 2026-08-21

### Fixed

- **HWP5 배포용 보호 문서의 무음 실패 (#1536 ③)** — 플래그 검사가 `flags & 0x02`(암호화)만 보고 **배포용 보호(`0x04`)를 통과시키고 있었다.** 그런 문서는 본문이 `BodyText` 가 아니라 `ViewText` 에 암호화되어 있어, `BodyText` 만 읽으면 문단 0개 → **3바이트 산출 + 종료코드 0** 이 된다.

  이 클래스가 위험한 이유는 **호출자가 구조적으로 못 잡기** 때문이다 — 변환기가 "성공했다" 고 말하므로, 모든 호출자에게 "산출 길이를 재라" 고 요구하지 않는 한 빈 문서가 조용히 통과한다. 실측(#1535, KACEM 입찰 첨부 227개)에서 1건 발생했고, 그 사실은 산출물을 열어 보고서야 드러났다.

  판정을 순수 함수 `check_readable_flags(flags)` 로 분리하고 배포용 보호를 명시 에러로 거부한다. 에러 메시지는 원인(`ViewText`)까지 말한다 — 다음 사람이 "왜 안 되지" 로 헤매지 않도록.

  검증: 실측 파일에서 **종료코드 0 → 1**, 출력 파일 미생성. 회귀 테스트 7건(실측 플래그 조합 `0b101` = 압축+배포 포함).

## [1.0.1] — 2026-07-28

### Added

- **통합 GUIDE.md** — 읽기/양식 채우기/서식 생성 3경로 사용자 가이드 신설(구 reader·report GUIDE 통합 + 채우기 절 신규). 게재 전 3경로 연결 실측으로 검증: 생성(gov-report, placeholder 포함) → `--list` 후보 탐지((부서명)×1·(담당자)×2) → 채우기(치환 횟수 보고) → 읽기 재변환에서 값 반영·개조식 구조 유지 확인.

## [1.0.0] — 2026-07-28 (hwpx 통합 스킬)

### Changed

- **hwpx-reader(v4.0.1) + hwpx-report(v0.3.3) 를 단일 `hwpx` 스킬로 병합** (마스터 지시, 미배포 상태라 별칭 없이 일괄 전환). 디렉토리: `reader/`(hwpx_native 읽기 엔진) · `report/`(hwpx_report 생성 엔진) · `scripts/fill_hwpx.py`(신규 채우기). 구 SKILL.md 는 `reader/USAGE.md`·`report/USAGE.md` 로 보존. 테스트는 `tests/{reader,report,fill}` 로 통합(스킬당 tests/ 단일 규칙). 버전은 1.0.0 에서 재시작하며 아래 항목들은 구 스킬 히스토리다.

### Added

- **양식 채우기 `scripts/fill_hwpx.py`** (표준 라이브러리 전용, hyve MCP 무의존): 기존 .hwpx 양식의 `Contents/section*.xml` 텍스트 placeholder 만 치환해 서식·표·번호 유지. `--list`(후보 탐지) / `--set`·`--map`(치환) / `--strict`. 동일 서식 인접 run 자동 병합(분절 placeholder 대응), mimetype 첫 엔트리·STORED 보존, 치환 후 XML 정합성 검사, 미발견 키 경고(무성 실패 금지). 테스트 8종(GREEN) — report 엔진 실산출물 채움 + `validate_archive` 교차 검증 포함.

모든 주요 변경사항을 기록합니다. [Keep a Changelog](https://keepachangelog.com) 포맷을 따릅니다.

## [4.0.1] — 2026-07-26 (이슈 #1274)

### Fixed

- 미정의 변수 `${CLAUDE_SKILL_DIR}` 제거 — Claude Code 세션에 존재하지 않아 빈 문자열로 전개(`pip install -r "/requirements.txt"` 등 조용한 실패). 요구 사항 절에 `SKILL_DIR` 확정 스니펫(Code=`$CLAUDE_PLUGIN_ROOT` / Cowork=세션 마운트 find) 신설, 전 명령 `${SKILL_DIR}` 로 통일.

## [4.0.0] — 2026-06-14

### Breaking Changes

- 외부 변환 바이너리 탐색과 Linux 번들 자동 추출을 제거했습니다.
- HWP5/HWPX 변환 경로가 스킬 내부 `hwpx_native` Python 패키지로 전환되었습니다.
- `scripts/find_hwpx.py`와 관련 테스트를 제거했습니다.

### New Features

- `python3 -m hwpx_native convert <input> -o <output> --format md|html` 엔트리포인트를 추가했습니다.
- HWPX Markdown/HTML 출력은 현 Go 엔진 기준 골든과 byte 단위로 검증합니다.
- HWP5 Markdown/HTML 출력은 삭제 전 Go HWP5 엔진 기준 골든과 byte 단위로 검증합니다.

### Compatibility

- Markdown 이미지 경로는 `<stem>/image_NNNN.ext` 정책을 유지합니다.
- HTML 변환은 이미지 데이터를 Base64로 임베드합니다.

## [3.0.2] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [3.0.1] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [3.0.0] — 2026-05-13 (SPEC-HWPX-DEFAULT-OFF-001)

### Breaking Changes

- **이미지 캡션 디폴트 OFF**: "이 hwp 읽어줘" 같은 기본 호출에서 Sonnet 서브에이전트 캡션 생성이 더 이상 자동 실행되지 않습니다. 이미지 추출 자체는 cli.hwpx 디폴트(O) 그대로 유지되므로, MD 본문에는 `![](path/to/image.png)` 가 alt 텍스트 없이 남습니다.
  - **마이그레이션**: 기존처럼 캡션을 받으려면 발화에 `"이미지 설명도"`, `"캡션 포함"`, `"이미지 분석해줘"`, `"이미지 설명 추가"` 중 하나를 추가하세요.
  - **이유**: 디폴트가 항상 Sonnet 서브에이전트를 호출하는 구조는 본문 요약·검색 인덱싱·대량 변환 시 토큰·시간이 과도하게 소모됨. 캡션은 명시 요청 시에만 비용을 지불하는 옵트인 모델로 전환.

### New Features

- **"본문만"/"텍스트만" 키워드 지원** (cli.hwpx v2.1.0+ 필요): 발화에 `"본문만"`, `"텍스트만"`, `"이미지 빼고"`, `"이미지 없이"` 중 하나가 있으면 CLI 호출에 `--no-extract-images` 가 부착됩니다. 이미지 디스크 IO 자체가 발생하지 않고 MD 본문에 `![](#image-omitted)` placeholder 가 주입됩니다. 본문 요약·검색·대량 변환 시나리오에 권장.
- **모순 요청 자동 가드**: "본문만" + "이미지 설명도" 가 동시에 등장하면 CLI 실행 전 AskUserQuestion 으로 의도를 재확인합니다 (cli.hwpx 의 `--no-extract-images` + `--require-images` 충돌 회피).

### Improvements

- **워크플로 ① 상단에 "이미지 옵션 매트릭스" 표 신설**: 4가지 케이스(디폴트 / 본문만 / 캡션 포함 / 모순) × CLI 호출 매핑을 한눈에 제시.
- **cli.hwpx 버전 호환성 표 추가**: v0.9.7 / v1.0.2 / v2.1.0 각 기능 라인 명시. v2.1.0 미만 환경에서 "본문만" 키워드 사용 시 디폴트 호출로 폴백 + 업그레이드 안내.
- **frontmatter description 갱신**: 자동 캡션 문구 → 옵트인 캡션 + "본문만" 키워드 안내로 교체.

### Compatibility

- cli.hwpx v2.1.0 이상에서 모든 기능 사용 가능 (Linux Cowork 는 SPEC-HWPX-AUTOFETCH-001 로 자동 페치).
- macOS/Windows 는 수동 업그레이드 필요. 미업그레이드 환경에서는 디폴트 호출은 정상, "본문만" 키워드만 무시됨.

### Measurements (예상 효과)

| 시나리오 | v2.7.0 | v3.0.0 디폴트 | v3.0.0 "본문만" |
|---------|--------|--------------|----------------|
| 본문 요약 (이미지 N개) | 추출 + N회 Sonnet 호출 | 추출만 + Sonnet 0회 | 추출 X + Sonnet 0회 |
| 캡션 포함 변환 | 추출 + N회 Sonnet 호출 | "이미지 설명도" 발화 시 동일 | (해당 없음) |
| 대량 변환 (M개 문서) | M×N 회 Sonnet 호출 | Sonnet 0회 | 디스크 IO 도 0회 |

실측 베이스라인은 evals/ 에 별도 추가 예정 (본 릴리즈에는 미포함).

## [2.7.0] — 2026-05-11 (SPEC-HWPX-DIFF-001 M3 통합)

### Improvements

- **Track A 실측 통합** (M3 완료): 한강·강북 보도자료 2건 실측 후 평균 집계. 추정치 전면 교체.
  - Track A 평균: 114,377토큰/회 (한강 116,988 + 강북 111,765).
  - 디버깅 라운드 실측 평균 4회 (한강 3회, 강북 5회) — 매번 다른 파서 코드 작성.
  - ratio_b_over_a (10회 누적): **0.003** — AC-DIFF-003 임계값(≤0.5) 약 185배 달성.
- **`compare_diff.py`에 `aggregate_track_a_samples()` 함수 추가** (TDD RED→GREEN):
  - 다중 Track A 샘플 JSON을 입력받아 평균 토큰/표 보존율/이미지 수 집계.
  - 신규 테스트 4개 추가 (`TestTwoSampleAggregation`), 전체 23개 테스트 통과.
- **SKILL.md description 실측 수치 인용으로 갱신** (REQ-DIFF-004):
  - "실측: 보도자료 1건당 클로드 단독 ~114,000토큰 vs 본 스킬 ~3,100토큰, 약 37배 절감" 문구.
  - evals 결과 파일 경로 및 측정일(2026-05-11) 명시.
- **README.md 비교표 견고성 행 추가** (REQ-DIFF-002):
  - 실측 수치로 전면 갱신: "1회 호출 토큰 ~114,000 vs ~3,100", "10회 누적 ratio=0.003".
  - 디버깅 라운드 행 추가: "평균 4회 vs 0회".
  - 표 보존율 실측값 반영: "0.625 (실측 평균)" vs "한국 공공기관 규격".
  - 실측 출처 (hangang.json + gangbuk.json) 명시.

### Measurements (실측 2 샘플 — 한강·강북 보도자료)

| 지표 | Track A (클로드 실측 평균) | Track B (hwpx 실측) |
|------|--------------------------|---------------------|
| tokens_per_call | 114,377 (실측 평균) | 3,113 (실측) |
| 10회 누적 토큰 | ~1,143,770 | ~28,017 |
| ratio_b_over_a (10회) | — | **0.003** |
| 디버깅 라운드 | 평균 4회 | 0회 |
| 표 보존율 | 0.625 (실측 평균) | 평탄화 규칙 적용 |
| 이미지 캡션 | 0 | Sonnet 자동 |

> 측정: `evals/results/track_a_hangang.json` + `track_a_gangbuk.json`, 2026-05-11.
> AC-DIFF-003 ratio ≤ 0.5 임계값 달성 (0.003). SPEC-HWPX-DIFF-001 `Implemented` 전환.

## [2.6.0] — 2026-05-11 (SPEC-HWPX-DIFF-001)

### New Features

- **`evals/compare_diff.py`** 신규 추가 — SPEC-HWPX-DIFF-001 3-way 비교 측정 도구.
  - `measure_track_b()`: hwpx 변환 산출물(md+이미지 디렉토리) 자동 측정.
  - `calc_cumulative_cost()`: Track A/B 10회 누적 토큰 및 ratio 계산.
  - `calc_breakeven()`: Track B 누적이 Track A보다 저렴해지는 최초 호출 횟수 계산.
  - `count_tables_in_markdown()`: `| --- |` 패턴 기반 표 개수·셀 수 측정.
  - `count_images_in_dir()`: 이미지 디렉토리 glob 기반 추출 개수 측정.
  - `load_track_a_result()`: 외부 오케스트레이터가 제공하는 Track A JSON 통합.
  - 결과 저장: `evals/results/SPEC-HWPX-DIFF-001-{YYYYMMDD}.json`
- **`evals/tests/test_compare_diff.py`** 신규 추가 — 19개 단위 테스트 (TDD RED→GREEN).

### Improvements

- **SKILL.md description 차별화 명시** (REQ-DIFF-001):
  - "(1순위) 즉시 1회 호출 — 매번 스크립트 작성 불필요" 키워드를 첫 문장에 배치.
  - "(2순위) 표 평탄화 + (3순위) 이미지 자동 캡션" 순으로 배치.
  - "본문만 필요한 가벼운 케이스는 클로드 단독도 가능" 정직한 안내 추가 (REQ-DIFF-005a).
- **README.md 비교표 신설** (REQ-DIFF-002):
  - "클로드 단독 vs hwpx 스킬" 11행 비교표 추가.
  - 재사용성 3개 행 (1회 호출 비용 / 10회 누적 / 새 엣지케이스) 포함 — v0.3.0 신설.
  - 클로드 단독의 HWP5 본문 추출 가능성 명시적 인정.
  - "언제 클로드 단독 / 언제 본 스킬" 사용 안내 섹션 추가.

### Measurements (PoC — 한강 보도자료 1개, Track A 추정치)

| 지표 | Track A (클로드 추정) | Track B (hwpx 실측) |
|------|----------------------|---------------------|
| tokens_per_call | ~5,500 (추정) | 3,113 (실측) |
| 10회 누적 토큰 | ~55,000 (추정) | 31,230 (실측) |
| ratio_b_over_a | — | 0.57 (추정 기반, 미달성) |
| 표 보존율 | 0% | 100% (5개 전부) |
| 이미지 추출 | 0개 | 8개 |
| 이미지 캡션 | 0개 | 8개 |

## [2.5.0] — 2026-05-01 (SPEC-HWPX-003)

### Improvements

- **cli.hwpx v1.0.2 BREAKING 동기화**: 이미지 추출 경로 체계가 `images/<stem>_image<N>.png` → `<stem>/image_NNNN.png` (4자리 zero-pad) 로 변경된 것을 반영. SKILL.md / README.md / references 9곳 일괄 갱신.
- **β fallback 헬퍼 도입**: `scripts/find_images.py` 신규 추가 (Track A). 신규 경로 (v1.0.2+) 와 구버전 경로 (v1.0.1 이하) 를 동시 탐색하여 점진적 마이그레이션 지원.
- **동적 이미지 참조 매칭**: SKILL.md 캡션 단계 (D) 의 Edit `old_string` 하드코딩 (`![](images/...)`) 을 정규식 기반 동적 추출로 전환. cli.hwpx 출력 경로를 그대로 본문에서 매칭하여 NFC/NFD 불일치 위험 제거.
- **출력 파일명 정책 명문화**: `-o` 명시 시 hash 접미사 없는 결정적 경로가 보장됨을 SKILL.md 신규 섹션으로 명시.

### New Features

- `scripts/find_images.py` — `find_images(output_dir, stem)` 함수. β 전략 (신규 + legacy) glob 동시 탐색, 4/5자리 zero-pad 흡수, 결과 정렬, 구버전 감지 시 안내 메시지 반환.

### Bug Fixes

- **`hwpx app *` 안내 추가** (SPEC-HWP-029 동기화): cli.hwpx v2.0.0 에서 `hwpx app launch/open/close/status` 가 제거됨을 SKILL.md 에러 처리 표에 명시. macOS/Windows 별 대안 안내.

### Unchanged

- HTML 변환 경로 (이미지 Base64 임베드) — 본 변경의 영향 없음.
- `find_hwpx.py` 바이너리 탐색 모듈 — 본 SPEC 범위 외, 그대로 유지.
- 읽기·변환 전용 정체성 (SPEC-HWPX-IMPROVE-001 의 정렬 결과) — 그대로 유지.
