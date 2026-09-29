# 제품 카탈로그 (product-catalog)

상태: draft (r2 구체화까지 Claude 1차 통과 — 마스터 판정 대기)
최종 실측: 2026-06-13 (codex-cli 0.137.0)

## 용도

제품 카탈로그/상세페이지/쇼핑몰용 상품 사진. "제품 사진 만들어줘", "카탈로그 컷",
"화이트 배경 상품샷" 류 요청. 마스터 요청으로 신설(2026-06-13, r2 피드백).
수집 패턴 근거: tloghost 나노바나나 40선의 제품 카테고리(향수병 자연광·명품 시계
드라마틱 조명·푸드포토 얕은 심도), pxz.ai product lifestyle 패턴.

## 프롬프트 템플릿

**프롬프트 A. 팩샷 — 카탈로그 기본**

```
Professional product catalog photograph of {제품 명세 — 절 단위: 재질/색/형태}.
Placed on {받침/표면 — 예: a light stone pedestal | a clean white surface}.
Clean seamless {배경색 — 예: light gray} studio background.
Lighting: soft diffused studio lighting with gentle shadow falloff,
subtle reflection, crisp product edges, true-to-material texture.
Shot on 85mm lens, f/8 — entire product in sharp focus.
Photorealistic, commercial packshot quality, highly detailed.
{Square 1024x1024|Landscape 1536x1024}. No text, no letters, no watermark.
```

**프롬프트 B. 라이프스타일 컷 — 사용 맥락 연출**

```
Professional lifestyle product photograph of {제품 명세}, {사용 장면 — 절 단위.
예: on a wooden cafe table beside a linen napkin, morning light}.
Natural soft lighting with gentle shadows, rule of thirds composition,
the product in sharp focus with a slightly blurred background.
Shot on 50mm lens, f/2.8, shallow depth of field, photorealistic,
true-to-material texture, subtle film grain.
{Landscape 1536x1024|Portrait 1024x1536}. No text, no letters, no watermark.
```

슬롯: `{제품 명세}` `{받침/표면}` `{배경색}` `{사용 장면}` `{비율}`.
제품 명세는 재질·색·마감(matte/glossy)·형태를 절 단위로 — 재질 표현이 카탈로그 품질의 핵심.
브랜드명·라벨 텍스트는 넣지 않는다(후가공) — 정확한 표기는 오차 0 계약이라 `poster.md` 경로 B 와 같은 이유다.

### C. 카탈로그 세트 (멀티앵글 — 상세페이지용)

카탈로그는 단일 컷이 아니라 **세트**다. `{제품 명세}` 블록을 **글자 그대로 고정**하고
(캐릭터 명세 블록 전략의 제품판) 앵글/연출 슬롯만 바꿔 병렬 생성한다:

| 컷 | 변형 포인트 |
|---|---|
| 정면 팩샷 | 템플릿 A 그대로 |
| 45도 컷 | `three-quarter angle view from slightly above` 추가 |
| 디테일 클로즈업 | `extreme close-up of {디테일 부위}, macro lens, the material texture filling the frame` |
| 라이프스타일 | 템플릿 B |

같은 세트는 배경색·조명 문구도 고정해 톤을 통일한다.

### D. 실존 제품 참조 (참조 이미지 입력)

실제 제품 사진이 있으면 `agent_run` 의 `inputs` 로 첨부하고(SKILL.md 핵심 패턴 3 — 확인 단계가 붙는다)
템플릿 A·B 앞에 영어 한 줄을 붙인다:

```
Use the attached reference image as the exact same product: keep its material, color, proportions and details.
```

충실도는 실측 기록 참고(r2 — 재질·구성·색 충실, 실루엣 비례는 다소 변형). r2 의 프롬프트 전문은 남아 있지 않다 — 다음 실측 때 기록한다.

## 품질 체크리스트

공통 C1~C6 (`_SCHEMA.md`) +

