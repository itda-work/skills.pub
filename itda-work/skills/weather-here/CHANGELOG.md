# Changelog — itda-work/weather-here

## [0.15.0] — 2026-10-01 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 Open-Meteo 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 날씨도 itda-hyve 가 받는다** (규칙 `cowork-network-via-hyve`). 스크립트의 Open-Meteo 직접 호출(`openmeteo_client.fetch`)을 지웠다. 위치만 주고 실행하던 옛 호출(`weather_here.py 부산`)은 이제 exit 2 로 다음 할 일을 안내한다 — `--weather-request` 로 호출 인자를 받고, itda-hyve 가 저장한 응답을 `--weather-input` 으로 넘긴다(지역명 1회, 현재 위치 2회 호출).
- **BREAKING — `--weather-request` 출력** — 옛판은 `{"url","params"}` 였다. 이제 `{"status":"ok","call":{url,params,timeout_sec:50,save_dir?,save_as},"then":…}` 이고 `call` 을 그대로 `http_request` 에 보낸다. 저장 이름 `weather-here/openmeteo-<위도>_<경도>-<YYYYMMDDHHMM>.json`(KST).
- **BREAKING — 스크립트 직접 IP 조회 제거** — 로컬(Cowork 아님)에서 인자 없이 실행하면 ipapi.co·ipwho.is 를 직접 부르던 경로(`geo_locator.locate_by_ip`)와 Cowork 판별(`_in_cowork_sandbox`)을 지웠다. 위치 입력이 없으면 어디서든 exit 3 과 `location` 도구 안내다.
- **BREAKING — IP 서비스 응답을 위치로 받지 않는다** — `compatibility` 가 itda-hyve 0.10.4 이상이라 `location`(0.10.1+)이 늘 있다. `location` 이 실패하면 지역명을 안내하고 IP 서비스를 따로 부르지 않는다(사용자 IP 를 외부로 더 보내지 않는다). 그 규칙을 코드로도 지킨다 — `--geo-input` 에 ipapi.co·ipwho.is 응답(본문·응답 JSON 전체)을 주면 사유와 함께 exit 3 이다(W9 리뷰 m1). `ip_single`·`ipapi`·`ipwho` 출처와 `_extract_latlon` 을 지웠다.
- **BREAKING — 묵은 위치 파일 거부** — `location` 응답의 `as_of` 가 1시간 넘게 지났거나 미래면 exit 3(W9 리뷰 m2). `as_of` 가 없으면 대조하지 않는다. `…Z`(호스트 시간대 UTC 의 RFC3339)도 Python 3.10 에서 읽는다(W9 재확인 m1).
- **BREAKING — 날씨 파일 식별** — 저장 이름이 `openmeteo-<위도>_<경도>-<YYYYMMDDHHMM>.json`(`--weather-request` 가 정한 이름) 이어야 하고 이름의 좌표가 요청 좌표와 넷째 자리까지 같아야 한다. 응답 좌표 허용 차를 **0.5° → 0.1°**(격자 맞춤 실측 최대 0.053° — 리뷰 11점)로 줄였다 — 옛 값은 대전 파일을 세종·청주 등 7곳 이름으로 통과시켰다(W9 리뷰 M2). NaN·무한 좌표는 거부, 경도는 날짜변경선에서 접는다(m5). 예보 첫 날(`daily.time`)이 응답 시간대의 오늘이 아니면(자정을 넘긴 파일) 거부한다(m6).
- `then` 은 다음 명령의 위치 인자를 셸 인용해 싣고(`shlex.quote` — 공백·한글 경로), `<save_dir>/…` 대신 `--weather-input <저장한 파일>` 이다(m7). SKILL 에 Windows 경로는 작은따옴표로.
- hyve 층 판독(본문 그대로·응답 JSON 전체·실패 자리·HTTP 오류·절단)을 공용 `shared/hyve_input.py` 로 — `geo_locator.unwrap_response` 를 지웠다. 파일 없음 사유 문구가 "입력 파일이 없습니다" 로 바뀌었다.
- Open-Meteo 를 계속 쓰는 판단을 `references/open-meteo-decision.md` 에 남겼다(스킬 판 표기는 0.12.0 — 초판은 SPEC 판 0.4.0 으로 잘못 적었다, m9) — `api.open-meteo.com/robots.txt` 가 `Disallow: /` 이나 공개 무키 API 호스트의 색인 차단으로 보고, 요청 1건당 1회 조회는 크롤링이 아니라는 사용자 결정(2026-10-01). 기각한 대안(기상청 교체·보류)과 bai-notice(W10 — 사이트 내부 API 만 골라 막음)와의 차이를 함께 적었다.

