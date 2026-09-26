# Ground Check Cell 양식

Task 1-A 에서 셀(핵심 항목 × 비교 대상의 1칸)마다 다음 3-tuple 을 기록한다.

## 단일 셀 양식

```
[셀 ID] 비교대상=<X> / 항목=<Y>

검증 질문: <이 셀에 대해 무엇을 확인해야 하는가?>

사실 한 줄 : <확인된 사실. hedge 표현 금지. URL 없는 주장 금지>
출처 URL  : <1차 소스 공식 도메인의 정확한 URL>
확인 시각 : <YYYY-MM-DD (ISO-8601)>

본문 인용 (선택):
<출처 본문에서 해당 사실이 명시된 1-2 문장 직접 인용>
```

## 미확인 셀 양식

```
[셀 ID] 비교대상=<X> / 항목=<Y>

검증 질문: <이 셀에 대해 무엇을 확인해야 하는가?>

상태      : 미확인
사유      : <WebFetch+web-reader 모두 실패 / 1차 소스 부재 / 명시 정보 없음 등>
시도한 URL: <후보 URL 리스트>
확인 시각 : <YYYY-MM-DD>
```

## 작성 규칙

- **사실 한 줄**: 수치·날짜·고유명사를 포함한 검증 가능한 단일 문장. 길이 200자 이내.
- **출처 URL**: 짧은 도메인 루트 URL이 아닌 **정확한 페이지 URL**. 리다이렉트 후 최종 URL.
- **확인 시각**: 본문을 실제로 연 날짜. ISO-8601 형식 (예: `2026-05-12`).
- **본문 인용** (권장): 사실 추출 근거를 본문에서 직접 가져온다. 의역 금지.
- **검증 질문**은 셀별 1개 이상. "X는 Y를 지원하는가?", "X의 가격 정책은 무엇인가?" 형태.

## 예시 (Public Web — Category A)

```
[CELL-A-3] 비교대상=Claude Pro / 항목=월간 메시지 한도

검증 질문: Claude Pro 플랜의 월간 메시지 한도는 공식적으로 얼마인가?

사실 한 줄 : Claude Pro 플랜은 사용량 한도가 무료 플랜의 5배이며 5시간 단위로 갱신된다.
출처 URL  : https://support.anthropic.com/en/articles/8324991-about-claude-pro-usage
확인 시각 : 2026-05-12

본문 인용:
"Pro plan includes approximately 5x more usage than the Free plan,
 with limits resetting every 5 hours."
```

## 미확인 예시

```
[CELL-A-7] 비교대상=Claude Cowork / 항목=동시 세션 수 한도

검증 질문: Cowork 플랜에서 동시에 실행 가능한 세션 수는 몇 개인가?

상태      : 미확인
사유      : anthropic.com / support.anthropic.com / docs.claude.com 에서
             동시 세션 수 명시 페이지를 찾지 못함. WebFetch + web-reader 모두 미발견.
시도한 URL:
  - https://www.anthropic.com/claude-code
  - https://docs.claude.com/en/docs/claude-code/overview
  - https://support.anthropic.com/en/collections/4078534-claude-code
확인 시각 : 2026-05-12
```
