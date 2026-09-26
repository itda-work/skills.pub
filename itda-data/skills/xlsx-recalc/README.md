# xlsx-recalc — 개발 노트

사용자 안내는 `GUIDE.md`, 에이전트 절차는 `SKILL.md`. 이 파일은 왜 이렇게 만들었는지만 적는다(#1690).

## 구조

| 위치 | 역할 |
|---|---|
| `scripts/recalc.py` | 진입점. 계산 전 검사(외부 링크 값 캐시 · AF_UNIX · LibreOffice ≥ 24.8) → 격리 프로필 `soffice --convert-to xlsx` → 계산 후 검사(타입별 캐시 · 수식 보존 · 외부 링크 파트 보존 · 재직렬화 보고) |
| `scripts/xlsxscan.py` | stdlib OOXML 판독 — 네임스페이스 URI 기준 셀 스캔, 타입별 캐시 판정, 공유 수식 전개, 1904·fullPrecision 설정, 외부 링크 파트(`sheetDataSet`) |
| `scripts/formula_text.py` | 수식 문자열 해석 — 문자열 리터럴 마스킹, 공유 수식 이동, 외부 참조 추출, 재직렬화 위험 분류 |
| `tests/lo_docker/` | 실엔진 로컬 게이트(Dockerfile · `run.sh` · AF_UNIX 차단 seccomp) |

## 왜 LibreOffice 단독인가

초판(커밋 `c5df73bcc`)은 excelize(Go) 1차 + LibreOffice 2차였다. 수식 모양으로 1차 가능 여부를 판정했지만 Codex 적대 리뷰가
Critical 12건을 냈고(IF·ROUND·조회·조건 문자열·날짜·표시 정밀도…), 반례 35건 중 31건을 1차로 내보내 틀린 캐시를 썼다.
대체 엔진 7종을 LibreOffice 25.2 정답과 대조한 결과(`docs/research/xlsx-formula-engine-bench-2026-09-13.md`) 조용한 오답 0 인 엔진이
없었다. 속도도 이점이 아니었다 — 33만 수식 파일에서 LibreOffice(10.5s)가 모든 엔진보다 빨랐다. 그래서 1차 경로를 걷어냈다
(Go 코드·릴리즈 CI 의 arm64 빌드·바이너리 선택 로직 전부). 조사 하네스는 `docs/research/xlsx-recalc-1690/` 에 보존한다.

## 계산 전후 검사를 둔 이유 (실측)

| 검사 | 근거 |
|---|---|
| LibreOffice ≥ 24.8 | Debian 12 기본 7.4.7 이 `_xlfn.XLOOKUP` 을 몰라 실무 파일 한 개에서 59,547셀을 에러 없이 틀렸다(엔진 비교 §LO 버전) |
| AF_UNIX 선감지 | 막힌 샌드박스에서 soffice 는 0.07초 만에 무관한 `javaldx` 경고만 남기고 죽는다(래퍼 A/B §3.3). Cowork 는 허용(2026-09-14 실측) — 셈(LD_PRELOAD)은 넣지 않았다 |
| 외부 링크 값 캐시 | 링크 파트 값 캐시가 없으면 LibreOffice 는 0/0/1 을 성공으로 쓴다. 시트 캐시만 빈 경우는 42/84/43 을 정확히 복원하고 링크를 보존한다(A/B §3.7). 그래서 거부 조건을 "링크 값 캐시 없음"으로 좁혔다 |
| 타입별 캐시 판정 | openpyxl 저장본은 수식 셀마다 빈 `<v></v>` 를 쓴다(20,079셀 전부). 구 스캐너는 이것을 캐시 있음으로 봤다(Codex #17) |
| 수식 보존 대조 | "캐시가 있다"는 수식이 값으로 굳은 산출도 통과시킨다 |
| 재직렬화 보고 | `ROUND(0.49999999999999994,0)` → `ROUND(0.5,0)` 은 다음 재계산에서 0→1 로 바뀐다(A/B §1). 막지는 않는다 — LibreOffice 가 계산한 캐시 자체는 원래 수식의 값이다 |
| 프로세스 정리 | 부모 soffice 가 먼저 끝나도 그룹을 정리한다(Codex #18). 잔존 탐지는 프로필 **URI**(퍼센트 인코딩)도 마커로 쓴다 |
| `/proc` cmdline | Linux procps `ps -eo args` 는 tty 가 없으면 인자를 잘라 프로필 마커를 놓친다 — Docker 실측으로 잔존 프로세스 탐지 0 이었다. `/proc` 가 없으면 `ps -ww` |
| 같은 폴더·다른 이름 스테이징 | 입력·산출 폴더가 다르면 LO 가 외부 링크 상대 경로를 작업 폴더 기준으로 바꾼다(`other.xlsx`→`../in/other.xlsx`). 같은 이름으로 제자리 변환하면 열린 원본을 못 덮어써 **저장 실패인데 exit 0** 이다(`SfxBaseModel::impl_store … Write Code:12`) — 그래서 `io/book.input` → `io/book.xlsx` + `--infilter`, 로그의 `Error:` 도 실패로 본다 |
| 외부 링크 대상 복원 | 같은 폴더여도 LO 는 절대 경로(`/data/x`·`file:///`·`C:\`)를 작업 폴더 기준 상대 경로로, UNC 를 `file://server/…` 로 바꿔 쓴다. 설정(`Save/URL/FileSystem=false`)을 끄면 반대로 상대 경로가 절대화된다. 그래서 같은 위치일 때만 rels `Target` 을 원문으로 되돌리고, 위치가 다르거나 LO 가 같은 파일 링크 둘을 **하나로 합치면** exit 5 |
| 데이터 테이블 거부 | LO 는 `t="dataTable"` 을 `TABLE(C$3,$D$1,$B4)` 수식으로 바꿔 쓴다 — 값은 맞지만 Excel 에 없는 함수라 계산 전 exit 9 |
| 배열 수식 결과 셀 | 부모 셀 밖의 결과 셀은 `<f>` 가 없는 값 셀이라 수식 캐시 검사가 못 본다 — 범위를 따로 모아 대조한다 |

`fullPrecision="0"`·`date1904` 는 7개 엔진이 모두 틀렸지만 LibreOffice 는 맞게 계산한다 → 막지 않고 실엔진 테스트로 확인만 한다.

## 테스트

```bash
cd skills/itda-data && just test-skill xlsx-recalc     # 단위 + 가짜 soffice(CI 도 이것)
skills/itda-data/skills/xlsx-recalc/tests/lo_docker/run.sh   # 실엔진 로컬 게이트(herdr pane 에서)
```

- `test_scan.py`: 캐시 판정·네임스페이스·공유 수식·외부 링크 판정·재직렬화 분류.
- `test_recalc.py`: 가짜 soffice 로 버전 게이트·AF_UNIX·외부 링크 거부·산출 검증·timeout 정리(공백·한글 TMPDIR)·예외→종료 코드.
- `test_recalc_lo_live.py`: 실 LibreOffice. `run.sh` 가 세 모드로 돈다 — trixie(25.2) 전체, bookworm(7.4) 버전 게이트,
  AF_UNIX 차단 seccomp. **CI 는 LibreOffice 가 없어 건너뛴다**(skip 사유 표시). 이 축의 게이트는 로컬 `run.sh` 다.
- 뮤테이션 자기검증(2026-09-14): 45종 전부 RED — 버전 게이트(미달·판독 불가·다른 제품 문자열·비정상 종료) · AF_UNIX ·
  외부 링크(거부·캐시 조회·값 유효성·범위 연속·동적 함수·이름 체인·대상 복원·식별 대조) · 빈 숫자 캐시 · 공유 문자열 범위 ·
  수식 보존 · 배열 범위·결과 셀 · Strict·데이터 테이블 · 부모 선종료 그룹 정리 · 버전 조회 그룹 정리 · URI·경계 마커 ·
  `ps -ww` · 저장 실패 로그 · 공유 수식 전개·시트 이름 보호 · 재직렬화 위험(숫자·미분류) · 산출 zip 예외 · 분리 폴더 스테이징(실엔진).
  첫 판 BLIND 2건(M14·M21)은 무해한 변조였고, 변조를 원래 결함 모양으로 바꾸거나 사용자 안내 문구를 단언해 RED 로 만들었다.
  세 번째 BLIND(따옴표 없는 시트 접두 가림)는 셀 정규식의 `!` 경계가 이미 막는 중복 코드라 지웠다.
- 외부 링크 대상 비교는 LibreOffice 규칙을 따른다 — 모든 대상을 URI 참조로 한 번 퍼센트 디코딩(평문 `/data/a b` ≡ `/data/a%20b`, `file:///…%2520…` 은 `%2520` 유지, 실측).
