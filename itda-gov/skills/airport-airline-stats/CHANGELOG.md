# Changelog — airport-airline-stats

## [1.0.4] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [1.0.3] — 2026-07-26 (이슈 #1280)

### Changed

- compatibility 라벨 "Designed for Claude Cowork. Python 3.10+" → "Claude Code & Cowork. Python 3.10+" (Claude Code 에서도 동작하므로 배타 표기 제거).

## [1.0.2] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [1.0.1] — 2026-05-28

### Improvements

- 프로젝트 지침 재구성에 맞춰 삭제된 SPEC 링크를 제거하고 코드·테스트·CHANGELOG를 구현 기준으로 명시.

## [1.0.0] — 2026-05-27

### 초기 출시

- 인천국제공항공사(airport.kr) 공개 웹페이지에서 항공사별 월별 통계(운항·여객·화물) 조회.
- 2단계 HTTP 워크플로우: navigation 페이지 GET → WMONID 쿠키 시드 → 데이터 페이지 GET.
- Windows User-Agent + Accept-Language: ko-KR + Referer 단계별 자동 지정.
- layout 토큰 `636f5f6b6f40403635314040666e637431` (정적, 라이브 falsification 확인).
- Python 3.10+ stdlib only (urllib + http.cookiejar + html.parser). 외부 의존성 0개.

### 인자

- `--year YYYY --month MM` (필수): 조회 연/월
- `--route {all,I,D}`: 국제선/국내선/전체
- `--airline-type {all,Y,N}`: 여객기/화물기/전체
- `--terminal {all,P01,P03}`: T1/T2/전체
- `--schedule {all,0,1}`: 정기/부정기/전체
- `--airline IATA`: 236 항공사 코드 화이트리스트
- `--format {json,csv,table}`: 출력 포맷 (기본 json)
- `--list-airlines`: 지원되는 항공사 코드 목록

### 출력

- 항공사별 도착/출발/합계 × 운항/여객/화물 9 metrics
- 천단위 콤마 자동 제거 → `int` 변환
- 합계(`summary.total`) + 전년대비 증감률(`summary.yoy_change`) 별도 분리
- 모든 포맷에 디스클레이머 고정 부착

### 오류 분류

- `future_month`: 미래 월 사전 차단 (HTTP 호출 없음)
- `invalid_month`: 13월 등 잘못된 입력
- `unknown_airline_code`: 화이트리스트 외 코드
- `session_seed_failed`: 1단계 호출 실패
- `fetch_failed`: 2단계 호출 실패
- `no_data`: 응답 정상이나 데이터 0행

### 라이브 검증

- 2026-05-27 라이브 프로브: `--year 2025 --month 3 --route I` → 106 항공사 행 + 합계/전년대비 추출 성공
- 컬럼 9개(화물도 합계 포함) 확정
- WMONID 쿠키 미포함 시 HTTP 302 무한 리다이렉트 확인

### 테스트

- mock 단위 테스트: 헤더 단언, 2단계 워크플로우, HTML 파싱, summary 분류, 천단위 콤마, 미래월 차단, 잘못된 항공사 코드 거부, 3 포맷 × 디스클레이머 부착
- 라이브 스모크 (opt-in, `ITDA_AIRPORT_SMOKE=1`): 2025-03 국제선 결과 ≥ 50 단언

### 알려진 한계

- 인천공항 단일 공항 (김포·김해·제주 등 한국공항공사 14개 지방공항 미지원)
- 응답 캐싱 미적용
- 월 범위 조회 미지원
- 사이트 마크업 변경 시 일시 동작 불가
