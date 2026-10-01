# KOSIS 국가통계포털 — 요청 계약 요약

제안서/사업계획서에 필요한 국가 공식 통계를 수집합니다.

## API 키

1. <https://kosis.kr> 회원가입 → <https://kosis.kr/openapi/> 에서 활용신청(자동 승인) → 마이페이지에서 인증키 확인
2. itda-hyve GUI 시크릿 탭에 `KOSIS_API_KEY` 로 등록한다. 요청의 `params.apiKey` 는 `{{secret:KOSIS_API_KEY}}` 자리표시자뿐이다.

> **주의**: KOSIS 인증키는 Base64 형태로 끝에 `=` 패딩 문자가 포함됩니다.
> 복사 시 `=`가 잘리면 "유효하지않은 인증KEY" 오류가 발생합니다.

**API 제한**: 분당 1,000회 호출, 1회 최대 40,000셀(넘으면 오류 31)

## 요청 URL (2026-09-30 확인)

| 명령 | URL | method |
|---|---|---|
| search | `https://kosis.kr/openapi/statisticsSearch.do` | getList |
| data | `https://kosis.kr/openapi/Param/statisticsParameterData.do` | getList (`format=json`+`jsonVD=Y`, 또는 `format=sdmx`+`type=Generic`) |
| info·region | `https://kosis.kr/openapi/statisticsData.do` | getMeta (`type=ITM` 등) |
| list | `https://kosis.kr/openapi/statisticsList.do` | getList |
| meta | `https://kosis.kr/openapi/statisticsExplData.do` | getList |
| indicator | `https://kosis.kr/openapi/pkNumberService.do` | getList (`service=1`, `serviceDetail=pkAll`) |

- 확정 근거: 매뉴얼 v1.0 §2.2.3.1(통계표선택 방식 입력변수) + 2026-09-30 itda-hyve 실측 — `Param/statisticsParameterData.do` 는
  키 없이 `{"err":"10","errMsg":"인증 KEY값이 누락되었습니다."}`(HTTP 200)를, 오타 `Param/statisticsParamData.do` 는 HTTP 404 HTML 을 줬다.
- 호출 인자는 스크립트 `plan <명령>` 이 만든다(`SKILL.md` 1단계). 응답은 itda-hyve `save_as` 로 저장해 `<명령> --input` 으로 가공한다.

## 자주 쓰는 통계표

| 주제 | orgId | tblId | 설명 |
|------|-------|-------|------|
| 주민등록인구 | 101 | DT_1B04005N | 행정구역별/연령별 인구 |
| 장래인구추계 | 101 | DT_1BPA001 | 인구 전망 |
| GDP | 301 | DT_200Y001 | 국내총생산 |
| 사업체조사 | 101 | DT_1K52B01 | 사업체수, 종사자수 |
| 온라인쇼핑 | 101 | DT_1KE10051 | 온라인 거래액 |

> 통계표 ID는 `search` 명령으로 확인하세요.

## 분류값(objL) 선택 팁

- `ALL` — 해당 분류의 모든 값
- `11` — 특정 코드 (예: 서울특별시)
- `11+21` — 다중 선택 (`+`로 구분, 예: 서울+부산)
- `11*` — 와일드카드 (예: 서울의 모든 하위 행정구역)

## 에러 코드

| 코드 | 의미 | 조치 |
|------|------|------|
| 10 | 인증키 누락 | API 키 확인 |
| 11 | 인증키 기간만료 | kosis.kr/openapi에서 기간 연장 |
| 20 | 필수요청변수 누락 | orgId, tblId, objL1, prdSe 확인 |
| 21 | 잘못된 요청변수 | 파라미터 값 확인 |
| 30 | 조회결과 없음 | 시점/분류 조건 변경 |
| 31 | 조회결과 초과 (40,000셀) | 조회 범위 축소 |
| 40 | 호출가능건수 제한 | 잠시 후 재시도 |
| 50 | 서버오류 | 관리자 문의 |
