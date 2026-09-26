---
preset: tech-vivid-dark
version: 1.0
description: >
  몰입형 다크 + 비비드 그린 글로우의 테크·미디어 톤 — 다크 캔버스에 단일 비비드 컬러와
  radial glow 모티프. Vivid Green Dark 검증 팔레트(spotify 계열) 기반.
colors:
  canvas: "#121212"
  surface: "#1F1F1F"
  ink: "#FFFFFF"
  muted: "#B3B3B3"
  primary: "#1ED760"
  accent: "#1ED760"
  hairline: "#2A2A2A"
  up: "#1ED760"
  down: "#E22134"
typography:
  display: "Arial Black"       # 라틴/숫자 run 전용(볼드 임팩트). 한글은 안전 고딕(굵게)
  body: "kr-safe-gothic"
semantic_convention: international
rounded: 0.25                 # 둥근 카드·pill 태그 감각
spacing: { margin: 0.7, gap: 0.35 }
motif: "그린 radial glow(Pillow 베이크)를 표지·전환 슬라이드에 + 그린 진행바/하이라이트 반복"
do:
  - "그린은 진행·성장·핵심 수치에 — 기능적으로 쓴다"
  - "표지·섹션 전환에만 glow, 본문은 플랫 다크"
  - "muted(#B3B3B3)로 보조 텍스트 위계"
dont:
  - "그린 외 비비드 컬러 추가(단일 보이스 붕괴)"
  - "본문 전체 glow(과용 시 싸구려 네온)"
  - "다크 위 저대비 다크 요소"
---

# Tech Vivid Dark — 몰입형 테크 문법

## Overview

다크 `#121212` 에 그린 `#1ED760` 단 하나 — 단일 비비드 컬러의 몰입형 구성.
glow 는 Pillow `radial_glow` 로 베이크해 표지·전환 슬라이드에만 깐다(본문은 플랫 유지로 대비 확보).
빅넘버·진행바·하이라이트가 그린을 독점하고, 보조 정보는 muted 그레이가 맡는다.

## 슬라이드 문법

- **표지**: 다크 + 그린 radial glow + 초대형 볼드 타이틀 + 그린 키커.
- **지표/성장**: 그린 빅넘버 콜아웃(60pt+) + 진행바 모티프 + 작은 라벨.
- **본문**: surface 카드(둥근 모서리) 그리드 — 카드당 아이콘 자리 대신 그린 포인트 도형.
- **클로징**: glow 재등장 + 핵심 메시지 한 문장.

## 차트 권장

`transparent=True` + 축·라벨 muted/ink 톤, 주 시리즈 그린·보조 시리즈 muted.
하락·경고만 `#E22134` 레드.
