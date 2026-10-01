# ECOS 한국은행 경제통계 — 요청 URL 과 collect_econ.py 상세

제안서의 경제 환경 분석에 필요한 거시경제 지표를 수집합니다.
요청은 itda-hyve 의 `http_request` 가 보내고, 스크립트(`collect_econ.py`)는 저장한 응답을 `--input` 으로 읽어
오류 판정·전량 대조·정리만 한다. 호출 절차의 정본은 `SKILL.md`, 공용 규약은 `references/netbridge.md` 다.

## 인증키

1. https://ecos.bok.or.kr/api/ 회원가입 → 인증키 신청(가입 시 즉시 발급)
2. itda-hyve GUI 시크릿 탭에 `ECOS_API_KEY` 로 등록 — URL **경로**의 `{{secret:ECOS_API_KEY}}` 자리에 채워진다

> 한국은행 공개 시험 키 `sample` 은 최대 10건만 준다. 이 스킬의 실측 픽스처(`tests/fixtures/*_sample.json`)가 그것으로 받은 응답이다.

## 요청 URL (경로 방식)

```
https://ecos.bok.or.kr/api/<서비스>/{{secret:ECOS_API_KEY}}/json/kr/<시작행>/<끝행>/<선택 세그먼트…>/
```

| 명령 | 서비스 | 선택 세그먼트 | 예 |
|------|--------|--------------|----|
| `key` | KeyStatisticList | — | `…/KeyStatisticList/{{secret:ECOS_API_KEY}}/json/kr/1/1000/` |
| `search` | StatisticSearch | 통계표코드/주기/시작/끝[/항목1[/항목2…]] | `…/StatisticSearch/{{secret:ECOS_API_KEY}}/json/kr/1/1000/901Y009/A/2020/2024/` |
| `items` | StatisticItemList | 통계표코드 | `…/StatisticItemList/{{secret:ECOS_API_KEY}}/json/kr/1/1000/901Y009/` |
| `tables` | StatisticTableList | — | `…/StatisticTableList/{{secret:ECOS_API_KEY}}/json/kr/1/1000/` |
| `word` | StatisticWord | 용어(한글 그대로) | `…/StatisticWord/{{secret:ECOS_API_KEY}}/json/kr/1/1000/기준금리/` |

- 한 요청은 1000행(`1/1000`, `1001/2000`, …)씩 받는다. 응답의 `list_total_count` 가 전체 행 수다.
- 응답 본문에는 행 범위가 없다 — 저장 이름 끝의 `-r<시작행>.json` 이 그 파일의 범위다. 스크립트는 이 이름과 받은 행 수로
  범위가 1행부터 빈틈없이 이어지는지, 겹치거나 같은 범위가 두 번 들어오지 않았는지, 모든 파일의 `list_total_count` 가 같은지
  (다르면 다른 질의가 섞였다) 보고, 빈 범위를 `missing_ranges` 로 정확히 알려 준다.
- 한글 용어는 경로에 **그대로** 쓴다. itda-hyve 가 한 번 인코딩한다. 미리 `%EA%B8%B0…` 로 인코딩해 넣어도 같은 URL 로 나간다
  (2026-09-30 실측 — `final_url` 동일, 이중 인코딩 없음). `%25` 가 보이면 이중 인코딩이다.
- 응답 크기(2026-09-30 `sample` 실측 기준 list_total_count): 100대 지표 101 · 통계표 목록 844 · 901Y009 세부항목 1,743 · 901Y009 월간 2020~2024 60.

## 서브커맨드

| 커맨드 | 입력(서비스) | 핵심 데이터 |
|-------|-------------|-----------|
| `key` | KeyStatisticList | GDP, 금리, 환율, 물가, 통화량 등 100대 지표 |
| `search` | StatisticSearch | 시점별 수치 데이터(값이 숫자가 아닌 행은 빼고 수를 `skipped_non_numeric` 에 남김) |
| `items` | StatisticItemList | 항목코드 조회 (search 전 확인용) |
| `tables` | StatisticTableList | 통계표코드 확인 |
| `word` | StatisticWord | 경제 용어 공식 정의 |

```bash
python3 scripts/collect_econ.py search --input ecos/search-901Y009-A-2020-2024-r1.json
python3 scripts/collect_econ.py search --input ecos/search-731Y003-D-20240102-20240131-0000003-r1.json   # 항목코드도 이름에
python3 scripts/collect_econ.py --format table items --input ecos/items-901Y009-r1.json ecos/items-901Y009-r1001.json
```

Windows: `python3` → `py -3`

## 주기별 날짜 형식

| 주기 | 코드 | 날짜 형식 | 예시 |
|------|------|---------|------|
| 연간 | year (A) | `YYYY` | `2024` |
| 반기 | semi (S) | `YYYYS1` | `2024S1` |
| 분기 | quarter (Q) | `YYYYQ1` | `2024Q1` |
| 월간 | month (M) | `YYYYMM` | `202401` |
| 일간 | day (D) | `YYYYMMDD` | `20240101` |

## 자주 쓰는 통계표코드

| 지표 | 코드 | 주기 | 주요 항목코드 |
|------|------|------|-----------|
| 소비자물가지수 (CPI) | `901Y009` | M, A | (총지수 등 품목별) |
| GDP (원계열, 실질) | `200Y106` | Q, A | |
| GDP (원계열, 명목) | `200Y105` | Q, A | |
| 환율 (원/달러 종가) | `731Y003` | D | `0000003` (원/달러 종가) |
| 한국은행 기준금리·여수신금리 | `722Y001` | D | |
| 국민소득 (명목, 연간) | `200Y113` | A | |

> 코드를 모르면 `items`(StatisticItemList)로 확인하세요.

## 에러 코드

| 코드 | 의미 | 조치 |
|------|------|------|
| INFO-100 | 인증키 유효하지 않음 | itda-hyve 시크릿 탭의 `ECOS_API_KEY` 확인 |
| INFO-200 | 데이터 없음 | 날짜/항목코드 변경 |
| ERROR-100 | 필수값 누락 | stat_code, period, 날짜 확인 |
| ERROR-101 | 주기와 날짜 형식 불일치 | 위 날짜 형식 표 참조 |
| ERROR-400 | 검색범위 초과 (60초 TIMEOUT) | 조회 범위 축소 |
| ERROR-602 | 과도한 호출 → 이용 제한 | 잠시 후 재시도 |
