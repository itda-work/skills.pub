# 서비스별 회원가입·API 키 발급 가이드 (정본 인덱스)

스킬들이 공유하는 외부 서비스의 **회원가입 조건·API 키 발급 절차의 단일 정본(SSoT)**.
발급 절차가 바뀌면 **이 디렉토리의 정본을 먼저 갱신**하고, 각 스킬 GUIDE의 요약 절차를 맞춘다.
정본은 publish 시 skills.pub 루트 `credentials/`로 미러되어 <https://itda.work/credentials/>에
발행된다(서비스별 페이지 = `/credentials/<파일명>/`). 각 GUIDE의 상세 참조는 이 웹 URL을 쓴다.

## 역할 분담 (2층 구조)

| 층 | 위치 | 담는 내용 |
|---|---|---|
| 요약 | 각 스킬 `GUIDE.md` | 핵심 발급 단계 번호 목록(자족 가능 최소한) + ` ```dotenv ` 블록 + 키별 영향 |
| 정본 | `skills/docs/credentials/<service>.md` | 가입 조건 · 상세 절차 · 키↔환경변수 매핑 · 한도/주의 · 사용 스킬 역링크 · Last Verified |

스킬 전용 정보는 정본에 넣지 않는다 — 예: 공공데이터포털의 **데이터셋별 활용신청 링크**는
스킬마다 다르므로 각 GUIDE 잔류(정본은 공통 가입·키 절차만).

## 정본 목록

| 서비스 | 파일 | 키(환경변수) | 사용 스킬 | Last Verified |
|---|---|---|---|---|
| 네이버 오픈API | [naver-openapi.md](naver-openapi.md) | `NAVER_CLIENT_ID` `NAVER_CLIENT_SECRET` | blog-seo · eatery-trend | 2026-06-10* |
| 네이버 검색광고 API | [naver-searchad.md](naver-searchad.md) | `NAVER_SEARCHAD_ACCESS_KEY` `NAVER_SEARCHAD_SECRET_KEY` `NAVER_SEARCHAD_CUSTOMER_ID` | blog-seo · eatery-trend | 2026-06-10* |
| 공공데이터포털 | [data-go-kr.md](data-go-kr.md) | `KO_DATA_API_KEY` | realestate · g2b · funding · realty-jeonse-gap · realty-supply · realty-deals · realty-price-stats · market-scan | 2026-06-10* |
| 네이버 앱 비밀번호 | [naver-app-password.md](naver-app-password.md) | `NAVER_EMAIL` `NAVER_APP_PASSWORD` | email · calendar · work-plan | 2026-06-10* |
| iCloud 앱 전용 비밀번호 | [icloud-app-password.md](icloud-app-password.md) | `ICLOUD_EMAIL` `ICLOUD_APP_PASSWORD` | email · calendar | 2026-06-10* |
| KOSIS 국가통계포털 | [kosis.md](kosis.md) | `KOSIS_API_KEY` | kosis · realty-supply · market-scan | 2026-06-10* |
| 한국은행 ECOS | [ecos.md](ecos.md) | `ECOS_API_KEY` | ecos · market-scan | 2026-06-10* |
| 금융감독원 DART | [dart.md](dart.md) | `DART_API_KEY` | dart · market-scan | 2026-06-10* |

`*` 기존 운영 문서(blog-seo `references/naver-api.md`, 각 스킬 GUIDE)에서 이전·통합한 시점.
실제 발급 화면 재검증 시 날짜를 갱신하고 `*`를 제거한다.

### 3차 후보 (SPEC-CREDENTIALS-GUIDE-001 REQ-006, 보류 가능)

R-ONE(`realty-price-stats` 단일 사용) · 검색 API 군(Tavily·Serper·Perplexity·Exa·Gemini — `web-search` 단일 사용).
단일 사용 서비스는 drift 면적이 좁아 해당 스킬 GUIDE 단독 안내로 충분할 수 있다.

## 운영 규칙

- 절차 변경 발견(사용자 제보·검증 실패) → 정본 수정 + `Last Verified` 갱신 → 사용 스킬 GUIDE 요약 동기화.
- `Last Verified` 6개월 경과 정본은 재검증 후보.
- 정본은 일반 사용자도 읽는 문서다 — 셸 명령·CLI 플래그를 노출하지 않는다(guide-authoring 원칙 준용).
