# 한국은행 ECOS Open API — 가입·키 발급 가이드

- 공식 사이트: <https://ecos.bok.or.kr/api/>
- 발급 키: `ECOS_API_KEY`
- Last Verified: 2026-06-10 (ecos 스킬 GUIDE에서 이전 — 실화면 재검증 시 갱신)

## 1. 가입 조건

- ECOS 일반 회원가입으로 충분합니다 (비용 없음).
- 인증키는 신청 즉시 발급됩니다 (별도 승인 대기 없음).

## 2. 발급 절차

1. [ecos.bok.or.kr/api](https://ecos.bok.or.kr/api/) 접속 → 회원가입 후 로그인
2. **Open API → 인증키 신청** → 사용 목적·서비스명 입력 후 제출 → **즉시 발급**
3. 발급된 인증키 복사

## 3. 키 ↔ 환경변수 매핑

| 항목 | 환경변수 |
|---|---|
| ECOS 인증키 | `ECOS_API_KEY` |

키는 Claude Code 설정 파일(`~/.claude/settings.json`)의 `env` 에 넣습니다(설정을 바꾼 뒤 Claude Code 를 다시 시작). 스킬이 itda-hyve 경로를 지원하면 itda-hyve 앱의 **시크릿** 탭에 같은 이름으로 등록해도 됩니다 — 어느 경로가 되는지는 각 스킬 GUIDE 에 적혀 있습니다. `.env` 같은 파일은 스킬이 읽지 않습니다(itda-work/skills#45).

```json
{ "env": { "ECOS_API_KEY": "발급받은_키" } }
```

## 4. 한도·주의사항

- 즉시 발급되지만 **첫 호출 시 수 분간 일시적으로 미반영**될 수 있습니다 — 잠시 후 다시 시도하세요.
- "API 키가 없다"는 안내(`INFO-100`)는 키가 비어 있거나 등록 위치가 잘못된 경우입니다.
- 너무 긴 기간·세밀한 주기를 한 번에 조회하면 타임아웃될 수 있습니다 — 3~5년 단위로 나눠 조회합니다.

## 5. 이 키를 쓰는 스킬

- `itda-gov/ecos` — 한국은행 경제통계(금리·환율·GDP·CPI 등)
- `itda-research/market-scan` — 거시지표 보강 (없어도 웹 대체로 동작)
