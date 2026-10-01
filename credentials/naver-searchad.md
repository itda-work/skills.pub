# 네이버 검색광고 API — 가입·키 발급 가이드

- 공식 사이트: <https://searchad.naver.com> · 관리 시스템 <https://manage.searchad.naver.com>
- 발급 키: `NAVER_SEARCHAD_ACCESS_KEY` · `NAVER_SEARCHAD_SECRET_KEY` · `NAVER_SEARCHAD_CUSTOMER_ID`
- Last Verified: 2026-06-10 (blog-seo 운영 문서에서 이전 — 실화면 재검증 시 갱신)

## 1. 가입 조건

- **광고주 계정이 필요합니다** — 일반 네이버 계정만으로는 발급할 수 없습니다.
- 광고주 가입은 **개인도 가능**합니다(사업자 없이 가입 유형에서 개인 선택). 가입·API 사용 모두 무료이며, 실제로 광고를 집행할 필요는 없습니다.

## 2. 발급 절차

1. [ads.naver.com](https://ads.naver.com) 접속 → **신규 가입**에서 광고주 가입 (개인 또는 사업자)
2. [manage.searchad.naver.com](https://manage.searchad.naver.com) 로그인
3. 상단 메뉴 **도구 → API 사용 관리** 클릭
4. **Access License**와 **Secret Key** 발급·복사
5. **고객 ID 확인** — 같은 페이지 주소창의 `/customers/숫자/` 부분 숫자가 고객 ID입니다 (또는 관리 시스템 우측 상단 계정 정보에 표시)

## 3. 키 ↔ 환경변수 매핑

| 발급 화면 명칭 | 환경변수 |
|---|---|
| Access License (액세스 라이선스) | `NAVER_SEARCHAD_ACCESS_KEY` |
| Secret Key (비밀키) | `NAVER_SEARCHAD_SECRET_KEY` |
| 고객 ID (URL의 `/customers/숫자/`) | `NAVER_SEARCHAD_CUSTOMER_ID` |

키는 Claude Code 설정 파일(`~/.claude/settings.json`)의 `env` 에 넣습니다(설정을 바꾼 뒤 Claude Code 를 다시 시작). 스킬이 itda-hyve 경로를 지원하면 itda-hyve 앱의 **시크릿** 탭에 같은 이름으로 등록해도 됩니다 — 어느 경로가 되는지는 각 스킬 GUIDE 에 적혀 있습니다. `.env` 같은 파일은 스킬이 읽지 않습니다(itda-work/skills#45).

```json
{
  "env": {
    "NAVER_SEARCHAD_ACCESS_KEY": "발급받은_액세스라이선스",
    "NAVER_SEARCHAD_SECRET_KEY": "발급받은_시크릿키",
    "NAVER_SEARCHAD_CUSTOMER_ID": "고객ID_숫자"
  }
}
```

## 4. 한도·주의사항

- 이 API는 **월 검색량(레벨) 조회용**입니다 — 키워드도구(연관키워드·월간 검색수)를 제공합니다.
- 인증 오류가 나면 세 값 중 **고객 ID 숫자**가 빠졌거나 틀린 경우가 가장 흔합니다.
- Secret Key는 발급 시점에만 전체가 표시될 수 있으니 복사해 바로 보관하세요. 분실 시 같은 메뉴에서 재발급하면 됩니다(기존 키는 무효화).

## 5. 이 키를 쓰는 스킬

- `itda-doc/blog-seo` — 키워드 확장·월간 검색수·포화지수 계산
- `itda-travel/eatery-trend` — 월 검색량(레벨) 지표. 이 키가 없어도 surge(속도) 분석은 동작하며 레벨 지표만 빠집니다(fail-loud로 사유 표시)
