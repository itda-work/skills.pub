# realty-supply 요청 계약 — 근거와 판독일

이 스킬이 itda-hyve 로 보내는 요청 두 가지의 근거다. 모두 2026-09-30 에 판독·실측했다.
실측은 itda-hyve `http_request` 로 했고, 키가 등록돼 있지 않은 곳은 키 없이 구조만 확인했다.

## 1. KOSIS 통계자료 (kosis 명령)

| 항목 | 값 | 근거 |
|---|---|---|
| URL | `https://kosis.kr/openapi/Param/statisticsParameterData.do` | kosis 스킬과 같은 진입점. 키 없이 부르면 `{"err":"10","errMsg":"인증 KEY값이 누락되었습니다."}`(HTTP 200) — itda-hyve 실측 |
| 옛 URL | `…/Param/statisticsParamData.do` | **HTTP 404** HTML(「요청하신 주소의 페이지를 표시할 수 없습니다」) — itda-hyve 실측. 0.10.0 까지의 오타 |
| 입력 변수 | `method=getList` · `apiKey` · `orgId` · `tblId` · `itmId` · `objL1`(필수)~`objL8` · `prdSe` · `startPrdDe`/`endPrdDe` · `format=json` · `jsonVD=Y` | 「KOSIS 공유서비스 개발가이드 v1.0」 §2.2.3.1 통계표선택 방법(kosis 스킬 `references/kosis-매뉴얼/openApi_manual_v1.0.pdf`) |
| 오류 | `{"err":"NN","errMsg":…}` — 옛 서버는 키에 따옴표 없는 표기도 준다 | 같은 매뉴얼 §1.4.2 · kosis 스킬 `_fix_unquoted_json` |
| 총건수 | 응답에 없다 → 전량 대조 기준선 없음(오류 31 = 조회결과 초과) | 같은 매뉴얼 §2.2 출력 변수 |

### 통계표 ID — KOSIS 통합검색·통계표 화면 판독 (aside, 2026-09-30)

0.10.0 까지 쓰던 `DT_MLTM_5209`·`5140`·`5141`·`5142` 는 KOSIS 에 **없는 표**였다. 통계표 화면
(`https://kosis.kr/statHtml/statHtml.do?orgId=116&tblId=<ID>`)이 네 개 모두 「통계청::error」를 냈고,
같은 방식으로 연 대조군(101/DT_1B04005N, 116/DT_MLTM_2080)은 정상 표 이름을 냈다.

| 지표 | 표 ID | 표 이름 | 수록기간 | 분류(화면) | 지역 축(`region_axes`) |
|---|---|---|---|---|---|
| unsold | `DT_MLTM_2082` | 시·군·구별 미분양현황 | 월 2000.12~ | 구분(시도) · 시군구 → 2개 | `C1`·`C2` |
| permitted | `DT_MLTM_1946` | 부문별 주택건설 인허가실적(**월별 누계**) | 월 2007.01~ | 구분명 · 부문명 · 시도별 → 3개 | `C3` |
| started | `DT_MLTM_5386` | 주택건설 착공실적(월계) | 월 2011.01~ | 구분 · 부문명 → 2개 | **`ITM`(항목)** |
| completed | `DT_MLTM_5372` | 주택건설 준공실적(월계) | 월 2010.07~ | 구분 · 부문명 → 2개 | **`ITM`(항목)** |

- 인허가는 월계 표가 없다(연간 `DT_MLTM_626`·`666` 과 월별 **누계** 표만 있다). 그래서 값이 그 해 1월부터의 누계다 —
  스크립트가 `warnings` 로 알린다.
- **지역 축** — 착공·준공은 화면 머리가 `구  분(1) 부문명(1)` 두 분류뿐이고, 열이 `2026.05 p) 2026.06 p) 2026.07 p)` × `전국 서울 인천 … 제주`
  다(W2 리뷰가 aside 로 판독한 통계표 화면, 2026-09-30). 시도가 시점과 함께 열로 펼쳐지는 **항목(ITM)** 축이라는 뜻이다. 2026.07 열에만
  `전남광주` 가 나오는 것도 항목 목록이 시점마다 달라지는 형태다. 대조군 인허가(`1946`)는 `시도별(1)` 이 분류다. 그래서 스크립트는
  표마다 지역 축을 선언하고 `region` 을 그 축에서만 뽑는다. 나머지 분류(구분·부문명)는 `category` 로 간다. 0.11.0 초판은 분류 이름을 전부
  이어 `region` 에 실어, 착공·준공에서 `region = "민간부문 민간분양"`·`item = "서울"` 이 되고 `--region 서울` 이 조용히 0행이었다(리뷰 M3).
