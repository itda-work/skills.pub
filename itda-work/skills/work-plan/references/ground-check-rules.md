# Ground-check 규칙

work-plan가 메모를 생성하기 전에 수행하는 두 가지 검증 규칙.

DP-3 원칙: 검증 실패 시 abort(중단)가 아닌 downgrade(경고 표시)로 처리한다.
사용자에게 "⚠️ 확인 필요" 마커를 달아 경고하되, 메모는 저장한다.

---

## 1. 스킬명 검증 규칙

메모에 등장하는 모든 `itda-*` 스킬 이름은 `skill-catalog.md`에 실제로 존재해야 한다.

### 허용된 스킬 목록

`skill-catalog.md`에 등재된 스킬명만 메모에 기입 가능하다.
카탈로그에 없는 스킬명(예: `itda-foo-bar`, `itda-phantom-skill`)은 절대 기입하지 않는다.

### 실패 시 처리

```
⚠️ 확인 필요: 'itda-phantom' 스킬이 카탈로그에서 확인되지 않았습니다.
```

위 마커를 해당 항목 옆에 추가하고, 메모 상단에 경고 박스를 삽입한다.

---

## 2. 환경변수명 검증 규칙

메모에 등장하는 모든 환경변수(API 키 이름)는 허용 목록에 있어야 한다.

허용 목록 = **① 아래 기본 표 ∪ ② `skill-catalog.md` "필요한 키" 열 자동 파생**
(`ground_check.get_known_env_vars()`, #1216). 카탈로그는 저장소 생성기가 공개 팩 스킬만 모아 만든
생성물이므로, 스킬이 추가·변경되면 카탈로그 재생성만으로 허용 목록이 따라온다.
아래 기본 표는 발급 방법 안내를 가진 대표 키만 담는다 — 표에 없는 카탈로그 파생 키의
발급 방법은 해당 스킬의 SKILL.md·GUIDE 를 참조한다.

### 기본 환경변수 표 (발급 방법 안내용)

| 환경변수명 | 사용하는 스킬 | 발급 방법 요약 |
|-----------|------------|--------------|
| NAVER_SEARCHAD_ACCESS_KEY | blog-seo, eatery-trend | 네이버 검색광고 API 콘솔 → 액세스 키 |
| NAVER_SEARCHAD_SECRET_KEY | blog-seo, eatery-trend | 네이버 검색광고 API 콘솔 → 시크릿 키 |
| RONE_API_KEY | realty-price-stats | 한국부동산원 R-ONE 가입 후 발급 |
| KO_DATA_API_KEY | g2b, realty-* | 공공데이터포털(data.go.kr) → 회원가입 → 해당 데이터셋 활용신청 |
| KOSIS_API_KEY | kosis, realty-supply | KOSIS 통계청(kosis.kr) → 개발자 센터 → API 키 발급 |
| DART_API_KEY | dart, market-scan | DART 공시(dart.fss.or.kr) → 오픈 API → 인증키 신청 |
| ECOS_API_KEY | ecos, market-scan | 한국은행 경제통계(ecos.bok.or.kr) → 개발자 센터 → API 키 |

### 실패 시 처리

```
⚠️ 확인 필요: 'FOO_API_KEY' 환경변수가 알려진 목록에 없습니다.
```

위 마커를 해당 항목 옆에 추가하고, 메모 상단에 경고 박스를 삽입한다.

### 메일·캘린더 계정은 환경변수가 아니다

email·calendar·morning-brief·time-audit 은 메일·캘린더 계정을 **itda-hyve(PC 에 설치하는 앱) 설정 창의
"계정" 화면**에 등록해 두고 그 앱의 도구로만 쓴다. 비밀번호는 itda-hyve 안에만 있고 Claude 에게 오지 않는다.

- 메모의 "필요한 키·접근 권한" 에 메일·캘린더 계정 이메일·앱 비밀번호를 **환경변수 이름으로 적지 않는다**.
  대신 `ground_check.ACCOUNT_NOTICE` 한 줄(계정 화면 → 제공자·이메일·앱 비밀번호 → 연결 테스트 → 저장)을 적는다 —
  계획에 위 스킬이 있으면 `ground_check.account_notice(스킬 이름들)` 가 그 줄을 돌려준다.
- 앱 비밀번호 **발급** 절차는 서비스별 안내를 링크한다:
  [네이버](https://itda.work/credentials/naver-app-password/) · [iCloud](https://itda.work/credentials/icloud-app-password/).
  Gmail·다음/카카오·회사 메일은 email 스킬 GUIDE 의 서비스별 절차를 가리킨다.
- 계정이 이미 등록돼 있는지는 스크립트가 판단하지 못한다(itda-hyve 도구만 안다). 메모는 등록 안내만 싣고,
  확인은 실행 첫 단계에서 그 스킬이 한다.
- 옛 이름(`<서비스>_EMAIL`·`<서비스>_APP_PASSWORD` 등)이 메모에 들어오면 `check_env_var` 가 등록 안내 마커로 내려보낸다:

```
⚠️ 확인 필요: '<서비스>_EMAIL' 는 쓰지 않습니다 — 메일·캘린더 계정은 itda-hyve 설정 창의 "계정" 화면에 등록합니다.
```

---

## 3. 경고 박스 형식

ground-check 실패 항목이 하나라도 있으면 메모 최상단에 다음 형식의 경고 박스를 삽입한다:

```markdown
---
> ⚠️ **확인이 필요한 항목이 있습니다**
>
> - 'itda-phantom' 스킬이 카탈로그에서 확인되지 않았습니다.
> - 'FOO_API_KEY' 환경변수가 알려진 목록에 없습니다.
>
> 아래 계획을 실행하기 전에 위 항목을 확인해주세요.
---
```

---

## 4. 절대 경로 검사

메모 본문에 절대 파일시스템 경로가 포함되어 있으면 제거 또는 GUI 수준으로 변환한다.

금지 패턴:
- `/Users/...`
- `/home/...`
- `C:\Users\...`
- `C:/Users/...`

허용 표현:
- "바탕화면에 새 폴더를 만들어서 그 안에 넣어주세요"
- "내 문서 폴더에 저장해두세요"
- "원드라이브에 업로드해주세요"
