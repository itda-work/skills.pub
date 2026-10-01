# 나라장터 (G2B) API 참조

나라장터 공공데이터개방표준서비스 API 상세 가이드.
요청은 itda-hyve 의 `http_request` 가 보내고, 키는 itda-hyve GUI 시크릿 탭의 `KO_DATA_API_KEY`(Decoding 키)를
`{{secret:KO_DATA_API_KEY}}` 자리표시자로만 가리킨다. 호출 절차의 정본은 `SKILL.md`, 공용 규약은 `references/netbridge.md` 다.

## 스크립트

스크립트는 네트워크를 하지 않는다.

- `scripts/collect_g2b.py plan` — 기간을 달력 달 단위 창으로 나눈 호출 계획(창마다 1쪽)
- `scripts/collect_g2b.py collect --input …` — 저장한 응답을 창별로 전량 대조·중복 제거·키워드 필터·출력
- `scripts/g2b_api.py` — 창 나누기·호출 인자·응답 파서

## collect 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--input` | (필수) | 저장한 응답 파일(들). 이름 규칙 `bids-<시작 YYYYMMDD>-<끝 YYYYMMDD>-p<쪽>.json` — 창을 이름으로 가른다 |
| `--keyword` | — | 공고명 키워드 필터 (부분 일치, 대소문자 무시). 창의 전 쪽을 받은 뒤 필터 |
| `--max-pages` | 20 | 창마다 받을 쪽 상한 (쪽당 최대 999건). 필요한 쪽이 넘으면 `truncated` |
| `--single-page` | false | 전량 대조 없이 넘긴 쪽만 훑어본다 |
| `--next-plan` | — | 전량 미달이면 더 받을 호출을 batch `plan_file` 형식으로 쓴다(40호출씩 `…a.json`·`…b.json` 으로 나눔) |
| `--format` | json | 출력 형식 (`json` \| `table`) |
| `--detail` | false | 상세 필드 포함 (table 형식에서 유효) |

> 나라장터는 하루 1,800~1,900건이 등록된다(2026-09-28·29 실측 1,836·1,901건). 첫 쪽만 보면 키워드가 뒤쪽 공고에
> 있을 때 거짓 0건이 난다 — collect 가 창마다 `totalCount` 와 받은 쪽을 대조해 모자라면 실패한다.

## 출력 포맷

### JSON 출력 (기본)

```json
{
  "status": "ok",
  "count": 24,
  "total_count": 3737,
  "scanned_count": 3737,
  "truncated": false,
  "page": "all",
  "windows": [{"from": "20260928", "to": "20260928", "total_count": 1836, "pages": [1, 2], "collected": 1836, "need_pages": 2, "will_truncate": false}],
  "results": [{"bidNtceNo": "R26BK01746734", "bidNtceNm": "…", "ntceInsttNm": "…"}],
  "sources": [{"path": "…/bids-20260928-20260928-p1.json", "page": 1, "total_count": 1836, "item_count": 999}]
}
```

| 필드 | 의미 |
|------|------|
| `total_count` | API가 보고한 **필터 전** 기간 전체 결과 수(창 합) |
| `scanned_count` | 받은 쪽에서 중복을 없앤 항목 수. `total_count` 보다 작으면 `truncated`·`--single-page`·받는 사이 공고 변화(경고) 중 하나 |
| `count` | **키워드 필터 후** 결과 수 (`results` 길이와 일치) |
| `truncated` | `--max-pages` 상한으로 미조회분이 남으면 `true` |
| `warnings` | 미조회분·쪽 경계 중복·쪽마다 다른 totalCount 안내 (있을 때만) |
| `page` | `--single-page` 면 그 쪽 번호, 아니면 `"all"` |

### 에러 출력

```json
{"status": "error", "error": "incomplete", "detail": "창마다 전량을 받지 못했습니다: …",
 "next_call_count": 57, "will_truncate": true,
 "windows": [{"from": "20260701", "to": "20260731", "total_count": 40000, "pages": [1], "collected": 999, "need_pages": 41, "will_truncate": true}, …],
 "plan_files": ["/Users/me/Projects/작업폴더/g2b/plan-next-1a.json", "/Users/me/Projects/작업폴더/g2b/plan-next-1b.json"],
 "next_calls_preview": [ … 앞 3개 … ]}
```

`plan_files` 는 `--next-plan` 에 준 경로를 펼친 **절대 경로**다(40호출씩 나뉜다). `--next-plan` 이 없으면 `plan_files`·`next_calls_preview` 대신
`next_calls`(전부)가 온다.

