# Changelog — itda-travel/eatery-trend

이 스킬의 변경 이력입니다. [Keep a Changelog](https://keepachangelog.com) 포맷을 따릅니다. 0.2.0 까지의 이력은 팩 CHANGELOG(`itda-travel/CHANGELOG.md`)에 있습니다.

## [0.4.0] — 2026-10-06 (itda-work/skills#46 W17)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.

### Changed

- **BREAKING — 요청을 itda-hyve 로 옮겼다** (사용자 결정 2026-10-06). 스크립트는 네트워크를 열지 않는다(가드 `LEGACY` 에서 뺐다).
  데이터랩 검색어트렌드(POST)는 `http_request` 하나씩(`single_calls`), 지역검색(GET)은 `batch` `plan_file` 로 받고, 키는 헤더의
  `{{secret:NAVER_CLIENT_ID}}`·`{{secret:NAVER_CLIENT_SECRET}}` 자리표시뿐이다(web-search 와 같은 이름, 프리셋 허용 호스트 `openapi.naver.com`).
- **BREAKING — CLI 가 `plan`·`collect` 두 하위 명령이 됐다.** `plan --mode A|B … --run-dir R --save-dir S` 가 회차 상태(`eatery-state.json`)와 첫 호출을
  내고, `collect --run-dir R` 이 저장 파일로 같은 파이프라인을 돌려 빠진 요청을 다음 계획으로 낸다(`incomplete` → … → `ok`/`partial`/`error`, exit 0/1/2/1).
  저장 이름은 요청 모양의 지문(`raw/dl-<10자>.json`·`raw/ls-<10자>.json`), 실패는 `-r2`·`-r3` 로 세 번까지, batch 계획은 40개 단위로 나눈다.
  옛 `--mode …` 단일 명령·`--emit-candidates`·`--judge-file`·`--no-cache`·`--throttle` 은 없어졌다(캐시 모듈 `cache.py` 삭제 — 회차 폴더의 저장 파일이 캐시다).
- **BREAKING — 출력 필드**: 결과에 `level_known`(지금 `false`)이 붙고, 라이저·강등의 `monthly_vol` 이 `null`, `trust.reason` 이 "거품 판정 보류" 다.
  `source_status.searchad`·`source_status.autocomplete` 에 쓰지 않는 사유가 실린다. 모드 A `viral_stores` 는 늘 빈 목록이다.
- 월검색량이 없을 때 magnitude floor 는 데이터랩 baseline 만 본다(`surge.magnitude_floor_pass(None, …)`) — 저볼륨 노이즈 격리(PoC#5)는 그대로다.

### Fixed (W17 리뷰 반영)

- **Windows 에서 재시도 경로가 `KeyError` 로 죽던 결함** — 재시도 저장 이름(`-r2`)을 `Path` 로 만들어 Windows 에서 `raw\…` 가 되고
  `calls` 키(`raw/…`)와 갈렸다. 저장 이름을 POSIX 문자열로만 다룬다(`posixpath`). `PureWindowsPath` 를 끼운 회귀 테스트.
- **키 오류로 멈춘 회차 폴더가 영구히 막히던 것** — 멈춘 실패 파일을 다음 이름으로 넘겨, 키를 등록한 뒤 **같은 `--run-dir`** 로 `collect` 하면
  다시 받을 계획이 나온다(`detail` 이 그 사실을 말한다). 상한(세 번)은 그대로 센다.
- **데이터랩 되비침 대조** — 응답의 `startDate`·`endDate`·`timeUnit`·그룹별 `keywords` 가 요청과 다르면 실패(다시 받기)다. 그룹 이름만 보던 판은
  본문을 고쳐 보낸 응답을 성공으로 받았다.
- **모드 A 바스켓 실패가 결과에 안 보이던 것**(0.2.0 부터) — 모드 B 처럼 `source_status.datalab_basket`·`errors` 에 싣는다.

### Removed

- 검색광고 키워드도구(월검색량·연관 키워드) — 요청 서명이 itda-hyve 서명 기능(itda-work/itda-hyve#34)을 기다린다. 돌아오면 레벨·거품 판정이 함께 돌아온다.
- 블로그 검색 total — 거품 비율(블로그/월검색량)의 분모가 없어 부르지 않는다.
- 자동완성(`ac.search.naver.com`) — robots `User-agent: *` 전면 불허(2026-10-06 확인)라 부르지 않는다. 후보는 지역×음식 그리드 10개뿐이고 LLM 음식 판정 단계가 없어졌다.

### Tests

- `tests/test_cli.py`(plan→collect 종단·`secret_missing`·인증 오류 본문(그대로·응답 JSON 전체)·잘림 재시도→partial·그룹 누락·미수신 세 번→partial·40개 분할)와
  `tests/test_adapters.py`(요청 모양·판독·네트워크 import 부재)를 새로 썼다. 응답은 합성 픽스처다(이 회차에 itda-hyve 라이브 실측을 못 했다).
  게이트 뮤테이션 9종 전부 RED.

## [0.3.0] — 2026-10-03 (itda-work/skills#46 W17)

### Removed

- **BREAKING — 네이버 키를 프로세스 환경변수로 읽던 경로를 없앴다** (사용자 결정 2026-10-03). 셸 환경변수·Claude Code 설정의 `env` 에 둔 `NAVER_CLIENT_*`·`NAVER_SEARCHAD_*` 를 더 읽지 않는다 — 키는 itda-hyve 시크릿에만 둔다. 요청을 아직 itda-hyve 로 옮기지 않았으므로 키가 필요한 네 소스(데이터랩·지역검색·블로그 수 — 이전 작업 대기, 검색광고 — itda-hyve 서명 기능 itda-work/itda-hyve#34 대기)는 네트워크를 열지 않고 `🚨 소스 상태` 에 사유를 싣는다. 조용히 건너뛰지 않는다.

### Changed

- 키 없는 자동완성만 동작한다 — 남는 기능은 `--emit-candidates` 의 후보 발굴. SKILL.md 에 「지금 되는 것과 안 되는 것」 표를 두고 키 주입·출처 표시 규칙을 지웠다. GUIDE.md 의 키 발급·등록 절을 같은 사정 안내로 바꿨다.
- 어댑터가 `env_loader` 를 더 import 하지 않는다 — 키 부재는 `KeyUnavailable` 로 올리고 어댑터가 `(False, 빈값, 사유)` 로 바꾼다.
