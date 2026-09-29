# Changelog — itda-hwpx

## [1.4.2] — 2026-09-28 (#29)

### Fixed

- **손상 입력이 트레이스백으로 죽던 것** — 잘리거나 비트가 깨진 문서가 exit 2 「손상된 HWP 5/HWPX 문서입니다」로 끝난다
  (`CorruptDocumentError`, `code="corrupt"`). 실 공고 첨부 79건 × 변형(fuzz) 실측으로 찾았다: HWP 5 는 짧은 FileHeader·본문 섹션
  없음(ValueError 52건)과 풀리지 않는 DocInfo 스트림(zlib.error 1건), HWPX 는 ZIP 안 XML 이 깨지면 전부(ET.ParseError 90건).
- 읽기 오류에 **종류 코드**를 붙였다 — `UnsupportedFormatError.code`: `unsupported`·`encrypted`·`distribution_protected`·
  `unsafe_archive`·`corrupt`·`missing_dependency`. 메시지 문구가 아니라 코드로 가른다.
- **olefile 이 없으면 트레이스백·exit 1 로 죽던 것** — HWP 5·배포용 판정 모두 olefile 경로라 Cowork(선탑재 없음)에서 설치 정문을
  건너뛰면 호출 스킬이 틀린 사유를 적었다. 이제 exit 2 「olefile 패키지가 필요합니다 — `install_skill_deps.py` 로 설치」(`code="missing_dependency"`, #32 사전 실측).
- 잘린 OLE 의 안내에서 "Word .doc 일 수 있음" 만 말하던 것을 "한글 문서가 아니거나 손상된 OLE" 로 넓혔다.

### Added (개발 도구 — 배포 제외 `reader/evals/`)

- **fuzz 게이트** `fuzz_sweep.py` — 변형 7종(50·90% 절단, 헤더·전체 8비트 뒤집기, HWPX 는 ZIP 안 XML 뒤집기·절단·숫자 속성 오염,
  HWP 5 는 풀어 낸 레코드 뒤집기), 시드 = 경로 해시. crash·hang·코드 없는 실패·slow 가 0 이어야 한다(한도 = max(30초, 원본×3), 상한 180초).
  저장소 픽스처 10건 60케이스 결정론 테스트 + 코퍼스 전수 옵트인. 실 코퍼스: 리더 485케이스 위반 0.
- **벤치 게이트 모드** `bench_revisions.py --gate` — 커밋된 하한 파일 `gate_floors.json`(지표별 min/max) · 형식별 모수 하한 ·
  2회 연속 개선 래칫(`--ratchet`) · 사유 필수 재기준(`--rebase --reason`) · 부분 실행(`--doc`, 모수 면제) · 코퍼스 부재 SKIP
  (`--if-corpus`, exit 3). 초기 하한은 실 코퍼스 79건(HWP5 34·HWPX 45) 실측 — 구 리더(e4c9be57)는 14개 지표 FAIL.
- 테스트 17건(게이트 10 · fuzz 7) · 뮤테이션 13종 전건 RED(하한 비교·모수 하한·kordoc 미측정·래칫 연속·재기준 사유·
  하네스 예외 삼킴·코드 없는 실패·손상 포장 제거·손상 삼킴 등, biz-redact 포함).

## [1.4.1] — 2026-09-28 (#27)

### Security

- **사용자 ZIP/HWP 입력 가드** — 읽기(HWPX·HWP 5·형식 판별)·채우기·구조 검증기·참고 서식(`derive_profile`)이 받은 파일을 상한 없이 풀던
  것을 막는다. 가드는 `reader/hwpx_native/safe_archive.py`(표준 라이브러리, 채우기·검증기·프로파일은 파일 경로로 읽는다).
  - 엔트리 수를 EOCD(ZIP64 포함)에서 **목록을 만들기 전에** 센다(기본 500) · Central Directory 의 단일·합계 비압축 크기(기본 256MB) ·
    저장/deflate 외 압축 방식 거부 · 저장 엔트리의 크기 불일치와 deflate 로 불가능한 비율(>1100:1)을 위조로 거부 · 경로 탐색 이름 거부.
  - 읽는 중에는 실제로 푼 바이트를 문서 예산에 올린다. 선언 크기를 줄인 위조는 잘림 + CRC 불일치로 드러나 명시 오류가 된다.
  - HWP 5 스트림은 `decompressobj(max_length)` 로 예산에서 멈춘다(64MB zlib 폭탄 → 추적 메모리 8MB 미만). BodyText·BinData 해제 실패를
    건너뛰던 `except Exception` 이 폭탄까지 삼키지 않게 했다.
  - XML 엔트리(`.xml`·`.hpf`·`.rdf`)의 DOCTYPE 을 루트 요소 전 expat 판독으로 거부한다(UTF-16 선언 포함, 파이썬·expat 버전의 완화에 기대지 않는다).
  - 형식 판별은 mimetype 앞 256바이트만 푼다(40MB mimetype → 추적 메모리 8MB 미만).
  - 오류는 읽기 `UnsupportedFormatError` exit 2 · 채우기 exit 1(쓰다 만 결과 삭제) · 검증기 `archive safety` 단독 실패 · 참고 서식 `ProfileError`.
  - 상한 조절: `ITDA_MAX_UNZIP_MB`(1~8192) · `ITDA_MAX_ZIP_ENTRIES`(1~65535). 근거: 실 파일 164건(HWPX 99 · HWP 5 65) 최대 합계 78MB·
    엔트리 33·비율 92:1(77MB BMP) · HWP 5 스트림 합계 22.6MB · DOCTYPE 0 — 가드 전 경로 거짓 양성 0. 수십~수백 배 비율 상한은
    이 BMP 를 막아 두지 않았다.
  - 테스트 47건(폭탄 픽스처는 테스트 안에서 생성) · 뮤테이션 25종 전건 RED.

## [1.4.0] — 2026-09-27 (#8~#14)

kordoc 대조 추적 이슈 #1 의 남은 항목.

### Fixed

- **원문 별표 이스케이프 (#8)** — 각주 `*`·가림 `****` 가 마크다운 강조와 섞여 강조가 잘못 짝지어지거나 줄머리 `* ` 가 목록이 됐다.
  마크다운 텍스트의 `*` 를 `\*` 로 쓴다(HTML 셀은 그대로). 벤치: 남은 공백·빈 강조 HWP5 5·1 → 0, HWPX 2 → 0.
- **`--residue` 자리·횟수 대조 (#9)** — 값 커버리지가 "결과 어딘가에 값이 있는가" 만 봐서 두 값이 서로 자리를 바꾸거나
  같은 값이 두 자리 중 한 곳에만 들어가도 통과했다(`{{A}} {{B}}` → `둘 하나` 재현). 채우기와 같은 규칙(매핑 순서·겹침 건너뛰기·
  목록 순차 소비)으로 문단별 기대 값을 계산해 결과의 같은 문단에서 순서대로 대조한다. 새 잔재 종류 `value_misplaced`·`structure`
  (문단 수 불일치 — 채우기는 문단 수를 바꾸지 않는다). 줄바꿈 값은 줄 단위로 이어 찾는다.
- **구조 검증기 확장 (#10)** — `report/hwpx_report/validator.py` 에 `section count (secCnt)`(header.xml secCnt = 섹션 파일 수)·
  `manifest hrefs`(content.hpf 의 모든 item 이 ZIP 에 실재)를 추가해 9검사. secCnt=99·없는 파트 참조가 7검사를 전부 통과하던 것
  (리뷰 재현)을 잡는다. 실 한컴 저장본 50개 전부 통과(거짓 양성 0). **채우기도 결과에 같은 검사**를 돌려, 원본에서 통과하던 검사가
  결과에서 실패하면 exit 1(채우기가 구조를 깨뜨림), 원본부터 어긋난 항목은 경고만 한다(한컴이 여는 사용자 양식을 거부하지 않는다).
- **내용 손실 경고의 strict 승격 (#11)** — `md_to_docspec.py --strict` 는 원고 내용을 버리는 경고(헤더보다 긴 행의 칸 절단·
  구분선/헤더 없는 표 건너뜀·짝 없는 표 제목 줄 버림)가 있으면 DocSpec 을 쓰지 않고 exit 2. 기본 동작(경고 후 산출)은 그대로.
  절단 경고는 버린 칸 글자를 보여 준다("버린 칸: '비고: 국비'").

### Added

- **레이아웃 틀 풀기 `--unwrap-layout-tables` (#13, 옵트인)** — 본문 전체를 감싼 1×1 표·한 열 표를 풀어 셀 내용을 본문 블록으로 올린다.
  보수적 판정: 모든 셀이 무거울 때(안쪽 표·비지 않은 문단 3개+·300자+)만, 열 2개 이상·병합·가벼운 칸이 있는 1열 표는 유지, 래퍼 안의 래퍼는
  재귀로. 공고 첨부 71건 + 픽스처 8건에서 41개 문서의 표 116개가 풀렸고 글자 손실 0(문자 다중집합 동일). 기본 출력 불변.
- **공문서 표기법 검사 `report/scripts/lint_notation.py` (#14)** — 원고 마크다운의 날짜(`2026년 9월 6일`·`2026.9.6`·`2026. 09. 06.`)·
  시각(`오후 3시`·`15시 20분`)·한글 병기 없는 `금…원`·쌍점 앞 띄움·띄어 쓴 물결표·`붙임:` 을 **경고만** 한다(자동 교정 없음, exit 1).
  근거는 「행정업무의 운영 및 혁신에 관한 규정」 제7조제5항·시행규칙 제2조제2항을 법제처 현행 조문으로 재판독(2026-09-28).
  front-matter·코드 블록·URL·`15:20`·`1:1`·마크다운 취소선 `~~` 는 보지 않는다. 생성 절차 0단계에 넣었다.
  저장소 예시 원고에 경고 25건이 남아 있다 — GUIDE 렌더 그림의 입력이라 그림 재생성과 함께 따로 정리한다.
- **내용 서명 형식 판정 + 미지원 형식 안내 (#16)** — 리더가 확장자가 아니라 파일 머리(OLE·ZIP mimetype·`HWP Document File`·`<HWPML`)로
  형식을 가른다. 확장자가 틀린 파일(.hwpx 인데 HWP 5, 그 반대)도 읽고, HWP 3.x·HWPML·Word/Excel 은 무엇인지 말하는 오류(exit 2, 트레이스백 없음).
  SKILL 에 HWP 3.x·HWPML 대체 경로(한글에서 HWPX 저장 → 사용자 동의 후 `npx -y kordoc@4.15.7`) 절을 두었다 — kordoc 4.15.7 로 HWP 3.x(한글 97)·
  HWPML 읽기를 실측했고, Cowork 에서는 kordoc OCR·PNG 가 `sharp` 부재로 동작하지 않음을 적었다.
  없는 입력 파일도 트레이스백 대신 "입력 파일이 없습니다"(exit 2).
  **암호·배포용 보호 HWP 5** 도 `ValueError` 트레이스백(exit 1) 대신 무엇인지와 조치를 말하는 exit 2 로 통일(brain-build #22 검수에서 발견).
  Cowork 2회차 실측으로 kordoc OCR·PNG 불가의 원인(linux/x64 onnxruntime-node 의 NuGet 다운로드 차단)과 우회(`ONNXRUNTIME_NODE_INSTALL=skip`)를 확정해 안내를 고쳤다.

### Changed

- **예시 원고 표기 정리 + GUIDE 그림 재생성 (#15)** — `report/examples/` 의 표기 경고 25건(본문 「9월 15일까지」류 날짜, 띄어 쓴 물결표)을
  `9. 15.까지`·`14:00∼17:00` 으로 고치고, 그림 입력인 v13-samples 를 rhwp 로 다시 구웠다(그림 5장, drift 게이트 정합).
  예시 테스트를 "경고 0" 단언으로 승격했다.

## [1.3.3] — 2026-09-27 (#6, #7)

변경 전후 벤치(`reader/evals/bench_revisions.py`, 기업마당 공고 첨부 71건 + 픽스처 8건)가 찾은 남은 결함 2건.

### Fixed

- **HWP5 글상자 텍스트 누락** — 그리기 개체(`gso `)에서 그림만 꺼내고 캡션·글상자 문단을 버렸다. SHAPE_COMPONENT 뒤
  LIST_HEADER 의 문단을 읽고 묶음 개체는 재귀로, 표 셀 안 개체도 셀 문단으로 읽는다. 실 공고(개체 64개)의 임원 명단·동의 항목 줄이 복원됐다
  (kordoc 대비 HWP5 텍스트 재현율 평균 0.961→0.975, 0.95 미만 파일 4→2).
- **밑줄이 섞인 강조 잔재** — 밑줄은 마크다운·HTML 셀에서 표시를 만들지 않으므로 병합 전에 포장을 풀고, 필드·하이퍼링크 자리의 빈 글자
  조각도 건너뛴다. `**출****자**`·`(****https://…` 가 사라졌다(HWPX 빈 강조 11→0).

### Added

- `reader/evals/bench_revisions.py` — 두 리비전(또는 작업 트리)의 리더를 같은 문서 묶음에 돌려 표 격자 정합률·이상 span·강조 잔재·
  이스케이프 누락·kordoc 대비 재현율·시간을 비교한다(개발 전용, 배포 제외). 강조 지표는 `**` 를 여닫이로 짝지어 세고 원문 별표 가림을 뺀다.
  최초(e4c9be57) 대비 HWP5 표 격자 정합률 65.3%→100%, 재현율 0.890→0.975, 셀 안 `**` 3,639→3.

## [1.3.2] — 2026-09-27 (#2, #3)

kordoc 대조(#1)와 gpt-6-astra 적대 리뷰로 찾은 읽기 결함을 고쳤다. 기존 골든이 결함 출력을 박제하고 있어
바이트 비교 테스트가 GREEN 이었다 — 골든을 재생성하고 원바이트 좌표·구조를 직접 단언하는 회귀를 추가했다.

### Fixed

- **HWP5 표가 무너지던 결함** — 셀 LIST_HEADER 의 주소를 offset 6 에서 읽어 col·row·병합이 한 칸씩 밀렸다(표가 한 행으로 뭉침).
  offset 8 로 바로잡고 최소 길이 검사를 24바이트로, 행 안 셀은 열 주소 순으로 둔다.
- **HWP5 셀 안 중첩 표 소실** — 셀 문단이 품은 표를 버리던 것을 재귀로 읽어 셀 안 표로 보존한다(실 서식에서 문단 150→228, 표 4→12 복원).
- **HWP5 표 캡션을 셀로 읽던 것** — TABLE 레코드 앞의 LIST_HEADER 는 캡션으로 표 앞 문단에 둔다.
- **마크다운 HTML 표 셀** — 텍스트를 이스케이프하고(`&lt;개정 …&gt;`), 강조를 `<strong>`·`<em>`·`<del>` 로 쓴다(HTML 블록 안 `**` 는 렌더되지 않았다).
  빈 강조는 만들지 않고, 앞뒤 줄바꿈은 태그 밖으로, 글자모양 경계로 쪼개진 같은 강조는 잇는다.
- **중첩 표가 GFM 셀에 HTML 문자열로 새던 것** — 셀 안에 표가 있으면 HTML 표로 쓰고 안쪽 표는 한 줄 HTML 로 넣는다.
- **마크다운 강조 잔재** — 표 밖에서도 같은 규칙을 쓴다: 이어진 같은 강조는 하나로 합치고(`**무료****대여**` → `**무료대여**`),
  안쪽 끝 공백·줄바꿈은 표시 밖으로 빼며(`** □ 평가대상**` 은 강조로 렌더되지 않았다), 빈 강조는 만들지 않는다.
  실 공고 `.hwp`(기업마당 첨부) 변환에서 확인했다. 원문에 있는 별표 글자(`****` 가림 표시)는 그대로 둔다.

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
