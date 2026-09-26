# ECOS 한국은행 경제통계 — collect_econ.py 상세

제안서의 경제 환경 분석에 필요한 거시경제 지표를 수집합니다.

## API 키 설정

```bash
# 1. https://ecos.bok.or.kr/api/ 회원가입 → 인증키 자동 부여
# 2. 작업 폴더 루트(예: outputs/)에 .env 파일 생성 후 키 추가
#    ECOS_API_KEY=발급받은_인증키
# (로컬 CLI 전용: claude config set env.ECOS_API_KEY "키" 또는 셸 환경변수도 가능)
```

> 테스트: API 키 대신 `sample`을 사용하면 최대 10건까지 테스트 조회 가능

## 서브커맨드

| 커맨드 | 역할 | 핵심 데이터 |
|-------|------|-----------|
| `key` | 100대 주요 경제지표 | GDP, 금리, 환율, 물가, 통화량 등 |
| `search` | 통계 데이터 조회 | 시점별 수치 데이터 |
| `items` | 세부항목 코드 확인 | 항목코드 조회 (search 전 확인용) |
| `tables` | 전체 통계표 목록 | 통계표코드 확인 |
| `word` | 통계용어사전 | 경제 용어 공식 정의 |

## 사용법

```bash
# 100대 주요 경제지표 (제안서 경제 환경 개요에 바로 사용)
python3 scripts/collect_econ.py key
python3 scripts/collect_econ.py --format table key

# 소비자물가지수 (CPI) 연간 조회
python3 scripts/collect_econ.py search --stat 901Y009 --start 2020 --end 2024

# 환율 (원/달러 종가) 일간 조회 — 731Y003은 일간(D) 주기, 종가 항목코드 0000003
python3 scripts/collect_econ.py search --stat 731Y003 --period day --start 20240102 --end 20240131 --item1 0000003

# 항목코드 확인 (search 전에 어떤 코드를 써야 하는지 확인)
python3 scripts/collect_econ.py items --stat 901Y009

# 통계표 목록 (통계표코드 찾기)
python3 scripts/collect_econ.py tables --count 50

# 통계용어사전 (제안서에서 경제 용어 정의 인용)
python3 scripts/collect_econ.py word --word "GDP디플레이터"
python3 scripts/collect_econ.py --format table word --word "소비자동향지수"
```

Windows:
```powershell
py -3 scripts/collect_econ.py key
```

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

> 코드를 모르면 `items` 명령으로 확인하세요.

## 에러 코드

| 코드 | 의미 | 조치 |
|------|------|------|
| INFO-100 | 인증키 유효하지 않음 | ECOS_API_KEY 확인 |
| INFO-200 | 데이터 없음 | 날짜/항목코드 변경 |
| ERROR-100 | 필수값 누락 | stat_code, period, 날짜 확인 |
| ERROR-101 | 주기와 날짜 형식 불일치 | 위 날짜 형식 표 참조 |
| ERROR-400 | 검색범위 초과 (60초 TIMEOUT) | 조회 범위 축소 |
| ERROR-602 | 과도한 호출 → 이용 제한 | 잠시 후 재시도 |
