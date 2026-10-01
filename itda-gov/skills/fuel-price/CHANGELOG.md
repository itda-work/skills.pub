# Changelog — itda-fuel-price

## [0.5.0] — 2026-09-30 (itda-work/skills#45)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 오피넷 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`parse` 가공만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `fuel_price.py` 는 오피넷을 직접 부르지 않는다. 하위 명령이 생겼다 — 인자만 주던 옛 호출(`fuel_price.py --region …`)은 없어졌다.
  - 웹 경로(기본, 호출 2회): `plan` → 화면 GET 호출 · `plan --input view-….html` → 조회 POST 호출(폼 본문은 기존 골든 빌더 그대로 — 브라우저 FormData 와 키 집합·순서 동일) · `parse --input avg-….html` → 요약.
  - API 경로(선택, 호출 1회): `plan --source api` → GET 호출(`params` 의 `{{secret:OPINET_API_KEY}}`) · `parse --input api-….json`.
- **BREAKING — 키 경로는 itda-hyve 시크릿 탭 하나** — `--api-key` 인자, `os.environ`·`env_loader` 키 읽기, settings.json `env` 안내, "Cowork 에서는 키를 넣을 방법이 없다" 문구를 지웠다. 키가 없으면 스크립트가 아니라 itda-hyve 가 `secret_missing` 으로 알린다. 빈 배열 오류 안내도 시크릿 탭 확인으로 바꿨다.
- **BREAKING — 실패 출력** — 옛판은 stderr 에 `오류: …` 한 줄 + exit 1 이었다. 이제 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 를 쓰고 exit 1(인자 오류 `args` 는 exit 2). 종류: `args`·`input`·`mismatch`·`period`(`missing`·`unexpected` 동봉)·`empty`·`site`·`api`·`hyve`(`hyve_code` 동봉)·`truncated`·`http`.
- **BREAKING — 성공 출력** — JSON 첫 필드에 `status: "ok"` 가 붙는다. 그 밖의 필드(`term`·`region`·`product`·`latest_*`·`prev_*`·`series`·`as_of`·`source`·`summary`·`detail_table`·`source_note`)는 그대로다. `as_of` 는 조회 응답 화면의 `h_maxDD` 다(옛판은 GET 화면 값 — 같은 회차면 같다).
- 호출에 `User-Agent`·`Cookie` 헤더를 싣지 않는다 — 2026-09-30 itda-hyve 실측으로 범용 UA·쿠키 없이 전국·시도 모두 성립함을 확인했다(옛판은 브라우저 UA 와 CookieJar 를 썼다). 헤더는 원 사이트 흐름과 같은 `Content-Type`·`Referer` 둘뿐이다(`request-profile-first`).
- **BREAKING — 저장 이름에 받은 날(KST)** — 화면 `view-<nat|area>-<YYYYMMDD>.html`(질의와 무관 — 같은 날 다른 지역·제품·기간 질의가 화면을 다시 받지 않는다), 조회 결과 `avg-<지역>-<제품>-<단위>-<시작>-<끝>-<YYYYMMDD>.html`, API `api-<지역>-<제품>-<YYYYMMDD>.json`. 어제 받은 화면으로 계획하면 `stale`(W7 리뷰 M2·m7).
- **BREAKING — 기간 대조** — 옛판은 받은 행을 그대로 잘라 썼다. 이제 표의 기간 행이 **기대 목록의 이어진 한 구간**이어야 한다: 월간·일간은 범위의 모든 기간, 주간은 "그 달 N번째 수요일이 든 주" 규칙(실측 응답 8종·56주 대조)으로 만든 주. 가운데 결손·범위 밖·중복·뒤쪽 결손(주간은 수요일이 최신 확정일 7일 전 이전인 주까지 필수)은 `period`. **앞쪽 결손**(자료 시작 경계 — 전남광주 2026-07 통합, 세종 주간 2012년11월3주부터)은 결과를 내고 요청 구간 안의 결손만 `missing_count`·`missing_range` 에 싣는다(W7 리뷰 M1·M3, 재리뷰 A1·b1·b4 — 재리뷰판 전에는 달초에 주간 꼬리 결손이 무음 통과했고, 세종 달 중간 시작은 실패했고, 넉넉히 잡은 앞 달 결손까지 "자료 없음" 이라 했다). 여유 안의 최신 주가 없는 표는 행 수와 무관하게 결과를 내고 `warnings` 에 "최신 주(…)가 응답에 없습니다" 를 싣는다 — 재리뷰판의 행 수 게이트는 기대 목록이 요청 수와 딱 맞는 `--periods`(예: 11-01·11-02 `--periods 4`)에서만 이 정상 상태를 `period` 로 막아 지웠다(W7c c1·c2). 요청한 수보다 적게 보이면 어떤 경우든 `warnings` 가 그 수를 말한다 — 최신 주 경고가 없어도 "요청한 N주 중 M주만 보입니다" 한 줄(`h_maxWW` 의 달이 `h_maxDD` 를 앞지를 때), 필수 주가 하나도 없을 만큼 어긋나면 traceback 이 아니라 `site`(W7m d1).
- **BREAKING — `parse` 가 `--periods`·`--end` 를 대조한다** — 인자와 **응답의 `h_max*`**(서버가 매번 새로 싣는 최신 시점 — 2026-09-30 실측: 09-01 값을 실은 POST 의 응답이 20260929)로 범위를 다시 계산해 이름과 대조한다. 끝이 다르면 `stale`(`--end` 없음), 끝은 같고 시작만 다르면(`--periods` 만 다름) `input`(W7 리뷰 M2, 재리뷰 b2).
- **BREAKING — 새 실패** — `stale`, 본문이 `</html>` 로 닫히지 않은 `truncated`, 최신 기간 가격 빈 칸 `empty`(W7 리뷰 m8), 숨김 필드 값 형식 오류 `site`(옛판·초판은 traceback — m2), 화면 시작 연도 셀렉트(1997~) 앞 범위 `args`(m3), `--end` 형식 오류를 화면 받기 전 `plan` 에서 `args`(m1), 한 셀렉트에 선택값이 여럿이면 `site`.
- **BREAKING — API 경로 대조** — `--periods` 8 이상 `args`, 행마다 `DATE`(8자리)·`PRODCD`·시도는 `AREA_CD` 필수(없으면 요청값으로 채워 보지 않는다), 날짜 하루씩 연속·중복 없음, 행 수 ≥ `min(max(periods,2),7)`(`period`), 최신 날짜가 받은 날보다 3일 넘게 묵으면 `stale`. `as_of` 는 최신 DATE. 오류 발췌는 공용 가림에 더해 `code=` 값을 가린다(W7 리뷰 m4).
- 주간 조회 범위를 한 달 최소 4주(수요일 넷)·끝 달 0주로 잡는다(`ceil(periods/4)` 달 앞부터) — 달초에 `--periods 5` 가 모자라던 계산을 고쳤다(W7 리뷰 M4).

