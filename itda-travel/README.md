# itda-travel — 여행 스킬팩

## 포함 스킬 (전체)

| 스킬 | 기능 |
|---|---|
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다. |
| [`flight-search`](skills/flight-search/SKILL.md) | Google Flights 공개 검색으로 항공권을 조회·비교하는 스킬입니다. |
| [`hotel-search`](skills/hotel-search/SKILL.md) | 같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾는 스킬입니다. |
| [`place-finder`](skills/place-finder/SKILL.md) | 카카오맵 기준으로 근처 장소를 목적별로 찾아주는 스킬입니다. |
| [`train-ktx`](skills/train-ktx/SKILL.md) | KTX 고속열차를 검색하고 예약하는 스킬입니다. |
| [`train-srt`](skills/train-srt/SKILL.md) | SRT는 2026-09-01부터 KTX로 통합되어 이 스킬은 기능을 갖지 않습니다. |


여행에 필요한 일을 자연어로 처리하는 스킬 모음입니다. 현재 다섯 가지를 다룹니다:
**KTX·SRT 열차 검색·예약**, **항공권 검색·날짜별 최저가 비교**, **여행지에서 지금 뜨는 맛집 탐지**, **카카오맵 근처 장소 찾기**.

## 포함 스킬

| 스킬 | 하는 일 | 데이터 소스 |
|------|--------|-----------|
| [`train-ktx`](skills/train-ktx/SKILL.md) | KTX 열차 검색·예약 (결제·취소는 사용자 직접) | 코레일 비공식 API (korail2 계열) |
| [`train-srt`](skills/train-srt/SKILL.md) | SRT(수서고속철) 검색·예약 (결제·취소는 사용자 직접) | SR 비공식 API (SRTrain) |
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 지역·테마의 '지금 뜨는' 맛집·음식 트렌드 탐지 | 네이버 데이터랩·검색·검색광고 API |
| [`flight-search`](skills/flight-search/SKILL.md) | Google Flights 항공권 검색·날짜별 최저가 비교 (예약·결제는 사용자 직접) | Google Flights 공개 표면 (fast-flights) |
| [`place-finder`](skills/place-finder/SKILL.md) | 위치 기준 근처 장소 목적별 검색 (맛집·카페·술집·숙박·관광·편의·교통) | 카카오맵 비공식 검색 |

각 스킬의 자세한 사용법은 해당 폴더의 GUIDE.md를 참조하세요.

## ⚠️ 열차 예약 스킬 주의 (train-ktx · train-srt)

`train-ktx`·`train-srt` 은 코레일/SR **비공식 API**를 사용합니다 (ToS 위반 소지,
사업자 측 변경 시 동작 불가 가능). **검색·예약까지만** 하며 **결제·취소는 사용자가
직접** 합니다. 예약 후 결제기한 내 미결제 시 좌석은 자동 취소됩니다. 매크로(취소표
자동낚기)는 제공하지 않으며, 예약·결제·노쇼 책임은 사용자 본인에게 있습니다.

## ⚠️ 항공권 스킬 주의 (flight-search)

`flight-search` 는 **Google Flights 공개 검색 표면**을 조회합니다 (Google ToS 관점
회색지대, Google 변경 시 동작 불가·상세 파싱 누락 가능). **검색·비교까지만** 하며
**예약·결제·좌석지정은 하지 않습니다** — 제공 링크는 Google Flights 검색 링크일
뿐, 실제 구매는 사용자가 직접 합니다. 표시 가격은 조회 시점 기준이며 실제
결제가와 다를 수 있습니다. 매크로(반복 폴링)는 제공하지 않습니다.

## ⚠️ place-finder 주의

`place-finder` 는 카카오맵 **비공식 검색**을 사용합니다 (ToS 위반 소지, 카카오 측
변경 시 동작 불가 가능). **읽기 전용·1회성** 조회만 하며, 실시간 영업중 여부·메뉴·
영업시간은 제공하지 않습니다(카카오맵 링크 위임). 매크로(자동 반복 조회)는 제공하지
않습니다.

## 시작 전: 자격증명

**train-ktx** — 코레일 회원 계정:

```
KORAIL_USER_ID=...      # 회원번호 8자리 / 휴대폰 / 이메일
KORAIL_PASSWORD=...
```

**train-srt** — SR(수서고속철) 회원 계정:

```
SRT_USER_ID=...         # 회원번호 / 휴대폰 / 이메일
SRT_PASSWORD=...
```

**eatery-trend** — 네이버 공개 API 키 (자동완성만 무인증):

```
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
NAVER_SEARCHAD_ACCESS_KEY=...
NAVER_SEARCHAD_SECRET_KEY=...
NAVER_SEARCHAD_CUSTOMER_ID=...
```

**flight-search** — **자격증명 불필요**(Google Flights 공개 표면 무인증). 처음 한
번 조회 도구(`fast-flights`) 설치만 필요하며, 미설치 시 스킬이 안내합니다.

**place-finder** — 자격증명이 **필요 없습니다**(카카오 개발자 키 없이 동작).

조회 우선순위: 셸 환경변수 > `~/.claude/settings.json` 의 env > 실행 위치/홈의
`.env`. 키가 없으면 해당 스킬이 fail-loud로 설정 방법을 안내합니다(크래시 아님).

- 네이버 OpenAPI 키: [developers.naver.com](https://developers.naver.com)
- 네이버 검색광고 키: [searchad.naver.com](https://searchad.naver.com) > 도구 > API 관리자
- 코레일 회원가입: [letskorail.com](https://www.letskorail.com) · SR 회원가입: [etk.srail.kr](https://etk.srail.kr)

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

> train-ktx·train-srt이 같은 모듈명(`stations` 등)을 써서, `pytest itda-travel`
> 로 전체를 한 번에 실행하면 모듈 캐시가 충돌합니다. `just test`(및 CI)는 스킬별로
> 분리 실행하므로 안전합니다. 단일 스킬은 `just test-skill itda-travel <skill>`.

## 비목표

- **train-ktx · train-srt**: 결제 자동완료 · 예약 취소 · 매크로/취소표 자동낚기 ·
  환승 (전부 v1 비목표 — 취소·매크로는 영구). train-ktx은 KTX, train-srt은 SR 전용.
- **eatery-trend**: 인스타그램 직접 스크래핑(영구) · 예약/결제(캐치테이블 영역) ·
  실시간 분 단위(데이터랩 일·주 lag 수용).
- **flight-search**: 예약·결제·좌석지정·취소(영구) · 로그인 회원가·할인·마일리지
  적용가 · CAPTCHA 우회 · Skyscanner 직접 조회 (전부 비목표).
- **place-finder**: 예약·결제·길찾기 · 실시간 영업중·메뉴·영업시간(카카오맵 링크 위임) ·
  매크로/반복 폴링(영구) · 공식 카카오 로컬 API 백엔드(v1 미구현).

## 라이선스

MIT (plugin.json 및 각 SKILL.md frontmatter 일치).
