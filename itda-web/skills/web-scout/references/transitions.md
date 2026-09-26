# 사다리 전이표 (정본 — grade.diagnose / TRANSITIONS 와 1:1)

| 진단코드 | 신호 | 전이 |
|---|---|---|
| `ok` | 200 + 본문 품질 OK | stop(성공) |
| `thin` / `spa_shell` | 200 + 가시 텍스트 빈약 (script 유무로 구분) | escalate(다음 단) |
| `js_redirect` | 본문 거의 없고 `location=`·meta refresh 로 다른 URL | **최종 URL 을 정적으로 재시도** (현대해상·공시실 실측: "JS 셸" 위장) |
| `install_gate` | 보안모듈/공동인증서 설치 안내 (Veraport·nProtect·AnySign·MagicLine·INISAFE·TouchEn·설치 링크) | **stop — 브라우저 에스컬레이션 금지**. 그 URL 만 폐쇄, 다른 후보로 계속. 다른 경로 없으면 `auth_state=blocked:security_module`(D) |
| `challenge` | 403/200 + WAF 챌린지 마커 | escalate(L4) — web-reader must_escalate 와 동일 |
| `auth_evidence` | 403 + 로그인 폼/안내 | stop → auth_state=required |
| `policy_block` | 403 + 명시 차단 문구 | stop(blocked) |
| `ambiguous_403` | 403 + 근거 없음 | require_confirmation |
| `auth_required` | 401 | stop → auth_state=required |
| `not_found` | 404/410 | 발견 프로브 1회 재실행 후 stop |
| `rate_limited` / `server_error` | 429 / 5xx | retry_after(예산 내 1회) → stop |
| `budget_exceeded` | 호스트 ≤40 요청 · 전체 ≤15분 · L4 ≤3회 초과 | stop(typed) |
| `browser_unavailable` | L4 필요 + 가용 브라우저 없음 | stop(typed, 폴백 없음) |
| robots.txt 403/부재 | — | 정보 없음, 등급 근거로 쓰지 않음 |