### Added

- **응답 식별 대조** — 조회 응답 화면이 되비친 폼 상태(기간 단위·시작/종료 셀렉트·제품·지역 체크)를 저장 이름과 대조한다. 화면(view-…) 파일이나 다른 질의의 응답을 넘기면 `mismatch` 다(`collection-completeness` ⑫ — 200 이어도 원한 것이 아닐 수 있다).
- 성공 출력에 `missing_count`·`missing_range`(요청 구간 앞쪽에서 응답에 없는 기간의 수와 구간 — 하나면 그 기간, 둘 이상이면 늘 `처음~끝`, 없으면 0·빈 문자열. `--periods 1` 의 빠진 앞 행은 전기 대비용이라 세지 않는다(W7m d5) — 결손은 늘 앞쪽의 이어진 한 구간이라 전부 나열하지 않는다. 전부 나열하던 판은 일간 장기 조회에서 509개·10KB 였다, W7c c5)·`warnings`(없으면 빈 목록). 결손이 있으면 `summary` 끝에 "… 응답에 행 없음"(3개 이상이면 `처음~끝` 구간), `warnings` 에 "요청한 N기간 중 M기간만"(`--periods 1` 이면 "전기 대비에 쓸 앞 기간 …")·1행만 남으면 "전기 대비 없음" — 원인은 단정하지 않는다(재리뷰 b5, W7c c5). `--format table` 도 끝(출처 앞)에 `warnings` 를 `※` 줄로 찍는다(W7m d2). 웹 응답의 최신 확정일이 저장 이름의 날짜(plan 한 날)보다 뒤면 `warnings` 한 줄(W7c c5). 최신 확정일이 받은 날 전전날 이전이면 `plan --input`·`parse` 의 `warnings` 가 새벽 갱신 전 파일일 수 있다고 알린다(재리뷰 b7).
- `references/opinet-web-contract.md` — 화면 관측 성질과 표본 수, **Cowork 실측 대기 항목**(요일별·2026-10-08 기본 주간 조회, 새벽 갱신 시각, Open API 경로, 오류 상태 본문 저장 — 재리뷰 b6).
- hyve 층 판독은 공용 `shared/hyve_input.py`(본문 그대로·응답 JSON 전체·실패 자리). Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다(테스트로 고정). `references/netbridge.md` 동봉.
- 실측 픽스처 — 2026-09-30 itda-hyve·리뷰 라이브 응답 14종(재리뷰: 세종 2012 주간·전국 1년 56주·전남광주 일간 경계) + 09-02 실측의 되비침만 조정한 달초 주간 1종. `tests/trim_fixture.py` 로 조회 폼 블록만 남겨 하단 개인정보 담당자 성명·전화·이메일을 없앴다(기존 09-02 픽스처 6종 포함 — W7 리뷰 m9).

