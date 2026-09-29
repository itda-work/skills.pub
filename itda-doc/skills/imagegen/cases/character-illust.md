# 캐릭터·일러스트 (character-illust)

상태: draft (r2까지 Claude 1차 통과 — 마스터 판정 대기)
최종 실측: 2026-06-13 (codex-cli 0.137.0)

## 용도

마스코트, 스티커풍 캐릭터 일러스트. "마스코트 만들어줘", "귀여운 캐릭터" 류 요청.
**스타일 일관성**이 이 케이스의 핵심 — 같은 캐릭터를 여러 장 만들 때 매번 다른
화풍/체형이 나오는 것이 대표 실패. (이모티콘 감정 세트 한 벌은 이 카드의 범위 밖이다)

## 프롬프트 템플릿

**프롬프트 A. 스티커풍 2D**

```
Cute mascot character: {캐릭터 명세 블록}.
Sticker-style illustration, clean thick outlines, soft cel shading, rounded shapes.
Full body, centered, facing {front|three-quarter view}, {표정/동작}.
Plain solid {배경색} background.
Square 1024x1024. No text, no letters, no watermark, no signature.
```

**프롬프트 B. 픽사풍 3D — 고급 마스코트, Threads 바이럴 군집**

```
Adorable 3D character render: {캐릭터 명세 블록}.
Pixar-style smooth polished rendering, slightly exaggerated expressive features,
soft studio lighting with gentle rim light, glossy eyes, subtle fuzzy texture details,
octane render, professional animation-quality lighting, warm atmosphere.
Full body, centered, {표정/동작}. Clean soft-gradient {배경색} backdrop.
Square 1024x1024. No text, no letters, no watermark.
```

슬롯: `{캐릭터 명세 블록}` `{front|three-quarter view}` `{표정/동작}` `{배경색}`.

**일관성 규칙**: `{캐릭터 명세 블록}` 은 한 번 확정하면 **글자 그대로 재사용**한다
(종·체형·색·복장·소품을 3~5개 절로 고정. 예: "a round honeybee with oversized eyes,
tiny wings, golden yellow body with brown stripes, wearing a small blue scarf").
여러 장 생성 시 명세 블록은 고정하고 `{표정/동작}` 만 바꾼다.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| K1 | 신체 정상 | 손가락·팔다리 수, 눈 위치 등 구조 왜곡이 없는가 |
| K2 | 명세 일치 | 캐릭터 명세 블록의 색·복장·소품이 전부 반영됐는가 |
| K3 | 배경 단색 | 스티커 후가공이 가능한 단색 배경인가 |

## 실측 기록

### r2 — 2026-06-13 (codex-cli 0.137.0) — 변형 B(픽사 3D) + 명세 블록 고정 검증

- 슬롯: 명세 블록 r1 과 **글자 그대로 동일**(일관성 전략 검증) / 변형 B / waving / cream
- 결과: 1254×1254 ⚠️ — "Square 1024x1024" 지정에도 codex 기본 정사각(1254)으로 드리프트.
  비율은 1:1 유지라 실용상 무해.
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ⚠️(비율 ✅·픽셀 ⚠️) C6 ✅ / K1 ✅ K2 ✅(명세 5요소 유지)
  K3 ✅(소프트 그래디언트)
- 썸네일: `measurements/character-illust-r2.jpg`
- 교훈:
  - **명세 블록 고정 전략 1차 검증**: 스티커풍(r1)→픽사 3D(r2)로 스타일을 바꿔도
    종/체형/색/목도리가 동일하게 유지됨. 다장 세트 생성의 기반 확보.
  - "fuzzy texture details, rim light" 반영 — 털 질감까지 렌더됨.
  - **비율 강제력의 한계 발견**: 가로/세로 방향은 정확하나 정사각 픽셀 크기는 기본값
    (1254)으로 드리프트 가능. 정확 픽셀이 필요하면 후처리(imagekit resize).

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 명세 블록 "a round honeybee with oversized friendly eyes, tiny translucent wings,
  golden yellow body with brown stripes, wearing a small blue scarf" / front /
  cheerfully waving one arm / cream
- 결과: 1024×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ / K1 ✅(신체 구조 정상) K2 ✅(명세 5요소 전부 반영:
  둥근 체형·왕눈·반투명 날개·노랑/갈색 줄무늬·파란 목도리) K3 ✅(크림 단색)
- 썸네일: `measurements/character-illust-r1.jpg`
- 교훈: "Sticker-style" 문구가 흰색 스티커 외곽 테두리를 자동 생성 — 스티커 용도면 그대로
  쓰고, 테두리가 불필요하면 "no sticker border outline" 추가 필요. 명세 블록 고정 전략의
  다장 일관성 효과는 라운드 2(동일 명세 + 표정만 변경 N장)에서 검증 예정.

## 실패 변형 (안티프롬프트)

(없음 — 실측과 함께 누적. 명세 블록 일부 생략 시 일관성 붕괴 가설은 미검증)
