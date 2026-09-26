![](media/image3.png)조달청 공공데이터 개방

OpenAPI 참고자료

[1. 서비스 명세 [3](#서비스-명세)](#서비스-명세)

[1.1 나라장터 공공데이터개방표준서비스 [3](#나라장터-공공데이터개방표준서비스)](#나라장터-공공데이터개방표준서비스)

[가. 서비스 개요 [3](#서비스-개요)](#서비스-개요)

[나. 오퍼레이션 목록 [4](#오퍼레이션-목록)](#오퍼레이션-목록)

**  **

**개정 이력**

<table style="width:97%;">
<colgroup>
<col style="width: 11%" />
<col style="width: 15%" />
<col style="width: 17%" />
<col style="width: 52%" />
</colgroup>
<tbody>
<tr>
<td>버 전</td>
<td>변경일</td>
<td>변경 구분</td>
<td>변경사유</td>
</tr>
<tr>
<td style="text-align: left;">1.0</td>
<td style="text-align: left;">2025</td>
<td style="text-align: left;">최초 개정</td>
<td style="text-align: left;">최초 개정</td>
</tr>
<tr>
<td style="text-align: left;">1.1</td>
<td style="text-align: left;">2025.08</td>
<td style="text-align: left;">항목추가</td>
<td style="text-align: left;"><blockquote>
<p>데이터셋 개방표준에 따른 계약정보</p>
</blockquote>
<ul>
<li><p>요청메시지 : [기관구분코드:insttDivCd , 기관코드:insttCd] 항목 추가</p></li>
</ul></td>
</tr>
<tr>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
</tr>
<tr>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
</tr>
<tr>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
</tr>
<tr>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
<td style="text-align: left;"></td>
</tr>
</tbody>
</table>

# 1. 서비스 명세

## 1.1 나라장터 공공데이터개방표준서비스

### 서비스 개요

<table style="width:100%;">
<colgroup>
<col style="width: 20%" />
<col style="width: 8%" />
<col style="width: 9%" />
<col style="width: 19%" />
<col style="width: 0%" />
<col style="width: 9%" />
<col style="width: 3%" />
<col style="width: 8%" />
<col style="width: 20%" />
</colgroup>
<tbody>
<tr>
<td rowspan="4">서비스 정보</td>
<td colspan="2">서비스 ID</td>
<td colspan="6">PubDataOpnStdService</td>
</tr>
<tr>
<td colspan="2">서비스명(국문)</td>
<td colspan="6">나라장터 공공데이터개방표준서비스</td>
</tr>
<tr>
<td colspan="2">서비스명(영문)</td>
<td colspan="6">PubDataOpnStdService</td>
</tr>
<tr>
<td colspan="2">서비스 설명</td>
<td colspan="6">나라장터 입찰, 낙찰, 계약정보 데이터를 행안부 고시 공공데이터 개방표준에 따라 제공하는 공공데이터개방표준서비스</td>
</tr>
<tr>
<td rowspan="3">서비스 보안</td>
<td colspan="2">서비스 인증/권한</td>
<td colspan="5"><p>[O] 서비스 Key[ ] 인증서 (GPKI)</p>
<p>[] Basic (ID/PW) [ ] 없음</p></td>
<td rowspan="2">[ ]WS-Security</td>
</tr>
<tr>
<td colspan="2">메시지 레벨 암호화</td>
<td colspan="5">[ ] 전자서명 [ ] 암호화 [O] 없음</td>
</tr>
<tr>
<td colspan="2">전송 레벨 암호화</td>
<td colspan="6">[ ] SSL [ O] 없음</td>
</tr>
<tr>
<td rowspan="2">적용 기술 수준</td>
<td colspan="2">인터페이스 표준</td>
<td colspan="6"><p>[ ] SOAP 1.2</p>
<p>(RPC-Encoded, Document Literal, Document Literal Wrapped)</p>
<p>[ O ] REST (GET)</p>
<p>[ ] RSS 1.0 [ ] RSS 2.0 [ ] Atom 1.0 [ ] 기타</p></td>
</tr>
<tr>
<td colspan="2">교환 데이터 표준</td>
<td colspan="6">[ O ] XML [ O ] JSON [ ] MIME [ ] MTOM</td>
</tr>
<tr>
<td rowspan="2">서비스 URL</td>
<td colspan="2">개발환경</td>
<td colspan="6">http://apis.data.go.kr/1230000/ao/PubDataOpnStdService</td>
</tr>
<tr>
<td colspan="2">운영환경</td>
<td colspan="6">http://apis.data.go.kr/1230000/ao/PubDataOpnStdService</td>
</tr>
<tr>
<td rowspan="2">서비스 WADL</td>
<td colspan="2">개발환경</td>
<td colspan="6">N/A</td>
</tr>
<tr>
<td colspan="2">운영환경</td>
<td colspan="6">N/A</td>
</tr>
<tr>
<td rowspan="3">서비스 배포 정보</td>
<td colspan="2">서비스 버전</td>
<td colspan="6">1.0</td>
</tr>
<tr>
<td colspan="2">서비스 시작일</td>
<td colspan="2">2025-01-06</td>
<td colspan="2">배포 일자</td>
<td colspan="2">2025-01-06</td>
</tr>
<tr>
<td colspan="2">서비스 이력</td>
<td colspan="6">N/A</td>
</tr>
<tr>
<td>메시지 교환 유형</td>
<td colspan="8"><p>[O] Request-Response [ ] Publish-Subscribe</p>
<p>[ ] Fire-and-Forgot [ ] Notification</p></td>
</tr>
<tr>
<td>메시지 로깅 수준</td>
<td>성공</td>
<td colspan="2">[O] Header [ ] Body</td>
<td colspan="2">실패</td>
<td colspan="3">[O] Header [O] Body</td>
</tr>
<tr>
<td>사용 제약 사항 (비고)</td>
<td colspan="8">N/A</td>
</tr>
<tr>
<td>서비스 제공자</td>
<td colspan="8" style="text-align: left;">김재혁 / 조달청 전자조달기획과 / 042-724-7677 / dobin@korea.kr</td>
</tr>
<tr>
<td>데이터 갱신주기</td>
<td colspan="8">수시</td>
</tr>
</tbody>
</table>

### 오퍼레이션 목록

<table>
<colgroup>
<col style="width: 12%" />
<col style="width: 16%" />
<col style="width: 28%" />
<col style="width: 25%" />
<col style="width: 16%" />
</colgroup>
<tbody>
<tr>
<td>일련번호</td>
<td>서비스명(국문)</td>
<td>오퍼레이션명(영문)</td>
<td>오퍼레이션명(국문)</td>
<td>메시지명(영문)</td>
</tr>
<tr>
<td>1</td>
<td rowspan="3">나라장터 공공데이터개방표준서비스</td>
<td>getDataSetOpnStdBidPblancInfo</td>
<td>데이터셋 개방표준에 따른 입찰공고정보</td>
<td>N/A</td>
</tr>
<tr>
<td>2</td>
<td>getDataSetOpnStdScsbidInfo</td>
<td>데이터셋 개방표준에 따른 낙찰정보</td>
<td>N/A</td>
</tr>
<tr>
<td>3</td>
<td>getDataSetOpnStdCntrctInfo</td>
<td>데이터셋 개방표준에 따른 계약정보</td>
<td>N/A</td>
</tr>
</tbody>
</table>

#### \[데이터셋 개방표준에 따른 입찰공고정보\] 오퍼레이션 명세

<table>
<colgroup>
<col style="width: 4%" />
<col style="width: 21%" />
<col style="width: 17%" />
<col style="width: 21%" />
<col style="width: 2%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr>
<td rowspan="6">오퍼레이션 정보</td>
<td>오퍼레이션 번호</td>
<td>1</td>
<td>오퍼레이션명(국문)</td>
<td colspan="2">데이터셋 개방표준에 따른 입찰공고정보</td>
</tr>
<tr>
<td>오퍼레이션 유형</td>
<td>조회(목록)</td>
<td>오퍼레이션명(영문)</td>
<td colspan="2">getDataSetOpnStdBidPblancInfo</td>
</tr>
<tr>
<td>오퍼레이션 설명</td>
<td colspan="4">검색조건을 입찰공고일시로 하여 입찰공고번호, 입찰공고차수, 나라장터공고여부, 입찰공고명, 입찰공고상태명, 입찰공고일자, 입찰공고시각, 업무구분명, 국제입찰여부 등 나라장터에 등록된 입찰공고정보 조회</td>
</tr>
<tr>
<td>Call Back URL</td>
<td colspan="4" style="text-align: left;">N/A</td>
</tr>
<tr>
<td>최대 메시지 사이즈</td>
<td colspan="4">[ 4000bytes]</td>
</tr>
<tr>
<td>평균 응답 시간</td>
<td>[ 500 ms]</td>
<td colspan="2">초당 최대 트랜잭션</td>
<td>[ 30 tps]</td>
</tr>
</tbody>
</table>

##### 요청 메시지 명세

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 13%" />
<col style="width: 12%" />
<col style="width: 12%" />
<col style="width: 21%" />
</colgroup>
<tbody>
<tr>
<td>항목명(영문)</td>
<td>항목명(국문)</td>
<td>항목크기</td>
<td>항목구분</td>
<td>샘플데이터</td>
<td>항목설명</td>
</tr>
<tr>
<td>numOfRows</td>
<td>한 페이지 결과 수</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">한 페이지 결과 수</td>
</tr>
<tr>
<td>pageNo</td>
<td>페이지 번호</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">페이지 번호</td>
</tr>
<tr>
<td>ServiceKey</td>
<td>서비스키</td>
<td style="text-align: center;">400</td>
<td style="text-align: center;">1</td>
<td style="text-align: left;">공공데이터포털에서 받은 인증키</td>
<td style="text-align: left;">공공데이터포털에서 받은 인증키</td>
</tr>
<tr>
<td>type</td>
<td>타입</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0</td>
<td style="text-align: left;">json</td>
<td style="text-align: left;">오픈API 리턴 타입을 JSON으로 받고 싶을 경우 'json' 으로 지정함</td>
</tr>
<tr>
<td>bidNtceBgnDt</td>
<td>입찰공고시작일시</td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">1</td>
<td style="text-align: left;">202507010000</td>
<td style="text-align: left;"><p>검색하고자하는 입찰공고일시범위 시작 'YYYYMMDDHHMM'</p>
<p>(입찰공고일시 범위는 1개월 로 제한)</p></td>
</tr>
<tr>
<td>bidNtceEndDt</td>
<td>입찰공고종료일시</td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">1</td>
<td style="text-align: left;">202507012359</td>
<td style="text-align: left;"><p>검색하고자하는 입찰공고일시범위 종료 'YYYYMMDDHHMM'</p>
<p>(입찰공고일시 범위는 1개월 로 제한)</p></td>
</tr>
</tbody>
</table>

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 응답 메시지 명세

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 18%" />
<col style="width: 14%" />
<col style="width: 13%" />
<col style="width: 13%" />
<col style="width: 19%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>항목명(영문)</strong></th>
<th style="text-align: center;"><strong>항목명(국문)</strong></th>
<th style="text-align: center;"><strong>항목크기</strong></th>
<th style="text-align: center;"><strong>항목구분</strong></th>
<th style="text-align: center;"><strong>샘플데이터</strong></th>
<th style="text-align: center;"><strong>항목설명</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>resultCode</td>
<td>결과코드</td>
<td style="text-align: left;">2</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">00</td>
<td style="text-align: left;">결과코드</td>
</tr>
<tr>
<td>resultMsg</td>
<td>결과메세지</td>
<td style="text-align: left;">50</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">정상</td>
<td style="text-align: left;">결과메세지</td>
</tr>
<tr>
<td>numOfRows</td>
<td>한 페이지 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">한 페이지 결과 수</td>
</tr>
<tr>
<td>pageNo</td>
<td>페이지 번호</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">페이지 번호</td>
</tr>
<tr>
<td>totalCount</td>
<td>전체 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">전체 결과 수</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceNo</td>
<td style="text-align: left;">입찰공고번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">R25BK00933743</td>
<td style="text-align: left;"><p>입찰공고를 관리하기 위한 번호이며 조달청나라장터 공고건의 형식은 년도(4)+월(2)+순번(5)이며 나라장터 외 (자체)전자조달시스템(이하 이 표에서 “기타 전자조달시스템”이라 함) 보유기관은 각 기관별 형식 별도 사용</p>
<p>*차세대나라장터 번호체계 개편 :R+년도(2)+BK+순번(8) 총 13자리 구성 적용</p>
<p>*2025년 공고건부터 적용</p></td>
</tr>
<tr>
<td style="text-align: left;">bidNtceOrd</td>
<td style="text-align: left;">입찰공고차수</td>
<td style="text-align: left;">2</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">000</td>
<td style="text-align: left;">입찰공고차수는 해당 입찰공고에 대한 정정(변경)공고 및 재공고 등이 발생되었을 경우 증가되는 수</td>
</tr>
<tr>
<td style="text-align: left;">refNtceNo</td>
<td style="text-align: left;">참조공고번호</td>
<td style="text-align: left;">40</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">R25BK00933743</td>
<td style="text-align: left;">조달청 입찰공고의 경우 참조공고번호는 기타 전자조달시스템에서 관리하는 공고번호를 의미하며 기타 전자조달시스템의 경우 참조공고번호는 나라장터(G2B) 입찰공고번호를 의미함</td>
</tr>
<tr>
<td style="text-align: left;">refNtceOrd</td>
<td style="text-align: left;">참조공고차수</td>
<td style="text-align: left;">3</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">000</td>
<td style="text-align: left;">참조공고번호에 대한 공고 차수</td>
</tr>
<tr>
<td style="text-align: left;">ppsNtceYn</td>
<td style="text-align: left;">나라장터공고여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">조달청에서 관리하는 나라장터 (https://www.g2b.go.kr)를 통해서도 입찰공고를 하는지의 여부</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceNm</td>
<td style="text-align: left;">입찰공고명</td>
<td style="text-align: left;">1000</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2025년 경기미 가공저장시설 스마트화 지원사업 현미 색채선별기 구매(긴급)</td>
<td style="text-align: left;">공사명 또는 사업명이라고도 하며 입찰공고 내용을 요약한 이름</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceSttusNm</td>
<td style="text-align: left;">입찰공고상태명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">일반공고</td>
<td style="text-align: left;">해당 공고의 상태가 일반 또는 긴급공고, 정정(또는 연기)공고, 재공고입찰, 취소공고를 구분하기 위한 명</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceDate</td>
<td style="text-align: left;">입찰공고일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2025-07-01</td>
<td style="text-align: left;">입찰공고서를 공고한 일자</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceBgn</td>
<td style="text-align: left;">입찰공고시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">07:49</td>
<td style="text-align: left;">입찰공고서를 공고한 시각</td>
</tr>
<tr>
<td style="text-align: left;">bsnsDivNm</td>
<td style="text-align: left;">업무구분명</td>
<td style="text-align: left;">20</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">물품</td>
<td style="text-align: left;">입찰업무를 구분하는 명으로 물품, 용역, 공사, 외자로 구분함</td>
</tr>
<tr>
<td style="text-align: left;">intrntnlBidYn</td>
<td style="text-align: left;">국제입찰여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">N</td>
<td style="text-align: left;">국제입찰대상인지의 여부를 나타내며 국제입찰 대상은 내외국인 또는 외국인을 대상으로 하여 물품, 공사 및 용역을 조달하기 위하여 행하는 입찰을 말하며 수의계약을 포함한다. 국가계약법 제4조(지방계약법 제5조)에 의해 추정가격이 고시금액(국제입찰 적용 대상 기준금액으로 기획재정부장관 및 행정안전부장관이 매 2년마다 고시한 금액을 말하며 WTO 또는 양자간(FTA) 정부조달협정에 따르면 국제입찰 대상 기준 금액이 SDR(Special Drawing Rights:특별인출권) 통화단위로 되어 있어 주무부 장관이 이를 2년마다 원화로 환산하여 고시) 이상일 경우 국제입찰대상이 됨</td>
</tr>
<tr>
<td style="text-align: left;">cmmnCntrctYn</td>
<td style="text-align: left;">공동계약여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">공동계약의 경우 공사/제조 기타의 계약에 있어서 필요하다고 인정할 때 계약 상대자를 2인 이상과 체결하는 계약이며 단독계약은 계약상대자를 1인으로 하는 통상적인 계약을 의미함.</td>
</tr>
<tr>
<td style="text-align: left;">cmmnReciptMethdNm</td>
<td style="text-align: left;">공동수급방식명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">공동이행</td>
<td style="text-align: left;">공동수급이라 함은 구성원을 2인 이상으로 하여 수급인이 해당계약을 공동으로 수행하기 위하여 잠정적으로 결성한 실체를 의미하며 공동수급체가도급을 받아 이행하는 방식을 구분하는 명임</td>
</tr>
<tr>
<td style="text-align: left;">elctrnBidYn</td>
<td style="text-align: left;">전자입찰여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">입찰의 방식이 전자입찰방식인지 일반입찰(직접입찰 및 우편)방식인지의 여부</td>
</tr>
<tr>
<td style="text-align: left;">cntrctCnclsSttusNm</td>
<td style="text-align: left;">계약체결형태명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">총액계약</td>
<td style="text-align: left;">계약체결형태를 구분하는 명<br />
*총액계약은 계약목적물 전체에 대하여 단가가 아닌 총액으로 체결하는 계약형태<br />
*단가계약은 수요 빈도가 많은 품목에 대하여 단가에 의해 예정수량을 명시하고 체결하는 계약형태,<br />
*제3자단가계약은 각 수요기관에서 공통적으로 필요로 하는 수요물자를 계약시 미리 단가만을 정하여 계약을 체결하고 각 수요기관에서 직접 납품요구하여 구매하는 계약형태</td>
</tr>
<tr>
<td style="text-align: left;">cntrctCnclsMthdNm</td>
<td style="text-align: left;">계약체결방법명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">제한경쟁</td>
<td style="text-align: left;">계약체결의 방법을 구분하는 명<br />
*일반경쟁계약은 계약 대상 물품의 규격 및 시방서와 계약조건 등을 널리 공고하여 일정한 자격을 가진 불특정 다수인의 입찰희망자를 모두 경쟁 입찰하는 계약방법<br />
*제한경쟁계약은 일반·지명경쟁계약제도의 단점을 보완하기 위해 실적제한, 기술보유제한, 특정물품제한, 지역제한 등을 두는 계약방법<br />
*지명경쟁계약은 계약상대자의 신용과 실적 등에 있어 적당하다고 인정하는 특정 다수의 경쟁 참가자를 지명하여 계약 상대방을 결정하는 계약방법<br />
*수의계약은 계약상대자를 결정함에 있어 경쟁방법에 의하지 않고 특정인을 선정하여 계약하는 계약방법</td>
</tr>
<tr>
<td style="text-align: left;">bidwinrDcsnMthdNm</td>
<td style="text-align: left;">낙찰자결정방법명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">최저가 낙찰제</td>
<td style="text-align: left;">해당 공고건에 대해 낙찰자를 결정하는 방법</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttNm</td>
<td style="text-align: left;">공고기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">신김포농업협동조합 양촌미곡사업소</td>
<td style="text-align: left;">수요기관의 의뢰를 받아 공고하는 기관의 명</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttCd</td>
<td style="text-align: left;">공고기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Z013176</td>
<td style="text-align: left;">공고를 하는 기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttOfclDeptNm</td>
<td style="text-align: left;">공고기관담당자부서명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">경영관리과</td>
<td style="text-align: left;">공고기관의 공고를 담당하는 담당부서의 명</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttOfclNm</td>
<td style="text-align: left;">공고기관담당자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">홍길동</td>
<td style="text-align: left;">공고기관의 공고를 담당하는 담당자의 명</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttOfclTel</td>
<td style="text-align: left;">공고기관담당자전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">070-000-0000</td>
<td style="text-align: left;">공고기관의 공고를 담당하는 담당자의 전화번호</td>
</tr>
<tr>
<td style="text-align: left;">ntceInsttOfclEmailAdrs</td>
<td style="text-align: left;">공고기관담당자이메일주소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">abcd@korea.kr</td>
<td style="text-align: left;">공고기관의 공고를 담당하는 담당자의 이메일주소</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttNm</td>
<td style="text-align: left;">수요기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">재단법인 대전테크노파크</td>
<td style="text-align: left;">중앙조달인 경우 조달사업에 관한 법률 제2조(정의)에 따라 수요물자의 구매 공급 또는 시설공사 계약의 체결을 조달청장에게 요청할 수 있도록 조달청장이 인정하여 등록한 기관 또는 기타 전자조달시스템을 이용하는 기관인 경우 계약을 의뢰한 기관의 명으로 공고기관과 수요기관이 동일할 수 있음</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttCd</td>
<td style="text-align: left;">수요기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">B552732</td>
<td style="text-align: left;">실제 수요기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttOfclDeptNm</td>
<td style="text-align: left;">수요기관담당자부서명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">구매과</td>
<td style="text-align: left;">수요기관의 공고를 담당하는 담당부서의 명</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttOfclNm</td>
<td style="text-align: left;">수요기관담당자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">홍길동</td>
<td style="text-align: left;">수요기관의 공고를 담당하는 담당자의 명</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttOfclTel</td>
<td style="text-align: left;">수요기관담당자전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">042-000-0000</td>
<td style="text-align: left;">수요기관의 공고를 담당하는 담당자의 전화번호</td>
</tr>
<tr>
<td style="text-align: left;">dmndInsttOfclEmailAdrs</td>
<td style="text-align: left;">수요기관담당자이메일주소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">abcd@korea.kr</td>
<td style="text-align: left;">수요기관의 공고를 담당하는 담당자의 이메일주소</td>
</tr>
<tr>
<td style="text-align: left;">presnatnOprtnYn</td>
<td style="text-align: left;">설명회실시여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">해당 공고에 대한 현장/입찰/과업 설명회를 실시하는지의 여부</td>
</tr>
<tr>
<td style="text-align: left;">presnatnOprtnDate</td>
<td style="text-align: left;">설명회실시일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2027-09-01</td>
<td style="text-align: left;">해당 공고에 대한 현장/입찰/과업 설명회를 실시하는 일자</td>
</tr>
<tr>
<td style="text-align: left;">presnatnOprtnTm</td>
<td style="text-align: left;">설명회실시시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">13:00</td>
<td style="text-align: left;">해당 공고에 대한 현장/입찰/과업 설명회를 실시하는 시각</td>
</tr>
<tr>
<td style="text-align: left;">presnatnOprtnPlce</td>
<td style="text-align: left;">설명회실시장소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">대전지방조달청 1층</td>
<td style="text-align: left;">해당 공고에 대한 설명회를 실시하는 경우 현장/입찰/과업 설명회를 실시하는 장소</td>
</tr>
<tr>
<td style="text-align: left;">bidPrtcptQlfctRgstClseDate</td>
<td style="text-align: left;">입찰참가자격등록마감일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2025-07-07</td>
<td style="text-align: left;">입찰참가등록이란 입찰사무를 효과적으로 집행하기 위하여 사전에 입찰참가자격등록을 해두었다가 필요 시 입찰에 참여하는 제도로 해당 공고에 대한 입찰참가자격의 등록이 완료되어야 하는 시점(일자)을 의미함</td>
</tr>
<tr>
<td style="text-align: left;">bidPrtcptQlfctRgstClseTm</td>
<td style="text-align: left;">입찰참가자격등록마감시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">14:00</td>
<td style="text-align: left;">입찰참가등록이란 입찰사무를 효과적으로 집행하기 위하여 사전에 입찰참가자격등록을 해두었다가 필요 시 입찰에 참여하는 제도로 해당 공고에 대한 입찰참가자격의 등록이 완료되어야 하는 시점(시각)을 의미함</td>
</tr>
<tr>
<td style="text-align: left;">cmmnReciptAgrmntClseDate</td>
<td style="text-align: left;">공동수급협정마감일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2016-09-27</td>
<td style="text-align: left;">공동계약이 허용된 공고에 대해 공동수급체를 구성하여 입찰에 참여하고자 할 경우 구성원이 일정 분담내용에 따라 나누어 공동으로 이행하는 약속을 한 공동수급협정서를 작성하여야 하며 이때 공동수급협정서의 등록(작성) 마감 시점(일자)을 의미함</td>
</tr>
<tr>
<td style="text-align: left;">cmmnReciptAgrmntClseTm</td>
<td style="text-align: left;">공동수급협정마감시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">18:00</td>
<td style="text-align: left;">공동계약이 허용된 공고에 대해 공동수급체를 구성하여 입찰에 참여하고자 할 경우 구성원이 일정 분담내용에 따라 나누어 공동으로 이행하는 약속을 한 공동수급협정서를 작성하여야 하며 이때 공동수급협정서의 등록(작성) 마감 시점(시각)을 의미함</td>
</tr>
<tr>
<td style="text-align: left;">bidBeginDate</td>
<td style="text-align: left;">입찰개시일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2025-07-01</td>
<td style="text-align: left;">입찰서의 제출을 개시하는 일자</td>
</tr>
<tr>
<td style="text-align: left;">bidBeginTm</td>
<td style="text-align: left;">입찰개시시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">10:00</td>
<td style="text-align: left;">입찰서의 제출을 개시하는 시각</td>
</tr>
<tr>
<td style="text-align: left;">bidClseDate</td>
<td style="text-align: left;">입찰마감일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2025-07-08</td>
<td style="text-align: left;">입찰서의 제출을 마감하는 일자</td>
</tr>
<tr>
<td style="text-align: left;">bidClseTm</td>
<td style="text-align: left;">입찰마감시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">15:00</td>
<td style="text-align: left;">입찰서의 제출을 마감하는 시각</td>
</tr>
<tr>
<td style="text-align: left;">opengDate</td>
<td style="text-align: left;">개찰일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2025-07-08</td>
<td style="text-align: left;">조달업체가 제출한 입찰서를 개찰하는 일자</td>
</tr>
<tr>
<td style="text-align: left;">opengTm</td>
<td style="text-align: left;">개찰시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">16:00</td>
<td style="text-align: left;">조달업체가 제출한 입찰서를 개찰하는 시각</td>
</tr>
<tr>
<td style="text-align: left;">opengPlce</td>
<td style="text-align: left;">개찰장소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">국가종합전자조달시스템(나라장터)</td>
<td style="text-align: left;">조달업체가 제출한 입찰서를 개찰하는 장소</td>
</tr>
<tr>
<td style="text-align: left;">asignBdgtAmt</td>
<td style="text-align: left;">배정예산금액(설계금액)</td>
<td style="text-align: left;">22</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">97240000</td>
<td style="text-align: left;">사업목적물을 달성하기 위하여 배정된 예산액 또는 설계금액(원화,원)</td>
</tr>
<tr>
<td style="text-align: left;">presmptPrce</td>
<td style="text-align: left;">추정가격</td>
<td style="text-align: left;">25</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">88400000</td>
<td style="text-align: left;">물품/공사/용역 등의 조달 계약을 체결함에 있어 국제입찰 대상여부를 판단하는 기준 등으로 삼기 위하여 예정가격이 결정되기 전에 국가계약법 시행령 등에서 정한 ‘추정가격의 산정’ 규정에 의하여 산정된 가격으로 부가가치세 및 관급자재비를 제외한 금액(원화,원)</td>
</tr>
<tr>
<td style="text-align: left;">rsrvtnPrceDcsnMthdNm</td>
<td style="text-align: left;">예정가격결정방법명</td>
<td style="text-align: left;">20</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">단일예가</td>
<td style="text-align: left;">예정가격의 결정을 위해 복수예정가격방식으로 산정하는지 단일 예정가격으로 산정하는지를 구분하는 명</td>
</tr>
<tr>
<td style="text-align: left;">rgnLmtYn</td>
<td style="text-align: left;">지역제한여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">해당 공고 입찰 시 지역제한을 두는지의 여부</td>
</tr>
<tr>
<td style="text-align: left;">prtcptPsblRgnNm</td>
<td style="text-align: left;">참가가능지역명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">대전광역시</td>
<td style="text-align: left;">지역제한이 Y일 경우 참여가능한 지역의 명칭을 콤마(,)로 나열함</td>
</tr>
<tr>
<td style="text-align: left;">indstrytyLmtYn</td>
<td style="text-align: left;">업종제한여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">해당 공고 입찰 시 업종(면허)제한을 두는지의 여부</td>
</tr>
<tr>
<td style="text-align: left;">bidprcPsblIndstrytyNm</td>
<td style="text-align: left;">투찰가능업종명</td>
<td style="text-align: left;">4000</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">전기공사업</td>
<td style="text-align: left;">업종제한이 Y일 경우 제한되는 업종의 명칭을 콤마(,)로 나열함</td>
</tr>
<tr>
<td style="text-align: left;">bidNtceUrl</td>
<td style="text-align: left;">입찰공고URL</td>
<td style="text-align: left;">500</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R25BK00933743&amp;bidPbancOrd=000</td>
<td style="text-align: left;">해당 입찰공고를 인터넷상에서 확인할 수 있는 URL주소</td>
</tr>
<tr>
<td style="text-align: left;">dataBssDate</td>
<td style="text-align: left;">데이터기준일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2016-09-30</td>
<td style="text-align: left;">데이터 작성 기준일자</td>
</tr>
</tbody>
</table>

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 요청 / 응답 메시지 예제

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td>REST(URI)</td>
</tr>
<tr>
<td style="text-align: left;">http://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo?numOfRows=10&amp;pageNo=1&amp;bidNtceBgnDt=202507010000&amp;bidNtceEndDt=202507010000&amp;ServiceKey=인증키</td>
</tr>
<tr>
<td>응답 메시지</td>
</tr>
<tr>
<td><p>&lt;response&gt;</p>
<p>&lt;header&gt;</p>
<p>&lt;resultCode&gt;00&lt;/resultCode&gt;</p>
<p>&lt;resultMsg&gt;정상&lt;/resultMsg&gt;</p>
<p>&lt;/header&gt;</p>
<p>&lt;body&gt;</p>
<p>&lt;items&gt;</p>
<p>&lt;item&gt;</p>
<p>&lt;bidNtceNo&gt;R25BK00933743&lt;/bidNtceNo&gt;</p>
<p>&lt;bidNtceOrd&gt;000&lt;/bidNtceOrd&gt;</p>
<p>&lt;refNtceNo&gt;R25BK00933743&lt;/refNtceNo&gt;</p>
<p>&lt;refNtceOrd&gt;000&lt;/refNtceOrd&gt;</p>
<p>&lt;ppsNtceYn&gt;Y&lt;/ppsNtceYn&gt;</p>
<p>&lt;bidNtceNm&gt;2025년 경기미 가공저장시설 스마트화 지원사업 현미 색채선별기 구매(긴급)&lt;/bidNtceNm&gt;</p>
<p>&lt;bidNtceSttusNm&gt;일반공고&lt;/bidNtceSttusNm&gt;</p>
<p>&lt;bidNtceDate&gt;2025-07-01&lt;/bidNtceDate&gt;</p>
<p>&lt;bidNtceBgn&gt;07:49&lt;/bidNtceBgn&gt;</p>
<p>&lt;bsnsDivNm&gt;물품&lt;/bsnsDivNm&gt;</p>
<p>&lt;intrntnlBidYn&gt;N&lt;/intrntnlBidYn&gt;</p>
<p>&lt;cmmnCntrctYn&gt;Y&lt;/cmmnCntrctYn&gt;</p>
<p>&lt;cmmnReciptMethdNm&gt;&lt;/cmmnReciptMethdNm&gt;</p>
<p>&lt;elctrnBidYn&gt;Y&lt;/elctrnBidYn&gt;</p>
<p>&lt;cntrctCnclsSttusNm&gt;총액계약&lt;/cntrctCnclsSttusNm&gt;</p>
<p>&lt;cntrctCnclsMthdNm&gt;제한경쟁&lt;/cntrctCnclsMthdNm&gt;</p>
<p>&lt;bidwinrDcsnMthdNm&gt;적격심사제&lt;/bidwinrDcsnMthdNm&gt;</p>
<p>&lt;ntceInsttNm&gt;신김포농업협동조합 양촌미곡사업소&lt;/ntceInsttNm&gt;</p>
<p>&lt;ntceInsttCd&gt;Z013176&lt;/ntceInsttCd&gt;</p>
<p>&lt;ntceInsttOfclDeptNm&gt;&lt;/ntceInsttOfclDeptNm&gt;</p>
<p>&lt;ntceInsttOfclNm&gt;박형준&lt;/ntceInsttOfclNm&gt;</p>
<p>&lt;ntceInsttOfclTel&gt;***-***-*****&lt;/ntceInsttOfclTel&gt;</p>
<p>&lt;ntceInsttOfclEmailAdrs&gt;nh241040-1@nonghyup.com&lt;/ntceInsttOfclEmailAdrs&gt;</p>
<p>&lt;dmndInsttNm&gt;신김포농업협동조합 양촌미곡사업소&lt;/dmndInsttNm&gt;</p>
<p>&lt;dmndInsttCd&gt;Z013176&lt;/dmndInsttCd&gt;</p>
<p>&lt;dmndInsttOfclDeptNm&gt;&lt;/dmndInsttOfclDeptNm&gt;</p>
<p>&lt;dmndInsttOfclNm&gt;박형준&lt;/dmndInsttOfclNm&gt;</p>
<p>&lt;dmndInsttOfclTel&gt;***********&lt;/dmndInsttOfclTel&gt;</p>
<p>&lt;dmndInsttOfclEmailAdrs&gt;&lt;/dmndInsttOfclEmailAdrs&gt;</p>
<p>&lt;presnatnOprtnYn&gt;&lt;/presnatnOprtnYn&gt;</p>
<p>&lt;presnatnOprtnDate&gt;&lt;/presnatnOprtnDate&gt;</p>
<p>&lt;presnatnOprtnTm&gt;&lt;/presnatnOprtnTm&gt;</p>
<p>&lt;presnatnOprtnPlce&gt;&lt;/presnatnOprtnPlce&gt;</p>
<p>&lt;bidPrtcptQlfctRgstClseDate&gt;2025-07-07&lt;/bidPrtcptQlfctRgstClseDate&gt;</p>
<p>&lt;bidPrtcptQlfctRgstClseTm&gt;14:00&lt;/bidPrtcptQlfctRgstClseTm&gt;</p>
<p>&lt;cmmnReciptAgrmntClseDate&gt;&lt;/cmmnReciptAgrmntClseDate&gt;</p>
<p>&lt;cmmnReciptAgrmntClseTm&gt;&lt;/cmmnReciptAgrmntClseTm&gt;</p>
<p>&lt;bidBeginDate&gt;2025-07-01&lt;/bidBeginDate&gt;</p>
<p>&lt;bidBeginTm&gt;10:00&lt;/bidBeginTm&gt;</p>
<p>&lt;bidClseDate&gt;2025-07-08&lt;/bidClseDate&gt;</p>
<p>&lt;bidClseTm&gt;15:00&lt;/bidClseTm&gt;</p>
<p>&lt;opengDate&gt;2025-07-08&lt;/opengDate&gt;</p>
<p>&lt;opengTm&gt;16:00&lt;/opengTm&gt;</p>
<p>&lt;opengPlce&gt;국가종합전자조달시스템(나라장터)&lt;/opengPlce&gt;</p>
<p>&lt;asignBdgtAmt&gt;97240000&lt;/asignBdgtAmt&gt;</p>
<p>&lt;presmptPrce&gt;88400000&lt;/presmptPrce&gt;</p>
<p>&lt;rsrvtnPrceDcsnMthdNm&gt;단일예가&lt;/rsrvtnPrceDcsnMthdNm&gt;</p>
<p>&lt;rgnLmtYn&gt;N&lt;/rgnLmtYn&gt;</p>
<p>&lt;prtcptPsblRgnNm&gt;...(이하생략 나라장터참조)&lt;/prtcptPsblRgnNm&gt;</p>
<p>&lt;indstrytyLmtYn&gt;N&lt;/indstrytyLmtYn&gt;</p>
<p>&lt;bidprcPsblIndstrytyNm&gt;&lt;/bidprcPsblIndstrytyNm&gt;</p>
<p>&lt;bidNtceUrl&gt;https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R25BK00933743&amp;amp;bidPbancOrd=000&lt;/bidNtceUrl&gt;</p>
<p>&lt;dataBssDate&gt;2025-08-07&lt;/dataBssDate&gt;</p>
<p>&lt;/item&gt;</p>
<p>&lt;/items&gt;</p>
<p>&lt;numOfRows&gt;10&lt;/numOfRows&gt;</p>
<p>&lt;pageNo&gt;1&lt;/pageNo&gt;</p>
<p>&lt;totalCount&gt;1417&lt;/totalCount&gt;</p>
<p>&lt;/body&gt;</p>
<p>&lt;/response&gt;</p></td>
</tr>
</tbody>
</table>

#### \[데이터셋 개방표준에 따른 낙찰정보\] 오퍼레이션 명세

<table>
<colgroup>
<col style="width: 4%" />
<col style="width: 21%" />
<col style="width: 17%" />
<col style="width: 21%" />
<col style="width: 2%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr>
<td rowspan="6">오퍼레이션 정보</td>
<td>오퍼레이션 번호</td>
<td>2</td>
<td>오퍼레이션명(국문)</td>
<td colspan="2">데이터셋 개방표준에 따른 낙찰정보</td>
</tr>
<tr>
<td>오퍼레이션 유형</td>
<td>조회(목록)</td>
<td>오퍼레이션명(영문)</td>
<td colspan="2">getDataSetOpnStdScsbidInfo</td>
</tr>
<tr>
<td>오퍼레이션 설명</td>
<td colspan="4">검색조건을 개찰일시, 업무구분명으로 입찰공고번호, 입찰공고차수, 입찰공고명, 업무구분명, 계약체결형태명, 계약체결방법명, 낙찰자결정방법명, 공고기관명, 공고기관코드 등 나라장터에 등록된 낙찰정보 조회</td>
</tr>
<tr>
<td>Call Back URL</td>
<td colspan="4" style="text-align: left;">N/A</td>
</tr>
<tr>
<td>최대 메시지 사이즈</td>
<td colspan="4">[ 4000bytes]</td>
</tr>
<tr>
<td>평균 응답 시간</td>
<td>[ 500 ms]</td>
<td colspan="2">초당 최대 트랜잭션</td>
<td>[ 30 tps]</td>
</tr>
</tbody>
</table>

##### 요청 메시지 명세

|  |  |  |  |  |  |
|----|----|----|----|----|----|
| 항목명(영문) | 항목명(국문) | 항목크기 | 항목구분 | 샘플데이터 | 항목설명 |
| numOfRows | 한 페이지 결과 수 | 4 | 0 | 10 | 한 페이지 결과 수 |
| pageNo | 페이지 번호 | 4 | 0 | 1 | 페이지 번호 |
| ServiceKey | 서비스키 | 400 | 1 | 공공데이터포털에서 받은 인증키 | 공공데이터포털에서 받은 인증키 |
| type | 타입 | 4 | 0 | json | 오픈API 리턴 타입을 JSON으로 받고 싶을 경우 'json' 으로 지정 |
| bsnsDivCd | 업무구분코드 | 2 | 1 | 3 | 업무구분코드가 1이면 물품, 2면 외자, 3이면 공사, 5면 용역 |
| opengBgnDt | 개찰시작일시 | 12 | 1 | 202507010000 | 검색하고자하는 개찰일시범위 시작 'YYYYMMDDHHMM' (개찰일시 범위는 1주일로 제한) |
| opengEndDt | 개찰종료일시 | 12 | 1 | 202507022359 | 검색하고자하는 개찰일시범위 종료 'YYYYMMDDHHMM' (개찰일시 범위는 1주일로 제한) |

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 응답 메시지 명세

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 18%" />
<col style="width: 14%" />
<col style="width: 13%" />
<col style="width: 14%" />
<col style="width: 18%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>항목명(영문)</strong></th>
<th style="text-align: center;"><strong>항목명(국문)</strong></th>
<th style="text-align: center;"><strong>항목크기</strong></th>
<th style="text-align: center;"><strong>항목구분</strong></th>
<th style="text-align: center;"><strong>샘플데이터</strong></th>
<th style="text-align: center;"><strong>항목설명</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>resultCode</td>
<td>결과코드</td>
<td style="text-align: left;">2</td>
<td style="text-align: left;">1</td>
<td>00</td>
<td>결과코드</td>
</tr>
<tr>
<td>resultMsg</td>
<td>결과메세지</td>
<td style="text-align: left;">50</td>
<td style="text-align: left;">1</td>
<td>정상</td>
<td>결과메세지</td>
</tr>
<tr>
<td>numOfRows</td>
<td>한 페이지 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>10</td>
<td>한 페이지 결과 수</td>
</tr>
<tr>
<td>pageNo</td>
<td>페이지 번호</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>1</td>
<td>페이지 번호</td>
</tr>
<tr>
<td>totalCount</td>
<td>전체 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>1</td>
<td>전체 결과 수</td>
</tr>
<tr>
<td>bidNtceNo</td>
<td>입찰공고번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">R25BK00925778</td>
<td style="text-align: left;"><p>입찰공고를 관리하기 위한 번호이며 조달청나라장터 공고건의 형식은 년도(4)+월(2)+순번(5)이며 나라장터 외 (자체)전자조달시스템(이하 이 표에서 “기타 전자조달시스템”이라 함) 보유기관은 각 기관별 형식 별도 사용</p>
<p>*차세대나라장터 번호체계 개편 :R+년도(2)+BK+순번(8) 총 13자리 구성 적용</p>
<p>*2025년 공고건부터 적용</p></td>
</tr>
<tr>
<td>bidNtceOrd</td>
<td>입찰공고차수</td>
<td style="text-align: left;">3</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">000</td>
<td style="text-align: left;">입찰공고차수는 해당 입찰공고에 대한 정정(변경)공고 및 재공고 등이 발생되었을 경우 증가되는 수</td>
</tr>
<tr>
<td>bidNtceNm</td>
<td>입찰공고명</td>
<td style="text-align: left;">1000</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">[부여]국도40호 가탑삼거리 교차로개선사업</td>
<td style="text-align: left;">공사명 또는 사업명이라고도 하며 입찰공고 내용을 요약한 이름</td>
</tr>
<tr>
<td>bsnsDivNm</td>
<td>업무구분명</td>
<td style="text-align: left;">20</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">공사</td>
<td style="text-align: left;">입찰업무를 구분하는 명으로 물품, 용역, 공사, 외자로 구분함</td>
</tr>
<tr>
<td>cntrctCnclsSttusNm</td>
<td>계약체결형태명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">총액계약</td>
<td style="text-align: left;">계약체결형태를 구분하는 명<br />
*총액계약은 계약목적물 전체에 대하여 단가가 아닌 총액으로 체결하는 계약형태<br />
*단가계약은 수요 빈도가 많은 품목에 대하여 단가에 의해 예정수량을 명시하고 체결하는 계약형태,<br />
*제3자단가계약은 각 수요기관에서 공통적으로 필요로 하는 수요물자를 계약시 미리 단가만을 정하여 계약을 체결하고 각 수요기관에서 직접 납품요구하여 구매하는 계약형태</td>
</tr>
<tr>
<td>cntrctCnclsMthdNm</td>
<td>계약체결방법명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">수의계약</td>
<td style="text-align: left;">계약체결의 방법을 구분하는 명<br />
*일반경쟁계약은 계약 대상 물품의 규격 및 시방서와 계약조건 등을 널리 공고하여 일정한 자격을 가진 불특정 다수인의 입찰희망자를 모두 경쟁 입찰하는 계약방법<br />
*제한경쟁계약은 일반·지명경쟁계약제도의 단점을 보완하기 위해 실적제한, 기술보유제한, 특정물품제한, 지역제한 등을 두는 계약방법<br />
*지명경쟁계약은 계약상대자의 신용과 실적 등에 있어 적당하다고 인정하는 특정 다수의 경쟁 참가자를 지명하여 계약 상대방을 결정하는 계약방법<br />
*수의계약은 계약상대자를 결정함에 있어 경쟁방법에 의하지 않고 특정인을 선정하여 계약하는 계약방법</td>
</tr>
<tr>
<td>bidwinrDcsnMthdNm</td>
<td>낙찰자결정방법명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">소액수의견적</td>
<td style="text-align: left;">해당 공고건에 대해 낙찰자를 결정하는 방법</td>
</tr>
<tr>
<td>ntceInsttNm</td>
<td>공고기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">충청남도 건설본부 건설사업부 동부사무소</td>
<td style="text-align: left;">수요기관의 의뢰를 받아 공고하는 기관의 명</td>
</tr>
<tr>
<td>ntceInsttCd</td>
<td>공고기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">6441502</td>
<td style="text-align: left;">공고를 하는 기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td>dmndInsttNm</td>
<td>수요기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">충청남도 건설본부 건설사업부 동부사무소</td>
<td style="text-align: left;">중앙조달인 경우 조달사업에 관한 법률 제2조(정의)에 따라 수요물자의 구매 공급 또는 시설공사 계약의 체결을 조달청장에게 요청할 수 있도록 조달청장이 인정하여 등록한 기관 또는 기타 전자조달시스템을 이용하는 기관인 경우 계약을 의뢰한 기관의 명으로 공고기관과 수요기관이 동일할 수 있음</td>
</tr>
<tr>
<td>dmndInsttCd</td>
<td>수요기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">6441502</td>
<td style="text-align: left;">실제 수요기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td>sucsfLwstlmtRt</td>
<td>낙찰하한율</td>
<td style="text-align: left;">22</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">89.745</td>
<td style="text-align: left;">적격심사제도나 중소기업간경쟁물품에 대한 계약이행능력심사시 입찰가격을 제외한 다른 항목은 모두 만점을 받을 경우를 가정하여 낙찰가능한 최소한의 예정가격 대비 가격 투찰율을 말하며 이 하한율 아래로 투찰하면 낙찰되지 못하는 비율을 말함</td>
</tr>
<tr>
<td>presmptPrce</td>
<td>추정가격</td>
<td style="text-align: left;">25</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">124209091</td>
<td style="text-align: left;">물품/공사/용역 등의 조달 계약을 체결함에 있어 국제입찰 대상여부를 판단하는 기준 등으로 삼기 위하여 예정가격이 결정되기 전에 국가계약법 시행령 등에서 정한 ‘추정가격의 산정’ 규정에 의하여 산정된 가격으로 부가가치세 및 관급자재비를 제외한 금액(원화,원)</td>
</tr>
<tr>
<td>rsrvtnPrce</td>
<td>예정가격</td>
<td style="text-align: left;">21</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">135898725</td>
<td style="text-align: left;">입찰 또는 계약 체결 전에 낙찰자 및 계약금액의 결정기준으로 삼기 위하여 미리 작성/비치하여 두는 가액(원화,원)</td>
</tr>
<tr>
<td>bssAmt</td>
<td>기초금액</td>
<td style="text-align: left;">21</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">136630000</td>
<td style="text-align: left;">예정가격 작성 과정에서 거래실례가격, 원가계산가격 등에 의하여 조사한 가격이나 설계가격에 대하여 계약담당공무원이 그 적정여부를 검토조정한 가격(복수 예비가격 산정을 위한 기준금액)(원화,원)</td>
</tr>
<tr>
<td>opengDate</td>
<td>개찰일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2025-07-01</td>
<td style="text-align: left;">조달업체가 제출한 입찰서를 개찰하는 일자</td>
</tr>
<tr>
<td>opengTm</td>
<td>개찰시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">10:00</td>
<td style="text-align: left;">조달업체가 제출한 입찰서를 개찰하는 시각</td>
</tr>
<tr>
<td>opengRsltDivNm</td>
<td>개찰결과구분명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">개찰완료</td>
<td style="text-align: left;">해당 공고건에 대한 개찰결과를 구분하는 것으로 개찰이 완료되었는지, 유찰되었는지, 재입찰 할것인지 등을 구분하는 명</td>
</tr>
<tr>
<td>opengRank</td>
<td>개찰순위</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">개찰순위는 낙찰자결정방법에 따라 개찰한 결과에 대한 업체별 순위이며, 협상에 의한 계약의 경우 협상기술능력 평가점수와 입찰가격 평가점수의 합산하여 고득점 순에 따라 결정되며 협상순위를 의미함</td>
</tr>
<tr>
<td>bidprcCorpBizrno</td>
<td>투찰업체사업자등록번호</td>
<td style="text-align: left;">12</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">3088103521</td>
<td style="text-align: left;">투찰한 업체의 사업자등록번호</td>
</tr>
<tr>
<td>bidprcCorpNm</td>
<td>투찰업체명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">대륜건설(주)</td>
<td style="text-align: left;">투찰한 업체의 명</td>
</tr>
<tr>
<td>bidprcCorpCeoNm</td>
<td>투찰업체대표자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">손현구</td>
<td style="text-align: left;">투찰한 업체의 대표자의 명</td>
</tr>
<tr>
<td>bidprcAmt</td>
<td>투찰금액</td>
<td style="text-align: left;">21</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">122845000</td>
<td style="text-align: left;">투찰한 금액(원화,원)</td>
</tr>
<tr>
<td>bidprcRt</td>
<td>투찰율</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">90.394</td>
<td style="text-align: left;">예정가격에 대한 투찰금액의 비율로 투찰금액/예정가격 *100 임(%)</td>
</tr>
<tr>
<td>bidprcDate</td>
<td>투찰일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2025-06-27</td>
<td style="text-align: left;">투찰업체가 투찰한 일자</td>
</tr>
<tr>
<td>bidprcTm</td>
<td>투찰시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">08:19</td>
<td style="text-align: left;">투찰업체가 투찰한 시각</td>
</tr>
<tr>
<td>sucsfYn</td>
<td>낙찰여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">Y</td>
<td style="text-align: left;">투찰업체의 해당 입찰공고건에 대한 낙찰여부</td>
</tr>
<tr>
<td>dqlfctnRsn</td>
<td>부적격사유</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">정상</td>
<td style="text-align: left;">투찰업체에 대한 개찰 결과가 부적격으로 판명될 경우 그 부적격으로 판명된 사유</td>
</tr>
<tr>
<td>fnlSucsfAmt</td>
<td>최종낙찰금액</td>
<td style="text-align: left;">21</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">122845000</td>
<td style="text-align: left;">최종낙찰은 개찰순위 순서대로 협상등을 통해 최종 낙찰된정보를 의미하며 최종낙찰금액은 최종낙찰된 금액으로 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임 (원화,원)</td>
</tr>
<tr>
<td>fnlSucsfRt</td>
<td>최종낙찰율</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">90.394</td>
<td style="text-align: left;">예정가격대비 최종낙찰금액으로 최종낙찰금액/예정가격 * 100 으로 계산되며 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임 (%)</td>
</tr>
<tr>
<td>fnlSucsfDate</td>
<td>최종낙찰일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">2025-07-02</td>
<td style="text-align: left;">최종낙찰된 일자로 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임</td>
</tr>
<tr>
<td>fnlSucsfCorpNm</td>
<td>최종낙찰업체명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">대륜건설(주)</td>
<td style="text-align: left;">최종낙찰된 업체의 명으로 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임</td>
</tr>
<tr>
<td>fnlSucsfCorpCeoNm</td>
<td>최종낙찰업체대표자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">홍삼동</td>
<td style="text-align: left;">최종낙찰된 업체의 대표자명으로 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임</td>
</tr>
<tr>
<td>fnlSucsfCorpOfclNm</td>
<td>최종낙찰업체담당자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">홍사동</td>
<td style="text-align: left;">최종낙찰된 업체의 담당자명으로 개찰결과구분명이 “개찰완료”일 경우 필수 입력 항목임</td>
</tr>
<tr>
<td>fnlSucsfCorpBizrno</td>
<td>최종낙찰업체사업자등록번호</td>
<td style="text-align: left;">12</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">308-81-03521</td>
<td style="text-align: left;">최종낙찰된 업체의 사업자등록번호임</td>
</tr>
<tr>
<td>fnlSucsfCorpAdrs</td>
<td>최종낙찰업체주소</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">충청남도 부여군 부여읍 성왕로161</td>
<td style="text-align: left;">최종낙찰된 업체의 주소임</td>
</tr>
<tr>
<td>fnlSucsfCorpContactTel</td>
<td>최종낙찰업체연락전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td style="text-align: left;">042-000-0000</td>
<td style="text-align: left;">최종낙찰된 업체의 연락 전화번호임</td>
</tr>
<tr>
<td>dataBssDate</td>
<td>데이터기준일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">2016-09-30</td>
<td style="text-align: left;">데이터 작성 기준일자</td>
</tr>
</tbody>
</table>

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 요청 / 응답 메시지 예제

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td>REST(URI)</td>
</tr>
<tr>
<td style="text-align: left;">http://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdScsbidInfo? numOfRows=10&amp;pageNo=1&amp;opengBgnDt=201701010000&amp;opengEndDt=201701062359&amp;bsnsDivCd=1&amp;ServiceKey=인증키</td>
</tr>
<tr>
<td>응답 메시지</td>
</tr>
<tr>
<td><p>&lt;response&gt;</p>
<p>&lt;header&gt;</p>
<p>&lt;resultCode&gt;00&lt;/resultCode&gt;</p>
<p>&lt;resultMsg&gt;정상&lt;/resultMsg&gt;</p>
<p>&lt;/header&gt;</p>
<p>&lt;body&gt;</p>
<p>&lt;items&gt;</p>
<p>&lt;item&gt;</p>
<p>&lt;bidNtceNo&gt;R25BK00925778&lt;/bidNtceNo&gt;</p>
<p>&lt;bidNtceOrd&gt;000&lt;/bidNtceOrd&gt;</p>
<p>&lt;bidNtceNm&gt;[부여]국도40호 가탑삼거리 교차로개선사업&lt;/bidNtceNm&gt;</p>
<p>&lt;bsnsDivNm&gt;공사&lt;/bsnsDivNm&gt;</p>
<p>&lt;cntrctCnclsSttusNm&gt;총액계약&lt;/cntrctCnclsSttusNm&gt;</p>
<p>&lt;cntrctCnclsMthdNm&gt;수의계약&lt;/cntrctCnclsMthdNm&gt;</p>
<p>&lt;bidwinrDcsnMthdNm&gt;소액수의견적&lt;/bidwinrDcsnMthdNm&gt;</p>
<p>&lt;ntceInsttNm&gt;충청남도 건설본부 건설사업부 동부사무소&lt;/ntceInsttNm&gt;</p>
<p>&lt;ntceInsttCd&gt;6441502&lt;/ntceInsttCd&gt;</p>
<p>&lt;dmndInsttNm&gt;충청남도 건설본부 건설사업부 동부사무소&lt;/dmndInsttNm&gt;</p>
<p>&lt;dmndInsttCd&gt;6441502&lt;/dmndInsttCd&gt;</p>
<p>&lt;sucsfLwstlmtRt&gt;89.745&lt;/sucsfLwstlmtRt&gt;</p>
<p>&lt;presmptPrce&gt;124209091&lt;/presmptPrce&gt;</p>
<p>&lt;rsrvtnPrce&gt;135898725&lt;/rsrvtnPrce&gt;</p>
<p>&lt;bssAmt&gt;136630000&lt;/bssAmt&gt;</p>
<p>&lt;opengDate&gt;2025-07-01&lt;/opengDate&gt;</p>
<p>&lt;opengTm&gt;10:00&lt;/opengTm&gt;</p>
<p>&lt;opengRsltDivNm&gt;개찰완료&lt;/opengRsltDivNm&gt;</p>
<p>&lt;opengRank&gt;1&lt;/opengRank&gt;</p>
<p>&lt;bidprcCorpBizrno&gt;3088103521&lt;/bidprcCorpBizrno&gt;</p>
<p>&lt;bidprcCorpNm&gt;대륜건설(주)&lt;/bidprcCorpNm&gt;</p>
<p>&lt;bidprcCorpCeoNm&gt;손현구&lt;/bidprcCorpCeoNm&gt;</p>
<p>&lt;bidprcAmt&gt;122845000&lt;/bidprcAmt&gt;</p>
<p>&lt;bidprcRt&gt;90.394&lt;/bidprcRt&gt;</p>
<p>&lt;bidprcDate&gt;2025-06-27&lt;/bidprcDate&gt;</p>
<p>&lt;bidprcTm&gt;08:19&lt;/bidprcTm&gt;</p>
<p>&lt;sucsfYn&gt;Y&lt;/sucsfYn&gt;</p>
<p>&lt;dqlfctnRsn&gt;정상&lt;/dqlfctnRsn&gt;</p>
<p>&lt;fnlSucsfAmt&gt;122845000&lt;/fnlSucsfAmt&gt;</p>
<p>&lt;fnlSucsfRt&gt;90.394&lt;/fnlSucsfRt&gt;</p>
<p>&lt;fnlSucsfDate&gt;2025-07-02&lt;/fnlSucsfDate&gt;</p>
<p>&lt;fnlSucsfCorpNm&gt;대륜건설(주)&lt;/fnlSucsfCorpNm&gt;</p>
<p>&lt;fnlSucsfCorpCeoNm&gt;손현구&lt;/fnlSucsfCorpCeoNm&gt;</p>
<p>&lt;fnlSucsfCorpOfclNm&gt;&lt;/fnlSucsfCorpOfclNm&gt;</p>
<p>&lt;fnlSucsfCorpBizrno&gt;308-81-03521&lt;/fnlSucsfCorpBizrno&gt;</p>
<p>&lt;fnlSucsfCorpAdrs&gt;충청남도 부여군 부여읍 성왕로161 &lt;/fnlSucsfCorpAdrs&gt;</p>
<p>&lt;fnlSucsfCorpContactTel&gt;042-826-6220&lt;/fnlSucsfCorpContactTel&gt;</p>
<p>&lt;dataBssDate&gt;2025-08-08&lt;/dataBssDate&gt;</p>
<p>&lt;/item&gt;</p>
<p>&lt;/items&gt;</p>
<p>&lt;numOfRows&gt;10&lt;/numOfRows&gt;</p>
<p>&lt;pageNo&gt;1&lt;/pageNo&gt;</p>
<p>&lt;totalCount&gt;315130&lt;/totalCount&gt;</p>
<p>&lt;/body&gt;</p>
<p>&lt;/response&gt;</p></td>
</tr>
</tbody>
</table>

####  ****\[데이터셋 개방표준에 따른 계약정보\] 오퍼레이션 명세

<table>
<colgroup>
<col style="width: 4%" />
<col style="width: 21%" />
<col style="width: 17%" />
<col style="width: 21%" />
<col style="width: 2%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr>
<td rowspan="6">오퍼레이션 정보</td>
<td>오퍼레이션 번호</td>
<td>3</td>
<td>오퍼레이션명(국문)</td>
<td colspan="2">데이터셋 개방표준에 따른 계약정보</td>
</tr>
<tr>
<td>오퍼레이션 유형</td>
<td>조회(목록)</td>
<td>오퍼레이션명(영문)</td>
<td colspan="2">getDataSetOpnStdCntrctInfo</td>
</tr>
<tr>
<td>오퍼레이션 설명</td>
<td colspan="4">검색조건을 계약체결일자로 계약번호, 통합계약번호, 계약차수, 계약명, 업무구분명, 계약체결형태명, 계약체결방법명, 장기계속구분명, 공동계약여부, 계약체결일자, 계약기간, 계약금액 등 나라장터에 등록된 계약정보 조회</td>
</tr>
<tr>
<td>Call Back URL</td>
<td colspan="4" style="text-align: left;">N/A</td>
</tr>
<tr>
<td>최대 메시지 사이즈</td>
<td colspan="4">[ 4000bytes]</td>
</tr>
<tr>
<td>평균 응답 시간</td>
<td>[ 500 ms]</td>
<td colspan="2">초당 최대 트랜잭션</td>
<td>[ 30 tps]</td>
</tr>
</tbody>
</table>

##### 요청 메시지 명세

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 13%" />
<col style="width: 12%" />
<col style="width: 12%" />
<col style="width: 21%" />
</colgroup>
<tbody>
<tr>
<td>항목명(영문)</td>
<td>항목명(국문)</td>
<td>항목크기</td>
<td>항목구분</td>
<td>샘플데이터</td>
<td>항목설명</td>
</tr>
<tr>
<td>numOfRows</td>
<td>한 페이지 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>10</td>
<td>한 페이지 결과 수</td>
</tr>
<tr>
<td>pageNo</td>
<td>페이지 번호</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>1</td>
<td>페이지 번호</td>
</tr>
<tr>
<td>ServiceKey</td>
<td>서비스키</td>
<td style="text-align: left;">400</td>
<td style="text-align: left;">1</td>
<td>공공데이터포털에서 받은 인증키</td>
<td>공공데이터포털에서 받은 인증키</td>
</tr>
<tr>
<td>type</td>
<td>타입</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">0</td>
<td>json</td>
<td>오픈API 리턴 타입을 JSON으로 받고 싶을 경우 'json' 으로 지정</td>
</tr>
<tr>
<td>cntrctCnclsBgnDate</td>
<td>계약체결시작일자</td>
<td style="text-align: left;">8</td>
<td style="text-align: left;">1</td>
<td>20250305</td>
<td>검색하고자하는 계약체결일자 시작 'YYYYMMDD' (계약체결일자 범위는 1개월 로 제한)</td>
</tr>
<tr>
<td>cntrctCnclsEndDate</td>
<td>계약체결종료일자</td>
<td style="text-align: left;">8</td>
<td style="text-align: left;">1</td>
<td>20250305</td>
<td>검색하고자하는 계약체결일자 종료 'YYYYMMDD' (계약체결일자 범위는 1개월 로 제한)</td>
</tr>
<tr>
<td>insttDivCd</td>
<td>기관구분값</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td>1</td>
<td>검색하고자 하는 기관구분값 1인 경우 계약기관, 2인 경우 수요기관</td>
</tr>
<tr>
<td>insttCd</td>
<td>기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td>4490000</td>
<td>기관구분코드이 1 일경우 계약기관코드<br />
기관구분코드 2일경우 수요기관코드</td>
</tr>
</tbody>
</table>

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 응답 메시지 명세

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 18%" />
<col style="width: 14%" />
<col style="width: 13%" />
<col style="width: 14%" />
<col style="width: 18%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>항목명(영문)</strong></th>
<th style="text-align: center;"><strong>항목명(국문)</strong></th>
<th style="text-align: center;"><strong>항목크기</strong></th>
<th style="text-align: center;"><strong>항목구분</strong></th>
<th style="text-align: center;"><strong>샘플데이터</strong></th>
<th style="text-align: center;"><strong>항목설명</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td>resultCode</td>
<td>결과코드</td>
<td style="text-align: left;">2</td>
<td style="text-align: left;">1</td>
<td>00</td>
<td>결과코드</td>
</tr>
<tr>
<td>resultMsg</td>
<td>결과메세지</td>
<td style="text-align: left;">50</td>
<td style="text-align: left;">1</td>
<td>정상</td>
<td>결과메세지</td>
</tr>
<tr>
<td>numOfRows</td>
<td>한 페이지 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>10</td>
<td>한 페이지 결과 수</td>
</tr>
<tr>
<td>pageNo</td>
<td>페이지 번호</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>1</td>
<td>페이지 번호</td>
</tr>
<tr>
<td>totalCount</td>
<td>전체 결과 수</td>
<td style="text-align: left;">4</td>
<td style="text-align: left;">1</td>
<td>1</td>
<td>전체 결과 수</td>
</tr>
<tr>
<td>cntrctNo</td>
<td>계약번호</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">1</td>
<td>R25TA00247713</td>
<td>계약서를 식별하기 위한 관리번호</td>
</tr>
<tr>
<td>untyCntrctNo</td>
<td>통합계약번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td>R25TA00247713</td>
<td>조달청 나라장터g2b.go.kr)에서 조달청에서 발주하는 중앙조달과 자체조달기관에서 발생되는 자체조달 계약의 통합 관리를 위해 채번되는 번호</td>
</tr>
<tr>
<td>cntrctOrd</td>
<td>계약차수</td>
<td style="text-align: left;">2</td>
<td style="text-align: left;">1</td>
<td>00</td>
<td>계약의 변경 시 변경된 차수</td>
</tr>
<tr>
<td>cntrctNm</td>
<td>계약명</td>
<td style="text-align: left;">500</td>
<td style="text-align: left;">1</td>
<td>2025년 시내버스 노후LED 전광판 교체사업</td>
<td>공사명 또는 사업명이라고도 하며 계약내용을 요약한 이름</td>
</tr>
<tr>
<td>bsnsDivNm</td>
<td>업무구분명</td>
<td style="text-align: left;">20</td>
<td style="text-align: left;">1</td>
<td>물품</td>
<td>입찰업무를 구분하는 명으로 물품, 용역, 공사, 외자, 비축으로 구분함</td>
</tr>
<tr>
<td>cntrctCnclsSttusNm</td>
<td>계약체결형태명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td>총액계약</td>
<td>계약체결형태를 구분하는 명<br />
*총액계약은 계약목적물 전체에 대하여 단가가 아닌 총액으로 체결하는 계약형태<br />
*단가계약은 수요 빈도가 많은 품목에 대하여 단가에 의해 예정수량을 명시하고 체결하는 계약형태,<br />
*제3자단가계약은 각 수요기관에서 공통적으로 필요로 하는 수요물자를 계약시 미리 단가만을 정하여 계약을 체결하고 각 수요기관에서 직접 납품요구하여 구매하는 계약형태</td>
</tr>
<tr>
<td>cntrctCnclsMthdNm</td>
<td>계약체결방법명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">1</td>
<td>수의계약</td>
<td>계약체결의 방법을 구분하는 명<br />
*일반경쟁계약은 계약 대상 물품의 규격 및 시방서와 계약조건 등을 널리 공고하여 일정한 자격을 가진 불특정 다수인의 입찰희망자를 모두 경쟁 입찰하는 계약방법<br />
*제한경쟁계약은 일반·지명경쟁계약제도의 단점을 보완하기 위해 실적제한, 기술보유제한, 특정물품제한, 지역제한 등을 두는 계약방법<br />
*지명경쟁계약은 계약상대자의 신용과 실적 등에 있어 적당하다고 인정하는 특정 다수의 경쟁 참가자를 지명하여 계약 상대방을 결정하는 계약방법<br />
*수의계약은 계약상대자를 결정함에 있어 경쟁방법에 의하지 않고 특정인을 선정하여 계약하는 계약방법</td>
</tr>
<tr>
<td>lngtrmCtnuDivNm</td>
<td>장기계속구분명</td>
<td style="text-align: left;">30</td>
<td style="text-align: left;">0</td>
<td>단년도계약</td>
<td>계약이행에 수년을 요하는 계약을 장기계속계약이라 하며 해당 계약이 단기계약인지 장기계속계약 또는 계속비계약인지를 구분하는 명</td>
</tr>
<tr>
<td>cmmnCntrctYn</td>
<td>공동계약여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td>N</td>
<td>공동계약의 경우 공사/제조 기타의 계약에 있어서 필요하다고 인정할 때 계약 상대자를 2인 이상과 체결하는 계약이며 단독계약은 계약상대자를 1인으로 하는 통상적인 계약을 의미함.</td>
</tr>
<tr>
<td>cntrctCnclsDate</td>
<td>계약체결일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td>2025-03-05</td>
<td>계약이 성립된 체결일자</td>
</tr>
<tr>
<td>cntrctPrd</td>
<td>계약기간</td>
<td style="text-align: left;">70</td>
<td style="text-align: left;">1</td>
<td>2025.03.05.</td>
<td>계약의 효력이 있는 기간</td>
</tr>
<tr>
<td>cntrctAmt</td>
<td>계약금액</td>
<td style="text-align: left;">25</td>
<td style="text-align: left;">1</td>
<td>214345450</td>
<td>당해연도계약의 경우 계약금액을 의미하며 장기계속계약의 경우 금차계약금액을 의미함(원화,원)</td>
</tr>
<tr>
<td>ttalCntrctAmt</td>
<td>총계약금액</td>
<td style="text-align: left;">25</td>
<td style="text-align: left;">0</td>
<td>0</td>
<td>장기계속계약의 경우에만 발생되며 장기계속계약 전체 계약금액(총부기금액) 을 의미함(원화,원)</td>
</tr>
<tr>
<td>cntrctInfoUrl</td>
<td>계약정보URL</td>
<td style="text-align: left;">500</td>
<td style="text-align: left;">0</td>
<td>https://www.g2b.go.kr/link/FIUA027_01/single/?ctrtNo=R25TA00348817&amp; ctrtChgOrd=00&amp; prcmBsneSeCd=조070001&amp;srchName=ctrtCrst&amp; openUrl=Y</td>
<td>계약정보를 인터넷상에서 확인할 수 있는 URL주소</td>
</tr>
<tr>
<td>bidNtceNo</td>
<td>입찰공고번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td>R25BK00646279</td>
<td><p>입찰공고 관리번호이며 조달청나라장터 공고건의 형식은 년도(4)+월(2)+순번(5)이며 자체전자조달시스템 보유기관은 각 기관별 형식 별도 사용</p>
<p>*차세대나라장터 번호체계 개편 : 테스트여부(1)+년도(2)+번호구분(2)+순번(8) 총 13자리 구성</p>
<p>(테스트여부 : T(모의)/R(실제), 번호구분 : BK(입찰공고번호)/TA(계약번호) 예시 : R24TA00000001 ☞ `24년 실제 계약번호이며 순번은 00000001)</p></td>
</tr>
<tr>
<td>bidNtceOrd</td>
<td>입찰공고차수</td>
<td style="text-align: left;">3</td>
<td style="text-align: left;">0</td>
<td>000</td>
<td>입찰공고차수는 해당 입찰공고에 대한 정정(변경)공고 및 재공고 등이 발생되었을 경우 증가되는 수</td>
</tr>
<tr>
<td>bidNtceNm</td>
<td>입찰공고명</td>
<td style="text-align: left;">1000</td>
<td style="text-align: left;">0</td>
<td>2025년 시내버스 노후LED 전광판 교체사업</td>
<td>공사명 또는 사업명이라고도 하며 입찰공고 내용을 요약한 이름</td>
</tr>
<tr>
<td>opengDate</td>
<td>개찰일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">0</td>
<td>2025-02-26</td>
<td>조달업체가 제출한 입찰서를 개찰하는 일자</td>
</tr>
<tr>
<td>opengTm</td>
<td>개찰시각</td>
<td style="text-align: left;">5</td>
<td style="text-align: left;">0</td>
<td>15:00</td>
<td>조달업체가 제출한 입찰서를 개찰하는 시각</td>
</tr>
<tr>
<td>rsrvtnPrce</td>
<td>예정가격</td>
<td style="text-align: left;">21</td>
<td style="text-align: left;">0</td>
<td>235387050</td>
<td>입찰 또는 계약 체결 전에 낙찰자 및 계약금액의 결정기준으로 삼기 위하여 미리 작성/비치하여 두는 가액</td>
</tr>
<tr>
<td>prvtcntrctRsn</td>
<td>수의계약사유</td>
<td style="text-align: left;">1000</td>
<td style="text-align: left;">0</td>
<td>중소벤처기업부장관이 지정 공고한 물품 [지방계약법 022조 000항 010호 000목]</td>
<td>계약상대자를 결정함에 있어 경쟁입찰방법에 의하지 않고 특정인을 계약상대방으로 선정하여 계약을 체결 시 그 사유내용임[국가계약법 시행령 제26조, 지방계약법 시행령 제25조]</td>
</tr>
<tr>
<td>bidNtceUrl</td>
<td>입찰공고URL</td>
<td style="text-align: left;">500</td>
<td style="text-align: left;">0</td>
<td>https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R25BK00646279&amp;bidPbancOrd=000</td>
<td>해당 입찰공고를 인터넷상에서 확인할 수 있는 URL주소</td>
</tr>
<tr>
<td>cntrctInsttDivNm</td>
<td>계약기관구분명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td>지방자치단체</td>
<td>계약기관이 국가기관인지 지자체인지 등을 구분하는 명</td>
</tr>
<tr>
<td>cntrctInsttNm</td>
<td>계약기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td>충청남도 천안시</td>
<td>계약의 주체가 되는 기관의 명</td>
</tr>
<tr>
<td>cntrctInsttCd</td>
<td>계약기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td>4490000</td>
<td>계약의 주체가 되는 기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td>cntrctInsttChrgDeptNm</td>
<td>계약기관담당부서명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td>천안시 회계과</td>
<td>계약기관의 담당 부서명</td>
</tr>
<tr>
<td>cntrctInsttOfclNm</td>
<td>계약기관담당자명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td>홍길동</td>
<td>계약기관의 담당자 명</td>
</tr>
<tr>
<td>cntrctInsttOfclTel</td>
<td>계약기관담당자전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td>070-000-0000</td>
<td>계약기관의 담당자 전화번호</td>
</tr>
<tr>
<td>cntrctInsttOfcl</td>
<td>계약기관담당자이메일주소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td>aa@b.co.kr</td>
<td>계약기관의 담당자 이메일주소</td>
</tr>
<tr>
<td>dmndInsttDivNm</td>
<td>수요기관구분명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td>지방자치단체</td>
<td>수요기관이 국가기관인지 지자체인지 등을 구분하는 명</td>
</tr>
<tr>
<td>dmndInsttNm</td>
<td>수요기관명</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">1</td>
<td>충청남도 천안시</td>
<td>중앙조달인 경우 조달사업에 관한 법률 제2조(정의)에 따라 수요물자의 구매 공급 또는 시설공사 계약의 체결을 조달청장에게 요청할 수 있도록 조달청장이 인정하여 등록한 기관 또는 기타 전자조달시스템을 이용하는 기관인 경우 계약을 의뢰한 기관의 명으로 공고기관과 수요기관이 동일할 수 있음</td>
</tr>
<tr>
<td>dmndInsttCd</td>
<td>수요기관코드</td>
<td style="text-align: left;">7</td>
<td style="text-align: left;">0</td>
<td>4490000</td>
<td>실제 수요기관의 코드로 행정안전부에서 부여한 기관코드임</td>
</tr>
<tr>
<td>dmndInsttOfclDeptNm</td>
<td>수요기관담당자부서명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td>천안시 회계과</td>
<td>수요기관의 계약을 담당하는 담당자의 명</td>
</tr>
<tr>
<td>dmndInsttOfclNm</td>
<td>수요기관담당자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td>홍이동</td>
<td>수요기관의 계약을 담당하는 담당부서의 명</td>
</tr>
<tr>
<td>dmndInsttOfclTel</td>
<td>수요기관담당자전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td>042-000-0000</td>
<td>수요기관의 계약을 담당하는 담당자의 전화번호</td>
</tr>
<tr>
<td>dmndInsttOfclEmailAdrs</td>
<td>수요기관담당자이메일주소</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">0</td>
<td>abcd@korea.kr</td>
<td>수요기관의 계약을 담당하는 담당자의 이메일주소</td>
</tr>
<tr>
<td>rprsntCorpNm</td>
<td>대표업체명</td>
<td style="text-align: left;">100</td>
<td style="text-align: left;">1</td>
<td>주식회사 티이케이</td>
<td>계약의 상대 중 대표가 되는 업체의 명</td>
</tr>
<tr>
<td>dmstcCorpYn</td>
<td>국내업체여부</td>
<td style="text-align: left;">1</td>
<td style="text-align: left;">0</td>
<td>Y</td>
<td>계약 상대업체가 국내업체인지의 여부</td>
</tr>
<tr>
<td>rprsntCorpCeoNm</td>
<td>대표업체대표자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td>홍삼동</td>
<td>대표업체의 대표자 성명</td>
</tr>
<tr>
<td>rprsntCorpOfclNm</td>
<td>대표업체담당자명</td>
<td style="text-align: left;">35</td>
<td style="text-align: left;">0</td>
<td>홍사동</td>
<td>대표업체의 담당자 명</td>
</tr>
<tr>
<td>rprsntCorpBizrno</td>
<td>대표업체사업자등록번호</td>
<td style="text-align: left;">12</td>
<td style="text-align: left;">0</td>
<td>123-45-67890</td>
<td>대표업체의 사업자등록번호</td>
</tr>
<tr>
<td>rprsntCorpAdrs</td>
<td>대표업체주소</td>
<td style="text-align: left;">200</td>
<td style="text-align: left;">0</td>
<td>충청남도 천안시 서북구 백석공단1로</td>
<td>대표업체의 사업장 주소</td>
</tr>
<tr>
<td>rprsntCorpContactTel</td>
<td>대표업체연락전화번호</td>
<td style="text-align: left;">13</td>
<td style="text-align: left;">0</td>
<td>041-000-0000</td>
<td>대표업체의 연락 전화번호</td>
</tr>
<tr>
<td>dataBssDate</td>
<td>데이터기준일자</td>
<td style="text-align: left;">10</td>
<td style="text-align: left;">1</td>
<td>2025-08-05</td>
<td>데이터 작성 기준일자</td>
</tr>
</tbody>
</table>

※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)

##### 요청 / 응답 메시지 예제

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr>
<td>REST(URI)</td>
</tr>
<tr>
<td style="text-align: left;">http://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdCntrctInfo? numOfRows=10&amp;pageNo=1&amp;cntrctCnclsBgnDate=20250305&amp;cntrctCnclsEndDate=20250305&amp;ServiceKey=인증키</td>
</tr>
<tr>
<td>응답 메시지</td>
</tr>
<tr>
<td><p>&lt;response&gt;</p>
<p>&lt;header&gt;</p>
<p>&lt;resultCode&gt;00&lt;/resultCode&gt;</p>
<p>&lt;resultMsg&gt;정상&lt;/resultMsg&gt;</p>
<p>&lt;/header&gt;</p>
<p>&lt;body&gt;</p>
<p>&lt;items&gt;</p>
<p>&lt;item&gt;</p>
<p>&lt;cntrctNo&gt;R25TA00247713&lt;/cntrctNo&gt;</p>
<p>&lt;untyCntrctNo&gt;R25TE01743533&lt;/untyCntrctNo&gt;</p>
<p>&lt;cntrctOrd&gt;00&lt;/cntrctOrd&gt;</p>
<p>&lt;cntrctNm&gt;2025년 시내버스 노후LED 전광판 교체사업&lt;/cntrctNm&gt;</p>
<p>&lt;bsnsDivNm&gt;물품&lt;/bsnsDivNm&gt;</p>
<p>&lt;cntrctCnclsSttusNm&gt;총액계약&lt;/cntrctCnclsSttusNm&gt;</p>
<p>&lt;cntrctCnclsMthdNm&gt;지명경쟁&lt;/cntrctCnclsMthdNm&gt;</p>
<p>&lt;lngtrmCtnuDivNm&gt;단년도계약&lt;/lngtrmCtnuDivNm&gt;</p>
<p>&lt;cmmnCntrctYn&gt;N&lt;/cmmnCntrctYn&gt;</p>
<p>&lt;cntrctCnclsDate&gt;2025-03-05&lt;/cntrctCnclsDate&gt;</p>
<p>&lt;cntrctPrd&gt;2025.03.05.&lt;/cntrctPrd&gt;</p>
<p>&lt;cntrctAmt&gt;214345450&lt;/cntrctAmt&gt;</p>
<p>&lt;ttalCntrctAmt&gt;&lt;/ttalCntrctAmt&gt;</p>
<p>&lt;cntrctInfoUrl&gt;https://www.g2b.go.kr/link/FIUA027_01/single/?ctrtNo=R25TA00247713&amp;ctrtChgOrd=00&amp;prcmBsneSeCd=조070001&amp;srchName=ctrtCrst&amp;openUrl=Y&lt;/cntrctInfoUrl&gt;</p>
<p>&lt;bidNtceNo&gt;R25BK00646279&lt;/bidNtceNo&gt;</p>
<p>&lt;bidNtceOrd&gt;000&lt;/bidNtceOrd&gt;</p>
<p>&lt;bidNtceNm&gt;2025년 시내버스 노후LED 전광판 교체사업&lt;/bidNtceNm&gt;</p>
<p>&lt;opengDate&gt;2025-02-26&lt;/opengDate&gt;</p>
<p>&lt;opengTm&gt;15:00&lt;/opengTm&gt;</p>
<p>&lt;rsrvtnPrce&gt;235387050&lt;/rsrvtnPrce&gt;</p>
<p>&lt;prvtcntrctRsn&gt;중소벤처기업부장관이 지정 공고한 물품 [지방계약법 022조 000항 010호 000목]&lt;/prvtcntrctRsn&gt;</p>
<p>&lt;bidNtceUrl&gt;https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R25BK00646279&amp; bidPbancOrd=000&lt;/bidNtceUrl&gt;</p>
<p>&lt;cntrctInsttDivNm&gt;지방자치단체&lt;/cntrctInsttDivNm&gt;</p>
<p>&lt;cntrctInsttNm&gt;충청남도 천안시&lt;/cntrctInsttNm&gt;</p>
<p>&lt;cntrctInsttCd&gt;4490000&lt;/cntrctInsttCd&gt;</p>
<p>&lt;cntrctInsttChrgDeptNm&gt;천안시 회계과&lt;/cntrctInsttChrgDeptNm&gt;</p>
<p>&lt;cntrctInsttOfclNm&gt;안선후&lt;/cntrctInsttOfclNm&gt;</p>
<p>&lt;cntrctInsttOfclTel&gt;0415215289&lt;/cntrctInsttOfclTel&gt;</p>
<p>&lt;cntrctInsttOfcl&gt;cact@korea.kr&lt;/cntrctInsttOfcl&gt;</p>
<p>&lt;dmndInsttDivNm&gt;지방자치단체&lt;/dmndInsttDivNm&gt;</p>
<p>&lt;dmndInsttNm&gt;충청남도 천안시&lt;/dmndInsttNm&gt;</p>
<p>&lt;dmndInsttCd&gt;4490000&lt;/dmndInsttCd&gt;</p>
<p>&lt;dmndInsttOfclDeptNm&gt;천안시 회계과&lt;/dmndInsttOfclDeptNm&gt;</p>
<p>&lt;dmndInsttOfclNm&gt;안선후&lt;/dmndInsttOfclNm&gt;</p>
<p>&lt;dmndInsttOfclTel&gt;0415215289&lt;/dmndInsttOfclTel&gt;</p>
<p>&lt;dmndInsttOfclEmailAdrs&gt;cact@korea.kr&lt;/dmndInsttOfclEmailAdrs&gt;</p>
<p>&lt;rprsntCorpNm&gt;주식회사 티이케이&lt;/rprsntCorpNm&gt;</p>
<p>&lt;dmstcCorpYn&gt;Y&lt;/dmstcCorpYn&gt;</p>
<p>&lt;rprsntCorpCeoNm&gt;윤민아&lt;/rprsntCorpCeoNm&gt;</p>
<p>&lt;rprsntCorpOfclNm&gt;윤민아&lt;/rprsntCorpOfclNm&gt;</p>
<p>&lt;rprsntCorpBizrno&gt;783-81-03488&lt;/rprsntCorpBizrno&gt;</p>
<p>&lt;rprsntCorpAdrs&gt;충청남도 천안시 서북구 백석공단1로&lt;/rprsntCorpAdrs&gt;</p>
<p>&lt;rprsntCorpContactTel&gt;0419065360&lt;/rprsntCorpContactTel&gt;</p>
<p>&lt;dataBssDate&gt;2025-08-05&lt;/dataBssDate&gt;</p>
<p>&lt;/item&gt;</p>
<p>&lt;/items&gt;</p>
<p>&lt;numOfRows&gt;10&lt;/numOfRows&gt;</p>
<p>&lt;pageNo&gt;1&lt;/pageNo&gt;</p>
<p>&lt;totalCount&gt;8302&lt;/totalCount&gt;</p>
<p>&lt;/body&gt;</p>
<p>&lt;/response&gt;</p></td>
</tr>
</tbody>
</table>

**  **

#### **OPEN API 에러코드별 조치방안**

<table>
<colgroup>
<col style="width: 7%" />
<col style="width: 16%" />
<col style="width: 36%" />
<col style="width: 40%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Code</strong></th>
<th style="text-align: center;"><strong>코드값</strong></th>
<th style="text-align: center;"><strong>설명</strong></th>
<th style="text-align: center;"><strong>조치방안</strong></th>
</tr>
</thead>
<tbody>
<tr>
<td style="text-align: center;">01</td>
<td style="text-align: left;">Application Error</td>
<td style="text-align: left;">제공기관 서비스 제공 상태가 원할하지 않습니다.</td>
<td style="text-align: left;">서비스 제공기관의 관리자에게 문의하시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">02</td>
<td style="text-align: left;">DB Error</td>
<td style="text-align: left;">제공기관 서비스 제공 상태가 원할하지 않습니다.</td>
<td style="text-align: left;">서비스 제공기관의 관리자에게 문의하시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">03</td>
<td style="text-align: left;">No Data</td>
<td style="text-align: left;">데이터 없음 에러</td>
<td style="text-align: left;"></td>
</tr>
<tr>
<td style="text-align: center;">04</td>
<td style="text-align: left;">HTTP Error</td>
<td style="text-align: left;">제공기관 서비스 제공 상태가 원할하지 않습니다.</td>
<td style="text-align: left;">서비스 제공기관의 관리자에게 문의하시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">05</td>
<td style="text-align: left;">service time out</td>
<td style="text-align: left;">제공기관 서비스 제공 상태가 원할하지 않습니다</td>
<td style="text-align: left;">서비스 제공기관의 관리자에게 문의하시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">06</td>
<td style="text-align: left;">날짜Format 에러</td>
<td style="text-align: left;">날짜 Default, Format Error</td>
<td style="text-align: left;">날짜형식을 확인 하시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">07</td>
<td style="text-align: left;">입력범위값 초과 에러</td>
<td style="text-align: left;">요청하신 OpenAPI의 파라미터 입력값 범위가 초과 되었습니다.</td>
<td style="text-align: left;">기술문서를 다시 한번 확인하여 주시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">08</td>
<td style="text-align: left;">필수값 입력 에러</td>
<td style="text-align: left;">요청하신 OpenAPI의 필수 파라미터가 누락되었습니다.</td>
<td style="text-align: left;">기술문서를 다시 한번 확인하여 주시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">10</td>
<td style="text-align: left;">잘못된 요청 파라미터 에러</td>
<td style="text-align: left;">OpenAPI 요청시 ServiceKey 파라미터가 없음</td>
<td style="text-align: left;"><p>-OpenAPI 요청시 ServiceKey 파라미터가 누락되었습니다.</p>
<p>-OpenAPI 요청 URL을 확인하시기 바랍니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">11</td>
<td style="text-align: left;">필수 요청 파라미터가 없음</td>
<td style="text-align: left;">요청하신 OpenAPI의 필수 파라미터가 누락되었습니다.</td>
<td style="text-align: left;">기술문서를 다시 한번 확인하시어 주시기 바랍니다.</td>
</tr>
<tr>
<td style="text-align: center;">12</td>
<td style="text-align: left;">해당 오픈API 서비스가 없거나 폐기됨</td>
<td style="text-align: left;">OpenAPI 호출시 URL이 잘못됨</td>
<td style="text-align: left;"><p>-제공기관 관리자에게 폐기된 서비스인지 확인바랍니다.</p>
<p>폐기된 서비스가 아니면 개발가이드에서 OpenAPI요청 URL을 다시 확인하시기 바랍니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">20</td>
<td style="text-align: left;">서비스 접근 거부</td>
<td style="text-align: left;">활용승인이 되지 않은 OpenAPI호출</td>
<td style="text-align: left;"><p>-OpenAPI활용신청정보의 승인상태를 확인하시기 바랍니다.</p>
<p>-활용신청에 대해 제공기관 담당자가 확인 후 '승인'이후 부터 사용할 수 있습니다.</p>
<p>-신청 후 2~3일 소요되고 결과는 회원가입 시 등록한 e-mail로 발송됩니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">22</td>
<td style="text-align: left;">서비스 요청 제한 횟수 초과 에러</td>
<td style="text-align: left;">일일 활용건수가 초과함(활용건수 증가 필요)</td>
<td style="text-align: left;"><p>-OpenAPI활용신청정보의 서비스 상세기능별 일일 트래픽량을 확인하시기 바랍니다.</p>
<p>-개발계정의 경우 제공기관에서 정의한 트래픽을 초과하여 활용할 수 없습니다.</p>
<p>-운영계정의 경우 변경신청을 통해서 일일트래픽량을 변경 할 수 있습니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">30</td>
<td style="text-align: left;">등록되지 않은 서비스 키</td>
<td style="text-align: left;">잘못된 서비스키를 사용하였거나 서비스키를 URL인코딩하지 않음</td>
<td style="text-align: left;"><p>-OpenAPI활용신청정보의 발급받은 서비스키를 다시 확인하시기 바랍니다.</p>
<p>- 서비스키 값이 같다면 서비스키가 URL 인코등 되었는지 다시 확인하시기 바랍니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">31</td>
<td style="text-align: left;">기한 만료된 서비스 키</td>
<td style="text-align: left;"><p>OpenAPI 사용기간이 만료됨</p>
<p>(활용연장신청 후 사용가능)</p></td>
<td style="text-align: left;"><p>-OpenAPI 활용신청정보의 활용기간을 확인합니다.</p>
<p>-활용기간이 지난 서비스는 이용할 수 없으며 연장신청을 통해 승인 받은 후 다시 이용가능 합니다.</p></td>
</tr>
<tr>
<td style="text-align: center;">32</td>
<td style="text-align: left;">등록되지 않은 도메인명 또는 IP주소</td>
<td style="text-align: left;">활용신청한 서버의 IP와 실제 OpenAPI호출한 서버가 다를 경우</td>
<td style="text-align: left;"><p>-OpenAPI 활용신청정보의 등록된 도메인명이나 IP주소를 다시 확인합니다.</p>
<p>-IP나 도메인의 정보를 변경하기 위해 변경신청을 할 수 있습니다.</p></td>
</tr>
</tbody>
</table>

#### 
