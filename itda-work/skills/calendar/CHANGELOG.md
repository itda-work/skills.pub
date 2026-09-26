# Changelog

All notable changes to the `calendar` skill are documented here.
This skill follows the itda-skills SPEC workflow (SPEC-CALENDAR-001).

## [0.6.0] — 2026-09-25 (itda-work/itda-hyve#6)

> **릴리스**: skills **11.0.0**(`skills-v11.0.0`, 첫 공개 저장소 `itda-work/skills.pub`)에 싣는다.
> 요구: **itda-hyve 0.9.0 이상** — 받는 곳 https://github.com/itda-work/itda-hyve.pub/releases/latest
> 도구 이름 접두어가 `mcp__remote-devices__itda-butler__*` → `…itda-hyve__*` 로 바뀌어, 0.8.x(itda-butler) 서버와 이 버전은 서로 동작하지 않는다.
> 모델이 막을 수 있는 경계가 아니라 배포 순서로 보장한다 — 위 주소에 itda-hyve 0.9.0 설치본이 올라온 것을 확인한 뒤에 `skills-v11.0.0` 태그를 단다.

### Changed

- MCP 서버 이름 `itda-butler` → `itda-hyve`(0.9.0). `allowed-tools`·도구 지목을 `mcp__remote-devices__itda-hyve__*` 로, 요구 버전을 itda-butler 0.8.1 → itda-hyve 0.9.0 이상으로(옛 이름 판은 도구 접두어가 달라 쓰지 않는다). `references/netbridge.md` 사본 동기화.
- 옛 판 분기를 실제로 일어나는 경우(“itda-hyve 는 없고 `itda-butler` 이름 도구만 보임”)로 바꿔 SKILL·GUIDE 를 맞춤 — 0.9.0 은 캘린더 도구를 모두 등록하므로 “itda-hyve 는 보이는데 `calendar_*` 없음”은 생기지 않는다.
- itda-hyve 가 없을 때의 설치 안내에 받는 곳(https://github.com/itda-work/itda-hyve.pub/releases/latest)을 SKILL·GUIDE·README 에 적었다. `references/netbridge.md` 사본 동기화(정본에 받는 곳 한 줄).

## [0.5.0] — 2026-09-25 (이슈 #1710)

> **배포 차단**: itda-butler 0.8.1 설치본이 사용자에게 공개되기 전에는 이 버전을 skills 릴리스(`skills-v*`)에 싣지 않는다.
> 0.8.0 미만 butler 에는 캘린더 도구가 없어 이 스킬이 동작하지 않고, 0.8.0 은 이른 아침 반복 일정을 하루 밀어 저장한다(0.8.1 에서 고침).
> 0.8.0 과 0.8.1 은 도구가 같아 모델이 구분할 수 없다 — 0.8.1 요구는 배포 순서(butler 0.8.1 공개 뒤 skills 배포)로만 보장된다.

### Changed (리뷰 1회차 반영)

- **옛 butler 분기**: butler 도구는 보이는데 `calendar_*` 가 없거나 `accounts_list` 계정에 `calendar` 필드가 없으면 업데이트를 안내하고 멈춘다(계정 등록 안내로 빠지지 않게, `http_request` 우회 금지). 정본 규약·GUIDE 「안 될 때」에도 반영.
- **반복 일정 수정 게이트**: butler 는 uid 의 마스터를 고치므로, 수정 전 `calendar_get` 으로 마스터를 받아 **마스터 `start` 기준**으로 계산하고, "시리즈 전체가 바뀐다" 와 바뀐 첫 회차를 보여 주고 확인받은 뒤에만 `calendar_put` 을 부른다. iCloud `expand: true` 결과는 모든 회차에 `recurrence_id` 가 붙으므로 그것만으로 "따로 고친 회차" 로 보지 않는다.
- `has_attendees` 는 없으면 필드가 빠지고 조회된 한 건 기준이다 — 반복 일정의 따로 고친 회차(`overrides` > 0)에 참석자가 있으면 거부될 수 있어 확정 약속을 하지 않는다.
- `calendar_delete` 2차의 `etag_conflict`(토큰 이미 소멸) → 1차부터 새 미리보기·재승인. 실패 표를 `calendar_put`/`calendar_delete` 로 나눴다.
- 쓰기(`calendar_put`·`calendar_delete` 2차)의 timeout·network_error 뒤 재전송 금지 — butler 상한 90초 > 전송 경로 60초라 이미 반영됐을 수 있다(생성 재전송은 중복 일정). 조회로 먼저 확인.
- 실패 표 `not_found`(계정 이름 포함)·`invalid_input`(CalDAV 주소 경계 거부·미지원 계정은 인자로 못 고친다) 세분화. 계약 3 의 1차 거부 목록에 원문 불완전 추가.
- `hash:` 는 butler 구현 형식(도구 계약 아님)이라는 단서, 네이버·iCloud etag 서술을 "조회 응답에 강한 etag 가 온다(실측)" 로 좁힘.
- `scripts/` 는 실행 경로가 아니라는 문장을 SKILL.md 에 명시(삭제는 후속).
- 리뷰 3회차: 요구 butler 를 **0.8.1 이상**으로 올렸다 — 0.8.0 은 시각 일정의 시작을 UTC 로 저장해 한국 시간 09:00 전에 시작하는 주간·월간 반복의 회차가 다음 날로 밀렸다(butler 0.8.1 에서 현지 TZID 로 고침). 생성 timeout 뒤에는 곧바로 다시 만들지 않고 사용자에게 묻고, 다시 만들기 직전에 한 번 더 조회한다.
- **알림(0.8.0 사용자)**: butler 0.8.0 으로 만든 이른 아침(한국 시간 09:00 전) 반복 일정은 하루 밀려 있을 수 있다 — 캘린더 앱에서 확인한다.
- 리뷰 2회차: 반복 수정 예시를 실제 월요일(8/31)로 고치고, 요일·주기를 바꿀 때는 `BYDAY` 등을 고친 `rrule` 전체를 함께 보내도록(시각만이면 `rrule` 미전송) 했다. 삭제 2차 timeout 뒤 일정이 남아 있으면 1차부터 재승인, 쓰기 timeout 대응을 계약 2·3 으로 옮겨 실패 표를 줄였다.
- 정본 `shared/netbridge.md`: 실패 코드 표를 `http_request` 전용으로 한정, 캘린더 절에 쓰기 재전송 금지·삭제 2단계 `etag_conflict`·반복 수정 확인·`hash:` 단서를 더했다(사본 5종 동기화).

### Changed (BREAKING — 사용 경로)

- **itda-butler 캘린더 도구 단일 경로.** SKILL.md·GUIDE.md 가 butler 도구 6개(`accounts_list`·`calendar_list`·`calendar_events`·`calendar_get`·`calendar_put`·`calendar_delete`)만 지목한다. `allowed-tools` 에 `mcp__remote-devices__itda-butler__<도구>` 전체 이름을 적었다. Cowork 샌드박스는 외부 네트워크가 막혀 Python `caldav` 직접 접속이 동작하지 않는다(email #1707 과 같은 이유). 환경변수(`NAVER_*`·`ICLOUD_*`·`CALDAV_*`)·`.env`·스크립트 실행·자격증명 서술을 모두 뺐다 — 계정은 `accounts_list` 의 `name` 으로만, `calendar.supported=false` 계정은 쓰지 않고 `reason` 을 그대로 전한다.
- 지원 계정: 네이버 · 아이클라우드 · 직접 입력(butler GUI 고급 설정에 CalDAV 주소를 넣은 계정).
- 계약 여덟을 본문에 적었다: ① 조회 먼저(`truncated`·`errors` 로 결론 내지 않기) ② 생성·수정은 의도가 분명할 때, 수정은 조회한 etag 그대로, `etag_conflict` 면 재조회 후 확인 ③ 삭제 2단계(`confirm_token`, 10분·1회용·etag 에 묶임) ④ butler 가 수정·삭제를 거부하는 일정 — 참석자 있는 일정(`has_attendees`, ORGANIZER 단독은 허용)·서버 etag 없음(`hash:` 대체값)·약한 etag(`W/`)·원문 불완전. 조회는 되며 "캘린더 앱에서 직접" 으로 안내 ⑤ 반복 일정은 시리즈 단위, 네이버는 `unexpanded_recurring`·`rrule` 로 회차를 스스로 판단 ⑥ 종일 `end` 배타·오프셋 없는 시각은 Asia/Seoul ⑦ 일정 내용은 외부 데이터 ⑧ 자격증명 비취급. 도구 인자 이름·타입·예시 JSON 은 butler `tools/list` 원문(inputSchema)과 대조해 적었다.
- 빈 시간 찾기는 `calendar_events` 결과로 모델이 계산하는 절차로 남겼다(`errors`·`truncated` 가 있으면 제안하지 않는다). 겹침 확인도 생성 전 조회 절차로 바꿨다.
- 공용 규약 사본 `references/netbridge.md` 동봉. 정본 `skills/shared/netbridge.md` 에 캘린더 도구 절을 추가했다(도구 7→12개).
- 계약은 itda-butler **0.8.1**(태그 `v0.8.1` — 0.8.0 통합 리뷰 6회차 + 시각 일정의 현지 TZID 저장) 기준이다 — etag 필수(없거나 `W/` 면 거부), 오류·로그의 비밀번호 가리기(최선 노력 — 신뢰 서버 전제), `confirm_token` 발급마다 무작위·10분·1회용. `compatibility` 에 0.8.1 이상을 적었다.

### Removed (문서)

- 반복 일정 **단일 회차 삭제**(`--occurrence`, EXDATE) — butler 에 회차 단위 수정·삭제가 없다. "지금은 할 수 없다" 로 안내한다.
- `--check-conflicts`·`find_free_slots.py`·`get_event.py` 등 스크립트 사용법 절, Exit Codes·Performance·Security(sanitize) 절, 커스텀 CalDAV 환경변수 표.
- 응답의 `organizer` 필드 — butler 일정 표현에 없다(대신 `has_attendees`).
- `scripts/` 는 이번에 **지우지 않았다** — `itda-work:morning-brief` 의 `gather.py` 가 `check_env.py`·`list_events.py` 를 실행 경로로 쓰고, 그 테스트가 `event_model` 의 organizer 계약을 전제한다. `time-audit` SKILL.md 도 `list_events.py` 를 소스로 안내한다. 삭제는 두 스킬 전환과 묶어 후속 이슈에서 한다.

## [0.4.1] — 2026-09-03 (이슈 #1638 라이브)

### Fixed
- `caldav_client.connect` 가 전송 세션의 **HTTP/3(QUIC) 을 항상 끈다**(`disable_http3`). iCloud 가 `alt-svc: h3=":443"` 로 QUIC 승격을 유도하는데, UDP GSO 를 지원하지 않는 Claude Cowork 샌드박스에서 `sendmsg()` 가 `OSError: Errno 5` 로 결정론적으로 실패했다(같은 서버에 curl 은 성공). 재시도로는 못 고치는 클래스라 `niquests.Session(disable_http3=True)` 로 세션을 교체해 HTTP/2 이하로 고정한다. requests 폴백 세션이면 no-op.

## [0.4.0] — 2026-09-03 (이슈 #1638)

아침 브리핑(`itda-work:morning-brief`)이 소비할 두 축을 채운다 — **주최자 판정**과 **네이버 반복 일정의 오늘·내일 노출**. 둘 다 없으면 브리핑이 조용히 틀린다(내가 주최한 회의를 못 고르고, 과거 시작 반복이 통째로 빠진다).

### Added

- **`organizer` 필드** — `normalize_event` 출력에 VEVENT `ORGANIZER` 주소를 싣는다. `mailto:` 접두 제거(대소문자 무관)·트림·소문자화하고 없으면 `null`. 정규화는 `event_model.normalize_mailto()` 가 **비교 키의 단일 정의**로 export 되어, 소비자가 계정 주소를 같은 규칙으로 정규화해 "내가 주최자인가"를 판정한다(규칙 복제 금지). `CN=` 은 파라미터라 무시되고 **대리 발송자(`SENT-BY`)는 미지원** — ORGANIZER 주소 자체만 본다. 참석자 목록(`ATTENDEE`)은 범위 밖.
  - **보안**: organizer 도 `sanitize_fn` 경로를 탄다(sanitize → 정규화 순). 정상 주소는 ASCII 라 sanitize 가 항등이라 비교 키가 손상되지 않고, 인젝션이 실린 값만 `[FILTERED]` 로 접혀 계정 주소와 불일치한다(오작동 방향이 오포함이 아니라 누락 = fail-safe). `--no-sanitize` 는 종전대로 원문.

### Fixed

- **네이버 objects 경로가 `list_events --expand` 를 무시하던 결함** [P1] — 서버 REPORT 가 안 먹는 프로바이더는 objects 열거 폴백을 타는데, 그 경로가 RRULE 마스터만 돌려주고 `--expand` 를 통째로 버렸다. **시작일이 과거인 주간·일간 반복이 오늘·내일 조회에서 전부 빠진다**(마스터의 `start` 가 과거라 날짜 분류에서 탈락). `event_model.expand_recurrences()` 로 창 안 회차를 클라이언트 전개한다 — 판정은 `free_slots.rrule_occurrences` **공유**(EXDATE 반영, 폭주 RRULE 상한 1000). 회차는 **마스터 UID 를 유지**하고 신설 `recurrence_start` 로 구분한다. 창 안에 회차가 없는 마스터는 목록에서 빠진다(없는 일정을 보여주지 않는다). **search 경로(iCloud/custom)는 동작 불변** — 게이트가 `args.expand and via_objects` 라 서버 expand 에 그대로 위임한다.
  - **RECURRENCE-ID 오버라이드는 미반영**(기존 `free_slots` 한계와 동일, 문서화). 전개 실패는 마스터 1건 보수 폴백 + **stderr 경고**로 표면화한다(무음 금지 — stdout JSON 은 오염하지 않는다).
  - 회귀 봉인: 단위(전개·종일 shape·창 밖 드롭·실패 폴백) + **배선**(objects 전개·`--expand` 미지정 현행 유지·search 경로 위임·stderr 경고). 뮤테이션 4종(전개 제거·배선 게이트 off·`via_objects` 조건 제거·창 밖 마스터 잔존) 전건 RED 실측.

### Changed

- **`recurrence_start` 필드 신설** — 모든 정규화 이벤트에 균일하게 실린다(마스터·단발은 `null`). 소비자가 shape 분기 없이 회차를 구분할 수 있다.

### Verified

- 단위/배포형 **139 passed, 0 skipped** (+11: organizer 9 · 전개 단위 6 · 배선 5 — 기존 119 대비).
- 실계정 라이브(네이버 objects 경로 반복 일정 노출)는 **미검증** — 네트워크 접근 없이 작업했다. 합성 RRULE 픽스처와 배선 테스트로만 봉인했으므로, 라이브 확인은 별도로 남는다.

## [0.3.0] — 2026-08-20 (이슈 #1514)

Google Calendar MCP 커넥터 벤치마킹에서 확인된 세 갭을 채운다 — 빈 시간 제안·텍스트 검색·uid 단건 상세. 겹침 계산을 LLM 암산에서 결정론 코드로 옮기는 것이 핵심이다.

### Added

- **`find_free_slots.py`** — 빈 시간 제안(커넥터 `suggest_time` 동형). 전 캘린더 조회 후 **클라이언트 측 busy 병합**으로 근무시간 창 안의 빈 구간을 결정론 계산한다(서버 free-busy REPORT 비의존 — iCloud·네이버·custom 전부 성립). `--from/--to`(기본 now~+7d)·`--duration`(분, 기본 60)·`--work-hours`(기본 09:00-18:00)·`--include-weekends`(기본 평일만)·`--ignore-all-day`·`--limit`. busy 판정: `STATUS:CANCELLED`·`TRANSP:TRANSPARENT` 제외, 종일 이벤트는 기본 busy. **RRULE 마스터의 클라이언트 전개**(EXDATE 반영, dateutil — icalendar 기존 의존이라 requirements 불변)로 네이버 objects 경로에서도 반복 일정을 정확히 반영. 범위는 **"내 빈 시간" 한정**(타인 free/busy는 CalDAV 구조상 불가 — SKILL.md 명시). 순수 로직은 `free_slots.py` 분리.
- **`list_events.py --query`** — 텍스트 필터(커넥터 `search_events` 동형). SUMMARY/DESCRIPTION/LOCATION 대상 대소문자 무시 substring, **클라이언트 측·sanitize 후 매칭**(화면 표시와 필터 결과 일치).
- **`get_event.py`** — uid 단건 상세(내부 `find_event_by_uid` 재사용, etag 포함). "조회 → uid 확보 → 단건" 라우팅 경로 확보.
- **`delete_event.py --occurrence`** (마스터 승인 확장 ②) — 반복 일정 단일 회차 삭제(EXDATE 추가, 시리즈 유지). 날짜만 주면 그 날의 회차 자동 특정(같은 날 복수 회차는 `occurrence_ambiguous`), 실재 검증(`occurrence_not_found`·`not_recurring`), confirm 게이트(`--yes`)·ETag 가드 동일 적용. EXDATE 는 마스터 DTSTART 동형(종일=DATE, 시각=동일 TZ)으로 넣고 **수정 후 재조회로 반영 검증** — 서버 무음 무시 시 `exdate_not_applied` 로 표면화(성공 위장 차단). 회차 전개는 `free_slots.rrule_occurrences` 공유. RECURRENCE-ID 오버라이드 시리즈는 미고려(문서화).
- **`create_event.py --check-conflicts`** (옵트인, 마스터 승인 확장) — 생성 전에 전 캘린더에서 같은 시간대 겹침을 조회해 응답 `conflicts:[...]` 로 표면화(생성은 막지 않음). 판정은 `free_slots.overlapping_components` 공유(CANCELLED·TRANSPARENT 제외, RRULE 클라이언트 전개 — free-slots와 conflicts가 갈라지지 않는다). 기본(플래그 미지정)은 조회 왕복 없이 현행 유지. 조회 실패는 생성을 막지 않되 `conflicts:null`+`conflicts_error` 로 명시 표면화(무음 금지). RRULE 생성 이벤트는 첫 회차 창만 검사.

### Fixed (릴리즈 전 — codex 적대 리뷰 findings 3건, 제안 표면의 조용한 실패)

- **`find_free_slots.py` fail-closed** [P1] — 캘린더 조회 예외를 빈 목록으로 접어 그 캘린더의 일정이 통째로 빈 시간으로 제안되던 결함. 하나라도 실패 시 부분 결과 대신 `calendar_fetch_failed`(exit 1, 실패 캘린더·사유 목록) — hyve Go `executeCalendarFreeSlots` 와 동일 계약.
- **`create_event.py --check-conflicts` 부분 실패 표면화** [P2] — 조회 실패 캘린더가 무충돌로 위장되던 결함. 생성(advisory)은 막지 않되 `conflict_check:"partial"` + `failed_calendars` 로 부분 결과임을 명시.
- **RRULE 전개 실패 경고** [P2] — `busy_intervals` 의 마스터 1건 보수 폴백이 무음이던 결함. free-slots 응답에 `warning` + `rrule_expand_failures:[{uid,summary}]` 를 실어 소비자가 제안에 단서를 달 수 있게 함.
- 셋 다 결함 주입 단위 테스트로 봉인(뮤테이션 3종 주입→RED→원복 GREEN 실측, `tests/test_silent_failure_guards.py`).

### Verified

- **라이브(iCloud 실계정)**: 실제 일정 회피 실측 — 기존 일정(15:20-16:20)·opaque 종일 이벤트를 피하고 TRANSPARENT 종일은 열림. 테스트 이벤트 생성 → 슬롯이 정확히 갈라짐(09-10, 11:30-18) → `--query` 제목·장소 매칭 → `get_event` 상세 → 삭제·잔존 0.
- **라이브(네이버 실계정, objects 경로)**: 단건 + 반복(WEEKLY;COUNT=3) 생성 → busy 4건(반복 3회차 클라이언트 전개 정확) → 슬롯 회피 → `--query`·`get_event` → 삭제·잔존 0.
- 단위/배포형 **119 passed, 0 skipped** (+62: free_slots 순수 로직·conflicts·occurrence 판정 43 · 조용한 실패 가드 6 · query 매칭 3 · deployed 계약 10).
- **라이브(`--check-conflicts`)**: iCloud·네이버 실계정 — 겹치는 시간 생성 시 기존 이벤트가 `conflicts` 에 표면화되고 생성은 진행, 겹침 없는 시간은 `conflicts:[]`, 플래그 미지정은 필드 없음(현행 유지). 검증 후 완전 정리.
- **라이브(`--occurrence`)**: iCloud — 주간 COUNT=4 에서 2회차만 삭제 → `--expand` 재조회로 그 회차 부재·나머지 3회차 존재 실증, free-slots 도 그 시간 free 로 정합. 네이버(직접 PUT 폴백 경로) — EXDATE 반영 재조회 검증 통과 + free-slots busy 2건(잔여 회차만). 검증 후 완전 정리.



### Changed

- `compatibility` 라벨을 `Claude Code & Cowork` 로 교체 (#1280) — Cowork 전용 오해 제거.
- 의존성 설치 안내를 `uv pip install --system` 에서 `python3 -m pip install` 로 교체 (#1281).
- `.env` 위치 안내를 "작업 폴더(Cowork 연결 폴더 / Claude Code 프로젝트 루트)" 로 일반화하고 셸 환경변수·`~/.claude/settings.json` 의 `env` 경로를 명시 (#1282).

## [0.2.5] — 2026-07-26 (이슈 #1279)

### Changed

- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## [0.2.4] - 2026-07-11

### Fixed
- **Windows cp949 stdio 파이프 디코드 실패** (#1036) — CLI 진입 공통(`cli_common.py`)과 `check_env.py` 에서 stdout/stderr 를 utf-8 로 reconfigure. locale(cp949)로 인코딩된 JSON `detail` 한국어 안내가 utf-8 부모 프로세스(subprocess 파이프)의 디코드를 깨뜨려 stdout 이 None 이 되던 문제 해소. deployed 테스트 2건(unsupported_provider bogus/google)이 Windows 에서 GREEN 복귀.

## [0.2.3] - 2026-06-29

### Changed
- **구글 캘린더 비목표 확정**(#686): 구글 캘린더는 **Claude 공식 Google Calendar 커넥터**가 이미 지원하므로, 본 스킬에서는 OAuth 트랙으로 **중복 구현하지 않는다 — 비목표(non-goal)**. 문서·런타임 메시지의 '별도 트랙으로 분리/후속 버전 대상/준비 중' 같은 **미래 약속** 표현을 제거하고 '지원하지 않음 + 공식 커넥터 사용'으로 못 박았다(SKILL.md·README.md·GUIDE.md, `cli_common`의 `unsupported_provider` detail). 런타임 동작(`google` → `unsupported_provider` exit 1)은 0.2.2에서 이미 구현됨 — 본 버전은 **의도 명문화**다. 마이크로소프트(Outlook)·카카오도 '현재 미지원'으로 동일 표기.

## [0.2.2] - 2026-06-29

### Changed
- **미지원 provider 분기**(#682): 지원하지 않는 provider(`google`·`outlook`·`kakao` 등 OAuth/iCal 트랙)를 요청하면 이제 `unsupported_provider`(exit 1)를 반환하고 `detail`에 지원 목록(`icloud`·`naver`·`custom`)을 담는다. 기존에는 `credentials_missing`("not configured, set its env vars")으로 빠져 "환경변수만 채우면 된다"는 오해를 줬다(미지원 provider는 채울 변수 자체가 없음). 지원하지만 **미설정**인 provider는 기존대로 `credentials_missing`을 유지한다(계약 경계).
- `caldav_providers`에 `is_supported_provider()`·`supported_provider_names()` 추가, `cli_common.resolve_provider_or_exit`가 자격증명 조회 전 미지원 여부를 먼저 분기.

### Tests
- 단위(`is_supported_provider`·`supported_provider_names`) + 배포형(google→unsupported_provider, bogus→unsupported_provider, 미설정 naver→credentials_missing) 추가. **57 passed, 0 skipped**.

## [0.2.1] - 2026-06-01

### Performance
조회 성능을 실사용 벤치마크 기반으로 대폭 개선:
- **provider별 조회 전략 분기**: iCloud/custom은 표준 time-range search(빈 결과 신뢰), 네이버만 objects 폴백. 네이버용 fallback이 iCloud의 정상 빈 캘린더에 오발동해 조회가 무한정 느려지던 버그 수정.
- **components PROPFIND 제거**(list_events): 캘린더당 supported-components 조회가 병목(10개 ~4s)이었으나 `event=True` search엔 불필요.
- **calendar-home url 디스커버리 캐싱**(데이터 루트 하위 `.itda-skills/calendar/cache/`, TTL 7일, `--refresh`로 무효화): iCloud principal 디스커버리(~1.7s)를 skip. → iCloud 전체 조회 약 8.5s → 2.7s.
- **캘린더 병렬 search**(ThreadPoolExecutor): 순차 REPORT를 동시 실행.

### Notes
- 벤치마크로 구조 규명: **iCloud(search)는 데이터량 둔감**(26→90건 ~4.4s 일정), **네이버(objects)는 캘린더 총 이벤트 수에 비례**(0→30개 1.8→4.2s) — time-range REPORT 미지원의 구조적 한계. `--calendar`로 좁히면 완화. `--expand` 반복 전개는 iCloud/custom만 지원(네이버 objects 경로는 마스터 이벤트만).
- 단위/배포형 **53 passed, 0 skipped** (`test_list_via_objects_flag` 추가).

## [0.2.0] - 2026-06-01

### Added
- **네이버 캘린더** 지원 (트랙 1). `caldav.calendar.naver.com`, itda-email의 `NAVER_EMAIL`/`NAVER_APP_PASSWORD`를 그대로 공유(네이버 메일 앱비번이 캘린더에도 동작). 로그인은 전체 이메일.

### Changed
- `update_event`: `--start`만 변경 시 기존 일정 길이(duration)를 유지해 종료시간도 함께 이동(`DTSTART > DTEND` 모순 방지 — iCloud가 모순 이벤트를 거부).
- `caldav_client`: 네이버 호환 폴백 — (1) 조회는 `comp-filter`/`time-range` REPORT가 비면 objects 열거 후 클라이언트 측 시간범위 필터, (2) 수정은 `ev.save()` 실패 시 직접 PUT(네이버의 `200 OK` 응답 대응, iCloud는 `ev.save()` 유지), (3) `find_event_by_uid`는 events()→objects() 순 탐색.

### Verified
- **네이버 라이브 왕복**(실계정 '내 캘린더', 생성→조회→수정→삭제, 미래 날짜·완전 정리) + **iCloud 회귀** 통과. 단위/배포형 52 passed, 0 skipped.

### Notes
- 네이버는 ETag 미제공 → 동시성 가드 best-effort(read-modify-write 의존). 캘린더 생성(make_calendar) 미지원.

## [0.1.0] - 2026-06-01

### Added
- 초기 출시 — CalDAV 기반 캘린더 일정 조회·생성·수정·삭제 (SPEC-CALENDAR-001, 트랙 1).
- **Providers**: iCloud(앱 전용 비밀번호, itda-email과 자격증명 공유) + custom CalDAV(`CALDAV_URL`).
- **Scripts**: `check_env` · `check_connection` · `list_calendars` · `list_events` · `create_event` · `update_event` · `delete_event`.
- **Events**: 시각/종일(VALUE=DATE) 이벤트, 시간대(기본 `Asia/Seoul`), 반복(RRULE), 알림(VALARM, N분 전 DISPLAY).
- **정확성·안전**: ETag 낙관적 동시성(`--etag` → `etag_conflict` exit 2), 삭제 확인 게이트(`--yes` 없으면 `confirm_required`), 조회 결과 프롬프트 인젝션 sanitize(itda-email 재사용).
- **멀티계정**: 환경변수 `_{SUFFIX}` 규칙(itda-email 동형).
- 구현: 외부 `caldav` + `icalendar` 라이브러리(`uv pip install --system caldav icalendar`).

### Verified
- **라이브 검증(iCloud 실계정)**: 전용 테스트 캘린더에서 생성→조회→수정→삭제 왕복 + RRULE 보존 + KST 타임존 + ETag 충돌 거부 + 삭제 확인 게이트. 검증 후 테스트 캘린더 완전 제거(사용자 데이터 영향 0).
- **단위/배포형 테스트**: 42 passed, 0 skipped (event_model·providers·cli_common 단위 + subprocess 배포형 계약).

### Known limits (v0.1.0)
- VTODO(미리알림)·참석자 초대·free/busy는 범위 밖(iCloud CalDAV 제약).
- iCloud는 UID REPORT(`event_by_uid`)를 412로 거부 → 이벤트 열거 매칭으로 우회(대형 캘린더에서 수정/삭제가 느릴 수 있음).
- 네이버 캘린더, 구글/마이크로소프트/카카오는 후속 버전(트랙 1 추가 / 트랙 2·3 별도 SPEC).
