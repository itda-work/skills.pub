# Changelog — taxlaw

## [0.1.3] - 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- `[책임 경계]`·“쓰지 않을 때” 표에서 세무 포털 자동화 행을 `itda-org-taxhero:web-automation` 대신 “현재 지원 스킬 없음” 으로 — 그 스킬은 hyve 앱 폐기로 실행 경로가 없다.

## [0.1.1] - 2026-09-01 (이슈 #1617)

### Changed

- **플러그인 이관 `itda-gov` → `itda-tax`** (마스터 결정). 스킬 내용·CLI·`SKILL_DIR` 규약은
  불변(플러그인 상대 경로 `skills/taxlaw`). stdout JSON compact 규율은 itda-gov 횡단 가드 밖으로
  나가므로 스킬 자체 가드(`tests/test_response_compact_guard.py`)로 유지.

## [0.1.0] - 2026-09-01 (이슈 #1616)

### Added

- 최초 릴리즈 — 국세법령정보시스템(taxlaw.nts.go.kr) 통합검색·전문 조회.
  - 통합검색(`ASEISA001MR01`): 법령·세법해석례·판례/결정례·상담사례·별표서식·전자도서관,
    문서번호 검색(`--docno`)·페이지네이션·정렬(정확도/등록일/생산일)·포함어/제외어·동의어.
  - 전문 조회: 세법해석례·판례(`ASIQTB002PR01` — 판결문·회신 전문 + 관련 법령),
    법령 조문(`ASISTA002MR03` — 조·항 단위), 상담사례(`ASEISA004MR01`).
  - 계약 근거는 2026-09-01 라이브 실측(`references/taxlaw-api.md` 박제). 쿠키·세션·키 불요,
    Python 표준 라이브러리만 사용.
- (릴리즈 전 적대 리뷰 R1 반영 — gpt-5.6-sol) stdout JSON compact 전환(#438 가드 정합) ·
  리터럴 `<개정 …>`·`<YYYY.MM.DD>` 표기 보존(태그 제거를 ASCII 시작 태그로 한정) ·
  요청 도메인 미수신 시 missing 명시 · `--article` 비대상 도메인 usage 에러 ·
  itda-gov justfile 테스트 러너 등재 · 픽스처 debugMsg 전 위치 소거(내부 인프라 정보) ·
  응답 close/타임아웃 typed 처리.
- (R2 반영 + 브라우저 10검색어 대조) 법령 제목을 사이트 표기 `법령명【조표시 조제목】` 로 정합 ·
  법령 링크를 사이트 라우팅(법령/통칙/집행/조약/훈령 5갈래)대로 생성 · 법령 전문 조회의 원문
  URL 을 렌더 필수 파라미터(`ntstTlawClCd`) + 버전 고정(`ntstBrkdId`)으로 생성하고 법령명을
  MR01 역해석으로 채움(전에는 빈 화면 URL·빈 법령명) · 텍스트 출력에 원문 URL 누락 수정 ·
  조/항·호/집행/훈령/통칙 실측 픽스처 추가.
- (R2 최종 반영) 공개 픽스처 위생 — 라이브 세션 키(wnKey UUID)·운영자 계정/조직 식별자를
  사이트 자체 익명화 형식으로 소거하고 `test_fixture_hygiene.py` 가드(UUID·debugMsg·내부
  IP·운영자 식별자 0, 뮤테이션 자기검증 포함) 신설 · `<!DOCTYPE>`/조건부 주석 선언 제거 ·
  조제목이 조표시로 시작할 때 제목 중복 방지 · references actionId 표 현행화.
- (R3 CONDITIONAL_LGTM 잔여 P2) 통칙 요약처럼 `&lt;p&gt;` 로 이중 인코딩된 마크업이 화면에
  리터럴 `<p>` 로 남던 것을 unescape 후 ASCII 태그 재제거로 정리(`<개정 …>` 보존 양립).