### Fixed

- 문서의 "브라우저와 바이트 동일" 을 "키 집합·순서 동일" 로 정정 — 브라우저는 건드리지 않은 분기·일 셀렉트를 그날 화면 기본값으로 보낸다(2026-09-30 은 STA_D=29). 서버가 그 필드를 쓰지 않음은 표 값 일치로 확인했다(W7 리뷰 m5).
- SKILL.md ① 의 명령과 예시 JSON 을 같은 질의로(m6), 응답 `status` 가 200 이 아니면 넘기지 말라는 줄(m11), `timeout` 재사용은 방금 보낸 호출에만(M2), 스크립트가 거부한 파일은 재사용하지 않고 새 하위 폴더로 `plan` 부터(재리뷰 b3) — `truncated`·`mismatch`·API `stale` 의 `detail` 도 같은 안내로 맞췄다(W7c c3, W7m d5). SKILL Step 4 에 "`warnings` 는 전부 그대로 전한다", ③ 에 목요일 최신 주 경고가 보통이라는 줄(사이트 안내: 금요일 발표)을 넣었다(W7m d4·d5).

### Removed

- 라이브 테스트 `tests/test_fuel_price_live.py` — 스크립트가 네트워크를 하지 않아 부를 대상이 없다. 실측은 itda-hyve 로 한다.

## [0.4.0] — 2026-09-30 (itda-work/skills#45)

### Changed

