---
name: train-srt
description: >
  SRT는 2026-09-01부터 KTX로 통합되어 이 스킬은 기능을 갖지 않습니다.
  "수서에서 부산 SRT 찾아줘", "SRT 예약해줘", "SRT 계정 확인해줘"처럼 SRT로
  요청이 들어오면 통합 사실을 안내하고 train-ktx로 넘깁니다.
  옛 SRT 구간(수서·동탄·평택지제)의 검색·예약은 train-ktx가 담당합니다.
  [책임 경계] 본 스킬은 통합 안내 전용 스텁 —
  실제 검색·예약은 itda-travel:train-ktx 가 전담합니다.
license: MIT
compatibility: "Python 3.10+. 외부 의존 없음(구 SRTrain 의존 제거)."
user-invocable: true
allowed-tools: Bash, Read
argument-hint: "수서에서 부산 SRT (→ train-ktx 로 안내)"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "domain"
  version: "0.3.0"
  status: "deprecated"
  created_at: "2026-06-05"
  updated_at: "2026-09-01"
  tags: "srt, srail, ktx, korail, train, deprecated, travel"
---

# train-srt (폐기 — 통합 안내 전용)

**SRT는 2026-09-01부로 폐지되고 KTX로 통합됐습니다.** 이 스킬은 검색·예약
기능을 갖지 않으며, 어떤 서브커맨드로 호출해도 통합 안내를 출력하고 `rc=2` 로
종료합니다(#1624).

## 무슨 일이 있었나

- 9월 1일 이후 **운행**하는 열차는 코레일+ 앱·코레일 홈페이지에서만 예매할 수
  있습니다. SR 앱(etk.srail.kr) 예매는 8월 31일 운행분까지였습니다.
- 옛 SRT 전용역(**수서·동탄·평택지제**)은 이제 코레일이 판매하며,
  `train-ktx` 가 담당합니다.
- 옛 SRT 열차는 코레일 표기로 **"KTX" / "KTX-산천"** 으로 나옵니다. 같은 열차입니다.

라이브 실측(#1624, 2026-09-02 기준)으로 확인: 수서→부산 06:00 편이 SR API 에서는
`SRT 303`, 코레일 API 에서는 `KTX-산천 303` 이고 **열차번호·종별코드·요금(52,400원)이
일치**합니다. 같은 재고를 코레일이 팝니다.

## Claude 라우팅 가이드

**규칙 1 — SRT 요청은 train-ktx 로 넘깁니다**
사용자가 "SRT" 라고 불러도 그대로 `train-ktx` 로 처리합니다. 역명을 바꿀 필요가
없습니다(수서·동탄·평택지제 모두 지원하며 `지제`·`평택` 은 `평택지제` 로 정규화).
통합 사실은 **한 줄로만** 알리고, 사용자를 붙잡지 말고 바로 검색을 진행합니다.

**규칙 2 — 이 스킬의 스크립트를 기능 목적으로 실행하지 않습니다**
`scripts/main.py` 는 안내만 하고 `rc=2` 로 끝납니다. 실행 결과를 "검색 실패" 로
보고하지 말고, `train-ktx` 로 재시도합니다.

**규칙 3 — SR 경로를 되살리지 않습니다**
SR 조회 API 는 지금도 응답을 주지만, **9월 1일 이후 운행분은 SR 에서 예매할 수
없습니다.** 그 경로를 되살리면 예약 단계에서 조용히 실패해 사용자가 좌석을 잡은
줄 알게 됩니다. 우회 구현을 제안하지 않습니다.

## 실행 (안내 확인용)

```bash
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/train-srt}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/train-srt' 2>/dev/null | head -1)

python3 "$SKILL_DIR/scripts/main.py"          # 통합 안내 (rc=2)
python3 "$SKILL_DIR/scripts/main.py" --json   # 기계 소비자용 JSON (rc=2)
```

JSON 계약: `{status: "integrated", integration_date, successor_skill,
former_srt_stations[], message, booking_channel}`.

## 제약 (Exclusions)

- **검색·예약·예약조회·계정확인** — 전부 폐기(#1624). `train-ktx` 사용.
- **SR API 재도입** — 영구 비목표(위 규칙 3).
- 자격증명(`SRT_USER_ID`/`SRT_PASSWORD`)을 읽지 않습니다. `.env` 에 남아 있어도
  이 스킬은 접근하지 않습니다.
