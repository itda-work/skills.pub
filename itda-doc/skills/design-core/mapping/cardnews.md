# 매체 매핑 — design-core v2 → 카드뉴스 이미지 (구조 스텁)

> **상태: 후속 SPEC (미구현)**. SPEC-DESIGN-CORE-001 은 1차 범위를 PPTX 로 한정했고, 카드뉴스 어댑터는 구조만 예약한다.

## 의도

design-core 토큰을 정사각/세로형 카드뉴스 이미지(인스타·블로그용)로 렌더한다. PPTX 와 달리 **Pillow/SVG 레이아웃 합성**(텍스트+도형+모티프)이 주 경로다.

## 예상 매핑 (확정 아님)

| v2 토큰 | 카드뉴스 적용(예상) |
|---|---|
| `color.*` | Pillow 배경·도형·텍스트 색 (hex 1:1, 매체 중립) |
| `font.*` | PIL ImageFont — 한글은 `constraints` fallback 폰트 직접 로드(LibreOffice 비경유라 가드 규칙이 다름) |
| `space`/`layout.three_zone` | 캔버스 분할(헤더/본문/푸터 밴드) |
| `motif` | 반복 도형 컴포지트 |
| `radius.base` | 둥근 사각 카드 — px 직접(PPTX 비율 제약 없음) |
| `constraints.cardnews` | (신설 예정) 세로형 안전영역·해상도 프로필 |

## 후속 작업 포인터

- 카드뉴스 전용 `constraints.cardnews` 프로필(해상도·안전영역) 정의.
- Pillow 합성 렌더러 + 검증(텍스트 오버플로·대비).