| # | 항목 | 판정 기준 |
|---|---|---|
| G1 | 재질 충실 | 지정 재질(매트/유광/유리/패브릭)의 질감이 실물처럼 읽히는가 |
| G2 | 상업 품질 | 그림자·반사·엣지가 쇼핑몰 상세페이지에 바로 쓸 수준인가 |
| G3 | 형태 정확 | 제품 형태가 왜곡 없이 대칭/직선이 유지되는가 |

## 실측 기록

### r2 — 2026-06-13 (codex-cli 0.137.0) — 세트·재질 확장·참조 입력 (구체화 라운드)

5장 병렬: 세트 3컷(45도·디테일·라이프스타일, 명세/배경/조명 고정) + 유리 세럼병 + 참조 테스트.

- **세트 일관성**: 제품 정체성(매트 블랙 세라믹·대나무 뚜껑·색)은 4컷 전체 유지 ✅,
  단 실루엣 비례가 컷마다 미세하게 다름(r1 둥근 텀블러 ↔ 45도 컷 컵형) —
  **텍스트 명세만으로는 동일 실루엣 보장 불가**. 엄밀한 세트는 참조 입력(D) 경유.
- 45도 컷: 1024×1024 ✅. "three-quarter angle from slightly above" 가 약간 위에서 본
  정면에 가깝게 나옴(부분 반영). 돌 받침 연출 자동 변형(블록형).
- 디테일 클로즈업: 1024×1024 ✅. 매크로 질감(대나무 결·매트 세라믹) 프레임 충만 — 모범.
- 라이프스타일(B 첫 실측): 1536×1024 ✅. 카페 테이블·리넨·비스코티·창가 아침광 —
  rule of thirds·심도 정확. G1 ✅ G2 ✅.
- 유리 세럼병(재질 확장): 1024×1024 ✅. 프로스티드 앰버 유리의 투과·굴절·반사 충실 —
  유리 재질도 "true-to-material + 재질 명명" 기법이 유효. "no label" 로 글자 0.
- **참조 입력(D 첫 실측, `codex exec -i`)**: r1 팩샷 PNG 첨부 → 순백 배경 정면 팩샷 변환
  **성공**. 재질·구성·색 충실, 실루엣은 약간 길쭉해짐(중간~높은 충실도). 출력 1122×1402
  (참조 영향으로 추정되는 비정형 해상도). → `_PATTERNS.md` §5 가설 검증 완료.
- 썸네일: `measurements/catalog-{45deg,detail,lifestyle,cosmetic,ref}-r2.jpg`
- 정사각 통계 갱신: 9회 중 6 정확 / 3 드리프트.

### r1 — 2026-06-13 (codex-cli 0.137.0)

- 슬롯: 제품 "매트 블랙 세라믹 텀블러 + 대나무 뚜껑" / light stone pedestal /
  light gray seamless / 템플릿 A(팩샷) / Square 1024x1024
- 결과: 1254×1254 ⚠️ — 정사각 픽셀 드리프트 3번째 관측(통계: 정사각 6회 중 정확 3·드리프트 3,
  가로/세로 방향 지정은 11/11 정확). 비율 1:1 유지.
- 판정: C1 ✅ C2 ✅ C3 ✅ C4 ✅ C5 ⚠️(비율 ✅·픽셀 ⚠️) C6 ✅ /
  G1 ✅(매트 세라믹·대나무 결 가독) G2 ✅(상세페이지 즉시 사용 수준) G3 ✅(대칭·직선 유지)
- 썸네일: `measurements/product-catalog-r1.jpg`
- 교훈: "true-to-material texture — the {재질} clearly readable" 식으로 재질을
  콕 집어 명명하는 것이 유효. 팩샷은 f/8(전체 선명)·라이프스타일은 f/2.8(심도) 구분 유지.

## 실패 변형 (안티프롬프트)

- **세트를 텍스트 명세만으로 생성** (r2): 재질·색은 유지되나 실루엣 비례가 컷마다
  달라짐 — 같은 제품의 멀티앵글 세트는 1컷을 먼저 확정한 뒤 그 이미지를 `inputs` 참조로
  넘겨(SKILL 패턴 3 — 확인 단계) 나머지 컷을 만드는 **앵커 컷 방식**이 안전.
