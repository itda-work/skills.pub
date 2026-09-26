# iCloud 앱 전용 비밀번호 — 발급 가이드

- 공식 사이트: <https://account.apple.com> (Apple 계정 관리)
- 발급 키: `ICLOUD_EMAIL` + `ICLOUD_APP_PASSWORD`
- Last Verified: 2026-06-10 (email·calendar 운영 GUIDE에서 통합 — 실화면 재검증 시 갱신)

## 1. 가입 조건

- Apple 계정(iCloud 계정)이면 됩니다 (비용 없음).
- 단, **2단계 인증(2FA)이 켜져 있어야** 앱 전용 비밀번호를 발급할 수 있습니다.
  아이폰에서는 `설정 → [내 이름] → 로그인 및 보안 → 2단계 인증`에서 확인·활성화합니다.

## 2. 발급 절차

1. 웹브라우저에서 [account.apple.com](https://account.apple.com) 로그인
2. **로그인 및 보안 → 앱 전용 비밀번호** 선택
3. **앱 전용 비밀번호 생성** → 이름 입력(예: `itda-skills`) → 생성
4. 화면에 표시된 16자리 비밀번호(`xxxx-xxxx-xxxx-xxxx`)를 **바로 복사** — 다시 볼 수 없습니다

## 3. 키 ↔ 환경변수 매핑

| 항목 | 환경변수 |
|---|---|
| iCloud 이메일 주소 | `ICLOUD_EMAIL` |
| 16자리 앱 전용 비밀번호 | `ICLOUD_APP_PASSWORD` |

```dotenv
ICLOUD_EMAIL=you@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

## 4. 한도·주의사항

- 앞뒤 하이픈 포함/제외 모두 동작하지만, **발급 화면에 보인 그대로** 넣는 것을 권장합니다.
- **하나의 앱 전용 비밀번호를 메일·캘린더가 공용**합니다 — itda-email용으로 발급했다면 calendar에서 재사용하면 됩니다(추가 발급 불필요).
- 분실 시 같은 메뉴에서 기존 항목을 삭제하고 새로 생성하세요.
- Apple 계정 비밀번호를 변경하면 기존 앱 전용 비밀번호가 모두 무효화됩니다 — 재발급이 필요합니다.

## 5. 이 키를 쓰는 스킬

- `itda-work/email` — 아이클라우드 메일 읽기·발송
- `itda-work/calendar` — 아이클라우드 캘린더 (CalDAV)
