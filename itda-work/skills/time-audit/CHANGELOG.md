# Changelog — time-audit

## [0.3.3] — 2026-10-01 (itda-work/skills#46)

### Changed

- `references/netbridge.md` 사본을 정본과 동기화 — `secret_missing` 은 그 소스 하나에 대한 멈춤이다: 다른 경로로 키를 넣지 않고(같은 API 를 다른 통로·다른 키로 부르지 않는다), 여러 소스를 묶는 스킬은 그 소스만 빼고 계속할 수 있다. 앞 판 뒤에 사본이 바뀌어 배포본 내용이 달라졌으므로 patch 를 올린다(skills v14.0.0 준비).

## [0.3.2] — 2026-09-30 (itda-work/skills#46, #47)

### Changed

- 공개된 적 없는 itda-hyve 판(0.9.1~0.10.0) 표기를 공개판 0.10.1 로 맞췄다(0.9.0 다음 공개판이 0.10.1 — 그 사이 판은 사용자가 설치할 수 없다, itda-work/skills#46). compatibility·SKILL.md 설치 안내·옛 판 판별 문장·GUIDE.md 를 `0.10.1 이상` 으로, `collect_events.py` 의 `itda_hyve_outdated` 문구도 0.10.1 로(판정 조건은 그대로 — `calendar` 필드 부재).
- `references/netbridge.md` 사본을 정본과 동기화 — itda-hyve 기능 판 표기를 공개판 기준으로 바꿨다(0.9.1~0.10.0 은 공개되지 않은 개발판이라 그 사이 기능을 모두 0.10.1 로 적는다, itda-work/skills#46).

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.3.1] — 2026-09-29 (itda-work/skills#44)

### Changed

- itda-hyve 설치·업데이트 안내의 받는 곳을 `https://itda.work/hyve/` 하나로 바꿨다(GitHub 릴리스 페이지 링크 제거, itda-work/skills#44). SKILL.md.
- `references/netbridge.md` 사본을 정본과 동기화 — 받는 곳 한 줄이 `https://itda.work/hyve/` 로 바뀌었다.

## [0.3.0] — 2026-09-28 (itda-work/skills#34)

### Changed

- itda-hyve 가 `calendar_events` 응답을 입력 폴더에 **직접** 쓴다 — `collect_events.py --plan` 이 인자에 `save_dir`(입력 폴더의
  호스트 경로 — 새 인자 `--save-dir`)·`save_as`·`overwrite: true` 를 싣는다. 모델은 요약(`saved_path`·`count`)만 받고 응답 JSON 을
  옮겨 적지 않는다(몇 주치 일정이면 수십 KB 였다). `--save-dir` 없는 `--plan` 은 `save_dir_required`(exit 2).
- 최소 itda-hyve **0.9.2**(0.9.1 은 공개하지 않는다). Cowork 는 연결 폴더가 필요하다. `itda_hyve_outdated` 문구도 0.9.2 로.

## [0.2.0] — 2026-09-28 (itda-work/skills#19)

### Changed

- 네이버·아이클라우드·CalDAV 소스를 **itda-hyve `calendar_events`** 경로로 옮겼다. 옛 경로(calendar 스킬의
  `scripts/list_events.py` 를 실행해 CalDAV 서버에 직접 접속)는 calendar 스크립트 제거(#19)와 함께 사라졌다.
  최소 itda-hyve 0.9.1.
- `source` 값 `itda-calendar` → `itda-hyve`.

### Added

- `scripts/collect_events.py` — morning-brief 0.3.0 과 같은 `--plan`/`--input` 방식. 계획이 호출(도구·인자·저장 파일)과
  조회 창(요청 기간 그대로)을 정하고, 저장된 응답에서 `timelog.json` 초안(`provisional: true`, 미배정)을 쓴다.
  네트워크·자격증명·환경변수를 쓰지 않는다(stdlib only).
- 부분본 차단: 계정 조회 실패·응답 누락·`truncated`·캘린더 일부 실패·전개 못 한 반복 규칙이 하나라도 있으면
  파일을 쓰지 않고 exit 1 로 전부 나열한다. 요청 기간 0건은 exit 3(파일 없음 — 다른 기간으로 대체하지 않는다).
- 서버가 전개하지 않은 반복 마스터(네이버)를 창 안 회차로 펼친다 — morning-brief `gather.py` 와 바이트 동일한
  사본이며 테스트가 동일성을 강제한다. 회차 수정본(recurrence_id)은 그 회차를 대신한다.
- `references/netbridge.md` 사본 동봉, 테스트 `tests/test_collect_events.py`(픽스처는 지어낸 `@sample.example.com` 응답).
- SKILL_DIR 확정 블록에 단일 `.skill` 업로드 경로(`.claude/skills`) 추가.

## [0.1.4] — 2026-07-28 (이슈 #1319)

### Changed

- itda-workmap → itda-coach 팩 이동 (workmap 팩 소멸, 여정 코칭 팩 재편). 스킬 이름·계약 불변.

## [0.1.3] — 2026-07-26 (이슈 #1279)

### Changed
- 실행 경로를 SKILL_DIR 확정 블록 기준으로 표준화 (#1279) — cwd 상대경로/저장소 경로 표기 제거.

## 0.1.2 (2026-07-24)

- D1·D2 기계 게이트 승격 (#1257, O2 후속 — 프롬프트 규율의 코드화): ① period 필수화 + 기간 밖 이벤트 전수 나열 exit 2(기간 무단 대체 차단) ② 제외(timed) 비율 >30% WARN(exclude 로 미배정 WARN 우회 차단) ③ `provisional: true` 시 사람용·JSON 출력에 잠정 마커 강제 각인(확정 인용 차단). timelog.json 계약·절차 동기화, 회귀 테스트 4건 추가(14 PASS)

## 0.1.1 (2026-07-24)

- 라이브 검증 (#1246, S2·S4·S5): 실 iCloud 캘린더 4주 58건 감사 — timelog 정규화 스키마·집계 exit 0·리포트 수치 전건 스크립트 출력 일치(어림 0건)·work-map 연계(제안만, 승인 후 수정) PASS. 빈 기간 엣지 FAIL 발견(D1)
- D1 수정: 요청 기간 0건 시 인접 기간 무단 대체·분석 강행 금지 명문화 — 확인 질문만 남기고 종료(2015→2025 무단 대체 실측 반려)
- D2 수정: 애매 이벤트는 exclude 아닌 미배정(WARN 우회 차단), 첫 실행 배정·제외안은 사용자 확인 전 "잠정", 난이도 임시 배정 금지 명문화
- 수치 규율 명확화: 파생 산술(비율·부분합)은 근거 수치 병기 시에만 허용

## 0.1.0 (2026-07-24)

- 최초 릴리즈 (#1244)
- 소스 겸용: 사용자 캘린더 MCP 커넥터(Google Calendar 등) · itda-work:calendar(CalDAV) · 내보내기 파일 — 에이전트가 timelog.json 계약으로 정규화, Python 은 MCP 를 직접 호출하지 않음
- 결정론 집계 `scripts/aggregate_time.py`: 카테고리·난이도별 시간/건수/평균, 주별 추이, 병목 후보(건당 최장), 미배정 비율 WARN(>20%), 겹침 탐지, 스키마 위반 전수 나열 후 exit 2
- 종일 일정은 건수만 집계(시간 합산 제외), 제외 일정은 내역 보존
- work-map.md 연계: 태스크 인벤토리를 카테고리 후보로, 4분면 실측 주석 제안(수정은 사용자 확인 후)
- 개념 출처: 퇴근길 AI "AI에게 의존하고 계시지는 않으신가요?" (2026-07-23) 트레이닝 1
