---
preset: equity-research-dark
version: 1.0
description: >
  트레이딩 터미널 감각의 다크 시장 보고 — 블랙 지배 + 옐로 희소 액센트 + mono 숫자,
  의미색(상승/하락)이 정보의 중심. Trading Yellow/Black 검증 팔레트(binance 계열) 기반.
colors:
  canvas: "#0B0E11"
  surface: "#1E2329"
  ink: "#EAECEF"
  muted: "#848E9C"
  primary: "#F0B90B"
  accent: "#F0B90B"
  hairline: "#2B3139"
  up: "#0ECB81"
  down: "#F6465D"
typography:
  display: "Consolas"          # 라틴/숫자 run 전용 — mono 숫자가 터미널 정체성. 한글은 안전 고딕
  body: "kr-safe-gothic"
semantic_convention: international   # krx 전환 시 up=레드/down=블루로 교체하고 범례 명시
rounded: 0.10
spacing: { margin: 0.7, gap: 0.3 }
motif: "옐로는 슬라이드당 1곳 이하(헤드라인 키워드·핵심 숫자) — 희소성이 곧 강조. 패널은 surface 색면 + 헤어라인"
do:
  - "숫자는 mono(라틴 run) + 크게 — 데이터가 주인공"
  - "상승/하락 의미색을 일관 적용(범례 1회 명시)"
  - "다크 위 차트는 축·라벨을 밝은 톤(ink/muted)으로"
dont:
  - "옐로 남용(2곳 이상이면 이미 과용)"
  - "순백 대형 면(다크 몰입 파괴)"
  - "저대비 회색 본문(muted 는 라벨 전용)"
---

# Equity Research Dark — 트레이딩 터미널 문법

## Overview

블랙 `#0B0E11` 풀블리드 위에 surface `#1E2329` 패널을 얹는 평면(flat) 구성 — 그라디언트·glow 없이
색면과 헤어라인만으로 위계를 만든다(PPTX 재현도 최상 조합). 옐로 `#F0B90B` 는 브랜드 시그니처이자
유일한 비-의미 액센트로, 슬라이드당 1곳 이하로 아낀다. 정보의 실질 색은 의미색이다:
상승 `#0ECB81` / 하락 `#F6465D` 가 모든 수치 방향을 즉시 읽히게 한다.

## 슬라이드 문법

- **표지**: 블랙 풀블리드 + 옐로 킥커 1줄 + 대형 타이틀 + 핵심 시세 스트립(현재가·등락·거래량, 의미색 적용).
- **시세/차트**: 풀폭 차트 + 하단 의미색 스탯 스트립, 또는 좌 차트 + 우 호가/지표 레일(surface 패널).
- **비교 그리드**: surface 카드에 종목/시나리오 비교 — 카드당 빅넘버 1개 + 의미색 변화율.
- **리스크/알림**: 좌 다크 패널(핵심 경고 빅넘버) + 우 번호 리스트(헤어라인 구분).
- **클로징**: 핵심 레벨(지지/저항·목표가) 요약 + 면책.

## 차트 권장

다크 배경이므로 matplotlib 차트는 `transparent=True` 로 굽고 축·라벨을 `ink`/`muted` 톤으로 지정한다.
네이티브 차트는 시리즈 색에 의미색·옐로를 1:1 지정(기본 파랑/주황 금지).
