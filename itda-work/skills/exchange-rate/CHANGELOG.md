# Changelog — itda-exchange-rate

## [0.11.0] — 2026-09-30 (itda-work/skills#45·#46)

> ⚠️ **배포 차단** — itda-hyve 0.10.4(itda-work/itda-hyve#31 — `final_url`·저장 경로에 키가 평문으로 남던 결함 수정) 공개 **뒤에** 배포한다.
> 이 경계는 도구 목록으로 가를 수 없어 스킬이 판별하지 못한다. `compatibility` 는 itda-hyve 0.10.4 이상 하나다.
> 0.10.4 는 기본 User-Agent 도 범용 `Mozilla/5.0` 으로 바꾼다 — 이 스킬의 호출은 UA 헤더를 싣지 않으므로, 그 전 판에서는 서울외국환중개 서버 로그에 제품명이 남는다.

### Changed

- **BREAKING — 요청은 itda-hyve, 스크립트는 `plan`·`show` 가공만** (규칙 `cowork-network-via-hyve`). `exchange_rate.py` 는 SMBS 를 직접 부르지 않는다(`urllib.request` 제거). 인자만 주던 옛 호출(`exchange_rate.py --date …`)은 없어졌다 — `plan --date …` 가 `http_request` 인자를 내고, 저장한 파일을 `show --date … --input <파일>` 이 판독한다.
- **BREAKING — 휴일 폴백 창을 스크립트가 정한다** — 옛판은 그해 1년치(1월 초면 전년도까지 2회)를 받아 거꾸로 훑었다. 이제 `--date D` 는 `[D-14일, D]` 한 번의 호출이고, 창 안에 고시가 없으면 더 거슬러 가지 않고 `empty` 로 끝낸다(실측 최장 공백은 2017 추석 연휴 11일, 2017-09-29 → 10-10 — W9 리뷰 M2 에서 정정). 연초 요청도 한 호출에 전년 말을 포함한다.
- **BREAKING — 월평균 호출은 요청한 달만** — 옛판은 1~12월을 받아 한 달을 골랐다. `arr_value` 가 `<통화>_<시작 YYYY-MM>_<끝 YYYY-MM>` 이다(`--month` 는 시작=끝).
- **BREAKING — 실패 출력** — 옛판은 stderr `오류: …` + exit 1 이었다. 이제 stdout 에 `{"status":"error","error":<종류>,"detail":…}` 를 쓰고 exit 1(인자 오류 `args` 는 exit 2). 종류: `args`·`input`(`missing` 동봉 가능)·`empty`·`gap`(`gaps` 동봉)·`mismatch`·`site`·`truncated`·`http`·`hyve`(`hyve_code` 동봉). argparse 오류(`--input` 누락 등)도 같은 JSON·exit 2 다.
- **BREAKING — 출처 줄** — `*출처: 서울외국환중개 (www.smbs.biz) — 매매기준율*`. 폴백 안내 문구가 "휴일로 환율 데이터가 없습니다" 에서 "고시된 환율이 없습니다(휴일 또는 고시 전)" 로 바뀌었다(당일 고시 전일 수 있다).
- 오늘(KST) 이후·2000년 전 날짜와 달, 10조각(약 10년)·60개월을 넘는 표는 호출 전에 `plan` 이 `args` 로 거부한다. 두 자리 연도·`0001-01-05` 류도 `args`(옛판·초판은 traceback).
- **BREAKING — 통화 목록 58종·위안은 CNH** — 사이트 통화 선택 목록(2026-10-01 화면)과 전수 대조해 KES·LYD·ETB·FJD 를 더했다. 별칭 `위안`·`인민폐` 를 CNY 에서 CNH 로 옮기고 `위안화` 를 더했다(사이트가 CNH 를 "위안" 으로 부르고, CNY 는 2016-01-01부터 고시 중단 — 옛판도 "위안" 은 늘 빈 결과였다). CNY 빈 결과에는 그 사실을 붙인다.

### Added

- `--from YYYY-MM-DD --to YYYY-MM-DD`·`--last-days N` — 기간 일별 표. 366일마다 한 조각(호출), 최대 10조각. 둘 이상이면 `plan --write-dir` 가 batch 계획 파일을 쓰고 `batch: {save_dir, plan_file}` 을 낸다 — `plan_file` 은 `save_dir` 기준 상대 경로라 같은 `save_dir` 를 함께 싣는다(funding 과 같은 꼴, W9 재확인 M2 — 초판은 `plan_file` 만 실어 itda-hyve 가 기본 저장 폴더에서 찾았다). `--write-dir` 없으면 `call_list`(옛 itda-hyve 폴백). `show` 는 조각마다 `--input` 을 받아 빠짐·겹침·조각 경계의 공백까지 이어 대조한다.
- `--month-from YYYY-MM --month-to YYYY-MM` — 월평균 표(최대 60개월, 호출 1회). 가운데·끝 달이 비면 `gap`, 앞쪽은 경고.
- **날짜 말은 스크립트가 푼다** — `--date today|yesterday`, `--month this|last`, `--to today`, `--last-days N` 을 KST 로 푼다(샌드박스 시계가 UTC 여도). `plan` 의 `then` 에는 푼 날짜가 실린다.
- `plan --save-dir` 검사 — 호스트 절대 경로(`/…`·`C:\…`·`C:/…`·`\\서버\…`)만, 상대 경로는 `args`.
- `show --format json` — `rates`·`result_date`·`fallback`·`warnings`·`fetched`.
- **응답 대조** — 저장 이름(`exrate/<daily|monthly>-<통화>-<시작>-<끝>-<받은 날>[HHMM].xml` — **끝이 오늘인 질의만 받은 시각 HHMM**: 고시 전에 받은 파일이 "같은 이름 = 이미 받은 파일" 규칙으로 그날 종일 재사용되지 않게, W9 리뷰 M3)과 인자가 같은 질의인가, 받은 날이 오늘 이후가 아닌가(`input`), 본문이 `</chart>` 로 끝나는가(`truncated`), 차트 종류(caption 일별·월평균)·행이 요청 기간 안인가(`mismatch`), 라벨·값 형식·중복(`site`), 오류·점검 페이지(`site`), 빈 창(`empty`). 기간 표는 이어진 두 고시일 사이 공백이 **14일**(폴백 창과 같은 근거)을 넘으면 `gap` 이고, 시작 쪽 공백·고시 없는 평일 목록은 `warnings` 다(W9 리뷰 M2·m1 — 초판의 10일은 2017 추석 11일 공백을 거짓 실패로 냈다). 라벨 형식·날짜가 아닌 라벨(`25.13.45`)·달이 아닌 월 라벨은 `site`.
- `warnings` 와 `refetch` — 진행 중인 달의 월평균(그날까지의 평균)·이번 달 집계 전, 받은 날 당일(평일)인데 고시가 없어 폴백한 경우(고시 전일 수 있음 — 주말이면 경고 없음), 폴백 거리가 실측 최장(11일)보다 먼 경우. 이번 달 단월 월평균이 비면 `empty` 에 "아직 집계 전 — 일별 표로" 를 싣는다(W9 리뷰 m2).
- hyve 층 판독은 공용 `shared/hyve_input.py`(본문 그대로·응답 JSON 전체·실패 자리). Windows 콘솔(cp949) 대비 stdout·stderr UTF-8 재설정. `references/netbridge.md` 동봉.
- 실측 픽스처 — 2026-09-30·10-01 itda-hyve 로 받은 응답 원본(EUC-KR, 2017 추석 구간·월평균 두 달 포함) + 빈 차트·오류 페이지 + 사이트 통화 선택 목록(58종 골든).

### Removed

- `scripts/build_cache.py`(연·통화 조합 선취 캐시)와 캐시 계층(`data/cache/`, 임시 폴더 캐시) — 스크립트가 받지 않으므로 채울 것이 없다. 옛 캐시는 실행마다 새 임시 폴더라 실제로 재사용되지 않았다.
- 라이브 테스트 `tests/test_exchange_rate_live.py` — 부를 대상이 없다. 실측은 itda-hyve 로 한다.
- `allowed-tools` 의 `WebFetch`·`mcp__workspace__web_fetch`·`Bash(date:*)`(대신 `…itda-hyve__batch`).
- description 에 `[책임 경계]` 슬롯.
## [0.10.8] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다.

## [0.10.7] — 2026-07-26 (이슈 #1283)

### Changed

- `allowed-tools` 에 Cowork 실명(mcp__workspace__bash, mcp__workspace__web_fetch) 병기 (#1283) — 표준명 단독 시 Cowork 필터에서 도구가 조용히 소실되는 결손(#1130) 차단.

## [0.10.6] — 2026-07-26 (이슈 #1280·#1283)

### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280).
- `allowed-tools` 를 공백 구분에서 쉼표 구분으로 교정 (#1283) — `Read, WebFetch, Bash(python3:*), Bash(date:*)`. 공백 구분은 도구명 매칭에 실패해 Bash·WebFetch 가 조용히 소실될 수 있었다.

## [0.10.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.10.4] — 2026-05-22

### Improvements
- `description` 정책 v3.0 전환 (SPEC-FRONTMATTER-LINT-001 amend).
  한국어 자연 본문 + 인용 트리거("...") ≥3개 흘리기로 통합, 별도 `Triggers:` 라인 폐기.
  목표 150~250자(avg 149), 400자 cap 유지. cowork-plugins 198 스킬 운영 실증 패턴 차용.
  토큰 부담 감소: 50 스킬 frontmatter avg 340→149자 (-56%).


## [0.10.3] — 2026-05-21

### Improvements

- description를 EN-first로 리팩터링 (한국어 트리거는 `Triggers:` 라인에 보존). 토큰 노이즈 감소 목적. 트리거 정확도 영향 없음.

## [0.10.2] — 2026-05-13

### Improvements

- **GUIDE.md 일반 사용자 문서 정책 준수**: 활용 시나리오 섹션에 노출된 `python3 scripts/exchange_rate.py --month ... --currency ...` CLI 예시 블록 2개(총 3건)를 제거. 그 위의 자연어 호출 예시("2025년 1월 한 달간 달러 환율을 일별로 보여줘", "이번 달 엔화 평균과 지난달 엔화 평균을 비교해줘")만 남겨 사용자 시점 일관성 확보. 일반 사용자용 문서에 CLI 명령 노출 금지 정책 준수.
