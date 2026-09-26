# 토큰 계층 (opendesign 4계층 + C-extension allowlist)

design-core 의 모든 토큰은 **누가 값을 정하고, 브랜드가 생략하면 어떻게 되는가**에 따라 정확히 한 계층에 속한다(기축: opendesign `token-schema.ts`). SPEC-DESIGN-CORE-001 §5.1.

## 4계층 + 확장

| 계층 | 정의 | 생략 시 | 우리 토큰 |
|---|---|---|---|
| **A1-identity** | 필수. 토큰이 *곧* 브랜드. 어떤 fallback 도 대체 불가. | ERROR | `color.{bg,surface,fg,muted,primary,accent,border}`, `font.{display,body}` |
| **A1-structure** | 필수. 구조적 결정(타입 스케일·그리드·리듬)으로 크로스브랜드 기본값이 없다 — 브랜드마다 자체 정의. | ERROR(해당 섹션 사용 시) | `space`, `type-scale`, `layout` |
| **A2** | 최종 산출엔 필수지만 `defaults` 에 합리적 fallback 존재. derive 단계가 inline. | fallback 주입 | `semantic.{up,down}`, `radius`, `accent-on` |
| **B-slot** | 선택 슬롯. 크로스브랜드 일관성용이나, 풍부한 tier 없는 브랜드는 상위 sibling 에 `var()` alias. | 상위 alias | `surface_2→surface`, `fg_2→fg`, `border_soft→border` |
| **C-extension** | 브랜드 전용. allowlist 로 관리. 범용 컴포넌트는 참조 금지. | (없음) | `motif`, `editorial`, `kicker_style`, `chart_hint` |

## 왜 A2 는 "선택"이 아니라 "필수+fallback"인가

산출물은 에이전트가 한 브랜드의 토큰 블록을 단일 문맥에 붙여 생성한다. 전역 defaults 스타일시트로부터의 런타임 cascade 가 없으므로, `var(--target)` 이 비면 규칙이 통째로 드롭된다. 그래서 fallback 은 derive 단계가 **inline** 하되, 계약은 "모든 산출에 A1+A2+B-slot 선언"을 요구한다. design-core 는 `design_core._inject_defaults()` 가 이 역할을 한다.

## 왜 C-extension 은 allowlist 인가

allowlist 없이는 브랜드가 임의 토큰명을 흘려 다른 브랜드 컴포넌트가 조용히 놓친다. allowlist 는 새 브랜드 전용 이름이 등장할 때 의도적 리뷰를 강제하고, **C→B-slot→A2 승격 경로**를 명시한다(≥2 브랜드가 같은 이름을 필요로 하면 승격).

현재 allowlist(`validate.py` `KNOWN_TOP_KEYS` + `C_EXTENSION_ALLOWLIST`): `motif`, `kicker_style`, `chart_hint` (+ 표준 키 `editorial` 등). 미등록 최상위 키는 검증기가 advisory 로 표면화한다.

## 검증

`scripts/validate.py` 가 본 계약을 강제한다:
- A1-identity 색·폰트 누락 → **ERROR**
- A1 색 비-hex → **ERROR**, B-slot/확장 비-hex → advisory
- A2 의미색 누락 → advisory(international 컨벤션 권장), 비-hex → ERROR
- C-extension allowlist 외 최상위 키 → advisory

## 매체 무관 vs 매체 종속

| 성격 | 토큰 | 비고 |
|---|---|---|
| 완전 매체 중립 | `color.*`, `space`, `radius`, `motif`, `editorial` | hex·비율·문장 — 모든 매체 동일 |
| 부분 종속 | `font.*` | 라틴 stack 은 중립, 한글은 매체별 CJK 가드(`constraints`) |
| 매체 프로필 | `constraints.<media>` | 매체별 표현 제약 선언(렌더는 어댑터) |
