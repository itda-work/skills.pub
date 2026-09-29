# calendar

itda-hyve 에 등록한 네이버·아이클라우드·직접 입력(CalDAV 주소) 계정의 캘린더 일정을 자연어로 **조회·검색·추가·수정·삭제**하고 **빈 시간을 찾아주는** 스킬.

> "내일 3시 회의 추가해줘" · "이번 주 일정 보여줘" · "다음 주에 1시간 빈 시간 찾아줘" · "OO 프로젝트 회의 다 찾아줘" · "토요일 약속 취소해줘"

이 README는 개요다. 실제 사용 절차는 **[GUIDE.md](GUIDE.md)**, 런타임 실행 계약은 **[SKILL.md](SKILL.md)**, 변경 이력은 **[CHANGELOG.md](CHANGELOG.md)** 를 본다.

---

## 동작 경로

0.5.0 부터 일정은 **itda-hyve(사용자 PC 의 로컬 MCP 서버, 0.9.0 이상)의 캘린더 도구로만** 다룬다. 받는 곳: https://github.com/itda-work/itda-hyve.pub/releases/latest
Cowork 샌드박스는 외부 네트워크가 막혀 있어 스킬이 CalDAV 서버에 직접 붙을 수 없기 때문이다(#1710).

| 도구 | 하는 일 |
|---|---|
| `accounts_list` | 계정 목록 + 계정별 캘린더 지원 여부(`calendar.supported`·`reason`) |
| `calendar_list` | 캘린더 목록 |
| `calendar_events` | 기간 조회·검색(`query`)·반복 전개 요청(`expand`) |
| `calendar_get` | uid 로 한 건(설명 전문·현재 etag) |
| `calendar_put` | 생성(uid 없음)·수정(uid + etag) |
| `calendar_delete` | 삭제 — 미리보기 → 사용자 확인 → `confirm_token` 2단계 |

계정·비밀번호는 itda-hyve GUI 에만 있다. 이 스킬은 환경변수·`.env`·자격증명을 다루지 않는다.

## 기능

- **일정 조회·검색·추가·수정·삭제** + 캘린더 목록
- **빈 시간 제안** — 조회 결과로 내 캘린더의 빈 구간을 계산(기본 평일 09~18시)
- **반복(RRULE) · 알림 · 종일/시각 일정 · 시간대(기본 Asia/Seoul)**
- **안전장치** — ETag 충돌 감지(`etag_conflict`), 삭제 2단계 확인(토큰은 발급마다 무작위·10분·1회용), 참석자 있는 일정·서버 etag 가 없거나 약한(`W/`) 일정·원문이 온전하지 않은 일정의 수정·삭제 거부(조회는 됨 — 캘린더 앱에서 직접), 일정 내용은 외부 데이터로 취급

## 제약

- 반복 일정은 시리즈 단위로만 수정·삭제한다(회차 하나만은 불가).
- 네이버는 서버가 반복 일정을 전개하지 않는다 — `unexpanded_recurring`·`rrule` 로 회차를 스스로 판단한다.
- 참석자 초대·타인 빈 시간·할 일(VTODO)·캘린더 관리는 범위 밖.

## 스크립트·의존성이 없다

0.7.0(itda-work/skills#19)에서 옛 `scripts/`(Python `caldav` 직접 접속 CLI)·`requirements.txt`(caldav·icalendar)·`deps.json`·`tests/` 를 지웠다.
마지막 사용처였던 `itda-work:morning-brief`(0.3.0, #18)·`itda-work:time-audit`(0.2.0, #19)이 itda-hyve `calendar_events` 로 옮겨 갔다.
이 스킬은 SKILL.md 절차와 itda-hyve 도구만으로 동작하며 설치할 파이썬 패키지가 없다.
