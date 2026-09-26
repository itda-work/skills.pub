# Changelog — itda-work/weather-here

## [0.12.5] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.12.4] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.12.3] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.12.2] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.12.1] — 2026-05-19

### Improvements

- **SKILL.md body 다이어트 — context 토큰 -37%.** 3,630 → 2,298 chars
  (≈2,269 → 1,436 토큰). Progressive Disclosure L2(스킬 호출 시 적재)
  비용 절감. [HARD] "Claude 라우팅 가이드" 규칙 1~5·Prerequisites·
  frontmatter description은 **무손실 보존**. 제거: 스킬구조 ASCII
  트리·테스트실행 섹션(개발자 정보 — repo 담당), 압축: 출력예시(detail
  블록→1줄)·데이터소스표(→산문)·제약사항. 기능·동작 무변경(메타 전용,
  118 tests·라이브 무영향). 측정 근거: gist 응답은 이미 ~56토큰으로
  극소, 데이터 가공은 100% Python 내부(raw JSON model 미유입) →
  유일한 토큰 레버가 SKILL.md body임을 실측 확인 후 적용.
- **UA 버전 드리프트 영구 해소**: `http_util._USER_AGENT`에서 버전
  토큰 제거(`weather-here-skill/0.11.0` → `weather-here-skill`).
  독립 Agent(evaluator-active) 재검증이 0.11.0↔SKILL 0.12.1 드리프트
  적발 — 버전 동기화 대신 토큰 제거로 향후 재드리프트 차단(무기능·
  무REQ 영향, UA는 요청 식별용). 단일 UA 출처(http_util) 확인.

## [0.12.0] — 2026-05-19 (SPEC-WEATHER-HERE-001 v0.4.0)

### Breaking Changes

- **날씨 데이터소스 기상청(KMA) apihub → Open-Meteo Forecast(무키) 전환.**
  `KMA_API_KEY`·apihub 활용신청 전제 **완전 폐기**(무키 복원). KMA가
  오퍼레이션별 활용신청(getUltraSrtNcst+getVilageFcst 각각) 마찰 +
  getVilageFcst raw 403 외부 차단으로 강수확률(POP)이 라이브 미통과한
  문제를, 무키 Open-Meteo로 해소.

### Why (결정 배경)

- v0.3.0이 Open-Meteo를 버린 사유는 **지오코더**(지역명→좌표, 한국
  부정확: 서울 0건·부산 155km)였지 **Forecast가 아니었음**. v0.4.0은
  검증된 좌표 권위표(`kma_points` lat/lon, 시청 <1km 라이브 실증)+
  이름 정규화를 **존속**시키고 그 좌표로 무키 Open-Meteo Forecast 호출
  → 정확성 유지 + 키·활용신청 0 + POP 무키 회복.

### New / Changed

- 신규: `openmeteo_client.py`(Open-Meteo Forecast current+daily 단일
  콜, urllib), `wmo_codes.py`(WMO weather_code → 한국어).
- 개정: `region_resolver.py` 반환 `(nx,ny,label)` → `(lat,lon,label)`.
  `weather_here.py` Open-Meteo 분기로 재작성(KMA_API_KEY/403 분기 제거).
- 폐기: `kma_grid.py`·`kma_client.py`·`kma_codes.py`·`oversea_client.py`
  (+테스트). `kma_points.py`는 좌표 권위표로 존속(lat/lon 사용).
- SKILL.md v0.11.0→0.12.0(무키·Open-Meteo로 본문 전면 정정),
  GUIDE.md 사전 준비 "없음(무키)"로 정정.

### 측정 / 라이브 검증

- pytest **118 passed**, ruff clean, py_compile OK, KMA 잔재 grep 0.
- 오케스트레이터 Phase 4 [HARD] 라이브 falsification **통과**: 부산
  "구름 조금, 강수확률 2%"·제주 "흐림, 68% — 비 올 듯해요"·수원→
  권선구·해운대구·한영(Busan)·IP 시나리오 A·평양 graceful 전부 정상.
  좌표 독립 km대조 서울 0.35·부산 0.32·대구 0.38·제주 3.26km(SPEC
  §4.5 문서값 재현, v0.2.0 부산 155km 거짓양성 구조적 불가). Open-Meteo
  좌표 정확 반영·해외 라벨(REQ-020) 검증.

## [0.11.0] — 2026-05-19 (SPEC-WEATHER-HERE-001 v0.3.x)

### Breaking Changes

