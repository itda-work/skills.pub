# K-Startup 정부 지원사업 API 가이드

## 개요

중소벤처기업부 K-Startup 통합공고 시스템의 공공데이터 API 명세다.
`funding` 스킬에서 이 API 는 **K-Startup 소스 수집의 최적화 경로**이며,
전수 커버리지의 보증 경로는 공개 페이지 크롤이다(`scripts/kstartup_api.py` → 실패 시 크롤 폴백,
사유는 stderr 로 명시 고지).

- **데이터 출처**: 공공데이터포털 (data.go.kr), 데이터셋 15125364
- **인증**: `KO_DATA_API_KEY` — **선택**. 없으면 크롤 경로로 동작한다
- **키 해석**: `shared/env_loader.py` 규약 (`os.environ` > `~/.claude/settings.json` > `.env` 계열).
  키는 로그·에러·URL 어디에도 출력하지 않는다(인코딩 변형까지 마스킹)
- **응답 형식**: JSON
- **데이터 특성**: K-Startup(www.k-startup.go.kr) 통합공고 기준
- **CLI 표면 정본**: [cli-contract.md](cli-contract.md) — 인자·exit code·jsonl/manifest 스키마

## API 키 발급

1. [공공데이터포털](https://www.data.go.kr) 회원가입
2. [창업진흥원_K-Startup(사업소개,사업공고,콘텐츠 등)_조회서비스](https://www.data.go.kr/data/15125364/openapi.do) 활용신청
3. 마이페이지 → 개발계정 → 일반 인증키(Decoding) 복사

## 엔드포인트

Base URL: `https://nidapi.k-startup.go.kr/api/kisedKstartupService/v1`

| 서비스 | 엔드포인트 | 설명 |
|-------|-----------|------|
| 지원사업 공고 | `/getAnnouncementInformation` | 통합공고 지원사업 공고 검색 |
| 통합공고 사업 현황 | `/getBusinessInformation` | 연도별 사업 현황 조회 |

> 참고: data.go.kr 활용신청 페이지에 표기된 `apis.data.go.kr/B552735/...` 게이트웨이 URL은 이 서비스에서 동작하지 않으며, 실제 호출은 K-Startup 도메인(`nidapi.k-startup.go.kr`)으로 이루어진다.

## 요청 파라미터 (공통)

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `serviceKey` | Y | API 인증키 (Decoding 키, URL 인코딩 후 전송) | - |
| `returnType` | Y | 응답 형식 | `json` |
| `page` | N | 페이지 번호 (기본 1) | `1` |
| `perPage` | N | 페이지당 건수 (기본 10) | `100` |

## 검색 조건 파라미터 (cond 방식)

### 지원사업 공고 (`getAnnouncementInformation`)

| 파라미터 | 설명 | 연산자 |
|---------|------|-------|
| `cond[biz_pbanc_nm::LIKE]` | 공고명 키워드 | 부분 일치 |
| `cond[rcrt_prgs_yn::EQ]` | 모집 진행 여부 | `Y`=모집 중 |
| `cond[supt_biz_clsfc::LIKE]` | 지원 분야 | 부분 일치 |
| `cond[pbanc_rcpt_bgng_dt::GTE]` | 접수 시작일 하한 | YYYYMMDD |
| `cond[pbanc_rcpt_end_dt::LTE]` | 접수 종료일 상한 | YYYYMMDD |

### 통합공고 사업 현황 (`getBusinessInformation`)

| 파라미터 | 설명 | 연산자 |
|---------|------|-------|
| `cond[supt_biz_titl_nm::LIKE]` | 사업명 키워드 | 부분 일치 |
| `cond[biz_yr::EQ]` | 사업 연도 | 정확 일치 |

## 응답 필드 (지원사업 공고)

| 필드명 | 설명 |
|-------|------|
| `biz_pbanc_nm` | 공고명 |
| `supt_biz_clsfc` | 지원 분야 (사업화, R&D, 창업교육 등) |
| `aply_trgt` | 신청 대상 |
| `pbanc_rcpt_bgng_dt` | 접수 시작일 (YYYYMMDD) |
| `pbanc_rcpt_end_dt` | 접수 종료일 (YYYYMMDD) |
| `rcrt_prgs_yn` | 모집 진행 여부 (Y/N) |
| `detl_pg_url` | 상세 페이지 URL |
| `tot_supt_amt` | 지원 총액 (만원) |

## 응답 필드 (통합공고 사업 현황)

| 필드명 | 설명 |
|-------|------|
| `biz_yr` | 사업 연도 |
| `supt_biz_titl_nm` | 사업명 |
| `biz_category_cd` | 사업 분류 코드 (예: `cmrczn_Tab1`) |
| `supt_biz_chrct` | 사업 특성 |
| `supt_biz_intrd_info` | 사업 소개 |
| `biz_supt_trgt_info` | 지원 대상 정보 |
| `biz_supt_ctnt` | 지원 내용 |
| `biz_supt_bdgt_info` | 예산·지원규모 정보 |
| `detl_pg_url` | 상세 페이지 URL |

## 지원 분야 분류

| 코드 | 설명 |
|------|------|
| 사업화 | 창업 아이템 사업화 지원 |
| R&D | 기술 연구·개발 지원 |
| 창업교육 | 창업가 교육·훈련 |
| 멘토링·컨설팅 | 전문가 멘토링 |
| 인프라 | 시설·공간·장비 지원 |
| 행사·네트워크 | 창업 행사 및 네트워킹 |
| 융자 | 저금리 융자 지원 |
| 글로벌 | 해외 진출 지원 |

## CLI 사용 예시

이 API 는 `survey_crawl.py list kstartup` 안에서 자동으로 쓰인다 — 별도 API 전용 서브커맨드는 없다.

```bash
# 키가 해석되면 API 우선, 실패 시 크롤 폴백 (사유 stderr 고지)
python3 "$SKILL_DIR/scripts/survey_crawl.py" list kstartup -o survey.jsonl

# 키가 없으면 곧바로 크롤 경로 (정상 기본 경로 — 고지 없음)
```

Windows: `python3` → `py -3`

> `collect_funding.py search/overview` 는 v1.0.0 에서 제거됐다(CHANGELOG 참조).
> 키워드 검색 대신 전수 수집 후 전건 검토가 정본 워크플로다.

## 커버리지 정직성 (API 경로)

이 데이터셋은 등록순(최신 우선)이고 모집중 공고가 마감 이력 사이에 분산돼 있다.
따라서 API 경로는 최신 우선으로 스캔해 모집중 집합을 모은다:

| 상황 | manifest `stop_reason` | exit |
|---|---|---|
| 데이터셋 끝까지 스캔해 `totalCount` 로 소진 증명 | `api` | 0 (전수) |
| 최신 우선 무마감 페이지 연속으로 조기 종료 | `api-window` | 2 (partial) |

`api-window` 는 **최근 구간 커버리지**일 뿐이라 뒤늦게 재연장된 오래된 공고가 빠질 수 있다.
전수 보증은 크롤이 권위이며, **diff 는 `api-window` 회차를 근거로 GONE 을 단정하지 않는다.**
`reported_total` 은 전체 이력 건수(모집중 건수가 아니다).

401/403·200 위장 차단(CAPTCHA)은 크롤로 우회하지 않고 **exit 3(수동 전환)** 이다.

## 주의사항

1. **데이터 특성**: K-Startup 통합공고 기준. 개별 기관 공고는 미포함될 수 있어 기업마당 등으로 보강한다.
2. **모집 기간 종료**: `rcrt_prgs_yn=N`인 공고는 이미 마감.
3. **실시간성**: API 데이터는 K-Startup 시스템 기준으로 주기적 갱신.
4. **페이지당 최대 건수**: 일반적으로 100건. 전체 조회 시 페이징 필요.
5. **게이트웨이 URL 주의**: 활용신청 페이지의 `apis.data.go.kr/B552735/...` 는 이 서비스에서 동작하지 않는다.

## 워크플로우 예시: 자금 조달 계획

```
1. 프로필 확정 + 저장 경로 합의 (SKILL.md 0·0.5단계)
2. 전수 수집
   → survey_crawl.py list all -o <회차>/survey.jsonl --max-pages 70
3. run_manifest.json 으로 커버리지 판정 (partial 이면 한계 고지)
4. 전체 목록 제목 직접 검토 → 후보 선별 (grep 대체 금지)
5. 후보 상세·첨부 검증 (사용자 옵트인 후)
   → survey_crawl.py detail <source> <url...> --download-dir ... --merge-into ...
6. A/B/C 분류 보고서 + 우선순위 액션 + 한계 고지
7. 2~4주 뒤 재조사
   → survey_diff.py <직전 회차> <새 회차> --out new_items.jsonl --old-profile ... --new-profile ...
```
