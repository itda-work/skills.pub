# 네이버 오픈API — 가입·키 발급 가이드

- 공식 사이트: <https://developers.naver.com> (네이버 개발자센터)
- 발급 키: `NAVER_CLIENT_ID` · `NAVER_CLIENT_SECRET`
- Last Verified: 2026-06-10 (blog-seo 운영 문서에서 이전 — 실화면 재검증 시 갱신)

> **⚠️ NAVER API HUB 이관 안내 (약관 시행 2026-07-31)**
>
> 네이버 개발자센터의 검색·데이터랩 API가 네이버클라우드(NCP)의 **NAVER API HUB**로 이관됩니다.
>
> - **신규 발급**: 2026-07-30 24:00 이후 개발자센터를 통한 신규 이용 신청이 **중단**됩니다. 이후 새로 키를 받으려면 NAVER API HUB에서 별도 절차로 신청해야 합니다(절차 공개 시 본 문서를 갱신할 예정입니다).
> - **기존 키**: 이미 발급받은 키는 **2027-06-30 24:00까지** 현행대로 동작합니다. 2027-07-01부터는 NAVER API HUB의 별도 이용 절차·약관을 따라야 합니다.
> - 아래 발급 절차는 **2026-07-30까지 유효한 개발자센터 기준**입니다.
> - 네이버 검색광고 API(`searchad.naver.com`)는 별개 서비스로 본 이관과 무관합니다.

## 1. 가입 조건

- **일반 네이버 계정**으로 발급 가능합니다 (광고주 가입·사업자 등록 불필요).
- 비용 없음, 심사 없음 — 애플리케이션 등록 즉시 키가 발급됩니다.

## 2. 발급 절차

1. [developers.naver.com](https://developers.naver.com) 접속 후 네이버 계정으로 로그인
2. 상단 메뉴 **Application → 애플리케이션 등록** 클릭
3. 애플리케이션 이름 입력 (자유 — 예: "itda-skills")
4. **사용 API** 선택 — 쓰려는 스킬에 맞게 체크:

   | 항목 | 용도 | 필요 스킬 |
   |------|------|----------|
   | **검색** | 블로그·지역(local) 검색 | blog-seo · eatery-trend |
   | **데이터랩(검색어트렌드)** | 검색량 추이·surge 분석 | blog-seo · eatery-trend |

   > "데이터랩(쇼핑인사이트)"는 쇼핑 카테고리 전용으로 위 스킬에서는 사용하지 않습니다.
5. **환경 설정**: **WEB 설정** 선택 → Callback URL에 `https://example.com` 입력 (실제 콜백을 쓰지 않으므로 형식만 맞추면 됩니다)
6. 등록 완료 화면에서 **Client ID**와 **Client Secret** 복사

## 3. 키 ↔ 환경변수 매핑

| 발급 화면 명칭 | 환경변수 |
|---|---|
| Client ID | `NAVER_CLIENT_ID` |
| Client Secret | `NAVER_CLIENT_SECRET` |

키는 Claude Code 설정 파일(`~/.claude/settings.json`)의 `env` 에 넣습니다(설정을 바꾼 뒤 Claude Code 를 다시 시작). 스킬이 itda-hyve 경로를 지원하면 itda-hyve 앱의 **시크릿** 탭에 같은 이름으로 등록해도 됩니다 — 어느 경로가 되는지는 각 스킬 GUIDE 에 적혀 있습니다. `.env` 같은 파일은 스킬이 읽지 않습니다(itda-work/skills#45).

```json
{
  "env": {
    "NAVER_CLIENT_ID": "발급받은_클라이언트ID",
    "NAVER_CLIENT_SECRET": "발급받은_클라이언트시크릿"
  }
}
```

## 4. 한도·주의사항

- **데이터랩 API는 하루 1,000회 한도**가 있습니다. 트렌드 조회는 키워드 1개당 1회를 소모하므로, 넓게 탐색한 뒤 추린 키워드에만 트렌드를 조회하는 패턴을 권장합니다.
- 검색 API(블로그·지역)는 하루 25,000회로 여유가 큽니다.
- 사용 API 체크를 빠뜨리고 등록했다면, **Application → 내 애플리케이션 → API 설정**에서 나중에 추가할 수 있습니다.
- 키가 맞는데 인증 오류(401)가 나면 해당 API 항목이 체크돼 있는지 먼저 확인하세요.

## 5. 이 키를 쓰는 스킬

- `itda-doc/blog-seo` — 블로그 문서수·검색 트렌드
- `itda-travel/eatery-trend` — 데이터랩 surge·지역검색 가게 매핑·블로그검색 거품 필터
- `itda-web/web-search` — 네이버 web·뉴스·블로그 검색(사용 API: 검색)

> `itda-web/web-search` 는 키를 **itda-hyve 앱의 시크릿 탭**에서만 읽습니다 — 같은 이름(`NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`)으로 등록하면 되고, 위 3절의 설정 파일 `env` 는 이 스킬이 읽지 않습니다(itda-work/skills#45).