- **Cowork 실측 대기**: `KOSIS_API_KEY` 가 등록되지 않아 이 표들을 API 로 받아 보지 못했다. 다음을 확인해야 한다.
  - `itmId=ALL`, `objL1..objL<분류 수>=ALL` 이 오류 20/21 없이 받아지는지
  - 분류 순서(objL 슬롯·`C<n>`)가 화면 순서와 같은지
  - **지역 축 선언이 응답과 맞는지** — 착공·준공 행의 `ITM_NM` 이 시도 이름인지, 인허가의 시도가 `C3` 인지. 화면 배치로 추정한 값이다.
    선언한 축이 비어 있는 행이 있으면 스크립트가 `warnings` 로 알린다(조용히 빈 `region` 으로 두지 않는다).
  - **각 분류의 `C<n>_OBJ_NM` 값**(분류 이름 — 예 미분양 `구분`·`시군구`)과 착공·준공 `ITM_NM` 값 목록. 이 한 번의 관측이 선언을 닫는다.
    그 전까지 스크립트가 응답으로 선언을 대조한다: 지역 축으로 선언하지 않은 분류의 `C<n>_OBJ_NM` 에 `시도`·`시군구`·`지역` 이 들거나,
    지역 축이 항목인 표의 `ITM_NM` 에 시도 이름(`전국`·`서울` …)이 하나도 없으면 "지역 축 선언이 응답과 다르다" 경고(재리뷰 minor 4 —
    추정이 틀리는 가장 그럴듯한 형태는 `ITM_NM` 이 비는 것이 아니라 `호수` 같은 다른 값이 오고 시도가 분류로 오는 것이다).

## 2. 청약홈 분양정보 (subscription 명령)

| 항목 | 값 | 근거 |
|---|---|---|
| 데이터셋 | 한국부동산원_청약홈 분양정보 조회 서비스 (data.go.kr 15098547) | https://www.data.go.kr/data/15098547/openapi.do (aside 판독) |
| URL | `https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail` | 같은 페이지 Swagger — Base URL `api.odcloud.kr/api`, 명세 `https://infuser.odcloud.kr/api/stages/37000/api-docs` |
| 옛 URL | `https://apis.data.go.kr/B552555/APTInfoSearchService2/getAPTLttotPblancDetail` | HTTP 400 `returnReasonCode 12` NO_OPENAPI_SERVICE_ERROR「해당 오픈API 서비스가 없거나 폐기됨」— itda-hyve 실측(KO_DATA_API_KEY) |
| 인증 | 쿼리 `serviceKey` 또는 헤더 `Authorization` | swagger `securityDefinitions` |
| 입력 | `page` · `perPage` · `returnType`(기본 JSON) · `cond[RCRIT_PBLANC_DE::GTE]` · `cond[RCRIT_PBLANC_DE::LTE]` 외 | swagger `parameters` |
| 응답 | `{page, perPage, totalCount, currentCount, matchCount, data:[…]}` | swagger `getAPTLttotPblancDetail_api` |
| 분모 | **`matchCount`** — cond 를 걸면 `totalCount` 는 데이터셋 전체 행 수다 | odcloud 응답 규약 |
| 오류 | `{"code":-401,"msg":"인증키는 필수 항목 입니다."}` (HTTP 401) | itda-hyve 실측(키 없이) |

- **경쟁률은 이 서비스에 없다.** 필드는 주택관리번호·공고번호·주택명·공급지역·공급위치·공급규모·모집공고일·접수일·
  당첨자발표일·분양정보 URL 등이다(swagger `getAPTLttotPblancDetail_model`). 0.10.0 은 없는 `cmpttRate` 를 읽어
  늘 `"0"` 을 냈다. 경쟁률은 별도 데이터셋(청약 신청·당첨자 정보)이다.
- `RCRIT_PBLANC_DE` 의 값 형식은 명세에 없다. 다른 날짜 필드가 `YYYY-MM-DD` 라 그 형식으로 보낸다 — **Cowork 실측 대기**.
- `perPage` 상한은 명세에 없다. 기본 500. 서버가 덜 주면 "중간 쪽이 덜 찼다" 로 잡힌다.
- 실측 당시(2026-09-30, 공개판 0.10.3 프리셋) 프리셋의 `KO_DATA_API_KEY` 허용 호스트는 `apis.data.go.kr` 뿐이라, 키를 실어 보내면
  `secret_host_denied`(「KO_DATA_API_KEY 는 api.odcloud.kr 로 보낼 수 없음」)였다. itda-hyve 0.10.4 프리셋에 `api.odcloud.kr` 가 들어갔다 —
  프리셋 변경은 새 등록에만 적용되므로, 0.10.4 전에 등록한 키는 GUI 시크릿 탭에서 허용 호스트에 `api.odcloud.kr` 를 추가한다.
