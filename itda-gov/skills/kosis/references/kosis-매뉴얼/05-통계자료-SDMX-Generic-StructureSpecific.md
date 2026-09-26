# 2.2.3.3 SDMX(Generic) / 2.2.3.4 SDMX(StructureSpecific)

출처: 통계청 발간 "KOSIS 공유서비스(OpenAPI) 개발가이드 v1.0" 2.2.3.3~2.2.3.4 (페이지 70~101)
원본 PDF: [openApi_manual_v1.0.pdf](openApi_manual_v1.0.pdf)
추출일: 2026-04-28

---

## 2.2.3.3 SDMX(Generic)

- **호출 URL**: `http://kosis.kr/openapi/statisticsData.do`

### 입력 변수

#### 자료등록 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| userStatsId | String | 사용자 등록 통계표 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| prdSe | String | 수록주기 | 필수 |
| startPrdDe (시점기준) | String | 시작수록시점 | 선택 (시점기준 또는 최신자료기준 택1) |
| endPrdDe (시점기준) | String | 종료수록시점 | 선택 |
| newEstPrdCnt (최신자료기준) | String | 최근수록시점 개수 | 선택 |
| prdInterval (최신자료기준) | String | 수록시점 간격 | 선택 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

#### 통계표선택 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| orgId | String | 기관 ID | 필수 |
| tblId | String | 통계표 ID | 필수 |
| objL2 ~ objL8 | String | 분류2(두번째 분류코드) ~ 분류8(여덟번째 분류코드) | 선택 |
| itmId | String | 항목 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| prdSe | String | 수록주기 | 필수 |
| startPrdDe (시점기준) | String | 시작수록시점 | 선택 (시점기준 또는 최신자료기준 택1) |
| endPrdDe (시점기준) | String | 종료수록시점 | 선택 |
| newEstPrdCnt (최신자료기준) | String | 최근수록시점 개수 | 선택 |
| prdInterval (최신자료기준) | String | 수록시점 간격 | 선택 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

### 출력 변수 (SDMX Generic)

| 그룹 | 항목 | 설명 |
|------|------|------|
| Header.Id | | 기관코드_통계표ID |
| Header.Name | | 통계표명 |
| Header.Prepared | | 전송시간 |
| Header.Sender.Id | | 전송기관 |
| Header.Sender.Name | | 전송기관명 |
| Header.Sender.Contact.Department | | 담당부서 |
| Header.Sender.Contact.Telephone | | 담당부서 연락처 |
| Header.Source | | 출처 |
| Series.SeriesKey.Value.Id | | 시리즈키ID |
| Series.SeriesKey.Value.value | | 시리즈키값 |
| Series.SeriesKey.Value.UNIT | | 단위 |
| Series.Obs.ObsDimension.Value | | 시점 |
| Series.Obs.ObsValue.Value | | 수치자료값 |
| Series.Obs.LstChnDe.Value | | 최종수정일 |

SDMX Generic 형식의 핵심: 각 차원(Dimension)을 일반화된(Generic) Value 노드로 표현.

---

## 2.2.3.4 SDMX(StructureSpecific)

- **호출 URL**: `http://kosis.kr/openapi/statisticsData.do`

### 입력 변수

#### 자료등록 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| userStatsId | String | 사용자 등록 통계표 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| prdSe | String | 수록주기 | 필수 |
| startPrdDe (시점기준) | String | 시작수록시점 | 선택 (시점기준 또는 최신자료기준 택1) |
| endPrdDe (시점기준) | String | 종료수록시점 | 선택 |
| newEstPrdCnt (최신자료기준) | String | 최근수록시점 개수 | 선택 |
| prdInterval (최신자료기준) | String | 수록시점 간격 | 선택 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

#### 통계표선택 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| orgId | String | 기관 ID | 필수 |
| tblId | String | 통계표 ID | 필수 |
| objL2 ~ objL8 | String | 분류2(두번째 분류코드) ~ 분류8(여덟번째 분류코드) | 선택 |
| itmId | String | 항목 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| prdSe | String | 수록주기 | 필수 |
| startPrdDe (시점기준) | String | 시작수록시점 | 선택 (시점기준 또는 최신자료기준 택1) |
| endPrdDe (시점기준) | String | 종료수록시점 | 선택 |
| newEstPrdCnt (최신자료기준) | String | 최근수록시점 개수 | 선택 |
| prdInterval (최신자료기준) | String | 수록시점 간격 | 선택 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

### 출력 변수 (SDMX StructureSpecific)

| 그룹 | 항목 | 설명 |
|------|------|------|
| Header.Id | | 기관코드_통계표ID |
| Header.Name | | 통계표명 |
| Header.Prepared | | 전송시간 |
| Header.Sender.Id | | 전송기관 |
| Header.Sender.Name | | 전송기관명 |
| Header.Sender.Contact.Department | | 담당부서 |
| Header.Sender.Contact.Telephone | | 담당부서 연락처 |
| Header.Source | | 출처 |
| Series.UNIT | | 단위 |
| Series.ITEM | | 항목 |
| Series.FIEQ | | 주기 |
| Series.C_분류 | | C_분류 (8개 분류까지 가능) |
| Series.OBS.TIME_PERIOD | | 시점 |
| Series.OBS.OBS_VALUE | | 수치자료 |

SDMX StructureSpecific 형식의 핵심: Series 노드에서 차원이 직접 속성(UNIT, ITEM, FIEQ, C_분류)으로 노출되어 파싱이 용이.

### 호출 예제 패턴

```
URL = "https://kosis.kr/openapi/statisticsData.do"
parameters = {
  "method": "getList",
  "apiKey": <KEY>,
  "format": "sdmx",
  "type": "StructureSpecific",
  "userStatsId": "openapisample/101/DT_1IN1502/2/1/20191106094026_1",
  "prdSe": "Y",
  "newEstPrdCnt": "3",
  "prdInterval": "1",
  "version": "v2_1",
}
```

응답 파싱 (Python):
```python
soup = BeautifulSoup(res.content, 'html.parser')
title = soup.find('common:name').text   # 차트제목
dataList = soup.find_all('obs')

for item in dataList:
    period = item.get('time_period')   # 년도
    value = item.get('obs_value')      # 값
```
