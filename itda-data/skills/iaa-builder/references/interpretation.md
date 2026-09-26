# κ 해석 기준 (Landis-Koch 1977)

Cohen's / Fleiss' κ 값의 등급 해석. `iaa.interpret()`가 이 표를 코드로 강제한다.

| κ 범위 | 등급(interpretation) | 의미 |
|--------|------|------|
| κ < 0.00 | poor | 우연보다 못함 — 분류 정의가 무너졌거나 라벨러 오해 |
| 0.00–0.20 | slight | 거의 우연 수준 — 운영 불가 |
| 0.21–0.40 | fair | 약함 — 정의 대폭 보강 필요 |
| 0.41–0.60 | moderate | 보통 — 경계 카테고리 재정의 후 재측정 (졸업 미달) |
| 0.61–0.80 | substantial | 견고 — 운영 졸업 후보 |
| 0.81–1.00 | almost perfect | 매우 견고 |

> 경계는 닫힌 상한이다 — κ=0.60은 `moderate`, `substantial`은 κ=0.61부터(`iaa.interpret`가 `kappa <= upper`로 강제).

## 졸업 게이트 (graduation)

- 기본 합격선 `threshold = 0.61` (= substantial 하한). `iaa.py <sheet.csv> <threshold>` 로 조정. κ=0.60(moderate)은 졸업 미달이라, 합격선과 등급이 자기일관된다.
- **합격선을 낮추지 말고 정의를 고친다**: κ가 낮으면 라벨러를 탓하기 전에 분류 카테고리 *정의*를 보강하고 재라벨한다.
- `per_category_kappa` 가 낮은(< threshold) 카테고리 = `ambiguous_categories`. 이들이 우선 재정의 대상. **2인(Cohen) 경로 한정** — 3인+(Fleiss)는 카테고리별 분해를 산출하지 않아 빈 배열.
- `disagreements` 의 실제 불일치 사례를 보고 경계 규칙을 다듬는다.

## 왜 IAA가 졸업 게이트인가

CS 분류축(`aspect-sentiment` 측면, `cs-intent` 인텐트)을 운영에 쓰려면 "이 카테고리가 사람마다 일관되게 라벨되는가"를 **측정**해야 한다. 측정 없는 분류축은 검증 불가능한 라벨만 누적하는 *벽장 안전망*이다. 새 분류축(원인·긴급도 등) 추가 요청은 이 게이트(골드셋 + 2인 + κ)를 먼저 통과해야 한다.

## 주의

- κ는 **명목(nominal) 단일 라벨** 기준. 다중 라벨(secondary_intents 등)은 primary만으로 측정하거나 라벨별 이진 κ로 분해한다.
- κ는 카테고리 분포에 민감(prevalence/bias paradox): 한 카테고리가 압도적이면 po가 높아도 κ가 낮을 수 있다. `po`·`pe`를 함께 보고한다.
- 샘플 대표성(층화 샘플링)이 무너지면 κ가 높아도 운영 일반화는 보장되지 않는다.
