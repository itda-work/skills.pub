# itda-travel — 여행 스킬팩

## 포함 스킬 (전체)

| 스킬 | 기능 |
|---|---|
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 여행지·동네의 '지금 뜨는' 맛집과 음식 트렌드를 검색량 surge로 탐지하는 스킬입니다. |
| [`hotel-search`](skills/hotel-search/SKILL.md) | 같은 호텔의 여러 예약 사이트(Booking·Agoda·Trip.com·Klook·공식사이트) 실시간 요금을 한 번에 비교해 최저가와 각 사이트 예약 링크를 찾는 스킬입니다. |
| [`train-ktx`](skills/train-ktx/SKILL.md) | KTX 고속열차를 검색하고 예약하는 스킬입니다. |
| [`train-srt`](skills/train-srt/SKILL.md) | SRT는 2026-09-01부터 KTX로 통합되어 이 스킬은 기능을 갖지 않습니다. |


여행에 필요한 일을 자연어로 처리하는 스킬 모음입니다. 현재 세 가지를 다룹니다:
**KTX·SRT 열차 검색·예약**, **숙소 요금 비교**, **여행지에서 지금 뜨는 맛집 탐지**.

## 포함 스킬

| 스킬 | 하는 일 | 데이터 소스 |
|------|--------|-----------|
| [`train-ktx`](skills/train-ktx/SKILL.md) | KTX 열차 검색·예약 (결제·취소는 사용자 직접) | 코레일 비공식 API (korail2 계열) |
| [`train-srt`](skills/train-srt/SKILL.md) | SRT(수서고속철) 검색·예약 (결제·취소는 사용자 직접) | SR 비공식 API (SRTrain) |
| [`eatery-trend`](skills/eatery-trend/SKILL.md) | 지역·테마의 '지금 뜨는' 맛집·음식 트렌드 탐지 | 네이버 데이터랩·검색·검색광고 API |

각 스킬의 자세한 사용법은 해당 폴더의 GUIDE.md를 참조하세요.

## ⚠️ 열차 예약 스킬 주의 (train-ktx · train-srt)

`train-ktx`·`train-srt` 은 코레일/SR **비공식 API**를 사용합니다 (ToS 위반 소지,
사업자 측 변경 시 동작 불가 가능). **검색·예약까지만** 하며 **결제·취소는 사용자가
직접** 합니다. 예약 후 결제기한 내 미결제 시 좌석은 자동 취소됩니다. 매크로(취소표
자동낚기)는 제공하지 않으며, 예약·결제·노쇼 책임은 사용자 본인에게 있습니다.


## 시작 전: 자격증명

**train-ktx** — 코레일 회원 계정:

```
KORAIL_USER_ID=...      # 회원번호 8자리 / 휴대폰 / 이메일
KORAIL_PASSWORD=...
```

**train-srt** — 자격증명을 읽지 않습니다(SR 조회·예약 폐기, `train-ktx` 로 안내만 합니다).

**eatery-trend** — 네이버 공개 API 키 (자동완성만 무인증):

```
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
NAVER_SEARCHAD_ACCESS_KEY=...
NAVER_SEARCHAD_SECRET_KEY=...
NAVER_SEARCHAD_CUSTOMER_ID=...
```

**hotel-search** — 자격증명이 **필요 없습니다**(키 없이 동작). 요청은 itda-hyve(로컬 MCP 서버)가 보냅니다.

위 값은 **환경변수**로 넣습니다 — Claude Code 에서는 셸 환경변수 또는
`~/.claude/settings.json` 의 `env`(Claude Code 가 스킬에 전달). 스킬은 `.env` 같은
파일을 읽지 않습니다(itda-work/skills#45). 이 팩 스킬은 아직 Cowork 에서 키를 넣을
방법이 없습니다. 키가 없으면 해당 스킬이 fail-loud로 설정 방법을 안내합니다(크래시 아님).

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

## 라이선스

MIT (plugin.json 및 각 SKILL.md frontmatter 일치).
