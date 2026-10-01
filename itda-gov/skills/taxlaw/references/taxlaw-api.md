# 국세법령정보시스템 내부 API 실측 계약

실측일: 2026-09-01 (aside 브라우저 XHR 훅 캡처 + 로컬 python urllib 재현 전건 성공, hyve #1616) ·
2026-10-01 (itda-hyve 경유 재현 — 검색·해석례·판례·상담·법령 2종, aside 로 상세·법령 화면의 XHR 원형 판독, itda-work/skills#46).
**비공개 내부 API 다** — 무예고 변경될 수 있으며, 이 문서가 스킬 파서의 근거 박제다.
계약이 어긋나면(typed 에러 발생) 아래 재실측 절차로 갱신한다.

## 전송 계약

```
POST https://taxlaw.nts.go.kr/action.do
Content-Type: application/x-www-form-urlencoded
body: actionId=<ID>&paramData=<URL인코딩된 JSON>
응답: {"status":"SUCCESS","message":null,"data":{"<actionId>":{...}}}
```

- 요청은 itda-hyve `http_request` 가 보낸다(itda-work/skills#45). 스크립트 `plan` 이 호출 인자를 만들고, `parse` 가 저장된 응답을 판독한다.
- **본문은 jQuery 가 만드는 글자 그대로**(2026-10-01 aside — 판례 상세 화면에서 사이트 `Req.doAction` 의 XHR `send` 인자를 캡처):
  `paramData` 는 `JSON.stringify`(공백 없음), 인코딩은 `encodeURIComponent` + 공백 `+`(jQuery.param). 골든은
  `tests/test_taxlaw_flow.py` `GOLDEN_DCM_BODY`. 0.1.x 는 파이썬 기본 `json.dumps`(`", "`·`": "` 공백)라 글자가 달랐다.
- 헤더는 사이트 JS(jQuery)가 싣는 셋 — `Content-Type: application/x-www-form-urlencoded`·`Accept: application/json, text/javascript, */*; q=0.01`·
  `X-Requested-With: XMLHttpRequest`(같은 캡처) — 과 Referer. **Referer 는 캡처가 아니라 그 XHR 을 보내는 화면 주소로 고른 값**이다
  (`send`·`setRequestHeader` 훅은 Referer 를 못 본다, 아래 표). 브라우저가 스스로 붙이는 `Origin`·`Accept-Language`·`Sec-Fetch-*`·쿠키는 싣지 않는다
  — 없이 성립함은 실측이다. User-Agent 는 싣지 않는다
  (itda-hyve 0.10.4 기본 `Mozilla/5.0`). **임의 파라미터·커스텀 헤더 추가 금지** (request-profile-first / outbound-identity-leak).
- 쿠키·세션·CSRF·`wnKey` 전부 불요(2026-09-01 bare urllib 재현 2회 · 2026-10-01 itda-hyve 쿠키 없는 POST 10회 전부 200).
  `wnKey` 는 빈 문자열로 보내면 서버가 응답에 새 UUID 를 발급한다.

| 호출 | Referer(사이트에서 그 XHR 을 보내는 화면) | 근거 |
|---|---|---|
| 통합검색 `ASEISA001MR01` | `/is/USEISA001M.do` | 쿼리 없는 주소로 두기로 했다(0.1.x 부터 같음) — 메뉴로 검색 화면을 연 뒤 화면 안에서 검색하면 브라우저도 이 주소를 싣는다 |
| 해석례·판례 상세 `ASIQTB002PR01` | `/qt/USEQTA002P.do?ntstDcmId=<id>&wnKey=` · `/pd/USEPDA002P.do?…` | common_link.js `qstnDetail`·`prtsDetail` → `Page.openPopup`(URL = `$.param({ntstDcmId, wnKey})`, 검색 결과에 `WN_KEY` 가 없어 빈 값) |
| 상담사례 `ASEISA004MR01` | `/is/USEISA004P.do?reqStdId=<id>` | common_link.js `hometaxCnslThanDetail` |
| 법령 `ASISTA002MR03`·`ASISTA002MR01` | `/st/USESTA002M.do?ntstTlawClCd=&ntstSysClCd=&ntstBscId=&ntstBrkdId=` | 사이트는 검색 결과에서 `ntstTextUqno`·`ntstEnfrDt` 를 실은 주소로 연다. 스킬 id 에는 그 두 값이 없어 **버전 고정 주소**(2026-09-01 렌더 실측)를 쓴다 — 알려진 차이 |

- 검색엔진은 WiseNut 계열. 응답 **여러 위치**(`searchResultVO`·`collectionKnd`·
  `totalYmoymVO` 등)의 `debugMsg` 에 엔진 설정·내부 인프라 정보가 노출된다
  (스킬은 미사용 — 픽스처에서는 **전 위치를 재귀 소거**한다. 잔존 검증 기준:
  내부 IP 문자열 0건).

## robots.txt (실측 2026-09-01 · 재확인 2026-10-01 — 같은 내용)

```
User-agent : *
Disallow : /is/USEISA001M.do
Disallow : /is/USEISA003M.do
```

검색 UI 화면 2개만 금지 대상. 본 스킬은 `/action.do` 만 호출하므로 Disallow 경로를 밟지 않는다
(`USEISA001M.do` 는 통합검색 XHR 의 Referer 헤더 값으로만 실린다 — 그 화면을 요청하지 않는다).

## actionId 목록

| actionId | 용도 | paramData |
|---|---|---|
| `ASEISA001MR01` | 통합검색 | 아래 §통합검색 |
| `ASIQTB002PR01` | 세법해석례·판례/결정례 상세 (공통) | `{"dcmDVO":{"ntstDcmId":"<DOC_ID>","wnKey":""}}` |
| `ASISTA002MR03` | 법령 조문 전문 | `{"ntstBscId","ntstBrkdId","ntstPmgNo"}` |
| `ASEISA004MR01` | 상담사례 상세 | `{"reqStdId":"<REQ_STD_ID>"}` |
| `ASISTA002MR01` | 법령 목록 — 전문 조회 시 법령명 역해석 | `{"ntstSysClCd","ntstTlawClCd"}` (법령 상세 화면 `Biz.doSearch` 와 같은 두 키·순서 — 2026-10-01 판독. 0.1.x 는 `{"ntstBscId","ntstSysClCd"}` 였다) |

## 통합검색 `ASEISA001MR01`

실측 paramData 원형(브라우저 검색 버튼 클릭 캡처):

```json
{"schVcb":"세법","startCount":1,
 "collection":"appendForm,statute,question,precedent,formerLibrary,intEpn,hometaxCnslThan",
 "wnKey":"","searchType":"","sortField":"SCORE/DESC",
 "ntstTlawClCdList":[],"icldVcbCtl":[],"exclVcbCtl":[],"rltnStttCtl":[],
 "schDtBase":"DCM_RGT_DTM","viewCount":"3","prtsSprcChiefJdgmYn":"",
 "prtsAttrYrCtl":[],"prtsPrgrStatCtl":[],"mainIdCtl":[],"useSynonymYn":"N"}
```

- `collection`: `statute`(법령) `question`(세법해석례) `precedent`(판례·결정례)
  `appendForm`(별표·서식) `formerLibrary`(전자도서관) `hometaxCnslThan`(상담사례)
  `intEpn`(국제해설 — 항상 0건 관측). 원하는 것만 CSV 로.
- `startCount`: 1-base. 페이지네이션 = `(page-1)*viewCount+1` (실측 검증: question 단독
  startCount=11/viewCount=10 이 page1 과 다른 결과).
- `sortField`: `SCORE/DESC`(정확도) `FRS_RGT_DTM/DESC`(등록일) `DCM_RGT_DTM/DESC`(생산일)
  — 페이지 `data-sortField` 속성 실측.
- `searchType`: `""`(통합) `"document"`(문서번호 — 실측: "부가가치세과-1196" 적중)
  `"frml"`(서식 — 미사용).
- `icldVcbCtl`/`exclVcbCtl`: 포함어/제외어 문자열 배열.

응답: `data.ASEISA001MR01.searchResultVO.collectionList[]` = `{nameKr, nameEn, totalCount,
resultCount, resultList[]}`. 하이라이트 마커는 `<!HS>…<!HE>`.

**되비침**(2026-10-01 실측 3건·2026-09-01 픽스처 동일): `data.ASEISA001MR01` 상위에 요청이 그대로 실린다 — `schVcb`·`collection`·
`startCount`(**문자열**)·`viewCount`(문자열)·`sortField`·`searchType`·`icldVcbCtl`·`exclVcbCtl`. `useSynonymYn` 만 `null` 이다.
`parse` 는 이 값들을 계획한 요청과 대조한다(다르면 `mismatch`, 없으면 `site`). 상세도 되비친다 — 해석례·판례 `dcmDVO.ntstDcmId`
(상위 `ntstDcmId` 는 `null`), 상담 상위 `reqStdId`, MR03 상위 `ntstBscId`·`ntstBrkdId`·`ntstPmgNo`, MR01 상위 `ntstSysClCd`·`ntstTlawClCd`.

**깊은 쪽 상한**: 검색엔진은 5,000번째 결과까지만 준다(추정 경계). 2026-10-01 "세법" 해석례(전체 42,410건) `viewCount 10` —
`startCount` 1,001·2,001·3,001·4,001 은 10건씩, 5,001 은 `resultCount 0`·`resultList []`(W11 리뷰 라이브: 9,901 도 0건). `totalCount` 는
그대로 42,410 이다. 4,011~5,000 은 재지 않았다. 스킬은 `page × limit > 5000` 을 받기 전에 막고, 분모 안인데 0건이면
"다시 받아도 같다" 는 `incomplete` 로 멈춘다.

### 컬렉션별 주요 결과 필드 (실측 표본 기준)

- **statute**: `NM`(법령명) `TEXT_UQNM`(제N조/장/절) `TEXT_KRN_NM`(조 제목)
  `TEXT_KRN_CNTN`(본문 발췌) `BSC_ID`·`BRKD_ID`·`PMG_NO`(상세 조회 키 3종)
  `PMG_DT`(공포) `ENFR_DT`(시행) `TLAW_CL_CD`·`SYS_CL_CD`(상세 URL 용) `STTT_SHRG_NM`(약칭)
- **question / precedent**: `TTL`(제목) `GIST_CNTN`(요지) `CNTN`(회신/내용)
  `NTST_DCM_DSCM_CNTN`(문서번호) `DOC_ID`(=ntstDcmId) `DCM_RGT_DTM_S`/`DCM_RGT_DTM`(생산일)
  `NTST_TLAW_CL_NM`(세목) `NTST_DCM_CL_NM`(질의/판례/정비 등) `NTST_DCM_DCS_CL_NM`(국승/국패 등)
- **hometaxCnslThan**: `STD_TITLE` `ANSWER_STD_CONTENT`(답변 전문) `REQ_STD_ID`
  `REQ_TP_NM`(상담유형) `REGST_DT` `VIEW_CNT`
- **appendForm**: `FRML_NM`(서식명) `FILE_CN`(서식 내용 텍스트) `BSC_ID`·`BRKD_ID`·`FRML_SN`
- **formerLibrary**: `NM`/`NTST_PLCN_BK_TTL`(책자명) `NTST_JRSD_DNO_NM`(담당부서) `PLCN_DT`

## 상세 응답

### `ASIQTB002PR01` (해석례·판례 공통)

- `dcmDVO`: `ntstDcmTtl`(제목) `ntstDcmDscmCntn`(문서번호) `ntstDcmGistCntn`(요지)
  `ntstDcmCntn`(회신/결정요지) `ntstDcmRgtDt`(생산일)
- `dcmHwpEditorDVOList[]`: `dcmFleTy=="html"` 항목의 `dcmFleByte` 가 **전문 HTML**
  (판례 판결문 85KB/텍스트 13,000자 전문 수신 확인)
- `dcmRltnStttList[]`: 관련 법령(`ntstTextNm`)
- 문서 부재 시: `status=SUCCESS` 인 채 `dcmDVO=null` → 스킬은 typed 에러로 변환

### `ASISTA002MR03` (법령 전문)

- `txaStttHsryDVOList[]` = 법 한 벌의 전 항목(국세기본법 1,551건 실측):
  `ntstTextUqnm`(제N조/장/절) `ntstTextNm`(제목) `ntstTextCntn`(본문 HTML)
  `ntstTextEnlrDscCntn`(개정 이력 — 극히 일부 행만 채워짐. 개정·시행일의
  실질 담체는 본문 안 리터럴 `<개정 …>` 표기다)
- ⚠️ `ntstNm`(법령명)·`ntstEnfrDt`·`ntstPmgNo`·`ntstTlawClCd` 는 **키만 있고 항상 null**
  (픽스처·라이브 동일 실측) — 행에 실린 식별자는 `ntstBrkdId`·`ntstSysClCd` 뿐이다.
  법령명·구분코드는 MR01 역해석(아래 URL 절)으로 얻는다.

### `ASISTA002MR01` (법령 목록 — 역해석용)

`{"ntstSysClCd","ntstTlawClCd"}` → `txaStttDVOList[]` 에 `ntstBscId`·`ntstNm`·`ntstTlawClCd`·`ntstSysClCd`.
**그 체계의 법령 목록 전체**가 온다(2026-10-01 itda-hyve 실측: `01/101` → 세법 31행·28KB, `02/ZZZ` → 4,775행·4MB — 세법구분 `ZZZ` 는 국세법 밖 일반 법령(표본: 어선원 및 어선 재해보상보험법 시행령). 세법 시행령 `02/1xx` 의 크기는 재지 않았다).
스킬은 같은 `ntstBscId` 행에서 법령명을 읽고, 모든 행의 체계구분이 요청과 같은지·그 행의 세법구분이 id 와 같은지 대조한다.
- 스킬 법령 id 는 검색 결과의 `BSC_ID`:`BRKD_ID`:`PMG_NO`:`SYS_CL_CD`:`TLAW_CL_CD` 다섯 칸(0.2.0 — 0.1.x 는 앞 세 칸).

### `ASEISA004MR01` (상담사례)

`stdTitle` `answerStdContent`(답변 전문) `reqTpNm` `regstDt` `viewCnt`

## 사람용 상세 URL (검색 결과에 병기)

### 법령 검색 결과의 링크 라우팅 — `SUB_ID` 접두 5갈래 (common_link.js `stttDetail` 이식)

| SUB_ID | 종류(LBL1_NM) | URL | 전문 조회(MR03) |
|---|---|---|---|
| `LBM001_*` | 법령 | `/st/USESTA002M.do?ntstTlawClCd=&ntstSysClCd=&ntstBscId=&ntstTextUqno=(RFRN_NTST_TEXT_UQNO 우선, 없으면 TEXT_UQNO)&ntstEnfrDt=` | 지원 (id = `BSC:BRKD:PMG_NO`) |
| `BM001_04` | 통칙 | `/st/USESTD002P.do?ntstBscId=&rgtYr=RGT_YR&ntstExrBaseSn=TEXT_SN` | 비지원 (id 비움) |
| `BM001_05` | 집행 | `/st/USESTE001P.do?ntstBscId=&rgtYr=&ntstExrBaseSn=` | 비지원 |
| `BL027` | 조세조약 | `/st/USESTC002P.do?txaAgrmBscId=&textUqnm=&textSn=` | 비지원 |
| 그 외 | 훈령·고시 | `/st/USESTA011P.do?ntarBscId=&ntarClCd=NTAR_CL_CD&ntstTextUqno=TEXT_UQNO` | 비지원 |

⚠️ **`USESTA002M` 렌더 필수 조건 (브라우저 실측 2026-09-01, 6조합)**: `ntstTlawClCd` 가 없으면
**빈 화면**이다(`ntstBscId` 단독·`ntstBscId+ntstBrkdId`·`ntstBscId+ntstEnfrDt` 전부 빈 화면).
`ntstTlawClCd+ntstSysClCd+ntstBscId` 에 **`ntstBrkdId` 를 더하면 그 버전(시행일)이 고정**된다
(`ntstEnfrDt` 와 동치). 전문 조회(`detail_law`)는 MR03 행에 구분코드·시행일이 없으므로
MR01(`{ntstBscId, ntstSysClCd}`)에서 같은 `ntstBscId` 행의 `ntstTlawClCd`·`ntstNm` 을 역해석해
URL 과 법령명을 만든다. 역해석에 실패하면 URL 을 지어내지 않고 비운다.

| 도메인 | URL |
|---|---|
| 법령(국세법령) | 위 표 — `/st/USESTA002M.do?ntstTlawClCd=&ntstSysClCd=&ntstBscId=&ntstBrkdId=` (전문 조회 산출) |
| 세법해석례 | `/qt/USEQTA002P.do?ntstDcmId=` — ⚠️ 미확인 갈래: common_link.js `qstnDetail` 은 `MAIN_ID == '001_41'` 행을 `/qt/USEQTM002P.do` 로 연다. 실측 표본(해석례 12행)에 그 행이 없었고 그 화면의 상세 액션도 모른다 — 스킬은 모두 USEQTA002P 로 둔다(0.1.x 부터 같다) |
| 판례·결정례 | `/pd/USEPDA002P.do?ntstDcmId=` |
| 상담사례 | `/is/USEISA004P.do?reqStdId=` |
| 별표·서식 | `/st/USESTA007P.do?ntstBscId=&ntstBrkdId=&ntstAtFrmlSn=` |
| 전자도서관 | `/el/USEELA002P.do?ntstPlcnBkId=&ntstFleId=&pageNum=` |

## 재실측 절차 (계약 drift 시)

1. 상세·법령 액션은 **robots 허용 화면**에서 뜬다 — aside 로 `/pd/USEPDA002P.do?ntstDcmId=<id>`·`/st/USESTA002M.do?…` 를 열고,
   `XMLHttpRequest.prototype.send`·`setRequestHeader` 를 감싼 뒤 사이트 `Req.doAction(<actionId>, <paramData>)` 를 불러
   본문·헤더를 캡처한다(2026-10-01 방식). paramData 모양은 화면 인라인 스크립트(`Biz.doSearch`·`Biz.doSearchCntn`)에서 읽는다.
2. **통합검색은 그 화면(`/is/USEISA001M.do`)이 robots Disallow 다** — 2026-09-01 초판은 그 화면을 aside 로 1회 열어 캡처했다.
   다시 떠야 하면 그 화면을 여는 것이 robots 에 어긋나므로 **사용자 결정**으로 올린다(itda-work/skills#46 W11 이후 규칙:
   불허 경로는 실측도 부르지 않는다). 허용 화면(상세 팝업)에서 `Req.doAction("ASEISA001MR01", …)` 를 부르면 본문 직렬화는
   확인할 수 있지만 paramData 키 집합은 검색 화면의 원형이 아니다 — 키 변경 확인에는 쓰지 않는다.
3. 바뀐 키를 이 문서와 `taxlaw_api.py`·픽스처에 반영한다. 픽스처는 캡처 raw 그대로 저장
   (소비 키로 위조 금지 — cross-language-contract-keys).
