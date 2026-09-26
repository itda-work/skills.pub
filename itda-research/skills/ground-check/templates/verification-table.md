# Verification Table 양식

Task 2-A 독립 검증 라운드 결과를 다음 표로 기록한다.

## 표 헤더

```
| 셀 ID | 주장 | 새 검색어 | 새 URL (원본과 달라야 함) | 결과 | 비고 |
| ----- | ---- | --------- | ------------------------- | ---- | ---- |
```

## 결과 컬럼 값

| 값 | 의미 |
|----|------|
| **일치** | 새 1차 소스에서 동일 사실 재발견. 본 셀 PASS. |
| **불일치** | 새 1차 소스에서 다른 사실 발견. 본 셀 FAIL. 어느 쪽이 맞는지 결정 필요. |
| **출처 부족** | 새 검색어로 1차 소스를 찾지 못함. 본 셀 FAIL. |
| **무효** | 새 URL이 원본과 동일하거나 1차 소스가 아님. 검증 무효. 재시도 필요. |

## 라운드 헤더 양식

```markdown
## 검증 라운드 N (YYYY-MM-DD)

대상 산출물: <산출물 식별자 또는 파일 경로>
검증자: 본 세션 (Claude 내부 자율 분기)

### 결과 표

| 셀 ID | 주장 | 새 검색어 | 새 URL | 결과 | 비고 |
| ----- | ---- | --------- | ------- | ---- | ---- |
| CELL-A-1 | Claude Code는 macOS·Linux·Windows를 지원한다 | "Claude Code system requirements", site:docs.claude.com | https://docs.claude.com/en/docs/claude-code/setup | 일치 | macOS/Linux/Windows(WSL) 명시 |
| CELL-A-3 | Claude Pro 한도는 무료의 5배 | "Claude Pro usage limit", site:anthropic.com | https://www.anthropic.com/pricing | 출처 부족 | pricing 페이지에 5배 명시 없음 |
| CELL-A-5 | Cowork는 동시 세션 N개 허용 | "Claude Cowork concurrent sessions" | (원본과 동일 URL) | 무효 | 다른 URL 미발견 |

### FAIL 항목 처리

- **CELL-A-3** (출처 부족) → 본 세션이 다른 1차 소스 후보 재탐색
- **CELL-A-5** (무효) → 새 검색어 2개 추가 생성 후 라운드 N+1
```

## 자동 FAIL 체크리스트

검증 라운드 시작 전 다음을 점검한다. 하나라도 해당하면 즉시 FAIL.

- [ ] 산출물 본문에 hedge 표현이 포함되어 있는가? → FAIL
- [ ] URL이 명시되지 않은 주장이 있는가? → FAIL
- [ ] "새 URL" 컬럼이 원본 URL과 동일한가? → 검증 무효, 재검색
- [ ] "새 URL" 도메인이 1차 소스(공식 도메인) 가 아닌가? → 검증 무효

## 라운드 종료 판정

- **모든 셀 일치** → 산출물 PASS, Task 3 진행
- **일부 FAIL** → 본 세션이 사유 + 수정안 작성 → 라운드 N+1
- **3 라운드 후에도 FAIL** → 해당 셀 "미확인" 강등 → Task 3 진행 (강등 셀 제외)

## 검증자 책임

- 산출물의 결론·논리를 신뢰하지 않는다
- 산출물에 적힌 URL을 재사용하지 않는다
- 동일 사실 검증을 위해 **다른 1차 소스 URL**을 새로 찾는다
- 원본 검색어를 그대로 재사용하지 않는다 (다른 키워드 조합 사용)
- hedge 표현은 출처 명시 + 1차 소스 인용 형태가 아니면 모두 FAIL
