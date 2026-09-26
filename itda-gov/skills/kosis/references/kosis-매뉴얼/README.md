# KOSIS OpenAPI 개발가이드 v1.0 — 발췌 인덱스

원본: 통계청 발간 "KOSIS 공유서비스(OpenAPI) 개발가이드 v1.0" (158페이지, 2026-04-28 시점 기준)
원본 PDF: [openApi_manual_v1.0.pdf](openApi_manual_v1.0.pdf)
발췌일: 2026-04-28

매뉴얼 본문을 11개 섹션으로 분할하여 md로 발췌하였다. 표·입출력 변수·예제 호출 패턴 중심으로 정리.

## 목차

| 번호 | 파일 | 매뉴얼 페이지 | 내용 |
|------|------|--------------|------|
| 00 | [00-개요-제공콘텐츠.md](00-개요-제공콘텐츠.md) | 5~13 | KOSIS 공유서비스 개요, 1.1 제공 콘텐츠 7종(통계목록/통계자료/대용량/통계설명/메타자료/통합검색/통계주요지표), 1.2 회원가입 |
| 01 | [01-인증키-에러메시지.md](01-인증키-에러메시지.md) | 14~16 | 1.3 인증키 발급 및 활용신청(자동 승인), 1.3.2 신청현황, 1.4 에러메시지 형식·유형(10종) |
| 02 | [02-통계목록.md](02-통계목록.md) | 17~32 | 2.1 통계목록 (statisticsList.do) JSON/SDMX(Category) 입출력, vwCd 9종, 예제 |
| 03 | [03-통계자료.md](03-통계자료.md) | 33~50 | 2.2 통계자료 (statisticsData.do / statisticsParameterData.do) JSON, 자료등록 vs 통계표선택 두 방식 |
| 04 | [04-통계자료-SDMX-DSD.md](04-통계자료-SDMX-DSD.md) | 54~69 | 2.2.3.2 SDMX(DSD) 입출력 트리 + getMeta 부가 기능 |
| 05 | [05-통계자료-SDMX-Generic-StructureSpecific.md](05-통계자료-SDMX-Generic-StructureSpecific.md) | 70~101 | 2.2.3.3 SDMX(Generic), 2.2.3.4 SDMX(StructureSpecific) |
| 06 | [06-대용량통계자료.md](06-대용량통계자료.md) | 102~109 | 2.3 대용량 통계자료 (statisticsBigData.do) DSD/Generic/StructureSpecific/XLS, 4만 셀 한도 |
| 07 | [07-통계설명.md](07-통계설명.md) | 110~136 | 2.4 통계설명 (statisticsExplData.do) JSON/XML, metaItm 28종 |
| 08 | [08-메타자료.md](08-메타자료.md) | 137~146 | 2.5 메타자료 (statisticsData.do?method=getMeta) type 9종 (TBL/ORG/PRD/ITM/CMMT/UNIT/SOURCE/WGT/NCD) |
| 09 | [09-통합검색.md](09-통합검색.md) | 147~148 | 2.6 KOSIS통합검색 (statisticsSearch.do) — **코드의 _SEARCH_URL** |
| 10 | [10-통계주요지표.md](10-통계주요지표.md) | 149~157 | 2.7 통계주요지표 (지표 Open API) 8종 endpoint |
| 11 | [11-참고-SDMX.md](11-참고-SDMX.md) | 158 | 부록 SDMX 표준 개요, DSD vs Generic vs StructureSpecific |

## 코드(`kosis_api.py`) 사용 endpoint 매핑

코드의 3개 변수와 매뉴얼 endpoint 정합:

| 코드 변수 | URL | 매뉴얼 위치 | 비고 |
|----------|-----|-----------|------|
| `_LIST_URL` | `https://kosis.kr/openapi/statisticsList.do` | 2.1 통계목록 (02 md) | 서비스뷰별 통계목록 조회 |
| `_DATA_URL` | `https://kosis.kr/openapi/Param/statisticsParameterData.do` | 2.2 통계자료 통계표선택 방식 (03 md) | 매뉴얼 예시는 statisticsData.do, 코드는 Param/ 경로의 별도 진입점 사용 |
| `_SEARCH_URL` | `https://kosis.kr/openapi/statisticsSearch.do` | 2.6 KOSIS통합검색 (09 md) | searchNm 파라미터로 통합검색 |

## 정본 에러 코드 (1.4.2)

| 코드 | 메시지 | 조치 |
|------|--------|------|
| 10 | 인증키 누락 | 인증키 확인 |
| 11 | 인증키 기간만료 | 인증키 기간 연장 |
| 20 | 필수요청변수 누락 | 필수요청변수 확인 |
| 21 | 잘못된 요청변수 | 요청변수 확인 |
| 30 | 조회결과 없음 | 조회조건 확인 |
| 31 | 조회결과 초과 | 호출건수 조정 |
| 40 | 호출가능건수 제한 | 관리자에게 문의 |
| 41 | 호출가능ROW수 제한 | 관리자에게 문의 |
| 42 | 사용자별 이용 제한 | 관리자에게 문의 |
| 50 | 서버오류 | 관리자에게 문의 |

응답 형식 (XML):
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<error>
  <err>50</err>
  <errMsg>서버오류가 발생하였습니다.</errMsg>
</error>
```

## 활용신청 정책 (1장 종합)

- KOSIS 회원당 인증키 **1개** 발급
- 활용신청 → **자동 승인** (수동 승인 단계 없음)
- 1개 인증키로 7개 모든 OpenAPI 서비스 사용 가능
- 활용신청 양식: 활용용도 / 활용기간 / 상업적활용 여부 / 사업목적(2,000자 이내) / 첨부파일(10MB 이하 — xls/doc/hwp/txt/gif/jpg/jpeg/png/bmp)

## 검수 결과

각 발췌 md는 PDF 원본과 1차 비교 검수를 거쳤다. 표 항목명, 입출력 변수, 형식(VARCHAR2 길이 등)은 매뉴얼 그대로 옮겨 적었다. 코드 예제는 매뉴얼의 핵심 호출 패턴만 발췌하고 전체 GUI 코드(JSP/PyQt5) 재현은 생략하였다.
