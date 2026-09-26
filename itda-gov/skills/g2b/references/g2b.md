# 나라장터 (G2B) API 참조

나라장터 공공데이터개방표준서비스 API 상세 가이드.
공공데이터포털(https://www.data.go.kr)의 `KO_DATA_API_KEY` 인증키를 사용합니다.

## 스크립트 위치

`scripts/collect_g2b.py` — CLI 진입점
`scripts/g2b_api.py` — API 클라이언트 래퍼

## 기본 사용법

```bash
# 최근 7일 입찰공고 조회 (JSON)
python3 scripts/collect_g2b.py

# 날짜 범위 지정
python3 scripts/collect_g2b.py --from 2026-03-01 --to 2026-03-28

# 키워드 필터링
python3 scripts/collect_g2b.py --keyword "소프트웨어"

# 테이블 형식 출력
python3 scripts/collect_g2b.py --format table

# 상세 필드 포함 (입찰자격, 담당자, 일정 등)
python3 scripts/collect_g2b.py --format table --detail

# 단일 페이지 조회 (--rows/--page 명시 시 자동 순회 끔)
python3 scripts/collect_g2b.py --rows 50 --page 2

# 키워드 자동 전체 순회 + 순회 상한 조정
python3 scripts/collect_g2b.py --keyword "용역" --max-pages 5
```

Windows: `python3` → `py -3`

## CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--from` | 7일 전 | 조회 시작일 (YYYY-MM-DD) |
| `--to` | 오늘 | 조회 종료일 (YYYY-MM-DD) |
| `--keyword` | — | 공고명 키워드 필터 (부분 일치, 대소문자 무시). 날짜 범위 전 페이지 자동 순회 후 필터 |
| `--rows` | 10 | **단일 페이지 모드** — 페이지당 결과 수 (최대 999). 명시 시 자동 순회 끔 |
| `--page` | 1 | **단일 페이지 모드** — 페이지 번호. 명시 시 자동 순회 끔 |
| `--max-pages` | 20 | 자동 순회 상한 페이지 수 (페이지당 최대 999건). 상한 도달 시 미조회분 경고 |
| `--format` | json | 출력 형식 (`json` \| `table`) |
| `--detail` | false | 상세 필드 포함 (table 형식에서 유효) |
| `--api-key` | — | 인증키 직접 지정 |

> **자동 전체 순회 (기본)**: `--rows`/`--page` 미지정 시 키워드 검색은 날짜 범위
> 전 페이지를 순회한다. 나라장터는 하루 수천 건이 등록되므로 첫 페이지만 보면
> 키워드가 뒤쪽 공고에 있을 때 거짓 0건(false 0)이 발생한다 — 순회로 이를 방지한다.
>
> **단일 페이지 모드**: `--rows` 또는 `--page`를 명시하면 자동 순회를 끄고 해당
> 페이지만 조회한다.

## 출력 포맷

### JSON 출력 (기본)

```json
{
  "status": "ok",
  "count": 5,
  "total_count": 3342,
  "scanned_count": 3342,
  "truncated": false,
  "page": "all",
  "results": [
    {
      "bidNtceNo": "20260318001",
      "bidNtceNm": "소프트웨어 개발 용역",
      "ntceInsttNm": "조달청",
      "presmptPrce": "100000000",
      "bidClseDt": "2026/03/25 18:00"
    }
  ]
}
```

출력 필드 의미:

| 필드 | 의미 |
|------|------|
| `total_count` | API가 보고한 **필터 전** 날짜 범위 전체 결과 수 |
| `scanned_count` | 실제 순회·스캔한(중복 제거 후) 항목 수 |
| `count` | **키워드 필터 후** 결과 수 (`results` 길이와 일치) |
| `truncated` | `--max-pages` 상한으로 미조회분이 남으면 `true` |
| `warnings` | `truncated`일 때만 추가되는 미조회분 안내 배열 |
| `page` | 단일 페이지 모드면 번호, 자동 순회면 `"all"` |

### 에러 출력

```json
{
  "status": "error",
  "error": "api",
  "detail": "API 응답 에러: resultCode=10 (ServiceKey 없음)"
}
```

에러 타입:
- `config` — API 키 미설정
- `api` — API 호출 오류 (네트워크, resultCode 오류)
- `argument` — 날짜 형식·범위 오류

### 테이블 출력 (`--format table`)

섹션별 구조화 출력:

- **공고일반**: 공고번호, 공고명, 공고기관, 입찰방식
- **가격정보**: 추정가격, 배정예산액
- **입찰일정**: 입찰시작/마감, 개찰일
- **공고링크**: 상세 URL
- **입찰자격** (`--detail`): 지역제한, 업종제한
- **담당자정보** (`--detail`): 공고담당자, 수요담당자
- **현장설명** (`--detail`): 현장설명 일시/장소
- **공동수급** (`--detail`): 협정 마감일
- **기타** (`--detail`): 조달청공고여부, 데이터기준일

## 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 런타임 오류 (API 키 미설정, API 오류) |
| 2 | 인자 오류 |

## API 상세

### 엔드포인트

```
GET https://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo
```

### 요청 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `serviceKey` | ✓ | 공공데이터포털 인증키 | (URL 인코딩) |
| `type` | ✓ | 응답 형식 | `json` |
| `pageNo` | — | 페이지 번호 | `1` |
| `numOfRows` | — | 페이지당 결과 수 | `10` (최대 999) |
| `bidNtceBgnDt` | ✓ | 입찰공고 시작일시 | `202603010000` |
| `bidNtceEndDt` | ✓ | 입찰공고 종료일시 | `202603282359` |

> 날짜 범위는 최대 1개월 (31일) 이내.

### 응답 구조

```json
{
  "response": {
    "header": {
      "resultCode": "00",
      "resultMsg": "NORMAL SERVICE"
    },
    "body": {
      "items": [...],
      "totalCount": 42,
      "pageNo": 1,
      "numOfRows": 10
    }
  }
}
```

### 주요 응답 필드

| 필드명 | 설명 |
|--------|------|
| `bidNtceNo` | 입찰공고번호 |
| `bidNtceNm` | 공고명 |
| `bidNtceSttusNm` | 공고종류 (일반공고, 재공고 등) |
| `ntceInsttNm` | 공고기관명 |
| `dmndInsttNm` | 수요기관명 |
| `presmptPrce` | 추정가격 (원) |
| `asignBdgtAmt` | 배정예산액 (원) |
| `bidClseDt` | 입찰마감일시 |
| `opengDt` | 개찰일시 |
| `cntrctCnclsMthdNm` | 계약방법 |
| `bidwinrDcsnMthdNm` | 낙찰방법 |
| `elctrnBidYn` | 전자입찰여부 (Y/N) |
| `bidNtceDtlUrl` | 공고상세 URL |
| `intrntnlBidYn` | 국제입찰여부 (Y/N) |
| `rgnLmtYn` | 지역제한여부 (Y/N) |
| `indstrytyLmtYn` | 업종제한여부 (Y/N) |
| `bidprcPsblIndstrytyNm` | 입찰가능업종 |

### 에러 코드 (resultCode)

| 코드 | 의미 |
|------|------|
| `00` | 정상 |
| `01` | 애플리케이션 에러 |
| `02` | DB 에러 |
| `03` | 데이터없음 |
| `04` | HTTP 에러 |
| `05` | 서비스 연결실패 |
| `06` | 날짜 Default/Format 에러 |
| `10` | 잘못된 요청 파라미터 |
| `11` | 필수 요청 파라미터 없음 |
| `20` | 서비스 접근거부 |
| `22` | 서비스 요청 제한 초과 |
| `30` | 등록되지 않은 서비스키 |
| `31` | 기한 만료된 서비스키 |
| `32` | 등록되지 않은 IP |

## 인증키 (serviceKey)

공공데이터포털에서 발급받은 인증키는 URL 인코딩 상태로 제공될 수 있습니다.
`collect_g2b.py`는 자동으로 `normalize_service_key()`를 적용하여 이중 인코딩을 방지합니다.

**인증키 발급 방법:**
1. https://www.data.go.kr 접속 및 회원가입
2. '조달청_나라장터 공공데이터개방표준서비스' 검색
3. 활용신청 (자동승인)
4. 마이페이지 > 인증키 확인 (일반 인증키 Decoding 사용)

**설정 방법:**
```bash
# 권장 (모든 환경): 작업 폴더 루트(예: outputs/)의 .env 파일
KO_DATA_API_KEY=발급받은_키

# CLI 직접 지정 (일회성)
python3 scripts/collect_g2b.py --api-key "발급받은_키"

# (로컬 CLI 전용: claude config set env.KO_DATA_API_KEY "키" 또는 셸 환경변수도 가능)
```

## 사용 시나리오

### 입찰 제안서 작성

```bash
# 1. 관련 입찰공고 확인
python3 scripts/collect_g2b.py --keyword "소프트웨어 개발" --from 2026-03-01 --to 2026-03-28

# 2. 공고기관/경쟁사 재무 조회 (DART)
python3 scripts/collect_company.py profile --name "조달청" --year 2024

# 3. 거시경제 환경 파악 (ECOS)
python3 scripts/collect_econ.py key

# 4. 관련 정부 지원사업 확인 (funding 스킬 — 모집중 전수 수집 후 검토)
python3 scripts/survey_crawl.py list kstartup -o kstartup_all.jsonl
```

## 제약사항

- 날짜 범위: 최대 1개월 (31일) 이내
- 페이지당 최대 결과: 999건
- 요청 타임아웃: 15초
- API 응답은 나라장터 공고 시간 기준 (KST)
