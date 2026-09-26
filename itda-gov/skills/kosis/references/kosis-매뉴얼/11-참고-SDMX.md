# 참고: SDMX (Statistical Data and Metadata eXchange)

출처: 통계청 발간 "KOSIS 공유서비스(OpenAPI) 개발가이드 v1.0" 부록 (페이지 158)
원본 PDF: [openApi_manual_v1.0.pdf](openApi_manual_v1.0.pdf)
추출일: 2026-04-28

## 개요

KOSIS 공유서비스 자료 제공형태 중에서 **SDMX는 XML의 일종으로서 통계에 특화된 XML**로 보면 된다.

**SDMX**는 Statistical Data and Metadata eXchange의 약어로, 통계작성기구(기관)간의 다양한 형태의 통계자료를 XML 기반으로 제공하여 교환과 공유를 효율적으로 지원한다.

### 후원 기관

SDMX 표준은 다음 국제기구들로부터 후원을 받고 있다:

- 국제결제은행(BIS)
- 유럽중앙은행
- 유럽통계처(Eurostat)
- 국제통화기금(IMF)
- 경제협력개발기구(OECD)
- UN 통계국 및 세계은행

### 표준 인증

현재 Version 2.1은 2013년 1월에 ISO(국제표준화기구) 17369로 국제표준 인증을 받았으며, 각 국의 통계청과 여러 국제기구에 이르기까지 사용범위가 점차 확대되고 있다.

표준 및 지침, 개발도구(software), 새로운 소식 등은 현재 [sdmx.org](https://sdmx.org) 웹사이트(링크)를 통해 제공되고 있다.

## SDMX 파일 구조 (Version 2.1)

| 구분 | 설명 |
|------|------|
| **DSD** (Data Structure Definition) | 통계자료에 대한 의미와 구조를 정의. 통계표를 예로 들면 통계표에 대한 설명과 통계표의 형태를 파악할 수 있는 통계표의 구성정보와 분류, 분류값, 단위, 항목에 대한 상세정보(코드 및 명칭)를 담고 있음 |
| **DATA** | DSD에서 정의한 구성정보에 주기, 시점에 따른 수치정보를 정의. SDMX version 2.1에서는 **Generic, StructureSpecific** 두 가지 포맷으로 나뉨 |

### Generic vs StructureSpecific

#### Generic

데이터를 담는 XML 구성요소가 구조를 정의하는 메시지와 **독립적인 형태**로 이루어져 있으며, 통계구성정보 및 수치정보가 각 Element(요소, 항목)로 구성되어 있다. **StructureSpecific에 비해 파일 용량이 큼**.

#### StructureSpecific

데이터를 담는 XML 구성요소는 구조를 정의하는 메시지에 **의존적인 형태**로 이루어져 있으며, 통계구성정보 및 수치정보는 하나의 Element(요소, 항목)에 **Attribute(속성)로 나열**되어 있어 **Generic에 비해 파일 용량이 작음**.

## 응답 파싱 가이드 (요약)

| 응답 형태 | 데이터 위치 | 파싱 방법 |
|----------|-----------|---------|
| JSON | 각 필드는 동등한 키-값 쌍 | `json.loads()` 후 키 직접 접근 |
| SDMX DSD | Codelist > Codelist > Code 노드 등 트리 구조 | `xml.find()`로 트리 탐색 |
| SDMX Generic | Series > Obs > ObsDimension/ObsValue 자식 Element | 자식 노드에서 텍스트 추출 |
| SDMX StructureSpecific | Series 속성에 UNIT/ITEM/FREQ + Obs 속성에 TIME_PERIOD/OBS_VALUE | `element.get(attr_name)` |
| XML (통계설명) | 각 필드를 자식 Element로 (statsNm, statsKind 등) | `element.find('statsNm').text` |

## SDMX 사용 권장 시나리오

- **소규모 데이터**: JSON 사용 (파싱 간단, 가장 빠름)
- **대용량 통계자료**: SDMX StructureSpecific 권장 (파일 크기 작음)
- **메타데이터와 함께 처리**: SDMX DSD (구조 + 데이터 한 번에 파악)
- **국제 통계 시스템 연동**: SDMX Generic (국제표준 호환성)

## 관련 도구

- 표준 사이트: https://sdmx.org
- ISO 17369:2013 — Statistical data and metadata exchange (SDMX)