- **BREAKING — env 파일을 더 읽지 않는다** (itda-work/skills#45, 사용자 결정 2026-09-30). `.env`·`.env.txt` 를 포함해 어떤 env 파일도, `~/.claude/settings.json` 도 스크립트가 직접 열지 않는다. 선택 키 `OPINET_API_KEY` 는 Claude Code 에서 셸 환경변수 또는 `claude config set env.OPINET_API_KEY "키"` 로만 받는다(스크립트가 `os.environ` 에서 읽음). 스크립트가 API 를 직접 부르므로 itda-hyve 시크릿 경로는 없다. 키 없는 기본 경로(웹 통계)는 그대로다. GUIDE.md 의 키 등록 안내를 고쳤다.

## [0.3.1] — 2026-09-30 (itda-work/skills#45, #47)

### Changed

- **자격증명 파일 별칭에서 `환경변수.txt` 제거** (itda-work/skills#45, BREAKING) — 읽는 파일명은 `.env`·`.env.txt` 두 가지다. `환경변수.txt` 로 키를 두었다면 파일 이름을 `.env.txt`(또는 `.env`)로 바꾼다. GUIDE.md 의 키 등록 안내를 `.env.txt` 기준으로 고쳤다.

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다.
  Windows 명령이 쓰던 `$env:SKILL_DIR` 을 정하는 PowerShell 블록이 없던 것도 정본 블록으로 채웠다.

## [0.3.0] — 2026-09-02 (이슈 #1632 후속, 마스터 지시)

### Changed

- **기본 출력을 compact JSON 으로 반전**(itda-gov 팩 관례 — dart·ecos 와 정합): `--format json|table` 신설, 기본 `json`.
  LLM 파싱·후속 계산이 안전하도록 정형 필드에 더해 표시용 완성 문자열 `summary`·`detail_table`·`source_note` 를 동봉
  — 에이전트가 숫자를 다시 타이핑하지 않고 그대로 표시한다(전사 오류 방지). `--json`(별칭)·`--detail`(table 함축) 존치.

## [0.2.0] — 2026-09-02 (이슈 #1632 후속, 마스터 결정)

### Changed

- **조회 전용으로 축소** — 유류비 정산 단가(`--efficiency`·`--factor`·km당 계산)와 공지문(`--notice`)을 제거.
  단가는 간단한 산식(기준가 ÷ 연비 × 보정계수)이라 회사 규정대로 소비자(대화)가 적용한다.
  스킬은 평균 유가 조회(전국·시도 16 × 일/주/월, `--end` 과거 시점, `--detail`·`--json`)에 집중.
  조회 전용 계약은 `test_scope_is_query_only` 정적 가드로 고정.

## [0.1.3+move] — 2026-09-02 (이슈 #1632)

### Changed

- **itda-work → itda-gov 로 이동**(마스터 결정) — 데이터 소스가 공공기관(한국석유공사 오피넷)이라 공공데이터 팩 소속이 맞다. 스킬명·내용 불변, 미배포 상태라 별칭 없음.

## [0.1.3] — 2026-09-02 (이슈 #1632 후속)

### Changed

- GUIDE.md 를 dart 가이드 형식으로 전면 재작성(마스터 지시) — 사전 준비(키 불요 강조·규정값 안내) · 자주 쓰는 요청 11종 · 활용 시나리오 6종(월초 공지·지역 기준·제품별·추세·과거 시점·오늘) · 출력 형식 · 팁 · 안 될 때 표 · 선택 API 키 절 · 주의사항.

## [0.1.2] — 2026-09-02 (이슈 #1632 후속)

### Changed

- GUIDE.md 에 `OPINET_API_KEY` 발급 절차 신설 — https://www.opinet.co.kr/user/custapi/custApiInfo.do 하단 「일반 API 이용 신청」(회원가입 → 자동 승인 즉시, 무료) → `.env` 설정. SKILL.md 데이터 경로 표·스크립트 안내 문구도 같은 URL·버튼명으로 정합.

## [0.1.1] — 2026-09-02 (이슈 #1632 후속)

### Added

- `--end` — 특정 시점 조회(일간 `YYYY-MM-DD`, 주간·월간 `YYYY-MM`). 오피넷 최신 확정 시점 이후는 거부(`까지만 있습니다`).
  API 경로(`--source api`)는 최근 7일만이라 `--end` 와 함께 쓰면 안내 에러.

### Changed

- SKILL.md — 키 유무별 지원 범위 표(현재 시세·시도 16·날짜별·주간·월간·과거 시점) 신설, 지원 지역 16개 전수
  명시(광주·전남 → 전남광주 통합 해석), "오늘 시세 = 전일 확정치" 안내, 오류 표 보강.

## [0.1.0] — 2026-09-02 (이슈 #1632)

### Added

- 신설 — **출장 유류비 기준가 브리핑**: 오피넷(한국석유공사) 주유소 평균 판매가격(전국·시도 × 일/주/월)을 조회해
  기준가 요약(전기 대비) → km당 단가(`--efficiency`·`--factor`) → 직원 공지문(`--notice`)을 낸다.
- 기본 경로는 **키 불요 웹 통계**(평균판매가격 화면의 폼 POST 를 브라우저와 바이트 동일하게 재현 — aside 브라우저
  실측 2026-09-02, `tests/test_payload_golden.py` 고정). 월간 평균은 Open API 에 없어 이 경로가 정본.
- 선택 경로 `--source api`(`OPINET_API_KEY`): `avgRecentPrice`·`areaAvgRecentPrice` 최근 7일. 키 누락 시 오피넷이
  에러 대신 200 + 빈 배열을 주는 함정을 명시 에러로 표면화.
- 배경: IGM 9기 사전설문 원문 "외부 자료를 정기적으로 확인해 내부 공지 (유류비 시가 확인 후 공지)" — 전국 출장형
  소기업 행정 총괄의 정산 기준가 갱신 과제로 판정해 "주유소 찾기"가 아니라 "기준가 + 단가 + 공지문"으로 설계.
