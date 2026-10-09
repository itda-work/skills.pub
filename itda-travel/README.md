# itda-travel — 여행 스킬팩

## 포함 스킬 (전체)

| 스킬 | 기능 |
|---|---|
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다. |
| [`hotel-search`](skills/hotel-search/SKILL.md) | 같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾는 스킬입니다. |


여행에 필요한 일을 자연어로 처리하는 스킬 모음입니다. 현재 두 가지를 다룹니다:
**숙소 요금 비교**, **여행지에서 지금 뜨는 맛집 탐지**.

> 2026-10-06 — 열차 예약 스킬 `train-ktx`·`train-srt` 는 저장소에서 지웠습니다. KTX(옛 SRT 구간 포함)는 코레일+ 앱이나
> letskorail.com 에서 조회·예매해 주세요.

## 포함 스킬

| 스킬 | 하는 일 | 데이터 소스 |
|------|--------|-----------|
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 지역·테마의 '지금 뜨는' 맛집·음식 트렌드 탐지 | 네이버 자동완성·데이터랩·지역검색·블로그검색(itda-hyve 경유) |
| [`hotel-search`](skills/hotel-search/SKILL.md) | 같은 호텔의 예약 사이트별 요금 비교 | 예약 사이트 공개 화면(itda-hyve 경유) |

각 스킬의 자세한 사용법은 해당 폴더의 GUIDE.md를 참조하세요.

## 시작 전: 자격증명

요청은 itda-hyve(로컬 MCP 서버)가 보내고, 키는 **itda-hyve 앱의 시크릿 탭**에만 둡니다 — 스킬은 환경변수·Claude Code 설정의
`env`·`.env` 같은 파일을 읽지 않습니다(itda-work/skills#45·#46). 키 값을 대화창에 붙여 넣지 마세요.

| 스킬 | 필요한 것 |
|---|---|
| **hotel-search** | 없음 |
| **eatery-trend** | 네이버 오픈API 키 — 시크릿 탭에 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`(web-search 와 같은 이름). 월 검색량(네이버 검색광고)은 itda-hyve 서명 기능을 기다려 지금은 빠집니다 |

## 설치

```bash
claude plugin marketplace add itda-work/skills.pub
claude plugin install itda-travel@itda-skills-pub
```

## 로컬 테스트

```bash
# 저장소 루트에서 (스킬별 분리 — CI와 동일)
just test itda-travel

# 또는 플러그인 디렉토리 로드
claude --plugin-dir itda-travel
```

> 스킬마다 같은 모듈명이 생길 수 있어 `pytest itda-travel`
> 로 전체를 한 번에 실행하면 모듈 캐시가 충돌할 수 있습니다. `just test`(및 CI)는 스킬별로
> 분리 실행하므로 안전합니다. 단일 스킬은 `just test-skill itda-travel <skill>`.

## 비목표

- **eatery-trend**: 인스타그램 직접 스크래핑(영구) · 예약/결제(캐치테이블 영역) ·
  실시간 분 단위(데이터랩 일·주 lag 수용).

## 라이선스

MIT (plugin.json 및 각 SKILL.md frontmatter 일치).
