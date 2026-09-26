# KOSIS 국가통계포털 — collect_stats.py 상세

제안서/사업계획서에 필요한 국가 공식 통계를 수집합니다.

## API 키 설정

```bash
# 1. https://kosis.kr 회원가입
# 2. https://kosis.kr/openapi/ 에서 서비스 신청 (자동 승인) → 인증키 발급
#    - 서비스 소개: https://kosis.kr/openapi/introduce/introduce_01List.do
# 3. 작업 폴더 루트(예: outputs/)에 .env 파일 생성 후 키 추가
#    KOSIS_API_KEY=발급받은_인증키
# (로컬 CLI 전용: claude config set env.KOSIS_API_KEY "키" 또는 셸 환경변수도 가능)
```

> **주의**: KOSIS 인증키는 Base64 형태로 끝에 `=` 패딩 문자가 포함됩니다.
> 복사 시 `=`가 잘리면 "유효하지않은 인증KEY" 오류가 발생합니다.
> 키 전체를 정확히 복사했는지 확인하세요.

**API 제한**: 분당 1,000회 호출, 1회 최대 40,000셀

## 서브커맨드

| 커맨드 | 역할 | 핵심 데이터 |
|-------|------|-----------|
| `search` | 키워드로 통계표 검색 | orgId, tblId, 통계표명 |
| `data` | 통계자료 조회 | 시점별 수치 데이터 |

## 사용법

```bash
# 키워드로 통계표 검색
python3 scripts/collect_stats.py search --keyword "인구"
python3 scripts/collect_stats.py search --keyword "GDP" --count 20

# 통계자료 조회 (최근 3년)
python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --recent 3

# 기간 지정 조회
python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --start 2020 --end 2024

# 월별 데이터
python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --period month --start 202301 --end 202412

# 특정 항목/분류
python3 scripts/collect_stats.py data --org-id 101 --tbl-id DT_1B04005N --item "T2+T3" --obj1 "11"

# 테이블 형식
python3 scripts/collect_stats.py --format table data --org-id 101 --tbl-id DT_1B04005N --recent 3
```

Windows:
```powershell
py -3 scripts/collect_stats.py search --keyword "인구"
```

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
