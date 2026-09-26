# 네이버 API 레퍼런스

## API 키 발급 방법

발급 절차의 정본은 저장소 `skills/docs/credentials/`에 있다 (SPEC-CREDENTIALS-GUIDE-001):

- 네이버 검색광고 API (`NAVER_SEARCHAD_ACCESS_KEY/SECRET_KEY/CUSTOMER_ID`) → `docs/credentials/naver-searchad.md`
- 네이버 오픈 API (`NAVER_CLIENT_ID/SECRET`) → `docs/credentials/naver-openapi.md`

사용자에게 발급을 안내할 때는 본 스킬 `GUIDE.md`의 "처음 설정하기" 요약 절차를 따른다.
오픈 API 등록 시 사용 API는 **검색 + 데이터랩(검색어트렌드)** 체크 (쇼핑인사이트 불필요).

> **⚠️ 이관 고지**: 오픈 API(검색·데이터랩)는 NCP **NAVER API HUB**로 이관 중 — 2026-07-30 이후 개발자센터 신규 신청 불가, 기존 키는 2027-06-30까지 유효. 상세는 `docs/credentials/naver-openapi.md`.

키 설정 위치: 작업 폴더 루트 `.env`(모든 환경 자동 탐색, Cowork 포함), 또는 셸 환경변수.

---

## API 기술 레퍼런스

### 1. 네이버 검색광고 API (키워드 확장)

#### 인증 방식

HMAC-SHA256 서명 방식.

```python
timestamp = str(int(time.time() * 1000))
message = f"{timestamp}.{method}.{uri}"
signature = base64.b64encode(
    hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
).decode()
```

요청 헤더:
- `X-Timestamp`: 밀리초 타임스탬프
- `X-API-KEY`: Access License (NAVER_SEARCHAD_ACCESS_KEY)
- `X-Customer`: 고객 ID (NAVER_SEARCHAD_CUSTOMER_ID)
- `X-Signature`: HMAC-SHA256 서명

#### 키워드 도구 API

```
GET https://api.naver.com/keywordstool?hintKeywords=파이썬&showDetail=1
```

응답 형식:

```json
{
  "keywordList": [
    {
      "relKeyword": "파이썬 독학",
      "monthlyPcQcCnt": "12000",
      "monthlyMobileQcCnt": "35000",
      "compIdx": "중간"
    }
  ]
}
```

- `monthlyPcQcCnt`: 월간 PC 검색수 (문자열, `"< 10"` 가능 → 5로 대체)
- `monthlyMobileQcCnt`: 월간 모바일 검색수
- `compIdx`: 경쟁 지수 (높음/중간/낮음)

---

### 2. 네이버 블로그 검색 API (문서수 조회)

#### 인증 방식

헤더 방식:
- `X-Naver-Client-Id`: NAVER_CLIENT_ID
- `X-Naver-Client-Secret`: NAVER_CLIENT_SECRET

#### 블로그 검색 API

```
GET https://openapi.naver.com/v1/search/blog.json?query=파이썬&display=1
```

응답 형식:

```json
{
  "total": 123456,
  "start": 1,
  "display": 1,
  "items": [...]
}
```

- `total`: 블로그 문서 총 수 (포화지수 계산에 사용)
- 배치 조회 시 0.1초 딜레이 적용 (Rate Limit 방지)

---

### 3. 네이버 데이터랩 API (트렌드 분석)

`--trend` 플래그 사용 시에만 호출됩니다. 인증은 블로그 검색 API와 동일합니다.

#### 검색어 트렌드 API

```
POST https://openapi.naver.com/v1/datalab/search
Content-Type: application/json
```

요청 바디:

```json
{
  "startDate": "2024-01-01",
  "endDate": "2024-12-31",
  "timeUnit": "month",
  "keywordGroups": [
    {
      "groupName": "파이썬",
      "keywords": ["파이썬"]
    }
  ]
}
```

응답 형식:

```json
{
  "results": [
    {
      "title": "파이썬",
      "data": [
        {"period": "2024-01", "ratio": 80.0},
        {"period": "2024-02", "ratio": 75.0}
      ]
    }
  ]
}
```

- `ratio`: 조회기간 내 최고 검색량 대비 상대적 비율 (0~100)
- 12개월 데이터로 rising / falling / seasonal / stable 트렌드 분류

---

## Rate Limit 처리

| API | 일일 한도 | 초당 한도 | 재시도 전략 |
|-----|---------|---------|------------|
| 검색광고 (키워드 확장) | 제한 없음 | 초당 10 요청 | 지수 백오프 (1s→2s→4s, 최대 3회) |
| 블로그 검색 | **25,000회/일** | 초당 10 요청 | 배치 간 0.1s 딜레이 |
| 데이터랩(검색어트렌드) | **1,000회/일** | 초당 10 요청 | 지수 백오프 (1s→2s→4s, 최대 3회) |

> **데이터랩 한도 주의**: 일일 1,000회는 `--trend` 플래그 사용 시 키워드 1개당 1회 소모됩니다.
> `--top-n 50` 기준으로 하루 최대 20회 실행이 가능합니다. 대량 분석 시 `--trend` 없이 먼저 실행하고,
> 유망 키워드만 추려서 별도로 트렌드를 확인하는 것을 권장합니다.
