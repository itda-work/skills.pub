# Changelog — hotel-search

## [0.4.0] — 2026-10-01 (itda-work/skills#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4 공개 **뒤에** 배포한다. 0.10.4 는 기본 User-Agent 를 범용 `Mozilla/5.0` 으로 바꾼다 —
> 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 Xotelo·ExchangeRate-API 서버 로그에 제품명이 남는다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 판독만** (itda-work/skills#45, 규칙 `cowork-network-via-hyve`). `xotelo.py`·`fx.py` 의
  `urllib.request` 직접 호출(`fetch_json`·`fetch_rates`·`fetch_heatmap`·`krw_rate`·`_fetch`)을 지웠다.
  - 옛판: `hotel_search.py rates|heatmap …` 한 번(스크립트가 요청).
  - 새판: `plan rates|heatmap … --run-dir R --save-dir S` → itda-hyve `batch`(`plan_file`) → `rates|heatmap … --run-dir R`.
    `--run-dir`(스크립트가 보는 회차 폴더)는 판독·계획 모두 필수, `--save-dir`(같은 폴더의 호스트 절대 경로 — `/…`·`C:\…`·`C:/…`·UNC)는 `plan` 에 필수.
  - `resolve` 는 그대로(네트워크 없음).
- **BREAKING — 저장 이름이 식별 계약** — `hotel/rates-<key>-<체크인>-<체크아웃>-<통화>-a<성인>-r<객실>.json`·`hotel/heatmap-<key>-<체크아웃>.json`·
  `hotel/fx-<통화>-<받은 날 KST>.json`. 같은 회차 폴더에 **성한** 파일이 있으면 다시 계획하지 않는다(`reused`, 전부 있으면 `status: "ready"`).
  환율은 하루 한 번만 받는다(ExchangeRate-API 이용 조건 — 하루 한 번 갱신·캐시 권장).
  실패 자리·빈 본문·잘린 본문·HTTP 5xx 또는 JSON 아닌 오류 본문·JSON 아닌 본문은 받은 것으로 치지 않고 같은 이름에 `overwrite: true` 로
  다시 계획한다(출력 `retry`, W13 리뷰 M1 — 실패 자리를 쓰라는 지시를 따르면 그 파일이 영영 재사용되던 결함). 한 이름에 **다시 받은**
  것이 2번까지(`retries-hotel.json` 에 횟수와 그때 파일의 크기·수정 시각을 적는다 — 파일이 그대로면 batch 전이라 세지 않는다) — 넘으면
  요금·달력은 `retry_exhausted`(exit 1), 환율은 `gave_up` 에 싣고 원화 환산만 뺀다. 재시도 기록 파일이 깨졌으면 처음부터 세되 출력
  `warnings` 에 밝힌다. Xotelo 가 4xx 와 함께 준 JSON 오류 객체는 API 의 답이라 다시 받지 않는다 — 408·429 는 예외(다시 받는다).
- 가장 최근 환율 파일을 쓸 수 없으면 같은 회차 폴더의 더 이른 성한 환율 파일로 환산하고 `warnings` 에 그 파일 이름과 사유를 싣는다
  (48시간 경고는 그대로).
- **BREAKING — 응답 대조** — `/rates` 가 되비친 `chk_in`·`chk_out`·`currency`, `/heatmap` 의 `chk_out` 이 요청과 다르면 `mismatch`(exit 1).
  JSON 이 아니거나 `rates`·`heatmap` 이 없으면 `site`. 실패 자리·HTTP 오류·잘림은 공용 `hyve_input`(`hyve`·`http`·`truncated`) —
  Xotelo 가 4xx 본문에 준 오류 객체는 먼저 읽는다(400 → 인자 오류 exit 2).
- **BREAKING — 결과 없음은 exit 3** — OTA 요금 0건이면 옛판은 "요금이 없습니다" 표와 exit 0 이었다(문서의 exit 3 과 어긋남). 이제 exit 3.
- **BREAKING — 오류 출력** — stderr `오류: …` 는 그대로, `--format json`·`plan` 이면 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 도 낸다.
  종류: `args`·`not_fetched`·`hyve`(`hyve_code`)·`http`·`truncated`·`site`·`mismatch`·`api`·`no_result`·`output`·`retry_exhausted`(`plan`).
  HTTP 오류 상태에 JSON 아닌 본문(점검 HTML)이면 `site` 가 아니라 `http` 로 두고 상태를 메시지에 싣는다. `EXIT_BLOCKED`(4)·`BlockedError`
  제거(쓰이지 않았다).
- **BREAKING — JSON 출력 필드** — `fetched_at`(Xotelo 응답 `timestamp` 의 KST — 같은 회차 폴더 파일을 다시 쓸 때 조회 시각),
  `warnings`(환산 생략 사유·48시간 넘은 환율·버린 행) 추가. 마크다운은 머리 줄에 조회 시각, 표 아래 `⚠️` 줄.
- 환율 출처 표기 — 주석에 "환율: Rates By Exchange Rate API (https://www.exchangerate-api.com)" 와 환율 기준일을 싣는다
  (키 없는 Open API 이용 조건: 출처 표기 필수). 옛판은 출처를 싣지 않았다.
- 요금 값을 읽을 수 없는 OTA 행을 버리면 그 수를 `warnings` 로 알린다(옛판은 조용히 뺐다 — `collection-completeness` ③).
- 요청에 UA 헤더를 싣지 않는다 — 옛판은 Xotelo 에 브라우저 UA(`Macintosh … AppleWebKit`)를 실었다. 헤더 없이 성립함을 2026-10-01 itda-hyve 로 확인했다.
- `--hotel-key` 와 `--url` 을 함께 주면 인자 오류(옛판은 `--hotel-key` 가 조용히 이겼다). `--adults`·`--rooms` 0 이하는 인자 오류.

### Added

- hyve 층 판독은 공용 `shared/hyve_input.py`. `references/netbridge.md` 동봉.
- Windows 콘솔(cp949)에서 한국어 출력이 죽지 않게 stdout·stderr 를 UTF-8 로 재설정한다(테스트로 고정).
- 실측 픽스처 3종(2026-10-01 itda-hyve — `/rates`·`/heatmap`·er-api USD, 환율은 4통화로 줄임).
- 이 파일(스킬 CHANGELOG)을 새로 둔다 — 0.3.5 까지의 이력은 팩 `itda-travel/CHANGELOG.md` 에 있다.
