# 2.2.3.2 통계자료 SDMX(DSD)

출처: 통계청 발간 "KOSIS 공유서비스(OpenAPI) 개발가이드 v1.0" 2.2.3.2 (페이지 54~69)
원본 PDF: [openApi_manual_v1.0.pdf](openApi_manual_v1.0.pdf)
추출일: 2026-04-28

## 호출 정보

- **호출 URL**: `http://kosis.kr/openapi/statisticsData.do`

## 입력 변수

### 자료등록 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| userStatsId | String | 사용자 등록 통계표 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

### 통계표선택 방법

| 항목명(영문) | 변수타입 | 항목설명 | 비고 |
|------------|---------|---------|------|
| apiKey | String | 발급된 인증키 | 필수 |
| orgId | String | 기관 ID | 필수 |
| tblId | String | 통계표 ID | 필수 |
| objL2 ~ objL8 | String | 분류2(두번째 분류코드) ~ 분류8(여덟번째 분류코드) | 선택 |
| itmId | String | 항목 | 필수 |
| type | String | SDMX의 유형(DSD, Generic, StructureSpecific) | 필수 |
| format | String | 결과 유형(json, sdmx) | 필수 |
| version | String | 결과값 구분 | 생략시 구버전으로 데이터 출력 |

> **주의**: 매뉴얼의 SDMX 통계표선택 표에서는 objL1이 명시적으로 표기되지 않았으나, 일반 JSON 통계표선택(2.2.3.1)에서는 objL1이 필수로 명시. SDMX 호출 시에도 첫 번째 분류는 통계표 구조상 필수로 간주.

## 출력 변수 (SDMX DSD 트리)

```
- Header
    - Id              (기관코드_통계표ID)
    - Name            (통계표명)
    - Prepared        (전송시간)
    - Sender
        - Id          (전송기관)
        - Name        (전송기관명)
        - Contact
            - Department      (담당부서)
            - Telephone       (담당부서 연락처)
    - Source          (출처)
- Codelist
    - Codelist
        - Id          (코드리스트ID)
        - Name        (코드리스트명)
        - Description (코드리스트영문명)
        - Code
            - Id      (코드ID)
            - Name    (코드명)
- Concepts
    - ConceptsScheme
        - Id          (컨셉스키마ID)
        - Name        (컨셉스키마명)
        - Description (컨셉스키마영문명)
        - Concept
            - Id          (컨셉ID)
            - Name        (컨셉명)
            - Description (컨셉영문명)
- DataStructures
    - DataStructure
        - Id          (통계표ID)
        - Name        (통계표명)
        - DataStructureComponents
            - Dimension
                - Id              (디멘젼Id)
                - conceptIdentity
                    - Id          (컨셉객체Id)
```

## 예제 호출 패턴 (페이지 56~69)

### JSP (Ajax + jquery + SimpleChart)

```javascript
$.ajax({
  type: "GET",
  url: "http://mgmk.kosis.kr/openapi_dev/Expt/statisticsData.do?method=getList&apiKey=<KEY>&format=sdmx&type=StructureSpecific&userStatsId=openapisample/101/DT_1IN1502/2/1/20191106094026_1&prdSe=Y&newEstPrdCnt=3&version=v2_1",
  data: "",
  async: true,
  dataType: "xml",
  success: function(object) {
    var data = object.documentElement.childNodes[1].childNodes[0].childNodes;
    // ...
  }
});
```

### R

```r
library(httr)
library(rvest)
library(XML)
library(ggplot2)

v_apiKey <- Sys.getenv('KOSIS_TOKEN')
baseurl <- 'https://kosis.kr/openapi/statisticsData.do'

res <- GET(
  url = baseurl,
  query = list(
    method = 'getList',
    format = 'sdmx',
    apiKey = v_apiKey,
    userStatsId = 'openapisample/101/DT_1IN1502/2/1/20191106094026_1',
    jsonVD = 'Y',
    type = 'StructureSpecific',
    prdSe = 'Y',
    newEstPrdCnt = 3,
    prdInterval = 1,
    version = 'v2_1'
  )
)

docParse <- xmlParse(res)
v_tbl_nm <- xmlToList(docParse)$Header$Name      # 통계표명
docList <- xmlToList(docParse)$DataSet$Series
```

### Python (requests + BeautifulSoup)

```python
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup

open_url = (
    'https://kosis.kr/openapi/statisticsData.do?'
    'method=getList&apiKey=<KEY>&format=sdmx&type=StructureSpecific'
    '&userStatsId=openapisample/101/DT_1IN1502/2/1/20191106094026_1'
    '&prdSe=Y&newEstPrdCnt=3&version=v2_1'
)

res = requests.get(open_url)
soup = BeautifulSoup(res.content, 'html.parser')
dataList = soup.find_all('obs')

for item in dataList:
    period = item.get('time_period')   # 년도
    value = item.get('obs_value')      # 값
```

## 메타 조회 (페이지 65~67)

`getMeta` method를 통한 메타데이터 별도 조회:

```
URL = "http://mgmk.kosis.kr/openapi_dev/statisticsData.do"
parameters = {
  "method": "getMeta",       # 메타 조회 모드
  "apiKey": <KEY>,
  "format": "xml",
  "type": "TBL" | "ITM" | "HJG" | "UNIT",   # 조회 타입
  "orgId": "101",
  "tblId": "DT_1B01003",
  "objId": "ITEM" | "HJG" | "UNIT",         # type별 obj 지정
  "itmId": <항목ID>,
  "unitId": <단위ID>,
}
```

type별 사용 예:
- `type=TBL` + orgId + tblId → 통계표 명칭 조회
- `type=ITM` + orgId + tblId + objId=ITEM + itmId → 항목 명칭 조회
- `type=ITM` + orgId + tblId + objId=HJG + itmId → 분류 명칭 조회
- `type=UNIT` + unitId → 단위 명칭 조회
- `type=SOURCE` + orgId + tblId → 출처 정보 조회

이 메타 조회는 통계자료(statisticsData.do)의 부가 기능으로, 별도의 메타자료 API(2.5)와는 다른 채널.
