# CS 인텐트 분류 few-shot

> 예시는 합성 문장(PII 없음). **"왜 연락했나"만** 분류 — 감정·측면은 `aspect-sentiment` 영역.

## 규칙 요약

| 상황 | 처리 |
|---|---|
| 단일 의도 | `primary_intent` 1개, `secondary_intents=[]` |
| 복수 의도 | primary(핵심) + `secondary_intents[]` + `flags.multi_intent=true` |
| 미분류 | `primary_intent="기타"` (억지 매핑 금지) |
| 불만·감정 동반 | 인텐트는 **문의유형**으로(감정 무시). "화나서 환불" → 환불보상 |

## 예시 1 — 단일 의도

입력: 『어제 주문한 거 아직 안 왔는데 언제 오나요?』
```json
{"doc_id":"d1","language":"ko","taxonomy_version":"cs-intent-1.0","domain":"cs","primary_intent":"배송","secondary_intents":[],"evidence":"아직 안 왔는데 언제 오나요","confidence":0.92,"flags":{"multi_intent":false,"low_confidence":false}}
```

## 예시 2 — 복수 의도

입력: 『바지 2개는 취소해주시고 후드는 언제 출고되나요?』
```json
{"doc_id":"d2","language":"ko","taxonomy_version":"cs-intent-1.0","domain":"cs","primary_intent":"주문취소변경","secondary_intents":["배송"],"evidence":"바지 2개는 취소해주시고 후드는 언제 출고","confidence":0.85,"flags":{"multi_intent":true,"low_confidence":false}}
```

## 예시 3 — 감정 동반 (인텐트는 문의유형, 감정 무시)

입력: 『이거 불량이에요 진짜 화나네요 환불해주세요』
```json
{"doc_id":"d3","language":"ko","taxonomy_version":"cs-intent-1.0","domain":"cs","primary_intent":"품질불량","secondary_intents":["환불보상"],"evidence":"이거 불량이에요 환불해주세요","confidence":0.88,"flags":{"multi_intent":true,"low_confidence":false}}
```
핵심: "화나네요"(감정)는 인텐트에 **넣지 않는다** — 그건 `aspect-sentiment`. 인텐트 = 불량 신고 + 환불 요청.

## 예시 4 — 미분류

입력: 『그냥 잘 쓰고 있어요 감사합니다』
```json
{"doc_id":"d4","language":"ko","taxonomy_version":"cs-intent-1.0","domain":"cs","primary_intent":"기타","secondary_intents":[],"evidence":"잘 쓰고 있어요 감사합니다","confidence":0.6,"flags":{"multi_intent":false,"low_confidence":true}}
```
