# 상품화 피규어 (figurine)

상태: draft (r1 Claude 1차 통과 — 마스터 판정 대기)
최종 실측: 2026-06-13 (codex-cli 0.137.0)

## 용도

인물/캐릭터를 상품화 피규어 렌더로 만드는 케이스. Threads 최다 바이럴 유형
(카리나 액션 피규어, 나노바나나 피규어 컷). "피규어로 만들어줘", "Funko 스타일로" 류 요청.
사진→피규어 변환은 SKILL 패턴 3(`inputs` 참조, 확인 단계)으로 시도할 수 있으나 이 카드로는 아직 실측하지 않았다(`_PATTERNS.md` §6 — 텍스트형만 실측). 결과는 실측 기록에 남긴다.

## 프롬프트 템플릿

```
A 1/7 scale commercialized collectible figure of {피사체 명세 — 절 단위},
in a realistic style and environment.
The figure stands on a {round transparent acrylic} base, placed on a {computer desk}.
Studio product photography: clean bright background, soft studio lighting,
the figure's paint texture, sculpt details and material seams vividly visible.
Shot on 85mm lens, f/2.8, shallow depth of field.
Highly detailed, photorealistic. {Square 1024x1024|Portrait 1024x1536}.
No text, no letters, no watermark.
```

슬롯: `{피사체 명세}` `{받침대}` `{배치 장소}` `{비율}`.
변형: Funko 풍은 첫 줄을 `A detailed 3D render of a chibi Funko Pop style figure of ...` 로.
패키지 박스 동반 연출(텍스트 포함)은 미실측 — 라운드 3 후보(`_PATTERNS.md` §6 트렌드 1위).

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| F1 | 피규어 질감 | 도색·사출 질감(살짝 광택, 파팅라인 느낌)이 "실물 피규어"로 읽히는가 |
| F2 | 제품샷 연출 | 받침대·심도·스튜디오 조명이 상품 사진처럼 보이는가 |

## 실측 기록

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 피사체 "둥근 안경에 네이비 후디, 빛나는 미니 노트북을 든 쾌활한 한국인 사무직
  캐릭터" / round transparent acrylic base / computer desk(모니터 흐림) / Square 1024x1024
- 결과: 1254×1254 ⚠️ — 정사각 픽셀 드리프트(2번째 관측, character r2 와 동일 패턴).
  비율 1:1 유지. 전체 실측 통계: 정사각 지정 5회 중 3회 정확·2회 1254 드리프트(간헐적),
  가로/세로 방향 지정은 7/7 정확.
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ⚠️(비율 ✅·픽셀 ⚠️) C6 ✅ /
  F1 ✅(PVC 도색 광택·사출 질감이 실물 피규어로 읽힘) F2 ✅(아크릴 받침·심도·스튜디오 조명)
- 썸네일: `measurements/figurine-r1.jpg`
- 교훈: "1/7 scale commercialized figure" + 아크릴 받침대 + "85mm lens, f/2.8" 조합이
  첫 시도에 상품 사진급 — Threads 바이럴 패턴(`_PATTERNS.md` §3)의 재현성 확인.
  치비 비율이 자연스럽게 섞임 — 리얼 비율 원하면 "realistic body proportions" 추가 검증 필요.

## 실패 변형 (안티프롬프트)

(없음 — 실측과 함께 누적)
