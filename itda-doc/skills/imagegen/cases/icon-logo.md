# 아이콘·로고·UI 시안 (icon-logo)

상태: draft (r2까지 Claude 1차 통과 — 마스터 판정 대기)
최종 실측: 2026-06-13 (codex-cli 0.137.0)

## 용도

앱 아이콘, 심볼, 단순 도형 기반 시안. "앱 아이콘 시안 몇 개", "로고 아이디어" 류 요청.
**텍스트 아티팩트 차단이 이 케이스의 존재 이유** — 로고 요청에 브랜드명이 섞이면
모델이 깨진 글자를 그려 넣으려 든다. 글자는 후가공으로, 이미지는 심볼만.

## 프롬프트 템플릿

**프롬프트 A. 플랫 벡터 — 심볼 시안용**

```
A single app icon symbol representing {개념}.
Flat vector style, bold simple geometry, smooth curves.
Centered composition, the symbol fills about 70% of the canvas.
Maximum {2|3} colors: {팔레트 — 예: honey yellow symbol on deep charcoal}.
Plain solid background, no gradients on background, no border, no bevel.
Square 1024x1024. Absolutely no text, no letters, no typography, no wordmark,
no watermark — symbol only.
```

**프롬프트 B. 글로시 3D — 앱스토어풍 고급 시안, Threads 바이럴 군집**

```
A premium glossy 3D app icon: {개념} symbol on a rounded-square iOS-style tile.
Soft studio lighting, subtle reflections and inner glow, smooth gradients
({팔레트 그래디언트}), octane render, highly detailed.
Centered, slight 3D depth, dark neutral backdrop.
Square 1024x1024. Absolutely no text, no letters, no typography, no wordmark.
```

슬롯: `{개념}` `{2|3}` `{팔레트}`.
브랜드명은 `{개념}` 에 넣지 않는다 — 이름 대신 **의미**(예: "벌집 + 자동화")를 넣을 것.
시안 N개 요청 시 같은 템플릿에 팔레트/기하 변형만 바꿔 병렬 생성.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| I1 | 축소 식별성 | 64px 로 줄여 봐도 무엇인지 식별되는 단순 기하인가 |
| I2 | 배경 단색 | 배경이 완전 단색인가 (마스킹·후가공 용이) |
| I3 | 글자 0 | 글자·글자 비슷한 획이 하나도 없는가 (C2 강화판) |

## 실측 기록

### r2 — 2026-06-13 (codex-cli 0.137.0) — 변형 B(글로시 3D) 첫 측정

- 슬롯: r1 과 동일 개념(벌집+기어) / 변형 B / honey amber gradient
- 결과: 1024×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ✅ C6 ✅ / I1 ✅ I2 ✅ I3 ✅(글자 0 유지)
- 썸네일: `measurements/icon-logo-r2.jpg`
- 교훈: 글로시 3D 변형이 앱스토어 시안급 품질로 — 반사·내부 발광·유리질 질감 전부 반영.
  타일 표면에 벌집 패턴이 자동 부가됨(개념 모티프 반복) — 과하면 "plain tile surface" 지정.
  플랫 벡터(A)와 글로시 3D(B)는 용도가 다름: 심볼 탐색은 A, 최종 시안 프레젠테이션은 B.

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 개념 "육각 벌집 셀 + 기어 모티프 융합(자동화 하이브)" / 2색 / honey yellow on deep charcoal
- 결과: 1024×1024 ✅
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅(중앙·캔버스 ~70%) C5 ✅ / I1 ✅(64px 축소에도 식별)
  I2 ✅(완전 단색) I3 ✅(글자 0)
- 썸네일: `measurements/icon-logo-r1.jpg`
- 교훈: "Absolutely no text, no letters, no typography, no wordmark" 강화 문구 +
  브랜드명 대신 의미 서술("개념"에 이름을 넣지 않음) 조합으로 글자 아티팩트 0 달성.
  "Maximum 2 colors" 가 정확히 2색으로 지켜짐 — 색 수 제한 지시가 동작함을 실측 확인.

## 실패 변형 (안티프롬프트)

(없음 — 실측과 함께 누적. 브랜드명 포함 시 글자 아티팩트 가설은 미검증)