| `error` | 뜻 |
|---|---|
| `incomplete` | 창의 쪽이 모자라다. `next_calls`(또는 `plan_files`)가 더 받을 호출(batch `calls` 형식), `will_truncate` 면 받기 전에 사용자에게 묻는다 |
| `api` | 본문의 오류 코드(`error_code` — `07`·`gateway-30` 등) |
| `truncated` · `http` · `hyve` | 입력이 잘린 본문 · HTTP 오류 응답 · itda-hyve 호출 실패 자리 |
| `input` | 파일 없음·이름 규칙 위반·JSON 아님·같은 쪽 두 번·이름의 쪽(`p<n>`)과 본문 `pageNo` 불일치 |
| `argument` | 날짜 형식·범위 오류 (종료 코드 2) |

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
| 1 | 가공 실패 (입력·API 오류·전량 미달) |
| 2 | 인자 오류 |

## API 상세

### 엔드포인트

```
GET https://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo
```

### 요청 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `serviceKey` | ✓ | 공공데이터포털 인증키 — `params` 에 `{{secret:KO_DATA_API_KEY}}` | |
| `type` | ✓ | 응답 형식 | `json` |
| `pageNo` | — | 페이지 번호 | `1` |
| `numOfRows` | — | 페이지당 결과 수 | `999` (최대) |
| `bidNtceBgnDt` | ✓ | 입찰공고 시작일시 | `202609010000` |
| `bidNtceEndDt` | ✓ | 입찰공고 종료일시 | `202609302359` |

> 날짜 범위는 1개월 이내. 넘기면 `resultCode 07`(입력범위값 초과)이 온다(2026-09-30 실측: 3개월 → 07).

### 응답 구조

```json
{
  "response": {
    "header": {"resultCode": "00", "resultMsg": "정상"},
    "body": {"items": [...], "numOfRows": 999, "pageNo": 1, "totalCount": 1901}
  }
}
```

오류는 두 형태로 온다(2026-09-30 실측).

```json
{"nkoneps.com.response.ResponseError": {"header": {"resultCode": "07", "resultMsg": "입력범위값 초과 에러"}}}
```

```json
{"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NULL", "returnAuthMsg": "서비스 접근거부", "returnReasonCode": "20"}}}
```

두 번째는 공공데이터포털 게이트웨이 거부이고 HTTP 401 로 오지만, `save_as` 는 본문을 그대로 저장한다 — collect 가 본문으로 판정한다.

공고가 없는 창은 오류가 아니라 `resultCode 00` + `totalCount 0` + 빈 `items` 로 온다(2026-10-10~11 창 실측, 2026-09-30) — 명세의
`03 데이터없음` 은 이 경로에서 관측되지 않았다. 31일 창(`202608010000`~`202608312359`)도 `07` 없이 받아진다(같은 날 실측, `totalCount` 32,895).

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
| `bidClseDate` · `bidClseTm` | 입찰마감일·시각 |
| `opengDate` · `opengTm` | 개찰일·시각 |
| `cntrctCnclsMthdNm` | 계약방법 |
| `bidwinrDcsnMthdNm` | 낙찰방법 |
| `elctrnBidYn` | 전자입찰여부 (Y/N) |
| `bidNtceUrl` | 공고상세 URL |
| `intrntnlBidYn` | 국제입찰여부 (Y/N) |
| `rgnLmtYn` | 지역제한여부 (Y/N) |
| `indstrytyLmtYn` | 업종제한여부 (Y/N) |
| `bidprcPsblIndstrytyNm` | 입찰가능업종 |

### 에러 코드 (resultCode · returnReasonCode)

| 코드 | 의미 |
|------|------|
| `00` | 정상 |
| `01` | 애플리케이션 에러 |
| `02` | DB 에러 |
| `03` | 데이터없음 |
| `04` | HTTP 에러 |
| `05` | 서비스 연결실패 |
| `06` | 날짜 Default/Format 에러 |
| `07` | 입력범위값 초과 (실측 — 기간 1개월 초과) |
| `10` | 잘못된 요청 파라미터 |
| `11` | 필수 요청 파라미터 없음 |
| `20` | 서비스 접근거부 (게이트웨이 — 활용신청 승인 전, 또는 키가 비었음) |
| `22` | 서비스 요청 제한 초과 |
| `30` | 등록되지 않은 서비스키 (Encoding 키를 등록한 경우 — Decoding 키로 다시 등록) |
| `31` | 기한 만료된 서비스키 |
| `32` | 등록되지 않은 IP |

## 인증키 (serviceKey)

1. https://www.data.go.kr 접속 및 회원가입
2. '조달청_나라장터 공공데이터개방표준서비스' 검색 → 활용신청 (자동승인)
3. 마이페이지 > 인증키 확인 → **일반 인증키(Decoding)** 복사
4. itda-hyve GUI 시크릿 탭에 `KO_DATA_API_KEY` 로 등록

`params` 는 값을 한 번 URL 인코딩하므로 Decoding 키를 등록해야 한다. Encoding 키(`%2B`·`%2F`·`%3D` 가 든 것)는 이중 인코딩되어 `30` 이 난다.

## 제약사항

- 날짜 범위: 1개월 이내 (plan 이 달력 달 단위로 나눈다)
- 페이지당 최대 결과: 999건 (한 쪽 응답 약 2MB)
- API 응답은 나라장터 공고 시간 기준 (KST)
