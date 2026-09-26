# DART 전자공시시스템 — collect_company.py 상세

경쟁사 분석에 필요한 기업 공시 데이터를 수집합니다.

## API 키 설정

```bash
# 1. https://opendart.fss.or.kr 회원가입
# 2. 인증키 발급 (즉시 발급, 40자리)
# 3. 작업 폴더 루트(예: outputs/)에 .env 파일 생성 후 키 추가
#    DART_API_KEY=발급받은_인증키
# (로컬 CLI 전용: claude config set env.DART_API_KEY "키" 또는 셸 환경변수도 가능)
```

> **주의**: 인증키 복사 시 앞뒤 공백이나 줄바꿈이 포함되지 않도록 하세요.

## 서브커맨드

| 커맨드 | 역할 | 핵심 데이터 |
|-------|------|-----------|
| `search` | 회사명으로 고유번호 검색 | corp_code, 종목코드 |
| `info` | 기업개황 | 대표자, 업종, 설립일, 주소 |
| `finance` | 재무제표 주요계정 | 매출액, 영업이익, 당기순이익, 자산총계 |
| `employees` | 직원현황 | 직원수, 평균 근속연수, 평균 급여 |
| `profile` | 종합 (위 3개 한번에) | 기업개황 + 재무 + 직원 |

## 사용법

```bash
# 회사 검색 (부분 일치, 영문명/혼합검색 지원)
python3 scripts/collect_company.py search --name "삼성전자"
python3 scripts/collect_company.py search --name "삼성SDS"
python3 scripts/collect_company.py search --name "samsung sds"

# 기업개황
python3 scripts/collect_company.py info --corp-code 00126380

# 재무제표 주요계정 (2024년 사업보고서, 연결 기준)
python3 scripts/collect_company.py finance --corp-code 00126380 --year 2024

# 직원현황
python3 scripts/collect_company.py employees --corp-code 00126380 --year 2024

# 종합 프로필 (회사명으로 한번에 조회)
python3 scripts/collect_company.py profile --name "삼성전자" --year 2024

# 테이블 형식 출력
python3 scripts/collect_company.py --format table search --name "삼성"
```

Windows:
```powershell
py -3 scripts/collect_company.py search --name "삼성전자"
```

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--format` | json / table | json |
| `--api-key` | DART 인증키 직접 전달 | 환경변수 |
| `--year` | 사업연도 (2015~) | - |
| `--report` | annual/half/q1/q3 | annual |
| `--fs-div` | CFS(연결)/OFS(개별) | CFS |

## 출력 예시 (profile)

```json
{
  "status": "ok",
  "corp_code": "00126380",
  "corp_name": "삼성전자",
  "stock_code": "005930",
  "year": "2024",
  "company_info": {
    "ceo_nm": "한종희",
    "induty_code": "264",
    "est_dt": "19690113",
    "adres": "경기도 수원시 영통구 삼성로 129"
  },
  "financials": [
    {"account_nm": "매출액", "thstrm_amount": "258935488000000", "frmtrm_amount": "..."},
    {"account_nm": "영업이익(손실)", "thstrm_amount": "6567200000000", "frmtrm_amount": "..."}
  ],
  "employees": [
    {"fo_bbm": "DS부문", "sm": "51000", "avrg_cnwk_sdytrn": "12.5"}
  ]
}
```

## raw 호출 — 엔드포인트 disambiguation

`collect_company.py raw --endpoint <이름> --param k=v ...`로 미구현 엔드포인트를 직접 호출할 때,
이름이 비슷해 헷갈리는 것들 (모두 우리 `references/` 분류 가이드에 정본 명세 존재):

| 엔드포인트 | 한글명 | 비고 |
|-----------|--------|------|
| `fnlttSinglAcnt` | 단일회사 주요계정 | 약 30항목 (`finance` 기본) |
| `fnlttSinglAcntAll` | 단일회사 전체 재무제표 | 약 176항목 (`finance --detail`) |
| `pifricDecsn` | 유무상증자 결정 | 유상+무상 동시 |
| `piicDecsn` | 유상증자 결정 | 유상만 |
| `fricDecsn` | 무상증자 결정 | 무상만 |
| `irdsSttus` | 증자(감자) 현황 | 정기보고서 |
| `alotMatter` | 배당에 관한 사항 | 정기보고서 |
| `tesstkAcqsDspsSttus` | 자기주식 취득·처분 현황 | 정기보고서 |
| `accnutAdtorNmNdAdtOpinion` | 회계감사인 명칭·감사의견 | 정기보고서 |
| `lwstLg` | 소송 등의 제기 | 주요사항, `bgn_de`·`end_de` 필요 |
| `cvbdIsDecsn` | 전환사채권 발행결정 | 주요사항, 기간 필요 |
| `exbdIsDecsn` | 교환사채권 발행결정 | 주요사항, 기간 필요 |

> 정기보고서 계열은 `corp_code`·`bsns_year`·`reprt_code`(11011 사업 / 11012 반기 / 11013 1분기 / 11014 3분기),
> 주요사항 결정 계열은 `corp_code`·`bgn_de`·`end_de`(YYYYMMDD)를 요구합니다.
> 전체 80여 개 엔드포인트 명세는 상위 `references/` 6개 분류 가이드를 참고하세요.

## corpCode.xml 캐싱

`search`와 `profile` 명령은 DART 전체 기업 목록(corpCode.xml, ~20MB ZIP)을 다운로드합니다.
첫 실행 시 `.itda-skills/dart-corp-codes.xml`에 캐시하여 이후 재사용합니다.
캐시를 갱신하려면 해당 파일을 삭제하면 됩니다.

## 에러 코드

| 코드 | 의미 | 조치 |
|------|------|------|
| 000 | 정상 | - |
| 010 | 등록되지 않은 키 | API 키 확인 |
| 013 | 데이터 없음 | 연도/보고서 유형 변경 |
| 020 | 요청 제한 초과 | 잠시 후 재시도 |