### Added

- `--location-request [--save-dir DIR]` — itda-hyve `location` 인자(`save_as` = `weather-here/location-<YYYYMMDDHHMM>.json`)를 낸다 — 위치 파일 이름도 스크립트가 정한다(W9 리뷰 m2).
- `--save-dir DIR` — `--weather-request`·`--location-request` 의 `save_dir`. itda-hyve 가 쓸 **호스트** 절대 경로를 받는다: `/Users/…`·`C:\…`·`C:/…`·`\\서버\…`(Cowork 의 리눅스 파이썬은 Windows 경로를 상대 경로로 본다 — W10 M1). 상대 경로는 exit 2.
- `--weather-input` 의 **묵은 파일 거부** — 관측 시각(`current.time` + `utc_offset_seconds`)이 3시간 넘게 지났거나 1시간 넘게 미래면 exit 1. 시각이 없으면 거부한다.
- 실측 픽스처 `openmeteo-36.3471_127.3866-202610010127.json`(2026-10-01 itda-hyve 로 받은 원본 — 이름이 곧 저장 이름 계약). Windows 콘솔(cp949) stdout·stderr 테스트, SKILL 예시 JSON ↔ 출력 대조, 배포형 맨 프로세스 테스트(publish 의 shared 주입 계산을 그대로 써서 scripts 를 복사해 돈다), 경도 축·이웃 지역·offset 없음·미래 경계·`then` 인용 테스트(W9 리뷰 m4). 테스트 임시 폴더는 회차 끝에 지운다.
- SKILL Step 2 에 itda-hyve 가 없을 때(설치 안내 후 멈춤 — 지역명을 묻지 않는다)·`location` 없는 옛 판(업데이트 안내)·Cowork 연결 폴더 없음(연결 요청 후 멈춤) 분기(m3). `invalid_input` 은 메시지가 "이미 있다" 일 때만 재사용 규칙.

### Fixed

- **`--detail` 풍속 단위** — Open-Meteo 기본 풍속 단위는 km/h 인데(`current_units.wind_speed_10m`, 2026-10-01 실측) "m/s" 를 붙여 3.6배로 표시했다. 응답의 단위로 m/s 로 환산한다(요청은 바꾸지 않는다). 단위를 모르면 "정보 없음".

### Removed

- `scripts/http_util.py`(`urllib.request` 래퍼)와 그 테스트, 라이브 테스트 `tests/test_weather_here_live.py`(저장소 `just live-check` 줄 포함).

## [0.14.2] — 2026-09-30 (itda-work/skills#46, #47)

### Changed

