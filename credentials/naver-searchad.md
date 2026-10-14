# 네이버 검색광고 API — 가입·키 발급 가이드

- 공식 사이트: <https://searchad.naver.com> · 관리 시스템 <https://manage.searchad.naver.com>
- 발급 키: `NAVER_SEARCHAD_ACCESS_KEY` · `NAVER_SEARCHAD_SECRET_KEY` · `NAVER_SEARCHAD_CUSTOMER_ID`
- Last Verified: 2026-06-10 (옛 blog-seo 운영 문서에서 이전 — 그 스킬은 2026-10-14 제거, 실화면 재검증 시 갱신)

## 1. 가입 조건

- **광고주 계정이 필요합니다** — 일반 네이버 계정만으로는 발급할 수 없습니다.
- 광고주 가입은 **개인도 가능**합니다(사업자 없이 가입 유형에서 개인 선택). 가입·API 사용 모두 무료이며, 실제로 광고를 집행할 필요는 없습니다.

## 2. 발급 절차

1. [ads.naver.com](https://ads.naver.com) 접속 → **신규 가입**에서 광고주 가입 (개인 또는 사업자)
2. [manage.searchad.naver.com](https://manage.searchad.naver.com) 로그인
3. 상단 메뉴 **도구 → API 사용 관리** 클릭
4. **Access License**와 **Secret Key** 발급·복사
5. **고객 ID 확인** — 같은 페이지 주소창의 `/customers/숫자/` 부분 숫자가 고객 ID입니다 (또는 관리 시스템 우측 상단 계정 정보에 표시)

## 3. 키 ↔ 시크릿 이름 매핑

| 발급 화면 명칭 | itda-hyve 시크릿 이름 |
|---|---|
| Access License (액세스 라이선스) | `NAVER_SEARCHAD_ACCESS_KEY` |
| Secret Key (비밀키) | `NAVER_SEARCHAD_SECRET_KEY` |
| 고객 ID (URL의 `/customers/숫자/`) | `NAVER_SEARCHAD_CUSTOMER_ID` |

키는 itda-hyve 앱의 **시크릿** 탭에 위 이름 그대로 등록합니다. 값은 itda-hyve 에만 저장되고 스크립트·대화에는 나오지 않습니다. 스킬은 키를 환경변수(셸·Claude Code 설정 파일의 `env`)나 `.env` 같은 파일로 읽지 않습니다(itda-work/skills#45·#46) — 그런 곳에 넣어 둔 키는 지워도 됩니다. 아직 itda-hyve 로 옮기지 않은 스킬은 이 키를 쓸 수 없습니다 — 각 스킬 GUIDE 에 적혀 있습니다.

## 4. 한도·주의사항

- 이 API는 **월 검색량(레벨) 조회용**입니다 — 키워드도구(연관키워드·월간 검색수)를 제공합니다.
- 인증 오류가 나면 세 값 중 **고객 ID 숫자**가 빠졌거나 틀린 경우가 가장 흔합니다.
- Secret Key는 발급 시점에만 전체가 표시될 수 있으니 복사해 바로 보관하세요. 분실 시 같은 메뉴에서 재발급하면 됩니다(기존 키는 무효화).

## 5. 이 키를 쓰는 스킬

**지금은 이 키를 쓰는 스킬이 없습니다** — 등록해도 쓰이지 않습니다. 검색광고 API 는 요청마다 서명이 필요해 itda-hyve 서명 기능(itda-work/itda-hyve#34)을 기다립니다(2026-10-03). 그 기능이 들어오면 아래 두 곳이 이 키를 씁니다 — 발급해 두었다면 그때 시크릿 탭에 등록하면 됩니다.

- `itda-travel/eatery-trend` — 월 검색량(레벨)과 협찬 거품 판정. 지금은 이 둘 없이 surge(속도)만 냅니다(결과에 사유 표시)
- `itda-doc` 블루키워드 분석 스킬 — 지금 배포 보류(키워드 확장이 이 API 뿐이라 서명 기능 전에는 동작하지 않습니다)
