---
title: "blog-seo 활용 가이드"
---

네이버 검색광고 API로 블로그 글감이 될 블루키워드를 발굴하는 스킬입니다. **아래처럼 `/blog-seo` 뒤에 키워드를 붙여 입력하면 됩니다** — 자연어로 말해도 동작합니다. 포화지수·KEI·등급(S~D)이 담긴 리포트를 돌려줍니다.

---

## 처음 설정하기

키워드 분석에는 네이버 API 키 두 종류(5개 값)가 필요합니다. 각각 한 번만 발급하면 이후에는 자동으로 사용됩니다.

발급받은 키는 아래처럼 등록합니다. **`.env` 같은 파일에 적어 두는 방식은 더 이상 쓰지 않습니다** — 스킬이 그 파일을 읽지 않습니다.

- **Claude Code** — Claude Code 설정 파일(`~/.claude/settings.json`)의 `env` 에 넣으면 Claude Code 가 스킬에 전달합니다. 설정을 바꾼 뒤에는 Claude Code 를 다시 시작하세요. 셸 환경변수로 넣어도 됩니다.

```json
{
  "env": {
    "NAVER_SEARCHAD_ACCESS_KEY": "검색광고_API키",
    "NAVER_SEARCHAD_SECRET_KEY": "검색광고_시크릿키",
    "NAVER_SEARCHAD_CUSTOMER_ID": "광고주_고객ID",
    "NAVER_CLIENT_ID": "네이버앱_클라이언트ID",
    "NAVER_CLIENT_SECRET": "네이버앱_클라이언트시크릿"
  }
}
```

- **Cowork** — 이 스킬은 아직 Cowork 에서 키를 넣을 방법이 없습니다. 키가 필요한 조회는 Claude Code 에서 하세요.

키 값을 대화창에 붙여 넣지 마세요. Claude Desktop 의 "Claude 지침"에 적는 방식도 동작하지만 대화 컨텍스트에 값이 노출되므로 권장하지 않습니다.

서비스 이름을 누르면 발급 페이지가 열립니다. 상세 절차는 아래 1·2번을 참고하세요.

:::cards

- [네이버 검색광고](https://manage.searchad.naver.com) — 광고주 계정 필요 (아래 1번 절차) → `NAVER_SEARCHAD_ACCESS_KEY` · `NAVER_SEARCHAD_SECRET_KEY` · `NAVER_SEARCHAD_CUSTOMER_ID`
- [네이버 오픈 API](https://developers.naver.com) — 일반 네이버 계정으로 발급 (아래 2번 절차) → `NAVER_CLIENT_ID` · `NAVER_CLIENT_SECRET`

:::

### 1. 네이버 검색광고 API (3개 키)

> 광고주 계정이 있어야 발급됩니다.

1. [ads.naver.com](https://ads.naver.com) 접속 후 광고주 가입
2. [manage.searchad.naver.com](https://manage.searchad.naver.com) 로그인
3. 상단 **도구 → API 사용 관리**에서 Access License(`NAVER_SEARCHAD_ACCESS_KEY`)와 Secret Key(`NAVER_SEARCHAD_SECRET_KEY`) 복사
4. 같은 페이지 URL의 숫자(`/customers/숫자/`)가 `NAVER_SEARCHAD_CUSTOMER_ID`

### 2. 네이버 오픈 API (2개 키)

> 일반 네이버 계정으로 발급 가능합니다.

1. [developers.naver.com](https://developers.naver.com) 로그인
2. **Application → 애플리케이션 등록** 클릭
3. 사용 API에서 **검색** + **데이터랩(검색어트렌드)** 체크 ("데이터랩(쇼핑인사이트)"는 불필요)
4. **WEB 설정 → Callback URL**에 `https://example.com` 입력 후 등록
5. 등록 후 Client ID와 Client Secret 복사

> **⚠️ 신규 발급 안내 (2026-07-31부터)**: 네이버가 이 API들을 네이버클라우드의 **NAVER API HUB**로 옮기고 있어요. 2026-07-30까지는 위 절차대로 발급되지만, 그 이후에 새로 발급하려면 NAVER API HUB에서 신청해야 합니다. 이미 발급받은 키는 2027-06-30까지 그대로 쓸 수 있습니다.

> 더 자세한 절차·주의사항(한도, 흔한 인증 오류 등)은 [네이버 오픈API](https://itda.work/credentials/naver-openapi/) · [네이버 검색광고](https://itda.work/credentials/naver-searchad/) 발급 가이드를 참고하세요.

---

## 빠른 시작

```
/blog-seo 파이썬 독학 블루키워드 찾아줘
```

```
/blog-seo 경쟁 적은 키워드 분석해줘
```

```
/blog-seo 블로그 키워드 포화지수 확인해줘
```

---

## 활용 시나리오

### 블로그 주제 추천

시드 키워드 몇 개로 관련 키워드를 확장해 글감을 추려냅니다.

```
/blog-seo "파이썬 독학"으로 쓸 만한 블로그 주제 추천해줘
```

### 블루키워드만 골라서 보기

경쟁이 적고 검색량이 보장된 키워드만 보고 싶을 때는 "A등급 이상만"처럼 등급을 말해주세요.

```
/blog-seo 파이썬 관련 블루키워드(A등급 이상)만 골라줘
```

등급 기준은 아래와 같습니다.

| 등급 | 포화지수 | 레이블 |
|------|---------|--------|
| S | 10% 미만 | 블루키워드 |
| A | 10~20% | 유망 키워드 |
| B | 20~40% | 기회 있음 |
| C | 40~60% | 경쟁 치열 |
| D | 60% 초과 | 레드키워드 |

### 트렌드 분석 포함

최근 트렌드(계절성·상승세)를 함께 보고 싶을 때 "트렌드도 같이"라고 말하세요.

```
/blog-seo 파이썬 독학 키워드의 최근 트렌드까지 확인해줘
```

> ⚠️ 트렌드 조회는 키워드 1개당 데이터랩 API 1회를 소모합니다. 하루 1,000회 한도가 있으므로 필터링된 키워드에만 사용하세요.

### 결과를 CSV로 받기

엑셀이나 구글 시트에 붙여넣고 싶을 때는 "CSV 파일로 저장해줘"라고 말하세요.

```
/blog-seo 파이썬 키워드 분석 결과 CSV 파일로 저장해줘
```

---

## 팁

- **두 단계 실행 패턴**: 먼저 트렌드 없이 넓게 탐색해 유망 키워드를 추리고, 그 결과에만 "트렌드도 봐줘"로 재실행하세요. 데이터랩 한도를 크게 절약합니다.
- **시드 키워드는 최대 5개**: 한 번에 5개 이상의 키워드를 넣으면 잘리거나 오류가 납니다. 쉼표로 구분해 5개 이하로 요청하세요.
- **캐시 활용**: 같은 작업 폴더에서 1시간 이내 동일 키워드를 다시 조회하면 블로그 문서수 API를 다시 호출하지 않아 빠르게 결과가 나옵니다.
- ⚠️ **API 키 5개 모두 필요**: 검색광고 API 3개와 오픈 API 2개가 모두 설정돼 있어야 지표 계산이 가능합니다. 하나라도 없으면 실행되지 않습니다.
- ⚠️ **트렌드 남용 주의**: 시드 키워드가 많은데 트렌드까지 요청하면 하루 1,000회 한도가 한 번에 소진될 수 있습니다. 1차 필터링 후에만 사용하세요.
