# 국세법령정보시스템 내부 API 실측 계약

실측일: 2026-09-01 (aside 브라우저 XHR 훅 캡처 + 로컬 python urllib 재현 전건 성공, hyve #1616).
**비공개 내부 API 다** — 무예고 변경될 수 있으며, 이 문서가 스킬 파서의 근거 박제다.
계약이 어긋나면(typed 에러 발생) 아래 재실측 절차로 갱신한다.

## 전송 계약

```
POST https://taxlaw.nts.go.kr/action.do
Content-Type: application/x-www-form-urlencoded
body: actionId=<ID>&paramData=<URL인코딩된 JSON>
응답: {"status":"SUCCESS","message":null,"data":{"<actionId>":{...}}}
```

- 쿠키·세션·CSRF·`wnKey` 전부 불요 (bare urllib 요청 200 재현 2회). `wnKey` 는 빈 문자열로
  보내면 서버가 응답에 새 UUID 를 발급한다.
- 헤더는 사이트 XHR 원형 그대로: 브라우저 UA + `X-Requested-With: XMLHttpRequest` +
  `Accept: application/json, ...` + Referer. **임의 파라미터·커스텀 헤더 추가 금지**
  (request-profile-first / outbound-identity-leak).
- 검색엔진은 WiseNut 계열. 응답 **여러 위치**(`searchResultVO`·`collectionKnd`·
  `totalYmoymVO` 등)의 `debugMsg` 에 엔진 설정·내부 인프라 정보가 노출된다
  (스킬은 미사용 — 픽스처에서는 **전 위치를 재귀 소거**한다. 잔존 검증 기준:
  내부 IP 문자열 0건).

## robots.txt (실측 2026-09-01)

```
User-agent : *
Disallow : /is/USEISA001M.do
Disallow : /is/USEISA003M.do
```

검색 UI 화면 2개만 금지 대상. 본 스킬은 `/action.do` 만 호출하므로 Disallow 경로를 밟지 않는다.

## actionId 목록

| actionId | 용도 | paramData |
|---|---|---|
| `ASEISA001MR01` | 통합검색 | 아래 §통합검색 |
| `ASIQTB002PR01` | 세법해석례·판례/결정례 상세 (공통) | `{"dcmDVO":{"ntstDcmId":"<DOC_ID>","wnKey":""}}` |
| `ASISTA002MR03` | 법령 조문 전문 | `{"ntstBscId","ntstBrkdId","ntstPmgNo"}` |
| `ASEISA004MR01` | 상담사례 상세 | `{"reqStdId":"<REQ_STD_ID>"}` |
| `ASISTA002MR01` | 법령 목록 — 전문 조회 시 법령명·구분코드 역해석 | `{"ntstBscId","ntstSysClCd"}` (사이트 페이지 자체는 `ntstTlawClCd`·`ntstEnfrDt` 까지 4키로 부른다) |

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

`{"ntstBscId","ntstSysClCd"}` → `txaStttDVOList[]` 에 `ntstBscId`·`ntstNm`·`ntstTlawClCd`·
`ntstSysClCd`. 요청한 `ntstBscId` 와 같은 행이 1건 온다(국세기본법 101 · 종합부동산세법 110 ·
부가가치세법 시행규칙 111/03 실측).
- 조회 키 3종은 검색 결과의 `BSC_ID`:`BRKD_ID`:`PMG_NO` (스킬 id 형식)

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
| 세법해석례 | `/qt/USEQTA002P.do?ntstDcmId=` |
| 판례·결정례 | `/pd/USEPDA002P.do?ntstDcmId=` |
| 상담사례 | `/is/USEISA004P.do?reqStdId=` |
| 별표·서식 | `/st/USESTA007P.do?ntstBscId=&ntstBrkdId=&ntstAtFrmlSn=` |
| 전자도서관 | `/el/USEELA002P.do?ntstPlcnBkId=&ntstFleId=&pageNum=` |

## 재실측 절차 (계약 drift 시)

1. aside repl 로 `https://taxlaw.nts.go.kr/is/USEISA001M.do?schVcb=세법&searchType=totalSearch`
   를 연다 (이 페이지 자체는 robots Disallow — 재실측 목적의 1회 수동 열람).
2. `XMLHttpRequest.prototype.open/send` 를 훅해 `window.__cap` 에 기록한 뒤 검색 버튼을
   눌러 `actionId`·`paramData`·응답을 캡처한다 (hyve #1616 세션 기록 참조).
3. 바뀐 키를 이 문서와 `taxlaw_api.py`·픽스처에 반영한다. 픽스처는 캡처 raw 그대로 저장
   (소비 키로 위조 금지 — cross-language-contract-keys).
