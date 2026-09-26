# 한국어 ABSA few-shot — 정확도 깎이는 난점과 처리 규칙

> 라벨링 시 아래 패턴을 고정 참조한다. 예시는 모두 **합성 문장**(실데이터·PII 없음).

## 난점 규칙 요약

| 난점 | 예시 | 처리 규칙 |
|---|---|---|
| 부정 스코핑 | "나쁘지 않아요" | 이중부정·완곡 긍정 식별, 측면별 극성 분리 |
| 한 문장 다측면 상반 | "배송은 빠른데 포장이 엉망" | 측면별 독립 극성, overall=mixed |
| 미언급 ≠ 중립 | 별점만 있고 본문 무측면 | aspects 비움(제외) |
| **화자 귀속(CS)** | [상담원] "불편을 드려 죄송합니다" | 상담원 정형 응대는 극성 미산입. 고객 발화만 측정 |
| **존댓말 완곡부정(CS)** | "좀 그렇네요", "알겠습니다만…" | 함축 부정 탐지 → `flags.euphemistic_negation=true` |
| **체념 단답(CS)** | "됐어요", "뭐 어쩔 수 없죠" | 맥락 반전(거부·포기) 후보 → euphemistic_negation + confidence 하향 |
| **턴간 지시대명사(CS)** | "아까 그거 어떻게 됐어요" | 동일 doc 내 선행 turn 참조로 측면 복원 |
| 사르카즘·반어 | "역시 빠르네요 일주일 만에 ㅋㅋ" | `flags.sarcasm=true`, 극성 반전 검토 |

## 예시 1 — 리뷰(평면, 다측면 상반)

입력: `{"doc_id": "rv_1", "text": "화질은 좋은데 배터리가 영 별로고 가격은 적당해요", "meta": {"source": "review"}}`

출력:
```json
{
  "doc_id": "rv_1", "language": "ko", "domain": "review",
  "overall_sentiment": "mixed",
  "aspects": [
    {"aspect": "품질", "polarity": "positive", "sub_aspect": null, "evidence": "화질은 좋은데", "turn_id": null, "speaker": null, "confidence": 0.9},
    {"aspect": "품질", "polarity": "negative", "sub_aspect": null, "evidence": "배터리가 영 별로고", "turn_id": null, "speaker": null, "confidence": 0.88},
    {"aspect": "가격", "polarity": "neutral", "sub_aspect": null, "evidence": "가격은 적당해요", "turn_id": null, "speaker": null, "confidence": 0.8}
  ],
  "mentioned_aspects": ["품질", "가격"],
  "flags": {"sarcasm": false, "euphemistic_negation": false, "low_confidence": false, "critical": false}
}
```

## 예시 2 — CS 티켓(화자분리 + 완곡부정 + 상태축)

입력:
```json
{"doc_id": "tk_1", "domain": "cs", "turns": [
  {"turn_id": 1, "speaker": "customer", "text": "어제 주문한 거 아직도 안 와서요. 30분째 전화도 안 받고"},
  {"turn_id": 2, "speaker": "agent", "text": "불편을 드려 죄송합니다. 확인해 드리겠습니다"},
  {"turn_id": 3, "speaker": "customer", "text": "네 알겠습니다만… 됐어요 그냥 취소해 주세요"}
]}
```

출력 (상담원 발화는 극성 미산입, 완곡부정/체념 플래그):
```json
{
  "doc_id": "tk_1", "language": "ko", "domain": "cs",
  "overall_sentiment": "negative", "customer_final_sentiment": "negative",
  "aspects": [
    {"aspect": "배송", "polarity": "negative", "sub_aspect": null, "evidence": "아직도 안 와서요", "turn_id": 1, "speaker": "customer", "confidence": 0.92},
    {"aspect": "대기시간", "polarity": "negative", "sub_aspect": null, "evidence": "30분째 전화도 안 받고", "turn_id": 1, "speaker": "customer", "confidence": 0.9}
  ],
  "process_signals": {"resolution": "unresolved", "escalated": false},
  "mentioned_aspects": ["배송", "대기시간"],
  "flags": {"sarcasm": false, "euphemistic_negation": true, "low_confidence": false, "critical": false}
}
```

핵심: `turn_id=2`(상담원 "죄송합니다")는 **측면·극성으로 잡지 않는다**. "됐어요/알겠습니다만…"은 수락 표면이지만 CS 맥락에서 체념·취소 신호 → `euphemistic_negation=true`. 취소 미완료 → `resolution=unresolved`.

> **`resolution=unknown` 도피 금지**: `unknown`은 본문에 해결 단서가 **전무할 때만**. 추론 가능하면 `partial`/`unresolved`로. (unknown 남용은 미해결율 통계 신호를 죽인다.)
> **`reopen_count`는 단건 출력에 넣지 않는다** — 재문의 누적은 cross-doc 집계량이라 단건 라벨러가 알 수 없다(집계 레이어 ml-absa 책임).
