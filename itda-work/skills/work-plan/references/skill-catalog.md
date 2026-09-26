# itda-* 스킬 카탈로그

> ⚠️ **자동 생성물 — 수기 편집 금지.** `skills/scripts/gen_skill_catalog.py` 가
> `itda-*/skills/*/SKILL.md` frontmatter·본문에서 생성한다 (#1216).
> 재생성: `python3 skills/scripts/gen_skill_catalog.py` (Windows: `py -3 …`)
> 정합 검사: `--check` — CI 가드는 `scripts/tests/test_gen_skill_catalog.py`.

DP-1 Hybrid: 정적 생성 목록 + 호출 시 sanity check
(`ground_check.skill_dir_exists` 가 아래 경로 매핑으로 실존 확인).

총 102개 스킬 / 12개 팩.

| 스킬명 | 한 줄 요약 | 필요한 키 | 트리거 예시 | 팩 | 책임 경계 |
|--------|-----------|-----------|------------|----|-----------|
| aspect-sentiment | 한국어 텍스트의 측면별 감정·상태를 Claude가 직접 추출하는 ABSA(측면 기반 감정분석) 스킬입니다. | 없음 | "이 리뷰들 측면별 감정 뽑아줘", "상담 로그 측면 분석", "배송·품질 따로 긍부정 분류" | itda-data | — |
| biz-redact | 업무 문서의 영업기밀(거래처명·프로젝트코드·담당자·단가 등)을 외부 AI에 넣기 전 로컬에서 결정론적으로 마스킹하고, AI 산출물의 토큰을 원값으로 되돌리는 왕… | 없음 | "이 견적서 마스킹해서 검토해줘", "거래처명 가리고 원가절감안 분석해줘", "AI가 돌려준 검토서 원래 이름으로 복원해줘" | itda-data | 본 스킬은 용어집 기반 영업기밀 마스킹·왕복 복원 전담 — itda-data:pii-redact 는 정형 PII 무상태 마스킹, itda-data:synthetic-data 는 실제 데이터 없이 같은 구조의 가상 데이터 생성. |
| cs-intent | 한국어 CS 상담·문의 텍스트를 "왜 연락했나"(인텐트/문의유형)로 분류하는 스킬입니다. | 없음 | "왜 연락했나", "이 문의 유형 분류해줘", "상담 인텐트 뽑아줘" | itda-data | — |
| data-ask | CSV 를 한국어로 물으면 실제로 계산해 답하는 질문 스킬입니다. | 없음 | "지역별 환불율", "월별 매출 추이", "재구매 비중" | itda-data | — |
| data-audit | 엑셀·스프레드시트의 수식 오류와 흔한 실수를 훑어 위험한 셀을 짚어주는 감사 스킬입니다. | 없음 | "이 시트 감사해줘", "수식 검토해줘", "수식 오류 찾아줘" | itda-data | 본 스킬은 수식 오류·실수 감사 전담 — 캐시값이 빈 파일의 재계산은 itda-data:xlsx-recalc. |
| data-compass | 처음 보는 데이터 앞에서 뭘 시켜야 할지 모르는 사람을 위한 데이터 분석 내비게이터(순수 코치)입니다. | 없음 | "분석 지도", "이렇게 말해보세요", "이 데이터 분석 어떻게 시작해?" | itda-data | — |
| data-prep | 엉망인 CSV·엑셀을 진단하고 원본은 그대로 둔 채 깔끔한 정돈본을 새 파일로 만들어주는 스킬입니다. | 없음 | "이 엑셀 정리해줘", "제목 행이 위에 있는데 정리해줘", "소계 행 빼고 깔끔하게" | itda-data | — |
| data-verify | 엑셀·CSV의 숫자가 실제로 맞는지 검수하는 스킬입니다. | 없음 | "이 숫자 틀렸어요", "이 수치 맞는지 검수해줘", "합계 검산해줘" | itda-data | — |
| iaa-builder | CS 분류 라벨의 어노테이터 간 일치도(IAA)를 Cohen·Fleiss κ로 측정하는 스킬입니다. | 없음 | "이 라벨링 일치도 재줘", "Cohen 카파 계산", "골드셋 만들어줘" | itda-data | — |
| pii-redact | 한국 CS 상담·문의 텍스트의 개인정보(PII)를 LLM에 넣기 전 결정론 룰로 검출·마스킹하는 스킬입니다. | 없음 | "이 상담 로그 비식별화해줘", "개인정보 가려줘", "PII 마스킹" | itda-data | — |
| synthetic-data | 실제 데이터 없이 업무 문서의 구조만 인터뷰로 받아 같은 구조의 가상 데이터 세트를 만듭니다. | 없음 | "우리 대장 구조로 가상 데이터 50건", "실습용 가짜 환자 명단", "이 양식에 테스트 데이터 채워줘" | itda-data | 본 스킬은 가상 데이터 생성 전담 — itda-data:biz-redact 는 실제 문서 영업기밀 마스킹·복원, itda-data:pii-redact 는 정형 PII 마스킹. |
| xlsx-recalc | openpyxl 등으로 만든 xlsx 는 수식만 있고 계산값이 비어 미리보기·pandas·다른 스킬에서 빈칸으로 보입니다. | 없음 | "엑셀 수식 값 채워줘", "xlsx 재계산해줘", "openpyxl 로 만든 파일 합계가 빈칸이야" | itda-data | 본 스킬은 수식 캐시값 재계산 전담 — itda-data:data-audit 는 수식 오류 감사, itda-doc:xlsx-design 은 xlsx 신규 생성. |
| changelog | Orca(onorca.dev)·Claude Code·Codex CLI·herdr 의 최근 릴리즈를 모아 버전별 한국어 요약으로 만들고 Orca 내장 브라우저 탭… | 없음 | "orca 업데이트 뭐 바뀌었어", "claude code 새 버전 뭐가 달라졌나", "codex cli 최근 릴리즈 요약" | itda-dev | — |
| claude-usage | 이 머신에 로그인된 Claude Code 계정의 사용량(5시간·7일 창 사용률, 모델별 주간 한도, 리셋 시각, 플랜)을 저장된 OAuth 자격증명으로 직접 조… | 없음 | "claude 사용량 얼마나 남았어", "클로드 코드 한도 확인해줘", "5시간 창 리셋 언제야" | itda-dev | 본 스킬은 Claude Code 구독 사용량 전담 — itda-dev:codex-usage 는 Codex CLI 사용량. |
| cloudflare-tunnel | 포트포워딩 없이 Cloudflare Tunnel로 내 서비스(원격 데스크톱·SSH·웹)를 안전하게 노출/접근하도록 셋업하는 스킬입니다. | CLOUDFLARE_API_TOKEN | "집 윈도우에 RDP 터널 깔아줘", "cloudflare tunnel로 ssh 열어줘", "터널 라우트에 access 걸어줘" | itda-dev | — |
| codex-usage | 이 머신에 로그인된 Codex CLI(ChatGPT 계정)의 사용량(5시간·주간 창 사용률, 리셋 시각, 플랜)을 ~/.codex/auth.json 토큰으로 직… | 없음 | "codex 사용량 얼마나 남았어", "코덱스 한도 확인해줘", "codex 리셋 언제야" | itda-dev | 본 스킬은 Codex CLI 구독 사용량 전담 — itda-dev:claude-usage 는 Claude Code 사용량. |
| harness | 하네스를 구성합니다. | 없음 | "하네스 구성해줘", "하네스 구축해줘", "하네스 설계 도와줘" | itda-dev | — |
| orca-coach | Orca(온오르카) 기능 활용 코치. | 없음 | "orca로 뭘 할 수 있어?", "이 작업에 orca 기능 뭐 쓰면 좋을까?", "orca 활용 아이디어 줘" | itda-dev | — |
| windows-parallels-lab | macOS Parallels Desktop 의 자동화 전용 Windows 11 클론(win11-parlab)을 제어해 Windows 실런타임(COM/Office… | 없음 | "윈도우에서 실행해서 확인해줘", "hwpx 가 한글에서 안 깨지는지 봐줘", "게스트 화면 캡처해줘" | itda-dev | 되돌릴 수 있는 클론 전담 — 되돌릴 수 없는 실머신 조작은 다루지 않는다. |
| blog-seo | 네이버 SearchAd API로 블로그 SEO용 블루키워드를 발굴하는 스킬입니다. | NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_SEARCHAD_ACCESS_KEY, NAVER_SEARCHAD_CUSTOMER_ID, NAVER_SEARCHAD_SECRET_KEY | "블루키워드 찾아줘", "경쟁 적은 키워드 분석해줘", "블로그 키워드 포화지수 확인해줘" | itda-doc | — |
| design-core | 브랜드 디자인을 고르고(getdesign 표준 DESIGN.md 카탈로그 차용), 만들고(한국·자사 브랜드 저작), 검증·조회해 웹·PPTX·DOCX·XLSX… | 없음 | "스포티파이 톤으로 디자인 골라줘", "우리 브랜드 디자인 시스템 정의해줘", "이 DESIGN.md 검증해줘" | itda-doc | — |
| docx-design | 콘텐츠 마크다운과 수치 데이터로 디자인된 Word 문서(.docx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는… | 없음 | "NovaTech 연차보고서 docx로 만들어줘", "이 프리셋으로 워드 보고서 디자인해줘", "md 내용으로 디자인된 워드 문서 생성" | itda-doc | — |
| draft-post | 블로그·보고서·기획서·보도자료·뉴스레터를 도메인 맞춤 인터뷰로 초안 작성하는 스킬입니다. | 없음 | "블로그 글 써줘", "보고서 초안 작성해줘", "기획서 만들어줘" | itda-doc | 본 스킬은 초안 생성 전담(AI 흔적 사전의 정본: itda-doc:human-tone) — 이미 작성된 글의 AI 흔적 제거·문체 후처리는 itda-doc:human-tone 이 맡고, 본 스킬은 발행·송부를 하지 않습니다. |
| html-report | 마크다운 보고서·분석 결과·회의 정리를 연차보고서 수준의 단일 파일 HTML 문서로 렌더링하는 스킬입니다. | 없음 | "이 보고서 HTML 파일로 만들어줘", "컨설팅 보고서 스타일로 전략 검토 문서 만들어줘", "공공기관 제출용 개조식 보고서 HTML로" | itda-doc | 본 스킬은 보고서형 HTML 렌더 전담 — 아침 브리핑 페이지는 itda-work:morning-brief. |
| human-tone | 이미 작성된 한국어 사무 글(보고서·메일·기획서·공지)에서 AI 흔적을 걷어내는 후처리 스킬입니다. | 없음 | "이 보고서 AI 같아", "메일 너무 딱딱해", "사람이 쓴 것처럼 고쳐줘" | itda-doc | 본 스킬은 완성된 글의 후처리 검수 전담(AI 흔적 사전 가드 정본) — itda-doc:draft-post 는 처음부터 초안을 쓰는 생성 단계이며, 같은 글에 두 스킬을 겹쳐 적용하지 않습니다. |
| hwpx | 한글 HWP·HWPX 문서 스킬입니다. | 없음 | "이 HWP 파일 읽어줘", "이 한글 양식 채워줘", "빈칸 채워줘" | itda-doc | — |
| imagekit | 이미지 조회·리사이즈·여백 크롭·DPI 변경·포맷 변환·회전을 단일 CLI로 처리하는 스킬입니다. | 없음 | "이미지 크기 줄여줘", "여백 크롭해줘", "PNG를 JPG로 변환해줘" | itda-doc | — |
| pdf-context-refinery | PDF를 LLM 컨텍스트·지식베이스용 구조화 마크다운으로 정제하는 스킬입니다. | 없음 | "PDF를 마크다운으로 변환해줘", "이 교재를 지식베이스로 만들어줘", "PDF OCR 정리해줘" | itda-doc | — |
| pptx-design | 콘텐츠 마크다운과 수치 데이터로 16:9 PPTX 발표자료를 크로스플랫폼(macOS/Linux, Office 불필요)으로 신규 생성하는 스킬입니다. | 없음 | "삼성전자 주가전망 ppt 만들어줘", "이 DESIGN.md로 발표자료 디자인해줘", "md 내용으로 슬라이드 덱 생성" | itda-doc | — |
| pptx-shrink | 기존 PPTX 파일의 용량을 줄이는 스킬입니다. | 없음 | "이 ppt 용량 줄여줘", "발표자료가 커서 메일로 못 보내", "pptx 압축해줘" | itda-doc | 본 스킬은 기존 pptx 용량 축소 전담 — itda-doc:imagekit 은 낱개 이미지, itda-doc:pptx-design 은 덱 신규 생성. |
| xlsx-design | 수치 데이터로 디자인된 Excel 통합문서(.xlsx)를 크로스플랫폼(macOS/Linux/Windows, Office 불필요)으로 신규 생성하는 스킬입니다. | 없음 | "NovaTech 실적 엑셀로 만들어줘", "이 프리셋으로 대시보드 시트 디자인해줘", "데이터로 디자인된 xlsx 생성" | itda-doc | 본 스킬은 디자인된 xlsx 신규 생성 전담 — 이미 있는 xlsx 의 수식 캐시값 재계산은 itda-data:xlsx-recalc. |
| artifact-packager | 정적 웹 산출물(Claude 아티팩트·HTML·dist 폴더)을 실행 가능한 단일 실행파일 또는 zip 으로 패키징해 내 PC 에서 띄우는 스킬입니다. | 없음 | "아티팩트 패키징해줘", "실행파일로 묶어줘", "이 산출물 실행파일로 만들어줘" | itda-egg | — |
| daiso | 다이소 상품 검색·가격·매장 찾기·매장별 재고·진열 위치를 로그인 없이 조회하는 스킬입니다. | 없음 | "다이소 수납박스 검색", "이 상품 강남역 근처 다이소에 재고 있어?", "강남 다이소 매장 찾아줘" | itda-egg | — |
| font-guide | 문서(docx/pptx/pdf)에 어울리는 무료 한글 폰트를 추천하고 자동 설치해주는 스킬입니다. | 없음 | "PPT용 폰트 추천해줘", "보고서에 어울리는 폰트 알려줘", "Pretendard 설치해줘" | itda-egg | — |
| hangul-pron | 영어 문장·중국어 병음·일본어 가나를 한글로 소리 나는 대로 적어 준다 — "레츠 겥 드레ˇ스드", "{워=3}먼 {츠=1#} {판=4o} 빠", "{고=v}항… | 없음 | "레츠 겥 드레ˇ스드", "{워=3}먼 {츠=1#} {판=4o} 빠", "{고=v}항 오 타{베=v}요ー" | itda-egg | — |
| kurly | 마켓컬리 상품 검색·가격·상세를 로그인 없이 조회하는 스킬입니다. | 없음 | "마켓컬리에서 우유 얼마야?", "컬리에서 딸기 검색해줘", "이 상품 품절인지 보고 링크도 줘" | itda-egg | — |
| music-dl | 음원을 내려받아 Apple Music(Music.app)용으로 태깅·정품 앨범아트·가사까지 채워 넣고, 기존 로컬 음원의 결손도 보정한다. | 없음 | "이 노래 받아줘", "유튜브에서 음악 다운받아줘", "앨범아트 넣어줘" | itda-egg | — |
| naver-blog-post | HTML 원고를 네이버 블로그 스마트에디터에 네이티브 컴포넌트(소제목·인용구 6종·구분선 8종·소스코드·표·이미지+캡션·목록)로 붙여넣고, 공개 범위를 확인한… | 없음 | "네이버 블로그에 올려줘", "블로그 글 발행해줘", "이 원고 네이버 블로그에 비공개로 올려줘" | itda-egg | — |
| parcel-tracker | Track Korean parcel deliveries by waybill number over plain HTTP (stdlib only, no browser… | 없음 | "택배 조회해줘", "한진택배 537444594341 어디쯤이야", "CJ대한통운 운송장 조회해줘" | itda-egg | — |
| u-library | 대전공공도서관(u-library.kr)의 대출현황·대출연장·소장자료 검색과 한밭도서관 희망도서 신청을 aside 브라우저 자동화로 수행한다. | 없음 | "빌린 책 언제까지야", "도서관 대출 연장해줘", "반납일 알려줘" | itda-egg | — |
| airport-airline-stats | 인천공항 항공사별 월별 통계(운항·여객·화물)를 LLM-친화 JSON으로 조회하는 스킬입니다. | 없음 | "2025년 3월 인천공항 항공사별 통계 알려줘", "지난달 국제선 여객기 통계 뽑아줘", "T1 터미널 항공사별 운항 횟수 조회해줘" | itda-gov | — |
| bai-notice | 감사원 통합공지 게시판을 내부 JSON API로 수집해 마크다운 표로 정리하는 스킬입니다. | 없음 | "감사원 공지 확인해줘", "감사원 통합공지 최근 10건 보여줘", "감사원에서 채용 공고 찾아줘" | itda-gov | — |
| court-auction | 대법원 법원경매정보(courtauction.go.kr)의 부동산 매각공고·사건·물건을 조회하는 스킬입니다. | 없음 | "오늘 서울중앙지법 경매 공고 보여줘", "2024타경100001 사건 진행상황 알려줘", "강남 아파트 5억 이하 유찰 1회 물건 찾아줘" | itda-gov | — |
| customs-notice | 관세청 공지사항 게시판을 수집해 마크다운 표로 정리하는 스킬입니다. | 없음 | "관세청 공지 확인해줘", "관세청 공지사항 최근 10건 보여줘", "관세청에서 원산지 관련 공지 찾아줘" | itda-gov | — |
| dart | 금융감독원 DART 전자공시 API로 기업 정보를 수집하는 스킬입니다. | DART_API_KEY | "삼성전자 재무제표 조회해줘", "경쟁사 직원수 알려줘", "사업보고서 비교해줘" | itda-gov | — |
| ecos | 한국은행 ECOS API로 거시경제 지표를 조회하는 스킬입니다. | ECOS_API_KEY | "GDP 추이 알려줘", "금리 환율 정리해줘", "100대 경제지표 확인해줘" | itda-gov | — |
| fss-docs | 금융감독원 공통업무자료 게시판을 수집해 마크다운 표로 정리하는 스킬입니다. | 없음 | "금감원 업무자료 확인해줘", "금융감독원 공통업무자료 이번 주 것만 보여줘", "금감원에서 사모펀드 자료 찾아줘" | itda-gov | — |
| fuel-price | 오피넷(한국석유공사) 주유소 평균 유가 조회 스킬입니다. | OPINET_API_KEY | "오늘 기름값 얼마야", "서울 휘발유 가격", "이달 전국 경유 월평균" | itda-gov | 본 스킬은 평균 유가 조회 전담 — 주유소 위치·최저가 검색, 유류비 정산 단가·공지문 생성은 하지 않고, 환율은 itda-work:exchange-rate 가 맡습니다. |
| funding | 한국 정부·공공기관 지원사업 공고를 5개 소스에서 전수 수집해 내 아이템 프로필로 3분류 판정하는 스킬입니다. | KO_DATA_API_KEY | "정부 지원사업 전수조사 해줘", "우리 아이템에 맞는 지원사업 찾아줘", "창업 지원사업 모집 공고 알려줘" | itda-gov | — |
| g2b | 조달청 나라장터 G2B API로 정부 입찰 공고를 검색·조회하는 스킬입니다. | KO_DATA_API_KEY | "나라장터 입찰공고 검색해줘", "조달청 공고 확인해줘", "소프트웨어 개발 입찰 공고 찾아줘" | itda-gov | — |
| kosis | 통계청 KOSIS 국가통계포털 API로 공식 통계를 검색·탐색·조회하는 스킬입니다. | KOSIS_API_KEY | "인구 통계 알려줘", "KOSIS 통계표 검색해줘", "이 통계표 분류·항목 코드 찾아줘" | itda-gov | — |
| realty-deals | 국토교통부 부동산 실거래 12개 유형을 단일 인터페이스로 수집하는 스킬입니다. | KO_DATA_API_KEY | "최근 6개월 강남구 아파트 실거래 전부 받아줘", "분당 연립다세대 매매 2025년 데이터 CSV로 줘", "강서구 오피스텔 전월세 조회해줘" | itda-gov | 본 스킬은 국토교통부 실거래 raw 수집 전담 — 가격지수·평균/중위 파생 통계는 itda-gov:realty-price-stats, 미분양·인허가·청약은 itda-gov:realty-supply. |
| realty-jeonse-gap | 매매와 전월세 실거래를 단지·전용면적 기준으로 조인해 전세가율과 갭 투자 후보를 스크리닝하는 스킬입니다. | KO_DATA_API_KEY | "강남구 아파트 전세가율 80% 넘는 단지 찾아줘", "분당 연립다세대 갭 3천만 이하 목록 뽑아줘", "전세가율 임계값 스크리닝 해줘" | itda-gov | — |
| realty-meta | itda-gov 부동산 스킬팩의 색인·도움말 가이드입니다. | KOSIS_API_KEY, KO_DATA_API_KEY, RONE_API_KEY | "부동산 스킬 목록 보여줘", "itda-gov 도움말", "실거래가 스킬 뭐 있어" | itda-gov | — |
| realty-price-stats | 한국부동산원 R-ONE 가격지수·전월세전환율과 realty-deals raw 데이터 기반 파생 통계를 제공하는 스킬입니다. | KO_DATA_API_KEY, RONE_API_KEY | "강남구 아파트 주간 가격지수 6개월치 가져와줘", "분당구 최근 3개월 평균·중위 매매가 통계 보여줘", "전월세전환율 추이 조회해줘" | itda-gov | 본 스킬은 R-ONE 가격지수와 파생 통계 전담 — 실거래 원본 행 수집은 itda-gov:realty-deals(derive 의 입력), 공급·청약 지표는 itda-gov:realty-supply. |
| realty-supply | KOSIS 주택 공급 지표(미분양·인허가·착공·준공·입주)와 청약홈 청약 통계를 수집하는 스킬입니다. | KOSIS_API_KEY, KO_DATA_API_KEY | "올해 강남구 아파트 미분양 추이 보여줘", "2024년 전국 인허가·착공·준공 통계 가져와줘", "최근 청약 경쟁률 높은 단지 목록 보여줘" | itda-gov | 본 스킬은 KOSIS 공급 지표·청약 통계 전담 — 개별 실거래 원본은 itda-gov:realty-deals, 가격지수·파생 통계는 itda-gov:realty-price-stats. |
| taxlaw | 국세법령정보시스템(taxlaw.nts.go.kr)에서 세법 법령·세법해석례(예규)·판례/결정례·상담사례를 검색하고 전문(全文)을 조회하는 스킬입니다. | 없음 | "양도소득세 예규 찾아줘", "부가가치세 판례 검색해줘", "국세기본법 제18조 보여줘" | itda-gov | 본 스킬은 국세법령정보시스템 세법 조회(법령·예규·판례) 전담 — 위하고·홈택스 등 세무 포털 자동화·장부 수집은 범위 밖(현재 지원 스킬 없음)이며, 세법 밖 일반 법령은 다루지 않습니다. |
| mmaa-welfare | 군인공제회 복지포털 스냅샷 Q&A — 복지부조(신규가입·출산 축하금, 재해위로금, 축하기념품)· 회원콘도 이용안내·유익한 정보(취업·창업·시니어)를 출처 URL… | 없음 | "출산축하금 얼마?", "군인공제회 콘도 이용 조건", "재해위로금 대상" | itda-org-mmaa | — |
| web-automation | [현재 실행 경로 없음 — 노하우 참고용] hyve 앱 폐기로 이 스킬이 전제하는 hyve web_browse MCP 가 없다. | 없음 | "위하고 분개장 수집해줘", "수임처 회계 들어가서 장부 뽑아줘", "홈택스 사업자 상태 조회해줘" | itda-org-taxhero | 본 스킬은 WEHAGO·HOMETAX 사이트 특화 레시피 전담 — 세법 조문·예규 조회는 itda-gov:taxlaw. |
| brain-audit | 업무DB(뇌)를 독립 재검수하는 스킬입니다. | 없음 | "뇌가 낡았는지", "이 업무DB 검수해줘", "뇌 아직 최신이야?" | itda-research | — |
| brain-build | 회사 공유폴더의 비정형 문서 무더기(워드·엑셀·PPT·PDF·txt 수십~수백 개)를 근거 추적 가능한 업무DB(뇌)로 만드는 빌드 스킬입니다. | 없음 | "이 폴더를 업무DB로 만들어줘", "공유폴더 정리해서 뇌로 만들어줘", "이 문서들 근거 추적 가능하게 정리" | itda-research | — |
| brain-fixture | 함정(모순·버전지옥·규정이중화·손상파일 등)을 의도적으로 심은 가상 회사의 연습용 데이터셋 폴더(워드·엑셀·PPT·PDF·txt·csv)를 만드는 스킬입니다. | 없음 | "연습용 가상 폴더 만들어줘", "함정 심은 모의 데이터셋 생성해줘", "헬스케어 회사 연습 데이터 만들어줘" | itda-research | — |
| brain-ingest | 업무DB(뇌)에 새 문서를 증분 적재하는 스킬입니다(v1.1). | 없음 | "뇌에 새 문서 반영해줘", "이 견적서들 업무DB에 넣어줘", "업무DB 업데이트" | itda-research | — |
| brain-scribe | 업무DB(뇌)의 규약을 배워 규약 준수 문서를 생성하는 스킬입니다(v1.5). | 없음 | "추정", "이번 달 견적서 규약대로 써줘", "회의록 양식으로 초안 만들어줘" | itda-research | — |
| ground-check | 1차 출처 강제 인용과 독립 검증으로 환각·hedge 표현을 절차로 차단하는 리서치 스킬입니다. | 없음 | "팩트체크해서 보고서 써줘", "출처 확인해서 정리해줘", "1차 소스만 써서 정리해줘" | itda-research | — |
| investigate | 경쟁 가설과 반증 실험으로 근본 원인을 체계적으로 조사하는 스킬입니다. | 없음 | "왜 이렇게 느리지?", "이 에러 원인이 뭐야?", "원인 분석해줘" | itda-research | — |
| market-scan | 외부 시장·산업 자료를 찾아 의사결정용으로 구조화하는 시장조사 스킬입니다. | DART_API_KEY, ECOS_API_KEY, EXA_API_KEY, KOSIS_API_KEY, NAVER_SEARCH_CLIENT_ID, NAVER_SEARCH_CLIENT_SECRET, PERPLEXITY_API_KEY, SERPER_API_KEY, TAVILY_API_KEY | "OO 시장 조사해줘", "시장 규모랑 경쟁사 알려줘", "신사업 진입할 만한지 분석해줘" | itda-research | — |
| meeting-reliability | 회의 녹취·기록에서 "확인 / 확인 필요 / 예외"를 근거와 함께 정확히 가르는 신뢰성 검수 스킬입니다. | 없음 | "확인 / 확인 필요 / 예외", "이 녹취 결정사항 표로 정리해줘", "회의록 신뢰성 검수해줘" | itda-research | — |
| kis-auth | 한국투자증권 KIS OpenAPI 인증을 설정·진단하는 스킬입니다. | KIS_ACCOUNT_NUMBER, KIS_APP_KEY, KIS_APP_SECRET | "KIS 인증 설정해줘", "한국투자증권 앱키 등록해줘", "모의투자 계정 설정해줘" | itda-stocks | — |
| kis-backtest | KIS 과거 시세로 트레이딩 전략을 백테스트하는 스킬입니다. | KIS_APP_KEY, KIS_APP_SECRET | "이 전략 백테스트 해줘", "골든 크로스 성과 분석해줘", "최근 1년 데이터로 백테스팅 돌려줘" | itda-stocks | — |
| kis-market | KIS OpenAPI로 시세·시장 데이터·계좌 잔고를 조회하는 스킬입니다. | KIS_APP_KEY, KIS_APP_SECRET | "삼성전자 현재 시세 조회해줘", "내 KIS 포트폴리오 보여줘", "내 계좌 잔고 확인해줘" | itda-stocks | — |
| kis-order | 모의/실전 KIS 주식 주문을 default-deny 실전 주문 게이트·감사 로그와 함께 실행하는 스킬입니다. | KIS_APP_KEY, KIS_APP_SECRET | "모의투자로 카카오 5주 매수해줘", "실전으로 삼성전자 매도 실행해줘", "모의 잔고 전량 매수해줘" | itda-stocks | — |
| kis-strategy | 트레이딩 전략을 설계하고 매수·매도·관망 시그널을 생성하는 스킬입니다. | KIS_APP_KEY, KIS_APP_SECRET | "골든크로스 전략 시그널 만들어줘", "RSI 14로 매매 시그널 생성해줘", "볼린저밴드 전략 만들어줘" | itda-stocks | — |
| market-events | 코스피/코스닥 사이드카·서킷브레이커(CB) 발동을 빠르게 감지하는 스킬입니다 (PoC). | KIS_APP_KEY, KIS_APP_SECRET | "오늘 사이드카 발동했어?", "서킷브레이커 걸렸는지 확인해줘", "시장조치 감시 시작해줘" | itda-stocks | — |
| stock-us | 미국 증시 분석·시황 아티클 작성 스킬입니다. | 없음 | "오늘 미국 증시 프리마켓 현황 알려줘", "NVDA 기술적 분석해줘", "이 PDF 시황 자료로 블로그 글 써줘" | itda-stocks | — |
| surge-data | ETF 급등 감지를 위한 데이터 수집 스킬입니다. | KIS_ACCOUNT_NUMBER, KIS_APP_KEY, KIS_APP_SECRET | "지금 ETF 시장 스냅샷 수집해줘", "야간 미국 ETF 변동 데이터 가져와줘", "나스닥 지수·VIX·환율 매크로 지표 조회해줘" | itda-stocks | — |
| eatery-trend | 여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다. | NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_SEARCHAD_ACCESS_KEY, NAVER_SEARCHAD_CUSTOMER_ID, NAVER_SEARCHAD_SECRET_KEY | "제주 요즘 뜨는 맛집", "성수에서 트렌디한 국밥", "지금 핫한 디저트 뭐야" | itda-travel | — |
| flight-search | Google Flights 공개 검색으로 항공권을 조회·비교하는 스킬입니다. | 없음 | "인천에서 도쿄 6월 26일 항공권 찾아줘", "ICN-NRT 다음 달 최저가 언제야?", "9월에 7일 일정 왕복으로 제일 싼 출발일은?" | itda-travel | — |
| hotel-search | 같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾… | 없음 | "신라호텔 서울 8월 1일부터 2박 최저가 비교해줘", "이 호텔 부킹이랑 아고다 중 어디가 싸? 예약 링크도 줘", "제주 그랜드하얏트 이번 주말 가격이랑 싼 날짜 알려줘" | itda-travel | — |
| place-finder | 카카오맵 기준으로 근처 장소를 목적별로 찾아주는 스킬입니다. | 없음 | "강남역 근처 술집 찾아줘", "홍대에서 와이파이 되는 카페", "제주공항 근처 숙소" | itda-travel | — |
| train-ktx | KTX 고속열차를 검색하고 예약하는 스킬입니다. | KORAIL_PASSWORD, KORAIL_USER_ID | "다음 주 금요일 서울에서 부산 KTX 찾아줘", "수서에서 부산 가는 표 있어?", "오후 2시 이후 동대구 가는 표 있어?" | itda-travel | 본 스킬은 KTX·옛 SRT 전 고속열차 예매 전담 — itda-travel:train-srt 는 통합 안내 스텁이며 기능을 갖지 않습니다. |
| train-srt | SRT는 2026-09-01부터 KTX로 통합되어 이 스킬은 기능을 갖지 않습니다. | 없음 | "수서에서 부산 SRT 찾아줘", "SRT 예약해줘", "SRT 계정 확인해줘" | itda-travel | 본 스킬은 통합 안내 전용 스텁 — 실제 검색·예약은 itda-travel:train-ktx 가 전담합니다. |
| aside-browser-mcp | Aside(사용자의 로그인 세션·쿠키·메모리를 쥔 AI 브라우저)를 MCP 도구 exec·repl·memory_search 로 다루는 규율 정본입니다. | 없음 | "슬랙 확인해줘", "지메일에서 찾아줘", "지금 열려 있는 탭 봐줘" | itda-web | 본 스킬은 Aside MCP 커넥터 전담 — 로그인 불요 정적 페이지는 itda-web:web-reader. |
| blog-reader | 네이버 블로그의 글 목록·본문·댓글 트리·블로그 내 검색·전역 키워드 검색을 로그인 없이 읽는 스킬입니다. | 없음 | "네이버 블로그 글 가져와줘", "블로그 본문이랑 댓글 보여줘", "이 블로그 최근 7일 글 보여줘" | itda-web | 본 스킬은 네이버 블로그(blog.naver.com) 전담 — 그 밖의 한국 웹페이지·EUC-KR·WAF 정적 페이지는 itda-web:web-reader, 범용 키워드 검색은 itda-web:web-search. |
| web-reader | WebFetch가 못 다루는 한국 웹페이지(EUC-KR/CP949·쿠키 인증·WAF 차단 정적 페이지)를 마크다운·JSON으로 가져오는 폴백 스킬입니다. | 없음 | "이 한국 사이트 읽어줘", "EUC-KR 페이지 가져와줘", "403 뜨는 페이지 가져와줘" | itda-web | 본 스킬은 정적 페이지 단건 페치·추출 전담 — 네이버 블로그는 itda-web:blog-reader, 키워드 검색은 itda-web:web-search, JS 렌더·로그인·봇 차단 페이지는 실제 브라우저 경로(itda-web:aside-browser-mcp — Aside, 없으면 Claude in Chrome 등). |
| web-scout | 정보원 정찰 스킬 — "이 정보가 어느 사이트 어디에 있고 어떻게 꺼내야 싸게 되는가"를 실측해 기억합니다. | 없음 | "이 정보가 어느 사이트 어디에 있고 어떻게 꺼내야 싸게 되는가", "이 사이트들 뉴스 어디서 어떻게 읽나 정리해줘", "정보원 등급표 만들어줘" | itda-web | — |
| web-search | 여러 검색엔진으로 웹을 한 번에 검색해 정규화된 결과 목록(제목·URL·발췌)을 돌려주는 스킬입니다. | EXA_API_KEY, NAVER_SEARCH_CLIENT_ID, NAVER_SEARCH_CLIENT_SECRET, PERPLEXITY_API_KEY, SERPER_API_KEY, TAVILY_API_KEY | "파이썬 입문 자료 검색해줘", "AI 규제 관련 최신 기사 찾아줘", "경쟁사 가격 정책 정보 모아줘" | itda-web | 본 스킬은 검색엔진 결과 목록(제목·URL·발췌) 수집 전담 — 찾은 URL 의 본문 추출은 itda-web:web-reader, 네이버 블로그는 itda-web:blog-reader 이며, 시장조사 보고서·팩트체크는 다루지 않습니다. |
| calendar | itda-hyve 에 등록한 네이버·아이클라우드·직접 입력(CalDAV 주소) 계정의 캘린더에서 일정을 조회·검색·추가·수정·삭제하고 빈 시간을 찾아주는 스킬입… | 없음 | "내일 3시 회의 추가해줘", "이번 주 일정 보여줘", "다음 주에 1시간 빈 시간 찾아줘" | itda-work | 본 스킬은 일정 조회·추가·수정·삭제·빈 시간 탐색 전담 — 아침 브리핑 페이지(오늘 일정+미회신 메일 한 장)는 itda-work:morning-brief, 메일 읽기·발송은 itda-work:email. |
| email | itda-hyve 에 등록한 네이버·Gmail·다음/카카오·아이클라우드·회사 메일 계정으로 메일을 찾고 읽고 보내는 스킬입니다. | 없음 | "메일 보내줘", "받은편지함 확인해줘", "naver 메일 읽어줘" | itda-work | 본 스킬은 메일 찾기·읽기·발송 전담 — 아침 브리핑 페이지(오늘 일정+미회신 요청 한 장)는 itda-work:morning-brief, 일정 조회·추가는 itda-work:calendar. |
| exchange-rate | 원화 기준 일별·월 평균 기준 환율을 조회하는 스킬입니다. | 없음 | "오늘 달러 환율 알려줘", "이번 달 엔화 평균 환율 보여줘", "EUR 환율 조회해줘" | itda-work | — |
| hour-slice | 하고 싶은 업무 개선은 큰데 "오늘 1시간 안에 뭘 만들 수 있지?"가 막막한 사람을 위해, 문제를 ~1시간 안에 눈에 보이는 결과가 나오는 한 조각으로 잘라… | 없음 | "오늘 1시간 안에 뭘 만들 수 있지?", "이거 너무 큰데 뭐부터 해볼까", "1시간 안에 만들 수 있는 걸로 줄여줘" | itda-work | — |
| miniskill-forge | 매번 같은 작업에 긴 프롬프트를 다시 쓰고 사람마다·날마다 결과가 달라지는 반복 업무를, Claude Cowork에서 한 마디로 부르는 재사용 미니스킬(SKIL… | 없음 | "이거 매번 자동으로 했으면", "내 반복 업무를 스킬로 만들어줘", "맨날 같은 프롬프트 다시 쓰기 싫어" | itda-work | — |
| morning-brief | 오늘 일정과 미회신 메일을 모아 아침 브리핑 HTML 한 장을 그리는 스킬입니다(calendar·email 소스). | 없음 | "아침 브리핑 만들어줘", "/morning-brief", "Sections: 환율" | itda-work | 본 스킬은 아침 브리핑 페이지 전담 — itda-work:calendar 는 일정, itda-work:email 은 메일, itda-doc:html-report 는 보고서 HTML. |
| stakeholder-map | 프로젝트 이해관계자별로 역할·요청할 것·받을 것·소통 방식과, 그 사람이 일을 시작하기 전에 알아야 할 선행 전달물(톤·형식·분량·필수 문구 같은 제약 조건)을… | 없음 | "이해관계자 정리해줘", "협업 지도 만들어줘", "누구한테 뭘 먼저 넘겨야 하지" | itda-work | — |
| task-brief | 모호한 일상 요청을 에이전트에 던지기 전, 작업 범위·검증 방법·완료 정의 3요소를 채운 브리프 한 장으로 다듬는 스킬입니다. | 없음 | "작업 브리프 짜줘", "이 요청 다듬어줘", "브리프로 정리해줘" | itda-work | — |
| time-audit | 캘린더 실적(완료한 일정)을 모아 카테고리·난이도별 소요 시간, 주별 추이, 병목 후보를 결정론 스크립트로 집계하는 업무 시간 감사 스킬입니다. | 없음 | "내 시간 어디에 쓰는지 분석해줘", "업무 시간 매핑해줘", "시간 감사 해줘" | itda-work | — |
| weather-here | 현재 위치 또는 지정 지역의 날씨를 한국어로 빠르게 조회하는 스킬입니다. | 없음 | "날씨 알려줘", "지금 여기 날씨 어때", "부산 날씨 알려줘" | itda-work | — |
| work-find | 비개발자 Cowork 사용자가 AI로 풀 업무를 함께 찾고 구체화하는 인터뷰 스킬입니다. | 없음 | "업무 찾기 도와줘", "자동화 아이디어가 없어요", "Cowork로 뭘 해볼까" | itda-work | — |
| work-pilot | 작성된 제안서·과제 신청서(또는 아이디어)를 Claude Cowork 안에서 실제로 돌아가는 파일럿으로 만드는 스킬입니다. | 없음 | "Cowork 가능 / 수동 브릿지 / 시스템 연동(IT 과제)", "신청서 다음 뭘 해야 해?", "이거 실제로 만들어보자" | itda-work | — |
| work-plan | 사용자의 요청을 적합한 itda-* 스킬 조합으로 매핑해 실행 계획을 만드는 스킬입니다. | 없음 | "계획 세워줘", "어떤 itda 스킬로 풀 수 있어?", "work-find 메모 받았는데 어떻게 진행해" | itda-work | — |
| work-proposal | 업무 개선·AI 과제 아이디어를 제안서 뼈대(프로젝트명·한 줄 소개·해결하려는 문제·AI 해결 방안(프로세스 포함)·핵심 기능·활용 계획 및 기대 효과)로 구조… | 없음 | "제안서 써줘", "AX 과제 신청서 도와줘", "이 아이디어 제안서로 정리해줘" | itda-work | — |
| work-redesign | 내 업무를 태스크→행동 단위로 쪼개고 가치×AI개입 4분면(인간이 지킬 것/AI로 증강할 것/ 일부러 유지할 것/자동화할 것)으로 매핑해, 위임 계획과 상시 컨… | 없음 | "내 업무 구조화해줘", "뭘 AI한테 맡겨야 할지 모르겠어", "업무 지도 만들어줘" | itda-work | — |

## 스킬 디렉토리 경로 매핑

ground-check sanity check 시 아래 경로로 존재 여부를 확인합니다.

```
aspect-sentiment      → itda-data/skills/aspect-sentiment/
biz-redact            → itda-data/skills/biz-redact/
cs-intent             → itda-data/skills/cs-intent/
data-ask              → itda-data/skills/data-ask/
data-audit            → itda-data/skills/data-audit/
data-compass          → itda-data/skills/data-compass/
data-prep             → itda-data/skills/data-prep/
data-verify           → itda-data/skills/data-verify/
iaa-builder           → itda-data/skills/iaa-builder/
pii-redact            → itda-data/skills/pii-redact/
synthetic-data        → itda-data/skills/synthetic-data/
xlsx-recalc           → itda-data/skills/xlsx-recalc/
changelog             → itda-dev/skills/changelog/
claude-usage          → itda-dev/skills/claude-usage/
cloudflare-tunnel     → itda-dev/skills/cloudflare-tunnel/
codex-usage           → itda-dev/skills/codex-usage/
harness               → itda-dev/skills/harness/
orca-coach            → itda-dev/skills/orca-coach/
windows-parallels-lab → itda-dev/skills/windows-parallels-lab/
blog-seo              → itda-doc/skills/blog-seo/
design-core           → itda-doc/skills/design-core/
docx-design           → itda-doc/skills/docx-design/
draft-post            → itda-doc/skills/draft-post/
html-report           → itda-doc/skills/html-report/
human-tone            → itda-doc/skills/human-tone/
hwpx                  → itda-doc/skills/hwpx/
imagekit              → itda-doc/skills/imagekit/
pdf-context-refinery  → itda-doc/skills/pdf-context-refinery/
pptx-design           → itda-doc/skills/pptx-design/
pptx-shrink           → itda-doc/skills/pptx-shrink/
xlsx-design           → itda-doc/skills/xlsx-design/
artifact-packager     → itda-egg/skills/artifact-packager/
daiso                 → itda-egg/skills/daiso/
font-guide            → itda-egg/skills/font-guide/
hangul-pron           → itda-egg/skills/hangul-pron/
kurly                 → itda-egg/skills/kurly/
music-dl              → itda-egg/skills/music-dl/
naver-blog-post       → itda-egg/skills/naver-blog-post/
parcel-tracker        → itda-egg/skills/parcel-tracker/
u-library             → itda-egg/skills/u-library/
airport-airline-stats → itda-gov/skills/airport-airline-stats/
bai-notice            → itda-gov/skills/bai-notice/
court-auction         → itda-gov/skills/court-auction/
customs-notice        → itda-gov/skills/customs-notice/
dart                  → itda-gov/skills/dart/
ecos                  → itda-gov/skills/ecos/
fss-docs              → itda-gov/skills/fss-docs/
fuel-price            → itda-gov/skills/fuel-price/
funding               → itda-gov/skills/funding/
g2b                   → itda-gov/skills/g2b/
kosis                 → itda-gov/skills/kosis/
realty-deals          → itda-gov/skills/realty-deals/
realty-jeonse-gap     → itda-gov/skills/realty-jeonse-gap/
realty-meta           → itda-gov/skills/realty-meta/
realty-price-stats    → itda-gov/skills/realty-price-stats/
realty-supply         → itda-gov/skills/realty-supply/
taxlaw                → itda-gov/skills/taxlaw/
mmaa-welfare          → itda-org-mmaa/skills/mmaa-welfare/
web-automation        → itda-org-taxhero/skills/web-automation/
brain-audit           → itda-research/skills/brain-audit/
brain-build           → itda-research/skills/brain-build/
brain-fixture         → itda-research/skills/brain-fixture/
brain-ingest          → itda-research/skills/brain-ingest/
brain-scribe          → itda-research/skills/brain-scribe/
ground-check          → itda-research/skills/ground-check/
investigate           → itda-research/skills/investigate/
market-scan           → itda-research/skills/market-scan/
meeting-reliability   → itda-research/skills/meeting-reliability/
kis-auth              → itda-stocks/skills/kis-auth/
kis-backtest          → itda-stocks/skills/kis-backtest/
kis-market            → itda-stocks/skills/kis-market/
kis-order             → itda-stocks/skills/kis-order/
kis-strategy          → itda-stocks/skills/kis-strategy/
market-events         → itda-stocks/skills/market-events/
stock-us              → itda-stocks/skills/stock-us/
surge-data            → itda-stocks/skills/surge-data/
eatery-trend          → itda-travel/skills/eatery-trend/
flight-search         → itda-travel/skills/flight-search/
hotel-search          → itda-travel/skills/hotel-search/
place-finder          → itda-travel/skills/place-finder/
train-ktx             → itda-travel/skills/train-ktx/
train-srt             → itda-travel/skills/train-srt/
aside-browser-mcp     → itda-web/skills/aside-browser-mcp/
blog-reader           → itda-web/skills/blog-reader/
web-reader            → itda-web/skills/web-reader/
web-scout             → itda-web/skills/web-scout/
web-search            → itda-web/skills/web-search/
calendar              → itda-work/skills/calendar/
email                 → itda-work/skills/email/
exchange-rate         → itda-work/skills/exchange-rate/
hour-slice            → itda-work/skills/hour-slice/
miniskill-forge       → itda-work/skills/miniskill-forge/
morning-brief         → itda-work/skills/morning-brief/
stakeholder-map       → itda-work/skills/stakeholder-map/
task-brief            → itda-work/skills/task-brief/
time-audit            → itda-work/skills/time-audit/
weather-here          → itda-work/skills/weather-here/
work-find             → itda-work/skills/work-find/
work-pilot            → itda-work/skills/work-pilot/
work-plan             → itda-work/skills/work-plan/
work-proposal         → itda-work/skills/work-proposal/
work-redesign         → itda-work/skills/work-redesign/
```