- 공개된 적 없는 itda-hyve 판(0.9.1~0.10.0) 표기를 공개판 0.10.1 로 맞췄다(0.9.0 다음 공개판이 0.10.1 — 그 사이 판은 사용자가 설치할 수 없다, itda-work/skills#46). `location` 경로를 `itda-hyve 0.10.1 이상`, IP 한 곳 경로를 `location 이 없는 0.9.0` 으로(compatibility·SKILL.md 판별 표·GUIDE.md·`weather_here.py` 안내 문구). 경로를 고르는 기준(도구 목록의 `location` 유무)은 그대로다.
- `references/netbridge.md` 사본을 정본과 동기화 — itda-hyve 기능 판 표기를 공개판 기준으로 바꿨다(0.9.1~0.10.0 은 공개되지 않은 개발판이라 그 사이 기능을 모두 0.10.1 로 적는다, itda-work/skills#46).

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.
- **새 Cowork 배치에서 Cowork 로 판정하지 못하던 것** — `_in_cowork_sandbox()` 가 `/sessions/…` 만 봐서, 플러그인이
  `/root/.claude/plugins/synced/…` 에 놓인 새 배치에서는 로컬로 판정했다. 그러면 스크립트가 클라우드 IP 로 위치를 잡는다(#33 의 샌프란시스코).
  이제 `/root/.claude/plugins/synced/` 로 시작하는 경로도 Cowork 다. macOS 의 `~/.claude/plugins/synced` 는 로컬로 남는다. 판정 근거는 여전히
  스크립트 위치다 — Cowork 에는 Claude Code 표준 환경변수가 주입되지 않는다(능력 지도 §3.5).

## [0.14.1] — 2026-09-29 (itda-work/skills#44)

### Changed

- itda-hyve 설치·업데이트 안내의 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44). SKILL.md·GUIDE.md.
- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다.

## [0.14.0] — 2026-09-28 (itda-work/skills#37)

### Changed

- **현재 위치를 itda-hyve `location` 도구로** — IP 서비스 한 곳(ipapi.co)이 대전 KT 회선을 성남으로 잡았다(itda-work/itda-hyve#12 실측). itda-hyve 0.9.3 의 `location`(OS 위치 서비스 → IP 서비스 6곳 합의)을 1순위로 쓴다. 순서: 지역명 → `location` → (location 이 없는 0.9.0~0.9.2) `http_request` IP 한 곳 → 로컬 직접 IP.
- 날씨 줄 첫머리를 출처별로 — `os` 는 장소 이름(예 "대전광역시 중구"), `ip_consensus` 는 "(시·도 기준)", `ip`·`accuracy=low` 와 IP 한 곳 경로(받은 ipapi.co·ipwho.is 응답·로컬 직접 조회)는 "(대략·IP 기준)". 합의가 안 났을 때 itda-hyve 의 `note`(다른 후보)를 stderr `위치 참고:` 로 낸다.
- Cowork 에서 위치 입력 없이 멈출 때 안내가 `location` 도구(0.9.3)를 먼저 가리킨다.

### Added

- `--geo-input` 이 `location` 응답(저장 파일 또는 batch 로 받은 파일)을 받는다. 도구 실패 기록 `{"error": …}` 은 사유(`code`·`message`)를 남기고 다음 파일로, 저장 요약(`saved_path`·`source` 만)은 위치가 아니라 거부한다.
- `allowed-tools` 에 `mcp__remote-devices__itda-hyve__location`.

## [0.13.0] — 2026-09-28 (itda-work/skills#33)

### Changed

- **Cowork 에서 현재 위치를 itda-hyve 로** — Cowork 작업 공간은 클라우드에서 돌아 스크립트의 IP 위치가 사용자 위치가 아니었다(morning-brief 날씨 절이 샌프란시스코를 받은 실측). 위치를 말하지 않은 요청은 itda-hyve `http_request` 로 `ipapi.co`(실패 시 `ipwho.is`)를 받아 스크립트에 넘긴다 — 사용자 PC 네트워크로 나가므로 그 PC 위치가 잡힌다.
- 스크립트가 `/sessions/<id>/…`(Cowork 마운트) 아래에서 돌면 **직접 IP 조회를 하지 않고 exit 3 으로 멈춘다**. 틀린 위치로 날씨를 내지 않는다. 로컬(Claude Code 등)은 지금처럼 직접 조회한다.
- 위치를 확정하지 못한 경우의 종료 코드를 `1` → `3` 으로 나눴다(`1` 은 지역명 미수록·날씨 조회 실패).

### Added

- `--lat`·`--lon`(받아 둔 위경도), `--geo-input <파일>`(itda-hyve 가 `save_as` 로 저장한 ipapi.co·ipwho.is 응답 또는 도구 응답 전체 `status`·`body`, 여러 번 가능 — 버린 파일은 사유를 남긴다).
- `--weather-request`(Open-Meteo 를 itda-hyve 로 부를 `url`·`params` JSON 출력)·`--weather-input <파일>`(저장한 응답을 읽음, 응답 좌표가 요청 위치와 0.5° 넘게 어긋나면 거부). 날씨 기본 경로는 스크립트 직접 호출 그대로다 — 좌표를 인자로 주므로 어디서 돌든 같은 값이고, 막힌 환경에서만 이 경로를 쓴다.
- `references/netbridge.md`(itda-hyve 규약 사본). Windows 콘솔 UTF-8 출력 재설정.

## [0.12.6] — 2026-09-27

### Changed

- User-Agent `Mozilla/5.0 (compatible; weather-here-skill; +itda-skills)` → `Mozilla/5.0`(outbound-identity-leak). 위치·날씨 API 로그에 스킬·조직 이름을 남기지 않는다.

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