- **날씨 데이터소스 Open-Meteo → 기상청(KMA) apihub 전면 교체.**
  `KMA_API_KEY` 환경변수 + apihub 활용신청이 신규 전제(구 "무키" 폐기).
  외부 지오코더(Open-Meteo·Nominatim) 완전 제거 — 한국 부정확 실증
  (서울 0건·부산 155km·대구 334km 북한). 위치 해석을 기상청 권위
  좌표표(`kma_points.py` 260점) + 이름 정규화 + 위경도→격자 LCC 변환
  으로 재설계. `weather_client.py`·`wmo_codes.py` 폐기.
- apihub는 **오퍼레이션별 활용신청** 필요: `getUltraSrtNcst`(실황)
  **및** `getVilageFcst`(예보)를 각각 신청(키 동일, 승인 별개 — 실증).

### New Features

- 신규 모듈: `region_resolver`(17 시·도+한영 별칭·일반구 prefix 집계·
  대표점 결정), `kma_grid`(LCC dfs_xy_conv), `kma_client`(실황+예보),
  `kma_codes`(SKY/PTY 한국어), `oversea_client`(해외 best-effort +
  "(해외·대략·미검증)" 라벨).
- 사용자 가이드 `GUIDE.md` 신설 — 사전 준비(2개 오퍼레이션 활용신청).

### Bug Fixes (v0.3.1 — run 단계 결함 수정)

- **[CRITICAL] LCC +1 체계 편향**: `int(x+1.5)` → 정본 `int(x+0.5)`.
  정적표 권위표 대비 정확일치 **0/260 → 257/260**(±1 초과 0건, 독립
  실증). 시나리오 A 격자 정확성 구조적 해소(v0.2.0 부산 155km형
  거짓양성 재발 방지).
- **[HIGH] getVilageFcst 403 무음 삼킴 → 거짓성공(exit 0)**: 403/키
  미설정을 `{"error":"forbidden"}`, fcst만 403이면 `fcst_forbidden`
  플래그로 구분. 활용신청 안내(전체) / 부분결과+안내(fcst만)로 분기
  (REQ-021 정합).
- `kma_codes`: PTY=0·SKY 미수신/미지 → "강수 없음"(graceful, '알 수
  없음'은 PTY까지 미지일 때만).
- `getVilageFcst` 발표 후 ~10분 가용 보정.
- 자기충족 테스트 제거: LCC 역검증 ±1 단독 허용 → 정확일치 ≥257/260.
- `_USER_AGENT` 버전 통일(0.9.0 잔존 → 0.11.0).

### 측정

- 테스트 52 → **135 passed**(신규 모듈 + 회귀 + fcst 403 분기), ruff
  clean, py_compile OK. LCC 정확일치 0/260 → 257/260(독립 실증).
- 위치 해석 라이브 검증: 부산→부산광역시·서울→서울특별시·수원→경기도
  수원시권선구·IP→Seongnam권역·평양→graceful 미수록(전부 정확).
- 잔여 [HARD] 게이트: getVilageFcst resultCode=00 라이브(SKY/POP)는
  사용자 활용신청 + apihub 응답 정상화 후 검증 — SPEC In Progress.

## [0.10.0] — 2026-05-19 (SPEC-WEATHER-HERE-001 v0.2.0)

### Breaking Changes

- 기본 출력이 상세 대시보드 → **한 줄 gist**로 변경. 기본 출력에서
  기온·체감·습도·풍속·최고/최저 제거. 종전 상세 블록은 `--detail`
  옵션으로만 제공(하위호환: 옵션 추가, 동작 보존).

### New Features

- `--detail` 플래그 추가. 기온·체감·습도·강수량·풍속 + 오늘 최고/최저
  상세 블록을 opt-in으로 출력.

### Improvements

- 기본 출력 형식: `{지역} · 오늘 {상태}, 강수확률 {N}% — {거친 한마디}`.
  거친 한마디는 강수확률 임계값으로 산출(≥60 "비 올 듯해요" /
  ≥30 "비 올 수 있어요" / 그 외 "비 올 가능성 낮아요"). 처방적 결정
  (우산 챙겨라 등)은 내리지 않고 대략의 가늠만 제공.
- 라이브 실측: 기본 출력 199 B(8줄) → **82 B(1줄), -59%**.
  "아침 현관 '비 와?'" 순간의 마찰 제거에 맞춘 설계(SPEC §REQ-006 개정).
- 강수확률 누락 시 확률·한마디 graceful 생략(None 미노출).

### 설계 근거

기술·데이터 나열이 아니라 "스킬을 쓰는 사람의 불편"에서 출발 — 사용자는
대략 "오늘 여기 비 올 듯한가"만 알면 되고, 우산 결정은 본인이 한다.
테스트 52 passed(+4 gist/detail/_rain_gloss), ruff clean, 라이브 A/B/--detail 검증.
