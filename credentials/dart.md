# 금융감독원 DART Open API — 가입·키 발급 가이드

- 공식 사이트: <https://opendart.fss.or.kr>
- 발급 키: `DART_API_KEY`
- Last Verified: 2026-06-10 (dart 스킬 GUIDE에서 이전 — 실화면 재검증 시 갱신). 키 등록 절은 2026-09-30 itda-hyve 시크릿 탭으로 바꿨다(itda-work/skills#46)

## 1. 가입 조건

- Open DART 일반 회원가입으로 충분합니다 (비용 없음).
- 인증키는 신청 즉시 발급됩니다 (별도 승인 대기 없음).

## 2. 발급 절차

1. [opendart.fss.or.kr](https://opendart.fss.or.kr) 접속 → 회원가입 후 로그인
2. **오픈 API → 인증키 신청/관리** → 사용 목적 입력 후 신청 → **40자리 키 즉시 발급**
3. 발급된 40자리 영숫자 키 복사

## 3. 키 등록 — itda-hyve 시크릿 탭

| 항목 | 등록 이름 |
|---|---|
| DART 인증키 (40자리 영숫자) | `DART_API_KEY` |

발급받은 키를 **itda-hyve 앱의 시크릿 탭**에 `DART_API_KEY` 이름으로 등록합니다. Claude Code·Cowork 모두 같은 방법입니다.
DART 조회는 itda-hyve(사용자 PC 에서 도는 도우미 앱)가 대신 받아 오고, 키 값은 itda-hyve 에만 저장되어 대화에는 나오지 않습니다.
키 값을 대화창에 붙여 넣지 마세요. `.env` 같은 파일·Claude Code 설정 파일의 `env` 는 dart 스킬이 읽지 않습니다(itda-work/skills#45).

## 4. 한도·주의사항

- 첫 호출이 실패하면: ① 시크릿 탭에 등록한 키가 **40자리 영숫자**인지, 앞뒤 공백이 없는지 확인 ② 발급 직후 수 분간 미반영될 수 있습니다 — 확인·수정한 뒤 다시 요청하면 새로 받아 옵니다 ③ "활용신청 URL" 안내가 보이면 사이트에서 키 활용 상태 확인.
- 일일 호출 한도(통상 20,000회)가 있습니다 — 개인 사용에는 충분합니다.

## 5. 이 키를 쓰는 스킬

- `itda-gov/dart` — 기업 공시·재무제표 조회
- `itda-research/market-scan` — 기업 재무 보강 (없어도 웹 대체로 동작)
